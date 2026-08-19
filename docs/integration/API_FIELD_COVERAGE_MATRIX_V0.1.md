# API Field Coverage Matrix V0.1

Status: TASK-SP-021B XiYou competition contracts live-verified; 157-field Workbook contract unchanged
Workbook contract: Operator Workbook V0.2, fixed 9 sheets / 157 fields
Analysis date: 2026-08-19

## 1. Method

This matrix contains every existing Workbook field exactly once and does not introduce new business fields. `Canonical field` names either an existing Canonical semantic/dimension or states that the Workbook value is derived outside Canonical. API evidence is limited to the official XiYou documentation and the audited Sorftime provider schemas identified in [Data Source API Mapping V0.1](DATA_SOURCE_API_MAPPING_V0.1.md).

Coverage status is restricted to:

| Status | Meaning |
|---|---|
| `AVAILABLE` | A provider directly supplies the business value. |
| `PARTIAL` | Some components are direct, but request context, combination, normalization, or another provider is required. |
| `CALCULATED` | The value is a deterministic system projection from validated evidence. |
| `UNAVAILABLE` | Neither confirmed provider directly supplies the value. |
| `UNKNOWN` | Available documentation/evidence cannot confirm the field. |

`CALCULATED` does not authorize new analysis logic; it describes fields already produced by the existing Intelligence, Evaluation, Scoring, Recommendation, Output, Export, or Workbook contracts.

## 2. Complete 157-field matrix

### 01_市场概览 — 12 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Marketplace | `MarketplaceIdentity.marketplace` | XiYou + Sorftime request scope | XiYou `country`; Sorftime `amz_site` request | PARTIAL | XiYou may echo country; Sorftime audited detail relies on request context. |
| Category Candidate | `ProductFact(category)` candidates | XiYou + Sorftime | XiYou `categoryTree`; Sorftime `category`, `node_id` | PARTIAL | Candidate set requires aggregation across products/providers. |
| Market Size Evidence Metric | Existing metric semantic | XiYou | `abaReport.weeklySearchVolume`, traffic/order evidence | PARTIAL | Direct proxy evidence exists; neither source supplies guaranteed total market size. |
| Metric Value | `ObservationValue.normalized_value` | XiYou + Sorftime | Direct metric value selected from supported observations | AVAILABLE | Value is direct when the selected metric is present. |
| Unit | `UnitDescriptor` | XiYou + Sorftime | Weekly search-volume context, CPC currency, Sorftime units | PARTIAL | Some units/periods are documented; order/traffic methods remain incomplete. |
| Observed Product Count | Not a Canonical source field; snapshot aggregation | System | Count of distinct validated product identities | CALCULATED | Can eliminate `NOT_AVAILABLE` after a bounded candidate set is collected. |
| Data Sources | Provenance providers | System | Distinct `provenance.provider` values | CALCULATED | Provider names come from connector metadata, not business payload. |
| Evidence-backed Trend | Not a direct Canonical field; opportunity projection | System from XiYou/Sorftime trends | Dated trend observations | CALCULATED | Provider time series is direct; human-readable trend text is projected. |
| Risk Alerts | Quality/risk diagnostics | System | Evidence quality, conflict, missing-period diagnostics | CALCULATED | APIs do not issue the system's risk conclusion. |
| Evidence Quality | Evidence evaluation classification | System | Presence, provenance and method diagnostics | CALCULATED | Derived without selecting a provider winner. |
| Analysis Limitations | Diagnostic/limitation codes | System | Missing/method/scope conditions | CALCULATED | Must remain visible even when more API data is connected. |
| Snapshot ID | Opportunity snapshot identity | System | Deterministic snapshot content | CALCULATED | Never supplied by a provider. |

### 02_产品数据库 — 30 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| ASIN | `ProductIdentity.asin` | XiYou + Sorftime | XiYou `entities[].asin`; Sorftime `asin` | AVAILABLE | Direct identifier. |
| Marketplace | `ProductIdentity.marketplace` | XiYou + Sorftime scope | XiYou `country`; Sorftime `amz_site` request | PARTIAL | Preserve response vs request provenance. |
| Display Title | `ProductFact(title)` | XiYou + Sorftime | XiYou `title`; Sorftime `title` | AVAILABLE | Multiple candidates remain unresolved. |
| Title State | Candidate/presence state | System | Title candidate inventory | CALCULATED | Distinguishes one value, conflict, missing and null. |
| Brand | `ProductFact(brand)` | Sorftime | `product_detail.brand` | AVAILABLE | Confirmed direct product field. |
| Category | `ProductFact(category)` | XiYou + Sorftime | XiYou BSR `categoryTree`; Sorftime `category`, `node_id` | AVAILABLE | Representations have different granularity. |
| Product Type | `ProductFact(product_type/type)` | Sorftime | `category`, `attributes` | PARTIAL | No universal typed `product_type`; conservative mapping is required. |
| Price | `Metric(price)` | XiYou + Sorftime | XiYou `price`; Sorftime `price` | AVAILABLE | Current values may conflict and remain separate observations. |
| Price Currency | `Metric(price).unit` | XiYou + Sorftime | XiYou `currency`; Sorftime marketplace/USD schema context | PARTIAL | Sorftime response evidence may depend on schema/request context. |
| Price State | Metric candidate/presence state | System | Price observation inventory | CALCULATED | No provider directly supplies canonical state. |
| Rating | `Metric(rating)` | XiYou + Sorftime | XiYou `stars`; Sorftime `star_rating` | AVAILABLE | Five-star scale; preserve provider differences. |
| Rating State | Metric candidate/conflict state | System | Rating observation inventory | CALCULATED | Never average or resolve in connector. |
| Review Evidence Count | `Metric(review_count)` | XiYou + Sorftime | XiYou `ratings`; Sorftime `review_count` | AVAILABLE | This is listing review count, not number of fetched raw reviews. |
| BSR | `Metric(bsr)` | XiYou | BSR trend `values[].rank` | AVAILABLE | Must include date and category context. |
| BSR Context | BSR category/rank context | XiYou | `categoryTree[].categoryId/name/root`, trend date | AVAILABLE | Prevents cross-category rank comparison. |
| Sales Evidence Value | Separate sales/order metrics | XiYou + Sorftime | XiYou `orders`; Sorftime `monthly_sales_volume`, variation `SalesAmount` | AVAILABLE | Three metrics are not aliases. |
| Sales Evidence Unit | Metric unit/period | XiYou + Sorftime | Sorftime units; XiYou endpoint period contract | PARTIAL | XiYou order unit/method and some exact windows remain unresolved. |
| Sales Evidence Type | `EvidenceType` plus metric semantic | System | Provider endpoint and field classification | CALCULATED | Provider estimate must be labeled, not inferred as observed. |
| Variation Role | Product relationship role | XiYou + Sorftime | XiYou `parentAsin`, `childAsins[]`; Sorftime `parent_asin`, child rows | PARTIAL | Only explicit valid edges establish a role. |
| Parent ASIN | `ProductFact(parent_product_relationship)` | XiYou + Sorftime | XiYou `parentAsin`; Sorftime `parent_asin` | AVAILABLE | Sorftime self-parent semantics remain cautious. |
| Child Count | Relationship aggregation | System | Count `childAsins[]`; Sorftime `ItemTotal`/variation count | CALCULATED | Count only valid explicit children. |
| Attribute Summary | Existing product fact candidates | Sorftime | `attributes`, `description`, package facts | PARTIAL | Summary selects supported facts but cannot resolve unit conflicts. |
| Seller | Existing product fact if later supported | Neither confirmed | No stable direct field confirmed | UNKNOWN | Public/audited schemas are insufficient; do not reuse brand/manufacturer. |
| FBA Status | `ProductFact(fulfillment)` | Sorftime | `product_detail.fulfillment` | AVAILABLE | Map only documented fulfillment values. |
| Data Sources | Provenance providers | System | Distinct provider values | CALCULATED | Display projection. |
| Data State | Evidence presence/quality state | System | Validated fact/metric candidates | CALCULATED | Remains distinct from provider response status. |
| Conflict State | Conflict evaluation state | System | Cross-provider/candidate comparison | CALCULATED | Connectors only add candidates. |
| Time / Period Status | Observation time/period quality | System | Provider dates, request periods and missing-time evidence | CALCULATED | Retrieval time is not observation time. |
| Product Snapshot ID | Product Intelligence snapshot identity | System | Deterministic snapshot content | CALCULATED | Internal identity. |
| Output Row ID | Operator Output row identity | System | Deterministic output row content | CALCULATED | Internal identity. |

### 03_TOP产品分析 — 16 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Product ASIN | `ProductIdentity.asin` | XiYou + Sorftime | Direct ASIN fields | AVAILABLE | Direct identity. |
| Display Title | `ProductFact(title)` | XiYou + Sorftime | `title` | AVAILABLE | Candidate status remains visible. |
| Marketplace | `ProductIdentity.marketplace` | XiYou + Sorftime scope | `country` or `amz_site` | PARTIAL | Request context may be required. |
| Source Rank Value | `Metric(bsr)` or relationship rank | XiYou | BSR `rank`; relationship `totalRank/pageRank` | AVAILABLE | Workbook does not create a ranking. |
| Rank Metric | Metric/relationship semantic | XiYou | Endpoint plus `position`/category context | PARTIAL | Position codes beyond approved mappings remain unknown. |
| Rank Context | Rank category/page context | XiYou | Category tree, page, page rank, total rank | AVAILABLE | Required for interpretation. |
| Channel | `RelationshipChannel` | XiYou | `ranks[].position` | PARTIAL | `or` and approved sponsored codes map safely; other codes remain unknown. |
| Rank Provider | Provenance provider | System | Connector/provider identity | CALCULATED | Provider name is lineage metadata. |
| Rank Status | Rank evidence state | System | Presence, context and semantic validation | CALCULATED | Distinguishes missing rank from rank zero. |
| Rank Period | Observation/rank period | XiYou | `date`, `rankTime`, requested day/week/month | AVAILABLE | Retain source precision and timezone when present. |
| Price | `Metric(price)` | XiYou + Sorftime | Direct price fields | AVAILABLE | Context only; not a ranking input in Workbook. |
| Review Evidence Count | `Metric(review_count)` | XiYou + Sorftime | `ratings`, `review_count` | AVAILABLE | Direct evidence. |
| Rating Evidence | `Metric(rating)` | XiYou + Sorftime | `stars`, `star_rating` | AVAILABLE | Direct candidates. |
| Product Features | Product fact inventory | Sorftime | `attributes`, `description`, package facts | PARTIAL | Presentation summary, not generated product claims. |
| Data Limitations | Limitation codes | System | Missing rank/context/method diagnostics | CALCULATED | Includes `NOT_BEST_PRODUCT`. |
| Rank Observation ID | Canonical observation identity | System | Deterministic canonical content | CALCULATED | Not supplied by API. |

### 04_关键词需求分析 — 23 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Keyword | `KeywordIdentity.normalized_text` | XiYou | `searchTerm` and request keyword | AVAILABLE | Raw and normalized text remain distinct. |
| Marketplace | `KeywordIdentity.marketplace` | XiYou request/response scope | `country` | PARTIAL | Some responses depend on request context. |
| Locale | `KeywordIdentity.locale` | Neither confirmed | No confirmed field | UNAVAILABLE | Country-to-locale guessing is unsafe. |
| Search Volume | `KeywordMetric(search_volume)` | XiYou | `list[].abaReport.weeklySearchVolume` | AVAILABLE | Live-confirmed integer provider estimate with report window; derivation method remains unconfirmed, so Market Analysis aggregation stays blocked. |
| Search Volume State | Keyword metric presence state | System | Search-volume presence/null/missing | CALCULATED | Null does not become zero. |
| Search Volume Unit | Keyword metric unit/period | XiYou | Weekly ABA report context | AVAILABLE | Preserve `searches_per_week` and report dates. |
| CPC | `KeywordMetric(cpc)` | XiYou | `list[].costPerClick.value` | AVAILABLE | Live-confirmed numeric string; preserve min/max suggested bids as evidence. |
| CPC Currency | CPC unit | XiYou marketplace context | Country/marketplace currency mapping | PARTIAL | Currency is not consistently echoed beside CPC. |
| CPC State | Keyword metric presence state | System | CPC presence/null/missing | CALCULATED | Explicit null remains explicit. |
| ABA Rank | `KeywordMetric(aba_search_frequency_rank)` | XiYou | `list[].abaReport.searchFrequencyRank` | AVAILABLE | Live-confirmed integer reported rank with explicit period. |
| ABA Rank State | Keyword metric presence state | System | ABA rank evidence | CALCULATED | State is system-owned. |
| Difficulty | `KeywordMetric(competition_difficulty)` | XiYou | `list[].competitiveDifficulty` | AVAILABLE | Live-confirmed integer value; Provider scale/method remain unconfirmed and unusable as a derived difficulty conclusion. |
| Difficulty State | Keyword metric presence state | System | Difficulty evidence | CALCULATED | State is not the score itself. |
| Related Product Count | Relationship aggregation | System | Count distinct valid forward relationship product identities in one exact keyword/direction scope | CALCULATED | Live-verified through the existing calculation rule; bounded pagination means 10 is the observed page count, not the provider total or market size. |
| Related Product ASINs | Product-keyword relationship endpoints | XiYou | `list[].asin` and keyword-info `topAsins[].asin` | AVAILABLE | Forward live response was 10/1005 and is explicitly `PARTIAL_PAGE`; completeness depends on pagination and period. |
| Channel | `RelationshipChannel` | XiYou | `list[].ranks[].position` | PARTIAL | Live observed `or`, `sb`, `sbv`, `sor`, and `sp`; only audited mappings execute and other codes stay unknown. |
| Query Direction | `QueryDirection` | System | Endpoint semantic | CALCULATED | Forward and reverse endpoints remain separate. |
| Query Status | `QueryExecutionRecord.result_status` | System | HTTP/result envelope plus list/total | CALCULATED | Empty, failed and populated outcomes differ. |
| Provider | Provenance provider | System | Connector identity | CALCULATED | Not a business payload field. |
| Estimate Method Status | Metric method-status evidence | XiYou | No sufficiently documented derivation method | UNKNOWN | Period is known for some metrics; estimation method is not. |
| Period Status | Period quality state | System | ABA dates, rank time, requested day/week/month | CALCULATED | Evaluates completeness/precision, not trend direction. |
| Limitations | Limitation codes | System | Method, direction, period and completeness diagnostics | CALCULATED | No demand guarantee. |
| Demand Snapshot ID | Demand snapshot identity | System | Deterministic snapshot content | CALCULATED | Internal identity. |

### 05_市场竞争证据 — 13 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Product ASIN | `ProductIdentity.asin` | XiYou | Relationship result/request ASIN | AVAILABLE | Direct endpoint identity. |
| Keyword | `KeywordIdentity` | XiYou | `searchTerm` | AVAILABLE | Direct relationship endpoint value. |
| Relationship Direction | `ProductKeywordRelationship.direction` | System | Forward/reverse endpoint semantic | CALCULATED | Never infer bidirectional equality. |
| Observed Relationship | Product-keyword relationship observation | System | Valid populated rank/traffic/candidate evidence | CALCULATED | Represents observation, not true competition. |
| Observed Relationship Type | Relationship type | System | Rank/traffic/candidate source field | CALCULATED | Provider codes are normalized conservatively. |
| Channel | `RelationshipChannel` | XiYou | `ranks[].position` | PARTIAL | Unknown codes remain `UNKNOWN`. |
| Provider | Provenance provider | System | Connector identity | CALCULATED | Lineage metadata. |
| Evidence Count | Relationship evidence aggregation | System | Count validated observations | CALCULATED | Count is not competition strength. |
| Evidence Classification | Evidence semantic class | System | Relationship kind/channel/presence | CALCULATED | No competitor ranking. |
| Variation Evidence Count | Variation relationship aggregation | System | XiYou child list; Sorftime variation rows | CALCULATED | Specification remains system-owned, but execution stays blocked because source rows, unique edges, and unique variants have no governed counting grain. |
| Query Status | Query execution status | System | Result envelope/list/total | CALCULATED | Explicit empty remains query-scoped. |
| Limitations | Limitation codes | System | Direction, method, rank and completeness diagnostics | CALCULATED | Prevents market-strength inference. |
| Competition Output Row ID | Operator Output identity | System | Deterministic row content | CALCULATED | Internal identity. |

### 06_产品结构分析 — 13 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Marketplace | Product scope marketplace | XiYou + Sorftime scope | `country`, `amz_site` | PARTIAL | Request context may be required. |
| Product Type | `ProductFact(product_type/type)` | Sorftime | `category`, structured attributes | PARTIAL | Requires conservative grouping; no clustering. |
| Product Count | Product identity aggregation | System | Distinct validated identities | CALCULATED | Depends on bounded candidate collection. |
| Observed Share | Exact-group observed share | System | Group count divided by observed set count | CALCULATED | Not market share. |
| Sales Evidence Summary | Sales metric projection | System | XiYou orders and Sorftime sales estimates | CALCULATED | Metrics remain separately labeled. |
| Minimum Comparable Price | Comparable price aggregation | System | Valid price observations | CALCULATED | System-owned specification remains; execution is blocked until governed `COMPARABLE` membership exists. |
| Maximum Comparable Price | Comparable price aggregation | System | Valid price observations | CALCULATED | Same governed-membership execution blocker as minimum comparable price. |
| Currency | Price unit | XiYou + Sorftime | XiYou `currency`; Sorftime schema/context | PARTIAL | Mixed currencies cannot be silently combined. |
| Observed Feature Inventory | Product fact inventory | Sorftime | `attributes`, `description`, package facts | PARTIAL | Exact observed features only; no feature generation. |
| Data State | Evidence state | System | Fact/metric presence and quality | CALCULATED | Derived quality view. |
| Provider Count | Provenance aggregation | System | Distinct providers | CALCULATED | Not a confidence score by itself. |
| Limitations | Limitation codes | System | Scope/comparability/missing diagnostics | CALCULATED | Includes no-clustering/no-market-share boundary. |
| Member Product IDs | Exact group membership | System | Valid product identities plus exact type grouping | CALCULATED | API ASINs are direct; group membership is system-derived. |

### 07_机会分析 — 15 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Product | Product identity/set | XiYou + Sorftime plus system scope | Direct ASINs and validated candidate set | PARTIAL | Direct identities may be aggregated into one opportunity row. |
| Demand Signal | Opportunity demand evidence projection | System | Keyword metrics/query evidence | CALCULATED | No demand guarantee. |
| Competition Signal | Opportunity competition evidence projection | System | Relationship evidence | CALCULATED | No competition-strength invention. |
| Product Signal | Opportunity product evidence projection | System | Product facts/metrics/reviews | CALCULATED | Existing rules only. |
| Signal Classification | Opportunity signal class | System | Existing opportunity rules | CALCULATED | Not a provider field. |
| Missing Evidence | Missing-evidence inventory | System | Required-vs-present evidence comparison | CALCULATED | Makes residual `NOT_AVAILABLE` explicit. |
| Risk Evidence | Risk evidence inventory | System | Conflict, quality, method and period diagnostics | CALCULATED | Does not predict failure. |
| Score Factor | Opportunity scoring factor identity | System | Existing scoring rules | CALCULATED | No connector calculation. |
| Rule Process Score | Opportunity score result | System | Existing scoring framework | CALCULATED | Not a success probability. |
| Score Status | Scoring process status | System | Rule/policy/evidence state | CALCULATED | Distinguishes calculated, excluded and blocked. |
| Score Reference | Score calculation identity | System | Deterministic calculation record | CALCULATED | Internal reference. |
| Score Interpretation | Existing score explanation | System | Existing scoring explanation | CALCULATED | Does not add a recommendation. |
| Explanation Reference | Explanation record identity | System | Deterministic explanation record | CALCULATED | Internal reference. |
| Limitations | Limitation codes | System | Opportunity/scoring boundaries | CALCULATED | No guarantee or forecast. |
| Opportunity Output Row ID | Operator Output identity | System | Deterministic row content | CALCULATED | Internal identity. |

### 08_行动建议 — 15 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Product | Product identity/set | XiYou + Sorftime plus system scope | Direct ASINs and validated recommendation scope | PARTIAL | Provider supplies identities, not recommendation scope. |
| Recommendation Type | Recommendation Framework output | System | Existing recommendation rule result | CALCULATED | APIs cannot supply the system recommendation. |
| Recommendation Display Label | Workbook presentation label | System | Mapping from existing recommendation type | CALCULATED | Display-only. |
| Reason | Recommendation explanation | System | Existing rule explanation | CALCULATED | No generative provider report substitution. |
| Rule Reference | Recommendation rule identity | System | Existing rule record | CALCULATED | Internal reference. |
| Policy Status | Evidence policy status | System | Existing policy evaluation | CALCULATED | Provider response code is not policy status. |
| Conflict Status | Conflict-resolution status | System | Existing conflict records | CALCULATED | Connectors do not resolve. |
| Missing Requirements | Recommendation missing inputs | System | Required-vs-present evidence | CALCULATED | Guides further research. |
| Evidence References | Canonical/evaluation references | System | Existing evidence IDs | CALCULATED | Internal references. |
| Evidence Count | Evidence reference aggregation | System | Count existing references | CALCULATED | Count is not recommendation strength. |
| Limitations | Limitation codes | System | Recommendation boundaries | CALCULATED | No purchase advice. |
| Manual Review Status | Operator workflow state | Operator only | No provider field | UNAVAILABLE | Intentionally human-owned and editable. |
| Recommendation Record ID | Recommendation record identity | System | Deterministic recommendation content | CALCULATED | Internal identity. |
| Source Snapshot ID | Source snapshot identity | System | Existing source snapshot | CALCULATED | Internal identity. |
| Operator Output Row ID | Operator Output identity | System | Deterministic output row | CALCULATED | Internal identity. |

### 09_数据审计 — 20 fields

| Workbook field | Canonical field | Data source | API field | Coverage status | Notes |
|---|---|---|---|---|---|
| Audit Record ID | Audit presentation identity | System | Deterministic audit row content | CALCULATED | Internal identity. |
| Source Sheet | Workbook presentation metadata | System | Workbook sheet mapping | CALCULATED | Not provider data. |
| Display Row Key | Workbook presentation identity | System | Display row content/scope | CALCULATED | Not provider data. |
| Excel Row | XLSX location metadata | System | Rendered row ordinal | CALCULATED | Not provider data. |
| Display Field | Workbook presentation metadata | System | Current row-level lineage marker | CALCULATED | No unsupported cell-level precision is claimed. |
| Excel Cell | XLSX location metadata | System | Rendered row/cell locator | CALCULATED | Presentation metadata. |
| Export Row ID | Operator Export identity | System | Deterministic export row | CALCULATED | Validated against current Output. |
| Output Row ID | Operator Output identity | System | Deterministic output row | CALCULATED | Internal identity. |
| Evidence ID | Canonical evidence identity | System | Deterministic canonical record | CALCULATED | Based on validated semantic content. |
| Provider | Provenance provider | System connector metadata | Configured provider identity | CALCULATED | Never taken from secrets or free text. |
| Source Tool | Provenance source tool | System connector metadata | Endpoint/tool identifier | CALCULATED | Records which capability produced evidence. |
| Source Field | Provenance source field | System mapping metadata | Exact response path | CALCULATED | Exact field locator is mapping-owned. |
| Raw Evidence Reference | Raw evidence identity | System | Immutable payload content hash/reference | CALCULATED | Raw payload itself is not placed in Workbook. |
| Collection Run ID | Collection-run identity | System | Deterministic collection envelope | CALCULATED | No credential content. |
| Transformation Run ID | Transformation-run identity | System | Deterministic transformation record | CALCULATED | Mapping execution reference. |
| Mapping Version | Transformation mapping version | System | Approved adapter mapping version | CALCULATED | Provider schema version may remain unknown. |
| Canonical Reference ID | Canonical observation/query identity | System | Deterministic canonical content | CALCULATED | Replayed against bundles. |
| Lineage ID | Serialized lineage identity | System | Deterministic lineage content | CALCULATED | Links Export, Output and Canonical. |
| Source Snapshot ID | Intelligence/source snapshot identity | System | Deterministic upstream snapshot | CALCULATED | Internal identity. |
| Source Bundle Fingerprint | Canonical bundle fingerprint | System | SHA-256 over canonical bundle content | CALCULATED | Integrity check, not provider-supplied hash. |

## 3. Coverage statistics

| Coverage status | Count | Share |
|---|---:|---:|
| AVAILABLE | 30 | 19.11% |
| PARTIAL | 24 | 15.29% |
| CALCULATED | 99 | 63.06% |
| UNAVAILABLE | 2 | 1.27% |
| UNKNOWN | 2 | 1.27% |
| **Total** | **157** | **100.0%** |

Interpretation:

- 30 fields have direct confirmed provider values.
- 24 fields can be materially improved by combining provider fields with explicit request scope or conservative normalization.
- 99 fields are expected system outputs and should not be sought as provider fields.
- `Locale` and `Manual Review Status` are intentionally unavailable from the two providers.
- `Seller` and `Estimate Method Status` remain unknown until an official, testable schema confirms them.

## 4. Connector implications

The matrix supports the following SP-018B P0 slice:

1. XiYou product info, orders, variations, BSR, keyword info, forward keyword analysis, and reverse ASIN research.
2. Sorftime product detail and variations, with reviews as a separately gated P1 capability.
3. Exact response-field provenance, request-scope provenance, pagination/completeness, explicit-empty handling, and immutable raw evidence.
4. No direct population of calculated Workbook fields by connectors.
5. No new field, score, recommendation, provider preference, unit conversion, or conflict resolution.

## 5. Matrix acceptance checks

- Workbook field rows: 157
- Sheet groups: 9
- Allowed coverage vocabulary only: yes
- Direct API and system-calculated fields separated: yes
- Future `NOT_AVAILABLE` reduction paths identified: yes
- SP-018B P0 scope identified: yes
