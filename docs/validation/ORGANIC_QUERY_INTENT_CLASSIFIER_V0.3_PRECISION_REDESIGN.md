# Organic Query Intent Classifier V0.3 Precision Redesign

## 1. Completion status

**TASK-SP-032H COMPLETE**

Organic Query Intent Classifier V0.3 is implemented as an isolated, deterministic ruleset. It changes only the Organic Search Term intent boundary. Buyer Need Taxonomy V0.2, Buyer Need extraction rules V0.2, Semantic Clustering, Gap, Scoring, and Opportunity Policy remain unchanged.

The two saved holdouts meet the patch-validation thresholds:

- SP-032E Need Precision: `81.63% → 100%`
- SP-032F Need Precision: `84.00% → 100%`
- Both holdouts V0.3 NON_NEED Precision: `100%`
- Both holdouts Need Recall proxy: `100%`
- Integrated Bowl recall: `80 / 80 = 100%`
- Target-product Outdoor routing retention: `100%` for portable, travel, walking, and hiking in both windows

These are retrospective results on V0.2-selected, previously annotated samples. They are not evidence of future generalization.

## 2. Baseline and scope

- Branch: `main`
- Baseline commit: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`
- Intent V0.2 registry remains: `buyer-need-query-intent-registry:099d6df1ed74a0e5098b98389e4472bb2eecb873881a907124fed21c34d04468`
- New ruleset: `buyer-need-intent-rules-v0.3`
- New contract: `buyer-need-intent-contract-v0.3`
- Taxonomy remains: `buyer-need-taxonomy-v0.2`
- Buyer Need extraction rules remain: `buyer-need-rules-v0.2`
- API calls: `0`
- XiYou credits consumed: `0`
- Git commit created: `No`

## 3. Files

### New files

- `src/amazon_product_intelligence/buyer_need_analysis/models_v0_3.py`
- `src/amazon_product_intelligence/buyer_need_analysis/intent_v0_3.py`
- `src/amazon_product_intelligence/buyer_need_analysis/builder_v0_3.py`
- `src/amazon_product_intelligence/buyer_need_analysis/replay_v0_3.py`
- `tests/test_buyer_need_intent_v0_3.py`
- `docs/validation/ORGANIC_QUERY_INTENT_CLASSIFIER_V0.3_PRECISION_REDESIGN.md`

### Modified files

- `src/amazon_product_intelligence/buyer_need_analysis/__init__.py` — exports the isolated V0.3 API and explicit classifier-version selector.

### Confirmed unchanged by this task

- `buyer_need_analysis/intent_v0_2.py`
- `buyer_need_analysis/builder_v0_2.py`
- `buyer_need_analysis/taxonomy_v0_2.py`
- Semantic Clustering, Gap, Scoring, and Opportunity Policy code
- SP-032E/F source snapshots and annotations

## 4. Intent V0.3 design

`IntentClassificationContext` makes the decision inputs explicit and serializable:

- `normalized_query`
- `category_scope`
- `product_object_matches`
- `brand_model_matches`
- `accessory_matches`
- `broad_query_matches`
- `out_of_scope_matches`
- `need_expression_matches`
- `diagnostics`, including category qualifier, modifier position, and modifier distance

`BuyerNeedQueryIntentEvidenceV0_3` records:

- `primary_intent`
- `secondary_need_signals`
- selected boundary
- matched gate/rule IDs
- source evidence and full query provenance
- whether the decision is eligible to enter Taxonomy

Only `NEED_CANDIDATE` is eligible for Taxonomy. A NON_NEED or AMBIGUOUS primary intent cannot publish Buyer Need candidates.

## 5. Precedence design

The implemented precedence is conditional rather than a mechanical first-match list:

1. Explicit non-dog audience → `OUT_OF_SCOPE`.
2. Audited brand/model evidence → `BRAND_MODEL`; Need-looking modifiers are retained as secondary signals.
3. Related-product head/object → `ACCESSORY_RELATED`; travel/walking tokens cannot override it.
4. Broad shopping context without a linked target-product modifier → `BROAD_QUERY`.
5. Target product object:
   - category-qualified and linked explicit modifier → `NEED_CANDIDATE`;
   - unchanged Taxonomy V0.2 explicit match → `NEED_CANDIDATE`;
   - no Need modifier → `PRODUCT_OBJECT`;
   - generic modifier without dog/pet context → `AMBIGUOUS`.
6. Taxonomy expression with explicit dog/pet context but no target object → `NEED_CANDIDATE`.
7. Insufficient structural evidence → `AMBIGUOUS`, not a guessed Need.

Precedence is part of deterministic identity material through versioned gate IDs and context.

## 6. Product Object boundary

The classifier formalizes two distinct states:

| Query | Boundary | Intent |
|---|---|---|
| `dog water bottle` | `PURE_PRODUCT_OBJECT` | `PRODUCT_OBJECT` |
| `dog water bottle with built-in bowl` | `PRODUCT_OBJECT_WITH_NEED_MODIFIER` | `NEED_CANDIDATE` |
| `portable dog water bottle` | `PRODUCT_OBJECT_WITH_NEED_MODIFIER` | `NEED_CANDIDATE` |
| `running water bottle` | `CONTEXT_MISSING` | `AMBIGUOUS` |
| `insulated water bottle` | `CONTEXT_MISSING` | `AMBIGUOUS` |

A modifier must have explicit dog/pet category context and a nearby target-product relation. A Taxonomy V0.2 match may also supply the explicit Need expression; this preserves established material, capacity, and other taxonomy routes without changing the taxonomy.

## 7. Accessory and broad boundaries

Accessory objects such as bags, carriers, poop bags, gifts, containers, pouches, toys, and accessories take precedence over travel/walking modifiers.

| Query | V0.3 result |
|---|---|
| `dog travel bag` | `ACCESSORY_RELATED` |
| `dog walking accessories` | `ACCESSORY_RELATED` |
| `dog travel accessories` | `ACCESSORY_RELATED` |
| `dog camping essentials` | `BROAD_QUERY` |
| `dog beach essentials` | `BROAD_QUERY` |
| `dog hiking gear` | `BROAD_QUERY` |
| `dog travel bowls` | remains `NEED_CANDIDATE` because bowl is a target object, not an accessory gate |

## 8. Brand boundary

Brand is a primary shopping intent. Need-looking text is not discarded; it is saved as `secondary_need_signals` with the same source evidence.

Example:

- Query: `TrailHound insulated dog water bottle`
- Primary intent: `BRAND_MODEL`
- Secondary Need signal: `insulated`
- Taxonomy eligibility: `false`

V0.3 does not automatically promote a brand query because it contains `insulated`, and it does not erase the secondary evidence. No Buyer Need was added or promoted.

## 9. Context gating

The main context requirements are:

- explicit dog/pet qualifier for generic modifier expressions;
- a recognized target product object;
- modifier-to-product distance of at most six tokens for the product-plus-modifier route;
- accessory/broad precedence for non-target query heads;
- taxonomy match precedence over a pure-product decision when category context is explicit;
- unresolved generic expressions become `AMBIGUOUS`.

This design addresses the repeated product-object, audience, accessory, broad-context, and multi-intent failures documented by SP-032G without changing Semantic Clustering.

## 10. Recovered 17/17 False Positive corpus

`Current Need/Type` and rule IDs are the frozen V0.2 evidence. `Failure layer` is the SP-032G attribution. All rows have human label `INCORRECT` under the V0.2 `NEED_CANDIDATE` audit group.

| Holdout | Keyword | ASIN | Current Need / Type | Failure layer | V0.3 intent | V0.2 intent rule ID | V0.2 extraction rule ID |
|---|---|---|---|---|---|---|---|
| E | `animal water bottle` | `B08L7N8M4Z` | UNKNOWN / UNKNOWN | Intent | `OUT_OF_SCOPE` | NONE | NONE |
| E | `dog travel accessories` | `B0H8WQT1DV` | travel / USE_CASE | Taxonomy route | `ACCESSORY_RELATED` | `buyer-need-query-taxonomy-route:d0e361591c845fc7720314b791a73ec2d3b38cd7ce7b0a61d6e2247dc68ed470` | `buyer-need-rule:d4875a8e54aaba818839cf7edbacb3ed07a1331a1bca429ff857d3c2542c76e1` |
| E | `malsipree dog water bottle` | `B09V14YQGT` | UNKNOWN / UNKNOWN | Intent | `PRODUCT_OBJECT` | NONE | NONE |
| E | `asobu` | `B08P5K8R5X` | UNKNOWN / UNKNOWN | Intent | `BRAND_MODEL` | NONE | NONE |
| E | `doggy water bottle` | `B0DZNGBXTS` | UNKNOWN / UNKNOWN | Intent | `PRODUCT_OBJECT` | NONE | NONE |
| E | `cat water bottle` | `B0B51TY6MR` | UNKNOWN / UNKNOWN | Intent | `OUT_OF_SCOPE` | NONE | NONE |
| E | `dog hiking gear` | `B0B3DKHGRX` | outdoor hiking / USE_CASE | Taxonomy route | `BROAD_QUERY` | `buyer-need-query-taxonomy-route:3487a1dc90d9efb3dff932a35bea5a6ed99a50c6ea1a71c8aae98730c8a901d8` | `buyer-need-rule:0d483c0f135fedabc6d5f342538d328cb70a2b480af69e0c21c3c4163d6b5fd5` |
| E | `stanley dog bowl` | `B08P5K8R5X` | UNKNOWN / UNKNOWN | Intent | `PRODUCT_OBJECT` | NONE | NONE |
| E | `springland dog water bottle` | `B0FZ8H3QGB` | UNKNOWN / UNKNOWN | Intent | `BRAND_MODEL` | NONE | NONE |
| F | `springland dog water bottle` | `B0H4BL2L5W` | UNKNOWN / UNKNOWN | Intent | `BRAND_MODEL` | NONE | NONE |
| F | `dog travel accessories` | `B0H6VLRV6G` | travel / USE_CASE | Taxonomy route | `ACCESSORY_RELATED` | `buyer-need-query-taxonomy-route:d0e361591c845fc7720314b791a73ec2d3b38cd7ce7b0a61d6e2247dc68ed470` | `buyer-need-rule:d4875a8e54aaba818839cf7edbacb3ed07a1331a1bca429ff857d3c2542c76e1` |
| F | `dog bottle water` | `B0B9HV5GMD` | UNKNOWN / UNKNOWN | Intent | `PRODUCT_OBJECT` | NONE | NONE |
| F | `dog camping essentials` | `B07VT1468W` | UNKNOWN / UNKNOWN | Intent | `BROAD_QUERY` | NONE | NONE |
| F | `asobu water bottle` | `B0C1VCKG32` | UNKNOWN / UNKNOWN | Intent | `BRAND_MODEL` | NONE | NONE |
| F | `dog beach essentials` | `B0DG6MXT1R` | UNKNOWN / UNKNOWN | Intent | `BROAD_QUERY` | NONE | NONE |
| F | `rabbit water bottle` | `B0002EZIRY` | UNKNOWN / UNKNOWN | Intent | `OUT_OF_SCOPE` | NONE | NONE |
| F | `rabbit water dispenser` | `B0002Z15ZW` | UNKNOWN / UNKNOWN | Intent | `OUT_OF_SCOPE` | NONE | NONE |

The three Taxonomy-matched errors are corrected by Intent precedence before Taxonomy; no Taxonomy rule was deleted or narrowed.

## 11. SP-032E offline replay

One human `AMBIGUOUS` item is excluded, leaving 79 evaluated annotations.

| Metric | V0.2 | V0.3 |
|---|---:|---:|
| Human true Need | 40 | 40 |
| Predicted Need | 49 | 40 |
| True positive | 40 | 40 |
| False positive | 9 | 0 |
| False negative | 0 | 0 |
| Need Precision | 81.63% | 100% |
| Need Recall proxy | 100% | 100% |
| Predicted NON_NEED | 30 | 39 |
| NON_NEED Precision | 100% | 100% |
| True Need concretely resolved | 33/40 (82.50%) | 33/40 (82.50%) |

## 12. SP-032F offline replay

All 80 selected audit items have a non-ambiguous human judgement.

| Metric | V0.2 | V0.3 |
|---|---:|---:|
| Human true Need | 42 | 42 |
| Predicted Need | 50 | 42 |
| True positive | 42 | 42 |
| False positive | 8 | 0 |
| False negative | 0 | 0 |
| Need Precision | 84.00% | 100% |
| Need Recall proxy | 100% | 100% |
| Predicted NON_NEED | 30 | 38 |
| NON_NEED Precision | 100% | 100% |
| True Need concretely resolved | 35/42 (83.33%) | 35/42 (83.33%) |

## 13. V0.2 versus V0.3 and recall tradeoff

Combined over 159 evaluated annotations:

| Metric | V0.2 | V0.3 |
|---|---:|---:|
| Predicted Need | 99 | 82 |
| True positive | 82 | 82 |
| False positive | 17 | 0 |
| Need Precision | 82.83% | 100% |
| Need Recall proxy | 100% | 100% |
| Predicted NON_NEED | 60 | 77 |
| True negative | 60 | 77 |
| NON_NEED Precision | 100% | 100% |
| False negative | 0 | 0 |
| Concrete true-Need resolution | 68/82 (82.93%) | 68/82 (82.93%) |

The observed historical tradeoff is `+17.17` percentage points Need Precision with no measured Recall-proxy loss. Concrete Need resolution does not increase because Taxonomy V0.2 is deliberately unchanged. Selection bias is material: these items were selected under V0.2 and cannot estimate population or future recall.

## 14. Integrated Bowl regression

| Holdout | V0.2 candidate relations | V0.3 retained | Recall |
|---|---:|---:|---:|
| SP-032E | 48 | 48 | 100% |
| SP-032F | 32 | 32 | 100% |
| Combined | 80 | 80 | 100% |

`dog water bottle with built-in bowl` remains `NEED_CANDIDATE → Integrated Bowl`. The Product Object gate cannot intercept the explicit `built-in bowl` modifier.

## 15. Outdoor Portability regression

Two routing metrics are reported:

- Raw routing retention compares every V0.2 NEED_CANDIDATE relation containing the term. It includes known generic/accessory false positives.
- Target-context retention requires both a dog/pet qualifier and a target water bottle/bowl/dispenser object. It measures the intended regression boundary.

| Holdout | Signal | V0.2 raw / V0.3 retained | Raw retention | Target context retained | Target-context retention |
|---|---|---:|---:|---:|---:|
| E | portable | 460 / 459 | 99.78% | 434 / 434 | 100% |
| E | travel | 338 / 314 | 92.90% | 278 / 278 | 100% |
| E | walking | 70 / 67 | 95.71% | 67 / 67 | 100% |
| E | hiking | 18 / 8 | 44.44% | 7 / 7 | 100% |
| F | portable | 433 / 431 | 99.54% | 404 / 404 | 100% |
| F | travel | 295 / 282 | 95.59% | 252 / 252 | 100% |
| F | walking | 60 / 57 | 95.00% | 57 / 57 | 100% |
| F | hiking | 11 / 5 | 45.45% | 4 / 4 | 100% |

The low raw hiking retention is not evidence of valid-Need recall collapse: the removed repeated terms are non-target expressions such as `dog hiking gear`, `hiking snacks`, and generic `hiking water bottle`. The hiking Taxonomy rule remains present and is marked `WATCH`; `hiking dog water bottle` remains a tested Need candidate.

## 16. Test results

### TASK-SP-032H targeted suite

- `22 / 22` passed.
- Covers all 15 required scenarios plus context contract, explicit version selection, unsupported version rejection, unchanged Taxonomy version, E/F replay thresholds, and Outdoor target-context retention.
- Deterministic IDs: passed.
- Strict JSON round-trip: passed.
- V0.2 registry snapshot and direct-versus-selected replay: passed.

### Repository-wide suite

- `766` tests/load checks were attempted.
- `756` passed.
- `0` assertion failures.
- `10` collection/import errors all had the same pre-existing environment cause: declared dependency `rapidfuzz>=3.14,<4` is not installed in the available Python environment.
- No dependency was downloaded because this task maintained zero external/provider calls.

The missing dependency affects existing Semantic Clustering and modules that import it. It did not affect the isolated V0.3 targeted suite or offline holdout replay.

## 17. Not implemented

- No Taxonomy V0.3 and no new Buyer Need.
- No synonym additions to Buyer Need Taxonomy.
- No Semantic Clustering changes.
- No Crate or Insulated promotion.
- No Gap, Scoring, or Opportunity Policy changes.
- No LLM or embeddings.
- No provider calls, new Amazon data, or XiYou credit use.
- No claim that the error is solved on unseen data.
- No automatic promotion of secondary brand-query Need signals.

## 18. TASK-SP-032I preparation and next recommendation

The only next validation should be **TASK-SP-032I Fresh 100-ASIN Holdout Validation**.

Required protocol:

1. Freeze the V0.3 registry, gate IDs, Taxonomy V0.2 ID, and test fingerprints before collection.
2. Select 100 new ASINs with zero overlap against the historical `20 + 100 + 100` ASIN cohorts.
3. Keep category, marketplace, collection method, and annotation contract explicit.
4. Annotate without consulting the SP-032E/F keyword labels during judgement.
5. Report Need Precision, NON_NEED Precision, Need Recall proxy, FP/FN, AMBIGUOUS rate, Integrated Bowl recall, and portable/travel/walking/hiking target-context retention.
6. Treat V0.3 as validated only if the fresh holdout independently meets the thresholds; otherwise record issues without tuning on the fresh set in place.

**Next stage: TASK-SP-032I — Fresh 100-ASIN Holdout Validation.**
