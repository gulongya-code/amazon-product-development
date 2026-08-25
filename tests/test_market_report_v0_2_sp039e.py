from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
import json
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    CategoryInformation,
    DataWindow,
    MarketReportSnapshot,
    OpportunityDimensionReport,
    OpportunityReportSection,
    ReportAvailability,
    SampleInformation,
)
from amazon_product_intelligence.market_report.v0_2 import (
    compose_market_report_v0_2,
    market_report_v0_2_from_dict,
)
from amazon_product_intelligence.market_report.v0_2.adapters import (
    CompetitorStructureAdapter,
    ExecutiveSummaryAdapter,
    GovernedExecutiveClaimInput,
    OpportunityProjectionAdapter,
    ReportContextAdapter,
    ValidatedExecutiveSource,
)
from amazon_product_intelligence.market_report.v0_2.models import (
    Availability,
    CompletenessStatus,
    EvidenceRecord,
    EvidenceSemantics,
    ExecutiveClaimCategory,
    ExternalIntegrationState,
    MarketReportSnapshotV0_2,
    MarketReportV0_2ValidationError,
    MetricSampleContext,
    MetricValueType,
    PresenceStatus,
    ReferenceKind,
    ReportProvenanceRecord,
    build_category_context,
    build_evidence_registry,
    build_executive_claim,
    build_external_integrations,
    build_metric_context,
    build_product_direction_section,
    build_reference,
    build_sample_context,
    build_sanitized_appendix,
    build_competitor_shortlist_section,
    unavailable_metric,
)
from tests.test_market_report_v0_2_sp039d import PROVENANCE, graph_bundle


GENERATED_AT = "2026-08-25T08:00:00Z"
FIXTURES = Path(__file__).parent / "fixtures" / "market_report_v0_2"


def _find(references, reference_id):
    return next(item for item in references if item.reference_id == reference_id)


def _local(namespace: str, target_id: str, target_version: str):
    return build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace=namespace,
        target_id=target_id,
        target_version=target_version,
    )


def _metric(
    *,
    name: str,
    value_type: MetricValueType,
    value: int | float,
    scope_reference_id: str,
    cohort_reference_id: str,
    denominator_reference_id: str | None = None,
    period_reference_id: str | None = None,
    currency: str | None = None,
    unit: str | None = None,
    sample_count: int = 1,
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
        product_grain_reference_id=scope_reference_id,
        method_policy_id="policy:sp039e-governed-metric",
        method_policy_version="v1",
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


def _source_context(graph, *, retrieved_at="2026-08-25T09:00:00Z"):
    scope = graph["scope"]
    category_ref = _find(scope.references, scope.category_reference_id)
    cohort_ref = _find(scope.references, scope.analysis_cohort_reference_id)
    period_ref = next(
        item
        for item in graph["detail_record"].references
        if item.namespace == "data-window"
    )
    category_source = CategoryInformation(
        category_id="category:US:dog-water-bottle",
        category_name="Dog Water Bottles",
        marketplace="US",
        scope="dog-water-bottle",
        provenance_reference_ids=(PROVENANCE,),
    )
    sample_material = {
        "sample_size": scope.included_grain_entity_count,
        "unique_asin_count": scope.included_grain_entity_count,
        "provider_total": None,
        "asin_coverage": None,
        "availability": ReportAvailability.PARTIAL,
        "provenance_reference_ids": (PROVENANCE,),
        "limitations": ("Provider total was not governed",),
    }
    sample_source = SampleInformation(
        sample_id=deterministic_id("market-report-sample", sample_material),
        **sample_material,
    )
    window_material = {
        "period": "2026-07",
        "start_at": "2026-07-01T00:00:00Z",
        "end_at": "2026-07-31T23:59:59Z",
        "availability": ReportAvailability.AVAILABLE,
        "provenance_reference_ids": (PROVENANCE,),
        "limitations": (),
    }
    window_source = DataWindow(
        window_id=deterministic_id("market-report-data-window", window_material),
        **window_material,
    )
    adapter = ReportContextAdapter()
    return (
        adapter.category(category_source, source_reference=category_ref),
        adapter.sample(sample_source, source_reference=cohort_ref, analysis_cohort_reference=cohort_ref),
        adapter.data_window(window_source, source_reference=period_ref, retrieved_at=retrieved_at),
        category_ref,
        cohort_ref,
        period_ref,
    )


def _market_size(graph, *, unavailable=False, monthly_sales_value=120):
    scope = graph["scope"]
    scope_ref = graph["scope_ref"]
    cohort = _find(scope.references, scope.analysis_cohort_reference_id)
    period = next(item for item in graph["detail_record"].references if item.namespace == "data-window")
    if unavailable:
        sales = unavailable_metric(
            metric_name="monthly_sales",
            value_type=MetricValueType.COUNT,
            marketplace="US",
            product_grain_reference_id=scope_ref.reference_id,
            provenance_reference_ids=(PROVENANCE,),
            limitations=("monthly sales unavailable",),
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
            limitations=("monthly revenue unavailable",),
            presence_status=PresenceStatus.MISSING,
            currency_code="USD",
            period_reference_id=period.reference_id,
            cohort_reference_id=cohort.reference_id,
        )
    else:
        sales = _metric(
            name="monthly_sales", value_type=MetricValueType.COUNT, value=monthly_sales_value,
            scope_reference_id=scope_ref.reference_id, cohort_reference_id=cohort.reference_id,
            period_reference_id=period.reference_id, unit="units/month",
            sample_count=scope.included_grain_entity_count,
        )
        revenue = _metric(
            name="monthly_revenue", value_type=MetricValueType.MONEY, value=2400.0,
            scope_reference_id=scope_ref.reference_id, cohort_reference_id=cohort.reference_id,
            period_reference_id=period.reference_id, currency="USD",
            sample_count=scope.included_grain_entity_count,
        )
    from amazon_product_intelligence.market_report.v0_2.adapters import MarketSizeAdapter
    return MarketSizeAdapter().adapt(
        scope_context=scope,
        scope_reference=scope_ref,
        monthly_sales=sales,
        monthly_revenue=revenue,
        references=(cohort, period),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("market economics unavailable",) if unavailable else (),
    )


def _structure(graph):
    competitors = graph["competitor_set"]
    included = _find(competitors.references, competitors.included_cohort_reference_id)
    denominator = _find(competitors.references, competitors.included_denominator_reference_id)
    values = {
        "competitor_count": (MetricValueType.COUNT, 1, None),
        "product_concentration": (MetricValueType.SHARE, 1.0, denominator.reference_id),
        "brand_concentration": (MetricValueType.SHARE, 1.0, denominator.reference_id),
        "seller_concentration": (MetricValueType.SHARE, 1.0, denominator.reference_id),
        "review_barrier": (MetricValueType.NUMBER, 240.0, None),
        "rating_barrier": (MetricValueType.NUMBER, 4.4, None),
    }
    metrics = {
        name: _metric(
            name=name,
            value_type=value_type,
            value=value,
            scope_reference_id=graph["scope_ref"].reference_id,
            cohort_reference_id=included.reference_id,
            denominator_reference_id=denominator_id,
        )
        for name, (value_type, value, denominator_id) in values.items()
    }
    disposition = competitors.dispositions[0]
    return CompetitorStructureAdapter().adapt(
        scope_context=graph["scope"],
        scope_reference=graph["scope_ref"],
        true_competitor_set=competitors,
        true_competitor_set_reference=graph["set_ref"],
        governed_metrics=metrics,
        head_entity_reference_ids=(disposition.grain_entity_reference_id,),
        references=competitors.references,
        provenance_reference_ids=(PROVENANCE,),
    )


def _opportunity(*, pending=False):
    dimension = OpportunityDimensionReport(
        dimension="market_attractiveness",
        status="UNKNOWN" if pending else "CALCULATED",
        score_value=None if pending else 42.0,
        contribution=None if pending else 21.0,
        max_contribution=50.0,
        evidence_ids=("evidence:opportunity-dimension",),
        provenance_reference_ids=(PROVENANCE,),
        explanation="Awaiting governed evidence" if pending else "Governed source projection",
    )
    source = OpportunityReportSection(
        score_id="opportunity-score:fixture",
        candidate_id="candidate:fixture",
        score_status="PENDING_DATA" if pending else "CALCULATED",
        score_value=None if pending else 42.0,
        confidence="LOW" if pending else "MEDIUM",
        policy_version="opportunity-score-policy-v0.1",
        policy_fingerprint="sha256:opportunity-policy-fixture",
        dimensions=(dimension,),
        risks=(),
        limitations=("score awaits governed source data",) if pending else (),
        evidence_ids=("evidence:opportunity", "evidence:opportunity-dimension"),
        provenance_reference_ids=(PROVENANCE,),
    )
    source_ref = build_reference(
        kind=ReferenceKind.EXTERNAL_PROVENANCE,
        namespace="opportunity",
        target_id=source.score_id,
        target_version="market-report-v0.1-opportunity-section-v0.1",
        content_fingerprint="sha256:opportunity-source-fixture",
        provenance_reference_ids=(PROVENANCE,),
    )
    return OpportunityProjectionAdapter().adapt(
        source,
        source_contract_version="market-report-v0.1-opportunity-section-v0.1",
        source_reference=source_ref,
    ), source_ref


def _collect_evidence(values):
    found = set()
    def visit(value):
        if is_dataclass(value):
            for item in fields(value):
                child = getattr(value, item.name)
                if item.name.endswith("evidence_ids"):
                    found.update(child)
                else:
                    visit(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                visit(child)
    visit(values)
    return found


def build_snapshot(
    *,
    market_unavailable=False,
    opportunity_pending=False,
    direction_unavailable=False,
    generated_at=GENERATED_AT,
    retrieved_at="2026-08-25T09:00:00Z",
    operational_metadata=None,
    report_limitations=(),
    monthly_sales_value=120,
    reverse=False,
):
    graph = graph_bundle(reverse=reverse)
    category, sample, window, category_ref, _cohort_ref, _period_ref = _source_context(graph, retrieved_at=retrieved_at)
    market = _market_size(graph, unavailable=market_unavailable, monthly_sales_value=monthly_sales_value)
    structure = _structure(graph)
    opportunity, opportunity_ref = _opportunity(pending=opportunity_pending)
    market_ref = _local("market-report-v0.2.market-size", market.section_id, market.contract_version)
    opportunity_projection_ref = _local(
        "market-report-v0.2.opportunity", opportunity.section_id, opportunity.contract_version
    )
    claim_availability = Availability.UNAVAILABLE if market_unavailable else Availability.AVAILABLE
    claim = GovernedExecutiveClaimInput(
        category=ExecutiveClaimCategory.MARKET_CONTEXT,
        availability=claim_availability,
        text="Monthly market economics are unavailable" if market_unavailable else "Governed monthly market economics are represented",
        typed_value=None if market_unavailable else {"monthly_sales": market.monthly_sales.value},
        source_reference_ids=(market_ref.reference_id,),
        evidence_ids=() if market_unavailable else market.monthly_sales.evidence_ids,
        provenance_reference_ids=(PROVENANCE,),
        confidence=None,
        limitations=("monthly sales and revenue were not supplied",) if market_unavailable else (),
    )
    source = ValidatedExecutiveSource(
        reference_id=market_ref.reference_id,
        availability=market.availability,
        evidence_ids=market.monthly_sales.evidence_ids + market.monthly_revenue.evidence_ids,
        provenance_reference_ids=(PROVENANCE,),
    )
    executive = ExecutiveSummaryAdapter().compose(
        inputs=(claim,),
        validated_sources={market_ref.reference_id: source},
    )
    direction = graph["direction"]
    shortlist = graph["shortlist"]
    extra_refs = [market_ref, opportunity_ref, opportunity_projection_ref]
    if direction_unavailable:
        direction = build_product_direction_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=graph["scope_ref"].reference_id,
            buyer_need_link_section_reference_id=graph["links_ref"].reference_id,
            proposal_authority_id=None,
            proposal_authority_version=None,
            directions=(),
            references=(graph["scope_ref"], graph["links_ref"]),
            provenance_reference_ids=(PROVENANCE,),
            limitations=("decision-support evidence is unavailable",),
        )
        shortlist = build_competitor_shortlist_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=graph["scope_ref"].reference_id,
            true_competitor_set_reference_id=graph["set_ref"].reference_id,
            selection_authority_id=None,
            selection_authority_version=None,
            selection_reason_policy_id="policy:shortlist-reasons",
            selection_reason_policy_version="v1",
            items=(),
            references=(graph["scope_ref"], graph["set_ref"]),
            provenance_reference_ids=(PROVENANCE,),
            limitations=("Product Direction evidence is unavailable",),
        )
        direction_ref = _local(
            "market-report-v0.2.product-directions",
            direction.section_id,
            direction.contract_version,
        )
        gap_claim = GovernedExecutiveClaimInput(
            category=ExecutiveClaimCategory.EVIDENCE_GAP,
            availability=Availability.UNAVAILABLE,
            text="Product Direction decision-support evidence is unavailable",
            typed_value=None,
            source_reference_ids=(direction_ref.reference_id,),
            evidence_ids=(),
            provenance_reference_ids=(PROVENANCE,),
            confidence=None,
            limitations=("decision-support evidence is unavailable",),
        )
        executive = ExecutiveSummaryAdapter().compose(
            inputs=(claim, gap_claim),
            validated_sources={
                market_ref.reference_id: source,
                direction_ref.reference_id: ValidatedExecutiveSource(
                    reference_id=direction_ref.reference_id,
                    availability=Availability.UNAVAILABLE,
                    evidence_ids=(),
                    provenance_reference_ids=(PROVENANCE,),
                ),
            },
        )
        extra_refs.append(direction_ref)
    sanitized = build_sanitized_appendix(
        availability=Availability.UNAVAILABLE,
        references=(),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("No governed sanitized appendix attachment was supplied",),
    )
    external = build_external_integrations(
        state=ExternalIntegrationState.NOT_ATTACHED,
        attachments=(),
        limitations=("Keyword Intelligence was not attached; demand is not inferred",),
    )
    sections = (
        category, sample, window, graph["scope"], market, graph["competitor_set"], structure,
        graph["distribution"], graph["detail_section"], graph["projection"], graph["links"],
        direction, shortlist, opportunity, executive, sanitized, external,
    )
    evidence = tuple(
        EvidenceRecord(
            evidence_id=evidence_id,
            semantics=EvidenceSemantics.OBSERVED,
            source_reference_ids=(category_ref.reference_id,),
            provenance_reference_ids=(PROVENANCE,),
            content_fingerprint=None,
            limitations=(),
        )
        for evidence_id in sorted(_collect_evidence(sections))
    )
    provenance = (
        ReportProvenanceRecord(
            provenance_id=PROVENANCE,
            source_namespace="category-product-map",
            source_version="fixture-v1",
            source_record_id="sp039e-offline-fixture",
            availability=Availability.AVAILABLE,
            content_fingerprint="sha256:sp039e-provenance-fixture",
            evidence_ids=(),
            limitations=(),
        ),
    )
    return compose_market_report_v0_2(
        generated_at=generated_at,
        producer_version="sp039e-fixture-producer-v1",
        operational_metadata=operational_metadata or {"runtime_path": "C:\\runtime", "retry_count": 1, "credits": 0},
        category=category,
        sample=sample,
        data_window=window,
        scope_context=graph["scope"],
        market_size=market,
        true_competitor_set=graph["competitor_set"],
        competitor_structure=structure,
        distributions=(graph["distribution"],),
        competitor_details=(graph["detail_section"],),
        buyer_needs=graph["projection"],
        buyer_need_links=graph["links"],
        product_directions=direction,
        competitor_shortlist=shortlist,
        opportunity_score=opportunity,
        executive_summary=executive,
        sanitized_appendix=sanitized,
        external_integrations=external,
        provenance=provenance,
        evidence=evidence,
        references=tuple(reversed(extra_refs)) if reverse else tuple(extra_refs),
        limitations=report_limitations,
    )


def test_complete_p0_composition_and_required_top_level_shape():
    snapshot = build_snapshot()
    assert isinstance(snapshot, MarketReportSnapshotV0_2)
    assert snapshot.metadata.report_version == "market-report-v0.2"
    assert set(snapshot.to_dict()) == {
        "contract_version", "metadata", "category", "sample", "data_window", "scope_context",
        "market_size", "true_competitor_set", "competitor_structure", "distributions",
        "competitor_details", "buyer_needs", "buyer_need_links", "product_directions",
        "competitor_shortlist", "opportunity_score", "executive_summary", "evidence_registry",
        "sanitized_appendix", "external_integrations", "provenance", "limitations",
    }


def test_partial_market_economics_never_become_zero():
    snapshot = build_snapshot(market_unavailable=True)
    assert snapshot.market_size.monthly_sales.value is None
    assert snapshot.market_size.monthly_revenue.value is None
    assert snapshot.executive_summary.claims[0].availability is Availability.UNAVAILABLE
    assert snapshot.executive_summary.claims[0].typed_value is None


def test_buyer_need_valid_while_direction_unavailable():
    snapshot = build_snapshot(direction_unavailable=True)
    assert snapshot.buyer_needs.source_need_order
    assert snapshot.product_directions.availability is Availability.UNAVAILABLE
    assert "decision-support evidence is unavailable" in snapshot.product_directions.limitations
    assert any("decision-support evidence is unavailable" in (claim.text or "") for claim in snapshot.executive_summary.claims)


def test_keyword_not_attached_is_valid_and_not_zero_demand():
    snapshot = build_snapshot()
    assert snapshot.external_integrations.state is ExternalIntegrationState.NOT_ATTACHED
    assert snapshot.external_integrations.keyword_attached is False
    assert "keyword" not in snapshot.executive_summary.to_dict()


def test_opportunity_pending_data_remains_null():
    snapshot = build_snapshot(opportunity_pending=True)
    assert snapshot.opportunity_score.source_section.score_status == "PENDING_DATA"
    assert snapshot.opportunity_score.source_section.score_value is None
    assert snapshot.opportunity_score.availability is Availability.UNAVAILABLE


def test_orphan_local_reference_fails_the_whole_snapshot():
    payload = build_snapshot().to_dict()
    payload["executive_summary"]["claims"][0]["source_reference_ids"] = ["missing:local-reference"]
    payload["executive_summary"]["claims"][0]["claim_id"] = "tampered"
    payload["executive_summary"]["section_id"] = "tampered"
    payload["metadata"]["semantic_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(MarketReportV0_2ValidationError):
        MarketReportSnapshotV0_2.from_dict(payload)


def test_external_provenance_reference_resolves_with_explicit_version():
    snapshot = build_snapshot()
    external = [item for item in snapshot.evidence_registry.references if item.kind is ReferenceKind.EXTERNAL_PROVENANCE]
    assert external
    assert all(item.target_version and item.provenance_reference_ids for item in external)


def test_executive_claim_cannot_upgrade_unavailable_source():
    source = ValidatedExecutiveSource(
        reference_id="reference:source",
        availability=Availability.UNAVAILABLE,
        evidence_ids=(),
        provenance_reference_ids=(PROVENANCE,),
    )
    claim = GovernedExecutiveClaimInput(
        category=ExecutiveClaimCategory.MARKET_CONTEXT,
        availability=Availability.AVAILABLE,
        text="Unsupported value",
        typed_value=0,
        source_reference_ids=(source.reference_id,),
        evidence_ids=(),
        provenance_reference_ids=(PROVENANCE,),
        confidence=None,
        limitations=(),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="upgrade"):
        ExecutiveSummaryAdapter().compose(inputs=(claim,), validated_sources={source.reference_id: source})


def test_executive_claim_rejects_unsupported_decision_semantics():
    with pytest.raises(MarketReportV0_2ValidationError, match="prohibited"):
        build_executive_claim(
            category=ExecutiveClaimCategory.OPPORTUNITY,
            availability=Availability.PARTIAL,
            text="This is a launch decision",
            typed_value=None,
            source_reference_ids=("reference:source",),
            evidence_ids=(),
            provenance_reference_ids=(PROVENANCE,),
            confidence=None,
            limitations=("unsupported",),
        )


def test_semantic_fingerprint_is_permutation_and_runtime_noise_invariant():
    first = build_snapshot(reverse=False, operational_metadata={"runtime_path": "C:\\one", "retry_count": 1, "credits": 10})
    second = build_snapshot(reverse=True, operational_metadata={"runtime_path": "D:\\two", "retry_count": 99, "credits": 999})
    assert first.metadata.semantic_fingerprint == second.metadata.semantic_fingerprint
    assert first.metadata.report_id == second.metadata.report_id


def test_retrieval_time_is_not_observation_window_identity():
    first = build_snapshot(retrieved_at="2026-08-25T09:00:00Z")
    second = build_snapshot(retrieved_at="2026-08-26T09:00:00Z")
    assert first.data_window.retrieved_at != second.data_window.retrieved_at
    assert first.metadata.semantic_fingerprint == second.metadata.semantic_fingerprint


def test_semantic_value_and_limitation_changes_change_fingerprint():
    first = build_snapshot()
    changed_value = build_snapshot(monthly_sales_value=121)
    changed_limitation = build_snapshot(report_limitations=("governed limitation changed",))
    assert first.metadata.semantic_fingerprint != changed_value.metadata.semantic_fingerprint
    assert first.metadata.semantic_fingerprint != changed_limitation.metadata.semantic_fingerprint


def test_generated_at_changes_report_id_not_semantic_fingerprint():
    first = build_snapshot(generated_at="2026-08-25T08:00:00Z")
    second = build_snapshot(generated_at="2026-08-25T08:01:00Z")
    assert first.metadata.semantic_fingerprint == second.metadata.semantic_fingerprint
    assert first.metadata.report_id != second.metadata.report_id


def test_strict_json_round_trip_and_deterministic_serialization():
    snapshot = build_snapshot()
    decoded = market_report_v0_2_from_dict(json.loads(snapshot.to_json(indent=None)))
    assert decoded.to_dict() == snapshot.to_dict()
    assert decoded.to_json(indent=None) == snapshot.to_json(indent=None)


def test_unknown_and_missing_fields_fail_closed():
    payload = build_snapshot().to_dict()
    payload["unknown"] = True
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown"):
        market_report_v0_2_from_dict(payload)
    payload = build_snapshot().to_dict()
    payload.pop("market_size")
    with pytest.raises(MarketReportV0_2ValidationError):
        market_report_v0_2_from_dict(payload)


def test_exact_version_and_v0_1_v0_2_isolation():
    payload = build_snapshot().to_dict()
    payload["metadata"]["report_version"] = "market-report-v0.1"
    with pytest.raises(MarketReportV0_2ValidationError, match="exact"):
        market_report_v0_2_from_dict(payload)
    with pytest.raises(Exception):
        MarketReportSnapshot.from_dict(build_snapshot().to_dict())


def test_sanitized_appendix_rejects_secret_and_raw_path():
    from amazon_product_intelligence.market_report.v0_2.models import build_sanitized_reference
    with pytest.raises(MarketReportV0_2ValidationError, match="secret"):
        build_sanitized_reference(
            content_address="sha256:fixture",
            media_type="text/plain",
            display_text="Authorization: Bearer token",
            source_reference_id="reference:fixture",
            provenance_reference_ids=(PROVENANCE,),
        )
    with pytest.raises(MarketReportV0_2ValidationError, match="path"):
        build_sanitized_reference(
            content_address="sha256:fixture",
            media_type="text/plain",
            display_text="C:\\secret\\raw.json",
            source_reference_id="reference:fixture",
            provenance_reference_ids=(PROVENANCE,),
        )


def test_composition_is_strictly_offline(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network forbidden")))
    assert build_snapshot().metadata.report_version == "market-report-v0.2"


def test_category_scope_marketplace_conflict_fails_closed():
    snapshot = build_snapshot()
    category = build_category_context(
        category_name=snapshot.category.category_name,
        marketplace="CA",
        scope=snapshot.category.scope,
        source_reference_id=snapshot.category.source_reference_id,
        provenance_reference_ids=snapshot.category.provenance_reference_ids,
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="marketplace"):
        replace(snapshot, category=category)


def test_sample_cohort_conflict_fails_closed_and_provider_total_is_not_market_size():
    snapshot = build_snapshot()
    sample = build_sample_context(
        availability=snapshot.sample.availability,
        analysis_cohort_reference_id="reference:different-cohort",
        sample_size=snapshot.sample.sample_size,
        unique_asin_count=snapshot.sample.unique_asin_count,
        provider_total=None,
        asin_coverage=None,
        source_reference_id=snapshot.sample.source_reference_id,
        provenance_reference_ids=snapshot.sample.provenance_reference_ids,
        limitations=snapshot.sample.limitations,
    )
    assert sample.provider_total is None
    assert snapshot.market_size.monthly_sales.value != sample.unique_asin_count
    with pytest.raises(MarketReportV0_2ValidationError, match="cohort"):
        replace(snapshot, sample=sample)


def test_unavailable_observation_window_does_not_infer_from_retrieval_clock():
    graph = graph_bundle()
    period = next(item for item in graph["detail_record"].references if item.namespace == "data-window")
    material = {
        "period": "UNKNOWN",
        "start_at": None,
        "end_at": None,
        "availability": ReportAvailability.UNAVAILABLE,
        "provenance_reference_ids": (PROVENANCE,),
        "limitations": ("observation window not supplied",),
    }
    source = DataWindow(window_id=deterministic_id("market-report-data-window", material), **material)
    projected = ReportContextAdapter().data_window(source, source_reference=period, retrieved_at="2026-08-25T10:00:00Z")
    assert projected.start_at is None and projected.end_at is None
    assert projected.retrieved_at == "2026-08-25T10:00:00Z"


def test_opportunity_adapter_copies_source_without_recalculation():
    projected, _ = _opportunity()
    assert projected.source_section.score_value == 42.0
    assert projected.source_section.policy_fingerprint == "sha256:opportunity-policy-fixture"
    assert projected.source_section.dimensions[0].contribution == 21.0


def test_unresolved_product_grain_cannot_validate_safe_looking_aggregates():
    from amazon_product_intelligence.market_report.v0_2.adapters import ScopeContextAdapter
    snapshot = build_snapshot()
    category_ref = _find(snapshot.evidence_registry.references, snapshot.scope_context.category_reference_id)
    cohort_ref = _find(snapshot.evidence_registry.references, snapshot.scope_context.analysis_cohort_reference_id)
    mixed = ScopeContextAdapter().mixed_unresolved(
        marketplace="US",
        category_reference=category_ref,
        cohort_reference=cohort_ref,
        included_grain_entity_count=snapshot.scope_context.included_grain_entity_count,
        excluded_grain_entity_count=0,
        unresolved_grain_entity_count=1,
        family_relationship_evidence_ids=(),
        provenance_reference_ids=(PROVENANCE,),
        limitations=("parent/child grain unresolved",),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="unsafe aggregates"):
        replace(snapshot, scope_context=mixed)


def test_duplicate_report_local_ids_fail_closed():
    snapshot = build_snapshot()
    with pytest.raises(MarketReportV0_2ValidationError, match="distribution IDs"):
        replace(snapshot, distributions=(snapshot.distributions[0], snapshot.distributions[0]))


def test_removed_registered_reference_is_report_level_orphan():
    snapshot = build_snapshot()
    claim_ref = snapshot.executive_summary.claims[0].source_reference_ids[0]
    registry = build_evidence_registry(
        references=tuple(item for item in snapshot.evidence_registry.references if item.reference_id != claim_ref),
        evidence=snapshot.evidence_registry.evidence,
        limitations=(),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="orphan references"):
        replace(snapshot, evidence_registry=registry)


def test_semantic_reference_cycle_rejected():
    with pytest.raises(MarketReportV0_2ValidationError, match="cycle"):
        MarketReportSnapshotV0_2._reject_cycles({"local:a": {"local:b"}, "local:b": {"local:a"}})


def test_missing_evidence_and_provenance_fail_closed():
    snapshot = build_snapshot()
    registry = build_evidence_registry(
        references=snapshot.evidence_registry.references,
        evidence=snapshot.evidence_registry.evidence[1:],
        limitations=(),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="omits represented evidence"):
        replace(snapshot, evidence_registry=registry)
    with pytest.raises(MarketReportV0_2ValidationError, match="requires report provenance"):
        replace(snapshot, provenance=())


def test_unapproved_external_namespace_fails_at_registry_boundary():
    with pytest.raises(MarketReportV0_2ValidationError, match="unapproved"):
        ReportProvenanceRecord(
            provenance_id="provenance:unapproved",
            source_namespace="arbitrary-provider-payload",
            source_version="v1",
            source_record_id="record",
            availability=Availability.AVAILABLE,
            content_fingerprint=None,
            evidence_ids=(),
            limitations=(),
        )


def test_nested_unknown_fields_and_raw_provider_payload_are_rejected():
    payload = build_snapshot().to_dict()
    payload["sample"]["provider_payload"] = {"raw": True}
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown"):
        market_report_v0_2_from_dict(payload)
    from amazon_product_intelligence.market_report.v0_2.models import SanitizedEvidenceReference
    with pytest.raises(MarketReportV0_2ValidationError, match="unknown"):
        SanitizedEvidenceReference.from_dict(
            {
                "appendix_reference_id": "id",
                "content_address": "sha256:fixture",
                "media_type": "application/json",
                "display_text": None,
                "source_reference_id": "reference:fixture",
                "provenance_reference_ids": [PROVENANCE],
                "raw_provider_payload": {"token": "forbidden"},
            }
        )


def test_report_identity_rejects_self_referential_or_tampered_id():
    from amazon_product_intelligence.market_report.v0_2.models import ReportMetadataV0_2
    payload = build_snapshot().metadata.to_dict()
    payload["report_id"] = payload["report_id"] + ":self"
    with pytest.raises(MarketReportV0_2ValidationError, match="report_id"):
        ReportMetadataV0_2.from_dict(payload)


def test_complete_p0_fixture_round_trips_as_exact_v0_2():
    payload = json.loads((FIXTURES / "sp039e_complete_p0_snapshot.json").read_text(encoding="utf-8"))
    snapshot = market_report_v0_2_from_dict(payload)
    assert snapshot.to_dict() == build_snapshot().to_dict()


def test_partial_economics_fixture_scenario_is_mechanically_true():
    scenario = json.loads((FIXTURES / "sp039e_partial_snapshot_missing_economics.json").read_text(encoding="utf-8"))
    snapshot = build_snapshot(**scenario["builder_args"])
    assert snapshot.market_size.monthly_sales.value is scenario["expected"]["monthly_sales"]
    assert snapshot.market_size.monthly_revenue.value is scenario["expected"]["monthly_revenue"]
    assert snapshot.executive_summary.claims[0].availability.value == scenario["expected"]["executive_claim_availability"]


def test_keyword_not_attached_fixture_scenario_is_mechanically_true():
    scenario = json.loads((FIXTURES / "sp039e_keyword_not_attached.json").read_text(encoding="utf-8"))
    snapshot = build_snapshot(**scenario["builder_args"])
    assert snapshot.external_integrations.state.value == scenario["expected"]["external_integration_state"]
    assert snapshot.external_integrations.keyword_attached is scenario["expected"]["keyword_attached"]
    assert scenario["expected"]["keyword_demand_inferred"] is False


def test_structurally_required_unavailable_sections_survive_round_trip():
    snapshot = build_snapshot(market_unavailable=True, opportunity_pending=True, direction_unavailable=True)
    decoded = market_report_v0_2_from_dict(snapshot.to_dict())
    assert decoded.market_size.availability is Availability.UNAVAILABLE
    assert decoded.product_directions.availability is Availability.UNAVAILABLE
    assert decoded.opportunity_score.availability is Availability.UNAVAILABLE


def test_external_not_attached_registry_rejects_hidden_attachment():
    from amazon_product_intelligence.market_report.v0_2.models import build_external_attachment
    attachment = build_external_attachment(
        integration_name="keyword-intelligence",
        integration_version="keyword-intelligence-v0.1",
        availability=Availability.PARTIAL,
        external_reference_id="reference:keyword",
        provenance_reference_ids=(PROVENANCE,),
        limitations=("attachment is partial",),
    )
    with pytest.raises(MarketReportV0_2ValidationError, match="NOT_ATTACHED"):
        build_external_integrations(
            state=ExternalIntegrationState.NOT_ATTACHED,
            attachments=(attachment,),
            limitations=(),
        )
