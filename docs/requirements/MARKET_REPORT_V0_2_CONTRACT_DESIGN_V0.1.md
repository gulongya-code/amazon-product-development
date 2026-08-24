# Market Report V0.2 Contract Design V0.1

Status: `BOUNDARY FROZEN — NON-RUNTIME DESIGN`

Task: `TASK-SP-039A`

Required baseline: `b01d18d03ab0af2fb3f448d268ff8322a42d23ec`

Companion ADR: `docs/decisions/MARKET_REPORT_V0_2_ARCHITECTURE_DECISION.md`

## 1. Purpose and normative language

This document freezes the minimum contract boundaries for staged `market-report-v0.2` implementation. It is not a JSON Schema, Python model, fixture, formula, classifier, renderer, or production integration.

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative design decisions. Conceptual field names can receive mechanical naming refinements during implementation only when ownership, meaning, required/data-gated behavior, identity, and references remain unchanged.

The design preserves:

- immutable `market-report-v0.1` behavior;
- Canonical Evidence First semantics;
- frozen Buyer Need, Competition, Opportunity, and Product Intelligence source semantics;
- deterministic content identity and ordering;
- `Missing != Zero`, `Estimate != Observed`, and `Query Empty != Market Zero`;
- one validated report as the business source for XLSX and Markdown.

## 2. Top-level V0.2 section map

`MarketReportSnapshotV0_2` is a new top-level graph with these owners:

```text
MarketReportSnapshotV0_2
├── metadata
├── category
├── sample
├── data_window
├── scope_context
├── market_size
├── true_competitor_set
├── competitor_structure
├── distributions
├── competitor_details
├── buyer_needs
├── buyer_need_links
├── product_directions
├── competitor_shortlist
├── opportunity_score
├── executive_summary
├── evidence_registry
├── sanitized_appendix
├── external_integrations
├── provenance
└── limitations
```

### 2.1 Required, optional, and data-gated behavior

| Section | Structural modality | Data behavior | Owner and boundary |
|---|---|---|---|
| `metadata` | Required | Must be valid | V0.2 version, report ID, semantic fingerprint, generated time, producer version. |
| `category` | Required | Must identify marketplace and category scope | V0.2 may adapt stable v0.1 category values without changing v0.1. |
| `sample` | Required | May be `PARTIAL` or `UNAVAILABLE` with limitations | Bounded cohort size, unique ASINs, Provider total/coverage when known. |
| `data_window` | Required | May be `UNAVAILABLE` | Observation period; retrieval time never substitutes for it. |
| `scope_context` | Required | May declare `MIXED_UNRESOLVED`; unsafe aggregates then remain unavailable | Analytical grain, family policy, cohort and duplicate-control boundary. |
| `market_size` | Required | Data-gated; may be `UNAVAILABLE` | Monthly sales/revenue metric envelopes and section limitations. |
| `true_competitor_set` | Required | Data-gated; may be `UNAVAILABLE` | Candidate dispositions and governed membership; no classifier in the contract. |
| `competitor_structure` | Required | Data-gated; may be `UNAVAILABLE` | Aggregate concentration/barrier metrics derived only from compatible governed inputs. |
| `distributions` | Required | Data-gated; registry may be empty only with section `UNAVAILABLE` and limitations | Versioned policy, denominator, buckets/dimensions, unknown share. |
| `competitor_details` | Required | Data-gated; may be `UNAVAILABLE` | Report-owned row projections referencing Product Intelligence/Canonical truth. |
| `buyer_needs` | Required | Data-gated; unavailable wrapper is allowed | Existing frozen Buyer Need projection and source version/fingerprint references. |
| `buyer_need_links` | Required | Data-gated; may be `UNAVAILABLE` independently of Buyer Need | Typed cross-links; never changes the source need. |
| `product_directions` | Required | Data-gated; may be `UNAVAILABLE` with empty items and limitations | Evidence-backed hypotheses for human validation. |
| `competitor_shortlist` | Required | Data-gated; may be `UNAVAILABLE` | Human-review list with governed reasons, not a winner ranking. |
| `opportunity_score` | Required | May retain `PENDING_DATA` and null | Existing frozen Opportunity projection; no scoring change. |
| `executive_summary` | Required | May be `PARTIAL` or `UNAVAILABLE`; claims can state missing evidence | Composition over validated sections only. |
| `evidence_registry` | Required | At least the references needed by represented claims/metrics | Report-local metric/context/reference index. |
| `sanitized_appendix` | Required | Data-gated; may be `UNAVAILABLE` | Content-addressed sanitized evidence/data references, not secrets or raw credentials. |
| `external_integrations` | Required registry | Attachments are optional | Empty registry means no external attachment. Keyword absence does not invalidate core. |
| `provenance` | Required and non-empty | Must resolve all report-local provenance references | Source module/version/record/evidence lineage. |
| `limitations` | Required collection | May be empty only when no report-level limitation exists | Report-wide limitations; section limitations remain local. |

A structurally required section is always present so ownership is unambiguous. `UNAVAILABLE` is a valid data state, not a schema omission. An owning section MAY fail the whole report only for a safety invariant such as invalid identity, duplicate membership, orphan reference, impossible denominator, or inconsistent declared grain. A missing Provider field normally makes its field/section unavailable instead of invalidating unrelated sections.

P1, P1-EXT, and P2 capability sections are not silently added to the P0 core. A future versioned extension can add them after their data and semantic gates.

## 3. Section relationship diagram

```text
category + sample + data_window
                │
                ▼
          scope_context ───────────────┐
                │                      │
       ┌────────┼─────────┐            │
       ▼        ▼         ▼            │
 market_size  true_competitor_set  buyer_needs (frozen projection)
       │        │         │            │
       │        ├─────────┼──────┐     │
       ▼        ▼         ▼      ▼     │
 distributions  competitor_details  buyer_need_links
       │        │                │
       └────────┴────────┐       ▼
                         ▼  product_directions
                competitor_structure │
                         │            ▼
                         └──── competitor_shortlist
                                      │
 opportunity_score ───────────────────┤
                                      ▼
                              executive_summary
                                      │
                                      ▼
                             Operator composition
                                      │
                                XLSX + Markdown

All report sections -> evidence_registry / provenance / sanitized_appendix
Optional external references -> external_integrations -> future cross-links only
```

No arrow points from a renderer back into a report section. No executive claim is an upstream input to market metrics or competitor membership.

## 4. Identity, fingerprint, and version rules

### 4.1 Versions

- Top-level version is exactly `market-report-v0.2`.
- Each ruleset/policy-bearing section records its own contract or policy version.
- A semantic change to grain, membership decision vocabulary, bucket/denominator behavior, cross-link meaning, or identity material requires a version change.
- `market-report-v0.1` constants and contracts remain separate and unchanged.

### 4.2 Deterministic identities

1. Canonical JSON uses UTF-8, sorted object keys, no NaN/infinity, and a stable scalar representation.
2. Every report-owned entity ID is derived from its semantic content after removing its own ID field.
3. `semantic_fingerprint` covers the complete validated analytical graph, contract/policy versions, governed observation windows/timestamps, values, dispositions, references, evidence IDs, and limitations.
4. `semantic_fingerprint` excludes report ID, itself, ordinary `generated_at`, output paths, runtime health, retry/resume facts, credits, artifact hashes, and collection insertion order.
5. `report_id` is derived from `report_version + semantic_fingerprint + generated_at`. `generated_at` is explicitly governed snapshot identity material but is not analytical semantic material.
6. Section IDs, metric IDs, claim IDs, direction IDs, shortlist IDs, and disposition IDs are content-derived under type-specific prefixes.
7. Equivalent uninterrupted and resumed analytical content has the same semantic fingerprint even if runtime health and artifact identity differ.

### 4.3 Ordering

| Collection | Stable order |
|---|---|
| Provenance, evidence, external references | Reference ID |
| Metrics | Metric name, subject/cohort reference, metric ID |
| True Competitor dispositions | Grain entity ID, disposition, disposition ID |
| Competitor details | Membership/grain entity ID, detail ID |
| Distributions | Distribution kind, dimension, policy ID, distribution ID |
| Distribution buckets | Policy ordinal, then bucket ID; ordinal is part of policy, not insertion order |
| Buyer Needs | Preserve governed v0.1 order when reused; otherwise need ID after source-defined semantic order is recorded |
| Buyer Need links | Need ID, link type, target ID, link ID |
| Product Directions | Direction ID; no implicit desirability ranking |
| Shortlist items | Review-priority enum, competitor identity, item ID; not a market ranking |
| Executive claims | Governed claim category ordinal, then claim ID |
| Limitations/reason/evidence IDs | Lexical unique order |

Duplicate identities are validation failures. Sorting must not silently deduplicate invalid duplicate records.

## 5. Availability and evidence semantics

V0.2 keeps three orthogonal concepts:

| Concept | Values | Meaning |
|---|---|---|
| Section/field availability | `AVAILABLE`, `PARTIAL`, `UNAVAILABLE` | Whether the report can safely publish the section or field. |
| Presence/result state | `PRESENT`, `EXPLICIT_NULL`, `MISSING`, `UNKNOWN`, `QUERY_RETURNED_EMPTY` | What the source/query established about presence. |
| Evidence semantics | `OBSERVED`, `PROVIDER_ESTIMATE`, `RESOLVED`, `DERIVED`, `UNKNOWN` | What kind of claim the value represents. |

Normative invariants:

- `PRESENT + value 0` is a real zero and remains distinct from every absence state.
- `QUERY_RETURNED_EMPTY` records the bounded query outcome and cannot become a market total of zero.
- `UNAVAILABLE` requires a null business value and at least one limitation. It may retain evidence/query references that prove absence or failure.
- `PARTIAL` may contain a value only with explicit completeness/coverage and limitations.
- `PROVIDER_ESTIMATE` must remain labeled and retain Provider provenance.
- `RESOLVED` and `DERIVED` require an explicit method/policy ID and version.
- `UNKNOWN` confidence is not converted to low confidence.
- A claim/metric cannot be upgraded merely because multiple Providers agree.

## 6. Reusable metric context envelope

Every new V0.2 business metric uses one conceptual `MetricContextEnvelope`:

| Field | Modality | Frozen meaning |
|---|---|---|
| `metric_id` | Required | Content-derived report identity. |
| `metric_name` | Required | Versioned semantic name, not a display label. |
| `value_type` | Required | Declared scalar/range/share/count/money/distribution semantic. |
| `availability` | Required | `AVAILABLE`, `PARTIAL`, or `UNAVAILABLE`. |
| `presence_status` | Required | Source/result presence semantics. |
| `evidence_semantics` | Required | Observed/estimate/resolved/derived/unknown. |
| `value` | Required nullable | Canonical JSON value; zero is allowed only as an explicit value. |
| `unit` | Required nullable | Versioned unit semantic when applicable. |
| `currency` | Required nullable | Marketplace-compatible currency for money; currency is not guessed. |
| `period_reference_id` | Required nullable | Resolves to report data window or a metric-specific governed period. |
| `marketplace` | Required | Must agree with report scope. |
| `subject_reference_ids` | Required collection | Exact product/category/brand/seller/market subjects when applicable. |
| `cohort_reference_id` | Required nullable | Exact input/evaluated cohort. |
| `denominator_reference_id` | Required nullable | Exact denominator for shares/rates/aggregates. |
| `product_grain_reference_id` | Required | Resolves to `scope_context`. |
| `method_policy_id/version` | Required nullable pair | Mandatory for resolved, derived, or aggregated metrics. |
| `sample_context` | Required | Total, included, excluded, unknown counts when applicable. |
| `coverage/completeness` | Required nullable | Governed coverage and completeness state, never inferred from missing totals. |
| `confidence` | Optional/data-gated | Only with method/scale/version when governed. |
| `evidence_ids` | Required collection | Exact source/calculation evidence; may be empty only for unsupported/missing input with provenance explanation. |
| `provenance_reference_ids` | Required non-empty | Resolves to report provenance. |
| `limitations` | Required collection | Non-empty for partial/unavailable values. |

The envelope authorizes no formula, threshold, aggregation, estimate window, currency conversion, or Provider preference. A metric producer must already own those semantics under a governed policy.

## 7. Scope context and product grain

### 7.1 Conceptual shape

`ScopeContext` owns:

- `scope_context_id`;
- marketplace and category reference;
- entry Demand Cluster/keyword references when governed and available;
- analysis cohort reference;
- `product_grain`;
- aggregation policy ID/version;
- family relationship/topology evidence references;
- duplicate-control status and policy reference;
- completeness status;
- included/excluded/unresolved grain-entity counts;
- provenance and limitations.

`product_grain` supports exactly these V0.2 boundary states:

| Value | Meaning |
|---|---|
| `CHILD_ASIN` | Each governed child ASIN is one analytical entity. |
| `PARENT_ASIN` | Each governed parent identity is one entity under an explicit policy. |
| `PRODUCT_FAMILY` | Each validated family topology is one entity under an explicit policy. |
| `MIXED_UNRESOLVED` | Inputs cannot be safely normalized to one grain. |

`MIXED_UNRESOLVED` is not an aggregation mode. It prohibits market totals, shares, concentration, and rankings that could double count. Row-level evidence may remain visible with limitations.

### 7.2 Grain invariants

- Parent/family aggregation requires a non-null policy ID/version and governed relationship evidence.
- Child-ASIN analysis records its identity/duplicate-control policy even when no family aggregation occurs.
- No universal parent/child sales-allocation or deduplication formula is frozen here.
- A family entity records all member ProductIdentity references and one stable grain entity ID.
- One Canonical ProductIdentity cannot appear in two included grain entities for the same scope.
- Invalid/multiple-parent/cyclic/unresolved topology fails the affected aggregation closed and becomes `MIXED_UNRESOLVED` or an explicit exclusion; it is not repaired by title, brand, or row order.

## 8. True Competitor Set boundary

### 8.1 Ownership and shape

`TrueCompetitorSetSection` owns:

- section status, contract version, set ID;
- `scope_context_id` and candidate cohort reference;
- membership policy/authority ID and version when available;
- candidate-universe completeness;
- one disposition for every evaluated grain entity;
- included, excluded, and review-required counts;
- downstream-compatible cohort/denominator reference;
- evidence/provenance and limitations.

Each disposition owns:

- disposition ID;
- grain entity/product identity references;
- exactly one decision: `INCLUDED`, `EXCLUDED`, or `REVIEW_REQUIRED`;
- versioned reason codes;
- authority/policy reference when the decision is governed;
- evidence IDs and provenance references;
- field/disposition limitations.

### 8.2 Invariants

- Candidate discovery is not membership authority.
- Provider result membership, same keyword, same category, same brand, price similarity, same variation family, or attribute similarity cannot independently produce `INCLUDED`.
- `REVIEW_REQUIRED` is neither included nor excluded and does not enter complete-cohort aggregates.
- A valid empty set requires a complete governed evaluation in which every candidate has a final `EXCLUDED` disposition. Missing evidence or all-review-required is not an empty set.
- Every candidate has one disposition at the declared grain; duplicate grain entities fail validation.
- Aggregate concentration/barrier metrics reference the exact included cohort and scope context. Partial cohorts remain labeled partial.
- The existing Comparable Product Set fail-closed discipline is reusable, but its target-to-peer semantics are not silently treated as the market-level True Competitor contract.

No classifier, reason vocabulary implementation, membership formula, AI authority, or manual workflow is selected by SP-039A.

## 9. Competitor structure boundary

`CompetitorStructureSection` is downstream of `true_competitor_set` and owns only aggregate structure metrics:

- competitor count;
- product/brand/seller concentration when supported;
- head entity references;
- core competitor sales/revenue share when supported;
- review/rating barriers;
- entry-difficulty and surface-versus-true-competition claims when governed;
- section status, evidence/provenance, and limitations.

Every numeric output is a `MetricContextEnvelope`. An existing v0.1 Competition metric can be adapted only when its cohort, denominator, grain, method, and evidence are compatible. Untyped or scope-ambiguous values remain partial/unavailable. This boundary does not authorize new concentration or barrier formulas.

## 10. Competitor detail boundary

### 10.1 Embed versus reference

The report embeds only the stable projection needed for deterministic report rendering:

- report row identity and True Competitor disposition reference;
- Canonical ProductIdentity projection and declared grain entity reference;
- display-ready resolved field value or null;
- field availability, presence, evidence semantics, evidence IDs, provenance refs, and limitations;
- report-safe URL/image reference when supported.

The report references, rather than duplicates:

- Product Intelligence snapshot/profile IDs;
- Canonical observation/resolution IDs;
- raw evidence content;
- transformation runs and Provider payloads;
- full attribute candidate inventories not selected for display.

### 10.2 Row groups

`CompetitorDetailRecord` can represent these groups without requiring every field to be available:

1. identity/catalog: ASIN, parent/family, brand, title, category path, URL, image;
2. product facts: type, material, structure/capacity, mounting, color, pack, dimensions/weight, package facts;
3. market/review metrics: BSR/context, sales, revenue, growth, variants, price/promotion, rating/reviews/Q&A/quality;
4. fulfillment/economics: fulfillment, FBA fee, shipping, size tier, economics status;
5. seller/marketing: seller identity/location/count, badges, A+, video, sponsored/deal signals.

Each fact uses an evidence-aware field projection; each numeric business metric uses `MetricContextEnvelope`. Missing fields keep the row present with null value and `UNAVAILABLE` plus the source absence state. No value defaults to zero, false, or an empty string.

One row cannot become source truth for upstream Product Intelligence. Corrections occur upstream and create a new report projection/fingerprint.

## 11. Distribution boundary

### 11.1 Policy and denominator

Each `DistributionSectionItem` owns:

- distribution ID, kind, and optional attribute dimension;
- section availability;
- bucket/dimension policy ID and version;
- exact cohort and denominator references;
- product grain reference;
- declared metric set;
- buckets/value segments;
- explicit unknown/unclassified segment;
- evidence/provenance and limitations.

A policy owns bucket definitions, inclusivity/exclusivity, unit/currency compatibility, unknown handling, and stable ordinal. Reference-template thresholds are not global constants and do not appear in the top-level schema.

### 11.2 Bucket/segment outputs

Each bucket or dimension value can carry:

- policy bucket/value ID and ordinal;
- display label and canonical bounds/value;
- product count and product share metric envelopes;
- optional sales, sales share, revenue, revenue share, average price, and median price metric envelopes when included in the declared metric set;
- member grain entity references when policy permits auditable membership;
- unknown/unclassified status, evidence, and limitations.

If sales/revenue/price evidence is incompatible with the bucket cohort/grain/window/currency, the declared metric envelope is `UNAVAILABLE`; it is not omitted or calculated from a different cohort. Product share and sales share always reference explicit denominators.

The generic model supports price, rating, review count, listing age, FBA fee, product attributes, and future seller geography without freezing their data availability or thresholds.

## 12. Buyer Need projection and cross-link boundary

### 12.1 Frozen projection

`buyer_needs` preserves the existing source record ID, intent ruleset version, taxonomy version, validation status/fingerprint, need IDs/labels, governed share basis, confidence, evidence, provenance, and limitations. V0.2 adapters MUST NOT change extraction, taxonomy, intent rules, cluster membership, scoring, share semantics, or frozen fingerprints.

When a v0.1 `BuyerNeedReportSection` is available, a V0.2 adapter may consume it and place one equivalent projection under the V0.2 owner. It must not reconstruct a different need from display text.

### 12.2 Cross-links

`BuyerNeedLinkSection` is separate so links cannot mutate Buyer Need truth. Each link records:

- link ID and link type;
- source `need_id`;
- evidence subject/review/ASIN references;
- competitor disposition/detail references and governed coverage/satisfaction state when available;
- relevant attribute distribution/value references;
- Product Direction references;
- optional future Demand–Supply Gap external reference;
- evidence/provenance, confidence method when governed, and limitations.

No competitor satisfaction, unmet need, or gap is inferred from a single review, keyword occurrence, or absent field. An unavailable link section does not invalidate the Buyer Need projection.

## 13. Product Direction boundary

`ProductDirectionSection` is a data-gated collection of **hypotheses for human validation**. Each direction can represent:

- direction ID and proposal semantic `HYPOTHESIS_FOR_VALIDATION`;
- proposed product type/configuration/attribute values clearly separated from observed facts;
- Buyer Need link references;
- market-size, distribution, competitor structure/detail evidence references;
- target price-band metric reference when available;
- direct competitor references;
- entry rationale composed from validated evidence;
- validation items and risk references;
- governed confidence method/value when available;
- evidence/provenance and limitations.

Product Direction does not contain or imply `WINNER`, `BUY`, `LAUNCH`, `GO`, `PROFITABLE`, automatic procurement, guaranteed success, or an unsupported numeric rank. A section with insufficient evidence is present as `UNAVAILABLE` with no direction items and explicit limitations.

## 14. Competitor Shortlist boundary

`CompetitorShortlistSection` is a human-review collection downstream of True Competitor Set and competitor details. Each item records:

- shortlist item ID;
- included/review-required competitor disposition and detail references;
- versioned selection reason codes and policy reference;
- related Product Direction references;
- representative metric/evidence references;
- `review_priority`: `HIGH`, `MEDIUM`, `LOW`, or `UNSPECIFIED`;
- evidence/provenance and limitations.

Review priority controls operator review order only. It is not product desirability, market rank, launch priority, or winner status. A Provider/source rank may be displayed only as a referenced metric with its context; it cannot become shortlist authority by itself.

## 15. Executive composition boundary

`ExecutiveSummarySection` owns validated executive claims. Each `ExecutiveClaim` records:

- claim ID and governed claim category;
- text and/or typed value;
- availability;
- source section IDs and metric/entity references;
- evidence IDs and provenance references;
- governed confidence when available;
- limitations.

Rules:

1. Every factual claim resolves to at least one validated section/metric/entity reference.
2. A claim cannot upgrade source availability or evidence semantics.
3. If a required source is unavailable, the claim is unavailable/partial and names the gap; it cannot substitute generic optimism or zero.
4. Executive Summary does not calculate metrics or classify competitors.
5. Operator Workflow is downstream. It may reference executive claim IDs and record an action relationship in the Operator snapshot; the Market Report never references a later Operator snapshot, avoiding a cycle.
6. Executive claims and the detailed section values must be identical across XLSX and Markdown because both consume the same validated report.

## 16. Evidence registry, provenance, and sanitized appendix

### 16.1 Reference strategy

References are either:

- **report-local:** resolve to a unique ID in the same V0.2 payload; or
- **external provenance namespace:** record namespace, target ID, source version, optional content fingerprint, and a report provenance reference.

Allowed external namespaces include governed Canonical, Product Intelligence, Buyer Need, Competition, Opportunity, policy, and sanitized evidence stores. Filesystem output paths and temporary paths are not business references.

No orphan local reference, absent provenance reference, duplicate membership, or dangling metric/section link is valid. A reference cycle is invalid except for explicitly modeled bidirectional indexes whose identity excludes the reverse cache; the initial implementation SHOULD use one-way ownership to avoid cycles.

### 16.2 Sanitized appendix

The appendix contains content-addressed, sanitized references or report-owned projections. It never contains credentials, authorization headers, account identifiers, unsanitized Provider payloads, or mutable runtime paths. A raw evidence store remains outside the report; the appendix references its sanitized/auditable representation with provenance.

## 17. External Keyword Intelligence boundary

`external_integrations` is a required registry whose attachments are optional. A future Keyword attachment contains only:

- integration kind `KEYWORD_INTELLIGENCE`;
- attachment status;
- source project and source contract version;
- snapshot/reference ID and optional content fingerprint;
- scope/window compatibility status;
- provenance reference and limitations.

The absence of an attachment means `NOT_ATTACHED`, not an empty keyword market and not a report failure. V0.2 core must generate without Keyword Intelligence. This design does not freeze or implement the external project's collection, cleaning, normalization, clustering, intent, trend, competition, seasonality, or opportunity-score schema/algorithms.

Future Keyword-to-ASIN/Buyer Need/Supply/Gap links require a jointly versioned adapter and cannot be inferred from an attachment label.

## 18. Delivery boundary

The future delivery contract is:

```text
strict V0.2 deserialize/validation
  -> one MarketReportSnapshotV0_2
  -> Operator composition with report references
  -> XLSX renderer + Markdown renderer
```

Delivery MAY:

- choose display labels, widths, sheets/sections, formatting, and safe unavailable text;
- project report-owned fields and executive claims;
- add runtime health from the Operator snapshot, visually separated from intelligence.

Delivery MUST NOT:

- produce a business metric absent from the report;
- run a market/competitor/direction/shortlist formula;
- turn null/partial/unavailable/query-empty into zero;
- use Excel formulas/helper sheets as source truth;
- allow XLSX and Markdown to consume different analytical snapshots.

No renderer is implemented in SP-039A or handed to SP-039B.

## 19. SP-039 P0 ownership map

This table covers MR-001 through MR-060. Non-P0 rows are shown to make their exclusion or extension boundary explicit. `Primary V0.2 owner` is unambiguous even when another section later consumes the result.

| ID | Audit priority | Primary V0.2 owner | Frozen disposition |
|---|---|---|---|
| MR-001 | P0 | `executive_summary` | Compose action-relevant opportunity/risk/next-check claims from validated sections. |
| MR-002 | P0 | `market_size` | Monthly capacity/revenue envelopes; executive only references them. |
| MR-003 | P0 | `distributions` | Versioned price-band/AOV-compatible distribution context. |
| MR-004 | P0 | `competitor_structure` | Maturity/barrier/difficulty metrics only when governed; executive consumes. |
| MR-005 | P0 | `distributions` | Product-form count/share and compatible sales-share metrics. |
| MR-006 | P0 | `buyer_needs` | Frozen need projection; richer relationships belong to links. |
| MR-007 | P0 | `competitor_details` | Field-aware fulfillment/package/fee/transport projections. |
| MR-008 | P1 | Future seller-geography extension | Not a P0 prerequisite; future data-gated distribution. |
| MR-009 | P0 | `executive_summary` | Claim evidence/confidence/limitations, backed by evidence registry. |
| MR-010 | P0 | `category` | Marketplace/category/scope identity. |
| MR-011 | P0 | `scope_context` | Typed hierarchy and entry Demand reference when governed. |
| MR-012 | P0 | `data_window` | Governed observation period and availability. |
| MR-013 | P0 | `sample` | Sample/cohort coverage and limitations. |
| MR-014 | P0 | `scope_context` | Product grain, family policy, duplicate control, completeness. |
| MR-015 | P0 | `market_size` | Monthly sales metric envelope. |
| MR-016 | P0 | `market_size` | Monthly revenue metric envelope. |
| MR-017 | P1 | Future trend extension | Not required for V0.2 P0 validity. |
| MR-018 | P1 | Future trend/maturity extension | Not required for V0.2 P0 validity. |
| MR-019 | P2 | Deferred forecast extension | Not in V0.2 P0. |
| MR-020 | P0 | `true_competitor_set` | Auditable candidate dispositions at declared grain. |
| MR-021 | P0 | `competitor_structure` | Concentration metrics over exact included cohort/denominator. |
| MR-022 | P0 | `competitor_structure` | Head entity references; row data resolves through details. |
| MR-023 | P0 | `competitor_structure` | Core count/share metrics over True Competitor cohort. |
| MR-024 | P0 | `competitor_structure` | New/old and review/rating/entry barrier metric envelopes. |
| MR-025 | P0 | `competitor_structure` | Governed surface-versus-true comparison claim. |
| MR-026 | P0 | `distributions` | Versioned product-attribute dimension registry/policies. |
| MR-027 | P0 | `distributions` | Count/share/unknown/evidence; may adapt v0.1 Category Map projection. |
| MR-028 | P0 | `distributions` | Compatible sales/revenue/price metrics per attribute segment. |
| MR-029 | P0 | `distributions` | Versioned price/review/rating buckets, not summary-only values. |
| MR-030 | P0 | `distributions` | Listing-age/FBA-fee/review-rate buckets, data-gated. |
| MR-031 | P1 | Future seller-geography distribution | Not a P0 prerequisite. |
| MR-032 | P0 | `distributions` | Product type/material/mounting/structure/pack dimensions. |
| MR-033 | P0 | `distributions` | Policy ID/version, denominator, unknown segment, declared metric set. |
| MR-034 | P0 | `competitor_details` | Identity/catalog report projections. |
| MR-035 | P0 | `competitor_details` | Product Intelligence field projections. |
| MR-036 | P0 | `competitor_details` | Per-competitor market/review metric envelopes. |
| MR-037 | P0 | `competitor_details` | Fulfillment/economics/seller/marketing field projections. |
| MR-038 | P1 | Future top-competitor delivery view | Projection over details; not P0 schema truth. |
| MR-039 | P0 | `buyer_needs` | Preserve V0.1/V0.3 governed projection and source fingerprints. |
| MR-040 | P0 | `buyer_need_links` | Need role and evidence-subject/review/ASIN references without mutation. |
| MR-041 | P0 | `buyer_need_links` | Competitor/attribute/direction/gap cross-links. |
| MR-042 | P0 | `product_directions` | Evidence-backed human-validation hypotheses. |
| MR-043 | P1 | Future Sample Plan section | Data-gated P1, not V0.2 P0 validity. |
| MR-044 | P0 | `competitor_shortlist` | Governed human-review items and reasons. |
| MR-045 | P1 | Future Unit Economics section | Not a P0 prerequisite. |
| MR-046 | P2 | Deferred advertising economics | Not in V0.2 P0. |
| MR-047 | P1 | Future risk section | Conservative screening only after its data gate. |
| MR-048 | P1 | Future claim/safety section | Future evidence classification; no title-to-truth inference. |
| MR-049 | P1-EXT | `external_integrations` | Optional Keyword snapshot reference only. |
| MR-050 | P1-EXT | Future Keyword report extension | Core delivery remains valid without it. |
| MR-051 | P1-EXT | Future cross-project link adapter | No local clustering/mapping engine. |
| MR-052 | P1-EXT | Future Demand–Supply Gap extension | Requires jointly governed inputs. |
| MR-053 | P1-EXT | External Keyword Intelligence | Ranking policy remains external. |
| MR-054 | P0 | `evidence_registry` | Availability, presence, and evidence semantics remain orthogonal. |
| MR-055 | P0 | `evidence_registry` | Metric context envelope owns scope/grain/period/cohort/method/coverage. |
| MR-056 | P0 | `executive_summary` | Claims reference metric/section/entity evidence graph. |
| MR-057 | P0 | `metadata` | Strict version, deterministic identity, validation boundary. |
| MR-058 | P0 | Delivery boundary | Same validated V0.2 report feeds both outputs. |
| MR-059 | P0 | `executive_summary` | One claim set is projected consistently by both renderers. |
| MR-060 | P0 | `sanitized_appendix` | Sanitized evidence/data references with provenance. |

## 20. Six required acceptance scenarios

### Scenario 1 — Full P0 data available

- `scope_context` declares one governed grain and complete duplicate control.
- `market_size` contains available monthly sales/revenue envelopes with compatible period/cohort/grain.
- every candidate in `true_competitor_set` has one governed disposition;
- distributions reference exact policies and denominators;
- competitor details resolve each field to report/upstream evidence;
- Buyer Need links, Product Directions, and Shortlist resolve without orphans;
- executive claims reference those validated sections.

Conceptual outcome: core sections are available/partial according to their own evidence, semantic fingerprint is deterministic, and delivery can represent the full P0 graph without calculation.

### Scenario 2 — Monthly sales/revenue unavailable

- `market_size` remains structurally present;
- monthly-sales and monthly-revenue envelopes have `availability=UNAVAILABLE`, null value, source presence state, provenance, and limitations;
- value zero is prohibited;
- other independently valid sections remain valid;
- executive claim states capacity is unavailable and references the two metric IDs.

Conceptual outcome: report validates; no whole-report failure and no fabricated capacity.

### Scenario 3 — Parent/child relationship unresolved

- `scope_context.product_grain=MIXED_UNRESOLVED`;
- topology/duplicate-control limitations identify the blocker;
- market-size totals, concentration, shares, and rank-like aggregates that can double count are unavailable;
- row-level evidence may remain in competitor details with its field/grain state;
- True Competitor evaluation cannot claim a complete included cohort at a mixed grain.

Conceptual outcome: report validates as incomplete evidence, avoids double counting, and does not invent a family formula.

### Scenario 4 — Competitor detail field missing

- competitor row identity and membership disposition remain present;
- the missing field projection has null value, `UNAVAILABLE`, and `MISSING`/`EXPLICIT_NULL`/`UNKNOWN` as sourced;
- evidence/provenance and limitation resolve;
- no default zero, false, blank string, or row removal occurs.

Conceptual outcome: auditable row continuity without fabricated data.

### Scenario 5 — Keyword project absent

- `external_integrations` contains no Keyword attachment or records `NOT_ATTACHED` in its registry semantics;
- core sections do not reference missing keyword IDs;
- limitations state which keyword-dependent cross-analysis is unavailable when relevant;
- no fixture fallback or local keyword engine runs.

Conceptual outcome: V0.2 core validates and delivery proceeds.

### Scenario 6 — Buyer Need available, Product Direction unavailable

- frozen Buyer Need projection remains available with unchanged source ruleset/taxonomy/fingerprint references;
- Buyer Need links may be partial/unavailable independently;
- `product_directions` is structurally present, `UNAVAILABLE`, has no items, and records missing decision-support inputs;
- executive summary may report Buyer Need evidence but cannot claim a direction.

Conceptual outcome: Buyer Need validity is independent of downstream direction derivation.

## 21. Backward compatibility and loader rules

1. Version detection occurs before section decoding.
2. `market-report-v0.1` payloads use only the existing v0.1 validator and model.
3. `market-report-v0.2` payloads use only the future v0.2 validator.
4. Unknown versions fail with a typed version error.
5. A future explicit v0.1-to-v0.2 adapter may populate unavailable V0.2 sections and retain the v0.1 source report ID; it cannot claim full V0.2 coverage.
6. A future v0.2-to-v0.1 projection is lossy and must require an explicit caller choice; it cannot be the default writer.
7. V0.1 JSON, fingerprints, examples, tests, and renderers remain unchanged.

## 22. Test and fixture acceptance plan

Future implementation tasks must add offline tests for:

- exact version dispatch and cross-version rejection;
- strict required/unknown-field validation;
- deterministic semantic fingerprint under input permutations;
- separate semantic fingerprint and generated snapshot identity;
- stable ordering of every collection;
- duplicate grain entity/membership failure;
- orphan internal/external provenance reference failure;
- metric zero versus missing/null/query-empty behavior;
- unavailable/partial section limitation invariants;
- product-grain mixed/unresolved aggregate blocking;
- valid empty True Competitor Set versus missing/unresolved distinction;
- field-level unavailable competitor details;
- frozen Buyer Need projection/fingerprint preservation;
- forbidden Product Direction/Shortlist semantics;
- Executive Claim source-reference and availability non-upgrade rules;
- Keyword-not-attached core validity;
- all six scenarios in §20;
- v0.1 schema/example/fingerprint and delivery regressions;
- eventual XLSX/Markdown parity from one validated V0.2 snapshot.

Version-specific future fixtures should be stored under `tests/fixtures/market_report_v0_2/` and named by scenario. They must not replace or be accepted as v0.1 fixtures. No fixture is created by SP-039A.

## 23. SP-039B exact bounded handoff

SP-039B is limited to the foundational contract slice below.

### 23.1 Expected new modules/files

```text
src/amazon_product_intelligence/market_report/v0_2/__init__.py
src/amazon_product_intelligence/market_report/v0_2/version.py
src/amazon_product_intelligence/market_report/v0_2/models/__init__.py
src/amazon_product_intelligence/market_report/v0_2/models/common.py
src/amazon_product_intelligence/market_report/v0_2/models/metric_context.py
src/amazon_product_intelligence/market_report/v0_2/models/scope_context.py
src/amazon_product_intelligence/market_report/v0_2/models/market_size.py
src/amazon_product_intelligence/market_report/v0_2/models/true_competitor_set.py
src/amazon_product_intelligence/market_report/v0_2/models/competitor_structure.py
src/amazon_product_intelligence/market_report/v0_2/adapters/__init__.py
src/amazon_product_intelligence/market_report/v0_2/adapters/scope_context_adapter.py
src/amazon_product_intelligence/market_report/v0_2/adapters/market_size_adapter.py
src/amazon_product_intelligence/market_report/v0_2/adapters/true_competitor_adapter.py
src/amazon_product_intelligence/market_report/v0_2/adapters/competitor_structure_adapter.py
tests/test_market_report_v0_2_contract_foundation.py
tests/test_market_report_v0_2_sp039b.py
tests/fixtures/market_report_v0_2/sp039b_scope_child_asin.json
tests/fixtures/market_report_v0_2/sp039b_market_size_unavailable.json
tests/fixtures/market_report_v0_2/sp039b_true_competitor_review_required.json
```

The bounded initial slice is expected to modify **no existing v0.1, Pipeline, delivery, renderer, or frozen Intelligence source file**. Version-disambiguated root exports and complete top-level `MarketReportSnapshotV0_2` composition wait until all required P0 section contracts exist or a separately accepted integration task explicitly authorizes them.

### 23.2 SP-039B implementation behavior

SP-039B may:

- implement the availability/reference primitives and metric context envelope;
- represent `CHILD_ASIN`, governed parent/family, and `MIXED_UNRESOLVED` grain states;
- represent unavailable monthly sales/revenue without zero;
- implement auditable True Competitor candidate dispositions and reference validation;
- adapt an already governed competitor membership input;
- project existing compatible concentration/barrier evidence into metric envelopes.

SP-039B must not:

- invent monthly sales/revenue calculations or Provider estimate windows;
- select a True Competitor authority or implement classification logic;
- use Comparable Product Set, Provider results, keywords, family membership, attributes, or price as automatic True Competitor membership;
- implement distributions, competitor detail rows, Buyer Need cross-links, Product Direction, Shortlist, executive summary, sanitized appendix, external Keyword integration, renderer, Pipeline switch, or XLSX/Markdown output;
- modify frozen Buyer Need, Competition, Opportunity, Product Intelligence, market-report-v0.1, Production Pipeline, or Batch semantics.

If existing concentration/barrier evidence lacks compatible scope, denominator, grain, method, or completeness, the adapter must emit unavailable/partial metric context rather than reconstruct those inputs.

## 24. Explicit non-goals of SP-039A

This design task does not:

- create Python source, runtime schema, validators, fixtures, renderers, or Pipeline integration;
- implement any SP-039B module listed above;
- calculate monthly sales/revenue, trends, concentration, barriers, distributions, economics, forecasts, or ranks;
- classify True Competitors;
- extract competitor detail data;
- change Buyer Need, Competition, Opportunity, Product Intelligence, or scoring semantics/fingerprints;
- generate Product Directions or Competitor Shortlists;
- define automatic selection, purchase, launch, procurement, profitability, or winner decisions;
- define Keyword Intelligence internal schema or algorithms;
- call a Provider or spend credits.

## 25. Freeze statement

The top-level ownership graph, version/compatibility decision, required/data-gated/optional behavior, product-grain states, metric context envelope, True Competitor dispositions, competitor detail reference strategy, distribution policy/denominator boundary, Buyer Need cross-link separation, Product Direction/Shortlist human-review semantics, executive composition constraint, external Keyword boundary, delivery direction, deterministic identity/order/reference rules, six scenarios, and SP-039B bounded handoff are frozen by TASK-SP-039A.

Implementation remains deferred to separately accepted tasks beginning with SP-039B.
