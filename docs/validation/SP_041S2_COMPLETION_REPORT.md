# TASK-SP-041S2 Completion Report

Issue: GitHub #56

Report date: 2026-08-29

Final verdict: **PASS — SEMANTIC_ENGINE_V2**

## A. Required baseline and workspace gate

- Required branch: `codex/task-sp-041s2-semantic-engine-v2` — verified.
- Required starting HEAD: `d470521da969426cbdc5f26448487080b1f8cb97` — verified before implementation and unchanged throughout acceptance work.
- Required ancestry: `6446c36618180d6a4b32b58c6801efd4f9f916fa` — verified.
- Starting workspace and staging area — clean; remote tracking state — current.
- Runtime: Python 3.14.4 and pytest 9.1.1.
- No reset, clean, stash, checkout-overwrite, or private-asset copy was used during resume/closeout.

## B. SP-041S1 calibrated-contract confirmation

The authoritative V1.1 materials were read completely before implementation:

- calibrated semantic architecture;
- V2 acceptance gates;
- cross-system reuse audit;
- multi-category evidence observations;
- operator-review synthesis;
- final local-validation closeout;
- private calibration runbook and private calibration asset inventory.

No accepted S1 contract was reopened or changed.

## C. Reuse and license decision

The targeted audit was completed before runtime implementation and is recorded in `docs/engineering/SP_041S2_TARGETED_IMPLEMENTATION_REUSE_AUDIT_V2.md`.

S2 reuses the governed market dataset, SP-041B importer, structured-parameter parser, SP-041C measurement parser, canonical JSON/IDs/fingerprints, availability/reference contracts, and confidence vocabulary. It extends those assets with the frozen V1.1 semantic contracts and APD cohort projection. It does not create a third Shared Semantic Core package.

No public repository code or fixture was copied/adapted and no package was added. The S1 public GitHub/license audit decisions remain unchanged: Shopify Product Taxonomy (MIT) and OA-Mine (Apache-2.0) are reference-only here; RapidFuzz (MIT) and scikit-learn (BSD-3-Clause) were not selected for S2; OpenTag remains no-copy/reference-only because its license is unclear. Raw operator-workbook reading reuses the already pinned `openpyxl>=3.1.5,<4`, whose existing MIT dependency decision was recorded by SP-041B.

## D. Files implemented

- `src/amazon_product_intelligence/semantic_engine_v2/` — five contract/profile/engine package files;
- `config/category_semantic_profiles/` — five V1.1 category profiles;
- `scripts/build_semantic_engine_v2.py` and `scripts/run_semantic_engine_v2_private_replay.py`;
- three S2 acceptance/safety/replay test files;
- this report and two S2 engineering/audit documents.

The allowed delta contains 18 text files and no private or spreadsheet asset.

## E. Semantic Fact V2

Implemented deterministic listing-grain Semantic Facts with Universal Semantic Role, normalized value, availability, observed/derived status, confidence, source classes, evidence IDs, quantity kind/subtype/scope, and profile/rule lineage. IDs and fingerprints use canonical semantic content and exclude clocks and input row order.

## F. Evidence Relationships V1.1

Implemented all frozen states: `AGREES`, `COMPLEMENTARY`, `COMPATIBLE_MULTI_VALUE`, `SOURCE_ONLY_TITLE`, `SOURCE_ONLY_STRUCTURED`, `UNAVAILABLE`, `TRUE_CONFLICT`, and `ROUTE_CRITICAL_CONFLICT`.

Conflict evaluation is two-stage. A single-valued dimension or an explicitly observed two-or-more-value conflict set establishes a conflict. An empty conflict set does not create a conflict for a multi-value dimension; it can only elevate an already-established conflict. Route-critical elevation requires equal-priority competing values and primary evidence. Missing non-critical evidence remains unavailable rather than forcing whole-listing review.

## G. Universal Semantic Roles

The exact 14-role vocabulary is implemented with explicit per-listing and aggregate coverage. Generic engine Python contains no five-category vocabulary, category branch, or route name.

## H. Product Identity

Product Identity is evidence-backed and independent of Product Role and cohort membership. Title is mandatory primary/co-primary evidence; provider category context cannot overwrite Title identity. Title source text cannot pass through as a semantic fact value. Use-case mention alone cannot establish target identity.

## I. Product Role

Implemented orthogonal:

- `relation_role`: `PRIMARY_PRODUCT / ACCESSORY / REPLACEMENT / REFILL / BUNDLE / UNKNOWN / REVIEW_REQUIRED`;
- `consumption_lifecycle`: `REUSABLE_DURABLE / CONSUMABLE / PERIODIC_REPLACEMENT / UNKNOWN / REVIEW_REQUIRED`.

Missing lifecycle does not force relation review, and quantity never authors `BUNDLE`. Accessory/refill/replacement semantics stay separate from lifecycle.

## J. Quantity and capacity safety

Implemented `PACKAGE_COUNT`, `STRUCTURAL_COMPONENT_COUNT`, and `CONSUMABLE_UNIT_COUNT`, plus item/package/component/consumable/host/unspecified scope. Every measurement rule must have exactly one matching `quantity_scope_rules` authorization; unused or duplicate authorizations fail profile loading. Invalid or ambiguous kinds/units remain unavailable with limitations. Accessory profiles do not authorize host-device capacity as accessory item capacity.

## K. Category Semantic Profile V1.1

Implemented exact-key UTF-8 JSON validation, version/normalization gates, source authorization and per-dimension policy, aliases, fact/identity/relation/lifecycle rules, coexistence/conflict rules, quantity/scope authorization, APD cohort policy, and deterministic profile fingerprinting.

The loader rejects unknown keys, globally unauthorized sources, rule sources outside their own semantic dimension's primary/corroborating/fallback policy, dimension-forbidden sources, one-value conflict declarations, LLM-authored Identity/Product Role, Title raw-value passthrough, authored Unknown/Review outcomes, and inconsistent route-critical policy. Provider category context therefore cannot cross the Product Identity policy boundary even when it is globally available as context.

## L. Five calibrated profiles

- Shower Caddy — Installation and Attachment core;
- Dog Water Bottle — Operation core and item capacity secondary;
- Vacuum Filter — Compatibility core; host, replacement, refill, and accessory relation layers are distinct;
- Food Storage Container — Structural Form core, item capacity secondary, and component count facet-only;
- Air Fryer mixed market — appliance primary identity plus accessory/use-case boundaries, Structural Form and Operation core, lifecycle secondary.

All category terms, phrases, exclusions, aliases, source keys, and rule IDs are profile data. No final route names are present.

## M. APD market-cohort projection

Implemented APD-local `PRIMARY_ONLY` projection with `PRIMARY_COHORT_ELIGIBLE`, `NON_PRIMARY_EXCLUDED`, `OFF_TARGET_EXCLUDED`, `UNKNOWN`, and `REVIEW_REQUIRED`. Only target Identity plus allowed primary relation can enter the primary cohort; any route-critical conflict blocks entry. S1 business labels were not promoted into the shared semantic vocabulary.

## N. Determinism and fingerprints

Every category was rebuilt after reversing listing order and changing the import timestamp. All five serialized results matched exactly: `5/5`, or `100%`.

| Calibration | Profile fingerprint | Result fingerprint | Import / build / replay seconds |
| --- | --- | --- | ---: |
| Shower Caddy | `d08a2a441d0746767dd0e0f0a35bd26675256c82f26cda1821a488b039ca9aa1` | `70912432f62ea21047ab7f27ac8eeec3df5798b2b8bade3fae2ca35c5f0e1cb1` | 2.897301 / 13.909571 / 12.794756 |
| Dog Water Bottle | `3bfa600c6659721fe133d27c866efdb8ed3ea0ac5d4623ed3055f16213c30173` | `8bc885de00786778ff320970392d50cf7cedcbf92deefd2f01aa519f337f36e1` | 0.954896 / 1.768884 / 2.248596 |
| Vacuum Filter | `bfeb66f3c065394acba8c3bd55672b8c349ebe58289eff203105310061320764` | `1eb1b4f55d27e13a42c6f7bd1c3974e6aff18c7a275ccdaf5fa792bc0d35d526` | 1.075013 / 1.851560 / 2.283485 |
| Food Storage Container | `097097108b11b88af72b3f0d1d81fb743dc3f8895176d0ec086980b87464339c` | `0d05543cc1ad2a6c1198301377730272f150b10c7a22b28fb395f49d5a9530f8` | 0.540000 / 0.877674 / 0.828871 |
| Air Fryer mixed | `d3a4e29090ce5e50872f2b53087d7423b6bc0295cf74e43e6b5d8549f2c8fe76` | `fd1f37e338890a2690e5b0259bab40a34007381775613fce4eb2306e256f0bff` | 0.876120 / 2.951603 / 1.841795 |

Total replay wall-clock time was 48.406044 seconds. Profile-fingerprint lineage matched for every emitted fact.

## O. Mandatory private five-category replay

The same five S1 calibration categories were replayed through `SP-041B governed import -> Semantic Engine V2` with exact counts: 998 + 400 + 300 + 150 + 300 = **2,148/2,148** accepted listings.

### Identity, relation, lifecycle, and cohort aggregates

| Calibration | Identity status | Relation-role distribution | Lifecycle distribution | Cohort distribution | Review listings |
| --- | --- | --- | --- | --- | ---: |
| Shower Caddy (998) | governed 883 (88.4770%); unknown 115 | primary 872; accessory 5; replacement 4; unknown 117 | reusable 307; periodic 1; unknown 690 | primary 868; non-primary 3; off-target 10; unknown 117 | 0 |
| Dog Water Bottle (400) | governed 297 (74.2500%); unknown 103 | primary 280; accessory 17; unknown 103 | reusable 49; unknown 351 | primary 280; off-target 17; unknown 103 | 0 |
| Vacuum Filter (300) | governed 300 (100%) | primary 23; replacement 251; refill 26 | consumable 26; periodic 136; reusable 19; unknown 119 | non-primary 251; off-target 49 | 0 |
| Food Storage Container (150) | governed 115 (76.6667%); unknown 35 | primary 112; accessory 3; unknown 35 | consumable 13; reusable 41; unknown 96 | primary 99; off-target 16; unknown 35 | 0 |
| Air Fryer mixed (300) | governed 287; review 3; unknown 10 | primary 162; accessory 128; unknown 10 | consumable 101; reusable 37; unknown 162 | primary 162; off-target 125; review 3; unknown 10 | 3 |

Relation-role governed coverage was 88.2766%, 74.2500%, 100%, 76.6667%, and 96.6667%, respectively. Lifecycle governed coverage was 30.8617%, 12.2500%, 60.3333%, 36.0000%, and 46.0000%, respectively.

### Universal-role coverage

Only non-zero roles are shown; every omitted role had explicit 0% coverage.

| Calibration | Non-zero role coverage |
| --- | --- |
| Shower Caddy | Product Identity 88.4770%; Product Role 90.6814%; Installation 90.9820%; Attachment 90.0802%; Quantity 11.9238% |
| Dog Water Bottle | Product Identity 74.2500%; Product Role 75.0000%; Operation 28.0000%; Size/Capacity 7.7500% |
| Vacuum Filter | Product Identity 100%; Product Role 100%; Compatibility 80.6667%; Material 79.0000%; Quantity 1.0000% |
| Food Storage Container | Product Identity 76.6667%; Product Role 88.0000%; Structural Form 100%; Size/Capacity 18.6667% |
| Air Fryer mixed | Product Identity 96.6667%; Product Role 97.0000%; Structural Form 55.6667%; Operation 41.6667%; Quantity 3.0000% |

All published same-role S1 CORE floors passed:

| Calibration / role | S1 floor | S2 actual | Result |
| --- | ---: | ---: | --- |
| Shower Caddy / Installation | 84.2% | 90.9820% | PASS |
| Vacuum Filter / Compatibility | 77.0% | 80.6667% | PASS |
| Food Storage Container / Structural Form | 3.3% | 100% | PASS |
| Air Fryer mixed / Structural Form | 37.3% | 55.6667% | PASS |

### Evidence-relationship aggregates

Cells are `count (rate)`. `A`, `C`, `CMV`, `SOT`, `SOS`, `U`, `TC`, and `RCC` mean Agree, Complementary, Compatible Multi-Value, Source-Only Title, Source-Only Structured, Unavailable, True Conflict, and Route-Critical Conflict.

| Calibration | A | C | CMV | SOT | SOS | U | TC | RCC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Shower Caddy | 0 | 857 (12.5201%) | 469 (6.8517%) | 2,137 (31.2199%) | 1,389 (20.2922%) | 1,990 (29.0723%) | 3 (0.0438%) | 0 |
| Dog Water Bottle | 0 | 9 (0.3736%) | 0 | 704 (29.2237%) | 82 (3.4039%) | 1,614 (66.9988%) | 0 | 0 |
| Vacuum Filter | 0 | 230 (11.3300%) | 47 (2.3153%) | 730 (35.9606%) | 434 (21.3793%) | 537 (26.4532%) | 52 (2.5616%) | 0 |
| Food Storage Container | 0 | 28 (3.0172%) | 7 (0.7543%) | 424 (45.6897%) | 29 (3.1250%) | 438 (47.1983%) | 2 (0.2155%) | 0 |
| Air Fryer mixed | 0 | 38 (2.0675%) | 61 (3.3188%) | 759 (41.2949%) | 195 (10.6094%) | 781 (42.4918%) | 1 (0.0544%) | 3 (0.1632%) |

## P. Bounded operator-safety validation

The original 60-row cohort was consumed without repairing, fabricating, or inferring operator cells:

- raw rows: 60;
- valid decision rows: 56;
- malformed/unfilled decision cells excluded: 4;
- valid decision with an unfilled/invalid relation override excluded from relation agreement: 1;
- final `relation_role` denominator: 55;
- agreement: **55/55 = 100%**, above the 90% gate;
- missing replay listings: 0.

Genuine `UNKNOWN` and `REVIEW_REQUIRED` relation labels are supported in the denominator; malformed cells are not. The legacy one-column consumable projection was retained as a non-gating diagnostic and matched 3/4; no missing lifecycle label was inferred to force agreement.

Required bounded safety results:

- obvious OTHER_PRODUCT false inclusion: **0/12**;
- non-primary leakage into `PRIMARY_ONLY`: **0/16**;
- use-case mention alone establishing target identity: **0/12**.

The broader, non-gating cohort comparison recorded 13 mismatches across 56 valid-decision rows; the three required false-inclusion/leakage strata above remained zero. The original operator workbook has no tagged invalid-quantity, ambiguous-unit, or host-capacity rows, so those three checks are covered non-vacuously by the synthetic S2 safety suite rather than by invented private labels.

## Q. Network and LLM operation

All five category diagnostics reported `network_calls=0` and `llm_authoritative_decisions=0`. Runtime code imports no network/provider client. `LLM_DERIVED_CANDIDATE` is vocabulary only and is rejected as an authoritative source for Product Identity, relation role, lifecycle, or cohort membership. Operation remains deterministic when no network or LLM is available.

## R. Privacy and security

- Private workbook/raw-row files in the Git delta: 0.
- XLS/XLSX/XLSM/CSV/TSV/ZIP assets in the allowed delta: 0.
- Private asset names or private absolute paths in the allowed delta: 0.
- Private listing rows, titles, brands, sellers, prices, or detailed-parameter strings: 0.
- Credential/secret-pattern findings after false-positive review: 0.
- Real ASINs: 0; the only ASIN-shaped values are fixed synthetic placeholders `B000000001` and `B000000002` in tests.
- Generic-engine five-category literal count: 0.
- Replay-report privacy leak count: 0.

The replay manifest, private inputs, and row-grain operator labels remained external and were never staged.

## S. Tests and regressions

- S2 acceptance/private-replay/safety suites: **41 passed**.
- SP-041A/B/C/D focused plus S2: **105 passed** (64 pre-S2 focused + 41 S2).
- Affected Product Intelligence/Opportunity/Market Report/pipeline set: **421 passed, 5 skipped**.
- Full suite: **1 failed, 1,457 passed, 13 skipped**.

The only full-suite failure is identical to the required-HEAD baseline:

`tests/test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`

- expected OOXML package fingerprint: `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`;
- actual Windows/Python 3.14 fingerprint: `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.

No new regression failure was introduced.

## T. Git state

Only the 18 allowed S2 code/config/test/doc files are included in the completion commit. Generated pytest basetemps are removed explicitly, never via `git clean`; no private asset is staged. Cached-diff whitespace/privacy/secret/path/ASIN checks and final branch status are verified before push. The exact commit and remote branch state are recorded in the Issue #56 closeout comment and completion response.

## U. Route Discovery V2 boundary

Readiness recommendation: **READY AS A SEMANTIC INPUT CONTRACT for a separately authorized future Route Discovery V2 issue**. This recommendation does not claim any downstream route-assignment, fragmentation, candidate-coverage, or representative-selection gate.

S2 does not implement Route Discovery V2, SP-041E, route membership/naming, representative-ASIN selection, Direct Competitors, procurement ceiling, opportunity scoring, KWS cutover, or a third Shared Semantic Core repository/package.

## V. Final verdict

Every Issue #56 gate is satisfied.

`PASS — SEMANTIC_ENGINE_V2`
