"""SellerSprite import orchestration and governed dataset construction."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.normalization.models import json_value

from .models import (
    HEADER_MAPPING_VERSION,
    IMPORT_RULESET_VERSION,
    GovernedMarketDatasetV1,
    ImportContext,
    ImportValueStatus,
    ListingRecordV1,
    RowDisposition,
    RowOutcome,
)
from .normalizers import normalize_field
from .reader import RawImportTable, SourceRow, read_local_export
from .schema_v1 import CORE_HEADERS, FIELD_SPECS


def _hash(value: Any) -> str:
    return sha256(canonical_json(json_value(value)).encode("utf-8")).hexdigest()


def _record_from_row(row: SourceRow, table: RawImportTable) -> tuple[ListingRecordV1 | None, RowOutcome | None]:
    if row.malformed:
        return None, RowOutcome(
            source_row=row.row_number,
            disposition=RowDisposition.REJECTED_MALFORMED_ROW,
            reason_codes=("ROW_WIDER_THAN_HEADER",),
        )
    present_headers = set(table.mapped_headers)
    fields = tuple(
        normalize_field(spec, row.values.get(spec.header), header_present=spec.header in present_headers)
        for spec in FIELD_SPECS
        if spec.requirement != "OUT_OF_SCOPE"
    )
    by_header = {field.header: field for field in fields}
    asin_field = by_header["ASIN"]
    if asin_field.import_status in {
        ImportValueStatus.BLANK,
        ImportValueStatus.NOT_AVAILABLE,
        ImportValueStatus.MISSING_HEADER,
    }:
        return None, RowOutcome(
            source_row=row.row_number,
            disposition=RowDisposition.REJECTED_MISSING_ASIN,
            reason_codes=("ASIN_REQUIRED",),
        )
    if asin_field.import_status is ImportValueStatus.PARSE_FAILED:
        return None, RowOutcome(
            source_row=row.row_number,
            disposition=RowDisposition.REJECTED_INVALID_ASIN,
            reason_codes=("INVALID_ASIN",),
        )
    asin = str(asin_field.value)
    parent = by_header["父ASIN"].value
    logical = {
        "asin": asin,
        "parent_asin": parent,
        "fields": [field.to_dict() for field in fields],
    }
    return ListingRecordV1(
        asin=asin,
        parent_asin=None if parent is None else str(parent),
        source_row=row.row_number,
        fields=fields,
        record_fingerprint=_hash(logical),
    ), None


def _deduplicate(
    candidates: list[ListingRecordV1],
) -> tuple[tuple[ListingRecordV1, ...], tuple[RowOutcome, ...]]:
    by_asin: dict[str, list[ListingRecordV1]] = defaultdict(list)
    for record in candidates:
        by_asin[record.asin].append(record)
    accepted: list[ListingRecordV1] = []
    outcomes: list[RowOutcome] = []
    for asin in sorted(by_asin):
        records = sorted(by_asin[asin], key=lambda item: item.source_row)
        variants = {record.record_fingerprint for record in records}
        if len(variants) > 1:
            outcomes.extend(
                RowOutcome(
                    source_row=record.source_row,
                    asin=asin,
                    disposition=RowDisposition.QUARANTINED_CONFLICT,
                    reason_codes=("CONFLICTING_DUPLICATE_ASIN",),
                )
                for record in records
            )
            continue
        accepted.append(records[0])
        outcomes.append(
            RowOutcome(
                source_row=records[0].source_row,
                asin=asin,
                disposition=RowDisposition.ACCEPTED,
                reason_codes=(),
            )
        )
        outcomes.extend(
            RowOutcome(
                source_row=record.source_row,
                asin=asin,
                disposition=RowDisposition.DUPLICATE_EQUIVALENT,
                reason_codes=("EQUIVALENT_DUPLICATE_ASIN",),
            )
            for record in records[1:]
        )
    return tuple(accepted), tuple(outcomes)


def _missing_core(records: tuple[ListingRecordV1, ...]) -> tuple[tuple[str, int], ...]:
    counts: Counter[str] = Counter()
    for record in records:
        fields = {field.header: field for field in record.fields}
        for header in CORE_HEADERS:
            if fields[header].import_status is not ImportValueStatus.NORMALIZED:
                counts[header] += 1
    return tuple((header, counts[header]) for header in CORE_HEADERS if counts[header])


def import_sellersprite_file(
    path: str | Path,
    *,
    context: ImportContext,
) -> GovernedMarketDatasetV1:
    table = read_local_export(path, explicit_sheet=context.sheet_name)
    candidates: list[ListingRecordV1] = []
    outcomes: list[RowOutcome] = []
    for row in table.rows:
        record, outcome = _record_from_row(row, table)
        if record is not None:
            candidates.append(record)
        if outcome is not None:
            outcomes.append(outcome)
    records, identity_outcomes = _deduplicate(candidates)
    outcomes.extend(identity_outcomes)
    records = tuple(sorted(records, key=lambda item: item.asin))
    outcomes_tuple = tuple(sorted(outcomes, key=lambda item: item.source_row))

    logical_payload = {
        "contract_version": "governed-market-dataset-v1.0",
        "import_ruleset_version": IMPORT_RULESET_VERSION,
        "header_mapping_version": HEADER_MAPPING_VERSION,
        "source_file_sha256": table.source_file_sha256,
        "source_type": table.source_type,
        "source_sheet": table.source_sheet,
        "marketplace": context.marketplace,
        "category": context.category,
        "observed_date": context.observed_date,
        "records": [record.logical_dict() for record in records],
        "row_outcomes": [outcome.to_dict() for outcome in outcomes_tuple],
    }
    semantic_fingerprint = _hash(logical_payload)
    dataset_id = "gmdv1-" + _hash(
        {
            "semantic_fingerprint": semantic_fingerprint,
            "source_file_sha256": table.source_file_sha256,
        }
    )[:24]
    duplicate_count = sum(
        outcome.disposition is RowDisposition.DUPLICATE_EQUIVALENT for outcome in outcomes_tuple
    )
    rejected_count = sum(outcome.disposition.value.startswith("REJECTED_") for outcome in outcomes_tuple)
    quarantined_count = sum(
        outcome.disposition is RowDisposition.QUARANTINED_CONFLICT for outcome in outcomes_tuple
    )
    return GovernedMarketDatasetV1(
        dataset_id=dataset_id,
        semantic_fingerprint=semantic_fingerprint,
        source_type=table.source_type,
        source_basename=table.source_basename,
        source_file_sha256=table.source_file_sha256,
        imported_at=context.imported_at,
        marketplace=context.marketplace,
        category=context.category,
        observed_date=context.observed_date,
        observed_date_status="OBSERVED" if context.observed_date else "UNKNOWN",
        source_sheet=table.source_sheet,
        header_row=table.header_row,
        source_row_count=len(table.rows),
        accepted_listing_count=len(records),
        unique_asin_count=len(records),
        duplicate_row_count=duplicate_count,
        rejected_row_count=rejected_count,
        quarantined_row_count=quarantined_count,
        missing_core_field_summary=_missing_core(records),
        unmapped_headers=table.unmapped_headers,
        out_of_scope_headers=table.out_of_scope_headers,
        records=records,
        row_outcomes=outcomes_tuple,
    )


__all__ = ("import_sellersprite_file",)
