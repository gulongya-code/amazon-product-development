# TASK-SP-042B — Provider-Neutral Route Discovery Input Boundary

Report date: 2026-08-29

## A. Baseline and scope

- Required baseline and verified starting HEAD: `da651cf397a0b4c6d1a1b991359c6d68d3b3ca25`.
- Required branch: `codex/task-sp-042b-provider-neutral-route-input`.
- Startup worktree status: clean.
- This task adds only the provider/input boundary for accepted Semantic Engine V2
  and Route Discovery V2 inputs.
- Market Report implementation, operator rendering, Route Discovery V2 semantics,
  category profiles/configuration, live acquisition, and acceptance integration are
  unchanged.
- No live provider or paid API call was made.

## B. Dependency and provider-coupling audit

The audit reviewed the existing provider adapters/connectors, Canonical evidence
and normalization contracts, Data Cleaning, the Sorftime contract/migration and
DTO-mapper reports, the XiYou/Sorftime capability findings, the governed dataset,
Semantic Engine V2, and Route Discovery V2.

| Classification | Dependency | SP-042B disposition |
| --- | --- | --- |
| Reusable provider-neutral | `CanonicalEvidenceBundle`, Canonical observations, `SubjectRef`, value/presence/unit/status contracts, transformation provenance, raw-evidence references, canonical JSON/IDs | Reused unchanged as the only accepted provider-side input. |
| Reusable provider-neutral | `CanonicalNormalizationPipeline` and its field-specific rules | Reused for ASIN, text, count, money, rank, rating, and date normalization. |
| Reusable provider-neutral | `GovernedMarketDatasetV1`, `ListingRecordV1`, `NormalizedField`, import value states, row outcomes | Reused as the exact dataset shape already consumed by S2/R2. Its source-kind default was made overrideable and missing evidence gained an honest `UNKNOWN` evidence semantic. Existing SellerSprite output is unchanged. |
| Reusable provider-neutral | S2 profiles/source policies/evidence relationships and Route Discovery V2 projection/engine | Reused without modification. The new boundary stops before S2. |
| Adapter-required | Canonical observation names/grains to the governed 66-header input vocabulary | Implemented as an explicit, versioned mapping table plus structured-attribute projection. |
| Adapter-required | Provider observation lineage to listing/header grain | Implemented as a deterministic field-lineage and field-availability sidecar linked by observation, raw-evidence, transformation, mapping, record, dataset, and package fingerprints. |
| Provider-coupled replaceable | `adapters/xiyou_*`, `connectors/xiyou_*`, `adapters/sorftime_*`, `connectors/sorftime_*`, provider DTOs/transport/source-field mappings | Left in their proper provider-owned layers. No source field, endpoint, sentinel, rank code, or provider preference was copied into the new boundary. |
| Provider-coupled requiring later refactor | Production Pipeline provider literals/composition, XiYou live client construction/replay paths, Batch XiYou-only validation, legacy organic-keyword capture and holdout workflows | Out of scope and unchanged. These remain acquisition/orchestration concerns, not Route Discovery intelligence semantics. |
| Provider-coupled requiring later refactor | Provider-neutral dataset contract remains located under the `sellersprite_import` package and retains the frozen operator-header shape | The source-kind false claim is removed for this adapter, but physical contract extraction/renaming is deferred because it would be a broad S2/R2 contract migration. |

Audit conclusion: the missing seam was not another provider adapter. Provider
adapters already terminate in Canonical evidence. The missing seam was a strict
Canonical-evidence-to-governed-listing adapter that did not choose a provider,
read provider payloads, or require intelligence code to know provider field names.

## C. New boundary and architecture

```text
Provider payload
  -> provider-owned strict DTO/adapter
  -> CanonicalEvidenceBundle(s)
  -> SP-042B build_route_discovery_input(...)
       -> explicit Canonical-field mapping
       -> existing Canonical normalization rules
       -> identity / marketplace / unit gates
       -> deterministic duplicate and conflict handling
       -> GovernedMarketDatasetV1
       -> field availability + raw/transformation provenance sidecar
  -> accepted Semantic Engine V2
  -> accepted Route Discovery V2
```

The public entry point is:

```python
build_route_discovery_input(
    bundles,
    context=RouteDiscoveryInputContext(...),
)
```

It returns `RouteDiscoveryInputPackage`. Callers pass `package.dataset` to the
existing S2 builder and then pass that dataset plus the matching S2 result to the
existing R2 builder. No R2 overload or provider branch was added.

The package contains:

- the exact governed dataset consumed by S2/R2;
- provider IDs as provenance only, never preference or control flow;
- Canonical bundle fingerprints;
- all raw-evidence references and transformation-run IDs;
- one availability record per mapped field/listing;
- field lineage with Canonical name, source operation/field, observation IDs,
  raw reference, mapper/run, normalization rule, units, statuses, selected-value
  fingerprint, and disposition;
- bounded issues and deterministic counts; and
- content-derived package, dataset, record, issue, and lineage identities.

## D. Explicit Canonical mapping

Mapping version: `route-discovery-canonical-field-map-v1.0`.

| Canonical observation | Governed target | Unit gate |
| --- | --- | --- |
| product fact `asin` / `product.asin` | `ASIN` and listing identity | Existing Canonical ASIN rule; must equal the product subject. |
| product fact `title` / `product.title` | `商品标题` | Text. |
| product fact `brand` / `product.brand` | `品牌` | Text. |
| product fact `category` / `product.category` | `类目路径` | Text. |
| product fact `parent_product_relationship` / `product.parent_asin` | `父ASIN` | Existing Canonical ASIN rule; self-parent is not promoted. |
| product fact `fulfillment` / `product.fulfillment` | `配送方式` | Text. |
| product fact `first_available_date` / `product.first_available_date` | `上架时间` | Existing Canonical date rule. |
| metric `estimated_monthly_sales` | `月销量` | Existing nonnegative-integer rule plus `COUNT` dimension. |
| metric `estimated_variation_sales` | `子体销量` | Existing nonnegative-integer rule plus `COUNT` dimension. |
| metric `price` | `价格($)` | Existing money rule plus explicit `CURRENCY/USD`. |
| metric `review_count` | `评分数` | Existing nonnegative-integer rule plus `COUNT` dimension. |
| metric `rating` | `评分` | Existing rating rule plus `RATING/stars_5`. |
| metric `bsr` | `大类BSR` | Existing rank rule plus `RANK` dimension. |
| Canonical `ATTRIBUTE`/`TECHNICAL` facts not claimed above | `详细参数` | Canonical dimension becomes a normalized parameter key; primitive value and explicit unit are preserved. |

XiYou `orders` is deliberately not mapped to monthly sales. Sorftime variation
sales with unknown presence remains unavailable. Description is not relabeled as
structured parameters or bullet points. Bounded variation collections are not
promoted into complete family topology. Unknown Canonical observations are
reported as out of mapping and remain in the caller-owned Canonical bundle.

## E. Missingness, conflicts, duplicates, and fail-closed behavior

- No observation becomes `MISSING`; explicit null becomes `EXPLICIT_NULL`;
  unknown/unavailable remains `UNAVAILABLE`; malformed or unit-incompatible
  present data becomes `INVALID`.
- Missing, null, unknown, malformed, false, empty, and numeric zero remain
  distinct. No substitute zero/value is fabricated.
- Equivalent observations are deduplicated by Canonical value while retaining
  every provider lineage record.
- Conflicting scalar values produce no selected value. The target field is
  `PROVIDER_CONFLICT`, invalid/unavailable to downstream consumers, and every
  candidate remains in lineage.
- Conflicting structured attribute values are emitted as repeated governed
  key/value evidence. The existing structured-parameter parser/S2 conflict
  machinery can inspect them; the adapter does not resolve them.
- Mixed marketplace/product identity, missing explicit ASIN identity,
  identity/subject disagreement, invalid Canonical bundles, conflicting content
  under one observation ID, and non-Canonical inputs fail with stable
  `RouteDiscoveryInputError` codes.
- Input bundle order and observation order do not affect package, dataset,
  record, field, issue, or lineage identities.

## F. Exact provider-specific code remaining

No provider name or provider-specific branch exists under
`src/amazon_product_intelligence/route_discovery_input/`.

Provider-specific code intentionally remains in:

- XiYou and Sorftime DTOs, adapters, connectors, HTTP clients, payload/operation
  catalogues, source-field mappings, sentinels, pagination and cost semantics;
- Production Pipeline composition and accepted live-release gates;
- Batch Product Selection, which remains XiYou-only;
- legacy XiYou organic keyword discovery/holdout flows; and
- provider-specific fixture and validation suites.

The provider string preserved in a `RouteInputFieldLineage` is evidence metadata.
It never changes mapping, conflict, ordering, normalization, S2, or R2 behavior.

## G. Sorftime readiness

Repository evidence before SP-042B records:

- SP-040G verdict `PASS — SORFTIME_V0_2_FULL_LIVE_ACCEPTANCE`;
- `_SORFTIME_V0_1_LIVE_RELEASE_ENABLED = True` and
  `_SORFTIME_V0_2_LIVE_RELEASE_ENABLED = True` for the exact accepted live scope;
- Sorftime remains explicit-selection only, US-only for the accepted production
  slice, with no XiYou fallback; and
- Batch remains XiYou-only.

SP-042B adds an offline contract test that sends the existing strict
`SorftimeDtoMapperV0_1` ProductRequest Canonical bundle through the same generic
boundary used by two arbitrary fake providers. It preserves Sorftime raw and
transformation provenance and performs zero network calls.

Readiness verdict:

- **Boundary readiness:** ready for approved Canonical Sorftime bundles.
- **Fixture/replay readiness:** ready and tested.
- **Exact accepted live acquisition scope:** remains governed by the existing
  release/credential/request gates; SP-042B neither broadens nor disables it.
- **General live Route Discovery V2 production:** not yet end-to-end enabled.
  The production orchestrator does not yet compose live acquisition -> this
  package -> S2 -> R2, the strict DTO slice does not supply every R2 market
  metric, and complete provider category cohorts/family topology remain
  unavailable. These cannot be repaired by substituting XiYou semantics.

## H. Production permits and blockers

Permitted now:

- deterministic offline fixture/replay conversion;
- conversion of already approved, credential-safe Canonical bundles;
- S2/R2 library execution on `package.dataset`; and
- exact existing Sorftime live acquisition only through its already accepted
  production gate, with its output retained as Canonical evidence.

Still required before broad live R2 use:

1. explicit production orchestration that supplies an approved category cohort
   and calls the new boundary, S2, and R2 without changing intelligence semantics;
2. provider/category-universe completeness and pagination contracts for the
   chosen production cohort;
3. sufficient title and structured route-defining evidence at listing grain;
4. accepted period/method/unit semantics for any additional market metric;
5. normal credential, request-limit, cost, recovery, privacy, and live acceptance
   gates; and
6. separate authorization for any downstream Market Report or operator delivery
   integration.

No blocker above authorizes a provider fallback, a fabricated missing value, a
provider preference in intelligence, Market Report integration, or acceptance
integration under SP-042B.

## I. Test and fixture coverage

Dedicated sanitized fixtures cover:

- complete valid observations;
- missing optional fields;
- missing required identity;
- equivalent duplicate observations;
- scalar provider conflict and preserved structured-attribute conflict;
- malformed numerical fields;
- explicit unavailable and explicit-null data; and
- repeat conversion under reversed provider/bundle/observation ordering.

Additional tests cover exact mapping inventory, raw/transformation lineage,
USD/unit rejection, mixed-marketplace rejection, direct S2/R2 library
consumption, zero R2 provider calls, and the existing Sorftime DTO mapper.

## J. Files and validation record

Files changed or added:

- `src/amazon_product_intelligence/route_discovery_input/` — new public
  provider-neutral boundary, models, stable errors, and explicit mapping;
- `src/amazon_product_intelligence/sellersprite_import/models.py` — narrow
  provider-neutral source-kind override and honest unknown evidence semantic;
- `tests/test_route_discovery_input_v1.py` — dedicated contract/boundary tests;
- `tests/fixtures/route_discovery_input/v1/` — seven sanitized scenario fixtures;
  and
- this completion report.

Explicitly unchanged:

- `src/amazon_product_intelligence/market_report/**`;
- `src/amazon_product_intelligence/route_discovery_v2/**`;
- operator rendering/delivery;
- provider live clients, release gates, and acquisition orchestration; and
- Route Discovery V2 intelligence semantics and acceptance artifacts.

Validation used Python 3.12.13. The desktop runtime initially lacked the test
runner and one declared project dependency, so `pytest`, `pytest-subtests`, and
`rapidfuzz` were installed only into a temporary directory outside the worktree;
that directory was removed after validation. No project dependency or runtime
environment file changed.

- compileall: `PASS`;
- dedicated SP-042B suite: `13 passed`;
- affected S2/R2, governed import, Sorftime mapper, provider adapter/connector,
  Canonical normalization, and Data Cleaning gate: `283 passed, 128 subtests
  passed`;
- full repository offline suite: `1508 passed, 13 skipped, 550 subtests passed`;
- live provider calls: `0`;
- Market Report/operator/R2 implementation changes: `0`.
