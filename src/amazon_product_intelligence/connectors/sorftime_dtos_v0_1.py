"""Strict offline Sorftime provider DTOs for the SP-040A minimum slice.

This module validates provider-shaped request and response data only.  It does
not construct HTTP requests, inject credentials, emit Canonical observations,
or infer any provider semantics beyond the accepted SP-040A evidence.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Any, Mapping, TypeVar

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)

from .errors import ProviderConnectorError, ProviderErrorCode


_ASIN = re.compile(r"^[A-Z0-9]{10}$")
_ORGANIC_POSITION = re.compile(
    r"^第(?P<page>[1-9][0-9]*)页，第(?P<position>[1-9][0-9]*)/(?P<slots>[1-9][0-9]*)位$"
)
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_LOCAL_DATETIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$")
_VARIATION_PROPERTIES = frozenset({"Color", "Size"})
_PRODUCT_REQUEST_WIRE_CAPTURE_VERSION = "sorftime-product-request-wire-v0.1"
_UNSAFE_WIRE_FIELD_TOKENS = frozenset(
    {
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "password",
        "secret",
        "token",
    }
)


def _fail(message: str) -> None:
    raise ContractValidationError(message)


def _require_asin(name: str, value: Any) -> str:
    if type(value) is not str or not _ASIN.fullmatch(value):
        _fail(f"{name} must be one normalized uppercase 10-character ASIN")
    return value


def _require_text(name: str, value: Any) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{name} must be non-empty text without surrounding whitespace")
    return value


def _require_date(name: str, value: str) -> date:
    if not _DATE.fullmatch(value):
        _fail(f"{name} must use yyyy-MM-dd")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractValidationError(f"{name} must be a real calendar date") from exc


def _require_local_datetime(name: str, value: str) -> None:
    if not _LOCAL_DATETIME.fullmatch(value):
        _fail(f"{name} must use yyyy-MM-dd HH:mm without an inferred timezone")
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ContractValidationError(f"{name} must be a real local date-time") from exc


def _provider_body(contract: JsonContract) -> dict[str, Any]:
    return {
        field.name: getattr(contract, field.name)
        for field in fields(contract)
        if getattr(contract, field.name) is not None
    }


def _request_identity(operation: str, body: Mapping[str, Any], domain: "SorftimeDomainContext") -> str:
    return deterministic_id(
        "sorftime-request",
        {"operation": operation, "domain": domain.domain, "body": body},
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeDomainContext(JsonContract):
    """Only the Amazon US mapping proven by SP-040A."""

    domain: int
    marketplace: str
    currency: str
    minor_unit_exponent: int

    def __post_init__(self) -> None:
        if (
            type(self.domain) is not int
            or self.domain != 1
            or self.marketplace != "US"
            or self.currency != "USD"
            or type(self.minor_unit_exponent) is not int
            or self.minor_unit_exponent != 2
        ):
            _fail("only Sorftime Amazon US domain=1 with USD minor-unit exponent 2 is proven")


SORFTIME_AMAZON_US = SorftimeDomainContext(
    domain=1,
    marketplace="US",
    currency="USD",
    minor_unit_exponent=2,
)


def resolve_sorftime_domain(domain: int) -> SorftimeDomainContext:
    if type(domain) is not int or domain != 1:
        raise ProviderConnectorError(
            ProviderErrorCode.CONFIGURATION,
            "Sorftime marketplace/domain mapping is not proven",
            provider_id="sorftime",
            details={"domain_status": "UNPROVEN"},
        )
    return SORFTIME_AMAZON_US


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductRequest(JsonContract):
    ASIN: str
    Trend: int | None = None
    QueryTrendStartDt: str | None = None
    QueryTrendEndDt: str | None = None

    def __post_init__(self) -> None:
        _require_asin("ProductRequest.ASIN", self.ASIN)
        if self.Trend is not None and (type(self.Trend) is not int or self.Trend not in {1, 2}):
            _fail("ProductRequest.Trend must be 1, 2, or omitted")
        if self.QueryTrendStartDt is not None:
            if self.Trend != 1:
                _fail("ProductRequest.QueryTrendStartDt is valid only when Trend=1")
            start = _require_date("ProductRequest.QueryTrendStartDt", self.QueryTrendStartDt)
        else:
            start = None
        if self.QueryTrendEndDt is not None:
            if self.Trend != 1 or start is None:
                _fail("ProductRequest.QueryTrendEndDt requires Trend=1 and QueryTrendStartDt")
            end = _require_date("ProductRequest.QueryTrendEndDt", self.QueryTrendEndDt)
            if end < start:
                _fail("ProductRequest.QueryTrendEndDt must not precede QueryTrendStartDt")

    def to_provider_body(self) -> dict[str, Any]:
        return _provider_body(self)

    def request_id(self, domain: SorftimeDomainContext = SORFTIME_AMAZON_US) -> str:
        return _request_identity("ProductRequest", self.to_provider_body(), domain)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductVariationsRequest(JsonContract):
    Asin: str
    PageIndex: int = 1
    IsSalesVolume: bool | None = None

    def __post_init__(self) -> None:
        _require_asin("ProductVariations.Asin", self.Asin)
        if type(self.PageIndex) is not int or self.PageIndex < 1:
            _fail("ProductVariations.PageIndex must be an integer starting at 1")
        if self.IsSalesVolume is not None and type(self.IsSalesVolume) is not bool:
            _fail("ProductVariations.IsSalesVolume must be a boolean or omitted")

    @property
    def sales_requested(self) -> bool:
        return self.IsSalesVolume is True

    def to_provider_body(self) -> dict[str, Any]:
        return _provider_body(self)

    def request_id(self, domain: SorftimeDomainContext = SORFTIME_AMAZON_US) -> str:
        return _request_identity("ProductVariations", self.to_provider_body(), domain)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeAsinRequestKeywordRequest(JsonContract):
    ASIN: str
    PageIndex: int = 1
    PageSize: int = 20

    def __post_init__(self) -> None:
        _require_asin("ASINRequestKeyword.ASIN", self.ASIN)
        if type(self.PageIndex) is not int or self.PageIndex < 1:
            _fail("ASINRequestKeyword.PageIndex must be an integer starting at 1")
        if type(self.PageSize) is not int or not 20 <= self.PageSize <= 200:
            _fail("ASINRequestKeyword.PageSize must be between 20 and 200")

    def to_provider_body(self) -> dict[str, Any]:
        return _provider_body(self)

    def request_id(self, domain: SorftimeDomainContext = SORFTIME_AMAZON_US) -> str:
        return _request_identity("ASINRequestKeyword", self.to_provider_body(), domain)


class SorftimeSalesState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNKNOWN = "UNKNOWN"


class SorftimePageState(StrEnum):
    RETURNED = "RETURNED"
    EMPTY = "EMPTY"


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductAttribute(JsonContract):
    Asin: str
    Name: str
    Value: str

    def __post_init__(self) -> None:
        _require_asin("ProductRequest.Attribute.Asin", self.Asin)
        if self.Name not in _VARIATION_PROPERTIES:
            _fail("ProductRequest.Attribute supports only the observed Color/Size keys")
        _require_text("ProductRequest.Attribute.Value", self.Value)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductRequestData(JsonContract):
    Asin: str
    ParentAsin: str | None
    VariationASIN: tuple[str, ...] | None
    VariationASINCount: int
    Attribute: tuple[tuple[str, ...], ...] | None
    ListingSalesVolumeOfMonthTrend: Any
    ListingSalesOfMonthTrend: Any
    RankTrend: Any
    BsrRankTrend: Any
    DealTrend: Any
    PriceTrend: Any
    ListPriceTrend: Any
    # The ordinary ProductRequest wire census proved these two legacy names may
    # be absent.  Their similarly named ``*DailyTrend`` extensions are retained
    # as capture-only evidence and are deliberately not treated as aliases.
    ListingSalesVolumeOfDaily: Any = None
    ListingSalesOfDaily: Any = None
    Title: str | None = None

    def __post_init__(self) -> None:
        _require_asin("ProductRequest.Data.Asin", self.Asin)
        if self.ParentAsin is not None:
            _require_asin("ProductRequest.Data.ParentAsin", self.ParentAsin)
        if type(self.VariationASINCount) is not int or self.VariationASINCount < 0:
            _fail("ProductRequest.Data.VariationASINCount must be a non-negative integer")
        variations = tuple(self.VariationASIN or ())
        for asin in variations:
            _require_asin("ProductRequest.Data.VariationASIN[]", asin)
        if len(set(variations)) != len(variations):
            _fail("ProductRequest.Data.VariationASIN contains duplicate identities")
        if len(variations) != self.VariationASINCount:
            _fail("ProductRequest.Data.VariationASINCount disagrees with VariationASIN")
        if variations and self.Asin not in variations:
            _fail("ProductRequest.Data.Asin is absent from the returned variation collection")
        if not variations and self.Attribute not in {None, ()}:
            _fail("ProductRequest.Data.Attribute requires returned variations")
        seen_attribute_asins: set[str] = set()
        for row in tuple(self.Attribute or ()):
            if len(row) < 3 or len(row) % 2 == 0:
                _fail("ProductRequest.Data.Attribute rows require ASIN followed by key/value pairs")
            row_asin = _require_asin("ProductRequest.Data.Attribute[].Asin", row[0])
            if row_asin not in variations:
                _fail("ProductRequest.Data.Attribute row ASIN is outside VariationASIN")
            if row_asin in seen_attribute_asins:
                _fail("ProductRequest.Data.Attribute contains duplicate ASIN rows")
            seen_attribute_asins.add(row_asin)
            names: set[str] = set()
            for index in range(1, len(row), 2):
                attribute = SorftimeProductAttribute(
                    Asin=row_asin,
                    Name=row[index],
                    Value=row[index + 1],
                )
                if attribute.Name in names:
                    _fail("ProductRequest.Data.Attribute row contains a duplicate key")
                names.add(attribute.Name)
        for name in (
            "ListingSalesVolumeOfDaily",
            "ListingSalesOfDaily",
            "ListingSalesVolumeOfMonthTrend",
            "ListingSalesOfMonthTrend",
            "RankTrend",
            "BsrRankTrend",
            "DealTrend",
            "PriceTrend",
            "ListPriceTrend",
        ):
            if getattr(self, name) is not None:
                _fail(f"ProductRequest.Data.{name} is unavailable in the accepted Trend=2 DTO slice")
        if self.Title is not None:
            if type(self.Title) is not str or not self.Title.strip():
                _fail("ProductRequest.Data.Title must be a non-empty string when present")

    @property
    def has_distinct_parent(self) -> bool:
        return self.ParentAsin is not None and self.ParentAsin != self.Asin

    @property
    def attributes(self) -> tuple[SorftimeProductAttribute, ...]:
        return tuple(
            SorftimeProductAttribute(Asin=row[0], Name=row[index], Value=row[index + 1])
            for row in tuple(self.Attribute or ())
            for index in range(1, len(row), 2)
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductVariationRow(JsonContract):
    Asin: str
    ItemIndex: int
    ItemTotal: int
    Property: str
    SalesAmount: int

    def __post_init__(self) -> None:
        _require_asin("ProductVariations.Data[].Asin", self.Asin)
        if type(self.ItemIndex) is not int or self.ItemIndex < 1:
            _fail("ProductVariations.Data[].ItemIndex must be an integer starting at 1")
        if type(self.ItemTotal) is not int or self.ItemTotal < 1:
            _fail("ProductVariations.Data[].ItemTotal must be a positive integer")
        if self.ItemIndex > self.ItemTotal:
            _fail("ProductVariations.Data[].ItemIndex exceeds ItemTotal")
        if type(self.SalesAmount) is not int or self.SalesAmount < -1:
            _fail("ProductVariations.Data[].SalesAmount must be -1 or a non-negative integer")
        self._parse_properties()

    def _parse_properties(self) -> tuple[tuple[str, str], ...]:
        _require_text("ProductVariations.Data[].Property", self.Property)
        pairs: list[tuple[str, str]] = []
        for raw_pair in self.Property.split(","):
            if raw_pair.count(":") != 1:
                _fail("ProductVariations.Data[].Property requires comma-separated key:value pairs")
            name, value = raw_pair.split(":", 1)
            if name not in _VARIATION_PROPERTIES or not value or value != value.strip():
                _fail("ProductVariations.Data[].Property supports non-empty Color/Size pairs only")
            pairs.append((name, value))
        if {name for name, _ in pairs} != _VARIATION_PROPERTIES or len(pairs) != 2:
            _fail("ProductVariations.Data[].Property requires exactly one Color and one Size")
        return tuple(pairs)

    @property
    def properties(self) -> tuple[tuple[str, str], ...]:
        return self._parse_properties()

    @property
    def sales_state(self) -> SorftimeSalesState:
        return SorftimeSalesState.UNKNOWN if self.SalesAmount == -1 else SorftimeSalesState.AVAILABLE

    @property
    def sales_value(self) -> int | None:
        return None if self.SalesAmount == -1 else self.SalesAmount


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeKeywordSummary(JsonContract):
    Keyword: str
    SearchVolume: int
    Cpc: int
    CpcRange: tuple[int, int]

    def __post_init__(self) -> None:
        _require_text("ASINRequestKeyword.Data[].Keyword.Keyword", self.Keyword)
        if type(self.SearchVolume) is not int or self.SearchVolume < 0:
            _fail("ASINRequestKeyword Keyword.SearchVolume must be a non-negative integer")
        if type(self.Cpc) is not int or self.Cpc < 0:
            _fail("ASINRequestKeyword Keyword.Cpc must be a non-negative local-minor-unit integer")
        if len(self.CpcRange) != 2 or any(type(item) is not int or item < 0 for item in self.CpcRange):
            _fail("ASINRequestKeyword Keyword.CpcRange requires two non-negative integers")
        minimum, maximum = self.CpcRange
        if minimum > self.Cpc or self.Cpc > maximum:
            _fail("ASINRequestKeyword Keyword.Cpc must fall within CpcRange")

    @property
    def search_volume_period_days(self) -> int:
        return 30

    @property
    def search_volume_estimate_method(self) -> None:
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeMinorUnitEvidence(JsonContract):
    source_value: int
    currency: str
    minor_unit_exponent: int
    unit_semantics: str = "LOCAL_MINOR_UNIT"

    def __post_init__(self) -> None:
        if type(self.source_value) is not int or self.source_value < 0:
            _fail("minor-unit source value must be a non-negative integer")
        if self.currency != "USD" or self.minor_unit_exponent != 2:
            _fail("only the proven US USD minor-unit context is supported")
        if self.unit_semantics != "LOCAL_MINOR_UNIT":
            _fail("minor-unit evidence must retain LOCAL_MINOR_UNIT semantics")

    @property
    def major_value(self) -> Decimal:
        return Decimal(self.source_value).scaleb(-self.minor_unit_exponent)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeOrganicPosition(JsonContract):
    raw_value: str
    page: int
    position: int
    page_slots: int
    observed_local_time: str
    timezone: str | None = None

    def __post_init__(self) -> None:
        if self.page not in {1, 2, 3}:
            _fail("ASINRequestKeyword organic exposure must remain within the documented first 3 pages")
        if self.position < 1 or self.page_slots < 1 or self.position > self.page_slots:
            _fail("ASINRequestKeyword organic position is outside its page bounds")
        _require_local_datetime("ASINRequestKeyword.SearchPositionDate", self.observed_local_time)
        if self.timezone is not None:
            _fail("ASINRequestKeyword SearchPositionDate timezone is not proven")


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeAsinKeywordRow(JsonContract):
    ShowType: str
    ShowShare: float
    PositionType: tuple[str, ...]
    AdPosition: str | None
    AdPositionDate: str | None
    SearchPosition: str
    SearchPositionDate: str
    Keyword: SorftimeKeywordSummary

    def __post_init__(self) -> None:
        _require_text("ASINRequestKeyword.Data[].ShowType", self.ShowType)
        if not 0 <= self.ShowShare <= 100:
            _fail("ASINRequestKeyword.Data[].ShowShare must be between 0 and 100")
        if not self.PositionType or any(
            type(item) is not str or not item or item != item.strip()
            for item in self.PositionType
        ):
            _fail("ASINRequestKeyword.Data[].PositionType must contain non-empty labels")
        if self.AdPosition not in {None, ""} or self.AdPositionDate not in {None, ""}:
            _fail("ASINRequestKeyword sponsored placement remains unavailable in the accepted DTO slice")
        self._organic_position()

    def _organic_position(self) -> SorftimeOrganicPosition:
        match = _ORGANIC_POSITION.fullmatch(self.SearchPosition)
        if match is None:
            _fail("ASINRequestKeyword.Data[].SearchPosition has an unsupported shape")
        _require_local_datetime("ASINRequestKeyword.Data[].SearchPositionDate", self.SearchPositionDate)
        return SorftimeOrganicPosition(
            raw_value=self.SearchPosition,
            page=int(match.group("page")),
            position=int(match.group("position")),
            page_slots=int(match.group("slots")),
            observed_local_time=self.SearchPositionDate,
            timezone=None,
        )

    @property
    def organic_position(self) -> SorftimeOrganicPosition:
        return self._organic_position()

    @property
    def sponsored_available(self) -> bool:
        return False

    def cpc_evidence(
        self,
        domain: SorftimeDomainContext = SORFTIME_AMAZON_US,
    ) -> SorftimeMinorUnitEvidence:
        return SorftimeMinorUnitEvidence(
            source_value=self.Keyword.Cpc,
            currency=domain.currency,
            minor_unit_exponent=domain.minor_unit_exponent,
        )

    def cpc_range_evidence(
        self,
        domain: SorftimeDomainContext = SORFTIME_AMAZON_US,
    ) -> tuple[SorftimeMinorUnitEvidence, SorftimeMinorUnitEvidence]:
        return tuple(
            SorftimeMinorUnitEvidence(
                source_value=value,
                currency=domain.currency,
                minor_unit_exponent=domain.minor_unit_exponent,
            )
            for value in self.Keyword.CpcRange
        )


def _validate_envelope(
    *,
    RequestLeft: int,
    RequestConsumed: int,
    Code: int,
    Message: str | None,
) -> None:
    if type(RequestLeft) is not int or RequestLeft < 0:
        _fail("Sorftime success RequestLeft must be a non-negative integer")
    if type(RequestConsumed) is not int or RequestConsumed < 0:
        _fail("Sorftime success RequestConsumed must be a non-negative integer")
    if type(Code) is not int or Code != 0:
        _fail("Sorftime success envelope requires Code=0")
    if Message is not None:
        _require_text("Sorftime success Message", Message)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductRequestResponse(JsonContract):
    RequestLeft: int
    RequestConsumed: int
    Code: int
    Message: str | None
    Data: SorftimeProductRequestData

    def __post_init__(self) -> None:
        _validate_envelope(
            RequestLeft=self.RequestLeft,
            RequestConsumed=self.RequestConsumed,
            Code=self.Code,
            Message=self.Message,
        )

    def validate_against(self, request: SorftimeProductRequest) -> None:
        if request.ASIN != self.Data.Asin:
            _fail("ProductRequest response ASIN does not match the request")
        if request.Trend != 2:
            _fail("only the accepted ProductRequest Trend=2 response slice is available")


class SorftimeWireFieldStatus(StrEnum):
    PROMOTED = "PROMOTED"
    CAPTURED_UNVERIFIED = "CAPTURED_UNVERIFIED"
    UNAVAILABLE_MISSING = "UNAVAILABLE_MISSING"
    IGNORED_UNSAFE = "IGNORED_UNSAFE"


# R3 proved that these exact fields can carry arrays on the ordinary Trend=2
# wire.  Their business semantics remain unapproved, so the values stay in the
# runtime-only capture and the semantic DTO continues to expose UNAVAILABLE.
_PRODUCT_REQUEST_CAPTURE_ONLY_ARRAY_DRIFT = frozenset({"BsrRankTrend", "DealTrend"})
_PRODUCT_REQUEST_PROVEN_OPTIONAL_FIELDS = frozenset(
    {"ListingSalesVolumeOfDaily", "ListingSalesOfDaily"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeWireFieldInventory(JsonContract):
    field_name: str
    json_type: str
    nullable: bool
    status: SorftimeWireFieldStatus
    source_operation: str = "ProductRequest"
    source_version: str = _PRODUCT_REQUEST_WIRE_CAPTURE_VERSION


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeStructuralFieldDiagnostic(JsonContract):
    field_name: str
    json_type: str
    nullable: bool
    status: str
    expected_semantic_field: str | None = None
    expected_json_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductRequestStructuralDiagnostic(JsonContract):
    """Scalar-free ProductRequest schema evidence safe for census persistence."""

    http_status: int
    envelope_keys: tuple[str, ...]
    data_root_field_count: int
    data_fields: tuple[SorftimeStructuralFieldDiagnostic, ...]
    missing_semantic_fields: tuple[str, ...]
    casing_aliases: tuple[str, ...]
    variation_asin_count: int | None
    attribute_row_count: int | None
    attribute_row_json_types: tuple[str, ...]
    attribute_row_lengths: tuple[int | None, ...]
    unsafe_field_count: int
    provider_code: int | None
    request_consumed: int | None
    request_left: int | None
    parser_accepted: bool
    parser_failure_kind: str | None
    parser_failure_path: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductRequestWireCapture:
    """Runtime-only ProductRequest extensions kept outside semantic DTOs and fingerprints."""

    semantic_response: SorftimeProductRequestResponse = field(repr=False)
    extensions: Mapping[str, Any] = field(repr=False)
    field_inventory: tuple[SorftimeWireFieldInventory, ...]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "source_operation": "ProductRequest",
            "source_version": _PRODUCT_REQUEST_WIRE_CAPTURE_VERSION,
            "field_inventory": [item.to_dict() for item in self.field_inventory],
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeProductVariationsResponse(JsonContract):
    RequestLeft: int
    RequestConsumed: int
    Code: int
    Message: str | None
    Data: tuple[SorftimeProductVariationRow, ...]

    def __post_init__(self) -> None:
        _validate_envelope(
            RequestLeft=self.RequestLeft,
            RequestConsumed=self.RequestConsumed,
            Code=self.Code,
            Message=self.Message,
        )
        if len(self.Data) > 100:
            _fail("ProductVariations response exceeds the documented 100-row page bound")
        asins = tuple(row.Asin for row in self.Data)
        indexes = tuple(row.ItemIndex for row in self.Data)
        if len(set(asins)) != len(asins):
            _fail("ProductVariations response contains duplicate ASINs")
        if len(set(indexes)) != len(indexes):
            _fail("ProductVariations response contains duplicate ItemIndex values")
        totals = {row.ItemTotal for row in self.Data}
        if len(totals) > 1:
            _fail("ProductVariations response rows disagree on ItemTotal")

    @property
    def page_state(self) -> SorftimePageState:
        return SorftimePageState.EMPTY if not self.Data else SorftimePageState.RETURNED

    @property
    def provider_total(self) -> int | None:
        return self.Data[0].ItemTotal if self.Data else None

    def validate_against(self, request: SorftimeProductVariationsRequest) -> None:
        if not request.sales_requested and any(row.sales_state is SorftimeSalesState.AVAILABLE for row in self.Data):
            _fail("ProductVariations numeric sales require explicit IsSalesVolume=true")


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeAsinRequestKeywordResponse(JsonContract):
    RequestLeft: int
    RequestConsumed: int
    Code: int
    Message: str | None
    Data: tuple[SorftimeAsinKeywordRow, ...]

    def __post_init__(self) -> None:
        _validate_envelope(
            RequestLeft=self.RequestLeft,
            RequestConsumed=self.RequestConsumed,
            Code=self.Code,
            Message=self.Message,
        )
        keywords = tuple(row.Keyword.Keyword.casefold() for row in self.Data)
        if len(set(keywords)) != len(keywords):
            _fail("ASINRequestKeyword response contains duplicate keyword identities")

    @property
    def page_state(self) -> SorftimePageState:
        return SorftimePageState.EMPTY if not self.Data else SorftimePageState.RETURNED

    @property
    def provider_total(self) -> None:
        return None

    @property
    def complete_keyword_universe(self) -> bool:
        return False

    @property
    def relationship_window_days(self) -> int:
        return 30

    @property
    def search_result_page_bound(self) -> int:
        return 3

    def validate_against(self, request: SorftimeAsinRequestKeywordRequest) -> None:
        if len(self.Data) > request.PageSize:
            _fail("ASINRequestKeyword returned row count exceeds requested PageSize")


_ResponseT = TypeVar(
    "_ResponseT",
    SorftimeProductRequestResponse,
    SorftimeProductVariationsResponse,
    SorftimeAsinRequestKeywordResponse,
)


def _data_state(payload: Any) -> str:
    if not isinstance(payload, MappingABC):
        return "MALFORMED_ENVELOPE"
    if "Data" not in payload:
        return "MISSING"
    if payload["Data"] is None:
        return "EXPLICIT_NULL"
    return "PRESENT"


def _require_http_success(status_code: int, operation: str) -> None:
    if type(status_code) is not int or not 100 <= status_code <= 599:
        raise ProviderConnectorError(
            ProviderErrorCode.BAD_RESPONSE,
            "provider HTTP status is invalid",
            provider_id="sorftime",
            operation=operation,
        )
    if 200 <= status_code <= 299:
        return
    if status_code in {401, 403}:
        code = ProviderErrorCode.AUTHENTICATION
    elif status_code == 429:
        code = ProviderErrorCode.RATE_LIMIT
    elif status_code in {408, 504}:
        code = ProviderErrorCode.TIMEOUT
    elif status_code >= 500:
        code = ProviderErrorCode.PROVIDER_UNAVAILABLE
    else:
        code = ProviderErrorCode.BAD_RESPONSE
    raise ProviderConnectorError(
        code,
        "Sorftime HTTP request failed before business-envelope validation",
        provider_id="sorftime",
        operation=operation,
        retryable=code in {
            ProviderErrorCode.RATE_LIMIT,
            ProviderErrorCode.TIMEOUT,
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
        },
        details={"http_status": status_code, "provider_envelope_accepted": False},
    )


def _decode_success(
    response_type: type[_ResponseT],
    payload: Any,
    *,
    operation: str,
    http_status: int,
) -> _ResponseT:
    _require_http_success(http_status, operation)
    if isinstance(payload, MappingABC):
        code = payload.get("Code")
        if type(code) is int and code != 0:
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                "Sorftime returned a non-success business code",
                provider_id="sorftime",
                operation=operation,
                details={
                    "business_code": code,
                    "data_state": _data_state(payload),
                    "http_status": http_status,
                },
            )
    try:
        return response_type.from_dict(payload)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ProviderConnectorError(
            ProviderErrorCode.SCHEMA_MISMATCH,
            "Sorftime response failed strict DTO validation",
            provider_id="sorftime",
            operation=operation,
            details={
                "data_state": _data_state(payload),
                "exception_type": type(exc).__name__,
                "http_status": http_status,
            },
        ) from exc


def _wire_json_type(value: Any) -> str:
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "BOOLEAN"
    if type(value) in {int, float}:
        return "NUMBER"
    if type(value) is str:
        return "STRING"
    if isinstance(value, MappingABC):
        return "OBJECT"
    if isinstance(value, (list, tuple)):
        return "ARRAY"
    return "UNSUPPORTED"


def _unsafe_wire_field_name(name: str) -> bool:
    normalized = "".join(character for character in name.casefold() if character.isalnum())
    return any(token in normalized for token in _UNSAFE_WIRE_FIELD_TOKENS)


def _contains_unsafe_wire_field(value: Any) -> bool:
    if isinstance(value, MappingABC):
        return any(
            type(name) is not str
            or _unsafe_wire_field_name(name)
            or _contains_unsafe_wire_field(child)
            for name, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_unsafe_wire_field(child) for child in value)
    return False


def _freeze_captured_json(value: Any) -> Any:
    canonical_json(value)
    if isinstance(value, MappingABC):
        return MappingProxyType(
            {name: _freeze_captured_json(child) for name, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_captured_json(child) for child in value)
    return value


def _product_request_schema_mismatch(
    message: str,
    *,
    payload: Any,
    http_status: int,
    field_path: str,
) -> ProviderConnectorError:
    return ProviderConnectorError(
        ProviderErrorCode.SCHEMA_MISMATCH,
        message,
        provider_id="sorftime",
        operation="ProductRequest",
        details={
            "data_state": _data_state(payload),
            "field_path": field_path,
            "http_status": http_status,
        },
    )


def parse_product_request_wire_response(
    payload: Any,
    request: SorftimeProductRequest,
    *,
    http_status: int = 200,
) -> SorftimeProductRequestWireCapture:
    """Split a rich ProductRequest wire payload from its strict semantic slice."""

    _require_http_success(http_status, "ProductRequest")
    if not isinstance(payload, MappingABC) or not isinstance(payload.get("Data"), MappingABC):
        _decode_success(
            SorftimeProductRequestResponse,
            payload,
            operation="ProductRequest",
            http_status=http_status,
        )
        raise AssertionError("strict ProductRequest decoding unexpectedly accepted malformed Data")

    data = payload["Data"]
    semantic_names = frozenset(item.name for item in fields(SorftimeProductRequestData))
    semantic_names_by_case = {name.casefold(): name for name in semantic_names}
    semantic_data: dict[str, Any] = {}
    extensions: dict[str, Any] = {}
    inventory: list[SorftimeWireFieldInventory] = []

    for name, value in data.items():
        if type(name) is not str:
            raise _product_request_schema_mismatch(
                "Sorftime ProductRequest Data field names must be strings",
                payload=payload,
                http_status=http_status,
                field_path="Data",
            )
        if (
            name in _PRODUCT_REQUEST_CAPTURE_ONLY_ARRAY_DRIFT
            and _wire_json_type(value) == "ARRAY"
        ):
            semantic_data[name] = None
            extensions[name] = _freeze_captured_json(value)
            status = SorftimeWireFieldStatus.CAPTURED_UNVERIFIED
        elif name in semantic_names:
            semantic_data[name] = value
            status = SorftimeWireFieldStatus.PROMOTED
        elif name.casefold() in semantic_names_by_case:
            expected = semantic_names_by_case[name.casefold()]
            raise _product_request_schema_mismatch(
                "Sorftime ProductRequest semantic field casing is invalid",
                payload=payload,
                http_status=http_status,
                field_path=f"Data.{name};expected={expected}",
            )
        elif _unsafe_wire_field_name(name) or _contains_unsafe_wire_field(value):
            status = SorftimeWireFieldStatus.IGNORED_UNSAFE
        else:
            try:
                extensions[name] = _freeze_captured_json(value)
            except (ContractValidationError, TypeError, ValueError) as exc:
                raise _product_request_schema_mismatch(
                    "Sorftime ProductRequest extension is not JSON-safe",
                    payload=payload,
                    http_status=http_status,
                    field_path=f"Data.{name}",
                ) from exc
            status = SorftimeWireFieldStatus.CAPTURED_UNVERIFIED
        inventory.append(
            SorftimeWireFieldInventory(
                field_name=name,
                json_type=_wire_json_type(value),
                nullable=value is None,
                status=status,
            )
        )

    for name in sorted(_PRODUCT_REQUEST_PROVEN_OPTIONAL_FIELDS - data.keys()):
        inventory.append(
            SorftimeWireFieldInventory(
                field_name=name,
                json_type="MISSING",
                nullable=False,
                status=SorftimeWireFieldStatus.UNAVAILABLE_MISSING,
            )
        )

    semantic_payload = dict(payload)
    semantic_payload["Data"] = semantic_data
    response = _decode_success(
        SorftimeProductRequestResponse,
        semantic_payload,
        operation="ProductRequest",
        http_status=http_status,
    )
    try:
        response.validate_against(request)
    except ContractValidationError as exc:
        raise ProviderConnectorError(
            ProviderErrorCode.SCHEMA_MISMATCH,
            "Sorftime ProductRequest request/response contract mismatch",
            provider_id="sorftime",
            operation="ProductRequest",
            details={"mismatch": "REQUEST_RESPONSE"},
        ) from exc
    return SorftimeProductRequestWireCapture(
        semantic_response=response,
        extensions=MappingProxyType(dict(sorted(extensions.items()))),
        field_inventory=tuple(sorted(inventory, key=lambda item: item.field_name)),
    )


def parse_product_request_response(
    payload: Any,
    request: SorftimeProductRequest,
    *,
    http_status: int = 200,
) -> SorftimeProductRequestResponse:
    return parse_product_request_wire_response(
        payload,
        request,
        http_status=http_status,
    ).semantic_response


_PRODUCT_REQUEST_DIAGNOSTIC_TYPES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "Asin": ("STRING",),
        "ParentAsin": ("NULL", "STRING"),
        "VariationASIN": ("ARRAY", "NULL"),
        "VariationASINCount": ("NUMBER",),
        "Attribute": ("ARRAY", "NULL"),
        "ListingSalesVolumeOfDaily": ("NULL",),
        "ListingSalesOfDaily": ("NULL",),
        "ListingSalesVolumeOfMonthTrend": ("NULL",),
        "ListingSalesOfMonthTrend": ("NULL",),
        "RankTrend": ("NULL",),
        "BsrRankTrend": ("ARRAY", "NULL"),
        "DealTrend": ("ARRAY", "NULL"),
        "PriceTrend": ("NULL",),
        "ListPriceTrend": ("NULL",),
        "Title": ("NULL", "STRING"),
    }
)
_PRODUCT_REQUEST_REQUIRED_DIAGNOSTIC_FIELDS = frozenset(
    name
    for name in _PRODUCT_REQUEST_DIAGNOSTIC_TYPES
    if name != "Title" and name not in _PRODUCT_REQUEST_PROVEN_OPTIONAL_FIELDS
)
_PRODUCT_REQUEST_ENVELOPE_FIELDS = frozenset(
    {"RequestLeft", "RequestConsumed", "Code", "Message", "Data"}
)


def _diagnostic_counter(payload: Mapping[str, Any], name: str) -> int | None:
    value = payload.get(name)
    return value if type(value) is int and value >= 0 else None


def _diagnostic_safe_field_name(name: str) -> str:
    return "[REDACTED_UNSAFE]" if _unsafe_wire_field_name(name) else name


def _unique_casefold_value(data: Mapping[str, Any], semantic_name: str) -> Any:
    matches = [
        value
        for name, value in data.items()
        if name.casefold() == semantic_name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def diagnose_product_request_wire_structure(
    payload: Any,
    request: SorftimeProductRequest,
    *,
    http_status: int = 200,
) -> SorftimeProductRequestStructuralDiagnostic:
    """Describe ProductRequest structure without retaining business scalar values."""

    envelope_keys: tuple[str, ...] = ()
    data: Mapping[str, Any] = MappingProxyType({})
    unsafe_field_count = 0
    if isinstance(payload, MappingABC):
        envelope_keys = tuple(
            sorted(
                _diagnostic_safe_field_name(name)
                for name in payload
                if type(name) is str
            )
        )
        candidate = payload.get("Data")
        if isinstance(candidate, MappingABC):
            data = candidate

    semantic_by_case = {
        name.casefold(): name for name in _PRODUCT_REQUEST_DIAGNOSTIC_TYPES
    }
    observed_by_case: dict[str, list[str]] = {}
    diagnostics: list[SorftimeStructuralFieldDiagnostic] = []
    for name, value in data.items():
        if type(name) is not str:
            unsafe_field_count += 1
            continue
        observed_by_case.setdefault(name.casefold(), []).append(name)
        unsafe = _unsafe_wire_field_name(name) or _contains_unsafe_wire_field(value)
        if unsafe:
            unsafe_field_count += 1
            diagnostics.append(
                SorftimeStructuralFieldDiagnostic(
                    field_name="[REDACTED_UNSAFE]",
                    json_type=_wire_json_type(value),
                    nullable=value is None,
                    status="IGNORED_UNSAFE",
                )
            )
            continue
        expected = semantic_by_case.get(name.casefold())
        exact = name in _PRODUCT_REQUEST_DIAGNOSTIC_TYPES
        diagnostics.append(
            SorftimeStructuralFieldDiagnostic(
                field_name=name,
                json_type=_wire_json_type(value),
                nullable=value is None,
                status=(
                    "CAPTURED_PROVEN_ARRAY_DRIFT"
                    if exact
                    and name in _PRODUCT_REQUEST_CAPTURE_ONLY_ARRAY_DRIFT
                    and _wire_json_type(value) == "ARRAY"
                    else "PROMOTED_EXACT"
                    if exact
                    else "CASING_ALIAS_CANDIDATE"
                    if expected is not None
                    else "CAPTURED_UNVERIFIED"
                ),
                expected_semantic_field=expected,
                expected_json_types=(
                    _PRODUCT_REQUEST_DIAGNOSTIC_TYPES[expected]
                    if expected is not None
                    else ()
                ),
            )
        )

    casing_aliases = tuple(
        sorted(
            f"{observed}->{expected}"
            for observed_names in observed_by_case.values()
            for observed in observed_names
            for expected in (semantic_by_case.get(observed.casefold()),)
            if expected is not None and observed != expected
        )
    )
    missing = tuple(
        sorted(
            name
            for name in _PRODUCT_REQUEST_DIAGNOSTIC_TYPES
            if name.casefold() not in observed_by_case
        )
    )

    variation = _unique_casefold_value(data, "VariationASIN")
    variation_count = len(variation) if isinstance(variation, (list, tuple)) else None
    attribute = _unique_casefold_value(data, "Attribute")
    attribute_rows = tuple(attribute) if isinstance(attribute, (list, tuple)) else ()
    attribute_row_types = tuple(_wire_json_type(row) for row in attribute_rows)
    attribute_row_lengths = tuple(
        len(row) if isinstance(row, (list, tuple)) else None for row in attribute_rows
    )

    failure_kind: str | None = None
    failure_path: str | None = None
    if not isinstance(payload, MappingABC):
        failure_kind, failure_path = "ENVELOPE_SHAPE", "$"
    else:
        raw_envelope_names = {name for name in payload if type(name) is str}
        if raw_envelope_names != _PRODUCT_REQUEST_ENVELOPE_FIELDS:
            failure_kind, failure_path = "ENVELOPE_SHAPE", "$"
        elif not isinstance(payload.get("Data"), MappingABC):
            failure_kind, failure_path = "ENVELOPE_SHAPE", "Data"
        else:
            duplicate = next(
                (
                    expected
                    for folded, names in sorted(observed_by_case.items())
                    for expected in (semantic_by_case.get(folded),)
                    if expected is not None and len(names) > 1
                ),
                None,
            )
            if duplicate is not None:
                failure_kind, failure_path = "WIRE_FIELD_CASING", f"Data.{duplicate}"
            elif casing_aliases:
                observed = casing_aliases[0].split("->", 1)[0]
                failure_kind, failure_path = "WIRE_FIELD_CASING", f"Data.{observed}"
            else:
                required_missing = sorted(
                    name
                    for name in _PRODUCT_REQUEST_REQUIRED_DIAGNOSTIC_FIELDS
                    if name not in data
                )
                if required_missing:
                    failure_kind = "SEMANTIC_FIELD_MISSING"
                    failure_path = f"Data.{required_missing[0]}"
                else:
                    incompatible = next(
                        (
                            item
                            for item in sorted(diagnostics, key=lambda item: item.field_name)
                            if item.expected_semantic_field is not None
                            and item.json_type not in item.expected_json_types
                        ),
                        None,
                    )
                    if incompatible is not None:
                        failure_kind = (
                            "SEMANTIC_FIELD_NULLABILITY"
                            if incompatible.json_type == "NULL"
                            or incompatible.expected_json_types == ("NULL",)
                            else "SEMANTIC_FIELD_TYPE"
                        )
                        failure_path = f"Data.{incompatible.field_name}"

    parser_accepted = False
    if failure_kind is None:
        try:
            parse_product_request_response(payload, request, http_status=http_status)
        except ProviderConnectorError as exc:
            failure_kind = "OTHER_PROVEN_WIRE_DRIFT"
            failure_path = str(exc.details.get("field_path") or "Data")
        else:
            parser_accepted = True

    mapping_payload = payload if isinstance(payload, MappingABC) else MappingProxyType({})
    return SorftimeProductRequestStructuralDiagnostic(
        http_status=http_status,
        envelope_keys=envelope_keys,
        data_root_field_count=len(data),
        data_fields=tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.field_name,
                    item.json_type,
                    item.status,
                ),
            )
        ),
        missing_semantic_fields=missing,
        casing_aliases=casing_aliases,
        variation_asin_count=variation_count,
        attribute_row_count=(
            len(attribute_rows) if isinstance(attribute, (list, tuple)) else None
        ),
        attribute_row_json_types=attribute_row_types,
        attribute_row_lengths=attribute_row_lengths,
        unsafe_field_count=unsafe_field_count,
        provider_code=_diagnostic_counter(mapping_payload, "Code"),
        request_consumed=_diagnostic_counter(mapping_payload, "RequestConsumed"),
        request_left=_diagnostic_counter(mapping_payload, "RequestLeft"),
        parser_accepted=parser_accepted,
        parser_failure_kind=failure_kind,
        parser_failure_path=failure_path,
    )


def parse_product_variations_response(
    payload: Any,
    request: SorftimeProductVariationsRequest,
    *,
    http_status: int = 200,
) -> SorftimeProductVariationsResponse:
    response = _decode_success(
        SorftimeProductVariationsResponse,
        payload,
        operation="ProductVariations",
        http_status=http_status,
    )
    try:
        response.validate_against(request)
    except ContractValidationError as exc:
        raise ProviderConnectorError(
            ProviderErrorCode.SCHEMA_MISMATCH,
            "Sorftime ProductVariations request/response contract mismatch",
            provider_id="sorftime",
            operation="ProductVariations",
            details={"mismatch": "REQUEST_RESPONSE"},
        ) from exc
    return response


def parse_asin_request_keyword_response(
    payload: Any,
    request: SorftimeAsinRequestKeywordRequest,
    *,
    http_status: int = 200,
) -> SorftimeAsinRequestKeywordResponse:
    response = _decode_success(
        SorftimeAsinRequestKeywordResponse,
        payload,
        operation="ASINRequestKeyword",
        http_status=http_status,
    )
    try:
        response.validate_against(request)
    except ContractValidationError as exc:
        raise ProviderConnectorError(
            ProviderErrorCode.SCHEMA_MISMATCH,
            "Sorftime ASINRequestKeyword request/response contract mismatch",
            provider_id="sorftime",
            operation="ASINRequestKeyword",
            details={"mismatch": "REQUEST_RESPONSE"},
        ) from exc
    return response


def sorftime_dto_json(contract: JsonContract) -> str:
    return canonical_json(contract)


__all__ = (
    "SORFTIME_AMAZON_US",
    "SorftimeAsinKeywordRow",
    "SorftimeAsinRequestKeywordRequest",
    "SorftimeAsinRequestKeywordResponse",
    "SorftimeDomainContext",
    "SorftimeKeywordSummary",
    "SorftimeMinorUnitEvidence",
    "SorftimeOrganicPosition",
    "SorftimePageState",
    "SorftimeProductAttribute",
    "SorftimeProductRequest",
    "SorftimeProductRequestData",
    "SorftimeProductRequestResponse",
    "SorftimeProductRequestStructuralDiagnostic",
    "SorftimeProductRequestWireCapture",
    "SorftimeProductVariationRow",
    "SorftimeProductVariationsRequest",
    "SorftimeProductVariationsResponse",
    "SorftimeSalesState",
    "SorftimeStructuralFieldDiagnostic",
    "SorftimeWireFieldInventory",
    "SorftimeWireFieldStatus",
    "parse_asin_request_keyword_response",
    "diagnose_product_request_wire_structure",
    "parse_product_request_response",
    "parse_product_request_wire_response",
    "parse_product_variations_response",
    "resolve_sorftime_domain",
    "sorftime_dto_json",
)
