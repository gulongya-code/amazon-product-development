"""Reference-only sanitized appendix contract; never a raw Provider payload store."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from amazon_product_intelligence.contracts import canonical_json, deterministic_id

from ..version import SANITIZED_APPENDIX_CONTRACT_VERSION
from .common import Availability, MarketReportV0_2ValidationError, V0_2Contract, identity, optional_text, text, texts


_SECRET = re.compile(r"(api[_-]?key|authorization|bearer\s+|access[_-]?token|secret|password)", re.IGNORECASE)
_PATH = re.compile(r"(^[A-Za-z]:\\|^/|file://|\\\\)")


@dataclass(frozen=True, slots=True, kw_only=True)
class SanitizedEvidenceReference(V0_2Contract):
    appendix_reference_id: str
    content_address: str
    media_type: str
    display_text: str | None
    source_reference_id: str
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.content_address.startswith("sha256:"):
            raise MarketReportV0_2ValidationError("sanitized appendix requires a content-addressed sha256 reference")
        text(self.media_type, "sanitized appendix media_type")
        text(self.source_reference_id, "sanitized appendix source_reference_id")
        optional_text(self.display_text, "sanitized appendix display_text")
        serialized = canonical_json(self.to_dict() | {"appendix_reference_id": ""})
        if _SECRET.search(serialized) or (self.display_text and _PATH.search(self.display_text)):
            raise MarketReportV0_2ValidationError("sanitized appendix contains secret/raw-path material")
        object.__setattr__(self, "provenance_reference_ids", texts(self.provenance_reference_ids, "sanitized appendix provenance", allow_empty=False))
        if self.appendix_reference_id != identity("market-report-v0.2-sanitized-reference", self, "appendix_reference_id"):
            raise MarketReportV0_2ValidationError("sanitized appendix reference ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class SanitizedAppendixSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    references: tuple[SanitizedEvidenceReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != SANITIZED_APPENDIX_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported sanitized appendix version")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("sanitized appendix availability is invalid")
        references = tuple(sorted(self.references, key=lambda item: item.appendix_reference_id))
        if any(not isinstance(item, SanitizedEvidenceReference) for item in references):
            raise MarketReportV0_2ValidationError("sanitized appendix contains an invalid reference")
        if len({item.appendix_reference_id for item in references}) != len(references):
            raise MarketReportV0_2ValidationError("sanitized appendix reference IDs must be unique")
        limitations = texts(self.limitations, "sanitized appendix limitations")
        if self.availability is Availability.UNAVAILABLE and (references or not limitations):
            raise MarketReportV0_2ValidationError("unavailable sanitized appendix must be empty with limitations")
        if self.availability is Availability.AVAILABLE and not references:
            raise MarketReportV0_2ValidationError("available sanitized appendix requires references")
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", texts(self.provenance_reference_ids, "sanitized appendix provenance", allow_empty=False))
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity("market-report-v0.2-sanitized-appendix", self, "section_id"):
            raise MarketReportV0_2ValidationError("sanitized appendix section_id does not match content")


def build_sanitized_reference(**content: Any) -> SanitizedEvidenceReference:
    content["provenance_reference_ids"] = tuple(sorted(content["provenance_reference_ids"]))
    return SanitizedEvidenceReference(appendix_reference_id=deterministic_id("market-report-v0.2-sanitized-reference", content), **content)


def build_sanitized_appendix(**content: Any) -> SanitizedAppendixSection:
    normalized = dict(content)
    normalized["references"] = tuple(sorted(normalized.get("references", ()), key=lambda item: item.appendix_reference_id))
    normalized["provenance_reference_ids"] = tuple(sorted(normalized.get("provenance_reference_ids", ())))
    normalized["limitations"] = tuple(sorted(normalized.get("limitations", ())))
    material = {"contract_version": SANITIZED_APPENDIX_CONTRACT_VERSION, **normalized}
    return SanitizedAppendixSection(section_id=deterministic_id("market-report-v0.2-sanitized-appendix", material), **material)


__all__ = ("SanitizedAppendixSection", "SanitizedEvidenceReference", "build_sanitized_appendix", "build_sanitized_reference")
