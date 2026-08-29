"""Immutable provider/import-neutral governed market dataset contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
import json
from typing import Any

from amazon_product_intelligence.contracts import NormalizationStatus, PresenceStatus, SemanticStatus
from amazon_product_intelligence.normalization.models import json_value


DATASET_CONTRACT_VERSION = "governed-market-dataset-v1.0"
IMPORT_RULESET_VERSION = "sellersprite-local-import-v1.0"
HEADER_MAPPING_VERSION = "operator-template-66-exact-v1.0"
SOURCE_KIND = "SELLERSPRITE_MANUAL_IMPORT"


class ImportValueStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    MISSING_HEADER = "MISSING_HEADER"
    BLANK = "BLANK"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    PARSE_FAILED = "PARSE_FAILED"


class EvidenceSemantics(StrEnum):
    UNKNOWN = "UNKNOWN"
    PROVIDER_EXPORTED_EVIDENCE = "PROVIDER_EXPORTED_EVIDENCE"
    THIRD_PARTY_ESTIMATE = "THIRD_PARTY_ESTIMATE"
    REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH = "REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH"


class RowDisposition(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE_EQUIVALENT = "DUPLICATE_EQUIVALENT"
    QUARANTINED_CONFLICT = "QUARANTINED_CONFLICT"
    REJECTED_MISSING_ASIN = "REJECTED_MISSING_ASIN"
    REJECTED_INVALID_ASIN = "REJECTED_INVALID_ASIN"
    REJECTED_MALFORMED_ROW = "REJECTED_MALFORMED_ROW"


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportContext:
    marketplace: str
    category: str
    imported_at: str
    observed_date: str | None = None
    sheet_name: str | None = None

    def __post_init__(self) -> None:
        for name in ("marketplace", "category", "imported_at"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        candidate = self.imported_at[:-1] + "+00:00" if self.imported_at.endswith("Z") else self.imported_at
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("imported_at must be an RFC 3339 date-time") from exc
        if parsed.tzinfo is None:
            raise ValueError("imported_at must include a timezone")
        if self.observed_date is not None:
            try:
                date.fromisoformat(self.observed_date)
            except (TypeError, ValueError) as exc:
                raise ValueError("observed_date must use ISO YYYY-MM-DD") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedField:
    header: str
    requirement: str
    value_type: str
    value: Any
    import_status: ImportValueStatus
    presence_status: PresenceStatus
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    evidence_semantics: EvidenceSemantics
    issue_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "header": self.header,
            "requirement": self.requirement,
            "value_type": self.value_type,
            "value": json_value(self.value),
            "import_status": self.import_status.value,
            "presence_status": self.presence_status.value,
            "normalization_status": self.normalization_status.value,
            "semantic_status": self.semantic_status.value,
            "evidence_semantics": self.evidence_semantics.value,
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ListingRecordV1:
    asin: str
    parent_asin: str | None
    source_row: int
    fields: tuple[NormalizedField, ...]
    record_fingerprint: str

    def logical_dict(self) -> dict[str, Any]:
        return {
            "asin": self.asin,
            "parent_asin": self.parent_asin,
            "fields": [field.to_dict() for field in self.fields],
        }

    def to_dict(self) -> dict[str, Any]:
        result = self.logical_dict()
        result.update({"source_row": self.source_row, "record_fingerprint": self.record_fingerprint})
        return result


@dataclass(frozen=True, slots=True, kw_only=True)
class RowOutcome:
    source_row: int
    disposition: RowDisposition
    reason_codes: tuple[str, ...]
    asin: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_row": self.source_row,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "asin": self.asin,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedMarketDatasetV1:
    dataset_id: str
    semantic_fingerprint: str
    source_type: str
    source_basename: str
    source_file_sha256: str
    imported_at: str
    marketplace: str
    category: str
    observed_date: str | None
    observed_date_status: str
    source_sheet: str | None
    header_row: int
    source_row_count: int
    accepted_listing_count: int
    unique_asin_count: int
    duplicate_row_count: int
    rejected_row_count: int
    quarantined_row_count: int
    missing_core_field_summary: tuple[tuple[str, int], ...]
    unmapped_headers: tuple[str, ...]
    out_of_scope_headers: tuple[str, ...]
    records: tuple[ListingRecordV1, ...]
    row_outcomes: tuple[RowOutcome, ...]
    contract_version: str = DATASET_CONTRACT_VERSION
    import_ruleset_version: str = IMPORT_RULESET_VERSION
    header_mapping_version: str = HEADER_MAPPING_VERSION
    source_kind_value: str = SOURCE_KIND

    @property
    def source_kind(self) -> str:
        return self.source_kind_value

    @property
    def source_format(self) -> str:
        return self.source_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "import_ruleset_version": self.import_ruleset_version,
            "header_mapping_version": self.header_mapping_version,
            "dataset_id": self.dataset_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            "source": {
                "type": self.source_kind,
                "format": self.source_format,
                "basename": self.source_basename,
                "file_sha256": self.source_file_sha256,
                "sheet": self.source_sheet,
                "header_row": self.header_row,
            },
            "imported_at": self.imported_at,
            "marketplace": self.marketplace,
            "category": self.category,
            "observed_date": self.observed_date,
            "observed_date_status": self.observed_date_status,
            "counts": {
                "source_rows": self.source_row_count,
                "accepted_listings": self.accepted_listing_count,
                "unique_asins": self.unique_asin_count,
                "duplicate_rows": self.duplicate_row_count,
                "rejected_rows": self.rejected_row_count,
                "quarantined_rows": self.quarantined_row_count,
            },
            "missing_core_field_summary": [
                {"header": header, "count": count}
                for header, count in self.missing_core_field_summary
            ],
            "unmapped_headers": list(self.unmapped_headers),
            "out_of_scope_headers": list(self.out_of_scope_headers),
            "records": [record.to_dict() for record in self.records],
            "row_outcomes": [outcome.to_dict() for outcome in self.row_outcomes],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


__all__ = (
    "DATASET_CONTRACT_VERSION",
    "EvidenceSemantics",
    "GovernedMarketDatasetV1",
    "HEADER_MAPPING_VERSION",
    "IMPORT_RULESET_VERSION",
    "ImportContext",
    "ImportValueStatus",
    "ListingRecordV1",
    "NormalizedField",
    "RowDisposition",
    "RowOutcome",
    "SOURCE_KIND",
)
