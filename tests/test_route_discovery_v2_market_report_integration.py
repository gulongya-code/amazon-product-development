from __future__ import annotations

from copy import copy
from dataclasses import replace
from pathlib import Path

import pytest

from amazon_product_intelligence.market_report.v0_2 import (
    market_report_v0_2_from_dict,
)
from amazon_product_intelligence.market_report.v0_2.integrations import (
    RouteDiscoveryV2MarketReportIntegrationError,
    RouteDiscoveryV2MarketReportProjection,
    integrate_route_discovery_v2,
    project_route_discovery_v2,
)
from amazon_product_intelligence.market_report.v0_2.models import (
    Availability,
    ExternalIntegrationState,
)
from amazon_product_intelligence.route_discovery_v2 import (
    build_route_discovery_v2,
    load_route_discovery_v2_config,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from tests.test_market_report_v0_2_sp039e import build_snapshot
from tests.test_route_discovery_v2 import (
    CONFIGS,
    PROFILES,
    _architecture_records,
    _build,
    _dataset,
    _record,
)


def _selected_result():
    records = _architecture_records((
        ("adhesive", "wall", 3),
        ("hanging", "wall", 3),
        ("suction", "wall", 3),
    ))
    *_, result = _build(records)
    return records, result


def _insufficient_candidate_result():
    records = _architecture_records((
        ("adhesive", "wall", 3),
        ("hanging", "wall", 3),
    ))
    *_, result = _build(records)
    return result


def _empty_route_result():
    records = tuple(_record(index) for index in range(1, 4))
    *_, result = _build(records)
    return result


def _result_compatible_with(report):
    references = {
        item.reference_id: item for item in report.evidence_registry.references
    }
    cohort = references[report.scope_context.analysis_cohort_reference_id]
    records = (
        _record(1, detail="Installation: Adhesive | Attachment: Wall"),
        _record(2, detail="Installation: Adhesive | Attachment: Wall"),
    )
    dataset = replace(
        _dataset(records),
        dataset_id=cohort.target_id,
        semantic_fingerprint=cohort.content_fingerprint,
    )
    profile = load_category_semantic_profile(
        Path(PROFILES) / "shower_caddies.v1_1.json"
    )
    semantic = build_semantic_engine_v2_result(dataset, profile=profile)
    config = replace(
        load_route_discovery_v2_config(
            Path(CONFIGS) / "shower_caddies.v2.json"
        ),
        min_route_size=2,
        fingerprint="test-only-min-route-size-2",
    )
    return build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )


def test_successful_route_v2_projection_is_reference_only_and_available() -> None:
    _, result = _selected_result()
    projection = project_route_discovery_v2(result)

    assert projection.availability is Availability.AVAILABLE
    assert projection.route_ids == tuple(sorted(
        item.route_id for item in result.routes
    ))
    assert projection.source_reference.target_id == result.result_id
    assert (
        projection.source_reference.content_fingerprint
        == result.semantic_fingerprint
    )
    assert projection.attachment.external_reference_id == (
        projection.source_reference.reference_id
    )
    assert projection.attachment.provenance_reference_ids == (
        projection.provenance.provenance_id,
    )
    assert projection.evidence.content_fingerprint == result.semantic_fingerprint
    assert "confidence" not in projection.to_dict()
    assert RouteDiscoveryV2MarketReportProjection.from_dict(
        projection.to_dict()
    ) == projection


def test_empty_route_result_remains_explicitly_unavailable() -> None:
    result = _empty_route_result()
    projection = project_route_discovery_v2(result)

    assert result.routes == ()
    assert projection.route_ids == ()
    assert projection.availability is Availability.UNAVAILABLE
    assert "ROUTE_DISCOVERY_V2_NO_VIABLE_ROUTES" in projection.limitations
    assert projection.attachment.availability is Availability.UNAVAILABLE


def test_insufficient_candidate_evidence_remains_partial_without_confidence() -> None:
    result = _insufficient_candidate_result()
    projection = project_route_discovery_v2(result)

    assert result.routes
    assert result.candidates == ()
    assert projection.availability is Availability.PARTIAL
    assert (
        "ROUTE_DISCOVERY_V2_CANDIDATE_EVIDENCE_INSUFFICIENT"
        in projection.limitations
    )
    assert projection.evidence.semantics.value == "DERIVED"
    assert "confidence" not in projection.evidence.to_dict()


def test_projection_is_repeatedly_deterministic_and_route_order_is_stable() -> None:
    records, first_result = _selected_result()
    *_, reversed_result = _build(tuple(reversed(records)))

    first = project_route_discovery_v2(first_result)
    repeated = project_route_discovery_v2(first_result)
    reversed_projection = project_route_discovery_v2(reversed_result)

    assert first.to_dict() == repeated.to_dict()
    assert first.projection_id == repeated.projection_id
    assert first.to_dict() == reversed_projection.to_dict()
    assert first.route_ids == tuple(sorted(first.route_ids))


def test_projection_preserves_unique_route_identity_and_source_provenance() -> None:
    _, result = _selected_result()
    projection = project_route_discovery_v2(result)

    assert len(projection.route_ids) == len(set(projection.route_ids))
    assert projection.provenance.source_record_id == result.result_id
    assert projection.provenance.source_version == result.contract_version
    assert projection.provenance.content_fingerprint == result.semantic_fingerprint
    assert projection.evidence.source_reference_ids == (
        projection.source_reference.reference_id,
    )
    assert projection.evidence.provenance_reference_ids == (
        projection.provenance.provenance_id,
    )


def test_malformed_or_duplicate_route_input_fails_closed() -> None:
    _, result = _selected_result()
    with pytest.raises(
        RouteDiscoveryV2MarketReportIntegrationError,
        match="ROUTE_V2_INPUT_TYPE_INVALID",
    ):
        project_route_discovery_v2(result.to_dict())

    duplicate = copy(result)
    object.__setattr__(duplicate, "routes", (result.routes[0], result.routes[0]))
    with pytest.raises(
        RouteDiscoveryV2MarketReportIntegrationError,
        match="ROUTE_V2_INPUT_CONTRACT_INVALID",
    ):
        project_route_discovery_v2(duplicate)


def test_compatible_result_attaches_to_existing_market_report_idempotently() -> None:
    report = build_snapshot()
    result = _result_compatible_with(report)

    integrated = integrate_route_discovery_v2(report, result)
    repeated = integrate_route_discovery_v2(integrated, result)

    assert integrated.external_integrations.state is ExternalIntegrationState.ATTACHED
    route_attachments = tuple(
        item for item in integrated.external_integrations.attachments
        if item.integration_name == "route-discovery-v2"
    )
    assert len(route_attachments) == 1
    assert repeated is integrated
    assert market_report_v0_2_from_dict(integrated.to_dict()).to_dict() == (
        integrated.to_dict()
    )


def test_incompatible_report_cohort_fails_closed() -> None:
    report = build_snapshot()
    _, result = _selected_result()

    with pytest.raises(
        RouteDiscoveryV2MarketReportIntegrationError,
        match="ROUTE_V2_REPORT_COHORT_INCOMPATIBLE",
    ):
        integrate_route_discovery_v2(report, result)


def test_existing_market_report_without_route_input_is_unchanged() -> None:
    report = build_snapshot()

    assert report.external_integrations.state is ExternalIntegrationState.NOT_ATTACHED
    assert report.external_integrations.attachments == ()
    assert market_report_v0_2_from_dict(report.to_dict()).to_dict() == report.to_dict()
