# Competition Intelligence Foundation V0.1

## 1. Status and boundary

Competition Intelligence V0.1 is an immutable, deterministic evidence inventory
over `CanonicalEvidenceBundle`. Its ruleset identifier is exactly:

```text
competition-intelligence-v0.1
```

The executable boundary is:

```text
CanonicalEvidenceBundle
        -> CompetitionIntelligenceRequest
        -> CompetitionIntelligenceBuilderV0_1
        -> CompetitionIntelligenceSnapshotV0_1
```

Competition source code imports only `amazon_product_intelligence.contracts`,
relative Competition modules, and the Python standard library. Provider raw JSON,
adapter results and contexts, Product Intelligence snapshots, and Demand
Intelligence snapshots are not public inputs.

V0.1 organizes evidence that later layers may inspect. It does not identify a
competitor set, infer competitive relationships, calculate competitor count or
competition intensity, compare prices, sales, revenue, ranks, reviews, or market
share, select preferred evidence, score products, classify markets, or issue
recommendations.

## 2. Public API

`amazon_product_intelligence.competition_intelligence` explicitly exports:

- `COMPETITION_INTELLIGENCE_RULESET_VERSION`;
- `CompetitionIntelligenceRequest`;
- `CompetitionIntelligenceSnapshotV0_1`;
- `CompetitionIntelligenceBuilderV0_1`;
- the Competition error hierarchy;
- direct/derived and source-record classifications;
- product, keyword, relationship, and variation evidence models;
- evidence graph node, edge, and graph models; and
- coverage, diagnostic, quality-reference, and lineage models.

The request accepts a non-empty tuple of canonical bundles only. It has no hidden
subject, competitor, provider, score, or threshold parameter.

## 3. Direct and derived evidence

The `classification` field makes the boundary explicit:

- `DIRECT_EVIDENCE` is a lossless projection of a qualifying canonical
  observation. It applies to keyword-product relationships and confirmed variation
  relationships.
- `DERIVED_EVIDENCE` is deterministic organization of direct or supplied canonical
  evidence. It applies to product inventory entries, keyword views, and graph nodes
  and edges.

Derived records never become observed facts. Their source observation IDs and
replayable lineage remain explicit.

## 4. Keyword-product relationship evidence

Every supplied `ProductKeywordRelationshipObservation` remains an individual
`CompetitionRelationshipEvidence` record. It preserves:

- product and keyword identity;
- `KEYWORD_TO_PRODUCT` or `PRODUCT_TO_KEYWORD` direction;
- relationship type and `ORGANIC`, `SPONSORED`, `MIXED`, or `UNKNOWN` channel;
- query result status;
- the complete rank mapping and traffic envelope;
- evidence type, value, scope, time, result status, and provider semantic; and
- provider, source tool, and canonical lineage.

Directions and channels are never merged. Rank and traffic values are not averaged,
summed, compared, normalized, or used to produce a competitive conclusion. A
keyword relationship proves only that the provider emitted that audited canonical
relationship.

## 5. Variation evidence

Only a canonical `ProductFactObservation` with one of these dimensions can enter
the variation inventory:

```text
child_product_relationship
parent_product_relationship
```

Its value must also be `PRESENT` and `CONFIRMED`. Missing, null, unknown, or
unconfirmed values are excluded with an informational diagnostic; they are not
converted into an edge.

Direction is normalized without discarding the source dimension:

- `child_product_relationship`: the observation subject is the parent and the
  normalized value is the child;
- `parent_product_relationship`: the normalized value is the parent and the
  observation subject is the child.

Parent and child must share a marketplace and cannot be the same product. Multiple
providers may support the same normalized parent-child graph edge, while their
individual direct observations remain separate.

Products that share a parent are siblings, not proven competitors. The builder
emits `SIBLING_COMPETITION_NOT_INFERRED` when this situation is visible and never
creates a sibling or competitor edge.

## 6. Observed product and keyword inventories

`observed_product_inventory` contains product identities that are actually present
in supplied canonical evidence, including relationship endpoints, review products,
product subjects, and confirmed variation endpoints. Each derived entry retains
its source observations, observed keywords, directions, channels, providers,
source tools, and lineage.

`keyword_evidence` is a derived view grouped by exact canonical `KeywordIdentity`.
It references the direct relationship observations, product endpoints, directions,
channels, providers, and lineage that support the view.

Neither inventory is a competitor set. Membership and tuple length do not establish
competition, market size, competitor count, or product similarity. Products in
different marketplaces remain different canonical identities.

## 7. Evidence relationship graph

The graph contains product identity nodes only. Its closed edge vocabulary is:

```text
keyword_observed_relationship
variation_relationship
```

A keyword-observed edge is a unary attachment between one product node and the
exact keyword recorded by one direct relationship observation. It does not connect
multiple products merely because they share a keyword.

A variation edge has two product endpoints and explicit
`variation_parent_product_identity` and `variation_child_product_identity` fields.
The generic endpoint tuple is canonicalized for deterministic identity; the
explicit fields preserve semantic direction.

There is deliberately no `COMPETITOR_EDGE`, similarity edge, co-occurrence edge,
sibling edge, or inferred edge type in V0.1.

## 8. Coverage and diagnostics

`CompetitionCoverageSummary` inventories source bundles, raw references,
transformation runs, observed product and keyword identities, direct relationship
and variation observations, graph edge types, providers, source tools, channels,
directions, canonical quality issues, and Competition diagnostics.

Coverage is descriptive bookkeeping. It contains no score, confidence, trust,
completeness percentage, provider preference, competitive rank, or intensity.
Diagnostics explain structural exclusions and absences without turning them into
business conclusions.

## 9. Replayable lineage

Every public evidence-bearing item connects to a
`CompetitionLineageReference`. A reference records:

```text
canonical observation ID and semantic observation ID
        -> transformation_run_id
        -> mapping_version
        -> raw_evidence_id
        -> collection_run_id
        -> source bundle fingerprint
```

It also retains observation kind, Competition source-record type, provider, source
tool, and source field. `validate_against_bundles()` verifies bundle fingerprints
and replays every public lineage reference through the observation, transformation,
raw evidence, and collection boundaries. It rejects a wrong source-record type,
missing or conflicting identity, orphan reference, mapping mismatch, collection
mismatch, and source fingerprint mismatch.

## 10. Immutability, identity, and serialization

Requests and snapshots use frozen, slotted dataclasses. Sequences are detached as
tuples. Nested mappings and lists are copied and recursively frozen. Builder
indices reject conflicting bundle, observation, transformation, raw evidence,
collection, quality issue, product, keyword, conflict, and resolution identities.

Bundle fingerprints use SHA-256 over canonical JSON and do not depend on bundle
input order. Snapshot members have explicit stable ordering. Content IDs use the
canonical `deterministic_id` function and do not use time, UUIDs, randomness,
`hash()`, `repr()`, or filesystem iteration order.

Strict `from_dict()` round trips enums, mappings, and nested contracts, rejects
unknown fields and invalid enum values, and rejects content whose deterministic ID
does not match. `snapshot_id` covers the ruleset and complete serialized snapshot
payload.

## 11. Audited fixture discovery

Integration tests execute the real XiYou and Sorftime adapters and consume only
their resulting canonical bundles:

- XiYou keyword forward output supplies five `KEYWORD_TO_PRODUCT` relationships
  for `plastic spoons`, retaining organic/sponsored channel, rank, and traffic;
- XiYou keyword reverse output supplies five `PRODUCT_TO_KEYWORD` relationships
  for product `B0G2VV4RBW` and keyword `1/2 ball valve`;
- XiYou variations output supplies confirmed child relationships from parent
  `B0G2VVX3ML` to children `B0G2VV4RBW` and `B0G2VZSWRN`;
- Sorftime product detail supplies a confirmed parent relationship from child
  `B0G2VV4RBW` to parent `B0G2VVX3ML`.

These fixtures exercise both relationship directions, multiple channels,
multi-provider variation support, marketplace identity, graph construction,
lineage replay, deterministic ordering, and strict serialization. They do not make
the fixture products competitors.

## 12. Residual limits

V0.1 intentionally leaves these questions unresolved:

- whether products attached to the same keyword compete;
- whether siblings, parents, children, or products seen by different providers are
  substitutes or competitors;
- which provider, rank, traffic, price, sales, review, or product fact is preferred;
- how complete the observed inventory is;
- what competitive intensity, market share, opportunity, or recommendation follows;
- how unsupported provider semantics or unconfirmed relationships should be
  interpreted beyond preserving their canonical state.

Those decisions require separately versioned rules and acceptance criteria. They
must not be inferred by Competition Intelligence V0.1.
