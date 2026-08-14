# SORFTIME PRODUCT INTELLIGENCE CAPABILITY AUDIT V0.1

**Audit status:** TASK-SP-002 COMPLETE  
**Audit date:** 2026-08-14  
**MVP decision:** **XIYOU_PLUS_SORFTIME_CORE_MVP_FEASIBLE_WITH_LIMITATIONS**

## Executive conclusion

Sorftime materially closes the Product Intelligence gaps found in TASK-SP-001. It directly returned brand, structured product attributes, category, parent ASIN, listing date, images, detailed HTML description, package dimensions/weight, variation counts, and other product facts for all three fixed ASINs. Targeted variation calls returned child ASINs with size/color properties, and one minimal review call returned review body, rating, date, title, and reviewed variant.

The strict bullet_points field remains only PARTIAL because Sorftime returns bullet-like listing content inside description rather than a dedicated bullet array. Technical evidence is rich but not automatically trustworthy: the industrial sample contains a pressure-unit conflict between attributes, title, and description. XiYou + Sorftime is therefore feasible for a core MVP, but semantic validation, provider timestamps, typed bullet normalization, and the industrial Keyword → ASIN gap remain limitations.

## A. Baseline

| Item | Result |
|---|---|
| Current directory | C:\Users\Administrator\Documents\亚马逊市场分析 |
| Isolation | Independent Amazon market-analysis workspace |
| Valid Git repository | NO |
| Sorftime MCP | Loaded in current session; 88 tools discovered |
| Sorftime handshake/tool availability | PASS |
| Sorftime marketplace used | Amazon US only |
| XiYou evidence | Reused TASK-SP-001 preserved evidence; no new XiYou business calls |
| XiYou MCP configuration changed by audit | NO |
| Protected projects modified | NO |
| Written path | research/sorftime_product_intelligence_audit_v0_1 |
| Non-Amazon marketplace calls | 0 |
| MCP configuration written by audit actions | NO |
| MCP config timestamp observation | Host-side config timestamp changed to 2026-08-14 16:13:41 +08:00 during the session. No audit command targeted or wrote the credential-bearing file. |

## B. Tool discovery

Nine Amazon Product Intelligence-relevant tools were recorded. Three were actually called:

1. product_detail — 3 calls, one per fixed ASIN.
2. product_variations — 2 calls for the two positive variation-count products.
3. product_reviews — 1 minimal review-capability call.

Six additional related tools were documented but not called because their output was redundant, analytical, search-oriented, or outside the minimal audit: product_customers_say, product_report, product_trend, product_search, product_search_from_name, and similar_product_feature.

All selected tools are single-ASIN; no batch endpoint was available.

## C. Calls

| Tool | Calls | Successful | Failed | Scope |
|---|---:|---:|---:|---|
| product_detail | 3 | 3 | 0 | Three fixed US ASINs |
| product_variations | 2 | 2 | 0 | Page 1; complete 6- and 8-child sets |
| product_reviews | 1 | 1 | 0 | One ASIN; Both; 8 returned reviews |
| **Total** | **6** | **6** | **0** | No unrelated marketplace calls |

Provider credits, quota, cost, or API usage were not exposed in the responses.

## D. Product field matrix

### D1. P0 — Critical

| Field | Status | Direct evidence |
|---|---|---|
| marketplace | PARTIAL | US is explicit in the audited request envelope, but product_detail does not echo the marketplace in its data object. |
| asin | PASS | Direct asin field for all samples. |
| title | PASS | Direct title field for all samples. |
| brand | PASS | SKLSSVF, Voatree, and Mocsicka returned directly. |
| category | PASS | category, node_id, top_category, and subcategory returned. |
| bullet_points | PARTIAL | No typed bullet_points field. description contains five labeled, br-separated listing sections for each sample, but was not relabeled as a formal bullet array. |
| product_attributes | PASS | attributes contains provider-documented key-value pairs; returned as a JSON-encoded string. |

### D2. P1 — Strong enhancement

| Field | Status | Direct evidence |
|---|---|---|
| parent_asin | PASS | Direct field for all three; B0GTDPF5NR equals its own parent value. |
| child_asins | PASS | product_variations returned full 6- and 8-child sets for positive samples; zero-variation spoon did not require a redundant call. |
| variation_theme | PARTIAL | No dedicated theme field; variation Property strings expose Size and Color keys. |
| variation_attributes | PASS | Per-child Property strings provide explicit key:value pairs. |
| technical_details | PASS | Structured attributes plus package dimensions/weight and detailed description. |
| description | PASS | Direct HTML description field for all three samples. |
| first_available_date | PASS | online_date is documented as listing date and returned for all samples. |
| manufacturer | MISSING | No direct field. Seller and brand were not substituted. |
| model_number | MISSING | No direct field. |
| included_components | MISSING | No typed field; description text was not converted into one. |
| images | PASS | main_image contains a JSON-encoded image URL list. |

### D3. P2 — Future enhancement

| Field | Status | Direct evidence |
|---|---|---|
| A+ text | PARTIAL | a_plus boolean is present; A+ content text is absent. |
| review text | PASS | content returned. |
| review rating | PASS | star_rating returned. |
| review date | PASS | review_date returned in yyyyMMdd. |
| review variant | PASS | variant_attribute returned. |
| helpful votes | MISSING | Not returned. |
| Q&A | MISSING | No audited direct tool/field. |
| rich product specifications | PASS | attributes, package_size_cm, weight_g, fulfillment, category and description evidence. |

## E. Per-ASIN findings

### E1. B0G2VV4RBW — Industrial ball valve

**Object Identification: READY**

Direct evidence identifies a valve in node 1265144011 / Ball Valves, with brand SKLSSVF and parent B0G2VVX3ML.

**Attribute Extraction: READY**

Direct attributes include:

- Material
- Brand
- item dimensions
- exterior finish
- 0.5-inch inlet and outlet sizes
- National Pipe Tapered / NPT connection types
- maximum operating pressure field
- two ports

The description additionally contains direct evidence for 304 stainless steel, PTFE seal, NPT thread, male/female connection, full-port shut-off design, working temperature, pressure, use with water/oil/gas, and locking handle.

**Complex Product Understanding: READY WITH SEMANTIC RISK**

The required 1/2 inch, NPT, thread/interface, material, valve type, and technical-specification evidence is directly present. However:

- attributes says Maximum Operating Pressure = 1000 pascal;
- title says 1000 WOG;
- description says up to 1000 PSI.

This conflict must remain unresolved until validated; no unit was selected as canonical.

**Variation evidence**

Six child ASINs were returned with Size properties ranging from 1/2 Inch to 2 Inch. The audited ASIN is Size:1/2 Inch.

### E2. B0GTDPF5NR — Clear plastic spoons

**Object Identification: READY**

Direct evidence identifies a SPOON in Disposable Spoons, brand Voatree.

**Attribute Extraction: READY**

Direct attributes provide Material=Plastic, Style=Clear, Number of Pieces=390, and a color/property value. Direct description supplies 6.5-inch size, bulk quantity, reinforced/deep-bowl feature, heat/cold resistance, BPA-free claim, storage pouch, and intended-use contexts.

No formal included_components field was returned, so the storage pouch text was not promoted to a canonical component.

### E3. B0F1XZJY5S — Pink bow bath mat

**Object Identification: READY**

Direct evidence identifies a RUG in Bath Rugs, brand Mocsicka, parent B0F8VBZCFK.

**Attribute Extraction: READY**

Direct attributes provide size, microfiber material, tufted weave, item weight, and brand. Description provides absorbency, anti-slip TPR backing, machine-wash instructions, and use locations.

**Style / Aesthetic Understanding: READY**

Evidence is not title-only. The title and description directly contain Pink Bow, cute/bow styling, bathroom/bath-mat identity, and multiple use contexts. Variation evidence directly supplies Color:Pink and size, with other children showing color/size alternatives.

**Variation evidence**

Eight child ASINs were returned with explicit Size and Color properties.

## F. Review capability

One product_reviews call for B0G2VV4RBW returned 8 reviews.

| Review capability | Status | Evidence |
|---|---|---|
| Review body | PASS | content |
| Rating | PASS | star_rating |
| Date | PASS | review_date |
| Title | PASS | title |
| Variant | PASS | variant_attribute |
| Helpful votes | MISSING | No field |
| Pagination/total | MISSING | No page, cursor, total, or has-next metadata in response |
| Review period | PARTIAL | Tool definition says last year; response has individual dates but no explicit window envelope |

No sentiment analysis, pain-point clustering, product recommendations, or Demand-Supply Gap derivation was performed.

## G. XiYou gap closure

| TASK-SP-001 gap | Sorftime closure | Evidence |
|---|---|---|
| Brand | CLOSED | Direct brand field for all three samples. |
| Bullet Points | PARTIALLY_CLOSED | Rich bullet-like content is present inside description, but no dedicated bullet_points schema. |
| Structured Product Attributes | CLOSED | Direct attributes key-value payload for all three samples. |

Additional enhancement capabilities:

- Technical Details: PASS, with the pressure-unit conflict noted.
- Variation Detail: PASS for positive-variation products.
- Description: PASS.
- Reviews: PARTIAL — core review fields present; helpful votes and pagination absent.
- A+ text: PARTIAL — boolean only.
- Manufacturer/model/included-components: MISSING as typed fields.

### Product Intelligence minimum-input test

Strict title + brand + bullet_points + attributes schema: **not fully satisfied** because bullet_points is not typed separately.

Practical result: **CORE_PRODUCT_EVIDENCE_AVAILABLE_WITH_SCHEMA_LIMITATION**. The evidence is not title-dominated: structured attributes and rich direct description content are available, but a future adapter must preserve provenance and must not silently rename description sections as Amazon bullets without validation.

## H. Cross-provider spot check

XiYou evidence was reused from TASK-SP-001. No new XiYou calls were made.

### H1. Overlapping current fields

| ASIN | Field | XiYou | Sorftime | Status |
|---|---|---|---|---|
| B0G2VV4RBW | Title | Same wording, straight quote | Same wording, curly quote | CONSISTENT |
| B0G2VV4RBW | Price USD | 18.99 | 18.99 | CONSISTENT |
| B0G2VV4RBW | Rating | 4.8 | 4.9 | MINOR_DIFFERENCE |
| B0G2VV4RBW | Review count | 20 | 21 | MINOR_DIFFERENCE |
| B0GTDPF5NR | Title | Same | Same | CONSISTENT |
| B0GTDPF5NR | Price USD | 17.99 | 17.99 | CONSISTENT |
| B0GTDPF5NR | Rating | 4.6 | 4.1 | MATERIAL_DIFFERENCE |
| B0GTDPF5NR | Review count | 75 | 78 | MINOR_DIFFERENCE |
| B0F1XZJY5S | Title | Minor spacing variation | Minor spacing variation | CONSISTENT |
| B0F1XZJY5S | Price USD | 18.39 | 18.39 | CONSISTENT |
| B0F1XZJY5S | Rating | 4.6 | 4.6 | CONSISTENT |
| B0F1XZJY5S | Review count | 180 | 180 | CONSISTENT |

XiYou product data was captured at 2026-08-14T07:44:59.345Z. Sorftime product calls were captured approximately 34 minutes later. Neither provider returned an explicit source observation timestamp for these current product facts, so differences cannot be assigned to freshness or accuracy without further evidence.

### H2. Category

All three category mappings are directionally consistent:

- Industrial & Scientific > Ball Valves ↔ VALVE / same Amazon node 1265144011.
- Health & Household > Disposable Spoons ↔ SPOON / same Amazon node 15754771.
- Home & Kitchen > Bath Rugs ↔ RUG / same Amazon node 1063242.

Status: **CONSISTENT**, with different representation granularity.

### H3. Sales/orders

| Provider | Metric | Values for the three ASINs | Unit | Period | Scope/method |
|---|---|---|---|---|---|
| XiYou | orders | 100 / 1000 / 300 | Not separately stated | Last 30 days per tool contract; exact dates absent | ASIN; parent/child and estimate method unconfirmed |
| Sorftime | monthly_sales_volume | 333 / 1125 / 736 | Units per tool documentation | Month not identified in response | Queried ASIN; estimate/capture method unconfirmed |
| Sorftime variation | SalesAmount | Per-child values | Documented as variation sales volume despite name | Most recently captured page-published figure within last 15 days | Child ASIN; -1 means no recent capture, not zero |

Cross-provider status: **NOT_COMPARABLE**. No percentage differences were calculated.

## I. Data semantics risks

1. product_detail does not echo marketplace; marketplace depends on the request envelope.
2. attributes and main_image are JSON-encoded strings rather than native nested fields.
3. No source observation timestamp accompanies current price/rating/review/product facts.
4. B0G2VV4RBW pressure evidence conflicts: pascal vs WOG vs PSI.
5. description looks like listing bullet content but is documented only as Product description.
6. parent_asin equals the queried ASIN for the zero-variation spoon; exact parent semantics should be normalized cautiously.
7. product_variations uses SalesAmount as a name while documentation calls it sales volume.
8. product_variations SalesAmount is a recent page-published figure within 15 days, not necessarily the same as product monthly_sales_volume or XiYou orders.
9. product_reviews exposes no pagination/total and only the tool definition states the last-year window.
10. Rating discrepancy for B0GTDPF5NR is material and cannot be resolved by capture-time proximity alone.
11. Manufacturer, model number, included components, helpful votes, and Q&A are not directly available in audited responses.
12. Sorftime marketplace/currency behavior is partly described by field documentation rather than echoed data.

## J. Combined provider readiness

| System stage | Status | Basis |
|---|---|---|
| Product Intelligence | READY | XiYou market facts plus Sorftime brand, category, structured attributes, description, variations and review raw material cover the core input foundation. Typed bullet and semantic validation remain limitations. |
| Demand Intelligence | PARTIAL | TASK-SP-001 remains unchanged: strong for six consumer keywords, incomplete for all three industrial valve terms. |
| Product–Demand Relevance input readiness | PARTIAL | Product-side evidence is now strong, but industrial keyword demand/forward-candidate coverage and rank-code semantics remain incomplete. |
| Market Reconstruction | PARTIAL | XiYou supplies candidate/rank/traffic evidence for six terms and Sorftime supplies richer product profiles, but industrial forward lookup, parent/child candidate grain, and full pagination remain gaps. |

No relevance algorithm, true-competitor set, Product Profile, Demand Profile, or opportunity score was implemented.

## K. Provider role recommendation

### XiYou

- PRIMARY_MARKET_PROVIDER
- PRIMARY_KEYWORD_PROVIDER
- PRIMARY_TRAFFIC_PROVIDER

### Sorftime

- PRIMARY_PRODUCT_EVIDENCE_PROVIDER
- PRIMARY_REVIEW_PROVIDER

No formal provider weighting or source-merging rule was created.

## L. MVP decision

**XIYOU_PLUS_SORFTIME_CORE_MVP_FEASIBLE_WITH_LIMITATIONS**

Evidence:

- Sorftime closes Brand and Structured Product Attributes for all three fixed ASINs.
- Sorftime provides rich description, technical data, variation details, images, listing date, category, and review raw material.
- XiYou continues to supply the stronger verified keyword, rank, traffic, BSR and market-evidence layer.
- The combined inputs are sufficient to start a provenance-preserving core MVP.

Limitations:

- bullet_points is schema-partial;
- industrial Keyword → ASIN and search-volume coverage remains absent;
- several metric definitions/timestamps remain uncertain;
- Sorftime contains at least one material cross-provider rating discrepancy and one internal technical-unit conflict;
- review pagination/helpful votes and several P1 fields are missing.

## M. Major remaining gaps

1. Industrial keyword demand and forward candidate-ASIN coverage.
2. Typed bullet_points and verified mapping between description sections and Amazon listing bullets.
3. Metric provenance, source observation timestamps, and comparable sales/order periods.
4. Pressure-unit conflict and provider data-quality validation.
5. Parent/child grain on XiYou candidate ASINs and cautious Sorftime parent normalization.
6. Manufacturer, model number, included components, review helpful votes, review pagination, Q&A, and A+ text.

## N. Safety and completion verification

- Fixed ASIN product-detail coverage: 3 / 3
- Sorftime raw MCP responses: 6
- Cross-provider audit projection: 1
- Valid JSON artifacts before report generation: 7 / 7
- Failed calls: 0
- isError=true responses: 0
- Sorftime credits/quota/usage exposed: NO
- New XiYou calls: 0
- Credentials written: NO
- Authorization/API key copied: NO
- MCP config written by audit actions: NO
- amazon_ads_optimizer modified: NO
- daily_data_auto_entry modified: NO
- Non-Amazon marketplace calls: 0
- Git commits/pushes/tags/PRs: 0
- Formal Product Intelligence implementation: 0

