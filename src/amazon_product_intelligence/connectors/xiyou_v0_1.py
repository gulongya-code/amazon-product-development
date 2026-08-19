"""XiYou connector definition backed by the audited offline adapter."""

from __future__ import annotations

from typing import Mapping

from amazon_product_intelligence.adapters import XiYouAdapterV0_1
from amazon_product_intelligence.contracts import ObservationKind

from .base import AdapterBackedProvider
from .models import CanonicalSelector, CapabilityStatus, ProviderCapability
from .transport import ProviderOperation, ProviderTransport, RetryPolicy


def _operation(
    name: str,
    payload_kind: str,
    source_tool: str,
    endpoint: str,
) -> ProviderOperation:
    return ProviderOperation(
        operation=name,
        payload_kind=payload_kind,
        source_tool=source_tool,
        method="POST",
        endpoint=endpoint,
        requires_credential=True,
        credential_injection_name="X-Api-Key",
        public_headers={"X-Auth-Version": "2.0"},
    )


XIYOU_OPERATIONS = (
    _operation("asin_info", "asin_info_http_v2", "get_asin_info", "/v1/asins/info"),
    _operation(
        "asin_variations",
        "asin_variations",
        "get_asin_variations",
        "/v1/asins/variations",
    ),
    _operation(
        "asin_orders_last_30_days",
        "asin_orders_last_30_days",
        "get_asin_orders_last_30_days",
        "/v1/asins/orders",
    ),
    _operation(
        "asin_bsr_trends",
        "asin_bsr_trends",
        "get_asin_bsr_trends",
        "/v1/asins/bsrInfo/trends/daily",
    ),
    _operation(
        "keyword_info",
        "keyword_info_http_v2",
        "get_keyword_info",
        "/v1/searchTerms/info",
    ),
    _operation(
        "keyword_asin_analysis",
        "keyword_asin_analysis_http_v2",
        "get_keyword_asin_analysis",
        "/v1/searchTerms/analysis/list/period",
    ),
    _operation(
        "asin_keywords",
        "asin_keywords_http_v2",
        "get_asin_keywords",
        "/v1/asins/research/list/period",
    ),
)

_ENDPOINTS = {item.operation: item.endpoint for item in XIYOU_OPERATIONS}


def _capability(
    canonical_field: str,
    status: CapabilityStatus,
    *,
    source_field: str | None = None,
    operation: str | None = None,
    payload_kind: str | None = None,
    kind: ObservationKind | None = None,
    names: tuple[str, ...] = (),
    notes: str = "",
    accepts_empty_query: bool = False,
) -> ProviderCapability:
    return ProviderCapability(
        provider_id="xiyou",
        canonical_field=canonical_field,
        capability_status=status,
        source_field=source_field,
        endpoint=_ENDPOINTS.get(operation or ""),
        operation=operation,
        payload_kind=payload_kind,
        selector=(
            CanonicalSelector(observation_kind=kind, canonical_names=names)
            if status in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
            else None
        ),
        notes=notes,
        accepts_empty_query=accepts_empty_query,
    )


XIYOU_CAPABILITIES = (
    _capability(
        "product.asin",
        CapabilityStatus.AVAILABLE,
        source_field="entities[].asin",
        operation="asin_info",
        payload_kind="asin_info_http_v2",
    ),
    _capability(
        "product.marketplace",
        CapabilityStatus.PARTIAL,
        source_field="entities[].country / request country",
        operation="asin_info",
        payload_kind="asin_info_http_v2",
        notes="Some operations rely on explicit request scope.",
    ),
    _capability(
        "product.title",
        CapabilityStatus.AVAILABLE,
        source_field="entities[].title",
        operation="asin_info",
        payload_kind="asin_info_http_v2",
        kind=ObservationKind.PRODUCT_FACT,
        names=("title",),
    ),
    _capability(
        "metric.price",
        CapabilityStatus.AVAILABLE,
        source_field="entities[].price",
        operation="asin_info",
        payload_kind="asin_info_http_v2",
        kind=ObservationKind.METRIC,
        names=("price",),
    ),
    _capability(
        "metric.rating",
        CapabilityStatus.AVAILABLE,
        source_field="entities[].stars",
        operation="asin_info",
        payload_kind="asin_info_http_v2",
        kind=ObservationKind.METRIC,
        names=("rating",),
    ),
    _capability(
        "metric.review_count",
        CapabilityStatus.AVAILABLE,
        source_field="entities[].ratings",
        operation="asin_info",
        payload_kind="asin_info_http_v2",
        kind=ObservationKind.METRIC,
        names=("review_count",),
    ),
    _capability(
        "product.parent_asin",
        CapabilityStatus.AVAILABLE,
        source_field="data.parentAsin",
        operation="asin_variations",
        payload_kind="asin_variations",
        kind=ObservationKind.PRODUCT_FACT,
        names=("parent_product_relationship",),
    ),
    _capability(
        "product.variation",
        CapabilityStatus.AVAILABLE,
        source_field="data.childAsins[]",
        operation="asin_variations",
        payload_kind="asin_variations",
        kind=ObservationKind.PRODUCT_FACT,
        names=("child_product_relationship",),
    ),
    _capability(
        "metric.orders",
        CapabilityStatus.AVAILABLE,
        source_field="data.entities[].orders",
        operation="asin_orders_last_30_days",
        payload_kind="asin_orders_last_30_days",
        kind=ObservationKind.METRIC,
        names=("orders",),
        notes="Method and parent/child grain remain explicitly unconfirmed.",
    ),
    _capability(
        "metric.bsr",
        CapabilityStatus.AVAILABLE,
        source_field="data.trends[].values[].rank",
        operation="asin_bsr_trends",
        payload_kind="asin_bsr_trends",
        kind=ObservationKind.METRIC,
        names=("bsr",),
    ),
    _capability(
        "metric.bsr_context",
        CapabilityStatus.AVAILABLE,
        source_field="data.categoryTree[]",
        operation="asin_bsr_trends",
        payload_kind="asin_bsr_trends",
        kind=ObservationKind.METRIC,
        names=("bsr",),
    ),
    _capability(
        "keyword.search_volume",
        CapabilityStatus.AVAILABLE,
        source_field="list[].abaReport.weeklySearchVolume",
        operation="keyword_info",
        payload_kind="keyword_info_http_v2",
        kind=ObservationKind.KEYWORD_METRIC,
        names=("search_volume",),
    ),
    _capability(
        "keyword.aba_rank",
        CapabilityStatus.AVAILABLE,
        source_field="list[].abaReport.searchFrequencyRank",
        operation="keyword_info",
        payload_kind="keyword_info_http_v2",
        kind=ObservationKind.KEYWORD_METRIC,
        names=("aba_search_frequency_rank",),
    ),
    _capability(
        "keyword.cpc",
        CapabilityStatus.AVAILABLE,
        source_field="list[].costPerClick.value",
        operation="keyword_info",
        payload_kind="keyword_info_http_v2",
        kind=ObservationKind.KEYWORD_METRIC,
        names=("cpc",),
    ),
    _capability(
        "keyword.difficulty",
        CapabilityStatus.AVAILABLE,
        source_field="list[].competitiveDifficulty",
        operation="keyword_info",
        payload_kind="keyword_info_http_v2",
        kind=ObservationKind.KEYWORD_METRIC,
        names=("competition_difficulty",),
        notes="Provider scale and method remain unconfirmed.",
    ),
    _capability(
        "relationship.keyword_to_product",
        CapabilityStatus.AVAILABLE,
        source_field="list[] / list[].ranks[]",
        operation="keyword_asin_analysis",
        payload_kind="keyword_asin_analysis_http_v2",
        kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
        names=("CANDIDATE_MEMBERSHIP",),
        accepts_empty_query=True,
    ),
    _capability(
        "relationship.product_to_keyword",
        CapabilityStatus.AVAILABLE,
        source_field="list[] / list[].ranks[]",
        operation="asin_keywords",
        payload_kind="asin_keywords_http_v2",
        kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
        names=("CANDIDATE_MEMBERSHIP",),
        accepts_empty_query=True,
    ),
    _capability(
        "keyword.channel",
        CapabilityStatus.PARTIAL,
        source_field="list[].ranks[].position",
        operation="keyword_asin_analysis",
        payload_kind="keyword_asin_analysis_http_v2",
        kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
        names=("RANK", "TRAFFIC"),
        notes="Only audited position codes map; unknown codes remain UNKNOWN.",
        accepts_empty_query=True,
    ),
    _capability("keyword.locale", CapabilityStatus.UNAVAILABLE),
    _capability("workflow.manual_review_status", CapabilityStatus.UNAVAILABLE),
    _capability("product.seller", CapabilityStatus.UNKNOWN),
    _capability("keyword.estimate_method_status", CapabilityStatus.UNKNOWN),
)


class XiYouProvider(AdapterBackedProvider):
    """Replaceable XiYou infrastructure adapter; transport is always injected."""

    def __init__(
        self,
        transport: ProviderTransport,
        *,
        environment: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(
            provider_id="xiyou",
            display_name="XiYou",
            adapter=XiYouAdapterV0_1(),
            capabilities=XIYOU_CAPABILITIES,
            operations=XIYOU_OPERATIONS,
            transport=transport,
            environment=environment,
            retry_policy=retry_policy,
        )


__all__ = ("XIYOU_CAPABILITIES", "XIYOU_OPERATIONS", "XiYouProvider")
