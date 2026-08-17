# Product Intelligence Foundation V0.1

## Purpose and boundary

Product Intelligence V0.1 is an immutable, replayable view over one or more validated `CanonicalEvidenceBundle` values. It organizes supplied canonical evidence around a requested `ProductIdentity`; it does not declare a product truth.

The contract declarations are explicit:

- Snapshot is a derived evidence view.
- Snapshot is not resolved canonical truth.
- Multiple candidate values are not a resolved conflict.
- No evidence does not mean zero.
- No relation evidence does not mean no variations.
- No review evidence does not mean no reviews.
- Coverage is not a completeness score.
- Product Intelligence does not consume Provider raw JSON.

The executable boundary is:

```text
CanonicalEvidenceBundle (1..N)
        -> ProductIntelligenceRequest
        -> ProductIntelligenceBuilderV0_1
        -> ProductIntelligenceSnapshotV0_1
```

Product Intelligence source imports only the public canonical contracts and the Python standard library. Provider payloads, adapter contexts, private provider JSON, network access and third-party packages are outside this layer. Adapters may be used by callers or integration tests to create canonical bundles before invoking the builder.

The ruleset is `product-intelligence-v0.1`. It is serialized and included in snapshot identity material.

## Public API

The stable package is `amazon_product_intelligence.product_intelligence`. Its explicit `__all__` contains exactly:

```text
PRODUCT_INTELLIGENCE_RULESET_VERSION
ProductScope
FactCandidateState
ProductIntelligenceRequest
ProductIntelligenceSnapshotV0_1
ProductIntelligenceBuilderV0_1
ProductIntelligenceError
ProductIntelligenceValidationError
ProductSubjectNotFoundError
ProductTopologyError
ProductIdentityCollisionError
SnapshotSerializationError
EvidenceCandidate
ProductFactEvidenceSet
ProductMetricSeries
VariationTopology
VariationEdge
ReviewEvidenceSummary
EvidenceCoverageSummary
LineageReference
QualityIssueReference
OutOfScopeObservationReference
ProductIntelligenceDiagnostic
```

Minimal use:

```python
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)

request = ProductIntelligenceRequest(
    target_product_identity=target,
    scope=ProductScope.EXACT_PRODUCT,
    canonical_bundles=(bundle,),
)
snapshot = ProductIntelligenceBuilderV0_1().build(request)
snapshot.validate_against_bundles((bundle,))
```

## Request and record merge

The request requires a valid target and one or more bundles. It validates every bundle, detaches the caller's sequence, stores it as a tuple and orders inputs by fingerprint. A whole-bundle duplicate is rejected.

The three request fields are `target_product_identity`, `scope` and `canonical_bundles`. A single-provider bundle and multiple independent Provider bundles are both valid inputs; multi-provider availability is never required for a valid snapshot.

The builder creates a read-only logical index for transformation runs, mappings, collections, raw evidence identities, observations and quality issues. Shared canonical records with the same identity and content are deterministically deduplicated while their source-bundle fingerprint inventory is retained. The same identity with different content fails closed; there is no first-wins or last-wins behavior.

A source bundle fingerprint is SHA-256 over UTF-8 canonical JSON from strict `bundle.to_dict()` data. Record arrays are sorted by their canonical form, so caller-controlled record order does not change the fingerprint. Mapping keys use canonical JSON sorting. Adapter mapping/transformation changes remain identity material and therefore naturally change the fingerprint.

## Snapshot fields

`ProductIntelligenceSnapshotV0_1` contains `snapshot_id`, `ruleset_version`, `target_product_identity`, `scope`, `included_product_identities`, `source_bundle_fingerprints`, `variation_topology`, `product_fact_evidence_sets`, `product_metric_series`, `review_evidence_summary`, `evidence_coverage_summary`, `quality_issue_references`, `out_of_scope_observation_references`, `lineage_index` and `diagnostics`. These are evidence organization and audit fields, not a preferred-value or scoring schema.

## Scope semantics

### Exact product

`EXACT_PRODUCT` includes ordinary product facts, metrics and reviews only when their canonical product subject equals the target product ID in the same marketplace. Confirmed relation evidence directly adjacent to the target may appear in variation topology, but it never expands the ordinary evidence scope. Unrelated supplied observations receive out-of-scope references and a stable diagnostic.

A matching title, brand, model, size, color, return order or co-occurrence never creates product membership. A target absent from both direct canonical evidence and confirmed relation endpoints is rejected rather than represented by an empty snapshot.

### Explicit variation family

`EXPLICIT_VARIATION_FAMILY` expands only through present relationship facts whose value semantics are `CONFIRMED` and whose dimension is one of the two audited variation dimensions:

```text
child_product_relationship:  subject parent, value child
parent_product_relationship: subject child,  value parent
```

Both are normalized to `parent -> child`. Thus XiYou's explicit parent/child evidence and Sorftime product-detail's child/parent evidence for `B0G2VVX3ML -> B0G2VV4RBW` become independent evidence on one normalized edge. The edge retains every observation ID, original dimension, provider, source tool and lineage. This is not a vote or a confidence score.

Family membership is the target's connected component over valid confirmed edges. Target-connected self-loops, directed cycles, multiple distinct parents, malformed endpoints and marketplace/identity mismatches fail closed. A confirmed invalid relationship outside the target component may be explicitly excluded, but global record identity collisions and lineage corruption still fail the whole build.

When no confirmed target relationship is supplied, family scope remains the exact target and emits `NO_CONFIRMED_VARIATION_RELATIONSHIP`. This means only that the supplied evidence has no confirmed relationship; it does not state that the product has no variations. Sorftime `product_variations` rows do not create relationships from row membership, size, color or return order.

## Evidence organization

### Product facts

Relationship dimensions are routed to topology and never appear as ordinary facts. Other fact observations are grouped only when product subject, marketplace, dimension, fact group, canonical scope, unit and provider semantic qualifier match. Every observation remains a candidate with its presence state, raw and normalized JSON value, value type, unit, normalization and semantic status, evidence type, result status, canonical time, provider/source and lineage.

The only summary state is structural:

- `NO_PRESENT_CANDIDATE`;
- `ONE_DISTINCT_PRESENT_VALUE`;
- `MULTIPLE_DISTINCT_PRESENT_VALUES`.

This state is not conflict resolution. Missing, explicit null, unknown, zero, empty string and empty collection remain distinct. Pa, WOG and psi remain separate evidence sets. No preferred value, latest value, majority result, average or provider priority is produced.

### Product metrics

Metric series keys preserve the product, metric, observed-versus-estimate measurement type, evidence type, unit, canonical scope, period type/start/end, observed-at status, timezone, currency, rank/category context and metric semantic. Candidates are deterministically ordered by canonical observation/period time and observation ID.

Unknown periods remain unknown. Retrieval time is never substituted for observation time. The builder performs no unit or currency conversion, averaging, current/latest selection, trend or growth calculation. It does not infer revenue from sales volume or turn provider order estimates into observed facts.

### Reviews

The review summary describes only the supplied evidence sample. It counts canonical review observations, exact provider review identities, providers/source tools, rating presence, present rating values, known/unknown dates, helpful-vote states and variant presence. It stores observation and lineage references rather than copying review bodies.

No fuzzy deduplication, sentiment, theme, pain point, authenticity result, feature extraction or language-model summary is performed. Absence of supplied review evidence is not a statement that a product has no reviews.

### Keyword observations

`KeywordMetricObservation` and `ProductKeywordRelationshipObservation` are outside Product Intelligence V0.1. Their IDs, kinds, reason codes and lineage are explicitly inventoried. They never become product facts or metrics and do not produce demand, competition, market-size, relevance or opportunity conclusions. An empty keyword query result is not converted to zero demand.

## Coverage, quality and diagnostics

`EvidenceCoverageSummary` is an inventory. It counts source bundles, collections, raw evidence IDs, mappings, transformations, observations by kind, included/excluded/out-of-scope observations, providers, source tools, evidence/presence states, fact dimensions, metric types, review evidence, variation edges, canonical quality issues and Product Intelligence diagnostics.

The canonical bundle does not expose payload-kind or full `RawEvidenceRecord` objects, only validated raw evidence references and transformation metadata; therefore `payload_kind_count` is `0` rather than inferred from source-tool names. No payload data is copied into the snapshot.

Coverage is not completeness, trust, confidence, product quality or provider ranking. Missing evidence does not prove the corresponding real-world field is absent.

Canonical quality issues are referenced without modification. Their raw/observation source references are validated and expanded into auditable raw, collection, transformation, mapping, provider, source-tool and observation-lineage inventories when those records are available through the canonical bundles. Product Intelligence may add deterministic diagnostics such as unrelated evidence exclusion, keyword out-of-scope inventory, no confirmed relationship, multiple distinct fact values, non-present-only facts, unknown metric period, non-comparable units and multi-source variation edges. Diagnostics neither create provider issues nor resolve evidence.

## Lineage and replay validation

Every fact candidate, metric candidate, variation edge observation, review reference and out-of-scope observation has one or more `LineageReference` values:

```text
snapshot item
  -> canonical observation / semantic observation
  -> transformation run
  -> mapping version
  -> raw evidence ID
  -> collection run ID
  -> provider / source tool / source field
  -> source bundle fingerprint(s)
```

Quality issue references preserve their source references, collection, transformation, mapping and source-bundle fingerprints. `validate_against_bundles()` independently rebuilds the record inventory and rejects missing/wrong bundles, identity collisions, observation or transformation or raw or collection or mapping or issue orphans, wrong types, scope-external fact/metric items and fingerprint mismatches. It also deterministically rebuilds the expected snapshot and compares the complete serialized result, so valid lineage cannot conceal altered candidates, topology, review summaries, coverage, diagnostics or inventories. Internal snapshot validation does not replace this replay check.

## Determinism, immutability and serialization

All public structures are frozen dataclasses. Public sequences are tuples; public JSON mappings and arbitrary nested JSON objects are detached and recursively immutable. The builder does not modify bundles or caller-owned lists.

Every public snapshot model uses JSON-compatible `to_dict()` and strict `from_dict()`. Decoding rejects unknown or missing fields, invalid enums, wrong primitives, booleans passed as integers, non-finite floats and non-string mapping keys. Nested contracts are reconstructed through their strict public contract boundary.

Snapshot ID is `snapshot:` plus SHA-256 of canonical JSON for all serialized snapshot content except `snapshot_id`. It includes ruleset, target, scope, included identities, source fingerprints, all evidence views, topology, issue/out-of-scope references, lineage, coverage and diagnostics. The ID is re-computed at construction and decoding. It is independent of current time, random state, process hash, working directory, input bundle order, record order and mapping insertion order.

## Fail-closed conditions

V0.1 rejects empty or invalid requests, invalid bundles or targets, unknown scopes, duplicate whole bundles, canonical identity/content collisions, an absent target, target-connected illegal topology, orphan/wrong lineage, source fingerprint disagreement, invalid serialized primitives and content/identity mismatch.

It does not represent failure as an empty snapshot and does not silently continue after a global identity or lineage violation.

## Explicit non-goals and retained unknowns

V0.1 does not implement cross-provider resolution, conflict adjudication, opportunity scoring, recommendations, demand/competition conclusions, review analysis, currency/unit conversion, inferred variants, current/latest selection or provider preference. It does not infer XiYou traffic methodology or order/keyword estimate windows, Sorftime monthly-sales methodology or self-parent semantics, unapproved structured attributes, timestamps from date-only periods, or any market conclusion from an empty forward keyword query.

Synthetic invalid topology/value objects in tests are labelled `SYNTHETIC_CANONICAL_TEST_INPUT`; they are not represented as captured provider evidence.

## Verification commands

The repository uses an uninstalled `src` layout and the approved Python 3.12 executable. Set `PYTHONPATH` only for the current PowerShell process, restore it afterward, and run both suites without installing the project or dependencies:

```powershell
$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
$previousPythonPath = $env:PYTHONPATH

try {
    $env:PYTHONPATH = (Resolve-Path "src").Path

    & $python -m unittest discover `
      -s tests `
      -p "test_product_intelligence_v0_1.py" `
      -v

    & $python -m unittest discover `
      -s tests `
      -p "test_*.py" `
      -v
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
```
