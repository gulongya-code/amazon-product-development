"""Deterministic ASIN reverse-keyword discovery runner V0.1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.connectors import ProviderConnectorError
from amazon_product_intelligence.contracts import (
    Channel,
    ProductKeywordRelationshipObservation,
    RelationshipDirection,
    RelationshipType,
    Severity,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.demand_intelligence import (
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
    DemandLineageReference,
    DemandSourceRecordType,
)

from .capture import CapturedXiYouOperation, XiYouLiveCaptureClient
from .models import (
    OrganicCoverageStatus,
    OrganicKeywordCorpusSnapshot,
    OrganicKeywordDiscoveryRecord,
    OrganicKeywordRankEvidence,
    OrganicKeywordSourceEvidence,
    OrganicTrafficStatus,
    ProviderCallAudit,
    ProviderCallStatus,
    QueryOrigin,
    QueryRole,
    build_call_audit,
    build_corpus_snapshot,
    build_diagnostic,
    build_organic_keyword_record,
)


class CreditApprovalRequired(RuntimeError):
    """Raised before network access when the estimated credit gate is exceeded."""


@dataclass(frozen=True, slots=True)
class CreditPlan:
    cohort_request_credits: int
    reverse_keyword_credits: int
    keyword_validation_credits: int
    estimated_total_credits: int
    gate_credits: int

    @classmethod
    def for_pilot(
        cls,
        *,
        asin_count: int,
        max_pages: int = 1,
        gate_credits: int = 30,
    ) -> "CreditPlan":
        if type(asin_count) is not int or asin_count <= 0:
            raise ValueError("asin_count must be positive")
        if type(max_pages) is not int or max_pages <= 0:
            raise ValueError("max_pages must be positive")
        cohort = 1
        reverse = asin_count * max_pages
        validation = 1
        total = cohort + reverse + validation
        return cls(
            cohort_request_credits=cohort,
            reverse_keyword_credits=reverse,
            keyword_validation_credits=validation,
            estimated_total_credits=total,
            gate_credits=gate_credits,
        )

    def enforce(self, *, prior_consumed_credits: int = 0) -> None:
        if type(prior_consumed_credits) is not int or prior_consumed_credits < 0:
            raise ValueError("prior_consumed_credits must be non-negative")
        cumulative = prior_consumed_credits + self.estimated_total_credits
        if cumulative > self.gate_credits:
            raise CreditApprovalRequired(
                f"CREDIT APPROVAL REQUIRED: cumulative estimate {cumulative} "
                f"> gate {self.gate_credits}"
            )


@dataclass(frozen=True, slots=True)
class CohortSelection:
    asins: tuple[str, ...]
    capture: CapturedXiYouOperation
    call_audit: ProviderCallAudit
    provider_total: int | None
    strategy: str = "keyword cohort page 1, provider traffic descending, response order"


@dataclass(frozen=True, slots=True)
class OrganicKeywordDiscoveryExecution:
    requested_asins: tuple[str, ...]
    records: tuple[OrganicKeywordDiscoveryRecord, ...]
    corpus: OrganicKeywordCorpusSnapshot
    calls: tuple[ProviderCallAudit, ...]
    failed_asins: tuple[str, ...]
    empty_asins: tuple[str, ...]
    lineage_by_discovery_id: Mapping[str, DemandLineageReference]
    captures_by_response_ref: Mapping[str, CapturedXiYouOperation]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lineage_by_discovery_id",
            MappingProxyType(dict(self.lineage_by_discovery_id)),
        )
        object.__setattr__(
            self,
            "captures_by_response_ref",
            MappingProxyType(dict(self.captures_by_response_ref)),
        )

    @property
    def request_count(self) -> int:
        return len(self.calls)

    @property
    def known_credits(self) -> int:
        return sum(item.cost_credits or 0 for item in self.calls)

    @property
    def unknown_credit_call_count(self) -> int:
        return sum(item.cost_credits is None for item in self.calls)


class OrganicKeywordDiscoveryRunner:
    """Run bounded reverse discovery while preserving every ASIN-keyword lineage."""

    def __init__(
        self,
        capture_client: XiYouLiveCaptureClient,
        *,
        marketplace: str = "US",
        period: str = "last7days",
        page_size: int = 20,
        max_pages: int = 1,
        reverse_operation: str = "asin_keywords",
        request_window_parameters: Mapping[str, Any] | None = None,
    ) -> None:
        if marketplace != marketplace.strip().upper():
            raise ValueError("marketplace must be uppercase")
        if type(page_size) is not int or page_size <= 0 or page_size > 20:
            raise ValueError("pilot page_size must be between 1 and 20")
        if type(max_pages) is not int or max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if reverse_operation not in {"asin_keywords", "asin_keywords_monthly"}:
            raise ValueError("reverse_operation is not an audited ASIN reverse operation")
        self.capture_client = capture_client
        self.marketplace = marketplace
        self.period = period
        self.page_size = page_size
        self.max_pages = max_pages
        self.reverse_operation = reverse_operation
        self.request_window_parameters = dict(
            request_window_parameters
            if request_window_parameters is not None
            else {"period": period}
        )

    def select_top_traffic_asins(
        self,
        *,
        cohort_query: str,
        asin_count: int = 20,
    ) -> CohortSelection:
        parameters = {
            "keyword": cohort_query,
            "searchTerm": cohort_query,
            "country": self.marketplace,
            "page": 1,
            "pageSize": asin_count,
            "period": self.period,
            "sort": {"field": "traffic", "order": "desc"},
        }
        capture = self.capture_client.capture(
            operation="keyword_asin_analysis",
            canonical_field="relationship.keyword_to_product",
            parameters=parameters,
        )
        rows, total = _rows_and_total(capture)
        ordered: list[str] = []
        for row in rows:
            asin = row.get("asin") if isinstance(row, Mapping) else None
            if isinstance(asin, str):
                normalized = asin.strip().upper()
                if len(normalized) == 10 and normalized.isalnum() and normalized not in ordered:
                    ordered.append(normalized)
            if len(ordered) == asin_count:
                break
        if not ordered:
            raise RuntimeError("deterministic cohort selection returned no valid ASINs")
        audit = _successful_call_audit(capture, returned_count=len(rows), provider_total=total)
        return CohortSelection(
            asins=tuple(ordered),
            capture=capture,
            call_audit=audit,
            provider_total=total,
        )

    def run(self, verified_asins: Sequence[str]) -> OrganicKeywordDiscoveryExecution:
        requested = tuple(dict.fromkeys(asin.strip().upper() for asin in verified_asins))
        if not requested:
            raise ValueError("verified ASIN cohort cannot be empty")
        if any(len(asin) != 10 or not asin.isalnum() for asin in requested):
            raise ValueError("verified cohort contains an invalid ASIN")
        records_by_relation: dict[tuple[str, str], OrganicKeywordDiscoveryRecord] = {}
        lineage_by_discovery: dict[str, DemandLineageReference] = {}
        captures: dict[str, CapturedXiYouOperation] = {}
        calls: list[ProviderCallAudit] = []
        failed: set[str] = set()
        empty: set[str] = set()
        diagnostics = []
        for asin in requested:
            asin_record_count = 0
            for page in range(1, self.max_pages + 1):
                parameters = {
                    "asin": asin,
                    "country": self.marketplace,
                    "page": page,
                    "pageSize": self.page_size,
                    "sort": {"field": "traffic", "order": "desc"},
                    **self.request_window_parameters,
                }
                request_ref = deterministic_id(
                    "organic-provider-request",
                    {"operation": self.reverse_operation, "parameters": parameters},
                )
                try:
                    capture = self.capture_client.capture(
                        operation=self.reverse_operation,
                        canonical_field="relationship.product_to_keyword",
                        parameters=parameters,
                    )
                except ProviderConnectorError as exc:
                    failed.add(asin)
                    calls.append(
                        build_call_audit(
                            operation=self.reverse_operation,
                            status=ProviderCallStatus.FAILED,
                            request_ref=request_ref,
                            response_ref=None,
                            source_asin=asin,
                            page=page,
                            returned_count=0,
                            provider_total=None,
                            cost_credits=None,
                            x_cost_credits=None,
                            diagnostic=f"{exc.code.value}: {exc}",
                        )
                    )
                    diagnostics.append(
                        build_diagnostic(
                            "ASIN_REVERSE_REQUEST_FAILED",
                            "The provider reverse-keyword request failed; UNKNOWN is preserved.",
                            severity=Severity.WARNING,
                            related_ids=(asin,),
                        )
                    )
                    break
                rows, total = _rows_and_total(capture)
                calls.append(
                    _successful_call_audit(
                        capture,
                        returned_count=len(rows),
                        provider_total=total,
                        source_asin=asin,
                        page=page,
                    )
                )
                captures[capture.response_ref] = capture
                page_records, page_lineages = self._records_from_capture(capture, page=page)
                asin_record_count += len(page_records)
                for record in page_records:
                    key = (record.source_asin, record.keyword_identity.keyword_id)
                    if key in records_by_relation:
                        diagnostics.append(
                            build_diagnostic(
                                "DUPLICATE_ASIN_KEYWORD_RELATION_SKIPPED",
                                "A repeated ASIN-keyword relation was deduplicated without merging different ASINs.",
                                related_ids=(record.source_asin, record.keyword_identity.keyword_id),
                            )
                        )
                        continue
                    records_by_relation[key] = record
                    lineage_by_discovery[record.discovery_id] = page_lineages[record.discovery_id]
                if total is None or len(rows) < self.page_size or page * self.page_size >= total:
                    break
            if asin_record_count == 0 and asin not in failed:
                empty.add(asin)
        records = tuple(sorted(records_by_relation.values(), key=lambda item: item.discovery_id))
        corpus = build_corpus_snapshot(
            records,
            requested_asins=requested,
            failed_asins=tuple(failed),
            empty_asins=tuple(empty),
            diagnostics=tuple(diagnostics),
        )
        return OrganicKeywordDiscoveryExecution(
            requested_asins=requested,
            records=records,
            corpus=corpus,
            calls=tuple(calls),
            failed_asins=tuple(sorted(failed)),
            empty_asins=tuple(sorted(empty)),
            lineage_by_discovery_id=lineage_by_discovery,
            captures_by_response_ref=captures,
        )

    def _records_from_capture(
        self,
        capture: CapturedXiYouOperation,
        *,
        page: int,
    ) -> tuple[tuple[OrganicKeywordDiscoveryRecord, ...], Mapping[str, DemandLineageReference]]:
        bundle = capture.bundle
        rows, total = _rows_and_total(capture)
        coverage = (
            OrganicCoverageStatus.FIRST_PAGE_ONLY
            if total is not None and total > page * max(len(rows), self.page_size)
            else OrganicCoverageStatus.COMPLETE_OR_SINGLE_PAGE
        )
        query_records = tuple(
            item
            for item in bundle.query_execution_records
            if item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
        )
        if len(query_records) != 1 or query_records[0].query_product is None:
            raise RuntimeError("reverse capture must contain one product query execution")
        query = query_records[0]
        source_asin = query.query_product.asin
        observations = tuple(
            item
            for item in bundle.observations
            if isinstance(item, ProductKeywordRelationshipObservation)
            and item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
            and item.product.asin == source_asin
        )
        memberships = tuple(
            item for item in observations if item.relationship_type is RelationshipType.CANDIDATE_MEMBERSHIP
        )
        fingerprint = sha256(canonical_json(bundle).encode("utf-8")).hexdigest()
        records: list[OrganicKeywordDiscoveryRecord] = []
        lineages: dict[str, DemandLineageReference] = {}
        for membership in memberships:
            pair = tuple(
                item
                for item in observations
                if item.keyword == membership.keyword and item.product == membership.product
            )
            ranks = tuple(
                OrganicKeywordRankEvidence(
                    channel=item.channel.value,
                    total_rank=_int_or_none(item.rank.get("totalRank")) if item.rank else None,
                    page=_int_or_none(item.rank.get("page")) if item.rank else None,
                    page_rank=_int_or_none(item.rank.get("pageRank")) if item.rank else None,
                    rank_time=(str(item.rank.get("rankTime")) if item.rank and item.rank.get("rankTime") else None),
                )
                for item in pair
                if item.relationship_type is RelationshipType.RANK
                and item.channel in {Channel.ORGANIC, Channel.SPONSORED}
            )
            organic = _traffic_value(pair, Channel.ORGANIC)
            advertising = _traffic_value(pair, Channel.SPONSORED)
            traffic_status = (
                OrganicTrafficStatus.AVAILABLE
                if organic is not None and advertising is not None
                else OrganicTrafficStatus.PARTIAL
                if organic is not None or advertising is not None
                else OrganicTrafficStatus.UNKNOWN
            )
            transform = membership.provenance.transformation
            source_evidence = OrganicKeywordSourceEvidence(
                query_execution_id=query.query_execution_id,
                relationship_observation_ids=tuple(item.observation_id for item in pair),
                raw_evidence_id=transform.raw_evidence_reference,
                collection_run_id=transform.collection_run_id,
                transformation_run_id=transform.transformation_run_id,
                mapping_version=transform.mapping_version,
                provider=membership.provenance.provider,
                source_tool=membership.provenance.source_tool,
                source_fields=tuple(item.provenance.source_field for item in pair),
                bundle_fingerprint=fingerprint,
            )
            diagnostics = (
                build_diagnostic(
                    "PROVIDER_TRAFFIC_SEMANTICS_UNCONFIRMED",
                    "Organic and advertising traffic retain provider units and are not Search Volume.",
                    related_ids=(membership.keyword.keyword_id, source_asin),
                ),
            )
            record = build_organic_keyword_record(
                marketplace=self.marketplace,
                source_asin=source_asin,
                keyword_identity=membership.keyword,
                provider_returned_text=membership.keyword.raw_text,
                normalized_text=membership.keyword.normalized_text,
                query_role=QueryRole.DISCOVERED_CANDIDATE,
                query_origin=QueryOrigin.ASIN_REVERSE_RETURNED,
                provider_returned=True,
                human_seeded=False,
                derived_from_asin=True,
                provider_operation=self.reverse_operation,
                provider_request_ref=query.query_execution_id,
                provider_response_ref=transform.raw_evidence_reference,
                period=self.period,
                page=page,
                rank=ranks,
                organic_traffic=organic,
                ad_traffic=advertising,
                traffic_status=traffic_status,
                coverage_status=coverage,
                source_evidence=(source_evidence,),
                diagnostics=diagnostics,
            )
            records.append(record)
            lineages[record.discovery_id] = _direct_relationship_lineage(
                capture,
                observation=membership,
                bundle_fingerprint=fingerprint,
            )
        return tuple(records), lineages


def _direct_relationship_lineage(
    capture: CapturedXiYouOperation,
    *,
    observation: ProductKeywordRelationshipObservation,
    bundle_fingerprint: str,
) -> DemandLineageReference:
    """Build validated canonical lineage without replaying the bundle per row."""

    transformation = observation.provenance.transformation
    runs = {
        item.transformation_run_id: item for item in capture.bundle.transformation_runs
    }
    run = runs.get(transformation.transformation_run_id)
    if run is None:
        raise RuntimeError("canonical reverse relationship has no transformation run")
    if (
        transformation.raw_evidence_reference not in capture.bundle.raw_evidence_references
        or transformation.raw_evidence_reference not in run.input_raw_evidence_references
        or run.collection_run_id != transformation.collection_run_id
        or run.mapping_version != transformation.mapping_version
    ):
        raise RuntimeError("canonical reverse relationship has inconsistent lineage")
    return DemandLineageReference(
        source_record_id=observation.observation_id,
        source_record_type=DemandSourceRecordType.PRODUCT_KEYWORD_RELATIONSHIP_OBSERVATION,
        semantic_observation_id=observation.semantic_observation_id,
        observation_kind=observation.observation_kind,
        transformation_run_id=transformation.transformation_run_id,
        mapping_version=transformation.mapping_version,
        raw_evidence_id=transformation.raw_evidence_reference,
        collection_run_id=transformation.collection_run_id,
        provider=observation.provenance.provider,
        source_tool=observation.provenance.source_tool,
        source_field=observation.provenance.source_field,
        source_bundle_fingerprints=(bundle_fingerprint,),
    )


def _relationship_lineage(
    capture: CapturedXiYouOperation,
    *,
    observation_id: str,
    keyword: Any,
) -> DemandLineageReference:
    snapshot = DemandIntelligenceBuilderV0_1().build(
        DemandIntelligenceRequest(
            target_keyword_identity=keyword,
            canonical_bundles=(capture.bundle,),
        )
    )
    for group in snapshot.relationship_evidence_groups:
        for record in group.records:
            if record.observation_id == observation_id:
                return record.lineage_references[0]
    raise RuntimeError("canonical reverse relationship has no Demand lineage")


def _traffic_value(
    observations: Sequence[ProductKeywordRelationshipObservation],
    channel: Channel,
) -> str | None:
    for item in observations:
        if item.relationship_type is RelationshipType.TRAFFIC and item.channel is channel and item.traffic is not None:
            value = item.traffic.normalized_value
            if value is not None:
                return format(Decimal(str(value)), "f")
    return None


def _rows_and_total(capture: CapturedXiYouOperation) -> tuple[tuple[Mapping[str, Any], ...], int | None]:
    data = capture.data
    raw_rows = data.get("list")
    rows = tuple(item for item in raw_rows if isinstance(item, Mapping)) if isinstance(raw_rows, list) else ()
    raw_total = data.get("total")
    total = raw_total if type(raw_total) is int and raw_total >= 0 else None
    return rows, total


def _successful_call_audit(
    capture: CapturedXiYouOperation,
    *,
    returned_count: int,
    provider_total: int | None,
    source_asin: str | None = None,
    page: int | None = 1,
) -> ProviderCallAudit:
    return build_call_audit(
        operation=capture.operation,
        status=ProviderCallStatus.SUCCEEDED,
        request_ref=capture.request_ref,
        response_ref=capture.response_ref,
        source_asin=source_asin,
        page=page,
        returned_count=returned_count,
        provider_total=provider_total,
        cost_credits=capture.cost_credits,
        x_cost_credits=capture.x_cost_credits,
        diagnostic=None,
    )


def _int_or_none(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


__all__ = (
    "CohortSelection",
    "CreditApprovalRequired",
    "CreditPlan",
    "OrganicKeywordDiscoveryExecution",
    "OrganicKeywordDiscoveryRunner",
)
