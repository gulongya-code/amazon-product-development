# Sorftime ProductRequest Wire Capture and Title Promotion V0.1

Issue: TASK-SP-040F-R1 / GitHub Issue #43

Date: 2026-08-26

Verdict: `PASS — SORFTIME_PRODUCTREQUEST_WIRE_CAPTURE_AND_TITLE_PROMOTION`

## A. Baseline/runtime/workspace

- Required baseline: `7d8f67de4d6a294298db36940dd2e5af890f2eec`.
- Dedicated branch: `codex/task-sp-040f-r1-productrequest-wire-title`.
- Workspace was clean and exactly at the required baseline before branch creation.
- Runtime: Python 3.12.10, pytest 9.0.3, Windows PowerShell.

## B. SP-040F failure evidence

The safe SP-040F record proves one authorized Pipeline invocation reached the pinned Sorftime ordinary HTTP endpoint, transmitted `ProductRequest(Trend=2)` once, received HTTP 200, and failed at typed response validation as `SCHEMA_MISMATCH`. No raw live body was committed or reconstructed.

## C. Exact mismatch classification

The pre-R1 parser passed the complete `Data` object directly to the globally strict `SorftimeProductRequestData` contract. A real rich ProductRequest object therefore failed on additional root-level product fields before its approved semantic slice could be validated. The repair adds an explicit ProductRequest-only wire projection; global `JsonContract` strictness is unchanged.

## D. Schema-census accounting if used

- Conditional ProductRequest schema-census calls: `0`.
- Retries: `0`.
- Pipeline live invocations: `0`.
- ASINRequestKeyword live calls: `0`.
- ProductVariations live calls: `0`.
- XiYou live calls: `0`.
- Sorftime CLI live calls: `0`.

The exact parser failure and `Title` contract were sufficiently established from Issue #43, the safe SP-040F validation record, existing DTO/parser code, and repository evidence. No credential was read.

## E. Wire-capture architecture

`parse_product_request_wire_response` keeps the top-level envelope strict, separates approved `Data` fields into the semantic DTO, freezes safe JSON-compatible root extensions in a runtime-only sidecar, and creates deterministic field inventory metadata. The ordinary client returns the same typed semantic response plus the sidecar in `SorftimeOperationResult.wire_capture`.

## F. Observed ProductRequest field inventory

The deterministic synthetic rich fixture inventories the existing approved fields plus `Title` as `PROMOTED`. Synthetic `Price`, `Brand`, `Rating`, `Sales`, and `Image` examples are classified `CAPTURED_UNVERIFIED`. Inventory records field name, observed JSON type/null state, status, operation, and capture-contract version; it contains no scalar field values.

## G. Title contract and Canonical mapping

Exact `Data.Title` accepts a non-blank string, explicit null, or omission. A present title maps once to the existing Canonical `ProductFactObservation` dimension `title`, `FactGroup.IDENTITY_RELATED`, at exact `Data.Asin` scope with Sorftime provenance. It is never copied to returned variation ASINs.

## H. Capture-only field behavior

Safe additional `Data` root fields are retained only in the wire sidecar and successful provider checkpoint payload. They are absent from the semantic DTO, mapper projection, Canonical observations, semantic fingerprints, capabilities, Intelligence inputs, and report behavior. Changing or reordering them does not change promoted Canonical IDs or fingerprints.

## I. Strict semantic-field behavior

Top-level envelope drift, semantic-field casing collisions, invalid ASIN identity, ParentAsin shape, variation identity/count errors, malformed accepted Attribute rows, non-null Trend=2 fields, invalid Title type, HTTP/business-code errors, and unknown structure inside approved fields remain fail-closed.

## J. Runtime/checkpoint preservation

The client exposes immutable safe wire extensions at runtime. The existing provider recording/checkpoint path retains the credential-free successful `TransportResponse.payload`; a deterministic test proves safe rich ProductRequest fields survive checkpoint serialization while Authorization and credential material are absent.

## K. DTO/mapper determinism

Minimal pre-R1 payloads still parse. Rich and minimal payloads preserve all prior mapped semantic values, with only the supplied Title added. Extension insertion order and capture-only values do not affect the mapper projection or promoted observation identities.

## L. ProductVariations/keyword non-regression

No production code or fixture for ProductVariations or ASINRequestKeyword was changed. Their existing strict DTO, mapper, and connector tests remain green. Live calls to both operations were zero.

## M. Pipeline/recovery/XiYou regressions

SP-040E fixture E2E/recovery, SP-040F gate tests, all XiYou behavior, Canonical/Data Cleaning, frozen Intelligence/Market Report, Operator, and Batch tests pass within the full suite. No fallback behavior changed.

## N. Secret/network safety

All implementation and test execution was offline with fake/local transports. Unsafe header/credential-like root or nested extension keys are omitted from captured values and marked `IGNORED_UNSAFE`; safe dictionaries expose inventory only. No environment credential, CLI profile, MCP credential, raw live response, Authorization value, hash, prefix, or suffix was read or emitted.

## O. Full-suite comparison

- Required-baseline full suite: `1 failed, 1256 passed, 16 skipped, 550 subtests`.
- R1 full suite: `1 failed, 1289 passed, 16 skipped, 550 subtests`.
- The sole failure is the unchanged Renderer baseline exception in `test_xlsx_delivery_v0_1.py`: expected OOXML package hash begins `89ff`, actual begins `84e5`.
- R1 adds 33 passing deterministic tests and introduces no full-suite failure.

## P. Git/diff/scan

`git diff --check`, staged diff inspection, repository secret-pattern scan, and tracked-file status checks pass. Only R1 implementation, synthetic fixture, tests, and this validation record are included.

## Q. Final live-gate state

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED` remains `False`. Sorftime Production Pipeline live remains disabled, and the market-report-v0.2 live gate is unchanged.

## R. Deferred field-promotion candidates

Price, brand, rating, reviews, category/node, description, seller, fulfillment, dates, images, coupons, dimensions/weight, sales/revenue, fees, profit/margin, A+ indicators, and all other unverified fields remain capture-only candidates. No units, periods, denominator, profitability method, or Canonical equivalence is inferred.

## S. Fast-landing handoff to SP-040F-R2

R1 leaves the narrow ProductRequest wire boundary ready for a separately authorized R2 live retry: rich safe root fields can pass acquisition while only existing semantics plus Title reach Canonical. R1 does not enable live execution and does not perform or start R2.

## T. Final verdict

`PASS — SORFTIME_PRODUCTREQUEST_WIRE_CAPTURE_AND_TITLE_PROMOTION`

SP-040F-R2 and SP-040G were not started.
