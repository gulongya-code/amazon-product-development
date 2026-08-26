# Sorftime V0.1 Offline XLSX Delivery and Replay R7

Issue: TASK-SP-040F-R7 / GitHub Issue #49

Date: 2026-08-26

Verdict: `PASS — SORFTIME_V0_1_RELEASE_OFFLINE_DELIVERY_REPLAY`

## A. Baseline/runtime/workspace

- Required baseline: `863b09ac28bc9dbfcea387765299d0261f8cdc24`.
- Dedicated branch: `codex/task-sp-040f-r7-offline-xlsx-delivery-repair`.
- The baseline workspace and staging area were clean before R7 work.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. Zero-provider-network prerequisite

- Sorftime calls: `0`.
- XiYou calls: `0`.
- Pipeline live invocations: `0`.
- Direct diagnostic HTTP calls: `0`.
- `SORFTIME_API_KEY`: `NOT READ`.
- Sorftime CLI/MCP/inactive profiles: `NOT INSPECTED`.
- No credential value, length, hash, prefix, suffix, Authorization header, or account identifier was printed or persisted.

## C. Exact offline reproduction

The R6 `market_report.json` and `run_manifest.json` were loaded locally, and the production `OperatorWorkflowBuilderV0_1` rebuilt the same workflow input used at delivery. Before the repair, `OperatorReportDelivery` reproduced:

- Exception: `OperatorReportExcelError`.
- Safe message: `artifact-tool node_modules is unavailable; configure MARKET_REPORT_NODE_MODULES`.
- Markdown written: `YES`.
- XLSX written: `NO`.
- Provider operations executed: `0`.

## D. Root-cause classification

- Report content: `NOT ROOT CAUSE`.
- Unavailable handling: `NOT ROOT CAUSE`.
- Workflow: `NOT ROOT CAUSE`.
- Artifact-tool runtime resolution: `ROOT CAUSE`.
- Windows junction/runtime execution: `NOT REACHED BEFORE FAILURE`.
- OOXML canonicalization: `NOT REACHED BEFORE FAILURE`.

The renderer required an explicitly configured `MARKET_REPORT_NODE_MODULES` path even though the bundled workspace runtime contained a valid Node executable and `@oai/artifact-tool` package. The failure occurred before template execution, cell authoring, junction creation, XLSX export, or OOXML canonicalization.

## E. Provider-neutral repair

- Explicit Node and node_modules configuration remains highest priority.
- An explicit node_modules directory is now accepted only when it contains `@oai/artifact-tool/package.json`; incomplete configuration remains a hard failure.
- With no explicit configuration, the renderer checks only bounded workspace runtime locations and accepts only a complete Node plus artifact-tool pairing.
- System Node remains the final executable fallback; node-relative dependency roots are checked deterministically.
- No Provider, DTO, Canonical, Intelligence, Buyer Need, scoring, report semantic, or golden-hash logic changed.

## F. Synthetic regression fixture

A sanitized, provider-neutral partial-report workflow fixture covers two logical/transport operations, null credits, and unavailable competition data. It proves that the repaired delivery path creates a real OOXML workbook with an Operator Summary and explicit `UNAVAILABLE` cells without depending on credentials, provider transports, or live values.

## G. Direct R6 report/workflow acceptance

- Source: existing external R6 report, manifest, and checkpoints only.
- Fresh destination: `YES`.
- R6 source directory immutable before/after: `YES`.
- XLSX signature and package: valid OOXML `PK` package.
- Required sheets: Operator Summary, Market Overview, Buyer Need Analysis, Competition Analysis, Opportunity Analysis.
- Markdown deterministic against the R6 original: byte-identical.
- Formula error scan through artifact-tool: `0` matches.
- Artifact-tool visual preview: all five sheets rendered and visually inspected; no severe clipping, blank-sheet, or unreadable-format defect.
- No R6 live artifact, checkpoint, report body, workbook, Markdown, or manifest is committed.

## H. Zero-network checkpoint replay

The R6 checkpoint source was replayed into a fresh destination through the production orchestrator. The test harness used a sentinel-only Sorftime provider composition whose transport raises on any execute. The harness relaxed only the production live-resume prohibition and live fresh-execution usage gate; all ordinary request validation and checkpoint fingerprint/integrity checks remained active.

- Status: `SUCCEEDED`.
- Requested/resolved ASINs: `1/1`.
- Executed provider operations: `0`.
- Replayed provider operations: `2`.
- Provider transport attempts: `0`.
- Forbidden transport execute count: `0`.
- Source R6 directory immutable before/after: `YES`.
- Recovery manifest executed/replayed counts: `0/2`.

The harness is external and uncommitted; production live resume remains prohibited.

## I. Replay artifact acceptance

The fresh replay destination contains exactly the four normal artifacts:

- `market_report.json`
- `operator_market_report.xlsx`
- `operator_market_report.md`
- `run_manifest.json`

Every manifest artifact path exists. The output destination is external and uncommitted.

## J. Usage and credit separation

- Provider: `sorftime`.
- Usage unit: `REQUEST`.
- Executed requests during replay: `0`.
- Replayed operations are not rebilled as executed requests.
- Credits: null; credit semantics: null.
- No XiYou credit field received Sorftime Request usage.

## K. Canonical and downstream boundary

- No Canonical, Data Cleaning, Intelligence, Buyer Need, Competition, Opportunity, scoring, or report-content implementation changed.
- Title remains the only newly promoted ProductRequest business field.
- Other ProductRequest fields remain capture-only.
- The 23 R5 keyword extensions remain capture-only.
- No sponsored semantics, pagination, field promotion, or complete-market claim was added.

## L. Provider and product boundaries

- Default provider remains `xiyou`.
- Explicit Sorftime selection remains required.
- No Sorftime-to-XiYou fallback exists.
- Market Report V0.2 live remains blocked.
- Batch remains XiYou-only.
- ProductVariations remains absent from the production Sorftime acquisition plan.

## M. Focused regressions

- R3/R5/Sorftime/Pipeline/Batch/Operator delivery focused set: `121 passed, 5 skipped, 48 subtests`.
- Final post-format Sorftime/Pipeline/Operator delivery set: `70 passed, 44 subtests`.
- Operator delivery module alone: `8 passed`.
- All tests were offline.

## N. Full regression

- Full suite: `1 failed, 1346 passed, 13 skipped, 550 subtests`.
- The sole failure is the unchanged required-baseline exception in `test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`: this Windows runtime produces OOXML package fingerprint `84e5...`, while the governed golden begins `89ff...`.
- R7 did not edit that renderer, its OOXML package content, or the golden hash. The Issue prohibition against changing a golden hash to conceal the mismatch was preserved.
- No new regression was introduced.

## O. Secret and live-data safety

- Changed-file high-risk credential pattern matches: `0`.
- External direct/replay artifact files scanned: `13`.
- External secret-marker matches: `0`.
- No exact-credential comparison was attempted because the credential was not read.
- No raw provider response, live checkpoint, live report body, workbook, Markdown, manifest, preview, or business scalar is tracked or committed.

## P. Source immutability and output isolation

- R6 source tree fingerprint matched before and after direct delivery.
- R6 source tree fingerprint matched before and after checkpoint replay.
- Direct delivery and replay used separate fresh external temporary destinations.
- No test or repair wrote into the R6 source directory.

## Q. Git/diff gate

`git diff --check`, changed-file secret scan, untracked-file review, focused test review, and full diff review pass. The only JSON addition is the sanitized provider-neutral R7 regression fixture. No XLSX or live artifact is in the worktree.

## R. Final rollout gate state

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = True`.

Sorftime V0.1 remains available only through explicit `provider=sorftime + mode=live + market-report-v0.1` within the existing ASIN/marketplace/retry/usage gates. Default XiYou, V0.2 live block, Batch XiYou-only, and no-fallback behavior remain unchanged.

## S. SP-040G status

SP-040G was not started. R7 contains no V0.2 live work or semantic expansion.

## T. Final verdict

`PASS — SORFTIME_V0_1_RELEASE_OFFLINE_DELIVERY_REPLAY`

The sole R6 delivery blocker is repaired and proven through direct R6 XLSX acceptance plus zero-network two-checkpoint Pipeline replay. Sorftime V0.1 live is enabled; no Provider request was made in R7.
