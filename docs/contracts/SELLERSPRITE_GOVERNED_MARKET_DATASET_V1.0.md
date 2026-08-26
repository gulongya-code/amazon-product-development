# SellerSprite Import / Governed Market Dataset V1.0

Date: 2026-08-26
Ruleset: `sellersprite-local-import-v1.0`
Dataset contract: `governed-market-dataset-v1.0`
Header mapping: `operator-template-66-exact-v1.0`

## Boundary

This contract governs a local SellerSprite `.xlsx` or UTF-8 `.csv` export and
produces a provider/import-neutral market dataset. It performs no network
access and is not wired into the Production Pipeline. It does not build a
Product Attribute Map, Product Archetype, score, representative set, direct
competitor set, procurement truth, Market Report, or workbook output.

## Source discovery

- XLSX: an explicitly requested sheet is authoritative. Otherwise a sheet
  named `原始数据源` is preferred and must itself contain exactly one candidate.
  If neither applies, the workbook must have exactly one candidate across all
  sheets.
- CSV: decode strictly as UTF-8 or UTF-8-SIG with the standard comma-separated
  Excel dialect. Encoding/dialect guessing is forbidden.
- Only the first 20 rows are scanned. A candidate contains exact `ASIN` plus at
  least four other distinct fields from the frozen 66-field contract.
- Zero candidates is `HEADER_SCHEMA_MISMATCH`; multiple candidates is
  `AMBIGUOUS_HEADER`; duplicate columns mapping to one contract field is
  `DUPLICATE_MAPPED_HEADER`.
- Mapping is by exact trimmed header name. The V1 explicit alias map is empty.
  Case folding, fuzzy matching, substring matching, and ordinal guessing are
  forbidden.

## Row and field rules

- Row grain is one listing ASIN. `父ASIN` is relationship evidence only; child
  rows are never collapsed into a parent row.
- A missing or invalid ASIN rejects that row. At most 1,500 nonblank listing
  rows are accepted as an import source.
- Missing header, blank cell, explicit NA token, and parse failure have distinct
  statuses and carry `null`; none is converted to numeric zero.
- Integers/counts/ranks, Decimal money, signed exported percentages, rating,
  ISO date, explicit boolean, HTTP(S) URL, ASIN, and conservative text are
  normalized by declared field type. Raw parameters, titles, dimensions, and
  weights stay text evidence and receive no product-attribute interpretation.
- `LQS` and `SP广告` are out of scope and never enter listing semantics.
- Unknown headers are retained by name at dataset level only. Their cell
  values are not imported.
- SellerSprite sales, revenue, rank, and growth estimates retain
  `THIRD_PARTY_ESTIMATE`. Exported `毛利率` is
  `REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH`.

## Duplicate identity rules

Normalized rows are grouped by ASIN. If every logical field/status is equal,
one row is accepted and later rows are counted as equivalent duplicates. If
one ASIN has more than one normalized logical variant, every row for that ASIN
is quarantined as `CONFLICTING_DUPLICATE_ASIN`; no first/last-write overwrite is
allowed.

## Governed result

The result includes contract/ruleset versions, deterministic dataset ID and
semantic fingerprint, source type, safe basename, file SHA-256, import time,
marketplace/category, observed date or `UNKNOWN`, sheet/header provenance,
source/accepted/unique/duplicate/rejected/quarantined counts, missing CORE
summary, unmapped/out-of-scope header names, normalized listing records, and
sanitized row outcomes.

Identity material excludes the runtime import timestamp but includes the
source digest, mapping/ruleset versions, context, normalized records, and row
outcomes. The same logical input and context therefore produce the same ID and
fingerprint. Canonical JSON uses sorted keys, compact separators, UTF-8 text,
finite numbers only, and Decimal/date string representations.

## Privacy and persistence

The library retains no source path; only the basename and SHA-256 are present
in the dataset. Errors and CLI stdout contain only codes, counts, safe names,
and fingerprints, never source row scalar values. The optional CLI JSON output
uses exclusive creation and refuses to overwrite an existing file. Source
workbooks/files are read-only and are never mutated.
