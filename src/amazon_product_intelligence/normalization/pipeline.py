"""Provider-neutral orchestration for Canonical normalization and quality issues."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    BlockingScope,
    DataQualityIssue,
    NormalizationStatus,
    OriginStage,
    PresenceStatus,
    SemanticStatus,
    Severity,
    Unit,
    deterministic_id,
)
from amazon_product_intelligence.provider_capabilities import CapabilityStatus

from .models import (
    NormalizationContext,
    NormalizationInput,
    NormalizationIssueCode,
    NormalizationResult,
    NormalizationRuleApplication,
    json_value,
)
from .registry import IssueSpec, NormalizationRule, NormalizerRegistry, RuleOutcome
from .rules import build_default_registry


def _fingerprint(value: Any) -> str:
    payload = json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


class CanonicalNormalizationPipeline:
    """Normalize fields independently according to Canonical field semantics."""

    def __init__(self, registry: NormalizerRegistry) -> None:
        self.registry = registry

    @classmethod
    def with_defaults(cls) -> "CanonicalNormalizationPipeline":
        return cls(build_default_registry())

    def normalize(
        self,
        item: NormalizationInput,
        context: NormalizationContext,
    ) -> NormalizationResult:
        capability_result = self._capability_boundary(item, context)
        if capability_result is not None:
            return capability_result

        absence_result = self._absence_boundary(item, context)
        if absence_result is not None:
            return absence_result

        rule = self.registry.get(item.canonical_field)
        if rule is None:
            issue = IssueSpec(
                code=NormalizationIssueCode.UNSUPPORTED_FIELD,
                severity=Severity.WARNING,
                message="no V0.1 normalization rule is registered for this Canonical field",
                blocking=False,
            )
            return self._result(item, context, None, NormalizationStatus.NOT_ATTEMPTED, item.semantic_status, item.unit, (issue,), None)

        value = item.mapped_value if item.mapped_value is not None else item.raw_value
        try:
            outcome = rule.normalize(value, item.unit)
        except Exception as exc:  # defensive field-level isolation around extension rules
            outcome = RuleOutcome(
                normalized_value=None,
                normalization_status=NormalizationStatus.FAILED,
                semantic_status=SemanticStatus.INVALID,
                unit=item.unit,
                transformations=(),
                issues=(
                    IssueSpec(
                        code=NormalizationIssueCode.NORMALIZATION_FAILED,
                        severity=Severity.BLOCKING,
                        message=f"normalization rule failed safely: {type(exc).__name__}",
                    ),
                ),
            )

        semantic_status = self._conservative_semantic_status(item.semantic_status, outcome.semantic_status)
        application = self._application(item, context, rule, outcome)
        return self._result(
            item,
            context,
            outcome.normalized_value,
            outcome.normalization_status,
            semantic_status,
            outcome.unit,
            outcome.issues,
            application,
        )

    def normalize_many(
        self,
        items: Iterable[NormalizationInput],
        context: NormalizationContext,
    ) -> tuple[NormalizationResult, ...]:
        """Normalize in caller order; failures remain isolated to their field."""

        return tuple(self.normalize(item, context) for item in items)

    @staticmethod
    def _conservative_semantic_status(
        input_status: SemanticStatus,
        outcome_status: SemanticStatus,
    ) -> SemanticStatus:
        if outcome_status is SemanticStatus.INVALID or input_status is SemanticStatus.INVALID:
            return SemanticStatus.INVALID
        if input_status in {SemanticStatus.SEMANTICS_UNCONFIRMED, SemanticStatus.UNPARSED}:
            return input_status
        return outcome_status

    def _capability_boundary(
        self,
        item: NormalizationInput,
        context: NormalizationContext,
    ) -> NormalizationResult | None:
        if item.capability_status is CapabilityStatus.UNAVAILABLE:
            issue = IssueSpec(
                code=NormalizationIssueCode.CAPABILITY_UNAVAILABLE,
                severity=Severity.INFO,
                message="provider capability is explicitly unavailable; no value was synthesized",
                blocking=False,
            )
        elif item.capability_status is CapabilityStatus.UNKNOWN:
            issue = IssueSpec(
                code=NormalizationIssueCode.CAPABILITY_UNKNOWN,
                severity=Severity.INFO,
                message="provider capability remains unknown; no value was synthesized",
                blocking=False,
            )
        else:
            return None
        return self._result(
            item,
            context,
            None,
            NormalizationStatus.NOT_ATTEMPTED,
            item.semantic_status,
            item.unit,
            (issue,),
            None,
        )

    def _absence_boundary(
        self,
        item: NormalizationInput,
        context: NormalizationContext,
    ) -> NormalizationResult | None:
        specifications = {
            PresenceStatus.MISSING: IssueSpec(
                code=NormalizationIssueCode.MISSING_VALUE,
                severity=Severity.INFO,
                message="source field is missing; zero or false was not inferred",
                blocking=False,
            ),
            PresenceStatus.EXPLICIT_NULL: IssueSpec(
                code=NormalizationIssueCode.EXPLICIT_NULL_VALUE,
                severity=Severity.INFO,
                message="source explicitly returned null; no business value was inferred",
                blocking=False,
            ),
            PresenceStatus.UNKNOWN: IssueSpec(
                code=NormalizationIssueCode.UNKNOWN_VALUE,
                severity=Severity.WARNING,
                message="value is unknown; no business value was inferred",
                blocking=False,
            ),
            PresenceStatus.QUERY_RETURNED_EMPTY: IssueSpec(
                code=NormalizationIssueCode.EMPTY_VALUE,
                severity=Severity.INFO,
                message="query returned no records; zero demand or competition was not inferred",
                blocking=False,
            ),
        }
        if item.presence_status is PresenceStatus.NOT_APPLICABLE:
            return self._result(
                item,
                context,
                None,
                NormalizationStatus.NOT_APPLICABLE,
                item.semantic_status,
                item.unit,
                (),
                None,
            )
        issue = specifications.get(item.presence_status)
        if issue is None:
            return None
        return self._result(
            item,
            context,
            None,
            NormalizationStatus.NOT_ATTEMPTED,
            item.semantic_status,
            item.unit,
            (issue,),
            None,
        )

    @staticmethod
    def _application(
        item: NormalizationInput,
        context: NormalizationContext,
        rule: NormalizationRule,
        outcome: RuleOutcome,
    ) -> NormalizationRuleApplication:
        input_material = {
            "canonical_field": item.canonical_field,
            "raw_value": json_value(item.raw_value),
            "mapped_value": json_value(item.mapped_value),
            "unit": None if item.unit is None else item.unit.to_dict(),
        }
        output_material = {
            "canonical_field": item.canonical_field,
            "normalized_value": json_value(outcome.normalized_value),
            "unit": None if outcome.unit is None else outcome.unit.to_dict(),
            "status": outcome.normalization_status.value,
        }
        return NormalizationRuleApplication(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            normalization_version=context.normalization_version,
            normalization_run_id=context.normalization_run_id,
            normalized_at=context.normalized_at,
            input_evidence_reference=item.evidence_reference,
            input_fingerprint=_fingerprint(input_material),
            output_fingerprint=_fingerprint(output_material),
            transformations=outcome.transformations,
        )

    def _result(
        self,
        item: NormalizationInput,
        context: NormalizationContext,
        normalized_value: Any,
        status: NormalizationStatus,
        semantic_status: SemanticStatus,
        unit: Unit | None,
        issue_specs: tuple[IssueSpec, ...],
        application: NormalizationRuleApplication | None,
    ) -> NormalizationResult:
        issues = tuple(self._quality_issue(item, context, specification) for specification in issue_specs)
        return NormalizationResult(
            canonical_field=item.canonical_field,
            raw_value=item.raw_value,
            mapped_value=item.mapped_value,
            normalized_value=normalized_value,
            presence_status=item.presence_status,
            normalization_status=status,
            semantic_status=semantic_status,
            unit=unit,
            capability_status=item.capability_status,
            issues=issues,
            application=application,
            provenance=item.provenance,
        )

    @staticmethod
    def _quality_issue(
        item: NormalizationInput,
        context: NormalizationContext,
        specification: IssueSpec,
    ) -> DataQualityIssue:
        transform = item.provenance.transformation
        issue_id = deterministic_id(
            "dqi",
            {
                "stage": OriginStage.NORMALIZATION.value,
                "normalization_run_id": context.normalization_run_id,
                "normalization_version": context.normalization_version,
                "evidence_reference": item.evidence_reference,
                "field": item.canonical_field,
                "code": specification.code.value,
                "message": specification.message,
            },
        )
        return DataQualityIssue(
            issue_id=issue_id,
            issue_code=specification.code.value,
            severity=specification.severity,
            subject=item.subject,
            dimension=item.canonical_field,
            message=specification.message,
            blocking=specification.blocking,
            blocking_scope=BlockingScope.FIELD if specification.blocking else BlockingScope.NONE,
            source_references=(item.evidence_reference,),
            created_at=context.normalized_at,
            origin_stage=OriginStage.NORMALIZATION,
            collection_run_id=transform.collection_run_id,
            transformation_run_id=transform.transformation_run_id,
            mapping_version=transform.mapping_version,
        )


__all__ = ("CanonicalNormalizationPipeline",)
