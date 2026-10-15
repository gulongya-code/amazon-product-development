# SP-041R2 Route Discovery V2

## 1. Purpose and scope

Route Discovery V2 is a deterministic, explainable route-discovery layer over the accepted Semantic Engine V2 (S2). It replaces the V1 exact-known attribute signature as the route-membership authority without re-evaluating product identity, product role, or market-cohort eligibility.

This document describes the implemented engineering contract. It is not an acceptance verdict and does not assert that a private replay or bounded human review has passed.

The governed flow is:

```text
SP-041B governed listing dataset
    -> accepted Semantic Engine V2 result
    -> S2 PRIMARY_ONLY cohort gate
    -> profile-authorized semantic route projection
    -> ordered hierarchical sparse semantic consensus
    -> one membership state per listing
    -> retained SP-041D market metrics
    -> semantic-distinct candidate routes when evidence is sufficient
```

The public entry point is `build_route_discovery_v2(dataset, semantic_result, profile=..., config=...)`. R2 consumes the governed SP-041B dataset and the matching accepted S2 result at listing grain; it does not import source spreadsheets itself.

## 2. S2 is the authoritative upstream

R2 accepts S2 decisions as frozen upstream facts. It does not reimplement Product Identity, Product Role, evidence-relationship logic, or market-cohort logic.

Before projection, the engine validates all of the following:

- the S2 result references the same governed dataset ID and semantic fingerprint;
- the S2 profile ID, version, and fingerprint match the supplied category profile;
- the governed dataset and S2 result contain the same listing set;
- every S2 listing points to the corresponding governed record fingerprint; and
- the route configuration and profile both authorize the dataset category.

Any mismatch fails closed with a stable `RouteDiscoveryV2Error` code. R2 never repairs, guesses, or silently rejoins inconsistent lineage.

Each projected `SemanticRouteFeatureView` retains the upstream record fingerprint, S2 listing result ID and fingerprint, S2 cohort state, selected semantic facts, evidence and relationship IDs, review reasons, limitations, and profile/source-policy lineage.

Only listings for which S2 sets `eligible_for_primary_cohort=true` may enter route discovery. Other listings remain in the result at the same grain but cannot receive a route:

- an S2 `REVIEW_REQUIRED` cohort state maps to route `REVIEW_REQUIRED`;
- every other non-primary cohort state maps to route `UNCLASSIFIED`; and
- a route-critical or true conflict on a configured route dimension maps an otherwise eligible listing to `REVIEW_REQUIRED`.

## 3. Profile-authorized semantic projection

The route configuration may reference only dimensions that exist in the accepted category profile. A route-defining dimension must have one of the allowed architectural roles:

- `STRUCTURAL_FORM`
- `USAGE_ARCHITECTURE`
- `INSTALLATION_ARCHITECTURE`
- `ATTACHMENT_MECHANISM`
- `OPERATION_MECHANISM`
- `POWER_MODE`
- `COMPATIBILITY`
- `SIZE_CAPACITY`

A profile `CORE` dimension may define a route directly. A profile `SECONDARY` dimension may do so only when the configuration explicitly lists it in `promoted_secondary_dimensions`. A `FACET_ONLY` dimension cannot define route identity. Product Identity and Product Role cannot be used as route descriptors.

Projection evaluates every configured route dimension. Whenever that dimension is present, it retains the dimension and all available normalized values while separately identifying the complete set of route-defining `defining_values`; an absent dimension stays absent rather than becoming a synthetic empty feature:

1. facts from the profile policy's primary sources are preferred;
2. governed fallback-source facts are used only when primary-source facts are absent;
3. corroborating-only facts remain visible for lineage and diagnostics but can never define route identity, supply a missing route value, or participate in route consensus; and
4. conflicts and source limitations remain explicit in the feature contract.

This projection is a read-only interpretation of accepted S2 facts. It does not mutate profiles or S2 output.

## 4. Ordered hierarchical sparse semantic consensus

The implemented method is versioned as `PROFILE_AUTHORIZED_HIERARCHICAL_SPARSE_SEMANTIC_CONSENSUS` in engine version `route-discovery-v2.0`.

For each PRIMARY_ONLY-eligible, non-conflicted listing, the engine builds one semantic signature by walking `route_dimensions` in configuration order. The signature retains every configured dimension that has profile-authorized `defining_values`, and retains all defining values on each such dimension. It does not select one value from a multi-value fact. A listing with no route-defining value remains unclassified; corroborating-only values never enter the signature.

Grouping then proceeds deterministically:

1. The first available configured dimension in each signature is its base dimension. Exact full value sets on that dimension form base nodes; this allows a listing whose earlier configured dimension is absent to start at its first known dimension without treating missingness as equality.
2. A base node with at least `min_route_size` members is viable. A tiny base can merge only into one uniquely compatible viable base on the same dimension. Compatibility requires a non-empty semantic value intersection, and the merged base must retain a non-empty consensus across every included base. A tiny base with zero or multiple viable targets, or whose combined consensus is empty, remains unresolved during hierarchical construction.
3. Within each viable base, the engine considers later configured dimensions in order. It refines only at the first dimension having at least two different exact single-value buckets that each independently reach `min_route_size`. Those buckets become child nodes and may be refined again by still-later dimensions.
4. Missing, multi-value, and rare remainder signatures are not forced to equal a single-value bucket. If their combined remainder reaches `min_route_size`, they form a broad parent route under the current semantic prefix. If the remainder is too small, only a multi-value signature that intersects exactly one viable child can attach directly to that child; the others remain unresolved during hierarchical construction.
5. Every emitted child route carries its complete hierarchical prefix. A broad parent carries only the prefix supported before the split. Thus known contradictory semantics can form distinct routes while sparse evidence remains broad or advances to an explicit compatibility outcome rather than becoming a false equality.
6. After all viable hierarchical routes are formed, a final generic compatibility resolver considers only still-unresolved groups that have a real defining signature. A route is compatible only when it shares at least one dimension with the signature and the value sets intersect on every shared dimension. Zero compatible routes yields `UNCLASSIFIED`; exactly one yields `ASSIGNED`; multiple compatible routes yield `REVIEW_REQUIRED`. A missing dimension and corroborating-only evidence cannot create a shared match, while market metrics, input or lexical order, and canonical sort order cannot choose among multiple compatible routes.

The five shipped configurations use a minimum route size of three and the singleton policy `MERGE_COMPATIBLE_ELSE_UNCLASSIFIED`. Canonical JSON, canonical value-set ordering, configured dimension order, and stable content-derived sorting are determinism mechanisms only; lexical order, market metrics, row order, and missingness never decide route membership. The method performs no fuzzy, probabilistic, learned, category-specific, network-backed, or LLM-backed clustering.

## 5. Membership and result contracts

R2 defines the following immutable, fingerprint-checked contracts:

- `SemanticRouteFeature` records one profile-authorized dimension, all visible values, defining values, fact/evidence/relationship lineage, relevance, and limitations.
- `SemanticRouteFeatureView` is the listing-grain S2-to-route projection.
- `RouteSemanticKey` is a route-defining role, dimension, and non-empty canonical value set.
- `RouteV2Membership` uses contract `route-membership-v2.0` and assigns exactly one state: `ASSIGNED`, `UNCLASSIFIED`, or `REVIEW_REQUIRED`.
- `ProductRouteV2` records defining semantics, members, membership IDs, evidence, limitations, feature coverage, descriptors, and retained market metrics.
- `RouteDiscoveryV2Result` uses contract `route-discovery-v2-result-v1.0` and carries complete upstream lineage, listing and membership counts, routes, metric denominators, references, candidate status, and bounded diagnostics.

An `ASSIGNED` membership must reference exactly one existing primary route. `UNCLASSIFIED` and `REVIEW_REQUIRED` memberships cannot reference a route. The result enforces:

```text
listing_count = assigned_count + unclassified_count + review_required_count
```

It also rejects duplicate listing memberships, duplicate route IDs, unknown route references, and ID/fingerprint mismatches. Product grain remains `LISTING_ASIN_NO_PARENT_COLLAPSE`; parent relationships do not collapse listings into one route member.

IDs and semantic fingerprints are content-derived. Memberships include reason codes, assignment evidence, profile fingerprint, route-config fingerprint, and limitations so an assignment can be reproduced and explained without an LLM.

## 6. Secondary and facet descriptors

Descriptors summarize a route but do not split it. For configured descriptor dimensions, the engine reports profile `SECONDARY` and `FACET_ONLY` values separately. A value must occur in at least 25% of route members to be shown; at most two values per dimension and four descriptors per descriptor class are retained.

Material, quantity, packaging, cosmetic, lifecycle, and other facet-only variation therefore cannot create a distinct route or create a distinct candidate pair. Descriptor evidence remains inspectable without becoming route identity.

## 7. Frozen SP-041D metric reuse

R2 does not change SP-041D market metric formulas, denominator semantics, availability handling, evidence semantics, or nearest-rank percentile behavior.

The implementation reuses two accepted V1 boundaries:

- `build_governed_market_fields(...)` projects the same governed market inputs and evidence/availability states used by SP-041D; and
- `build_route_metrics(...)` computes the accepted route metrics and explicit denominators without an R2 formula fork.

R2 supplies those functions with a listing-grain metric adapter whose route/adoption attributes come from the S2 feature view. The configured new-product age threshold is retained from SP-041D. Missing market fields stay unavailable or partial under the existing metric-context contract; R2 does not impute them.

For any non-empty route set, the engine checks that assigned-cohort route listing shares sum to one. When route sales shares are available, it checks that they sum to one as well. Month-over-month aggregate growth and review-count distributions continue to use the frozen SP-041D aggregation and `NEAREST_RANK` policies.

## 8. Candidate route selection

Candidate qualification reuses the frozen SP-041D market-evidence reason codes. R2 adds only the semantic-distinctness layer required for Route Discovery V2:

1. routes with duplicate defining semantic token sets are deduplicated;
2. a route must satisfy the configured minimum count of SP-041D metric reason codes;
3. qualified routes are ordered deterministically by member count, reason count, retained demand and sales evidence, then route ID;
4. semantic distance is the symmetric difference of defining semantic tokens divided by their union;
5. every selected pair must be materially distinct: the routes must share at least one known route dimension on which their defining value sets are disjoint, so missingness or a broad-versus-specific relationship cannot manufacture diversity; and
6. every selected pair must also meet the configured minimum semantic distance.

The shipped configurations request three to five candidates, require at least two metric reason codes, and use a minimum semantic distance of `0.15`. Selection is a deterministic pairwise clique search, attempted from five candidates down to three in the frozen qualification order. The engine never forces a minimum candidate count: if no qualifying clique of at least three exists, it returns no candidates with `INSUFFICIENT_EVIDENCE`.

Because candidate semantic tokens come only from route-defining keys, facet-only differences cannot make two candidates distinct.

## 9. Strict configuration roles

The strict JSON schema separates five kinds of configuration authority:

| Configuration role | Purpose |
| --- | --- |
| Category authority | `category` and `category_aliases` bind a configuration to categories also accepted by the S2 profile. |
| Ordered route identity | `route_dimensions` defines the authorized base and recursive refinement order for hierarchical semantic consensus. |
| Explicit secondary promotion | `promoted_secondary_dimensions` is the allowlist for profile-secondary dimensions intentionally elevated into route identity. |
| Route description | `descriptor_dimensions` exposes secondary/facet summaries that cannot split a route. |
| Adoption and metric context | `adoption_dimensions` supplies semantic attributes used by the retained SP-041D metric layer without redefining route membership. |

The schema rejects missing keys, unknown keys, duplicate dimensions, unsupported singleton or percentile policies, invalid candidate bounds, and unauthorized profile roles. Quantitative controls such as minimum route size, new-product age, candidate evidence count, and semantic distance are config data rather than category branches in the generic engine.

Five category configurations are shipped:

| Configuration | Ordered route dimensions | Descriptor dimensions |
| --- | --- | --- |
| Shower caddies | installation architecture, attachment mechanism | package count |
| Dog water bottles | operation mechanism | item capacity, package count |
| Vacuum replacement filters | compatibility | material, consumable unit count |
| Food storage containers | structural form | item capacity, structural component count |
| Air fryers | structural form, operation mechanism | consumable unit count |

All five use the same generic Python implementation. Category vocabulary and dimension choices remain in the accepted semantic profiles and strict configuration files; there are no category-specific branches in route code.

## 10. Determinism, privacy, and CLI boundary

Determinism is enforced through canonical JSON serialization, stable sorting, content-derived IDs, immutable contract validation, and config/profile fingerprints. Input listing order and non-semantic import timestamps do not change a result when governed semantic content is unchanged. The engine has no randomized clustering, learned threshold, or online dependency.

R2 performs zero network, provider, credential, or authoritative LLM calls. Neither route membership nor candidate membership depends on network or LLM availability. Diagnostics expose bounded counts, IDs, fingerprints, route-size distributions, and reason codes; they do not include source titles or raw private values.

The full runtime result necessarily retains listing-grain references and evidence lineage for auditability. A caller must therefore treat a serialized `RouteDiscoveryV2Result` derived from private calibration data as private and must not commit it, its raw rows, or any source workbook. Public code, configuration, tests, and documentation must contain only synthetic or sanitized material.

The production boundary remains the Python library API. A separate local acceptance CLI, `scripts/run_route_discovery_v2_private_replay.py`, runs the governed SP-041B importer, accepted S2 engine, and R2 over the authorized five-category manifest. Its primary output is a privacy-scanned, aggregate-only JSON summary. It can also create a new, explicitly external listing-grain JSON review sample whose operator decisions are all blank; it never fabricates, infers, or repairs human labels. Private inputs, completed review documents, and the blank review artifact must remain outside the repository. The CLI adds no workbook writer, network service, provider call, or authoritative LLM path.

## 11. Known limitations

- The hierarchical method refines only when at least two later-dimension single-value buckets independently meet the configured support floor. It intentionally preserves a viable broad parent or leaves undersupported evidence unclassified instead of forcing maximum fragmentation.
- Multi-value facts remain complete value sets. A small multi-value remainder attaches directly only when it intersects one unique viable child; a later all-dimension compatibility result with multiple possible routes is sent to review, not broken by arbitrary order.
- Compatible tiny-base merging is conservative: it requires one same-dimension viable target and a non-empty combined semantic consensus. The final resolver likewise requires compatibility on every shared known dimension. There is no fuzzy nearest-route fallback.
- Descriptors are aggregate summaries with fixed coverage and count bounds; they are not new semantic facts.
- Candidate selection depends on both semantic distinctness and availability of frozen SP-041D market evidence. It can correctly return insufficient evidence.
- Adding another category requires an accepted S2 profile and strict R2 configuration. It must not require a category literal in generic engine code.
- The local review sample is only a blank review instrument. This implementation contract and its CLI do not assert acceptance and do not replace the required quantitative replay, deterministic replay, privacy scans, regressions, or completed bounded human route-coherence review.

## 12. Forbidden downstream scope

SP-041R2 stops at deterministic route discovery and candidate-route evidence. It does not:

- select representative listings or representative ASINs;
- create Direct Competitors;
- implement a procurement ceiling;
- start SP-041E;
- change or extract a Shared Semantic Core package;
- cut `amazon_keyword_screener` over to S2 or R2;
- change accepted S2 semantic contracts;
- change frozen SP-041D metric formulas; or
- use an LLM as authoritative route-membership logic.

Those actions remain outside this implementation and require their own governed tasks and acceptance gates.
