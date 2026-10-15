# SP-041S1 Semantic Architecture V1.1

Status: **PROPOSED_AND_FROZEN_FOR_CALIBRATION — PASS PENDING REAL MULTI_CATEGORY EVIDENCE**

## 1. Objective

Freeze the category-neutral semantic representation that must exist before Semantic Engine V2 and Route Discovery V2 are implemented.

The governing sequence is:

`Evidence Source -> Observed Attribute/Value -> Evidence Relationship -> Universal Semantic Role -> Product Role -> Route Eligibility -> Primary Product Route -> Market Metrics -> LLM Explanation`

The generic engine must not treat literal category keywords as its ontology and must not equate every observed attribute difference with a different product route.

## 2. Core principles

1. **Understand the product before evaluating the market route.**
2. Evidence source and semantic meaning are separate concepts.
3. There is no universal source-priority order that is correct for every semantic dimension.
4. Title is first-class market-semantic evidence; structured/catalog-like parameters remain strong evidence and are normally preferred for exact specifications.
5. Missing evidence is unavailable, not zero, false, old, non-featured, or automatically review-required.
6. Evidence that describes different semantic dimensions may be complementary rather than conflicting.
7. Evidence in the same dimension may be compatible multi-value rather than conflicting.
8. Only ambiguity/conflict that affects Product Identity, Product Role, or route-critical structure should block primary route assignment.
9. Product Route identity is structural/architectural by default. Material, functional selling points, cosmetic attributes and quantity are facets by default unless cross-category calibration justifies an explicit category-specific promotion.
10. Market metrics evaluate a route after membership exists; sales/price/review must not define the product type by themselves.
11. LLM may discover/explain candidates but must not be the sole authority for governed facts or primary route membership.
12. Adding a calibrated category should change configuration/profile data, not generic engine code.

## 3. Evidence-source taxonomy V1.1

The evidence model must support at least these logical sources when available:

| Source | Intended semantic use | Notes |
| --- | --- | --- |
| `LISTING_TITLE` | Product identity, product role, market positioning, usage/installation/operation language, features, compatibility, sometimes material/quantity | First-class market-semantic evidence; brevity/marketing constraints mean it is not a complete specification source. |
| `STRUCTURED_PARAMETERS` | Catalog-like attributes, material, dimensions, size/capacity, compatibility, structured usage/installation fields | Strong for exact/normalized specifications but may be incomplete, constrained or less expressive than buyer-facing text. |
| `DEDICATED_GOVERNED_FIELD` | Explicit SP-041B fields with known semantics | Use according to field-specific contract. |
| `AUTHORIZED_SKU` | Explicitly authorized encoded evidence only | Never assume arbitrary SKU text is semantic evidence. |
| `BULLET_OR_ITEM_HIGHLIGHT` | Market semantics, use cases, functional features, compatibility, included components | Optional source when the governed dataset/provider supplies it. |
| `TARGETED_ENRICHMENT` | Later deep research for a bounded candidate set | Must not become a requirement for broad-market ingestion. |
| `LLM_DERIVED_CANDIDATE` | Candidate vocabulary/role proposal only | Never a hard fact without governed promotion/validation. |

### 3.1 Dimension-aware source policy

Every semantic dimension/profile entry must be able to declare:

- primary evidence source(s);
- corroborating source(s);
- safe fallback source(s);
- forbidden inference source(s);
- whether exact structured values are preferred;
- whether the dimension supports multiple simultaneous values;
- conflict/coexistence rules;
- whether missingness is route-critical;
- route relevance.

Example policy classes, not literal category rules:

- **Product identity / Product Role:** Title is normally primary or co-primary; structured category evidence corroborates.
- **Exact dimensions / weight / capacity:** Structured or dedicated numeric field is normally primary; text is fallback/corroboration.
- **Functional selling point:** Title/Bullet/Highlight normally provide market-facing evidence; structured fields corroborate where present.
- **Compatibility:** Title and structured evidence may both be important; true incompatibility can be route-critical depending on category.

## 4. Evidence relationship and conflict model

Before source preference is applied, evidence items must be compared semantically.

Required relationship states:

| State | Meaning | Default action |
| --- | --- | --- |
| `AGREES` | Sources express the same normalized fact | Merge evidence; raise confidence/coverage according to policy. |
| `COMPLEMENTARY` | Sources express different semantic dimensions or non-competing details | Preserve both. |
| `COMPATIBLE_MULTI_VALUE` | Same dimension legitimately supports more than one simultaneous value | Preserve all governed values. |
| `SOURCE_ONLY_TITLE` | Fact observed only in Title | Accept/hold according to dimension policy; do not erase because structured is missing. |
| `SOURCE_ONLY_STRUCTURED` | Fact observed only in structured/catalog evidence | Accept/hold according to dimension policy. |
| `UNAVAILABLE` | No governed evidence for the dimension | Keep unavailable; do not infer zero/false. |
| `TRUE_CONFLICT` | Same mutually exclusive semantic question receives incompatible values | Preserve both evidence trails and apply dimension-specific resolution/review policy. |
| `ROUTE_CRITICAL_CONFLICT` | A true conflict prevents safe Product Role or route-critical structural assignment | Block primary route assignment and require review/insufficient-evidence state. |

A global rule such as `structured always wins` is prohibited in V2.

## 5. Universal Semantic Role V1.1

The following compact vocabulary is frozen as the calibration target. Exact downstream field names may be versioned, but generic code must preserve these semantic separations.

| Role | Meaning | Multi-value | Default route relevance | Typical evidence | Missing/conflict behavior |
| --- | --- | --- | --- | --- | --- |
| `PRODUCT_IDENTITY` | What the product fundamentally is | Usually bounded | `CORE` | Title + structured category/form evidence | Missing/true conflict is often route-critical. |
| `PRODUCT_ROLE` | Primary product vs accessory/replacement/refill/bundle | Single primary role | `CORE_GATE` | Title + compatibility/included-component evidence | Unresolved role may block primary-route cohort eligibility. |
| `STRUCTURAL_FORM` | Physical architecture/form factor | Sometimes | `CORE` | Title + structured form/shape fields | Missing reduces assignability; conflict can be route-critical. |
| `USAGE_ARCHITECTURE` | How/where the product is used at an architectural level | Multi-value possible | `CORE_OR_SECONDARY` | Title + structured + bullets | Missing is not automatically fatal. |
| `INSTALLATION_ARCHITECTURE` | Installation mode/architecture | Multi-value possible | `CORE_OR_SECONDARY` | Title + structured + bullets | Coexisting modes must not be forced into conflict. |
| `ATTACHMENT_MECHANISM` | Mechanism that fixes/attaches product | Multi-value possible | `CORE_OR_SECONDARY` | Title + structured + bullets | Category profile determines route criticality. |
| `OPERATION_MECHANISM` | How product mechanically/technically operates | Multi-value possible | `CORE_OR_SECONDARY` | Title + structured + bullets | Often route-defining in operation-heavy categories. |
| `POWER_MODE` | Manual/battery/corded/etc. power architecture | Multi-value possible | `CONDITIONAL_CORE` | Structured + Title | Often route-defining for powered categories. |
| `COMPATIBILITY` | Boundary of compatible host/device/object/system | Multi-value | `CONDITIONAL_CORE` | Title + structured + bullets | Can be route-critical for replacement/accessory categories. |
| `MATERIAL` | Material family/composition | Multi-value | `FACET_ONLY` | Structured + Title | Missing does not block route by default. |
| `SIZE_CAPACITY` | Size, dimensions, volume/capacity class | Multi-dimensional | `SECONDARY_OR_FACET` | Structured numeric fields + Title fallback | Exact specs prefer structured evidence; category may promote a coarse class with evidence. |
| `QUANTITY` | Pack/piece/set count | Usually single normalized count plus unit concept | `FACET_ONLY` | Dedicated/structured + Title | Must distinguish quantity from tiers/pockets/shelves/layers. |
| `FUNCTIONAL_FEATURE` | Functional performance/selling point | Multi-value | `FACET_ONLY` | Title + bullets + structured | Coexisting features do not define independent primary routes by default. |
| `COSMETIC` | Color/style/aesthetic variant | Multi-value | `FACET_ONLY` | Structured + Title | Must not split primary routes by default. |

`CORE_GATE` means the role determines whether a listing belongs in the primary-product route universe before route discovery.

## 6. Product Role contract

Before primary Route Discovery every accepted listing must have a governed Product Role state.

Minimum vocabulary:

- `PRIMARY_PRODUCT`
- `ACCESSORY`
- `REPLACEMENT`
- `REFILL`
- `BUNDLE`
- `UNKNOWN`
- `REVIEW_REQUIRED` only when evidence genuinely conflicts/ambiguous on the role itself.

Rules:

1. Product Role is evidence-backed and preserves evidence references.
2. Title is normally a major source because it expresses what the buyer is purchasing.
3. A primary product that includes hooks/components/accessories does not become `ACCESSORY` merely because accessory words are present.
4. Compatibility language must distinguish “works with X” from “replacement part for X”.
5. `ACCESSORY`, `REPLACEMENT` and `REFILL` do not compete with `PRIMARY_PRODUCT` for the main candidate routes unless the operator explicitly requests that market universe.
6. `BUNDLE` may contain primary products plus components; its route policy must be explicit rather than inferred from pack count alone.
7. Missing material, color, quantity or non-critical feature evidence must not alter Product Role.
8. `UNKNOWN` is a valid non-fabricated state when evidence is insufficient.

## 7. Route eligibility versus facets

### 7.1 Default route-eligible semantics

Primary route identity should be built from recurring combinations of semantic dimensions that materially change what the product is or how it is used, installed, attached, operated or bounded by compatibility.

Default eligible/conditional roles include:

- Product Identity;
- Structural Form;
- Usage Architecture;
- Installation Architecture;
- Attachment Mechanism;
- Operation Mechanism;
- Power Mode where category-relevant;
- Compatibility where it creates a real product boundary;
- coarse Size/Capacity classes only where calibration proves they represent product architecture rather than ordinary variants.

### 7.2 Facet-only by default

- Material;
- Functional Feature / selling point;
- Cosmetic/color;
- Quantity/pack count;
- other attributes that commonly coexist without changing the underlying product architecture.

A category profile may promote/demote a role only with explicit rationale and calibration evidence. Promotion changes role relevance, not a hard-coded final route name.

Market data must discover the actual recurring route combinations.

## 8. Category Semantic Profile V1.1 contract

S1 freezes the required shape; full production implementation belongs to Semantic Engine V2.

A versioned profile must be able to express at least:

```text
profile_id / version / category_scope
source_policy_by_semantic_dimension
attribute_aliases_and_value_aliases
negative_or_exclusion_rules
source_authorization
observed_attribute -> Universal Semantic Role mapping
role_relevance: CORE | SECONDARY | FACET_ONLY | IGNORE
Product Role evidence rules
coexistence rules
true-conflict rules
route-critical conflict rules
normalization/version metadata
canonical fingerprint
```

Constraints:

- No generic Python branch may test for a category-specific literal solely to create a primary route.
- The profile may teach the system category language but cannot predeclare final market route A/B/C membership.
- Profile changes are versioned, deterministic and auditable.
- LLM proposals cannot silently mutate an accepted profile.

## 9. LLM role and token contract

### 9.1 Allowed LLM work

LLM may:

- propose open-world attribute/value candidates from sampled/aggregated product language;
- propose mappings of unfamiliar phrases to existing Universal Semantic Roles;
- propose vocabulary grouping/normalization for operator or governed-rule approval;
- name and explain a route after deterministic membership exists;
- later summarize review/buyer-need evidence and compare locked-direction competitors;
- generate final narrative explanations from governed metrics/evidence.

### 9.2 Forbidden authoritative LLM work

LLM must not:

- calculate governed sales/share/growth/concentration/procurement metrics;
- invent missing hard facts;
- overwrite explicit governed source evidence;
- be the sole authority assigning a listing to a primary route;
- silently modify Semantic Profiles;
- turn a marketing feature into a primary route solely because it appears salient in text.

### 9.3 Token budget

For a normal approximately 1,000-listing market study, design for:

- target total LLM budget: `100k–150k` tokens;
- soft budget: `200k` tokens;
- hard budget: `300k` tokens unless explicitly overridden;
- model, prompt template/version, input/output token accounting and purpose must be auditable.

The architecture should use a funnel: broad market rows are processed by deterministic code; LLM receives sampled/ambiguous vocabulary, route summaries and a bounded representative/competitor set rather than every raw listing by default.

## 10. Cross-category calibration plan

### 10.1 Corpus design

Calibrate on `4–6` materially different real categories. Use approximately `200–500` listings per added category where practical.

The corpus should exercise:

1. installation/structure-heavy semantics;
2. capacity + operation semantics;
3. compatibility/accessory/replacement semantics;
4. powered/electronic operation semantics;
5. size/material-heavy semantics where material should not explode route count;
6. bundle/multipack semantics.

The existing private structure-heavy category may serve as one category. Added real source files remain outside Git.

If a planned category cannot be obtained, the report must record the semantic dimension that remains unvalidated rather than fabricating coverage.

### 10.2 Required aggregate evidence matrix

For each category and each key Semantic Role/dimension, produce privacy-safe aggregate statistics:

| Metric | Meaning |
| --- | --- |
| `title_observed_rate` | Governed Title evidence exists for the dimension |
| `structured_observed_rate` | Governed structured evidence exists |
| `both_observed_rate` | Both source classes provide relevant evidence |
| `agreement_rate` | Both sources agree on the normalized semantic fact |
| `complementary_rate` | Sources add non-conflicting semantic information |
| `compatible_multi_value_rate` | Multiple values coexist legitimately |
| `true_conflict_rate` | Mutually incompatible same-dimension evidence |
| `unavailable_rate` | Neither governed source provides evidence |
| `bullet_highlight_observed_rate` | Optional when the source exists |
| `product_role_coverage` | Product Role can be governed without fabrication |
| `route_critical_evidence_coverage` | Evidence exists for required route dimensions |

Commit only aggregates, category-safe labels where approved, configuration fingerprints and methodology. Never commit real ASINs, titles, brands, sellers, prices, private file paths or raw rows.

### 10.3 Human review sample

For each category perform a bounded private review of:

- Product Role correctness;
- key Semantic Role correctness;
- whether source relationships are agreement/complementary/true conflict;
- whether proposed route-eligible dimensions reflect genuinely different product architectures;
- whether common features/materials remain facets rather than artificial routes.

Only sanitized aggregate counts/rates are committed.

## 11. Quantitative acceptance metrics for V2

Final numeric thresholds are intentionally **TBD_FROM_CALIBRATION**. S1 must not invent arbitrary round-number gates.

Calibration must produce evidence to set thresholds for:

- Product Role governed coverage;
- key Semantic Role extraction coverage;
- true-conflict and route-critical-conflict rates;
- primary route assignment coverage;
- unclassified rate;
- review-required rate;
- route fragmentation / small-route rate;
- number and market coverage of candidate routes;
- bounded human intra-route consistency;
- material distinctness among candidate routes;
- input permutation determinism;
- repeated-run fingerprint determinism;
- category onboarding without generic-engine code changes.

Threshold proposal must include observed category distributions, rationale, risks and expected false-positive/false-negative trade-offs.

## 12. Migration boundary

### `RETAIN_AS_IS`

- SP-041A template contracts;
- SP-041B import/governed dataset;
- Evidence/Provenance foundations;
- Availability/missingness discipline;
- canonical identity/fingerprints;
- SP-041D denominator-safe market metrics;
- privacy/secret/network controls.

### `EXTEND`

- Product Attribute Map with Semantic Role projection;
- CategoryRulePack into Category Semantic Profile responsibilities;
- evidence conflict representation;
- Product Role evidence and cohort gating;
- candidate diversity based on route-eligible semantics.

### `REPLACE_IN_V2`

- global evidence precedence shortcut;
- exact-known-attribute-signature as the primary route engine;
- listing-wide review triggered by ordinary missing non-critical attributes.

### `DEPRECATE_AFTER_V2`

- primary route identity driven by functional/cosmetic/material facets unless category calibration explicitly proves structural relevance.

## 13. Revised development sequence

1. **SP-041S1 — Cross-Category Semantic Calibration & Reuse Gate**
2. **Semantic Engine V2** — implement evidence relationship, Universal Semantic Role projection, Product Role and Category Semantic Profile
3. **Route Discovery V2** — discover deterministic primary routes from route-eligible semantics; retain SP-041D metric layer
4. **SP-041E** — representative ASIN selection and direction state machine
5. **SP-041F** — procurement ceiling
6. **Targeted Sorftime / Review Intelligence** — bounded candidate/direction enrichment
7. **Operator Workbook Integration**
8. **Final multi-category E2E acceptance**

SP-041E remains explicitly frozen until Semantic Engine V2 and Route Discovery V2 pass their calibrated acceptance gates.

## 14. S1 acceptance status

The architecture/specification portion is frozen for calibration, but SP-041S1 is **not PASS** until the real multi-category calibration gate is completed and reviewed.

Current status:

`IN_PROGRESS — PRIVATE_MULTI_CATEGORY_CALIBRATION_REQUIRED`

No production semantic or route algorithm should be implemented from intuition alone before that evidence is collected.
