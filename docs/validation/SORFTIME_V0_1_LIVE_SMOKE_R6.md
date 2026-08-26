# Sorftime V0.1 Final Live Pipeline Smoke R6

Issue: TASK-SP-040F-R6 / GitHub Issue #48

Date: 2026-08-26

Verdict: `BLOCKED — PIPELINE_OR_ARTIFACT_GATE`

## A. Baseline/runtime/workspace

- Required baseline: `9507c57b03f20e0539625760f68f180fbb49b6b7`.
- Dedicated branch: `codex/task-sp-040f-r6-final-live-smoke`.
- The baseline workspace and staging area were clean before R6 work.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. Credential prerequisite

- Launch-process `SORFTIME_API_KEY` presence: `YES`.
- Windows User credential: `NOT READ`.
- CLI/MCP/inactive profiles: `NOT INSPECTED`.
- No credential value, length, hash, prefix, suffix, Authorization header, or account identifier was printed or persisted.

## C. Offline preflight

- R3/R5/Sorftime/Provider/Pipeline/Data Cleaning/Canonical/Intelligence/Report/Operator/Batch focused set: `901 passed, 16 skipped, 262 subtests`.
- Full required-baseline suite: `1 failed, 1340 passed, 16 skipped, 550 subtests`.
- The sole failure was the Issue-declared Renderer OOXML package fingerprint exception.
- The plan was exactly `ProductRequest(Trend=2)` followed by `ASINRequestKeyword(PageIndex=1, PageSize=20)` for one fixed ASIN.
- ProductVariations was absent; pinned origin, BasicAuth path, `NoRetryPolicy`, `max_attempts=1`, Request-versus-credit semantics, default XiYou, V0.2 live block, and Batch XiYou-only boundaries were verified.
- Repository exact-credential scan found zero matches.
- Automated preflight tests made zero external Provider network calls.

## D. Live invocation accounting

- Production Pipeline live invocations: `1`.
- Fixed marketplace/ASIN/category: `US` / `B09265WXY5` / `dog water bottle`.
- ProductRequest logical operations/attempts: `1/1`.
- ASINRequestKeyword logical operations/attempts: `1/1`.
- Total logical operations/transport attempts: `2/2`.
- Retries: `0`; reruns: `0`; live resumes: `0`; replayed operations: `0`.
- ProductVariations: `0`; XiYou: `0`; fallback: `0`.
- Direct/ad-hoc Sorftime diagnostic HTTP calls: `0`; Sorftime CLI live calls: `0`.

The single live budget is exhausted. No additional Provider request was issued after the run ended.

## E. ProductRequest result

- HTTP `200`; provider `Code=0`; RequestConsumed `1`; RequestLeft `1339`.
- R3 reconciled wire parser: accepted.
- Missing daily fields remained unavailable rather than zero.
- R3 capture-only arrays, daily-trend extensions, and all other unapproved product fields remained outside the semantic DTO and downstream outputs.
- ProductRequest logical operation status: `SUCCEEDED`; one success checkpoint was created only in the external smoke directory.

## F. Title result

- Title present: `YES`.
- Canonical `title` fact count: `1`.
- Exact requested-ASIN grain: `YES`.
- Variation title copies: `0`.
- The Title scalar was not printed or copied into this record.

## G. ASINRequestKeyword result

- Exact request shape: fixed ASIN, `PageIndex=1`, `PageSize=20`.
- HTTP `200`; provider `Code=0`; RequestConsumed `1`; RequestLeft `1338`.
- R5 reconciled wire parser: accepted.
- Accepted row count: `20`.
- Existing strict nested semantic slice remained exactly `Keyword`, `SearchVolume`, `Cpc`, and `CpcRange`.
- No pagination, full-universe claim, timezone inference, or zero-demand inference was added.

## H. Keyword capture-only verification

- Distinct census-proven nested extensions: `23`.
- Every accepted row retained exactly the 23 proven extensions in the runtime-only capture boundary.
- Their values remained outside semantic DTOs, Canonical evidence, Buyer Need, reports, and persisted safe summaries.
- Sponsored relationship count: `0`.
- No sponsored semantics, Buyer Need changes, or new keyword-field promotions were introduced.

## I. Usage accounting

- Unit: `REQUEST`.
- Semantics: `LIVE_PROVIDER_REPORTED`.
- Current R6 run consumed: `2` from the two accepted typed-envelope RequestConsumed values.
- Final remaining: `1338`, from the accepted keyword envelope.
- Credits: null; credit semantics: null.
- Prior structural-census usage was not included.

## J. Canonical/Data Cleaning

- Requested/resolved ASINs: `1/1`.
- Acquisition completed with both provider operations accepted.
- Data Cleaning completed with truthful partial availability; missing economics remained missing rather than zero.
- ProductRequest and keyword capture-only values did not enter Canonical semantics.

## K. Downstream truthfulness

- Market Report contract remained exactly `market-report-v0.1`.
- The explicit ASIN remained the requested cohort identity; variation evidence did not expand the cohort.
- Title remained listing evidence and was not treated as Buyer Need evidence.
- Keyword evidence was not relabeled as XiYou last-seven-days evidence.
- Buyer Need, Competition, Opportunity, and Product Intelligence missingness remained partial/explicit.
- No field promotion, NLP, pagination, sponsored semantics, scoring change, or complete-market claim was added.

## L. Artifacts

- Final run status: `FAILED`; final manifest stage: `COMPLETE`.
- Schema validation completed before delivery.
- `market_report.json`: 32,505 bytes; SHA-256 `a88ac1688d1cbb3beefa2dff5ce5111b9e63cb02747705619363ddbd6d4ff0df`; valid JSON.
- `operator_market_report.md`: 22,822 bytes; SHA-256 `a63dad11e257bd64b2cb0bf55c943c6033e0c795d5c28b43478cd464d1db29e7`; non-empty.
- `run_manifest.json`: 7,713 bytes; SHA-256 `e0c94fb2bc97a48d5bb3e289164356b7883380598d06ca4bfc8dcd012f0bfe18`; final stage complete.
- `operator_market_report.xlsx`: missing.
- Delivery failure code/type: `DELIVERY_FAILURE` / `OperatorReportExcelError`.
- Four-artifact gate: `FAILED`.
- All smoke files and checkpoints are in one fresh external temporary directory and are not committed.

Classification: `BLOCKED — PIPELINE_OR_ARTIFACT_GATE`.

## M. Secret safety

- External smoke files exact-credential matches: `0`.
- External smoke files high-risk Authorization/BasicAuth matches: `0`.
- No credential, Authorization header, raw response, checkpoint, smoke output, report body, XLSX, Markdown, stdout, or stderr log is committed.
- All activity after the unique Pipeline invocation was offline.

## N. Post-live focused/full regressions

- Post-live focused set: `901 passed, 16 skipped, 262 subtests`.
- Post-live full suite: `1 failed, 1340 passed, 16 skipped, 550 subtests`.
- All post-live tests were offline and introduced no new failure.

## O. Renderer baseline classification

The known `test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type` exception remains unchanged: expected OOXML package fingerprint begins `89ff`, while this environment produces `84e5`. R6 did not edit Renderer code, expectations, or business logic. The live `OperatorReportExcelError` is recorded separately without assuming an unproven causal equivalence.

## P. Git/diff/scan

`git diff --check`, staged diff review, repository exact-credential scan, high-risk Authorization/BasicAuth scan, and tracked/untracked review pass. Only this sanitized R6 validation record is committed; no live artifact or production-code change remains.

## Q. Final rollout gate state

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = False`.

The temporary live switch was restored immediately after the non-PASS result. Default provider remains XiYou, market-report-v0.2 live remains blocked, fallback remains absent, broader Sorftime marketplaces remain unavailable, and Batch remains XiYou-only.

## R. Deferred field promotions unchanged

Title remains the only newly promoted ProductRequest business field. Product Price/Brand/Rating/Review/Sales/Profit and other R3 fields remain capture-only. All 23 R5 keyword extensions remain capture-only. No sponsored or Buyer Need semantics were promoted.

## S. SP-040G handoff status

SP-040G was not started. R6 did not pass and provides no V0.2 live-acceptance handoff.

## T. Final verdict

`BLOCKED — PIPELINE_OR_ARTIFACT_GATE`

No retry, rerun, resume, direct diagnostic HTTP call, ProductVariations call, XiYou fallback, field expansion, R7 work, or SP-040G work was performed.
