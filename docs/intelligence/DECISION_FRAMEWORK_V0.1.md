# Decision Framework Foundation V0.1

## Purpose

Decision Framework V0.1 is an auditable rule-analysis layer. It records which
declarative analysis rules are applicable, lack required evidence, or are
blocked by upstream Evidence Policy. It does not recommend, rank, score, select,
or reject a product, keyword, provider, market, or investment.

The layer consumes validated canonical bundles and strict serialized V0.1
snapshots from Evidence Evaluation, Conflict Resolution, and Evidence Policy.
It produces one deterministic `DecisionFrameworkSnapshotV0_1`.

## Public API

`amazon_product_intelligence.decision_framework` exposes exactly:

- `DECISION_FRAMEWORK_RULESET_VERSION`
- `DecisionFrameworkRequest`
- `DecisionFrameworkSnapshotV0_1`
- `DecisionFrameworkBuilderV0_1`
- `DecisionFrameworkError`
- `DecisionFrameworkValidationError`
- `DecisionFrameworkSerializationError`
- `DecisionRuleDefinition`
- `DecisionApplicabilityRecord`
- `DecisionEvaluationRecord`
- `DecisionAuditRecord`
- `DecisionCoverageSummary`
- `DecisionLineageReference`
- `DecisionDiagnostic`

All public models are frozen, detach nested JSON from caller-owned containers,
reject unknown serialized fields, and validate deterministic identities.

## Independent serialized handoff

Production code imports only `amazon_product_intelligence.contracts`, this
package, and the Python standard library. It never imports Adapters, Product,
Demand, Competition, Opportunity, Evidence Evaluation, Conflict Resolution, or
Evidence Policy implementations.

The request validates exact outer shapes, V0.1 ruleset versions, canonical JSON
snapshot identities, bundle fingerprint continuity, and the complete source
snapshot chain:

```text
Evidence Evaluation
    -> Conflict Resolution
    -> Evidence Policy
    -> Decision Framework
```

The builder independently replays the source support, conflict, analysis,
candidate, resolution-attempt, policy-evaluation, and policy-lineage identities
used by decision analysis. Preference-based resolution methods and process
fields fail closed. Live upstream implementation objects are not accepted.

## Declarative rule definitions

V0.1 contains four fixed rules.

### Evidence inventory

Requires at least one support record and complete lineage policy permission.
It records evidence availability. Conflict may be present because inventory is
descriptive and does not interpret or resolve the conflict.

### Conflict-free evidence analysis

Requires evidence, complete lineage, absence of conflict, and applicable policy
permission. When the conflict policy is `ACTION_BLOCKED`, this rule becomes
`BLOCKED_BY_POLICY`; that does not mean a product or market was rejected.

### Keyword evidence analysis

Requires at least one `KEYWORD_METRIC` or `PRODUCT_KEYWORD_RELATIONSHIP` support
record, complete lineage, absence of conflict, and policy permission. Missing
keyword evidence produces `INSUFFICIENT_EVIDENCE`, never a negative demand,
competition, opportunity, or product conclusion.

### Conflict context analysis

Requires conflict presence and complete lineage. It records auditable conflict
context for review but does not resolve the conflict or select any candidate.

Each `DecisionRuleDefinition` contains a version, description, explicit input
requirements, declarative conditions, and expected process behavior. No rule
contains a callback or hidden executable business policy.

## Applicability

`DecisionApplicabilityRecord` preserves:

- the rule identity;
- available support-record identities;
- explicit missing evidence requirements;
- aggregate conflict status;
- aggregate policy status and referenced policy evaluations;
- the applicability result and reason codes.

Allowed applicability results are:

| Result | Meaning |
| --- | --- |
| `NOT_APPLICABLE` | The declarative condition did not match. |
| `INSUFFICIENT_EVIDENCE` | Required evidence was absent. |
| `APPLICABLE` | A rule-analysis record may be produced. |
| `BLOCKED_BY_POLICY` | Upstream policy prevents that analysis process. |

Missing evidence is not negative evidence. Policy blocking is not product,
market, investment, or provider rejection.

## Evaluation and audit records

Every rule has exactly one applicability, evaluation, and audit record.
Evaluation results are process-analysis states:

- `RULE_NOT_APPLICABLE`
- `INSUFFICIENT_EVIDENCE`
- `RULE_ANALYSIS_RECORDED`
- `RULE_ANALYSIS_BLOCKED_BY_POLICY`

The analysis output is deliberately closed and contains only its record type,
applicability state, and the statement that it is not a business conclusion.
Audit metadata preserves only source snapshot identities and the condition type.

Output cannot contain a winner, recommendation, ranking, score, priority, best
product, best keyword, market-entry decision, investment decision, ROI, profit
or revenue prediction, confidence, trust, selection, preference, truth, or
evidence weight.

## Snapshot and lineage

`DecisionFrameworkSnapshotV0_1` contains:

- deterministic snapshot and source identities;
- source bundle fingerprints;
- rule definitions;
- applicability and evaluation records;
- audit records;
- descriptive coverage and diagnostics;
- decision-specific lineage references over existing upstream identities.

`validate_against_bundles()` replays:

```text
Decision evaluation
    -> Evidence Policy evaluation
    -> Conflict Resolution analysis and candidate, when present
    -> resolution attempt process evidence, when present
    -> Evidence Evaluation support/conflict record
    -> canonical observation emission
    -> transformation run
    -> mapping version
    -> raw evidence reference
    -> collection run
    -> canonical bundle fingerprint
```

Decision lineage creates no new evidence, observation, conflict, candidate,
resolution, or policy identity. Orphans, missing rules, unknown policy
references, omitted emissions, identity mismatches, and fingerprint mismatches
fail closed.

## Determinism

All rule, applicability, evaluation, audit, diagnostic, lineage, and snapshot
identities use SHA-256 over canonical JSON. Inputs and outputs use stable
ordering. Identity does not use a clock, UUID, random source, process hash,
object representation, filesystem state, or locale.

## V0.1 boundary

This foundation answers only which declarative rule produced which auditable
analysis record. It does not implement a recommendation engine, opportunity or
product score, automatic selection, winning product, market-entry or investment
decision, ROI, profit or revenue prediction, ranking, confidence, or trust.
