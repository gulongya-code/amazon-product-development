# TASK-SP-041S2 Semantic Engine V2 Implementation

Status: **IMPLEMENTED AND ACCEPTED — `PASS — SEMANTIC_ENGINE_V2`**

## Scope

This implementation adds a deterministic, listing-grain Semantic Engine V2 to APD. It implements the accepted SP-041S1 V1.1 contracts without changing SP-041A/B/C/D behavior and without beginning Route Discovery V2 or SP-041E.

The runtime flow is:

`GovernedMarketDatasetV1 -> source observations -> Semantic Facts -> Evidence Relationships -> Universal Semantic Roles -> Product Identity -> orthogonal relation_role + consumption_lifecycle -> APD primary-cohort eligibility`

The engine creates no route, representative ASIN, Direct Competitor, procurement ceiling or opportunity score.

## Runtime package

`src/amazon_product_intelligence/semantic_engine_v2` contains:

- strict, self-validating fact/relationship/identity/role/cohort/result contracts;
- the complete frozen Universal Semantic Role, evidence-relationship, relation-role, lifecycle and quantity-subtype vocabularies;
- a strict Category Semantic Profile V1.1 loader with exact-key validation and deterministic fingerprinting;
- fail-closed cross-validation that every rule source belongs to its own semantic dimension's primary/corroborating/fallback policy and is not forbidden;
- a generic profile interpreter with no five-category vocabulary or branches;
- deterministic identifiers, fingerprints, ordering, availability and upstream/profile references;
- fail-closed quantity-kind and semantic-scope parsing through the accepted SP-041C measurement parser;
- APD-local `PRIMARY_ONLY` cohort projection.

The engine uses no network call or LLM decision. `LLM_DERIVED_CANDIDATE` is present only as the frozen source-class vocabulary; the profile loader prohibits it from authoritative Product Identity, relation role or lifecycle rules.

## Frozen evidence states

The runtime preserves all V1.1 states:

- `AGREES`
- `COMPLEMENTARY`
- `COMPATIBLE_MULTI_VALUE`
- `SOURCE_ONLY_TITLE`
- `SOURCE_ONLY_STRUCTURED`
- `UNAVAILABLE`
- `TRUE_CONFLICT`
- `ROUTE_CRITICAL_CONFLICT`

Missing non-critical evidence remains `UNAVAILABLE`/`UNKNOWN`; it does not force whole-listing review. Equal-priority mutually exclusive route-critical evidence produces `REVIEW_REQUIRED` and blocks APD primary-cohort eligibility.

## Product Identity and Product Role

Product Identity is separate from Product Role and from APD market membership. Title is mandatory primary/co-primary identity evidence. Structured parameters may corroborate governed dimensions, but the absence of a structured product-type field does not create Review.

Product Role is orthogonal:

- `relation_role`: `PRIMARY_PRODUCT / ACCESSORY / REPLACEMENT / REFILL / BUNDLE / UNKNOWN / REVIEW_REQUIRED`;
- `consumption_lifecycle`: `REUSABLE_DURABLE / CONSUMABLE / PERIODIC_REPLACEMENT / UNKNOWN / REVIEW_REQUIRED`.

No quantity rule can author `BUNDLE`. Missing lifecycle remains `UNKNOWN` without changing a governed relation role.

## Quantity and capacity safety

Quantity preserves `PACKAGE_COUNT`, `STRUCTURAL_COMPONENT_COUNT` and `CONSUMABLE_UNIT_COUNT`. Size/capacity facts require an explicit quantity kind and semantic scope. Ambiguous or mismatched measurement input is rejected with a limitation rather than coerced. The Air Fryer mixed profile deliberately has no accessory item-capacity rule, preventing host capacity from being assigned to an accessory.

## Category Semantic Profiles V1.1

Five versioned JSON profiles contain all category vocabulary, aliases, source policies, role relevance, identity/role/lifecycle rules, coexistence/conflict policy and quantity/scope authorization:

- Shower Caddy — Installation and Attachment are core;
- Dog Water Bottle — Operation is core and item capacity is secondary;
- Vacuum Filter — Compatibility is core; replacement relation gating and periodic lifecycle are explicit;
- Food Storage Container — Structural Form is core, capacity secondary and component count facet-only;
- Air Fryer mixed market — main appliance Identity plus Structural Form/Operation are core; accessories/refills/use-case-only mentions are excluded from the primary cohort.

The profiles do not contain final route names.

## Determinism and privacy

Semantic output excludes import timestamps and is stable under input record/field ordering. Evidence references contain source class/field/key and content/upstream fingerprints, not Title or detailed-parameter text. Title-derived facts use fixed normalized values; the profile loader rejects Title `SOURCE_VALUE` passthrough.

Private replay tooling accepts an external five-entry manifest and external operator-review labels, runs timestamp/order replay, and emits aggregate JSON only. It checks exact corpus sizes, core-role floors, operator agreement, boundary false-includes, quantity/scope safety, generic-engine coupling, profile lineage, offline/LLM invariants and report privacy.

## Compatibility and downstream boundary

SP-041C remains unchanged and no existing consumer is cut over. SP-041D exact route signatures and market metrics remain untouched. `amazon_keyword_screener` is not modified or adapted. Route Discovery V2 must consume this S2 output under its own future Issue and gates; S2 makes no Route Discovery readiness claim beyond contract availability.

## Acceptance closeout

The mandatory private replay completed through the unchanged SP-041B governed importer and Semantic Engine V2 for all five calibrated categories: 998 + 400 + 300 + 150 + 300 = 2,148 accepted listings. Reversed-order/different-import-timestamp replay produced identical results for every category.

The original 60-row operator-review cohort was read without repairing or inferring private labels. Four malformed/unfilled decision cells were excluded as required. One otherwise valid decision with an unfilled relation override also remained outside the relation denominator. The resulting bounded `relation_role` agreement was 55/55 (100%). Obvious-other false inclusion, non-primary leakage, and use-case-only target-identity inclusion were all zero.

Every published same-role S1 CORE floor passed, generic-engine category patches remained zero, runtime diagnostics reported zero network calls and zero authoritative LLM decisions, and the aggregate replay report contained no private row/path/ASIN data. The full completion evidence is recorded in `docs/validation/SP_041S2_COMPLETION_REPORT.md`.

`PASS — SEMANTIC_ENGINE_V2`
