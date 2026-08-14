# XIYOU CAPABILITY AUDIT V0.1

**Audit status:** TASK-SP-001 COMPLETE

## Executive conclusion

**Task:** TASK-SP-001  
**Audit date:** 2026-08-14  
**Recommendation:** **SECONDARY_DATA_SOURCE_RECOMMENDED**

XiYou supplies useful current product facts, BSR/category evidence, variation relationships, weekly keyword indicators, reverse keywords, candidate ASIN sets, rank observations, and separate organic/advertising traffic metrics. It is strong enough to be a primary market-metrics source for a constrained MVP, but it is not sufficient as the only source for the full first-stage intelligent product-selection MVP defined by this task.

The blocking gaps are direct product-understanding inputs: brand, bullet points, and structured attributes are absent. Keyword-to-ASIN reconstruction is also incomplete for the industrial test case: all three valve terms returned no candidate ASINs and no ABA/search-volume report, although reverse lookup for B0G2VV4RBW contained the matching term 1/2 ball valve with ranking evidence. A secondary listing/catalog source is therefore recommended.

## A. Baseline

| Item | Result |
|---|---|
| Current working directory | C:\Users\Administrator\Documents\亚马逊市场分析 |
| Independent product-selection/market-analysis directory | YES |
| Valid Git repository | NO; the existing .git directory was empty |
| Git remote | N/A |
| Git branch | N/A |
| Initial worktree status | N/A |
| MCP server | xydc-mcp |
| MCP connection | NORMAL; tool discovery, resource read, and all 21 business calls completed |
| Marketplace | US, explicitly confirmed by the user |
| Protected project amazon_ads_optimizer modified | NO |
| Protected project daily_data_auto_entry modified | NO |
| MCP configuration written by audit actions | NO |
| MCP config filesystem timestamp observation | The host-side file timestamp changed to 2026-08-14 15:44:59 +08:00 while the existing MCP connection was in use. No audit command targeted or wrote this file; content was not copied or diffed because it contains credentials. |
| Audit write directory | research/xiyou_capability_audit_v0_1 |
| Extra tools outside the prescribed seven | NONE |

The XiYou resource xiyou://guides/category-insight-workflow was read before business calls. No category resource was generated because this audit did not invoke category-insight tools.

## B. Fixed test samples

### ASINs

1. B0G2VV4RBW
2. B0GTDPF5NR
3. B0F1XZJY5S

### Keywords

1. 1/2 Ball Valve
2. 1/2 NPT Valve
3. 1/2 Shut Off Valve
4. plastic spoons
5. clear plastic spoons
6. plastic spoons heavy duty
7. pink bathroom rugs
8. bath mat cute
9. bow bathroom rug

## C. Actual MCP calls

| Tool | Calls | Mode | Success | Failure | Credits returned |
|---|---:|---|---:|---:|---:|
| get_asin_info | 1 | Batch, 3 ASINs | 1 | 0 | 3 |
| get_asin_variations | 3 | Single ASIN | 3 | 0 | 15 |
| get_asin_orders_last_30_days | 1 | Batch, 3 ASINs | 1 | 0 | 1 |
| get_asin_bsr_trends | 3 | Single ASIN, 7 complete days | 3 | 0 | 3 |
| get_asin_keywords | 3 | Single ASIN, page 1 × 20 | 3 | 0 | 3 |
| get_keyword_info | 1 | Batch, 9 keywords | 1 | 0 | 1 |
| get_keyword_asin_analysis | 9 | Single keyword, page 1 × 20 | 9 | 0 | 6 |
| **Total** | **21** | **3 batch calls** | **21** | **0** | **32** |

No retries were needed. Empty industrial keyword results were treated as valid empty business responses, not transport failures.

## D. Product data findings

### D1. Actual sample facts returned

| ASIN | Current facts | Category evidence | Variation evidence | Orders field | Reverse-keyword total |
|---|---|---|---|---:|---:|
| B0G2VV4RBW | title; USD 18.99; stars 4.8; ratings 20; images/link | Industrial & Scientific > Ball Valves | parent B0G2VVX3ML; 6 child ASINs; updated 2026-08-14 14:20:00 | 100 | 91 |
| B0GTDPF5NR | title; USD 17.99; stars 4.6; ratings 75; images/link | Health & Household > Disposable Spoons | empty parent; 0 child ASINs; updated 2026-08-14 07:05:00 | 1000 | 568 |
| B0F1XZJY5S | title; USD 18.39; stars 4.6; ratings 180; images/link | Home & Kitchen > Bath Rugs | parent B0F8VBZCFK; 8 child ASINs; updated 2026-08-13 10:00:00 | 300 | 162 |

The orders values above are reproduced raw provider metrics. They are not interpreted as verified Amazon sales.

### D2. Product identity/listing audit

| Canonical field | Status | Evidence |
|---|---|---|
| marketplace | PASS | country=US appears in product, variation, BSR, and relationship responses. |
| asin | PASS | Explicit in all ASIN responses and candidate items. |
| title | PASS | Returned for all three samples. |
| brand | MISSING | No brand field in get_asin_info or candidate asinInfo. Brand-like title text was not promoted into a brand value. |
| category | PASS | categoryTree with categoryId/name/root returned by get_asin_bsr_trends. |
| bullet_points | MISSING | No field returned. No title-derived substitute was created. |
| product_attributes | MISSING | No structured material, size, interface, feature, style, compatibility, or use-case fields returned. |
| parent_asin | PASS (P1) | Positive parent values for two samples; explicit empty value for one sample. |
| variations | PASS | childAsins arrays and parentAsin fields returned; one sample had an empty relationship. |
| main_image | PASS (P1) | bigPicUrl/smallPicUrl returned for all three samples. |

### D3. Market metric audit

| Metric | Status | Evidence classification | Notes |
|---|---|---|---|
| price | PASS | OBSERVED | price and currency returned. |
| rating | PASS | OBSERVED | stars returned. |
| review_count | PASS | OBSERVED | ratings returned as review/rating count. |
| orders_last_30_days | SEMANTICS_UNCONFIRMED | Unconfirmed provider metric | Tool contract says recent 30 days, but the response does not identify exact boundaries, as-of time, estimate method, order-versus-sales semantics, or parent/child grain. |
| bsr | PASS | PROVIDER_OBSERVATION | Daily categoryId/rank pairs returned for 2026-08-07 through 2026-08-13. |
| bsr_category | PASS | OBSERVED / PROVIDER_OBSERVATION | categoryTree returns root and leaf category IDs and names. |
| variation relationship | PASS | OBSERVED | parentAsin and childAsins are explicit. Standalone-versus-missing semantics remain unclear for empty relationships. |
| keyword traffic relationship | PASS | PROVIDER_OBSERVATION | Reverse-keyword and keyword-candidate responses expose rank observations plus trafficSummary. Units/method remain provider-defined. |

## E. Keyword data findings

get_keyword_info returned nine identity-preserving rows. Six rows contained abaReport data for the explicit weekly period 2026-08-02 through 2026-08-08; three industrial rows contained abaReport=null.

| Keyword | weeklySearchVolume | ABA rank | Difficulty | CPC value | Period/status |
|---|---:|---:|---:|---:|---|
| plastic spoons | 41910 | 2922 | 63 | 2.74 | 2026-08-02 to 2026-08-08 |
| clear plastic spoons | 1210 | 156875 | 60 | 2.53 | 2026-08-02 to 2026-08-08 |
| plastic spoons heavy duty | 1346 | 141606 | 51 | 3.09 | 2026-08-02 to 2026-08-08 |
| pink bathroom rugs | 8944 | 19657 | 81 | 0.74 | 2026-08-02 to 2026-08-08 |
| bath mat cute | 3059 | 75830 | 86 | 0.48 | 2026-08-02 to 2026-08-08 |
| bow bathroom rug | 247 | 725112 | 62 | 0.48 | 2026-08-02 to 2026-08-08 |
| 1/2 Ball Valve | — | — | — | — | abaReport=null |
| 1/2 NPT Valve | — | — | — | — | abaReport=null |
| 1/2 Shut Off Valve | — | — | — | — | abaReport=null |

### Keyword canonical audit

| Field | Status | Evidence |
|---|---|---|
| keyword | PASS | searchTerm in keyword-info and reverse-keyword responses; query keyword preserved in the audit envelope for keyword-to-ASIN calls. |
| search_volume | PARTIAL | Explicit weeklySearchVolume for 6/9 samples; null for all three industrial terms. |
| ABA rank | PARTIAL | Present for 6/9 samples. |
| competition difficulty | PARTIAL | Present for 6/9 samples. |
| suggested bid/CPC | PARTIAL | min, max, and value present for 6/9 samples. |
| marketplace | PASS | US is fixed in call input; country=US is echoed in relationship/product responses, although get_keyword_info does not echo country. |
| time period | PASS for populated ABA rows; MISSING for null rows | reportFromDate/reportToDate are explicit for six rows. |
| observation/update time | PARTIAL | ABA date range and individual rankTime values exist; no single overall retrieval/as-of time is returned by every tool. |

The weekly period is confirmed. The response nests weeklySearchVolume inside abaReport, but does not explain whether the numeric volume is direct Amazon ABA data, a XiYou estimate derived from ABA, or another transformation. Its metric-type provenance therefore remains unconfirmed.

## F. Keyword-ASIN relationship findings

### F1. Keyword to candidate ASIN set

| Keyword | total candidates reported | first-page rows preserved |
|---|---:|---:|
| plastic spoons | 647 | 20 |
| clear plastic spoons | 329 | 20 |
| plastic spoons heavy duty | 314 | 20 |
| pink bathroom rugs | 1426 | 20 |
| bath mat cute | 1322 | 20 |
| bow bathroom rug | 508 | 20 |
| 1/2 Ball Valve | 0 | 0 |
| 1/2 NPT Valve | 0 | 0 |
| 1/2 Shut Off Valve | 0 | 0 |

Returned candidate records contain asin, a compact asinInfo object, country, ranks, and trafficSummary. Rank observations may contain page, pageRank, totalRank, position, and rankTime. Traffic is explicitly split into organic, advertising, and total values.

- Can XiYou directly provide candidate ASINs for one keyword? **PARTIAL** — yes for 6/9 fixed terms, no candidates for the three industrial terms.
- Can XiYou distinguish organic vs sponsored competition? **YES at traffic level; PARTIAL at rank-code level** — trafficSummary uses explicit organic/advertising fields, but raw position codes such as or, sp, sb, sor, and sbv are not decoded.
- Is rank evidence sufficient for Market Reconstruction? **PARTIAL** — page/rank/time evidence is strong for returned candidates, but three terms are empty, position-code semantics are undocumented, pagination is partial, and candidate parent/child grain is absent.

### F2. ASIN to keyword set

All three ASINs returned non-empty reverse-keyword sets:

- B0G2VV4RBW: total 91; first 20 preserved.
- B0GTDPF5NR: total 568; first 20 preserved.
- B0F1XZJY5S: total 162; first 20 preserved.

Each returned keyword row contains searchTerm, country, rank observations, and organic/advertising/total traffic summaries. It does not contain search volume.

- Can XiYou provide reverse keyword evidence? **YES**, with **PARTIAL completeness** because only page 1 was requested and search volume must be obtained separately.
- Directional consistency risk: B0G2VV4RBW reverse lookup contains 1/2 ball valve with an organic rank observation, but the direct 1/2 Ball Valve keyword-to-ASIN request returned total=0.

## G. Canonical P0 capability matrix

The matrix contains the 22 required canonical rows. PARTIAL is not counted as PASS.

| # | Canonical field | Status | Primary reason |
|---:|---|---|---|
| 1 | ASIN | PASS | Explicit identifiers. |
| 2 | Marketplace | PASS | US request context and echoed country evidence. |
| 3 | Title | PASS | All products and candidate profiles. |
| 4 | Brand | MISSING | No direct field. |
| 5 | Category | PASS | BSR categoryTree. |
| 6 | Bullet Points | MISSING | Not returned. |
| 7 | Attributes | MISSING | Not returned. |
| 8 | Variation | PASS | parentAsin and childAsins. |
| 9 | Price | PASS | price/currency. |
| 10 | Rating | PASS | stars. |
| 11 | Review Count | PASS | ratings. |
| 12 | Orders Last 30 Days | SEMANTICS_UNCONFIRMED | Exact semantics, grain, dates, and estimate status absent. |
| 13 | BSR | PASS | Daily category ranks. |
| 14 | Keyword | PASS | searchTerm/query identity. |
| 15 | Search Volume | PARTIAL | 6/9 populated. |
| 16 | Keyword → ASIN | PARTIAL | 6/9 populated; industrial set empty. |
| 17 | Search Rank | PARTIAL | Numeric ranks for some placement types; incomplete samples and undocumented codes. |
| 18 | Organic / Sponsored distinction | PARTIAL | Explicit traffic split; rank-type code mapping absent. |
| 19 | Provider | PASS | xydc-mcp call provenance preserved. |
| 20 | Observation Time | PARTIAL | Some dates/timestamps, not universal. |
| 21 | Metric Type | SEMANTICS_UNCONFIRMED | Provider does not label observed versus estimated for orders/search volume/traffic. |
| 22 | Metric Period | PARTIAL | Explicit for ABA/BSR; incomplete for orders and traffic windows. |

### Coverage calculation

- PASS: **11**
- PARTIAL: **6**
- MISSING: **3**
- SEMANTICS_UNCONFIRMED: **2**
- CALL_FAILED: **0**
- PERMISSION_BLOCKED: **0**
- Total: **22**
- Strict coverage = 11 / 22 = **50.0%**
- Usable coverage = (11 + 6) / 22 = **77.3%**

Usable coverage is not a quality score. It only indicates that evidence exists at PASS or PARTIAL level.

## H. Data semantics risks

1. **Orders metric:** orders is returned without exact boundaries, as-of time, source/estimate label, parent-versus-child grain, or clarification of orders versus unit sales.
2. **Search-volume provenance:** period is explicit and the field sits inside abaReport, but the derivation and estimate method are not defined.
3. **Traffic metric:** organic, advertising, and total are separated, but units, calculation method, and exact seven-day window are not echoed in the response.
4. **Rank-type codes:** or, sp, sb, sor, and sbv are not decoded in raw data or tool schema; no mapping was inferred.
5. **Observation time:** rankTime includes timezone offsets; variation lastUpdatedTime lacks a timezone; current product facts and orders have no timestamp.
6. **Variation emptiness:** an empty parentAsin/childAsins response does not explicitly distinguish a standalone listing from missing relationship data.
7. **Candidate grain:** keyword-to-ASIN results do not identify parent versus child ASIN.
8. **Directional inconsistency:** industrial reverse lookup contains evidence where direct forward lookup returns no candidates.
9. **Partial pagination:** candidate/reverse-keyword evidence covers only the first 20 rows by design.
10. **Product detail insufficiency:** candidate and direct product profiles lack brand, category in the base profile, bullets, and attributes.

## I. Product Intelligence readiness

### PI-1 Basic Product Identification: PARTIAL

ASIN, title, category, price, rating, review count, images, and variation relationships are available. Brand is not directly supplied.

### PI-2 Structured Attribute Extraction: PARTIAL

Titles contain descriptive text, but bullet points and product_attributes are absent. The audit did not infer material, size, interface, feature, style, compatibility, or use cases from title text.

### PI-3 Complex Product Understanding: BLOCKED

Industrial specifications, compatibility, multi-attribute product facts, and appearance/style cannot be grounded reliably from the returned structured fields. Variation topology helps but does not replace listing attributes.

### Overall Product Intelligence: PARTIAL

XiYou can seed product identity and market facts, but a secondary listing/catalog source is needed for reliable structured product understanding.

## J. Demand Intelligence readiness

**PARTIAL**

Six consumer keywords have explicit weekly demand signals, ABA rank, competition, CPC, top-ASIN shares, and candidate competition. All three industrial keywords lack ABA/search-volume rows and direct candidate sets. Search-volume provenance also remains unconfirmed.

## K. Market Reconstruction readiness

**PARTIAL**

The future chain Keyword → Candidate ASINs → Product Profiles is supported for six terms. Returned candidates include rank observations and organic/advertising traffic separation. The chain is incomplete because:

- three industrial terms have no forward candidates;
- candidate parent/child grain is absent;
- candidate profiles lack brand/category/bullets/attributes;
- rank position codes are undocumented;
- only first-page samples were collected;
- forward and reverse industrial evidence is inconsistent.

## L. Major data gaps

1. No direct brand, bullet-points, or structured product-attribute data.
2. Industrial keyword demand and forward candidate-ASIN coverage failed across all three fixed valve terms.
3. Orders, search-volume provenance, traffic units/windows, and metric-type classifications are not fully specified.
4. Rank placement codes lack a documented mapping.
5. Candidate ASINs have no parent/child grain and limited product profiles.
6. Observation timestamps are inconsistent or missing across tools.

## M. MVP recommendation

**SECONDARY_DATA_SOURCE_RECOMMENDED**

XiYou is useful as a primary source for market metrics and relationship evidence, but relying on it alone would force the MVP either to hallucinate product attributes from titles or to leave core Product Intelligence and industrial Market Reconstruction incomplete. Add a secondary authorized listing/catalog source that directly provides brand, bullets, structured attributes, and parent/child-aware product profiles. Keep XiYou for BSR, recent provider metrics, keyword demand, ranks, traffic, and candidate-set discovery.

## N. Evidence classification and non-derivation statement

- OBSERVED: identifiers, titles, prices, stars, ratings, images/links, categories, variation links, and dated rank observations where directly returned.
- PROVIDER_OBSERVATION: BSR and rank/traffic relationship records.
- SEMANTICS_UNCONFIRMED: orders, weeklySearchVolume provenance, and traffic metric units/method where the provider did not label the calculation.
- RESOLVED: none generated.
- DERIVED: none generated.

No formal product_type, use_case, relevance score, true-competitor label, or opportunity score was produced.

## O. Safety and isolation

- Authorization token exposed: NO
- Complete MCP user configuration copied: NO
- MCP configuration written by audit actions: NO
- Host-side MCP config timestamp changed during the live-call session: YES; cause not attributed, and no credential-bearing content was copied into the audit.
- Credentials written to artifacts: NO
- amazon_ads_optimizer modified: NO
- daily_data_auto_entry modified: NO
- Git commits created: NO
- Git pushes performed: NO
- Git tags or PRs created: NO
- Files written outside research/xiyou_capability_audit_v0_1: NO

## P. Completion verification

- Fixed ASIN coverage: 3 / 3
- Fixed keyword coverage: 9 / 9
- Raw response files: 21
- Valid JSON files: 21 / 21
- MCP status 200 responses: 21 / 21
- MCP isError=true responses: 0
- Failed business calls: 0
- Provider-reported credits: 32
- Credential scan findings requiring remediation: 0
- Protected-project writes: 0
- Formal product/demand/relevance/market-reconstruction features implemented: 0
