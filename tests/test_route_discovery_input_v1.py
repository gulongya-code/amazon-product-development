from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from amazon_product_intelligence.adapters import AdaptationContext
from amazon_product_intelligence.connectors import (
    SorftimeProductRequest,
    parse_product_request_response,
)
from amazon_product_intelligence.adapters.sorftime_dto_mapper_v0_1 import (
    PRODUCT_REQUEST_PAYLOAD_KIND,
    SorftimeDtoMapperV0_1,
    sorftime_sanitized_mapping_request,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    EvidenceType,
    FactGroup,
    MetricObservation,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    ResultStatus,
    Scope,
    ScopeStatus,
    ScopeType,
    SemanticStatus,
    SubjectRef,
    SubjectType,
    TimeWindow,
    TransformationCodeVersion,
    TransformationProvenance,
    TransformationRunRecord,
    TransformationStatus,
    Unit,
    ValueEnvelope,
    ValueType,
    VersionStatus,
    CodeVersionScheme,
    Provenance,
    canonical_json,
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.route_discovery_input import (
    ROUTE_INPUT_FIELD_MAPPINGS,
    ROUTE_INPUT_SOURCE_KIND,
    RouteDiscoveryInputContext,
    RouteDiscoveryInputError,
    RouteInputAvailabilityStatus,
    RouteInputLineageDisposition,
    build_route_discovery_input,
)
from amazon_product_intelligence.route_discovery_v2 import (
    build_route_discovery_v2,
    load_route_discovery_v2_config,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from amazon_product_intelligence.sellersprite_import.models import (
    ImportValueStatus,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "route_discovery_input" / "v1"
PROFILES = ROOT / "config" / "category_semantic_profiles"
ROUTE_CONFIGS = ROOT / "config" / "route_discovery_v2"
RETRIEVED_AT = "2026-08-29T07:59:00Z"
TRANSFORMED_AT = "2026-08-29T07:59:30Z"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _value_type(value: Any) -> ValueType:
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    if isinstance(value, int):
        return ValueType.INTEGER
    if isinstance(value, float):
        return ValueType.NUMBER
    return ValueType.STRING


def _bundles(payload: dict[str, Any], *, reverse: bool = False) -> tuple[CanonicalEvidenceBundle, ...]:
    raw_observations = list(payload["observations"])
    if reverse:
        raw_observations.reverse()
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for raw in raw_observations:
        by_provider.setdefault(str(raw["provider"]), []).append(raw)
    result: list[CanonicalEvidenceBundle] = []
    for provider in sorted(by_provider, reverse=reverse):
        raw_ref = f"raw:{provider}:route-input-fixture"
        run_id = f"transform:{provider}:route-input-fixture"
        collection_id = f"collection:{provider}:route-input-fixture"
        schema = ProviderSchemaVersion(
            status=VersionStatus.UNKNOWN,
            value=None,
            source=ProviderSchemaSource.UNKNOWN,
        )
        code = TransformationCodeVersion(
            status=VersionStatus.KNOWN,
            value="route-input-fixture-v1",
            scheme=CodeVersionScheme.RULESET_VERSION,
        )
        observations = []
        for raw in by_provider[provider]:
            asin = str(raw["asin"])
            subject = SubjectRef(
                subject_type=SubjectType.PRODUCT,
                subject_id=product_id("US", asin),
                marketplace="US",
            )
            presence = PresenceStatus(raw.get("presence", "PRESENT"))
            value = raw.get("value") if presence is PresenceStatus.PRESENT else None
            unit_raw = raw.get("unit")
            unit = None if unit_raw is None else Unit(**unit_raw)
            evidence = (
                EvidenceType.PROVIDER_ESTIMATE
                if raw.get("estimate", False)
                else EvidenceType.OBSERVED
            )
            identity_material = {
                "provider": provider,
                "asin": asin,
                "kind": raw["kind"],
                "name": raw["name"],
                "presence": presence.value,
                "value": value,
                "unit": unit_raw,
            }
            observation_id = deterministic_id("fixture-observation", identity_material)
            transformation = TransformationProvenance(
                collection_run_id=collection_id,
                provider_schema_version=schema,
                mapping_version="fixture-canonical-mapping-v1",
                transformation_run_id=run_id,
                transformation_code_version=code,
                raw_evidence_reference=raw_ref,
                transformed_at=TRANSFORMED_AT,
                transformation_status=TransformationStatus.SUCCESS,
            )
            provenance = Provenance(
                provider=provider,
                source_tool="fixture_export",
                source_field=f"source.{raw['name']}",
                source_record_identity=subject.subject_id,
                retrieved_at=RETRIEVED_AT,
                transformation=transformation,
            )
            envelope = ValueEnvelope(
                presence_status=presence,
                raw_value=value,
                normalized_value=None,
                value_type=_value_type(value),
                unit=unit,
                normalization_status=NormalizationStatus.NOT_ATTEMPTED,
                semantic_status=SemanticStatus.CONFIRMED,
            )
            common = dict(
                semantic_observation_id=deterministic_id(
                    "fixture-semantic-observation", identity_material
                ),
                observation_id=observation_id,
                subject=subject,
                evidence_type=evidence,
                value=envelope,
                scope=Scope(
                    scope_type=ScopeType.ASIN,
                    scope_status=ScopeStatus.CONFIRMED,
                    scope_subject_id=subject.subject_id,
                ),
                time=TimeWindow(
                    observed_at=None,
                    observed_at_status=ObservedAtStatus.UNKNOWN,
                    retrieved_at=RETRIEVED_AT,
                    period_start=None,
                    period_end=None,
                    period_type=PeriodType.UNKNOWN,
                    timezone=None,
                ),
                provenance=provenance,
                quality_issue_ids=(),
                result_status=(
                    ResultStatus.POPULATED
                    if presence is PresenceStatus.PRESENT
                    else ResultStatus.UNKNOWN
                ),
            )
            if raw["kind"] == "PRODUCT_FACT":
                observations.append(ProductFactObservation(
                    observation_kind=ObservationKind.PRODUCT_FACT,
                    dimension=str(raw["name"]),
                    fact_group=FactGroup(raw.get("fact_group", "OTHER")),
                    provider_semantic=None,
                    **common,
                ))
            else:
                observations.append(MetricObservation(
                    observation_kind=ObservationKind.METRIC,
                    metric=str(raw["name"]),
                    measurement_type=evidence,
                    metric_semantic=None,
                    currency=(
                        unit.unit_code
                        if unit is not None and unit.dimension == "CURRENCY"
                        else None
                    ),
                    **common,
                ))
        run = TransformationRunRecord(
            provider=provider,
            collection_run_id=collection_id,
            provider_schema_version=schema,
            mapping_version="fixture-canonical-mapping-v1",
            transformation_run_id=run_id,
            transformation_code_version=code,
            started_at=TRANSFORMED_AT,
            completed_at=TRANSFORMED_AT,
            status=TransformationStatus.SUCCESS,
            input_raw_evidence_references=(raw_ref,),
            output_observation_ids=tuple(item.observation_id for item in observations),
            quality_issue_ids=(),
        )
        result.append(CanonicalEvidenceBundle(
            transformation_runs=(run,),
            observations=tuple(observations),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
            raw_evidence_references=(raw_ref,),
        ))
    return tuple(result)


def _context(payload: dict[str, Any]) -> RouteDiscoveryInputContext:
    raw = payload["context"]
    return RouteDiscoveryInputContext(
        marketplace=raw["marketplace"],
        category=raw["category"],
        imported_at=raw["imported_at"],
        normalization_run_id="normalize:route-input-fixture",
        normalized_at=raw["normalized_at"],
        observed_date=raw["observed_date"],
    )


def _build(name: str, *, reverse: bool = False):
    payload = _fixture(name)
    return build_route_discovery_input(
        _bundles(payload, reverse=reverse), context=_context(payload)
    )


def _field(package, header: str):
    return next(item for item in package.dataset.records[0].fields if item.header == header)


def _available(package, canonical_field: str):
    return next(
        item for item in package.field_availability
        if item.canonical_field == canonical_field
    )


def test_mapping_contract_is_explicit_and_contains_no_provider_selection() -> None:
    keys = {(item.observation_kind, item.canonical_name) for item in ROUTE_INPUT_FIELD_MAPPINGS}
    assert ("PRODUCT_FACT", "asin") in keys
    assert ("PRODUCT_FACT", "title") in keys
    assert ("METRIC", "estimated_monthly_sales") in keys
    assert ("METRIC", "price") in keys
    assert all("provider" not in item.canonical_field for item in ROUTE_INPUT_FIELD_MAPPINGS)


def test_complete_valid_observation_builds_s2_and_route_v2_input() -> None:
    package = _build("complete_valid_observation")
    record = package.dataset.records[0]
    assert package.dataset.source_kind == ROUTE_INPUT_SOURCE_KIND
    assert record.asin == "B0TEST0001"
    assert record.parent_asin == "B0PARENT01"
    assert str(_field(package, "价格($)").value) == "24.99"
    assert _field(package, "评分数").value == 1234
    assert _field(package, "月销量").value == 120
    assert "installation type: adhesive" in _field(package, "详细参数").value
    assert set(package.provider_ids) == {"provider_alpha", "provider_beta"}
    assert package.source_raw_evidence_references
    assert all(item.raw_evidence_reference for item in package.field_lineage)

    profile = load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json")
    semantic = build_semantic_engine_v2_result(package.dataset, profile=profile)
    config = load_route_discovery_v2_config(ROUTE_CONFIGS / "shower_caddies.v2.json")
    result = build_route_discovery_v2(
        package.dataset, semantic, profile=profile, config=config
    )
    assert result.upstream_dataset_id == package.dataset.dataset_id
    assert dict(result.diagnostics)["provider_calls"] == 0


def test_existing_sorftime_dto_mapper_bundle_enters_the_same_boundary_offline() -> None:
    request = SorftimeProductRequest(ASIN="B09265WXY5", Trend=2)
    response = parse_product_request_response(
        json.loads(
            (ROOT / "tests" / "fixtures" / "sorftime_dtos" / "v0_1"
             / "product_request_rich_wire.json").read_text(encoding="utf-8")
        ),
        request,
    )
    adaptation = SorftimeDtoMapperV0_1().map_product_request(
        request,
        response,
        AdaptationContext(
            provider="sorftime",
            payload_kind=PRODUCT_REQUEST_PAYLOAD_KIND,
            source_tool="ProductRequest",
            marketplace="US",
            locale="en-us",
            retrieved_at=RETRIEVED_AT,
            transformed_at=TRANSFORMED_AT,
            collection_run_id="collection:sorftime:route-input-offline",
            sanitized_request=sorftime_sanitized_mapping_request(request),
            currency="USD",
        ),
    )
    package = build_route_discovery_input(
        (adaptation.bundle,),
        context=RouteDiscoveryInputContext(
            marketplace="US",
            category="shower caddies",
            imported_at="2026-08-29T08:00:00Z",
            normalization_run_id="normalize:sorftime:route-input-offline",
            normalized_at="2026-08-29T08:01:00Z",
        ),
    )
    assert package.provider_ids == ("sorftime",)
    requested = next(
        item for item in package.dataset.records if item.asin == "B09265WXY5"
    )
    title = next(item for item in requested.fields if item.header == "商品标题")
    assert title.import_status is ImportValueStatus.NORMALIZED
    assert package.source_raw_evidence_references == (
        adaptation.bundle.raw_evidence_references[0],
    )


def test_missing_optional_fields_are_explicit_and_not_fabricated() -> None:
    package = _build("missing_optional_fields")
    price = _field(package, "价格($)")
    sales = _field(package, "月销量")
    assert price.value is None and sales.value is None
    assert price.import_status is ImportValueStatus.MISSING_HEADER
    assert _available(package, "metric.price").status is RouteInputAvailabilityStatus.MISSING
    assert package.dataset.observed_date is None


def test_missing_required_identity_fails_closed() -> None:
    with pytest.raises(RouteDiscoveryInputError) as caught:
        _build("missing_required_identity")
    assert caught.value.code == "INPUT_REQUIRED_IDENTITY_MISSING"


def test_equivalent_duplicate_observations_are_deduplicated_with_all_lineage() -> None:
    package = _build("duplicate_observations")
    assert package.duplicate_observation_count >= 3
    title = _field(package, "商品标题")
    assert title.value == "Tension Pole Shower Caddy"
    assert "EQUIVALENT_DUPLICATE_OBSERVATION" in title.issue_codes
    title_lineage = [
        item for item in package.field_lineage
        if item.canonical_field == "product.title"
    ]
    assert len(title_lineage) == 2
    assert {item.provider for item in title_lineage} == {
        "provider_alpha", "provider_beta"
    }
    assert {
        item.disposition for item in title_lineage
    } == {RouteInputLineageDisposition.ACCEPTED_EQUIVALENT}


def test_provider_conflict_never_selects_a_provider_value() -> None:
    package = _build("provider_conflict")
    title = _field(package, "商品标题")
    assert title.value is None
    assert title.import_status is ImportValueStatus.PARSE_FAILED
    assert _available(package, "product.title").status is RouteInputAvailabilityStatus.CONFLICT
    assert package.conflict_field_count == 1
    assert any(item.code == "PROVIDER_CONFLICT" and item.blocking for item in package.issues)
    detail = _field(package, "详细参数")
    assert "installation type: adhesive" in detail.value
    assert "installation type: hanging" in detail.value
    assert "ATTRIBUTE_CONFLICT_PRESERVED" in detail.issue_codes


def test_malformed_numerics_are_invalid_not_zero_or_raw_strings() -> None:
    package = _build("malformed_numerical_fields")
    assert _field(package, "价格($)").value is None
    assert _field(package, "价格($)").import_status is ImportValueStatus.PARSE_FAILED
    assert _field(package, "评分数").value is None
    assert _available(package, "metric.review_count").status is RouteInputAvailabilityStatus.INVALID


def test_explicit_unavailable_and_null_data_remain_distinct() -> None:
    package = _build("unavailable_data")
    sales = _field(package, "月销量")
    rating = _field(package, "评分")
    assert sales.value is None and rating.value is None
    assert sales.import_status is ImportValueStatus.NOT_AVAILABLE
    assert rating.import_status is ImportValueStatus.BLANK
    assert _available(package, "metric.estimated_monthly_sales").status is RouteInputAvailabilityStatus.UNAVAILABLE
    assert _available(package, "metric.rating").status is RouteInputAvailabilityStatus.EXPLICIT_NULL


def test_repeat_conversion_and_input_order_are_deterministic() -> None:
    first = _build("complete_valid_observation")
    second = _build("complete_valid_observation", reverse=True)
    assert first.package_id == second.package_id
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.dataset.dataset_id == second.dataset.dataset_id
    assert first.dataset.semantic_fingerprint == second.dataset.semantic_fingerprint
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())
    assert first.semantic_fingerprint == sha256(
        canonical_json(first.semantic_dict()).encode("utf-8")
    ).hexdigest()


def test_incompatible_marketplace_subject_fails_closed() -> None:
    payload = _fixture("complete_valid_observation")
    bundles = _bundles(payload)
    observation = bundles[0].observations[0]
    incompatible = replace(
        observation,
        subject=SubjectRef(
            subject_type=SubjectType.PRODUCT,
            subject_id=product_id("CA", "B0TEST0001"),
            marketplace="CA",
        ),
    )
    run = bundles[0].transformation_runs[0]
    changed_bundle = CanonicalEvidenceBundle(
        transformation_runs=(run,),
        observations=(incompatible, *bundles[0].observations[1:]),
        conflicts=(), resolutions=(), quality_issues=(),
        raw_evidence_references=bundles[0].raw_evidence_references,
    )
    with pytest.raises(RouteDiscoveryInputError) as caught:
        build_route_discovery_input(
            (changed_bundle, *bundles[1:]), context=_context(payload)
        )
    assert caught.value.code == "INPUT_MARKETPLACE_OR_IDENTITY_MISMATCH"


def test_unit_incompatible_value_fails_closed_at_field_grain() -> None:
    payload = _fixture("complete_valid_observation")
    price = next(item for item in payload["observations"] if item["name"] == "price")
    price["unit"] = {
        "dimension": "CURRENCY", "unit_code": "EUR", "unit_system": "ISO_4217"
    }
    package = build_route_discovery_input(_bundles(payload), context=_context(payload))
    assert _field(package, "价格($)").value is None
    assert _available(package, "metric.price").status is RouteInputAvailabilityStatus.INVALID


def test_self_parent_identity_is_not_promoted() -> None:
    payload = _fixture("complete_valid_observation")
    parent = next(
        item for item in payload["observations"]
        if item["name"] == "parent_product_relationship"
    )
    parent["value"] = parent["asin"]
    package = build_route_discovery_input(_bundles(payload), context=_context(payload))
    assert package.dataset.records[0].parent_asin is None
    parent_field = _field(package, "父ASIN")
    assert parent_field.value is None
    assert parent_field.import_status is ImportValueStatus.PARSE_FAILED
    assert "SELF_PARENT_IDENTITY_REJECTED" in parent_field.issue_codes
