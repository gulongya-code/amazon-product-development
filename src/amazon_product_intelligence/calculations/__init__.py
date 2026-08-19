"""Provider-neutral calculated-field specification and engine foundation."""

from . import errors as _errors
from . import models as _models
from .audit_v0_1 import (
    AUDITED_CALCULATED_FIELDS,
    CALCULATED_FIELD_SPECS,
    D2A_DEFERRED_FIELD_IDS,
    D2A_IMPLEMENTED_FIELD_IDS,
    D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS,
    D2C_IMPLEMENTED_FIELD_IDS,
    D2_CURRENT_DEFERRED_FIELD_IDS,
    D2_IMPLEMENTED_FIELD_IDS,
    D2_READY_FIELD_IDS,
    build_audited_registry,
)
from .engine import CalculationEngine
from .errors import *  # noqa: F403
from .functions import (
    COUNT_UNIT,
    RATIO_UNIT,
    calculate_observed_share,
    count_unique_canonical_identifiers,
    decimal_value,
    project_member_product_ids,
    require_compatible_currencies,
    require_compatible_units,
    safe_decimal_ratio,
)
from .models import *  # noqa: F403
from .registry import CalculatedFieldRegistry, CalculationFunction


__all__ = (
    "AUDITED_CALCULATED_FIELDS",
    "CALCULATED_FIELD_SPECS",
    "COUNT_UNIT",
    "RATIO_UNIT",
    "D2A_DEFERRED_FIELD_IDS",
    "D2A_IMPLEMENTED_FIELD_IDS",
    "D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS",
    "D2C_IMPLEMENTED_FIELD_IDS",
    "D2_CURRENT_DEFERRED_FIELD_IDS",
    "D2_IMPLEMENTED_FIELD_IDS",
    "D2_READY_FIELD_IDS",
    "CalculatedFieldRegistry",
    "CalculationEngine",
    "CalculationFunction",
    "build_audited_registry",
    "calculate_observed_share",
    "count_unique_canonical_identifiers",
    "decimal_value",
    "project_member_product_ids",
    "require_compatible_currencies",
    "require_compatible_units",
    "safe_decimal_ratio",
) + _errors.__all__ + _models.__all__
