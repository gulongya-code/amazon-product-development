"""Strict projection from the existing production V0.1 result into V0.2.

This module is deliberately analytical, not presentational.  It copies governed
V0.1 sections and represents unsupported V0.2 facts as unavailable; it never
calculates replacement market, competitor, direction, or shortlist values.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from hashlib import sha256
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report.models import (
    MarketReportSnapshot,
    ReportAvailability,
)

from .adapters import (
    BuyerNeedProjectionAdapter,
    CompetitorStructureAdapter,
    MarketSizeAdapter,
    OpportunityProjectionAdapter,
    ReportContextAdapter,
    TrueCompetitorSetAdapter,
)
from .builder import compose_market_report_v0_2
from .models import (
    Availability,
    CompletenessStatus,
    DuplicateControlStatus,
    EvidenceRecord,
    EvidenceSemantics,
    ExecutiveClaimCategory,
    ExternalIntegrationState,
    MetricValueType,
    PresenceStatus,
    ProductGrainV0_2,
    ReferenceKind,
    ReportProvenanceRecord,
    build_buyer_need_link_section,
    build_competitor_shortlist_section,
    build_executive_claim,
    build_executive_summary,
    build_external_integrations,
    build_product_direction_section,
    build_reference,
    build_sanitized_appendix,
    build_scope_context,
    unavailable_metric,
)


PRODUCTION_V0_2_ADAPTER_VERSION = "production-market-report-v0.2-adapter-v1"
_V0_1_BUYER_NEED_CONTRACT = "market-report-v0.1-buyer-need-section-v0.1"
_V0_1_OPPORTUNITY_CONTRACT = "market-report-v0.1-opportunity-section-v0.1"
_ALLOWED_PROVENANCE_NAMESPACES = {
    "buyer-need", "canonical", "canonical-product", "category-product-map",
    "competition", "data-window", "distribution-denominator", "opportunity",
    "policy", "product-intelligence", "sanitized-evidence", "true-competitor",
}


def _fingerprint(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return "sha256:" + sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _availability(value: ReportAvailability) -> Availability:
    return Availability(value.value)


def _local_reference(namespace: str, target: Any, contract_version: str):
    return build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace=f"market-report-v0.2.{namespace}",
        target_id=target,
        target_version=contract_version,
    )


def _evidence_ids(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if is_dataclass(item):
            for field in fields(item):
                child = getattr(item, field.name)
                if field.name.endswith("evidence_ids"):
                    found.update(child)
                else:
                    visit(child)
        elif isinstance(item, (tuple, list)):
            for child in item:
                visit(child)

    visit(value)
    return tuple(sorted(found))


class ProductionMarketReportV0_2Adapter:
    """Compose one strict V0.2 snapshot from the validated V0.1 upstream result."""

    def adapt(
        self,
        source: MarketReportSnapshot,
        *,
        operational_metadata: Mapping[str, Any],
    ):
        source.validate()
        provenance = tuple(
            ReportProvenanceRecord(
                provenance_id=item.reference_id,
                source_namespace=(
                    item.source_module
                    if item.source_module in _ALLOWED_PROVENANCE_NAMESPACES
                    else "canonical"
                ),
                source_version=item.source_version,
                source_record_id=item.source_record_id,
                availability=_availability(item.availability),
                content_fingerprint=None,
                evidence_ids=item.evidence_ids,
                limitations=item.limitations,
            )
            for item in source.provenance
        )
        provenance_ids = tuple(item.provenance_id for item in provenance)
        primary_provenance = provenance_ids[0]

        category_reference = build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="category-product-map",
            target_id=source.category.category_id,
            target_version="market-report-v0.1-category-context-v0.1",
            content_fingerprint=_fingerprint(source.category),
            provenance_reference_ids=source.category.provenance_reference_ids,
        )
        cohort_reference = build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="category-product-map",
            target_id=source.sample.sample_id,
            target_version="market-report-v0.1-sample-context-v0.1",
            content_fingerprint=_fingerprint(source.sample),
            provenance_reference_ids=source.sample.provenance_reference_ids,
        )
        window_reference = build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="data-window",
            target_id=source.data_window.window_id,
            target_version="market-report-v0.1-data-window-v0.1",
            content_fingerprint=_fingerprint(source.data_window),
            provenance_reference_ids=source.data_window.provenance_reference_ids,
        )
        context = ReportContextAdapter()
        category = context.category(source.category, source_reference=category_reference)
        sample = context.sample(
            source.sample,
            source_reference=cohort_reference,
            analysis_cohort_reference=cohort_reference,
        )
        data_window = context.data_window(
            source.data_window,
            source_reference=window_reference,
            retrieved_at=None,
        )

        scope = build_scope_context(
            marketplace=source.category.marketplace,
            category_reference_id=category_reference.reference_id,
            analysis_cohort_reference_id=cohort_reference.reference_id,
            product_grain=ProductGrainV0_2.CHILD_ASIN,
            aggregation_policy_id=None,
            aggregation_policy_version=None,
            family_relationship_evidence_ids=(),
            duplicate_control_status=DuplicateControlStatus.APPLIED,
            duplicate_control_policy_id="explicit-asin-deduplication",
            duplicate_control_policy_version="v1",
            completeness=CompletenessStatus.COMPLETE,
            included_grain_entity_count=source.sample.unique_asin_count,
            excluded_grain_entity_count=0,
            unresolved_grain_entity_count=0,
            unsafe_aggregate_guard=False,
            references=(category_reference, cohort_reference),
            provenance_reference_ids=provenance_ids,
            limitations=(),
        )
        scope_reference = _local_reference(
            "scope", scope.scope_context_id, scope.contract_version
        )

        economic_limitation = "governed monthly market sales and revenue were not supplied"
        sales = unavailable_metric(
            metric_name="monthly_sales",
            value_type=MetricValueType.COUNT,
            marketplace=source.category.marketplace,
            product_grain_reference_id=scope_reference.reference_id,
            cohort_reference_id=cohort_reference.reference_id,
            period_reference_id=window_reference.reference_id,
            presence_status=PresenceStatus.MISSING,
            unit="units/month",
            provenance_reference_ids=provenance_ids,
            limitations=(economic_limitation,),
        )
        revenue = unavailable_metric(
            metric_name="monthly_revenue",
            value_type=MetricValueType.MONEY,
            marketplace=source.category.marketplace,
            product_grain_reference_id=scope_reference.reference_id,
            cohort_reference_id=cohort_reference.reference_id,
            period_reference_id=window_reference.reference_id,
            presence_status=PresenceStatus.MISSING,
            currency_code=None,
            provenance_reference_ids=provenance_ids,
            limitations=(economic_limitation,),
        )
        market_size = MarketSizeAdapter().adapt(
            scope_context=scope,
            scope_reference=scope_reference,
            monthly_sales=sales,
            monthly_revenue=revenue,
            references=(cohort_reference, window_reference),
            provenance_reference_ids=provenance_ids,
            limitations=(economic_limitation,),
        )
        market_reference = _local_reference(
            "market-size", market_size.section_id, market_size.contract_version
        )

        competitor_limitation = "governed true-competitor membership authority was not supplied"
        competitor_set = TrueCompetitorSetAdapter().adapt(
            scope_context=scope,
            scope_reference=scope_reference,
            candidate_cohort_reference=cohort_reference,
            dispositions=(),
            membership_authority_id=None,
            membership_authority_version=None,
            reason_code_policy_id="true-competitor-reason-codes",
            reason_code_policy_version="v1",
            candidate_universe_completeness=CompletenessStatus.UNKNOWN,
            included_cohort_reference=None,
            included_denominator_reference=None,
            references=(category_reference, cohort_reference),
            provenance_reference_ids=provenance_ids,
            limitations=(competitor_limitation,),
        )
        competitor_set_reference = _local_reference(
            "true-competitor-set", competitor_set.set_id, competitor_set.contract_version
        )
        competitor_structure = CompetitorStructureAdapter().adapt(
            scope_context=scope,
            scope_reference=scope_reference,
            true_competitor_set=competitor_set,
            true_competitor_set_reference=competitor_set_reference,
            governed_metrics={},
            head_entity_reference_ids=(),
            references=(cohort_reference,),
            provenance_reference_ids=provenance_ids,
            limitations=(competitor_limitation,),
        )

        buyer_fingerprint = _fingerprint(source.buyer_needs)
        buyer_reference = build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="buyer-need",
            target_id=source.buyer_needs.source_record_id,
            target_version=_V0_1_BUYER_NEED_CONTRACT,
            content_fingerprint=buyer_fingerprint,
            provenance_reference_ids=source.buyer_needs.provenance_reference_ids,
        )
        buyer_needs = BuyerNeedProjectionAdapter().adapt(
            source_section=source.buyer_needs,
            source_reference=buyer_reference,
            source_contract_version=_V0_1_BUYER_NEED_CONTRACT,
            required_intent_ruleset_version=source.buyer_needs.intent_ruleset_version,
            required_taxonomy_version=source.buyer_needs.taxonomy_version,
            required_validation_status=source.buyer_needs.validation_status,
            source_validation_fingerprint=buyer_fingerprint,
            query_intent_ruleset_fingerprint=_fingerprint(
                {"version": source.buyer_needs.intent_ruleset_version}
            ),
            taxonomy_fingerprint=_fingerprint(
                {"version": source.buyer_needs.taxonomy_version}
            ),
            semantic_normalization_version="identity-projection-v1",
            semantic_normalization_fingerprint=_fingerprint(
                {"method": "identity-projection", "source": buyer_fingerprint}
            ),
            provenance_reference_ids=provenance_ids,
        )
        buyer_reference_local = _local_reference(
            "buyer-needs", buyer_needs.projection_id, buyer_needs.contract_version
        )
        link_limitation = "governed Buyer Need relationship authority was not supplied"
        buyer_links = build_buyer_need_link_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=scope_reference.reference_id,
            buyer_need_projection_reference_id=buyer_reference_local.reference_id,
            link_authority_id=None,
            link_authority_version=None,
            reason_code_policy_id="buyer-need-link-reason-codes",
            reason_code_policy_version="v1",
            declared_need_ids=buyer_needs.source_need_order,
            links=(),
            references=(scope_reference, buyer_reference_local),
            provenance_reference_ids=provenance_ids,
            limitations=(link_limitation,),
        )
        links_reference = _local_reference(
            "buyer-need-links", buyer_links.section_id, buyer_links.contract_version
        )
        direction_limitation = "Product Direction hypotheses require governed decision-support evidence"
        directions = build_product_direction_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=scope_reference.reference_id,
            buyer_need_link_section_reference_id=links_reference.reference_id,
            proposal_authority_id=None,
            proposal_authority_version=None,
            directions=(),
            references=(scope_reference, links_reference),
            provenance_reference_ids=provenance_ids,
            limitations=(direction_limitation,),
        )
        shortlist = build_competitor_shortlist_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=scope_reference.reference_id,
            true_competitor_set_reference_id=competitor_set_reference.reference_id,
            selection_authority_id=None,
            selection_authority_version=None,
            selection_reason_policy_id="competitor-shortlist-review-reasons",
            selection_reason_policy_version="v1",
            items=(),
            references=(scope_reference, competitor_set_reference),
            provenance_reference_ids=provenance_ids,
            limitations=("shortlist is review order only and governed selection evidence is unavailable",),
        )

        opportunity_reference = build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="opportunity",
            target_id=source.opportunity_score.score_id,
            target_version=_V0_1_OPPORTUNITY_CONTRACT,
            content_fingerprint=_fingerprint(source.opportunity_score),
            provenance_reference_ids=source.opportunity_score.provenance_reference_ids,
        )
        opportunity = OpportunityProjectionAdapter().adapt(
            source.opportunity_score,
            source_contract_version=_V0_1_OPPORTUNITY_CONTRACT,
            source_reference=opportunity_reference,
        )
        gap_claim = build_executive_claim(
            category=ExecutiveClaimCategory.EVIDENCE_GAP,
            availability=Availability.UNAVAILABLE,
            text="Governed monthly market economics are unavailable",
            typed_value=None,
            source_reference_ids=(market_reference.reference_id,),
            evidence_ids=(),
            provenance_reference_ids=provenance_ids,
            confidence=None,
            limitations=(economic_limitation,),
        )
        executive = build_executive_summary(
            availability=Availability.UNAVAILABLE,
            claims=(gap_claim,),
            provenance_reference_ids=provenance_ids,
            limitations=(economic_limitation,),
        )
        sanitized = build_sanitized_appendix(
            availability=Availability.UNAVAILABLE,
            references=(),
            provenance_reference_ids=provenance_ids,
            limitations=("no governed sanitized appendix attachment was supplied",),
        )
        external = build_external_integrations(
            state=ExternalIntegrationState.NOT_ATTACHED,
            attachments=(),
            limitations=("Keyword Intelligence was not attached; demand is not inferred",),
        )

        sections = (
            category, sample, data_window, scope, market_size, competitor_set,
            competitor_structure, buyer_needs, buyer_links, directions, shortlist,
            opportunity, executive, sanitized, external, provenance,
        )
        evidence = tuple(
            EvidenceRecord(
                evidence_id=evidence_id,
                semantics=EvidenceSemantics.OBSERVED,
                source_reference_ids=(category_reference.reference_id,),
                provenance_reference_ids=(primary_provenance,),
                content_fingerprint=None,
                limitations=(),
            )
            for evidence_id in _evidence_ids(sections)
        )
        return compose_market_report_v0_2(
            generated_at=source.generated_at,
            producer_version=PRODUCTION_V0_2_ADAPTER_VERSION,
            operational_metadata=operational_metadata,
            category=category,
            sample=sample,
            data_window=data_window,
            scope_context=scope,
            market_size=market_size,
            true_competitor_set=competitor_set,
            competitor_structure=competitor_structure,
            distributions=(),
            competitor_details=(),
            buyer_needs=buyer_needs,
            buyer_need_links=buyer_links,
            product_directions=directions,
            competitor_shortlist=shortlist,
            opportunity_score=opportunity,
            executive_summary=executive,
            sanitized_appendix=sanitized,
            external_integrations=external,
            provenance=provenance,
            evidence=evidence,
            references=(
                scope_reference,
                market_reference,
                competitor_set_reference,
                buyer_reference_local,
                links_reference,
                opportunity_reference,
            ),
            limitations=tuple(sorted({
                *source.limitations,
                economic_limitation,
                competitor_limitation,
                link_limitation,
                direction_limitation,
                "distribution and competitor-detail registries are unavailable",
            })),
        )


__all__ = (
    "PRODUCTION_V0_2_ADAPTER_VERSION",
    "ProductionMarketReportV0_2Adapter",
)
