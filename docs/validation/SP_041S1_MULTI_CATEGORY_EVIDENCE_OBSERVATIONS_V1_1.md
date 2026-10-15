# SP-041S1 Multi-Category Evidence Observations V1.1

Status: **PRELIMINARY_REAL_DATA_OBSERVATIONS — OPERATOR REVIEW PENDING**

This document records privacy-safe aggregate observations from the five qualified private calibration categories. It is not a production rule source, does not contain private listing rows, and does not claim final `AGREES / COMPLEMENTARY / CONFLICT` labels before bounded operator review.

## 1. Corpus

| Calibration category | Listings |
| --- | ---: |
| Shower Caddy | 998 |
| Dog Water Bottle | 400 |
| Vacuum Filter | 300 |
| Food Storage Container Sets | 150 |
| Air Fryer mixed market sample | 300 |
| **Total** | **2,148** |

The separate cross-category `Bundle` search export remains excluded from the formal category corpus.

## 2. Evidence-source availability

| Category | Title observed | Structured `详细参数` observed | Rows with deterministic detail-parse issue | Explicit structured `Product Type` / `Item Type` key |
| --- | ---: | ---: | ---: | ---: |
| Shower Caddy | 998 / 998 (100.00%) | 998 / 998 (100.00%) | 17 / 998 (1.70%) | 0 / 998 (0.00%) |
| Dog Water Bottle | 400 / 400 (100.00%) | 400 / 400 (100.00%) | 29 / 400 (7.25%) | 0 / 400 (0.00%) |
| Vacuum Filter | 300 / 300 (100.00%) | 300 / 300 (100.00%) | 9 / 300 (3.00%) | 0 / 300 (0.00%) |
| Food Storage Container Sets | 150 / 150 (100.00%) | 149 / 150 (99.33%) | 5 / 150 (3.33%) | 0 / 150 (0.00%) |
| Air Fryer mixed | 300 / 300 (100.00%) | 300 / 300 (100.00%) | 9 / 300 (3.00%) | 0 / 300 (0.00%) |

A parse-issue row is not automatically a rejected listing. The accepted SP-041C detailed-parameter parser retains usable pairs and reports malformed segments explicitly.

### Immediate architecture finding

`PRODUCT_IDENTITY` and `PRODUCT_ROLE` cannot use a universal `structured parameters > Title` precedence rule in this corpus. Buyer-facing Title is present on every listing while the structured detail field provides no explicit `Product Type` / `Item Type` key in any of the 2,148 rows.

Decision candidate for V1.1:

> Title is a first-class primary evidence source for Product Identity and Product Role. Structured parameters may corroborate or constrain those roles where an authorized dimension/key exists, but absence of a structured product-type field must not force Review.

## 3. Conservative structured-role coverage

The following table uses only a conservative, key-driven calibration projection. It is not a future runtime ontology. Mapped keys are restricted to semantically obvious source fields such as `material`, `capacity`, `mounting type`, `compatible devices`, `power source`, `special feature`, explicit package-count fields, etc.

Each cell is `listings with mapped structured evidence / category listings`.

| Candidate Semantic Role | Shower Caddy | Dog Water Bottle | Vacuum Filter | Food Storage Sets | Air Fryer mixed |
| --- | ---: | ---: | ---: | ---: | ---: |
| MATERIAL | 928 / 998 (93.0%) | 355 / 400 (88.8%) | 237 / 300 (79.0%) | 131 / 150 (87.3%) | 257 / 300 (85.7%) |
| SIZE_CAPACITY | 920 / 998 (92.2%) | 326 / 400 (81.5%) | 205 / 300 (68.3%) | 116 / 150 (77.3%) | 163 / 300 (54.3%) |
| QUANTITY | 209 / 998 (20.9%) | 39 / 400 (9.8%) | 49 / 300 (16.3%) | 10 / 150 (6.7%) | 125 / 300 (41.7%) |
| USAGE_ARCHITECTURE | 885 / 998 (88.7%) | 55 / 400 (13.8%) | 1 / 300 (0.3%) | 25 / 150 (16.7%) | 23 / 300 (7.7%) |
| INSTALLATION_ARCHITECTURE | 840 / 998 (84.2%) | 0 / 400 | 0 / 300 | 0 / 150 | 5 / 300 (1.7%) |
| POWER_MODE | 0 / 998 | 28 / 400 (7.0%) | 40 / 300 (13.3%) | 0 / 150 | 0 / 300 |
| COMPATIBILITY | 0 / 998 | 0 / 400 | 231 / 300 (77.0%) | 0 / 150 | 0 / 300 |
| FUNCTIONAL_FEATURE | 899 / 998 (90.1%) | 51 / 400 (12.8%) | 250 / 300 (83.3%) | 112 / 150 (74.7%) | 126 / 300 (42.0%) |
| STRUCTURAL_FORM | 1 / 998 (0.1%) | 7 / 400 (1.8%) | 0 / 300 | 5 / 150 (3.3%) | 112 / 300 (37.3%) |
| COSMETIC | 970 / 998 (97.2%) | 360 / 400 (90.0%) | 40 / 300 (13.3%) | 138 / 150 (92.0%) | 172 / 300 (57.3%) |

### Interpretation boundary

A zero in this table means **the conservative structured-key projection did not observe that role**. It does not mean the product lacks the semantic property. Title or other evidence may still express it.

## 4. Literal Title echo — lower-bound observation only

For listings with mapped structured evidence, calibration also measured whether at least one normalized structured value is literally echoed in the Title. This is only a lower-bound evidence-overlap diagnostic; it is **not** Semantic `AGREES` and it must not classify non-echo as conflict.

Examples of structured-evidence cohorts with literal Title echo:

| Role / category | Structured cohort | Literal Title echo | Echo rate within structured cohort |
| --- | ---: | ---: | ---: |
| MATERIAL — Shower Caddy | 928 | 292 | 31.5% |
| MATERIAL — Dog Water Bottle | 355 | 116 | 32.7% |
| MATERIAL — Vacuum Filter | 237 | 20 | 8.4% |
| MATERIAL — Food Storage Sets | 131 | 74 | 56.5% |
| MATERIAL — Air Fryer mixed | 257 | 80 | 31.1% |
| SIZE_CAPACITY — Shower Caddy | 920 | 2 | 0.2% |
| SIZE_CAPACITY — Dog Water Bottle | 326 | 1 | 0.3% |
| SIZE_CAPACITY — Vacuum Filter | 205 | 0 | 0.0% |
| SIZE_CAPACITY — Food Storage Sets | 116 | 4 | 3.4% |
| SIZE_CAPACITY — Air Fryer mixed | 163 | 6 | 3.7% |
| COMPATIBILITY — Vacuum Filter | 231 | 23 | 10.0% |
| INSTALLATION_ARCHITECTURE — Shower Caddy | 840 | 106 | 12.6% |
| QUANTITY — Air Fryer mixed | 125 | 80 | 64.0% |

### Finding

Exact specifications are frequently present in structured evidence without literal duplication in Title. Therefore:

- Title non-echo must not become disagreement;
- Title and structured evidence should first be tested for same semantic dimension and coexistence;
- exact specification authority may remain structured-first for dimensions such as parsed capacity/dimensions/compatibility when the source contract is clear;
- Product Identity / Product Role must not inherit that same precedence automatically.

## 5. Cross-category architecture findings requiring S1 resolution

### 5.1 Product Role and target-market membership are separate

The mixed real samples contain all of the following patterns:

- a genuine target product;
- an accessory/replacement/refill for the target product;
- a standalone primary product with a different Product Identity that merely mentions the target term;
- a product placed in a provider/category node whose Title implies a different identity.

A `PRIMARY_PRODUCT` role alone does not mean the listing belongs to the intended Product Route market. V1.1 therefore needs both:

1. Product Identity / category-semantic membership; and
2. intrinsic Product Role.

### 5.2 `CONSUMABLE` is a Product Role candidate

The Air Fryer mixed sample contains a large consumable-liner cohort. Treating those rows as ordinary primary Air Fryers is unsafe, while `REFILL` is not a natural description for every consumable accessory.

S1 operator review must decide whether to:

- add `CONSUMABLE` as a distinct Product Role; or
- define an explicit governed mapping of consumables into `ACCESSORY` / `REFILL` without ambiguity.

No enum change is authorized by this preliminary observation alone.

### 5.3 `QUANTITY` requires subtype separation

Real fields include package quantity as well as structural counts. Examples of semantic classes include:

- number of items / packs / unit count;
- number of compartments / shelves;
- sheet count for consumables.

These values cannot be collapsed into one route-defining quantity. V1.1 should distinguish at least package/commercial quantity from structural component count, while keeping both under auditable semantic facts.

### 5.4 `SIZE_CAPACITY` requires quantity-kind/context semantics

A source key named `capacity` is not globally a volume field. Across categories it may represent volume or load/weight capacity. Existing SP-041C measurement parsing already fails closed on ambiguous units such as unqualified `oz`; V1.1 should preserve that discipline rather than making `capacity` globally equivalent to liquid volume.

### 5.5 Semantic Roles are category-conditional in evidence availability

The real corpus strongly supports the Category Semantic Profile concept:

- installation evidence is dominant in Shower Caddies and nearly absent elsewhere;
- compatibility evidence is dominant in Vacuum Filters and absent in the other four conservative structured projections;
- operation/power evidence is sparse or expressed outside one universal structured key;
- material/cosmetic evidence is common but usually should not define primary route identity by default.

Adding category-specific keywords to generic Python code would encode the wrong abstraction level.

## 6. Operator-review gate

A deterministic private 60-row review cohort has been generated outside Git:

- 12 rows per formal calibration category;
- balanced where possible across `CORE_TARGET`, `RELATED_TARGET`, `ACCESSORY_MARKET`, and `OTHER_PRODUCT` observations;
- Assistant proposals are explicitly non-authoritative;
- operator fields capture `ACCEPT / OVERRIDE / REVIEW`, final target-market membership and Product Role.

The review specifically tests:

- Product Role versus Product Identity separation;
- accessory/replacement/refill boundaries;
- whether `CONSUMABLE` is needed;
- set/multipack versus true Bundle;
- provider-category noise;
- target-market boundary behavior.

Private row content is intentionally absent from this repository document.

## 7. Current verdict

```text
PRIVATE_MULTI_CATEGORY_ASSETS = AVAILABLE
PRELIMINARY_SOURCE_COVERAGE = COMPLETE
CROSS_SYSTEM_REUSE_AUDIT = COMPLETE
OPERATOR_PRODUCT_ROLE_BOUNDARY_REVIEW = PENDING
FINAL_EVIDENCE_RELATIONSHIP_MATRIX = PENDING
V2_NUMERIC_ACCEPTANCE_GATES = PENDING
SP_041S1_PASS = NOT YET AUTHORIZED
```

Next: complete bounded operator review, aggregate the accepted outcomes, then freeze the final V1.1 Product Role/evidence-source policy and derive Semantic Engine V2 / Route Discovery V2 gates.
