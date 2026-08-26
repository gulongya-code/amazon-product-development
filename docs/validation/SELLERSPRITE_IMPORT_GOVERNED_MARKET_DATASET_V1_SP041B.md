# SP-041B SellerSprite Import / Governed Market Dataset V1 Validation

Date: 2026-08-26
Issue: `#52 TASK-SP-041B`
Required baseline: `c7c545761030e145ada54067dcc493134dade6c3`
Branch: `codex/task-sp-041b-sellersprite-import-governed-market-dataset`

## Development-start gate

- Exact `HEAD` matched the required baseline.
- Worktree and staging area were clean before the dedicated branch was made.
- Runtime: Python 3.14.4; pytest 9.1.1.
- SP-041A plus affected baseline tests: 71 passed, 27 subtests passed.
- Full baseline: 1 failed, 1369 passed, 13 skipped, 550 subtests passed.
- The sole baseline failure was
  `test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`:
  expected canonical OOXML hash `89ffe16d...`, actual `84e5aed6...`.
- The internal reuse audit and public GitHub/license audit were completed and
  recorded before implementation began.

## Acceptance evidence

| Area | Evidence | Result |
|---|---|---|
| local XLSX/CSV | strict `.xlsx`; UTF-8/UTF-8-SIG CSV; no sniffing | PASS |
| header discovery | preferred `原始数据源`, explicit sheet, zero/multiple candidate errors, first-20-row bound | PASS |
| 66-field contract | exact names, reordered full contract, empty V1 alias map, duplicate mapped-header rejection | PASS |
| typed/status normalization | ASIN, rank/count, Decimal money, signed percentage, rating, date, explicit boolean, URL, text | PASS |
| missing semantics | missing header, blank, NA, and parse failure remain distinct and never become zero | PASS |
| evidence semantics | third-party estimates retained; `毛利率` reference-only; OOS fields excluded | PASS |
| row grain | ASIN identity; parent relationship preserved; children never collapsed | PASS |
| duplicates/conflicts | equivalent rows dedupe with count; every conflicting identity row quarantined | PASS |
| governed result | SellerSprite manual-import type, CSV/XLSX format, stable ID/fingerprint, safe source metadata, provenance | PASS |
| boundaries | exactly 1,500 rows accepted; 1,501 rejected; malformed wide row isolated | PASS |
| safety/privacy | zero network constructor use, source hash unchanged, no source path in dataset, sanitized CLI stdout, no overwrite | PASS |
| forbidden scope | no pipeline wiring, Product Attribute Map, archetype, scoring, representative/direct-competitor, report, procurement, or workbook output | PASS |

## Test commands and results

Focused final suite:

```text
python -m pytest -q \
  tests/test_sellersprite_import_governed_dataset_v1.py \
  tests/test_sellersprite_import_cli_v1.py \
  tests/test_sellersprite_import_boundaries_v1.py \
  tests/test_sellersprite_import_contract_validation_v1.py \
  tests/test_sellersprite_import_source_contract_v1.py

18 passed in 6.15s
```

SP-041A and affected regression suite:

```text
122 passed, 62 subtests passed in 4.44s
```

Final full suite:

```text
1 failed, 1387 passed, 13 skipped, 550 subtests passed in 286.88s
```

The final failure is exactly the pre-existing XLSX delivery hash failure above:
same test, expected hash, and actual hash. Net result versus development-start
baseline is +18 passed, zero new failures.

## Optional private replay

`PRIVATE_REAL_EXPORT_REPLAY = NOT_RUN`

No private SellerSprite export was available or required. Synthetic/minimal
fixtures cover the acceptance cases, and the optional replay does not block
the verdict.

## Verdict

`PASS — SELLERSPRITE_IMPORT_GOVERNED_MARKET_DATASET_V1`
