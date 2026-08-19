# Opportunity Scoring Input Contract & Metric Dependency Mapping V0.1

Status: specification-only; non-executable

Contract version: `opportunity-scoring-input-contract-v0.1`

Parent specification: `opportunity-scoring-specification-v0.1`

Future algorithm: `opportunity-score-v0.1` — reserved, still non-executable

## 0. Purpose and boundary

This document defines the Provider-neutral input contract for a future business
Opportunity Score. It identifies the evidence a scorer would need, the current owner
and source of each input, present availability, missing-data behavior, quality and
provenance requirements, and the relationship to all 157 fixed Operator Workbook V0.2
fields.

This contract does **not** define or authorize:

- a scoring formula, weight, threshold, band, normalization parameter, or evaluator;
- a profit score, Competition Score, final recommendation, or automatic decision;
- a new Workbook field, Canonical field, Connector mapping, API call, or credential;
- use of the existing fixed `25` process allocation as a business Opportunity Score.

The future scoring layer must consume cleaned Canonical and owned analysis results. It
must not read a Workbook cell or parse a XiYou or Sorftime payload as its source of
truth.

```text
Provider / governed manual evidence
-> Canonical Evidence and normalization
-> CleanCanonicalResult
-> MarketAnalysisResult / CompetitionAnalysisResult / quality and risk companions
-> OpportunityScoringInputEnvelope
-> future OpportunityScoreResult (NON_EXECUTABLE in V0.1)
```

No live API was requested for this specification. Provider capability conclusions are
limited to the audited SP-018A mapping and the later checked-in contract validations.

## 1. Scoring Input Overview

| Input category | Purpose | Included input classes | V0.1 boundary |
|---|---|---|---|
| Demand Inputs | Describe evidence of buyer/search interest in an exact marketplace, keyword, period, and sample scope. | Search volume, ABA rank, CPC, keyword/product relationships, traffic, sales evidence, trends, category growth, market size, seasonality. | Direct values and bounded observations are not a demand conclusion; several trend and total-market semantics remain unavailable. |
| Competition Inputs | Describe barriers visible in an explicit observed or governed top-product scope. | Rating, reviews, brand/seller structure, observed price, comparable-price pressure, BSR, variation and relationship evidence. | Observed products are not automatically Comparable Products or a market census. |
| Economics Inputs | Determine whether enough compatible economic evidence exists to evaluate economics later. | Selling price, price stability, compatible sales estimate, revenue dependency, cost/fee inputs, margin readiness. | This is readiness, not profitability. No profit or margin value may be emitted. |
| Data Quality Inputs | Gate interpretation and expose evidence adequacy without hiding exclusions. | Sample counts, presence state, conflict state, completeness, timestamp/period quality, provenance, qualitative evidence quality. | Quality is a mandatory companion, not a hidden weight or numeric confidence adjustment. |
| Risk Inputs | Preserve blockers and limitations separately from desirability. | Risk inventory, analysis limitations, incompatible scope/unit/context blockers. | No severity, probability, numeric penalty, or risk-adjusted score is defined. |

The metric inventory below contains **43** rows. Its availability vocabulary answers
only whether an input can currently be obtained or produced with known semantics. It
does not make any metric score-executable.

| Status | Contract meaning |
|---|---|
| `AVAILABLE` | A semantically identified current input can be obtained from the named owner/source. Score direction or normalization may still be undecided. |
| `PARTIAL` | Some evidence exists, but coverage, units, methods, cohort, period, or interpretation is incomplete. |
| `CALCULATED` | An existing deterministic owner already derives the record from governed inputs. This never authorizes a new scoring calculation. |
| `UNAVAILABLE` | No current approved direct or derived input satisfies the stated semantic. A future governed source or manual input is required. |
| `UNKNOWN` | The source identity or derivation semantic cannot yet be confirmed safely. |

## 2. Metric Dependency Map

| ID | Scoring dimension/category | Metric | Canonical or owned analysis field | Data source | Source API/tool | Status | Notes |
|---|---|---|---|---|---|---|---|
| D01 | DEMAND_POTENTIAL | Keyword search volume | `keyword.search_volume` / `market_analysis.keyword_search_volume` | XiYou through Cleaning and Market Analysis | `/v1/searchTerms/info` | PARTIAL | Weekly value and report period are known; provider estimate method is unconfirmed, so current Market Analysis aggregation remains blocked. |
| D02 | DEMAND_POTENTIAL | ABA search-frequency rank | `keyword.aba_rank` / `market_analysis.keyword_aba_rank` | XiYou through Cleaning and Market Analysis | `/v1/searchTerms/info` | AVAILABLE | Direct integer rank with period; a future reference population and normalization policy are still required. |
| D03 | DEMAND_POTENTIAL | Keyword CPC | `keyword.cpc` / `market_analysis.keyword_cpc` | XiYou through Cleaning and Market Analysis | `/v1/searchTerms/info` | PARTIAL | Value is observed, but currency is not consistently echoed and CPC's opportunity direction is unresolved. |
| D04 | DEMAND_POTENTIAL | Keyword-to-product relationship count | `ProductKeywordRelationship` and `workbook.keyword_demand.related_product_count` | Calculation Engine through Market Analysis | `/v1/searchTerms/analysis/list/period`, `/monthly` | CALCULATED | Distinct validated relationships in one directional page scope; never provider total or market size. |
| D05 | DEMAND_POTENTIAL | Keyword trend observations | Dated `KeywordMetric` observations; no approved trend result | XiYou | `/v1/searchTerms/abaReport/trends/weekly` | PARTIAL | Time-series capability exists; window, slope/direction, minimum observations, ties, and missing policy are not approved. |
| D06 | DEMAND_POTENTIAL | Product sales/order evidence | Separate `metric.orders`, `metric.estimated_monthly_sales`, and `metric.estimated_sales_volume` observations | XiYou + Sorftime | XiYou `/v1/asins/orders`; Sorftime `product_detail`, `product_variations` | PARTIAL | Provider estimates have different methods, periods, and possible grains and must not be aliased. |
| D07 | DEMAND_POTENTIAL | Sales trend observations | Dated separate sales/order observations; no approved trend result | XiYou + Sorftime | XiYou documented order trend; Sorftime `product_trend` | PARTIAL | Sorftime exact response contract and cross-provider period/method comparability remain incomplete. |
| D08 | DEMAND_POTENTIAL | Traffic evidence | Product-keyword relationship/traffic observations with period and channel | XiYou | Keyword/ASIN analysis endpoints and `/v1/asins/trafficScore/trend/*` | PARTIAL | Provider traffic method, some channel codes, completeness, and scoring direction remain unresolved. |
| D09 | DEMAND_POTENTIAL | Category growth | No current Canonical or analysis metric | Future governed category time-series analysis | None confirmed | UNAVAILABLE | BSR/category facts do not by themselves define category sales or demand growth. |
| D10 | DEMAND_POTENTIAL | Total market size | No direct Canonical metric; proxy evidence must stay separately labelled | Future governed market model | No confirmed total-market endpoint | UNAVAILABLE | Search, traffic, observed product, and relationship counts are not guaranteed total market size. |
| D11 | DEMAND_POTENTIAL | Seasonality | No approved seasonal metric | Future system calculation from sufficiently long compatible time series | No complete seasonal source contract | UNAVAILABLE | Requires governed cycle length, coverage minimum, baseline, missing periods, and cross-year behavior. |
| C01 | COMPETITION_ACCESSIBILITY | Observed product count | `workbook.market_overview.observed_product_count` | Calculation Engine through Market/Competition Analysis | Product identities originating from audited product/relationship operations | CALCULATED | Bounded distinct identity count, not a market census or Comparable Product count. |
| C02 | COMPETITION_ACCESSIBILITY | Observed-sample review-count distribution | `market_analysis.product_review_count` | Market/Competition Analysis | XiYou `/v1/asins/info`; Sorftime `product_detail` | CALCULATED | Existing min/max/mean/median with valid and excluded counts; zero is valid. |
| C03 | COMPETITION_ACCESSIBILITY | TOP-ASIN review barrier | `metric.review_count` plus governed top-product membership | XiYou + Sorftime plus future cohort policy | Product facts plus XiYou rank/relationship operations | PARTIAL | Values are available, but “TOP ASIN” membership, scope size, rank rule, and snapshot policy are not governed. |
| C04 | COMPETITION_ACCESSIBILITY | Observed-sample rating distribution | `market_analysis.product_rating` | Market/Competition Analysis | XiYou `/v1/asins/info`; Sorftime `product_detail` | CALCULATED | Existing compatible-scale min/max/mean/median with exclusions. |
| C05 | COMPETITION_ACCESSIBILITY | TOP-ASIN rating barrier | `metric.rating` plus governed top-product membership | XiYou + Sorftime plus future cohort policy | Product facts plus XiYou rank/relationship operations | PARTIAL | Rating is available, but the top-product cohort and its minimum sample are not governed. |
| C06 | COMPETITION_ACCESSIBILITY | Brand concentration | `ProductFact(brand)` plus governed sample membership | Sorftime plus future system aggregation | Sorftime `product_detail` | PARTIAL | Brand candidates exist, but one compatible cohort, brand identity resolution, missing-brand treatment, and concentration definition are absent. |
| C07 | COMPETITION_ACCESSIBILITY | Seller count/concentration | Future `product.seller` identity plus governed sample | No confirmed current provider | No stable audited XiYou or Sorftime seller field | UNKNOWN | Brand, manufacturer, store text, or offer text must not substitute for seller identity. |
| C08 | COMPETITION_ACCESSIBILITY | Observed price distribution | `market_analysis.observed_product_price` | Market Analysis | XiYou `/v1/asins/info`; Sorftime `product_detail` | CALCULATED | Same-currency observed sample only; this is not price competition or comparable-product price. |
| C09 | COMPETITION_ACCESSIBILITY | Price competition/comparable-price pressure | Governed `COMPARABLE` membership plus compatible resolved prices | Future Comparable Product Set and Calculation Engine | No provider endpoint can create governed membership | UNAVAILABLE | Blocked by `MEMBERSHIP_SOURCE`; observed products cannot be renamed Comparable Products. |
| C10 | COMPETITION_ACCESSIBILITY | Exact-context BSR distribution | `competition_analysis.contextual_bsr` | Competition Analysis | XiYou `/v1/asins/bsrInfo/trends/daily` | CALCULATED | Only identical marketplace/category/rank type/date/unit contexts aggregate; cross-category average is forbidden. |
| C11 | COMPETITION_ACCESSIBILITY | Variation structure | `competition_analysis.variation_structure` | Competition Analysis | XiYou `/v1/asins/variations`; Sorftime `product_variations` | CALCULATED | Existing source-record, unique-edge, parent, child, duplicate, and incomplete-family counts stay separate; no single variation score/count is approved. |
| C12 | COMPETITION_ACCESSIBILITY | Product-keyword/channel evidence inventory | `ProductKeywordRelationship` and `workbook.competition_evidence.evidence_count` | Calculation Engine/Competition evidence | XiYou keyword-to-ASIN and ASIN-to-keyword operations | CALCULATED | Evidence count describes the bounded query result, not competition strength. |
| E01 | PRODUCT_ECONOMICS_READINESS | Observed selling-price distribution | `market_analysis.observed_product_price` | Market Analysis | XiYou `/v1/asins/info`; Sorftime `product_detail` | CALCULATED | Compatible current selling-price context only; price is not profit. |
| E02 | PRODUCT_ECONOMICS_READINESS | Price stability | Dated price observations; no approved stability result | XiYou + Sorftime | XiYou `/v1/asins/infoChange/trends/daily`, `/v1/asins/info/trends/daily`; Sorftime `product_trend` | PARTIAL | Time-series capability exists, but stability window, dispersion/change rule, outliers, and minimum observations are undefined. |
| E03 | PRODUCT_ECONOMICS_READINESS | Compatible sales-estimate input | Separate sales/order metrics from D06 | XiYou + Sorftime | XiYou `/v1/asins/orders`; Sorftime `product_detail`, `product_variations` | PARTIAL | May support future economics only after method, unit, period, product grain, and snapshot alignment. |
| E04 | PRODUCT_ECONOMICS_READINESS | Estimated revenue | No current owned field or approved derivation | Future deterministic economics layer | No direct provider field | UNKNOWN | Price multiplied by an incompatible or method-unknown estimate would be false precision; revenue semantics and period are unapproved. |
| E05 | PRODUCT_ECONOMICS_READINESS | Landed unit cost input | Future governed manual/external cost record; no current Canonical/Workbook field | Operator or approved cost system | None | UNAVAILABLE | Required future manual/reference input; must carry currency, unit, effective period, source, and provenance. |
| E06 | PRODUCT_ECONOMICS_READINESS | Amazon fee input | Future governed fee schedule/input; no current Canonical/Workbook field | Approved fee table or operator | None | UNAVAILABLE | Referral/FBA fee semantics, marketplace, size tier, effective date, and source are required. |
| E07 | PRODUCT_ECONOMICS_READINESS | Fulfillment/logistics cost input | Future governed manual/external cost record | Operator or approved logistics source | None; Sorftime fulfillment status is not a cost | UNAVAILABLE | Fulfillment type alone cannot supply inbound, storage, handling, or delivery cost. |
| E08 | PRODUCT_ECONOMICS_READINESS | Advertising, return, tax, and allowance assumptions | Future governed scenario inputs | Operator or approved reference source | None | UNAVAILABLE | Each assumption requires separate unit, scope, effective period, owner, and provenance; no defaults are authorized. |
| E09 | PRODUCT_ECONOMICS_READINESS | Cost input availability | Future dependency-state record over E05-E08 | Future economics readiness layer | None | UNAVAILABLE | No current implemented owner evaluates the required cost set; absence cannot be interpreted as zero cost. |
| E10 | PRODUCT_ECONOMICS_READINESS | Margin calculation readiness | Future dependency validation over compatible price, sales period, and cost/fee inputs | Future economics readiness layer | None | UNAVAILABLE | Readiness may later be an explicit state; this contract does not calculate margin or profitability. |
| Q01 | DATA_QUALITY | Valid and excluded sample counts | Market/Competition numeric-summary counters | Market/Competition Analysis | None; derived from cleaned inputs | CALCULATED | Required per metric and per exclusion reason. |
| Q02 | DATA_QUALITY | Presence/normalization state | `CleanFieldResult` presence, normalization, and quality states | Cleaning | None; derived from Canonical evidence | CALCULATED | Missing, explicit null, unknown, invalid, and valid zero remain distinct. |
| Q03 | DATA_QUALITY | Candidate/conflict state | Product/metric candidate state and conflict evaluation | Product Intelligence/Evidence Evaluation | None; system-owned | CALCULATED | Multiple unresolved candidates cannot be silently selected or averaged. |
| Q04 | DATA_QUALITY | Query and pagination completeness | `QueryExecutionRecord` plus requested/returned/total/page metadata | Canonical query evidence and analysis | XiYou paginated relationship operations when applicable | CALCULATED | A partial page remains partial and provider total is not a measured market count. |
| Q05 | DATA_QUALITY | Timestamp/period completeness | Observation time, period and `time_period_status` | Canonical/Intelligence quality projection | Source operation fields and request context | CALCULATED | Retrieval time cannot replace missing observation time. |
| Q06 | DATA_QUALITY | End-to-end provenance | Canonical provenance, normalization/calculation lineage, raw-evidence reference | Canonical, Cleaning, analysis owners | Exact source operation/tool and field | CALCULATED | Every numeric input must reach provider or governed manual source without credential material. |
| Q07 | DATA_QUALITY | Qualitative evidence quality | `EvidenceQualityProfile` and analysis quality summary | Evidence Evaluation/Market/Competition Analysis | None; system-owned | CALCULATED | This is not a probability or numeric confidence score and cannot become a hidden weight. |
| R01 | RISK | Risk evidence inventory | `opportunity_intelligence.risk_evidence` | Opportunity Intelligence | None; derived from evidence diagnostics | CALCULATED | Visible limitation evidence only; no severity or penalty. |
| R02 | RISK | Analysis limitations | Market, competition, opportunity, and quality limitation codes | Owning analysis layers | None; system-owned | CALCULATED | Every blocked dependency and sample limitation remains visible in output. |
| R03 | RISK | Incompatible scope/unit/context blocker | Quality gates for marketplace, currency, unit, period, rank context, snapshot, and candidate conflicts | Cleaning/Market/Competition Analysis | None; derived from source metadata | CALCULATED | Unsafe aggregation is blocked; values are not converted, zero-filled, or discarded silently. |

### 2.1 Metric status totals

| Status | Count |
|---|---:|
| AVAILABLE | 1 |
| PARTIAL | 11 |
| CALCULATED | 19 |
| UNAVAILABLE | 10 |
| UNKNOWN | 2 |
| **Total** | **43** |

The small `AVAILABLE` count is intentional: this table classifies score-ready input
records, not raw API field presence. Many direct values are exposed only as `PARTIAL`
because their method, cohort, currency, or period is incomplete, while existing safe
summaries are `CALCULATED`. None of the 43 rows is an executable score factor.

## 3. DEMAND_POTENTIAL Input Definitions

| Input | Why it is needed / role in demand judgment | Current source | Missing handling |
|---|---|---|---|
| Keyword volume | Supplies direct search-demand evidence for an exact keyword and report period. More confirmed volume may support demand, but the value remains a provider estimate. | XiYou keyword info. | Missing/unknown stays null. Method-unconfirmed evidence remains `PARTIAL` and cannot enter an aggregate until governed. |
| Keyword trend | Distinguishes a dated series from a single snapshot and may later show direction or persistence. | XiYou weekly keyword trend observations. | No series is not “flat”; insufficient coverage is `NOT_AVAILABLE` or `PENDING`, and conflicting periods are `CONFLICT`. |
| Sales trend | May later show whether product demand evidence is growing, declining, or seasonal without relying only on search behavior. | XiYou order series and Sorftime product trend evidence, kept as separate semantics. | Missing periods are not zero sales. Incompatible methods/grains block combination. |
| Category growth | Would contextualize product/keyword evidence within a governed category population. | No current confirmed category-growth source. | `NOT_AVAILABLE`; BSR movement must not be relabelled as category sales growth. |
| Market size | Would bound the addressable market rather than only describe an observed page/sample. | No confirmed total-market source; current search/traffic/sales evidence is proxy-only. | `NOT_AVAILABLE`; observed count, provider total, and related-product count cannot substitute. |
| Seasonality | Would distinguish repeatable seasonal change from durable demand. | Future calculation from sufficiently long compatible time series. | `NOT_AVAILABLE` until cycle, history length, missing-period, and cross-year rules exist. |
| ABA rank | Provides an independently reported keyword-demand rank with explicit period. | XiYou keyword info. | Missing/invalid excluded; mixed ABA periods or universes block comparison. |
| CPC | Provides paid-acquisition/intent context, but can mean stronger commercial intent and/or higher acquisition cost. | XiYou keyword info. | Missing/invalid excluded; missing or mixed currency blocks use; direction remains unresolved. |
| Keyword/product and traffic evidence | Establishes bounded product association and channel context around a keyword. | XiYou directional relationship and traffic operations. | Empty query is query-scoped, partial pagination remains partial, and unknown channel codes remain unknown. |

Demand inputs must share compatible marketplace, keyword identity, period/window,
estimate method, unit, and snapshot context before any future composition is considered.

## 4. COMPETITION_ACCESSIBILITY Input Definitions

| Input | Entry-difficulty role | Current source | Missing handling |
|---|---|---|---|
| TOP ASIN review count | High incumbent review evidence may represent a barrier, but only inside an approved top-product cohort. | XiYou/Sorftime review-count facts plus future governed rank cohort. | Without governed TOP membership, retain observed-sample summary as context and mark the TOP barrier `PENDING`/partial. Zero reviews remains a valid value. |
| TOP ASIN rating | High incumbent ratings may represent a quality/reputation barrier in a governed cohort. | XiYou/Sorftime rating facts plus future governed rank cohort. | Missing/invalid ratings are excluded; scale mismatch or unresolved cohort blocks the barrier input. |
| Brand concentration | May indicate whether visible demand is concentrated among a few resolved brands. | Sorftime brand candidates plus future aggregation. | Missing brands do not become a brand called “Unknown”; unresolved identities/cohort block concentration. |
| Seller count | Could describe seller concentration only with stable seller identity. | No confirmed current provider field. | `UNKNOWN`; brand/manufacturer/store text cannot be guessed as seller. |
| Price competition | Could describe price pressure only across a governed comparable cohort with compatible resolved prices. | Future Comparable Product Set; current observed price is context only. | `NOT_AVAILABLE` while `MEMBERSHIP_SOURCE` is blocked; no observed-to-comparable substitution. |
| BSR distribution | Describes rank evidence within one exact comparable rank context. | XiYou BSR through Competition Analysis. | Missing context or mixed marketplace/category/rank type/date/unit creates separate groups or blocks use. |
| Observed product count | Describes the bounded supplied identity scope, not market size. | Calculation Engine through Market/Competition Analysis. | No validated identity means missing input, never a fabricated zero-product market. |
| Variation structure | Describes explicit family complexity with mechanically separate grains. | XiYou/Sorftime relationship evidence through Competition Analysis. | Missing relationships do not mean zero variations; no aggregate variation factor until a business grain is approved. |

No observed-product statistic may be labelled “Comparable Product” without a governed
`COMPARABLE` assertion. No competition-strength formula is defined here.

## 5. PRODUCT_ECONOMICS_READINESS Input Definitions

The dimension measures whether compatible economic evidence is present. It does not
measure profit and does not authorize a profit score.

| Input | Readiness role | Current source | Missing handling |
|---|---|---|---|
| Selling price | Establishes observed revenue-side price context in one currency/snapshot. | Market Analysis observed-price distribution. | Mixed/missing currency blocks aggregation; missing price is not zero. |
| Price stability | Would indicate whether one snapshot price is representative across a governed window. | XiYou price history and Sorftime product trend capability. | `PARTIAL`; absence of changes is not stability unless observation coverage is proven. |
| Estimated revenue | Would require compatible price, sales quantity, grain, and period semantics. | No current direct field or approved formula. | `UNKNOWN`; no multiplication until revenue period, quantity method, returns, and product grain are governed. |
| Cost input availability | Determines whether required cost classes exist with compatible unit/currency/effective period. | Future governed manual or reference inputs. | `NOT_AVAILABLE`; missing costs are never zero costs. |
| Margin calculation readiness | Would indicate dependency completeness before a future margin calculation. | Future economics readiness layer. | `NOT_AVAILABLE`; no margin value or readiness claim until the required dependency set is approved. |

### 5.1 Future manual/reference inputs

| Future input | Expected owner/source | Minimum contract | Current treatment |
|---|---|---|---|
| Landed unit cost | Operator or approved cost system | Amount, ISO currency, per-unit basis, marketplace, effective period, source reference. | Required future input; no current Canonical or Workbook field is added. |
| Amazon referral/FBA fee | Approved versioned fee table or operator | Fee type, amount/rate, size tier, marketplace, effective date, source version. | Required when applicable; fulfillment status is not fee evidence. |
| Inbound/storage/handling/logistics cost | Operator or approved logistics source | Separate cost components, unit, currency, scenario, effective period, provenance. | Required future input; no default is authorized. |
| Advertising/return/tax/allowance assumptions | Operator or approved reference source | Separate named assumptions, units/rates, scope, effective period, owner, provenance. | Optionality and required set are future business decisions; absent values remain absent. |

`workbook.action_recommendations.manual_review_status` is not one of these economics
inputs. It remains an isolated operator workflow field and must never feed a score.

## 6. Data Quality Contract

Every future scoring input is a `ScoringInputRecord` and must contain at least:

| Field | Requirement |
|---|---|
| `input_id` | Stable metric identity matching the versioned metric catalogue. |
| `dimension_or_category` | One of the three candidate dimensions or the separate `DATA_QUALITY` / `RISK` categories. |
| `value` | Nullable typed value. A null requires an explicit presence/missing reason. |
| `unit` | Explicit unit/currency/rank/count semantic when the value is numeric. |
| `scope` | Marketplace, product/keyword/cohort, observation window/snapshot, and relevant rank/category context. |
| `source` | Authoritative analysis owner plus originating Provider or governed manual/reference owner. |
| `timestamp` | Observation time or period with precision; collection time is recorded separately and cannot substitute. |
| `confidence` | Non-probabilistic evidence state such as confirmed/partial/unknown plus reasons; no invented percentage. |
| `completeness` | Structured total/valid/excluded counts, exclusion reasons, pagination/scope coverage, and partial status. |
| `provenance` | End-to-end references from derived input through clean/canonical evidence to raw evidence and Provider/manual source. |
| `quality_issues` | Stable issue/limitation identifiers affecting interpretation or eligibility. |
| `availability_status` | Exactly one of the five statuses defined in section 1. |
| `presence_status` | Present or an explicit missing state from section 7; numeric zero is never a missing state. |

Hard gate: **a numeric value without source, timestamp/period, applicable unit/scope,
completeness, and provenance is ineligible for future scoring**. It remains an invalid
input record for audit; it is not repaired with a default, inferred Provider, or current
clock time.

Required provenance chain:

```text
ScoringInputRecord
-> owned Market/Competition/Quality/Risk result and rule version
-> CleanCanonicalResult and normalization record
-> Canonical Evidence and mapping version
-> RawEvidenceRef and exact source operation/field
-> Provider
```

For governed manual/reference data, the final step is the named owner/source artifact,
version, and effective period instead of a Provider API.

## 7. Missing Data Rules

Availability status and presence status are independent. For example, ABA rank can be
`AVAILABLE` as a metric capability while one record is `PENDING` or `UNKNOWN`.

| Missing state | Meaning | Future scoring effect |
|---|---|---|
| `UNKNOWN` | Evidence exists or a field is expected, but its value, identity, unit, method, or meaning cannot be confirmed. | Never zero-fill or penalize. The affected metric is ineligible; future configuration must decide whether the dimension blocks or remains explicitly partial. |
| `NOT_AVAILABLE` | The required source/capability does not currently exist or cannot supply the semantic. | Report the dependency. A required metric blocks its dimension; an optional metric may be excluded only under a future versioned eligibility policy. |
| `PENDING` | Collection, manual entry, approval, or governed derivation has not completed. | Keep the score/dimension pending or partial according to a future policy; do not treat pending as low demand, high competition, or zero cost. |
| `CONFLICT` | Two or more valid candidates disagree and no resolution policy selected an authoritative value. | Block single-value use and unsafe aggregation. Preserve all candidates and conflict provenance. |

Existing `MISSING`, `EXPLICIT_NULL`, and `INVALID` evidence states remain distinct under
Cleaning and analysis contracts. They map to an explicit `presence_status`/quality
reason but are not collapsed into the four business missing states above.

Mandatory invariants:

1. `missing != 0`, `unknown != 0`, and `pending != 0`.
2. A semantically valid numeric zero remains present and participates in an eligible
   statistic.
3. Invalid values are excluded with reason and provenance.
4. Partial records do not remove valid sibling records, but result completeness stays
   partial.
5. Mixed currencies, units, rank contexts, marketplaces, periods, or snapshots block
   unsafe aggregation.
6. No missing state has an implicit score penalty, weight redistribution, average
   imputation, or provider preference in V0.1.

## 8. API and Source Mapping

### 8.1 Provider responsibilities from SP-018A

| Scoring input slice | Primary source | Secondary/source support | Current boundary |
|---|---|---|---|
| Keyword identity, search volume, ABA rank, CPC | XiYou `/v1/searchTerms/info` | None confirmed | Period and estimate/method status remain explicit. |
| Keyword trend and keyword/product relationships | XiYou keyword trend, keyword-to-ASIN and ASIN-to-keyword operations | None confirmed | Direction, pagination, period, channel, and Provider method must be retained. |
| BSR/rank/channel/traffic | XiYou BSR, relationship, and traffic operations | Sorftime `product_trend` only after exact schema verification | Exact category/rank/date context is mandatory. |
| Current product price/rating/review count | XiYou `/v1/asins/info` | Sorftime `product_detail` | Preserve separate candidates and conflicts. |
| Rich product facts and brand | Sorftime `product_detail` | XiYou current facts where available | Sorftime is primary for brand/attributes; no brand-to-seller inference. |
| Variation structure | XiYou `/v1/asins/variations` | Sorftime `product_variations` | Only explicit confirmed relationships; separate counting grains. |
| Sales/order evidence | XiYou `/v1/asins/orders` | Sorftime monthly sales and variation `SalesAmount` | Separate provider metrics; no aliasing or automatic revenue. |
| Product trend / price-history support | XiYou dated product operations | Sorftime `product_trend` after contract verification | Source period/method compatibility remains a gate. |
| Seller identity | None confirmed | None | Remains `UNKNOWN`. |
| Costs, fees, margin dependencies | Governed manual/reference source in a future contract | Possible future approved systems | No current Provider or Workbook source. |

### 8.2 Source ownership rules

- XiYou supplies keyword, directional relationship, BSR/rank/channel/traffic, current
  product, variation, and order evidence only through the existing Provider boundary.
- Sorftime supplies rich product, brand, attribute, review, variation-property,
  sales-estimate, discovery, and trend evidence only where its audited schema confirms
  the field.
- The system owns deterministic counts, distributions, quality/completeness,
  conflicts, risk/limitation inventories, and provenance projections.
- Operators or governed reference systems must own future costs and assumptions. These
  values require the same provenance discipline as API evidence.
- Providers do not supply an Opportunity Score, business conclusion, comparable
  membership, weight, threshold, or recommendation.

## 9. Future Scoring Engine Contract

### 9.1 Input

A future `OpportunityScoringInputEnvelope` must contain:

- contract/specification version and requested future algorithm version;
- product dataset identity plus marketplace, product/keyword scope, snapshot/run, and
  cohort/membership references;
- immutable references to the contributing `CleanCanonicalResult`,
  `MarketAnalysisResult`, and `CompetitionAnalysisResult` records;
- ordered `ScoringInputRecord` values from the 43-row catalogue;
- separate data-quality, confidence/completeness, risk, missing, conflict, and blocked
  dependency inventories;
- all applicable metric-definition, normalization, eligibility, missing-policy, and
  future configuration version references.

V0.1 defines no executable configuration. Therefore a conforming prototype may
validate and report the input envelope but must not calculate a business score.

### 9.2 Output

A future `OpportunityScoreResult` must contain at least:

- nullable `score_value` and explicit `score_status`;
- nullable dimension scores and a status for each of
  `DEMAND_POTENTIAL`, `COMPETITION_ACCESSIBILITY`, and
  `PRODUCT_ECONOMICS_READINESS`;
- input-validity, confidence/completeness, and sample/exclusion summaries;
- risk, limitation, missing, conflict, and blocked-dependency records;
- specification, algorithm, metric, normalization, eligibility, missing-policy,
  weight, aggregation, and threshold version references where later approved;
- end-to-end provenance and calculation/explanation references;
- an explanation of contributing and excluded inputs without a generated business
  conclusion.

The result must never be returned or displayed as only one number. In the current
non-executable state, total and dimension score values remain null with a blocked
configuration/data status as applicable.

## 10. Relationship to all 157 Workbook fields

The Workbook is an operator presentation/audit projection, not a scoring input store.
The relationship below covers every fixed field ID exactly once. `SOURCE_OR_SCOPE`
means the field may expose or constrain a metric in section 2; it does not authorize
direct cell ingestion or inclusion in a score.

| Relationship | Workbook field IDs | Count | Rule |
|---|---|---:|---|
| `SOURCE_OR_SCOPE` | F001-F006, F008; F013-F015, F017-F021, F023, F025-F029, F031-F033, F035-F036; F043-F049, F052-F055; F059-F062, F064-F066, F068, F070, F072-F075; F082-F087, F089-F091; F095-F103, F107; F108-F114, F121 | 77 | Potential source display, identity, unit, cohort/context dependency, or existing evidence companion. Only the 43-row metric catalogue determines future input eligibility. |
| `QUALITY_OR_RISK_GATE` | F009-F011; F016, F022, F024, F030, F038-F040; F051, F057; F063, F067, F069, F071, F076, F078-F080; F092-F093; F104-F106 | 25 | Mandatory quality/risk companion or gate; never a hidden desirability weight. |
| `PROVENANCE_REQUIRED` | F007, F012; F037, F041-F042; F050, F058; F077, F081; F088, F094; F122; F146-F157 | 24 | Provides/references lineage, snapshot, Provider, source operation/field, and integrity metadata; numbers without this chain are ineligible. |
| `DISPLAY_ONLY_NOT_INPUT` | F034, F056, F138-F145 | 10 | Presentation summary or rendered Workbook location metadata; not model input. |
| `CURRENT_PROCESS_SCORE_EXCLUDED` | F115-F120 | 6 | Existing factor/process-score/status/explanation records, including fixed `25`; explicitly excluded from the future business score to prevent circularity. |
| `DOWNSTREAM_OUTPUT_EXCLUDED` | F123-F133, F135-F137 | 14 | Recommendation/output records occur after opportunity analysis and must not feed back into scoring. |
| `HUMAN_WORKFLOW_EXCLUDED` | F134 | 1 | Manual Review Status is operator workflow state, not evidence, cost input, score input, or label. |
| **Total** | **F001-F157, each exactly once** | **157** | Operator Workbook V0.2 remains fixed at 9 sheets / 157 fields. |

Sheet totals remain unchanged:

| Workbook sheet | Field IDs | Count | Scoring-contract relationship |
|---|---|---:|---|
| `01_市场概览` | F001-F012 | 12 | Demand/market scope, quality/risk, and snapshot provenance. |
| `02_产品数据库` | F013-F042 | 30 | Product/competition/economics evidence, state gates, and provenance. |
| `03_TOP产品分析` | F043-F058 | 16 | Candidate cohort/rank context, rating/review/price evidence, and limitations; no automatic TOP membership rule. |
| `04_关键词需求分析` | F059-F081 | 23 | Demand evidence, method/unit/period/completeness gates, and demand provenance. |
| `05_市场竞争证据` | F082-F094 | 13 | Directional relationship/variation evidence and competition limitations; not competition strength. |
| `06_产品结构分析` | F095-F107 | 13 | Observed structure/price context; Comparable price fields remain membership-blocked. |
| `07_机会分析` | F108-F122 | 15 | Existing evidence companions plus process-scoring outputs that are explicitly excluded from business-score input. |
| `08_行动建议` | F123-F137 | 15 | Downstream recommendation/workflow outputs; excluded to prevent feedback. |
| `09_数据审计` | F138-F157 | 20 | Presentation metadata plus mandatory provenance references; no business metric value. |
| **Total** | **F001-F157** | **157** | No Workbook field was added, removed, renamed, or repurposed. |

This crosswalk also preserves the authoritative acquisition coverage totals from
SP-018A/SP-021B: `30 AVAILABLE / 24 PARTIAL / 99 CALCULATED / 2 UNAVAILABLE /
2 UNKNOWN`. Those totals describe Workbook acquisition coverage and are independent of
the 43-row scoring-input status totals in section 2.1.

## 11. Blocked Dependencies and Decision Queue

The future engine remains non-executable while any required business decisions are
unapproved. Current blockers include:

- `ESTIMATE_METHOD`: search-volume, traffic, order, and sales-estimate methodology;
- `TREND_DEFINITION`: window, observation minimum, direction, ties, missing periods,
  stability, growth, and seasonality rules;
- `TOP_PRODUCT_COHORT`: membership/rank rule, cohort size, period, marketplace, and
  completeness for TOP-ASIN barriers;
- `MEMBERSHIP_SOURCE`: governed Comparable Product membership for price competition;
- `BRAND_IDENTITY_POLICY` and `SELLER_IDENTITY`: concentration identities and missing
  handling;
- `VARIATION_GRAIN`: evidence rows, unique edges, or unique variants;
- `PROFITABILITY_INPUTS`: landed cost, fees, logistics, advertising, returns, taxes,
  allowances, and compatible revenue period/grain;
- `MARKET_SIZE_SOURCE` and `CATEGORY_GROWTH_SOURCE`;
- `CONFIDENCE_POLICY`: evidence adequacy, minimum samples, partial behavior, and
  qualitative-to-output rules;
- `SCORING_CONFIGURATION`: active metrics/dimensions, normalization, weights,
  aggregation, thresholds, rounding, and missing-data eligibility.

Business decisions must be versioned before implementation. This input contract does
not choose among them and supplies no default.

## 12. Acceptance Invariants

1. All three candidate scoring dimensions have explicit input definitions.
2. Every one of the 43 metric rows names its authoritative source and current status.
3. Every fixed Workbook field F001-F157 is related exactly once without changing the
   Workbook contract.
4. API-dependent, system-calculated, unavailable, unknown, and future manual inputs are
   distinguishable.
5. No number without source, timestamp/period, confidence state, completeness, and
   provenance may enter future scoring.
6. No weight, threshold, normalization parameter, score formula, profit score, or
   executable scoring code is defined by this document.
