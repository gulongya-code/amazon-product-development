"""DTO-first Sorftime to existing Canonical mapping boundary for SP-040C.

The public mapper accepts only validated SP-040B DTO instances.  It has no raw
dictionary adaptation path, transport, credential handling, provider selection,
or downstream business behavior.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from amazon_product_intelligence.connectors.sorftime_dtos_v0_1 import (
    SORFTIME_AMAZON_US,
    SorftimeAsinKeywordRow,
    SorftimeAsinRequestKeywordRequest,
    SorftimeAsinRequestKeywordResponse,
    SorftimeDomainContext,
    SorftimeProductRequest,
    SorftimeProductRequestResponse,
    SorftimeProductVariationRow,
    SorftimeProductVariationsRequest,
    SorftimeProductVariationsResponse,
    SorftimeSalesState,
)
from amazon_product_intelligence.contracts import (
    BlockingScope,
    Channel,
    CodeVersionScheme,
    ContractValidationError,
    EstimateMethodStatus,
    EvidenceType,
    FactGroup,
    NormalizationStatus,
    OriginStage,
    PeriodType,
    PresenceStatus,
    ProductKeywordRelationshipObservation,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    QueryExecutionOutcome,
    RelationshipDirection,
    RelationshipType,
    ResultStatus,
    ScopeType,
    SemanticStatus,
    TransformationCodeVersion,
    Unit,
    ValueType,
    VersionStatus,
    canonical_json,
)

from .base import (
    AdaptationContext,
    AdaptationResult,
    AdapterContextError,
    AdapterError,
    MappingDisposition,
    MappingSpecification,
    _AdapterSession,
    absent_value,
    keyword_identity,
    product_identity,
    value_envelope,
)


SORFTIME_DTO_CONTRACT_VERSION = "sorftime-dto-v0.1"
SORFTIME_DTO_MAPPER_VERSION = "0.1.0"
SORFTIME_DTO_MAPPER_RULESET_VERSION = "sorftime-dto-mapper-v0.1"

PRODUCT_REQUEST_PAYLOAD_KIND = "sorftime_product_request_dto"
PRODUCT_VARIATIONS_PAYLOAD_KIND = "sorftime_product_variations_dto"
ASIN_REQUEST_KEYWORD_PAYLOAD_KIND = "sorftime_asin_request_keyword_dto"


def _spec(
    *,
    operation: str,
    payload_kind: str,
    mapping_version: str,
) -> MappingSpecification:
    return MappingSpecification(
        specification_id=f"sorftime.dto.{operation}.v0.1",
        version="0.1",
        mapping_version=mapping_version,
        provider="sorftime",
        payload_kind=payload_kind,
        source_tool=operation,
    )


SORFTIME_DTO_MAPPING_SPECIFICATIONS: Mapping[str, MappingSpecification] = MappingProxyType(
    {
        PRODUCT_REQUEST_PAYLOAD_KIND: _spec(
            operation="ProductRequest",
            payload_kind=PRODUCT_REQUEST_PAYLOAD_KIND,
            mapping_version="sorftime_product_request_dto_mapping_v0_1",
        ),
        PRODUCT_VARIATIONS_PAYLOAD_KIND: _spec(
            operation="ProductVariations",
            payload_kind=PRODUCT_VARIATIONS_PAYLOAD_KIND,
            mapping_version="sorftime_product_variations_dto_mapping_v0_1",
        ),
        ASIN_REQUEST_KEYWORD_PAYLOAD_KIND: _spec(
            operation="ASINRequestKeyword",
            payload_kind=ASIN_REQUEST_KEYWORD_PAYLOAD_KIND,
            mapping_version="sorftime_asin_request_keyword_dto_mapping_v0_1",
        ),
    }
)


SorftimeMapperRequest: TypeAlias = (
    SorftimeProductRequest
    | SorftimeProductVariationsRequest
    | SorftimeAsinRequestKeywordRequest
)


def _operation_for_request(request: SorftimeMapperRequest) -> str:
    if type(request) is SorftimeProductRequest:
        return "ProductRequest"
    if type(request) is SorftimeProductVariationsRequest:
        return "ProductVariations"
    if type(request) is SorftimeAsinRequestKeywordRequest:
        return "ASINRequestKeyword"
    raise AdapterError("Sorftime mapper request must be an exact SP-040B request DTO")


def sorftime_sanitized_mapping_request(
    request: SorftimeMapperRequest,
    domain: SorftimeDomainContext = SORFTIME_AMAZON_US,
) -> dict[str, Any]:
    """Build the only request material allowed in SP-040C provenance."""

    operation = _operation_for_request(request)
    return {
        "operation": operation,
        "domain": domain.domain,
        "marketplace": domain.marketplace,
        "request_id": request.request_id(domain),
        "body": request.to_provider_body(),
    }


def _known_local_dto_schema() -> ProviderSchemaVersion:
    return ProviderSchemaVersion(
        status=VersionStatus.KNOWN,
        value=SORFTIME_DTO_CONTRACT_VERSION,
        source=ProviderSchemaSource.LOCAL_CONTRACT,
    )


def _mapper_code_version() -> TransformationCodeVersion:
    return TransformationCodeVersion(
        status=VersionStatus.KNOWN,
        value=SORFTIME_DTO_MAPPER_RULESET_VERSION,
        scheme=CodeVersionScheme.RULESET_VERSION,
    )


def _validate_mapping_context(
    *,
    context: AdaptationContext,
    specification: MappingSpecification,
    request: SorftimeMapperRequest,
    domain: SorftimeDomainContext,
) -> AdaptationContext:
    if context.provider != "sorftime":
        raise AdapterContextError("Sorftime DTO mapper requires provider='sorftime'")
    if context.payload_kind != specification.payload_kind:
        raise AdapterContextError(
            f"Sorftime DTO mapper requires payload_kind={specification.payload_kind!r}"
        )
    if context.source_tool != specification.source_tool:
        raise AdapterContextError(
            f"Sorftime DTO mapper requires source_tool={specification.source_tool!r}"
        )
    if context.marketplace != domain.marketplace or context.currency != domain.currency:
        raise AdapterContextError(
            "Sorftime DTO mapper supports only domain=1 / US / USD mapping context"
        )
    expected_request = sorftime_sanitized_mapping_request(request, domain)
    if canonical_json(context.sanitized_request) != canonical_json(expected_request):
        raise AdapterContextError(
            "sanitized_request must exactly equal the typed DTO request identity and domain context"
        )
    return replace(
        context,
        sanitized_request=expected_request,
        provider_schema_version=_known_local_dto_schema(),
        transformation_code_version=_mapper_code_version(),
    )


def _string_value(value: str) -> Any:
    return value_envelope(
        presence_status=PresenceStatus.PRESENT,
        raw_value=value,
        normalized_value=value,
        value_type=ValueType.STRING,
        normalization_status=NormalizationStatus.NOT_APPLICABLE,
        semantic_status=SemanticStatus.CONFIRMED,
    )


def _product_request_projection(response: SorftimeProductRequestResponse) -> dict[str, Any]:
    data = response.Data
    attributes = None
    if data.Attribute is not None:
        attributes = [list(row) for row in sorted(data.Attribute, key=lambda row: tuple(row))]
    return {
        "dto_contract_version": SORFTIME_DTO_CONTRACT_VERSION,
        "operation": "ProductRequest",
        "Code": response.Code,
        "Data": {
            "Asin": data.Asin,
            "ParentAsin": data.ParentAsin,
            "VariationASIN": (
                None if data.VariationASIN is None else sorted(data.VariationASIN)
            ),
            "VariationASINCount": data.VariationASINCount,
            "Attribute": attributes,
            "ListingSalesVolumeOfDaily": data.ListingSalesVolumeOfDaily,
            "ListingSalesOfDaily": data.ListingSalesOfDaily,
            "ListingSalesVolumeOfMonthTrend": data.ListingSalesVolumeOfMonthTrend,
            "ListingSalesOfMonthTrend": data.ListingSalesOfMonthTrend,
            "RankTrend": data.RankTrend,
            "BsrRankTrend": data.BsrRankTrend,
            "DealTrend": data.DealTrend,
            "PriceTrend": data.PriceTrend,
            "ListPriceTrend": data.ListPriceTrend,
        },
    }


def _variation_sort_key(row: SorftimeProductVariationRow) -> tuple[int, str]:
    return row.ItemIndex, row.Asin


def _product_variations_projection(
    response: SorftimeProductVariationsResponse,
) -> dict[str, Any]:
    return {
        "dto_contract_version": SORFTIME_DTO_CONTRACT_VERSION,
        "operation": "ProductVariations",
        "Code": response.Code,
        "Data": [row.to_dict() for row in sorted(response.Data, key=_variation_sort_key)],
    }


def _keyword_sort_key(row: SorftimeAsinKeywordRow) -> tuple[str, str]:
    return " ".join(row.Keyword.Keyword.split()).casefold(), row.Keyword.Keyword


def _asin_keyword_projection(
    response: SorftimeAsinRequestKeywordResponse,
) -> dict[str, Any]:
    return {
        "dto_contract_version": SORFTIME_DTO_CONTRACT_VERSION,
        "operation": "ASINRequestKeyword",
        "Code": response.Code,
        "Data": [row.to_dict() for row in sorted(response.Data, key=_keyword_sort_key)],
    }


def _session(
    *,
    context: AdaptationContext,
    specification: MappingSpecification,
    projection: Mapping[str, Any],
    raw_response_status: str = "SUCCESS",
) -> _AdapterSession:
    return _AdapterSession(
        provider="sorftime",
        adapter_version=SORFTIME_DTO_MAPPER_VERSION,
        mapping_specification=specification,
        context=context,
        payload=projection,
        raw_response_status=raw_response_status,
    )


def _add_product_identity(
    session: _AdapterSession,
    *,
    asin: str,
    source_field: str,
    source_record_identity: str,
    provider_semantic: str,
    scope_type: ScopeType,
    discriminator: str,
    parent_asin: str | None = None,
) -> Any:
    product = product_identity(
        session.context.marketplace,
        asin,
        parent_asin=parent_asin,
    )
    session.add_product_fact(
        product=product,
        dimension="asin",
        fact_group=FactGroup.IDENTITY_RELATED,
        value=_string_value(asin),
        source_field=source_field,
        source_record_identity=source_record_identity,
        provider_semantic=provider_semantic,
        scope_type=scope_type,
        discriminator=discriminator,
    )
    return product


def _unknown_sales_value(*, confirmed_sentinel: bool) -> Any:
    return absent_value(
        PresenceStatus.UNKNOWN,
        ValueType.NUMBER,
        semantic_status=(
            SemanticStatus.CONFIRMED
            if confirmed_sentinel
            else SemanticStatus.SEMANTICS_UNCONFIRMED
        ),
        unit=Unit(dimension="COUNT", unit_code="units", unit_system="PROVIDER"),
    )


def _major_units(source_value: int, exponent: int) -> float:
    return float(Decimal(source_value).scaleb(-exponent))


class SorftimeDtoMapperV0_1:
    """Explicit typed mapper for the three accepted SP-040B response DTOs."""

    provider = "sorftime"
    mapper_version = SORFTIME_DTO_MAPPER_VERSION
    dto_contract_version = SORFTIME_DTO_CONTRACT_VERSION
    mapping_specifications = SORFTIME_DTO_MAPPING_SPECIFICATIONS
    supported_payload_kinds = tuple(SORFTIME_DTO_MAPPING_SPECIFICATIONS)

    def map_product_request(
        self,
        request: SorftimeProductRequest,
        response: SorftimeProductRequestResponse,
        context: AdaptationContext,
        domain: SorftimeDomainContext = SORFTIME_AMAZON_US,
    ) -> AdaptationResult:
        if type(request) is not SorftimeProductRequest or type(response) is not SorftimeProductRequestResponse:
            raise AdapterError("ProductRequest mapping requires exact SP-040B request/response DTOs")
        try:
            response.validate_against(request)
        except ContractValidationError as exc:
            raise AdapterError("ProductRequest DTO request/response mismatch") from exc
        specification = self.mapping_specifications[PRODUCT_REQUEST_PAYLOAD_KIND]
        checked_context = _validate_mapping_context(
            context=context,
            specification=specification,
            request=request,
            domain=domain,
        )
        session = _session(
            context=checked_context,
            specification=specification,
            projection=_product_request_projection(response),
        )
        data = response.Data
        parent_asin = data.ParentAsin if data.has_distinct_parent else None
        requested_product = _add_product_identity(
            session,
            asin=data.Asin,
            parent_asin=parent_asin,
            source_field="Data.Asin",
            source_record_identity=f"US:{data.Asin}:ProductRequest",
            provider_semantic="ProductRequest returned product ASIN identity",
            scope_type=ScopeType.ASIN,
            discriminator="requested-product-identity",
        )
        if parent_asin is not None:
            session.add_product_fact(
                product=requested_product,
                dimension="parent_product_relationship",
                fact_group=FactGroup.VARIATION,
                value=_string_value(parent_asin),
                source_field="Data.ParentAsin",
                source_record_identity=f"US:{data.Asin}:ProductRequest",
                provider_semantic="Provider-reported distinct parent ASIN identity",
                scope_type=ScopeType.CHILD_ASIN,
                discriminator="bounded-parent-identity",
            )
        elif data.ParentAsin == data.Asin:
            session.diagnostic(
                code="SELF_PARENT_NOT_PROJECTED",
                message="Self-valued ParentAsin is not emitted as a relationship edge.",
                source_locator="Data.ParentAsin",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
                affects_status=False,
            )

        variations = None if data.VariationASIN is None else tuple(sorted(data.VariationASIN))
        if variations is None:
            session.add_product_fact(
                product=requested_product,
                dimension="variation_identity_collection",
                fact_group=FactGroup.VARIATION,
                value=absent_value(PresenceStatus.EXPLICIT_NULL, ValueType.OBJECT),
                source_field="Data.VariationASIN",
                source_record_identity=f"US:{data.Asin}:ProductRequest",
                provider_semantic="Provider returned explicit null variation collection",
                result_status=ResultStatus.PARTIAL,
            )
        else:
            session.add_product_fact(
                product=requested_product,
                dimension="variation_identity_collection",
                fact_group=FactGroup.VARIATION,
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=list(variations),
                    normalized_value={
                        "asins": list(variations),
                        "returned_count": data.VariationASINCount,
                        "complete_family": False,
                        "completeness_status": "BOUNDED_RESPONSE_ONLY",
                    },
                    value_type=ValueType.OBJECT,
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field="Data.VariationASIN",
                source_record_identity=f"US:{data.Asin}:ProductRequest",
                provider_semantic=(
                    "Bounded ProductRequest variation identity collection; not complete family topology"
                ),
                discriminator="bounded-variation-collection",
            )
            for variation_asin in variations:
                _add_product_identity(
                    session,
                    asin=variation_asin,
                    source_field=f"Data.VariationASIN[Asin={variation_asin}]",
                    source_record_identity=f"US:{variation_asin}:ProductRequest:variation",
                    provider_semantic="Bounded ProductRequest variation ASIN identity",
                    scope_type=ScopeType.CHILD_ASIN,
                    discriminator="bounded-variation-identity",
                )

        for attribute in sorted(
            data.attributes,
            key=lambda item: (item.Asin, item.Name, item.Value),
        ):
            child = product_identity(session.context.marketplace, attribute.Asin)
            session.add_product_fact(
                product=child,
                dimension=attribute.Name.casefold(),
                fact_group=FactGroup.ATTRIBUTE,
                value=_string_value(attribute.Value),
                source_field=f"Data.Attribute[Asin={attribute.Asin}].{attribute.Name}",
                source_record_identity=f"US:{attribute.Asin}:ProductRequest:attribute",
                provider_semantic=f"ProductRequest child-scoped variation {attribute.Name}",
                scope_type=ScopeType.CHILD_ASIN,
                discriminator=f"attribute:{attribute.Name.casefold()}",
            )

        session.diagnostic(
            code="FAMILY_COMPLETENESS_UNPROVEN",
            message=(
                "Variation identities and response cardinality are bounded evidence, not complete family topology."
            ),
            source_locator="Data.VariationASIN",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
        session.diagnostic(
            code="TREND_FIELDS_UNAVAILABLE",
            message="Accepted Trend=2 null fields emit no trend observations, zeros, or empty series.",
            source_locator="Data.*Trend",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        return session.finish()

    def map_product_variations(
        self,
        request: SorftimeProductVariationsRequest,
        response: SorftimeProductVariationsResponse,
        context: AdaptationContext,
        domain: SorftimeDomainContext = SORFTIME_AMAZON_US,
    ) -> AdaptationResult:
        if type(request) is not SorftimeProductVariationsRequest or type(response) is not SorftimeProductVariationsResponse:
            raise AdapterError("ProductVariations mapping requires exact SP-040B request/response DTOs")
        try:
            response.validate_against(request)
        except ContractValidationError as exc:
            raise AdapterError("ProductVariations DTO request/response mismatch") from exc
        specification = self.mapping_specifications[PRODUCT_VARIATIONS_PAYLOAD_KIND]
        checked_context = _validate_mapping_context(
            context=context,
            specification=specification,
            request=request,
            domain=domain,
        )
        rows = tuple(sorted(response.Data, key=_variation_sort_key))
        session = _session(
            context=checked_context,
            specification=specification,
            projection=_product_variations_projection(response),
            raw_response_status="EMPTY" if not rows else "PARTIAL",
        )
        session.raw_evidence = replace(
            session.raw_evidence,
            pagination={
                "request_page": request.PageIndex,
                "returned_count": len(rows),
                "provider_item_total": rows[0].ItemTotal if rows else None,
                "family_completeness": "UNKNOWN",
                "collection_status": "EXPLICIT_EMPTY" if not rows else "BOUNDED_PAGE",
            },
        )
        if not rows:
            session.diagnostic(
                code="VARIATION_PAGE_RETURNED_EMPTY",
                message="A valid empty page is bounded empty evidence, not proof of an empty family.",
                source_locator="Data",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
                affects_status=False,
            )
        for row in rows:
            locator = f"Data[ItemIndex={row.ItemIndex};Asin={row.Asin}]"
            child = _add_product_identity(
                session,
                asin=row.Asin,
                source_field=f"{locator}.Asin",
                source_record_identity=f"US:{row.Asin}:ProductVariations:{row.ItemIndex}",
                provider_semantic="Bounded ProductVariations child ASIN identity",
                scope_type=ScopeType.CHILD_ASIN,
                discriminator="variation-row-identity",
            )
            for name, value in sorted(row.properties):
                session.add_product_fact(
                    product=child,
                    dimension=name.casefold(),
                    fact_group=FactGroup.ATTRIBUTE,
                    value=_string_value(value),
                    source_field=f"{locator}.Property.{name}",
                    source_record_identity=f"US:{row.Asin}:ProductVariations:{row.ItemIndex}",
                    provider_semantic=f"ProductVariations child-scoped {name} property",
                    scope_type=ScopeType.CHILD_ASIN,
                    discriminator=f"property:{name.casefold()}",
                )
            confirmed_sentinel = row.sales_state is SorftimeSalesState.UNKNOWN
            session.add_metric(
                product=child,
                metric="estimated_variation_sales",
                value=_unknown_sales_value(confirmed_sentinel=confirmed_sentinel),
                source_field=f"{locator}.SalesAmount",
                source_record_identity=f"US:{row.Asin}:ProductVariations:{row.ItemIndex}",
                metric_semantic=(
                    "Provider -1 sentinel means sales unavailable, never numeric sales"
                    if confirmed_sentinel
                    else "Positive provider sales remains unavailable because period and method are unproven"
                ),
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                period_type=PeriodType.UNKNOWN,
                scope_type=ScopeType.CHILD_ASIN,
                result_status=ResultStatus.PARTIAL,
                discriminator="sales-unavailable",
            )
            session.diagnostic(
                code=(
                    "SALES_SENTINEL_UNKNOWN"
                    if confirmed_sentinel
                    else "POSITIVE_SALES_PERIOD_METHOD_UNPROVEN"
                ),
                message=(
                    "SalesAmount=-1 is emitted only as UNKNOWN and never -1 or zero."
                    if confirmed_sentinel
                    else "Positive SalesAmount is not emitted as a numeric Canonical sales value in SP-040C."
                ),
                source_locator=f"{locator}.SalesAmount",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        session.diagnostic(
            code="PRODUCT_VARIATIONS_TOPOLOGY_UNPROVEN",
            message=(
                "ProductVariations emits child facts only; it creates no parent edge or complete-family claim."
            ),
            source_locator="Data",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
        return session.finish()

    def map_asin_request_keyword(
        self,
        request: SorftimeAsinRequestKeywordRequest,
        response: SorftimeAsinRequestKeywordResponse,
        context: AdaptationContext,
        domain: SorftimeDomainContext = SORFTIME_AMAZON_US,
    ) -> AdaptationResult:
        if type(request) is not SorftimeAsinRequestKeywordRequest or type(response) is not SorftimeAsinRequestKeywordResponse:
            raise AdapterError("ASINRequestKeyword mapping requires exact SP-040B request/response DTOs")
        try:
            response.validate_against(request)
        except ContractValidationError as exc:
            raise AdapterError("ASINRequestKeyword DTO request/response mismatch") from exc
        specification = self.mapping_specifications[ASIN_REQUEST_KEYWORD_PAYLOAD_KIND]
        checked_context = _validate_mapping_context(
            context=context,
            specification=specification,
            request=request,
            domain=domain,
        )
        rows = tuple(sorted(response.Data, key=_keyword_sort_key))
        normalized_keywords = tuple(
            " ".join(row.Keyword.Keyword.split()).casefold() for row in rows
        )
        if len(set(normalized_keywords)) != len(normalized_keywords):
            raise AdapterError("ASINRequestKeyword DTO rows collide after Canonical keyword normalization")
        session = _session(
            context=checked_context,
            specification=specification,
            projection=_asin_keyword_projection(response),
            raw_response_status="EMPTY" if not rows else "PARTIAL",
        )
        session.raw_evidence = replace(
            session.raw_evidence,
            pagination={
                "request_page": request.PageIndex,
                "request_page_size": request.PageSize,
                "returned_count": len(rows),
                "provider_total": None,
                "later_pages": "UNAVAILABLE",
                "complete_keyword_universe": False,
                "relationship_window_days": response.relationship_window_days,
                "search_result_page_bound": response.search_result_page_bound,
                "collection_status": "EXPLICIT_EMPTY" if not rows else "BOUNDED_PAGE_TOTAL_UNKNOWN",
            },
        )
        product = product_identity(session.context.marketplace, request.ASIN)
        if not rows:
            session.add_query_execution(
                query_product=product,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                outcome=QueryExecutionOutcome.EXPLICIT_EMPTY,
                related_relationship_observation_ids=(),
                source_field="Data",
                source_record_identity=f"US:{request.ASIN}:ASINRequestKeyword",
            )
            session.diagnostic(
                code="KEYWORD_PAGE_RETURNED_EMPTY",
                message="A successful bounded empty page is not zero search volume or no demand.",
                source_locator="Data",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
                affects_status=False,
            )
        for row in rows:
            keyword = keyword_identity(
                session.context.marketplace,
                session.context.locale,
                row.Keyword.Keyword,
            )
            source_identity = f"US:{request.ASIN}:{keyword.keyword_id}:PRODUCT_TO_KEYWORD"
            locator = f"Data[Keyword={keyword.keyword_id}]"
            session.add_relationship(
                product=product,
                keyword=keyword,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                relationship_type=RelationshipType.CANDIDATE_MEMBERSHIP,
                channel=Channel.UNKNOWN,
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=True,
                    normalized_value=True,
                    value_type=ValueType.BOOLEAN,
                    normalization_status=NormalizationStatus.NOT_APPLICABLE,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=locator,
                source_record_identity=source_identity,
                provider_semantic=(
                    "Bounded ASIN-to-keyword exposure within the approximate last 30 days and first three result pages"
                ),
                evidence_type=EvidenceType.OBSERVED,
                query_result_status=ResultStatus.POPULATED,
                period_type=PeriodType.ROLLING_30_DAYS,
                discriminator="bounded-membership",
            )

            organic = row.organic_position
            rank = {
                "raw_position": organic.raw_value,
                "page": organic.page,
                "position": organic.position,
                "page_slots": organic.page_slots,
                "page_scope": "FIRST_THREE_SEARCH_RESULT_PAGES",
                "observed_local_time": organic.observed_local_time,
                "timezone": None,
            }
            session.add_relationship(
                product=product,
                keyword=keyword,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                relationship_type=RelationshipType.RANK,
                channel=Channel.ORGANIC,
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=organic.raw_value,
                    normalized_value=rank,
                    value_type=ValueType.OBJECT,
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"{locator}.SearchPosition",
                source_record_identity=source_identity,
                provider_semantic=(
                    "Organic position within the documented first-three-pages scope; local timestamp timezone unknown"
                ),
                evidence_type=EvidenceType.OBSERVED,
                query_result_status=ResultStatus.POPULATED,
                rank=rank,
                period_type=PeriodType.ROLLING_30_DAYS,
                discriminator="bounded-organic-rank",
            )

            traffic = value_envelope(
                presence_status=PresenceStatus.PRESENT,
                raw_value=row.ShowShare,
                normalized_value=row.ShowShare,
                value_type=ValueType.NUMBER,
                unit=Unit(dimension="RATIO", unit_code="percent", unit_system="PROVIDER"),
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=SemanticStatus.CONFIRMED,
            )
            session.add_relationship(
                product=product,
                keyword=keyword,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                relationship_type=RelationshipType.TRAFFIC,
                channel=Channel.UNKNOWN,
                value=traffic,
                traffic=traffic,
                source_field=f"{locator}.ShowShare",
                source_record_identity=source_identity,
                provider_semantic="Traffic share within this bounded ASIN reverse-keyword result",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                query_result_status=ResultStatus.POPULATED,
                period_type=PeriodType.ROLLING_30_DAYS,
                discriminator="bounded-traffic-share",
            )

            search_volume = session.add_keyword_metric(
                keyword=keyword,
                metric="search_volume",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=row.Keyword.SearchVolume,
                    normalized_value=row.Keyword.SearchVolume,
                    value_type=ValueType.INTEGER,
                    unit=Unit(
                        dimension="COUNT",
                        unit_code="searches_per_30_days",
                        unit_system="PROVIDER",
                    ),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                ),
                source_field=f"{locator}.Keyword.SearchVolume",
                source_record_identity=source_identity,
                metric_semantic=(
                    "Provider 30-day search-volume evidence; estimation method remains unknown"
                ),
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                estimate_method_status=EstimateMethodStatus.UNKNOWN,
                period_type=PeriodType.ROLLING_30_DAYS,
                result_status=ResultStatus.PARTIAL,
                discriminator="bounded-search-volume",
            )
            issue_id = session.quality_issue(
                code="SEARCH_VOLUME_ESTIMATE_METHOD_UNKNOWN",
                subject=search_volume.subject,
                dimension="search_volume",
                message=(
                    f"{locator}.Keyword.SearchVolume: 30-day window proven; estimation method unavailable."
                ),
                blocking_scope=BlockingScope.NONE,
                origin_stage=OriginStage.RAW_EVIDENCE,
            )
            session.attach_issue((search_volume.observation_id,), issue_id)

            cpc = row.cpc_evidence(domain)
            cpc_range = row.cpc_range_evidence(domain)
            session.add_keyword_metric(
                keyword=keyword,
                metric="cpc",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=cpc.source_value,
                    normalized_value=_major_units(
                        cpc.source_value,
                        cpc.minor_unit_exponent,
                    ),
                    value_type=ValueType.NUMBER,
                    unit=Unit(
                        dimension="CURRENCY",
                        unit_code=cpc.currency,
                        unit_system="ISO_4217",
                    ),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"{locator}.Keyword.Cpc",
                source_record_identity=source_identity,
                metric_semantic=(
                    "US CPC converted from provider local minor units using explicit USD exponent 2; source integer retained"
                ),
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                estimate_method_status=EstimateMethodStatus.PARTIALLY_DOCUMENTED,
                range_value={
                    "minimum_source_minor_units": cpc_range[0].source_value,
                    "maximum_source_minor_units": cpc_range[1].source_value,
                    "minimum_major_units": _major_units(
                        cpc_range[0].source_value,
                        cpc_range[0].minor_unit_exponent,
                    ),
                    "maximum_major_units": _major_units(
                        cpc_range[1].source_value,
                        cpc_range[1].minor_unit_exponent,
                    ),
                    "currency": cpc.currency,
                    "minor_unit_exponent": cpc.minor_unit_exponent,
                    "source_unit_semantics": cpc.unit_semantics,
                },
                discriminator="cpc-usd-minor-unit-conversion",
            )

        if rows:
            related_ids = tuple(
                item.observation_id
                for item in session.observations
                if isinstance(item, ProductKeywordRelationshipObservation)
            )
            session.add_query_execution(
                query_product=product,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                outcome=QueryExecutionOutcome.RESULTS_RETURNED,
                related_relationship_observation_ids=related_ids,
                source_field="Data",
                source_record_identity=f"US:{request.ASIN}:ASINRequestKeyword",
                quality_issue_ids=tuple(item.issue_id for item in session.issues),
            )
        session.diagnostic(
            code="KEYWORD_UNIVERSE_INCOMPLETE",
            message=(
                "Returned rows are a bounded page; provider total, later pages, and complete keyword universe remain unavailable."
            ),
            source_locator="Data",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
        session.diagnostic(
            code="SPONSORED_PLACEMENT_UNAVAILABLE",
            message="No sponsored relationship is emitted from the accepted DTO slice.",
            source_locator="Data[*].AdPosition",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        session.diagnostic(
            code="OBSERVATION_TIMEZONE_UNKNOWN",
            message=(
                "SearchPositionDate remains local source context; Canonical observed_at and timezone stay unknown."
            ),
            source_locator="Data[*].SearchPositionDate",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        session.diagnostic(
            code="KEYWORD_LOCALE_CALLER_CONTEXT",
            message="Keyword locale comes from explicit caller context, not a provider-declared response field.",
            source_locator="context.locale",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        return session.finish()


__all__ = (
    "ASIN_REQUEST_KEYWORD_PAYLOAD_KIND",
    "PRODUCT_REQUEST_PAYLOAD_KIND",
    "PRODUCT_VARIATIONS_PAYLOAD_KIND",
    "SORFTIME_DTO_CONTRACT_VERSION",
    "SORFTIME_DTO_MAPPER_RULESET_VERSION",
    "SORFTIME_DTO_MAPPER_VERSION",
    "SORFTIME_DTO_MAPPING_SPECIFICATIONS",
    "SorftimeDtoMapperV0_1",
    "sorftime_sanitized_mapping_request",
)
