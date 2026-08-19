# Opportunity Scoring Engine Architecture V0.1

Status: architecture and contract skeleton; business scoring is non-executable

Architecture version: `opportunity-scoring-engine-architecture-v0.1`

Configuration status: `BUSINESS_DECISION_REQUIRED`

Parent specifications:

- `opportunity-scoring-specification-v0.1`
- `opportunity-scoring-input-contract-v0.1`

## 0. Purpose and hard boundary

This architecture defines the interfaces, state model, orchestration boundary, quality
companions, risk records, provenance, and explanation structure for a future business
Opportunity Scoring Engine. It does not decide which product is good.

V0.1 intentionally contains no business weight, threshold, normalization parameter,
dimension formula, aggregate formula, score band, ranking rule, profit formula, or
recommendation. The score value is always null. Every unresolved business parameter is
serialized as `BUSINESS_DECISION_REQUIRED`.

The existing `OpportunityScoringBuilderV0_1` remains a separate audited process-result
framework. Its fixed component value `25` is not a business opportunity score and is
not an input, weight, threshold, dimension value, or default for this engine.

No Connector, Canonical model, Workbook field, API endpoint, credential, or Provider
mapping is changed by this architecture.

## 1. Scoring Engine Overview

The engine consumes Provider-neutral, normalized Canonical and owned-analysis inputs.
It never reads raw XiYou/Sorftime payloads, calls an API, loads credentials, or reads a
Workbook as the source of truth.

```text
Canonical Data / owned analysis results
        |
        v
OpportunityScoringEngineInput
        |
        v
Scoring Engine
        |
        v
OpportunityScoringEngineResult
        |
        v
AI Explanation (optional rendering only)
        |
        v
Workbook projection (future downstream handoff)
```

The current engine may assemble input state, dimension readiness, qualitative quality,
risk evidence, provenance, and structured explanations. It cannot produce a numeric
business score because the required configuration has not been approved.

AI is downstream. It may rephrase an already structured explanation, but it may not
create evidence, fill missing inputs, resolve conflicts, choose weights, change state,
or generate a score.

## 2. Engine Component Design

### 2.1 `ScoringEngine`

Responsibilities:

- validate one `OpportunityScoringEngineInput`;
- request one result for each required dimension;
- request quality and risk companions;
- require an explanation for every dimension;
- preserve provenance on the final result;
- expose configuration as `BUSINESS_DECISION_REQUIRED`;
- keep `score_value=null`.

The orchestrator contains no business calculation. Evaluators are dependency-injected
interfaces so later executable versions can be governed and versioned separately.

### 2.2 `DimensionEvaluator`

Responsibilities:

- inspect only the input records assigned to one dimension;
- return state, evidence, missing inputs, risks, and conflict references;
- keep its dimension score null in V0.1.

It must not read Provider payloads, infer missing values, select a conflict winner, or
borrow the fixed process allocation from the existing scoring framework.

### 2.3 `QualityEvaluator`

Responsibilities:

- report qualitative confidence and the reasons for it;
- report available, missing, pending, and conflicting input identities;
- distinguish quality/readiness from desirability.

No numeric confidence formula, minimum-sample threshold, completeness threshold, or
hidden score adjustment is defined.

### 2.4 `RiskEvaluator`

Responsibilities:

- expose missing-data, incompatible-scope, unresolved-conflict, and dependency risks;
- attach evidence references where source evidence exists;
- keep risk separate from desirability.

No severity scale, probability, penalty, multiplier, or risk-adjusted score exists.

### 2.5 `ExplanationBuilder`

Responsibilities:

- produce one structured explanation per dimension;
- reference the metrics, sources, snapshots, and provenance used;
- separate positive factors, negative factors, missing data, and risk;
- explain non-numeric states as carefully as future calculated states.

An output without all three explanations is invalid.

## 3. Input Contract

`OpportunityScoringEngineInput` contains:

| Field | Contract |
|---|---|
| `product_identity` | Stable product ID, normalized ASIN, and marketplace. |
| `metrics` | Mapping of metric ID to value/state, dimension, source, snapshot, timestamp, confidence, completeness, provenance ID, and quality flags. |
| `provenance` | Explicit source chain for every referenced metric. |
| `quality` | Qualitative confidence/completeness plus missing inputs, conflicts, and limitations. |

Every metric must satisfy all of the following:

1. its mapping key equals `metric_id`;
2. its provenance reference exists;
3. metric source, snapshot, timestamp, and Canonical field match provenance;
4. `AVAILABLE` carries a value;
5. `MISSING`, `NOT_AVAILABLE`, `UNKNOWN`, `PENDING`, and `CONFLICT` do not carry a
   selected value;
6. missing and conflict states are never converted to numeric zero.

Example:

```json
{
  "product_identity": {
    "product_id": "product:US:B0G2VV4RBW",
    "asin": "B0G2VV4RBW",
    "marketplace": "US"
  },
  "metrics": {
    "metric.review_count": {
      "metric_id": "metric.review_count",
      "dimension": "COMPETITION_ACCESSIBILITY",
      "value": 1500,
      "status": "AVAILABLE",
      "source": "sorftime",
      "snapshot_id": "snapshot-001",
      "timestamp": "2026-08-19T03:00:00Z",
      "confidence": "high",
      "completeness": "COMPLETE",
      "provenance_id": "provenance:review-count:001",
      "quality_flags": []
    }
  },
  "provenance": [
    {
      "provenance_id": "provenance:review-count:001",
      "canonical_field": "metric.review_count",
      "source": "sorftime",
      "snapshot_id": "snapshot-001",
      "timestamp": "2026-08-19T03:00:00Z",
      "source_field": "data.review_count",
      "raw_evidence_id": "raw:sorftime:001"
    }
  ],
  "quality": {
    "confidence": "high",
    "completeness": "PARTIAL",
    "missing_inputs": ["TOP_PRODUCT_COHORT"],
    "conflict_ids": [],
    "limitations": ["Observed products are not a governed TOP cohort."]
  }
}
```

The example is an input-validation example, not a product score.

## 4. Dimension Contract

Each `DimensionResult` contains:

- `dimension`;
- `result_status`;
- referenced `evidence`;
- `missing_inputs`;
- `risks`;
- `conflict_ids`;
- `score_value=null`;
- `business_parameters_status=BUSINESS_DECISION_REQUIRED`.

### 4.1 `DEMAND_POTENTIAL`

Inputs are those identified by SP-022B, including keyword search volume, ABA rank,
CPC, directional keyword/product evidence, separate sales/order evidence, and dated
trend observations where available.

Output reports only:

- evidence readiness state;
- exact metric/source/snapshot references;
- missing demand inputs and unresolved method/period dependencies.

No trend direction, market-size substitution, demand score, or demand weight is
implemented.

### 4.2 `COMPETITION_ACCESSIBILITY`

Inputs are those identified by SP-022B, including governed-scope rating/review
evidence, observed product context, exact-context BSR, variation structure, and future
cohort/concentration dependencies.

Output reports only:

- evidence readiness state;
- evidence references;
- missing cohort/context inputs;
- conflict and risk records.

Observed products are not silently promoted to TOP or Comparable Products. No
competition score or accessibility threshold is implemented.

### 4.3 `PRODUCT_ECONOMICS_READINESS`

This is economic data readiness, not profit attractiveness.

Inputs may include compatible observed selling price, price-history evidence,
separately identified sales/order estimates, and future governed cost/fee/logistics
records.

Output reports only:

- whether the necessary economic evidence is ready, partial, pending, insufficient,
  or conflicting;
- missing cost, fee, period, unit, currency, and provenance dependencies;
- risk evidence.

It cannot emit margin, ROI, profit, revenue, break-even, or economics desirability.

## 5. Output Contract

`OpportunityScoringEngineResult` contains:

| Field | Contract |
|---|---|
| `result_status` | Overall readiness/state result. |
| `score_version` | `BUSINESS_DECISION_REQUIRED` in V0.1. |
| `dimension_results` | Exactly one result for each of the three dimensions. |
| `confidence` | Qualitative level and explicit reasons; no probability. |
| `completeness` | Available, missing, pending, and conflicting input identities. |
| `risks` | Separate risk evidence records; no penalty. |
| `missing_inputs` | Explicit unresolved input/configuration identities. |
| `provenance` | Source, snapshot, timestamp, Canonical field, and raw evidence reference. |
| `explanations` | Exactly one structured explanation per dimension. |
| `configuration` | All business parameters remain `BUSINESS_DECISION_REQUIRED`. |
| `score_value` | Always null in architecture V0.1. |

Example boundary:

```json
{
  "result_status": "PENDING",
  "score_version": "BUSINESS_DECISION_REQUIRED",
  "score_value": null,
  "dimension_results": [
    {"dimension": "DEMAND_POTENTIAL", "result_status": "PARTIAL", "score_value": null},
    {"dimension": "COMPETITION_ACCESSIBILITY", "result_status": "PARTIAL", "score_value": null},
    {"dimension": "PRODUCT_ECONOMICS_READINESS", "result_status": "INSUFFICIENT_DATA", "score_value": null}
  ],
  "confidence": {"level": "low", "reasons": ["Required business inputs remain missing."]},
  "completeness": {"level": "PARTIAL"},
  "risks": [],
  "missing_inputs": ["SCORING_CONFIGURATION", "PROFITABILITY_INPUTS"],
  "provenance": [
    {
      "provenance_id": "provenance:review-count:001",
      "canonical_field": "metric.review_count",
      "source": "sorftime",
      "snapshot_id": "snapshot-001",
      "timestamp": "2026-08-19T03:00:00Z",
      "source_field": "data.review_count",
      "raw_evidence_id": "raw:sorftime:001"
    }
  ],
  "explanations": [
    {"dimension": "DEMAND_POTENTIAL", "summary": "Demand evidence is partial."},
    {"dimension": "COMPETITION_ACCESSIBILITY", "summary": "Competition evidence is partial."},
    {"dimension": "PRODUCT_ECONOMICS_READINESS", "summary": "Required economic inputs are missing."}
  ],
  "configuration": {
    "score_version": "BUSINESS_DECISION_REQUIRED",
    "dimension_weights": "BUSINESS_DECISION_REQUIRED",
    "thresholds": "BUSINESS_DECISION_REQUIRED",
    "aggregation_formula": "BUSINESS_DECISION_REQUIRED",
    "normalization_parameters": "BUSINESS_DECISION_REQUIRED"
  }
}
```

The abbreviated example shows the outer shape only. A valid contract instance must
contain complete dimension records, non-empty provenance, and one explanation for
each dimension. A response such as `{"score": 80}` is invalid.

## 6. State Model

These are readiness/evaluation states, not score bands:

| State | Trigger contract |
|---|---|
| `READY` | Required compatible evidence for that dimension is present, no required input is missing, and no unresolved conflict exists. This does not mean the opportunity is good. |
| `PARTIAL` | Some usable evidence exists, but one or more required inputs or coverage elements are missing. Both evidence and missing identities must be reported. |
| `PENDING` | Evidence/configuration is expected but awaits a governed source, upstream processing, or business approval. In V0.1 the overall engine is normally `PENDING` because scoring configuration is unapproved. |
| `INSUFFICIENT_DATA` | The available evidence cannot support evaluation of the dimension. Missing input identities are mandatory. |
| `CONFLICT` | Multiple unresolved candidates or incompatible contexts prevent a selected input. Conflict IDs and source evidence are mandatory. |

State precedence for current orchestration is deliberately minimal:

1. a conflicting dimension makes the overall result `CONFLICT`;
2. otherwise the unapproved scoring configuration keeps the overall result `PENDING`;
3. no state produces a numeric score in V0.1.

No threshold is used to select these states. Contract invariants rely only on explicit
presence, missing, pending, and conflict records supplied by upstream owners.

## 7. Configuration Strategy

Future executable business configuration must be external, immutable, versioned,
reviewable, and included in provenance. It must eventually identify at least:

```yaml
score_version: <approved version>
active_dimensions: <approved dimensions>
dimension_weights: <approved external mapping>
metric_weights: <approved external mapping>
normalization_parameters: <approved rules and reference populations>
thresholds: <approved external mapping>
aggregation_formula: <approved formula version>
missing_data_policy: <approved eligibility policy>
confidence_policy: <approved adequacy policy>
rounding_policy: <approved rule>
```

Current configuration is exactly:

```yaml
score_version: BUSINESS_DECISION_REQUIRED
dimension_weights: BUSINESS_DECISION_REQUIRED
thresholds: BUSINESS_DECISION_REQUIRED
aggregation_formula: BUSINESS_DECISION_REQUIRED
normalization_parameters: BUSINESS_DECISION_REQUIRED
```

There are no hard-coded defaults. Configuration values other than the required
sentinel are rejected by the V0.1 contract.

## 8. Explainability Design

Every dimension explanation contains:

### Evidence

- metric identity;
- source;
- snapshot ID;
- timestamp;
- provenance ID.

### Reason

- positive factors, when an approved future interpretation exists;
- negative factors, when an approved future interpretation exists;
- current missing or pending dependencies;
- a non-empty bounded summary.

V0.1 supports the structure but does not invent positive/negative business direction
where SP-022A/B leaves it unresolved.

### Risk

- missing input identity;
- unresolved conflict identity;
- incompatible marketplace, currency, period, unit, cohort, or rank context;
- source/method/completeness limitation.

Explanation records never change state or values. An AI renderer must consume this
structure read-only and must cite the same evidence references.

## 9. Validation and acceptance invariants

1. Input product identity, metric source, timestamp, confidence, completeness, and
   provenance are mandatory.
2. Metric-to-provenance source context must match exactly.
3. Exactly three dimension results are required.
4. Missing and conflict states cannot carry a selected metric value.
5. `READY`, `PARTIAL`, `PENDING`, `INSUFFICIENT_DATA`, and `CONFLICT` have mechanically
   distinct validation requirements.
6. A conflict result requires conflict IDs.
7. Every dimension requires one non-empty explanation.
8. Output always retains provenance and cannot be only a number.
9. `score_value` is null and every business configuration value is
   `BUSINESS_DECISION_REQUIRED`.
10. No test or implementation calls a real API or reads credentials.

## 10. Deferred business decisions

The following remain explicitly deferred:

- active metric and dimension set;
- eligibility and minimum-sample rules;
- normalization strategies and reference populations;
- weights and aggregation formula;
- thresholds, score range, bands, rounding, and tie behavior;
- partial-score and missing-data policy;
- numeric/qualitative confidence policy;
- risk severity or adjustment policy;
- economics input requirements and profitability semantics;
- trend definition and cohort/comparable membership.

Until these decisions are approved together and assigned new versions, this engine is
an auditable readiness and explanation skeleton only.
