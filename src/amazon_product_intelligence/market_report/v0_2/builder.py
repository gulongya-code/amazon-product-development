"""Bounded composer for already validated Market Report V0.2 sections."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from hashlib import sha256
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json

from .models import ContractReference, MarketReportV0_2ValidationError
from .models.evidence_registry import EvidenceRecord, ReportProvenanceRecord, build_evidence_registry
from .models.report_context import ReportMetadataV0_2
from .models.report_snapshot import MarketReportSnapshotV0_2, report_id_for
from .version import MARKET_REPORT_V0_2_VERSION, REPORT_CONTEXT_CONTRACT_VERSION, REPORT_SNAPSHOT_CONTRACT_VERSION


def _collect_references(value: Any) -> tuple[ContractReference, ...]:
    collected: dict[str, ContractReference] = {}
    def visit(item: Any) -> None:
        if isinstance(item, ContractReference):
            prior = collected.get(item.reference_id)
            if prior is not None and prior != item:
                raise MarketReportV0_2ValidationError("conflicting ContractReference identity")
            collected[item.reference_id] = item
            return
        if is_dataclass(item):
            for field in fields(item):
                visit(getattr(item, field.name))
        elif isinstance(item, (tuple, list)):
            for child in item:
                visit(child)
    visit(value)
    return tuple(sorted(collected.values(), key=lambda item: item.reference_id))


def compose_market_report_v0_2(
    *,
    generated_at: str,
    producer_version: str,
    operational_metadata: Mapping[str, Any],
    category: Any,
    sample: Any,
    data_window: Any,
    scope_context: Any,
    market_size: Any,
    true_competitor_set: Any,
    competitor_structure: Any,
    distributions: tuple[Any, ...],
    competitor_details: tuple[Any, ...],
    buyer_needs: Any,
    buyer_need_links: Any,
    product_directions: Any,
    competitor_shortlist: Any,
    opportunity_score: Any,
    executive_summary: Any,
    sanitized_appendix: Any,
    external_integrations: Any,
    provenance: tuple[ReportProvenanceRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
    references: tuple[ContractReference, ...] = (),
    evidence_registry_limitations: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> MarketReportSnapshotV0_2:
    sections = (
        category, sample, data_window, scope_context, market_size, true_competitor_set,
        competitor_structure, distributions, competitor_details, buyer_needs, buyer_need_links,
        product_directions, competitor_shortlist, opportunity_score, executive_summary,
        sanitized_appendix, external_integrations,
    )
    combined: dict[str, ContractReference] = {}
    for item in references:
        prior = combined.get(item.reference_id)
        if prior is not None and prior != item:
            raise MarketReportV0_2ValidationError("conflicting explicit reference identity")
        combined[item.reference_id] = item
    for item in _collect_references(sections):
        prior = combined.get(item.reference_id)
        if prior is not None and prior != item:
            raise MarketReportV0_2ValidationError("conflicting global reference identity")
        combined[item.reference_id] = item
    evidence_registry = build_evidence_registry(
        references=tuple(combined.values()),
        evidence=evidence,
        limitations=evidence_registry_limitations,
    )
    placeholder = "sha256:" + "0" * 64
    metadata = ReportMetadataV0_2(
        report_id=report_id_for(semantic_fingerprint=placeholder, generated_at=generated_at),
        report_version=MARKET_REPORT_V0_2_VERSION,
        contract_version=REPORT_CONTEXT_CONTRACT_VERSION,
        semantic_fingerprint=placeholder,
        generated_at=generated_at,
        producer_version=producer_version,
        operational_metadata=operational_metadata,
    )
    kwargs = dict(
        contract_version=REPORT_SNAPSHOT_CONTRACT_VERSION, metadata=metadata, category=category, sample=sample,
        data_window=data_window, scope_context=scope_context, market_size=market_size,
        true_competitor_set=true_competitor_set, competitor_structure=competitor_structure,
        distributions=tuple(sorted(distributions, key=lambda item: item.distribution_id)),
        competitor_details=tuple(sorted(competitor_details, key=lambda item: item.section_id)), buyer_needs=buyer_needs,
        buyer_need_links=buyer_need_links, product_directions=product_directions,
        competitor_shortlist=competitor_shortlist, opportunity_score=opportunity_score,
        executive_summary=executive_summary, evidence_registry=evidence_registry,
        sanitized_appendix=sanitized_appendix, external_integrations=external_integrations,
        provenance=tuple(sorted(provenance, key=lambda item: item.provenance_id)), limitations=tuple(sorted(set(limitations))),
    )
    material = MarketReportSnapshotV0_2.__new__(MarketReportSnapshotV0_2)
    for name, value in kwargs.items():
        object.__setattr__(material, name, value)
    payload = material.to_dict()
    payload["metadata"] = {
        "report_version": MARKET_REPORT_V0_2_VERSION,
        "contract_version": REPORT_CONTEXT_CONTRACT_VERSION,
        "producer_version": producer_version,
    }
    payload["data_window"].pop("retrieved_at", None)
    fingerprint = "sha256:" + sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    kwargs["metadata"] = ReportMetadataV0_2(
        report_id=report_id_for(semantic_fingerprint=fingerprint, generated_at=generated_at),
        report_version=MARKET_REPORT_V0_2_VERSION,
        contract_version=REPORT_CONTEXT_CONTRACT_VERSION,
        semantic_fingerprint=fingerprint,
        generated_at=generated_at,
        producer_version=producer_version,
        operational_metadata=operational_metadata,
    )
    return MarketReportSnapshotV0_2(**kwargs)


__all__ = ("compose_market_report_v0_2",)
