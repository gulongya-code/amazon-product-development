# Recommendation Framework Foundation V0.1

## Status and scope

Recommendation Framework V0.1 is an immutable, deterministic, auditable rule
generation layer. It consumes canonical evidence and serialized Evidence
Evaluation, Conflict Resolution, Evidence Policy, Decision Framework, and
Opportunity Scoring snapshots.

Its output is a `RecommendationFrameworkSnapshotV0_1`. A generation record
means:

> The current versioned rule produced this bounded advisory record from the
> supplied evidence and process state.

It does not mean that the recommendation is factual truth. V0.1 is not a final
decision engine and does not select a product, rank candidates, name a winner,
guarantee success, decide market entry, provide investment advice, or predict
ROI, profit, or revenue.

## Dependency and handoff boundary

Production code imports only `amazon_product_intelligence.contracts`, local
Recommendation Framework modules, and the Python standard library. It does not
import adapters or any upstream intelligence implementation module, including
Opportunity Scoring.

The request requires:

1. one or more validated `CanonicalEvidenceBundle` objects;
2. a serialized Evidence Evaluation V0.1 snapshot;
3. a serialized Conflict Resolution V0.1 snapshot;
4. a serialized Evidence Policy V0.1 snapshot;
5. a serialized Decision Framework V0.1 snapshot; and
6. a serialized Opportunity Scoring V0.1 snapshot.

Every serialized handoff is strict. Unknown or missing outer fields,
unsupported rulesets, identity mismatches, fingerprint mismatches, or broken
source-snapshot continuity fail closed. Input payloads are detached from
caller-owned containers and deeply frozen.

## Declarative recommendation rules

V0.1 defines one recommendation rule for each existing Decision Framework and
Opportunity Scoring condition:

| Decision condition | Recommendation rule purpose |
|---|---|
| `EVIDENCE_INVENTORY` | Generate a bounded evidence-inventory advisory. |
| `CONFLICT_FREE_EVIDENCE` | Apply policy to conflict-free analysis availability. |
| `KEYWORD_EVIDENCE` | Preserve missing keyword evidence without predicting demand. |
| `CONFLICT_CONTEXT` | Require further review while conflicts remain visible. |

Every `RecommendationRuleDefinition` contains a deterministic rule ID, rule
version, description, input requirements, declarative conditions, and expected
recommendation behavior. Definitions contain no callable or hidden executable
business logic. Public model validation rejects explicit product-purchase,
guaranteed-success, best-product, best-market, profitable-market, and assured
success language even when a caller recomputes deterministic identities.

The fixed condition mapping is:

| Upstream process state | Generated record type |
|---|---|
| Calculated without conflict | `RULE_CONDITIONS_SATISFIED` |
| Calculated with visible conflict | `FURTHER_REVIEW_RECOMMENDED` |
| Missing evidence without policy block | `EVIDENCE_COLLECTION_RECOMMENDED` |
| Any referenced `ACTION_BLOCKED` | `RECOMMENDATION_BLOCKED_BY_POLICY` |
| Rule not applicable | `RULE_NOT_APPLICABLE` |

These are process-advisory types, not truth labels or business outcomes.

## Applicability

Each `RecommendationApplicabilityRecord` preserves:

- rule ID;
- available evidence IDs;
- explicit missing evidence requirements;
- score component and calculation IDs;
- policy and conflict status;
- applicability result; and
- reason codes.

Allowed applicability results are `NOT_APPLICABLE`,
`INSUFFICIENT_EVIDENCE`, `APPLICABLE`, and `BLOCKED_BY_POLICY`.

Policy blocking takes precedence over recommendation generation. Missing
requirements remain visible when a blocked rule also lacks evidence.

## Generation records

Every rule has exactly one `RecommendationGenerationRecord`. The record
preserves:

- rule and applicability identities;
- input evidence IDs;
- Decision Framework evaluation IDs;
- Opportunity Scoring component and calculation IDs;
- Evidence Policy evaluation IDs;
- conflict IDs;
- generated recommendation type; and
- explanation identity.

The record contains no numeric score. The scoring result is referenced by its
audited identity and status; no score value is copied or translated into
certainty, probability of success, priority, or rank.

## Missing evidence

If upstream scoring reports `EXCLUDED_MISSING_EVIDENCE` and no referenced
policy blocks generation, V0.1 emits `EVIDENCE_COLLECTION_RECOMMENDED` with an
explicit `UPSTREAM_SCORE_EXCLUDED_MISSING_EVIDENCE` requirement.

Missing evidence is never silently converted into zero, negative evidence,
zero demand, or a failed opportunity.

## Conflict visibility

Conflict IDs are retained on applicability, generation, explanation, and
lineage records. A calculated component with conflict produces
`FURTHER_REVIEW_RECOMMENDED`.

The framework does not resolve a conflict, select a candidate, choose a
provider, hide a resolution attempt, or override the upstream conflict state.

## Policy integration

The builder independently reads the referenced serialized policy evaluations.
If any referenced evaluation is `ACTION_BLOCKED`, applicability becomes
`BLOCKED_BY_POLICY` and the generated type becomes
`RECOMMENDATION_BLOCKED_BY_POLICY`.

This blocks only recommendation generation. It does not reject a product,
keyword, provider, market, or investment.

## Explanations and limitations

Every generation record references exactly one
`RecommendationExplanationRecord`. The explanation preserves:

- rule explanation;
- evidence and Decision Framework references;
- score component and calculation references;
- policy and conflict references; and
- a fixed limitations inventory.

The limitations state that the output is based only on the current rules and
evidence, is not factual truth, performs no automatic selection, provides no
guarantee or forecast, and makes no market or investment decision.

Snapshots with a missing or mismatched explanation fail validation.
The explanation text must equal the corresponding audited rule description;
an independently substituted explanation fails closed.

## Lineage

Each `RecommendationLineageReference` extends an existing score lineage with
recommendation rule, applicability, generation, and explanation identities.
The chain is:

```text
Recommendation Generation
  -> Decision Evaluation
  -> Score Calculation / Score Lineage / Decision Lineage
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

Builder validation independently verifies relevant upstream record identities,
source references, score state, complete score lineage, and canonical emission
content. `validate_against_bundles()` replays every recommendation lineage
through canonical transformations.

Orphan records, missing rules, missing score references, missing explanations,
identity mismatches, incomplete lineage, transformation mismatches, or
fingerprint mismatches fail closed.

## Snapshot contents

The snapshot includes:

- deterministic snapshot and source snapshot identities;
- source bundle fingerprints;
- recommendation rules;
- applicability records;
- generation records;
- explanations;
- descriptive coverage;
- diagnostics; and
- complete lineage.

Coverage values are descriptive counts, not ranks or recommendation scores.

## Immutability, serialization, and determinism

All public models are frozen dataclasses. Nested mappings are detached and
stored in read-only mapping proxies; arrays are tuples. Strict `from_dict()`
rejects unknown fields and invalid identities.

All identities use SHA-256 over canonical JSON via `deterministic_id()`.
Bundle order and serialized record order do not change output. Identity
material contains no wall-clock time, UUID, random value, Python `hash()`,
`repr()`, filesystem state, or locale-dependent value.

## Public API

The package exports exactly:

- `RECOMMENDATION_FRAMEWORK_RULESET_VERSION`;
- `RecommendationFrameworkRequest`;
- `RecommendationFrameworkSnapshotV0_1`;
- `RecommendationFrameworkBuilderV0_1`;
- the three Recommendation Framework error classes; and
- `RecommendationRuleDefinition`, `RecommendationApplicabilityRecord`,
  `RecommendationGenerationRecord`, `RecommendationExplanationRecord`,
  `RecommendationCoverageSummary`, `RecommendationLineageReference`, and
  `RecommendationDiagnostic`.

Private helpers, standard-library names, adapters, and upstream implementation
types are not re-exported.
