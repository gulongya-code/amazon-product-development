from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket
import urllib.request
from unittest.mock import patch

import pytest

from amazon_product_intelligence.adapters import (
    AdaptationContext,
    AdapterContextError,
    AdapterError,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.adapters.sorftime_dto_mapper_v0_1 import (
    ASIN_REQUEST_KEYWORD_PAYLOAD_KIND,
    PRODUCT_REQUEST_PAYLOAD_KIND,
    PRODUCT_VARIATIONS_PAYLOAD_KIND,
    SORFTIME_DTO_CONTRACT_VERSION,
    SORFTIME_DTO_MAPPER_RULESET_VERSION,
    SORFTIME_DTO_MAPPING_SPECIFICATIONS,
    SorftimeDtoMapperV0_1,
    sorftime_sanitized_mapping_request,
)
from amazon_product_intelligence.connectors import (
    SorftimeAsinRequestKeywordRequest,
    SorftimeAsinRequestKeywordResponse,
    SorftimeKeywordSummary,
    SorftimeProductRequest,
    SorftimeProductRequestResponse,
    SorftimeProductVariationsRequest,
    SorftimeProductVariationsResponse,
    parse_asin_request_keyword_response,
    parse_product_request_response,
    parse_product_variations_response,
)
from amazon_product_intelligence.connectors.errors import ProviderConnectorError
from amazon_product_intelligence.contracts import (
    Channel,
    KeywordMetricObservation,
    MetricObservation,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProductKeywordRelationshipObservation,
    QueryExecutionOutcome,
    RelationshipDirection,
    RelationshipType,
    ScopeType,
    SemanticStatus,
    canonical_json,
)
from amazon_product_intelligence.normalization import (
    CanonicalNormalizationPipeline,
    NormalizationContext,
    NormalizationInput,
)
from amazon_product_intelligence.provider_capabilities import CapabilityStatus


ROOT = Path(__file__).resolve().parents[1]
DTO_FIXTURES = ROOT / "tests" / "fixtures" / "sorftime_dtos" / "v0_1"
LEGACY_FIXTURES = ROOT / "tests" / "fixtures" / "provider_adapters" / "v0_1"
RETRIEVED_AT = "2026-08-26T08:00:00Z"
TRANSFORMED_AT = "2026-08-26T08:01:00Z"
NORMALIZED_AT = "2026-08-26T08:02:00Z"
ASIN = "B09265WXY5"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def product_request() -> SorftimeProductRequest:
    return SorftimeProductRequest(ASIN=ASIN, Trend=2)


def variations_request(*, sales: bool | None = None) -> SorftimeProductVariationsRequest:
    return SorftimeProductVariationsRequest(
        Asin=ASIN,
        PageIndex=1,
        IsSalesVolume=sales,
    )


def keyword_request() -> SorftimeAsinRequestKeywordRequest:
    return SorftimeAsinRequestKeywordRequest(ASIN=ASIN, PageIndex=1, PageSize=20)


def product_response() -> SorftimeProductRequestResponse:
    request = product_request()
    return parse_product_request_response(
        load_json(DTO_FIXTURES / "product_request_success.json"),
        request,
    )


def variations_response(
    request: SorftimeProductVariationsRequest | None = None,
) -> SorftimeProductVariationsResponse:
    return parse_product_variations_response(
        load_json(DTO_FIXTURES / "product_variations_success.json"),
        request or variations_request(),
    )


def keyword_response() -> SorftimeAsinRequestKeywordResponse:
    request = keyword_request()
    return parse_asin_request_keyword_response(
        load_json(DTO_FIXTURES / "asin_request_keyword_success.json"),
        request,
    )


def mapping_context(payload_kind: str, operation: str, request: object) -> AdaptationContext:
    return AdaptationContext(
        provider="sorftime",
        payload_kind=payload_kind,
        source_tool=operation,
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:sp040c:{payload_kind}",
        sanitized_request=sorftime_sanitized_mapping_request(request),  # type: ignore[arg-type]
        currency="USD",
    )


def product_result():
    return SorftimeDtoMapperV0_1().map_product_request(
        product_request(),
        product_response(),
        mapping_context(PRODUCT_REQUEST_PAYLOAD_KIND, "ProductRequest", product_request()),
    )


def variation_result(
    request: SorftimeProductVariationsRequest | None = None,
    response: SorftimeProductVariationsResponse | None = None,
):
    request = request or variations_request()
    response = response or variations_response(request)
    return SorftimeDtoMapperV0_1().map_product_variations(
        request,
        response,
        mapping_context(PRODUCT_VARIATIONS_PAYLOAD_KIND, "ProductVariations", request),
    )


def keyword_result(response: SorftimeAsinRequestKeywordResponse | None = None):
    request = keyword_request()
    return SorftimeDtoMapperV0_1().map_asin_request_keyword(
        request,
        response or keyword_response(),
        mapping_context(ASIN_REQUEST_KEYWORD_PAYLOAD_KIND, "ASINRequestKeyword", request),
    )


def facts(result, dimension: str) -> tuple[ProductFactObservation, ...]:
    return tuple(
        item
        for item in result.bundle.observations
        if isinstance(item, ProductFactObservation) and item.dimension == dimension
    )


def metrics(result, metric: str) -> tuple[MetricObservation | KeywordMetricObservation, ...]:
    return tuple(
        item
        for item in result.bundle.observations
        if isinstance(item, (MetricObservation, KeywordMetricObservation))
        and item.metric == metric
    )


def relationships(
    result,
    relationship_type: RelationshipType,
) -> tuple[ProductKeywordRelationshipObservation, ...]:
    return tuple(
        item
        for item in result.bundle.observations
        if isinstance(item, ProductKeywordRelationshipObservation)
        and item.relationship_type is relationship_type
    )


def test_mapping_specifications_are_operation_specific_and_versioned() -> None:
    assert SorftimeDtoMapperV0_1.dto_contract_version == SORFTIME_DTO_CONTRACT_VERSION
    assert SorftimeDtoMapperV0_1.mapper_version == "0.1.0"
    assert set(SORFTIME_DTO_MAPPING_SPECIFICATIONS) == {
        PRODUCT_REQUEST_PAYLOAD_KIND,
        PRODUCT_VARIATIONS_PAYLOAD_KIND,
        ASIN_REQUEST_KEYWORD_PAYLOAD_KIND,
    }
    assert {item.provider for item in SORFTIME_DTO_MAPPING_SPECIFICATIONS.values()} == {
        "sorftime"
    }
    assert {item.source_tool for item in SORFTIME_DTO_MAPPING_SPECIFICATIONS.values()} == {
        "ProductRequest",
        "ProductVariations",
        "ASINRequestKeyword",
    }


def test_mapper_has_no_raw_adapt_success_path() -> None:
    mapper = SorftimeDtoMapperV0_1()
    assert not hasattr(mapper, "adapt")
    with pytest.raises(AdapterError, match="exact SP-040B"):
        mapper.map_product_request(  # type: ignore[arg-type]
            product_request(),
            load_json(DTO_FIXTURES / "product_request_success.json"),
            mapping_context(PRODUCT_REQUEST_PAYLOAD_KIND, "ProductRequest", product_request()),
        )


def test_product_request_requested_asin_maps_deterministically() -> None:
    first = product_result()
    second = product_result()
    assert first.succeeded
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())
    requested = [item for item in facts(first, "asin") if item.scope.scope_type is ScopeType.ASIN]
    assert len(requested) == 1
    assert requested[0].value.normalized_value == ASIN
    assert requested[0].subject.marketplace == "US"


def test_distinct_parent_projects_only_bounded_parent_identity() -> None:
    result = product_result()
    parent = facts(result, "parent_product_relationship")
    assert len(parent) == 1
    assert parent[0].value.normalized_value == product_response().Data.ParentAsin
    assert parent[0].scope.scope_type is ScopeType.CHILD_ASIN
    assert parent[0].provenance.provider_semantic == "Provider-reported distinct parent ASIN identity"


def test_self_parent_creates_no_parent_edge() -> None:
    response = product_response()
    data = replace(response.Data, ParentAsin=response.Data.Asin)
    result = SorftimeDtoMapperV0_1().map_product_request(
        product_request(),
        replace(response, Data=data),
        mapping_context(PRODUCT_REQUEST_PAYLOAD_KIND, "ProductRequest", product_request()),
    )
    assert not facts(result, "parent_product_relationship")
    assert any(item.code == "SELF_PARENT_NOT_PROJECTED" for item in result.diagnostics)


def test_product_variation_collection_is_bounded_not_complete_family() -> None:
    result = product_result()
    collection = facts(result, "variation_identity_collection")
    identities = [item for item in facts(result, "asin") if item.scope.scope_type is ScopeType.CHILD_ASIN]
    assert len(collection) == 1
    assert collection[0].value.normalized_value["returned_count"] == 10
    assert collection[0].value.normalized_value["complete_family"] is False
    assert len(identities) == 10
    assert any(item.code == "FAMILY_COMPLETENESS_UNPROVEN" for item in result.diagnostics)


def test_product_attributes_attach_only_to_referenced_child() -> None:
    result = product_result()
    attribute_facts = facts(result, "color") + facts(result, "size")
    assert len(attribute_facts) == 4
    expected = {
        (attribute.Asin, attribute.Name.casefold(), attribute.Value)
        for attribute in product_response().Data.attributes
    }
    actual = {
        (
            item.subject.subject_id.rsplit(":", 1)[-1],
            item.dimension,
            item.value.normalized_value,
        )
        for item in attribute_facts
    }
    assert actual == expected
    assert all(item.scope.scope_type is ScopeType.CHILD_ASIN for item in attribute_facts)


def test_product_trend_nulls_emit_no_trend_or_zero() -> None:
    result = product_result()
    assert not [
        item
        for item in result.bundle.observations
        if "trend" in getattr(item, "dimension", "").casefold()
        or "trend" in getattr(item, "metric", "").casefold()
    ]
    assert any(item.code == "TREND_FIELDS_UNAVAILABLE" for item in result.diagnostics)


def test_product_request_input_permutation_is_deterministic() -> None:
    response = product_response()
    data = replace(
        response.Data,
        VariationASIN=tuple(reversed(response.Data.VariationASIN or ())),
        Attribute=tuple(reversed(response.Data.Attribute or ())),
    )
    mapper = SorftimeDtoMapperV0_1()
    context = mapping_context(PRODUCT_REQUEST_PAYLOAD_KIND, "ProductRequest", product_request())
    first = mapper.map_product_request(product_request(), response, context)
    second = mapper.map_product_request(product_request(), replace(response, Data=data), context)
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())


def test_product_request_mismatch_cannot_enter_mapper_success() -> None:
    other_request = SorftimeProductRequest(ASIN="B012345678", Trend=2)
    with pytest.raises(AdapterError, match="mismatch"):
        SorftimeDtoMapperV0_1().map_product_request(
            other_request,
            product_response(),
            mapping_context(
                PRODUCT_REQUEST_PAYLOAD_KIND,
                "ProductRequest",
                other_request,
            ),
        )


def test_variation_rows_map_identity_and_color_size_deterministically() -> None:
    result = variation_result()
    assert result.succeeded
    assert len(facts(result, "asin")) == 10
    assert len(facts(result, "color")) == 10
    assert len(facts(result, "size")) == 10
    assert all(item.scope.scope_type is ScopeType.CHILD_ASIN for item in facts(result, "color"))


def test_product_variations_never_creates_parent_edge_or_completeness() -> None:
    result = variation_result()
    assert not facts(result, "parent_product_relationship")
    assert result.raw_evidence.pagination["family_completeness"] == "UNKNOWN"
    assert any(item.code == "PRODUCT_VARIATIONS_TOPOLOGY_UNPROVEN" for item in result.diagnostics)


def test_sales_minus_one_is_unknown_and_never_numeric() -> None:
    result = variation_result()
    sales = metrics(result, "estimated_variation_sales")
    assert len(sales) == 10
    assert all(item.value.presence_status is PresenceStatus.UNKNOWN for item in sales)
    assert all(item.value.raw_value is None and item.value.normalized_value is None for item in sales)
    serialized = canonical_json([item.value for item in sales])
    assert '"raw_value":-1' not in serialized
    assert '"normalized_value":0' not in serialized


def test_positive_sales_remains_unavailable_without_period_or_method_upgrade() -> None:
    request = variations_request(sales=True)
    response = variations_response()
    row = replace(response.Data[0], SalesAmount=7)
    positive = replace(response, Data=(row,))
    result = variation_result(request, positive)
    sales = metrics(result, "estimated_variation_sales")
    assert len(sales) == 1
    assert sales[0].value.presence_status is PresenceStatus.UNKNOWN
    assert sales[0].value.semantic_status is SemanticStatus.SEMANTICS_UNCONFIRMED
    assert sales[0].time.period_type is PeriodType.UNKNOWN
    assert any(item.code == "POSITIVE_SALES_PERIOD_METHOD_UNPROVEN" for item in result.diagnostics)


def test_empty_variation_page_is_not_empty_family() -> None:
    response = replace(variations_response(), Data=())
    result = variation_result(response=response)
    assert result.raw_evidence.response_status == "EMPTY"
    assert not result.bundle.observations
    assert result.raw_evidence.pagination["family_completeness"] == "UNKNOWN"
    assert any(item.code == "VARIATION_PAGE_RETURNED_EMPTY" for item in result.diagnostics)


def test_variation_input_permutation_is_deterministic() -> None:
    response = variations_response()
    first = variation_result(response=response)
    second = variation_result(response=replace(response, Data=tuple(reversed(response.Data))))
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())


def test_keyword_page_emits_bounded_relationships_and_metrics() -> None:
    result = keyword_result()
    assert len(relationships(result, RelationshipType.CANDIDATE_MEMBERSHIP)) == 20
    assert len(relationships(result, RelationshipType.RANK)) == 20
    assert len(relationships(result, RelationshipType.TRAFFIC)) == 20
    assert len(metrics(result, "search_volume")) == 20
    assert len(metrics(result, "cpc")) == 20
    query = result.bundle.query_execution_records[0]
    assert query.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
    assert query.outcome is QueryExecutionOutcome.RESULTS_RETURNED
    assert result.raw_evidence.pagination["complete_keyword_universe"] is False
    assert result.raw_evidence.pagination["provider_total"] is None


def test_organic_position_retains_first_three_pages_and_unknown_timezone() -> None:
    ranks = relationships(keyword_result(), RelationshipType.RANK)
    assert all(item.channel is Channel.ORGANIC for item in ranks)
    assert all(item.rank["page"] in {1, 2, 3} for item in ranks)
    assert all(item.rank["page_scope"] == "FIRST_THREE_SEARCH_RESULT_PAGES" for item in ranks)
    assert all(item.rank["timezone"] is None for item in ranks)
    assert all(item.time.observed_at is None for item in ranks)
    assert all(item.time.observed_at_status is ObservedAtStatus.UNKNOWN for item in ranks)
    assert all(item.time.timezone is None for item in ranks)


def test_traffic_share_preserves_percent_and_bounded_period() -> None:
    traffic = relationships(keyword_result(), RelationshipType.TRAFFIC)
    assert traffic[0].value.unit.unit_code == "percent"
    assert traffic[0].value.normalized_value == 20.0
    assert all(item.time.period_type is PeriodType.ROLLING_30_DAYS for item in traffic)


def test_search_volume_remains_provider_estimate_with_unknown_method() -> None:
    result = keyword_result()
    volumes = metrics(result, "search_volume")
    assert volumes[0].estimate_method_status.value == "UNKNOWN"
    assert volumes[0].time.period_type is PeriodType.ROLLING_30_DAYS
    assert volumes[0].value.semantic_status is SemanticStatus.SEMANTICS_UNCONFIRMED
    assert any(item.issue_code == "SEARCH_VOLUME_ESTIMATE_METHOD_UNKNOWN" for item in result.bundle.quality_issues)


def test_cpc_preserves_source_minor_units_and_auditable_usd_conversion() -> None:
    cpc = metrics(keyword_result(), "cpc")[0]
    assert cpc.value.raw_value == 51
    assert cpc.value.normalized_value == 0.51
    assert cpc.value.unit.dimension == "CURRENCY"
    assert cpc.value.unit.unit_code == "USD"
    assert cpc.range["minor_unit_exponent"] == 2
    assert cpc.range["source_unit_semantics"] == "LOCAL_MINOR_UNIT"
    assert cpc.range["minimum_source_minor_units"] == 41
    assert cpc.range["minimum_major_units"] == 0.41


def test_sponsored_data_and_timezone_remain_unavailable() -> None:
    result = keyword_result()
    relationship_rows = tuple(
        item
        for item in result.bundle.observations
        if isinstance(item, ProductKeywordRelationshipObservation)
    )
    assert not [item for item in relationship_rows if item.channel is Channel.SPONSORED]
    codes = {item.code for item in result.diagnostics}
    assert "SPONSORED_PLACEMENT_UNAVAILABLE" in codes
    assert "OBSERVATION_TIMEZONE_UNKNOWN" in codes


def test_empty_keyword_page_is_query_outcome_not_zero_demand() -> None:
    result = keyword_result(replace(keyword_response(), Data=()))
    assert not result.bundle.observations
    assert result.raw_evidence.response_status == "EMPTY"
    query = result.bundle.query_execution_records[0]
    assert query.outcome is QueryExecutionOutcome.EXPLICIT_EMPTY
    assert query.related_relationship_observation_ids == ()
    assert not metrics(result, "search_volume")
    assert result.raw_evidence.pagination["complete_keyword_universe"] is False


def test_keyword_input_permutation_is_deterministic() -> None:
    response = keyword_response()
    first = keyword_result(response)
    second = keyword_result(replace(response, Data=tuple(reversed(response.Data))))
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())


def test_canonical_keyword_collision_fails_closed() -> None:
    response = keyword_response()
    first = response.Data[0]
    collision_summary = replace(first.Keyword, Keyword="fixture  keyword 01")
    collision = replace(first, Keyword=collision_summary)
    typed = replace(response, Data=(first, collision))
    with pytest.raises(AdapterError, match="collide"):
        keyword_result(typed)


def test_context_must_match_typed_request_marketplace_and_operation() -> None:
    request = product_request()
    context = mapping_context(PRODUCT_REQUEST_PAYLOAD_KIND, "ProductRequest", request)
    with pytest.raises(AdapterContextError, match="sanitized_request"):
        SorftimeDtoMapperV0_1().map_product_request(
            request,
            product_response(),
            replace(context, sanitized_request={"operation": "ProductRequest", "domain": 1}),
        )
    with pytest.raises(AdapterContextError, match="source_tool"):
        SorftimeDtoMapperV0_1().map_product_request(
            request,
            product_response(),
            replace(context, source_tool="ProductVariations"),
        )
    with pytest.raises(AdapterContextError, match="US / USD"):
        SorftimeDtoMapperV0_1().map_product_request(
            request,
            product_response(),
            replace(context, currency="EUR"),
        )


def test_secret_like_request_material_is_rejected_and_not_persisted() -> None:
    request = product_request()
    context = mapping_context(PRODUCT_REQUEST_PAYLOAD_KIND, "ProductRequest", request)
    unsafe = dict(sorftime_sanitized_mapping_request(request))
    unsafe["Authorization"] = "fixture-forbidden"
    with pytest.raises(AdapterContextError, match="sanitized_request"):
        SorftimeDtoMapperV0_1().map_product_request(
            request,
            product_response(),
            replace(context, sanitized_request=unsafe),
        )
    serialized = canonical_json(product_result().to_dict()).casefold()
    assert "authorization" not in serialized
    assert "account-sk" not in serialized
    assert "api_key" not in serialized


def test_dto_business_failure_cannot_reach_mapper() -> None:
    payload = load_json(DTO_FIXTURES / "product_request_success.json")
    payload["Code"] = 10
    payload["Data"] = None
    with pytest.raises(ProviderConnectorError):
        parse_product_request_response(payload, product_request())


def test_raw_snapshot_is_sanitized_typed_projection_not_full_envelope() -> None:
    result = keyword_result()
    assert result.raw_snapshot["dto_contract_version"] == SORFTIME_DTO_CONTRACT_VERSION
    assert "RequestLeft" not in result.raw_snapshot
    assert "RequestConsumed" not in result.raw_snapshot
    assert "Message" not in result.raw_snapshot
    assert result.raw_evidence.provider_schema_version.value == SORFTIME_DTO_CONTRACT_VERSION
    assert result.bundle.transformation_runs[0].transformation_code_version.value == SORFTIME_DTO_MAPPER_RULESET_VERSION


def test_sorftime_and_xiyou_share_identity_contract_but_not_provenance() -> None:
    payload = load_json(LEGACY_FIXTURES / "xiyou_asin_info.json")
    payload["data"]["entities"][0]["asin"] = ASIN  # type: ignore[index]
    xiyou_context = AdaptationContext(
        provider="xiyou",
        payload_kind="asin_info",
        source_tool="get_asin_info",
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id="collection:sp040c:xiyou-identity",
        sanitized_request={"asin": ASIN},
        currency="USD",
    )
    xiyou = XiYouAdapterV0_1().adapt(payload, xiyou_context)
    sorftime_identity = facts(product_result(), "asin")[0]
    xiyou_identity = next(
        item
        for item in xiyou.bundle.observations
        if item.subject.subject_id == sorftime_identity.subject.subject_id
    )
    assert xiyou_identity.subject == sorftime_identity.subject
    assert xiyou_identity.provenance.provider == "xiyou"
    assert sorftime_identity.provenance.provider == "sorftime"
    assert xiyou_identity.observation_id != sorftime_identity.observation_id


def test_relationship_parity_does_not_claim_provider_or_period_equivalence() -> None:
    payload = load_json(LEGACY_FIXTURES / "xiyou_asin_keywords_reverse.json")
    payload["data"]["list"][0]["searchTerm"] = "fixture keyword 01"  # type: ignore[index]
    xiyou_context = AdaptationContext(
        provider="xiyou",
        payload_kind="asin_keywords",
        source_tool="get_asin_keywords",
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id="collection:sp040c:xiyou-relationship",
        sanitized_request={"asin": ASIN},
        currency="USD",
    )
    xiyou = XiYouAdapterV0_1().adapt(payload, xiyou_context)
    xiyou_membership = next(
        item
        for item in xiyou.bundle.observations
        if isinstance(item, ProductKeywordRelationshipObservation)
        and item.relationship_type is RelationshipType.CANDIDATE_MEMBERSHIP
    )
    sorftime_membership = relationships(
        keyword_result(),
        RelationshipType.CANDIDATE_MEMBERSHIP,
    )[0]
    assert xiyou_membership.product == sorftime_membership.product
    assert xiyou_membership.keyword == sorftime_membership.keyword
    assert xiyou_membership.direction is sorftime_membership.direction
    assert xiyou_membership.relationship_type is sorftime_membership.relationship_type
    assert xiyou_membership.provenance.provider != sorftime_membership.provenance.provider
    assert xiyou_membership.observation_id != sorftime_membership.observation_id
    assert xiyou_membership.time.period_type is not sorftime_membership.time.period_type


def test_existing_normalization_boundary_consumes_sorftime_bundle_without_branch() -> None:
    product = product_result()
    keywords = keyword_result()
    variations = variation_result()
    selected = (
        facts(product, "asin")[0],
        facts(product, "parent_product_relationship")[0],
        relationships(keywords, RelationshipType.CANDIDATE_MEMBERSHIP)[0],
        metrics(keywords, "search_volume")[0],
        metrics(keywords, "cpc")[0],
        metrics(variations, "estimated_variation_sales")[0],
    )
    canonical_fields = (
        "product.asin",
        "product.parent_asin",
        "relationship.product_to_keyword",
        "keyword.search_volume",
        "keyword.cpc",
        "metric.estimated_variation_sales",
    )
    inputs = tuple(
        NormalizationInput.from_observation(
            observation,
            canonical_field=field,
            capability_status=CapabilityStatus.PARTIAL,
        )
        for observation, field in zip(selected, canonical_fields, strict=True)
    )
    results = CanonicalNormalizationPipeline.with_defaults().normalize_many(
        inputs,
        NormalizationContext(
            normalization_run_id="normalization:sp040c:compatibility",
            normalized_at=NORMALIZED_AT,
        ),
    )
    assert len(results) == len(inputs)
    assert all(item.provenance.provider == "sorftime" for item in results)
    assert results[4].normalized_value.__str__() == "0.51"
    assert results[5].presence_status is PresenceStatus.UNKNOWN
    assert results[5].normalized_value is None


def test_network_construction_is_denied_during_all_mapping_paths() -> None:
    def denied(*_args, **_kwargs):
        raise AssertionError("network construction is forbidden in SP-040C")

    with patch.object(socket, "socket", side_effect=denied), patch.object(
        urllib.request,
        "urlopen",
        side_effect=denied,
    ):
        assert product_result().succeeded
        assert variation_result().succeeded
        assert keyword_result().succeeded
