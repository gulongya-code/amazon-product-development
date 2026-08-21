# TASK-SP-032E — 100-ASIN Organic Discovery Holdout Validation v0.1

**TASK-SP-032E COMPLETE**

- Baseline: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`
- Analysis ID: `organic-buyer-need-holdout-analysis:145498186b0d73dcdd944652c35f0f3bf8233b22cf19b00116ee4653c9452482`
- Final judgement: **TAXONOMY_V0_2_OVERFIT**
- Category: Amazon US > Pet Supplies > Dog Travel Water Bottles
- Marketplace / period: `US` / `last7days`
- Important: ASIN coverage below is cohort recurrence, **not Demand Share**.

## 1. Cohort and independence

XiYou keyword_asin_analysis page 1, last7days, traffic descending; preserve provider response order, deduplicate ASIN, exclude frozen SP-032B 20-ASIN set, take first 100 without handpicking.

- Provider total: **664**
- Holdout ASIN count: **100**
- Frozen pilot exclusion count: **20**
- Pilot overlap: **0**
- Parent ASIN is retained when the provider row supplies it; otherwise it remains UNKNOWN.

| # | Child ASIN | Parent ASIN | Provider page | Response rank |
|---|---|---|---|---|
| 1 | B09265WXY5 | UNKNOWN | 1 | 21 |
| 2 | B0GGR3F5KZ | UNKNOWN | 1 | 22 |
| 3 | B0H235BRVX | UNKNOWN | 1 | 23 |
| 4 | B09DVT8XJT | UNKNOWN | 1 | 24 |
| 5 | B084GSXR6G | UNKNOWN | 1 | 25 |
| 6 | B0GTQRR9PW | UNKNOWN | 1 | 26 |
| 7 | B0D1CGMY1Q | UNKNOWN | 1 | 27 |
| 8 | B0B51TY6MR | UNKNOWN | 1 | 28 |
| 9 | B09B4YTZKM | UNKNOWN | 1 | 29 |
| 10 | B08JYKNX86 | UNKNOWN | 1 | 30 |
| 11 | B0B3DKHGRX | UNKNOWN | 1 | 31 |
| 12 | B0G59FP8ZH | UNKNOWN | 1 | 32 |
| 13 | B0GD7CSYTT | UNKNOWN | 1 | 33 |
| 14 | B09FFVC2WR | UNKNOWN | 1 | 34 |
| 15 | B0GQNHCM8S | UNKNOWN | 1 | 35 |
| 16 | B0FXWZ82RH | UNKNOWN | 1 | 36 |
| 17 | B09CTLJ43V | UNKNOWN | 1 | 37 |
| 18 | B0FPRB6NWL | UNKNOWN | 1 | 38 |
| 19 | B09V14YQGT | UNKNOWN | 1 | 39 |
| 20 | B0C1BYCNNF | UNKNOWN | 1 | 40 |
| 21 | B0FNRBRGV4 | UNKNOWN | 1 | 41 |
| 22 | B07FRP7MRT | UNKNOWN | 1 | 42 |
| 23 | B00S02SRI2 | UNKNOWN | 1 | 43 |
| 24 | B0C33FR1VB | UNKNOWN | 1 | 44 |
| 25 | B019DJZ0KI | UNKNOWN | 1 | 45 |
| 26 | B0H33S2S9K | UNKNOWN | 1 | 46 |
| 27 | B0GYTWBQH9 | UNKNOWN | 1 | 47 |
| 28 | B07WDMJRP4 | UNKNOWN | 1 | 48 |
| 29 | B0892CX7BL | UNKNOWN | 1 | 49 |
| 30 | B0H7HYNRBP | UNKNOWN | 1 | 50 |
| 31 | B0FQNPQ4WT | UNKNOWN | 1 | 51 |
| 32 | B0DBJDZWM3 | UNKNOWN | 1 | 52 |
| 33 | B0DX5B5L6F | UNKNOWN | 1 | 53 |
| 34 | B0B9LPPQWY | UNKNOWN | 1 | 54 |
| 35 | B0H2HCHX3S | UNKNOWN | 1 | 55 |
| 36 | B0002DKBDG | UNKNOWN | 1 | 56 |
| 37 | B0DZVMQPYS | UNKNOWN | 1 | 57 |
| 38 | B0GD7PH8TD | UNKNOWN | 1 | 58 |
| 39 | B08MBBMQQZ | UNKNOWN | 1 | 59 |
| 40 | B0DNRM1CPV | UNKNOWN | 1 | 60 |
| 41 | B0B2NM5Z9W | UNKNOWN | 1 | 61 |
| 42 | B0FVMWMGQF | UNKNOWN | 1 | 62 |
| 43 | B0H36N1YC4 | UNKNOWN | 1 | 63 |
| 44 | B0H6X9MHLL | UNKNOWN | 1 | 64 |
| 45 | B084GSN6BC | UNKNOWN | 1 | 65 |
| 46 | B0GLN6DQCM | UNKNOWN | 1 | 66 |
| 47 | B0BZQZZP7Q | UNKNOWN | 1 | 67 |
| 48 | B0H8WQT1DV | UNKNOWN | 1 | 68 |
| 49 | B01N3L9PTZ | UNKNOWN | 1 | 69 |
| 50 | B08L7N8M4Z | UNKNOWN | 1 | 70 |
| 51 | B0BQN8TNHH | UNKNOWN | 1 | 71 |
| 52 | B07SQTSBDM | UNKNOWN | 1 | 72 |
| 53 | B004HSUL46 | UNKNOWN | 1 | 73 |
| 54 | B0C3LWLCL9 | UNKNOWN | 1 | 74 |
| 55 | B084GT23R9 | UNKNOWN | 1 | 75 |
| 56 | B0002DIYTO | UNKNOWN | 1 | 76 |
| 57 | B0GD7Q14ZP | UNKNOWN | 1 | 77 |
| 58 | B0H26KRMLS | UNKNOWN | 1 | 78 |
| 59 | B08P5K8R5X | UNKNOWN | 1 | 79 |
| 60 | B0GD7XPT45 | UNKNOWN | 1 | 80 |
| 61 | B09F5ZVV3D | UNKNOWN | 1 | 81 |
| 62 | B08L7NMK4P | UNKNOWN | 1 | 82 |
| 63 | B07M66ZPXG | UNKNOWN | 1 | 83 |
| 64 | B08P5JCF4C | UNKNOWN | 1 | 84 |
| 65 | B084GT8JKX | UNKNOWN | 1 | 85 |
| 66 | B0B9LPCC3W | UNKNOWN | 1 | 86 |
| 67 | B0B2NKFN2L | UNKNOWN | 1 | 87 |
| 68 | B09H2LH8NJ | UNKNOWN | 1 | 88 |
| 69 | B0D1V3FDHX | UNKNOWN | 1 | 89 |
| 70 | B0H1QS6945 | UNKNOWN | 1 | 90 |
| 71 | B0BZR4SRZ3 | UNKNOWN | 1 | 91 |
| 72 | B0H5K2MB4L | UNKNOWN | 1 | 92 |
| 73 | B0C7T1FS57 | UNKNOWN | 1 | 93 |
| 74 | B0GTRY9MPM | UNKNOWN | 1 | 94 |
| 75 | B0B4ZC6HY5 | UNKNOWN | 1 | 95 |
| 76 | B0DSB8M9LW | UNKNOWN | 1 | 96 |
| 77 | B0H2DKCH7R | UNKNOWN | 1 | 97 |
| 78 | B0C6KZVSCD | UNKNOWN | 1 | 98 |
| 79 | B0GFDP5GML | UNKNOWN | 1 | 99 |
| 80 | B0FF8ZGVJX | UNKNOWN | 1 | 100 |
| 81 | B0B1J94TB6 | UNKNOWN | 1 | 101 |
| 82 | B0DZNGBXTS | UNKNOWN | 1 | 102 |
| 83 | B0BVQLYCWR | UNKNOWN | 1 | 103 |
| 84 | B0D9R8X7ML | UNKNOWN | 1 | 104 |
| 85 | B0H2CS9NRK | UNKNOWN | 1 | 105 |
| 86 | B0H1MGX4F4 | UNKNOWN | 1 | 106 |
| 87 | B0DTBZCYN6 | UNKNOWN | 1 | 107 |
| 88 | B0FZ8H3QGB | UNKNOWN | 1 | 108 |
| 89 | B0FXX1DPWR | UNKNOWN | 1 | 109 |
| 90 | B0DFBD8GJW | UNKNOWN | 1 | 110 |
| 91 | B0H28DR8R8 | UNKNOWN | 1 | 111 |
| 92 | B0D86TNJL9 | UNKNOWN | 1 | 112 |
| 93 | B0BNX4PVDN | UNKNOWN | 1 | 113 |
| 94 | B0GRQBTDGW | UNKNOWN | 1 | 114 |
| 95 | B0H2RX9CJ6 | UNKNOWN | 1 | 115 |
| 96 | B0C7G5Q647 | UNKNOWN | 1 | 116 |
| 97 | B0H3JPDH7D | UNKNOWN | 1 | 117 |
| 98 | B0F6TVPX1Y | UNKNOWN | 1 | 118 |
| 99 | B0GVXQ95MX | UNKNOWN | 1 | 119 |
| 100 | B07Q3451WW | UNKNOWN | 1 | 120 |

## 2. API calls and credits

- Pre-call estimate: **102 credits**
- Gate: **150 credits**
- Executed calls: **102**
- Provider-reported known credits: **113**
- Calls without credit metadata: **0**

| # | Operation | ASIN | Page | Page size / terms | Rows | Total | Credits | X-Cost-Credits |
|---|---|---|---|---|---|---|---|---|
| 1 | keyword_asin_analysis | UNKNOWN | 1 | 200 | 200 | 664 | 10 | 10 |
| 2 | asin_keywords | B09265WXY5 | 1 | 20 | 20 | 97 | 1 | 1 |
| 3 | asin_keywords | B0GGR3F5KZ | 1 | 20 | 20 | 537 | 1 | 1 |
| 4 | asin_keywords | B0H235BRVX | 1 | 20 | 20 | 176 | 1 | 1 |
| 5 | asin_keywords | B09DVT8XJT | 1 | 20 | 20 | 71 | 1 | 1 |
| 6 | asin_keywords | B084GSXR6G | 1 | 20 | 20 | 601 | 1 | 1 |
| 7 | asin_keywords | B0GTQRR9PW | 1 | 20 | 20 | 119 | 1 | 1 |
| 8 | asin_keywords | B0D1CGMY1Q | 1 | 20 | 20 | 424 | 1 | 1 |
| 9 | asin_keywords | B0B51TY6MR | 1 | 20 | 20 | 235 | 1 | 1 |
| 10 | asin_keywords | B09B4YTZKM | 1 | 20 | 20 | 285 | 1 | 1 |
| 11 | asin_keywords | B08JYKNX86 | 1 | 20 | 20 | 39 | 1 | 1 |
| 12 | asin_keywords | B0B3DKHGRX | 1 | 20 | 20 | 181 | 1 | 1 |
| 13 | asin_keywords | B0G59FP8ZH | 1 | 20 | 20 | 150 | 1 | 1 |
| 14 | asin_keywords | B0GD7CSYTT | 1 | 20 | 20 | 155 | 1 | 1 |
| 15 | asin_keywords | B09FFVC2WR | 1 | 20 | 20 | 108 | 1 | 1 |
| 16 | asin_keywords | B0GQNHCM8S | 1 | 20 | 20 | 106 | 1 | 1 |
| 17 | asin_keywords | B0FXWZ82RH | 1 | 20 | 20 | 471 | 1 | 1 |
| 18 | asin_keywords | B09CTLJ43V | 1 | 20 | 20 | 104 | 1 | 1 |
| 19 | asin_keywords | B0FPRB6NWL | 1 | 20 | 20 | 210 | 1 | 1 |
| 20 | asin_keywords | B09V14YQGT | 1 | 20 | 20 | 21 | 1 | 1 |
| 21 | asin_keywords | B0C1BYCNNF | 1 | 20 | 20 | 46 | 1 | 1 |
| 22 | asin_keywords | B0FNRBRGV4 | 1 | 20 | 20 | 54 | 1 | 1 |
| 23 | asin_keywords | B07FRP7MRT | 1 | 20 | 20 | 221 | 1 | 1 |
| 24 | asin_keywords | B00S02SRI2 | 1 | 20 | 20 | 191 | 1 | 1 |
| 25 | asin_keywords | B0C33FR1VB | 1 | 20 | 20 | 192 | 1 | 1 |
| 26 | asin_keywords | B019DJZ0KI | 1 | 20 | 16 | 16 | 1 | 1 |
| 27 | asin_keywords | B0H33S2S9K | 1 | 20 | 20 | 129 | 1 | 1 |
| 28 | asin_keywords | B0GYTWBQH9 | 1 | 20 | 20 | 310 | 1 | 1 |
| 29 | asin_keywords | B07WDMJRP4 | 1 | 20 | 20 | 44 | 1 | 1 |
| 30 | asin_keywords | B0892CX7BL | 1 | 20 | 20 | 243 | 1 | 1 |
| 31 | asin_keywords | B0H7HYNRBP | 1 | 20 | 20 | 310 | 1 | 1 |
| 32 | asin_keywords | B0FQNPQ4WT | 1 | 20 | 20 | 128 | 1 | 1 |
| 33 | asin_keywords | B0DBJDZWM3 | 1 | 20 | 20 | 120 | 1 | 1 |
| 34 | asin_keywords | B0DX5B5L6F | 1 | 20 | 20 | 257 | 1 | 1 |
| 35 | asin_keywords | B0B9LPPQWY | 1 | 20 | 20 | 121 | 1 | 1 |
| 36 | asin_keywords | B0H2HCHX3S | 1 | 20 | 20 | 123 | 1 | 1 |
| 37 | asin_keywords | B0002DKBDG | 1 | 20 | 20 | 29 | 1 | 1 |
| 38 | asin_keywords | B0DZVMQPYS | 1 | 20 | 20 | 96 | 1 | 1 |
| 39 | asin_keywords | B0GD7PH8TD | 1 | 20 | 20 | 387 | 1 | 1 |
| 40 | asin_keywords | B08MBBMQQZ | 1 | 20 | 20 | 44 | 1 | 1 |
| 41 | asin_keywords | B0DNRM1CPV | 1 | 20 | 20 | 160 | 1 | 1 |
| 42 | asin_keywords | B0B2NM5Z9W | 1 | 20 | 20 | 136 | 1 | 1 |
| 43 | asin_keywords | B0FVMWMGQF | 1 | 20 | 20 | 170 | 1 | 1 |
| 44 | asin_keywords | B0H36N1YC4 | 1 | 20 | 20 | 134 | 1 | 1 |
| 45 | asin_keywords | B0H6X9MHLL | 1 | 20 | 20 | 77 | 1 | 1 |
| 46 | asin_keywords | B084GSN6BC | 1 | 20 | 20 | 309 | 1 | 1 |
| 47 | asin_keywords | B0GLN6DQCM | 1 | 20 | 20 | 83 | 1 | 1 |
| 48 | asin_keywords | B0BZQZZP7Q | 1 | 20 | 20 | 408 | 1 | 1 |
| 49 | asin_keywords | B0H8WQT1DV | 1 | 20 | 20 | 62 | 1 | 1 |
| 50 | asin_keywords | B01N3L9PTZ | 1 | 20 | 20 | 39 | 1 | 1 |
| 51 | asin_keywords | B08L7N8M4Z | 1 | 20 | 20 | 338 | 1 | 1 |
| 52 | asin_keywords | B0BQN8TNHH | 1 | 20 | 20 | 122 | 1 | 1 |
| 53 | asin_keywords | B07SQTSBDM | 1 | 20 | 20 | 135 | 1 | 1 |
| 54 | asin_keywords | B004HSUL46 | 1 | 20 | 20 | 148 | 1 | 1 |
| 55 | asin_keywords | B0C3LWLCL9 | 1 | 20 | 20 | 101 | 1 | 1 |
| 56 | asin_keywords | B084GT23R9 | 1 | 20 | 20 | 321 | 1 | 1 |
| 57 | asin_keywords | B0002DIYTO | 1 | 20 | 20 | 77 | 1 | 1 |
| 58 | asin_keywords | B0GD7Q14ZP | 1 | 20 | 20 | 265 | 1 | 1 |
| 59 | asin_keywords | B0H26KRMLS | 1 | 20 | 20 | 227 | 1 | 1 |
| 60 | asin_keywords | B08P5K8R5X | 1 | 20 | 20 | 328 | 1 | 1 |
| 61 | asin_keywords | B0GD7XPT45 | 1 | 20 | 20 | 193 | 1 | 1 |
| 62 | asin_keywords | B09F5ZVV3D | 1 | 20 | 20 | 222 | 1 | 1 |
| 63 | asin_keywords | B08L7NMK4P | 1 | 20 | 20 | 309 | 1 | 1 |
| 64 | asin_keywords | B07M66ZPXG | 1 | 20 | 20 | 111 | 1 | 1 |
| 65 | asin_keywords | B08P5JCF4C | 1 | 20 | 20 | 312 | 1 | 1 |
| 66 | asin_keywords | B084GT8JKX | 1 | 20 | 20 | 312 | 1 | 1 |
| 67 | asin_keywords | B0B9LPCC3W | 1 | 20 | 20 | 71 | 1 | 1 |
| 68 | asin_keywords | B0B2NKFN2L | 1 | 20 | 5 | 5 | 1 | 1 |
| 69 | asin_keywords | B09H2LH8NJ | 1 | 20 | 20 | 49 | 1 | 1 |
| 70 | asin_keywords | B0D1V3FDHX | 1 | 20 | 20 | 93 | 1 | 1 |
| 71 | asin_keywords | B0H1QS6945 | 1 | 20 | 20 | 101 | 1 | 1 |
| 72 | asin_keywords | B0BZR4SRZ3 | 1 | 20 | 20 | 355 | 1 | 1 |
| 73 | asin_keywords | B0H5K2MB4L | 1 | 20 | 17 | 17 | 1 | 1 |
| 74 | asin_keywords | B0C7T1FS57 | 1 | 20 | 20 | 327 | 1 | 1 |
| 75 | asin_keywords | B0GTRY9MPM | 1 | 20 | 20 | 57 | 1 | 1 |
| 76 | asin_keywords | B0B4ZC6HY5 | 1 | 20 | 20 | 52 | 1 | 1 |
| 77 | asin_keywords | B0DSB8M9LW | 1 | 20 | 20 | 74 | 1 | 1 |
| 78 | asin_keywords | B0H2DKCH7R | 1 | 20 | 20 | 73 | 1 | 1 |
| 79 | asin_keywords | B0C6KZVSCD | 1 | 20 | 19 | 19 | 1 | 1 |
| 80 | asin_keywords | B0GFDP5GML | 1 | 20 | 20 | 31 | 1 | 1 |
| 81 | asin_keywords | B0FF8ZGVJX | 1 | 20 | 20 | 94 | 1 | 1 |
| 82 | asin_keywords | B0B1J94TB6 | 1 | 20 | 20 | 276 | 1 | 1 |
| 83 | asin_keywords | B0DZNGBXTS | 1 | 20 | 20 | 122 | 1 | 1 |
| 84 | asin_keywords | B0BVQLYCWR | 1 | 20 | 20 | 79 | 1 | 1 |
| 85 | asin_keywords | B0D9R8X7ML | 1 | 20 | 20 | 100 | 1 | 1 |
| 86 | asin_keywords | B0H2CS9NRK | 1 | 20 | 20 | 101 | 1 | 1 |
| 87 | asin_keywords | B0H1MGX4F4 | 1 | 20 | 20 | 180 | 1 | 1 |
| 88 | asin_keywords | B0DTBZCYN6 | 1 | 20 | 20 | 171 | 1 | 1 |
| 89 | asin_keywords | B0FZ8H3QGB | 1 | 20 | 17 | 17 | 1 | 1 |
| 90 | asin_keywords | B0FXX1DPWR | 1 | 20 | 20 | 419 | 1 | 1 |
| 91 | asin_keywords | B0DFBD8GJW | 1 | 20 | 20 | 100 | 1 | 1 |
| 92 | asin_keywords | B0H28DR8R8 | 1 | 20 | 20 | 72 | 1 | 1 |
| 93 | asin_keywords | B0D86TNJL9 | 1 | 20 | 20 | 101 | 1 | 1 |
| 94 | asin_keywords | B0BNX4PVDN | 1 | 20 | 20 | 284 | 1 | 1 |
| 95 | asin_keywords | B0GRQBTDGW | 1 | 20 | 20 | 87 | 1 | 1 |
| 96 | asin_keywords | B0H2RX9CJ6 | 1 | 20 | 20 | 105 | 1 | 1 |
| 97 | asin_keywords | B0C7G5Q647 | 1 | 20 | 20 | 122 | 1 | 1 |
| 98 | asin_keywords | B0H3JPDH7D | 1 | 20 | 20 | 55 | 1 | 1 |
| 99 | asin_keywords | B0F6TVPX1Y | 1 | 20 | 20 | 206 | 1 | 1 |
| 100 | asin_keywords | B0GVXQ95MX | 1 | 20 | 20 | 22 | 1 | 1 |
| 101 | asin_keywords | B07Q3451WW | 1 | 20 | 20 | 31 | 1 | 1 |
| 102 | keyword_info | UNKNOWN | UNKNOWN | 30 | 30 | 30 | 3 | 3 |

## 3. Raw keyword corpus

- Raw ASIN-keyword relations: **1974**
- Unique keywords: **285**
- Cross-ASIN duplicates: **1689**
- Source ASINs: **100**
- Successful source coverage: **100.00%**
- Rank availability: `{"ORGANIC_RANK_AVAILABLE": 1616, "ORGANIC_RANK_UNKNOWN": 358}`
- Traffic availability: `{"AVAILABLE": 1974}`

### Top 100 organic discovered terms

| # | Keyword | Relations | ASIN count | ASIN coverage | Provider traffic | Best organic rank |
|---|---|---|---|---|---|---|
| 1 | dog water bottle | 100 | 100 | 100.00% | 212230 | 7 |
| 2 | dog water bottle portable | 80 | 80 | 80.00% | 105197 | 7 |
| 3 | portable dog water bottle | 75 | 75 | 75.00% | 36469 | 5 |
| 4 | water bottle for dogs | 72 | 72 | 72.00% | 19029 | 3 |
| 5 | travel dog water bottle | 61 | 61 | 61.00% | 15902 | 3 |
| 6 | dog travel water bottle | 60 | 60 | 60.00% | 24654 | 3 |
| 7 | portable dog water bowl | 56 | 56 | 56.00% | 40421 | 3 |
| 8 | dog portable water bottle | 54 | 54 | 54.00% | 9117 | 3 |
| 9 | dog water bottle with built-in bowl | 48 | 48 | 48.00% | 9705 | 4 |
| 10 | dog water bottles | 41 | 41 | 41.00% | 4487 | 3 |
| 11 | portable water bottle for dogs | 39 | 39 | 39.00% | 5215 | 5 |
| 12 | portable water bowl for dog | 36 | 36 | 36.00% | 13578 | 7 |
| 13 | travel water bowl for dogs | 36 | 36 | 36.00% | 9263 | 7 |
| 14 | water bottle for dogs on walks | 32 | 32 | 32.00% | 4280 | 12 |
| 15 | pet water bottle | 31 | 31 | 31.00% | 6374 | 7 |
| 16 | water bottle dog | 31 | 31 | 31.00% | 2494 | 3 |
| 17 | botella de agua para perros | 26 | 26 | 26.00% | 3603 | 1 |
| 18 | dog bottle | 25 | 25 | 25.00% | 1870 | 6 |
| 19 | water bottle for dog | 24 | 24 | 24.00% | 1017 | 7 |
| 20 | rover and oak dog water bottle | 21 | 21 | 21.00% | 3871 | 4 |
| 21 | trailhound dog water bottle | 21 | 21 | 21.00% | 3648 | 2 |
| 22 | portable dog bowl | 21 | 21 | 21.00% | 2736 | 30 |
| 23 | insulated dog water bottle | 21 | 21 | 21.00% | 2269 | 7 |
| 24 | travel dog bowls | 20 | 20 | 20.00% | 3409 | 31 |
| 25 | portable dog water | 20 | 20 | 20.00% | 2348 | 7 |
| 26 | dog travel water bowl | 19 | 19 | 19.00% | 3423 | 8 |
| 27 | portable dog water bottle with bowl | 18 | 18 | 18.00% | 2269 | 4 |
| 28 | dog bottle water dispenser | 17 | 17 | 17.00% | 1480 | 10 |
| 29 | travel water bottle for dogs | 16 | 16 | 16.00% | 1522 | 7 |
| 30 | dog water bowl travel | 15 | 15 | 15.00% | 1829 | 22 |
| 31 | dog travel water | 15 | 15 | 15.00% | 1399 | 10 |
| 32 | stainless steel dog water bottle | 15 | 15 | 15.00% | 1284 | 8 |
| 33 | dog travel bowls | 15 | 15 | 15.00% | 987 | 47 |
| 34 | trailhound insulated dog water bottle | 14 | 14 | 14.00% | 1968 | 2 |
| 35 | dog walking water bottle | 14 | 14 | 14.00% | 670 | 3 |
| 36 | dog crate water bottle | 13 | 13 | 13.00% | 2529 | 1 |
| 37 | travel dog water bowl | 13 | 13 | 13.00% | 2174 | 7 |
| 38 | dog waterbottle | 13 | 13 | 13.00% | 866 | 9 |
| 39 | dog portable water bowl | 12 | 12 | 12.00% | 1587 | 9 |
| 40 | springer dog water bottle | 12 | 12 | 12.00% | 800 | 13 |
| 41 | dog water bottle for walks | 12 | 12 | 12.00% | 604 | 15 |
| 42 | animal water bottle | 12 | 12 | 12.00% | 424 | 14 |
| 43 | small dog water bottle | 11 | 11 | 11.00% | 749 | 1 |
| 44 | portable pet water bottle | 11 | 11 | 11.00% | 648 | 4 |
| 45 | pupflask dog water bottle | 11 | 11 | 11.00% | 473 | 5 |
| 46 | travel dog bowl | 11 | 11 | 11.00% | 448 | 32 |
| 47 | dog drinking bottle portable | 11 | 11 | 11.00% | 321 | 12 |
| 48 | water bottles for dogs | 11 | 11 | 11.00% | 302 | 3 |
| 49 | dog food storage container | 10 | 10 | 10.00% | 0 | UNKNOWN |
| 50 | dog travel accessories | 9 | 9 | 9.00% | 5194 | 3 |
| 51 | pupflask | 9 | 9 | 9.00% | 989 | 4 |
| 52 | water bottle for dog crate | 9 | 9 | 9.00% | 742 | 1 |
| 53 | malsipree dog water bottle | 9 | 9 | 9.00% | 459 | 1 |
| 54 | asobu | 9 | 9 | 9.00% | 386 | 42 |
| 55 | doggy water bottle | 9 | 9 | 9.00% | 112 | 41 |
| 56 | dog food container | 9 | 9 | 9.00% | 0 | UNKNOWN |
| 57 | cat water bottle | 8 | 8 | 8.00% | 1981 | 5 |
| 58 | dog kennel water dispenser | 8 | 8 | 8.00% | 1356 | 2 |
| 59 | yeti dog bowl | 8 | 8 | 8.00% | 1113 | 65 |
| 60 | crate water dispenser for dogs | 8 | 8 | 8.00% | 751 | 1 |
| 61 | dog hiking gear | 8 | 8 | 8.00% | 673 | 3 |
| 62 | dog water bottle for crate | 8 | 8 | 8.00% | 566 | 1 |
| 63 | travel dog water | 8 | 8 | 8.00% | 373 | 25 |
| 64 | stanley dog bowl | 8 | 8 | 8.00% | 361 | 26 |
| 65 | springland dog water bottle | 8 | 8 | 8.00% | 206 | 16 |
| 66 | travel water bottle | 8 | 8 | 8.00% | 0 | UNKNOWN |
| 67 | dog water dispenser | 7 | 7 | 7.00% | 3304 | 72 |
| 68 | dog water | 7 | 7 | 7.00% | 1813 | 7 |
| 69 | collapsible dog bowls | 7 | 7 | 7.00% | 1227 | 88 |
| 70 | dog cage water dispenser | 7 | 7 | 7.00% | 950 | 2 |
| 71 | dog crate water dispenser | 7 | 7 | 7.00% | 634 | 2 |
| 72 | puppy water bottle | 7 | 7 | 7.00% | 574 | 2 |
| 73 | pup flask | 7 | 7 | 7.00% | 570 | 4 |
| 74 | dog water bottle dispenser | 7 | 7 | 7.00% | 397 | 3 |
| 75 | pet water bottles for dogs | 7 | 7 | 7.00% | 202 | 19 |
| 76 | dog water bottle with bowl | 7 | 7 | 7.00% | 186 | 25 |
| 77 | dog water bowl portable | 6 | 6 | 6.00% | 866 | 20 |
| 78 | dog water travel | 6 | 6 | 6.00% | 404 | 3 |
| 79 | dog stuff | 6 | 6 | 6.00% | 294 | 3 |
| 80 | dog hiking water bottle | 6 | 6 | 6.00% | 254 | 3 |
| 81 | dog kennel water bottle | 6 | 6 | 6.00% | 243 | 3 |
| 82 | lesotc dog water bottle | 6 | 6 | 6.00% | 211 | 2 |
| 83 | dog walk water bottle | 6 | 6 | 6.00% | 134 | 37 |
| 84 | dog travel | 5 | 5 | 5.00% | 1422 | 7 |
| 85 | dog camping | 5 | 5 | 5.00% | 1046 | 4 |
| 86 | dog accessories | 5 | 5 | 5.00% | 471 | 3 |
| 87 | drip water bottles | 5 | 5 | 5.00% | 420 | 28 |
| 88 | collapsible dog water bowl | 5 | 5 | 5.00% | 405 | 39 |
| 89 | pawb pet bottle | 5 | 5 | 5.00% | 317 | 2 |
| 90 | large dog water bottle | 5 | 5 | 5.00% | 129 | 8 |
| 91 | portable dog water bottle leak proof | 5 | 5 | 5.00% | 127 | 39 |
| 92 | rabbit water bottle | 4 | 4 | 4.00% | 2920 | 48 |
| 93 | hamster water bottle | 4 | 4 | 4.00% | 2737 | 31 |
| 94 | dog camping essentials | 4 | 4 | 4.00% | 1815 | 16 |
| 95 | dog beach essentials | 4 | 4 | 4.00% | 1663 | 9 |
| 96 | dog water bowl dispenser | 4 | 4 | 4.00% | 698 | 3 |
| 97 | pet travel water bottle | 4 | 4 | 4.00% | 272 | 4 |
| 98 | the trailhound™ insulated dog water bottle + bowl | 4 | 4 | 4.00% | 222 | 6 |
| 99 | portable dog water dispenser | 4 | 4 | 4.00% | 221 | 17 |
| 100 | crate water bottle | 4 | 4 | 4.00% | 151 | 10 |

## 4. Intent distribution

| Intent | Relations | Share of raw relations |
|---|---|---|
| ACCESSORY_RELATED | 27 | 1.37% |
| AMBIGUOUS | 1 | 0.05% |
| BRAND_MODEL | 132 | 6.69% |
| BROAD_QUERY | 25 | 1.27% |
| NEED_CANDIDATE | 1365 | 69.15% |
| OUT_OF_SCOPE | 5 | 0.25% |
| PRODUCT_OBJECT | 419 | 21.23% |

## 5. Buyer Need resolution

- Resolved Buyer Need relations: **1012**
- Explicit NON_NEED relations: **608**
- UNKNOWN Need Candidate relations: **353**
- AMBIGUOUS relations: **1**
- True Need Resolution Rate: **82.07%**
- Buyer Need unresolved rate: **17.93%**
- NON_NEED share: **30.80%**
- NON_NEED contributes to resolution coverage; it is not Buyer Need coverage.

## 6. Semantic clusters

| Cluster | Need records | Relations | Source ASINs | ASIN coverage | Expressions |
|---|---|---|---|---|---|
| Outdoor Portability | 816 | 816 | 90 | 90.00% | cat travel essentials; collapsible dog water bowl travel; dog drinking bottle portable; dog hiking; dog hiking gear; dog hiking water bottle; dog portable water bottle; dog portable water bowl; dog travel; dog travel accessories; dog travel bowl; dog travel bowls |
| Integrated Bowl Need | 48 | 48 | 48 | 48.00% | dog water bottle with built-in bowl |
| Walking Need | 70 | 70 | 44 | 44.00% | dog walk water bottle; dog walking accessories; dog walking water bottle; dog walking water bowl; dog water bottle for walks; portable dog water bowl for walking; water bottle for dogs on walks |
| Stainless Steel Need | 20 | 20 | 17 | 17.00% | stainless steel bottle; stainless steel dog water bottle; stainless steel snack container; stainless steel snack containers; stainless steel snack cup; stainless steel water bottle |
| Compact Size Collapsible Structure Need | 16 | 16 | 13 | 13.00% | collapsible dog bowls; collapsible dog bowls large; collapsible dog water bowl; collapsible dog water bowl travel; collapsible water bottles; collapsible water bowl for dogs |
| Compatibility Requirement Need | 22 | 22 | 13 | 13.00% | dog crate water bottle; water bottle for dog crate |
| Small Dogs Need | 12 | 12 | 12 | 12.00% | small dog bowls; small dog water bottle |
| Leak Prevention | 9 | 9 | 7 | 7.00% | leak proof dog water bottle; leak proof water bottles; portable dog water bottle leak proof |
| Large Dogs Need | 5 | 5 | 5 | 5.00% | large dog water bottle |
| 30 Oz Need | 1 | 1 | 1 | 1.00% | 30 oz water bottle |

## 7. Manual precision audit

- NEED_CANDIDATE: selected **50**, correct **40**, incorrect **9**, ambiguous **1**, precision **81.63%**.
- NON_NEED: selected **30**, correct **30**, incorrect **0**, ambiguous **0**, precision **100.00%**.
- AMBIGUOUS is excluded from the precision denominator.

| Group | Keyword | Predicted intent | Predicted resolution | Manual label | Reason |
|---|---|---|---|---|---|
| NEED_CANDIDATE | dog water bottle portable | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable dog water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel dog water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog travel water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable dog water bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog portable water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog water bottle with built-in bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable water bottle for dogs | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable water bowl for dog | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel water bowl for dogs | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | water bottle for dogs on walks | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable dog bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | insulated dog water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel dog bowls | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable dog water | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog travel water bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable dog water bottle with bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel water bottle for dogs | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog water bowl travel | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog travel water | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | stainless steel dog water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog travel bowls | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog walking water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog crate water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel dog water bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog portable water bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog water bottle for walks | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | animal water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | small dog water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | portable pet water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel dog bowl | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog drinking bottle portable | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog travel accessories | NEED_CANDIDATE | RESOLVED_BUYER_NEED | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | water bottle for dog crate | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | malsipree dog water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | asobu | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | doggy water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | cat water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | dog kennel water dispenser | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | crate water dispenser for dogs | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog hiking gear | NEED_CANDIDATE | RESOLVED_BUYER_NEED | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | dog water bottle for crate | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | travel dog water | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | stanley dog bowl | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | springland dog water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | INCORRECT | The frozen intent route admits a product, brand, broad, accessory, or out-of-scope term as a Buyer Need candidate. |
| NEED_CANDIDATE | travel water bottle | NEED_CANDIDATE | RESOLVED_BUYER_NEED | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| NEED_CANDIDATE | collapsible dog bowls | NEED_CANDIDATE | RESOLVED_BUYER_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog cage water dispenser | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | dog crate water dispenser | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NEED_CANDIDATE | puppy water bottle | NEED_CANDIDATE | UNKNOWN_NEED_CANDIDATE | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog food storage container | ACCESSORY_RELATED | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | rover and oak dog water bottle | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog water | BROAD_QUERY | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | hamster water bottle | OUT_OF_SCOPE | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog water bottle | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog food container | ACCESSORY_RELATED | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | trailhound dog water bottle | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog stuff | BROAD_QUERY | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | guinea pig water bottle | OUT_OF_SCOPE | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | water bottle for dogs | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog treat container | ACCESSORY_RELATED | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | trailhound insulated dog water bottle | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog accessories | BROAD_QUERY | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog water bottles | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog mom | ACCESSORY_RELATED | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | springer dog water bottle | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog accessories girl | BROAD_QUERY | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | pet water bottle | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | water bottle dog toy | ACCESSORY_RELATED | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | pupflask dog water bottle | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | puppy essentials | BROAD_QUERY | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | water bottle dog | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | poop bags for dogs | ACCESSORY_RELATED | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | pupflask | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog essentials | BROAD_QUERY | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | botella de agua para perros | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | yeti dog bowl | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | dog bottle | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | pup flask | BRAND_MODEL | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |
| NON_NEED | water bottle for dog | PRODUCT_OBJECT | EXPLICIT_NON_NEED | CORRECT | The predicted route is consistent with the explicit term semantics in the dog travel water context. |

## 8. Integrated Bowl holdout validation

- Relations / source ASINs / coverage: **48 / 48 / 48.00%**
- False positives: **0**
- Precision: **100.00%**
- Expressions: `["dog water bottle with built-in bowl"]`
- Judgement: **CONFIRMED**

## 9. Collapsible holdout validation

- Relations / source ASINs / coverage: **16 / 13 / 13.00%**
- True / false positives: **15 / 1**
- Precision: **93.75%**
- Recall observation: **100.00%**
- Expressions: `["collapsible dog bowls", "collapsible dog bowls large", "collapsible dog water bowl", "collapsible dog water bowl travel", "collapsible water bottles", "collapsible water bowl for dogs"]`

## 10. Crate compatibility experimental validation

- Relations / source ASINs: **22 / 13**
- False positives / precision: **0 / 100.00%**
- Expressions: `["dog crate water bottle", "water bottle for dog crate"]`
- Judgement: **PROMOTE_CANDIDATE** (no taxonomy promotion performed)

## 11. Insulated proposal validation

- Relations / source ASINs / coverage: **46 / 32 / 32.00%**
- Dog-related / generic / branded relations: **21 / 7 / 18**
- False positives: **25**
- Judgement: **KEEP_PROPOSAL** (no taxonomy change performed)

## 12. Outdoor Portability bias recheck

- Outdoor among matched Need relations: **885 / 1012 (87.45%)**
- Outdoor in raw organic relations: **885 / 1974 (44.83%)**
- Source ASIN coverage: **90 / 100 (90.00%)**
- Judgement: **DATA_DRIVEN_DOMINANCE**

## 13. New UNKNOWN audit

- Unresolved relations: **354**
- Unique unresolved terms: **152**
- New vs 20-ASIN pilot: **145**
- Category distribution: `{"AMBIGUOUS": 31, "EXISTING_TAXONOMY_GAP": 23, "NEW_VALID_BUYER_NEED": 9, "PRODUCT_OR_NON_NEED_MISROUTED": 89}`

| Term | Raw expressions | Relations | ASINs | New vs pilot | Audit category | Reason |
|---|---|---|---|---|---|---|
| 2 in 1 bottle | 2 in 1 bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| 2 in 1 water bottle | 2 in 1 water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| accesorios para perros | accesorios para perros | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| animal water bottle | animal water bottle | 12 | 12 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| asobu | asobu | 9 | 9 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| asobu bestie bottle | asobu bestie bottle | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| asobu water bottle | asobu water bottle | 3 | 3 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| beach dog essentials | beach dog essentials | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| bebedero de agua para perros | bebedero de agua para perros | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| bebedero para perros | bebedero para perros | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| bebederos para perros | bebederos para perros | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| botellas de agua para perros | botellas de agua para perros | 4 | 4 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| bottle buddy | bottle buddy | 2 | 2 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| boy dog accessories | boy dog accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| bunny water bottle | bunny water bottle | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| bunny water dispenser | bunny water dispenser | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| camo water bottle | camo water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| camping dog essentials | camping dog essentials | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| camping essentials for dogs | camping essentials for dogs | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| capybara water bottle | capybara water bottle | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| cat accessories | cat accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| cat sip | cat sip | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| cat water bottle | cat water bottle | 8 | 8 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| chateau | chateau | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| chihuahua accessories | chihuahua accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| choco lab water bottle | choco lab water bottle | 2 | 2 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| choco nose no drip water bottle | choco nose no drip water bottle | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| clear water bottle insulated | clear water bottle insulated | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| corgi water bottle | corgi water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| crate water bottle | crate water bottle | 4 | 4 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| crate water bowl no spill | crate water bowl no spill | 3 | 3 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| crate water dispenser for dogs | crate water dispenser for dogs | 8 | 8 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| cute water bottle | cute water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| dachshund accessories | dachshund accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dachshund water bottle | dachshund water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| dishwasher safe water bottle | dishwasher safe water bottle | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog accessories boy | dog accessories boy | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog bag holder | dog bag holder | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog bandana water bowl | dog bandana water bowl | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| dog beach | dog beach | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog beach essentials | dog beach essentials | 4 | 4 | False | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog bowl | dog bowl | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog bowls | dog bowls | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog bows | dog bows | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog cage water dispenser | dog cage water dispenser | 7 | 7 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog camping | dog camping | 5 | 5 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog camping essentials | dog camping essentials | 4 | 4 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog crate water | dog crate water | 2 | 2 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog crate water bowl no spill | dog crate water bowl no spill | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog crate water dispenser | dog crate water dispenser | 7 | 7 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog drinking bottle | dog drinking bottle | 3 | 3 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog food storage | dog food storage | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog friendly co | dog friendly co | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| dog kayak | dog kayak | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| dog kennel water bottle | dog kennel water bottle | 6 | 6 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog kennel water dispenser | dog kennel water dispenser | 8 | 8 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog needs | dog needs | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog poop bag holder | dog poop bag holder | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog supplies | dog supplies | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog tumbler | dog tumbler | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dog water bottle bowl | dog water bottle bowl | 3 | 3 | False | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog water bottle for crate | dog water bottle for crate | 8 | 8 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog water bottle with bowl | dog water bottle with bowl | 7 | 7 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog water bowl collapsible | dog water bowl collapsible | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| dog water bowl for car | dog water bowl for car | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| doggie water bottle | doggie water bottle | 3 | 3 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| doggy water bottle | doggy water bottle | 9 | 9 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| dogman water bottle | dogman water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| drip water bottles | drip water bottles | 5 | 5 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| female dog accessories | female dog accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| filtered water bottle | filtered water bottle | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| foldable bottle | foldable bottle | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| foldable dog bowl | foldable dog bowl | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| foldable dog water bowl | foldable dog water bowl | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| foldable water bottle | foldable water bottle | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| frenchie dog accessories | frenchie dog accessories | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| frost buddy bottle buddy with lid | frost buddy bottle buddy with lid | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| frost buddy water bottle | frost buddy water bottle | 3 | 3 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| girl dog accessories | girl dog accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| girl dog stuff | girl dog stuff | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| girl puppy accessories | girl puppy accessories | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| go dog | go dog | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| gorilla grip | gorilla grip | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| gorilla grip dog bowl | gorilla grip dog bowl | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| gravity water bowl | gravity water bowl | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| guinea pig water bottle no drip | guinea pig water bottle no drip | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| gulpy pet water dispenser | gulpy pet water dispenser | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| hamster water dispenser | hamster water dispenser | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| hemli | hemli | 1 | 1 | False | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| houndsy dog food dispenser | houndsy dog food dispenser | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| huellita go water bowl | huellita go water bowl | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| insulated bottles | insulated bottles | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| insulated dog water bottle | insulated dog water bottle | 21 | 21 | False | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| insulated snack container | insulated snack container | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| insulated water bottle | insulated water bottle | 2 | 2 | False | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| kennel water bottle | kennel water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| kennel water dispenser | kennel water dispenser | 3 | 3 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| little chonk | little chonk | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| lumoleaf dog water bowl | lumoleaf dog water bowl | 3 | 3 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| malsipree dog water bottle | malsipree dog water bottle | 9 | 9 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| mini water bottle | mini water bottle | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| no spill water bowl for dogs | no spill water bowl for dogs | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| norbit | norbit | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| one piece water bottle | one piece water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| pawp water for dogs | pawp water for dogs | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pawsip | pawsip | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| pawsipus dog water bottle | pawsipus dog water bottle | 3 | 3 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pee pad holder | pee pad holder | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pee pad holder for dogs | pee pad holder for dogs | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pet food container | pet food container | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pet water bottles for dogs | pet water bottles for dogs | 7 | 7 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pink dog accessories | pink dog accessories | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pink dog stuff | pink dog stuff | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| pink puppy accessories | pink puppy accessories | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| puppy accessories | puppy accessories | 2 | 2 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| puppy clothes | puppy clothes | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| puppy essentials girl | puppy essentials girl | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| puppy stroller | puppy stroller | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| puppy water bottle | puppy water bottle | 7 | 7 | False | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| puppy water bowl | puppy water bowl | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| rabbit water bottle | rabbit water bottle | 4 | 4 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| rabbit water bottle no drip for cage | rabbit water bottle no drip for cage | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| rabbit water bottles | rabbit water bottles | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| rabbit water dispenser | rabbit water dispenser | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| shiloh & bros | shiloh & bros | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| short water bottle | short water bottle | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| small pet water bottle | small pet water bottle | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| small water trough | small water trough | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| smart water bottle | smart water bottle | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| snack dispenser | snack dispenser | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| springland dog water bottle | springland dog water bottle | 8 | 8 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| stanley dog bowl | stanley dog bowl | 8 | 8 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| stanley water bottle | stanley water bottle | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| steel snack containers | steel snack containers | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| tal water bottle | tal water bottle | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| thermos water bottle | thermos water bottle | 3 | 3 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| to go buddy | to go buddy | 1 | 1 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| vittles vault | vittles vault | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| waggle | waggle | 2 | 2 | True | AMBIGUOUS | The term alone does not support a reliable category-relevant intent judgement. |
| water bottle dog bowl | water bottle dog bowl | 4 | 4 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| water bottle for rabbits | water bottle for rabbits | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| water bottle insulated | water bottle insulated | 1 | 1 | False | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| water bottle rabbit | water bottle rabbit | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| water bottle with dog bowl | water bottle with dog bowl | 1 | 1 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| water bottle with snack compartment | water bottle with snack compartment | 1 | 1 | True | NEW_VALID_BUYER_NEED | The term explicitly expresses a plausible category-relevant attribute, use case, audience, or integration not resolved by v0.2. |
| water bottles | water bottles | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| water dispenser for baby bottles | water dispenser for baby bottles | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| water dispenser for dog crate | water dispenser for dog crate | 4 | 4 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| water feeder for dogs | water feeder for dogs | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| water for dog crate | water for dog crate | 2 | 2 | True | EXISTING_TAXONOMY_GAP | The expression is a variant of a need concept already represented in v0.2 but is not matched by the frozen rule. |
| water for dogs | water for dogs | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |
| 宠物 | 宠物 | 1 | 1 | True | PRODUCT_OR_NON_NEED_MISROUTED | The term is primarily a product/object, brand/model, accessory, broad, or out-of-scope query rather than a Buyer Need. |

## 14. Optional Top-30 keyword enrichment

- Executed: **True**
- Selection used ASIN coverage, provider traffic, organic rank, and stable text order.
- `query_origin` remains `ASIN_REVERSE_RETURNED`.

| Keyword | Search volume | ABA rank | CPC | Difficulty | Origin |
|---|---|---|---|---|---|
| dog water bottle | 10968 | 14765 | 0.97 | 63 | ASIN_REVERSE_RETURNED |
| dog water bottle portable | 8106 | 22644 | 0.87 | 64 | ASIN_REVERSE_RETURNED |
| portable dog water bottle | 2630 | 84907 | 0.89 | 64 | ASIN_REVERSE_RETURNED |
| water bottle for dogs | 1324 | 143899 | 0.73 | 53 | ASIN_REVERSE_RETURNED |
| travel dog water bottle | 1125 | 168176 | 0.86 | 62 | ASIN_REVERSE_RETURNED |
| dog travel water bottle | 1861 | 104103 | 0.83 | 64 | ASIN_REVERSE_RETURNED |
| portable dog water bowl | 4862 | 46553 | 0.98 | 65 | ASIN_REVERSE_RETURNED |
| dog portable water bottle | 803 | 232819 | 0.78 | 63 | ASIN_REVERSE_RETURNED |
| dog water bottle with built-in bowl | 881 | 212867 | 1.01 | 54 | ASIN_REVERSE_RETURNED |
| dog water bottles | 377 | 482891 | 0.88 | 62 | ASIN_REVERSE_RETURNED |
| portable water bottle for dogs | 583 | 317193 | 0.78 | 62 | ASIN_REVERSE_RETURNED |
| portable water bowl for dog | 1643 | 117137 | 0.89 | 58 | ASIN_REVERSE_RETURNED |
| travel water bowl for dogs | 1522 | 126010 | 0.89 | 57 | ASIN_REVERSE_RETURNED |
| water bottle for dogs on walks | 372 | 489834 | 0.8 | 61 | ASIN_REVERSE_RETURNED |
| pet water bottle | 1008 | 186927 | 0.83 | 57 | ASIN_REVERSE_RETURNED |
| water bottle dog | 253 | 707657 | 0.73 | 55 | ASIN_REVERSE_RETURNED |
| botella de agua para perros | 326 | 556533 | 0.95 | 56 | ASIN_REVERSE_RETURNED |
| dog bottle | 225 | 791072 | 1.03 | 60 | ASIN_REVERSE_RETURNED |
| water bottle for dog | 197 | 896478 | 0.82 | 63 | ASIN_REVERSE_RETURNED |
| rover and oak dog water bottle | 604 | 306837 | 0.95 | 53 | ASIN_REVERSE_RETURNED |
| trailhound dog water bottle | 531 | 347274 | 0.9 | 65 | ASIN_REVERSE_RETURNED |
| portable dog bowl | 1084 | 174401 | 0.91 | 65 | ASIN_REVERSE_RETURNED |
| insulated dog water bottle | 270 | 665395 | 0.95 | 53 | ASIN_REVERSE_RETURNED |
| travel dog bowls | 3559 | 66257 | 1.01 | 64 | ASIN_REVERSE_RETURNED |
| portable dog water | 337 | 539142 | 0.86 | 61 | ASIN_REVERSE_RETURNED |
| dog travel water bowl | 821 | 227905 | 0.93 | 59 | ASIN_REVERSE_RETURNED |
| portable dog water bottle with bowl | 334 | 543216 | 0.77 | 61 | ASIN_REVERSE_RETURNED |
| dog bottle water dispenser | 304 | 594961 | 1.08 | 66 | ASIN_REVERSE_RETURNED |
| travel water bottle for dogs | 250 | 715253 | 0.84 | 65 | ASIN_REVERSE_RETURNED |
| dog water bowl travel | 589 | 314188 | 0.84 | 60 | ASIN_REVERSE_RETURNED |

## 15. Success criteria

| Criterion | Result |
|---|---|
| holdout_independent | True |
| true_need_resolution_rate_gte_85pct | False |
| buyer_need_unresolved_rate_lte_30pct | True |
| need_precision_gte_90pct | False |
| non_need_precision_gte_90pct | True |
| integrated_bowl_independently_addressed | True |
| collapsible_precision_not_collapsed | True |
| lineage_complete | True |
| manual_audit_complete | True |

## 16. Generalization judgement

**TAXONOMY_V0_2_OVERFIT**

This judgement is evidence aggregation over the frozen v0.2 implementation. No taxonomy, intent, semantic, gap, scoring, or policy rule was changed during the holdout.

## 17. Limitations

- Only first-page/top-20 reverse keywords per ASIN were captured.
- ASIN coverage is recurrence in this cohort and is not Demand Share.
- Provider traffic semantics remain provider-defined and uncalibrated.
- Parent ASIN is UNKNOWN whenever the forward response omits it.
- Manual precision is a structured term audit, not Amazon behavioral ground truth.

## 18. Next step — one recommendation

Keep v0.2 frozen and run a second independent time-window holdout before any taxonomy promotion or rule change.
