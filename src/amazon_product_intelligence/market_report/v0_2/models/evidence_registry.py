"""Report-level evidence, provenance, and reference registry contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import EVIDENCE_REGISTRY_CONTRACT_VERSION
from .common import (
    Availability,
    ContractReference,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    identity,
    normalize_references,
    optional_text,
    text,
    texts,
)


ALLOWED_EXTERNAL_NAMESPACES = frozenset(
    {
        "buyer-need", "canonical", "canonical-product", "category-product-map",
        "competition", "data-window", "distribution-denominator", "opportunity", "policy", "product-intelligence",
        "sanitized-evidence", "true-competitor",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportProvenanceRecord(V0_2Contract):
    provenance_id: str
    source_namespace: str
    source_version: str
    source_record_id: str
    availability: Availability
    content_fingerprint: str | None
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.provenance_id, "ReportProvenanceRecord.provenance_id")
        for name in ("source_namespace", "source_version", "source_record_id"):
            text(getattr(self, name), f"ReportProvenanceRecord.{name}")
        if self.source_namespace not in ALLOWED_EXTERNAL_NAMESPACES:
            raise MarketReportV0_2ValidationError(f"unapproved external namespace: {self.source_namespace}")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("provenance availability is invalid")
        optional_text(self.content_fingerprint, "provenance content_fingerprint")
        evidence = texts(self.evidence_ids, "provenance evidence")
        limitations = texts(self.limitations, "provenance limitations")
        if self.availability is Availability.UNAVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError("unavailable provenance requires limitations")
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "limitations", limitations)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceRecord(V0_2Contract):
    evidence_id: str
    semantics: EvidenceSemantics
    source_reference_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    content_fingerprint: str | None
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.evidence_id, "EvidenceRecord.evidence_id")
        if not isinstance(self.semantics, EvidenceSemantics):
            raise MarketReportV0_2ValidationError("evidence semantics is invalid")
        source_refs = texts(self.source_reference_ids, "evidence source references", allow_empty=False)
        provenance = texts(self.provenance_reference_ids, "evidence provenance", allow_empty=False)
        optional_text(self.content_fingerprint, "evidence content_fingerprint")
        object.__setattr__(self, "source_reference_ids", source_refs)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", texts(self.limitations, "evidence limitations"))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceRegistry(V0_2Contract):
    registry_id: str
    contract_version: str
    references: tuple[ContractReference, ...]
    evidence: tuple[EvidenceRecord, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != EVIDENCE_REGISTRY_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported evidence registry version")
        references = normalize_references(self.references, "EvidenceRegistry.references", allow_empty=True)
        evidence = tuple(sorted(self.evidence, key=lambda item: item.evidence_id))
        if any(not isinstance(item, EvidenceRecord) for item in evidence):
            raise MarketReportV0_2ValidationError("evidence registry contains an invalid record")
        if len({item.evidence_id for item in evidence}) != len(evidence):
            raise MarketReportV0_2ValidationError("evidence registry IDs must be unique")
        known_refs = {item.reference_id for item in references}
        for item in evidence:
            missing = set(item.source_reference_ids) - known_refs
            if missing:
                raise MarketReportV0_2ValidationError(f"evidence contains orphan source references: {sorted(missing)}")
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "limitations", texts(self.limitations, "evidence registry limitations"))
        if self.registry_id != identity("market-report-v0.2-evidence-registry", self, "registry_id"):
            raise MarketReportV0_2ValidationError("evidence registry_id does not match content")


def build_provenance_record(*, provenance_id: str | None = None, **content: Any) -> ReportProvenanceRecord:
    return ReportProvenanceRecord(
        provenance_id=provenance_id or deterministic_id("market-report-v0.2-provenance", content),
        **content,
    )


def build_evidence_registry(**content: Any) -> EvidenceRegistry:
    normalized = dict(content)
    normalized["references"] = tuple(sorted(normalized.get("references", ()), key=lambda item: item.reference_id))
    normalized["evidence"] = tuple(sorted(normalized.get("evidence", ()), key=lambda item: item.evidence_id))
    normalized["limitations"] = tuple(sorted(normalized.get("limitations", ())))
    material = {"contract_version": EVIDENCE_REGISTRY_CONTRACT_VERSION, **normalized}
    return EvidenceRegistry(
        registry_id=deterministic_id("market-report-v0.2-evidence-registry", material),
        **material,
    )


__all__ = (
    "ALLOWED_EXTERNAL_NAMESPACES", "EvidenceRecord", "EvidenceRegistry", "ReportProvenanceRecord",
    "build_evidence_registry", "build_provenance_record",
)
