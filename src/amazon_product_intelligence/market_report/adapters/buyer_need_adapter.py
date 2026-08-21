"""Read-only Buyer Need V0.3/Buyer Need Map to Market Report adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    BuyerNeedReportItem,
    BuyerNeedReportSection,
    MarketReportValidationError,
    ProvenanceReference,
    ReportAvailability,
)


BUYER_NEED_INTENT_STABLE_VERSION = "buyer-need-intent-rules-v0.3"
BUYER_NEED_TAXONOMY_STABLE_VERSION = "buyer-need-taxonomy-v0.2"


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise MarketReportValidationError(f"{path} must be a mapping or serializable contract")
    return value


def _sequence(value: Any, path: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MarketReportValidationError(f"{path} must be an array")
    rows = tuple(_mapping(item, f"{path}[]") for item in value)
    return rows


def _reference(
    *, source_module: str, source_version: str, source_record_id: str, evidence_ids: tuple[str, ...]
) -> ProvenanceReference:
    material = {
        "source_module": source_module,
        "source_version": source_version,
        "source_record_id": source_record_id,
        "availability": ReportAvailability.AVAILABLE,
        "evidence_ids": tuple(sorted(set(evidence_ids))),
        "limitations": (),
    }
    return ProvenanceReference(
        reference_id=deterministic_id("market-report-provenance", material),
        **material,
    )


class BuyerNeedReportAdapter:
    """Convert without mutating or reclassifying the source Buyer Need output."""

    def __init__(
        self,
        *,
        intent_ruleset_version: str = BUYER_NEED_INTENT_STABLE_VERSION,
        taxonomy_version: str = BUYER_NEED_TAXONOMY_STABLE_VERSION,
    ) -> None:
        self.intent_ruleset_version = intent_ruleset_version
        self.taxonomy_version = taxonomy_version

    def adapt(
        self, source: Any
    ) -> tuple[BuyerNeedReportSection, tuple[ProvenanceReference, ...]]:
        payload = _mapping(source, "Buyer Need output")
        if "semantic_clusters" in payload:
            return self._from_v0_3_validation(payload)
        if "need_clusters" in payload:
            return self._from_buyer_need_map(payload)
        raise MarketReportValidationError(
            "Buyer Need output must contain semantic_clusters or need_clusters"
        )

    def _from_v0_3_validation(
        self, payload: Mapping[str, Any]
    ) -> tuple[BuyerNeedReportSection, tuple[ProvenanceReference, ...]]:
        source_id = str(payload.get("analysis_id") or "")
        if not source_id:
            raise MarketReportValidationError("V0.3 Buyer Need output requires analysis_id")
        clusters = _sequence(payload.get("semantic_clusters"), "semantic_clusters")
        decision = _mapping(payload.get("final_decision", {}), "final_decision")
        validation_status = str(decision.get("label") or "VALIDATION_STATUS_UNKNOWN")
        evidence_ids = tuple(
            sorted(
                {
                    str(value)
                    for cluster in clusters
                    for value in cluster.get("source_need_ids", ())
                    if str(value)
                }
            )
        )
        reference = _reference(
            source_module="buyer_need_analysis",
            source_version=self.intent_ruleset_version,
            source_record_id=source_id,
            evidence_ids=evidence_ids,
        )
        items = []
        for cluster in clusters:
            need_id = str(cluster.get("cluster_id") or "")
            need_label = str(cluster.get("cluster_label") or "")
            cluster_evidence = tuple(
                sorted({str(value) for value in cluster.get("source_need_ids", ()) if str(value)})
            )
            if not need_id or not need_label or not cluster_evidence:
                raise MarketReportValidationError("semantic cluster lacks identity, label, or evidence")
            raw_share = cluster.get("asin_coverage")
            share = float(raw_share) if raw_share is not None else None
            confidence = cluster.get("confidence", "UNKNOWN")
            if isinstance(confidence, Mapping):
                confidence = confidence.get("level", "UNKNOWN")
            item_validation_status = str(
                cluster.get("validation_status") or validation_status
            )
            limitations = ["ASIN_COVERAGE_IS_COHORT_RECURRENCE_NOT_DEMAND_SHARE"]
            if str(confidence) == "UNKNOWN":
                limitations.append("SOURCE_CLUSTER_CONFIDENCE_UNAVAILABLE")
            items.append(
                BuyerNeedReportItem(
                    need_id=need_id,
                    need_label=need_label,
                    share=share,
                    share_basis="ASIN_COVERAGE_SHARE",
                    availability=(
                        ReportAvailability.PARTIAL
                        if share is not None
                        else ReportAvailability.UNAVAILABLE
                    ),
                    confidence=str(confidence),
                    validation_status=item_validation_status,
                    evidence_count=int(cluster.get("need_count") or len(cluster_evidence)),
                    evidence_ids=cluster_evidence,
                    provenance_reference_ids=(reference.reference_id,),
                    limitations=tuple(limitations),
                )
            )
        section = BuyerNeedReportSection(
            source_record_id=source_id,
            intent_ruleset_version=self.intent_ruleset_version,
            taxonomy_version=self.taxonomy_version,
            validation_status=validation_status,
            needs=tuple(items),
            provenance_reference_ids=(reference.reference_id,),
            limitations=(
                "ASIN coverage is cohort recurrence, not Demand Share.",
                "Per-cluster confidence is unavailable in the V0.3 validation snapshot.",
            ),
        )
        return section, (reference,)

    def _from_buyer_need_map(
        self, payload: Mapping[str, Any]
    ) -> tuple[BuyerNeedReportSection, tuple[ProvenanceReference, ...]]:
        source_id = str(payload.get("map_id") or "")
        if not source_id:
            raise MarketReportValidationError("Buyer Need Map output requires map_id")
        clusters = _sequence(payload.get("need_clusters"), "need_clusters")
        metrics = _sequence(payload.get("demand_metrics", ()), "demand_metrics")
        by_cluster: dict[str, list[Mapping[str, Any]]] = {}
        for metric in metrics:
            by_cluster.setdefault(str(metric.get("cluster_id")), []).append(metric)
        evidence_ids = tuple(
            sorted(
                {
                    str(value)
                    for cluster in clusters
                    for value in cluster.get("evidence_reference_ids", ())
                    if str(value)
                }
                | {
                    str(value)
                    for metric in metrics
                    for value in metric.get("evidence_reference_ids", ())
                    if str(value)
                }
            )
        )
        reference = _reference(
            source_module="buyer_need_map",
            source_version=str(payload.get("ruleset_version") or "buyer-need-map-v0.1"),
            source_record_id=source_id,
            evidence_ids=evidence_ids,
        )
        items = []
        for cluster in clusters:
            cluster_id = str(cluster.get("cluster_id") or "")
            candidates = sorted(
                by_cluster.get(cluster_id, ()),
                key=lambda item: (
                    item.get("metric_type") != "SEARCH_DEMAND_SHARE",
                    item.get("metric_type") != "PRODUCT_COVERAGE_SHARE",
                    str(item.get("metric_type")),
                ),
            )
            selected = candidates[0] if candidates else {}
            metric_status = str(selected.get("status") or "UNKNOWN")
            share_value = selected.get("share")
            share = float(share_value) if share_value is not None else None
            availability = {
                "AVAILABLE": ReportAvailability.AVAILABLE,
                "PARTIAL": ReportAvailability.PARTIAL,
            }.get(metric_status, ReportAvailability.UNAVAILABLE)
            confidence = selected.get("confidence", {})
            if isinstance(confidence, Mapping):
                confidence = confidence.get("level", "UNKNOWN")
            cluster_evidence = tuple(
                sorted(
                    {
                        str(value)
                        for value in (
                            *cluster.get("evidence_reference_ids", ()),
                            *selected.get("evidence_reference_ids", ()),
                        )
                        if str(value)
                    }
                )
            )
            limitations = tuple(sorted(str(value) for value in selected.get("limitations", ()) if str(value)))
            if availability is ReportAvailability.UNAVAILABLE and not limitations:
                limitations = ("DEMAND_SHARE_UNAVAILABLE",)
            items.append(
                BuyerNeedReportItem(
                    need_id=cluster_id,
                    need_label=str(cluster.get("cluster_label") or ""),
                    share=share,
                    share_basis=str(selected.get("metric_type") or "UNKNOWN"),
                    availability=availability,
                    confidence=str(confidence),
                    validation_status=str(payload.get("validation_status") or "NOT_VALIDATED"),
                    evidence_count=int(cluster.get("evidence_count") or len(cluster_evidence)),
                    evidence_ids=cluster_evidence,
                    provenance_reference_ids=(reference.reference_id,),
                    limitations=limitations,
                )
            )
        section = BuyerNeedReportSection(
            source_record_id=source_id,
            intent_ruleset_version=self.intent_ruleset_version,
            taxonomy_version=self.taxonomy_version,
            validation_status=str(payload.get("validation_status") or "NOT_VALIDATED"),
            needs=tuple(items),
            provenance_reference_ids=(reference.reference_id,),
            limitations=tuple(sorted(str(value) for value in payload.get("limitations", ()) if str(value))),
        )
        return section, (reference,)


__all__ = (
    "BUYER_NEED_INTENT_STABLE_VERSION",
    "BUYER_NEED_TAXONOMY_STABLE_VERSION",
    "BuyerNeedReportAdapter",
)
