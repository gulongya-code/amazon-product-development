# Sorftime V0.1 Live Smoke R2

Issue: TASK-SP-040F-R2 / GitHub Issue #44

Date: 2026-08-26

Verdict: `BLOCKED — PRODUCTREQUEST_PROVIDER_CONTRACT`

## A. Baseline/runtime/workspace

- Required baseline: `e258330730dce06a5ec9d16fa08062d38c98fc52`.
- Dedicated branch: `codex/task-sp-040f-r2-sorftime-live-smoke`.
- The baseline workspace and staging area were clean before edits or network access.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. Credential prerequisite

- Launch-process `SORFTIME_API_KEY` presence: `YES`.
- Windows User value: `NOT CHECKED`, because the launch process already had the variable.
- In-process bridge: `NOT NEEDED`.
- No value, length, hash, prefix, suffix, profile, MCP credential, header, or account identifier was printed or persisted.

## C. Offline preflight

- R1/Sorftime/Production Pipeline/provider/Canonical/Data Cleaning focused set: `357 passed, 176 subtests`.
- Full baseline: `1 failed, 1289 passed, 16 skipped, 550 subtests`.
- The sole failure was the already-recorded Renderer OOXML package fingerprint exception.
- The plan was exactly `ProductRequest(Trend=2)` followed by `ASINRequestKeyword(PageIndex=1, PageSize=20)` for one ASIN.
- `NoRetryPolicy`, `max_attempts=1`, pinned Sorftime origin, Sorftime-only runtime, V0.2 live block, default XiYou, and Batch XiYou-only constraints were verified before network access.
- Automated preflight tests made zero provider calls.

## D. Live invocation accounting

- Production Pipeline live invocations: `1`.
- Fixed ASIN: `B09265WXY5`.
- ProductRequest transport attempts: `1`.
- ASINRequestKeyword transport attempts: `0`.
- Retries: `0`.
- Reruns: `0`.
- Live resumes: `0`.
- ProductVariations: `0`.
- XiYou: `0`.
- Fallback: `0`.
- Direct/ad-hoc Sorftime diagnostic HTTP calls: `0`.
- Sorftime CLI live calls: `0`.

The live phase stopped immediately after the first operation failed. All subsequent inspection was local and offline.

## E. ProductRequest HTTP/wire/DTO result

- Transport result: HTTP 200 on the single ProductRequest attempt.
- Resolver result: `FAILED / SCHEMA_MISMATCH`.
- Pipeline result: `PROVIDER_FAILURE` at provider resolution.
- The typed ProductRequest response was not accepted, so the R1 rich-wire repair could not be declared live-proven.
- No raw live response was committed, reconstructed, or retained as validation evidence.

Classification: `BLOCKED — PRODUCTREQUEST_PROVIDER_CONTRACT`.

## F. Live ProductRequest field inventory

Unavailable. The response did not pass the ProductRequest wire/semantic boundary, and no successful checkpoint was written. Issuing another call to obtain field names or types was forbidden, so no live inventory is claimed.

## G. Title live mapping result

Unavailable. ProductRequest did not produce an accepted semantic response; no Canonical title fact was emitted or inspected, and no title value was logged.

## H. ASINRequestKeyword result

Not started. The Pipeline stopped after ProductRequest failed, preserving the hard sequential stop rule.

## I. Usage accounting

- Provider usage unit: `REQUEST`.
- Usage semantics: `LIVE_PROVIDER_REPORTED`.
- Accepted `consumed`: unavailable/null.
- Accepted `remaining`: unavailable/null.
- Credits: null.
- Credit semantics: null.

The HTTP response was not accepted by the typed boundary, so its counters were not counted. The required consumed total of 2 was not met and no balance subtraction was used.

## J. Canonical/Data Cleaning result

No Canonical or Data Cleaning result was produced. Requested/resolved ASINs were `1/0`; acquisition and all downstream stages were skipped.

## K. Downstream truthfulness

No downstream business logic changed. No title, price, brand, rating, sales, profit, keyword, demand, economics, or market-universe statement was synthesized from the failed live response.

## L. Artifacts

The failed run produced only the managed `run_manifest.json`. No Market Report JSON, XLSX, or Markdown was produced. The failure manifest records one ProductRequest operation, one HTTP 200 transport attempt, zero replay, zero checkpoint, and skipped downstream stages.

The local smoke directory remains outside the repository and is not committed.

## M. Secret safety

Captured stdout/stderr and all local smoke files were scanned against the process credential without printing it. Credential-value matches, Authorization BasicAuth header matches, and credential label/value matches were all zero. The output contained no checkpoint files. Repository records contain only allowlisted classifications and counters.

## N. Post-live focused/full regressions

- Post-live focused set: `357 passed, 176 subtests`.
- Post-live full suite: `1 failed, 1289 passed, 16 skipped, 550 subtests`.
- No new regression was introduced.
- All post-live tests were offline.

## O. Renderer baseline classification

The only full-suite failure remains `test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`: expected OOXML package fingerprint begins `89ff`, actual begins `84e5`. This is unchanged from the required baseline and was not edited away.

## P. Git/diff/secret scan

The production live-switch edit used for the controlled invocation was restored. The final production tree therefore keeps the baseline gate disabled. `git diff --check`, staged diff inspection, and repository secret-pattern scanning pass; only this sanitized validation record is committed for R2.

## Q. Final rollout gate state

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = False`.

Explicit Sorftime V0.1 live remains disabled. Default provider remains XiYou, market-report-v0.2 live remains blocked, no fallback was added, and Batch remains XiYou-only.

## R. Deferred field promotions unchanged

Price, brand, rating, reviews, sales, profit, and every other R1 capture-only candidate remain unpromoted. No Title NLP or Buyer Need title extraction was added.

## S. SP-040G handoff status

SP-040G was not started. R2 did not pass, so there is no V0.2 Full Live Acceptance handoff from this task.

## T. Final verdict

`BLOCKED — PRODUCTREQUEST_PROVIDER_CONTRACT`

No rerun, resume, extra diagnostic API call, SP-040G work, or semantic expansion was performed.
