"""Stable public API for Supply/Demand Gap Analysis V0.1."""

from .builder_v0_1 import SupplyDemandGapBuilderV0_1
from .classifier import GapClassifier
from .errors import (
    SupplyDemandGapError,
    SupplyDemandGapSerializationError,
    SupplyDemandGapValidationError,
)
from .models import (
    GAP_CLASSIFICATION_POLICY_VERSION,
    GAP_TYPE_REGISTRY_VERSION,
    SUPPLY_DEMAND_GAP_RULESET_VERSION,
    GapClassificationPolicy,
    GapConfidence,
    GapConfidenceLevel,
    GapDiagnostic,
    GapEvidence,
    GapMetricConfidence,
    GapSignalBand,
    GapSignalStatus,
    GapStrength,
    GapSupplyMetric,
    GapType,
    GapTypeDefinition,
    GapTypeRegistry,
    SupplyDemandGapRequest,
    SupplyDemandGapSnapshot,
    SupplyMetricType,
)
from .registry import (
    GAP_CLASSIFICATION_POLICY_V0_1,
    GAP_TYPE_REGISTRY_V0_1,
    build_gap_classification_policy_v0_1,
    build_gap_type_registry_v0_1,
)


__all__ = (
    "GAP_CLASSIFICATION_POLICY_V0_1",
    "GAP_CLASSIFICATION_POLICY_VERSION",
    "GAP_TYPE_REGISTRY_V0_1",
    "GAP_TYPE_REGISTRY_VERSION",
    "SUPPLY_DEMAND_GAP_RULESET_VERSION",
    "GapClassificationPolicy",
    "GapClassifier",
    "GapConfidence",
    "GapConfidenceLevel",
    "GapDiagnostic",
    "GapEvidence",
    "GapMetricConfidence",
    "GapSignalBand",
    "GapSignalStatus",
    "GapStrength",
    "GapSupplyMetric",
    "GapType",
    "GapTypeDefinition",
    "GapTypeRegistry",
    "SupplyDemandGapBuilderV0_1",
    "SupplyDemandGapError",
    "SupplyDemandGapRequest",
    "SupplyDemandGapSerializationError",
    "SupplyDemandGapSnapshot",
    "SupplyDemandGapValidationError",
    "SupplyMetricType",
    "build_gap_classification_policy_v0_1",
    "build_gap_type_registry_v0_1",
)
