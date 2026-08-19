"""Explicit local loader for versioned scoring configuration artifacts."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from amazon_product_intelligence.contracts import ContractValidationError

from .config_validator import (
    BusinessScoringConfiguration,
    ConfigurationValidationError,
)


class ConfigurationLoadError(ValueError):
    """Raised when an explicit configuration artifact cannot be loaded."""


class ScoringConfigurationLoader:
    """Load one explicitly identified JSON configuration; no default/latest lookup."""

    def load(
        self,
        path: str | Path,
        *,
        configuration_id: str,
    ) -> BusinessScoringConfiguration:
        requested_id = _explicit_id(configuration_id)
        candidate = Path(path)
        if candidate.suffix.casefold() != ".json":
            raise ConfigurationLoadError(
                "V0.1 scoring configuration artifacts must use JSON"
            )
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfigurationLoadError(
                f"cannot load scoring configuration {candidate}"
            ) from exc
        return self.load_mapping(payload, configuration_id=requested_id)

    def load_mapping(
        self,
        payload: Mapping[str, Any],
        *,
        configuration_id: str,
    ) -> BusinessScoringConfiguration:
        requested_id = _explicit_id(configuration_id)
        if not isinstance(payload, Mapping):
            raise ConfigurationLoadError("scoring configuration must be an object")
        try:
            configuration = BusinessScoringConfiguration.from_dict(payload)
        except (ContractValidationError, ConfigurationValidationError) as exc:
            raise ConfigurationLoadError(f"invalid scoring configuration: {exc}") from exc
        if configuration.configuration_id != requested_id:
            raise ConfigurationLoadError(
                "loaded configuration_id does not match the explicitly requested ID"
            )
        return configuration


def _explicit_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationLoadError("configuration_id must be explicitly specified")
    if value.casefold() == "latest":
        raise ConfigurationLoadError("automatic latest configuration selection is prohibited")
    return value


ConfigurationLoader = ScoringConfigurationLoader


__all__ = (
    "ConfigurationLoadError",
    "ConfigurationLoader",
    "ScoringConfigurationLoader",
)
