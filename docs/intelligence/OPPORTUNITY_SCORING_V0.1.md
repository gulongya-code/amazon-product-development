# Opportunity Scoring Framework Foundation V0.1

## Status and scope

Opportunity Scoring V0.1 is an immutable, deterministic, auditable numerical
process layer. It consumes canonical evidence plus serialized Evidence
Evaluation, Conflict Resolution, Evidence Policy, and Decision Framework
snapshots. Its public snapshot type is `OpportunityScoringSnapshotV0_1`.

The layer answers one narrow question:

> What numeric result does the current versioned process rule produce from the
> supplied, audited decision evaluation?

It does not answer whether a product is attractive, whether a market should be
entered, or which product or keyword should be selected.

V0.1 deliberately emits no aggregate score. It also emits no recommendation,
ranking, priority, candidate winner, market-entry decision, investment
decision, ROI, profit prediction, or revenue prediction.

## Dependency and handoff boundary

Production code depends only on `amazon_product_intelligence.contracts`, local
Opportunity Scoring modules, and the Python standard library. It does not
import any adapter or intelligence implementation module.

The request requires:

1. one or more validated `CanonicalEvidenceBundle` objects;
2. a serialized Evidence Evaluation V0.1 snapshot;
3. a serialized Conflict Resolution V0.1 snapshot;
4. a serialized Evidence Policy V0.1 snapshot; and
5. a serialized Decision Framework V0.1 snapshot.

Each serialized handoff is strict. Unknown or missing outer fields, an
unsupported ruleset version, an invalid deterministic identity, a fingerprint
mismatch, or broken source-snapshot continuity fails closed. Caller-owned
payloads are canonicalized, detached, and deeply frozen.

Opportunity Intelligence was reviewed during discovery for its existing signal,
missing-evidence, risk, and lineage semantics. It is not an input to this V0.1
contract. Scoring therefore does not duplicate Opportunity Intelligence
identity or signal models.

## Fixed factors

V0.1 binds one factor to each existing Decision Framework condition:

| Factor | Decision condition | Purpose |
|---|---|---|
| Evidence Availability Factor | `EVIDENCE_INVENTORY` | Record whether the audited inventory analysis can produce a process result. |
| Conflict-Free Analysis Factor | `CONFLICT_FREE_EVIDENCE` | Record whether policy permits conflict-free analysis. |
| Keyword Evidence Factor | `KEYWORD_EVIDENCE` | Keep absent keyword evidence distinct from a zero result. |
| Conflict Context Factor | `CONFLICT_CONTEXT` | Record a process result with unresolved conflicts visible. |

Every `ScoreFactorDefinition` has a deterministic factor ID, factor version,
description, input requirement, calculation rule, explicit explanation
template, and bounded expected behavior. The template requires the explanation
to cover the factor rule, evidence references, calculation method, version,
process status, and bounded interpretation. The definitions contain no
executable callable and no business conclusion.

The fixed V0.1 rule declares:

- calculation method: `FIXED_PROCESS_RULE_RESULT_V0_1`;
- conflict behavior: `PRESERVE_AND_MARK_VISIBLE`;
- missing behavior: `EXCLUDE_WITHOUT_NUMERIC_RESULT`;
- policy-block behavior: `UNAVAILABLE_WITHOUT_NUMERIC_RESULT`.

## Components and calculations

Each factor has exactly one `ScoreComponentRecord`, one
`ScoreCalculationRecord`, and one `ScoreExplanationRecord`.

The component preserves the factor ID, input evidence IDs, Decision Framework
evaluation ID, Evidence Policy evaluation IDs, conflict IDs, process status,
component-level explanation, and reason codes. It contains no numeric result.

The calculation is the only public record permitted to contain the score
result field. It preserves:

- calculation ID and version;
- factor and component identities;
- calculation method;
- input component IDs;
- evidence, decision evaluation, Decision lineage, policy, and conflict
  references;
- result status; and
- optional integer `result_value`.

When an upstream rule analysis is recorded, V0.1 emits the fixed component
result `25`. This value is an allocation used by the current process rule. It
is not a probability, confidence estimate, truth value, recommendation, or
decision. V0.1 does not add the component values into a total.

## Result states

`ScoreCalculationRecord.result_status` is one of:

- `CALCULATED`: the rule analysis was recorded and no conflict was referenced;
- `CALCULATED_WITH_CONFLICT_VISIBLE`: the rule analysis was recorded and every
  referenced conflict remains visible;
- `BLOCKED_BY_POLICY`: policy made the component unavailable;
- `EXCLUDED_MISSING_EVIDENCE`: required evidence was missing and was not
  converted to zero; or
- `NOT_APPLICABLE`: the upstream decision condition did not apply.

Only the two calculated states may carry an integer result. All other states
must use `result_value=null`. Supplying zero or any other number for a blocked,
missing, or not-applicable calculation is invalid.

## Missing evidence

Missing evidence is explicit in the component status, calculation status,
reason code, diagnostic, and explanation. The V0.1 rule excludes missing
evidence without a numeric result. In particular, absent keyword evidence does
not mean zero demand, zero market, zero competition, or a negative business
conclusion.

## Conflict handling

Conflict IDs are preserved on components, calculations, explanations, and
lineage records. A calculated result with conflicts uses the distinct
`CALCULATED_WITH_CONFLICT_VISIBLE` status and method. A policy-blocked
conflict-free component is unavailable rather than silently scored.

The layer never selects a conflict candidate, provider, or winner. Existing
resolution attempts remain process evidence; unresolved status is not
overridden.

## Policy and decision integration

An upstream `ACTION_BLOCKED` evaluation can produce
`BLOCKED_BY_POLICY`. This means only that the score component is unavailable.
It does not reject a product, keyword, provider, market, or investment.

Every component preserves exactly one Decision Framework evaluation reference.
Decision applicability is mapped only to calculation process state:

| Decision evaluation result | Score calculation state |
|---|---|
| `RULE_ANALYSIS_RECORDED` | `CALCULATED` or `CALCULATED_WITH_CONFLICT_VISIBLE` |
| `RULE_ANALYSIS_BLOCKED_BY_POLICY` | `BLOCKED_BY_POLICY` |
| `INSUFFICIENT_EVIDENCE` | `EXCLUDED_MISSING_EVIDENCE` |
| `RULE_NOT_APPLICABLE` | `NOT_APPLICABLE` |

This mapping does not convert Decision Framework applicability into a
recommendation.

## Explanation completeness

Every calculation, including a calculation with no numeric result, has one
explanation. An explanation includes:

- factor explanation;
- calculation rule and version;
- evidence IDs;
- Decision Framework evaluation IDs;
- Evidence Policy evaluation IDs;
- conflict IDs; and
- a bounded interpretation of the process result.

There are no unexplained numeric results.

## Lineage and validation

Each `ScoreLineageReference` extends an existing Decision Framework lineage
record with factor, component, and calculation identities. The replay chain is:

```text
Score Calculation
  -> Decision Evaluation / Decision Lineage
  -> Policy Evaluation
  -> Conflict Analysis / Candidate / Resolution Attempt
  -> Evidence Support / Conflict Record
  -> Canonical Observation
  -> Transformation Run
  -> Mapping Version
  -> Raw Evidence
  -> Collection Run
  -> Source Bundle Fingerprint
```

`validate_against_bundles()` independently replays the canonical portion of
every lineage. Builder validation also checks the serialized upstream chain:

- record identities and exact fields;
- evidence support to observation references;
- conflict analysis and candidate references;
- policy evaluation and policy lineage references;
- decision rule, applicability, evaluation, audit, and lineage references;
- policy-block result continuity; and
- complete calculation input coverage.

Every calculation stores the exact upstream Decision lineage IDs used to build
its score lineage. Snapshot validation requires those IDs to match the
calculation's complete `ScoreLineageReference` set, so the calculation-to-
lineage bridge is direct and cannot be silently substituted.

Orphan records, missing factors, invalid numeric state, identity mismatch,
lineage omission, transformation mismatch, or fingerprint mismatch fail
closed.

## Immutability, serialization, and determinism

All public models are frozen dataclasses. Nested JSON mappings are detached and
exposed through read-only mapping proxies; arrays are tuples. `from_dict()` is
strict and rejects unknown fields.

All identities use SHA-256 over canonical JSON through `deterministic_id()`.
Ordering of source bundles and serialized records does not affect output.
Identity material contains no wall-clock time, UUID, random value, Python
`hash()`, `repr()`, filesystem state, or locale-dependent value.

## Public API

The package exports exactly:

- `OPPORTUNITY_SCORING_RULESET_VERSION`;
- `OpportunityScoringRequest`;
- `OpportunityScoringSnapshotV0_1`;
- `OpportunityScoringBuilderV0_1`;
- the three Opportunity Scoring error classes; and
- `ScoreFactorDefinition`, `ScoreComponentRecord`,
  `ScoreCalculationRecord`, `ScoreExplanationRecord`,
  `ScoreCoverageSummary`, `ScoreLineageReference`, and `ScoreDiagnostic`.

Private helpers, standard-library names, and upstream implementation types are
not re-exported.
