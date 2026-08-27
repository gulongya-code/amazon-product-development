# SP-041S1 Cross-System Reuse Audit V1.1

Status: **COMPLETE_FOR_S1_DESIGN — IMPLEMENTATION MIGRATION DEFERRED**

## 1. Scope

This audit extends Issue #55 beyond repository-internal reuse and evaluates the accepted semantic assets in:

- Market/route system: `gulongya-code/amazon-product-development`
- Keyword system: `gulongya-code/amazon_keyword_screener`
- KWS audited snapshot: `c0074f1700061f5e7abe65e562a243cc598638da`

The objective is to prevent both systems from building separate category-specific semantic engines while preserving their independent business authority.

Governing principle:

> **Share what a product fact or phrase means; keep what each system does with that meaning system-specific.**

S1 does not create a third repository/package and does not cut either production system over to a new shared dependency.

## 2. KWS assets reviewed

The audit reviewed the accepted KWS contracts and implementation around:

- `ProductProfile`
- `SearchTargetInference` / `SearchTargetRole` / `SearchTargetRelation`
- `ProductKeywordAssessment`
- `HardConflict` / `HardConflictDimension`
- `SemanticRelation`
- `EvidenceSufficiency`
- `AttributeFinding`
- `UsageSuitability`
- deterministic relevance execution
- query-side search-target inference
- canonical keyword normalization and measurement parsing
- Brand Evidence Authority
- Brand Query Binding
- governed Brand Semantic shadow / `semantic-contract/v2`
- accepted Ground Truth and regression gates

## 3. Cross-system contract classification

| KWS capability | S1 decision | Shared-core implication | KWS authority after migration |
| --- | --- | --- | --- |
| `ProductProfile` field model | `ALIGN_CONTRACT / DEPRECATE_FIELD_EXPLOSION_AFTER_MIGRATION` | Future product facts should be consumable from a category-neutral Product Semantic Profile / SemanticFact contract instead of adding one field per category. | KWS may keep a compatibility adapter while accepted consumers migrate. |
| Product type / material / size / compatibility facts | `EXTRACT_CONCEPT_TO_SHARED_CORE` | These are product semantic facts and should use the same Universal Semantic Role, evidence, unknown and provenance semantics in both systems. | KWS decides how facts affect keyword relevance; shared core does not. |
| `SearchTargetInference` | `KEEP_KWS_SPECIFIC + ALIGN_VOCABULARY` | Query-side target interpretation is KWS-specific, but its target/product-role vocabulary should map cleanly to shared Product Role and Product Identity semantics. | KWS remains authority for query target inference. |
| `SearchTargetRole.TARGET_PRODUCT / COMPONENT / ACCESSORY_OR_REPLACEMENT / OTHER_PRODUCT` | `ALIGN_CONTRACT` | Avoid duplicate conflicting definitions of primary product/accessory/replacement/component. Query role and listing Product Role are related but not identical contracts. | KWS retains query-role result; shared core supplies stable role semantics/mappings. |
| `HardConflict` gate | `KEEP_KWS_SPECIFIC + CONSUME_SHARED_FACTS` | Hard conflict is a product-keyword business gate, not a universal product-fact primitive. Shared core should expose facts/conflicts/evidence; KWS projects them into its Hard Conflict decision. | KWS remains authority for eligibility/safety gating. |
| `HardConflictDimension` | `ALIGN_DIMENSIONS` | Material, size/capacity, compatibility and product identity should map to shared semantic dimensions/roles. KWS-only gate dimensions remain local. | Existing KWS versions remain supported until explicit migration. |
| `SemanticRelation` (`MATCH/RELATED/MISMATCH/UNKNOWN`) | `KEEP_KWS_SPECIFIC` | This is the relationship between a query and a product, not an intrinsic listing fact. It should consume shared semantic representations on both sides. | KWS remains current semantic consumer authority. |
| `EvidenceSufficiency` | `ALIGN_CONTRACT` | Shared evidence/availability vocabulary should make insufficiency derivable consistently, but KWS may retain its consumer enum/projection. | No automatic enum replacement in S1. |
| `AttributeFinding` | `KEEP_KWS_SPECIFIC + CONSUME_SHARED_FACTS` | Query-requested attribute match/conflict/unknown is a comparison result. Shared core supplies normalized attribute/value facts and evidence relationships. | KWS keeps query-product findings and review behavior. |
| `UsageSuitability` / Listing / PPC Exact / PPC Test | `KEEP_KWS_SPECIFIC` | These are keyword-operating recommendations and must not enter Shared Semantic Core. | Fully local to KWS. |
| Search Intent | `KEEP_KWS_SPECIFIC` | Search intent is query-side business interpretation. | Fully local to KWS. |
| Brand Evidence Authority | `RETAIN_AS_IS_KWS_SPECIFIC` | Governed brand identity is useful evidence, but current authority/policy is deliberately KWS-controlled. Do not move it merely to create code reuse. | KWS authority unchanged. |
| Brand Query Binding | `RETAIN_AS_IS_KWS_SPECIFIC` | Binding is query-structure evidence and remains KWS-specific. | KWS authority unchanged. |
| Brand Semantic `semantic-contract/v2` shadow | `PROTECT_AS_REGRESSION_AUTHORITY` | Future shared-core adoption must reproduce or explicitly supersede accepted Brand semantics without weakening fail-closed behavior. | No default cutover from this audit. |
| Canonical Keyword / KeywordCandidate normalization | `KEEP_KWS_SPECIFIC` | Canonical keyword identity has deliberately conservative rules and is not the same as semantic analysis normalization. | KWS authority unchanged. |
| Measurement/unit analysis helpers | `EXTRACT_CANDIDATE / ALIGN` | Safe, category-neutral numeric+unit parsing is a legitimate shared-core candidate if semantics and tests match both systems. | KWS may consume a shared helper after migration gate. |
| Material aliases / category-specific relevance vocabulary | `SPLIT` | Truly universal normalization candidates may move to shared core; category-specific/product-family vocabulary must move to Category Semantic Profiles, not generic shared Python constants. | Existing rules remain frozen until validated replacement is accepted. |
| KWS Ground Truth / validation workbooks | `RETAIN_AS_MIGRATION_GATE` | They are not runtime ontology; they protect migration correctness. | Must gate KWS integration. |

## 4. Important semantic distinctions

### 4.1 Product Role is not Search Target Role

The shared `ProductRole` answers what an observed listing/product is:

`PRIMARY_PRODUCT / ACCESSORY / REPLACEMENT / REFILL / BUNDLE / UNKNOWN ...`

KWS `SearchTargetRole` answers what the query appears to be searching for relative to the profiled product.

The vocabularies should map, but they must not be collapsed into one object because their evidence grain and authority differ.

### 4.2 Product facts are not keyword findings

Shared core should represent facts such as:

- product identity;
- material;
- size/capacity;
- compatibility;
- installation/operation structure;
- included components;
- evidence source, status and provenance.

KWS should continue to produce comparison results such as:

- attribute match;
- attribute conflict;
- unknown requested attribute;
- semantic relation;
- Hard Conflict;
- Listing/PPC suitability.

### 4.3 Shared normalization is not canonical keyword identity

KWS canonical keyword identity is intentionally conservative and evidence-preserving. A future shared semantic normalizer may create private analysis views for alias/unit/value matching, but must never silently rewrite canonical keyword identity.

## 5. Current KWS category-generalization debt

The current accepted KWS implementation is intentionally conservative but contains bounded US/en-US vocabularies and product/category-specific decision support, including:

- governed product-head lists in Search Target;
- room/use-case vocabularies;
- material/product-family aliases and conflict rules;
- specific broad-relation tokens in Semantic Contract.

These were validated for the accepted KWS cohorts and must not be deleted casually. However, adding Air Fryer-, Office Chair-, Dog Water Bottle-, or other category-specific branches to the same generic modules would create duplicated cross-category semantics.

Decision:

`NO_NEW_LARGE_CATEGORY_SPECIFIC_PATCHES_IN_GENERIC_KWS_SEMANTIC_CODE_BEFORE_SHARED_CONTRACT_FREEZE`

Any such task must declare `SEMANTIC_SHARED_CORE_DEPENDENCY` and either wait for or explicitly justify deviation from the shared contract.

## 6. Proposed Shared Semantic Core responsibility

Subject to real multi-category S1 calibration, the shared layer should own only category-neutral semantics such as:

- `SemanticRole` vocabulary;
- `ProductRole` vocabulary and evidence-backed product-role fact contract;
- normalized `SemanticFact` / attribute-value representation;
- evidence source/status/provenance;
- availability/missing/unknown semantics;
- evidence relationship (`AGREES`, `COMPLEMENTARY`, `COMPATIBLE_MULTI_VALUE`, conflicts, etc.);
- unit/value normalization that is truly category-neutral;
- strict `CategorySemanticProfile` schema/version/fingerprint;
- category language/attribute/value aliases and role relevance configuration;
- deterministic semantic identity/versioning.

It must not know or decide:

- Product Route market opportunity;
- Keyword Eligibility;
- Search Intent;
- Brand Query Binding policy;
- Listing/PPC suitability;
- advertising search-term performance;
- Amazon write actions.

## 7. Consumer architecture target

```text
                     Shared Semantic Core
                    /                    \
                   /                      \
       Listing Semantic Adapter        Query Semantic Adapter
                |                              |
     Product Semantic Facts             Query Semantic Claims
                |                              |
      amazon-product-development        amazon_keyword_screener
                |                              |
       Route/Market Analysis        Relevance/Intent/Listing/PPC
```

The two systems may share contracts and small pure helpers while keeping repositories and business decisions independent.

## 8. Migration sequence

1. `SP-041S1`: freeze/calibrate the semantic contracts across multiple real categories.
2. `S2 — Semantic Engine V2`: implement the reference listing-side semantic engine in `amazon-product-development` using frozen contracts.
3. `S3 — Shared Semantic Core Extraction`: decide package/repository boundary and extract only proven category-neutral contracts/helpers.
4. `KWS Integration`: add a compatibility adapter and query-side consumer, then replay accepted KWS Ground Truth, Brand Binding GT and semantic/usage regression gates.
5. Only after equal-or-better safety may KWS default consumers migrate.

S1 does not authorize step 3 or 4.

## 9. KWS migration acceptance requirements

A future KWS integration gate must at minimum preserve or explicitly supersede with accepted evidence:

- historical false-acceptance / false-rejection safety;
- accepted Ground Truth authorities;
- Search Target fail-closed behavior;
- Hard Conflict gate safety;
- Brand Evidence Authority integrity;
- Brand Query Binding consumer-safety cohort;
- governed Brand Semantic behavior;
- Listing/PPC Exact/PPC Test suitability boundaries;
- canonical keyword identity and raw evidence preservation;
- no automatic Amazon execution.

A shared-core architectural improvement is not sufficient evidence for a KWS production cutover.

## 10. S1 decision

`CROSS_SYSTEM_REUSE_BOUNDARY_FROZEN_FOR_CALIBRATION`

The two systems have substantial semantic overlap and should converge on one category-neutral semantic fact/profile contract. They must not merge business authority, and KWS accepted semantic safety remains an independent migration gate.
