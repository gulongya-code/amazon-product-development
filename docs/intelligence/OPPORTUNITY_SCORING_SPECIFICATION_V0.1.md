# Opportunity Scoring Specification V0.1

Status: specification-only; non-executable

Specification version: `opportunity-scoring-specification-v0.1`

Reserved future algorithm version: `opportunity-score-v0.1`

## 1. Purpose

This document defines the auditable contract for a future deterministic business
opportunity score. It identifies candidate dimensions, approved input owners,
metric direction, normalization decisions, missing-data behavior, quality safeguards,
provenance, versioning, and unresolved business decisions.

This version does **not** define an executable total-score formula, numeric weights,
normalization parameters, score thresholds, or an evaluator. The reserved algorithm
version is therefore `NON_EXECUTABLE`, and a conforming implementation must return a
null score until the P0 decisions in section 14 are approved and versioned.

The future score is an explanatory aid. It must not become an automatic final
selection decision, a recommendation, a probability of success, or a substitute for
human review.

## 2. Existing scoring audit

The repository already contains Opportunity Scoring V0.1 code, tests, and the
implemented field `workbook.opportunity_analysis.rule_process_score`. That framework:

- maps four Decision Framework availability conditions to four process factors;
- emits a fixed component allocation of `25` when the corresponding upstream rule
  analysis is available;
- uses explicit result states for missing, blocked, conflict-visible, and
  not-applicable cases;
- never converts unavailable evidence to zero;
- emits no `total_score`, aggregate, ranking, recommendation, or business decision;
- has no business weights, thresholds, desirability direction, or cross-metric
  normalization.

The fixed `25` is a process-rule allocation. It is not an opportunity desirability
value and **must not** be copied, normalized, weighted, or included in the future
business Opportunity Score. The implemented package and its tests remain unchanged.

The Workbook and semantic audit identify no other approved opportunity-score formula,
weight set, threshold set, or business desirability rule. Calculation Engine guidance
also prohibits a new composite rule until an accepted versioned configuration exists.

## 3. Inputs and ownership boundary

The future scoring layer consumes Provider-neutral, cleaned and analyzed records. It
does not parse XiYou or any other Provider payload.

```text
Provider evidence
-> Adapter / Canonical Evidence
-> Normalization / CleanCanonicalResult
-> MarketAnalysisResult / CompetitionAnalysisResult
-> future Opportunity Score evaluator
```

Existing owners remain authoritative:

| Responsibility | Authoritative owner |
|---|---|
| identity, raw lineage, normalized values | Canonical Data / Cleaning |
| observed distributions and directional relationship count | Market Analysis V1 |
| competition context, exact-context BSR, variation structure | Competition Analysis V1 |
| existing deterministic count/distribution formulas | Calculation Engine and the owning analysis layer |
| source quality and limitations | Cleaning, Market Analysis, Competition Analysis, Opportunity Intelligence |
| future score composition | Opportunity Scoring, only after approved versioned configuration |

Opportunity Scoring may reference existing results and provenance but must not duplicate
their formulas, silently select conflicting candidates, or reinterpret Provider fields.

## 4. Conceptual score architecture

The candidate architecture is deliberately separated into desirability dimensions,
context, and safeguards:

```text
Future Opportunity Score (NON_EXECUTABLE)
|
+-- Candidate desirability dimensions
|   +-- Demand Potential
|   +-- Competition Accessibility
|   +-- Product Economics Readiness (dependency-blocked)
|
+-- Non-scored market context
|   +-- Observed Product / Keyword Scope
|   +-- Product / Variation Structure
|
+-- Mandatory safeguards, reported separately
    +-- Data Confidence and Completeness
    +-- Risk and Limitations
```

This architecture does not approve inclusion of any dimension in an aggregate. P0 must
approve the active dimension set, eligibility gates, normalization functions, weights,
and aggregation formula together. Until then, every candidate desirability dimension
and the total score remain null.

### 4.1 Demand Potential

**Purpose and business meaning:** represent observed demand evidence for the exact
marketplace, keyword scope, snapshot, direction, and query boundary. More confirmed
demand can support opportunity, but an observed page or relationship inventory is not
market demand by itself.

**Inputs:** search volume when Provider semantics are confirmed, ABA rank, CPC, and
keyword-product relationship evidence/counts from Market Analysis.

**Direction:** higher confirmed search volume is positive; a higher numeric ABA rank is
negative because lower rank is stronger. CPC and relationship count remain neutral
context until their dual business meaning and population boundary are governed.

**Owner:** Market Analysis consumes cleaned Canonical keyword data; future Opportunity
Scoring owns only the versioned composition rule.

### 4.2 Competition Accessibility

**Purpose and business meaning:** represent barriers visible in the bounded observed
product sample. This is an observed competition sample, not a governed Comparable
Product Set and not total market competition.

**Inputs:** incumbent rating and review-count summaries, observed product count,
exact-context BSR summaries, and explicit variation structure.

**Direction:** higher incumbent ratings and review counts are negative barrier signals.
Observed product count, BSR, and variation structure are neutral context in V0.1 because
their opportunity interpretation depends on a governed population, exact rank meaning,
or an approved counting grain.

**Owner:** Competition Analysis, reusing Market Analysis and Calculation Engine results;
future Opportunity Scoring owns only approved composition.

### 4.3 Product Economics Readiness

**Purpose and business meaning:** reserve a dimension for economic attractiveness, not
mistake observed selling price for profitability.

**Inputs:** current observed product price is context only. A usable economics dimension
requires governed cost, Amazon fee, fulfillment, advertising, return/allowance, tax, and
margin semantics at a compatible marketplace/currency/snapshot scope.

**Direction:** observed price alone is neutral. No profitability direction or score may
be inferred from price without the missing economic inputs.

**Owner:** current price distribution is owned by Market Analysis. The dimension is
`BLOCKED_BY_PROFITABILITY_INPUTS` and has no executable formula.

### 4.4 Data Confidence and Completeness

This is a mandatory companion result, not a desirability dimension and not a hidden
weight. It reports valid sample counts, exclusions, missing/unknown/invalid/partial
states, compatibility limitations, and source quality issues. Higher completeness can
increase confidence; more exclusions and unresolved quality issues can reduce
confidence. The numeric confidence formula, minimum sample requirements, and blocking
thresholds are P0 decisions.

A future result must never present a sparse score as high-confidence. Until the quality
eligibility policy is approved, the total score remains blocked instead of manufacturing
a confidence adjustment.

### 4.5 Risk and Limitations

This is a mandatory evidence inventory, not an adjustment formula. Existing risk
evidence has no governed severity, probability, or numeric penalty. Risk stays visible
and traceable, but no risk value may change a dimension or total score until a versioned
risk policy is approved.

## 5. Metric contract and direction

`POSITIVE` means a higher compatible metric value would support opportunity.
`NEGATIVE` means a higher compatible metric value would reduce opportunity.
`NEUTRAL` means context-only: it cannot change a score in this specification.

| Metric | Dimension / role | Direction | Authoritative source | Current scoring status |
|---|---|---|---|---|
| `market_analysis.keyword_search_volume` | Demand Potential | POSITIVE | Market Analysis from cleaned `keyword.search_volume` | Blocked for XiYou while estimate method semantics are unconfirmed |
| `market_analysis.keyword_aba_rank` | Demand Potential | NEGATIVE | Market Analysis from cleaned `keyword.aba_rank` | Candidate; normalization and population policy required |
| `market_analysis.keyword_cpc` | Demand Potential | NEUTRAL | Market Analysis from cleaned `keyword.cpc` | Context only; may indicate intent and/or acquisition cost |
| `workbook.keyword_demand.related_product_count` | Market context | NEUTRAL | Calculation Engine through Market Analysis | Observed directional page count only |
| `market_analysis.product_rating` | Competition Accessibility | NEGATIVE | Competition Analysis reusing Market Analysis | Candidate barrier input |
| `market_analysis.product_review_count` | Competition Accessibility | NEGATIVE | Competition Analysis reusing Market Analysis | Candidate barrier input; zero is valid |
| `workbook.market_overview.observed_product_count` | Market context | NEUTRAL | Calculation Engine through Market/Competition Analysis | Bounded identity count, not market size |
| `competition_analysis.contextual_bsr` | Competition context | NEUTRAL | Competition Analysis from cleaned contextual BSR | Exact context only; no cross-category aggregation |
| `competition_analysis.variation_structure` | Product structure context | NEUTRAL | Competition Analysis from explicit Canonical relationships | Separate grains only; aggregate semantic unresolved |
| `market_analysis.observed_product_price` | Product Economics Readiness | NEUTRAL | Market Analysis from cleaned price | Observed price, not comparable price or profit |
| `market_analysis.quality` | Confidence / completeness | POSITIVE | Market Analysis | Companion metadata; no numeric confidence formula |
| `market_analysis.source_quality_issues` | Confidence / completeness | NEGATIVE | Cleaning / Market Analysis | Companion evidence; no numeric penalty |
| `opportunity_intelligence.risk_evidence` | Risk / limitations | NEUTRAL | Opportunity Intelligence | Visible evidence only; no severity or adjustment |

Directions apply only inside the exact compatible scope. They do not authorize a
transformation, threshold, weight, or total score.

## 6. Normalization strategy

CPC, counts, ratings, prices, and ranks have different units and distributions and must
never be directly added. This specification records candidate transformations for
business review but approves none:

| Metric class | Required compatibility boundary | Candidate strategies | Decision |
|---|---|---|---|
| search volume | marketplace, period/count unit, estimate method, snapshot | log transform then percentile; governed buckets | `BUSINESS_DECISION_REQUIRED` and current method block |
| ABA rank | marketplace, ABA universe/context, snapshot | inverse percentile; governed inverse buckets | `BUSINESS_DECISION_REQUIRED` |
| CPC | marketplace, explicit ISO currency, snapshot | within-scope percentile; governed currency buckets | direction first; then `BUSINESS_DECISION_REQUIRED` |
| rating | one explicit compatible rating scale | bounded scale transform; empirical percentile | `BUSINESS_DECISION_REQUIRED` |
| review count | compatible count semantic and snapshot | log transform then percentile; governed buckets | `BUSINESS_DECISION_REQUIRED` |
| observed product/relationship count | governed population and pagination completeness | log transform; percentile; buckets | context-only; population decision required first |
| BSR | identical marketplace/category/rank type/observation context | context-specific inverse percentile or buckets | context-only; direction and reference population required first |
| price | identical ISO currency and economic scope | percentile or margin transform | context-only; profitability inputs required first |
| variation structure | approved edge/evidence/unique-product grain | governed buckets after grain selection | `BLOCKED_BY_VARIATION_GRAIN` |

Min/max normalization is not safe without a frozen reference population and outlier
policy. Percentiles are not safe without a versioned comparison population. Logarithmic
transforms require zero/negative-domain behavior and parameters. Buckets require frozen
edges and tie behavior. All such parameters must be configuration, not hidden code.

Normalization version is `UNASSIGNED_BUSINESS_DECISION_REQUIRED`.

## 7. Weight and aggregation strategy

No existing business desirability weights were found. The existing fixed process value
`25` is not a weight and is excluded.

P0 must choose the source of truth for the first weight set: fixed versioned business
weights or versioned operator-configurable global weights. P1 may decide whether
category-specific or operator overrides are allowed. Learned weights are P2 research
only and cannot enter a deterministic V1 without separate governance and validation.

P0 must also define dimension activation, weight sum/scale, rounding, ties, caps,
eligibility gates, total-score range, and whether incomplete dimensions block the total
or permit a separately labelled partial score. Until approved:

- weight version is `UNASSIGNED_BUSINESS_DECISION_REQUIRED`;
- aggregation formula version is `UNASSIGNED_BUSINESS_DECISION_REQUIRED`;
- threshold version is `UNASSIGNED_BUSINESS_DECISION_REQUIRED`;
- no metric or dimension is executable.

## 8. Missing-data and quality policy

The following rules are already safe and mandatory:

1. `missing != 0`, `unknown != 0`, explicit null remains distinct, and invalid values
   are excluded.
2. A numeric zero remains valid where the metric semantic allows it, including review
   count.
3. Every metric reports valid sample count and excluded count; exclusions preserve
   reason/status.
4. Mixed currencies, units, rank contexts, marketplaces, or incompatible snapshots
   block unsafe aggregation.
5. Partial records do not destroy valid records, but the result remains visibly partial.
6. Multiple unresolved candidates are not averaged or silently selected.
7. Missing Provider evidence cannot be replaced by guessed values, averages, or a
   penalty masquerading as evidence.

The unresolved aggregate effect is explicit: for every desirability input, missing or
blocked data is reported and never zero-filled, while P0 decides whether that state
blocks its dimension, reduces only score completeness/confidence, or permits a labelled
partial dimension. The same decision must specify minimum sample sizes and required
metrics. No production score may be emitted before that policy exists.

Metric-specific behavior is:

| Input | Existing safe behavior | Unresolved score effect |
|---|---|---|
| search volume | remain blocked when estimate method is unconfirmed | demand dimension eligibility is P0 |
| ABA rank | exclude missing/invalid; require compatible unit/context | demand dimension eligibility is P0 |
| CPC | exclude missing/invalid; block mixed currency | direction and dimension eligibility are P0 |
| keyword/product relationship count | no validated relationship/query result means missing; partial pages stay partial | context only in V0.1 |
| rating | exclude missing/invalid; require compatible scale | dimension eligibility/minimum sample are P0 |
| review count | exclude missing/invalid; retain numeric zero | dimension eligibility/minimum sample are P0 |
| observed product count | no validated identity means `MISSING_INPUT`, never zero | context only in V0.1 |
| BSR | missing exact context or incompatible categories block aggregation | context only in V0.1 |
| variation structure | missing relationships do not imply zero variants | aggregate is blocked by grain decision |
| price | exclude missing/invalid; block mixed currency | economics dimension remains blocked |

## 9. Comparable Product, trend, and AI boundaries

- Observed products are not the governed Comparable Product Set. Neither
  `minimum_comparable_price` nor `maximum_comparable_price` is an input. Future use
  requires an explicit `COMPARABLE` membership assertion and compatible price scope.
- Trend is excluded. No window, direction, minimum observations, threshold, tie, or
  missing policy is approved. A future trend input must remain
  `BLOCKED_BY_TREND_DEFINITION` until those semantics are versioned.
- The score must remain deterministic. AI may later explain an already calculated,
  fully referenced result or help phrase a recommendation, but cannot generate,
  change, fill, normalize, weight, or threshold a score.
- Comparable scoring, Competition Score, ML, embeddings, and LLM scoring are outside
  this specification.

## 10. Future output contract

A future `OpportunityScoreResult` must be Provider-neutral and contain at least:

- `score_value`: nullable decimal; null unless an approved executable configuration is
  satisfied;
- `score_status`: explicit calculated, partial, blocked-data, blocked-context, or
  blocked-configuration state;
- `score_version` and specification version;
- analysis scope: marketplace, snapshot/run, product/keyword scope, and source result
  IDs;
- dimension records with nullable value, status, purpose, contributing metrics,
  direction, valid/excluded sample counts, missing inputs, and quality limitations;
- separate confidence/completeness result, including its version and limitations;
- risk and limitation evidence without an invented severity;
- metric, normalization, weight, aggregation, missing-policy, confidence-policy, and
  threshold version references;
- calculation and explanation references;
- end-to-end provenance.

The result must never be serialized or displayed as only a number such as `87`.

## 11. Provenance contract

Each contributing metric must retain this chain:

```text
Opportunity score result
-> score/dimension/metric rule and configuration versions
-> MarketAnalysisResult or CompetitionAnalysisResult metric
-> CleanCanonicalResult field and normalization record
-> Canonical Evidence / mapping version
-> RawEvidenceRef and source operation/field
-> Provider
```

The future score is `system-derived`; it must never be labelled as Provider supplied.
All excluded inputs, quality gates, and blocked dependencies require the same auditable
references where source evidence exists.

## 12. Versioning and change control

| Artifact | V0.1 identifier | Rule |
|---|---|---|
| specification | `opportunity-scoring-specification-v0.1` | changes to semantics or contract require a new version |
| future algorithm | `opportunity-score-v0.1` | reserved and non-executable until P0 approval |
| metric definitions | `opportunity-score-metrics-v0.1` | records metric identity, owner, direction, and compatibility |
| missing policy | `opportunity-score-missing-policy-v0.1` | only no-zero-fill/exclusion invariants are approved; aggregate effect remains unresolved |
| normalization | `UNASSIGNED_BUSINESS_DECISION_REQUIRED` | must identify transformations, populations, parameters, and rounding |
| weights | `UNASSIGNED_BUSINESS_DECISION_REQUIRED` | must identify source, dimension/metric weights, scope, and activation |
| aggregation formula | `UNASSIGNED_BUSINESS_DECISION_REQUIRED` | must identify formula, caps, range, and rounding |
| confidence policy | `UNASSIGNED_BUSINESS_DECISION_REQUIRED` | must identify adequacy gates, sample minima, and partial behavior |
| thresholds/display bands | `UNASSIGNED_BUSINESS_DECISION_REQUIRED` | must not be inferred from score range |

Any formula, input direction, transform, weight, required-input set, quality gate,
threshold, or rounding change requires a new owning version and replayable references.
Presentation-only label changes may version independently but cannot change calculation.

## 13. Blocked dependencies

| Dependency | Status | Required decision/evidence |
|---|---|---|
| XiYou search-volume score input | `BLOCKED_BY_ESTIMATE_METHOD` | confirmed search-volume method/unit semantics |
| comparable min/max price | `BLOCKED_BY_MEMBERSHIP_SOURCE` | governed `COMPARABLE` membership source |
| product economics/profitability | `BLOCKED_BY_PROFITABILITY_INPUTS` | compatible costs, fees, advertising, returns, tax, and margin contract |
| trend input | `BLOCKED_BY_TREND_DEFINITION` | window, direction, thresholds, ties, samples, missing behavior |
| variation aggregate | `BLOCKED_BY_VARIATION_GRAIN` | edge/evidence-record/unique-product grain and duplicate policy |
| seller competition input | `BLOCKED_BY_SELLER_IDENTITY` | confirmed seller identity semantics and source |
| BSR desirability input | `BLOCKED_BY_BSR_DIRECTION_POLICY` | exact comparison population and approved opportunity interpretation |
| CPC desirability input | `BLOCKED_BY_CPC_DIRECTION_POLICY` | decide demand-intent versus acquisition-cost interpretation |
| total opportunity score | `BLOCKED_BY_SCORING_CONFIGURATION` | all P0 composition, normalization, weight, missing, quality, and threshold decisions |

## 14. Business decision queue

### P0 — required before implementation

1. Approve the active desirability dimensions and whether Product Economics remains
   mandatory, optional, or excluded until its inputs exist.
2. Approve each dimension's required metrics and minimum valid sample sizes.
3. Approve each metric's normalization function, reference population, parameters,
   compatibility boundary, outlier behavior, and rounding.
4. Decide CPC direction and whether BSR can ever become a desirability input.
5. Choose the initial weight source and exact versioned weight set.
6. Define aggregation formula, score range, caps, rounding, and tie behavior.
7. Decide missing/blocked behavior per metric and dimension: block, confidence-only,
   or explicitly labelled partial calculation; never zero-fill.
8. Define confidence/completeness calculation, adequacy gates, and the rule preventing
   a sparse result from appearing high-confidence.
9. Define result statuses and whether any partial total score may be published.
10. Define threshold/band semantics if business labels are required.

### P1 — governance and operating model

1. Decide whether category-specific configurations are supported and how category
   identity is governed.
2. Decide whether operators may override weights and how overrides are authorized,
   versioned, and reproduced.
3. Define configuration approval, rollout, rollback, and historical replay procedures.
4. Decide whether a future governed Comparable Product Set can become an optional
   scoring dependency.
5. Define monitoring for distribution drift without automatically changing weights.

### P2 — presentation and future research

1. Choose score display format, labels, color bands, and explanation layout after
   threshold semantics exist.
2. Evaluate learned weights only under a separate governed research specification;
   they are not part of deterministic V1.
3. Define AI explanation wording constraints after the deterministic result contract is
   implemented; AI remains unable to generate or modify scores.

## 15. Machine-readable specification manifest

The following JSON is normative for mechanical documentation tests. It is configuration
metadata only; no production code loads or executes it.

<!-- MACHINE-READABLE-SPEC:START -->
```json
{
  "specification_version": "opportunity-scoring-specification-v0.1",
  "reserved_score_version": "opportunity-score-v0.1",
  "metric_definition_version": "opportunity-score-metrics-v0.1",
  "missing_policy_version": "opportunity-score-missing-policy-v0.1",
  "normalization_version": "UNASSIGNED_BUSINESS_DECISION_REQUIRED",
  "weight_version": "UNASSIGNED_BUSINESS_DECISION_REQUIRED",
  "aggregation_version": "UNASSIGNED_BUSINESS_DECISION_REQUIRED",
  "confidence_policy_version": "UNASSIGNED_BUSINESS_DECISION_REQUIRED",
  "execution_status": "NON_EXECUTABLE",
  "evaluator_implemented": false,
  "existing_process_score_boundary": {
    "field_id": "workbook.opportunity_analysis.rule_process_score",
    "fixed_component_value": 25,
    "meaning": "PROCESS_RULE_ALLOCATION_NOT_BUSINESS_DESIRABILITY",
    "included_in_opportunity_score": false
  },
  "dimensions": [
    {
      "dimension_id": "DEMAND_POTENTIAL",
      "classification": "CANDIDATE_DESIRABILITY",
      "purpose": "Represent compatible observed demand evidence for an exact scope.",
      "business_meaning": "Stronger confirmed demand may support opportunity without treating observed pages as market size.",
      "owner_layer": "MARKET_ANALYSIS_AND_FUTURE_OPPORTUNITY_SCORING",
      "normalization_requirement": "BUSINESS_DECISION_REQUIRED",
      "missing_policy": "NO_ZERO_FILL_REPORT_MISSING_AGGREGATE_EFFECT_P0",
      "quality_impact": "VALID_EXCLUDED_PARTIAL_AND_COMPATIBILITY_STATES_MUST_AFFECT_CONFIDENCE_OR_ELIGIBILITY_PER_P0",
      "confidence": "SEPARATE_UNASSIGNED_POLICY",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false,
      "metric_ids": [
        "market_analysis.keyword_search_volume",
        "market_analysis.keyword_aba_rank"
      ]
    },
    {
      "dimension_id": "COMPETITION_ACCESSIBILITY",
      "classification": "CANDIDATE_DESIRABILITY",
      "purpose": "Represent rating and review barriers in the bounded observed competition sample.",
      "business_meaning": "Higher compatible incumbent rating and review barriers reduce accessibility, without asserting Comparable membership.",
      "owner_layer": "COMPETITION_ANALYSIS_AND_FUTURE_OPPORTUNITY_SCORING",
      "normalization_requirement": "BUSINESS_DECISION_REQUIRED",
      "missing_policy": "NO_ZERO_FILL_REPORT_MISSING_AGGREGATE_EFFECT_P0",
      "quality_impact": "SAMPLE_COVERAGE_EXCLUSIONS_AND_CONTEXT_LIMITATIONS_MUST_AFFECT_CONFIDENCE_OR_ELIGIBILITY_PER_P0",
      "confidence": "SEPARATE_UNASSIGNED_POLICY",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false,
      "metric_ids": [
        "market_analysis.product_rating",
        "market_analysis.product_review_count"
      ]
    },
    {
      "dimension_id": "PRODUCT_ECONOMICS_READINESS",
      "classification": "DEPENDENCY_BLOCKED_DESIRABILITY",
      "purpose": "Represent economic attractiveness only when governed cost and margin inputs exist.",
      "business_meaning": "Observed price alone is not profitability.",
      "owner_layer": "MARKET_ANALYSIS_AND_FUTURE_ECONOMICS_OWNER",
      "normalization_requirement": "BLOCKED_BY_PROFITABILITY_INPUTS",
      "missing_policy": "BLOCK_DIMENSION_NO_ZERO_FILL",
      "quality_impact": "MISSING_ECONOMIC_INPUTS_BLOCK_DIMENSION",
      "confidence": "NOT_CALCULABLE",
      "formula_status": "BLOCKED_DEPENDENCY",
      "executable": false,
      "metric_ids": [
        "market_analysis.observed_product_price"
      ]
    },
    {
      "dimension_id": "MARKET_AND_PRODUCT_CONTEXT",
      "classification": "NON_SCORED_CONTEXT",
      "purpose": "Expose bounded scope and product structure without inventing desirability.",
      "business_meaning": "Observed counts, BSR contexts, relationships, and variations qualify interpretation but do not change score.",
      "owner_layer": "MARKET_ANALYSIS_AND_COMPETITION_ANALYSIS",
      "normalization_requirement": "NOT_APPLICABLE_CONTEXT_ONLY",
      "missing_policy": "NO_ZERO_FILL_REPORT_CONTEXT_LIMITATION",
      "quality_impact": "INCOMPLETE_CONTEXT_REMAINS_VISIBLE",
      "confidence": "CONTEXT_FOR_SEPARATE_POLICY",
      "formula_status": "NOT_APPLICABLE_CONTEXT_ONLY",
      "executable": false,
      "metric_ids": [
        "market_analysis.keyword_cpc",
        "workbook.keyword_demand.related_product_count",
        "workbook.market_overview.observed_product_count",
        "competition_analysis.contextual_bsr",
        "competition_analysis.variation_structure"
      ]
    },
    {
      "dimension_id": "DATA_CONFIDENCE_AND_COMPLETENESS",
      "classification": "MANDATORY_COMPANION_NOT_DESIRABILITY",
      "purpose": "Report whether score inputs are adequate, compatible, and complete.",
      "business_meaning": "Prevents sparse or low-quality evidence from appearing as a high-confidence opportunity.",
      "owner_layer": "CLEANING_MARKET_ANALYSIS_COMPETITION_ANALYSIS_AND_FUTURE_OPPORTUNITY_SCORING",
      "normalization_requirement": "CONFIDENCE_POLICY_BUSINESS_DECISION_REQUIRED",
      "missing_policy": "NO_ZERO_FILL_MISSING_QUALITY_METADATA_BLOCKS_FUTURE_SCORE",
      "quality_impact": "DIRECT_COMPANION_OUTPUT_AND_FUTURE_ELIGIBILITY_GATE",
      "confidence": "SELF_REPORTED_WITH_VERSIONED_POLICY",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false,
      "metric_ids": [
        "market_analysis.quality",
        "market_analysis.source_quality_issues"
      ]
    },
    {
      "dimension_id": "RISK_AND_LIMITATIONS",
      "classification": "MANDATORY_COMPANION_NOT_DESIRABILITY",
      "purpose": "Expose source-backed risks and limitations without invented severity.",
      "business_meaning": "Risk evidence qualifies human interpretation but has no numeric adjustment in V0.1.",
      "owner_layer": "OPPORTUNITY_INTELLIGENCE_AND_FUTURE_OPPORTUNITY_SCORING",
      "normalization_requirement": "NOT_APPLICABLE_UNTIL_RISK_POLICY",
      "missing_policy": "NO_ZERO_FILL_REPORT_ABSENCE_OR_LIMITATION",
      "quality_impact": "VISIBLE_COMPANION_OUTPUT_NO_NUMERIC_PENALTY",
      "confidence": "QUALITATIVE_ONLY",
      "formula_status": "NOT_APPLICABLE_CONTEXT_ONLY",
      "executable": false,
      "metric_ids": [
        "opportunity_intelligence.risk_evidence"
      ]
    }
  ],
  "metrics": [
    {
      "metric_id": "market_analysis.keyword_search_volume",
      "owner": "MARKET_ANALYSIS",
      "direction": "POSITIVE",
      "normalization": "BUSINESS_DECISION_REQUIRED_LOG_OR_PERCENTILE_OR_BUCKET",
      "missing_policy": "NO_ZERO_FILL_EXCLUDE_AND_REPORT_METHOD_BLOCK",
      "quality_impact": "BLOCK_WHEN_ESTIMATE_METHOD_OR_UNIT_SEMANTICS_UNCONFIRMED",
      "formula_status": "BLOCKED_DEPENDENCY",
      "executable": false
    },
    {
      "metric_id": "market_analysis.keyword_aba_rank",
      "owner": "MARKET_ANALYSIS",
      "direction": "NEGATIVE",
      "normalization": "BUSINESS_DECISION_REQUIRED_CONTEXTUAL_INVERSE_PERCENTILE_OR_BUCKET",
      "missing_policy": "NO_ZERO_FILL_EXCLUDE_MISSING_INVALID_REPORT",
      "quality_impact": "REQUIRE_COMPATIBLE_CONTEXT_UNIT_AND_SAMPLE_COUNTS",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false
    },
    {
      "metric_id": "market_analysis.keyword_cpc",
      "owner": "MARKET_ANALYSIS",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_UNTIL_DIRECTION_POLICY",
      "missing_policy": "NO_ZERO_FILL_EXCLUDE_MISSING_INVALID_BLOCK_MIXED_CURRENCY",
      "quality_impact": "REPORT_CURRENCY_COMPATIBILITY_AND_EXCLUSIONS",
      "formula_status": "NOT_APPLICABLE_CONTEXT_ONLY",
      "executable": false
    },
    {
      "metric_id": "workbook.keyword_demand.related_product_count",
      "owner": "CALCULATION_ENGINE_THROUGH_MARKET_ANALYSIS",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_CONTEXT_ONLY",
      "missing_policy": "NO_ZERO_FILL_MISSING_QUERY_IS_NOT_ZERO_PARTIAL_PAGE_STAYS_PARTIAL",
      "quality_impact": "REPORT_DIRECTION_QUERY_STATUS_PAGINATION_AND_DUPLICATE_POLICY",
      "formula_status": "NOT_APPLICABLE_CONTEXT_ONLY",
      "executable": false
    },
    {
      "metric_id": "market_analysis.product_rating",
      "owner": "COMPETITION_ANALYSIS_REUSING_MARKET_ANALYSIS",
      "direction": "NEGATIVE",
      "normalization": "BUSINESS_DECISION_REQUIRED_BOUNDED_SCALE_OR_PERCENTILE",
      "missing_policy": "NO_ZERO_FILL_EXCLUDE_MISSING_INVALID_REPORT",
      "quality_impact": "REQUIRE_COMPATIBLE_SCALE_VALID_AND_EXCLUDED_COUNTS",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false
    },
    {
      "metric_id": "market_analysis.product_review_count",
      "owner": "COMPETITION_ANALYSIS_REUSING_MARKET_ANALYSIS",
      "direction": "NEGATIVE",
      "normalization": "BUSINESS_DECISION_REQUIRED_LOG_OR_PERCENTILE_OR_BUCKET",
      "missing_policy": "NO_ZERO_FILL_EXCLUDE_MISSING_INVALID_RETAIN_VALID_ZERO",
      "quality_impact": "REQUIRE_COMPATIBLE_COUNT_SEMANTIC_VALID_AND_EXCLUDED_COUNTS",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false
    },
    {
      "metric_id": "workbook.market_overview.observed_product_count",
      "owner": "CALCULATION_ENGINE_THROUGH_MARKET_AND_COMPETITION_ANALYSIS",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_CONTEXT_ONLY",
      "missing_policy": "NO_ZERO_FILL_NO_VALIDATED_IDENTITY_MEANS_MISSING_INPUT",
      "quality_impact": "BOUNDED_SAMPLE_MUST_NOT_BE_LABELLED_MARKET_SIZE_OR_COMPARABLE_SET",
      "formula_status": "NOT_APPLICABLE_CONTEXT_ONLY",
      "executable": false
    },
    {
      "metric_id": "competition_analysis.contextual_bsr",
      "owner": "COMPETITION_ANALYSIS",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_UNTIL_DIRECTION_AND_REFERENCE_POPULATION_POLICY",
      "missing_policy": "NO_ZERO_FILL_BLOCK_WITHOUT_EXACT_RANK_CONTEXT",
      "quality_impact": "BLOCK_CROSS_CATEGORY_OR_INCOMPATIBLE_CONTEXT_AGGREGATION",
      "formula_status": "BLOCKED_DEPENDENCY",
      "executable": false
    },
    {
      "metric_id": "competition_analysis.variation_structure",
      "owner": "COMPETITION_ANALYSIS",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_CONTEXT_ONLY",
      "missing_policy": "NO_ZERO_FILL_NO_RELATIONSHIP_EVIDENCE_DOES_NOT_MEAN_ZERO_VARIANTS",
      "quality_impact": "INCOMPLETE_FAMILY_AND_DUPLICATE_IDENTITIES_REMAIN_VISIBLE",
      "formula_status": "BLOCKED_DEPENDENCY",
      "executable": false
    },
    {
      "metric_id": "market_analysis.observed_product_price",
      "owner": "MARKET_ANALYSIS",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_UNTIL_PROFITABILITY_INPUTS",
      "missing_policy": "NO_ZERO_FILL_EXCLUDE_MISSING_INVALID_BLOCK_MIXED_CURRENCY",
      "quality_impact": "OBSERVED_PRICE_NOT_COMPARABLE_PRICE_OR_MARGIN",
      "formula_status": "BLOCKED_DEPENDENCY",
      "executable": false
    },
    {
      "metric_id": "market_analysis.quality",
      "owner": "MARKET_ANALYSIS",
      "direction": "POSITIVE",
      "normalization": "CONFIDENCE_POLICY_BUSINESS_DECISION_REQUIRED",
      "missing_policy": "NO_ZERO_FILL_MISSING_QUALITY_METADATA_BLOCKS_FUTURE_SCORE",
      "quality_impact": "COMPANION_OUTPUT_AND_FUTURE_ELIGIBILITY_GATE",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false
    },
    {
      "metric_id": "market_analysis.source_quality_issues",
      "owner": "CLEANING_AND_MARKET_ANALYSIS",
      "direction": "NEGATIVE",
      "normalization": "CONFIDENCE_POLICY_BUSINESS_DECISION_REQUIRED",
      "missing_policy": "NO_ZERO_FILL_PRESERVE_ISSUE_INVENTORY_NO_ASSUMED_ZERO_ISSUES",
      "quality_impact": "COMPANION_OUTPUT_NO_UNVERSIONED_NUMERIC_PENALTY",
      "formula_status": "BUSINESS_DECISION_REQUIRED",
      "executable": false
    },
    {
      "metric_id": "opportunity_intelligence.risk_evidence",
      "owner": "OPPORTUNITY_INTELLIGENCE",
      "direction": "NEUTRAL",
      "normalization": "NOT_APPLICABLE_UNTIL_RISK_POLICY",
      "missing_policy": "NO_ZERO_FILL_PRESERVE_ABSENCE_AND_LIMITATION_NO_ASSUMED_ZERO_RISK",
      "quality_impact": "VISIBLE_WITHOUT_INVENTED_SEVERITY_PROBABILITY_OR_PENALTY",
      "formula_status": "NOT_APPLICABLE_CONTEXT_ONLY",
      "executable": false
    }
  ],
  "blocked_dependencies": [
    "BLOCKED_BY_ESTIMATE_METHOD",
    "BLOCKED_BY_MEMBERSHIP_SOURCE",
    "BLOCKED_BY_PROFITABILITY_INPUTS",
    "BLOCKED_BY_TREND_DEFINITION",
    "BLOCKED_BY_VARIATION_GRAIN",
    "BLOCKED_BY_SELLER_IDENTITY",
    "BLOCKED_BY_BSR_DIRECTION_POLICY",
    "BLOCKED_BY_CPC_DIRECTION_POLICY",
    "BLOCKED_BY_SCORING_CONFIGURATION"
  ],
  "excluded_inputs": [
    "workbook.product_structure.minimum_comparable_price",
    "workbook.product_structure.maximum_comparable_price",
    "workbook.market_overview.evidence_backed_trend",
    "workbook.competition_evidence.variation_evidence_count",
    "workbook.opportunity_analysis.rule_process_score",
    "AI_GENERATED_SCORE"
  ],
  "decision_queue": {
    "P0": [
      "ACTIVE_DIMENSION_SET",
      "REQUIRED_METRICS_AND_MINIMUM_SAMPLES",
      "NORMALIZATION_FUNCTIONS_AND_REFERENCE_POPULATIONS",
      "CPC_AND_BSR_DIRECTION_POLICY",
      "WEIGHT_SOURCE_AND_VALUES",
      "AGGREGATION_RANGE_ROUNDING_AND_TIES",
      "MISSING_AND_PARTIAL_SCORE_POLICY",
      "CONFIDENCE_COMPLETENESS_AND_ADEQUACY_GATES",
      "RESULT_STATUSES_AND_PARTIAL_PUBLICATION",
      "THRESHOLD_AND_BAND_SEMANTICS"
    ],
    "P1": [
      "CATEGORY_SPECIFIC_CONFIGURATION",
      "OPERATOR_WEIGHT_OVERRIDES",
      "CONFIGURATION_GOVERNANCE_AND_REPLAY",
      "FUTURE_COMPARABLE_SET_DEPENDENCY",
      "DISTRIBUTION_DRIFT_MONITORING"
    ],
    "P2": [
      "DISPLAY_FORMAT_LABELS_AND_COLORS",
      "SEPARATE_LEARNED_WEIGHT_RESEARCH",
      "DETERMINISTIC_RESULT_EXPLANATION_WORDING"
    ]
  }
}
```
<!-- MACHINE-READABLE-SPEC:END -->

## 16. Implementation boundary

The next implementation task may begin only after P0 produces accepted, versioned
configuration. That task may add an evaluator and numeric tests, but it must reuse the
existing Canonical, Cleaning, Market Analysis, Competition Analysis, Calculation Engine,
and Provenance boundaries. This document itself authorizes no production calculation.
