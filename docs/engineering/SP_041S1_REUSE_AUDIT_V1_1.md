# SP-041S1 Reuse Audit V1.1

Status: **IN_PROGRESS — PRIVATE_MULTI_CATEGORY_CALIBRATION_REQUIRED**

## 1. Baseline and task boundary

- Repository: `gulongya-code/amazon-product-development`
- Issue: `#55 [TASK-SP-041S1] Cross-Category Semantic Calibration & Reuse Gate V1.1`
- Required baseline: `6446c36618180d6a4b32b58c6801efd4f9f916fa`
- Parent SP-041D implementation: `5ab44a0d5f6bd76d649f7221d1def4201220f2e8`
- Dedicated branch: `codex/task-sp-041s1-cross-category-semantic-calibration`
- SP-041E remains frozen.

SP-041S1 is a calibration, requirements and reuse gate. It must not implement the full Semantic Engine V2 or Route Discovery V2. The purpose of this audit is to identify what is already safe to retain, what must be extended, what should be replaced in V2, and which public components are suitable for dependency/reference reuse.

## 2. Internal reuse audit

### 2.1 RETAIN_AS_IS

The following accepted layers are outside the semantic defect exposed by the private SP-041D business review and should remain the default implementation:

| Component | Decision | Reason |
| --- | --- | --- |
| SP-041A Operator Template contracts | `RETAIN_AS_IS` | Template/sheet/header/formula contracts are independent of route semantics. |
| SP-041B SellerSprite import/governed dataset | `RETAIN_AS_IS` | Header-based import, provenance, missingness and row-grain controls remain valid. |
| Evidence/provenance primitives | `RETAIN_AS_IS` | Existing source/evidence traceability should be extended, not duplicated. |
| Availability/missing-value discipline | `RETAIN_AS_IS` | Missing/blank/parse-failure must continue to remain distinct from zero/false. |
| Canonical JSON / deterministic IDs / fingerprints | `RETAIN_AS_IS` | Required for repeatability, auditability and private replay comparison. |
| Decimal/business-numeric conventions | `RETAIN_AS_IS` | Market and procurement arithmetic must remain deterministic. |
| SP-041D route market metrics | `RETAIN_AS_IS` | Listing share, sales share, demand efficiency, growth reconstruction, distributions and concentration logic operate after membership and are not the source of the observed route-semantic defect. |
| Denominator/coverage/limitation reporting | `RETAIN_AS_IS` | Critical to avoid treating missing evidence as fact. |
| Privacy/secret/network controls | `RETAIN_AS_IS` | Real market rows remain external acceptance assets. |

### 2.2 EXTEND

| Component | Decision | Required V2 extension |
| --- | --- | --- |
| `ProductAttributeMapV1` / SP-041C attribute output | `EXTEND` | Add semantic-role projection, evidence relationship/coexistence, Product Role evidence and route-criticality without breaking provenance. |
| CategoryRulePack concept | `EXTEND` | Evolve responsibility toward a Category Semantic Profile: category language -> normalized attribute/value -> universal Semantic Role + source authorization + role relevance. It must not encode final route names. |
| Conflict representation | `EXTEND` | Distinguish agreement, complementary evidence, compatible multi-value evidence, true conflicts and route-critical conflicts. |
| Review-required logic | `EXTEND` | Review only when ambiguity/conflict affects product identity, Product Role or route-critical structure; ordinary missing attributes remain unavailable. |
| Candidate diversity semantics | `EXTEND` | Diversity must operate on route-eligible structural semantics, not arbitrary feature differences. |

### 2.3 REPLACE_IN_V2 / DEPRECATE_AFTER_V2

| Component | Decision | Reason |
| --- | --- | --- |
| One global evidence precedence such as `structured > dedicated > SKU > title` | `REPLACE_IN_V2` | Source reliability depends on semantic dimension. Title can be first-class market-semantic evidence while structured fields are stronger for exact specifications. |
| `EXACT_KNOWN_STRUCTURAL_ATTRIBUTE_SIGNATURE` as the main route-membership strategy | `REPLACE_IN_V2` | Private replay produced excessive fragmentation; exact combinations also allow non-route properties to split products that belong to the same architecture. |
| Feature-driven primary route identity | `DEPRECATE_AFTER_V2` | Functional features often coexist on the same product and should normally be facets rather than route identity. |
| Missing non-critical attributes causing listing-wide review | `REPLACE_IN_V2` | Missing material/quantity/etc. must not block otherwise-understood primary product structure. |

## 3. Public GitHub / dependency audit

### 3.1 Shopify Product Taxonomy

- Repository: `Shopify/product-taxonomy`
- License classification: `DIRECT_REUSE_ALLOWED` / MIT.
- Relevant concepts: Category / Attribute / Value separation, category-to-attribute relationships, mappings, stable taxonomy source-of-truth/distribution architecture.
- S1 decision: **SELECTED_AS_ARCHITECTURE_AND_DATA_MODEL_REFERENCE**.
- Reuse mode: architecture/data-structure reference first; evaluate consuming versioned taxonomy data or a dependency in S2 only if it maps cleanly to project contracts.
- Not selected: copying a large taxonomy implementation into project-specific core.
- Protection: project Semantic Roles remain business semantics for route analysis; external taxonomy values must not silently become primary routes.

### 3.2 OA-Mine

- Repository: `xinyangz/OAMine`
- License classification: `DIRECT_REUSE_ALLOWED` / Apache-2.0.
- Relevant concepts: open-world e-commerce attribute mining from product titles, candidate generation and attribute-value grouping.
- S1 decision: **SELECTED_AS_RESEARCH_ARCHITECTURE / FUTURE_BOUNDED_POC_CANDIDATE**.
- Reuse mode: architecture and bounded component evaluation; no wholesale integration during S1.
- Reason: the project needs open-world vocabulary discovery for unfamiliar categories, but authoritative production mapping still requires governed roles/profiles and determinism.
- Protection: any future adapted/copied Apache-2.0 code must preserve attribution/license obligations and be isolated behind project contracts/tests.

### 3.3 RapidFuzz

- Repository: `rapidfuzz/RapidFuzz`
- License classification: `DEPENDENCY_REUSE_ALLOWED` / MIT.
- Relevant concepts: fast normalized string similarity and fuzzy phrase matching.
- S1 decision: **SELECTED_AS_POTENTIAL_S2_DEPENDENCY**.
- Intended use: alias candidates, punctuation/spacing normalization, typo-tolerant candidate mapping.
- Forbidden use: a fuzzy score alone must never establish a governed attribute fact, Product Role or primary Product Route.
- Determinism requirement: preprocessing, thresholds, tie-breaking and accepted candidate sets must be versioned and deterministic.

### 3.4 scikit-learn

- Repository: `scikit-learn/scikit-learn`
- License classification: `DEPENDENCY_REUSE_ALLOWED` / BSD-3-Clause.
- Relevant concepts: distance/similarity transforms, clustering, validation/stability and representative-selection primitives.
- S1 decision: **SELECTED_AS_POTENTIAL_ROUTE_V2_DEPENDENCY; NO_ALGORITHM_SELECTED_YET**.
- Reason: selecting clustering before semantic representation is frozen risks reproducing the current category/feature conflation with a more complex algorithm.
- Protection: any later estimator must use fixed randomness where applicable, canonical post-labeling, permutation-stability tests and business-semantic validation.

### 3.5 OpenTag 2019

- Repository: `hackerxiaobai/OpenTag_2019`
- License classification: `REFERENCE_ONLY` because repository license metadata is unavailable/unclear in the audit.
- Relevant concept: attribute-value extraction from product titles.
- S1 decision: **REFERENCE_ONLY — NO CODE COPY**.
- Allowed use: paper/architecture/test-idea review only.

## 4. Selection summary

| Candidate | Classification | S1 selection |
| --- | --- | --- |
| Existing project evidence/provenance/determinism | Internal reuse | Retain and extend |
| Existing SP-041D market metrics | Internal reuse | Retain as-is |
| Shopify Product Taxonomy | MIT | Architecture/data-model reference; future bounded data reuse evaluation |
| OA-Mine | Apache-2.0 | Research architecture / bounded future PoC |
| RapidFuzz | MIT | Potential S2 dependency for candidate/alias matching |
| scikit-learn | BSD-3-Clause | Potential Route V2 dependency after semantic representation is frozen |
| OpenTag 2019 | No clear license | Reference only; no code copy |

**NO_PRODUCTION_ALGORITHM_SELECTED_IN_S1.**

S1 intentionally does not select a production clustering method and does not introduce a new algorithm dependency. The first deliverable is a stable semantic representation and evidence policy; algorithms are evaluated only after those contracts are calibrated across real categories.

## 5. Attribution, security and maintenance rules

1. Prefer direct dependency use over copying permissively licensed algorithm implementations.
2. If any permissively licensed code/data is copied or adapted later, preserve required license notices/attribution and record exact source/version.
3. Unclear/no-license repositories remain architecture references only.
4. External taxonomy/ML dependencies must be pinned/versioned according to repository dependency policy and protected by deterministic regression tests.
5. No external project may bypass project Evidence/Provenance, Availability, privacy, or canonical identity contracts.
6. No public dependency may receive private market rows through tests or CI.
7. Public dependency outputs are candidates/signals unless an explicit governed contract promotes them to facts.

## 6. Migration boundary for S2 / Route V2

### Preserve

`SellerSprite import -> governed market dataset -> evidence/provenance -> deterministic identity`

and, after route membership exists:

`route membership -> listing/sales share -> demand efficiency -> growth -> review/price distributions -> concentration -> opportunity scorecard`

### Refactor

`listing evidence -> source relationship -> normalized attribute/value -> Semantic Role -> Product Role -> route eligibility -> route membership`

This boundary minimizes change to accepted numerical and delivery layers while directly addressing the business-review failure mode.

## 7. Current acceptance status

This audit satisfies only the reuse/design portion of Issue #55. It does **not** promote SP-041S1 to PASS.

Remaining hard gate: execute privacy-safe calibration across multiple materially different real categories, produce aggregate evidence matrices, derive justified V2 acceptance thresholds, and complete bounded operator review.

Current status remains:

`IN_PROGRESS — PRIVATE_MULTI_CATEGORY_CALIBRATION_REQUIRED`
