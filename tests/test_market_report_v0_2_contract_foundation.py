from __future__ import annotations

import pytest

from amazon_product_intelligence.market_report.v0_2 import (
    MARKET_REPORT_V0_2_FOUNDATION_VERSION,
    MARKET_REPORT_V0_2_VERSION,
)
from amazon_product_intelligence.market_report.v0_2.adapters import (
    CompetitorStructureAdapter,
    GovernedDispositionInput,
    MarketSizeAdapter,
    ScopeContextAdapter,
    TrueCompetitorSetAdapter,
)
from amazon_product_intelligence.market_report.v0_2.models import (
    Availability,
    CompletenessStatus,
    CompetitorDispositionType,
    CompetitorStructureSection,
    DuplicateControlStatus,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    MarketSizeSection,
    MetricSampleContext,
    MetricValueType,
    PresenceStatus,
    ProductGrainV0_2,
    ReferenceKind,
    ScopeContext,
    TrueCompetitorSetSection,
    build_competitor_disposition,
    build_metric_context,
    build_reference,
    build_scope_context,
    unavailable_metric,
)


PROVENANCE = "provenance:fixture:sp039b"


def external_reference(namespace: str, target_id: str, version: str = "fixture-v1"):
    return build_reference(
        kind=ReferenceKind.EXTERNAL_PROVENANCE,
        namespace=namespace,
        target_id=target_id,
        target_version=version,
        content_fingerprint=f"sha256:{target_id}",
        provenance_reference_ids=(PROVENANCE,),
    )


def scope_bundle(
    grain: ProductGrainV0_2 = ProductGrainV0_2.CHILD_ASIN,
):
    category = external_reference("category-product-map", "category:US:dog-water-bottle")
    cohort = external_reference("category-product-map", "cohort:US:dog-water-bottle")
    aggregation = grain in {
        ProductGrainV0_2.PARENT_ASIN,
        ProductGrainV0_2.PRODUCT_FAMILY,
    }
    mixed = grain is ProductGrainV0_2.MIXED_UNRESOLVED
    scope = build_scope_context(
        marketplace="US",
        category_reference_id=category.reference_id,
        analysis_cohort_reference_id=cohort.reference_id,
        product_grain=grain,
        aggregation_policy_id="policy:family-aggregation" if aggregation else None,
        aggregation_policy_version="v1" if aggregation else None,
        family_relationship_evidence_ids=("evidence:family",) if aggregation else (),
        duplicate_control_status=(
            DuplicateControlStatus.BLOCKED
            if mixed
            else DuplicateControlStatus.APPLIED
        ),
        duplicate_control_policy_id=None if mixed else "policy:duplicate-control",
        duplicate_control_policy_version=None if mixed else "v1",
        completeness=(
            CompletenessStatus.UNRESOLVED
            if mixed
            else CompletenessStatus.COMPLETE
        ),
        included_grain_entity_count=2,
        excluded_grain_entity_count=0,
        unresolved_grain_entity_count=1 if mixed else 0,
        unsafe_aggregate_guard=mixed,
        references=(cohort, category),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("parent/child topology unresolved",) if mixed else (),
    )
    scope_ref = build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace="market-report-v0.2.scope-context",
        target_id=scope.scope_context_id,
        target_version=scope.contract_version,
    )
    return scope, scope_ref, category, cohort


def available_metric(
    *,
    name: str,
    value_type: MetricValueType,
    value: int | float,
    grain_reference_id: str,
    cohort_reference_id: str,
    denominator_reference_id: str | None = None,
    period_reference_id: str | None = None,
    unit: str | None = None,
    currency: str | None = None,
    method_policy: bool = True,
    sample_count: int = 2,
):
    return build_metric_context(
        metric_name=name,
        value_type=value_type,
        availability=Availability.AVAILABLE,
        presence_status=PresenceStatus.PRESENT,
        evidence_semantics=EvidenceSemantics.OBSERVED,
        value=value,
        unit=unit,
        currency=currency,
        period_reference_id=period_reference_id,
        marketplace="US",
        subject_reference_ids=(),
        cohort_reference_id=cohort_reference_id,
        denominator_reference_id=denominator_reference_id,
        product_grain_reference_id=grain_reference_id,
        method_policy_id="policy:governed-metric" if method_policy else None,
        method_policy_version="v1" if method_policy else None,
        sample_context=MetricSampleContext(
            total_count=sample_count,
            included_count=sample_count,
            excluded_count=0,
            unknown_count=0,
        ),
        coverage=1.0,
        completeness=CompletenessStatus.COMPLETE,
        confidence=None,
        evidence_ids=(f"evidence:{name}",),
        provenance_reference_ids=(PROVENANCE,),
        limitations=(),
    )


def market_size_bundle(*, unavailable: bool = False, mixed: bool = False):
    scope, scope_ref, category, cohort = scope_bundle(
        ProductGrainV0_2.MIXED_UNRESOLVED if mixed else ProductGrainV0_2.CHILD_ASIN
    )
    period = external_reference("data-window", "period:2026-07")
    if unavailable:
        sales = unavailable_metric(
            metric_name="monthly_sales",
            value_type=MetricValueType.COUNT,
            marketplace="US",
            product_grain_reference_id=scope_ref.reference_id,
            provenance_reference_ids=(PROVENANCE,),
            limitations=("monthly sales not supplied",),
            presence_status=PresenceStatus.MISSING,
            unit="units/month",
            period_reference_id=period.reference_id,
            cohort_reference_id=cohort.reference_id,
        )
        revenue = unavailable_metric(
            metric_name="monthly_revenue",
            value_type=MetricValueType.MONEY,
            marketplace="US",
            product_grain_reference_id=scope_ref.reference_id,
            provenance_reference_ids=(PROVENANCE,),
            limitations=("monthly revenue not supplied",),
            presence_status=PresenceStatus.MISSING,
            currency_code="USD",
            period_reference_id=period.reference_id,
            cohort_reference_id=cohort.reference_id,
        )
    else:
        sales = available_metric(
            name="monthly_sales",
            value_type=MetricValueType.COUNT,
            value=0,
            grain_reference_id=scope_ref.reference_id,
            cohort_reference_id=cohort.reference_id,
            period_reference_id=period.reference_id,
            unit="units/month",
        )
        revenue = available_metric(
            name="monthly_revenue",
            value_type=MetricValueType.MONEY,
            value=0.0,
            grain_reference_id=scope_ref.reference_id,
            cohort_reference_id=cohort.reference_id,
            period_reference_id=period.reference_id,
            currency="USD",
        )
    section = MarketSizeAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        monthly_sales=sales,
        monthly_revenue=revenue,
        references=(period, category, cohort),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("monthly capacity unavailable",) if unavailable else (),
    )
    return section, scope, scope_ref, category, cohort, period


def true_competitor_bundle(*, review_required: bool = False, all_excluded: bool = False):
    scope, scope_ref, category, cohort = scope_bundle()
    first = external_reference("canonical-product", "product:US:B09265WXY5")
    second = external_reference("canonical-product", "product:US:B0GGR3F5KZ")
    included = external_reference("true-competitor", "cohort:included")
    denominator = external_reference("true-competitor", "denominator:included")
    inputs = (
        GovernedDispositionInput(
            grain_entity_reference_id=first.reference_id,
            product_reference_ids=(first.reference_id,),
            disposition=(
                CompetitorDispositionType.REVIEW_REQUIRED
                if review_required
                else CompetitorDispositionType.EXCLUDED
                if all_excluded
                else CompetitorDispositionType.INCLUDED
            ),
            reason_codes=("GOVERNED_MATCH",),
            evidence_ids=("evidence:first",),
            provenance_reference_ids=(PROVENANCE,),
            limitations=("human membership review required",) if review_required else (),
        ),
        GovernedDispositionInput(
            grain_entity_reference_id=second.reference_id,
            product_reference_ids=(second.reference_id,),
            disposition=CompetitorDispositionType.EXCLUDED,
            reason_codes=("GOVERNED_EXCLUSION",),
            evidence_ids=("evidence:second",),
            provenance_reference_ids=(PROVENANCE,),
        ),
    )
    safe_included = not review_required and not all_excluded
    section = TrueCompetitorSetAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        candidate_cohort_reference=cohort,
        dispositions=inputs,
        membership_authority_id="authority:true-competitor-v1",
        membership_authority_version="v1",
        reason_code_policy_id="policy:competitor-reasons",
        reason_code_policy_version="v1",
        candidate_universe_completeness=(
            CompletenessStatus.PARTIAL
            if review_required
            else CompletenessStatus.COMPLETE
        ),
        included_cohort_reference=included if safe_included else None,
        included_denominator_reference=denominator if safe_included else None,
        references=(category, first, second),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("membership review remains",) if review_required else (),
    )
    section_ref = build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace="market-report-v0.2.true-competitor-set",
        target_id=section.set_id,
        target_version=section.contract_version,
    )
    return section, section_ref, scope, scope_ref, (category, cohort, first, second, included, denominator)


def test_foundation_package_is_explicitly_isolated_and_not_a_top_level_report():
    import amazon_product_intelligence.market_report.v0_2 as package

    assert MARKET_REPORT_V0_2_VERSION == "market-report-v0.2"
    assert MARKET_REPORT_V0_2_FOUNDATION_VERSION == "market-report-v0.2-foundation-v0.1"
    assert not hasattr(package, "MarketReportSnapshotV0_2")
    assert not hasattr(package, "renderer")
    assert not hasattr(package, "pipeline")


def test_external_references_require_version_and_provenance_and_are_deterministic():
    first = external_reference("canonical-product", "product:US:B09265WXY5")
    second = external_reference("canonical-product", "product:US:B09265WXY5")
    assert first == second
    with pytest.raises(MarketReportV0_2ValidationError):
        build_reference(
            kind=ReferenceKind.EXTERNAL_PROVENANCE,
            namespace="canonical-product",
            target_id="product:US:B09265WXY5",
            target_version=None,
        )


def test_metric_explicit_zero_is_distinct_from_missing_null():
    available, *_ = market_size_bundle()
    missing, *_ = market_size_bundle(unavailable=True)
    assert available.monthly_sales.value == 0
    assert available.monthly_sales.presence_status is PresenceStatus.PRESENT
    assert available.monthly_sales.availability is Availability.AVAILABLE
    assert missing.monthly_sales.value is None
    assert missing.monthly_sales.presence_status is PresenceStatus.MISSING
    assert missing.monthly_sales.availability is Availability.UNAVAILABLE


def test_query_returned_empty_is_not_zero_and_requires_query_evidence():
    _, scope_ref, _, cohort = scope_bundle()
    with pytest.raises(MarketReportV0_2ValidationError):
        unavailable_metric(
            metric_name="query_count",
            value_type=MetricValueType.COUNT,
            marketplace="US",
            product_grain_reference_id=scope_ref.reference_id,
            provenance_reference_ids=(PROVENANCE,),
            limitations=("query returned no records",),
            presence_status=PresenceStatus.QUERY_RETURNED_EMPTY,
            cohort_reference_id=cohort.reference_id,
        )
    metric = unavailable_metric(
        metric_name="query_count",
        value_type=MetricValueType.COUNT,
        marketplace="US",
        product_grain_reference_id=scope_ref.reference_id,
        provenance_reference_ids=(PROVENANCE,),
        limitations=("query returned no records",),
        presence_status=PresenceStatus.QUERY_RETURNED_EMPTY,
        evidence_ids=("evidence:query-execution",),
        cohort_reference_id=cohort.reference_id,
    )
    assert metric.value is None


@pytest.mark.parametrize("grain", tuple(ProductGrainV0_2))
def test_all_four_product_grains_are_explicit(grain):
    scope, *_ = scope_bundle(grain)
    assert scope.product_grain is grain
    assert scope.unsafe_aggregate_guard is (grain is ProductGrainV0_2.MIXED_UNRESOLVED)


def test_parent_and_family_grains_require_governed_policy_and_relationship_evidence():
    scope, _, category, cohort = scope_bundle(ProductGrainV0_2.PARENT_ASIN)
    payload = scope.to_dict()
    payload["family_relationship_evidence_ids"] = []
    payload["scope_context_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="family_relationship"):
        ScopeContext.from_dict(payload)
    assert {category.reference_id, cohort.reference_id} <= {
        item.reference_id for item in scope.references
    }


def test_mixed_unresolved_scope_blocks_available_market_size_before_projection():
    _, scope, scope_ref, _, cohort, period = market_size_bundle(unavailable=True, mixed=True)
    sales = available_metric(
        name="monthly_sales",
        value_type=MetricValueType.COUNT,
        value=4,
        grain_reference_id=scope_ref.reference_id,
        cohort_reference_id=cohort.reference_id,
        period_reference_id=period.reference_id,
        unit="units/month",
    )
    revenue = available_metric(
        name="monthly_revenue",
        value_type=MetricValueType.MONEY,
        value=80.0,
        grain_reference_id=scope_ref.reference_id,
        cohort_reference_id=cohort.reference_id,
        period_reference_id=period.reference_id,
        currency="USD",
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="cannot project"):
        MarketSizeAdapter().adapt(
            scope_context=scope,
            scope_reference=scope_ref,
            monthly_sales=sales,
            monthly_revenue=revenue,
            references=(period, cohort),
            provenance_reference_ids=(PROVENANCE,),
        )


def test_market_size_is_structurally_present_when_both_metrics_are_unavailable():
    section, *_ = market_size_bundle(unavailable=True)
    assert isinstance(section, MarketSizeSection)
    assert section.availability is Availability.UNAVAILABLE
    assert section.monthly_sales.value is None
    assert section.monthly_revenue.value is None
    assert section.limitations


def test_metric_and_section_round_trip_are_strict_about_unknown_fields():
    section, *_ = market_size_bundle(unavailable=True)
    assert MarketSizeSection.from_dict(section.to_dict()) == section
    payload = section.to_dict()
    payload["invented_total"] = 0
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown fields"):
        MarketSizeSection.from_dict(payload)


def test_market_size_rejects_orphan_references():
    section, *_ = market_size_bundle(unavailable=True)
    payload = section.to_dict()
    payload["references"] = payload["references"][1:]
    payload["section_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="orphan"):
        MarketSizeSection.from_dict(payload)


def test_true_competitor_requires_authority_for_final_decisions():
    _, _, scope, scope_ref, refs = true_competitor_bundle()
    product = refs[2]
    entry = GovernedDispositionInput(
        grain_entity_reference_id=product.reference_id,
        product_reference_ids=(product.reference_id,),
        disposition=CompetitorDispositionType.INCLUDED,
        reason_codes=("MATCH",),
        evidence_ids=("evidence:membership",),
        provenance_reference_ids=(PROVENANCE,),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="membership authority"):
        TrueCompetitorSetAdapter().adapt(
            scope_context=scope,
            scope_reference=scope_ref,
            candidate_cohort_reference=refs[1],
            dispositions=(entry,),
            membership_authority_id=None,
            membership_authority_version=None,
            reason_code_policy_id="policy:reasons",
            reason_code_policy_version="v1",
            candidate_universe_completeness=CompletenessStatus.COMPLETE,
            included_cohort_reference=refs[4],
            included_denominator_reference=refs[5],
            references=(product,),
            provenance_reference_ids=(PROVENANCE,),
        )


def test_review_required_is_partial_guarded_and_has_no_included_denominator():
    section, *_ = true_competitor_bundle(review_required=True)
    assert section.availability is Availability.PARTIAL
    assert section.review_required_count == 1
    assert section.unsafe_aggregate_guard is True
    assert section.included_cohort_reference_id is None
    assert section.included_denominator_reference_id is None


def test_valid_empty_true_competitor_set_is_distinct_from_missing_or_unresolved():
    valid_empty, *_ = true_competitor_bundle(all_excluded=True)
    unresolved, *_ = true_competitor_bundle(review_required=True)
    assert valid_empty.availability is Availability.AVAILABLE
    assert valid_empty.is_valid_empty is True
    assert valid_empty.included_count == 0
    assert unresolved.is_valid_empty is False
    assert unresolved.availability is Availability.PARTIAL


def test_duplicate_product_membership_and_orphan_references_fail_closed():
    section, *_ = true_competitor_bundle()
    original = section.dispositions[1]
    duplicate = build_competitor_disposition(
        grain_entity_reference_id=original.grain_entity_reference_id,
        product_reference_ids=section.dispositions[0].product_reference_ids,
        disposition=original.disposition,
        reason_codes=original.reason_codes,
        authority_id=original.authority_id,
        authority_version=original.authority_version,
        evidence_ids=original.evidence_ids,
        provenance_reference_ids=original.provenance_reference_ids,
        limitations=original.limitations,
    )
    payload = section.to_dict()
    payload["dispositions"][1] = duplicate.to_dict()
    payload["set_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="multiple grain"):
        TrueCompetitorSetSection.from_dict(payload)
    payload = section.to_dict()
    payload["references"] = []
    payload["set_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError):
        TrueCompetitorSetSection.from_dict(payload)


def test_true_competitor_identity_and_order_are_input_permutation_invariant():
    section, _, scope, scope_ref, refs = true_competitor_bundle()
    entries = tuple(
        GovernedDispositionInput(
            grain_entity_reference_id=item.grain_entity_reference_id,
            product_reference_ids=tuple(reversed(item.product_reference_ids)),
            disposition=item.disposition,
            reason_codes=tuple(reversed(item.reason_codes)),
            evidence_ids=tuple(reversed(item.evidence_ids)),
            provenance_reference_ids=tuple(reversed(item.provenance_reference_ids)),
            limitations=tuple(reversed(item.limitations)),
        )
        for item in reversed(section.dispositions)
    )
    rebuilt = TrueCompetitorSetAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        candidate_cohort_reference=refs[1],
        dispositions=entries,
        membership_authority_id=section.membership_authority_id,
        membership_authority_version=section.membership_authority_version,
        reason_code_policy_id=section.reason_code_policy_id,
        reason_code_policy_version=section.reason_code_policy_version,
        candidate_universe_completeness=section.candidate_universe_completeness,
        included_cohort_reference=refs[4],
        included_denominator_reference=refs[5],
        references=tuple(reversed((refs[0], refs[2], refs[3]))),
        provenance_reference_ids=(PROVENANCE,),
    )
    assert rebuilt.to_dict() == section.to_dict()


def structure_metrics(scope_ref, included, denominator):
    values = {
        "competitor_count": (MetricValueType.COUNT, 1, None),
        "product_concentration": (MetricValueType.SHARE, 1.0, denominator.reference_id),
        "brand_concentration": (MetricValueType.SHARE, 1.0, denominator.reference_id),
        "seller_concentration": (MetricValueType.SHARE, 1.0, denominator.reference_id),
        "review_barrier": (MetricValueType.NUMBER, 240.0, None),
        "rating_barrier": (MetricValueType.NUMBER, 4.4, None),
    }
    return {
        name: available_metric(
            name=name,
            value_type=value_type,
            value=value,
            grain_reference_id=scope_ref.reference_id,
            cohort_reference_id=included.reference_id,
            denominator_reference_id=denominator_id,
            sample_count=1,
        )
        for name, (value_type, value, denominator_id) in values.items()
    }


def test_competitor_structure_projects_only_exactly_compatible_metrics():
    competitor_set, set_ref, scope, scope_ref, refs = true_competitor_bundle()
    metrics = structure_metrics(scope_ref, refs[4], refs[5])
    section = CompetitorStructureAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=competitor_set,
        true_competitor_set_reference=set_ref,
        governed_metrics=metrics,
        head_entity_reference_ids=(refs[2].reference_id,),
        references=refs,
        provenance_reference_ids=(PROVENANCE,),
    )
    assert isinstance(section, CompetitorStructureSection)
    assert section.availability is Availability.AVAILABLE
    assert section.product_concentration.value == 1.0
    assert section.included_cohort_reference_id == refs[4].reference_id


def test_incompatible_denominator_degrades_only_that_metric_without_recalculation():
    competitor_set, set_ref, scope, scope_ref, refs = true_competitor_bundle()
    metrics = structure_metrics(scope_ref, refs[4], refs[5])
    wrong_denominator = external_reference("true-competitor", "denominator:wrong")
    metrics["brand_concentration"] = available_metric(
        name="brand_concentration",
        value_type=MetricValueType.SHARE,
        value=0.5,
        grain_reference_id=scope_ref.reference_id,
        cohort_reference_id=refs[4].reference_id,
        denominator_reference_id=wrong_denominator.reference_id,
        sample_count=1,
    )
    section = CompetitorStructureAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=competitor_set,
        true_competitor_set_reference=set_ref,
        governed_metrics=metrics,
        head_entity_reference_ids=(refs[2].reference_id,),
        references=(*refs, wrong_denominator),
        provenance_reference_ids=(PROVENANCE,),
    )
    assert section.availability is Availability.PARTIAL
    assert section.brand_concentration.value is None
    assert section.brand_concentration.availability is Availability.UNAVAILABLE
    assert section.product_concentration.value == 1.0


def test_ungoverned_competitor_metric_method_is_downgraded_not_reconstructed():
    competitor_set, set_ref, scope, scope_ref, refs = true_competitor_bundle()
    metrics = structure_metrics(scope_ref, refs[4], refs[5])
    metrics["review_barrier"] = available_metric(
        name="review_barrier",
        value_type=MetricValueType.NUMBER,
        value=240.0,
        grain_reference_id=scope_ref.reference_id,
        cohort_reference_id=refs[4].reference_id,
        method_policy=False,
        sample_count=1,
    )
    section = CompetitorStructureAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=competitor_set,
        true_competitor_set_reference=set_ref,
        governed_metrics=metrics,
        head_entity_reference_ids=(refs[2].reference_id,),
        references=refs,
        provenance_reference_ids=(PROVENANCE,),
    )
    assert section.review_barrier.availability is Availability.UNAVAILABLE
    assert section.review_barrier.value is None
    assert any("method policy" in item for item in section.review_barrier.limitations)


def test_market_size_rejects_published_aggregate_without_governed_method():
    scope, scope_ref, category, cohort = scope_bundle()
    period = external_reference("data-window", "period:2026-07")
    sales = available_metric(
        name="monthly_sales",
        value_type=MetricValueType.COUNT,
        value=4,
        grain_reference_id=scope_ref.reference_id,
        cohort_reference_id=cohort.reference_id,
        period_reference_id=period.reference_id,
        unit="units/month",
        method_policy=False,
    )
    revenue = available_metric(
        name="monthly_revenue",
        value_type=MetricValueType.MONEY,
        value=80.0,
        grain_reference_id=scope_ref.reference_id,
        cohort_reference_id=cohort.reference_id,
        period_reference_id=period.reference_id,
        currency="USD",
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="method policy"):
        MarketSizeAdapter().adapt(
            scope_context=scope,
            scope_reference=scope_ref,
            monthly_sales=sales,
            monthly_revenue=revenue,
            references=(category, cohort, period),
            provenance_reference_ids=(PROVENANCE,),
        )


def test_review_required_competitor_scope_blocks_all_structure_aggregates():
    competitor_set, set_ref, scope, scope_ref, refs = true_competitor_bundle(
        review_required=True
    )
    section = CompetitorStructureAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=competitor_set,
        true_competitor_set_reference=set_ref,
        governed_metrics={},
        head_entity_reference_ids=(refs[2].reference_id,),
        references=refs,
        provenance_reference_ids=(PROVENANCE,),
    )
    assert section.availability is Availability.UNAVAILABLE
    assert section.unsafe_aggregate_guard is True
    assert section.head_entity_reference_ids == ()
    assert all(
        getattr(section, name).value is None
        for name in (
            "competitor_count",
            "product_concentration",
            "brand_concentration",
            "seller_concentration",
            "review_barrier",
            "rating_barrier",
        )
    )


def test_contract_builders_do_not_require_or_invoke_network(monkeypatch):
    import socket

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    market, *_ = market_size_bundle(unavailable=True)
    competitors, *_ = true_competitor_bundle(review_required=True)
    assert market.availability is Availability.UNAVAILABLE
    assert competitors.availability is Availability.PARTIAL


def test_scope_order_and_identity_are_input_permutation_invariant():
    scope, _, category, cohort = scope_bundle()
    rebuilt = build_scope_context(
        marketplace=scope.marketplace,
        category_reference_id=scope.category_reference_id,
        analysis_cohort_reference_id=scope.analysis_cohort_reference_id,
        product_grain=scope.product_grain,
        aggregation_policy_id=None,
        aggregation_policy_version=None,
        family_relationship_evidence_ids=(),
        duplicate_control_status=scope.duplicate_control_status,
        duplicate_control_policy_id=scope.duplicate_control_policy_id,
        duplicate_control_policy_version=scope.duplicate_control_policy_version,
        completeness=scope.completeness,
        included_grain_entity_count=scope.included_grain_entity_count,
        excluded_grain_entity_count=scope.excluded_grain_entity_count,
        unresolved_grain_entity_count=scope.unresolved_grain_entity_count,
        unsafe_aggregate_guard=False,
        references=(category, cohort),
        provenance_reference_ids=tuple(reversed(scope.provenance_reference_ids)),
        limitations=(),
    )
    assert rebuilt.to_dict() == scope.to_dict()


def test_scope_context_adapter_exposes_mixed_unresolved_without_family_inference():
    _, _, category, cohort = scope_bundle()
    scope = ScopeContextAdapter().mixed_unresolved(
        marketplace="US",
        category_reference=category,
        cohort_reference=cohort,
        included_grain_entity_count=1,
        excluded_grain_entity_count=0,
        unresolved_grain_entity_count=2,
        family_relationship_evidence_ids=(),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("no governed parent/child topology",),
    )
    assert scope.product_grain is ProductGrainV0_2.MIXED_UNRESOLVED
    assert scope.aggregation_policy_id is None
    assert scope.unsafe_aggregate_guard is True
