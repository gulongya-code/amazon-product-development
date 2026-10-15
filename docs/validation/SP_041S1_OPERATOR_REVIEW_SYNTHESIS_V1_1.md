# SP-041S1 Operator Review Synthesis V1.1

Status: **COMPLETE — PRODUCT-ROLE BOUNDARY CALIBRATED; RAW REVIEW ASSET REMAINS PRIVATE**

## 1. Purpose and privacy boundary

This document records privacy-safe conclusions from the bounded operator review required by Issue #55. The private review workbook and all listing-grain evidence remain outside Git.

No ASIN, listing title, brand, seller, price, raw row, private path, or customer/user identifier is included here.

## 2. Review cohort

The private review cohort contained `60` rows:

- `12` Shower Caddy calibration rows;
- `12` Dog Water Bottle calibration rows;
- `12` Vacuum Filter calibration rows;
- `12` Food Storage Container Sets calibration rows;
- `12` Air Fryer mixed-market calibration rows.

The cohort deliberately included core products, related products, accessories/replacements/refills, and off-target products found inside real market/search/category exports.

## 3. Raw operator decision result

| Decision state | Count | Rate |
| --- | ---: | ---: |
| `ACCEPT` / 接受建议 | 46 | 76.67% |
| `MODIFY` / 修改 | 10 | 16.67% |
| malformed/unresolved cell content | 4 | 6.67% |
| explicit `REVIEW` | 0 | 0.00% |
| **Total** | **60** | **100.00%** |

The malformed cells contained a non-semantic numeric entry and are excluded from semantic conclusions rather than silently interpreted.

### 3.1 Interpretation of the 10 MODIFY rows

The `MODIFY` count must not be treated as a model-error count.

- `7/10` MODIFY rows repeated the already-present corrected Market Scope / Product Role proposal without a semantic label change;
- `2/10` materially changed the single Product Role label to a consumable interpretation;
- `1/10` preserved the Market Scope correction but contained an invalid Product Role override.

This behavior is itself calibration evidence: the one-dimensional Product Role field was forcing the operator to choose between **relationship-to-host** semantics and **consumption/replenishment** semantics.

## 4. Calibrated architecture finding — Product Role must be orthogonalized

The pre-calibration Product Role vocabulary mixed at least two different semantic questions:

1. **What is the product's relationship to a host/primary product?**
2. **How is the item consumed, replenished, or replaced over its service life?**

A single mutually exclusive enum cannot represent real products safely.

Examples, expressed generically rather than with private listing rows:

| Product pattern | Relation role | Consumption lifecycle |
| --- | --- | --- |
| paper/liner used with an appliance | `ACCESSORY` | `CONSUMABLE` |
| disposable collection bag | `REFILL` | `CONSUMABLE` |
| replaceable filter | `REPLACEMENT` | `PERIODIC_REPLACEMENT` |
| replacement hook/plate | `REPLACEMENT` | `REUSABLE_DURABLE` |
| main appliance/container/caddy | `PRIMARY_PRODUCT` | normally `REUSABLE_DURABLE` when evidence supports it |

### 4.1 Frozen V1.1 Product Role composition

`PRODUCT_ROLE` remains the umbrella semantic concept, but Semantic Engine V2 must represent at least these orthogonal fields.

#### A. `relation_role` — required for primary-product cohort gating

- `PRIMARY_PRODUCT`
- `ACCESSORY`
- `REPLACEMENT`
- `REFILL`
- `BUNDLE`
- `UNKNOWN`
- `REVIEW_REQUIRED`

Rules:

1. `relation_role` is evidence-backed and preserves provenance.
2. Quantity alone never establishes `BUNDLE`.
3. Replacement wording must not be collapsed into ordinary accessory semantics.
4. Included components do not turn a primary product into an accessory.
5. `ACCESSORY / REPLACEMENT / REFILL` are excluded from the main primary-product route universe unless the APD operator explicitly requests that market universe.

#### B. `consumption_lifecycle` — orthogonal semantic fact

Minimum vocabulary:

- `REUSABLE_DURABLE`
- `CONSUMABLE`
- `PERIODIC_REPLACEMENT`
- `UNKNOWN`
- `REVIEW_REQUIRED`

Rules:

1. Lifecycle does not replace `relation_role`.
2. A filter may be both `REPLACEMENT` and `PERIODIC_REPLACEMENT`.
3. A liner may be both `ACCESSORY` and `CONSUMABLE`.
4. A refill bag may be both `REFILL` and `CONSUMABLE`.
5. Lifecycle is `FACET_ONLY` by default for primary-product route discovery; a Category Semantic Profile may promote it only for a market whose product identity is itself defined by replenishment/consumption behavior.
6. Missing lifecycle evidence remains unavailable/unknown rather than defaulting to durable.

## 5. Calibrated architecture finding — target-market membership is not Product Role

The review confirmed that these are separate concepts:

- a standalone product may be `PRIMARY_PRODUCT` intrinsically but still be outside the intended market;
- a replacement component may be inside a replacement-part market while not being a primary product relative to its host device;
- provider category/search membership may contain off-target product identities;
- a title may mention the target product merely as a use case.

Therefore Shared Semantic Core must own intrinsic facts such as `PRODUCT_IDENTITY` and `PRODUCT_ROLE`, while APD retains system-specific authority for **market-cohort eligibility**.

The private calibration labels `CORE_TARGET / RELATED_TARGET / ACCESSORY_MARKET / OTHER_PRODUCT` are calibration/business-layer labels and are **not** promoted into a universal shared-core enum.

Target architecture:

```text
Shared facts:
PRODUCT_IDENTITY + relation_role + consumption_lifecycle + evidence
        |
        v
APD-specific Market Cohort Eligibility
        |
        v
Primary Product Route Discovery / accessory-market analysis
```

This preserves the cross-system rule:

> Share what a product fact means; keep what each system does with the fact system-specific.

## 6. Evidence-source conclusions from bounded review

The operator review and the 2,148-listing aggregate observations jointly support these policies.

### 6.1 Product Identity / Product Role

- Title is a primary/co-primary source.
- Provider/category-node placement is corroborating context, not universal authority.
- Structured parameters may corroborate identity/role when an authorized key exists.
- The absence of a structured `Product Type` / `Item Type` field must not force Review.
- A provider category path that disagrees with clear buyer-facing identity/compatibility evidence must be preserved as conflicting evidence rather than silently overriding Title.

### 6.2 Exact specification dimensions

For exact material/size/capacity/compatibility facts, structured or dedicated fields remain strong/primary sources when their quantity kind and semantic scope are valid.

However the real corpus exposed provider-field semantic contamination cases, including a key named `capacity` carrying a mass-like value. Therefore:

- source key name alone is insufficient;
- quantity kind/unit and product scope must be validated;
- invalid/mismatched quantity kinds fail closed;
- inherited host-device specifications must not silently become accessory-item specifications.

### 6.3 Evidence relationship model survives calibration

The required relationship states remain valid:

- `AGREES`
- `COMPLEMENTARY`
- `COMPATIBLE_MULTI_VALUE`
- `SOURCE_ONLY_TITLE`
- `SOURCE_ONLY_STRUCTURED`
- `UNAVAILABLE`
- `TRUE_CONFLICT`
- `ROUTE_CRITICAL_CONFLICT`

The review confirmed the need to classify semantic dimension/coexistence before applying source preference. Real examples included:

- title identity plus structured exact specifications as complementary evidence;
- category-placement noise versus direct product-identity evidence;
- same-dimension material disagreement;
- quantity-kind/context mismatch in structured capacity evidence;
- compatible multiple uses/features that must not be forced into conflict.

Private examples remain outside the repository.

## 7. Quantity and capacity contract refinements

### 7.1 Quantity

`QUANTITY` remains a Universal Semantic Role but must preserve subtype/scope, at minimum:

- `PACKAGE_COUNT` — pack/unit commercial quantity;
- `STRUCTURAL_COMPONENT_COUNT` — shelves, pockets, compartments, layers, etc.;
- `CONSUMABLE_UNIT_COUNT` — sheets/bags/pods/etc. where lifecycle semantics matter.

These are not interchangeable and are `FACET_ONLY` by default.

### 7.2 Size/Capacity

`SIZE_CAPACITY` must preserve quantity kind and scope rather than treating the literal source key `capacity` as volume.

Minimum governed concepts include:

- volume capacity;
- mass/load capacity;
- dimensions/length;
- host-device capacity versus item capacity where the source can leak parent/compatibility data.

## 8. Category-profile calibration decisions

These are role-relevance decisions, not hard-coded route names.

| Semantic role | Shower Caddy | Dog Water Bottle | Vacuum Filter | Food Storage Sets | Air Fryer mixed |
| --- | --- | --- | --- | --- | --- |
| `PRODUCT_IDENTITY` | CORE_GATE | CORE_GATE | CORE_GATE | CORE_GATE | CORE_GATE |
| `PRODUCT_ROLE.relation_role` | CORE_GATE | CORE_GATE | CORE_GATE | CORE_GATE | CORE_GATE |
| `STRUCTURAL_FORM` | SECONDARY | SECONDARY | SECONDARY | CORE_OR_SECONDARY | CORE |
| `USAGE_ARCHITECTURE` | SECONDARY | SECONDARY | IGNORE_OR_FACET | SECONDARY | SECONDARY |
| `INSTALLATION_ARCHITECTURE` | CORE | IGNORE | IGNORE | IGNORE | IGNORE |
| `ATTACHMENT_MECHANISM` | CORE | SECONDARY | IGNORE | IGNORE | IGNORE |
| `OPERATION_MECHANISM` | SECONDARY | CORE_OR_SECONDARY | IGNORE | IGNORE | CORE |
| `POWER_MODE` | IGNORE | SECONDARY | IGNORE | IGNORE | SECONDARY |
| `COMPATIBILITY` | IGNORE_OR_SECONDARY | IGNORE_OR_SECONDARY | CORE | IGNORE | SECONDARY_FOR_NONPRIMARY |
| `MATERIAL` | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY |
| `SIZE_CAPACITY` | FACET_ONLY | SECONDARY | FACET_ONLY | SECONDARY | SECONDARY |
| `QUANTITY` | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY |
| `FUNCTIONAL_FEATURE` | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY |
| `COSMETIC` | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY | FACET_ONLY |
| `consumption_lifecycle` | FACET_ONLY | FACET_ONLY | SECONDARY | FACET_ONLY | SECONDARY_FOR_NONPRIMARY |

`CORE_OR_SECONDARY`, `IGNORE_OR_SECONDARY`, and `SECONDARY_FOR_NONPRIMARY` are calibration outcomes that S2 must resolve into strict versioned profile values for the chosen market universe. They do not authorize category-specific branches in generic Python code.

## 9. Cross-system impact

For future Shared Semantic Core extraction:

- shared core owns `relation_role` and `consumption_lifecycle` as intrinsic product semantic facts;
- KWS `SearchTargetRole` remains query-side and system-specific;
- KWS may map query-side `ACCESSORY_OR_REPLACEMENT` claims to shared listing-side relation facts but must not collapse the objects;
- APD market-cohort eligibility remains APD-specific;
- KWS Hard Conflict, relevance, Listing/PPC suitability, Brand Evidence and Brand Query Binding remain KWS-specific authorities.

No KWS production cutover is authorized by S1.

## 10. Operator-review verdict

```text
PRIVATE_OPERATOR_REVIEW_ROWS = 60
OPERATOR_ACCEPT_DECISIONS = 46
OPERATOR_MODIFY_DECISIONS = 10
MALFORMED_UNRESOLVED_DECISIONS = 4
EXPLICIT_REVIEW_DECISIONS = 0
PRODUCT_ROLE_SINGLE_ENUM = REJECTED
PRODUCT_ROLE_RELATION_LIFECYCLE_SPLIT = ACCEPTED_FOR_V1_1
TARGET_MARKET_MEMBERSHIP_SEPARATE_FROM_PRODUCT_ROLE = ACCEPTED
QUANTITY_SUBTYPE_REQUIREMENT = ACCEPTED
SIZE_CAPACITY_QUANTITY_KIND_REQUIREMENT = ACCEPTED
RAW_PRIVATE_REVIEW_ASSET_COMMITTED = NO
```

The remaining S1 gate is to freeze evidence-backed V2 quantitative acceptance thresholds, record the calibrated semantic architecture, and complete the final privacy/validation closeout. Semantic Engine V2 / Route Discovery V2 are still not implemented in S1.
