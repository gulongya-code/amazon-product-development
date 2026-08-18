# Evidence Policy Framework V0.1

## Purpose

Evidence Policy V0.1 is an auditable interpretation-policy layer. It determines
whether a named evidence-handling process is applicable, allowed, blocked, or
requires no action. It does not decide which fact is true and does not make a
product, market, or opportunity decision.

The layer consumes:

- validated `CanonicalEvidenceBundle` values;
- a strict serialized Evidence Evaluation V0.1 snapshot;
- a strict serialized Conflict Resolution V0.1 snapshot.

It produces one deterministic `EvidencePolicySnapshotV0_1`.

## Public API

`amazon_product_intelligence.evidence_policy` exposes:

- `EVIDENCE_POLICY_RULESET_VERSION`
- `EvidencePolicyRequest`
- `EvidencePolicySnapshotV0_1`
- `EvidencePolicyBuilderV0_1`
- `EvidencePolicyError`
- `EvidencePolicyValidationError`
- `EvidencePolicySerializationError`
- `PolicyDefinition`
- `PolicyApplicabilityRecord`
- `PolicyEvaluationRecord`
- `PolicyAuditRecord`
- `PolicyCoverageSummary`
- `PolicyLineageReference`
- `PolicyDiagnostic`

All public models are frozen, reject unknown serialized fields, detach nested
JSON data from caller-owned containers, and validate deterministic identities.

## Independent serialized handoff

Production code imports only `amazon_product_intelligence.contracts`, this
package, and the Python standard library. It does not import Adapters, Evidence
Evaluation, Conflict Resolution, or any Product, Demand, Competition, or
Opportunity module.

The request accepts the upstream snapshots through `to_dict()` and validates:

- exact V0.1 outer fields and ruleset versions;
- canonical JSON snapshot identities;
- the shared canonical bundle fingerprint inventory;
- Evaluation support, profile, conflict, coverage, diagnostic, and lineage
  relationships used by policy processing;
- Conflict Resolution analysis, candidate, attempt, coverage, diagnostic, and
  lineage relationships;
- resolution-attempt status/method consistency and rejection of preference or
  provider-priority process evidence;
- Evaluation-to-Conflict Resolution snapshot identity continuity;
- values, providers, sources, semantic fields, and lineage against canonical
  observations.

Passing live upstream model instances is rejected. This keeps the production
dependency boundary explicit without creating duplicate observation models.

## Declarative policies

V0.1 contains three fixed, versioned definitions.

### Multi-provider support context

Condition: at least two providers support a comparable evidence record.

Result when applicable: `APPLICABLE_NO_ACTION`.

The result records source context only. It does not increase confidence, assign
a weight, or prefer one provider.

### Complete lineage requirement

Condition: the interpreted evidence has `COMPLETE_LINEAGE`.

Result when complete: `ACTION_ALLOWED`.

The allowed action is only the continuation of an audited interpretation
process. It does not establish truth, validate a value, or authorize a business
decision. Incomplete lineage would produce `ACTION_BLOCKED`; malformed upstream
V0.1 lineage also fails closed before policy evaluation.

### Conflict review requirement

Condition: evaluated evidence contains a `CONFLICT_PRESENT` record.

Result when applicable: `ACTION_BLOCKED`.

The block prevents automatic interpretation and requires explicit review. It
does not select a winner, value, provider, or resolution attempt. A prior
`RESOLUTION_PRODUCED` remains process evidence and is not promoted to truth.

## Policy outcomes

| Outcome | Meaning |
| --- | --- |
| `NOT_APPLICABLE` | The condition did not apply to the supplied evidence. |
| `APPLICABLE_NO_ACTION` | Context was recorded; no process action was produced. |
| `ACTION_ALLOWED` | A named audited process may continue. |
| `ACTION_BLOCKED` | A named audited process must not continue. |

No outcome is a canonical truth update, recommendation, ranking, score, or
market decision.

## Applicability, evaluation, and audit trail

Every policy has exactly one:

- immutable definition;
- applicability record;
- evaluation record;
- audit record.

Evaluation records preserve policy identity, all examined Evaluation support
record IDs, related conflict IDs, the process outcome, expected behavior, and
source snapshot identities. Applicability records separately identify evidence
that matched the declarative condition. Audit records preserve the checked
condition and descriptive counts without time, score, confidence, or trust.

Arbitrary audit mappings are deep-frozen. Nested keys that encode winner,
score, confidence, trust, recommendation, ranking, decision, truth, preference,
weight, or priority conclusions are rejected.

## Snapshot and lineage

`EvidencePolicySnapshotV0_1` contains:

- its deterministic identity and ruleset;
- source Evaluation and Conflict Resolution snapshot identities;
- source bundle fingerprints;
- definitions, applicability records, evaluations, and audits;
- descriptive coverage and diagnostics;
- a policy-specific reference index over existing upstream identities.

`validate_against_bundles()` replays:

```text
Policy evaluation
    -> Evidence Evaluation support record
    -> Evidence Evaluation conflict record, when present
    -> Conflict Resolution analysis and candidate, when present
    -> Resolution attempt process evidence, when present
    -> canonical observation emission
    -> transformation run
    -> mapping version
    -> raw evidence reference
    -> collection run
    -> canonical bundle fingerprint
```

Policy lineage stores references only. It does not create a new observation,
candidate, conflict, or resolution identity. Unknown policies, orphan evidence,
missing input coverage, identity mismatch, omitted emissions, and fingerprint
mismatch fail closed.

## Determinism

All policy, applicability, evaluation, audit, diagnostic, lineage, and snapshot
identities use SHA-256 over canonical JSON. Inputs and outputs have stable
ordering.

Identity does not use a clock, UUID, random source, process hash, object
representation, filesystem state, locale, or path separator.

## V0.1 boundaries

This foundation does not implement:

- automatic winner or provider selection;
- canonical truth or candidate mutation;
- confidence, trust, product, opportunity, or other numeric scores;
- evidence weighting or ranking;
- recommendation or market decision;
- sentiment, demand, competition, or opportunity analysis.

Coverage values are descriptive counts only. Policy output remains auditable
process evidence and never becomes canonical truth by itself.
