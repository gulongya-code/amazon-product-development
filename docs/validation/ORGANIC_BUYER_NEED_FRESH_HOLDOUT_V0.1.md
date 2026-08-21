# TASK-SP-032I Fresh 100-ASIN Holdout Validation v0.1

## 1. Executive result

Final decision: **A. V0.3_STABLE**.

Fresh precision meets the ideal Need target and all required regression gates.

- Baseline commit: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`
- Marketplace/category: `US` / Amazon US > Pet Supplies > Dog Travel Water Bottles
- Retrieval time: `2026-08-21T08:21:25+00:00`
- Window: `last7days` — Current rolling seven-day provider window; later than the prior last7days capture. Official docs did not establish last30days as a supported enum.
- Fresh cohort: `100` child-ASIN product rows; historical exclusion union: `220`; overlap: `0`
- API calls / actual known credits: `101` / `120`
- Credit estimate / gate: `120` / `150`
- Frozen fingerprints identical: `true`
- Files in frozen model/rule scope modified: `0`

## 2. Frozen system and holdout contract

The evaluated stack is `buyer-need-intent-rules-v0.3` + `buyer-need-taxonomy-v0.2` + the existing semantic-clustering registry. Start/end registry and source SHA-256 fingerprints are embedded in the machine-readable snapshot. No alias, intent rule, taxonomy entry, semantic threshold, Gap rule, score formula, policy, LLM, or embedding model was changed.

Selection was deterministic: query `dog water bottle`, XiYou `keyword_asin_analysis`, page `1`, page size `400`, `traffic desc`; retain provider order, deduplicate, exclude SP-032B/E/F 220-ASIN union, take the first 100. Selected provider ranks span `122`–`269`; provider total was `666`. Product grain follows the XiYou ASIN product-row contract; parent ASIN remains UNKNOWN when not returned.

`last30days` was not used because the official recent-days documentation only established the example value `last7days`; a trial call would have spent credits. This run used the current rolling `last7days`, whose dates have advanced since the earlier E capture.

## 3. Provider calls and credit audit

- 1 × `keyword_asin_analysis`, page 1 / up to 400 rows.
- 100 × `asin_keywords`, page 1 / top 20 rows per ASIN.
- No keyword enrichment call; no retry-based period probing.
- Every successful response was checkpointed immediately.
- Official billing upper bound before calls: `ceil(400/20) + 100×ceil(20/20) = 120` credits, below the 150-credit gate.
- Actual provider-reported known credits: `120`; calls with unknown credit metadata: `0`.

## 4. Organic keyword corpus

- Raw ASIN-keyword relations: `1872`
- Unique normalized keywords: `339`
- Source ASINs: `100`
- Duplicate relation count: `1533`

## 5. V0.3 intent distribution

| Intent | Relations |
|---|---:|
| `ACCESSORY_RELATED` | 42 |
| `AMBIGUOUS` | 109 |
| `BRAND_MODEL` | 147 |
| `BROAD_QUERY` | 28 |
| `NEED_CANDIDATE` | 997 |
| `OUT_OF_SCOPE` | 58 |
| `PRODUCT_OBJECT` | 491 |

## 6. Buyer Need / semantic distribution

| Semantic cluster | Relations | ASINs | ASIN coverage |
|---|---:|---:|---:|
| Outdoor Portability | 668 | 84 | 84.00% |
| Walking Need | 81 | 42 | 42.00% |
| Integrated Bowl Need | 33 | 33 | 33.00% |
| Stainless Steel Need | 23 | 23 | 23.00% |
| Small Dogs Need | 23 | 21 | 21.00% |
| Compact Size Collapsible Structure Need | 29 | 16 | 16.00% |
| Leak Prevention | 20 | 13 | 13.00% |
| Large Dogs Need | 13 | 12 | 12.00% |
| Compatibility Requirement Need | 9 | 6 | 6.00% |

ASIN coverage is recurrence within this cohort, not Demand Share.

## 7. Manual precision audit

The deterministic audit selected `50` V0.3 Need predictions and `30` V0.3 NON_NEED predictions. Labels use the same semantic standard as SP-032E/F; AMBIGUOUS and UNREVIEWED are excluded from precision denominators.

| Group | Correct | Incorrect | Ambiguous | Unreviewed | Precision | Target |
|---|---:|---:|---:|---:|---:|---:|
| Need | 49 | 1 | 0 | 0 | 98.00% | ≥90% (ideal ≥93%) |
| NON_NEED | 30 | 0 | 0 | 0 | 100.00% | ≥95% |

## 8. Integrated Bowl regression

- Fresh raw Integrated/Built-in Bowl expressions: `33`
- Routed to the unchanged Integrated Bowl taxonomy entry: `33`
- Recall: `100.00%`

## 9. Outdoor portability regression

| Expression | Raw relations | Raw ASINs | Target-context relations | Retained | Routing recall |
|---|---:|---:|---:|---:|---:|
| portable | 400 | 81 | 365 | 365 | 100.00% |
| travel | 273 | 72 | 215 | 215 | 100.00% |
| walking | 87 | 46 | 81 | 81 | 100.00% |
| hiking | 21 | 20 | 19 | 19 | 100.00% |

The target-context denominator requires both a dog/pet qualifier and a target bottle/bowl/dispenser object. Generic accessory phrases are not counted as a target-product recall failure.

## 10. Precision error analysis

| Error type | Count |
|---|---:|
| AMBIGUOUS_CONTEXT | 1 |

Incorrect items, reasons, predicted intent, ASIN lineage, and error type are preserved in the JSON analysis and annotation artifacts. No correction was made during this task.

Cross-holdout judgement: **LOW_FREQUENCY_STRUCTURAL_BLIND_SPOT_WATCH**. The bare broad-context query 'dog travel' exposes the taxonomy-with-category route when no water or target-product object is present. It is new in I, not a repeated SP-032E/F V0.3 error, and remains below the precision gate.

## 11. SP-032E / F / I comparison

| Holdout | Need precision | NON_NEED precision | FP | FN | Audited items |
|---|---:|---:|---:|---:|---:|
| SP-032E | 100.00% | 100.00% | 0 | 0 | 79 |
| SP-032F | 100.00% | 100.00% | 0 | 0 | 80 |
| SP-032I | 98.00% | 100.00% | 1 | 0 | 80 |

E/F are offline replays of their saved human-labelled samples under the same frozen V0.3 classifier. I is the first completely fresh ASIN and keyword sample, so it is the controlling anti-overfit evidence.

## 12. New valid Buyer Need proposals

No new Buyer Need is asserted merely from an UNKNOWN or repeated token. A proposal requires repeated fresh evidence plus manual confirmation that the expression is a target-product need rather than a brand, accessory, product object, or context fragment. Fresh proposal count: `0`.

## 13. Final decision and next step

**A. V0.3_STABLE** — Fresh precision meets the ideal Need target and all required regression gates.

Unique next step:

- Freeze V0.3 as validated and proceed to broader-category validation.

## 14. Limitations

1. Only page 1 / top 20 reverse keywords per ASIN were captured.
2. `last30days` support was not proven, so the current rolling `last7days` was used.
3. Provider traffic semantics are provider-defined and uncalibrated.
4. Parent ASIN is UNKNOWN when omitted by the provider.
5. Manual term judgement is not Amazon behavioral ground truth.

## 15. Artifacts and immutability

- Raw checkpoint: `docs/validation/ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.raw.json`
- Manual annotations: `docs/validation/ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.annotations.json`
- Machine-readable analysis: `docs/validation/ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.json`
- This report: `docs/validation/ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.md`
- Git commit created: `0`
- Frozen production/rule files modified: `0`
