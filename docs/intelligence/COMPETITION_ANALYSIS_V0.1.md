# Competition Analysis V0.1

Status: TASK-SP-021B implemented and XiYou live-validated
Validation date: 2026-08-19

## 1. Purpose and boundary

Competition Analysis V1 turns Provider-neutral `CleanCanonicalResult` values into a
deterministic `CompetitionAnalysisResult`:

```text
Provider response
-> Provider Adapter
-> Canonical Evidence
-> Normalization / Cleaning
-> Competition Analysis V1
```

The analysis never parses XiYou payloads. XiYou-specific root/envelope and field-name
handling stays in the connector/adapter. The result describes a bounded observed
competition sample; it does not declare a governed Comparable Product set or a market
census.

## 2. Input and result contract

`CompetitionAnalysisRequest` contains:

- one normalized marketplace;
- zero or more unique `CleanCanonicalResult` runs.

`CompetitionAnalysisResult` contains:

- deterministic analysis/version/calculation identities;
- the reused Market Analysis scope and Calculation Engine observed-product count;
- rating and review-count summaries reused from Market Analysis V1;
- zero or more exact-context BSR summaries;
- explicit variation relationship records and separate structure grains;
- source quality/completeness, blocked metrics, and complete calculation provenance;
- a reference to the deterministic base `MarketAnalysisResult`.

The result type and formulas are Provider-neutral. A future provider can participate by
producing the same clean Canonical fields with valid provenance.

## 3. Supported metrics and formulas

### 3.1 Observed product count

`workbook.market_overview.observed_product_count` reuses
`calculation.observed_product_count`. The input set is the distinct validated product
identities in the clean scope, including explicit variation parent/child identities.
The value is an observed-scope count, not Comparable membership and not market size.

### 3.2 Rating and review count

The existing summaries are reused without a second formula:

- `market_analysis.product_rating`;
- `market_analysis.product_review_count`.

For each metric, the valid values are sorted and calculated with decimal precision 28
and round-half-even:

```text
minimum = first(sorted values)
maximum = last(sorted values)
mean = sum(values) / valid_sample_count
median = middle value, or mean of the two middle values
```

Each output includes total subjects, valid samples, every exclusion class, status,
unit, limitations, source observation IDs, and calculation provenance.

### 3.3 BSR

BSR is grouped only when the following full context is present and identical:

```text
marketplace
category ID
category name
root/non-root rank type
source date
date precision
rank unit/system
```

Each exact context gets an independent min/max/mean/median summary using the same
decimal formula. Different categories, dates, root flags, or rank units are never
combined. Multiple valid candidates for one product in one exact context block that
context instead of selecting by order.

### 3.4 Variation structure

Only confirmed, normalized explicit parent-to-child relationships are included. The
result exposes these mechanically distinct quantities:

- source relationship record count;
- unique parent/child pair count;
- unique parent count;
- unique child count;
- duplicate source record count;
- clean runs carrying incomplete-family diagnostics.

These quantities are intentionally not projected into
`workbook.competition_evidence.variation_evidence_count` because the approved business
grain for that field remains unresolved.

## 4. Quality rules

- missing, explicit null, unknown, invalid, and zero are distinct;
- zero is included when valid;
- invalid values are excluded, never converted to zero;
- multiple candidates for one subject/context block unsafe aggregation;
- rank context/unit differences create separate groups or block aggregation;
- a partial record does not remove valid sibling records;
- empty input returns `EMPTY`; no statistic is fabricated as zero;
- small samples remain calculated only with explicit `SMALL_SAMPLE_SIZE_LT_2` and
  partial status.

An analysis can be `PARTIAL` while still carrying safe metric results. This is expected
for bounded competition samples with incomplete rating/review/BSR coverage.

## 5. Provenance

Every calculated metric traces through:

```text
Competition metric
-> calculation rule/version/run
-> CleanCanonicalResult field
-> normalization application/provenance
-> Canonical observation and Raw Evidence reference
-> adapter mapping version/source field
-> XiYou operation/provider
```

BSR calculation lineage additionally contains the exact context. Variation records
retain the Canonical provenance of each explicit edge. `CompetitionAnalysisResult` is
system-derived; it is never labelled as a provider conclusion.

## 6. Live validation

On 2026-08-19, credential state was `CONFIGURED`. A bounded script protected by the
explicit `--live` gate made exactly three no-retry XiYou requests and consumed nine
credits reported by response headers:

1. one `/v1/asins/info` request for three public US ASINs;
2. one `/v1/asins/variations` request for one of those ASINs;
3. one `/v1/asins/bsrInfo/trends/daily` request for one ASIN and one date.

No complete response, credential, authorization header, account data, or unsanitized
fixture was saved.

### 6.1 Actual schema and quality observations

- Product info used the direct root `entities[]` contract.
- The three product rows used `price`/`stars` as numeric strings or explicit null and
  `ratings` as integer or explicit null.
- One row had empty title and null price/rating/review count. The other two valid rows
  were retained.
- Variation used the direct root and returned one explicit parent plus six unique
  children. The bounded observed identity inventory therefore contained seven unique
  products, even though only three ASINs were requested for product info.
- BSR used the direct root `categoryTree[]` plus `trends[].values[]` structure and
  returned two categories for one product/date.
- No seller or offer identity was present.

### 6.2 Mechanical recalculation

| Metric/context | Valid | Excluded | Produced | Independent | Match |
|---|---:|---:|---|---|---|
| Observed product count | 7 | 0 | 7 | 7 | YES |
| Rating | 2 | 5 | min/max/mean/median = 4.9 | same | YES |
| Review count | 2 | 5 | min/max/mean/median = 21 | same | YES |
| Ball Valves BSR | 1 | 6 | min/max/mean/median = 24 | same | YES |
| Industrial & Scientific root BSR | 1 | 6 | min/max/mean/median = 10531 | same | YES |

The two BSR values were deliberately not averaged together. All successful comparisons
matched for count, min, max, mean, median, valid sample count, and excluded count.
Sample sizes are too small for reliable market conclusions; this validation proves the
pipeline and quality behavior only.

### 6.3 Real-data fixes

- Production variation and BSR operations now use distinct current direct-root mapping
  versions with truthful source fields.
- Clean fields preserve exact BSR rank context and explicit variation parent/child IDs.
- `product.variation` uses the existing canonical ASIN normalization rule.
- `metric.bsr_context` is context-only metadata carried on `metric.bsr`; it no longer
  creates a duplicate unsupported scalar field.
- Market/competition observed identity scope includes explicit variation endpoints.

## 7. Blocked and excluded metrics

| Metric | State | Reason |
|---|---|---|
| Seller count | BLOCKED | Official/live contracts did not expose confirmed seller identity. |
| Variation Evidence Count | BLOCKED | Record, edge, and unique-variant grains are not governed. |
| Minimum/maximum comparable price | BLOCKED | No governed `COMPARABLE` membership source exists. |
| Competition Score | OUT OF SCOPE | No new score formula is approved for V1. |
| Opportunity Score | OUT OF SCOPE | Existing scoring was not changed. |
| Trend | OUT OF SCOPE | No trend window/direction formula is introduced. |

AI, Workbook redesign, Sorftime/SellerSprite integration, Comparable Product
membership, and speculative competition-strength formulas are not part of V1.

## 8. Reproduction and network safety

The bounded live validation command is:

```powershell
python scripts/live_validate_competition_v0_1.py --live
```

Without `--live`, the script exits before constructing a production request. It uses
one attempt per operation. Ordinary tests use injected static transports and make zero
production network requests.
