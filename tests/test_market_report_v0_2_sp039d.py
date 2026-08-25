from __future__ import annotations

import json
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    BuyerNeedReportItem,
    BuyerNeedReportSection,
    ReportAvailability,
)
from amazon_product_intelligence.market_report.v0_2.adapters import (
    BuyerNeedLinkAdapter,
    BuyerNeedProjectionAdapter,
    CompetitorDetailAdapter,
    CompetitorShortlistAdapter,
    GovernedBuyerNeedLinkInput,
    GovernedCompetitorShortlistInput,
    GovernedDispositionInput,
    GovernedProductDirectionInput,
    MetricCompatibilityBoundary,
    ProductDirectionAdapter,
    ProductDirectionMetricBoundary,
    TrueCompetitorSetAdapter,
)
from amazon_product_intelligence.market_report.v0_2.models import (
    Availability,
    BuyerNeedLinkSection,
    BuyerNeedLinkType,
    BuyerNeedProjection,
    CompletenessStatus,
    CompetitorDetailPurpose,
    CompetitorDispositionType,
    CompetitorShortlistSection,
    GovernedNeedCoverageState,
    MarketReportV0_2ValidationError,
    ProductDirectionSection,
    ProductDirectionSemantic,
    ReferenceKind,
    ReviewPriority,
    build_reference,
)
from tests.test_market_report_v0_2_sp039c import (
    PROVENANCE,
    competitor_detail_bundle,
    distribution_bundle,
)


FIXTURES = Path(__file__).parent / "fixtures" / "market_report_v0_2"
SOURCE_CONTRACT = "market-report-v0.1-buyer-need-section-v0.1"
SOURCE_FINGERPRINT = "sha256:buyer-need-source-fixture"
INTENT_FINGERPRINT = "sha256:query-intent-v0.3-fixture"
TAXONOMY_FINGERPRINT = "sha256:taxonomy-v0.2-fixture"
NORMALIZATION_FINGERPRINT = "sha256:semantic-normalization-v0.1-fixture"


def local(namespace: str, target_id: str, version: str):
    return build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace=namespace,
        target_id=target_id,
        target_version=version,
    )


def buyer_need_source(*, version: str = "buyer-need-intent-rules-v0.3"):
    item = BuyerNeedReportItem(
        need_id="need:portable-hydration",
        need_label="Portable hydration",
        share=0.75,
        share_basis="ASIN_COVERAGE_SHARE",
        availability=ReportAvailability.PARTIAL,
        confidence="MEDIUM",
        validation_status="V0.3_STABLE",
        evidence_count=2,
        evidence_ids=("evidence:buyer-need:1", "evidence:buyer-need:2"),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("ASIN coverage is not demand share",),
    )
    return BuyerNeedReportSection(
        source_record_id="buyer-need-report:fixture",
        intent_ruleset_version=version,
        taxonomy_version="buyer-need-taxonomy-v0.2",
        validation_status="V0.3_STABLE",
        needs=(item,),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("frozen source limitation",),
    )


def projection_bundle(*, source: BuyerNeedReportSection | None = None):
    source = source or buyer_need_source()
    source_ref = build_reference(
        kind=ReferenceKind.EXTERNAL_PROVENANCE,
        namespace="buyer-need",
        target_id=source.source_record_id,
        target_version=SOURCE_CONTRACT,
        content_fingerprint=SOURCE_FINGERPRINT,
        provenance_reference_ids=(PROVENANCE,),
    )
    projection = BuyerNeedProjectionAdapter().adapt(
        source_section=source,
        source_reference=source_ref,
        source_contract_version=SOURCE_CONTRACT,
        required_intent_ruleset_version="buyer-need-intent-rules-v0.3",
        required_taxonomy_version="buyer-need-taxonomy-v0.2",
        required_validation_status="V0.3_STABLE",
        source_validation_fingerprint=SOURCE_FINGERPRINT,
        query_intent_ruleset_fingerprint=INTENT_FINGERPRINT,
        taxonomy_fingerprint=TAXONOMY_FINGERPRINT,
        semantic_normalization_version="semantic-normalization-rules-v0.1",
        semantic_normalization_fingerprint=NORMALIZATION_FINGERPRINT,
        provenance_reference_ids=(PROVENANCE,),
    )
    projection_ref = local(
        "market-report-v0.2.buyer-need-projection",
        projection.projection_id,
        projection.contract_version,
    )
    return projection, projection_ref, source, source_ref


def graph_bundle(*, reverse: bool = False, with_links: bool = True):
    (
        detail_section,
        detail_record,
        competitor_set,
        set_ref,
        scope,
        scope_ref,
        canonical,
        _snapshot,
        _pi_ref,
    ) = competitor_detail_bundle(reverse=reverse)
    distribution, *_ = distribution_bundle(reverse=reverse)
    projection, projection_ref, source, source_ref = projection_bundle()

    disposition = competitor_set.dispositions[0]
    disposition_ref = local(
        "market-report-v0.2.true-competitor-disposition",
        disposition.disposition_id,
        competitor_set.contract_version,
    )
    detail_ref = local(
        "market-report-v0.2.competitor-detail-record",
        detail_record.record_id,
        detail_record.contract_version,
    )
    segment = distribution.segments[0]
    segment_ref = local(
        "market-report-v0.2.distribution-segment",
        segment.segment_id,
        segment.contract_version,
    )
    common_references = (
        disposition_ref,
        detail_ref,
        segment_ref,
        canonical,
    )
    link_inputs = (
        (
            GovernedBuyerNeedLinkInput(
                link_type=BuyerNeedLinkType.MULTI_SOURCE_CONTEXT,
                reason_code="GOVERNED_CONTEXT_ASSOCIATION",
                need_id=source.needs[0].need_id,
                evidence_subject_reference_ids=(canonical.reference_id,),
                competitor_disposition_reference_ids=(disposition_ref.reference_id,),
                competitor_detail_reference_ids=(detail_ref.reference_id,),
                distribution_reference_ids=(segment_ref.reference_id,),
                coverage_state=None,
                evidence_ids=("evidence:buyer-need-link",),
                provenance_reference_ids=(PROVENANCE,),
            ),
        )
        if with_links
        else ()
    )
    links = BuyerNeedLinkAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        buyer_need_projection=projection,
        buyer_need_projection_reference=projection_ref,
        inputs=link_inputs,
        link_authority_id="authority:buyer-need-link-v1" if with_links else None,
        link_authority_version="v1" if with_links else None,
        reason_code_policy_id="policy:buyer-need-link-reasons",
        reason_code_policy_version="v1",
        true_competitor_set=competitor_set,
        competitor_detail_sections=(detail_section,),
        distributions=(distribution,),
        references=tuple(reversed(common_references)) if reverse else common_references,
        provenance_reference_ids=(PROVENANCE,),
    )
    links_ref = local(
        "market-report-v0.2.buyer-need-links",
        links.section_id,
        links.contract_version,
    )
    if not links.links:
        return {
            "projection": projection,
            "projection_ref": projection_ref,
            "links": links,
            "links_ref": links_ref,
            "scope": scope,
            "scope_ref": scope_ref,
            "competitor_set": competitor_set,
            "set_ref": set_ref,
            "detail_section": detail_section,
            "detail_record": detail_record,
            "distribution": distribution,
            "refs": common_references,
        }

    link_ref = local(
        "market-report-v0.2.buyer-need-link",
        links.links[0].link_id,
        links.links[0].contract_version,
    )
    direction = ProductDirectionAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        buyer_need_links=links,
        buyer_need_link_section_reference=links_ref,
        inputs=(
            GovernedProductDirectionInput(
                proposed_product_type="portable hydration vessel",
                proposed_configuration={
                    "capacity_oz": 16,
                    "closure": "leak-resistant proposal",
                },
                buyer_need_link_reference_ids=(link_ref.reference_id,),
                distribution_reference_ids=(segment_ref.reference_id,),
                competitor_detail_reference_ids=(detail_ref.reference_id,),
                direct_competitor_reference_ids=(disposition_ref.reference_id,),
                entry_rationale="Evaluate a compact configuration against supplied evidence.",
                rationale_reference_ids=(canonical.reference_id,),
                validation_items=("Validate capacity and closure with human review",),
                risk_reference_ids=(canonical.reference_id,),
                evidence_ids=("evidence:product-direction",),
                provenance_reference_ids=(PROVENANCE,),
            ),
        ),
        proposal_authority_id="authority:proposal-v1",
        proposal_authority_version="v1",
        distributions=(distribution,),
        competitor_detail_sections=(detail_section,),
        true_competitor_set=competitor_set,
        references=(
            link_ref,
            disposition_ref,
            detail_ref,
            segment_ref,
            canonical,
        ),
        provenance_reference_ids=(PROVENANCE,),
    )
    direction_ref = local(
        "market-report-v0.2.product-direction",
        direction.directions[0].direction_id,
        direction.directions[0].contract_version,
    )
    shortlist = CompetitorShortlistAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=competitor_set,
        true_competitor_set_reference=set_ref,
        competitor_detail_sections=(detail_section,),
        inputs=(
            GovernedCompetitorShortlistInput(
                disposition_reference_id=disposition_ref.reference_id,
                competitor_detail_reference_id=detail_ref.reference_id,
                selection_reason_codes=("GOVERNED_REVIEW_CANDIDATE",),
                product_direction_reference_ids=(direction_ref.reference_id,),
                representative_evidence_reference_ids=(canonical.reference_id,),
                review_priority=ReviewPriority.HIGH,
                evidence_ids=("evidence:shortlist",),
                provenance_reference_ids=(PROVENANCE,),
            ),
        ),
        selection_authority_id="authority:shortlist-v1",
        selection_authority_version="v1",
        selection_reason_policy_id="policy:shortlist-reasons",
        selection_reason_policy_version="v1",
        product_direction_section=direction,
        references=(
            disposition_ref,
            detail_ref,
            direction_ref,
            canonical,
        ),
        provenance_reference_ids=(PROVENANCE,),
    )
    return {
        "projection": projection,
        "projection_ref": projection_ref,
        "links": links,
        "links_ref": links_ref,
        "direction": direction,
        "direction_ref": direction_ref,
        "shortlist": shortlist,
        "scope": scope,
        "scope_ref": scope_ref,
        "competitor_set": competitor_set,
        "set_ref": set_ref,
        "detail_section": detail_section,
        "detail_record": detail_record,
        "distribution": distribution,
        "refs": common_references,
    }


def review_required_shortlist_bundle():
    base = graph_bundle()
    scope = base["scope"]
    scope_ref = base["scope_ref"]
    canonical = next(
        reference
        for reference in base["detail_record"].references
        if reference.namespace == "canonical-product"
        and reference.reference_id
        == base["detail_record"].grain_entity_reference_id
    )
    cohort = next(
        reference
        for reference in scope.references
        if reference.reference_id == scope.analysis_cohort_reference_id
    )
    review_set = TrueCompetitorSetAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        candidate_cohort_reference=cohort,
        dispositions=(
            GovernedDispositionInput(
                grain_entity_reference_id=canonical.reference_id,
                product_reference_ids=(canonical.reference_id,),
                disposition=CompetitorDispositionType.REVIEW_REQUIRED,
                reason_codes=("HUMAN_REVIEW_REQUIRED",),
                evidence_ids=("evidence:review-disposition",),
                provenance_reference_ids=(PROVENANCE,),
                limitations=("membership requires human review",),
            ),
        ),
        membership_authority_id=None,
        membership_authority_version=None,
        reason_code_policy_id="policy:competitor-reasons",
        reason_code_policy_version="v1",
        candidate_universe_completeness=CompletenessStatus.PARTIAL,
        included_cohort_reference=None,
        included_denominator_reference=None,
        references=scope.references + (canonical,),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("candidate evaluation is incomplete",),
    )
    review_set_ref = local(
        "market-report-v0.2.true-competitor-set",
        review_set.set_id,
        review_set.contract_version,
    )
    disposition = review_set.dispositions[0]
    disposition_ref = local(
        "market-report-v0.2.true-competitor-disposition",
        disposition.disposition_id,
        review_set.contract_version,
    )
    source_record = base["detail_record"]
    pi_ref = next(
        reference
        for reference in source_record.references
        if reference.namespace == "product-intelligence"
    )
    snapshot = competitor_detail_bundle()[7]
    period = next(
        reference
        for reference in source_record.references
        if reference.namespace == "data-window"
    )
    review_record = CompetitorDetailAdapter().project_record(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=review_set,
        true_competitor_set_reference=review_set_ref,
        purpose=CompetitorDetailPurpose.REVIEW_QUEUE,
        grain_entity_reference_id=canonical.reference_id,
        product_intelligence_snapshot=snapshot,
        product_intelligence_reference=pi_ref,
        canonical_references=(canonical,),
        fields=source_record.fields,
        metrics=source_record.metrics,
        metric_boundaries={
            "fba_fee": MetricCompatibilityBoundary(
                cohort_reference_id=cohort.reference_id,
                denominator_reference_id=None,
                period_reference_id=period.reference_id,
                currency="USD",
            )
        },
        references=source_record.references,
        provenance_reference_ids=(PROVENANCE,),
        limitations=("membership requires human review",),
    )
    review_detail = CompetitorDetailAdapter().compose_section(
        purpose=CompetitorDetailPurpose.REVIEW_QUEUE,
        scope_reference=scope_ref,
        true_competitor_set_reference=review_set_ref,
        records=(review_record,),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("membership requires human review",),
    )
    detail_ref = local(
        "market-report-v0.2.competitor-detail-record",
        review_record.record_id,
        review_record.contract_version,
    )
    shortlist = CompetitorShortlistAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=review_set,
        true_competitor_set_reference=review_set_ref,
        competitor_detail_sections=(review_detail,),
        inputs=(
            GovernedCompetitorShortlistInput(
                disposition_reference_id=disposition_ref.reference_id,
                competitor_detail_reference_id=detail_ref.reference_id,
                selection_reason_codes=("GOVERNED_HUMAN_REVIEW_CANDIDATE",),
                review_priority=ReviewPriority.MEDIUM,
                evidence_ids=("evidence:review-shortlist",),
                provenance_reference_ids=(PROVENANCE,),
                limitations=("membership remains REVIEW_REQUIRED",),
            ),
        ),
        selection_authority_id="authority:shortlist-v1",
        selection_authority_version="v1",
        selection_reason_policy_id="policy:shortlist-reasons",
        selection_reason_policy_version="v1",
        references=(disposition_ref, detail_ref, canonical),
        provenance_reference_ids=(PROVENANCE,),
    )
    return shortlist


def test_frozen_buyer_need_projection_preserves_source_identity_versions_and_order():
    projection, _, source, _ = projection_bundle()
    assert projection.source_section is source
    assert projection.source_need_order == tuple(item.need_id for item in source.needs)
    assert projection.source_section.to_dict() == source.to_dict()
    assert projection.source_section.intent_ruleset_version == "buyer-need-intent-rules-v0.3"
    assert projection.source_section.taxonomy_version == "buyer-need-taxonomy-v0.2"
    assert projection.query_intent_ruleset_fingerprint == INTENT_FINGERPRINT
    assert projection.taxonomy_fingerprint == TAXONOMY_FINGERPRINT
    assert projection.semantic_normalization_fingerprint == NORMALIZATION_FINGERPRINT


def test_incompatible_buyer_need_version_and_fingerprint_fail_closed():
    with pytest.raises(MarketReportV0_2ValidationError, match="ruleset/taxonomy"):
        projection_bundle(source=buyer_need_source(version="buyer-need-intent-rules-v0.2"))
    projection, *_ = projection_bundle()
    payload = projection.to_dict()
    payload["source_validation_fingerprint"] = "sha256:tampered"
    payload["projection_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="fingerprint"):
        BuyerNeedProjection.from_dict(payload)


def test_buyer_need_link_resolves_competitor_detail_disposition_and_distribution():
    bundle = graph_bundle()
    link = bundle["links"].links[0]
    assert bundle["links"].availability is Availability.AVAILABLE
    assert link.competitor_disposition_reference_ids
    assert link.competitor_detail_reference_ids
    assert link.distribution_reference_ids
    assert link.coverage_state is None


def test_links_can_be_unavailable_without_mutating_buyer_need_truth():
    bundle = graph_bundle(with_links=False)
    assert bundle["projection"].availability is Availability.PARTIAL
    assert bundle["projection"].source_need_order == ("need:portable-hydration",)
    assert bundle["links"].availability is Availability.UNAVAILABLE
    assert bundle["links"].links == ()


def test_missing_link_authority_discards_inputs_and_fails_closed_unavailable():
    bundle = graph_bundle()
    source = bundle["links"].links[0]
    unavailable = BuyerNeedLinkAdapter().adapt(
        scope_context=bundle["scope"],
        scope_reference=bundle["scope_ref"],
        buyer_need_projection=bundle["projection"],
        buyer_need_projection_reference=bundle["projection_ref"],
        inputs=(
            GovernedBuyerNeedLinkInput(
                link_type=source.link_type,
                reason_code=source.reason_code,
                need_id=source.need_id,
                evidence_subject_reference_ids=source.evidence_subject_reference_ids,
                competitor_disposition_reference_ids=source.competitor_disposition_reference_ids,
                competitor_detail_reference_ids=source.competitor_detail_reference_ids,
                distribution_reference_ids=source.distribution_reference_ids,
                evidence_ids=source.evidence_ids,
                provenance_reference_ids=source.provenance_reference_ids,
            ),
        ),
        link_authority_id=None,
        link_authority_version=None,
        reason_code_policy_id="policy:buyer-need-link-reasons",
        reason_code_policy_version="v1",
        references=bundle["links"].references,
        provenance_reference_ids=(PROVENANCE,),
    )
    assert unavailable.availability is Availability.UNAVAILABLE
    assert unavailable.links == ()


def test_no_ungoverned_unmet_satisfaction_or_gap_inference():
    bundle = graph_bundle()
    source = bundle["links"].links[0]
    payload = source.to_dict()
    payload["reason_code"] = "UNMET_NEED_FROM_ONE_REVIEW"
    payload["link_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="governed"):
        from amazon_product_intelligence.market_report.v0_2.models import BuyerNeedLink

        BuyerNeedLink.from_dict(payload)


def test_coverage_state_requires_governed_authority():
    bundle = graph_bundle()
    payload = bundle["links"].links[0].to_dict()
    payload["coverage_state"] = GovernedNeedCoverageState.NOT_COVERED.value
    payload["link_id"] = "bad"
    from amazon_product_intelligence.market_report.v0_2.models import BuyerNeedLink

    with pytest.raises(MarketReportV0_2ValidationError, match="authority"):
        BuyerNeedLink.from_dict(payload)


@pytest.mark.parametrize(
    "field",
    (
        "competitor_disposition_reference_ids",
        "competitor_detail_reference_ids",
        "distribution_reference_ids",
    ),
)
def test_link_target_orphans_fail_closed(field):
    bundle = graph_bundle()
    payload = bundle["links"].to_dict()
    referenced_id = payload["links"][0][field][0]
    payload["references"] = [
        value for value in payload["references"] if value["reference_id"] != referenced_id
    ]
    payload["section_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="orphan"):
        BuyerNeedLinkSection.from_dict(payload)


def test_product_direction_is_hypothesis_and_missing_target_price_is_partial():
    direction = graph_bundle()["direction"]
    item = direction.directions[0]
    assert item.proposal_semantic is ProductDirectionSemantic.HYPOTHESIS_FOR_VALIDATION
    assert item.availability is Availability.PARTIAL
    assert item.target_price_metric_reference_id is None
    assert any("target price unavailable" in value for value in item.limitations)
    assert "observed" not in json.dumps(item.to_dict()["proposed_configuration"]).casefold()


@pytest.mark.parametrize(
    "forbidden", ("WINNER", "BEST_PRODUCT", "BUY", "LAUNCH", "GO", "PROFITABLE")
)
def test_product_direction_rejects_forbidden_decision_semantics(forbidden):
    bundle = graph_bundle()
    payload = bundle["direction"].directions[0].to_dict()
    payload["entry_rationale"] = forbidden
    payload["direction_id"] = "bad"
    from amazon_product_intelligence.market_report.v0_2.models import ProductDirection

    with pytest.raises(MarketReportV0_2ValidationError, match="forbidden"):
        ProductDirection.from_dict(payload)


def test_missing_proposal_authority_produces_unavailable_empty_section():
    bundle = graph_bundle()
    unavailable = ProductDirectionAdapter().adapt(
        scope_context=bundle["scope"],
        scope_reference=bundle["scope_ref"],
        buyer_need_links=bundle["links"],
        buyer_need_link_section_reference=bundle["links_ref"],
        inputs=(
            GovernedProductDirectionInput(
                proposed_product_type="proposal",
                proposed_configuration={"attribute": "candidate"},
                buyer_need_link_reference_ids=(),
            ),
        ),
        proposal_authority_id=None,
        proposal_authority_version=None,
        provenance_reference_ids=(PROVENANCE,),
    )
    assert unavailable.availability is Availability.UNAVAILABLE
    assert unavailable.directions == ()


def test_incompatible_target_price_metric_is_not_used_or_recalculated():
    bundle = graph_bundle()
    source = bundle["direction"].directions[0]
    wrong_metric = bundle["detail_record"].metrics[0]
    metric_ref = local(
        "market-report-v0.2.metric",
        wrong_metric.metric_id,
        wrong_metric.contract_version,
    )
    direction = ProductDirectionAdapter().adapt(
        scope_context=bundle["scope"],
        scope_reference=bundle["scope_ref"],
        buyer_need_links=bundle["links"],
        buyer_need_link_section_reference=bundle["links_ref"],
        inputs=(
            GovernedProductDirectionInput(
                proposed_product_type=source.proposed_product_type,
                proposed_configuration=source.to_dict()["proposed_configuration"],
                buyer_need_link_reference_ids=source.buyer_need_link_reference_ids,
                distribution_reference_ids=source.distribution_reference_ids,
                competitor_detail_reference_ids=source.competitor_detail_reference_ids,
                target_price_metric_reference_id=metric_ref.reference_id,
                direct_competitor_reference_ids=source.direct_competitor_reference_ids,
                entry_rationale=source.entry_rationale,
                rationale_reference_ids=source.rationale_reference_ids,
                validation_items=source.validation_items,
                risk_reference_ids=source.risk_reference_ids,
                evidence_ids=source.evidence_ids,
                provenance_reference_ids=source.provenance_reference_ids,
            ),
        ),
        proposal_authority_id="authority:proposal-v1",
        proposal_authority_version="v1",
        target_price_boundary=ProductDirectionMetricBoundary(
            cohort_reference_id=wrong_metric.cohort_reference_id,
            denominator_reference_id=wrong_metric.denominator_reference_id,
            period_reference_id=wrong_metric.period_reference_id,
            currency=wrong_metric.currency,
        ),
        metrics=(wrong_metric,),
        distributions=(bundle["distribution"],),
        competitor_detail_sections=(bundle["detail_section"],),
        true_competitor_set=bundle["competitor_set"],
        references=(*bundle["direction"].references, metric_ref),
        provenance_reference_ids=(PROVENANCE,),
    )
    item = direction.directions[0]
    assert item.target_price_metric_reference_id is None
    assert item.availability is Availability.PARTIAL
    assert any("not target_price_band" in value for value in item.limitations)


def test_shortlist_is_human_review_only_and_has_no_numeric_rank():
    shortlist = graph_bundle()["shortlist"]
    assert shortlist.availability is Availability.AVAILABLE
    assert shortlist.items[0].review_priority is ReviewPriority.HIGH
    payload = shortlist.to_dict()
    assert "desirability_rank" not in json.dumps(payload).casefold()
    assert "opportunity_rank" not in json.dumps(payload).casefold()


def test_review_required_shortlist_preserves_disposition_for_human_review():
    shortlist = review_required_shortlist_bundle()
    assert shortlist.availability is Availability.PARTIAL
    assert shortlist.items[0].disposition is CompetitorDispositionType.REVIEW_REQUIRED
    assert shortlist.items[0].review_priority is ReviewPriority.MEDIUM
    assert any("REVIEW_REQUIRED" in value for value in shortlist.limitations)


def test_missing_shortlist_authority_produces_unavailable_not_empty_market():
    bundle = graph_bundle()
    unavailable = CompetitorShortlistAdapter().adapt(
        scope_context=bundle["scope"],
        scope_reference=bundle["scope_ref"],
        true_competitor_set=bundle["competitor_set"],
        true_competitor_set_reference=bundle["set_ref"],
        competitor_detail_sections=(bundle["detail_section"],),
        inputs=(
            GovernedCompetitorShortlistInput(
                disposition_reference_id=bundle["shortlist"].items[0].disposition_reference_id,
                competitor_detail_reference_id=bundle["shortlist"].items[0].competitor_detail_reference_id,
                selection_reason_codes=("GOVERNED_REVIEW_CANDIDATE",),
                evidence_ids=("evidence:shortlist",),
                provenance_reference_ids=(PROVENANCE,),
            ),
        ),
        selection_authority_id=None,
        selection_authority_version=None,
        selection_reason_policy_id="policy:shortlist-reasons",
        selection_reason_policy_version="v1",
        references=bundle["shortlist"].references,
        provenance_reference_ids=(PROVENANCE,),
    )
    assert unavailable.availability is Availability.UNAVAILABLE
    assert unavailable.items == ()
    assert any("authority" in value for value in unavailable.limitations)


def test_shortlist_requires_versioned_selection_reasons():
    bundle = graph_bundle()
    payload = bundle["shortlist"].items[0].to_dict()
    payload["selection_reason_codes"] = []
    payload["item_id"] = "bad"
    from amazon_product_intelligence.market_report.v0_2.models import CompetitorShortlistItem

    with pytest.raises(MarketReportV0_2ValidationError):
        CompetitorShortlistItem.from_dict(payload)


def test_excluded_competitor_is_rejected_from_shortlist():
    bundle = graph_bundle()
    disposition = bundle["competitor_set"].dispositions[0]
    payload = bundle["shortlist"].items[0].to_dict()
    payload["disposition"] = "EXCLUDED"
    payload["item_id"] = "bad"
    from amazon_product_intelligence.market_report.v0_2.models import CompetitorShortlistItem

    with pytest.raises(MarketReportV0_2ValidationError, match="EXCLUDED"):
        CompetitorShortlistItem.from_dict(payload)
    assert disposition.disposition.value == "INCLUDED"


def test_review_priority_order_is_deterministic_not_a_market_rank():
    from amazon_product_intelligence.market_report.v0_2.models import (
        REVIEW_PRIORITY_ORDER,
    )

    assert [
        value.value
        for value in sorted(ReviewPriority, key=lambda item: REVIEW_PRIORITY_ORDER[item])
    ] == ["HIGH", "MEDIUM", "LOW", "UNSPECIFIED"]


def test_one_way_graph_has_no_reverse_product_direction_identity():
    bundle = graph_bundle()
    link_payload = bundle["links"].links[0].to_dict()
    assert "product_direction_reference_ids" not in link_payload
    assert bundle["direction"].directions[0].buyer_need_link_reference_ids


def test_orphan_and_duplicate_links_fail_closed():
    bundle = graph_bundle()
    payload = bundle["links"].to_dict()
    payload["links"] = [payload["links"][0], payload["links"][0]]
    payload["section_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="duplicate"):
        BuyerNeedLinkSection.from_dict(payload)
    payload = bundle["links"].to_dict()
    payload["links"][0]["need_id"] = "need:orphan"
    link_material = dict(payload["links"][0])
    link_material.pop("link_id")
    payload["links"][0]["link_id"] = deterministic_id(
        "market-report-v0.2-buyer-need-link", link_material
    )
    payload["section_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="orphan"):
        BuyerNeedLinkSection.from_dict(payload)


def test_external_reference_requires_namespace_version_and_provenance():
    with pytest.raises(MarketReportV0_2ValidationError):
        build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="future-demand-supply-gap",
            target_id="gap:fixture",
            target_version=None,
            provenance_reference_ids=(PROVENANCE,),
        )


@pytest.mark.parametrize(
    ("key", "contract"),
    (
        ("projection", BuyerNeedProjection),
        ("links", BuyerNeedLinkSection),
        ("direction", ProductDirectionSection),
        ("shortlist", CompetitorShortlistSection),
    ),
)
def test_strict_round_trip_and_unknown_field_rejection(key, contract):
    value = graph_bundle()[key]
    assert contract.from_dict(value.to_dict()) == value
    payload = value.to_dict()
    payload["renderer_hint"] = "xlsx"
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown fields"):
        contract.from_dict(payload)


def test_input_permutation_is_deterministic():
    first = graph_bundle(reverse=False)
    second = graph_bundle(reverse=True)
    for key in ("projection", "links", "direction", "shortlist"):
        assert first[key].to_dict() == second[key].to_dict()


def test_keyword_project_is_not_required():
    payload = json.dumps(graph_bundle()["direction"].to_dict()).casefold()
    assert "keyword_project" not in payload


def test_contracts_exclude_runtime_provider_payload_and_secret_surfaces():
    bundle = graph_bundle()
    payload = json.dumps(
        {
            key: bundle[key].to_dict()
            for key in ("projection", "links", "direction", "shortlist")
        },
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "raw_payload",
        "authorization",
        "api_key",
        "access_token",
        "credential",
        "retry_count",
        "billed_credits",
        "runtime_path",
    ):
        assert forbidden not in payload


def test_sp039d_adapters_make_zero_network_or_provider_calls(monkeypatch):
    import socket

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    bundle = graph_bundle()
    assert bundle["links"].links
    assert bundle["direction"].directions
    assert bundle["shortlist"].items


@pytest.mark.parametrize(
    ("name", "key", "contract"),
    (
        (
            "sp039d_buyer_need_projection_links.json",
            "buyer_need_projection",
            BuyerNeedProjection,
        ),
        (
            "sp039d_buyer_need_projection_links.json",
            "buyer_need_links",
            BuyerNeedLinkSection,
        ),
        (
            "sp039d_product_direction_hypothesis.json",
            "product_direction",
            ProductDirectionSection,
        ),
        (
            "sp039d_product_direction_unavailable.json",
            "product_direction",
            ProductDirectionSection,
        ),
        (
            "sp039d_competitor_shortlist_review.json",
            "competitor_shortlist",
            CompetitorShortlistSection,
        ),
    ),
)
def test_checked_in_sp039d_fixtures_strictly_round_trip(name, key, contract):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))[key]
    assert contract.from_dict(payload).to_dict() == payload
