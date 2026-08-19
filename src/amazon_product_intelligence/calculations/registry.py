"""Calculated-field registry and deterministic dependency graph."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .errors import (
    CalculationDependencyCycleError,
    DuplicateCalculatedFieldError,
    UnknownCalculatedFieldError,
    UnknownCalculationDependencyError,
)
from .models import (
    CalculatedFieldSpec,
    CalculationEvaluationContext,
    CalculationOutcome,
    DependencyType,
)


CalculationFunction = Callable[[CalculationEvaluationContext], CalculationOutcome]


class CalculatedFieldRegistry:
    """Specification/evaluator registry with explicit graph validation."""

    def __init__(self) -> None:
        self._specifications: dict[str, CalculatedFieldSpec] = {}
        self._functions: dict[str, CalculationFunction] = {}

    def register(
        self,
        specification: CalculatedFieldSpec,
        function: CalculationFunction | None = None,
    ) -> None:
        if not isinstance(specification, CalculatedFieldSpec):
            raise TypeError("specification must be CalculatedFieldSpec")
        if specification.field_id in self._specifications:
            raise DuplicateCalculatedFieldError(
                f"calculated field already registered: {specification.field_id}"
            )
        if function is not None and not callable(function):
            raise TypeError("calculation function must be callable")
        self._specifications[specification.field_id] = specification
        if function is not None:
            self._functions[specification.field_id] = function

    def get(self, field_id: str) -> CalculatedFieldSpec:
        try:
            return self._specifications[field_id]
        except KeyError as exc:
            raise UnknownCalculatedFieldError(
                f"calculated field is not registered: {field_id}"
            ) from exc

    def function(self, field_id: str) -> CalculationFunction | None:
        self.get(field_id)
        return self._functions.get(field_id)

    def dependencies(self, field_id: str) -> tuple[str, ...]:
        return tuple(item.field_id for item in self.get(field_id).dependencies)

    @property
    def specifications(self) -> tuple[CalculatedFieldSpec, ...]:
        return tuple(self._specifications[key] for key in sorted(self._specifications))

    @property
    def field_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._specifications))

    @property
    def executable_field_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._functions))

    def validate(self) -> None:
        self.execution_order(self.field_ids)

    def execution_order(self, requested_fields: Iterable[str]) -> tuple[str, ...]:
        requested = tuple(sorted(set(requested_fields)))
        for field_id in requested:
            self.get(field_id)

        state: dict[str, int] = {}
        stack: list[str] = []
        ordered: list[str] = []

        def visit(field_id: str) -> None:
            marker = state.get(field_id, 0)
            if marker == 2:
                return
            if marker == 1:
                start = stack.index(field_id)
                cycle = stack[start:] + [field_id]
                raise CalculationDependencyCycleError(
                    "calculation dependency cycle: " + " -> ".join(cycle)
                )
            state[field_id] = 1
            stack.append(field_id)
            calculated_dependencies = sorted(
                dependency.field_id
                for dependency in self.get(field_id).dependencies
                if dependency.dependency_type is DependencyType.CALCULATED_FIELD
            )
            for dependency_id in calculated_dependencies:
                if dependency_id not in self._specifications:
                    raise UnknownCalculationDependencyError(
                        f"{field_id} references unknown calculated dependency {dependency_id}"
                    )
                visit(dependency_id)
            stack.pop()
            state[field_id] = 2
            ordered.append(field_id)

        for field_id in requested:
            visit(field_id)
        return tuple(ordered)


__all__ = ("CalculatedFieldRegistry", "CalculationFunction")
