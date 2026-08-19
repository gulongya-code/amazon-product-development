"""Field-level provider selection and basic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import ProviderConnectorError, ProviderErrorCode
from .models import ProviderFetchResult, ProviderFetchStatus, ProviderRequest
from .registry import ProviderRegistry


class ProviderAttemptStatus(StrEnum):
    SELECTED = "SELECTED"
    EMPTY_SELECTED = "EMPTY_SELECTED"
    FIELD_MISSING = "FIELD_MISSING"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderAttempt:
    provider_id: str
    status: ProviderAttemptStatus
    error_code: ProviderErrorCode | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "provider_id": self.provider_id,
            "status": self.status.value,
            "error_code": self.error_code.value if self.error_code is not None else None,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderResolution:
    canonical_field: str
    selected_provider_id: str
    result: ProviderFetchResult
    attempts: tuple[ProviderAttempt, ...]


class ProviderResolver:
    """Resolve through configured candidates without concrete provider knowledge."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def resolve(self, request: ProviderRequest) -> ProviderResolution:
        candidates = self._registry.candidates(request.canonical_field)
        if not candidates:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                f"no enabled provider can supply {request.canonical_field}",
                details={"canonical_field": request.canonical_field},
            )
        attempts: list[ProviderAttempt] = []
        for candidate in candidates:
            try:
                result = candidate.provider.fetch(request, candidate.configuration)
            except ProviderConnectorError as exc:
                attempts.append(
                    ProviderAttempt(
                        provider_id=candidate.provider.provider_id,
                        status=ProviderAttemptStatus.FAILED,
                        error_code=exc.code,
                    )
                )
                continue
            if result.status is ProviderFetchStatus.FIELD_MISSING:
                attempts.append(
                    ProviderAttempt(
                        provider_id=candidate.provider.provider_id,
                        status=ProviderAttemptStatus.FIELD_MISSING,
                    )
                )
                continue
            selected_status = (
                ProviderAttemptStatus.EMPTY_SELECTED
                if result.status is ProviderFetchStatus.EMPTY
                else ProviderAttemptStatus.SELECTED
            )
            attempts.append(
                ProviderAttempt(
                    provider_id=candidate.provider.provider_id,
                    status=selected_status,
                )
            )
            return ProviderResolution(
                canonical_field=request.canonical_field,
                selected_provider_id=candidate.provider.provider_id,
                result=result,
                attempts=tuple(attempts),
            )
        raise ProviderConnectorError(
            ProviderErrorCode.RESOLUTION_EXHAUSTED,
            f"all enabled providers failed or omitted {request.canonical_field}",
            details={"attempts": tuple(item.to_dict() for item in attempts)},
        )


__all__ = (
    "ProviderAttempt",
    "ProviderAttemptStatus",
    "ProviderResolution",
    "ProviderResolver",
)
