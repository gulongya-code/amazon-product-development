# Sorftime DTO-to-Canonical Mapper V0.1

Status: `SP-040C COMPLETE — OFFLINE DTO-FIRST MAPPING`

This document records the mapping boundary delivered by GitHub Issue #39 from
required baseline `720165bb37bf736f20064f7150aef73466708978`. The implementation
maps only strict SP-040B DTOs into the existing Canonical evidence model. It does
not implement SP-040D transport, credentials, provider selection, pipeline
wiring, retries, checkpoints, Intelligence, Renderer, or report behavior.

## Architecture

```text
SP-040B typed request + successful typed response DTO
        -> SorftimeDtoMapperV0_1 explicit operation method
        -> existing _AdapterSession / MappingSpecification
        -> existing CanonicalEvidenceBundle observations
        -> existing provider-neutral normalization / Data Cleaning boundary
```

The mapper has no generic `adapt(payload, context)` method. Its only successful
entry points require exact typed pairs:

- `SorftimeProductRequest` + `SorftimeProductRequestResponse`
- `SorftimeProductVariationsRequest` +
  `SorftimeProductVariationsResponse`
- `SorftimeAsinRequestKeywordRequest` +
  `SorftimeAsinRequestKeywordResponse`

Raw dictionaries, malformed data, nonzero provider codes, HTTP failures, and
request/response mismatches must fail at or before the DTO boundary. The older
raw `SorftimeAdapterV0_1` remains unchanged and isolated; it is not called by
this DTO-first mapper and is not semantic authority for SP-040C.

## Reuse audit

The mapper reuses:

- `AdaptationContext`, `AdaptationResult`, `_AdapterSession`, and
  `MappingSpecification`;
- existing Product/Keyword identity helpers and deterministic ID machinery;
- `CanonicalEvidenceBundle`, `ProductFactObservation`, `MetricObservation`,
  `KeywordMetricObservation`, and `ProductKeywordRelationshipObservation`;
- existing presence, semantic, evidence, period, channel, scope, direction,
  result, query-outcome, quality-issue, and provenance contracts;
- existing normalization and Data Cleaning input boundary;
- XiYou adapter structure only for provider-neutral software patterns.

No Canonical field, type, schema version, evidence ontology, normalization rule,
or downstream special case was added.

## Versioned mapping specifications

Each operation has a separate specification with provider `sorftime`, local DTO
schema `sorftime-dto-v0.1`, and mapper ruleset
`sorftime-dto-mapper-v0.1`:

| Operation | Typed payload kind | Mapping version |
| --- | --- | --- |
| `ProductRequest` | `sorftime_product_request_dto` | `sorftime_product_request_dto_mapping_v0_1` |
| `ProductVariations` | `sorftime_product_variations_dto` | `sorftime_product_variations_dto_mapping_v0_1` |
| `ASINRequestKeyword` | `sorftime_asin_request_keyword_dto` | `sorftime_asin_request_keyword_dto_mapping_v0_1` |

Caller context must exactly agree on provider, operation, payload kind, US/USD
marketplace context, and a deterministic sanitized request identity generated
from the typed request and `domain=1`. Any extra field, including a secret-like
field, is rejected.

## Sanitized evidence projection

The `RawEvidenceRecord` fingerprints a deterministic typed DTO projection, not
an arbitrary or full HTTP response. It retains the local DTO version, operation,
success code, and only the accepted `Data` slice. Quota counters, provider
message, headers, Authorization, Account-SK, sessions, endpoints, and mutable
file paths are excluded.

Input rows and collections are sorted by stable semantic keys before projection
and emission. Request, raw-evidence, transformation, observation, relationship,
query-execution, and quality-issue identities are deterministic under input
permutation.

## ProductRequest mapping

The mapper emits:

- requested ASIN identity under US marketplace context;
- a `parent_product_relationship` fact only for a valid distinct ParentAsin;
- no edge for self-parent;
- a bounded variation identity collection with returned cardinality and
  `complete_family=false`;
- child-scoped variation ASIN identity evidence;
- Color/Size facts only on the exact child ASIN named by each Attribute row.

The variation count remains response-cardinality evidence, not a family or
market denominator. Trend=2 null fields emit no trend observations, empty
series, current-history assertions, or zeros. No title, price, rating, review,
category, sales, BSR, brand, description, or historical value is mapped.

## ProductVariations mapping

Each validated row emits child-scoped ASIN, Color, and Size evidence. ItemIndex,
request page, returned count, and ItemTotal remain source/pagination context;
they are not business rank or complete-family proof. The mapper creates no
parent edge.

For `SalesAmount=-1`, an existing Canonical metric envelope records
`PresenceStatus.UNKNOWN` with no raw or normalized numeric value. It never emits
`-1` or zero. A positive DTO-valid sales value also remains numerically
unavailable in SP-040C because its period and method are unproven. Its source row
is auditable, while the Canonical metric stays UNKNOWN with period UNKNOWN and a
deterministic limitation diagnostic.

A valid empty page is recorded as bounded empty response evidence, not proof of
an empty product family.

## ASINRequestKeyword mapping

For each validated row the mapper emits:

- bounded Product-to-Keyword candidate-membership relationship;
- organic rank relationship limited to the first-three-pages scope;
- traffic-share relationship with explicit provider percent unit;
- 30-day search-volume provider estimate with method `UNKNOWN` and partial
  semantic status;
- CPC provider estimate with original USD local-minor-unit integer retained and
  an auditable exponent-2 conversion into existing USD major-unit semantics.

The organic local observation text remains rank context only. Canonical
`observed_at`, timezone, period endpoints, and UTC/local offset remain unknown.
No sponsored relationship is emitted. Caller locale is recorded as caller
context, not as a provider-declared response fact.

Pagination provenance explicitly retains request page/size, returned count,
provider total unavailable, later pages unavailable, 30-day/first-three-pages
scope, and `complete_keyword_universe=false`. A 20-row page is never upgraded to
a complete keyword universe. An empty successful page produces an
`EXPLICIT_EMPTY` directional query outcome and no zero-demand observation.

## XiYou parity and divergence

Tests prove only generic overlap:

- the same marketplace/ASIN resolves to the same Canonical Product identity;
- the same normalized keyword and ASIN can use the same generic
  Product-to-Keyword membership direction/type;
- provider provenance, raw evidence, transformation, observation, and
  relationship identities remain distinct;
- Sorftime rolling-30-day bounded evidence is not forced equal to XiYou period,
  rank, traffic, missingness, or provider semantics.

No provider-value equality or field-name equivalence is asserted.

## Missingness and completeness

The mapper preserves:

- explicit-null variation collection as `EXPLICIT_NULL`;
- valid empty pages as response/query outcomes, not numeric zeros;
- `SalesAmount=-1` as UNKNOWN;
- positive sales as unavailable without period/method proof;
- bounded collection/page as incomplete/unknown completeness;
- parent identity as a bounded provider fact, not complete family topology;
- malformed/business/HTTP failure as upstream failure, never empty evidence.

## Data Cleaning compatibility

Representative product identity, parent identity, Product-to-Keyword
membership, search volume, CPC, and unknown variation-sales observations pass
through the existing `NormalizationInput` and
`CanonicalNormalizationPipeline` without a Sorftime-specific downstream branch.
The USD CPC conversion remains `0.51` for a source value of 51 minor units, and
unknown sales remains unknown after normalization.

## Deterministic scenario coverage

The focused suite covers all 24 Issue #39 scenarios plus strict context,
canonical keyword-collision, typed-projection, secret-like input, and legacy
public-boundary preservation checks:

1. deterministic requested ASIN;
2. distinct parent identity;
3. self-parent omission;
4. bounded ten-identity collection;
5. child-scoped Color/Size;
6. null trends produce no values;
7. deterministic variation rows/properties;
8. no ProductVariations parent edge;
9. `-1` UNKNOWN/no numeric sales;
10. positive sales unavailable;
11. bounded 20-row Product-to-Keyword relations;
12. organic first-three-pages rank;
13. percent traffic share;
14. partial 30-day estimate;
15. auditable USD minor-unit CPC;
16. no sponsored mapping;
17. unknown timezone;
18. empty keyword page is not zero demand;
19. total/later pages unavailable and completeness false;
20. permutation determinism;
21. Sorftime-specific provenance under shared identities;
22. raw/malformed/business failure cannot enter success;
23. provider-neutral normalization/Data Cleaning consumption;
24. socket and URL network construction denied.

## Validation record

- Baseline focused SP-040A/B, adapter/connector, Canonical, and Data Cleaning:
  `262 passed, 133 subtests passed`.
- Baseline full suite:
  `1167 passed, 16 skipped, 506 subtests passed, 1 failed`.
- New SP-040C focused suite: `33 passed`.
- Combined SP-040A/B/C, adapter/connector, Canonical, and Data Cleaning:
  `295 passed, 133 subtests passed`.
- Frozen Intelligence, V0.1/V0.2 Market Report, Production Pipeline,
  reliability, and Batch: `400 passed, 8 skipped, 56 subtests passed`.
- Post-change full suite:
  `1200 passed, 16 skipped, 506 subtests passed, 1 failed`.
- The sole baseline failure is the existing XLSX Renderer logical fingerprint;
  the post-change run reproduced the same test with the same expected and actual
  hashes. It is classified `BASELINE_RENDERER_NONREGRESSION`. Renderer and
  golden files remain unchanged and outside SP-040C. The 33 additional passing
  tests are exactly the new SP-040C focused suite.

## Known limitations and SP-040D handoff

Full family topology/completeness, a ProductVariations parent edge, positive
sales period/method, provider keyword totals, later-page completeness,
sponsored placement, timestamp timezone, trend/history, category denominators,
broader marketplace mappings, and XiYou equivalence remain unproven.

SP-040D may later provide typed DTOs to this mapper after transport succeeds and
strict DTO validation completes. SP-040D was not started here.
