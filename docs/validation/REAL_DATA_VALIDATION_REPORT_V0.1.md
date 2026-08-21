# REAL DATA VALIDATION REPORT V0.1

Status: COMPLETE  
Task: TASK-SP-031 Real Data Validation v0.1  
Baseline commit: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`  
Validation run: `real-data-validation-run:23e5836f03cd2392f4d272894bd8d84563129421d6d1b84a73ba368e675c065a`

## 1. 测试类目

- Category: Pet Supplies
- Subcategory: Dog Travel Water Bottles
- Marketplace: US
- Cohort query: `dog water bottle`
- Inclusion rule: ASINs returned on page 1 for 'dog water bottle', last7days, traffic descending; only successfully adapted product profiles are included.
- Analysis window: `last7days`
- Retrieved at: `2026-08-21T00:35:39+00:00`

该子类目属于中等复杂度 Pet Supplies：存在容量、材质、便携、漏水防护、包装数量等可解释属性，同时避免 Fashion/Electronics 的高复杂度边界。

## 2. 数据来源与规模

数据来自 [XiYou OpenAPI V2](https://openapi-doc.xydc.com/)，使用显式只读 live gate。未保存 API Key 或完整原始响应。

- 请求商品数: 200
- 返回唯一 ASIN: 200
- Provider total: 658
- 商品详情行: 200
- Buyer Need 查询: 23/23
- Provider 请求数: 4
- Credits: 213

## 3. Pipeline 运行结果

| 阶段 | 输入 | 输出 | 失败 | UNKNOWN | Coverage | UNKNOWN % | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Attribute Extraction | 1000 | 417 | 0 | 583 | 41.70% | 58.30% | PARTIAL |
| Buyer Need Evidence | 23 | 23 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Buyer Need Map | 19 | 19 | 0 | 19 | 0.00% | 100.00% | PARTIAL |
| Canonical Evidence | 200 | 200 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Category Product Map | 200 | 200 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Competition Intelligence | 3 | 1 | 0 | 2 | 33.33% | 66.67% | PARTIAL |
| Data Input | 200 | 200 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Economic Evidence | 3 | 1 | 0 | 2 | 33.33% | 66.67% | PARTIAL |
| Opportunity Intelligence | 19 | 19 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Opportunity Score | 19 | 19 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Product Intelligence | 200 | 200 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Semantic Clustering | 24 | 19 | 0 | 0 | 100.00% | 0.00% | COMPLETE |
| Supply Demand Gap | 19 | 19 | 0 | 19 | 0.00% | 100.00% | PARTIAL |

完整链路已经执行至 Evidence-based Opportunity Score。所有 UNKNOWN 均保持为 UNKNOWN，没有填 0；相同 Candidate 与 Policy 的即时重放结果一致。

## 4. Coverage 分析

重点覆盖结论：

- Attribute coverage 由标题可验证字段决定；缺少结构化 catalog ground truth。
- Buyer Need 仅有 Search Term 来源；Review/Bullet population 为 UNKNOWN。
- Competition 可保留商品/关键词关系与评论门槛证据；Brand concentration 为 UNKNOWN。
- Economic Evidence 有 observed price；sales/revenue 为 UNKNOWN。

## 5. Attribute 验证

Sampling: Deterministic PRNG sample; SHA-256 seed TASK-SP-031:attribute-sample:v0.1  
Evidence basis: Confirmed extractor assertion must be textually concordant with the live XiYou product title.

| 维度 | 正确 | 错误 | UNKNOWN | 已知值准确率 | 已知覆盖率 |
| --- | --- | --- | --- | --- | --- |
| capacity | 72 | 1 | 27 | 98.63% | 73.00% |
| feature | 85 | 0 | 15 | 100.00% | 85.00% |
| material | 56 | 0 | 44 | 100.00% | 56.00% |
| package_quantity | 2 | 0 | 98 | 100.00% | 2.00% |
| size | 0 | 0 | 100 | 0.00% | 0.00% |

这里的“正确”表示确认 assertion 与真实 provider title 文本一致，不等同于独立 Amazon catalog ground truth。UNKNOWN 不进入准确率分母。

## 6. Category Product Map 验证

Overall judgement: **PARTIAL**  
Reason: Bottle capacities/features are plausible where title evidence exists, but UNKNOWN rates are high and category membership is keyword-defined.

| 维度 | Known | UNKNOWN | Coverage | Top values |
| --- | --- | --- | --- | --- |
| capacity | 149 | 51 | 0.745 | 0.295735295625 L (35, 23.5%), 0.946352946 L (17, 11.4%), 0.35488235475 L (14, 9.4%), 0.5618970616875 L (13, 8.7%), 1.0942205938125 L (9, 6.0%) |
| feature | 165 | 35 | 0.825 | Portable (150, 90.9%), Leakproof (106, 64.2%), Foldable (35, 21.2%) |
| material | 101 | 99 | 0.505 | Stainless Steel (78, 77.2%), Silicone (32, 31.7%), Plastic (9, 8.9%) |
| package_quantity | 2 | 198 | 0.01 | 1 COUNT (1, 50.0%), 2 COUNT (1, 50.0%) |
| size | 0 | 200 | 0 | UNKNOWN |

- Combination segments: 99
- Observed price band: minimum=5.99, maximum=43.69, mean=17.90929292929292929292929293, median=15.09
- Price ownership note: Market Analysis observed product price; Category Product Map has no native price dimension.

## 7. Buyer Need 验证

| Rank | Buyer Need | Search share | 状态 | Confidence | 来源 | 人工评价 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12 Oz Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 2 | 19 Oz Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 3 | 27 Oz Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 4 | 32 Oz Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 5 | Compact Size Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 6 | Compatible With Car Cup Holder Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 7 | Durability | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 8 | Easy Cleaning | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 9 | Fits Bicycle Bottle Cage Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 10 | Large Capacity | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 11 | Large Dogs Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 12 | Leak Prevention | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 13 | Lightweight | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 14 | Outdoor Portability | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 15 | Small Dogs Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 16 | Spill Prevention | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 17 | Stainless Steel Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 18 | Walking Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |
| 19 | Works With Stroller Cup Holder Need | UNKNOWN | UNKNOWN | UNKNOWN | Search Term | INSUFFICIENT_DATA |

这些需求都由真实 Search Term 明示触发；由于 Review 与 Bullet 证据缺失，评价最多为 POSSIBLE，不升级为已确认消费者共识。

## 8. Supply/Demand Gap 验证

| Rank | Need | Gap type | Strength | Confidence | 人工评价 | 理由 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12 Oz Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 2 | 19 Oz Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 3 | 27 Oz Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 4 | 32 Oz Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 5 | Compact Size Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 6 | Compatible With Car Cup Holder Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 7 | Durability | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 8 | Easy Cleaning | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 9 | Fits Bicycle Bottle Cage Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 10 | Large Capacity | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 11 | Large Dogs Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 12 | Leak Prevention | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 13 | Lightweight | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 14 | Outdoor Portability | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 15 | Small Dogs Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 16 | Spill Prevention | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 17 | Stainless Steel Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 18 | Walking Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |
| 19 | Works With Stroller Cup Holder Need | INSUFFICIENT_EVIDENCE | UNKNOWN | UNKNOWN | INSUFFICIENT_DATA | Demand or linked canonical supply evidence is incomplete; no zero was substituted. |

VALID_GAP 只用于 `HIGH_DEMAND_LOW_SUPPLY` 且上游证据可计算的结果；其余明确标为 FALSE_GAP 或 INSUFFICIENT_DATA。

## 9. Opportunity Score 验证

| Rank | Candidate | Score | Confidence | Candidate status | 人工评价 | Reason/Risk |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Durability | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 2 | Leak Prevention | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 3 | Spill Prevention | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 4 | Stainless Steel Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 5 | Compact Size Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 6 | Large Capacity | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 7 | Walking Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 8 | Large Dogs Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 9 | Outdoor Portability | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 10 | Easy Cleaning | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 11 | Compatible With Car Cup Holder Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 12 | Fits Bicycle Bottle Cage Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 13 | 19 Oz Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 14 | 12 Oz Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 15 | Small Dogs Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 16 | Lightweight | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 17 | 27 Oz Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 18 | Works With Stroller Cup Holder Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |
| 19 | 32 Oz Need | 50.0 | UNKNOWN | INSUFFICIENT_EVIDENCE | WEAK | PARTIAL_EVIDENCE:competition.price_competition; PARTIAL_EVIDENCE:competition.review_barrier; PARTIAL_EVIDENCE:evidence_confidence.competition |

- Policy version: `opportunity-score-policy-v0.1`
- Score 与 Confidence 分离；LOW/UNKNOWN Confidence 不会被改写成 0 分。
- 排名只比较同一验证 cohort 内的 evidence aggregation，不是自动选品或利润预测。

## 10. 发现问题

| # | 分类 | 严重度 | 问题 | 影响模块 | 建议修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | DATA_QUALITY | WARNING | Traffic evidence method and exact period are unconfirmed | competition_intelligence, demand_intelligence | Obtain provider method documentation before treating traffic as a calibrated demand metric. |
| 2 | DATA_QUALITY | WARNING | Keyword cohort is not a browse-node census | category_product_map, opportunity_intelligence, supply_demand_gap | Validate against an audited Amazon browse-node or category inventory source in the next run. |
| 3 | COMPETITION | WARNING | Brand concentration cannot be calculated | competition_intelligence, opportunity_scoring | Add canonical brand identity evidence and preserve UNKNOWN until it is available. |
| 4 | DATA_QUALITY | ERROR | Product detail source lacks bullets, reviews, brand, and structured attributes | attribute_extraction, buyer_need_map, competition_intelligence, product_intelligence | Add an audited provider source for bullets, review text, brand, and structured attributes before calibration; do not infer absent facts. |
| 5 | OTHER | INFO | Category Product Map has no native price-band dimension | category_product_map, market_analysis | Decide contract ownership for price bands before any future implementation task. |
| 6 | DEMAND_MODEL | WARNING | Demand validation has no Review or Bullet population | buyer_need_analysis, buyer_need_map, supply_demand_gap | Collect audited review and bullet evidence, then re-run without changing the taxonomy during validation. |
| 7 | OTHER | WARNING | XiYou forward request identity uses two equivalent fields | connectors, data_cleaning | Add a versioned request adapter that maps canonical keyword to provider searchTerm while preserving canonical request context. |
| 8 | SCORING | WARNING | Sales and revenue evidence are unavailable | market_analysis, opportunity_scoring | Add audited sales/revenue evidence in a later data-source task; do not change score policy in this validation task. |

## 11. 限制

- Attribute audit is source-title concordance, not independent catalog ground truth.
- Cohort is a traffic-ranked keyword result page, not a complete Amazon browse-node census.
- No scoring, extraction, taxonomy, gap, opportunity, or Foundation policy was changed during validation.
- Provider traffic method and exact period semantics are unconfirmed by the canonical adapter.
- Review mention demand, brand concentration, sales, and revenue remain UNKNOWN.
- XiYou asin_info exposes title, price, rating, and review count but no bullets, review text, brand, or structured attributes.

## 12. 下一阶段优化建议

1. 先补齐 audited Amazon browse-node/category inventory，避免以单关键词 cohort 代表完整类目。
2. 补齐 bullet、review text、brand 与 structured attribute 数据源，再做 Attribute/Buyer Need 独立 ground-truth calibration。
3. 补齐 sales/revenue evidence；继续保持缺失经济数据 UNKNOWN，不惩罚也不奖励。
4. TASK-SP-032 只针对本报告记录的问题做 calibration proposal；权重、taxonomy、gap threshold 的任何变化必须另起版本并回放本次 validation snapshot。
5. 建立第二类目对照（Kitchen 或 Home Improvement），检验结论是否跨类目稳定。

## 禁止范围审计

- 未修改 Opportunity Score 公式或 Policy。
- 未修改 Attribute Extraction Rules。
- 未修改 Buyer Need Taxonomy。
- 未修改 Gap Threshold。
- 未修改 Foundation/Core Model。
- 未新增 UI、Excel、利润预测或 AI 自动推荐。
