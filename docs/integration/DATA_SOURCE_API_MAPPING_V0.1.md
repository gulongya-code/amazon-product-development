# Data Source API Mapping V0.1

Status: TASK-SP-018A design baseline
Analysis date: 2026-08-18
Scope: XiYou OpenAPI and Sorftime Open API capability analysis only; no connector, credential, or business API call was created.

## 0. Analysis boundary and evidence

This document maps documented provider capabilities to the existing Canonical and Operator Workbook V0.2 contracts. It does not add fields, select a winning provider, resolve conflicts, or reinterpret provider estimates as observed facts.

Primary sources reviewed:

- [XiYou OpenAPI V2 integration guide](https://openapi-doc.xydc.com/)
- [XiYou ASIN product information](https://openapi-doc.xydc.com/335282030e0)
- [XiYou recent ASIN orders](https://openapi-doc.xydc.com/339953324e0)
- [XiYou ASIN variations](https://openapi-doc.xydc.com/370838212e0)
- [XiYou BSR daily trend](https://openapi-doc.xydc.com/327781736e0)
- [XiYou product information daily trend](https://openapi-doc.xydc.com/331311535e0)
- [XiYou keyword information](https://openapi-doc.xydc.com/333379279e0)
- [XiYou keyword ABA weekly trend](https://openapi-doc.xydc.com/333362889e0)
- [XiYou keyword-to-ASIN analysis](https://openapi-doc.xydc.com/451262166e0)
- [XiYou ASIN-to-keyword research](https://openapi-doc.xydc.com/331502595e0)
- [XiYou traffic score daily/weekly/monthly trends](https://openapi-doc.xydc.com/326002208e0)
- [Sorftime Open API portal](https://open.sorftime.com/api)
- [Sorftime Product Intelligence capability audit](../../research/sorftime_product_intelligence_audit_v0_1/SORFTIME_PRODUCT_INTELLIGENCE_AUDIT_V0.1.md)
- [Canonical provider mapping examples](../design/CANONICAL_PROVIDER_MAPPING_EXAMPLES_V0.1.md)

XiYou exposes public endpoint-level documentation and response examples. Sorftime's public portal is a JavaScript application and did not expose a complete unauthenticated field catalogue in static page content. Therefore Sorftime fields marked as confirmed below are limited to the provider tool schemas and sanitized responses already preserved and audited in this repository. Anything not confirmed by that evidence remains `UNKNOWN`; no marketing-page capability was promoted to an API field.

## 1. Data source overview

### 1.1 XiYou OpenAPI positioning

XiYou is a market, keyword, ranking, traffic, and time-series evidence provider. Its documented V2 authentication uses `X-Auth-Version: 2.0` and `X-Api-Key`, while business paths remain under `/v1/...`. The public guide documents a default 40 requests per minute, credit-based billing, trace IDs, and retry guidance. These operational details belong to the future connector boundary and must never be written into workbook data.

Recommended business role:

- primary keyword and directional query source;
- primary rank, BSR, channel, and traffic evidence source;
- primary explicit-period trend source;
- supplementary current product price/rating/review-count source;
- supplementary recent order evidence source whose method and parent/child grain remain unresolved.

### 1.2 Sorftime Open API positioning

Sorftime is a product-evidence and review-oriented provider. Audited capabilities include product detail, structured attributes, category, parent ASIN, description, images, listing date, package facts, fulfillment, monthly sales-volume evidence, child variations, recent variation sales figures, raw reviews, product trend, and product search.

Recommended business role:

- primary rich product profile and structured attribute source;
- primary raw review evidence source;
- primary variation-property source;
- supplementary price/rating/review-count and sales-estimate source;
- supplementary product-search and product-trend source after its public API schema is contract-tested.

### 1.3 Combined role

| Layer | Primary source | Secondary source | Boundary |
|---|---|---|---|
| Product identity/current facts | Sorftime | XiYou | Preserve both observations; do not overwrite conflicts. |
| Keyword demand/ABA/CPC | XiYou | None confirmed | Provider estimate and method status remain explicit. |
| Product-keyword relationships | XiYou | None confirmed | Keep `KEYWORD_TO_PRODUCT` and `PRODUCT_TO_KEYWORD` separate. |
| BSR/rank/channel | XiYou | Sorftime product trend where documented | Rank context, position code, period, and provider are mandatory. |
| Sales/order evidence | Both | — | XiYou orders, Sorftime monthly sales, and variation `SalesAmount` are not aliases. |
| Reviews | Sorftime | None confirmed | Raw review facts only; no sentiment or recommendation inference. |
| Trend inputs | XiYou | Sorftime | Workbook trend text remains a system projection, not a provider conclusion. |

## 2. API module analysis

### 2.1 XiYou modules

| Data module | API capability | Field examples | Operator use |
|---|---|---|---|
| Product data | `/v1/asins/info` batch current facts | `country`, `asin`, `title`, `currency`, `price`, `stars`, `ratings`, image/URL fields | Product database identity, title, price, rating, review-count evidence. |
| Product change | `/v1/asins/infoChange/trends/daily`, `/v1/asins/info/trends/daily` | `date`, current/previous title/image, `ratings`, `stars`, `priceDistribution.*` | Listing-change and price/rating/review-count trend evidence. |
| Variations | `/v1/asins/variations` | `asin`, `country`, `parentAsin`, `childAsins[]`, `lastUpdatedTime` | Parent/child organization and child count; only explicit edges are usable. |
| Orders/sales | `/v1/asins/orders`, documented monthly order trend | `asin`, `orders`, period request fields | Recent order evidence and trend input; method/grain cannot be inferred. |
| BSR | `/v1/asins/bsrInfo/trends/daily` | `categoryTree[].categoryId/name/root`, `trends[].date`, `values[].rank` | BSR value with category and period context. |
| Keyword metrics | `/v1/searchTerms/info` | `searchTerm`, `competitiveDifficulty`, `abaReport.searchFrequencyRank`, `abaReport.weeklySearchVolume`, `costPerClick.value/minSuggestedBid/maxSuggestedBid` | Search volume, CPC, ABA rank, difficulty, and related top-ASIN evidence. |
| Keyword trends | `/v1/searchTerms/abaReport/trends/weekly` | week range, competition difficulty, organic rotation, conversion rate, CPC range | Period-aware keyword trend and estimation evidence. |
| Keyword to ASIN | `/v1/searchTerms/analysis/list/period` and `/monthly` | `asin`, `ranks[].position/totalRank/page/pageRank/rankTime`, traffic totals/ratios/growth | Forward query results, product relationships, channel/rank/traffic evidence. |
| ASIN to keyword | `/v1/asins/research/list/period` and `/monthly` | `searchTerm`, ranks, `trafficSummary.traffic`, acquisition rates | Reverse relationship evidence and ASIN keyword coverage. |
| ASIN-keyword trends | documented daily traffic and daily/hourly rank trend endpoints | date/time, rank, traffic, position code | Fine-grained relationship trend evidence. |
| Traffic trends | `/v1/asins/trafficScore/trend/daily`, `/weekly`, `/monthly` | `summaryTrafficScore.organic/advertising`, `positionTrafficScore.*`, date/week/month | Organic/sponsored traffic evidence and trend inputs; score method must remain provider-defined. |
| Advertising change | `/v1/asins/advertisingChange/trends/daily` | dated advertising-change records | Advertising-change context; not an opportunity guarantee. |

### 2.2 Sorftime modules

| Data module | API capability | Field examples confirmed by audited schema | Operator use |
|---|---|---|---|
| Product detail | `product_detail` | `asin`, `title`, `brand`, `category`, `node_id`, `attributes`, `description`, `parent_asin`, `price`, `star_rating`, `review_count`, `monthly_sales_volume` | Rich product database, product features, price/rating/review/sales evidence. |
| Product enrichment | `product_detail` | images, listing date, package dimensions/weight, fulfillment, variation count, A+ presence | Feature inventory, listing maturity, fulfillment and visual/product context. |
| Variations | `product_variations` | child `Asin`, `Property`, `ItemIndex`, `ItemTotal`, `SalesAmount` | Child variants, variation attributes and recent page-published sales evidence. |
| Reviews | `product_reviews` | `content`, `review_date`, `star_rating`, `title`, `variant_attribute` | Review evidence and variant-specific operator review. Helpful votes/pagination are not confirmed. |
| Review summary | `product_customers_say` | provider/Amazon review summary capability | Future display enrichment only; must not replace raw review evidence. |
| Product trends | `product_trend` | monthly sales/amount, price, main-rank or BSR trend as described by tool schema | Secondary product trend source after exact response schema verification. |
| Product discovery | `product_search`, `product_search_from_name` | marketplace filters, result list, product matches | Candidate discovery and product-set construction; pagination/completeness must be explicit. |
| Product features | `similar_product_feature` | subcategory/product feature evidence | Feature vocabulary enrichment; not a competitor ranking. |
| Provider analysis | `product_report` | provider-generated product analysis report | P2 reference only; cannot be treated as canonical fact or system recommendation. |

## 3. Field mapping principles

1. Provider response fields map to existing Canonical dimensions and metrics only.
2. Request context may support scope but is not silently promoted to a response field.
3. `null`, missing, explicit empty, zero, and provider sentinel values remain distinct.
4. XiYou `orders`, Sorftime `monthly_sales_volume`, and variation `SalesAmount` remain separate metrics with separate periods and methods.
5. Ranking requires value, metric, context, channel, provider, and period. Unknown position codes remain unknown.
6. Sorftime `attributes` and `description` are evidence; the connector must not invent typed bullets or resolve unit conflicts.
7. Counts, states, risk alerts, scores, recommendations, IDs, and lineage records are system-calculated outputs even when their inputs are provider fields.
8. Provider estimates never become observed facts solely because the value is numeric.

## 4. NOT_AVAILABLE elimination analysis

### 4.1 Directly reducible after connectors

The following currently sparse business fields have confirmed provider inputs and can usually stop showing `NOT_AVAILABLE` when the relevant endpoint returns present evidence:

- product title, brand, category, price, rating, review count;
- BSR and BSR category context;
- recent orders, monthly sales-volume evidence, and explicit units where documented;
- parent ASIN, child ASIN inventory, variation role/property summary;
- structured product attributes and fulfillment/FBA evidence;
- keyword search volume, CPC, ABA rank, difficulty, related products;
- product-keyword relationship, direction, channel, rank and explicit period;
- product and keyword trend inputs.

### 4.2 Reducible only through deterministic system projection

These fields cannot come directly from either API and must remain calculated from validated upstream evidence:

- observed product/relationship/provider counts and shares;
- candidate/state/conflict/time-quality classifications;
- min/max comparable price and feature inventory summaries;
- demand, competition, product, missing-evidence and risk signals;
- opportunity scores, explanations and recommendations;
- all snapshot/output/export/evidence/lineage IDs and audit references.

### 4.3 Not eliminable from confirmed provider evidence

- `Locale`: neither confirmed interface directly supplies a locale; marketplace-to-locale guessing is unsafe.
- `Manual Review Status`: this is an operator-owned workflow field, not provider data.
- `Seller`: no stable direct field was confirmed in the audited Sorftime schema or XiYou public response examples.
- `Estimate Method Status`: providers expose values and some periods, but the derivation method is not documented sufficiently for a confirmed status.

## 5. Data acquisition priority

### P0 — Directly affects product and market review

| Slice | Endpoints/tools | Reason |
|---|---|---|
| Current product facts | XiYou `/v1/asins/info`; Sorftime `product_detail` | Fills ASIN/title/brand/category/price/rating/review/product attributes. |
| Keyword metrics | XiYou `/v1/searchTerms/info` | Supplies search volume, CPC, ABA rank and difficulty with report context. |
| Directional relationships | XiYou keyword analysis and ASIN research endpoints | Required for related products, channels, ranks and competition evidence. |
| BSR | XiYou BSR daily trend | Supplies explicit rank, category context and date. |
| Variations | XiYou variations; Sorftime `product_variations` | Required for parent/child scope and variant attributes. |
| Sales evidence | XiYou orders; Sorftime `monthly_sales_volume` | Important for product review, but must remain non-comparable estimates. |

### P1 — Strengthens analysis and quality review

| Slice | Endpoints/tools | Reason |
|---|---|---|
| Product/traffic/keyword trends | XiYou daily/weekly/monthly trend endpoints; Sorftime `product_trend` | Enables period-aware change evidence without inventing trend conclusions. |
| Reviews | Sorftime `product_reviews` | Adds direct qualitative evidence for operator review. |
| Product discovery | Sorftime `product_search`; XiYou keyword analysis | Expands candidate coverage with explicit pagination/completeness controls. |
| Listing changes | XiYou info/advertising change endpoints | Adds context for freshness and listing intervention. |

### P2 — Future enrichment

| Slice | Endpoints/tools | Reason |
|---|---|---|
| Review summaries | Sorftime `product_customers_say` | Useful display enrichment but must not replace raw evidence. |
| Similar-product features | Sorftime `similar_product_feature` | Feature discovery, not ranking or product selection. |
| Provider reports | Sorftime `product_report` | Provider analysis must remain separately labeled and non-authoritative. |
| Fine-grained hourly rank | XiYou hourly ASIN-keyword trend | High cost/volume; only needed for later monitoring use cases. |

## 6. SP-018B connector scope

SP-018B should implement a narrow, credential-safe P0 acquisition boundary only:

1. XiYou V2 transport envelope with server-side credential injection, timeout, 429 handling, trace ID, credit metadata, and no secret logging.
2. XiYou calls for ASIN info, orders, variations, BSR, keyword info, forward keyword analysis, and reverse ASIN research.
3. Sorftime calls for product detail and product variations; `product_reviews` may be a separately enabled P1 slice.
4. Raw immutable response capture, request-scope capture, collection-run identity, provider schema status, and source hash.
5. Existing adapter invocation only after payload-kind validation; no direct Workbook writing.
6. Pagination/completeness records for every list endpoint and explicit empty-query evidence.
7. Rate, credit, retry, and partial-failure diagnostics without business-value inference.

Explicitly out of SP-018B:

- new Canonical or Workbook fields;
- scoring, recommendation, conflict resolution, or provider weighting changes;
- review sentiment, competitor ranking, opportunity guarantees, or purchase recommendations;
- automatic unit conversion or cross-provider sales/order comparison;
- live credential storage design beyond an injected secret reference.

## 7. Exit criteria for SP-018B

- P0 endpoint contracts are fixture-backed and fail closed on schema drift.
- No connector response bypasses Raw Evidence and Canonical mapping.
- Empty, missing, null, zero and provider sentinels remain distinct.
- Every emitted observation has provider, source tool/field, collection run, raw reference, mapping version and bundle fingerprint.
- A connector can run for one provider without requiring the other.
- No credential value appears in fixtures, logs, tests, workbook output or Git history.
