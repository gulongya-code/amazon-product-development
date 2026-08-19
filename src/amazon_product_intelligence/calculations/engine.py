"""Provider-neutral partial-execution Calculation Engine Foundation V0.1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Any

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
    deterministic_id,
)

from .errors import (
    CalculationCurrencyMismatchError,
    CalculationDivisionByZeroError,
    CalculationEvaluationError,
    CalculationUnitMismatchError,
    InvalidCalculationInputError,
)
from .models import (
    CalculatedFieldSpec,
    CalculationBatchResult,
    CalculationContext,
    CalculationEvaluationContext,
    CalculationInput,
    CalculationInputLineage,
    CalculationIssue,
    CalculationOutcome,
    CalculationPlan,
    CalculationProvenance,
    CalculationResult,
    CalculationStatus,
    DependencyType,
    FormulaStatus,
    InputResolutionStatus,
    MissingPolicy,
    json_value,
)
from .registry import CalculatedFieldRegistry


_SUCCESS = {CalculationStatus.CALCULATED, CalculationStatus.PARTIAL}


def _fingerprint(value: Any) -> str:
    payload = json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


class CalculationEngine:
    """Plan and execute only explicitly registered deterministic formulas."""

    def __init__(self, registry: CalculatedFieldRegistry) -> None:
        if not isinstance(registry, CalculatedFieldRegistry):
            raise TypeError("registry must be CalculatedFieldRegistry")
        registry.validate()
        self.registry = registry

    def plan(self, requested_fields: Sequence[str]) -> CalculationPlan:
        order = self.registry.execution_order(requested_fields)
        external: set[str] = set()
        blocked: dict[str, tuple[str, ...]] = {}
        for field_id in order:
            spec = self.registry.get(field_id)
            external.update(
                dependency.field_id
                for dependency in spec.dependencies
                if dependency.dependency_type is not DependencyType.CALCULATED_FIELD
            )
            reasons: list[str] = []
            if spec.formula_status is not FormulaStatus.DEFINED:
                reasons.append(f"FORMULA_STATUS_{spec.formula_status.value}")
            if self.registry.function(field_id) is None:
                reasons.append("EVALUATOR_NOT_REGISTERED")
            blocked_dependencies = tuple(
                dependency.field_id
                for dependency in spec.dependencies
                if dependency.dependency_type is DependencyType.CALCULATED_FIELD
                and dependency.field_id in blocked
            )
            reasons.extend(f"DEPENDENCY_BLOCKED:{item}" for item in blocked_dependencies)
            if reasons:
                blocked[field_id] = tuple(reasons)
        return CalculationPlan(
            requested_fields=tuple(requested_fields),
            execution_order=order,
            external_dependencies=tuple(external),
            blocked_fields=blocked,
        )

    def calculate(
        self,
        requested_fields: Sequence[str],
        inputs: Mapping[str, CalculationInput],
        context: CalculationContext,
    ) -> CalculationBatchResult:
        if not isinstance(context, CalculationContext):
            raise TypeError("context must be CalculationContext")
        if not isinstance(inputs, Mapping):
            raise TypeError("inputs must be a mapping")
        if any(not isinstance(value, CalculationInput) for value in inputs.values()):
            raise InvalidCalculationInputError(
                "calculation input mapping values must be CalculationInput"
            )
        if any(key != value.field_id for key, value in inputs.items()):
            raise InvalidCalculationInputError(
                "calculation input mapping keys must equal input field IDs"
            )
        plan = self.plan(requested_fields)
        results: dict[str, CalculationResult] = {}
        for field_id in plan.execution_order:
            results[field_id] = self._calculate_one(
                self.registry.get(field_id), inputs, results, context
            )
        return CalculationBatchResult(
            plan=plan,
            results=tuple(results[field_id] for field_id in plan.execution_order),
        )

    def _calculate_one(
        self,
        spec: CalculatedFieldSpec,
        inputs: Mapping[str, CalculationInput],
        prior_results: Mapping[str, CalculationResult],
        context: CalculationContext,
    ) -> CalculationResult:
        function = self.registry.function(spec.field_id)
        if spec.formula_status is not FormulaStatus.DEFINED or function is None:
            return self._blocked_result(
                spec,
                CalculationStatus.FORMULA_UNDEFINED,
                "FORMULA_NOT_DEFINED",
                "field has no approved executable formula",
            )

        values: dict[str, Any] = {}
        units: dict[str, Any] = {}
        used_inputs: list[CalculationInput] = []
        calculated_results: list[CalculationResult] = []
        missing: list[tuple[str, CalculationStatus, str]] = []

        for dependency in spec.dependencies:
            if dependency.dependency_type is DependencyType.CALCULATED_FIELD:
                result = prior_results[dependency.field_id]
                if result.status not in _SUCCESS:
                    return self._blocked_result(
                        spec,
                        CalculationStatus.DEPENDENCY_BLOCKED,
                        "CALCULATED_DEPENDENCY_BLOCKED",
                        "calculated dependency did not produce a usable value",
                        dependency.field_id,
                    )
                values[dependency.field_id] = result.value
                units[dependency.field_id] = result.unit
                calculated_results.append(result)
                continue

            item = inputs.get(dependency.field_id)
            if item is None:
                missing.append((dependency.field_id, CalculationStatus.MISSING_INPUT, "dependency input is absent"))
                continue
            unsafe = self._unsafe_input(item)
            if unsafe is not None:
                status, message = unsafe
                missing.append((dependency.field_id, status, message))
                continue
            values[dependency.field_id] = item.value
            units[dependency.field_id] = item.unit
            used_inputs.append(item)

        partial = False
        if missing:
            if spec.missing_policy in {MissingPolicy.ALLOW_PARTIAL, MissingPolicy.IGNORE_MISSING} and values:
                partial = True
            else:
                dependency_id, status, message = self._highest_priority_missing(missing)
                return self._blocked_result(spec, status, status.value, message, dependency_id)

        evaluation = CalculationEvaluationContext(spec=spec, values=values, units=units)
        try:
            outcome = function(evaluation)
            if not isinstance(outcome, CalculationOutcome):
                raise CalculationEvaluationError("calculation function returned wrong contract")
        except CalculationDivisionByZeroError:
            return self._blocked_result(
                spec, CalculationStatus.DIVISION_BY_ZERO, "DIVISION_BY_ZERO", "ratio denominator is zero"
            )
        except CalculationCurrencyMismatchError:
            return self._blocked_result(
                spec, CalculationStatus.CURRENCY_MISMATCH, "CURRENCY_MISMATCH", "monetary input currencies are incompatible"
            )
        except CalculationUnitMismatchError:
            return self._blocked_result(
                spec, CalculationStatus.UNIT_MISMATCH, "UNIT_MISMATCH", "input units are incompatible"
            )
        except CalculationEvaluationError as exc:
            return self._blocked_result(
                spec, CalculationStatus.FAILED, "CALCULATION_FAILED", str(exc)
            )
        except Exception as exc:  # extension boundary: isolate one field without leaking input data
            return self._blocked_result(
                spec,
                CalculationStatus.FAILED,
                "CALCULATION_FAILED",
                f"calculation failed safely: {type(exc).__name__}",
            )

        status = CalculationStatus.PARTIAL if partial else outcome.status
        input_material = {
            "field_id": spec.field_id,
            "inputs": [item.to_dict() for item in sorted(used_inputs, key=lambda value: value.field_id)],
            "calculated_dependencies": [item.to_dict() for item in calculated_results],
            "configuration_version": context.configuration_version,
        }
        output_material = {
            "field_id": spec.field_id,
            "value": json_value(outcome.value),
            "unit": None if outcome.unit is None else outcome.unit.to_dict(),
            "status": status.value,
            "rule": spec.calculation_rule_id,
            "version": spec.calculation_version,
        }
        provenance = CalculationProvenance(
            calculation_rule_id=spec.calculation_rule_id or "calculation.unspecified",
            calculation_version=spec.calculation_version,
            calculation_run_id=context.calculation_run_id,
            configuration_version=context.configuration_version,
            input_lineage=tuple(self._input_lineage(item) for item in used_inputs),
            calculated_dependency_result_ids=tuple(item.result_id for item in calculated_results),
            input_fingerprint=_fingerprint(input_material),
            output_fingerprint=_fingerprint(output_material),
        )
        content = {
            "field_id": spec.field_id,
            "value": json_value(outcome.value),
            "status": status.value,
            "unit": None if outcome.unit is None else outcome.unit.to_dict(),
            "input_fields": sorted(values),
            "issues": [item.to_dict() for item in outcome.issues],
            "calculation_rule_id": spec.calculation_rule_id,
            "calculation_version": spec.calculation_version,
            "provenance": provenance.to_dict(),
        }
        return CalculationResult(
            result_id=deterministic_id("calculation-result", content),
            field_id=spec.field_id,
            value=outcome.value,
            status=status,
            unit=outcome.unit,
            input_fields=tuple(values),
            issues=outcome.issues,
            calculation_rule_id=spec.calculation_rule_id,
            calculation_version=spec.calculation_version,
            provenance=provenance,
        )

    @staticmethod
    def _unsafe_input(item: CalculationInput) -> tuple[CalculationStatus, str] | None:
        if item.resolution_status is InputResolutionStatus.UNRESOLVED:
            return CalculationStatus.DEPENDENCY_BLOCKED, "canonical input is unresolved"
        if any(issue.blocking for issue in item.quality_issues):
            return CalculationStatus.INVALID_INPUT, "input has a blocking Canonical quality issue"
        if item.normalization_status not in {
            NormalizationStatus.NORMALIZED,
            NormalizationStatus.NOT_APPLICABLE,
        } or item.semantic_status is not SemanticStatus.CONFIRMED:
            return CalculationStatus.INVALID_INPUT, "input is not cleanly normalized with confirmed semantics"
        if item.presence_status is PresenceStatus.NOT_APPLICABLE:
            return CalculationStatus.NOT_APPLICABLE, "input is not applicable"
        if item.presence_status is PresenceStatus.UNKNOWN:
            return CalculationStatus.UNKNOWN_INPUT, "input value is unknown"
        if item.presence_status in {
            PresenceStatus.MISSING,
            PresenceStatus.EXPLICIT_NULL,
            PresenceStatus.QUERY_RETURNED_EMPTY,
        }:
            return CalculationStatus.MISSING_INPUT, "input has no business value"
        return None

    @staticmethod
    def _highest_priority_missing(
        values: list[tuple[str, CalculationStatus, str]],
    ) -> tuple[str, CalculationStatus, str]:
        priority = {
            CalculationStatus.INVALID_INPUT: 0,
            CalculationStatus.DEPENDENCY_BLOCKED: 1,
            CalculationStatus.UNKNOWN_INPUT: 2,
            CalculationStatus.NOT_APPLICABLE: 3,
            CalculationStatus.MISSING_INPUT: 4,
        }
        return min(values, key=lambda item: (priority[item[1]], item[0]))

    @staticmethod
    def _input_lineage(item: CalculationInput) -> CalculationInputLineage:
        return CalculationInputLineage(
            field_id=item.field_id,
            normalized_value=item.value,
            presence_status=item.presence_status,
            normalization_status=item.normalization_status,
            semantic_status=item.semantic_status,
            resolution_status=item.resolution_status,
            unit=item.unit,
            evidence_references=item.evidence_references,
            provenances=item.provenances,
            quality_issue_ids=tuple(issue.issue_id for issue in item.quality_issues),
            input_fingerprint=_fingerprint(item.to_dict()),
        )

    @staticmethod
    def _blocked_result(
        spec: CalculatedFieldSpec,
        status: CalculationStatus,
        code: str,
        message: str,
        dependency_field: str | None = None,
    ) -> CalculationResult:
        issue = CalculationIssue(code=code, message=message, dependency_field=dependency_field)
        content = {
            "field_id": spec.field_id,
            "value": None,
            "status": status.value,
            "unit": None,
            "input_fields": [] if dependency_field is None else [dependency_field],
            "issues": [issue.to_dict()],
            "calculation_rule_id": spec.calculation_rule_id,
            "calculation_version": spec.calculation_version,
            "provenance": None,
        }
        return CalculationResult(
            result_id=deterministic_id("calculation-result", content),
            field_id=spec.field_id,
            value=None,
            status=status,
            unit=None,
            input_fields=() if dependency_field is None else (dependency_field,),
            issues=(issue,),
            calculation_rule_id=spec.calculation_rule_id,
            calculation_version=spec.calculation_version,
            provenance=None,
        )


__all__ = ("CalculationEngine",)
