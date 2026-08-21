# ORGANIC BUYER NEED TEMPORAL HOLDOUT V0.1

## 1. Executive decision

**TASK-SP-032F COMPLETE — SYSTEMATIC_GENERALIZATION_PROBLEM**

The unique next recommendation is **TASK-SP-032G Need Precision Error Analysis**

This result answers whether the TASK-SP-032E 81.63% Need Precision finding replicates under an independent cohort and a different explicit provider window. It does not modify the frozen Taxonomy or rules.

## 2. Baseline and frozen versions

- Baseline commit: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`
- Taxonomy: `buyer-need-taxonomy-v0.2`
- Buyer Need rules: `buyer-need-rules-v0.2`
- Intent rules: `buyer-need-intent-rules-v0.2`
- Semantic contract: `semantic-clustering-contract-v0.1`
- Semantic rules: `semantic-normalization-rules-v0.1`
- Start/end fingerprints identical: **True**
- Taxonomy/Rules modified: **0**

| Registry | Identity | SHA-256 |
| --- | --- | --- |
| buyer_need_intent_registry_v0_2 | buyer-need-query-intent-registry:099d6df1ed74a0e5098b98389e4472bb2eecb873881a907124fed21c34d04468 | 2546f9b7458be2a324d057a3bac12459a459633e9e4ed0d42a39aac6484bddd9 |
| buyer_need_taxonomy_v0_2 | buyer-need-taxonomy:0ba5ae58893082b34cbaaa2476a0d0747747a0114eb43b845cccd513936f0860 | 8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6 |
| semantic_normalization_registry_v0_1 | semantic-normalization-registry:b713123582646196d7b23c6dd2104a7b8f669211a57f64dc1207668bcb94426b | 49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2 |

## 3. Temporal window and provider contract

- TASK-SP-032E period: `last7days`
- TASK-SP-032F period: `2026-07`
- Semantics: XiYou explicit monthly window, 2026-07 through 2026-07
- Selection timing: The latest complete calendar month was selected before provider data capture.
- Provider API overview: <https://openapi-doc.xydc.com/>
- Previous reverse contract: <https://openapi-doc.xydc.com/331502595e0>
- Monthly reverse contract: <https://openapi-doc.xydc.com/331594504e0>
- Monthly cohort contract: <https://openapi-doc.xydc.com/451506681e0>

The recent reverse contract exposes `last7days`; the monthly endpoint is therefore used for the preselected latest complete calendar month (2026-07). No provider result was inspected before choosing the window.

## 4. Independent cohort

- Marketplace: `US`
- Category: Amazon US > Pet Supplies > Dog Travel Water Bottles
- Seed query: `dog water bottle`
- Independent Child ASINs: **100**
- Historical exclusions: **120**
- Overlap with prior 120 ASINs: **0**
- Provider total: **883**
- Selection: page 1, provider traffic descending, response order; exclude prior 120, deduplicate, then take first 100.
- Excluded rows encountered before the 100th selected ASIN: **{'EXCLUDED_SP032B_ASIN': 20, 'EXCLUDED_SP032E_ASIN': 81}**

## 5. API calls and credits

| Measure | Value |
| --- | --- |
| Estimated credits | 115 |
| Credit gate | 150 |
| Actual known credits | 115 |
| Unknown-credit calls | 0 |
| Request count | 101 |

| Operation | Calls | Known credits |
| --- | --- | --- |
| asin_keywords_monthly | 100 | 100 |
| keyword_asin_analysis_monthly | 1 | 15 |

## 6. Organic discovery corpus

| Measure | Value |
| --- | --- |
| Raw ASIN-keyword relations | 1988 |
| Unique keywords | 343 |
| Cross-ASIN duplicate relations | 1645 |
| Source ASINs | 100 |
| Successful ASINs | 100 |
| Failed ASINs | 0 |
| Empty ASINs | 0 |
| Traffic availability | {'AVAILABLE': 1988} |
| Organic rank availability | {'ORGANIC_RANK_AVAILABLE': 1631, 'ORGANIC_RANK_UNKNOWN': 357} |

## 7. Frozen Taxonomy v0.2 results

| Intent | SP-032E | SP-032F |
| --- | --- | --- |
| NEED_CANDIDATE | 1365 | 1369 |
| PRODUCT_OBJECT | 419 | 378 |
| BRAND_MODEL | 132 | 203 |
| ACCESSORY_RELATED | 27 | 14 |
| BROAD_QUERY | 25 | 15 |
| OUT_OF_SCOPE | 5 | 9 |
| AMBIGUOUS | 1 | 0 |

| Resolution | SP-032F count |
| --- | --- |
| EXPLICIT_NON_NEED | 619 |
| RESOLVED_BUYER_NEED | 930 |
| UNKNOWN_NEED_CANDIDATE | 439 |

True Need Resolution: **77.92%**. Unresolved Rate: **22.08%**.

## 8. Precision audit

| Audit group | Selected | Correct | Incorrect | Ambiguous | Unreviewed | Precision |
| --- | --- | --- | --- | --- | --- | --- |
| NEED_CANDIDATE | 50 | 42 | 8 | 0 | 0 | 84.00% |
| NON_NEED | 30 | 30 | 0 | 0 | 0 | 100.00% |

The deterministic sample uses the same SP-032E rule: top 50 unique NEED_CANDIDATE terms and an intent-stratified 30-term NON_NEED sample. AMBIGUOUS is excluded from the precision denominator; no label standard was changed.
Exact normalized terms previously adjudicated in SP-032E retain that judgement; SP-032F independently reviews new terms and may explicitly override only with a recorded reason. The companion annotations file records this reference policy.

## 9. SP-032E vs SP-032F

| Metric | SP-032E | SP-032F | Delta |
| --- | --- | --- | --- |
| Raw relations | 1974 | 1988 | — |
| Unique keywords | 285 | 343 | — |
| True Need Resolution | 82.07% | 77.92% | — |
| Unresolved Rate | 17.93% | 22.08% | — |
| Need Precision | 81.63% | 84.00% | 2.37 pp |
| NON_NEED Precision | 100.00% | 100.00% | 0.00 pp |

| Buyer Need cluster | SP-032E relations | SP-032F relations |
| --- | --- | --- |
| 24 Oz Need | 0 | 1 |
| 30 Oz Need | 1 | 0 |
| Compact Size Collapsible Structure Need | 16 | 27 |
| Compatibility Requirement Need | 22 | 16 |
| Integrated Bowl Need | 48 | 32 |
| Kids Need | 0 | 6 |
| Large Dogs Need | 5 | 8 |
| Leak Prevention | 9 | 16 |
| Outdoor Portability | 816 | 741 |
| Small Dogs Need | 12 | 10 |
| Stainless Steel Need | 20 | 22 |
| Walking Need | 70 | 60 |

## 10. Need-specific replication

| Need | E relations | F relations | E ASINs | F ASINs | E precision | F precision | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Integrated Bowl | 48 | 32 | 48 | 32 | 100.00% | 100.00% | STABLE |
| Collapsible | 16 | 27 | 13 | 15 | 93.75% | 85.19% | VARIABLE |
| Crate Compatibility | 22 | 16 | 13 | 9 | 100.00% | 100.00% | KEEP_EXPERIMENTAL |

Crate remains **EXPERIMENTAL**; expression diversity in SP-032F is **2**. It was not promoted.

Insulated remains **PROPOSAL_ONLY**. SP-032F dog-specific/generic/branded relations: **26 / 2 / 35**; source ASINs: **36**; decision: **KEEP_PROPOSAL**.

Outdoor Portability decision: **DATA_DRIVEN_DOMINANCE**. SP-032E raw outdoor relations/ASINs: **885 / 90**; SP-032F: **802 / 86**. This comparison uses raw frozen-rule expressions, not inferred Demand Share.

| Expression | E relations | F relations | E ASINs | F ASINs |
| --- | --- | --- | --- | --- |
| portable | 460 | 433 | 89 | 83 |
| travel | 338 | 298 | 82 | 80 |
| walking | 70 | 60 | 44 | 36 |
| hiking | 18 | 11 | 14 | 11 |

## 11. Error-pattern replication

| Category | SP-032E | SP-032F | Replication |
| --- | --- | --- | --- |
| NON_NEED_MISROUTED_AS_NEED | 89 | 133 | REPEATED_ERROR_PATTERN |
| EXISTING_TAXONOMY_GAP | 23 | 29 | REPEATED_ERROR_PATTERN |
| NEW_VALID_BUYER_NEED | 9 | 23 | REPEATED_ERROR_PATTERN |
| AMBIGUOUS | 31 | 15 | REPEATED_ERROR_PATTERN |
| OTHER | 0 | 0 | NOT_OBSERVED |

Major error patterns reproduced: **True**.

## 12. Overfit replication decision

Final decision: **SYSTEMATIC_GENERALIZATION_PROBLEM**.

Need Precision moved from **81.63%** to **84.00%**, a **2.37 percentage-point** change. The decision combines that result with independent reproduction of the two principal SP-032E error classes; it does not treat a low score alone as proof.

## 13. Limitations

- Only page 1 / top 20 monthly reverse keywords were captured per ASIN.
- ASIN coverage is cohort recurrence, not Demand Share.
- Provider traffic semantics remain provider-defined and uncalibrated.
- Parent ASIN remains UNKNOWN when omitted by the cohort response.
- Manual term review is not Amazon behavioral ground truth.
- The cohort and keyword corpus both change, so sample and temporal effects are not separately identified.

## 14. Unique next task

**TASK-SP-032G Need Precision Error Analysis**

No alternate next task is recommended in this validation decision.

## Appendix A — 100-ASIN cohort

| # | ASIN | Parent ASIN | Page | Rank | Provider total | Selection reason |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | B0D2XLB81Y | UNKNOWN | 1 | 14 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 2 | B0GXNTLVYM | UNKNOWN | 1 | 29 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 3 | B0CT89DDBX | UNKNOWN | 1 | 35 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 4 | B09CHBDPKR | UNKNOWN | 1 | 38 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 5 | B0DY7H2HK8 | UNKNOWN | 1 | 46 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 6 | B0H3HGWC84 | UNKNOWN | 1 | 55 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 7 | B0B9HV5GMD | UNKNOWN | 1 | 59 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 8 | B0CGLDG8L3 | UNKNOWN | 1 | 60 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 9 | B07CG51J7C | UNKNOWN | 1 | 67 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 10 | B0C7G5CSMV | UNKNOWN | 1 | 70 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 11 | B0D9GTCNBL | UNKNOWN | 1 | 71 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 12 | B09CH9T2WN | UNKNOWN | 1 | 72 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 13 | B0B4G2QGLG | UNKNOWN | 1 | 74 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 14 | B0C7FYDRZL | UNKNOWN | 1 | 75 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 15 | B0B51W43P5 | UNKNOWN | 1 | 78 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 16 | B0C7G1RP7C | UNKNOWN | 1 | 79 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 17 | B07C79C5BT | UNKNOWN | 1 | 82 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 18 | B0CX2Q2H8B | UNKNOWN | 1 | 84 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 19 | B0FJF5P8HV | UNKNOWN | 1 | 90 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 20 | B0FDWJG93L | UNKNOWN | 1 | 93 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 21 | B0GFH1T733 | UNKNOWN | 1 | 100 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 22 | B0DNGJTSY5 | UNKNOWN | 1 | 101 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 23 | B0DTBRRGZ7 | UNKNOWN | 1 | 102 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 24 | B0GQGVYJJ2 | UNKNOWN | 1 | 103 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 25 | B00S02SRGO | UNKNOWN | 1 | 104 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 26 | B0H5W8JZSG | UNKNOWN | 1 | 107 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 27 | B0FNBKTP6T | UNKNOWN | 1 | 110 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 28 | B0F9YYNH8N | UNKNOWN | 1 | 111 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 29 | B08YK1YXN6 | UNKNOWN | 1 | 112 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 30 | B0DG6MXT1R | UNKNOWN | 1 | 113 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 31 | B0GXNPMGJ7 | UNKNOWN | 1 | 114 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 32 | B0F21Q165L | UNKNOWN | 1 | 115 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 33 | B0GYDYYQLB | UNKNOWN | 1 | 117 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 34 | B07SZ234ZT | UNKNOWN | 1 | 118 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 35 | B0H33TJVMF | UNKNOWN | 1 | 119 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 36 | B06XJ88KYW | UNKNOWN | 1 | 120 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 37 | B0GX12P4MK | UNKNOWN | 1 | 121 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 38 | B097Y4MTBD | UNKNOWN | 1 | 124 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 39 | B0BQF3WMBR | UNKNOWN | 1 | 127 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 40 | B0CFVJNC6Q | UNKNOWN | 1 | 128 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 41 | B0H7HQ618K | UNKNOWN | 1 | 129 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 42 | B0194L7AFS | UNKNOWN | 1 | 130 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 43 | B0002EZIRY | UNKNOWN | 1 | 131 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 44 | B0H6VLRV6G | UNKNOWN | 1 | 134 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 45 | B0DXP9ZHX1 | UNKNOWN | 1 | 135 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 46 | B0C1VCKG32 | UNKNOWN | 1 | 136 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 47 | B0DMPBX3N2 | UNKNOWN | 1 | 137 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 48 | B0DG6PVDJL | UNKNOWN | 1 | 140 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 49 | B0H1QRG8RP | UNKNOWN | 1 | 141 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 50 | B09CH926J4 | UNKNOWN | 1 | 143 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 51 | B0CYZKP7BS | UNKNOWN | 1 | 144 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 52 | B0DLJ9H1K1 | UNKNOWN | 1 | 145 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 53 | B07S3FRP73 | UNKNOWN | 1 | 147 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 54 | B0FKNKFKXK | UNKNOWN | 1 | 148 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 55 | B09DVT26FW | UNKNOWN | 1 | 149 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 56 | B0DKY6NP3G | UNKNOWN | 1 | 150 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 57 | B0H1GRXBV2 | UNKNOWN | 1 | 151 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 58 | B078JNSZCZ | UNKNOWN | 1 | 152 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 59 | B0H48W1BLR | UNKNOWN | 1 | 153 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 60 | B0GY9JZZTV | UNKNOWN | 1 | 155 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 61 | B0C33G239D | UNKNOWN | 1 | 156 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 62 | B0H33DFJ77 | UNKNOWN | 1 | 158 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 63 | B0FJ24H6RK | UNKNOWN | 1 | 159 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 64 | B0GXMH5Y8J | UNKNOWN | 1 | 160 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 65 | B09T3B8PMH | UNKNOWN | 1 | 161 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 66 | B0DX4VBH35 | UNKNOWN | 1 | 162 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 67 | B0GYCTH97K | UNKNOWN | 1 | 163 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 68 | B0F9Z2996S | UNKNOWN | 1 | 165 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 69 | B0H33799QX | UNKNOWN | 1 | 166 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 70 | B0D1C14D9X | UNKNOWN | 1 | 167 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 71 | B0FV8NPS3H | UNKNOWN | 1 | 168 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 72 | B0GCZK57GJ | UNKNOWN | 1 | 169 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 73 | B0H4BL2L5W | UNKNOWN | 1 | 170 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 74 | B0BKG5F7HG | UNKNOWN | 1 | 171 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 75 | B0G13JXTQQ | UNKNOWN | 1 | 173 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 76 | B09CYS4F7L | UNKNOWN | 1 | 174 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 77 | B09YTSM35S | UNKNOWN | 1 | 175 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 78 | B0C33DNQ14 | UNKNOWN | 1 | 176 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 79 | B0DNGF8446 | UNKNOWN | 1 | 177 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 80 | B0G1Z1Q6BB | UNKNOWN | 1 | 178 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 81 | B0G4DFDPJR | UNKNOWN | 1 | 179 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 82 | B0B4G1HWKY | UNKNOWN | 1 | 180 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 83 | B0G837WSSP | UNKNOWN | 1 | 181 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 84 | B0BZR3C5X5 | UNKNOWN | 1 | 182 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 85 | B0H1L7MTXL | UNKNOWN | 1 | 183 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 86 | B0D5QHZWWP | UNKNOWN | 1 | 184 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 87 | B0GZD64QL3 | UNKNOWN | 1 | 185 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 88 | B07Y9PD2PP | UNKNOWN | 1 | 186 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 89 | B0GY39JM4G | UNKNOWN | 1 | 187 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 90 | B0H18FDX5Y | UNKNOWN | 1 | 190 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 91 | B0002Z15ZW | UNKNOWN | 1 | 191 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 92 | B0H33BGNY9 | UNKNOWN | 1 | 193 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 93 | B0H7BPTQRQ | UNKNOWN | 1 | 194 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 94 | B0GXKBZW6X | UNKNOWN | 1 | 195 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 95 | B07VT1468W | UNKNOWN | 1 | 196 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 96 | B089SPMGB7 | UNKNOWN | 1 | 197 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 97 | B0G2VWZ2HR | UNKNOWN | 1 | 198 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 98 | B0FJMDSQZQ | UNKNOWN | 1 | 199 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 99 | B001N4E7GU | UNKNOWN | 1 | 200 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |
| 100 | B09DVRR1XT | UNKNOWN | 1 | 201 | 883 | First unique valid provider row after frozen SP-032B and SP-032E exclusions |

## Appendix B — Fingerprinted source files

| File | SHA-256 |
| --- | --- |
| buyer_need_analysis/builder_v0_2.py | ad368c94a8b42be8047b266ddddd987fb7508554fe425ed186370d6fdb04f394 |
| buyer_need_analysis/intent_v0_2.py | a849009994f6c4fc78aaafa26c0d58e4cd7122093211311789e8bec9ff4f8701 |
| buyer_need_analysis/taxonomy_v0_2.py | ac8d4c4a9a7db0fcf1d6f0caf3a2e3e0c136586189ee9ce6ddcb5669853ba09e |
| semantic_clustering/builder_v0_1.py | d3e9aee431c35dd1b1644cd3994799f5398b9cc348def010eebccd3ae294b423 |
| semantic_clustering/rules.py | ca524b770c1cf8c049b70c9ceadb0653bbd782c53a18840f3ae07c238c651804 |

The complete relation lineage, precision items, keyword expressions, provider request/response references, exclusion log, and operation-level credit audit are preserved in the companion analysis and raw checkpoint JSON files.
