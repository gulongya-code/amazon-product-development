"""DTO-first Sorftime ordinary-HTTP provider for the proven US slice."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from typing import Any, Mapping

from amazon_product_intelligence.adapters import AdaptationContext, AdapterError
from amazon_product_intelligence.adapters.sorftime_dto_mapper_v0_1 import (
    SorftimeDtoMapperV0_1,
    sorftime_sanitized_mapping_request,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    ObservationKind,
    QueryExecutionOutcome,
)

from .errors import ProviderConnectorError, ProviderErrorCode
from .models import (
    CanonicalSelector,
    CapabilityStatus,
    ProviderCapability,
    ProviderConfig,
    ProviderFetchResult,
    ProviderFetchStatus,
    ProviderRequest,
)
from .sorftime_client import (
    ASIN_REQUEST_KEYWORD_OPERATION,
    PRODUCT_REQUEST_OPERATION,
    PRODUCT_VARIATIONS_OPERATION,
    SORFTIME_HTTP_OPERATIONS,
    SorftimeClient,
)
from .sorftime_dtos_v0_1 import (
    SorftimeAsinRequestKeywordRequest,
    SorftimeProductRequest,
    SorftimeProductVariationsRequest,
)
from .transport import ProviderOperation, ProviderTransport, RetryPolicy


SORFTIME_OPERATIONS = SORFTIME_HTTP_OPERATIONS
_ENDPOINTS = {item.operation: item.endpoint for item in SORFTIME_OPERATIONS}
_PAYLOAD_KINDS = {item.operation: item.payload_kind for item in SORFTIME_OPERATIONS}


def _capability(
    canonical_field: str,
    status: CapabilityStatus,
    *,
    source_field: str,
    operation: str,
    kind: ObservationKind,
    names: tuple[str, ...],
    notes: str = "",
    accepts_empty_query: bool = False,
) -> ProviderCapability:
    return ProviderCapability(
        provider_id="sorftime",
        canonical_field=canonical_field,
        capability_status=status,
        source_field=source_field,
        endpoint=_ENDPOINTS[operation],
        operation=operation,
        payload_kind=_PAYLOAD_KINDS[operation],
        selector=CanonicalSelector(observation_kind=kind, canonical_names=names),
        notes=notes,
        accepts_empty_query=accepts_empty_query,
    )


SORFTIME_CAPABILITIES = (
    _capability(
        "product.title",
        CapabilityStatus.AVAILABLE,
        source_field="Data.Title",
        operation="ProductRequest",
        kind=ObservationKind.PRODUCT_FACT,
        names=("title",),
        notes="Exact requested-ASIN listing title only; no title NLP or variation-title inference.",
    ),
    _capability(
        "product.asin",
        CapabilityStatus.AVAILABLE,
        source_field="Data.Asin / Data.VariationASIN",
        operation="ProductRequest",
        kind=ObservationKind.PRODUCT_FACT,
        names=("asin",),
        notes="Requested and bounded child identities only; family completeness is unproven.",
    ),
    _capability(
        "product.parent_asin",
        CapabilityStatus.PARTIAL,
        source_field="Data.ParentAsin",
        operation="ProductRequest",
        kind=ObservationKind.PRODUCT_FACT,
        names=("parent_product_relationship",),
        notes="Distinct provider-reported parent identity only; self-parent is not an edge.",
    ),
    _capability(
        "product.attributes",
        CapabilityStatus.PARTIAL,
        source_field="Data.Attribute[].Color / Data.Attribute[].Size",
        operation="ProductRequest",
        kind=ObservationKind.PRODUCT_FACT,
        names=("variation_identity_collection", "color", "size"),
        notes="Only bounded child Color/Size facts from the strict DTO slice.",
    ),
    _capability(
        "product.variation",
        CapabilityStatus.PARTIAL,
        source_field="Data[].Asin / Data[].Property",
        operation="ProductVariations",
        kind=ObservationKind.PRODUCT_FACT,
        names=("asin", "color", "size"),
        notes="One bounded page; no parent edge or complete-family claim.",
        accepts_empty_query=True,
    ),
    _capability(
        "metric.estimated_variation_sales",
        CapabilityStatus.PARTIAL,
        source_field="Data[].SalesAmount",
        operation="ProductVariations",
        kind=ObservationKind.METRIC,
        names=("estimated_variation_sales",),
        notes="-1 and positive unproven-period sales remain Canonical UNKNOWN.",
        accepts_empty_query=True,
    ),
    _capability(
        "relationship.product_to_keyword",
        CapabilityStatus.AVAILABLE,
        source_field="Data[].Keyword.Keyword",
        operation="ASINRequestKeyword",
        kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
        names=("CANDIDATE_MEMBERSHIP",),
        notes="Bounded to the documented approximate 30-day/first-three-pages slice.",
        accepts_empty_query=True,
    ),
    _capability(
        "keyword.channel",
        CapabilityStatus.PARTIAL,
        source_field="Data[].SearchPosition / Data[].ShowShare",
        operation="ASINRequestKeyword",
        kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
        names=("RANK", "TRAFFIC"),
        notes="Organic rank and bounded traffic only; sponsored semantics unavailable.",
        accepts_empty_query=True,
    ),
    _capability(
        "keyword.search_volume",
        CapabilityStatus.PARTIAL,
        source_field="Data[].Keyword.SearchVolume",
        operation="ASINRequestKeyword",
        kind=ObservationKind.KEYWORD_METRIC,
        names=("search_volume",),
        notes="30-day provider estimate with unknown estimation method.",
        accepts_empty_query=True,
    ),
    _capability(
        "keyword.cpc",
        CapabilityStatus.AVAILABLE,
        source_field="Data[].Keyword.Cpc / Data[].Keyword.CpcRange",
        operation="ASINRequestKeyword",
        kind=ObservationKind.KEYWORD_METRIC,
        names=("cpc",),
        notes="US local minor units converted under explicit USD exponent-2 context.",
        accepts_empty_query=True,
    ),
)


class SorftimeProvider:
    """Production-ready typed connector, intentionally not registered by SP-040D."""

    provider_id = "sorftime"
    display_name = "Sorftime"
    capabilities = SORFTIME_CAPABILITIES

    def __init__(
        self,
        transport: ProviderTransport | None = None,
        *,
        environment: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
        client: SorftimeClient | None = None,
    ) -> None:
        if client is not None and transport is not None:
            raise ValueError("provide either client or transport, not both")
        self._client = client or SorftimeClient(
            transport=transport,
            environment=environment,
            retry_policy=retry_policy,
        )
        self._mapper = SorftimeDtoMapperV0_1()
        self._capability_index = {item.canonical_field: item for item in self.capabilities}
        self._operation_index = {item.operation: item for item in SORFTIME_OPERATIONS}

    def capability(self, canonical_field: str) -> ProviderCapability | None:
        return self._capability_index.get(canonical_field)

    def fetch(
        self,
        request: ProviderRequest,
        configuration: ProviderConfig,
    ) -> ProviderFetchResult:
        self._validate_configuration(configuration)
        capability = self.capability(request.canonical_field)
        if capability is None:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                f"provider sorftime does not declare {request.canonical_field}",
                provider_id="sorftime",
            )
        self._validate_context(request)
        operation = self._operation_index[capability.operation or ""]
        typed_request = self._typed_request(operation, request.parameters)
        result = self._execute_typed(operation, typed_request, configuration)
        context = AdaptationContext(
            provider="sorftime",
            payload_kind=operation.payload_kind,
            source_tool=operation.source_tool,
            marketplace=request.marketplace,
            locale=request.locale,
            retrieved_at=request.retrieved_at,
            transformed_at=request.transformed_at,
            collection_run_id=request.collection_run_id,
            sanitized_request=sorftime_sanitized_mapping_request(typed_request),
            currency=request.currency,
        )
        try:
            adaptation = self._map(operation, typed_request, result.response, context)
        except (AdapterError, ContractValidationError, ValueError) as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.SCHEMA_MISMATCH,
                "Sorftime typed response could not be mapped",
                provider_id="sorftime",
                operation=operation.operation,
                details={"exception_type": type(exc).__name__},
            ) from exc
        observations = self._matching_observations(capability, adaptation.bundle.observations)
        if observations:
            status = ProviderFetchStatus.RETURNED
        elif capability.accepts_empty_query and any(
            item.outcome is QueryExecutionOutcome.EXPLICIT_EMPTY
            for item in adaptation.bundle.query_execution_records
        ):
            status = ProviderFetchStatus.EMPTY
        elif adaptation.raw_evidence is not None and adaptation.raw_evidence.response_status == "EMPTY":
            status = ProviderFetchStatus.EMPTY
        else:
            status = ProviderFetchStatus.FIELD_MISSING
        return ProviderFetchResult(
            provider_id="sorftime",
            canonical_field=request.canonical_field,
            capability=capability,
            status=status,
            adaptation=adaptation,
            observations=observations,
        )

    @staticmethod
    def _validate_configuration(configuration: ProviderConfig) -> None:
        if configuration.provider_id != "sorftime":
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "provider configuration ID does not match Sorftime connector",
                provider_id="sorftime",
            )
        if not configuration.enabled:
            raise ProviderConnectorError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "provider sorftime is disabled",
                provider_id="sorftime",
            )

    @staticmethod
    def _validate_context(request: ProviderRequest) -> None:
        if request.marketplace != "US" or request.currency != "USD":
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "only Sorftime US/domain=1/USD context is proven",
                provider_id="sorftime",
                details={"domain_status": "UNPROVEN"},
            )

    @staticmethod
    def _typed_request(operation: ProviderOperation, parameters: Mapping[str, Any]) -> Any:
        if not isinstance(parameters, MappingABC):
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "Sorftime request parameters must be a mapping",
                provider_id="sorftime",
                operation=operation.operation,
            )
        request_type = {
            "ProductRequest": SorftimeProductRequest,
            "ProductVariations": SorftimeProductVariationsRequest,
            "ASINRequestKeyword": SorftimeAsinRequestKeywordRequest,
        }[operation.operation]
        try:
            return request_type.from_dict(dict(parameters))
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "Sorftime request failed strict DTO validation",
                provider_id="sorftime",
                operation=operation.operation,
                details={"exception_type": type(exc).__name__},
            ) from exc

    def _execute_typed(
        self, operation: ProviderOperation, request: Any, configuration: ProviderConfig
    ) -> Any:
        if operation is PRODUCT_REQUEST_OPERATION:
            return self._client.product_request(request, configuration)
        if operation is PRODUCT_VARIATIONS_OPERATION:
            return self._client.product_variations(request, configuration)
        if operation is ASIN_REQUEST_KEYWORD_OPERATION:
            return self._client.asin_request_keyword(request, configuration)
        raise ProviderConnectorError(
            ProviderErrorCode.CONFIGURATION,
            "Sorftime operation is not part of the accepted HTTP contract",
            provider_id="sorftime",
        )

    def _map(self, operation: ProviderOperation, request: Any, response: Any, context: AdaptationContext) -> Any:
        if operation is PRODUCT_REQUEST_OPERATION:
            return self._mapper.map_product_request(request, response, context)
        if operation is PRODUCT_VARIATIONS_OPERATION:
            return self._mapper.map_product_variations(request, response, context)
        if operation is ASIN_REQUEST_KEYWORD_OPERATION:
            return self._mapper.map_asin_request_keyword(request, response, context)
        raise ProviderConnectorError(
            ProviderErrorCode.CONFIGURATION,
            "Sorftime operation is not part of the accepted mapper contract",
            provider_id="sorftime",
        )

    @staticmethod
    def _matching_observations(
        capability: ProviderCapability,
        observations: tuple[Any, ...],
    ) -> tuple[Any, ...]:
        selector = capability.selector
        if selector is None:
            return ()
        return tuple(item for item in observations if selector.matches(item))


__all__ = ("SORFTIME_CAPABILITIES", "SORFTIME_OPERATIONS", "SorftimeProvider")
