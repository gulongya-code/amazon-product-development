# Sorftime Relevant Amazon Product Intelligence Tools — TASK-SP-002

- Audit date: 2026-08-14
- MCP server: sorftime
- Session tool discovery: 88 total Sorftime tools
- Marketplace scope used: Amazon US only
- Relevant Amazon Product Intelligence tools recorded: 9
- Tools actually called: 3
- Business calls: 6
- Batch calls: 0; all selected tools are single-ASIN
- Failed calls: 0
- Provider credits/usage: not exposed in the responses
- Non-Amazon tools called: 0

| Tool | Purpose | Batch Support | Main Inputs | Expected Data | Actually Called |
|---|---|---:|---|---|---|
| product_detail | Detailed Amazon product profile | No; single ASIN | asin, amz_site | Identity, brand, category, attributes, description, images, parent, listing date, variation count, price/rating/reviews, package and market metrics | YES — 3 calls |
| product_variations | Child-variation details | No; one ASIN and page | asin, amz_site, page | Child ASIN, variation property string, recent page-published variation sales figure, item index/total | YES — 2 calls for products with variation_count > 0 |
| product_reviews | Reviews from the last year, at most 100 | No; one ASIN | asin, amz_site, review_type | Variant, review date, rating, title, body | YES — 1 call |
| product_customers_say | Amazon Customers Say review summary | No | asin, site | Provider/Amazon review summary rather than raw review evidence | NO — redundant for raw review-capability audit |
| product_report | Single-product analysis report | No | asin, amz_site | Provider analysis report | NO — analysis output was unnecessary after product_detail returned direct fields |
| product_trend | Historical product metrics | No | asin, amz_site, trend type | Monthly sales/amount, price, main-rank or BSR trend | NO — outside the minimal Product Intelligence gap test |
| product_search | Filtered real-time Amazon product search | No; page-based | marketplace plus filters | Product result list and market filters | NO — fixed ASINs were already known |
| product_search_from_name | Name-based Amazon product search | No; page-based | name, site, page | Up to 20 matching products | NO — fixed ASINs were already known |
| similar_product_feature | Subcategory product-feature lookup | Not indicated | product_name, amz_site | Subcategory feature evidence | NO — not a direct fixed-ASIN profile and unnecessary for gap closure |

## Actual call accounting

| Tool | Calls | Scope | Successful | Failed | Usage/credits |
|---|---:|---|---:|---:|---|
| product_detail | 3 | All fixed ASINs | 3 | 0 | Not exposed |
| product_variations | 2 | B0G2VV4RBW and B0F1XZJY5S | 2 | 0 | Not exposed |
| product_reviews | 1 | B0G2VV4RBW, Both sentiments | 1 | 0 | Not exposed |
| **Total** | **6** |  | **6** | **0** | **Not exposed** |

## Minimal-call rationale

- product_detail already returned brand, attributes, description, parent, variation count, images, category, listing date, package data, and overlapping current metrics. No product_report call was needed.
- product_variations was limited to the two samples whose product_detail reported positive variation counts. Page 1 returned all 6 and all 8 children respectively, so no further page was needed.
- product_reviews was called once on the lower-review-count industrial sample. It returned 8 reviews, sufficient to inspect the review schema. No large-scale review collection or analysis was performed.
- product_customers_say was not called because it is a review summary, not required raw review evidence.

