"""Deterministic provider-qualified acquisition plans for Production Pipeline V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from amazon_product_intelligence.contracts import deterministic_id

from .providers import xiyou_reverse_keyword_parameters


ACQUISITION_PLAN_CONTRACT_VERSION = "production-acquisition-plan-v0.1"
SUPPORTED_PRODUCTION_PROVIDERS = ("xiyou", "sorftime")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class AcquisitionRole(StrEnum):
    PRODUCT = "PRODUCT"
    REVERSE_KEYWORD = "REVERSE_KEYWORD"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderAcquisitionStep:
    provider_id: str
    operation: str
    canonical_field: str
    parameters: Mapping[str, Any]
    role: AcquisitionRole
    marketplace: str
    locale: str
    currency: str
    asin: str | None
    ordinal: int
    step_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze(self.parameters))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderAcquisitionPlan:
    provider_id: str
    marketplace: str
    steps: tuple[ProviderAcquisitionStep, ...]
    contract_version: str = ACQUISITION_PLAN_CONTRACT_VERSION

    @property
    def product_steps(self) -> tuple[ProviderAcquisitionStep, ...]:
        return tuple(item for item in self.steps if item.role is AcquisitionRole.PRODUCT)

    @property
    def keyword_steps(self) -> tuple[ProviderAcquisitionStep, ...]:
        return tuple(
            item for item in self.steps if item.role is AcquisitionRole.REVERSE_KEYWORD
        )


def build_acquisition_plan(
    *,
    provider_id: str,
    marketplace: str,
    asins: tuple[str, ...],
    locale: str = "en-us",
    currency: str = "USD",
) -> ProviderAcquisitionPlan:
    """Build the frozen minimum plan; the selected provider is never substituted."""

    if provider_id not in SUPPORTED_PRODUCTION_PROVIDERS:
        raise ValueError("provider_id must be exactly xiyou or sorftime")
    if provider_id == "sorftime" and marketplace != "US":
        raise ValueError("Sorftime production acquisition is proven only for US")

    specifications: list[tuple[str, str, Mapping[str, Any], AcquisitionRole, str | None]] = []
    if provider_id == "xiyou":
        specifications.append(
            (
                "asin_info",
                "metric.price",
                {
                    "entities": [
                        {"country": marketplace, "asin": asin} for asin in asins
                    ]
                },
                AcquisitionRole.PRODUCT,
                None,
            )
        )
        specifications.extend(
            (
                "asin_keywords",
                "relationship.product_to_keyword",
                xiyou_reverse_keyword_parameters(asin=asin, marketplace=marketplace),
                AcquisitionRole.REVERSE_KEYWORD,
                asin,
            )
            for asin in asins
        )
    else:
        specifications.extend(
            (
                "ProductRequest",
                "product.asin",
                {"ASIN": asin, "Trend": 2},
                AcquisitionRole.PRODUCT,
                asin,
            )
            for asin in asins
        )
        specifications.extend(
            (
                "ASINRequestKeyword",
                "relationship.product_to_keyword",
                {"ASIN": asin, "PageIndex": 1, "PageSize": 20},
                AcquisitionRole.REVERSE_KEYWORD,
                asin,
            )
            for asin in asins
        )

    steps = tuple(
        ProviderAcquisitionStep(
            provider_id=provider_id,
            operation=operation,
            canonical_field=canonical_field,
            parameters=parameters,
            role=role,
            marketplace=marketplace,
            locale=locale,
            currency=currency,
            asin=asin,
            ordinal=ordinal,
            step_id=deterministic_id(
                "production-acquisition-step",
                {
                    "contract_version": ACQUISITION_PLAN_CONTRACT_VERSION,
                    "provider_id": provider_id,
                    "marketplace": marketplace,
                    "locale": locale,
                    "currency": currency,
                    "operation": operation,
                    "canonical_field": canonical_field,
                    "parameters": parameters,
                    "role": role.value,
                    "asin": asin,
                    "ordinal": ordinal,
                },
            ),
        )
        for ordinal, (operation, canonical_field, parameters, role, asin) in enumerate(
            specifications, 1
        )
    )
    return ProviderAcquisitionPlan(
        provider_id=provider_id,
        marketplace=marketplace,
        steps=steps,
    )


__all__ = (
    "ACQUISITION_PLAN_CONTRACT_VERSION",
    "SUPPORTED_PRODUCTION_PROVIDERS",
    "AcquisitionRole",
    "ProviderAcquisitionPlan",
    "ProviderAcquisitionStep",
    "build_acquisition_plan",
)
