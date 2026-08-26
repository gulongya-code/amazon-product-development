# Sorftime ASINRequestKeyword Live Wire Contract Reconciliation R5

Issue: TASK-SP-040F-R5 / GitHub Issue #47

Date: 2026-08-26

Verdict: `PASS — SORFTIME_KEYWORD_LIVE_WIRE_CONTRACT_RECONCILED`

## A. Baseline/runtime/workspace

- Required baseline: `aa98760ad9257335caa37d1f0b7ebcf608cdc0a2`.
- Dedicated branch: `codex/task-sp-040f-r5-keyword-wire-repair`.
- The workspace and index were clean at the required baseline before R5 work.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. R4 keyword failure

R4 recorded one successful ProductRequest followed by one HTTP-200 ASINRequestKeyword response that failed strict DTO validation with `SCHEMA_MISMATCH`. R4 stopped immediately and restored the Sorftime V0.1 live gate to disabled. R5 did not rerun or resume that Pipeline.

## C. Strict contract audit

The accepted keyword row remained limited to `ShowType`, `ShowShare`, `PositionType`, `AdPosition`, `AdPositionDate`, `SearchPosition`, `SearchPositionDate`, and nested `Keyword`. The nested semantic boundary remained exactly `Keyword`, `SearchVolume`, `Cpc`, and `CpcRange`. No global case-insensitive parser, pagination, sponsored semantics, Buyer Need mapping, or new business-field promotion was introduced.

Source: [GitHub Issue #47](https://github.com/gulongya-code/amazon-product-development/issues/47).

## D. Offline structural diagnostic

Before network access, R5 added a deterministic structural diagnostic and exercised it against local fixtures and synthetic drift. It retains only HTTP/envelope state, field names, JSON types, nullability, counts, casing candidates, position/cardinality classes, sponsored presence classes, date/position format classes, request counters, parser result, failure kind, and failure path. Unsafe credential-like names and nested structures are redacted.

The pre-census focused offline set passed: `389 passed, 5 skipped, 180 subtests`.

## E. Credential prerequisite

- Launch-process `SORFTIME_API_KEY` presence: `YES`.
- Windows User credential: `NOT READ`.
- CLI/MCP profiles: `NOT INSPECTED`.
- No credential value, length, hash, prefix, suffix, Authorization header, or account identifier was printed or persisted.

## F. Structural-census accounting

- ASINRequestKeyword structural-census calls: `1`.
- Exact request: ASIN `B09265WXY5`, `PageIndex=1`, `PageSize=20`, domain `1`.
- HTTP status: `200`; provider `Code`: `0`.
- Provider-reported RequestConsumed: `1`; RequestLeft: `1340`.
- Retries: `0`.
- Pipeline live invocations: `0`.
- ProductRequest calls: `0`.
- ProductVariations calls: `0`.
- XiYou calls: `0`.
- Sorftime CLI calls: `0`.

The one-call budget is exhausted. No response body, scalar business value, response header, or raw artifact was persisted.

## G. Sanitized structural inventory

The committed census fixture contains structure only. It contains no ASIN, keyword, search volume, CPC, share, position, timestamp, Authorization value, or response body.

- Envelope keys: `Code`, `Data`, `Message`, `RequestConsumed`, `RequestLeft`.
- Data: array with `20` object rows.
- Exact row strings: `SearchPosition`, `SearchPositionDate`, `ShowType`.
- Exact row number: `ShowShare`.
- Exact row array: `PositionType`.
- Exact row nulls: `AdPosition`, `AdPositionDate`.
- Exact row object: `Keyword`.
- Nested semantic strings: `Keyword`.
- Nested semantic numbers: `SearchVolume`, `Cpc`.
- Nested semantic array: `CpcRange`.
- Row extras: `0`; casing aliases: `0`.

## H. Exact mismatch classification

The pre-repair parser failed only because every nested `Keyword` object contained 23 additional fields. The first deterministic failure was `NESTED_KEYWORD_EXTRA_FIELDS` at `Data[].Keyword.ClickConversionRateD90`. No row-level extra, casing, missing, nullability, semantic type, position, sponsored, search-position, timestamp, or CPC-range drift was observed.

## I. Keyword-local projection

Only the 23 exact, census-proven nested names and their observed JSON types are admitted to a keyword-local runtime sidecar. The strict semantic projection is decoded through the existing DTO. Unknown nested names, casing variants, duplicate aliases, wrong extension types, row extras, and missing semantic fields still fail closed. There is no globally case-insensitive or permissive parser.

## J. Sponsored boundary

`AdPosition` and `AdPositionDate` were null in all 20 rows. No sponsored relationship, placement, timestamp, rank, or capability was promoted. The existing explicit sponsored-unavailable diagnostic remains unchanged.

## K. Position and timestamp boundary

`PositionType` was an array with one string element in every row. `SearchPosition` matched the already accepted Chinese page/slot format, and `SearchPositionDate` matched the existing local-minute format with timezone unknown. These observations only confirm existing validation; no new interpretation or timestamp normalization was added.

## L. Keyword/CPC/search-volume semantics

The only semantic nested fields remain `Keyword`, `SearchVolume`, `Cpc`, and `CpcRange`. `CpcRange` remained a two-number array. Existing keyword identity, search-volume evidence, CPC minor-unit evidence, organic-position handling, and deterministic Canonical mapping are unchanged.

## M. Capture-only extensions

- Numbers: `ClickConversionRateD90`, `ClickOf90D`, `ProductCount`, `Rank`, `RankChangeOfWeekly`, `SalesVolumeOf90D`, `SearchConversionRate`, `SearchConversionRateD90`, `ShareClickRate`, `ShareConversionRate`, `WordCount`.
- Arrays: `Images`, `ImagesFromAsin`, `SearchRankTrend`, `SearchVolumeGrowthRateTrend`, `SearchVolumeTrend`, `Top3Brand`, `Top3Category`, `Top3asin`.
- Strings: `KeywordCNName`, `Season`, `Update`.
- Null: `Department`.

Their runtime values do not enter the semantic DTO, Canonical observations, raw snapshot, content fingerprint, capabilities, Buyer Need logic, Intelligence inputs, reports, or persisted safe representation. The safe sidecar exposes only structural inventory.

## N. ProductRequest non-regression

R3/R4 ProductRequest parsing, wire capture, Title-only promotion, missing/null handling, and capture-only field behavior pass unchanged. R5 makes no ProductRequest contract, mapper, or capability change.

## O. Pipeline/recovery/XiYou non-regression

SP-040E fixture Pipeline/recovery, provider-qualified checkpoints, Request-versus-XiYou-credit separation, default XiYou behavior, Data Cleaning, Canonical normalization, and Batch XiYou-only behavior pass offline. R5 adds no fallback, retry, live resume, pagination, ProductVariations, or acquisition-plan change.

## P. Secret/network safety

The diagnostic, sanitized census, diff, and repository artifacts retain no credential or Authorization value and no live response scalar. All post-census work and tests were offline. The unique ordinary-HTTP census was the only R5 Provider operation.

## Q. Focused/full regression result

- DTO/HTTP/mapper/R5 focused set: `150 passed`.
- Provider/Pipeline/Batch focused set: `250 passed, 5 skipped, 52 subtests`.
- Full suite: `1 failed, 1340 passed, 16 skipped, 550 subtests`.
- The sole failure is the unchanged Renderer baseline exception in `test_xlsx_delivery_v0_1.py`: expected OOXML package fingerprint begins `89ff`, actual begins `84e5`. R5 does not touch Renderer code or expectations.

## R. Git/diff/scan/gate

`git diff --check`, Python compilation, tracked/untracked review, exact process-credential scan, Authorization/credential-pattern scan, and census-content safety checks pass. R5 changes only the Sorftime keyword structural diagnostic, narrow nested projection/sidecar, sanitized fixture, tests, exports, client integration, and this report.

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = False`. Sorftime V0.1 live remains disabled, market-report-v0.2 live remains blocked, default provider remains XiYou, and Batch remains XiYou-only.

## S. R6 readiness

The proven ASINRequestKeyword wire mismatch is reconciled offline, but R5 does not enable live execution or run a Pipeline smoke. Any R6 Pipeline validation requires separate authorization and must begin from the accepted R5 commit.

## T. Final verdict

`PASS — SORFTIME_KEYWORD_LIVE_WIRE_CONTRACT_RECONCILED`

R6 and SP-040G were not started.
