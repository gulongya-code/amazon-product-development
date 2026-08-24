# Market Report Reference Template Gap Audit V0.1

Status: `AUDIT COMPLETE — IMPLEMENTATION NOT STARTED`

Task: `TASK-SP-039`

Required baseline: `c45292919ec12221518e3323450d35a10e0e8fcf`

Audit date: 2026-08-24

## 0. Scope, method, and decision rules

This is a documentation-only gap audit. It does not change `market-report-v0.1`, any Intelligence Model, formula, renderer, fixture, test, Provider operation, or production behavior.

Authoritative product sources:

- `docs/requirements/MARKET_REPORT_REFERENCE_TEMPLATE_REQUIREMENTS_V0.1.md`
- `docs/requirements/亚马逊智能选品系统_产品需求与核心架构说明_V0.2.md`

Current-state evidence was inspected in:

- `src/amazon_product_intelligence/market_report/models/`
- `src/amazon_product_intelligence/market_report/builder/`
- `src/amazon_product_intelligence/market_report/adapters/`
- `src/amazon_product_intelligence/market_report/delivery/`
- `src/amazon_product_intelligence/operator_workflow/`
- `src/amazon_product_intelligence/production_pipeline/orchestrator.py`
- `src/amazon_product_intelligence/category_product_map/`, `market_analysis/`, `competition_analysis/`, `product_intelligence/`, and `opportunity_intelligence/`
- `docs/examples/market_report.json`, the Market Report / Operator fixture tests, and the current integration and operation documentation

The primary status of every audited requirement is exactly one of:

| Status | Audit meaning |
|---|---|
| `IMPLEMENTED` | The governed capability is represented in the current report or delivery contract and has concrete repository evidence. |
| `PARTIAL` | A governed subset exists, but one or more required semantics, fields, grains, or delivery views are absent. |
| `MISSING` | The authoritative requirement is a product capability, but no governed Market Report contract or delivery path represents it. |
| `EXTERNAL_INTEGRATION` | The capability belongs to the external Keyword Intelligence integration boundary and must not be rebuilt here. |
| `NOT_PRODUCT_CONTRACT` | The reference sheet is an Excel implementation/helper concern, not a required product contract. |
| `DEFERRED_ENHANCEMENT` | The authoritative requirements explicitly place the capability after the first complete report contract. |

Priority is one of `P0`, `P1`, `P1-EXT`, `P2`, or `N/A`. A report-level requirement is not marked implemented merely because an upstream Canonical or Provider field may exist; it must have a governed path into the validated Market Report and its delivery.

## A. Executive conclusion

The reference template is **not fully covered** by the current `market-report-v0.1`. The current implementation is a strong, deterministic evidence envelope and operator triage report, but it is not yet the full market-research decision-support contract described by the reference requirements.

The audit contains **66 atomic requirements**:

| Status | Count |
|---|---:|
| `IMPLEMENTED` | 9 |
| `PARTIAL` | 17 |
| `MISSING` | 27 |
| `EXTERNAL_INTEGRATION` | 5 |
| `NOT_PRODUCT_CONTRACT` | 3 |
| `DEFERRED_ENHANCEMENT` | 5 |
| **Total** | **66** |

| Priority | Count |
|---|---:|
| `P0` | 44 |
| `P1` | 9 |
| `P1-EXT` | 5 |
| `P2` | 5 |
| `N/A` | 3 |
| **Total** | **66** |

The decisive findings are:

1. `market-report-v0.1` correctly validates and serializes category, sample, data window, Buyer Need summaries, attribute count/share distributions, limited competition metrics, Opportunity Score evidence, provenance, and limitations.
2. Operator Workflow V0.1 adds conservative action triage, known/unknown evidence, next checks, runtime health, recovery lineage, and safe credit semantics without inventing intelligence.
3. The missing P0 center is a governed market-size and competitor-detail layer: monthly sales/revenue, True Competitor Set grain, concentration by product/brand/seller, configurable business distributions, auditable competitor rows, Product Direction, and Competitor Shortlist.
4. Keyword capability is a future versioned input from the separate Keyword Intelligence project. All five keyword requirements remain `EXTERNAL_INTEGRATION / P1-EXT`; this repository must not create a second keyword engine.
5. The stable v0.1 schema should not be expanded in place. The smallest safe route is a staged, versioned `market-report-v0.2` contract while retaining v0.1 compatibility.

## B. Full coverage matrix

`Current evidence` names the concrete repository artifact supporting every `IMPLEMENTED` or `PARTIAL` result. For `MISSING`, the evidence states the inspected boundary in which the governed capability is absent.

| ID | Requirement | Template source | Priority | Status | Current evidence | Gap | Owning layer | Next task |
|---|---|---|---|---|---|---|---|---|
| MR-001 | Executive action, opportunity, risk, and next-check brief | 综合说明 / 3.1 | P0 | PARTIAL | `operator_workflow/builder_v0_1.py`; `delivery/markdown_renderer.py`; XLSX `Operator Summary` | Operator triage exists, but it cannot summarize absent market-size, Product Direction, shortlist, or seller evidence. | Market Report composition | SP-039A executive contract design |
| MR-002 | Executive market capacity and monthly revenue | 综合说明 / 3.1 | P0 | MISSING | `MarketReportSnapshot` has no market-size or revenue section; `MarketReportBuildRequest` does not accept one. | No governed capacity/revenue conclusion or method. | Market intelligence + report contract | SP-039B market-size slice |
| MR-003 | Executive price band and average order value | 综合说明 / 3.1 | P0 | PARTIAL | `CompetitionReportSection.price_distribution`; Markdown/XLSX Competition Analysis | Only min/max/mean/median price is exposed; no configured price band, cohort share, or AOV semantic. | Distribution contract | SP-039C distribution slice |
| MR-004 | Executive maturity, competition, promotion difficulty, and Review Barrier | 综合说明 / 3.1 | P0 | PARTIAL | `competition_level`, concentration, rating/review summaries; Opportunity risks | Generic competition level and sample summaries exist; maturity and explicit Review/Rating barriers do not. | Competition report | SP-039B competition structure |
| MR-005 | Executive dominant product forms and sales share | 综合说明 / 3.1 | P0 | PARTIAL | `ProductAttributeDistributionReport` count/share fields | Attribute listing shares exist; sales and revenue shares by form do not. | Attribute aggregation | SP-039C attribute economics |
| MR-006 | Executive buyer pain points | 综合说明 / 3.1 and §4 | P0 | PARTIAL | `BuyerNeedReportSection`; Operator `top_buyer_need_themes` | Need labels and cohort recurrence are shown, but positive/pain typing and review/ASIN impact are not report fields. | Buyer Need report adapter | SP-039D Buyer Need links |
| MR-007 | Executive FBA and transport characteristics | 综合说明 / 3.1 | P0 | MISSING | No fulfillment, fee, size-tier, package, or transport section exists in `MarketReportSnapshot` or delivery. | Upstream fields are not governed into the report. | Product detail + report contract | SP-039C competitor detail |
| MR-008 | Executive seller geography structure | 综合说明 / §12 | P1 | MISSING | No seller identity/location section exists; `COMPETITION_ANALYSIS_V0.1.md` records seller count as blocked. | Seller location cannot be inferred from brand. | External/provider data + market structure | SP-039E seller geography |
| MR-009 | Executive evidence, confidence, and limitations | 综合说明 / §13 | P0 | IMPLEMENTED | `MarketReportSnapshot.provenance/limitations`; section availability; Operator known/unknown and evidence readiness | No P0 gap at the current v0.1 grain. | Market Report + delivery | Preserve and extend in SP-039A |
| MR-010 | Marketplace, category, and explicit scope | 类目 / 3.2 | P0 | IMPLEMENTED | `CategoryReportSection`; builder category inputs; Market Overview in both renderers | Covered at one category-name/scope-string grain. | Market Report | Preserve |
| MR-011 | Category hierarchy and entry keyword or Demand Cluster | 类目 / 3.2 | P0 | PARTIAL | `CategoryReportSection.category_name/scope`; upstream Product facts and Buyer Need clusters | Free-text scope exists; typed large/subcategory hierarchy and entry-demand identity do not. | Scope contract | SP-039A scope design |
| MR-012 | Data window with availability and limitations | 类目 / 3.2 | P0 | IMPLEMENTED | `DataWindowReportSection`; Operator missing-window next action | Period/start/end and explicit availability are governed. | Market Report | Preserve |
| MR-013 | Sample size, unique ASINs, Provider total, coverage, and limitations | 类目 / 3.2 | P0 | IMPLEMENTED | `SampleReportSection`; pipeline passes requested/resolved cohort; Market Overview delivery | Covered for the bounded report sample. | Market Report | Preserve |
| MR-014 | Parent/Child aggregation grain and duplicate-control declaration | 类目 / 3.2 and 3.4 | P0 | MISSING | `MarketReportBuildRequest` passes counts only; `MarketReportSnapshot` has no product-grain field. | Upstream pipeline uses child-ASIN scope, but report consumers cannot audit the grain or family aggregation rule. | Scope + competitor-set contract | SP-039A grain decision |
| MR-015 | Monthly sales | 市场调研 / 3.3 | P0 | MISSING | No monthly-sales metric in report schema, builder, or delivery; upstream evidence is not a report contract. | Missing value, unit, period, cohort, estimate type, and completeness semantics. | Market intelligence | SP-039B market-size slice |
| MR-016 | Monthly revenue | 市场调研 / 3.3 | P0 | MISSING | No monthly-revenue metric in report schema, builder, or delivery. | Missing currency, period, cohort, estimate type, and completeness semantics. | Market intelligence | SP-039B market-size slice |
| MR-017 | Sales/revenue trend with governed window | 市场调研 / 3.3 | P1 | MISSING | Data window exists, but `MarketReportSnapshot` has no trend series or conclusion contract; Market Analysis records trend formula as blocked. | No windowed series, direction rule, or trend evidence link. | Trend intelligence | SP-039E trend slice |
| MR-018 | Seasonality, new-product contribution, and market maturity | 市场调研 / 3.3 | P1 | MISSING | No corresponding report sections or adapter inputs exist. | Requires time series, listing age/product cohort, and governed maturity semantics. | Trend + competition intelligence | SP-039E trend/maturity |
| MR-019 | Real three-month forecast with intervals and model metadata | 市场调研 / 3.3 | P2 | DEFERRED_ENHANCEMENT | Requirements explicitly allow `PARTIAL`/`UNAVAILABLE` until sufficient data/model exist. | No forecasting contract is authorized now. | Future forecast model | SP-039H only after data gate |
| MR-020 | True Competitor Set | 市场调研 / 3.4 | P0 | MISSING | Competition docs distinguish observed scope from governed Comparable/True Competitor membership; report has only aggregate sample metrics. | No membership records, reason codes, grain, or completeness contract. | Competition intelligence | SP-039B competitor-set slice |
| MR-021 | Product, brand, and seller concentration with explicit grain | 市场调研 / 3.4 | P0 | PARTIAL | `competition_concentration` accepts an evidence-linked value; example has top-5 ASIN/brand share | The metric is untyped JSON; no required top-10 grain, seller concentration, denominator, or parent/child rule. | Competition report | SP-039B concentration contract |
| MR-022 | Head products, brands, and sellers | 市场调研 / 3.4 | P0 | MISSING | No ranked/member rows exist in `CompetitionReportSection` or delivery. | Aggregate metrics cannot identify the head entities or their evidence. | Competition report | SP-039C competitor detail |
| MR-023 | Core competitor count and sales/revenue shares | 市场调研 / 3.4 | P0 | PARTIAL | `asin_count` and `brand_count` expose observed-scope counts | Counts are not a True Competitor count; sales/revenue shares are absent. | Competition intelligence | SP-039B competitor-set slice |
| MR-024 | New/old structure, Review/Rating barriers, and entry difficulty | 市场调研 / 3.4 | P0 | PARTIAL | Rating/review numeric summaries and `competition_level` are exposed | No listing-age cohort, barrier thresholds/method, or decomposed entry-difficulty evidence. | Competition report | SP-039B barrier contract |
| MR-025 | Surface-search competition versus true competition explanation | 市场调研 / 3.4 | P0 | MISSING | Repository design docs state the distinction, but no Market Report field delivers it. | Product contract cannot rely on engineering documentation alone. | Competition report | SP-039B competitor-set diagnostics |
| MR-026 | Required product-attribute dimensions | 不同维度分析 / 3.5 | P0 | PARTIAL | Category Product Map adapter emits governed dimensions and values; Product Intelligence supports typed facts | Coverage is input-dependent; report does not require or enumerate the full reference dimension set. | Product Intelligence + report adapter | SP-039C dimension registry |
| MR-027 | Attribute listing count/share, unknown coverage, evidence, and limitations | 不同维度分析 / 3.5 | P0 | IMPLEMENTED | `ProductAttributeDistributionReport` and `ProductAttributeValueReport` | Count/share is over known values and unknown/coverage is explicit. | Market Report | Preserve |
| MR-028 | Attribute sales/revenue shares and average/median price | 不同维度分析 / 3.5 | P0 | MISSING | Attribute value rows contain only ASIN count/share and evidence IDs. | No safe join to compatible sales/revenue/price observations by segment. | Attribute aggregation | SP-039C attribute economics |
| MR-029 | Price, review, and rating distributions | 不同维度分析 / 3.6 | P0 | PARTIAL | Competition adapter exposes min/max/mean/median distributions with status/evidence | Required configurable buckets with product count/share and sales/share are absent. | Distribution contract | SP-039C bucket distributions |
| MR-030 | Listing-age, FBA-fee, and review-rate distributions | 不同维度分析 / 3.6 | P0 | MISSING | No report fields, builder inputs, or renderer sections exist for these distributions. | Upstream evidence availability varies and no governed bucket contract exists. | Product/market analysis | SP-039C bucket distributions |
| MR-031 | Seller-country/geography distribution | 不同维度分析 / §12 | P1 | MISSING | No seller location identity or report distribution exists. | Requires sourced location and parse status, never brand inference. | Provider integration + market structure | SP-039E seller geography |
| MR-032 | Product-type/material/mounting/structure/pack distributions | 不同维度分析 / 3.6 | P0 | PARTIAL | Generic `product_attributes[]` can carry these dimensions with count/share/unknown | No required dimension registry, sales share, or configured cross-report presentation. | Attribute aggregation | SP-039C dimension registry |
| MR-033 | Versioned bucket definitions and product/sales share per bucket | 不同维度分析 / 3.6 | P0 | MISSING | Current numeric distributions are summary statistics; no bucket policy ID/version is serialized. | Thresholds and denominator policy are not governed. | Distribution contract | SP-039C bucket policy |
| MR-034 | Auditable competitor identity/catalog rows | 竞品数据 / 3.7A | P0 | MISSING | Product Intelligence has upstream facts, but `MarketReportSnapshot` has no competitor row collection and delivery has no detail sheet/table. | ASIN, parent, title, brand, category path, URL, and image cannot be audited together in the report. | Competitor detail contract | SP-039C competitor detail |
| MR-035 | Competitor product-intelligence detail | 竞品数据 / 3.7B | P0 | MISSING | Upstream Product Intelligence and attribute extraction exist; report only aggregates attribute distributions. | Per-competitor material, structure, mounting, size, weight, and package facts are absent. | Competitor detail contract | SP-039C competitor detail |
| MR-036 | Competitor market/review metrics detail | 竞品数据 / 3.7C-D | P0 | MISSING | Aggregate competition summaries exist; no per-ASIN metric rows exist in report/delivery. | BSR, change, sales, revenue, variants, price, ratings, new reviews, Q&A, and quality status lack row-level report linkage. | Competitor detail contract | SP-039C competitor detail |
| MR-037 | Competitor fulfillment/economics/seller/marketing detail | 竞品数据 / 3.7E-F | P0 | MISSING | No competitor detail collection exists in report schema. | Fulfillment, fee, shipping, seller, badges, A+/video/ads/deals, and economics status are not report fields. | Competitor detail contract | SP-039C competitor detail |
| MR-038 | Top competitor operational view | top100—日单量分析 / 3.8 | P1 | MISSING | Existing workbook `TOP产品分析` contracts are outside current Market Report delivery; its XLSX has only five report sheets. | No governed Top rows or derived daily-sales status in this delivery. | Operator delivery + competitor detail | SP-039E top-competitor view |
| MR-039 | Buyer Need label, recurrence/share basis, confidence, evidence, and provenance | 综合说明 / §4 | P0 | IMPLEMENTED | `BuyerNeedReportItem`; V0.3 adapter preserves taxonomy/ruleset, evidence count/IDs, share basis, confidence, availability, and limitations | Covered at semantic-cluster summary grain. | Buyer Need report adapter | Preserve |
| MR-040 | Need type, positive need, pain point, and impacted ASIN/review evidence | 综合说明 / §4 | P0 | PARTIAL | V0.3 intent rules and evidence IDs are preserved; Operator displays top themes | Report item has no typed positive/pain role or structured affected ASIN/review links. | Buyer Need report contract | SP-039D Buyer Need links |
| MR-041 | Buyer Need to competitor satisfaction, attribute, gap, and Product Direction links | 综合说明 / §4 | P0 | MISSING | `BuyerNeedReportItem` has no typed cross-link fields; Opportunity evidence IDs are not a replacement. | Cross-analysis traceability and competitor-coverage semantics are absent. | Buyer Need integration | SP-039D Buyer Need links |
| MR-042 | Evidence-backed Product Direction records | 产品初步筛选范围 / §5 | P0 | MISSING | Operator next actions are evidence-collection checks, not product configurations; report schema has no direction collection. | Missing typed configuration, need/evidence/competitor links, entry logic, validation items, risk, confidence, and limitations. | Decision-support contract | SP-039D Product Direction |
| MR-043 | Sample validation plan | 样品类型 / §6 | P1 | MISSING | No report or Operator Workflow sample-plan contract exists. | Must remain a validation recommendation, not a purchase instruction. | Decision-support contract | SP-039E Sample Plan |
| MR-044 | Governed competitor shortlist with selection reasons | 竞品收集 / §7 | P0 | MISSING | No shortlist collection exists; Opportunity and Operator action types do not select competitors. | Requires True Competitor membership, row metrics, reason codes, direction links, and URLs. | Decision-support contract | SP-039D Shortlist |
| MR-045 | Core Unit Economics | 价格核算 / §8 | P1 | MISSING | Opportunity economic evidence only exposes a score dimension; no cost-input or profit bridge exists in Market Report. | Missing fee/cost inputs, status per input, gross/contribution profit and margin formulas. | Unit Economics contract | SP-039E Unit Economics |
| MR-046 | Break-even CPC/ACoS and fuller ad economics | 价格核算 / §8 | P2 | DEFERRED_ENHANCEMENT | Requirements identify it as a later enhancement; no current report contract exists. | Depends on governed economics and external keyword/ad inputs. | Future economics model | SP-039H after SP-039E |
| MR-047 | Structured IP risk screening | 风险 / 9.1 | P1 | MISSING | Current report only carries free-text risks/limitations; no risk level/type/trigger/evidence/check/disclaimer record exists. | Must not make legal conclusions. | Risk contract | SP-039E risk screening |
| MR-048 | Product claim and safety evidence classification | 风险 / 9.2 | P1 | MISSING | Canonical evidence types exist upstream, but Market Report has no claim record distinguishing seller claim, observation, review, test, and inference. | Title/bullet claims cannot be treated as verified properties. | Risk + evidence contract | SP-039E claim safety |
| MR-049 | Versioned external Keyword Intelligence input validation and provenance | 关键词1—数据源 / 10.1-10.4 | P1-EXT | EXTERNAL_INTEGRATION | Requirement reserves semantics only; current Market Report has no external snapshot adapter. | Jointly freeze source project/version/window/schema and fail-safe validation. | External Keyword Intelligence adapter | SP-039F joint contract |
| MR-050 | Keyword demand display in JSON/XLSX/Markdown | 关键词1—数据源 / 10.5 | P1-EXT | EXTERNAL_INTEGRATION | Current delivery has no keyword section; internal Provider keyword observations are not the external project contract. | Display must degrade safely when external data is unavailable. | External integration + delivery | SP-039F display adapter |
| MR-051 | Keyword to Buyer Need and ASIN/product-supply mappings | 关键词1—数据源 / 10.3 | P1-EXT | EXTERNAL_INTEGRATION | No versioned external mapping input or report cross-link contract exists. | Do not infer equivalence from text or recreate external clustering. | Cross-project integration | SP-039F mapping contract |
| MR-052 | Demand × Supply Gap | §11 | P1-EXT | EXTERNAL_INTEGRATION | Opportunity Score may contain an internal supply-gap dimension, but it does not implement the required Keyword × Buyer Need × True Competitor trace. | Requires all three governed inputs and evidence/confidence/limitations. | Cross-project integration | SP-039F gap contract |
| MR-053 | Keyword opportunity ranking not based on volume alone | 关键词1—数据源 / 10.5 | P1-EXT | EXTERNAL_INTEGRATION | No external keyword opportunity collection is accepted or rendered. | Ranking policy belongs to Keyword Intelligence and must arrive versioned. | External Keyword Intelligence | SP-039F ranking ingestion |
| MR-054 | Full evidence-state semantics, including observed/estimate/resolved/derived/empty/missing/zero | 原始数据源 / §13.1 | P0 | PARTIAL | Canonical and cleaning layers distinguish detailed states; report uses `AVAILABLE/PARTIAL/UNAVAILABLE` plus null-safe values | Report projection loses some evidence-type and query-empty distinctions. | Evidence projection contract | SP-039A evidence-state design |
| MR-055 | Metric scope, grain, period, marketplace, coverage, estimate type, and duplicate risk | 原始数据源 / §13.2 | P0 | PARTIAL | Category, sample, window, provenance, units, and limitations exist | Required metric-specific denominator/grain/method metadata is not uniformly attached. | Metric contract | SP-039A metric context |
| MR-056 | Conclusion-to-metric-to-provider traceability | 综合说明 / §13.3 | P0 | PARTIAL | Report sections carry provenance reference IDs and evidence IDs; Operator claims retain both | Some Operator narrative is traceable, but absent conclusions and untyped aggregate values prevent complete conclusion lineage. | Report composition | SP-039A conclusion links |
| MR-057 | Versioned, strict, deterministic Market Report JSON | Delivery / §14 | P0 | IMPLEMENTED | `MarketReportSnapshot`, strict payload validation, deterministic IDs, `MarketReportBuilderV0_1.write_json`, schema regression tests | v0.1 core contract is stable. | Market Report | Preserve v0.1 |
| MR-058 | XLSX and Markdown from the same validated report | Delivery / §14 | P0 | IMPLEMENTED | `OperatorReportDelivery.load_report()` validates once and passes the same snapshot/workflow to both renderers | Covered. | Operator delivery | Preserve |
| MR-059 | Core conclusion consistency across XLSX and Markdown | Delivery / §14 | P0 | IMPLEMENTED | Both renderers use the same `OperatorWorkflowSnapshotV0_1`; delivery and workflow tests assert aligned action/health semantics | Covered for fields represented by v0.1. | Operator delivery | Extend with parity tests |
| MR-060 | Evidence/raw-data appendix | 原始数据源 / §13 and §15 | P0 | PARTIAL | Markdown Evidence and Provenance table; report-level provenance references and limitations | This is an audit lineage appendix, not a complete sanitized row-level raw/canonical evidence appendix. | Evidence delivery | SP-039G appendix view |
| MR-061 | Excel automation configuration sheet | 自动化配置 / §15 | N/A | NOT_PRODUCT_CONTRACT | Requirements explicitly classify it as Excel internal configuration. | No product schema should copy template cell controls. | Excel implementation | No task |
| MR-062 | Analysis-model comparison sheet | 分析模型对比 / §15 | N/A | NOT_PRODUCT_CONTRACT | Requirements classify it as optional delivery/internal validation. | Validation evidence may remain in tests/docs rather than product output. | Internal validation | No task unless separately requested |
| MR-063 | Excel automation helper sheet | 自动化辅助 / §15 | N/A | NOT_PRODUCT_CONTRACT | Requirements explicitly classify it as an internal derived layer. | Do not expose helper formulas as business truth. | Excel implementation | No task |
| MR-064 | External IP data search | P2 list | P2 | DEFERRED_ENHANCEMENT | Requirements defer fuller IP external retrieval; only conservative screening is P1. | Requires approved external source and legal boundary. | Future external integration | SP-039H |
| MR-065 | Supply-chain and sample-test feedback loop | P2 list | P2 | DEFERRED_ENHANCEMENT | Requirements explicitly defer this closed loop. | No governed supply/test result contract exists. | Future operations integration | SP-039H |
| MR-066 | Historical report/version comparison | P2 list | P2 | DEFERRED_ENHANCEMENT | Current deterministic report IDs support identity, but no comparison contract/view exists. | Requires compatible version/window comparison rules. | Future report analytics | SP-039H |

## C. Fifteen-sheet coverage matrix

All 15 sheets are audited as business intents, not as a requirement to reproduce the workbook layout or formulas.

| # | Reference sheet | Business intent | Current equivalent | Status | Missing contract/data | Gap type / owner |
|---:|---|---|---|---|---|---|
| 1 | 综合说明 | Executive decision-support summary | Operator Summary / Operator Brief | PARTIAL | Market size, maturity, seller/FBA summary, Product Direction, shortlist | Contract / Market Report composition |
| 2 | 类目 | Category, scope, sample, window, grain | Category/Sample/DataWindow report sections | PARTIAL | Typed hierarchy, entry Demand Cluster, parent/child grain | Contract / scope |
| 3 | 市场调研 | Size, trend, concentration, maturity | Limited Competition section and sample metadata | MISSING | Sales/revenue, time series, true competitor set, governed concentration | Intelligence + contract |
| 4 | 竞品数据 | Auditable competitor detail | Upstream Product Intelligence only; no report detail rows | MISSING | Per-ASIN catalog, attributes, metrics, fulfillment, seller, marketing | Contract / competitor detail |
| 5 | 不同维度分析 | Configured distributions and segments | Attribute count/share plus price/rating/review numeric summaries | PARTIAL | Bucket policies, full dimensions, sales/revenue/price joins | Contract + aggregation |
| 6 | 自动化配置 | Workbook implementation controls | None required | NOT_PRODUCT_CONTRACT | Not a business capability | Excel internal |
| 7 | 原始数据源 | Evidence/data appendix | Report provenance and Markdown evidence table | PARTIAL | Sanitized row-level evidence appendix and richer state/method context | Evidence delivery |
| 8 | 关键词1—数据源 | External keyword-demand input | No external Keyword Intelligence adapter | EXTERNAL_INTEGRATION | Joint versioned input, mappings, availability degradation | External project integration |
| 9 | 分析模型对比 | Internal analytics/validation | Tests, fingerprints, design and validation docs | NOT_PRODUCT_CONTRACT | Optional only; not a report truth source | Internal validation |
| 10 | top100—日单量分析 | Top competitor operational view | No current Market Report delivery equivalent | MISSING | Ranked competitor rows, explicit grain, derived daily-sales label | Delivery + competitor detail |
| 11 | 产品初步筛选范围 | Evidence-backed Product Direction | Operator next checks are not directions | MISSING | Typed direction/configuration/evidence/risk contract | Decision support |
| 12 | 价格核算 | Explainable Unit Economics | Opportunity economic score dimension only | MISSING | Cost inputs, formula/provenance/status, margins | Economics contract |
| 13 | 样品类型 | Sample validation plan | No equivalent | MISSING | Priority, configuration, target, competitor, test purpose/risk | Decision support |
| 14 | 竞品收集 | Governed competitor shortlist | No equivalent | MISSING | True competitors, reason rules, direction links, detail metrics | Decision support |
| 15 | 自动化辅助 | Internal formulas/derived helpers | None required | NOT_PRODUCT_CONTRACT | Not a business capability | Excel internal |

## D. P0 gaps and smallest contract boundaries

P0 has 44 requirements: 9 `IMPLEMENTED`, 17 `PARTIAL`, and 18 `MISSING`. The smallest safe boundaries are deliberately narrower than a complete new schema design:

| Boundary | Covers | Minimum future contract decision | Owner |
|---|---|---|---|
| Scope context extension | MR-011, MR-014 | Typed category path/entry-demand reference plus explicit product grain and family aggregation policy ID. | Market Report contract |
| Metric context envelope | MR-054-MR-056 | Preserve observation/estimate/derived/query-empty semantics and attach denominator, grain, period, method, coverage, and lineage to each new metric/conclusion. | Evidence + Market Report |
| Market-size section | MR-002, MR-015-MR-016 | Monthly sales/revenue values with unit, period, cohort ID, estimate type, completeness, and limitation. No new formula is authorized by this audit. | Market intelligence |
| True Competitor Set and structure | MR-004, MR-020-MR-025 | Versioned membership snapshot with inclusion reason, product grain, denominator, and aggregate concentration/barrier outputs. | Competition intelligence |
| Distribution extension | MR-003, MR-005, MR-026-MR-033 | Versioned dimension/bucket policy and metric joins for product count/share and, only when compatible, sales/revenue/price. | Category Map + Market Report |
| Competitor detail | MR-007, MR-022, MR-034-MR-037 | Evidence-linked per-product rows referencing existing Product Intelligence/Clean Canonical records; fields remain null/status-aware. | Product Intelligence adapter |
| Buyer Need decision-support links | MR-006, MR-040-MR-042, MR-044 | Add typed need role/evidence subjects, competitor coverage, direction records, and rule-based shortlist references without changing Buyer Need semantics. | Report integration |
| Executive composition and appendix | MR-001, MR-009, MR-057-MR-060 | Compose only validated sections into stable executive claims and a sanitized evidence appendix; keep XLSX/Markdown parity. | Market Report + delivery |

No boundary above authorizes a score/formula change. In particular, Product Direction and Shortlist are explainable human-review artifacts, not `GO`, `BUY`, `LAUNCH`, profitability, or winner decisions.

## E. P1 gaps

All 9 P1 requirements are currently `MISSING`:

| Capability | IDs | Smallest future boundary | Dependency |
|---|---|---|---|
| Seller geography | MR-008, MR-031 | Sourced seller identity/location with parse status, then listing/sales/revenue distribution using explicit denominators. | Confirmed provider/external data |
| Trend, seasonality, new-product contribution, maturity | MR-017-MR-018 | Versioned time-series input and approved window/direction/cohort policies. | Comparable dated evidence |
| Top competitor operational view | MR-038 | Delivery projection over governed competitor detail/True Competitor Set; derived daily sales must be labeled `DERIVED`. | P0 competitor slices |
| Sample Plan | MR-043 | Typed validation-plan records linked to Product Direction, direct competitors, target evidence, and test risks. | P0 Product Direction |
| Unit Economics | MR-045 | Versioned input assumptions and formula lineage; missing cost inputs remain unavailable. | Prices/fees/cost sources |
| Risk and claim safety | MR-047-MR-048 | Structured, non-legal risk records and claim-evidence classification. | Evidence policy + optional external sources |

## F. External keyword gaps (`P1-EXT`)

MR-049 through MR-053 are all `EXTERNAL_INTEGRATION`. The architectural rule is **later integration, no duplicate implementation**.

The bounded integration boundary is:

```text
External Keyword Intelligence versioned snapshot
  -> contract validation and provenance preservation
  -> Keyword-to-ASIN / Buyer Need / Product Supply links
  -> Demand × Supply Gap projection
  -> validated Market Report extension
  -> XLSX / Markdown parity
```

This repository must not implement a new keyword collector, cleaner, normalizer, clusterer, intent engine, trend/seasonality engine, competition engine, or keyword opportunity scoring engine. Existing XiYou keyword observations and internal Demand artifacts are useful upstream evidence, but they do not satisfy the cross-project input contract. If the external snapshot is unavailable, the report must continue with an explicit unavailable/limitation state.

## G. P2 enhancements

All five P2 requirements are `DEFERRED_ENHANCEMENT`:

- MR-019: real three-month forecast;
- MR-046: break-even CPC/ACoS and fuller ad economics;
- MR-064: external IP data search;
- MR-065: supply-chain/sample-test feedback loop;
- MR-066: historical report/version comparison.

They must not be pulled into P0 contract work. Each requires its own data and semantic gate; absent values must remain `PARTIAL` or `UNAVAILABLE`, never synthetic numbers.

## H. Current capabilities that exceed the reference template

The current repository has governed capabilities not expressed as explicit requirements by the 15-sheet reference:

1. Deterministic report, provenance, workflow, and artifact identities and fingerprints.
2. Strict `additionalProperties: false` Market Report validation and deterministic JSON serialization.
3. Typed missing-data behavior that keeps null/unavailable distinct from numeric zero in report and operator presentation.
4. Operator triage actions (`COLLECT_EVIDENCE`, `FURTHER_REVIEW`, etc.) that avoid unauthorized market-entry decisions.
5. Explicit known/unknown evidence lists and evidence-triggered next checks.
6. Runtime health, bounded retry visibility, resume lineage, logical/executed/replayed operation counts, and provider usage presentation.
7. Machine-readable fixture-reference versus live-provider-reported credit semantics, including the operator-facing non-billed fixture note.
8. Checkpoint/resume and batch candidate isolation/recovery outside the analytical report semantics.
9. Frozen Buyer Need V0.3 / Taxonomy V0.2 and governed Opportunity policy fingerprints.
10. Same validated snapshot and same operator workflow driving both XLSX and Markdown.

These capabilities should be preserved in future versions. They do not compensate for missing reference-template business sections.

## I. Versioning recommendation

Recommendation: **keep `market-report-v0.1` stable and introduce a staged `market-report-v0.2`**, rather than adding optional fields to v0.1 or creating unrelated sidecar truth sources.

The version decision should follow these rules:

1. v0.1 remains readable, reproducible, and supported; its schema and fingerprints do not change.
2. v0.2 begins with an ADR and typed-contract design for P0 section boundaries, compatibility, deterministic serialization, validation, fixtures, and delivery parity.
3. Existing Buyer Need, Competition, Opportunity, Product Intelligence, and evidence outputs are adapted, not reimplemented or semantically changed.
4. Large row collections may be versioned nested sections or referenced evidence appendices, but validated JSON remains the business truth source.
5. Keyword Intelligence enters through an optional, separately versioned external snapshot adapter after joint contract freeze. It must not block non-keyword report generation.
6. P1 and P2 sections are staged behind explicit data gates and preserve unavailable/partial states.

This is a versioning recommendation only; this audit does not freeze the v0.2 schema.

## J. Bounded implementation sequence

| Sequence | Proposed bounded task | Outcome | Explicit non-goal |
|---:|---|---|---|
| 1 | SP-039A — Market Report V0.2 ADR and contract skeleton | Freeze compatibility, section boundaries, evidence context, product grain, and acceptance fixtures. | No metric formula or renderer implementation. |
| 2 | SP-039B — Scope, market size, and True Competitor structure | Add governed scope grain, sales/revenue envelope, competitor membership, concentration, and barrier outputs using existing intelligence. | No Product Direction or keyword work. |
| 3 | SP-039C — Distributions and competitor detail | Add versioned bucket/dimension policies and evidence-linked competitor rows; reuse Product Intelligence/Category Map. | No new extraction or scoring model. |
| 4 | SP-039D — Buyer Need links, Product Direction, and Shortlist | Adapt existing Buyer Need evidence into explainable directions and governed competitor reasons. | No automatic launch/buy/winner decision. |
| 5 | SP-039E — P1 seller/trend/operations/economics/risk/sample slices | Implement each only after its data and formula gate passes. | No synthetic values or legal conclusions. |
| 6 | SP-039F — External Keyword Intelligence integration | Joint versioned input, mappings, gap projection, safe degradation, and keyword delivery. | No duplicate keyword engine. |
| 7 | SP-039G — Executive and delivery completion | Compose validated sections into executive JSON, XLSX, Markdown, and sanitized evidence appendix with parity tests. | Delivery must not invent conclusions. |
| 8 | SP-039H — Separately approved P2 enhancements | Forecast, ad economics, external IP, test feedback, and history comparison as independent gated tasks. | No bundling into v0.2 P0 acceptance. |

Each future task must independently protect frozen Intelligence fingerprints and run regression gates. The sequence is a roadmap, not implementation performed by TASK-SP-039.

## Audit conclusion

The reference template is best treated as a business-capability acceptance model, not an Excel file to clone. Current v0.1 should remain the stable evidence-safe baseline. A staged v0.2 is justified by the number and nature of P0 contract gaps, especially market size, True Competitor Set, competitor detail, Product Direction, and Shortlist. External keyword capability remains a clearly separated P1-EXT integration. No identified gap was implemented in this audit.
