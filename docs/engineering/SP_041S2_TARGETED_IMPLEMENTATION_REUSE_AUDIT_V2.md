# TASK-SP-041S2 Targeted Implementation Reuse Audit V2

- Audit date: 2026-08-29
- Required starting HEAD: `d470521da969426cbdc5f26448487080b1f8cb97`
- Required ancestry: `6446c36618180d6a4b32b58c6801efd4f9f916fa`
- Audit timing: completed before Semantic Engine V2 implementation
- Scope: listing-side Semantic Engine V2 and APD cohort projection only

## Governing decision

S2 will extend the accepted listing-side repository rather than create a third Shared Semantic Core package or a parallel ingestion/evidence system. The S1-calibrated Semantic Fact, Evidence Relationship, Universal Semantic Role, Product Identity, orthogonal Product Role, quantity/scope, profile, and APD cohort boundaries are implemented in one new `semantic_engine_v2` package. Existing production contracts remain unchanged and continue to serve existing consumers.

No new dependency or copied/adapted external implementation is selected. S1 already completed the broad public GitHub/license review. S2 uses the Python standard library and existing repository dependencies only, so no fresh external license/security decision is required. The closeout parser for the original operator-review workbook reuses the already pinned `openpyxl>=3.1.5,<4` dependency in read-only/data-only mode; SP-041B had already selected that MIT-licensed dependency without copying or vendoring its source.

## Component mapping

| S2 component | Existing asset | Decision | Exact implementation boundary |
| --- | --- | --- | --- |
| Listing input and grain | `GovernedMarketDatasetV1`, `ListingRecordV1`, `NormalizedField`, import statuses/evidence semantics | `REUSE_AS_IS` | S2 consumes accepted listing records directly, preserves upstream IDs/fingerprints and never collapses parent families. |
| Detailed structured evidence | `parse_detailed_parameters`, `DetailedParameterParseResult`, normalized keys, retained parse issues/conflicts | `REUSE_AS_IS` | Parse structured evidence without copying raw rows into results. Parse issues become limitations; usable pairs remain usable. |
| Exact measurement parsing | `parse_measurement`, `ParsedMeasurement`, `QuantityKind`, `MeasurementScope` | `REUSE_AS_IS_WITH_PROFILE_AUTHORIZATION` | Reuse only after the S2 profile declares the expected quantity kind and semantic scope. Ambiguous `oz`, mismatched kind and invalid values remain unavailable. |
| SP-041C evidence records | `EvidenceReference`, `AttributeSlot`, `AttributeConflict`, availability/review vocabulary | `EXTEND` | Reuse evidence/status concepts and upstream source lineage patterns. S2 facts add Universal Semantic Role, source class, observed/derived status, quantity subtype/scope, profile/rule references and relationship states. |
| Deterministic contracts | `JsonContract`, `canonical_json`, `deterministic_id`, stable sorting and fingerprint patterns | `REUSE_AS_IS` | All profile/fact/relationship/listing/result identities use canonical semantic material; timestamps and row order are excluded. |
| Availability/evidence/provenance | Market Report V0.2 `Availability`, `PresenceStatus`, `EvidenceSemantics`, `ContractReference` | `REUSE_AS_IS` | S2 uses the accepted availability/evidence vocabulary and registered upstream/profile references rather than a parallel missingness framework. |
| Confidence | `AttributeConfidenceLevel` | `REUSE_AS_IS` | S2 facts reuse HIGH/MEDIUM/LOW/UNKNOWN confidence without modifying the accepted enum. |
| Source taxonomy | SP-041C `SourceKind` (`STRUCTURED_PARAMETERS`, `DEDICATED_FIELD`, `SKU`, `TITLE`) | `EXTEND` | S2 defines the frozen source classes needed by S1, including provider category context, bullets, enrichment and non-authoritative LLM candidates. SP-041C's enum remains frozen. |
| Category configuration | `CategoryRulePack` strict UTF-8 JSON loader/schema/version/fingerprint pattern | `EXTEND` | Implement a distinct strict `CategorySemanticProfileV1_1` because S1 freezes new responsibilities: source policies, role mapping/relevance, identity/role/lifecycle/coexistence/conflict/quantity/scope rules. No final route names are allowed. |
| Attribute aliases/value aliases | SP-041C match/passthrough rules and existing normalization helpers | `EXTEND` | Profile-owned deterministic phrase/alias matching produces candidate semantic facts. Generic Python contains no category vocabulary. |
| Evidence resolution | SP-041C global source priority in `listing_attribute_map.engine` | `REPLACE_IN_V2` | S2 evaluates semantic question, coexistence and kind/scope before applying per-dimension profile policy. The accepted SP-041C engine is not changed and existing consumers are not cut over. |
| Relationship classification | SP-041C conflict model | `EXTEND` | Add all frozen V1.1 states and distinguish complementary/multi-value/source-only/true/route-critical conflict without forcing whole-listing review for ordinary missing facets. |
| Product Identity and Product Role | No accepted runtime equivalent | `EXTEND` | Implement evidence-backed identity plus orthogonal relation/lifecycle facts from profile rules. Title is primary/co-primary; pack count never establishes bundle. |
| Quantity semantics | SP-041C count parser | `EXTEND` | Preserve `PACKAGE_COUNT`, `STRUCTURAL_COMPONENT_COUNT`, and `CONSUMABLE_UNIT_COUNT`; do not collapse them. |
| Size/capacity scope | SP-041C measurement kind/scope | `EXTEND` | Add semantic scope distinguishing observed item from host device; a source key named capacity is never sufficient by itself. |
| APD market membership | No shared-core equivalent; S1 calibration business labels only | `EXTEND_AS_APD_PROJECTION` | Produce APD-specific `PRIMARY_COHORT_ELIGIBLE / NON_PRIMARY_EXCLUDED / OFF_TARGET_EXCLUDED / UNKNOWN / REVIEW_REQUIRED`. Do not promote calibration labels into universal facts and do not discover routes. |
| Semantic clustering | `semantic_clustering` buyer-need normalization/clustering | `REPLACE_IN_V2_NOT_REUSED` | Buyer-need clustering answers a different question and cannot authoritatively establish listing identity/role/cohort. Its generic identity/sorting pattern is already covered by shared contract reuse. |
| Legacy product-attribute extraction profile | `product_attribute_extraction` V0.1 contracts | `REPLACE_IN_V2_FOR_THIS_PATH` | Preserve existing consumers, but do not expand field-per-category modeling. S2 uses the frozen role/profile contract and reuses only accepted confidence/identity patterns. |
| SP-041D Product Map join | `product_route_opportunity.product_map` | `EXTEND_PATTERN_ONLY` | Reuse fail-closed listing-set/upstream fingerprint checks and sanitized diagnostics patterns. S2 does not invoke route metrics or membership. |
| Exact structural route signatures | SP-041D `EXACT_KNOWN_STRUCTURAL_ATTRIBUTE_SIGNATURE` | `DEPRECATE_AFTER_V2` | No change in S2. Route Discovery V2 will later consume S2 route-eligible roles and replace exact signatures under its own gates. |
| SP-041D route market metrics | share/growth/distribution/concentration/demand-efficiency code | `REUSE_AS_IS_DOWNSTREAM` | These metrics remain frozen and untouched. S2 produces no route or opportunity metric. |
| KWS semantic/business authorities | external `amazon_keyword_screener` accepted contracts | `DEPRECATE_AFTER_V2_NONE / NO_CUTOVER` | S2 does not modify KWS, create adapters, or change Ground Truth, Brand, Search Target, Hard Conflict, Listing or PPC authority. |

## Generic-engine/profile split

Generic engine code may contain only frozen role/state vocabularies, deterministic evaluation order, profile interpretation, evidence normalization, relationship classification, result construction and APD projection logic driven by profile facts. All five category identities, phrases, aliases, structured keys, rule IDs, source authorization and role relevance live in versioned JSON profiles.

The production tests will scan generic engine Python for the five category literals and fail if any category branch/vocabulary leaks into it.

## Private replay reuse

The same S1-calibrated five-category corpus is the mandatory S2 replay input:

- Shower Caddy: 998 accepted listings;
- Dog Water Bottle: 400;
- Vacuum Filter: 300;
- Food Storage Container Sets: 150;
- Air Fryer mixed market: 300.

Private workbooks, paths, ASINs, titles, brands, sellers, prices, detailed-parameter strings and raw rows remain external. The S2 replay boundary may emit only category-level counts/rates, role/relationship/coverage aggregates, deterministic fingerprints and runtime summaries.

## Baseline evidence before implementation

- Branch/HEAD/workspace/staging/runtime gate: PASS.
- Required ancestry: PASS.
- SP-041A/B/C/D focused baseline: 64 passed.
- Affected Product Intelligence/Opportunity/Market Report/pipeline baseline: 453 passed, 5 skipped, 129 subtests passed.
- Full required-HEAD baseline: 1 failed, 1416 passed, 13 skipped, 550 subtests passed.
- Sole failure is the frozen Windows OOXML fingerprint exception: expected `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`, actual `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.

## Audit verdict

`TARGETED_S2_REUSE_AUDIT = COMPLETE_BEFORE_IMPLEMENTATION`

`NEW_EXTERNAL_DEPENDENCY_OR_COPY = NO`

`THIRD_SHARED_CORE_PACKAGE = NO`
