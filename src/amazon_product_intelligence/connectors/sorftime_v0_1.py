"""Sorftime connector definition backed only by audited provider evidence."""

from __future__ import annotations

from typing import Mapping

from amazon_product_intelligence.adapters import SorftimeAdapterV0_1
from amazon_product_intelligence.contracts import ObservationKind

from .base import AdapterBackedProvider
from .models import CanonicalSelector, CapabilityStatus, ProviderCapability
from .transport import ProviderOperation, ProviderTransport, RetryPolicy


def _operation(name: str, source_tool: str) -> ProviderOperation:
    return ProviderOperation(
        operation=name,
        payload_kind=name,
        source_tool=source_tool,
        method="PROVIDER_TOOL",
        endpoint=f"provider-tool://sorftime/{name}",
        requires_credential=True,
        credential_injection_name="provider_credential",
    )


SORFTIME_OPERATIONS = (
    _operation("product_detail", "product_detail"),
    _operation("product_variations", "product_variations"),
    _operation("product_reviews", "product_reviews"),
)

_ENDPOINTS = {item.operation: item.endpoint for item in SORFTIME_OPERATIONS}


def _capability(
    canonical_field: str,
    status: CapabilityStatus,
    *,
    source_field: str | None = None,
    operation: str | None = None,
    kind: ObservationKind | None = None,
    names: tuple[str, ...] = (),
    notes: str = "",
) -> ProviderCapability:
    return ProviderCapability(
        provider_id="sorftime",
        canonical_field=canonical_field,
        capability_status=status,
        source_field=source_field,
        endpoint=_ENDPOINTS.get(operation or ""),
        operation=operation,
        payload_kind=operation,
        selector=(
            CanonicalSelector(observation_kind=kind, canonical_names=names)
            if status in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
            else None
        ),
        notes=notes,
    )


SORFTIME_CAPABILITIES = (
    _capability(
        "product.asin",
        CapabilityStatus.AVAILABLE,
        source_field="data.asin",
        operation="product_detail",
    ),
    _capability(
        "product.marketplace",
        CapabilityStatus.PARTIAL,
        source_field="request amz_site",
        operation="product_detail",
        notes="Marketplace is audited request scope, not a stable response field.",
    ),
    _capability(
        "product.title",
        CapabilityStatus.AVAILABLE,
        source_field="data.title",
        operation="product_detail",
        kind=ObservationKind.PRODUCT_FACT,
        names=("title",),
    ),
    _capability(
        "product.brand",
        CapabilityStatus.AVAILABLE,
        source_field="data.brand",
        operation="product_detail",
        kind=ObservationKind.PRODUCT_FACT,
        names=("brand",),
    ),
    _capability(
        "product.category",
        CapabilityStatus.AVAILABLE,
        source_field="data.category / data.node_id",
        operation="product_detail",
        kind=ObservationKind.PRODUCT_FACT,
        names=("category", "category_node_id"),
    ),
    _capability(
        "product.parent_asin",
        CapabilityStatus.AVAILABLE,
        source_field="data.parent_asin",
        operation="product_detail",
        kind=ObservationKind.PRODUCT_FACT,
        names=("parent_product_relationship",),
        notes="Self-parent values remain unconfirmed and are not published as relationships.",
    ),
    _capability(
        "product.attributes",
        CapabilityStatus.PARTIAL,
        source_field="data.attributes / data.description",
        operation="product_detail",
        kind=ObservationKind.PRODUCT_FACT,
        names=(
            "brand",
            "color",
            "description",
            "exterior_finish",
            "inlet_connection_size",
            "inlet_connection_type",
            "item_dimensions",
            "item_weight",
            "material",
            "maximum_operating_pressure",
            "number_of_ports",
            "outlet_connection_size",
            "outlet_connection_type",
            "quantity",
            "size",
            "style",
            "weave_type",
        ),
        notes="Only audited structured attributes map; no unit conflict is resolved.",
    ),
    _capability(
        "product.fulfillment",
        CapabilityStatus.AVAILABLE,
        source_field="data.delivery_type",
        operation="product_detail",
        kind=ObservationKind.PRODUCT_FACT,
        names=("fulfillment",),
        notes="Confirmed provider input; unsupported payloads correctly return FIELD_MISSING.",
    ),
    _capability(
        "metric.price",
        CapabilityStatus.AVAILABLE,
        source_field="data.price",
        operation="product_detail",
        kind=ObservationKind.METRIC,
        names=("price",),
    ),
    _capability(
        "metric.rating",
        CapabilityStatus.AVAILABLE,
        source_field="data.star_rating",
        operation="product_detail",
        kind=ObservationKind.METRIC,
        names=("rating",),
    ),
    _capability(
        "metric.review_count",
        CapabilityStatus.AVAILABLE,
        source_field="data.review_count",
        operation="product_detail",
        kind=ObservationKind.METRIC,
        names=("review_count",),
    ),
    _capability(
        "metric.estimated_monthly_sales",
        CapabilityStatus.AVAILABLE,
        source_field="data.monthly_sales_volume",
        operation="product_detail",
        kind=ObservationKind.METRIC,
        names=("estimated_monthly_sales",),
        notes="Provider estimate; method and exact period remain unconfirmed.",
    ),
    _capability(
        "product.variation",
        CapabilityStatus.AVAILABLE,
        source_field="data[].Asin / data[].Property",
        operation="product_variations",
        kind=ObservationKind.PRODUCT_FACT,
        names=("variation", "size", "color"),
    ),
    _capability(
        "metric.estimated_variation_sales",
        CapabilityStatus.AVAILABLE,
        source_field="data[].SalesAmount",
        operation="product_variations",
        kind=ObservationKind.METRIC,
        names=("estimated_sales_volume",),
        notes="The -1 sentinel remains missing evidence, never zero sales.",
    ),
    _capability(
        "review.raw",
        CapabilityStatus.AVAILABLE,
        source_field="data[]",
        operation="product_reviews",
        kind=ObservationKind.REVIEW,
        notes="P1 capability; helpful votes remain MISSING when absent.",
    ),
    _capability("keyword.locale", CapabilityStatus.UNAVAILABLE),
    _capability("workflow.manual_review_status", CapabilityStatus.UNAVAILABLE),
    _capability("product.seller", CapabilityStatus.UNKNOWN),
    _capability("keyword.estimate_method_status", CapabilityStatus.UNKNOWN),
)


class SorftimeProvider(AdapterBackedProvider):
    """Replaceable Sorftime adapter with no guessed undocumented capability."""

    def __init__(
        self,
        transport: ProviderTransport,
        *,
        environment: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(
            provider_id="sorftime",
            display_name="Sorftime",
            adapter=SorftimeAdapterV0_1(),
            capabilities=SORFTIME_CAPABILITIES,
            operations=SORFTIME_OPERATIONS,
            transport=transport,
            environment=environment,
            retry_policy=retry_policy,
        )


__all__ = ("SORFTIME_CAPABILITIES", "SORFTIME_OPERATIONS", "SorftimeProvider")
