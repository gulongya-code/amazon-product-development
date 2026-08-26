# Sorftime V0.1 Live Smoke R4

Issue: TASK-SP-040F-R4 / GitHub Issue #46

Date: 2026-08-26

Verdict: `BLOCKED — KEYWORD_PROVIDER_CONTRACT`

## A. Baseline/runtime/workspace

- Required baseline: `0077fdf2c26e80d864392dac2472467d8847ec5b`.
- Dedicated branch: `codex/task-sp-040f-r4-sorftime-live-smoke`.
- The baseline workspace and staging area were clean before R4 work.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. Credential prerequisite

- Launch-process `SORFTIME_API_KEY` presence: `YES`.
- Windows User credential: `NOT READ`.
- CLI/MCP/inactive profiles: `NOT INSPECTED`.
- No credential value, length, hash, prefix, suffix, Authorization header, or account identifier was printed or persisted.

## C. Offline preflight

- R3/Sorftime/Provider/Pipeline/Data Cleaning/Canonical/Intelligence/Report/Operator/Batch focused set: `776 passed, 16 skipped, 197 subtests`.
- Full required-baseline suite: `1 failed, 1310 passed, 16 skipped, 550 subtests`.
- The sole failure was the already-recorded Renderer OOXML package fingerprint exception.
- Static plan: exactly `ProductRequest(Trend=2)` followed by `ASINRequestKeyword(PageIndex=1, PageSize=20)` for one ASIN.
- `ProductVariations` was absent from the plan; the pinned origin, `NoRetryPolicy`, `max_attempts=1`, default XiYou, V0.2 live block, and Batch XiYou-only boundaries were verified.
- Repository credential and derived BasicAuth scans found zero matches.
- Automated preflight tests made zero Provider network calls.

Two local harness setup failures occurred before the live invocation: one unsupported PowerShell directory parameter and one Python import-order cycle. Both stopped before constructing or calling `ProductionPipelineOrchestrator.run`; therefore they consumed zero Pipeline invocations and zero HTTP operations. A subsequent import-only offline check passed.

## D. Live invocation accounting

- Production Pipeline live invocations: `1`.
- Fixed marketplace/ASIN/category: `US` / authorized fixed ASIN / `dog water bottle`.
- ProductRequest logical operations: `1`; transport attempts: `1`; HTTP `200`.
- ASINRequestKeyword logical operations: `1`; transport attempts: `1`; HTTP `200`.
- Retries: `0`.
- Reruns: `0`.
- Live resumes: `0`.
- ProductVariations: `0`.
- XiYou: `0`.
- Fallback: `0`.
- Direct/ad-hoc Sorftime diagnostic HTTP calls: `0`.
- Sorftime CLI live calls: `0`.

The live phase ended after the ASINRequestKeyword strict provider path failed. No additional request was issued.

## E. ProductRequest HTTP/wire/DTO result

- Transport: HTTP `200`.
- Provider envelope: `Code=0`, `RequestConsumed=1`, `RequestLeft=1342`.
- R3 wire parser: accepted.
- Live field casing: exact PascalCase; casing aliases: `0`.
- Proven missing fields: `ListingSalesOfDaily`, `ListingSalesVolumeOfDaily`; both remained unavailable rather than zero.
- `BsrRankTrend` and `DealTrend` arrays remained capture-only.
- `ListingSalesOfDailyTrend` and `ListingSalesVolumeOfDailyTrend` remained distinct capture-only extensions.
- ProductRequest logical operation status: `SUCCEEDED` with one successful checkpoint.

## F. Safe ProductRequest inventory result

The live inventory matched the R3 reconciled 65-field structure plus two explicit missing-state inventory entries:

- Promoted strings: `Asin`, `ParentAsin`, `Title`.
- Promoted arrays: `Attribute`, `VariationASIN`.
- Promoted number: `VariationASINCount`.
- Promoted nulls: `ListPriceTrend`, `ListingSalesOfMonthTrend`, `ListingSalesVolumeOfMonthTrend`, `PriceTrend`, `RankTrend`.
- Missing/unavailable: `ListingSalesOfDaily`, `ListingSalesVolumeOfDaily`.
- Capture-only arrays: `BsrCategory`, `BsrRankTrend`, `Category`, `DealTrend`, `EBCPhoto`, `ExtraSavings`, `FbaDetetail`, `Photo`, `ProductBadge`, `Size`.
- Capture-only nulls: `ListingSalesOfDailyTrend`, `ListingSalesVolumeOfDailyTrend`.
- Capture-only booleans: `APlus`, `HasBrandStore`, `HasVideo`, `IsFBA`.
- Capture-only object: `Feature`.
- Capture-only strings: `Brand`, `BrandPromotion`, `BuyboxSeller`, `BuyboxSellerAddress`, `BuyboxSellerId`, `DealType`, `Description`, `OnlineDate`, `ProductInfo`, `ProductType`, `Property`, `ShipsFrom`, `StoreName`, `UpdateDate`.
- Capture-only numbers: `AsinSalesCount`, `Coupon`, `FbaFee`, `FiveStartRatings`, `FourStartRatings`, `ListPrice`, `ListingSalesVolumeOfYear`, `OffSale`, `OneStartRatings`, `OnlineDays`, `PlatformFee`, `Price`, `Profit`, `ProfitRate`, `Rank`, `Ratings`, `RatingsCount`, `SalesPrice`, `SellerCount`, `ShipCost`, `ThreeStartRatings`, `TwoStartRatings`, `Weight`.

No scalar business value is retained in this record.

## G. Title mapping result

- Title presence: `YES`.
- Canonical `title` fact count: `1`.
- Exact requested-product scope: `YES`.
- Variation identity copies: `0`.
- The title scalar was not printed or copied into this validation record.

## H. ASINRequestKeyword result

- Request shape: exact fixed ASIN, `PageIndex=1`, `PageSize=20`.
- Transport: one attempt, HTTP `200`.
- Strict provider path: `SCHEMA_MISMATCH`.
- Logical operation status: `FAILED`.
- Resolver attempts: `1`; provider: `sorftime`; no retry.
- No successful keyword checkpoint or typed row count was available.

Classification: `BLOCKED — KEYWORD_PROVIDER_CONTRACT`.

Per Issue #46, R4 did not relax the DTO, rerun the Pipeline, resume, or issue a diagnostic request.

## I. Usage accounting

- Unit: `REQUEST`.
- Semantics: `LIVE_PROVIDER_REPORTED`.
- Confirmed accepted-envelope consumed total: `1`.
- Confirmed remaining: `1342`.
- Credits: null.
- Credit semantics: null.

Only the accepted ProductRequest envelope was confirmed. The HTTP-200 keyword response failed strict parsing and was therefore not counted or checkpointed. Prior R3 census usage was not included.

## J. Canonical/Data Cleaning result

ProductRequest produced the approved Canonical slice and exactly one title fact during provider adaptation. The Pipeline failed in acquisition before Data Cleaning; requested/resolved counts were `1/0`. No keyword Canonical relationship bundle was accepted.

## K. Downstream truthfulness

All stages after acquisition were skipped. No title NLP, Buyer Need inference, complete-universe claim, sponsored inference, economics zero-fill, XiYou period relabeling, or capture-only field promotion occurred.

## L. Artifacts

- Final run status: `FAILED`.
- Final manifest stage: `COMPLETE`.
- Managed top-level artifact: `run_manifest.json`, 6020 bytes, SHA-256 `1fd234a5b16dc9ba6d2a1e607fde7c652faacb87720498e35c67f801cc1a9298`.
- One ProductRequest checkpoint was created locally.
- `market_report.json`, XLSX, and Markdown were not created because acquisition failed before report construction.
- The smoke output directory is outside the repository and is not committed.

## M. Secret safety

Captured process output, local smoke files, repository files, and the diff were checked without printing the secret. Credential-value and derived BasicAuth matches were zero. No raw live response, checkpoint, smoke output, stdout/stderr log, report artifact, credential, or Authorization header is committed.

## N. Post-live focused/full regressions

- Post-live focused set: `776 passed, 16 skipped, 197 subtests`.
- Post-live full suite: `1 failed, 1310 passed, 16 skipped, 550 subtests`.
- The only full-suite failure is the unchanged Renderer baseline exception described below.
- All post-live tests were offline and introduced no new failure.

## O. Renderer baseline classification

The known `test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type` exception remains out of scope: expected OOXML package fingerprint begins `89ff`, while this environment produces `84e5`. R4 does not edit Renderer code or expectations.

## P. Git/diff/secret scan

`git diff --check` and tracked/untracked review pass. Repository credential-value, derived BasicAuth, and high-risk diff-pattern scans each found zero matches. The production orchestrator has zero final diff lines, proving the live gate was restored. Only this sanitized R4 validation record remains as the R4 task diff.

## Q. Final rollout gate state

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = False`.

Sorftime V0.1 live was restored to disabled because R4 did not pass. Default provider remains XiYou, market-report-v0.2 live remains blocked, fallback remains absent, and Batch remains XiYou-only.

## R. Deferred field promotions unchanged

Title remains the only newly promoted business field. Price, brand, rating, reviews, sales, profit, fees, rank arrays, seller, category, images, and all other R3 capture-only fields remain unpromoted. No new NLP or business semantics were added.

## S. SP-040G handoff status

SP-040G was not started. R4 did not pass and provides no V0.2 live-acceptance handoff.

## T. Final verdict

`BLOCKED — KEYWORD_PROVIDER_CONTRACT`

No rerun, resume, retry, direct diagnostic request, contract relaxation, R5 work, or SP-040G work was performed.
