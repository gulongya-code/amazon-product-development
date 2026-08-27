# SP-041S1 — Semantic Engine V2 / Route Discovery V2 Acceptance Gates V1.1

Status: **PROPOSED_FROM_REAL_CALIBRATION — SAME-CORPUS BASELINE GATES FROZEN FOR S2**

## 1. Principle

Issue #55 requires measurable V2 acceptance criteria derived from real observations rather than arbitrary round numbers.

This document separates:

1. **hard semantic invariants** that must hold on every category; and
2. **same-corpus quantitative improvement gates** derived directly from the accepted SP-041D private Shower Caddy replay baseline.

The V2 implementation must replay the same private acceptance corpus for apples-to-apples comparison. Private listings remain outside Git.

## 2. Real baselines used

### 2.1 Five-category S1 semantic calibration corpus

- qualified categories: `5`;
- total accepted listings: `2,148`;
- Listing Title observed: `2,148 / 2,148 = 100%`;
- explicit structured `Product Type / Item Type`: `0 / 2,148 = 0%`;
- structured detail parse-issue range by category: `1.70%–7.25%`;
- route-critical structured-role availability is category-conditional, e.g. Shower installation `84.2%`, Vacuum compatibility `77.0%` in the conservative structured-key projection.

### 2.2 Bounded operator review

- review cohort: `60` rows;
- direct ACCEPT decisions: `46`;
- MODIFY decisions: `10`;
- malformed/unresolved input cells: `4`;
- explicit REVIEW decisions: `0`;
- `7/10` MODIFY rows repeated the corrected proposed labels;
- `2/10` materially selected consumable semantics, leading to the relation-role / lifecycle split;
- `1/10` contained a malformed role override.

This is a contract-calibration sample, not a production-model accuracy claim.

### 2.3 SP-041D same-corpus Route V1 baseline

The accepted private 998-listing replay recorded:

| Metric | V1 baseline |
| --- | ---: |
| accepted listings | 998 |
| assigned to route | 29.7595% |
| unclassified | 56.3126% |
| review required | 13.9279% |
| total routes | 80 |
| size-2 routes | 45 / 80 = 56.2500% |
| selected candidate routes | 5 |
| candidate coverage of assigned listings | 13.8047% |
| candidate coverage of accepted listings | 4.1082% |
| structural sample mismatches | 0 / 209 |
| repeated-run fingerprint mismatch | 0 |

The business review rejected this route structure as sufficiently general because assignment was low and route fragmentation was high.

## 3. Hard Semantic Engine V2 invariants

These gates are not negotiable by category averages.

| Gate | Required result |
| --- | --- |
| global source precedence | `0` universal `structured > title` shortcut |
| Product Identity | Title supported as primary/co-primary evidence |
| Product Role | orthogonal `relation_role` + `consumption_lifecycle` supported |
| Market Scope | not embedded as a universal shared-core Product Role |
| missing non-critical facet | must not by itself force whole-listing Review |
| quantity | package/structural/consumable count scopes not collapsed |
| size/capacity | quantity kind + semantic scope validated |
| facet-only route split | `0` candidate-route distinctions based only on Material/Feature/Cosmetic/Quantity/lifecycle |
| new calibrated category | `0` generic-engine code changes required for category-specific vocabulary |
| evidence | provenance/source/status retained for governed facts |
| deterministic replay | same input/profile/version => identical semantic fingerprints |
| LLM authority | no authoritative primary-route membership from LLM alone |

Any failure is a hard fail regardless of aggregate metrics.

## 4. Product understanding / operator gates

### 4.1 Relation-role bounded review agreement

For an architecture-balanced operator review sample, S2 must achieve:

`relation_role operator agreement >= 90%`

Rationale:

- the S1 architecture-aware proposal aligned with the operator workflow on the large majority of interpretable rows;
- the meaningful disagreement exposed a missing orthogonal lifecycle field rather than ordinary accessory/replacement confusion;
- `90%` is deliberately below the observed architecture-calibration alignment, leaving room for honest UNKNOWN/REVIEW rather than fabricated certainty.

The denominator excludes malformed spreadsheet input but includes genuine `UNKNOWN / REVIEW_REQUIRED` decisions.

### 4.2 Product Identity / market-cohort safety

On a balanced sample containing core, accessory/replacement/refill and off-target products:

- false inclusion of obvious `OTHER_PRODUCT` into the primary-product route universe: `0` in the reviewed sample;
- accessories/replacements/refills competing in primary-product routes without explicit accessory-market mode: `0`;
- target-term use-case mention alone establishing target Product Identity: `0`.

These are fail-closed safety gates, not optimization metrics.

## 5. Evidence coverage gates

### 5.1 No global structured-coverage threshold

The five-category data proves that one global structured-role coverage number is invalid. Installation and Compatibility are category-conditional, while Product Identity is Title-heavy.

Each Category Semantic Profile must therefore declare its route-critical roles.

### 5.2 Profile-declared CORE role coverage

For each profile-declared `CORE` role on the calibration corpus:

`combined governed evidence coverage >= structured-only calibration floor for that role/category`

Examples of current floors:

- Shower installation: `84.2%` structured-only;
- Vacuum compatibility: `77.0%` structured-only.

Because V2 adds Title/co-primary evidence, it must not reduce coverage below the accepted structured-only floor. If a role fails this gate, either extraction must improve or the role must be downgraded with operator-approved profile evidence.

### 5.3 Exact specification safety

For exact quantity/measurement facts:

- invalid quantity kind accepted as valid fact: `0` in bounded tests;
- ambiguous unit silently coerced: `0`;
- host-device capacity silently assigned to an accessory item without governed scope: `0`.

## 6. Same-corpus Route Discovery V2 improvement gates

These minimum gates are derived mechanically from the rejected SP-041D private V1 baseline so they can be tested on the same 998-listing corpus.

### 6.1 Route assignment coverage — at least 2x V1

V1: `29.7595%`

V2 gate:

`assigned_route_coverage >= 59.5190%`

This is a minimum improvement gate, not a universal final target for every Amazon category.

### 6.2 Unclassified rate — at most half V1

V1: `56.3126%`

V2 gate:

`unclassified_rate <= 28.1563%`

### 6.3 Review-required rate — at most half V1

V1: `13.9279%`

V2 gate:

`review_required_rate <= 6.9640%`

Ordinary missing facets cannot be used to meet this gate by fabricating values; they must remain unavailable.

### 6.4 Size-2 route fragmentation — at most half V1

V1: `45 / 80 = 56.2500%` of discovered routes had only two members.

V2 gate:

`size_2_route_share <= 28.1250%`

This gate directly targets the real business-review failure that exact signatures created excessive micro-routes.

### 6.5 Candidate coverage — at least 2x V1

V1 candidate coverage:

- of assigned listings: `13.8047%`;
- of accepted listings: `4.1082%`.

V2 gates:

- `candidate_coverage_of_assigned >= 27.6094%`;
- `candidate_coverage_of_accepted >= 8.2164%`.

Candidate selection remains `3–5` routes. Passing coverage does not override the material-distinctness and business-consistency gates below.

## 7. Route quality gates

### 7.1 Candidate material distinctness

For every pair of selected candidate routes:

`at_least_one_route_eligible_semantic_difference = true`

and

`facet_only_distinct_pair_count = 0`

Differences only in Material, selling Feature, Cosmetic, Quantity or lifecycle cannot establish separate primary candidate routes unless the Category Semantic Profile explicitly promotes the role based on calibration evidence.

### 7.2 Intra-route bounded human consistency

SP-041D recorded `0` structural mismatches across `209` privacy-preserving sample assignments.

V2 must maintain:

`bounded_human_intra_route_consistency >= 95%`

while also improving fragmentation/coverage. High consistency achieved only by creating tiny exact-signature routes does not pass the combined gate.

### 7.3 Candidate route minimum business sense

A selected route must not pass solely because it is mathematically distinct. Bounded operator review must confirm:

- coherent Product Identity;
- coherent relation-role cohort;
- route-eligible structural distinction;
- no accessory/off-target leakage;
- no facet-only route identity.

Any candidate failing these checks is rejected even if numeric coverage passes.

## 8. Cross-category portability gate

At least the five calibrated category patterns must be expressible by versioned Category Semantic Profiles without generic-engine category literals.

Hard gate:

`generic_engine_changes_for_new_profile = 0`

A profile may contain category language/aliases/rules; the generic engine may not gain `if category == ...` branches to satisfy calibration.

## 9. Determinism and privacy gates

- repeated same-input semantic fingerprint equality: `100%`;
- repeated same-input route fingerprint equality: `100%`;
- timestamp/runtime metadata excluded from semantic identity;
- raw private calibration files committed: `0`;
- private ASIN/title/brand/seller/price rows in Git delta: `0`;
- secret/private-path leakage in Git delta: `0`.

## 10. KWS future integration gates

S2 does not cut KWS over, but the calibrated shared semantics must be designed so later KWS integration can preserve:

- accepted Ground Truth safety;
- Search Target / Hard Conflict fail-closed behavior;
- Brand Evidence Authority;
- Brand Query Binding;
- Brand Semantic v2 shadow authorities;
- Listing/PPC Exact/PPC Test boundaries;
- canonical keyword identity;
- zero automatic Amazon execution.

The shared `relation_role` maps to KWS query-target semantics only through an adapter; `consumption_lifecycle` is optional consumer evidence and does not replace KWS business gates.

## 11. Gate summary

```text
SEMANTIC_HARD_INVARIANTS = REQUIRED
RELATION_ROLE_OPERATOR_AGREEMENT = >= 90%
OBVIOUS_OTHER_PRODUCT_FALSE_INCLUSION = 0
NONPRIMARY_LEAKAGE_IN_PRIMARY_ROUTES = 0
CORE_ROLE_COMBINED_COVERAGE = >= SAME_CATEGORY_STRUCTURED_ONLY_FLOOR
SAME_CORPUS_ROUTE_ASSIGNMENT = >= 59.5190%
SAME_CORPUS_UNCLASSIFIED = <= 28.1563%
SAME_CORPUS_REVIEW_REQUIRED = <= 6.9640%
SAME_CORPUS_SIZE2_ROUTE_SHARE = <= 28.1250%
SAME_CORPUS_CANDIDATE_COVERAGE_ASSIGNED = >= 27.6094%
SAME_CORPUS_CANDIDATE_COVERAGE_ACCEPTED = >= 8.2164%
BOUNDED_HUMAN_INTRA_ROUTE_CONSISTENCY = >= 95%
FACET_ONLY_DISTINCT_CANDIDATE_PAIRS = 0
GENERIC_ENGINE_CATEGORY_PATCHES = 0
DETERMINISTIC_REPLAY_FINGERPRINT_MATCH = 100%
PRIVATE_DATA_LEAKAGE = 0
```

These gates are the minimum S2/V2 acceptance floor. Passing them does not by itself authorize SP-041E; S2 must also complete focused/affected/full regression, privacy scans, and bounded business review on the actual V2 outputs.
