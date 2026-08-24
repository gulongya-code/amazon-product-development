from __future__ import annotations

import json
from pathlib import Path

import pytest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.contracts import ProductIdentity, product_id
from amazon_product_intelligence.market_report.v0_2.adapters import (
    CompetitorDetailAdapter,
    DistributionAdapter,
    GovernedDispositionInput,
    GovernedDistributionSegmentInput,
    MetricCompatibilityBoundary,
    TrueCompetitorSetAdapter,
)
from amazon_product_intelligence.market_report.v0_2.models import (
    Availability,
    CompletenessStatus,
    CompetitorDetailPurpose,
    CompetitorDetailRecord,
    CompetitorDetailSection,
    CompetitorDispositionType,
    CompetitorFieldGroup,
    DistributionKind,
    DistributionMembershipMode,
    DistributionMetricName,
    DistributionSectionItem,
    DuplicateControlStatus,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    MembershipDisclosure,
    MetricSampleContext,
    MetricValueType,
    PresenceStatus,
    ProductGrainV0_2,
    ReferenceKind,
    SegmentClassification,
    build_competitor_detail_section,
    build_distribution_section,
    build_distribution_segment,
    build_field_projection,
    build_metric_context,
    build_reference,
    build_scope_context,
    unavailable_metric,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
SP039C_FIXTURES = FIXTURE_ROOT / "market_report_v0_2"
PROVENANCE = "provenance:fixture:sp039c"
TARGET_ASIN = "B0G2VV4RBW"
PARENT_ASIN = "B0G2VVX3ML"


def external(namespace: str, target_id: str, version: str = "fixture-v1"):
    return build_reference(
        kind=ReferenceKind.EXTERNAL_PROVENANCE,
        namespace=namespace,
        target_id=target_id,
        target_version=version,
        content_fingerprint=f"sha256:{target_id}",
        provenance_reference_ids=(PROVENANCE,),
    )


def scope_bundle(*, mixed: bool = False):
    category = external("category-product-map", "category:US:dog-water-bottle")
    cohort = external("category-product-map", "cohort:US:dog-water-bottle")
    scope = build_scope_context(
        marketplace="US",
        category_reference_id=category.reference_id,
        analysis_cohort_reference_id=cohort.reference_id,
        product_grain=(
            ProductGrainV0_2.MIXED_UNRESOLVED
            if mixed
            else ProductGrainV0_2.CHILD_ASIN
        ),
        aggregation_policy_id=None,
        aggregation_policy_version=None,
        family_relationship_evidence_ids=(),
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
        unresolved_grain_entity_count=2 if mixed else 0,
        unsafe_aggregate_guard=mixed,
        references=(category, cohort),
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
    scope_reference_id: str,
    cohort_reference_id: str | None,
    denominator_reference_id: str | None,
    subject_reference_ids: tuple[str, ...],
    period_reference_id: str | None = None,
    currency: str | None = None,
    unit: str | None = None,
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
        subject_reference_ids=subject_reference_ids,
        cohort_reference_id=cohort_reference_id,
        denominator_reference_id=denominator_reference_id,
        product_grain_reference_id=scope_reference_id,
        method_policy_id="policy:governed-metric",
        method_policy_version="v1",
        sample_context=MetricSampleContext(
            total_count=2,
            included_count=len(subject_reference_ids),
            excluded_count=2 - len(subject_reference_ids),
            unknown_count=0,
        ),
        coverage=1.0,
        completeness=CompletenessStatus.COMPLETE,
        confidence=None,
        evidence_ids=(f"evidence:{name}:{value}",),
        provenance_reference_ids=(PROVENANCE,),
        limitations=(),
    )


def distribution_bundle(
    *,
    with_economics: bool = False,
    numeric: bool = False,
    mixed: bool = False,
    reverse: bool = False,
):
    scope, scope_ref, category, cohort = scope_bundle(mixed=mixed)
    denominator = external("distribution-denominator", "denominator:all-products")
    period = external("data-window", "period:2026-07")
    first = external("canonical-product", "product:US:B09265WXY5")
    second = external("canonical-product", "product:US:B0GGR3F5KZ")
    declared = (
        DistributionMetricName.PRODUCT_COUNT,
        DistributionMetricName.PRODUCT_SHARE,
        *(
            (
                DistributionMetricName.SALES,
                DistributionMetricName.REVENUE,
            )
            if with_economics
            else ()
        ),
    )

    def segment(
        *,
        policy_value_id: str,
        ordinal: int,
        label: str,
        definition,
        classification: SegmentClassification,
        member,
    ):
        metrics = {
            "product_count": available_metric(
                name="product_count",
                value_type=MetricValueType.COUNT,
                value=1,
                scope_reference_id=scope_ref.reference_id,
                cohort_reference_id=cohort.reference_id,
                denominator_reference_id=None,
                subject_reference_ids=(member.reference_id,),
                unit="products",
            ),
            "product_share": available_metric(
                name="product_share",
                value_type=MetricValueType.SHARE,
                value=0.5,
                scope_reference_id=scope_ref.reference_id,
                cohort_reference_id=cohort.reference_id,
                denominator_reference_id=denominator.reference_id,
                subject_reference_ids=(member.reference_id,),
                unit="share",
            ),
        }
        return GovernedDistributionSegmentInput(
            policy_value_id=policy_value_id,
            policy_ordinal=ordinal,
            display_label=label,
            canonical_definition=definition,
            classification=classification,
            membership_disclosure=MembershipDisclosure.COMPLETE,
            member_grain_entity_reference_ids=(member.reference_id,),
            metrics=metrics,
            evidence_ids=(f"evidence:segment:{policy_value_id}",),
            provenance_reference_ids=(PROVENANCE,),
        )

    known = segment(
        policy_value_id="bucket:known",
        ordinal=20 if numeric else 10,
        label="USD 10 <= price < 25" if numeric else "Bottle",
        definition=(
            {"lower": 10, "upper": 25, "lower_inclusive": True, "upper_inclusive": False}
            if numeric
            else {"value": "bottle"}
        ),
        classification=SegmentClassification.CLASSIFIED,
        member=first,
    )
    unknown = segment(
        policy_value_id="bucket:unknown",
        ordinal=99,
        label="Unknown / unclassified",
        definition=None,
        classification=SegmentClassification.UNKNOWN_UNCLASSIFIED,
        member=second,
    )
    segments = (unknown, known) if reverse else (known, unknown)
    section = DistributionAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        distribution_kind=(
            DistributionKind.NUMERIC_BUCKET if numeric else DistributionKind.ATTRIBUTE_VALUE
        ),
        dimension="price" if numeric else "product_type",
        policy_id="policy:caller-supplied-price-v7" if numeric else "policy:product-type-v1",
        policy_version="v7" if numeric else "v1",
        membership_mode=DistributionMembershipMode.SINGLE_CLASSIFICATION,
        cohort_reference=cohort,
        product_denominator_reference=denominator,
        sales_denominator_reference=None,
        revenue_denominator_reference=None,
        period_reference=period if with_economics else None,
        currency_code="USD" if with_economics else None,
        declared_metric_names=tuple(reversed(declared)) if reverse else declared,
        segments=segments,
        references=tuple(reversed((category, first, second))) if reverse else (category, first, second),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("compatible sales/revenue evidence not supplied",)
        if with_economics
        else (),
    )
    return section, scope, scope_ref, category, cohort, denominator, period, first, second


def product_intelligence_snapshot():
    payload = json.loads(
        (
            FIXTURE_ROOT
            / "provider_adapters"
            / "v0_1"
            / "sorftime_product_detail.json"
        ).read_text(encoding="utf-8")
    )
    bundle = SorftimeAdapterV0_1().adapt(
        payload,
        AdaptationContext(
            provider="sorftime",
            payload_kind="product_detail",
            source_tool="product_detail",
            marketplace="US",
            locale="en-us",
            retrieved_at="2026-08-14T09:00:00Z",
            transformed_at="2026-08-14T09:01:00Z",
            collection_run_id="collection:sp039c:fixture",
            sanitized_request={"asin": TARGET_ASIN},
            currency="USD",
        ),
    ).bundle.validate()
    identity = ProductIdentity(
        product_id=product_id("US", TARGET_ASIN),
        marketplace="US",
        asin=TARGET_ASIN,
        parent_asin=PARENT_ASIN,
        identity_status="CONFIRMED",
    )
    return ProductIntelligenceBuilderV0_1().build(
        ProductIntelligenceRequest(
            target_product_identity=identity,
            scope=ProductScope.EXACT_PRODUCT,
            canonical_bundles=(bundle,),
        )
    )


def competitor_bundle():
    scope, scope_ref, category, cohort = scope_bundle()
    canonical = external("canonical-product", product_id("US", TARGET_ASIN))
    included_cohort = external("true-competitor", "cohort:included")
    included_denominator = external("true-competitor", "denominator:included")
    competitor_set = TrueCompetitorSetAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        candidate_cohort_reference=cohort,
        dispositions=(
            GovernedDispositionInput(
                grain_entity_reference_id=canonical.reference_id,
                product_reference_ids=(canonical.reference_id,),
                disposition=CompetitorDispositionType.INCLUDED,
                reason_codes=("GOVERNED_MATCH",),
                evidence_ids=("evidence:membership",),
                provenance_reference_ids=(PROVENANCE,),
            ),
        ),
        membership_authority_id="authority:true-competitor-v1",
        membership_authority_version="v1",
        reason_code_policy_id="policy:competitor-reasons",
        reason_code_policy_version="v1",
        candidate_universe_completeness=CompletenessStatus.COMPLETE,
        included_cohort_reference=included_cohort,
        included_denominator_reference=included_denominator,
        references=(category, canonical),
        provenance_reference_ids=(PROVENANCE,),
    )
    set_ref = build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace="market-report-v0.2.true-competitor-set",
        target_id=competitor_set.set_id,
        target_version=competitor_set.contract_version,
    )
    snapshot = product_intelligence_snapshot()
    pi_ref = external(
        "product-intelligence",
        snapshot.snapshot_id,
        snapshot.ruleset_version,
    )
    period = external("data-window", "period:2026-07")
    return (
        competitor_set,
        set_ref,
        scope,
        scope_ref,
        category,
        cohort,
        canonical,
        included_cohort,
        included_denominator,
        snapshot,
        pi_ref,
        period,
    )


def available_field(name, group, value, display, sources):
    return build_field_projection(
        field_name=name,
        field_group=group,
        availability=Availability.AVAILABLE,
        presence_status=PresenceStatus.PRESENT,
        evidence_semantics=EvidenceSemantics.RESOLVED,
        value=value,
        display_value=display,
        method_policy_id="policy:canonical-resolution",
        method_policy_version="v1",
        source_reference_ids=sources,
        evidence_ids=(f"evidence:{name}",),
        provenance_reference_ids=(PROVENANCE,),
        limitations=(),
    )


def unavailable_field(name, group, source, limitation):
    return build_field_projection(
        field_name=name,
        field_group=group,
        availability=Availability.UNAVAILABLE,
        presence_status=PresenceStatus.MISSING,
        evidence_semantics=EvidenceSemantics.UNKNOWN,
        value=None,
        display_value=None,
        method_policy_id=None,
        method_policy_version=None,
        source_reference_ids=(source,),
        evidence_ids=(),
        provenance_reference_ids=(PROVENANCE,),
        limitations=(limitation,),
    )


def competitor_detail_bundle(*, metric_mismatch: str | None = None, reverse: bool = False):
    (
        competitor_set,
        set_ref,
        scope,
        scope_ref,
        category,
        cohort,
        canonical,
        included_cohort,
        included_denominator,
        snapshot,
        pi_ref,
        period,
    ) = competitor_bundle()
    fields = (
        available_field(
            "title",
            CompetitorFieldGroup.IDENTITY_CATALOG,
            "Portable Dog Water Bottle",
            "Portable Dog Water Bottle",
            (pi_ref.reference_id, canonical.reference_id),
        ),
        available_field(
            "material",
            CompetitorFieldGroup.PRODUCT_FACTS,
            "plastic",
            "Plastic",
            (pi_ref.reference_id,),
        ),
        unavailable_field(
            "seller_location",
            CompetitorFieldGroup.SELLER_MARKETING,
            pi_ref.reference_id,
            "seller location is not governed upstream",
        ),
        unavailable_field(
            "fulfillment_mode",
            CompetitorFieldGroup.FULFILLMENT_ECONOMICS,
            pi_ref.reference_id,
            "fulfillment evidence is missing",
        ),
    )
    mismatch_reference = (
        external("competitor-metric-context", f"{metric_mismatch}:wrong")
        if metric_mismatch is not None
        else None
    )
    metric_cohort = mismatch_reference if metric_mismatch == "cohort" else cohort
    metric_scope_reference_id = (
        mismatch_reference.reference_id
        if metric_mismatch == "grain"
        else scope_ref.reference_id
    )
    metric_period_reference_id = (
        mismatch_reference.reference_id
        if metric_mismatch == "period"
        else period.reference_id
    )
    fba_fee = unavailable_metric(
        metric_name="fba_fee",
        value_type=MetricValueType.MONEY,
        marketplace="US",
        product_grain_reference_id=metric_scope_reference_id,
        provenance_reference_ids=(PROVENANCE,),
        limitations=("FBA fee evidence is missing",),
        presence_status=PresenceStatus.MISSING,
        currency_code="USD",
        period_reference_id=metric_period_reference_id,
        subject_reference_ids=(canonical.reference_id,),
        cohort_reference_id=metric_cohort.reference_id,
    )
    if metric_mismatch is not None:
        fba_fee = available_metric(
            name="fba_fee",
            value_type=MetricValueType.MONEY,
            value=4.25,
            scope_reference_id=metric_scope_reference_id,
            cohort_reference_id=metric_cohort.reference_id,
            denominator_reference_id=None,
            subject_reference_ids=(canonical.reference_id,),
            period_reference_id=metric_period_reference_id,
            currency="USD",
        )
    adapter = CompetitorDetailAdapter()
    record = adapter.project_record(
        scope_context=scope,
        scope_reference=scope_ref,
        true_competitor_set=competitor_set,
        true_competitor_set_reference=set_ref,
        purpose=CompetitorDetailPurpose.INCLUDED_COMPETITORS,
        grain_entity_reference_id=canonical.reference_id,
        product_intelligence_snapshot=snapshot,
        product_intelligence_reference=pi_ref,
        canonical_references=(canonical,),
        fields=tuple(reversed(fields)) if reverse else fields,
        metrics=(fba_fee,),
        metric_boundaries={
            "fba_fee": MetricCompatibilityBoundary(
                cohort_reference_id=cohort.reference_id,
                denominator_reference_id=None,
                period_reference_id=period.reference_id,
                currency="USD",
            )
        },
        references=(
            category,
            cohort,
            included_cohort,
            included_denominator,
            period,
            *(() if mismatch_reference is None else (mismatch_reference,)),
        ),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("some competitor fields are unavailable",),
    )
    section = adapter.compose_section(
        purpose=CompetitorDetailPurpose.INCLUDED_COMPETITORS,
        scope_reference=scope_ref,
        true_competitor_set_reference=set_ref,
        records=(record,),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("some competitor fields are unavailable",),
    )
    return section, record, competitor_set, set_ref, scope, scope_ref, canonical, snapshot, pi_ref


def test_attribute_distribution_available_with_explicit_unknown_segment():
    section, *_ = distribution_bundle()
    assert section.availability is Availability.AVAILABLE
    assert section.distribution_kind is DistributionKind.ATTRIBUTE_VALUE
    assert [item.policy_value_id for item in section.segments] == [
        "bucket:known",
        "bucket:unknown",
    ]
    unknown = section.segments[-1]
    assert unknown.classification is SegmentClassification.UNKNOWN_UNCLASSIFIED
    assert unknown.canonical_definition is None
    assert {metric.metric_name for metric in unknown.metrics} == {
        "product_count",
        "product_share",
    }


def test_distribution_economics_are_explicitly_unavailable_not_zero():
    section, *_ = distribution_bundle(with_economics=True)
    assert section.availability is Availability.PARTIAL
    for segment in section.segments:
        metrics = {item.metric_name: item for item in segment.metrics}
        assert metrics["product_count"].availability is Availability.AVAILABLE
        assert metrics["sales"].availability is Availability.UNAVAILABLE
        assert metrics["revenue"].availability is Availability.UNAVAILABLE
        assert metrics["sales"].value is None
        assert metrics["revenue"].value is None


def test_numeric_bucket_policy_is_caller_supplied_and_not_a_global_threshold():
    section, *_ = distribution_bundle(numeric=True)
    assert section.distribution_kind is DistributionKind.NUMERIC_BUCKET
    assert section.policy_id == "policy:caller-supplied-price-v7"
    assert section.policy_version == "v7"
    assert section.segments[0].canonical_definition["lower"] == 10
    assert section.segments[0].policy_ordinal == 20


def test_distribution_requires_policy_version():
    section, *_ = distribution_bundle()
    payload = section.to_dict()
    payload["policy_version"] = None
    payload["distribution_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="policy"):
        DistributionSectionItem.from_dict(payload)


def test_distribution_duplicate_policy_ordinal_fails():
    section, *_ = distribution_bundle()
    payload = section.to_dict()
    payload["segments"][1]["policy_ordinal"] = payload["segments"][0]["policy_ordinal"]
    payload["segments"][1]["segment_id"] = "bad"
    payload["distribution_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError):
        DistributionSectionItem.from_dict(payload)


def test_distribution_duplicate_segment_identity_fails():
    section, *_ = distribution_bundle()
    with pytest.raises(MarketReportV0_2ValidationError, match="duplicate policy value"):
        build_distribution_section(
            distribution_kind=section.distribution_kind,
            dimension=section.dimension,
            availability=section.availability,
            marketplace=section.marketplace,
            policy_id=section.policy_id,
            policy_version=section.policy_version,
            membership_mode=section.membership_mode,
            scope_context_reference_id=section.scope_context_reference_id,
            cohort_reference_id=section.cohort_reference_id,
            product_denominator_reference_id=section.product_denominator_reference_id,
            sales_denominator_reference_id=None,
            revenue_denominator_reference_id=None,
            product_grain_reference_id=section.product_grain_reference_id,
            period_reference_id=None,
            currency=None,
            declared_metric_names=section.declared_metric_names,
            segments=(section.segments[0], section.segments[0]),
            unsafe_aggregate_guard=False,
            references=section.references,
            evidence_ids=section.evidence_ids,
            provenance_reference_ids=section.provenance_reference_ids,
            limitations=section.limitations,
        )


def test_distribution_requires_exactly_one_unknown_segment():
    section, *_ = distribution_bundle()
    payload = section.to_dict()
    payload["segments"] = payload["segments"][:-1]
    payload["distribution_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown/unclassified"):
        DistributionSectionItem.from_dict(payload)


def test_distribution_orphan_denominator_fails_closed():
    section, *_ = distribution_bundle()
    payload = section.to_dict()
    payload["references"] = [
        item
        for item in payload["references"]
        if item["reference_id"] != payload["product_denominator_reference_id"]
    ]
    payload["distribution_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="orphan"):
        DistributionSectionItem.from_dict(payload)


def test_single_classification_shares_must_reconcile_without_guessing():
    section, _, _, _, cohort, denominator, _, first, _ = distribution_bundle()
    known = section.segments[0]
    changed_share = available_metric(
        name="product_share",
        value_type=MetricValueType.SHARE,
        value=0.4,
        scope_reference_id=section.scope_context_reference_id,
        cohort_reference_id=cohort.reference_id,
        denominator_reference_id=denominator.reference_id,
        subject_reference_ids=(first.reference_id,),
        unit="share",
    )
    changed_known = build_distribution_segment(
        policy_value_id=known.policy_value_id,
        policy_ordinal=known.policy_ordinal,
        display_label=known.display_label,
        canonical_definition=known.canonical_definition,
        classification=known.classification,
        membership_disclosure=known.membership_disclosure,
        metrics=tuple(
            changed_share if item.metric_name == "product_share" else item
            for item in known.metrics
        ),
        member_grain_entity_reference_ids=known.member_grain_entity_reference_ids,
        evidence_ids=tuple({*known.evidence_ids, *changed_share.evidence_ids}),
        provenance_reference_ids=known.provenance_reference_ids,
        limitations=(),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="reconcile to one"):
        build_distribution_section(
            distribution_kind=section.distribution_kind,
            dimension=section.dimension,
            availability=section.availability,
            marketplace=section.marketplace,
            policy_id=section.policy_id,
            policy_version=section.policy_version,
            membership_mode=section.membership_mode,
            scope_context_reference_id=section.scope_context_reference_id,
            cohort_reference_id=section.cohort_reference_id,
            product_denominator_reference_id=section.product_denominator_reference_id,
            sales_denominator_reference_id=None,
            revenue_denominator_reference_id=None,
            product_grain_reference_id=section.product_grain_reference_id,
            period_reference_id=None,
            currency=None,
            declared_metric_names=section.declared_metric_names,
            segments=(changed_known, section.segments[1]),
            unsafe_aggregate_guard=False,
            references=section.references,
            evidence_ids=tuple({*section.evidence_ids, *changed_share.evidence_ids}),
            provenance_reference_ids=section.provenance_reference_ids,
            limitations=(),
        )


def test_distribution_money_requires_explicit_currency():
    section, *_ = distribution_bundle(with_economics=True)
    payload = section.to_dict()
    payload["currency"] = None
    payload["distribution_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="currency"):
        DistributionSectionItem.from_dict(payload)


def test_mixed_unresolved_scope_blocks_metrics_and_membership():
    section, *_ = distribution_bundle(mixed=True)
    assert section.availability is Availability.UNAVAILABLE
    assert section.unsafe_aggregate_guard is True
    for segment in section.segments:
        assert segment.membership_disclosure is MembershipDisclosure.NOT_DISCLOSED
        assert segment.member_grain_entity_reference_ids == ()
        assert all(metric.value is None for metric in segment.metrics)


def test_distribution_adapter_does_not_create_undeclared_thresholds_or_metrics():
    section, *_ = distribution_bundle()
    payload = json.dumps(section.to_dict(), sort_keys=True)
    assert "lower" not in payload
    assert "upper" not in payload
    assert "sales" not in {item.value for item in section.declared_metric_names}


def test_distribution_identity_is_input_permutation_invariant():
    first, *_ = distribution_bundle(reverse=False)
    second, *_ = distribution_bundle(reverse=True)
    assert first.to_dict() == second.to_dict()


def test_distribution_strict_round_trip_and_unknown_field_rejection():
    section, *_ = distribution_bundle(with_economics=True)
    assert DistributionSectionItem.from_dict(section.to_dict()) == section
    payload = section.to_dict()
    payload["global_price_thresholds"] = [10, 25]
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown fields"):
        DistributionSectionItem.from_dict(payload)


def test_competitor_detail_partial_fields_keep_row_present():
    section, record, *_ = competitor_detail_bundle()
    assert section.availability is Availability.PARTIAL
    assert len(section.records) == 1
    fields = {item.field_name: item for item in record.fields}
    assert fields["title"].value == "Portable Dog Water Bottle"
    assert fields["material"].value == "plastic"
    assert fields["seller_location"].value is None
    assert fields["seller_location"].availability is Availability.UNAVAILABLE
    assert fields["fulfillment_mode"].presence_status is PresenceStatus.MISSING


def test_competitor_numeric_business_fields_reuse_metric_context():
    _, record, *_ = competitor_detail_bundle()
    assert len(record.metrics) == 1
    metric = record.metrics[0]
    assert metric.metric_name == "fba_fee"
    assert metric.value_type is MetricValueType.MONEY
    assert metric.value is None
    assert metric.currency == "USD"


def test_competitor_detail_preserves_product_intelligence_and_canonical_references():
    _, record, _, _, _, _, canonical, snapshot, pi_ref = competitor_detail_bundle()
    assert record.product_identity_reference_ids == (canonical.reference_id,)
    assert canonical.reference_id in record.canonical_source_reference_ids
    assert record.product_intelligence_reference_ids == (pi_ref.reference_id,)
    assert pi_ref.target_id == snapshot.snapshot_id


def test_competitor_detail_orphan_product_intelligence_reference_fails():
    _, record, *_ = competitor_detail_bundle()
    payload = record.to_dict()
    pi_reference_id = payload["product_intelligence_reference_ids"][0]
    payload["references"] = [
        item for item in payload["references"] if item["reference_id"] != pi_reference_id
    ]
    payload["record_id"] = "bad"
    with pytest.raises(MarketReportV0_2ValidationError, match="orphan"):
        CompetitorDetailRecord.from_dict(payload)


@pytest.mark.parametrize("mismatch", ("cohort", "grain", "period"))
def test_wrong_competitor_metric_context_degrades_without_using_value(mismatch):
    _, record, *_ = competitor_detail_bundle(metric_mismatch=mismatch)
    metric = record.metrics[0]
    assert metric.availability is Availability.UNAVAILABLE
    assert metric.value is None
    assert any(mismatch in item for item in metric.limitations)


def test_true_competitor_set_reference_mismatch_fails():
    (
        competitor_set,
        _,
        scope,
        scope_ref,
        category,
        cohort,
        canonical,
        included_cohort,
        included_denominator,
        snapshot,
        pi_ref,
        period,
    ) = competitor_bundle()
    wrong_set_ref = build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace="market-report-v0.2.true-competitor-set",
        target_id="set:wrong",
        target_version=competitor_set.contract_version,
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="supplied set"):
        CompetitorDetailAdapter().project_record(
            scope_context=scope,
            scope_reference=scope_ref,
            true_competitor_set=competitor_set,
            true_competitor_set_reference=wrong_set_ref,
            purpose=CompetitorDetailPurpose.INCLUDED_COMPETITORS,
            grain_entity_reference_id=canonical.reference_id,
            product_intelligence_snapshot=snapshot,
            product_intelligence_reference=pi_ref,
            canonical_references=(canonical,),
            fields=(
                available_field(
                    "title",
                    CompetitorFieldGroup.IDENTITY_CATALOG,
                    "Title",
                    "Title",
                    (pi_ref.reference_id,),
                ),
            ),
            metrics=(),
            metric_boundaries={},
            references=(category, cohort, included_cohort, included_denominator, period),
            provenance_reference_ids=(PROVENANCE,),
        )


def test_duplicate_competitor_detail_row_fails():
    section, record, *_ = competitor_detail_bundle()
    with pytest.raises(MarketReportV0_2ValidationError, match="duplicate"):
        build_competitor_detail_section(
            availability=section.availability,
            purpose=section.purpose,
            scope_context_reference_id=section.scope_context_reference_id,
            true_competitor_set_reference_id=section.true_competitor_set_reference_id,
            records=(record, record),
            references=section.references,
            provenance_reference_ids=section.provenance_reference_ids,
            limitations=section.limitations,
        )


def test_competitor_detail_identity_is_input_permutation_invariant():
    first, *_ = competitor_detail_bundle(reverse=False)
    second, *_ = competitor_detail_bundle(reverse=True)
    assert first.to_dict() == second.to_dict()


def test_field_level_unavailable_requires_null_and_limitation():
    _, _, _, _, _, _, _, _, pi_ref = competitor_detail_bundle()
    with pytest.raises(MarketReportV0_2ValidationError):
        build_field_projection(
            field_name="seller_location",
            field_group=CompetitorFieldGroup.SELLER_MARKETING,
            availability=Availability.UNAVAILABLE,
            presence_status=PresenceStatus.MISSING,
            evidence_semantics=EvidenceSemantics.UNKNOWN,
            value="US",
            display_value="US",
            method_policy_id=None,
            method_policy_version=None,
            source_reference_ids=(pi_ref.reference_id,),
            evidence_ids=(),
            provenance_reference_ids=(PROVENANCE,),
            limitations=(),
        )


def test_competitor_detail_strict_round_trip_and_unknown_field_rejection():
    section, *_ = competitor_detail_bundle()
    assert CompetitorDetailSection.from_dict(section.to_dict()) == section
    payload = section.to_dict()
    payload["renderer_hint"] = "xlsx"
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown fields"):
        CompetitorDetailSection.from_dict(payload)


def test_contracts_and_projections_contain_no_raw_payload_or_credential_fields():
    distribution, *_ = distribution_bundle(with_economics=True)
    details, *_ = competitor_detail_bundle()
    payload = json.dumps(
        {"distribution": distribution.to_dict(), "details": details.to_dict()},
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "raw_payload",
        "authorization",
        "api_key",
        "access_token",
        "credential",
    ):
        assert forbidden not in payload


def test_sp039c_builders_make_zero_network_or_provider_calls(monkeypatch):
    import socket

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    distribution, *_ = distribution_bundle(with_economics=True)
    details, *_ = competitor_detail_bundle()
    assert distribution.availability is Availability.PARTIAL
    assert details.availability is Availability.PARTIAL


@pytest.mark.parametrize(
    ("name", "contract_type"),
    (
        ("sp039c_attribute_distribution.json", DistributionSectionItem),
        (
            "sp039c_numeric_distribution_unavailable_economics.json",
            DistributionSectionItem,
        ),
        (
            "sp039c_competitor_detail_partial_fields.json",
            CompetitorDetailSection,
        ),
    ),
)
def test_checked_in_sp039c_fixtures_strictly_round_trip(name, contract_type):
    payload = json.loads((SP039C_FIXTURES / name).read_text(encoding="utf-8"))
    contract = contract_type.from_dict(payload)
    assert contract.to_dict() == payload


def test_checked_in_fixtures_have_no_delivery_or_secret_surface():
    forbidden = {
        "renderer",
        "xlsx",
        "markdown",
        "pipeline",
        "authorization",
        "api_key",
        "access_token",
        "raw_payload",
        "credential",
    }
    for path in SP039C_FIXTURES.glob("sp039c_*.json"):
        payload = path.read_text(encoding="utf-8").casefold()
        assert not any(f'"{name}"' in payload for name in forbidden)
