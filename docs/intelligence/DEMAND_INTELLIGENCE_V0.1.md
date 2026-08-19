# Demand Intelligence Foundation V0.1

## 1. Status and boundary

Demand Intelligence V0.1 is an immutable, deterministic organization layer over
`CanonicalEvidenceBundle`. Its ruleset identifier is exactly:

```text
demand-intelligence-v0.1
```

The executable boundary is:

```text
CanonicalEvidenceBundle
        -> DemandIntelligenceRequest
        -> DemandIntelligenceBuilderV0_1
        -> DemandIntelligenceSnapshotV0_1
```

Demand source code imports only `amazon_product_intelligence.contracts`, relative
Demand modules, and the Python standard library. Provider raw JSON, adapter results,
adapter contexts, and Product Intelligence snapshots are not public inputs.

V0.1 organizes evidence. It does not calculate demand, opportunity, market size,
competitor count, competition, preferred values, recommendations, advertising
strategy, or product ranking.

## 2. Public API

`amazon_product_intelligence.demand_intelligence` explicitly exports:

- `DEMAND_INTELLIGENCE_RULESET_VERSION`
- `DemandIntelligenceRequest`
- `DemandIntelligenceSnapshotV0_1`
- `DemandIntelligenceBuilderV0_1`
- `DemandIntelligenceError`
- `DemandIntelligenceValidationError`
- `DemandSubjectNotFoundError`
- `DemandIdentityCollisionError`
- `DemandSerializationError`
- the immutable metric, relationship, query, inventory, coverage, diagnostic,
  quality-reference, and lineage models used by the snapshot

## 3. Exact keyword identity

The request reuses the canonical `KeywordIdentity` object. Matching is Python value
equality against that complete canonical object. Demand Intelligence performs no
additional lowercasing, uppercasing, trimming, whitespace collapsing, Unicode
normalization, punctuation removal, stemming, translation, or synonym expansion.

This rule intentionally keeps the two fixture identities below distinct even though
their canonical `keyword_id` and `normalized_text` are equal:

```text
raw_text = "1/2 Ball Valve"
raw_text = "1/2 ball valve"
```

The different `raw_text` values make the complete `KeywordIdentity` values unequal.
Evidence for one is not silently attached to the other.

An exact target is considered present when at least one supplied canonical record is:

- a `KeywordMetricObservation` whose `keyword` equals the target;
- a `ProductKeywordRelationshipObservation` whose `keyword` equals the target; or
- a forward `DirectionalQueryExecutionRecord` whose `query_keyword` equals the
  target.

Otherwise the builder raises `DemandSubjectNotFoundError`.

## 4. Keyword metric evidence sets

The builder consumes the actual canonical `KeywordMetricObservation` fields. Each
candidate retains its keyword, metric, metric semantic, estimate-method status,
range, evidence type, complete `ValueEnvelope`, scope, `TimeWindow`, provider
semantic, result status, provider, source tool, and lineage.

Evidence sets use the complete non-resolving grouping boundary:

- keyword identity, marketplace, and locale;
- metric and metric semantic;
- unit;
- period type, start, end, observed-at status, and timezone;
- scope;
- evidence type; and
- provider semantic.

Search volume, ABA search-frequency rank, CPC, and competition difficulty therefore
remain different metric evidence sets. Candidates in a set are never averaged,
normalized by this layer, trended, predicted, scored, preferred, or resolved.

The structural candidate state is one of:

```text
NO_PRESENT_CANDIDATE
ONE_DISTINCT_PRESENT_VALUE
MULTIPLE_DISTINCT_PRESENT_VALUES
```

`MISSING`, `EXPLICIT_NULL`, `UNKNOWN`, and numeric zero retain their canonical
meaning. Numeric zero is a present value. A non-present candidate never becomes a
zero-valued candidate.

## 5. Relationship evidence

Every matching `ProductKeywordRelationshipObservation` becomes an immutable
`RelationshipEvidenceItem`. Items are organized into groups whose boundaries are
the exact canonical `direction` and `channel`:

```text
KEYWORD_TO_PRODUCT / PRODUCT_TO_KEYWORD
ORGANIC / SPONSORED / MIXED / UNKNOWN
```

Directions and channels are never merged. The canonical rank object, traffic
envelope, relationship type, query result status, evidence type, value, scope, time,
provider semantic, and lineage remain on the individual record. There is no rank
aggregation or channel preference.

The adapter's audited interpretation of provider rank codes remains authoritative.
The Demand layer does not reinterpret `or`, `sb`, or any unknown code.

## 6. Query execution evidence

The builder consumes canonical `DirectionalQueryExecutionRecord` values; it does
not reconstruct query execution from relationship rows. All four outcomes remain
representable:

```text
RESULTS_RETURNED
EXPLICIT_EMPTY
OUTCOME_UNKNOWN
EXECUTION_FAILED
```

A forward record belongs to a snapshot only when its `query_keyword` exactly equals
the target. A reverse record belongs when either:

- its result relationships contain the exact target keyword; or
- its `query_product` is already an observed product endpoint for the target keyword.

The second rule allows an empty, unknown, or failed reverse execution to be retained
when a separate canonical relationship supplies the product-to-target association.
The association IDs are explicit in `target_related_relationship_observation_ids`.
No association is invented for an unrelated reverse query.

The exact query result IDs remain in `related_relationship_observation_ids`.
Forward and reverse evidence is never combined. A forward `EXPLICIT_EMPTY` beside a
reverse `RESULTS_RETURNED` record produces the informational
`DIRECTIONAL_QUERY_ASYMMETRY` diagnostic. It does not imply zero demand, no related
products, or a contradiction requiring resolution.

## 7. Related product evidence inventory

`related_product_evidence_inventory` contains only product endpoints actually
present in matching canonical relationship observations. Each inventory item lists
its supporting relationship observation IDs, directions, channels, providers, and
lineage.

This is an evidence inventory, not a competitor set. Its tuple length is not
published as competitor count or market size, and membership does not establish
competition.

## 8. Out-of-scope canonical evidence

Supplied `ProductFactObservation`, `MetricObservation`, and `ReviewObservation`
records are not inputs to demand inference. They remain visible as
`OutOfScopeEvidenceReference` entries with their observation IDs, kinds, reason
codes, and replayable lineage. An informational diagnostic documents their
exclusion.

Keyword observations and query executions that do not exactly relate to the target
are also inventoried as out of scope. This prevents a multi-bundle request from
silently losing supplied records while preserving the exact target boundary.

## 9. Coverage

`DemandEvidenceCoverage` is an inventory of:

- source bundle, raw reference, and transformation-run counts;
- keyword metric, relationship, and query execution counts;
- included metric, relationship, and query counts;
- out-of-scope record count;
- relationship and query direction counts;
- channel and query outcome counts;
- providers and provider record counts;
- canonical quality issue count; and
- Demand diagnostic count.

Coverage contains no completeness, trust, confidence, score, or provider ranking.

## 10. Replayable lineage

Every included metric candidate, relationship record, query record, related-product
inventory item, and out-of-scope reference is connected to a
`DemandLineageReference`. A reference records:

```text
canonical observation or query execution ID
        -> transformation_run_id
        -> mapping_version
        -> raw_evidence_id
        -> collection_run_id
        -> source bundle fingerprint
```

It also retains provider, source tool, and source field. Canonical bundles currently
carry the audited mapping identity as `TransformationRunRecord.mapping_version`;
they do not embed the adapter's `MappingSpecification` object. V0.1 therefore
replays the mapping boundary through that required version identity.

`validate_against_bundles()` validates bundle fingerprints and replays every public
lineage reference. It rejects wrong input types, duplicate bundle fingerprints,
missing observations or query records, transformation mismatches, mapping
mismatches, orphan raw references, collection mismatches, and source fingerprint
mismatches. Builder indexing also rejects conflicting observation, query,
transformation, quality issue, keyword, product, conflict, and resolution identities.

## 11. Immutability, identity, and serialization

Requests and snapshots use frozen, slotted dataclasses. Sequences are detached as
tuples. JSON-like nested mappings and lists are validated, copied, and recursively
frozen as mapping proxies and tuples. Supplied canonical bundles are themselves
immutable contract objects.

The request sorts unique bundles by their order-insensitive canonical SHA-256
fingerprint. Snapshot members use explicit stable sort keys. IDs use SHA-256 over
canonical JSON through the canonical `deterministic_id` function. Identity does not
use current time, UUIDs, randomness, `hash()`, `repr()`, or filesystem order.

`snapshot_id` includes the exact ruleset version and all serialized snapshot
content. Strict `from_dict()` round trips enums and nested contracts, rejects unknown
fields and invalid enum values, and rejects a snapshot whose ID does not match its
content.

## 12. Audited fixture discovery

The following inventory records the actual Adapter V0.1.4 canonical output used by
the Demand integration tests.

### `xiyou_keyword_info.json`

- `plastic spoons`: present `search_volume=41910`,
  `aba_search_frequency_rank=2922`, `competition_difficulty=63`, and `cpc=2.74`.
- `1/2 Ball Valve`: the same four metric kinds, each `EXPLICIT_NULL`.
- Mapping: `xiyou_keyword_info_mapping_v1`.
- No relationship or query execution records.

### `xiyou_keyword_forward_populated.json`

- Query keyword: exact identity for `plastic spoons`.
- Product endpoint: `B0CDV36NF6`.
- Direction: `KEYWORD_TO_PRODUCT`.
- Five relationship observations: unknown-channel candidate membership, sponsored
  rank, organic rank, organic traffic, and sponsored traffic.
- Query outcome: `RESULTS_RETURNED`, referencing all five observations.
- Mapping: `xiyou_keyword_to_asin_mapping_v1_1`.

The provider envelope's `total=647` is not a market-size or competitor metric.

### `xiyou_keyword_forward_empty.json`

- Query keyword: exact identity for `1/2 ball valve`.
- Direction: `KEYWORD_TO_PRODUCT`.
- Relationship observations: none.
- Query outcome: `EXPLICIT_EMPTY` with zero related observation IDs.
- Mapping: `xiyou_keyword_to_asin_mapping_v1_1`.

### `xiyou_asin_keywords_reverse.json`

- Query product: `B0G2VV4RBW`.
- Keyword identity raw text: `1/2 ball valve`.
- Direction: `PRODUCT_TO_KEYWORD`.
- Five relationship observations: unknown-channel candidate membership, sponsored
  rank, organic rank, organic traffic `355`, and sponsored traffic `0`.
- Query outcome: `RESULTS_RETURNED`, referencing all five observations.
- Mapping: `xiyou_asin_to_keyword_mapping_v1_1`.

The reverse sponsored traffic value `0` remains a present zero. The provider
envelope's `total=91` is not a demand metric.

## 13. Residual limits

V0.1 intentionally leaves the following unresolved:

- provider metric methods or periods that canonical evidence marks unknown;
- the business meaning of an empty query beyond the fact that it executed and
  returned no relationship rows;
- whether any related product is a competitor;
- whether forward and reverse asymmetry is expected provider behavior;
- cross-provider metric resolution, weighting, or preference; and
- demand, opportunity, market, recommendation, and advertising conclusions.

Those limits must be addressed by later, explicitly authorized rulesets rather than
inferred by this foundation layer.
