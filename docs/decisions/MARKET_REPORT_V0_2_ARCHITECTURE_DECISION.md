# Market Report V0.2 Architecture Decision

Status: `ACCEPTED FOR STAGED IMPLEMENTATION`

Task: `TASK-SP-039A`

Decision date: 2026-08-24

Required baseline: `b01d18d03ab0af2fb3f448d268ff8322a42d23ec`

## 1. Context

`market-report-v0.1` is a stable, strict, deterministic contract. It owns category, sample, data window, Buyer Need projection, product-attribute count/share distributions, limited Competition metrics, Opportunity projection, provenance, and limitations. The same validated report drives XLSX and Markdown through Operator Delivery.

TASK-SP-039 found that the reference-template P0 contract also needs explicit analytical grain, market size, True Competitor membership and structure, versioned business distributions, auditable competitor rows, Buyer Need cross-links, Product Direction, Competitor Shortlist, executive claims, richer metric context, and a sanitized evidence appendix. These additions change top-level ownership and cross-section invariants; they are not safe optional fields for v0.1.

The architectural question is:

> What is the smallest safe V0.2 report contract that can absorb those P0 boundaries in stages while preserving v0.1 stability, Evidence First semantics, deterministic identity, and one validated source for delivery?

## 2. Decision

### 2.1 New top-level contract

`market-report-v0.2` will be a **new strict top-level contract**, not an in-place v0.1 schema extension and not a wrapper containing an authoritative v0.1 payload plus unrelated sidecars.

The future public type is conceptually `MarketReportSnapshotV0_2`. Its top level owns:

- metadata and semantic fingerprint;
- category, sample, and data window;
- `scope_context` and analytical grain;
- `market_size`;
- `true_competitor_set` and competitor structure;
- distributions and competitor details;
- Buyer Need projection and cross-links;
- Product Directions and Competitor Shortlist;
- Opportunity projection;
- executive summary claims;
- evidence/metric-context registries, sanitized appendix references, provenance, external integration references, and limitations.

Exact conceptual fields and invariants are frozen in `docs/requirements/MARKET_REPORT_V0_2_CONTRACT_DESIGN_V0.1.md`. This ADR does not create a runtime schema.

### 2.2 V0.1 remains immutable

The following v0.1 assets remain unchanged:

- `MARKET_REPORT_VERSION = "market-report-v0.1"`;
- `MarketReportSnapshot` and all v0.1 section dataclasses;
- `MARKET_REPORT_JSON_SCHEMA` and strict unknown-field rejection;
- v0.1 builders, adapters, fixtures, deterministic IDs, delivery behavior, and regression expectations.

No v0.2 field is added to a v0.1 payload. A v0.1 reader is not required to accept v0.2, and a v0.2 reader must not silently interpret a v0.1 payload as complete v0.2.

### 2.3 Compatibility policy

1. **Read/support:** v0.1 remains readable and supported for existing artifacts and callers. Its current tests remain a release gate.
2. **Version dispatch:** a future loader selects the exact validator by `report_version`. Unknown versions fail closed.
3. **No silent upgrade/downgrade:** conversion is an explicit adapter operation with declared loss/availability semantics, never an implicit deserialize path.
4. **Internal reuse:** v0.2 builders/adapters may consume unchanged v0.1 section models or their serialized values internally when their semantics fit. The v0.2 owner must still validate the resulting V0.2 section envelope and references.
5. **No double authority:** if a v0.1 projection is reused, v0.2 does not also retain a second authoritative copy of the same field. The V0.2 payload contains one report-owned representation with source references.
6. **Fixtures/tests:** v0.1 and v0.2 fixtures live in version-named locations, assert exact `report_version`, and are never accepted by the other validator by accident.

### 2.4 Staged completeness

Core P0 section envelopes are structurally required in V0.2. A data-gated section may be `UNAVAILABLE` with null values, explicit presence state, and limitations. This permits safe staged implementation without confusing absent evidence with zero or omitting ownership.

P1, P1-EXT, and P2 data is not a prerequisite for a V0.2 core report. External Keyword Intelligence is an optional attachment reference; it is not part of V0.2 core validity.

### 2.5 Delivery remains downstream

The only allowed direction is:

```text
Validated Market Report V0.2
        -> Operator composition
        -> XLSX + Markdown
```

Delivery may format, order, and explain validated fields. It may not calculate market size, classify competitors, create Product Directions, choose shortlist members, or invent executive claims absent from the validated report.

## 3. Why a new top level is the smallest safe boundary

A new top-level version is larger than adding one optional field, but smaller and safer than maintaining several competing truth sources. The P0 gaps share cross-cutting invariants:

- every market aggregate depends on declared scope and product grain;
- every distribution depends on a versioned policy and denominator;
- competitor detail and shortlist must reference one competitor membership identity;
- Buyer Need links and Product Directions must not mutate frozen Buyer Need records;
- executive claims must resolve to validated section/metric references;
- all references participate in one deterministic identity and orphan check.

Those invariants require one owning graph. A wrapper that treats v0.1 as an opaque authoritative subtree would either duplicate category/sample/evidence context or leave new sections unable to share one reference namespace.

## 4. Alternatives considered

### Alternative A — Add optional fields to v0.1

Rejected. v0.1 has strict required/unknown-field behavior and deterministic identities over its content. Optional additions would change its schema, payload identity, fixtures, and compatibility promise while obscuring whether a field is absent because the producer is old or because evidence is unavailable.

### Alternative B — Extension wrapper containing a complete v0.1 report

Rejected as the public V0.2 shape. It creates nested metadata and two potential ownership roots. Cross-references between extensions and v0.1 sections become indirect, executive claims span namespaces, and consumers can incorrectly treat the wrapped v0.1 subtree as the whole report. V0.1 objects may still be consumed internally by adapters.

### Alternative C — Independent sidecar contracts for every gap

Rejected. Sidecars create multiple business truth sources and cannot guarantee common scope, grain, identity, ordering, or XLSX/Markdown parity. A future implementation may modularize code by section, but the validated snapshot remains one top-level graph.

### Alternative D — Excel-first or renderer-owned calculations

Rejected. Excel is not a calculation source. Renderer formulas, hidden helper sheets, or Markdown-only narratives would bypass evidence and validation.

### Alternative E — Wait for every P0/P1/keyword data source before defining V0.2

Rejected. It would keep ownership ambiguous and encourage ad hoc outputs. Structurally required, data-gated envelopes let the contract represent `UNAVAILABLE` truthfully while implementation proceeds in bounded slices.

## 5. Compatibility and identity strategy

V0.2 will use stable canonical JSON and content-derived IDs. It separates:

- a `semantic_fingerprint`, which excludes run paths, artifact hashes, runtime health, credit usage, and ordinary generation time;
- a snapshot `report_id`, which includes the version, semantic fingerprint, and governed `generated_at` so two materialized snapshots remain distinguishable;
- section/metric/entity IDs derived from their semantic content excluding their own ID fields.

Observation windows and source observation timestamps are semantic when the metric contract says they are. Retrieval time, retry counts, output paths, and resume lineage are operational and stay outside the report semantic fingerprint.

All unordered collections have a contract-defined stable key. An intentionally ordered collection must carry an explicit governed ordinal or policy order; insertion order alone has no meaning. Duplicate identities and unresolved internal references fail validation. External references must use an explicit namespace and provenance record.

## 6. Staged implementation boundaries

### SP-039B — Foundational P0 slice

- scope/product grain contract;
- metric context envelope;
- market-size section capable of explicit unavailable values;
- True Competitor Set membership/disposition contract and adapter boundary;
- competitor concentration/barrier metric envelopes only for already governed compatible inputs.

SP-039B must not implement competitor classification algorithms, monthly sales/revenue formulas, new Provider endpoints, competitor rows, distributions, Product Direction, Shortlist, executive composition, renderers, or pipeline switching.

### SP-039C — Distributions and competitor details

- versioned distribution policies/denominators;
- evidence-linked competitor detail projection;
- compatible attribute/economic joins only where governed.

### SP-039D — Buyer Need decision-support links

- Buyer Need cross-links without changing Buyer Need source semantics;
- Product Direction human-review artifacts;
- rule/evidence-backed Competitor Shortlist.

### SP-039E and later

- data-gated P1 sections;
- optional external Keyword integration under a jointly frozen input contract;
- executive/delivery completion after source sections validate;
- separately approved P2 work.

## 7. Consequences

### Positive

- v0.1 remains reproducible and independently supportable.
- Every P0 requirement has one V0.2 owner before implementation begins.
- Missing data can be represented without zero substitution or whole-report failure.
- Scope/grain and denominator errors become visible contract failures rather than hidden analytical assumptions.
- Executive and delivery layers cannot outrun validated intelligence.
- External Keyword Intelligence can attach later without blocking core reports.

### Costs

- A version dispatcher and parallel v0.2 contract/test surface will be required.
- Explicit adapters are required to reuse v0.1 sections.
- Cross-reference validation and deterministic ordering add implementation work.
- Some sections will initially validate as `UNAVAILABLE`, which is intentionally less visually complete than fabricated output.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| V0.1 and V0.2 semantics drift | Keep independent version fixtures and run all v0.1 regressions for every v0.2 task. |
| New section wrappers duplicate source truth | Embed only report-owned projections needed for deterministic delivery and retain canonical/intelligence references. |
| `UNAVAILABLE` becomes a loophole for unsafe partial output | Require section-specific safety invariants, explicit presence/availability, and limitations. |
| Reference graph becomes fragile | One report namespace, deterministic IDs, uniqueness checks, and no orphan references. |
| Product Direction becomes an automatic decision | Restrict it to human-review artifacts and prohibit winner/buy/launch/go/profitability semantics. |
| Keyword scope expands into a second engine | Permit only an optional versioned external reference/adapter. |

## 8. Rejected shortcuts

The following shortcuts are explicitly prohibited:

- changing `market-report-v0.1` constants, models, schema, IDs, fixtures, or renderers;
- treating observed ASIN count as market size or True Competitor count;
- treating Provider result membership, same keyword, same family, price similarity, or attribute similarity as competitor membership;
- creating a universal parent/child aggregation formula;
- hard-coding reference-template bucket thresholds as global policy;
- copying all Canonical/Product Intelligence data into competitor rows without references;
- converting missing, null, unresolved, or query-empty evidence to zero;
- generating Product Directions, shortlist membership, executive conclusions, or rankings from renderer text;
- making Keyword Intelligence required for core V0.2;
- using runtime timestamps, paths, artifact hashes, retries, credits, or resume lineage as analytical semantic fingerprint material;
- beginning SP-039B implementation in TASK-SP-039A.

## 9. Decision outcome

The architecture and ownership boundaries are frozen for staged implementation. No runtime contract, schema, builder, adapter, validator, fixture, renderer, or business capability is implemented by this decision task.
