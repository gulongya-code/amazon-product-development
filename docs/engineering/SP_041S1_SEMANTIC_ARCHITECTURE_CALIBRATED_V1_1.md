# SP-041S1 Semantic Architecture — Calibrated V1.1

Status: **CALIBRATION_REVISED_AND_FROZEN_FOR_S2 DESIGN**

This document is the post-calibration authoritative architecture for Issue #55. It supersedes the pre-calibration Product Role assumptions in `SP_041S1_SEMANTIC_ARCHITECTURE_V1_1.md` where the two differ. The earlier file remains as an audit trail of the proposal that entered real calibration.

## 1. Governing architecture

```text
Evidence Source
    -> Observed Attribute / Value
    -> Evidence Relationship
    -> Universal Semantic Role
    -> Product Identity
    -> Product Role
         |- relation_role
         `- consumption_lifecycle
    -> System-specific Cohort Eligibility
    -> Route Eligibility / Facets
    -> Deterministic Product Route
    -> Market Metrics
    -> LLM Explanation
```

The cross-system rule remains:

> Share what a product fact or phrase means; keep what each system does with that meaning system-specific.

## 2. Core invariants

1. Product understanding precedes route discovery.
2. Evidence source and semantic meaning are separate.
3. There is no universal source-priority order that is correct for every semantic dimension.
4. Title is first-class evidence for Product Identity and Product Role.
5. Structured/dedicated fields remain strong evidence for exact specifications only when source semantics, quantity kind and scope are valid.
6. Missing evidence is unavailable, not false/zero and not automatically review-required.
7. Evidence must be checked for semantic dimension and coexistence before source preference is applied.
8. Product Role is not target-market membership.
9. Product Role cannot be represented safely by one mutually exclusive enum when relationship and consumption lifecycle are mixed.
10. Material, functional features, cosmetic attributes, quantity and lifecycle are facet-only by default for primary-product route discovery.
11. Only identity/role/route-critical ambiguity may block primary-route assignment.
12. Category onboarding changes versioned profile/configuration, not generic engine code.
13. LLM proposals are non-authoritative until governed promotion/validation.

## 3. Evidence-source taxonomy

Minimum logical sources:

- `LISTING_TITLE`
- `STRUCTURED_PARAMETERS`
- `DEDICATED_GOVERNED_FIELD`
- `AUTHORIZED_SKU`
- `BULLET_OR_ITEM_HIGHLIGHT`
- `TARGETED_ENRICHMENT`
- `LLM_DERIVED_CANDIDATE`

Every dimension policy must declare:

- primary evidence sources;
- corroborating sources;
- safe fallback sources;
- forbidden inference sources;
- exact-specification preference;
- multi-value/coexistence behavior;
- conflict behavior;
- missingness/route-critical behavior;
- route relevance.

### 3.1 Calibrated source policy

- **Product Identity / relation role:** Title is primary/co-primary. Structured/category evidence corroborates when authorized.
- **Exact size/dimensions/capacity:** structured/dedicated numeric evidence is primary only after quantity-kind/scope validation; Title is fallback/corroboration.
- **Compatibility:** Title and structured fields may both be primary/co-primary; model/host boundaries are preserved.
- **Functional features / buyer-facing use:** Title/Bullets are normally primary market-semantic evidence; structured fields corroborate.
- **Provider category path:** context/corroboration, never universal product-identity authority.

## 4. Evidence relationship model

Frozen states:

- `AGREES`
- `COMPLEMENTARY`
- `COMPATIBLE_MULTI_VALUE`
- `SOURCE_ONLY_TITLE`
- `SOURCE_ONLY_STRUCTURED`
- `UNAVAILABLE`
- `TRUE_CONFLICT`
- `ROUTE_CRITICAL_CONFLICT`

Required evaluation order:

```text
same semantic question?
    -> can values coexist?
        -> normalize / validate quantity kind and scope
            -> classify relationship
                -> then apply dimension-specific source preference
```

A global `structured always wins` shortcut is prohibited.

## 5. Universal Semantic Role V1.1

Frozen semantic roles:

- `PRODUCT_IDENTITY`
- `PRODUCT_ROLE`
- `STRUCTURAL_FORM`
- `USAGE_ARCHITECTURE`
- `INSTALLATION_ARCHITECTURE`
- `ATTACHMENT_MECHANISM`
- `OPERATION_MECHANISM`
- `POWER_MODE`
- `COMPATIBILITY`
- `MATERIAL`
- `SIZE_CAPACITY`
- `QUANTITY`
- `FUNCTIONAL_FEATURE`
- `COSMETIC`

### 5.1 Default route relevance

| Role | Default relevance |
| --- | --- |
| `PRODUCT_IDENTITY` | `CORE_GATE` |
| `PRODUCT_ROLE.relation_role` | `CORE_GATE` |
| `STRUCTURAL_FORM` | `CORE_OR_SECONDARY` |
| `USAGE_ARCHITECTURE` | `CORE_OR_SECONDARY` |
| `INSTALLATION_ARCHITECTURE` | `CORE_OR_SECONDARY` |
| `ATTACHMENT_MECHANISM` | `CORE_OR_SECONDARY` |
| `OPERATION_MECHANISM` | `CORE_OR_SECONDARY` |
| `POWER_MODE` | `CONDITIONAL_CORE` |
| `COMPATIBILITY` | `CONDITIONAL_CORE` |
| `MATERIAL` | `FACET_ONLY` |
| `SIZE_CAPACITY` | `SECONDARY_OR_FACET` |
| `QUANTITY` | `FACET_ONLY` |
| `FUNCTIONAL_FEATURE` | `FACET_ONLY` |
| `COSMETIC` | `FACET_ONLY` |
| `PRODUCT_ROLE.consumption_lifecycle` | `FACET_ONLY` by default |

## 6. Calibrated Product Role contract

`PRODUCT_ROLE` is a semantic object containing at least two orthogonal facts.

### 6.1 `relation_role`

Required vocabulary:

- `PRIMARY_PRODUCT`
- `ACCESSORY`
- `REPLACEMENT`
- `REFILL`
- `BUNDLE`
- `UNKNOWN`
- `REVIEW_REQUIRED`

`relation_role` answers the product's relationship/composition role and is the role used by APD to gate the main primary-product universe.

Rules:

1. Evidence-backed with provenance.
2. Title is normally a major source.
3. Compatibility wording must distinguish ordinary compatibility from replacement intent.
4. Included accessories do not change a primary product into an accessory.
5. Pack count alone never establishes `BUNDLE`.
6. Missing material/color/quantity/non-critical feature evidence does not change relation role.
7. `UNKNOWN` is a valid fail-closed state.

### 6.2 `consumption_lifecycle`

Required vocabulary:

- `REUSABLE_DURABLE`
- `CONSUMABLE`
- `PERIODIC_REPLACEMENT`
- `UNKNOWN`
- `REVIEW_REQUIRED`

This field answers lifecycle/replenishment behavior and does not replace `relation_role`.

Examples:

- liner/paper: `ACCESSORY + CONSUMABLE`
- disposable bag: `REFILL + CONSUMABLE`
- replaceable filter: `REPLACEMENT + PERIODIC_REPLACEMENT`
- replacement hook/plate: `REPLACEMENT + REUSABLE_DURABLE`

Missing lifecycle evidence must remain unavailable/unknown rather than defaulting to durable.

## 7. Market membership boundary

The private calibration states `CORE_TARGET / RELATED_TARGET / ACCESSORY_MARKET / OTHER_PRODUCT` proved useful for operator review but are **not Shared Semantic Core facts**.

Shared core owns intrinsic facts:

- Product Identity;
- relation role;
- lifecycle;
- compatibility;
- attributes/values/evidence.

APD owns the system-specific projection:

`intrinsic shared facts -> Market Cohort Eligibility -> Route Discovery`

KWS owns its own projection:

`intrinsic shared facts + query claims -> Relevance / Hard Conflict / Listing / PPC`

## 8. Quantity semantics

`QUANTITY` must preserve subtype/scope, at minimum:

- `PACKAGE_COUNT`
- `STRUCTURAL_COMPONENT_COUNT`
- `CONSUMABLE_UNIT_COUNT`

A count of packs/units is not equivalent to shelves/pockets/compartments/layers/sheets. Quantity is facet-only by default.

## 9. Size / capacity semantics

`SIZE_CAPACITY` must preserve quantity kind and semantic scope.

Minimum concepts:

- volume;
- mass/load capacity;
- length/dimensions;
- item capacity;
- host-device capacity when evidence refers to a compatible/parent product rather than the observed accessory.

A source key named `capacity` does not establish a volume fact by itself.

## 10. Category Semantic Profile contract

A strict versioned profile must express:

```text
profile_id / version / category_scope
source_policy_by_semantic_dimension
attribute_aliases / value_aliases
negative / exclusion rules
source_authorization
observed attribute -> Universal Semantic Role mapping
role relevance: CORE | SECONDARY | FACET_ONLY | IGNORE
Product Role relation rules
consumption lifecycle rules where material
coexistence rules
true-conflict rules
route-critical conflict rules
quantity-kind / scope rules
normalization/version metadata
canonical fingerprint
```

Constraints:

- no category-specific branch in generic Python solely to create route membership;
- profile teaches vocabulary/semantics, not final route A/B/C labels;
- changes are versioned, deterministic and auditable;
- LLM proposals cannot silently mutate an accepted profile.

## 11. Calibrated category relevance direction

The five-category real corpus supports these profile directions:

- **Shower Caddy:** Installation/Attachment are route-core; Material/Feature/Quantity remain facets.
- **Dog Water Bottle:** Operation and coarse Capacity are secondary/conditional route semantics; Material/Quantity/Cosmetic remain facets.
- **Vacuum Filter:** Compatibility is route-core; relation role is a critical gate; lifecycle is useful secondary evidence; Material remains facet-only.
- **Food Storage Container Sets:** Structural Form and coarse Capacity may be secondary/core depending on market universe; Quantity remains a facet rather than Bundle authority.
- **Air Fryer mixed market:** Structural Form and Operation are core; accessory/replacement/refill relation gating is mandatory; lifecycle is secondary for non-primary cohorts; ordinary use-case mentions must not create market membership.

Final strict profile values are S2 configuration work and must be validated without generic-engine code changes.

## 12. Route eligibility

Primary route identity may use recurring combinations of:

- Product Identity;
- Structural Form;
- Usage Architecture;
- Installation Architecture;
- Attachment Mechanism;
- Operation Mechanism;
- conditional Power Mode;
- conditional Compatibility;
- coarse Size/Capacity only when the category profile proves architectural relevance.

Facet-only by default:

- Material;
- Functional Feature;
- Cosmetic;
- Quantity;
- consumption lifecycle;
- ordinary variant attributes.

A selected candidate route must differ from another selected candidate on at least one route-eligible semantic role. `facet-only distinctness = 0` is a hard design requirement.

## 13. LLM authority and token contract

Allowed:

- open-world attribute/value candidate proposals;
- mapping unfamiliar phrases to existing Universal Semantic Roles;
- candidate vocabulary normalization/grouping for governed approval;
- route naming/explanation after deterministic membership exists;
- bounded later review/buyer-need summarization.

Forbidden:

- governed market metric calculation;
- invention of missing hard facts;
- overwriting governed evidence;
- sole authority for primary route membership;
- silent Semantic Profile mutation;
- making a selling feature route-core solely because it is textually salient.

Budget for a normal ~1,000-listing study:

- target `100k–150k` tokens;
- soft `200k`;
- hard `300k` unless explicitly overridden;
- model/prompt/version/purpose/token accounting required.

## 14. Migration boundary

### Retain as-is

- SP-041A template contracts;
- SP-041B governed ingestion/dataset;
- provenance/evidence foundations;
- availability/missingness discipline;
- canonical JSON / deterministic identity / fingerprints;
- SP-041D denominator-safe market metrics;
- privacy/secret/network controls.

### Extend in S2

- Product Attribute Map -> Semantic Fact / Universal Semantic Role projection;
- CategoryRulePack responsibilities -> Category Semantic Profile;
- evidence relationship/conflict representation;
- Product Role relation/lifecycle facts;
- APD market-cohort eligibility;
- route candidate diversity based only on route-eligible semantics.

### Replace in V2

- global evidence precedence shortcut;
- exact-known-structural-attribute signature as the primary route identity engine;
- listing-wide Review caused by ordinary missing non-critical facets.

### Deprecate after V2

- route identity split by Material/Functional Feature/Cosmetic/Quantity unless explicitly promoted by calibrated profile evidence.

## 15. Revised development sequence

1. **SP-041S1** — calibration/design/reuse gate.
2. **S2 — Semantic Engine V2** — implement the calibrated listing-side semantic reference in `amazon-product-development`.
3. **Route Discovery V2** — consume route-eligible shared semantics and replay the same private corpus against V2 gates.
4. **S3 — Shared Semantic Core Extraction** — extract only proven category-neutral contracts/helpers after S2 stabilizes.
5. **KWS Integration** — add compatibility/query adapters and replay all KWS safety/GT authorities before any cutover.

SP-041E remains frozen until the S1 gate is formally closed and the S2 baseline is authorized.

## 16. S1 calibrated contract verdict

```text
UNIVERSAL_SEMANTIC_ROLE_V1_1 = FROZEN
EVIDENCE_RELATIONSHIP_MODEL_V1_1 = FROZEN
GLOBAL_SOURCE_PRECEDENCE = PROHIBITED
PRODUCT_ROLE_RELATION_ROLE = FROZEN
PRODUCT_ROLE_CONSUMPTION_LIFECYCLE = FROZEN
MARKET_COHORT_ELIGIBILITY = SYSTEM_SPECIFIC
QUANTITY_SUBTYPE_SCOPE = REQUIRED
SIZE_CAPACITY_QUANTITY_KIND_SCOPE = REQUIRED
CATEGORY_SEMANTIC_PROFILE_CONTRACT = FROZEN
FACET_ONLY_DEFAULT_POLICY = FROZEN
LLM_AUTHORITY_BOUNDARY = FROZEN
SEMANTIC_ENGINE_V2_IMPLEMENTATION = NOT_STARTED_IN_S1
```
