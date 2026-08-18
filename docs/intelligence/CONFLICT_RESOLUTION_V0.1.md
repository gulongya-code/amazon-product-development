# Conflict Resolution Foundation V0.1

## Purpose

Conflict Resolution V0.1 is an auditable process-evidence layer. It preserves
every candidate from an Evidence Evaluation conflict, records whether an
explicit method was attempted, and keeps the result of that method distinct
from canonical truth.

It does not automatically choose a provider or value. It does not publish a
new canonical observation, mutate a canonical bundle, or consume existing
canonical `ResolvedEvidence` as a preference signal.

## Public API

`amazon_product_intelligence.conflict_resolution` exposes:

- `CONFLICT_RESOLUTION_RULESET_VERSION`
- `ConflictResolutionRequest`
- `ConflictResolutionSnapshotV0_1`
- `ConflictResolutionBuilderV0_1`
- `ConflictResolutionError`
- `ConflictValidationError`
- `ConflictSerializationError`
- `ConflictCandidate`
- `ConflictAnalysisRecord`
- `ResolutionAttemptRecord`
- `ConflictCoverageSummary`
- `ConflictLineageReference`
- `ConflictDiagnostic`

All public models are frozen, reject unknown serialized fields, detach nested
JSON data from caller-owned objects, and validate deterministic identities.

## Independent serialized handoff

Production code depends only on `amazon_product_intelligence.contracts`, this
package, and the Python standard library. It does not import Evidence
Evaluation or any Product, Demand, Competition, Opportunity, or Adapter layer.

To satisfy both independence and the required Evaluation input, the request
accepts `EvidenceEvaluationSnapshotV0_1.to_dict()` as a strict JSON mapping.
The handoff validates:

- the exact Evidence Evaluation V0.1 snapshot shape and ruleset;
- snapshot identity from canonical JSON;
- source bundle fingerprints;
- conflict-record identity and candidate inventory;
- candidate values, providers, sources, and lineage against canonical bundles.
- semantic-field identity and comparability against canonical observations.

Passing a live Evaluation model object is rejected. This keeps the production
dependency boundary explicit and makes serialization part of the audited
interface.

## Candidate preservation

Each `ConflictAnalysisRecord` corresponds to exactly one Evaluation conflict.
It contains at least two `ConflictCandidate` values with:

- source Evaluation conflict identity;
- canonical observation identity;
- complete `ValueEnvelope`;
- provider and provider/source-tool identity;
- every canonical emission lineage reference.

All candidates are present values. Missing, unknown, or null evidence cannot
be inserted into `available_evidence_candidate_ids` and cannot make another
candidate correct. An attempt must reference the analysis's complete candidate
set; candidate deletion fails closed.

## Resolution attempt statuses

V0.1 supports four process statuses:

| Status | Meaning |
| --- | --- |
| `NOT_ATTEMPTED` | No rule was applied. This is the builder default. |
| `INSUFFICIENT_EVIDENCE` | An explicit review found no sufficient basis. |
| `AMBIGUOUS` | An explicit review could not produce one candidate. |
| `RESOLUTION_PRODUCED` | An explicit supplied rule produced one preserved candidate. |

`RESOLUTION_PRODUCED` is not a truth claim and does not change canonical data.
It requires an explicit `ResolutionAttemptRecord`, a produced candidate from
the preserved set, available candidate evidence, and non-empty process
evidence. The builder never creates this status on its own.

The method guard rejects provider priority, latest/highest/lowest selection,
averaging, median selection, majority voting, and confidence/trust/score/ranking
methods. Process-evidence objects also recursively reject conclusion-bearing fields such as
winner, score, confidence, trust, recommendation, ranking, weight, probability,
preference, priority, and truth. V0.1 does not contain a default business
preference.

## Snapshot and lineage

`ConflictResolutionSnapshotV0_1` contains:

- its deterministic identity and ruleset;
- source Evaluation snapshot identity;
- canonical bundle fingerprints;
- conflict analyses and resolution attempts;
- descriptive coverage and diagnostics;
- the exact candidate lineage index.

`validate_against_bundles()` replays:

```text
Resolution attempt
    -> conflict analysis
    -> preserved candidate
    -> canonical observation emission
    -> transformation run
    -> mapping version
    -> raw evidence reference
    -> collection run
    -> source bundle fingerprint
```

Wrong types, orphan candidates, candidate/value/source mismatches, identity
collisions, incomplete lineage, broken transformation references, coverage
mismatches, and fingerprint mismatches are rejected.

## Determinism

All identities use SHA-256 over canonical JSON. Bundles, analyses, candidates,
attempts, diagnostics, and lineage references use stable canonical ordering.
Output identity does not use a clock, UUID, random source, process hash,
object representation, locale, filesystem state, or path separator.

## V0.1 boundaries

This foundation does not implement automatic conflict resolution, winner
selection, preferred-provider policy, latest-value choice, numeric weight,
confidence or truth score, probability, averaging, majority voting, ranking,
recommendation, or business decision.

Coverage values are descriptive counts only. A produced candidate remains a
record of rule execution and is never promoted to canonical truth by this
layer.
