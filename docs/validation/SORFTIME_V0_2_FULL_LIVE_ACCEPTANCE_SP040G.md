# Sorftime V0.2 Full Live Acceptance SP-040G

Issue: TASK-SP-040G / GitHub Issue #50

Date: 2026-08-26

Verdict: `PASS — SORFTIME_V0_2_FULL_LIVE_ACCEPTANCE`

## A. Baseline/runtime/workspace

- Required baseline: `ce2a86b142f03c5a7a3b54c263d613b79955c6ec`.
- Dedicated branch: `codex/task-sp-040g-sorftime-v0-2-full-live-acceptance`.
- The baseline workspace and staging area were clean before SP-040G work.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. V0.1 release preservation

- `_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = True` before and after SP-040G.
- No V0.1 Provider, DTO, Canonical, Data Cleaning, Intelligence, Buyer Need, scoring, delivery, or release behavior was changed.
- The final V0.2 decision did not gate, disable, or broaden the accepted V0.1 scope.

## C. Zero-network live-derived V0.2 preflight

- The accepted external R6 report, manifest, and two checkpoints were used as local evidence only; the R6 source directory remained immutable.
- A fresh V0.2 production-adapter run completed with zero Provider network calls and produced strict V0.2 JSON, XLSX, and Markdown.
- Strict schema serialization round-trip: `PASS`.
- Required workbook sheets: `12/12`; artifact-tool formula error matches: `0`; all 12 sheets rendered and visually inspected.
- ProductRequest capture-only census fields found in V0.2 report semantics: `0/54`.
- ASINRequestKeyword capture-only census fields found in V0.2 report semantics: `0/23`.
- Market economics remained `UNAVAILABLE`; Buyer Needs remained `PARTIAL`; distributions and competitor details remained empty; Product Directions, Competitor Shortlist, and Opportunity remained `UNAVAILABLE`.
- No credential was read and no Provider call was made until every offline gate passed.

## D. V0.2 live-gate change

- Live V0.2 is accepted only for explicit `provider=sorftime`.
- The production request boundary continues to reject XiYou V0.2 live requests.
- The independent V0.2 release gate is version-qualified and fails before runtime or credential construction when disabled.
- The existing marketplace, exact-ASIN, no-resume, acquisition-plan, retry, and usage acceptance gates apply to V0.2 without weakening V0.1.

## E. Credential prerequisite

- Launch-process `SORFTIME_API_KEY` presence: `YES`.
- The value, length, hash, prefix, suffix, Authorization header, and account identifier were not printed, logged, or persisted.
- Sorftime CLI/MCP/inactive profiles were not inspected.
- No credential-like alternate source was inspected or recovered.

## F. Live invocation accounting

- Production Pipeline live invocations: `1`.
- Fixed scope: `provider=sorftime`, `mode=live`, `report_version=market-report-v0.2`, marketplace `US`, ASIN `B09265WXY5`, category `dog water bottle`.
- ProductRequest logical operations/attempts: `1/1`.
- ASINRequestKeyword logical operations/attempts: `1/1`.
- Total logical operations/transport attempts: `2/2`.
- Retries: `0`; reruns: `0`; live resumes: `0`; replayed operations: `0`.
- ProductVariations: `0`; XiYou: `0`; fallback: `0`.
- Direct diagnostic HTTP calls: `0`; Sorftime CLI live calls: `0`.
- The single live budget is exhausted. Every subsequent validation step was offline.

## G. ProductRequest result

- HTTP status: `200`; logical operation status: `SUCCEEDED`; transport attempt: `1`.
- Exact request: fixed ASIN with `Trend=2`.
- The R3-proven ProductRequest wire contract and R1 runtime wire capture remained active.
- Title was present and mapped to exactly one requested-ASIN Canonical fact; its scalar was not printed or copied into this record.
- Price, Brand, Rating, Review, Sales, Profit, and every other unapproved ProductRequest field remained capture-only.

## H. ASINRequestKeyword result

- HTTP status: `200`; logical operation status: `SUCCEEDED`; transport attempt: `1`.
- Exact request: fixed ASIN with `PageIndex=1` and `PageSize=20`.
- Accepted rows: `20`; distinct R5-proven nested capture-only extensions: `23`.
- Sponsored non-null observations: `0`.
- No pagination, sponsored promotion, Buyer Need change, timezone inference, or zero-demand inference was introduced.

## I. Usage accounting

- Unit: `REQUEST`.
- Semantics: `LIVE_PROVIDER_REPORTED`.
- Consumed: `2`; final remaining: `1336`.
- Credits: null; credit semantics: null.
- Sorftime Request usage was not written into any XiYou credit field.

## J. V0.2 schema and section truthfulness

- Report version: `market-report-v0.2`; strict deserialization and reserialization matched exactly.
- Requested/resolved ASINs: `1/1`; product grain remained `CHILD_ASIN`.
- Market Size remained `UNAVAILABLE`, including null monthly sales and revenue.
- True competitor candidate-universe completeness remained `UNKNOWN`; no empty cohort was treated as complete.
- Buyer Needs remained `PARTIAL`; Title was not used as Buyer Need evidence and no Title NLP was added.
- Product Directions, Competitor Shortlist, and Opportunity remained `UNAVAILABLE` rather than receiving invented values or numeric zeroes.

## K. Canonical/Data Cleaning/Intelligence non-regression

- Title remains the only newly promoted ProductRequest business field.
- All other ProductRequest extensions and all 23 Keyword extensions remain outside semantic DTOs and report semantics.
- No Canonical, Data Cleaning, Intelligence, Buyer Need, Competition, Opportunity, scoring, or aggregate-policy implementation changed.
- ProductVariations, pagination, sponsored semantics, field expansion, and complete-market claims remain absent.

## L. V0.2 artifacts and workbook contract

- Final run status: `SUCCEEDED`; final manifest stage: `COMPLETE`.
- Schema validation completed before operator delivery.
- The four formal artifacts exist in one fresh external, untracked directory: `market_report.json`, `operator_market_report.xlsx`, `operator_market_report.md`, and `run_manifest.json`.
- Workbook signature is valid OOXML; exact sheet count is `12`; exact names and order match the V0.2 contract.
- Artifact-tool import succeeded; formula error scan matched `0`; all sheets rendered and passed visual inspection.
- No live report, workbook, Markdown, manifest, checkpoint, preview, or raw Provider response is tracked or committed.

## M. V0.1 regression

- Existing SP-040E/SP-040F/V0.1 Pipeline tests remained in the focused post-live matrix.
- V0.1 release-gate tests confirm it remains enabled independently of V0.2.
- The known V0.1 OOXML canonical fingerprint exception is unchanged from the required baseline; SP-040G did not edit its renderer or golden hash.

## N. XiYou, Batch, and defaults

- Default provider remains `xiyou`.
- Default report remains `market-report-v0.1`.
- Batch remains XiYou-only.
- Sorftime requires explicit selection and has no XiYou fallback.
- The Sorftime acquisition plan remains exactly ProductRequest followed by ASINRequestKeyword; ProductVariations is absent.

## O. Secret and live-artifact safety

- Repository high-risk credential-pattern matches: `0`.
- External live artifact secret-marker matches: `0`.
- No credential value, Authorization header, raw response, live checkpoint, report body, workbook, Markdown, manifest, or preview is committed.
- The generated offline workspace output was moved outside the repository before staging.

## P. Post-live tests

- Focused Sorftime/Pipeline/V0.2/Operator-workbook matrix: `431 passed, 48 subtests`.
- Full suite: `1 failed, 1352 passed, 13 skipped, 550 subtests`.
- The sole failure is the unchanged required-baseline exception in `test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`: this Windows runtime produces OOXML package fingerprint beginning `84e5`, while the governed golden begins `89ff`.
- No new regression was introduced; all post-live tests were offline.

## Q. Renderer baseline classification

The V0.2 workbook was independently imported, formula-scanned, rendered, and visually inspected through artifact-tool. The unrelated V0.1 OOXML package fingerprint mismatch existed at the required baseline, remains byte-for-byte the same observed mismatch, and was not concealed by changing a golden hash.

## R. Git/diff gate

`git diff --check`, changed-file review, secret scan, live-artifact exclusion, focused tests, full-suite delta review, and final staged-diff review pass. Only production request/gate code, scoped tests, and this sanitized validation record are committed.

## S. Final rollout gates

- `_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = True`.
- `_SORFTIME_V0_2_LIVE_RELEASE_ENABLED = True` for the accepted exact Sorftime live scope.
- Default provider: `xiyou`; default report: `market-report-v0.1`.
- Batch: XiYou-only; fallback: absent.
- No broader marketplace, ASIN, report version, field, pagination, or operation scope is enabled.

## T. Final verdict

`PASS — SORFTIME_V0_2_FULL_LIVE_ACCEPTANCE`

Sorftime V0.2 passed the zero-network live-derived preflight and the single authorized full live Pipeline acceptance. V0.1 remains released and unchanged. No subsequent field expansion or follow-on task was started.
