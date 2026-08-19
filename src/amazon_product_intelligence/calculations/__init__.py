"""Provider-neutral calculated-field specification and engine foundation."""

from . import errors as _errors
from . import models as _models
from .audit_v0_1 import (
    AUDITED_CALCULATED_FIELDS,
    CALCULATED_FIELD_SPECS,
    D2_READY_FIELD_IDS,
    build_audited_registry,
)
from .engine import CalculationEngine
from .errors import *  # noqa: F403
from .functions import (
    decimal_value,
    require_compatible_currencies,
    require_compatible_units,
    safe_decimal_ratio,
)
from .models import *  # noqa: F403
from .registry import CalculatedFieldRegistry, CalculationFunction


__all__ = (
    "AUDITED_CALCULATED_FIELDS",
    "CALCULATED_FIELD_SPECS",
    "D2_READY_FIELD_IDS",
    "CalculatedFieldRegistry",
    "CalculationEngine",
    "CalculationFunction",
    "build_audited_registry",
    "decimal_value",
    "require_compatible_currencies",
    "require_compatible_units",
    "safe_decimal_ratio",
) + _errors.__all__ + _models.__all__
