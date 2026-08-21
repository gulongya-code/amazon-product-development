"""End-to-end organic Buyer Need discovery pilot orchestration V0.1."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedCandidateBuilder,
    BuyerNeedCandidateStatus,
    BuyerNeedEvidence,
    BuyerNeedType,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.buyer_need_map import (
    BuyerNeedMapBuilderV0_1,
    BuyerNeedMapRequest,
    BuyerNeedMapSnapshot,
    EvidencePopulationStatus,
)
from amazon_product_intelligence.category_product_map import (
    CategoryScopeType,
    build_category_scope,
    unknown_analysis_window,
)
from amazon_product_intelligence.contracts import PresenceStatus, deterministic_id
from amazon_product_intelligence.demand_intelligence import (
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
)
from amazon_product_intelligence.normalization import normalize_keyword_text
from amazon_product_intelligence.semantic_clustering import (
    SemanticClusterBuilder,
    SemanticClusteringResult,
)

from .capture import CapturedXiYouOperation, XiYouLiveCaptureClient
from .models import (
    ProviderCallAudit,
    ProviderCallStatus,
    QueryOrigin,
    build_call_audit,
)
from .runner import (
    CohortSelection,
    CreditPlan,
    OrganicKeywordDiscoveryExecution,
    OrganicKeywordDiscoveryRunner,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicBuyerNeedLineageLink:
    link_id: str
    discovery_id: str
    source_asin: str
    query_origin: QueryOrigin
    buyer_need_text_id: str
    need_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "discovery_id": self.discovery_id,
            "source_asin": self.source_asin,
            "query_origin": self.query_origin.value,
            "buyer_need_text_id": self.buyer_need_text_id,
            "need_ids": list(self.need_ids),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class KeywordValidationEvidence:
    validation_id: str
    keyword_text: str
    normalized_text: str
    query_origin: QueryOrigin
    search_volume: str | None
    aba_rank: str | None
    cpc: str | None
    difficulty: str | None
    availability_status: str
    source_evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "keyword_text": self.keyword_text,
            "normalized_text": self.normalized_text,
            "query_origin": self.query_origin.value,
            "search_volume": self.search_volume,
            "aba_rank": self.aba_rank,
            "cpc": self.cpc,
            "difficulty": self.difficulty,
            "availability_status": self.availability_status,
            "source_evidence_ids": list(self.source_evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class OrganicDiscoveryPilotResult:
    run_id: str
    baseline_commit: str
    credit_plan: CreditPlan
    cohort: CohortSelection
    discovery: OrganicKeywordDiscoveryExecution
    provider_calls: tuple[ProviderCallAudit, ...]
    buyer_need_links: tuple[OrganicBuyerNeedLineageLink, ...]
    buyer_need_evidence: tuple[BuyerNeedEvidence, ...]
    clustering: SemanticClusteringResult
    buyer_need_map: BuyerNeedMapSnapshot
    keyword_validation: tuple[KeywordValidationEvidence, ...]
    success_criteria: Mapping[str, Any]
    prior_live_request_count: int = 0
    prior_live_credits_accounted: int = 0
    prior_live_usage_note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "success_criteria", MappingProxyType(dict(self.success_criteria)))

    @property
    def request_count(self) -> int:
        return self.prior_live_request_count + len(self.provider_calls)

    @property
    def completed_run_request_count(self) -> int:
        return len(self.provider_calls)

    @property
    def known_credits(self) -> int:
        return self.prior_live_credits_accounted + sum(
            item.cost_credits or 0 for item in self.provider_calls
        )

    @property
    def completed_run_known_credits(self) -> int:
        return sum(item.cost_credits or 0 for item in self.provider_calls)

    @property
    def unknown_credit_call_count(self) -> int:
        return sum(item.cost_credits is None for item in self.provider_calls)

    def classification_summary(self) -> dict[str, Any]:
        need_ids_by_discovery = {
            link.discovery_id: link.need_ids for link in self.buyer_need_links
        }
        needs = {item.need_id: item for item in self.buyer_need_evidence}
        unknown_relations = sum(
            bool(ids) and all(needs[item].status is BuyerNeedCandidateStatus.UNKNOWN for item in ids)
            for ids in need_ids_by_discovery.values()
        )
        matched = tuple(
            item for item in self.buyer_need_evidence if item.status is BuyerNeedCandidateStatus.CANDIDATE
        )
        distribution = Counter(item.need_type.value for item in matched)
        relation_count = self.discovery.corpus.asin_keyword_relation_count
        return {
            "raw_relation_count": relation_count,
            "matched_buyer_need_count": len(matched),
            "matched_relation_count": relation_count - unknown_relations,
            "unknown_relation_count": unknown_relations,
            "unknown_relation_share": (
                format(Decimal(unknown_relations) / Decimal(relation_count), "f")
                if relation_count
                else "0"
            ),
            "buyer_need_type_distribution": dict(sorted(distribution.items())),
        }

    def cluster_operational_metrics(self) -> tuple[dict[str, Any], ...]:
        links_by_need: dict[str, list[OrganicBuyerNeedLineageLink]] = defaultdict(list)
        for link in self.buyer_need_links:
            for need_id in link.need_ids:
                links_by_need[need_id].append(link)
        rows = []
        denominator = len(self.cohort.asins)
        for cluster in self.clustering.clusters:
            links = [link for need_id in cluster.source_need_ids for link in links_by_need[need_id]]
            asins = {link.source_asin for link in links}
            discovery_ids = {link.discovery_id for link in links}
            rows.append(
                {
                    "cluster_id": cluster.cluster_id,
                    "cluster_label": cluster.cluster_label,
                    "cluster_member_count": len(cluster.source_need_ids),
                    "discovered_keyword_relation_count": len(discovery_ids),
                    "source_asin_count": len(asins),
                    "asin_coverage_share": (
                        format(Decimal(len(asins)) / Decimal(denominator), "f")
                        if denominator
                        else "0"
                    ),
                    "source_asins": sorted(asins),
                    "discovery_ids": sorted(discovery_ids),
                }
            )
        return tuple(
            sorted(
                rows,
                key=lambda item: (
                    -item["source_asin_count"],
                    -item["cluster_member_count"],
                    item["cluster_label"],
                ),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "baseline_commit": self.baseline_commit,
            "credit_plan": {
                "cohort_request_credits": self.credit_plan.cohort_request_credits,
                "reverse_keyword_credits": self.credit_plan.reverse_keyword_credits,
                "keyword_validation_credits": self.credit_plan.keyword_validation_credits,
                "estimated_total_credits": self.credit_plan.estimated_total_credits,
                "gate_credits": self.credit_plan.gate_credits,
            },
            "cohort": {
                "asins": list(self.cohort.asins),
                "provider_total": self.cohort.provider_total,
                "strategy": self.cohort.strategy,
            },
            "provider_calls": [item.to_dict() for item in self.provider_calls],
            "credits": {
                "completed_run_known_total": self.completed_run_known_credits,
                "prior_live_credits_accounted": self.prior_live_credits_accounted,
                "task_total_accounted": self.known_credits,
                "unknown_credit_call_count": self.unknown_credit_call_count,
            },
            "prior_live_usage": {
                "request_count": self.prior_live_request_count,
                "credits_accounted": self.prior_live_credits_accounted,
                "note": self.prior_live_usage_note,
            },
            "organic_keyword_corpus": self.discovery.corpus.to_dict(),
            "organic_keyword_records": [item.to_dict() for item in self.discovery.records],
            "buyer_need_links": [item.to_dict() for item in self.buyer_need_links],
            "buyer_need_evidence": [
                {
                    "need_id": item.need_id,
                    "need_type": item.need_type.value,
                    "need_label": item.need_label,
                    "source_text": item.source_text,
                    "normalized_text": item.normalized_text,
                    "status": item.status.value,
                    "source_text_ids": [
                        evidence.text_id for evidence in item.source_evidence
                    ],
                }
                for item in self.buyer_need_evidence
            ],
            "classification_summary": self.classification_summary(),
            "semantic_clustering": {
                "result_id": self.clustering.result_id,
                "clusters": [
                    {
                        "cluster_id": item.cluster_id,
                        "cluster_label": item.cluster_label,
                        "source_need_ids": list(item.source_need_ids),
                        "evidence_count": item.evidence_count,
                        "confidence": item.confidence.to_dict(),
                    }
                    for item in self.clustering.clusters
                ],
                "excluded_unknown_need_ids": list(
                    self.clustering.excluded_unknown_need_ids
                ),
            },
            "cluster_operational_metrics": list(self.cluster_operational_metrics()),
            "buyer_need_map": {
                "map_id": self.buyer_need_map.map_id,
                "coverage": self.buyer_need_map.coverage.to_dict(),
                "need_clusters": [
                    {
                        "cluster_id": item.cluster_id,
                        "cluster_label": item.cluster_label,
                        "need_ids": list(item.need_ids),
                        "evidence_count": item.evidence_count,
                    }
                    for item in self.buyer_need_map.need_clusters
                ],
                "demand_metrics": [item.to_dict() for item in self.buyer_need_map.demand_metrics],
                "diagnostics": [item.to_dict() for item in self.buyer_need_map.diagnostics],
            },
            "keyword_validation": [item.to_dict() for item in self.keyword_validation],
            "success_criteria": dict(self.success_criteria),
        }


class OrganicBuyerNeedDiscoveryPilot:
    """Run one bounded live pilot without changing taxonomy or semantic rules."""

    def __init__(
        self,
        capture_client: XiYouLiveCaptureClient,
        *,
        baseline_commit: str,
        cohort_query: str = "dog water bottle",
        asin_count: int = 20,
        page_size: int = 20,
        max_pages: int = 1,
        credit_gate: int = 30,
        prior_live_request_count: int = 0,
        prior_live_credits_accounted: int = 0,
        prior_live_usage_note: str | None = None,
    ) -> None:
        self.capture_client = capture_client
        self.baseline_commit = baseline_commit
        self.cohort_query = cohort_query
        self.asin_count = asin_count
        self.prior_live_request_count = prior_live_request_count
        self.prior_live_credits_accounted = prior_live_credits_accounted
        self.prior_live_usage_note = prior_live_usage_note
        self.credit_plan = CreditPlan.for_pilot(
            asin_count=asin_count,
            max_pages=max_pages,
            gate_credits=credit_gate,
        )
        self.runner = OrganicKeywordDiscoveryRunner(
            capture_client,
            marketplace="US",
            period="last7days",
            page_size=page_size,
            max_pages=max_pages,
        )

    def run(self) -> OrganicDiscoveryPilotResult:
        self.credit_plan.enforce(
            prior_consumed_credits=self.prior_live_credits_accounted
        )
        cohort = self.runner.select_top_traffic_asins(
            cohort_query=self.cohort_query,
            asin_count=self.asin_count,
        )
        if len(cohort.asins) != self.asin_count:
            raise RuntimeError(
                f"controlled pilot requires {self.asin_count} ASINs; provider returned {len(cohort.asins)}"
            )
        discovery = self.runner.run(cohort.asins)
        needs, links = self._buyer_needs(discovery)
        clustering = SemanticClusterBuilder().build(needs)
        if not clustering.clusters:
            raise RuntimeError("organic keywords produced no taxonomy-recognized Buyer Need cluster")
        buyer_need_map = BuyerNeedMapBuilderV0_1().build(
            BuyerNeedMapRequest(
                category_scope=build_category_scope(
                    scope_type=CategoryScopeType.INPUT_COHORT,
                    scope_value="Amazon US > Pet Supplies > Dog Travel Water Bottles > Organic Pilot",
                    inclusion_rule=(
                        "Deterministic top-traffic 20-ASIN keyword cohort; reverse keywords are "
                        "provider-returned and limited to page 1."
                    ),
                ),
                marketplace="US",
                analysis_window=unknown_analysis_window(),
                buyer_need_evidence=needs,
                semantic_clusters=clustering.clusters,
                search_metric_evidence_sets=(),
                category_product_map=None,
                search_population_status=EvidencePopulationStatus.UNKNOWN,
                review_population_status=EvidencePopulationStatus.UNKNOWN,
            )
        )
        validation_capture, validation_call, validations = self._validate_top_keywords(discovery)
        del validation_capture
        calls = (cohort.call_audit, *discovery.calls, validation_call)
        criteria = self._success_criteria(discovery, needs, links, clustering)
        run_payload = {
            "baseline_commit": self.baseline_commit,
            "cohort_asins": cohort.asins,
            "corpus_snapshot_id": discovery.corpus.snapshot_id,
            "cluster_result_id": clustering.result_id,
            "buyer_need_map_id": buyer_need_map.map_id,
            "provider_call_ids": tuple(item.call_id for item in calls),
        }
        return OrganicDiscoveryPilotResult(
            run_id=deterministic_id("organic-buyer-need-discovery-pilot", run_payload),
            baseline_commit=self.baseline_commit,
            credit_plan=self.credit_plan,
            cohort=cohort,
            discovery=discovery,
            provider_calls=tuple(calls),
            buyer_need_links=links,
            buyer_need_evidence=needs,
            clustering=clustering,
            buyer_need_map=buyer_need_map,
            keyword_validation=validations,
            success_criteria=criteria,
            prior_live_request_count=self.prior_live_request_count,
            prior_live_credits_accounted=self.prior_live_credits_accounted,
            prior_live_usage_note=self.prior_live_usage_note,
        )

    @staticmethod
    def _buyer_needs(
        discovery: OrganicKeywordDiscoveryExecution,
    ) -> tuple[tuple[BuyerNeedEvidence, ...], tuple[OrganicBuyerNeedLineageLink, ...]]:
        builder = BuyerNeedCandidateBuilder()
        needs: list[BuyerNeedEvidence] = []
        links: list[OrganicBuyerNeedLineageLink] = []
        for record in discovery.records:
            text = build_search_term_text_evidence(
                record.keyword_identity,
                demand_lineage=discovery.lineage_by_discovery_id[record.discovery_id],
            )
            candidates = builder.build(text)
            needs.extend(candidates)
            link_payload = {
                "discovery_id": record.discovery_id,
                "source_asin": record.source_asin,
                "query_origin": QueryOrigin.ASIN_REVERSE_RETURNED,
                "buyer_need_text_id": text.text_id,
                "need_ids": tuple(item.need_id for item in candidates),
            }
            links.append(
                OrganicBuyerNeedLineageLink(
                    link_id=deterministic_id("organic-buyer-need-link", link_payload),
                    **link_payload,
                )
            )
        return (
            tuple(sorted(needs, key=lambda item: item.need_id)),
            tuple(sorted(links, key=lambda item: item.link_id)),
        )

    def _validate_top_keywords(
        self,
        discovery: OrganicKeywordDiscoveryExecution,
    ) -> tuple[CapturedXiYouOperation, ProviderCallAudit, tuple[KeywordValidationEvidence, ...]]:
        top = discovery.corpus.top_keywords[:20]
        keywords = [item.keyword_identity.raw_text for item in top]
        capture = self.capture_client.capture(
            operation="keyword_info",
            canonical_field="keyword.search_volume",
            parameters={"country": "US", "searchTerms": keywords},
        )
        data = capture.data
        raw_rows = data.get("list")
        returned = len(raw_rows) if isinstance(raw_rows, list) else 0
        total = data.get("total") if type(data.get("total")) is int else None
        call = build_call_audit(
            operation="keyword_info",
            status=ProviderCallStatus.SUCCEEDED,
            request_ref=capture.request_ref,
            response_ref=capture.response_ref,
            source_asin=None,
            page=None,
            returned_count=returned,
            provider_total=total,
            cost_credits=capture.cost_credits,
            x_cost_credits=capture.x_cost_credits,
            diagnostic=None,
        )
        validations = []
        for summary in top:
            keyword = summary.keyword_identity
            try:
                demand = DemandIntelligenceBuilderV0_1().build(
                    DemandIntelligenceRequest(
                        target_keyword_identity=keyword,
                        canonical_bundles=(capture.bundle,),
                    )
                )
            except Exception:
                metrics: dict[str, str | None] = {}
                evidence_ids: tuple[str, ...] = ()
            else:
                metrics = {
                    item.metric: _present_metric_value(item)
                    for item in demand.keyword_metric_evidence_sets
                }
                evidence_ids = tuple(
                    item.metric_evidence_set_id for item in demand.keyword_metric_evidence_sets
                )
            values = {
                "search_volume": metrics.get("search_volume"),
                "aba_rank": metrics.get("aba_search_frequency_rank"),
                "cpc": metrics.get("cpc"),
                "difficulty": metrics.get("competition_difficulty"),
            }
            status = (
                "AVAILABLE"
                if all(value is not None for value in values.values())
                else "PARTIAL"
                if any(value is not None for value in values.values())
                else "UNKNOWN"
            )
            payload = {
                "keyword_text": keyword.raw_text,
                "normalized_text": keyword.normalized_text,
                "query_origin": QueryOrigin.ASIN_REVERSE_RETURNED,
                **values,
                "availability_status": status,
                "source_evidence_ids": tuple(sorted(evidence_ids)),
            }
            validations.append(
                KeywordValidationEvidence(
                    validation_id=deterministic_id("organic-keyword-validation", payload),
                    **payload,
                )
            )
        return capture, call, tuple(validations)

    @staticmethod
    def _success_criteria(
        discovery: OrganicKeywordDiscoveryExecution,
        needs: tuple[BuyerNeedEvidence, ...],
        links: tuple[OrganicBuyerNeedLineageLink, ...],
        clustering: SemanticClusteringResult,
    ) -> dict[str, Any]:
        preset_queries = {
            normalize_keyword_text(item)
            for item in (
                "portable dog water bottle",
                "leakproof dog water bottle",
                "travel dog water bottle",
                "dog water bottle for walking",
                "hiking dog water bottle",
                "dog water bottle for large dogs",
                "dog water bottle for small dogs",
                "easy to clean dog water bottle",
                "spill proof dog water bottle",
                "large capacity dog water bottle",
                "easy to carry dog water bottle",
                "dog water bottle fits in backpack",
                "lightweight dog water bottle",
                "durable dog water bottle",
                "12 oz dog water bottle",
                "19 oz dog water bottle",
                "27 oz dog water bottle",
                "32 oz dog water bottle",
                "stainless steel dog water bottle",
                "compact size dog water bottle",
                "dog water bottle compatible with car cup holder",
                "dog water bottle works with stroller cup holder",
                "dog water bottle fits bicycle bottle cage",
            )
        }
        need_by_id = {item.need_id: item for item in needs}
        record_by_id = {item.discovery_id: item for item in discovery.records}
        new_expressions = sorted(
            {
                record_by_id[link.discovery_id].provider_returned_text
                for link in links
                if record_by_id[link.discovery_id].normalized_text not in preset_queries
                and any(
                    need_by_id[need_id].status is BuyerNeedCandidateStatus.CANDIDATE
                    for need_id in link.need_ids
                )
            },
            key=str.casefold,
        )
        clustered_need_ids = {
            need_id for cluster in clustering.clusters for need_id in cluster.source_need_ids
        }
        linked_need_ids = {need_id for link in links for need_id in link.need_ids}
        criterion_1 = all(
            item.query_origin is QueryOrigin.ASIN_REVERSE_RETURNED
            and item.provider_returned
            and not item.human_seeded
            for item in discovery.records
        ) and bool(discovery.records)
        criterion_2 = bool(discovery.records)
        criterion_3 = all(
            item.source_evidence
            and item.provider_request_ref
            and item.provider_response_ref
            for item in discovery.records
        )
        criterion_4 = bool(clustered_need_ids) and clustered_need_ids <= linked_need_ids
        criterion_5 = bool(new_expressions)
        return {
            "criterion_1_not_human_preset": criterion_1,
            "criterion_2_provider_returned_keyword": criterion_2,
            "criterion_3_asin_request_response_term_lineage": criterion_3,
            "criterion_4_cluster_to_discovered_keyword_lineage": criterion_4,
            "criterion_5_new_expression_vs_sp031_presets": criterion_5,
            "new_expression_examples": new_expressions[:20],
            "organic_discovery_success": all(
                (criterion_1, criterion_2, criterion_3, criterion_4, criterion_5)
            ),
        }


def _present_metric_value(metric_set: Any) -> str | None:
    values = [
        item.value.normalized_value
        for item in metric_set.candidates
        if item.value.presence_status is PresenceStatus.PRESENT
        and item.value.normalized_value is not None
    ]
    if not values:
        return None
    return str(values[0])


__all__ = (
    "KeywordValidationEvidence",
    "OrganicBuyerNeedDiscoveryPilot",
    "OrganicBuyerNeedLineageLink",
    "OrganicDiscoveryPilotResult",
)
