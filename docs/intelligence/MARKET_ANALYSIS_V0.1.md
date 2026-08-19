# Market Analysis V0.1

Status: implemented; Provider-neutral fixture and XiYou live validation complete

## 1. Purpose and boundary

Market Analysis V1 converts already-clean Canonical data into a deterministic,
structured analysis result:

```text
Provider Data
  -> Data Cleaning V1
  -> CleanCanonicalResult
  -> MarketAnalysisBuilderV0_1
  -> MarketAnalysisResult
```

The layer produces bounded observed-sample statistics. It does not claim total market
coverage, select comparable products, resolve Provider candidates, score opportunities,
project trends, or make recommendations.

## 2. Inputs

`MarketAnalysisRequest` contains:

- one normalized marketplace;
- zero or more unique `CleanCanonicalResult` values from that marketplace.

The builder uses only clean fields, Canonical subjects, quality issues, normalization
statuses, units, and provenance already present at the Cleaning boundary. It does not read
Provider payloads or call a Connector. `CleanFieldResult.subject` carries the original
Canonical `SubjectRef`; Market Analysis never parses Provider locators or titles to invent
product identity.

An empty input is valid as a controlled state. It returns `EMPTY`, a missing observed-product
count, missing numeric summaries, and the `NO_CLEAN_RESULTS` limitation. It never returns a
fabricated zero-product market conclusion.

## 3. Result contract

`MarketAnalysisResult` contains:

- deterministic `analysis_id`, version, analysis status, and calculation run ID;
- `MarketAnalysisScope` with marketplace, snapshot time, clean run IDs, observed Canonical
  product IDs, observed Canonical keyword IDs, and source Providers;
- existing Calculation Engine count results;
- typed numeric summaries with samples, exclusions, units, and calculation provenance;
- aggregate Cleaning quality/completeness;
- original unique `DataQualityIssue` values;
- explicit blocked metrics and their missing dependencies.

Stable sort order and deterministic content fingerprints make replay independent of clean
field ordering. Full raw Provider responses are not included.

## 4. Supported metrics and formulas

### 4.1 Observed product count

| Result field | Existing rule | Dependency | Unit | Missing policy |
|---|---|---|---|---|
| `workbook.market_overview.observed_product_count` | `calculation.observed_product_count` | Sorted unique Canonical `product:<marketplace>:<asin>` identities in the explicit clean snapshot | count | No validated product identity means `MISSING_INPUT`, not zero. |

This reuses the audited Calculation Engine evaluator. It is a bounded observed-set count,
never total market size.

### 4.2 Numeric observed-sample summaries

For one supported Canonical numeric field, let `S` be the values that remain after the
quality and compatibility gates below, and let `n = |S|`.

```text
minimum = min(S)
maximum = max(S)
mean    = sum(S) / n
median  = middle(sorted(S)) when n is odd
median  = (lower_middle + upper_middle) / 2 when n is even
```

Decimal arithmetic uses a fixed 28-significant-digit, half-even context. Serialized
decimals use a deterministic non-exponent form. `n >= 1` is mathematically sufficient to
emit the distribution, but `n < 2` is marked `PARTIAL` with
`SMALL_SAMPLE_SIZE_LT_2`; it is not presented as a reliable market conclusion.

| Market metric | Canonical input | Compatibility gate | Meaning |
|---|---|---|---|
| `market_analysis.observed_product_price` | `metric.price` | Every included value has the same explicit ISO currency | Distribution of observed clean price candidates in the explicit sample; **not** comparable-product price. |
| `market_analysis.product_rating` | `metric.rating` | One compatible explicit rating unit | Distribution of observed product ratings. |
| `market_analysis.product_review_count` | `metric.review_count` | One compatible explicit count unit | Distribution of listing review-count evidence; zero is valid. |
| `market_analysis.keyword_cpc` | `keyword.cpc` | Every included value has the same explicit ISO currency | Distribution of clean keyword CPC observations. |
| `market_analysis.keyword_aba_rank` | `keyword.aba_rank` | One compatible explicit ABA-rank unit | Distribution of clean ABA rank observations in the supplied scope. |
| `market_analysis.keyword_search_volume` | `keyword.search_volume` | One compatible explicit period/count unit and confirmed semantics with no blocking method issue | Distribution only when the Provider mapping confirms usable search-volume semantics. Current XiYou method-unconfirmed evidence remains blocked. |

No Candidate winner is selected. If one subject has multiple clean candidates for the same
metric, the summary is `BLOCKED` with `MULTIPLE_CANDIDATES_BLOCKED`; values are not averaged.

## 5. Quality and completeness rules

Every numeric summary exposes:

- `total_subject_count` and `valid_sample_count`;
- excluded missing, explicit-null, unknown, invalid, candidate-conflict, and unit-mismatch
  counts;
- included partial-input count;
- source observation IDs and related quality issue IDs;
- limitations and `CALCULATED`, `PARTIAL`, `MISSING`, or `BLOCKED` status.

Rules:

1. `MISSING`, `EXPLICIT_NULL`, and `UNKNOWN` never become zero.
2. Numeric zero is a present valid input.
3. `INVALID`, failed normalization, or blocking field quality does not participate.
4. A valid subset may calculate as `PARTIAL`; every exclusion remains counted.
5. No valid sample returns `MISSING` when all inputs are absent, or `BLOCKED` when invalid,
   unknown, conflicting, or incompatible evidence prevents use.
6. Currency/unit conversion is not performed. Mixed or missing units block the metric.
7. One subject contributes at most one value to a product/keyword summary.
8. A partial Provider capability may contribute a clean confirmed value, but the summary
   remains `PARTIAL` and records `PARTIAL_INPUTS_INCLUDED`.

The result-level quality summary mechanically aggregates source clean-run status, field
presence/validity, unique quality issues, and observed product/keyword subject counts. It
is not a confidence score.

## 6. Provenance

Each successful numeric summary uses the existing `CalculationProvenance` and
`CalculationInputLineage` contracts:

```text
Market numeric summary
  -> market_analysis.* calculation rule / v0.1-observed-summary
  -> calculation run and deterministic input/output fingerprints
  -> CleanFieldResult observation ID and normalized value
  -> normalization status, unit, and DataQualityIssue IDs
  -> Canonical Provenance and TransformationProvenance
  -> raw evidence reference
  -> Provider and source operation/field
```

Observed product count retains the Calculation Engine's normal provenance over the
authoritative Canonical product-identity collection. Market outputs are therefore
system-derived; they are not labeled as values supplied directly by XiYou, Sorftime, or
another Provider.

## 7. Explicitly blocked metrics

| Metric | Status/reason | Required decision or dependency |
|---|---|---|
| Product Structure Product Count | `EXACT_PRODUCT_TYPE_GROUP_UNAVAILABLE` | An approved exact product-type group membership source. |
| Product Structure Member Product IDs | `EXACT_PRODUCT_TYPE_GROUP_UNAVAILABLE` | The same exact group; analysis-scope membership is not silently reinterpreted as product type. |
| Product Structure Observed Share | `EXACT_PRODUCT_TYPE_GROUP_UNAVAILABLE` | Approved group identities contained in the explicit observed snapshot. |
| Minimum Comparable Price | `BLOCKED_BY_MEMBERSHIP_SOURCE` | Governed Comparable Product Set `COMPARABLE` membership plus compatible resolved prices. |
| Maximum Comparable Price | `BLOCKED_BY_MEMBERSHIP_SOURCE` | Same governed comparable membership and compatibility boundary. |
| Variation Evidence Count | `SEMANTIC_AMBIGUITY` | One approved counting grain shared by variation edges and competition evidence records. |
| Evidence-backed Trend | `FORMULA_UNSPECIFIED` | Approved window, direction, threshold, and tie behavior. |
| Keyword Difficulty Summary | `PROVIDER_SCALE_UNCONFIRMED` | Confirmed Provider scale and method. |
| Product BSR Summary | `RANK_CONTEXT_COMPATIBILITY_UNRESOLVED` | Compatible category and rank contexts. |

These fields remain visible as blocked records. Field names never authorize a guessed
formula.

## 8. Provider neutrality and integration boundary

The builder contains no XiYou or Sorftime branch. Provider identity appears only in
Canonical provenance and scope metadata. Tests pass both XiYou and Sorftime clean results
through the same builder.

The small integration boundary uses the sanitized XiYou HTTP V2 `entities[]` fixture:

```text
Static fixture Transport
  -> XiYou Connector
  -> XiYou Adapter
  -> Canonical Evidence
  -> Normalization
  -> CleanCanonicalResult
  -> MarketAnalysisResult
```

Production network construction remains owned by the explicit Data Cleaning `--live`
gate. Ordinary `pytest` never opts into that gate and performs zero production network
requests.

### 8.1 XiYou live validation

On 2026-08-19, one public US ASIN was processed through the existing explicit `--live`
gate and the complete pipeline. No raw response was persisted.

```text
XiYou HTTP success
  -> Cleaning SUCCESS (4 observed, 2 normalized, 2 unchanged, 0 quality issues)
  -> one validated Canonical product identity
  -> observed product count CALCULATED (1)
  -> price/rating/review summaries produced with explicit units and verified provenance
  -> MarketAnalysisResult PARTIAL
```

All three numeric product summaries had one valid sample and no missing, unknown, or
invalid input. Their `PARTIAL` status and `SMALL_SAMPLE_SIZE_LT_2` limitation are expected:
the run validates the integration and formulas but does not pretend that one product is a
reliable market sample.

## 9. V1 exclusions

V1 does not implement or modify:

- final Opportunity Score or any new Competition Score formula;
- Opportunity Scoring behavior;
- AI analysis or recommendations;
- Trend;
- Comparable Product membership;
- comparable-price formulas;
- Variation Evidence Count;
- SellerSprite or Sorftime integration behavior;
- Workbook design or export behavior;
- Provider candidate resolution, currency conversion, rank-context conversion, or
  statistical confidence claims.

Observed min/max/mean/median describe only the supplied clean sample. They are not market
share, market size, a comparable-product benchmark, or a selection recommendation.
