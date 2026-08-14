# XiYou MCP Tool Inventory — TASK-SP-001

- Audit date: 2026-08-14
- MCP server: xydc-mcp
- Marketplace: US
- Probe mode: read-only, minimal calls, batch-first
- Business calls: 21
- Batch calls: 3
- Failed calls: 0
- Provider-reported credits across responses: 32
- Pagination policy: get_asin_keywords and get_keyword_asin_analysis were limited to page 1, page_size 20; these are head samples, not full exports.

| Tool | Purpose | Batch support | Input scope used | Actual high-level response fields | Calls | Result | Notes |
|---|---|---:|---|---|---:|---|---|
| get_asin_info | Product identity and current market facts | Yes | 3 ASINs in one US request | cost_credits, status, entities; amazonUrl, asin, bigPicUrl, country, currency, price, ratings, smallPicUrl, stars, title | 1 | SUCCESS | Does not return brand, category, bullet points, product attributes, or update time. |
| get_asin_variations | Parent/child variation relationship | No | 1 ASIN per US request | cost_credits, status; asin, childAsins, country, lastUpdatedTime, parentAsin | 3 | SUCCESS | Two samples returned parent/children; B0GTDPF5NR returned empty parent and child list. Empty values do not explicitly distinguish standalone product from unavailable relationship data. |
| get_asin_orders_last_30_days | Recent order metric | Yes, max 100 ASINs | 3 ASINs in one US request | cost_credits, status; country, entities; asin, orders | 1 | SUCCESS | Tool contract says last 30 days, but response has no exact date boundaries, as-of time, estimate flag, or parent/child grain. |
| get_asin_bsr_trends | Daily BSR and category evidence | No | 1 ASIN per request; 2026-08-07 through 2026-08-13 | cost_credits, status; asin, categoryTree, country, dateRangeNotice, trends; date, categoryId, rank | 3 | SUCCESS | Seven daily points returned for each sample. Supplies category identity missing from get_asin_info. |
| get_asin_keywords | Reverse keyword and traffic evidence | No | 1 ASIN; page 1; 20 rows; traffic descending | cost_credits, status; list, total; country, ranks, searchTerm, trafficSummary; page, pageRank, totalRank, position, rankTime; organic/advertising traffic | 3 | SUCCESS | Totals were 91, 568, and 162; only first 20 rows preserved. Search volume is not returned. Position codes are not decoded by the raw response. |
| get_keyword_info | Weekly keyword demand indicators | Yes | 9 keywords in one US request | cost_credits, status; list, total; searchTerm, abaReport, reportFromDate, reportToDate, weeklySearchVolume, searchFrequencyRank, topAsins, competitiveDifficulty, costPerClick, clickConversionRate, organicRotation | 1 | SUCCESS | Six consumer keywords returned ABA data for 2026-08-02 through 2026-08-08. Three industrial valve keywords returned abaReport=null. |
| get_keyword_asin_analysis | Keyword-to-candidate-ASIN competition set | No | 1 keyword; page 1; 20 rows; traffic descending | cost_credits, status; list, total; asin, asinInfo, country, ranks, trafficSummary; title, price, stars, ratings; page/pageRank/totalRank/position/rankTime; organic/advertising traffic | 9 | SUCCESS | Six keywords returned candidate sets; all three industrial valve keywords returned total=0. No parent/child indicator or category/brand/attributes in candidate profiles. |

## Call accounting

| Tool | Total calls | Batch calls | Successful calls | Failed calls | Provider-reported credits |
|---|---:|---:|---:|---:|---:|
| get_asin_info | 1 | 1 | 1 | 0 | 3 |
| get_asin_variations | 3 | 0 | 3 | 0 | 15 |
| get_asin_orders_last_30_days | 1 | 1 | 1 | 0 | 1 |
| get_asin_bsr_trends | 3 | 0 | 3 | 0 | 3 |
| get_asin_keywords | 3 | 0 | 3 | 0 | 3 |
| get_keyword_info | 1 | 1 | 1 | 0 | 1 |
| get_keyword_asin_analysis | 9 | 0 | 9 | 0 | 6 |
| **Total** | **21** | **3** | **21** | **0** | **32** |

## Business-result qualifications

- SUCCESS means the MCP call completed and returned status 200. It does not mean every requested entity had data.
- The three valve keyword-to-ASIN calls were technically successful but returned empty lists and zero credits.
- No retry was performed for those empty results because the same three terms also returned abaReport=null from the independent batch keyword-info call. The two responses consistently indicate a coverage gap rather than a transient transport failure.
- No extra category-resource or large historical tool was called.

