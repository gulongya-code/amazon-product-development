"""Versioned Gap Type Registry and classification policy V0.1."""

from __future__ import annotations

from amazon_product_intelligence.contracts import deterministic_id

from .models import (
    GAP_CLASSIFICATION_POLICY_VERSION,
    GAP_TYPE_REGISTRY_VERSION,
    GapClassificationPolicy,
    GapSignalBand,
    GapType,
    GapTypeDefinition,
    GapTypeRegistry,
)


def _definition(
    gap_type: GapType,
    demand_band: GapSignalBand,
    supply_band: GapSignalBand,
    definition: str,
) -> GapTypeDefinition:
    payload = {
        "gap_type": gap_type,
        "demand_band": demand_band,
        "supply_band": supply_band,
        "definition": definition,
    }
    return GapTypeDefinition(
        definition_id=deterministic_id("gap-type-definition", payload),
        **payload,
    )


def build_gap_type_registry_v0_1() -> GapTypeRegistry:
    definitions = (
        _definition(
            GapType.HIGH_DEMAND_LOW_SUPPLY,
            GapSignalBand.HIGH,
            GapSignalBand.LOW,
            "At least one supported demand share is high while Product Coverage Share is low.",
        ),
        _definition(
            GapType.HIGH_DEMAND_HIGH_SUPPLY,
            GapSignalBand.HIGH,
            GapSignalBand.HIGH,
            "At least one supported demand share is high and Product Coverage Share is high.",
        ),
        _definition(
            GapType.LOW_DEMAND_LOW_SUPPLY,
            GapSignalBand.LOW,
            GapSignalBand.LOW,
            "All available supported demand shares are low and Product Coverage Share is low.",
        ),
        _definition(
            GapType.LOW_DEMAND_HIGH_SUPPLY,
            GapSignalBand.LOW,
            GapSignalBand.HIGH,
            "All available supported demand shares are low while Product Coverage Share is high.",
        ),
        _definition(
            GapType.INSUFFICIENT_EVIDENCE,
            GapSignalBand.UNKNOWN,
            GapSignalBand.UNKNOWN,
            "A required demand or Product Coverage signal is unavailable; UNKNOWN is not zero.",
        ),
    )
    ordered = tuple(sorted(definitions, key=lambda item: item.gap_type.value))
    payload = {
        "registry_version": GAP_TYPE_REGISTRY_VERSION,
        "definitions": ordered,
    }
    return GapTypeRegistry(
        registry_id=deterministic_id("gap-type-registry", payload),
        **payload,
    )


def build_gap_classification_policy_v0_1() -> GapClassificationPolicy:
    payload = {
        "policy_version": GAP_CLASSIFICATION_POLICY_VERSION,
        "high_demand_threshold": "0.2",
        "high_supply_threshold": "0.2",
        "medium_gap_margin": "0.05",
        "high_gap_margin": "0.15",
        "minimum_high_strength_demand_metric_coverage": "0.25",
        "minimum_high_strength_supply_metric_coverage": "0.5",
    }
    return GapClassificationPolicy(
        policy_id=deterministic_id("gap-classification-policy", payload),
        **payload,
    )


GAP_TYPE_REGISTRY_V0_1 = build_gap_type_registry_v0_1()
GAP_CLASSIFICATION_POLICY_V0_1 = build_gap_classification_policy_v0_1()


__all__ = (
    "GAP_CLASSIFICATION_POLICY_V0_1",
    "GAP_TYPE_REGISTRY_V0_1",
    "build_gap_classification_policy_v0_1",
    "build_gap_type_registry_v0_1",
)
