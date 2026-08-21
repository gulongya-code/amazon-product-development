"""Read-only EvidenceBasedOpportunityScore to Market Report adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    MarketReportValidationError,
    OpportunityDimensionReport,
    OpportunityReportSection,
    ProvenanceReference,
    ReportAvailability,
)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise MarketReportValidationError(f"{path} must be a mapping or serializable contract")
    return value


def _rows(value: Any, path: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MarketReportValidationError(f"{path} must be an array")
    return tuple(_mapping(item, f"{path}[]") for item in value)


def _reference(
    *,
    module: str,
    version: str,
    record_id: str,
    evidence_ids: tuple[str, ...],
    availability: ReportAvailability,
    limitations: tuple[str, ...],
) -> ProvenanceReference:
    material = {
        "source_module": module,
        "source_version": version,
        "source_record_id": record_id,
        "availability": availability,
        "evidence_ids": tuple(sorted(set(evidence_ids))),
        "limitations": tuple(sorted(set(limitations))),
    }
    return ProvenanceReference(
        reference_id=deterministic_id("market-report-provenance", material),
        **material,
    )


class OpportunityReportAdapter:
    """Copy score/explanation fields; never calculate or adjust a score."""

    def adapt(
        self, source: Any
    ) -> tuple[OpportunityReportSection, tuple[ProvenanceReference, ...]]:
        payload = _mapping(source, "Opportunity Score output")
        explanation = _mapping(payload.get("explanation"), "score explanation")
        score_id = str(payload.get("score_id") or "")
        integration_version = str(
            payload.get("integration_version")
            or "opportunity-scoring-integration-v0.1"
        )
        if not score_id:
            raise MarketReportValidationError("Opportunity Score output requires score_id")
        source_refs = _rows(
            explanation.get("evidence_references"), "score evidence_references"
        )
        dimension_rows = _rows(
            explanation.get("dimension_breakdown"), "score dimension_breakdown"
        )
        report_refs = []
        all_evidence: set[str] = set()
        for item in source_refs:
            record_ids = tuple(
                sorted(
                    str(value)
                    for value in item.get("record_ids", ())
                    if str(value)
                )
            )
            original_id = str(item.get("reference_id") or item.get("source_id") or "")
            limitations = tuple(
                sorted(
                    str(value)
                    for value in item.get("limitations", ())
                    if str(value)
                )
            )
            missing = bool(item.get("missing", False))
            evidence = tuple(
                sorted({*record_ids, *(value for value in (original_id,) if value)})
            )
            all_evidence.update(evidence)
            report_refs.append(
                _reference(
                    module=str(item.get("source") or "opportunity_score_evidence"),
                    version=integration_version,
                    record_id=str(item.get("source_id") or original_id or score_id),
                    evidence_ids=evidence,
                    availability=(
                        ReportAvailability.UNAVAILABLE
                        if missing
                        else ReportAvailability.AVAILABLE
                    ),
                    limitations=(
                        limitations
                        or (("SOURCE_EVIDENCE_MISSING",) if missing else ())
                    ),
                )
            )
        for item in dimension_rows:
            dimension_evidence = tuple(
                sorted(
                    str(value)
                    for value in item.get("source_evidence_ids", ())
                    if str(value)
                )
            ) or (str(item.get("dimension_score_id") or score_id),)
            all_evidence.update(dimension_evidence)
        root = _reference(
            module="opportunity_scoring",
            version=integration_version,
            record_id=score_id,
            evidence_ids=tuple(sorted(all_evidence)) or (score_id,),
            availability=(
                ReportAvailability.PARTIAL
                if str(payload.get("score_status")) == "CALCULATED_PARTIAL"
                else ReportAvailability.AVAILABLE
            ),
            limitations=tuple(
                sorted(
                    str(value)
                    for value in explanation.get("limitations", ())
                    if str(value)
                )
            ),
        )
        report_refs.append(root)
        ref_ids = tuple(sorted(item.reference_id for item in report_refs))
        dimensions = []
        for item in dimension_rows:
            evidence_ids = tuple(
                sorted(
                    str(value)
                    for value in item.get("source_evidence_ids", ())
                    if str(value)
                )
            ) or (str(item.get("dimension_score_id") or score_id),)
            dimensions.append(
                OpportunityDimensionReport(
                    dimension=str(item.get("dimension") or ""),
                    status=str(item.get("status") or "UNKNOWN"),
                    score_value=item.get("score_value"),
                    contribution=item.get("contribution"),
                    max_contribution=item.get("max_contribution"),
                    evidence_ids=evidence_ids,
                    provenance_reference_ids=(root.reference_id,),
                    explanation=str(
                        item.get("explanation") or "No source explanation supplied."
                    ),
                )
            )
        section = OpportunityReportSection(
            score_id=score_id,
            candidate_id=str(payload.get("candidate_id") or ""),
            score_status=str(payload.get("score_status") or ""),
            score_value=payload.get("score_value"),
            confidence=str(payload.get("confidence") or "UNKNOWN"),
            policy_version=str(payload.get("policy_version") or ""),
            policy_fingerprint=str(payload.get("policy_fingerprint") or ""),
            dimensions=tuple(dimensions),
            risks=tuple(
                sorted(
                    str(value)
                    for value in explanation.get("risks", ())
                    if str(value)
                )
            ),
            limitations=tuple(
                sorted(
                    str(value)
                    for value in explanation.get("limitations", ())
                    if str(value)
                )
            ),
            evidence_ids=tuple(sorted(all_evidence)) or (score_id,),
            provenance_reference_ids=ref_ids,
        )
        return section, tuple(sorted(report_refs, key=lambda item: item.reference_id))


__all__ = ("OpportunityReportAdapter",)
