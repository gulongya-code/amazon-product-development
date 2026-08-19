# Business Scoring Configuration Specification V0.1

- Specification version: `business-scoring-configuration-specification-v0.1`
- Current execution status: `NON_EXECUTABLE`
- Current business parameter status: `BUSINESS_DECISION_REQUIRED`
- Parent architecture: `opportunity-scoring-engine-architecture-v0.1`
- Input owner: `OpportunityResult` / three `DimensionEvaluationResult` records

This specification defines how future business scoring policy is represented,
versioned, reviewed, validated, selected, and audited. It defines no weight,
threshold, score formula, score band, profit rule, or product recommendation.

The existing fixed rule-process values in the legacy Opportunity Scoring V0.1
framework are not defaults for this configuration and must not be copied into it.
No Evaluator, Canonical Model, Connector, Workbook field, or Workbook structure is
changed by this specification.

## 1. Scoring Configuration Overview

Business scoring configuration is the governed boundary between evidence/readiness
analysis and a future numeric Opportunity Score. It converts approved operating policy
into external data that an engine may validate and execute; it does not place policy
inside Python code.

```text
Dimension Results
        |
        v
Versioned Business Scoring Configuration
        |
        v
Future Scoring Engine
        |
        v
Opportunity Score Result
```

The current flow stops before numeric scoring:

```text
OpportunityResult + NON_EXECUTABLE configuration draft
        |
        v
Validation / BUSINESS_DECISION_REQUIRED report only
        |
        v
score_value = null
```

Configuration is not evidence. It may define how eligible evidence is interpreted in
a future engine, but it may not create metric values, repair missing inputs, select a
conflict winner, change provenance, or turn an `INSUFFICIENT_DATA` result into complete
data.

## 2. Configuration Principles

### 2.1 External configuration

- Business parameters must be loaded from a separately governed configuration
  artifact, never embedded as source constants, conditional branches, or defaults.
- The engine must receive an explicit `configuration_id`; it must not silently use
  “latest”, a local fallback, environment-specific numbers, or Workbook cells.
- Secrets and API credentials are outside this configuration and must never appear in
  it.

### 2.2 Version control and immutability

- Every saved configuration artifact is immutable and content-addressable.
- A change creates a new `configuration_id`; an approved change that can alter a score
  also creates a new `score_version`.
- Historical configurations, approval records, and effective periods remain
  retrievable so a prior result can be reproduced.

### 2.3 Auditability

- Every parameter records an owner, decision/change reference, approval identity,
  approval time, and configuration fingerprint.
- The result records the exact configuration ID, score version, and fingerprint used.
- Configuration validation and future rule execution produce machine-readable trace
  records. A numeric result without these references is invalid.

### 2.4 No hard-coded business policy

- Source code owns parsing, structural validation, deterministic execution, and audit
  emission only.
- Operations owns weights, directions, eligibility, thresholds, missing-data policy,
  economics requirements, score bands, and entry/exit standards.
- A code release must not be required merely to adjust an approved business parameter.

### 2.5 Controlled adjustment

- Drafts may contain `BUSINESS_DECISION_REQUIRED` and are non-executable.
- Approved/active configurations must be complete, internally consistent, and linked
  to an approval record before use.
- Activation is explicit by scope and effective period; silent retroactive changes are
  prohibited.

## 3. Configuration Schema

### 3.1 Logical envelope

The following YAML defines the future shape, not executable values. Every field that
could change a business score remains `BUSINESS_DECISION_REQUIRED`.

```yaml
configuration_schema_version: business-scoring-configuration-schema-v0.1
configuration_id: BUSINESS_DECISION_REQUIRED
score_version: BUSINESS_DECISION_REQUIRED
lifecycle_status: DRAFT

scope:
  marketplace: BUSINESS_DECISION_REQUIRED
  category_scope: BUSINESS_DECISION_REQUIRED
  currency_policy: BUSINESS_DECISION_REQUIRED
  effective_from: BUSINESS_DECISION_REQUIRED
  effective_to: BUSINESS_DECISION_REQUIRED

dimensions:
  DEMAND_POTENTIAL:
    enabled: BUSINESS_DECISION_REQUIRED
    weight: BUSINESS_DECISION_REQUIRED
    eligibility_policy: BUSINESS_DECISION_REQUIRED
    missing_data_policy: BUSINESS_DECISION_REQUIRED
    rules:
      - metric_id: BUSINESS_DECISION_REQUIRED
        enabled: BUSINESS_DECISION_REQUIRED
        weight: BUSINESS_DECISION_REQUIRED
        direction: BUSINESS_DECISION_REQUIRED
        normalization: BUSINESS_DECISION_REQUIRED
        thresholds: BUSINESS_DECISION_REQUIRED
        missing_data_policy: BUSINESS_DECISION_REQUIRED

  COMPETITION_ACCESSIBILITY:
    enabled: BUSINESS_DECISION_REQUIRED
    weight: BUSINESS_DECISION_REQUIRED
    eligibility_policy: BUSINESS_DECISION_REQUIRED
    missing_data_policy: BUSINESS_DECISION_REQUIRED
    risk_treatment: BUSINESS_DECISION_REQUIRED
    rules:
      - metric_id: BUSINESS_DECISION_REQUIRED
        enabled: BUSINESS_DECISION_REQUIRED
        weight: BUSINESS_DECISION_REQUIRED
        direction: BUSINESS_DECISION_REQUIRED
        normalization: BUSINESS_DECISION_REQUIRED
        thresholds: BUSINESS_DECISION_REQUIRED
        missing_data_policy: BUSINESS_DECISION_REQUIRED

  PRODUCT_ECONOMICS_READINESS:
    enabled: BUSINESS_DECISION_REQUIRED
    weight: BUSINESS_DECISION_REQUIRED
    required_cost_inputs: BUSINESS_DECISION_REQUIRED
    eligibility_policy: BUSINESS_DECISION_REQUIRED
    insufficient_data_policy: BUSINESS_DECISION_REQUIRED
    profit_rule: BUSINESS_DECISION_REQUIRED
    rules:
      - metric_id: BUSINESS_DECISION_REQUIRED
        enabled: BUSINESS_DECISION_REQUIRED
        weight: BUSINESS_DECISION_REQUIRED
        direction: BUSINESS_DECISION_REQUIRED
        normalization: BUSINESS_DECISION_REQUIRED
        thresholds: BUSINESS_DECISION_REQUIRED
        missing_data_policy: BUSINESS_DECISION_REQUIRED

aggregation:
  formula_id: BUSINESS_DECISION_REQUIRED
  score_range: BUSINESS_DECISION_REQUIRED
  dimension_missing_policy: BUSINESS_DECISION_REQUIRED
  conflict_policy: BUSINESS_DECISION_REQUIRED
  rounding_policy: BUSINESS_DECISION_REQUIRED

score_bands:
  definitions: BUSINESS_DECISION_REQUIRED
  boundary_policy: BUSINESS_DECISION_REQUIRED
  display_labels: BUSINESS_DECISION_REQUIRED

governance:
  business_owner: BUSINESS_DECISION_REQUIRED
  decision_reference: BUSINESS_DECISION_REQUIRED
  approved_by: BUSINESS_DECISION_REQUIRED
  approved_at: BUSINESS_DECISION_REQUIRED
  change_summary: BUSINESS_DECISION_REQUIRED
  configuration_fingerprint: BUSINESS_DECISION_REQUIRED
```

`DRAFT` is a system lifecycle state, not a score rule. This example cannot be used to
calculate a score because it contains the decision sentinel and has no approval.

### 3.2 Parameter classes

| Parameter class | Examples | Owner | Current status |
|---|---|---|---|
| System identity | Schema version, configuration ID format, fingerprint algorithm | System/architecture | Defined structurally; no business value |
| Scope | Marketplace, category scope, currency policy, effective period | Operations with data governance | `BUSINESS_DECISION_REQUIRED` |
| Dimension policy | Enabled dimensions, dimension weights, eligibility | Operations | `BUSINESS_DECISION_REQUIRED` |
| Metric policy | Metric inclusion, weight, direction, normalization, thresholds | Operations | `BUSINESS_DECISION_REQUIRED` |
| Missing/conflict policy | Eligibility, block/partial behavior, conflict handling | Operations with data governance | `BUSINESS_DECISION_REQUIRED` |
| Economics policy | Required cost/fee/logistics inputs and future profit semantics | Operations/finance owner | `BUSINESS_DECISION_REQUIRED` |
| Aggregation/display | Formula, score range, rounding, bands, boundary behavior | Operations | `BUSINESS_DECISION_REQUIRED` |
| Audit metadata | Decision reference, approver, effective time, change summary | Governance/system | Required before approval |

### 3.3 Sentinel semantics

`BUSINESS_DECISION_REQUIRED` means no approved value exists. It is not zero, null, an
empty list, a default, or an instruction to infer a value. It is valid only in a
non-executable draft or validation report. Any executable/active configuration that
contains the sentinel in a business parameter is invalid.

## 4. Dimension Configuration

Dimension configuration governs future interpretation only. The SP-022C-2 Evaluators
continue to report evidence readiness without consulting these parameters.

### 4.1 `DEMAND_POTENTIAL`

The future configuration must explicitly decide:

- which approved demand metrics are active;
- metric and dimension weights;
- direction for keyword volume, keyword trend, sales trend, category growth, market
  size, and seasonality;
- normalization/reference population and compatible period/window requirements;
- metric thresholds and boundary inclusivity;
- missing, pending, insufficient, and conflict behavior;
- whether one-point observations are eligible (they must not be treated as growth by
  default).

Current values:

| Parameter | Value |
|---|---|
| Metric weights | `BUSINESS_DECISION_REQUIRED` |
| Metric directions | `BUSINESS_DECISION_REQUIRED` |
| Normalization | `BUSINESS_DECISION_REQUIRED` |
| Thresholds | `BUSINESS_DECISION_REQUIRED` |
| Missing-data policy | `BUSINESS_DECISION_REQUIRED` |

### 4.2 `COMPETITION_ACCESSIBILITY`

The future configuration must explicitly decide:

- active review, rating, brand concentration, seller, price competition, and exact
  BSR-context inputs;
- direction and normalization for every active metric;
- cohort/comparable membership requirements;
- whether and how risk records affect eligibility or a future score;
- conflict, missing-brand, missing-seller, partial-pagination, and incompatible-context
  behavior;
- dimension and metric weights and thresholds.

The configuration must not equate a review count with high/low competition unless an
approved versioned rule says so. Risk records have no implicit penalty.

| Parameter | Value |
|---|---|
| Metric/dimension direction | `BUSINESS_DECISION_REQUIRED` |
| Risk treatment | `BUSINESS_DECISION_REQUIRED` |
| Cohort eligibility | `BUSINESS_DECISION_REQUIRED` |
| Thresholds | `BUSINESS_DECISION_REQUIRED` |
| Missing/conflict policy | `BUSINESS_DECISION_REQUIRED` |

### 4.3 `PRODUCT_ECONOMICS_READINESS`

This dimension remains data readiness until an approved economics configuration
exists. The future configuration must explicitly decide:

- required product cost, logistics, fee, advertising, return, tax, and allowance
  inputs;
- unit, currency, effective-period, marketplace, and product-grain compatibility;
- revenue-period and sales-estimate eligibility;
- the future profit/margin formula and treatment of fees, returns, taxes, and costs;
- incomplete-cost and insufficient-data behavior;
- direction, weights, thresholds, rounding, and score-band relationship.

No absent cost is zero and no margin is calculated by this specification.

| Parameter | Value |
|---|---|
| Required cost inputs | `BUSINESS_DECISION_REQUIRED` |
| Revenue eligibility | `BUSINESS_DECISION_REQUIRED` |
| Profit/margin rule | `BUSINESS_DECISION_REQUIRED` |
| Insufficient-data policy | `BUSINESS_DECISION_REQUIRED` |
| Weights/thresholds | `BUSINESS_DECISION_REQUIRED` |

## 5. Score Versioning

### 5.1 Version identities

Three identities are separate:

| Identity | Purpose |
|---|---|
| `configuration_schema_version` | Defines the accepted document structure and validator behavior. |
| `score_version` | Identifies one complete business scoring strategy and its result semantics, for example future `v0.1` or `v0.2`. |
| `configuration_id` | Identifies one immutable configuration artifact, including scope, effective period, approvals, and content fingerprint. |

The examples `v0.1` and `v0.2` illustrate the mechanism only; neither is approved for
execution by this document.

### 5.2 Change rules

- Any change to a business parameter creates a new immutable `configuration_id`.
- Any change that can alter eligibility, a numeric result, a score band, or displayed
  interpretation requires a new `score_version`.
- A schema-only compatibility change requires a new schema version and an explicit
  compatibility declaration.
- Retired configurations remain readable for replay and audit.
- A result must never resolve a configuration by an unpinned “latest” alias.

### 5.3 Lifecycle

| State | Meaning | Executable |
|---|---|---|
| `DRAFT` | Incomplete or under review; may contain the decision sentinel. | No |
| `APPROVED` | Complete and signed, but not necessarily active for a scope/time. | Only after explicit activation selection |
| `ACTIVE` | Explicitly selected for a defined scope and effective period. | Future engine only |
| `RETIRED` | Preserved for historical reproduction; not selected for new runs. | Replay only |

Promotion must be recorded as an audit event. Editing an approved or active artifact
in place is prohibited.

## 6. Business Parameter Ownership

| Decision or responsibility | Operations/business owner | Data/finance governance | System/engineering |
|---|---|---|---|
| Dimension/metric inclusion and weights | Decides and approves | Reviews semantic compatibility | Loads and validates only |
| Metric direction and entry standards | Decides and approves | Confirms metric meaning, unit, scope | Executes approved rule in a future phase |
| Thresholds, bands, rounding, tie behavior | Decides and approves | Reviews data-domain assumptions | Validates declared structure and determinism |
| Missing/partial/conflict policy | Decides business behavior | Defines safe evidence eligibility | Enforces policy without filling data |
| Economics input requirements and profit semantics | Approves with finance owner | Confirms cost/currency/period semantics | Validates dependencies; future execution only |
| Configuration IDs, fingerprints, immutable storage | Supplies decision references | Supplies approval records | Generates/validates and retains artifacts |
| Runtime selection | Authorizes scope/effective period | May apply governance blocks | Requires explicit ID; no implicit latest/default |
| Calculation trace and result provenance | Reviews output | Audits evidence/config chain | Produces deterministic trace in future engine |

The system must never invent an operational parameter to make a configuration pass.
Operations cannot override source provenance or label missing data as zero through a
configuration.

## 7. Validation Rules

Validation has four layers. Passing validation means the configuration is structurally
eligible for future execution; it does not mean the strategy is commercially correct.

### 7.1 Structural validation

- The schema version, configuration ID, score version, lifecycle status, scope,
  dimensions, aggregation, score-band, and governance sections are required.
- Each of the three canonical dimension keys appears exactly once.
- Unknown top-level fields, duplicate rule IDs, duplicate metric entries, and illegal
  lifecycle states are rejected.
- Every active rule must declare its metric ID, direction, normalization, thresholds,
  missing policy, and provenance/decision reference.

### 7.2 Referential and semantic validation

- Metric IDs must exist in the pinned scoring-input catalogue version.
- Units, currencies, marketplaces, periods, cohorts, and reference populations must
  be declared where applicable.
- Threshold ordering, boundary inclusivity, and score-band overlap/gap behavior must be
  explicit and internally consistent under the approved rule definition.
- Formula, normalization, missing-policy, and band identifiers must resolve to pinned,
  approved definitions; free-form executable code is prohibited.

### 7.3 Governance validation

- Draft configurations may retain `BUSINESS_DECISION_REQUIRED` but are non-executable.
- Approved/active configurations reject missing weights, directions, thresholds,
  policies, versions, owners, approval records, or fingerprints.
- Approved/active configurations reject `BUSINESS_DECISION_REQUIRED` in any executable
  business parameter.
- Effective periods must be explicit; overlapping active configurations for the same
  governed scope require an explicit resolution decision.

### 7.4 Execution gate

The future scoring engine must refuse calculation when any of the following is true:

- no configuration ID was supplied;
- the configuration is missing, draft, retired for a new run, unsigned, or altered;
- schema or score versions are absent, incompatible, or unrecognized;
- required business parameters are missing or contain the decision sentinel;
- configuration scope does not match the Opportunity Result scope;
- required dimension inputs are missing/conflicting under the approved policy;
- provenance or configuration fingerprint validation fails.

There is no fallback configuration. Failure returns a structured non-scored result
with `score_value=null`, validation errors, missing decisions, and provenance.

## 8. Future Scoring Engine Contract

### 8.1 Input

A future executable request must contain:

```yaml
opportunity_result: <immutable OpportunityResult reference or payload>
configuration:
  configuration_id: <explicit immutable ID>
  score_version: <explicit approved version>
  configuration_fingerprint: <verified fingerprint>
execution_context:
  requested_at: <timestamp>
  marketplace: <explicit scope>
  category_scope: <explicit scope>
```

The engine first validates the configuration and its compatibility with all three
dimension results. It may calculate only after the execution gate passes. This
specification supplies no executable configuration, so the current output remains
non-scored.

### 8.2 Future output

The future `OpportunityScoreResult` must retain at least:

- nullable `score_value` and explicit `result_status`;
- `score_version`, `configuration_id`, schema version, and configuration fingerprint;
- the three source dimension results and their statuses;
- dimension/metric calculation trace records for included and excluded inputs;
- confidence, completeness, risks, missing inputs, and conflicts;
- score-band reference when a future approved band applies;
- evidence provenance and configuration decision/approval provenance;
- a bounded explanation of rule execution, without a generated product recommendation.

Required audit chain:

```text
OpportunityScoreResult
        |
        +--> OpportunityResult
        |       +--> DimensionResult
        |               +--> Evidence / Metric / Snapshot / API Source
        |
        +--> configuration_id + fingerprint
                +--> score_version
                +--> business decision reference
                +--> approval and effective-period records
```

A numeric result without both evidence provenance and configuration provenance is
invalid. AI explanation and Workbook rendering remain downstream read-only consumers;
they cannot change parameters, recompute a score, or create a recommendation.

## 9. Acceptance and deferred decisions

This specification is accepted when:

1. business parameters are external, versioned, immutable, and auditable;
2. all three dimensions have explicit future configuration requirements;
3. parameter ownership and approval responsibilities are unambiguous;
4. draft and executable configuration states are distinguishable;
5. missing version, illegal state, incomplete approval, or unresolved decision blocks
   future calculation;
6. score results can be replayed against exact evidence and configuration artifacts;
7. no weight, threshold, formula, band, profit rule, or product score is defined here.

All numeric values and outcome-changing policies remain deferred to an approved
operations decision. Until then, `BUSINESS_DECISION_REQUIRED` is the only valid
business-parameter representation and `score_value` remains null.
