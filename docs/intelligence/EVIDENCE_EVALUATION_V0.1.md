# Evidence Evaluation Foundation V0.1

## Purpose

Evidence Evaluation V0.1 turns canonical observations into an auditable,
qualitative description of the evidence itself. It can state that a semantic
field has multi-provider support, an unknown period, complete lineage, or
conflicting present values. It does not state whether a product is attractive
or which candidate value is true.

The public entry point accepts only `CanonicalEvidenceBundle` values. Product,
Demand, Competition, and Opportunity Intelligence consume the same canonical
evidence, so their evidence can be evaluated without importing or coupling to
those layers. Production imports are limited to
`amazon_product_intelligence.contracts`, this package, and the Python standard
library.

## Public API

`amazon_product_intelligence.evidence_evaluation` exposes:

- `EVIDENCE_EVALUATION_RULESET_VERSION`
- `EvidenceEvaluationRequest`
- `EvidenceEvaluationSnapshotV0_1`
- `EvidenceEvaluationBuilderV0_1`
- `EvidenceEvaluationError`
- `EvidenceValidationError`
- `EvidenceSerializationError`
- `EvidenceQualityProfile`
- `EvidenceSupportRecord`
- `EvidenceConflictRecord`
- `EvidenceCoverageSummary`
- `EvidenceLineageReference`
- `EvidenceDiagnostic`

All models are frozen, use strict contract decoding, reject unknown fields, and
detach nested JSON data from caller-owned mutable containers.

## Conservative semantic-field grouping

V0.1 groups evidence only when the following canonical properties are
compatible:

- subject and observation kind;
- provider-neutral dimension or metric name;
- exact scope;
- observation timestamp and period semantics, excluding retrieval time;
- evidence type and exact unit;
- metric currency and rank context where applicable;
- keyword/product identities and relationship direction, type, and channel
  where applicable.

Provider-specific semantic descriptions are not identities because the same
canonical metric can use different descriptive wording. Units are never
converted. Review identities remain distinct. A parent product's separate
child relationships are repeatable facts rather than competing values, so a
different child does not create a false conflict.

## Qualitative evidence profile

Every `EvidenceSupportRecord` has exactly one `EvidenceQualityProfile`. The
closed V0.1 dimensions are:

| Dimension | V0.1 states |
| --- | --- |
| Source diversity | `SINGLE_PROVIDER`, `MULTI_PROVIDER_SUPPORT` |
| Observation time | `KNOWN_OBSERVATION_TIME`, `UNKNOWN_OBSERVATION_TIME`, `MIXED_OBSERVATION_TIME` |
| Period | `KNOWN_PERIOD`, `UNKNOWN_PERIOD`, `MIXED_PERIOD` |
| Value presence | `ALL_VALUES_PRESENT`, `NO_PRESENT_VALUE`, `MIXED_VALUE_PRESENCE` |
| Lineage | `COMPLETE_LINEAGE` |
| Consistency | `SINGLE_VALUE`, `SAME_VALUE`, `CONFLICT_PRESENT`, `NO_PRESENT_VALUE` |

`EvidenceSupportRecord` preserves supporting observation IDs, providers,
provider/source-tool identities, descriptive counts, semantic and presence
statuses, and complete lineage references. Counts are inventories, not
weights.

V0.1 does not define required dimensions for a product or market. It therefore
does not reinterpret an absent or unknown value as negative evidence. The
`NON_PRESENT_EVIDENCE_NOT_NEGATIVE` diagnostic makes this boundary explicit.

## Conflicts remain unresolved

An `EvidenceConflictRecord` is emitted only when comparable observations have
at least two different present values. It contains every present candidate
observation ID, its complete `ValueEnvelope`, providers, sources, and lineage.

The record contains no winner, provider priority, latest-value selection,
average, majority vote, or truth value. Canonical resolutions supplied in an
input bundle are validated for identity safety but are not used to select an
evaluation result.

## Lineage replay

`validate_against_bundles()` replays each evaluated observation through:

```text
Evidence support or conflict record
    -> canonical observation emission
    -> transformation run
    -> mapping version
    -> raw evidence reference
    -> collection run
    -> source bundle fingerprint
```

Validation rejects missing emissions, orphan observations or raw references,
transformation mismatches, cross-bundle identity collisions, and source bundle
fingerprint mismatches. Quality dimensions, candidate values, and descriptive
coverage are recomputed during replay.

## Determinism

All public identities use SHA-256 over canonical JSON. Requests sort bundles by
an order-insensitive bundle fingerprint. Observations, groups, candidates,
diagnostics, and lineage references are sorted by stable canonical identities.
No clock, random source, process-dependent hash, filesystem state, or generated
identifier participates in output identity.

## Example from the accepted fixtures

For the shared product `B0G2VV4RBW`, XiYou and Sorftime independently publish
the same price, producing `MULTI_PROVIDER_SUPPORT` and `SAME_VALUE`. Their
rating, review-count, and title values differ, producing three
`CONFLICT_PRESENT` records. All candidate values remain available and none is
selected.

## V0.1 boundaries

The framework intentionally does not implement numeric evidence weights,
confidence values, product/demand/competition/opportunity scores, rankings,
recommendations, market-entry decisions, or product-selection decisions.

Recency is descriptive only: V0.1 reports whether canonical observation time
is known and never prefers the latest record. Completeness describes observed
value presence only; it is not a claim that every business-required field is
available. Cross-unit comparison and semantic adjudication remain outside this
version.

Directional query-execution records are not canonical observations and are not
individually quality-profiled in V0.1; the public support contract is explicitly
observation-ID based. Canonical relationship observations emitted by populated
queries are evaluated normally, while empty-query meaning remains preserved by
the existing Demand and Opportunity evidence layers.
