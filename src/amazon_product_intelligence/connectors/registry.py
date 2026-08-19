"""Configuration-driven provider registry and field-level candidate ordering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .base import DataProvider
from .errors import ProviderConnectorError, ProviderErrorCode
from .models import CapabilityStatus, ProviderCapability, ProviderConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderCandidate:
    provider: DataProvider
    configuration: ProviderConfig
    capability: ProviderCapability
    effective_priority: int


@dataclass(frozen=True, slots=True, kw_only=True)
class _Registration:
    provider: DataProvider
    configuration: ProviderConfig


class ProviderRegistry:
    """Provider-neutral registry; no concrete provider imports or branches."""

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}

    def register(self, provider: DataProvider, configuration: ProviderConfig) -> None:
        if not isinstance(provider, DataProvider):
            raise TypeError("provider must implement DataProvider")
        if provider.provider_id != configuration.provider_id:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "provider and configuration IDs must match",
                provider_id=provider.provider_id,
            )
        if provider.provider_id in self._registrations:
            raise ProviderConnectorError(
                ProviderErrorCode.DUPLICATE_PROVIDER,
                f"provider {provider.provider_id} is already registered",
                provider_id=provider.provider_id,
            )
        self._registrations[provider.provider_id] = _Registration(
            provider=provider,
            configuration=configuration,
        )

    def get(self, provider_id: str) -> DataProvider:
        return self._registration(provider_id).provider

    def configuration(self, provider_id: str) -> ProviderConfig:
        return self._registration(provider_id).configuration

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        registration = self._registration(provider_id)
        self._registrations[provider_id] = _Registration(
            provider=registration.provider,
            configuration=registration.configuration.with_enabled(enabled),
        )

    def set_priority(self, provider_id: str, priority: int) -> None:
        registration = self._registration(provider_id)
        self._registrations[provider_id] = _Registration(
            provider=registration.provider,
            configuration=registration.configuration.with_priority(priority),
        )

    def enabled(self) -> tuple[DataProvider, ...]:
        registrations = sorted(
            (item for item in self._registrations.values() if item.configuration.enabled),
            key=lambda item: (item.configuration.priority, item.provider.provider_id),
        )
        return tuple(item.provider for item in registrations)

    def capabilities(
        self,
        canonical_field: str | None = None,
        *,
        enabled_only: bool = False,
    ) -> tuple[ProviderCapability, ...]:
        values: list[ProviderCapability] = []
        for provider_id in sorted(self._registrations):
            registration = self._registrations[provider_id]
            if enabled_only and not registration.configuration.enabled:
                continue
            for capability in registration.provider.capabilities:
                if canonical_field is None or capability.canonical_field == canonical_field:
                    values.append(capability)
        return tuple(values)

    def candidates(self, canonical_field: str) -> tuple[ProviderCandidate, ...]:
        candidates: list[ProviderCandidate] = []
        for registration in self._registrations.values():
            if not registration.configuration.enabled:
                continue
            capability = registration.provider.capability(canonical_field)
            if capability is None or capability.capability_status not in {
                CapabilityStatus.AVAILABLE,
                CapabilityStatus.PARTIAL,
            }:
                continue
            candidates.append(
                ProviderCandidate(
                    provider=registration.provider,
                    configuration=registration.configuration,
                    capability=capability,
                    effective_priority=registration.configuration.priority_for(capability),
                )
            )
        return tuple(
            sorted(
                candidates,
                key=lambda item: (item.effective_priority, item.provider.provider_id),
            )
        )

    def _registration(self, provider_id: str) -> _Registration:
        try:
            return self._registrations[provider_id]
        except KeyError as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.PROVIDER_NOT_REGISTERED,
                f"provider {provider_id} is not registered",
                provider_id=provider_id,
            ) from exc


def build_registry(
    registrations: Iterable[tuple[DataProvider, ProviderConfig]],
) -> ProviderRegistry:
    """Generic composition helper; adding a provider requires only another pair."""

    registry = ProviderRegistry()
    for provider, configuration in registrations:
        registry.register(provider, configuration)
    return registry


__all__ = ("ProviderCandidate", "ProviderRegistry", "build_registry")
