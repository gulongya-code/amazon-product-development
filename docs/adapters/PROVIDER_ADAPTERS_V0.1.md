# Provider Adapters V0.1.2

Status: Level 3 implementation note with audited V0.1.2 query-execution evidence
Tasks: `TASK-SP-005`, `TASK-SP-005B`, `TASK-SP-005C`, `TASK-SP-007B`

## 1. Scope

This package is the dependency-free, offline boundary from audited XiYou and Sorftime payloads to Canonical Data Contracts V0.1. It implements:

```text
audited provider payload
  -> immutable raw snapshot and RawEvidenceRecord
  -> versioned mapping and TransformationRunRecord
  -> CanonicalEvidenceBundle with validated observations and issues
```

The implementation covers provider-neutral invocation, XiYou audited product/variation/order/BSR/keyword/directional slices, Sorftime audited product/variation/review slices, deterministic identity, structured failures, and strict bundle validation.

### V0.1.2 directional-query evidence

V0.1.2 adds canonical `DirectionalQueryExecutionRecord` outputs for XiYou forward and reverse keyword mappings. Populated queries publish `RESULTS_RETURNED` with concrete relationship-observation references. An explicit empty `data.list` publishes `EXPLICIT_EMPTY` with no fabricated target or metric. A non-empty response that cannot safely publish any relationship is `OUTCOME_UNKNOWN`. These records are part of `CanonicalEvidenceBundle`, not adapter-local diagnostics, so downstream consumers can distinguish execution outcomes without reading provider JSON.

### V0.1.1 variation correction

V0.1.1 re-audits variation direction before Product Intelligence consumes these facts. The governing rules are:

- a request/query ASIN is context, not parent evidence;
- family-set membership alone is not a directed relationship;
- a parent and child in one published relationship must be different ASINs;
- self members, duplicates, missing parents, and unconfirmed parent semantics remain in raw evidence with diagnostics instead of becoming confirmed edges;
- independent child attributes and metrics remain executable when their own semantics are safe.

XiYou's audited response explicitly labels `parentAsin` as the parent and `childAsins` as children under it. The adapter therefore publishes only distinct `parentAsin -> child ASIN` facts for valid members that have an exact `childAsins[]` raw locator. A query ASIN is published as a child only when that same ASIN appears in `childAsins`; `parentAsin` plus request context alone is insufficient. Sorftime's variation response documents child rows but returns no explicit parent identifier. Its request ASIN remains query context, so the adapter publishes no parent/child relationship from that response while retaining safe child Size/Color and sales-volume evidence.

Variation safety diagnostics are `MISSING_VARIATION_PARENT_UNCONFIRMED`, `NULL_VARIATION_PARENT_UNCONFIRMED`, `EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED`, `QUERY_AS_CHILD_NOT_CONFIRMED`, `VARIATION_SELF_MEMBER_NOT_PUBLISHED`, `DUPLICATE_VARIATION_MEMBER_NOT_PUBLISHED`, and Sorftime's `VARIATION_PARENT_SEMANTICS_UNCONFIRMED`. Invalid primitives/ASINs remain field quality issues rather than being silently coerced.

## 2. Non-goals

V0.1.2 does not call a live provider, implement an MCP client, authenticate, retry, paginate, persist, schedule, cache, resolve cross-provider conflicts, select a preferred source, average values, convert units, calculate provider weights, or expose a UI, CLI, or service endpoint.

## 3. Architecture

`ProviderAdapter` is the provider-neutral protocol. The public class names `XiYouAdapterV0_1` and `SorftimeAdapterV0_1` remain stable. XiYou's `adapter_version` is `0.1.2`; Sorftime remains `0.1.1` because no Sorftime source or mapping changed. Each owns its audited field mappings; no provider field appears in the common boundary.

One adaptation uses one `MappingSpecification`, one explicit `AdaptationContext`, and one immutable raw snapshot. A valid mapping execution creates one `TransformationRunRecord`. Emitted observations and directional query records carry matching `TransformationProvenance`; `CanonicalEvidenceBundle.validate()` checks run, raw, output, and issue references. Collection-level failures create no transformation run or output.

## 4. Public API

The stable import surface is:

```python
from amazon_product_intelligence.adapters import (
    ADAPTER_RULESET_VERSION,
    AdaptationContext,
    AdaptationResult,
    AdaptationStatistics,
    AdapterContextError,
    AdapterDiagnostic,
    AdapterError,
    AdapterFailure,
    AdapterFailureLevel,
    MappingDisposition,
    MappingSpecification,
    ProviderAdapter,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
```

Example:

```python
adapter = XiYouAdapterV0_1()
result = adapter.adapt(payload, adaptation_context)
result.bundle.validate()
```

`amazon_product_intelligence.adapters.__all__` contains only these public symbols. Provider helpers, field constants, and normalization functions are private.

## 5. Adaptation context

`AdaptationContext` requires:

- `provider`, `payload_kind`, and exact `source_tool`;
- normalized `marketplace` and `locale`;
- explicit RFC 3339 `retrieved_at` and `transformed_at`;
- explicit `collection_run_id`;
- sanitized request identity fields needed by the payload kind;
- optional explicit `currency`;
- explicit known/unknown `ProviderSchemaVersion` and `TransformationCodeVersion` objects, with safe defaults.

The context never reads the current clock or process environment. `sanitized_request` is detached and recursively immutable. Forward keyword relationships require request `keyword`; reverse keyword relationships and reviews require request `asin`. XiYou variations use returned `data.asin` as query-product identity, while Sorftime variations require request `asin` strictly as query context, not as parent evidence.

## 6. Adaptation result

`AdaptationResult` contains:

- provider, adapter version, and payload kind;
- the exact `MappingSpecification` used;
- `RawEvidenceRecord` plus an immutable raw snapshot;
- a validated `CanonicalEvidenceBundle`;
- canonical directional query execution records for supported XiYou query mappings;
- `AdapterDiagnostic` coverage records;
- structured `AdapterFailure` records;
- deterministic `AdaptationStatistics`.

`succeeded` means no collection-level error. A valid explicit-empty directional query succeeds with no canonical relationship observation and a successful transformation run whose output is the canonical query execution record. Field-level issues may coexist with independent safe observations.

## 7. Raw evidence preservation

The complete supplied JSON object is canonicalized by sorted-key JSON, detached from caller containers, and recursively frozen. Unknown fields remain in `raw_snapshot`; they are never promoted to observations without an approved mapping.

`RawEvidenceRecord` stores provider, source tool, collection identity, request scope, retrieval time, response state, an inline content reference, and an algorithm-labelled SHA-256 content fingerprint. The result-owned raw snapshot is the content addressed by that reference. Provider schema version remains explicitly unknown when the provider supplied no trustworthy version.

## 8. Deterministic identity

Raw identity uses provider, source tool, sanitized-request fingerprint, explicit retrieval time, and raw-response fingerprint. Transformation identity uses explicit collection identity, raw identity, mapping version, adapter ruleset, and explicit transformation time. Observation identities use the canonical contract helpers and include source record identity, dimension, provider semantics, period state, and relationship direction/channel when applicable.

Sorted canonical JSON makes mapping insertion order irrelevant. No random value, process hash, object representation, locale, filesystem path, current time, or test order participates in output.

`ADAPTER_RULESET_VERSION` is `provider-adapters-v0.1.2`. The XiYou directional mapping versions and XiYou adapter version changed with the canonical query output. The global default transformation code version therefore changes transformation-run identities and embedded provenance deterministically. Raw-evidence identities remain content-derived, and relationship-observation semantic/revision identities remain stable because adapter version and transformation provenance do not participate in those identity inputs.

## 9. Error and issue model

Collection/envelope failures include unsupported provider, unsupported payload kind, source-tool mismatch, malformed top level, non-string JSON keys, invalid provider status, missing request identity, and invalid envelope shape. They return `AdapterFailureLevel.COLLECTION`, no observations, and no transformation run.

Record/field issues use `DataQualityIssue` when they affect canonical safety and `AdapterDiagnostic` for mapping coverage. Wrong primitives omit only the unsafe observation. Mapping continues for independent safe fields. A partial run lists every emitted observation and issue. Exceptions are not converted to an empty successful result.

Mapping dispositions are `APPROVED_EXECUTABLE`, `APPROVED_WITH_EXPLICIT_UNKNOWN`, `DOCUMENTATION_ONLY`, `SEMANTICS_UNCONFIRMED`, and `OUT_OF_SCOPE`.

## 10. XiYou supported payload kinds

| Payload kind | Source tool | Mapping version |
|---|---|---|
| `asin_info` | `get_asin_info` | `xiyou_product_info_mapping_v1` |
| `asin_variations` | `get_asin_variations` | `xiyou_variations_mapping_v1_1` |
| `asin_orders_last_30_days` | `get_asin_orders_last_30_days` | `xiyou_orders_30d_mapping_v1` |
| `asin_bsr_trends` | `get_asin_bsr_trends` | `xiyou_bsr_trends_mapping_v1` |
| `keyword_info` | `get_keyword_info` | `xiyou_keyword_info_mapping_v1` |
| `keyword_asin_analysis` | `get_keyword_asin_analysis` | `xiyou_keyword_to_asin_mapping_v1_1` |
| `asin_keywords` | `get_asin_keywords` | `xiyou_asin_to_keyword_mapping_v1_1` |

## 11. XiYou mapping coverage

| Source locator | Canonical output | Classification and handling |
|---|---|---|
| `data.entities[].title` | product fact `title` | `APPROVED_EXECUTABLE`; observed, ASIN scope, observation time unknown. |
| `price` + `currency` | metric `price` | `APPROVED_EXECUTABLE`; only audited numeric strings/numbers, raw value retained. |
| `stars` | metric `rating` | `APPROVED_EXECUTABLE`; observed five-star scale. |
| `ratings` | metric `review_count` | `APPROVED_EXECUTABLE`; strict non-negative integer. |
| explicit `parentAsin` + valid `childAsins[]` member | `child_product_relationship` with the explicit parent as subject | `APPROVED_EXECUTABLE`; only distinct `parentAsin -> child` edges with exact child-list raw locators are published. A query ASIN is linked only when it is also an explicit `childAsins[]` member. |
| query ASIN absent from `childAsins[]` | no inferred query-as-child relationship | Request context and raw evidence are retained with `QUERY_AS_CHILD_NOT_CONFIRMED`; `parentAsin` alone does not authorize synthesis. |
| self or duplicate `childAsins[]` member | no additional relationship | Raw evidence retained with `VARIATION_SELF_MEMBER_NOT_PUBLISHED` or `DUPLICATE_VARIATION_MEMBER_NOT_PUBLISHED`. |
| missing, null, empty, or invalid `parentAsin` | no directed relationship | Family members stay raw; missing/null/empty semantics are explicit unknown diagnostics, invalid values are quality issues, and none imply a standalone product or zero variations. |
| `orders` | metric `orders` | `APPROVED_WITH_EXPLICIT_UNKNOWN`; provider estimate, rolling-30-day label, method and parent/child scope unconfirmed. |
| BSR trend `rank` | metric `bsr` | `APPROVED_EXECUTABLE`; category and source calendar date retained in rank context; observation timestamp remains unknown because the date has no timezone. |
| `abaReport.weeklySearchVolume` | keyword metric `search_volume` | `APPROVED_WITH_EXPLICIT_UNKNOWN`; provider estimate with unconfirmed derivation; calendar-week type and raw date-only boundaries retained through raw lineage. |
| `abaReport.searchFrequencyRank` | keyword metric `aba_search_frequency_rank` | `APPROVED_EXECUTABLE`; provider-reported rank. |
| `competitiveDifficulty` | keyword metric `competition_difficulty` | `APPROVED_WITH_EXPLICIT_UNKNOWN`; provider scale/method issue attached. |
| `costPerClick.value/min/max` | keyword metric `cpc` and range | `APPROVED_EXECUTABLE` when explicit context currency exists; provider estimate. |
| forward/reverse rows | product-keyword candidate membership | `APPROVED_EXECUTABLE`; direction is mandatory identity material. |
| rank code `or` | organic rank relationship | `APPROVED_EXECUTABLE`. |
| rank code `sb` | sponsored rank relationship | `APPROVED_EXECUTABLE`. |
| other rank codes | no observation | `SEMANTICS_UNCONFIRMED`; raw retained with diagnostic. |
| organic/advertising traffic | separate channel traffic relationships | `APPROVED_WITH_EXPLICIT_UNKNOWN`; values preserved as provider estimates, unit/method/period issue attached. |

Numeric zero remains `PRESENT`. XiYou title text is not used to infer Brand. No structured attribute or bullet-point observation is created. Embedded image/listing URLs and analytical rate fields are retained raw but remain out of scope.

## 12. Sorftime supported payload kinds

| Payload kind | Source tool | Mapping version |
|---|---|---|
| `product_detail` | `product_detail` | `sorftime_product_detail_mapping_v1` |
| `product_variations` | `product_variations` | `sorftime_variations_mapping_v1_1` |
| `product_reviews` | `product_reviews` | `sorftime_reviews_mapping_v1` |

## 13. Sorftime mapping coverage

| Source locator | Canonical output | Classification and handling |
|---|---|---|
| direct `title`, `brand`, `category`, `node_id` | product facts | `APPROVED_EXECUTABLE`; independent facts with exact source locators. |
| `parent_asin` | parent relationship fact | `APPROVED_EXECUTABLE`; self-parent value is kept raw and marked semantics-unconfirmed. |
| direct `price`, `star_rating`, `review_count` | metrics | `APPROVED_EXECUTABLE`; price requires explicit currency context. |
| JSON-encoded `attributes` | approved structured product facts | `APPROVED_EXECUTABLE` only for audited attribute keys; multiple same-dimension facts are retained separately. |
| `description` | product fact `description` | `APPROVED_EXECUTABLE`; it is not renamed to bullet points. |
| `monthly_sales_volume` | metric `estimated_monthly_sales` | `APPROVED_WITH_EXPLICIT_UNKNOWN`; period/method issue attached. |
| pressure attribute/title/description spans | three `maximum_operating_pressure` facts | `APPROVED_EXECUTABLE` for the audited spans; Pa, WOG, and psi remain separate with a field-blocking unit/semantic issue. |
| variation request ASIN | no parent relationship | `APPROVED_WITH_EXPLICIT_UNKNOWN`; it is query context, not a response-confirmed parent. Diagnostic: `VARIATION_PARENT_SEMANTICS_UNCONFIRMED`. |
| variation row `Asin` + approved `Property` | child Size/Color facts | `APPROVED_EXECUTABLE`; child ASIN scope, exact source row, and query context in source identity are retained without setting `parent_asin`. |
| `SalesAmount` with returned `doc.sales_amount` | metric `estimated_sales_volume` | `APPROVED_EXECUTABLE`; sales volume, not revenue; period remains unknown. `-1` maps to `UNKNOWN`, not negative or zero. |
| `SalesAmount` without confirming documentation | no sales/revenue metric | `SEMANTICS_UNCONFIRMED`; raw retained with issue. |
| review rating/title/body/date/variant | `ReviewObservation` | `APPROVED_EXECUTABLE`; source identity is a deterministic adapter identity over ASIN, record index, and immutable review content. |
| review helpful votes | `MISSING` envelope | `APPROVED_WITH_EXPLICIT_UNKNOWN`; never zero. |

Review date is normalized to a date value while source `observed_at` remains unknown. Missing or malformed core review identity material prevents that review observation without blocking unrelated records.

## 14. Unmapped and semantics-unconfirmed fields

Every supplied field is either mapped, intentionally ignored with a reason, or diagnosed as unmapped/unconfirmed. Unknown fields remain in the raw snapshot and never become canonical dimensions automatically. XiYou placement codes beyond audited `or`/`sb`, traffic method/window, order grain, and keyword-estimate method remain unconfirmed. Sorftime unapproved attribute keys, product-detail self-parent semantics, variation-parent identity, sales method/window, and undocumented `SalesAmount` semantics remain unconfirmed.

Provider field names never determine semantic truth by themselves. `SalesAmount` is executable only when returned provider documentation explicitly establishes variation sales-volume semantics.

## 15. Directional query execution semantics

A successful XiYou forward query with `data.list=[]` produces:

- raw response status `EMPTY`;
- an immutable raw snapshot retaining `list=[]` and provider `total`;
- a successful transformation run with no fabricated relationship observation;
- a canonical `DirectionalQueryExecutionRecord` whose outcome is `EXPLICIT_EMPTY` and whose query subject is the requested keyword;
- an `AdapterDiagnostic` with code `QUERY_RETURNED_EMPTY`, the raw reference, source locator, and mapping specification.

Canonical `ProductKeywordRelationshipObservation` requires a concrete product, so the adapter does not invent a placeholder product for an empty set. The empty query is fully auditable inside the canonical bundle through raw evidence, mapping, run, and the query execution record. It never emits `market_size`, `competitor_count`, `demand`, or any zero metric. Independent reverse evidence remains valid and populated.

Populated forward and reverse queries publish `RESULTS_RETURNED` records containing the safely emitted relationship observation IDs. If a provider returns non-empty rows but none can safely become a canonical relationship, the outcome is `OUTCOME_UNKNOWN`, not `EXPLICIT_EMPTY`. Reverse explicit-empty behavior is supported without inventing a keyword, although the V0.1 fixture set contains only a captured forward empty response.

## 16. Unit safety

Numbers and units are bound in `ValueEnvelope`. The audited pressure values `1000 pascal`, `1000 WOG`, and `1000 PSI` become separate observations with distinct source locators and unit codes. WOG is marked ambiguous and is not treated as PSI. No automatic conversion, merge, selected value, conflict resolution, or unit registry is implemented. A `UNIT_SEMANTIC_CONFLICT` issue references the raw record and all pressure observations.

## 17. Single-provider behavior

Each concrete adapter can independently create a complete Raw -> Collection -> Mapping -> Transformation -> Observation chain. No second provider, provider count, corroboration, preferred-source policy, or cross-provider average is required. Single-source observations are evidence, not resolved truth.

## 18. Fixture provenance

All provider fixtures are classified `CAPTURED_AND_SANITIZED`. They are minimal excerpts from the ignored local raw evidence verified against both `RAW_EVIDENCE_MANIFEST.sha256` files: XiYou 21/21 hashes and Sorftime 7/7 hashes matched before fixture creation.

| Fixture | Audited source |
|---|---|
| `xiyou_asin_info.json` | XiYou batch product-info response |
| `xiyou_asin_variations.json` | XiYou B0G2VV4RBW variation response |
| `xiyou_asin_orders.json` | XiYou batch recent-orders response |
| `xiyou_asin_bsr.json` | XiYou B0G2VV4RBW BSR response |
| `xiyou_keyword_info.json` | XiYou batch keyword response |
| `xiyou_keyword_forward_populated.json` | XiYou `plastic spoons` forward response |
| `xiyou_keyword_forward_empty.json` | XiYou `1/2 Ball Valve` empty forward response |
| `xiyou_asin_keywords_reverse.json` | XiYou B0G2VV4RBW reverse-keyword response |
| `sorftime_product_detail.json` | Sorftime B0G2VV4RBW product detail |
| `sorftime_product_variations.json` | Sorftime B0G2VV4RBW variation response |
| `sorftime_product_reviews.json` | Sorftime B0G2VV4RBW review response, with review text minimized |

`fixture_manifest.json` records each LF-normalized UTF-8 fixture content hash, source path, source hash, and classification. Audit envelopes, unrelated rows, URLs, user task text, and sensitive authentication material were removed. These excerpts are not described as complete provider responses. Raw audit artifacts are verified during acceptance but remain local evidence, so committed unit tests do not require those ignored files to exist after a clean checkout.

## 19. Test command

With the repository `src` directory on the process-only import path:

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath "src").Path
py -3.12 -m unittest discover -s tests -p "test_*.py" -v
```

Tests cover public API, strict envelopes and primitives, input immutability, unknown-field retention, deterministic replay (including fresh processes and key-order perturbation), presence states, both keyword relationship directions, channel separation, empty query behavior, pressure-unit safety, review identity, helpful-vote absence, explicit-parent variation direction, self/duplicate/missing/null/empty/invalid variation cases, Sorftime query-context safety, raw/mapping/run lineage, strict bundle round trip, fixture parsing, provenance classification, and authentication-material scanning.

## 20. Known limitations

- Fixtures are minimized audited excerpts, not complete live responses.
- No live schema/version is declared by either provider; schema version remains explicitly unknown.
- XiYou source calendar dates are retained in raw/rank context because date-only values do not safely establish an RFC 3339 observation timestamp or timezone.
- XiYou rank codes other than `or` and `sb` are not executable.
- XiYou traffic unit/method/window, order method/grain, and keyword-estimate derivation remain unconfirmed.
- XiYou variation edges require a valid explicit `parentAsin` and a valid distinct `childAsins[]` member with an exact raw locator; family members without a parent are not directed, and request context cannot fill a missing child member.
- A directional query outcome is represented independently from relationship observations. Explicit empty remains scoped execution evidence and cannot be interpreted as zero demand, zero competition, or a permanent absence.
- Sorftime description is not a typed bullet array.
- Sorftime variation responses do not expose an explicit parent identifier, so no parent/child relationship is published from them.
- Only audited structured attribute keys and exact audited pressure text patterns are executable.
- Review pagination, helpful votes, manufacturer, model, included components, and rich A+ text remain unavailable or unsupported.
- Resolution, unit conversion, parent/child aggregation, and provider preference require separate versioned tasks.

## 21. Product and Demand Intelligence boundary

This package produces provider-neutral source observations and directional query execution evidence only. It does not create a Product Profile, Product Knowledge Snapshot, Demand Profile, relevance judgment, true-competitor set, market reconstruction, demand-supply gap, opportunity score, or final product-selection decision. Product Intelligence V0.1 ignores query execution records as non-observation bundle content while retaining their effect on the source bundle fingerprint. A later Demand Intelligence contract may consume those canonical records, but it must not read adapter diagnostics or provider JSON to recover query outcomes. Product Intelligence must consume the corrected adapter semantics; it must not reinterpret a query ASIN or family-member set as a parent in order to repair adapter output downstream.
