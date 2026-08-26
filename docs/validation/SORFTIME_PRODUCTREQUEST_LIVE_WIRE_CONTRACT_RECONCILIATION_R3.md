# Sorftime ProductRequest Live Wire Contract Reconciliation R3

Issue: TASK-SP-040F-R3 / GitHub Issue #45

Date: 2026-08-26

Verdict: `PASS — SORFTIME_PRODUCTREQUEST_LIVE_WIRE_CONTRACT_RECONCILED`

## A. Baseline/runtime/workspace

- Required baseline: `a935e57b94a0630ce05c0e44d0476c04d0cd334a`.
- Dedicated branch: `codex/task-sp-040f-r3-productrequest-wire-repair`.
- The workspace and index were clean at the required baseline before R3 work.
- Runtime: Python 3.12.10 and pytest 9.0.3 on Windows PowerShell.

## B. R2 evidence

R2 recorded exactly one Pipeline invocation and one HTTP-200 ProductRequest transport attempt, followed by `SCHEMA_MISMATCH`. It made no keyword, ProductVariations, XiYou, fallback, retry, rerun, resume, or direct diagnostic call. The Sorftime V0.1 live gate was restored to disabled.

## C. Official casing audit

The current first-party Sorftime CLI page states that CLI/API data structures are equivalent and shows lowercase ProductRequest example fields such as `asin`, `title`, `sales`, and `trend`. That evidence was treated only as a hypothesis. It did not authorize a lowercase alias or a case-insensitive parser. The R3 ordinary-HTTP census instead observed PascalCase semantic names and zero casing aliases.

Sources: [GitHub Issue #45](https://github.com/gulongya-code/amazon-product-development/issues/45), [Sorftime CLI documentation](https://www.sorftime.com/zh-CN/cli).

## D. Offline structural diagnostic

Before network access, R3 added a scalar-free ProductRequest diagnostic. It retains only HTTP/envelope state, field names, JSON types, nullability, counts, casing candidates, request counters, parser result, failure kind, and failure path. It never retains response scalar values, headers, or credentials. Unsafe credential-like names and nested structures are redacted as a whole.

The pre-census focused offline set passed: `367 passed, 176 subtests`.

## E. Credential prerequisite

- Launch-process `SORFTIME_API_KEY` presence: `YES`.
- Windows User credential: `NOT READ`.
- CLI/MCP profiles: `NOT INSPECTED`.
- No credential value, length, hash, prefix, suffix, Authorization header, or account identifier was printed or persisted.

## F. Structural-census accounting

- ProductRequest structural-census calls: `1`.
- Fixed request: `ProductRequest`, domain `1`, `Trend=2`, authorized fixed ASIN only.
- HTTP status: `200`; provider `Code`: `0`.
- Provider-reported RequestConsumed: `1`; RequestLeft: `1343`.
- Retries: `0`.
- Pipeline live invocations: `0`.
- ASINRequestKeyword calls: `0`.
- ProductVariations calls: `0`.
- XiYou calls: `0`.
- Sorftime CLI calls: `0`.

The one-call budget is exhausted. No response body, scalar business value, response header, or raw artifact was persisted.

## G. Sanitized structural inventory

The committed census fixture groups exact field names that share the same observed type, nullability, and disposition. It contains no ASIN, title, price, seller, metric, or other business value.

- Envelope keys: `Code`, `Data`, `Message`, `RequestConsumed`, `RequestLeft`.
- Data root field count: `65`.
- VariationASIN count: `10`.
- Attribute row count: `10`; every row was an array of length `5`.
- Unsafe field count: `0`; casing aliases: `0`.
- Exact promoted strings: `Asin`, `ParentAsin`, `Title`.
- Exact promoted arrays: `Attribute`, `VariationASIN`.
- Exact promoted number: `VariationASINCount`.
- Exact promoted nulls: `ListPriceTrend`, `ListingSalesOfMonthTrend`, `ListingSalesVolumeOfMonthTrend`, `PriceTrend`, `RankTrend`.
- Proven array drift retained capture-only: `BsrRankTrend`, `DealTrend`.
- Proven missing/unavailable: `ListingSalesOfDaily`, `ListingSalesVolumeOfDaily`.
- Capture-only nulls: `ListingSalesOfDailyTrend`, `ListingSalesVolumeOfDailyTrend`.
- Capture-only booleans: `APlus`, `HasBrandStore`, `HasVideo`, `IsFBA`.
- Capture-only strings: `Brand`, `BrandPromotion`, `BuyboxSeller`, `BuyboxSellerAddress`, `BuyboxSellerId`, `DealType`, `Description`, `OnlineDate`, `ProductInfo`, `ProductType`, `Property`, `ShipsFrom`, `StoreName`, `UpdateDate`.
- Capture-only arrays: `BsrCategory`, `Category`, `EBCPhoto`, `ExtraSavings`, `FbaDetetail`, `Photo`, `ProductBadge`, `Size`.
- Capture-only object: `Feature`.
- Capture-only numbers: `AsinSalesCount`, `Coupon`, `FbaFee`, `FiveStartRatings`, `FourStartRatings`, `ListPrice`, `ListingSalesVolumeOfYear`, `OffSale`, `OneStartRatings`, `OnlineDays`, `PlatformFee`, `Price`, `Profit`, `ProfitRate`, `Rank`, `Ratings`, `RatingsCount`, `SalesPrice`, `SellerCount`, `ShipCost`, `ThreeStartRatings`, `TwoStartRatings`, `Weight`.

## H. Exact mismatch classification

- `WIRE_FIELD_CASING`: not observed.
- `SEMANTIC_FIELD_MISSING`: observed at `Data.ListingSalesOfDaily`; `Data.ListingSalesVolumeOfDaily` was also absent.
- Proven non-null shape drift: `Data.BsrRankTrend` and `Data.DealTrend` were arrays where the accepted Trend=2 semantic slice had only admitted null.
- Additional `ListingSalesOfDailyTrend` and `ListingSalesVolumeOfDailyTrend` fields were observed, but no semantic equivalence to the missing legacy names was proven.
- Envelope, ASIN identity, variation count, and Attribute row shape were structurally compatible.

## I. Normalization decision

No casing normalization was added. Only the two exact missing legacy names receive omission defaults. Only the two exact array-drift names receive a ProductRequest-local capture-only projection. Lowercase aliases, mixed-case duplicates, and unproven object/string/number shapes still fail closed. There is no globally case-insensitive parser.

## J. Missing/null/casing preservation

Missing daily fields are represented as `MISSING / UNAVAILABLE_MISSING`, not explicit null, in wire inventory. Their semantic DTO values remain unavailable. The two similarly named `*DailyTrend` fields remain distinct capture-only extensions. Exact null values remain `NULL`, and case drift remains a schema mismatch.

## K. Title boundary

`Title` remains the only newly promoted business field. Exact nonblank string maps at exact ASIN scope; explicit null or omission remains unavailable. No Title NLP, Buyer Need extraction, or variation-level title inference was added.

## L. Capture-only boundary

Price, brand, rating, reviews, sales, profit, fees, seller, category, images, dimensions, rank arrays, daily-trend extensions, and all other unapproved fields remain runtime/checkpoint capture-only. They do not enter the semantic DTO, Canonical observations, semantic fingerprints, capabilities, Intelligence inputs, or reports.

## M. DTO/mapper/Canonical result

The structural reproduction of the proven live shape now passes the wire parser. Missing daily fields map to unavailable; the two proven arrays remain in the immutable runtime sidecar; existing approved fields plus Title alone reach the strict semantic DTO. Mapper and Canonical identities remain deterministic and provider-qualified.

## N. Pipeline/recovery/XiYou non-regression

SP-040E fixture Pipeline/recovery, SP-040F gates, default XiYou behavior, provider-qualified checkpoints, Data Cleaning, Canonical normalization, and Batch XiYou-only behavior pass offline. R3 did not add fallback, retry, live resume, ProductVariations, or a new acquisition operation.

## O. Secret/network safety

The structural diagnostic and committed census were scanned for raw/value/header/credential markers and business scalar values. The credential and BasicAuth header did not appear in captured output or repository artifacts. All tests after the one census were offline.

## P. Focused/full regression result

- R3 DTO/wire/diagnostic focused set: `104 passed`.
- Provider/Pipeline/Data Cleaning/Canonical/Batch focused set: `283 passed, 5 skipped, 89 subtests`.
- Full suite: `1 failed, 1310 passed, 16 skipped, 550 subtests`.
- The sole failure is the unchanged Renderer baseline exception in `test_xlsx_delivery_v0_1.py`: expected OOXML package fingerprint begins `89ff`, actual begins `84e5`. R3 does not touch Renderer code or expectations.

## Q. Git/diff/secret scan

`git diff --check` and tracked/untracked file review pass. The process credential, derived BasicAuth value, and high-risk credential-pattern scans each found zero repository/diff matches. Only R3 diagnostic, narrow ProductRequest repair, sanitized structural fixture, tests, and this report are in scope.

## R. Final gate state

`_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = False`. Sorftime V0.1 live remains disabled. Default provider remains XiYou, market-report-v0.2 live remains blocked, and Batch remains XiYou-only.

## S. R4 readiness

The proven ProductRequest wire mismatch is reconciled offline, but R3 does not enable live execution and does not run a Pipeline smoke. Any R4 Pipeline live smoke requires separate authorization and must begin from this accepted commit.

## T. Final verdict

`PASS — SORFTIME_PRODUCTREQUEST_LIVE_WIRE_CONTRACT_RECONCILED`

R4 and SP-040G were not started.
