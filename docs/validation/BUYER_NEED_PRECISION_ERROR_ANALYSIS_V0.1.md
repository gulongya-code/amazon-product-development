# BUYER NEED PRECISION ERROR ANALYSIS V0.1

## 1. Executive decision

**TASK-SP-032G COMPLETE**

Final decision: **B. REDESIGN_INTENT_CLASSIFIER**

Across two independent 100-ASIN holdouts, 17 audited `NEED_CANDIDATE` decisions were incorrect. Fourteen of the 17 (82.35%) did not match a Buyer Need Taxonomy rule at all: they entered through the low-confidence Intent fallback that preserves any query not covered by an enumerated high-precision NON_NEED rule. Only three errors produced a concrete Taxonomy Need, and Semantic Clustering caused none of the audited false positives.

The smallest effective next step is therefore a precision-oriented Intent v0.3 design: add structural product-object, out-of-scope audience, and related-product precedence gates before the fallback/Taxonomy route. This report proposes changes only; it does not implement them.

## 2. Scope, baseline, and evidence

- Baseline branch: `main`
- Baseline commit: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`
- SP-032E evidence: `ORGANIC_BUYER_NEED_HOLDOUT_100_V0.1.json` and its annotations
- SP-032F evidence: `ORGANIC_BUYER_NEED_TEMPORAL_HOLDOUT_V0.1.json` and its annotations
- SP-032E Need Precision: `40 / 49 = 81.63%` (`1` ambiguous excluded)
- SP-032F Need Precision: `42 / 50 = 84.00%`
- Both holdouts NON_NEED Precision: `100%`
- Taxonomy: `buyer-need-taxonomy-v0.2`
- Buyer Need rules: `buyer-need-rules-v0.2`
- Intent rules: `buyer-need-intent-rules-v0.2`
- Semantic rules: `semantic-normalization-rules-v0.1`
- Core model files modified: **0**
- API calls: **0**
- XiYou credits consumed: **0**
- Git commit created: **No**

This is an offline analysis of existing deterministic samples. Counts and counterfactuals apply to the audited annotations and are not estimates of future Amazon traffic without further validation.

## 3. False Positive Need corpus summary

| Measure | Result |
|---|---:|
| SP-032E incorrect NEED_CANDIDATE | 9 |
| SP-032F incorrect NEED_CANDIDATE | 8 |
| Audited false-positive events | 17 |
| Union unique keywords | 15 |
| Exact keywords repeated across both holdouts | 2 |
| False positives with concrete Taxonomy Need | 3 |
| False positives from no-rule Intent fallback | 14 |

The two exact repeated keywords are:

| Keyword | SP-032E ASIN | SP-032F ASIN | Repeated result |
|---|---|---|---|
| `springland dog water bottle` | `B0FZ8H3QGB` | `B0H4BL2L5W` | Product/brand query entered low-confidence Need fallback |
| `dog travel accessories` | `B0H8WQT1DV` | `B0H6VLRV6G` | Related-product head noun lost to the `travel` Taxonomy route |

## 4. False Positive Need Corpus

`INTENT_FALLBACK_NONE` means `matched_rule_id=None`, no Taxonomy candidate, and `UNKNOWN` predicted Need. Exact rule identities are listed after the table.

| # | Keyword | Holdout | Source ASIN | Predicted Need | Predicted Type | Rule ID | Human Label | Error Category | Failure Layer |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `animal water bottle` | E | `B08L7N8M4Z` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | AUDIENCE_FALSE_POSITIVE | QUERY_INTENT_CLASSIFICATION |
| 2 | `dog travel accessories` | E | `B0H8WQT1DV` | travel | USE_CASE | `TRAVEL_RULE` | INCORRECT | MULTI_INTENT_COLLISION | BUYER_NEED_TAXONOMY |
| 3 | `malsipree dog water bottle` | E | `B09V14YQGT` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 4 | `asobu` | E | `B08P5K8R5X` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 5 | `doggy water bottle` | E | `B0DZNGBXTS` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 6 | `cat water bottle` | E | `B0B51TY6MR` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | AUDIENCE_FALSE_POSITIVE | QUERY_INTENT_CLASSIFICATION |
| 7 | `dog hiking gear` | E | `B0B3DKHGRX` | outdoor hiking | USE_CASE | `HIKING_RULE` | INCORRECT | MULTI_INTENT_COLLISION | BUYER_NEED_TAXONOMY |
| 8 | `stanley dog bowl` | E | `B08P5K8R5X` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | RELATED_PRODUCT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 9 | `springland dog water bottle` | E | `B0FZ8H3QGB` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 10 | `springland dog water bottle` | F | `B0H4BL2L5W` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 11 | `dog travel accessories` | F | `B0H6VLRV6G` | travel | USE_CASE | `TRAVEL_RULE` | INCORRECT | MULTI_INTENT_COLLISION | BUYER_NEED_TAXONOMY |
| 12 | `dog bottle water` | F | `B0B9HV5GMD` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 13 | `dog camping essentials` | F | `B07VT1468W` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | BROAD_CONTEXT_AS_NEED | QUERY_INTENT_CLASSIFICATION |
| 14 | `asobu water bottle` | F | `B0C1VCKG32` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | PRODUCT_OBJECT_MISROUTED | QUERY_INTENT_CLASSIFICATION |
| 15 | `dog beach essentials` | F | `B0DG6MXT1R` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | BROAD_CONTEXT_AS_NEED | QUERY_INTENT_CLASSIFICATION |
| 16 | `rabbit water bottle` | F | `B0002EZIRY` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | AUDIENCE_FALSE_POSITIVE | QUERY_INTENT_CLASSIFICATION |
| 17 | `rabbit water dispenser` | F | `B0002Z15ZW` | UNKNOWN | UNKNOWN | `INTENT_FALLBACK_NONE` | INCORRECT | AUDIENCE_FALSE_POSITIVE | QUERY_INTENT_CLASSIFICATION |

### Rule identity registry

| Alias | Extraction Rule ID | Taxonomy Entry ID | Intent route ID |
|---|---|---|---|
| `TRAVEL_RULE` | `buyer-need-rule:d4875a8e54aaba818839cf7edbacb3ed07a1331a1bca429ff857d3c2542c76e1` | `buyer-need-taxonomy-entry:c035906473b76b6aa32ffa75e0d34a5d7df41465318d210d9b0db3e64878b149` | `buyer-need-query-taxonomy-route:d0e361591c845fc7720314b791a73ec2d3b38cd7ce7b0a61d6e2247dc68ed470` |
| `HIKING_RULE` | `buyer-need-rule:0d483c0f135fedabc6d5f342538d328cb70a2b480af69e0c21c3c4163d6b5fd5` | `buyer-need-taxonomy-entry:47d8a4fdf9d0573bdab52ec3dbe5da8d2c71183a3de31815eb7826d8fc20b3f4` | `buyer-need-query-taxonomy-route:3487a1dc90d9efb3dff932a35bea5a6ed99a50c6ea1a71c8aae98730c8a901d8` |
| `INTENT_FALLBACK_NONE` | — | — | `matched_rule_id=None`; low-confidence NEED_CANDIDATE fallback |

## 5. Error category distribution

Each false-positive event has one primary category. Categories not shown had zero audited events.

| Error Category | SP-032E | SP-032F | Total | Share |
|---|---:|---:|---:|---:|
| PRODUCT_OBJECT_MISROUTED | 4 | 3 | 7 | 41.18% |
| AUDIENCE_FALSE_POSITIVE | 2 | 2 | 4 | 23.53% |
| MULTI_INTENT_COLLISION | 2 | 1 | 3 | 17.65% |
| BROAD_CONTEXT_AS_NEED | 0 | 2 | 2 | 11.76% |
| RELATED_PRODUCT_MISROUTED | 1 | 0 | 1 | 5.88% |
| **Total** | **9** | **8** | **17** | **100%** |

No audited false positive was primarily classified as `ATTRIBUTE_WITHOUT_PREFERENCE`, `USE_CASE_FALSE_POSITIVE`, `COMPATIBILITY_FALSE_POSITIVE`, `RULE_TOO_BROAD`, `CONTEXT_MISSING`, `SEMANTIC_COLLAPSE_ERROR`, `ANNOTATION_DISAGREEMENT`, or `OTHER`. Context deficiencies still contribute to several errors and are analyzed separately below.

## 6. Repeated error patterns

### Cross-window repeated patterns

| Pattern | SP-032E | SP-032F | Total | Affected rules | Examples | Severity |
|---|---:|---:|---:|---|---|---|
| Bare product/brand/model query falls through as Need | 4 | 3 | 7 | `INTENT_FALLBACK_NONE` | `malsipree dog water bottle`; `asobu`; `springland dog water bottle`; `dog bottle water` | HIGH |
| Non-dog or indeterminate audience survives dog-category scope | 2 | 2 | 4 | `INTENT_FALLBACK_NONE` | `animal water bottle`; `cat water bottle`; `rabbit water bottle`; `rabbit water dispenser` | HIGH |
| Related-product head noun loses to a use-case token | 2 | 1 | 3 | `TRAVEL_RULE`, `HIKING_RULE` | `dog travel accessories`; `dog hiking gear` | HIGH |

All three patterns are `REPEATED_ERROR_PATTERN`: they occur under different ASINs and in both the recent and monthly holdouts. The exact phrase `dog travel accessories` and the exact brand/product phrase `springland dog water bottle` each repeat across both windows.

### Sample-specific patterns

| Pattern | SP-032E | SP-032F | Status | Action |
|---|---:|---:|---|---|
| Broad `essentials` context admitted as Need | 0 | 2 | SAMPLE_SPECIFIC | Record; do not create a rule from one window |
| Adjacent branded bowl admitted as Need | 1 | 0 | SAMPLE_SPECIFIC | Record; do not patch from one event |

## 7. Rule-level precision audit

Precision excludes `AMBIGUOUS` from the denominator, consistent with SP-032E/F. Status thresholds are SAFE `>=95%`, WATCH `85%-<95%`, and HIGH_RISK `<85%`.

| Rule | E matched | E correct | E incorrect | E precision | F matched | F correct | F incorrect | F precision | Combined matched | Combined correct | Combined incorrect | Combined precision | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `travel` / `TRAVEL_RULE` | 14 | 12 | 1 | 92.31% | 12 | 11 | 1 | 91.67% | 26 | 23 | 2 | 92.00% | WATCH |
| `outdoor hiking` / `HIKING_RULE` | 1 | 0 | 1 | 0.00% | 0 | 0 | 0 | UNKNOWN | 1 | 0 | 1 | 0.00% | HIGH_RISK |

Notes:

- The `travel` rule has repeatable but bounded context leakage. Removing it wholesale is not justified: it has 23 correct, two incorrect, and one ambiguous audited match.
- `HIKING_RULE` is mechanically HIGH_RISK under the threshold, but `n=1` and it did not recur in SP-032F. It belongs on the Do Not Fix list pending more evidence.
- Fourteen of the 17 false positives have no Taxonomy rule, so no Taxonomy rule-level precision can be assigned to them.

## 8. Failure-layer distribution

The table assigns one primary failure layer per false-positive event. For the three Taxonomy-route failures, Intent precedence is a contributing boundary issue, but the concrete false Need and high-confidence route were created by the Taxonomy match.

| Failure Layer | Count | Share | Evidence |
|---|---:|---:|---|
| QUERY_INTENT_CLASSIFICATION | 14 | 82.35% | No NON_NEED rule matched; query defaulted to low-confidence NEED_CANDIDATE with no predicted Taxonomy Need |
| BUYER_NEED_TAXONOMY | 3 | 17.65% | `travel` or `hiking` token produced a concrete USE_CASE Need despite `accessories`/`gear` product context |
| SEMANTIC_CLUSTERING | 0 | 0.00% | Every audited error existed before clustering; no wrong cluster merge created these labels |
| **Total** | **17** | **100%** | |

This distribution answers the core question: the 16%-18% Need Precision gap is primarily an Intent admission problem, not a Semantic Clustering problem and not mainly a Taxonomy synonym problem.

## 9. Context requirement audit

### Context gating opportunities — proposals only

| Opportunity | Evidence in E | Evidence in F | Missing condition | Expected protection | Risk if over-applied |
|---|---:|---:|---|---|---|
| Product-object/brand gate before fallback | 4 | 3 | Detect bare brand/model plus product-head structure; require explicit preference/Need evidence | Stops repeated brand/product queries from becoming unresolved Need candidates | Emerging brands and genuine branded attribute searches could be suppressed |
| Audience scope gate | 2 | 2 | In dog scope, require dog/pet qualifier or explicitly route cat/rabbit/other-animal audiences OUT_OF_SCOPE | Stops stable non-dog audience leakage | Generic `pet` or multi-animal products may be wrongly excluded |
| Related-product head precedence | 2 | 1 | `accessories`, `gear`, and equivalent product heads should outrank embedded `travel`/`hiking` tokens | Prevents multi-intent product queries from becoming USE_CASE Needs | Genuine queries for travel-compatible accessories could lose recall |
| Explicit preference evidence | 4 | 3 | A product noun alone is not a preference; require a matched Need phrase, constraint, problem, audience, or use-case relationship | Separates product discovery from buyer preference | A strict gate would remove correct but unresolved hypotheses |
| Phrase-bound use-case context | 2 | 1 | Apply `travel`/`hiking` only when attached to the target product/use, not merely present anywhere in the query | Contains WATCH/HIGH_RISK use-case leakage | Complex natural-language word order could be missed |

The contrast between `insulated water bottle` and `insulated dog water bottle` illustrates the general principle, but Insulated is proposal-only and none of the 17 audited false-positive events justifies changing it here.

## 10. Need Type precision

This table covers concrete Taxonomy matches within the two deterministic 50-term NEED_CANDIDATE audits. `matched` includes ambiguous labels; precision uses only correct plus incorrect. Fourteen incorrect fallback rows have no Need Type and are reported separately.

| Need Type | Matched | Correct | Incorrect | Ambiguous | Precision |
|---|---:|---:|---:|---:|---:|
| USE_CASE | 33 | 29 | 3 | 1 | 90.63% |
| AUDIENCE | 3 | 3 | 0 | 0 | 100.00% |
| PROBLEM_SOLUTION | 1 | 1 | 0 | 0 | 100.00% |
| ATTRIBUTE_NEED | 26 | 26 | 0 | 0 | 100.00% |
| SPECIFICATION_PREFERENCE | 5 | 5 | 0 | 0 | 100.00% |
| COMPATIBILITY | 4 | 4 | 0 | 0 | 100.00% |

`USE_CASE` is the only concrete Need Type with audited false positives and therefore the least precise type. The larger risk remains outside typed Taxonomy matches: the no-rule fallback has 14 correct and 14 incorrect audited rows, or 50.00% precision.

## 11. Outdoor Portability deep audit

### Deterministic audited-term precision

| Expression family | E matched | E correct | E incorrect | E precision | F matched | F correct | F incorrect | F precision | Combined correct | Combined incorrect | Combined precision | False-positive examples |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| portable | 12 | 12 | 0 | 100.00% | 12 | 12 | 0 | 100.00% | 24 | 0 | 100.00% | None |
| travel | 14 | 12 | 1 | 92.31% | 12 | 11 | 1 | 91.67% | 23 | 2 | 92.00% | `dog travel accessories` in E and F |
| walking | 3 | 3 | 0 | 100.00% | 3 | 3 | 0 | 100.00% | 6 | 0 | 100.00% | None |
| hiking | 1 | 0 | 1 | 0.00% | 0 | 0 | 0 | UNKNOWN | 0 | 1 | 0.00% | `dog hiking gear` in E only |

`travel` E has one additional `AMBIGUOUS` term (`travel water bottle`), excluded from precision.

Across the four expression families, the adjudicated denominator is 56: 53 correct and three incorrect, giving **94.64% audited precision** and **5.36% audited false-positive share**. One additional term is ambiguous.

### Full-corpus dominance context

| Measure | SP-032E | SP-032F | Combined |
|---|---:|---:|---:|
| Raw outdoor-expression relations | 885 | 802 | 1,687 |
| Outdoor relations matched to Need | 885 | 801 | 1,686 |
| Raw-to-matched alignment | 100.00% | 99.88% | 99.94% |
| Source ASIN coverage | 90/100 | 86/100 | Not additive across holdouts |

Conclusion: Outdoor Portability dominance is primarily data-driven. Raw organic keywords contain the frozen portable/travel/walking/hiking expressions across most ASINs, and portable/walking are perfectly precise in the audited sample. The rules still contribute a localized 5.36% false-positive share among adjudicated outdoor matches, concentrated in multi-intent related-product queries. Full-corpus alignment is not itself precision and must not be presented as 99.94% semantic correctness.

## 12. Integrated Bowl precision stability

| Holdout | Relations | Source ASINs | Correct | False positives | Precision |
|---|---:|---:|---:|---:|---:|
| SP-032E | 48 | 48 | 48 | 0 | 100.00% |
| SP-032F | 32 | 32 | 32 | 0 | 100.00% |
| Combined | 80 | Not additive | 80 | 0 | 100.00% |

Status: **HIGH_CONFIDENCE_STABLE_RULE**

The exact `built-in bowl` rule contrasts sharply with the Intent fallback and broad use-case tokens: it has explicit phrase boundaries, target-product context, independent cross-window support, and zero annotated false positives. No modification is recommended.

## 13. Minimal Fix Set proposal

These are proposals for the next task, not changes made by SP-032G. Each item is supported in both holdouts.

| Fix | Problem | Affected boundary/rule | Two-window evidence | Offline expected precision gain | Offline expected recall loss | Future false-positive/negative risk | Required version bump |
|---|---|---|---|---|---|---|---|
| FIX-1 | Bare product/brand/model queries default to Need | Low-confidence `matched_rule_id=None` Intent fallback | E: 4 FP; F: 3 FP | F 84.00% → 89.36% standalone; combined 82.83% → 89.13% | 0 annotated correct Need rows under exact retrospective targeting; future loss UNKNOWN | Medium: generic product phrasing can contain implicit need | `buyer-need-intent-rules-v0.3`; Taxonomy unchanged |
| FIX-2 | Non-dog audiences survive dog scope | Intent audience/out-of-scope gate | E: 2 FP; F: 2 FP | F 84.00% → 87.50% standalone; after FIX-1 → 93.33% | 0 observed; future loss UNKNOWN | Low-to-medium: generic `pet`/multi-animal queries | `buyer-need-intent-rules-v0.3`; Taxonomy unchanged |
| FIX-3 | `travel`/`hiking` token outranks `accessories`/`gear` product head | Intent precedence before `TRAVEL_RULE`/`HIKING_RULE` Taxonomy route | E: 2 FP; F: 1 FP; exact `dog travel accessories` repeated | F 84.00% → 85.71% standalone; FIX-1+2+3 → 95.45% | 0 observed; future loss UNKNOWN | Medium: true use-case searches involving accessories may be suppressed | `buyer-need-intent-rules-v0.3`; Taxonomy remains v0.2 unless implementation changes rule context |

The three-fix retrospective oracle removes 8/9 E false positives and 6/8 F false positives while retaining all 82 annotated correct Need rows:

- SP-032E: `81.63% → 97.56%`
- SP-032F: `84.00% → 95.45%`
- Combined: `82.83% → 96.47%`

These are upper-bound replay results using known error categories. They are not guaranteed future performance; the proposed gates require a new holdout after implementation.

## 14. Do Not Fix list

| Item | Why it should not be changed now |
|---|---|
| Remove or broadly narrow `travel` | 23 correct versus two incorrect audited matches; wholesale removal reduces precision and recall |
| Remove Outdoor Portability cluster/rules | Portable and walking are 100% precise in the audit; dominance is supported by raw data |
| Patch `HIKING_RULE` from one event | 0% observed precision is based on `n=1`, appears only in E, and did not reproduce in F |
| Add a rule for `camping essentials` or `beach essentials` | Both occur only in F; no cross-window support |
| Add a special case for `stanley dog bowl` | Single E event; brand-specific patches would recreate enumeration overfit |
| Change Integrated Bowl | 80/80 validated relations, zero false positives, stable across windows |
| Promote or modify Crate | It remains experimental; this task has no promotion authority |
| Promote or modify Insulated | It remains proposal-only and is outside the 17-error evidence basis |
| Redesign Semantic Clustering | Zero audited false positives originate at the clustering layer |
| Add synonyms or new Needs | The dominant failure occurs before Taxonomy matching; synonyms would not fix 14/17 errors |
| Resolve annotation disagreements | No false-positive event is classified as ANNOTATION_DISAGREEMENT; ambiguous labels remain excluded |

## 15. Offline counterfactual precision/recall tradeoff

All scenarios replay the existing 100 audited NEED_CANDIDATE terms. `Observed correct-Need retention` is recall relative to the 82 currently annotated-correct terms, not population recall.

| Counterfactual | E precision | F precision | Combined precision | Observed correct-Need retention | Interpretation |
|---|---:|---:|---:|---:|---|
| Current v0.2 | 81.63% | 84.00% | 82.83% | 100.00% | Baseline: 82 correct, 17 incorrect, one ambiguous |
| Route every no-rule fallback to NON_NEED | 94.29% | 97.22% | 95.77% | 82.93% | Removes 14 false positives but also 14 correct unresolved Need hypotheses; too blunt |
| Repeated PRODUCT_OBJECT gate only | 88.89% | 89.36% | 89.13% | 100.00% in annotations | Useful but not sufficient alone |
| PRODUCT_OBJECT + AUDIENCE gates | 93.02% | 93.33% | 93.18% | 100.00% in annotations | Cross-window evidence supports both boundaries |
| PRODUCT_OBJECT + AUDIENCE + MULTI_INTENT precedence | 97.56% | 95.45% | 96.47% | 100.00% in annotations | Best retrospective minimal set; requires new holdout validation |
| Remove only `travel` rule | Lower than current | Lower than current | 79.73% | 71.95% | Removes 23 correct and two incorrect; reject |

The strict no-rule fallback counterfactual demonstrates why simply changing UNKNOWN-like Need hypotheses to NON_NEED is unsafe: it improves precision but loses 17.07% of annotated correct Need evidence. Structural gates are preferable to blanket rejection.

## 16. Unique next-step decision

**B. REDESIGN_INTENT_CLASSIFIER**

Why this is the smallest effective next step:

1. `14/17` false positives originate in the no-rule Intent fallback.
2. The remaining three can be addressed by Intent precedence/context before Taxonomy routing.
3. Taxonomy matched rules are generally precise; only USE_CASE shows localized leakage.
4. Semantic Clustering contributes zero audited false positives.
5. A Taxonomy-only patch cannot correct queries for which no Taxonomy rule matched.

Recommended next task: design and holdout-test `buyer-need-intent-rules-v0.3` with only FIX-1 through FIX-3. Keep Taxonomy v0.2, Crate, Insulated, Semantic rules, Gap, Scoring, and Opportunity Policy frozen until that new validation is complete.

## Appendix A — Complete provenance for 17 false-positive events

Every row preserves `ASIN → organic keyword → intent → Taxonomy rule/fallback → predicted Need → human audit`. `qex` is the Canonical query execution/request reference; `raw` is the captured provider response evidence reference.

| # | Holdout | Keyword | ASIN | Intent / rule | Predicted Need | qex request reference | raw response reference | Human audit |
|---:|---|---|---|---|---|---|---|---|
| 1 | E | `animal water bottle` | `B08L7N8M4Z` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:d332feafb41ac3973a5804f934d7a985f4e4dc1635afc933e0d43b30c12a052c` | `raw:b5c9b87ef8d60fe9614b6084ce053fc5f81baff673c6b60840ff4101c187f01c` | INCORRECT |
| 2 | E | `dog travel accessories` | `B0H8WQT1DV` | NEED_CANDIDATE / `TRAVEL_RULE` | travel | `qex:c22f033b5b65c037d1526e62f2167ff1435f24f72f43226c82dbfbc3d8854a07` | `raw:fffe29f00d685c2bbac511fb37168469919ac1975e12a240380e715fc7e8af81` | INCORRECT |
| 3 | E | `malsipree dog water bottle` | `B09V14YQGT` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:7993d75e875af083102a00f1f7914e99c9789c4b048bc5c201ea702c107524d1` | `raw:b22e29e72eb317de9ebb5d49ad73cf3726240bf0c51504e0534f947578d7a8a6` | INCORRECT |
| 4 | E | `asobu` | `B08P5K8R5X` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:0283866712c4fa7d6234cea7063547c872b38f160d370e8e8ae9d1592188c1cd` | `raw:14405e59aded4b6fd71bde370bc007500442ff46424eaa4e4702a8c03b1860cf` | INCORRECT |
| 5 | E | `doggy water bottle` | `B0DZNGBXTS` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:76545f60f545b33ffb3469192eda21fad8147d197f54df93a334a622ea134dd6` | `raw:bedc4d6fd0611b610a7c7d4afe6e22a5a1da347d2d66dfab93cb194613873552` | INCORRECT |
| 6 | E | `cat water bottle` | `B0B51TY6MR` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:a8259d8c0efa5b42478c44bc90bd6cd245b6f6ad868673be69febf27336fcf2c` | `raw:a8f1f10b533b04fbd1e26f8adbb7b89916853affc5b6ba142c477f574db9bd3c` | INCORRECT |
| 7 | E | `dog hiking gear` | `B0B3DKHGRX` | NEED_CANDIDATE / `HIKING_RULE` | outdoor hiking | `qex:e3e923c48304bb11f131160a41bd605c1a668950fdea66545f0185b136ced79a` | `raw:196cf35da33134823a989691ca265c34febfff527fd300706597ba5ebf874746` | INCORRECT |
| 8 | E | `stanley dog bowl` | `B08P5K8R5X` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:0283866712c4fa7d6234cea7063547c872b38f160d370e8e8ae9d1592188c1cd` | `raw:14405e59aded4b6fd71bde370bc007500442ff46424eaa4e4702a8c03b1860cf` | INCORRECT |
| 9 | E | `springland dog water bottle` | `B0FZ8H3QGB` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:4678f968e3be8927158804c4cfa6cfcb4bf1bf650b0a987f647f233dcf65b1e9` | `raw:551cb625591254df9c8a7d7869726eb057ee0e57c210d3563c49929bb5d8825a` | INCORRECT |
| 10 | F | `springland dog water bottle` | `B0H4BL2L5W` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:f6511d74756f59137d61f71648eb8c0e12be69f8f7a2336422eddf3d6305e149` | `raw:524784d100cb47b2777c4bcc4478dd6743a964abe882f63d173f263c04afce0e` | INCORRECT |
| 11 | F | `dog travel accessories` | `B0H6VLRV6G` | NEED_CANDIDATE / `TRAVEL_RULE` | travel | `qex:9464763072e0f79fd43b83dcd72eb41e7f75f6ec2aa25d888cca21bc6233eaad` | `raw:623814817855f964e0d3d5e14ffc0d901636fb17378f9bf6a67210e2c866e318` | INCORRECT |
| 12 | F | `dog bottle water` | `B0B9HV5GMD` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:cacc52394b80ef8956482348137d156b7828c5e08ed11ea182522b46126e3329` | `raw:ac93ff3d2ea7a5ccca923641bf6d989defc83f32e16e28e61dc2e5477bfb13e0` | INCORRECT |
| 13 | F | `dog camping essentials` | `B07VT1468W` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:37fec56795b496c230603594c9ae98245791d27e080f2689b1246a59d3b7b038` | `raw:88e1ecfdcf21728b7647b9da89295f5c51c073475eda28f70f58421f33b93ee1` | INCORRECT |
| 14 | F | `asobu water bottle` | `B0C1VCKG32` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:5b0c67fbd692de2844a010efb86f53f303e9dd1a26cc1ac5781bb6cf4db1925e` | `raw:fda0a2c360a456d24ee08ccea798710acacb01a5de18642e0207dd5bd9c153a9` | INCORRECT |
| 15 | F | `dog beach essentials` | `B0DG6MXT1R` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:b93fd3f71beb3c99c0acbecdfb20d0d75ed5311c553f089fd6b5ddf8a1e44fc4` | `raw:accef5a598eac935f8b92993f002aa3a2dbaf207b26d9b845a262456bff680cb` | INCORRECT |
| 16 | F | `rabbit water bottle` | `B0002EZIRY` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:c7bdb32f55b97ebbefc641e885fac2f5bc9c730018f5f383f2fb5312923174fb` | `raw:4780d22057554c07d3da67ffcab1b319eb0b30350a438f6a2ebbde1423964b4e` | INCORRECT |
| 17 | F | `rabbit water dispenser` | `B0002Z15ZW` | NEED_CANDIDATE / fallback | UNKNOWN | `qex:c6747ed3727a23af69545b9279c18a2ff7dd6f58fae3f23827ff6dab71bda250` | `raw:9e52c5a3e37f19d82ee1579d30f173e71210fb5b9f0f4d48f2cfdf460f688aae` | INCORRECT |

## Appendix B — Completion declaration

- Baseline recorded: **Yes**
- E false positives recovered: **9**
- F false positives recovered: **8**
- False Positive Need Corpus complete: **17/17**
- Error categories complete: **17/17**
- Cross-window repeated patterns analyzed: **Yes**
- Rule precision table complete: **Yes**
- Failure-layer distribution complete: **Yes**
- Need Type precision complete: **Yes**
- Outdoor Portability deep audit complete: **Yes**
- Integrated Bowl stability confirmed: **Yes**
- Minimal Fix Set proposed but not implemented: **Yes**
- Do Not Fix list recorded: **Yes**
- Offline counterfactual only: **Yes**
- Unique next decision: **REDESIGN_INTENT_CLASSIFIER**
- Core model files modified: **0**
- API calls: **0**
- XiYou credits: **0**
