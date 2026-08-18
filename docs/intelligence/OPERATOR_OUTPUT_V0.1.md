# Operator Output Layer Foundation V0.1

## Purpose

Operator Output V0.1 is an immutable presentation boundary over existing audited
snapshots. It turns serialized Product, Demand, Competition, Opportunity,
Opportunity Scoring, and Recommendation records into five table-oriented views.
It does not alter canonical evidence or run analysis, conflict resolution,
policy, decision, scoring, selection, or recommendation logic.

Ruleset: `operator-output-v0.1`.

## Dependency boundary

Production code depends only on:

- `amazon_product_intelligence.contracts`
- the Python standard library
- local relative Operator Output modules

All six intelligence inputs are consumed as serialized mappings. Production code
does not import adapters or any upstream intelligence implementation package.
Each input is checked for its exact V0.1 top-level schema, ruleset version,
deterministic snapshot identity, and canonical bundle fingerprints.

## Public API

The package exposes exactly:

- `OPERATOR_OUTPUT_RULESET_VERSION`
- `OperatorOutputRequest`
- `OperatorOutputSnapshotV0_1`
- `OperatorOutputBuilderV0_1`
- `OperatorOutputError`
- `OperatorOutputValidationError`
- `OperatorOutputSerializationError`
- `ProductOutputRow`
- `KeywordOutputRow`
- `CompetitionOutputRow`
- `OpportunityOutputRow`
- `RecommendationOutputRow`
- `OutputCoverageSummary`
- `OutputLineageReference`
- `OutputDiagnostic`

## Request contract

`OperatorOutputRequest` requires canonical bundles and serialized snapshots from:

1. Product Intelligence V0.1
2. Demand Intelligence V0.1
3. Competition Intelligence V0.1
4. Opportunity Intelligence V0.1
5. Opportunity Scoring V0.1
6. Recommendation Framework V0.1

The request freezes detached copies of all serialized inputs. It rejects unknown
top-level fields, incorrect source identities, unsupported rulesets, bundle
references outside the request, duplicate canonical bundle content, and a broken
Recommendation-to-Scoring source chain. Recommendation and Scoring must also
reference the same Evaluation, Conflict, Policy, and Decision snapshots.

## Five operator views

### Product

One row represents the Product snapshot target. It exposes ASIN, marketplace,
title candidates, all product fact evidence sets, metric series, variation
topology, review evidence summary, and quality indicators. `title` is a candidate
collection; V0.1 does not choose a winning title or fact.

### Keyword

One row represents the Demand snapshot target keyword. It exposes keyword metric
evidence sets, directional query execution status, related product evidence,
channels, providers, and explicit limitations. Empty query results, unknown
state, and zero remain distinct. The view makes no demand or market-size claim.

### Competition evidence

Rows group observed product-keyword relationships by product endpoint, keyword,
direction, relationship type, channel, and provider. They expose mechanical
evidence counts and related variation evidence. This is an evidence relationship
view only: it does not produce a competitor inventory, competitive-strength
judgment, or ranking.

### Opportunity

One row exposes existing observed and derived opportunity signals, missing
evidence, risk evidence, and references copied from existing score calculations
and score explanations. Existing `result_value` and `result_status` values may be
displayed as source data; the output layer never calculates, combines, normalizes,
or ranks them.

### Recommendation

One row is emitted for each existing Recommendation generation record. It joins
the existing rule and explanation, preserves evidence references and limitations,
copies the existing recommendation type, and identifies the exact source
generation record. The builder never creates a new recommendation type or
applies a rule.

## Export contract

`OperatorOutputSnapshotV0_1.to_dict()` returns the strict nested JSON structure.
`to_json()` returns canonical JSON. `to_table_rows()` returns five named tables:

- `product`
- `keyword`
- `competition_evidence`
- `opportunity`
- `recommendation`

Every table row is a dictionary whose values are CSV-safe scalars. Structured
cells are encoded as canonical JSON strings, preserving exact evidence without
flattening away status, units, provenance, or limitations.

Raw provider payloads, credentials, authorization material, secrets, tokens,
passwords, and hidden metadata are rejected. Canonical raw evidence identifiers
remain available only as audit references; raw payload content is never exported.

## Lineage

Every emitted row has at least one `OutputLineageReference`:

```text
output row
  -> serialized source snapshot
  -> serialized source record and source lineage record
  -> canonical observation or directional query execution
  -> transformation run
  -> raw evidence identifier
```

Each reference carries the source snapshot ID, source record ID, source lineage
ID, canonical reference type and ID, transformation run, mapping version,
collection run, provider, source tool, source field, raw evidence ID, and bundle
fingerprints. `validate_against_bundles()` replays every link against supplied
canonical bundles and fails closed on a missing reference, collision, mismatched
provenance field, or fingerprint mismatch.

Snapshot validation also requires each lineage reference to use the view and
source snapshot assigned to its row, and requires its source record ID to occur
in that row's serialized source data. Lineage records that belong only to
out-of-scope or undisplayed source records are not attached to an output row.

## Immutability, serialization, and identity

All public models are frozen, slotted dataclasses. Nested JSON mappings are
detached and recursively frozen. `from_dict()` is strict and rejects missing or
unknown fields. Rows, lineage records, diagnostics, and the final snapshot use
SHA-256 deterministic IDs over canonical JSON. Input sequence order and mapping
key order do not affect output. No clock, UUID, random value, process hash,
representation string, filesystem state, or network state participates in output.

## Mechanical coverage

`OutputCoverageSummary` contains row counts for the five tables plus source
snapshot, lineage reference, and diagnostic counts. These are presentation-layer
inventory counts, not analytical metrics.

## Real synthetic integration fixture

The V0.1 integration test builds all six source snapshots from audited synthetic
canonical fixtures. Its deterministic output is:

```text
operator-output-snapshot:c1b2618855d5f26478b289882a5e46612d25adeb4b9306d52c6d1fc48bfa013b
```

It contains one Product row, one Keyword row, ten Competition evidence rows, one
Opportunity row, four Recommendation rows, and 332 output lineage references.
The snapshot passes strict round-trip, CSV-ready export, cross-process identity,
deep immutability, unknown-field rejection, source-chain checks, and canonical
bundle lineage replay.

## Explicit non-goals

V0.1 does not:

- modify canonical truth, evidence, conflicts, policies, or decisions;
- resolve competing fact or metric candidates;
- infer demand, market size, competitive intensity, or opportunity quality;
- calculate, aggregate, normalize, compare, rank, or choose scores;
- generate, change, rank, or automatically select recommendations;
- expose raw provider payloads, credentials, or hidden metadata.
