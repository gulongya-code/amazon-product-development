# Market Report Reference Template Requirements V0.1

- **文档状态**：Current Reference Requirements / 当前参考需求
- **版本**：V0.1
- **日期**：2026-08-24
- **适用项目**：Amazon Product Intelligence / 亚马逊智能选品系统
- **来源模板**：`浴室淋浴置物架市场调研.xlsx`
- **模板用途**：作为最终 Market Report 的业务能力参考与验收样板，不作为 Excel 公式、Sheet 排列或内部实现方式的强制复制合同。
- **上位需求**：`docs/requirements/亚马逊智能选品系统_产品需求与核心架构说明_V0.2.md`
- **当前实现基线**：`market-report-v0.1`，现有核心包含 category / sample / data_window / buyer_needs / product_attributes / competition / opportunity_score / provenance / limitations。
- **本次变更边界**：只冻结需求，不在本任务修改 Intelligence Model、Market Report Schema、XLSX Renderer 或任何算法代码。

---

## 1. 文档结论

用户提供的 `浴室淋浴置物架市场调研.xlsx` 正式作为 Market Report 的重要参考验收样板。

系统最终目标不是复刻该 Excel 的公式和人工维护方式，而是自动生成其核心业务结论，并在以下方面达到或超过模板：

1. 数据与结论可追溯；
2. Product / Demand / Competition / Buyer Need 能够互相连接；
3. 缺失、未知、估算与真实观察明确区分；
4. 关键词需求由外部 Keyword Intelligence 项目后续融合，不在本项目重复开发；
5. 利润、趋势预测与风险结论不制造虚假精度；
6. XLSX / Markdown 只是交付层，JSON / typed contract 仍是事实源。

最终 Market Report 应能回答：

> 市场多大、增长如何、谁在卖、卖什么结构、价格和评论门槛如何、买家真正需要什么、哪里存在供给缺口、哪些产品方向值得进一步打样，以及主要风险和证据限制是什么。

---

## 2. 参考模板结构审计

模板共 15 个 Sheet：

1. `综合说明`
2. `类目`
3. `市场调研`
4. `竞品数据`
5. `不同维度分析`
6. `自动化配置`
7. `原始数据源`
8. `关键词1—数据源`
9. `分析模型对比`
10. `top100—日单量分析`
11. `产品初步筛选范围`
12. `价格核算`
13. `样品类型`
14. `竞品收集`
15. `自动化辅助`

当前模板样本特征：

- 原始 Listing 样本约 998 条；
- `原始数据源` 包含 66 个字段；
- `竞品数据` 扩展到 89 个字段；
- 既包含原始数据，也包含属性清洗、分布分析、选品建议、竞品筛选、成本核算和综合结论。

### 2.1 业务合同与 Excel 内部实现必须分离

以下属于**业务能力需求**：

- 市场容量；
- 销售额；
- 市场趋势；
- 品牌 / 商品 / 卖家集中度；
- 价格、评论、评分、上架时间、FBA 等分布；
- 产品类型、安装方式、材质、颜色、结构容量、套装件数等属性分布；
- 竞品明细；
- 竞争门槛；
- Buyer Need / 痛点；
- 选品方向；
- 样品建议；
- 竞品收集清单；
- 成本与利润边界；
- 风险、限制与证据。

以下属于**模板内部实现细节，不冻结为系统产品合同**：

- `自动化配置` 的具体 Excel 操作方式；
- `自动化辅助` 的中间公式结构；
- 数据透视表位置；
- 特定单元格坐标；
- 蓝色表头下拉规则；
- WPS/Excel 特定图片公式；
- Sheet 必须保持完全相同的名称、数量和顺序。

系统可以重新设计最终 Workbook，只要业务信息完整、可追溯、易于运营人员使用。

---

## 3. 最终 Market Report 的必备信息架构

### 3.1 Executive Summary / 综合结论 — MUST

最终报告首页或第一部分至少需要输出：

- 品类 / 核心研究对象；
- 市场容量与月销售额；
- 主要价格带与客单价；
- 市场成熟度；
- 市场竞争度；
- 推广难度 / Review Barrier；
- 主要产品形态与销量占比；
- 买家主要痛点；
- FBA / 运输特点；
- 卖家地域结构；
- 主要进入机会；
- 主要风险；
- 推荐进一步验证的产品方向；
- 结论的 evidence / confidence / limitation。

综合结论不得只输出 Opportunity Score。

### 3.2 Category & Scope / 类目与研究范围 — MUST

至少包含：

- marketplace；
- 核心类目；
- 大类目 / 细分类目；
- 研究入口关键词或 Demand Cluster；
- 数据窗口；
- 样本量；
- 唯一 ASIN 数；
- Parent / Child 聚合口径；
- Provider 覆盖情况；
- 样本覆盖率与限制。

### 3.3 Market Size & Trend / 市场容量与趋势 — MUST

至少包含：

- 月销量；
- 月销售额；
- 销量 / 销售额趋势；
- 季节性；
- 新品销量贡献；
- 市场成熟度；
- 趋势结论及其数据窗口。

如果未来三个月预测模型和数据不足，则必须输出 `PARTIAL` 或 `UNAVAILABLE`，不得为了填表生成伪预测值。

当预测模块具备足够数据时，SHOULD 输出：

- 下月预测销量；
- 第 2 月预测销量；
- 第 3 月预测销量；
- 预测区间；
- 旺淡季系数或主要驱动因素；
- 模型版本与限制。

### 3.4 Competition Structure / 竞争结构 — MUST

至少包含：

- True Competitor Set；
- Top 10 商品销量集中度；
- 品牌集中度；
- 卖家集中度；
- 头部品牌 / 商品 / 卖家；
- 核心竞品数量；
- 核心竞品销量 / 销售额占比；
- 新品与老品的竞争结构；
- Review Barrier；
- Rating Barrier；
- Market Entry Difficulty；
- 表面搜索竞争与真实竞争的差异说明。

所有集中度必须明确计算范围和粒度，避免 Parent / Child 重复计数。

### 3.5 Product Attribute Segmentation / 产品属性细分 — MUST

系统应尽量自动提取并统计以下维度：

- product_type / 产品类型；
- material / 材质；
- structure_capacity / 结构容量；
- mounting_type / 安装方式；
- color / 颜色；
- pack_count / 套装件数；
- size / 尺寸；
- weight / 重量；
- package_size / 包装尺寸；
- use_case / 使用场景；
- audience / 人群；
- special_feature / 核心功能卖点。

每个维度至少应支持：

- Listing 数量；
- Listing 占比；
- 销量；
- 销量占比；
- 销售额；
- 销售额占比（数据可得时）；
- 平均 / 中位价格（适用时）；
- Unknown 数量与覆盖率；
- 证据来源与 limitation。

不可将 AI 无证据猜测当作已确认属性。

### 3.6 Distribution Analysis / 多维分布分析 — MUST

参考模板中的以下分析应被系统能力覆盖：

- 价格区间分布；
- 评论数分布；
- 上架时间分布；
- 评分分布；
- FBA 费用分布；
- 留评率分布；
- 卖家国家 / 地域分布；
- 产品类型分布；
- 安装方式分布；
- 材质分布；
- 结构容量分布；
- 套装件数分布。

每个区间或 bucket 应至少支持：

- 产品数；
- 产品数占比；
- 销量；
- 销量占比。

区间边界必须配置化 / 版本化，不应将模板里的 `$15`、`$30`、评论 100/1000、上架天数等阈值永久硬编码为全品类通用规则。

### 3.7 Competitor Detail / 竞品明细 — MUST

系统最终应有可审计的竞品明细表。字段按能力分组，不要求 1:1 复制模板列顺序。

#### A. Identity & Catalog

- ASIN；
- Parent ASIN；
- SKU / Variation；
- Brand；
- Title；
- Category Path；
- Product URL；
- Main Image URL。

#### B. Product Intelligence

- Product Type；
- Material；
- Structure / Capacity；
- Mounting Type；
- Color；
- Pack Count；
- Product Facts / Attributes；
- Product Dimension / Weight；
- Package Dimension / Weight。

#### C. Market Metrics

- BSR；
- BSR Change；
- Monthly Sales；
- Sales Growth；
- Monthly Revenue；
- Child Sales / Revenue（口径明确时）；
- Variant Count；
- Price；
- Prime Price；
- Coupon。

#### D. Reviews & Quality

- Rating；
- Review Count；
- New Reviews；
- Review Rate；
- Q&A；
- LQS / 等价内容质量指标（数据可得时）。

#### E. Fulfillment & Economics

- Fulfillment Type；
- FBA Fee；
- Buyer Shipping；
- Product / Package Size Tier；
- Gross Margin / Unit Economics 状态。

#### F. Seller / Marketing Signals

- Seller Count；
- Buy Box Seller；
- Seller Location；
- Best Seller；
- Amazon's Choice；
- New Release；
- A+；
- Video；
- Sponsored Placement；
- Brand Story / Brand Ads；
- Deal / Promotion indicators。

任何字段缺失时不得默认填 0。

### 3.8 Top Competitor Operational View — SHOULD

参考 `top100—日单量分析`，系统 SHOULD 提供 Top 商品的运营视图，例如：

- 排名；
- ASIN；
- 品牌；
- 月销量 / 推导日均销量；
- Parent / Child 粒度；
- 上架天数；
- 售价；
- FBA；
- 留评率；
- 核心产品类型。

如果日单量由月销量除以天数推导，必须标记为 `DERIVED`，不得伪装成 Provider 直接观察值。

---

## 4. Buyer Need 与售后痛点要求

模板已经表达了粘胶脱落、承重、锈蚀、安装兼容、晃动、排水和耐用性等售后问题，但最终系统不应只靠人工填写。

Market Report MUST 连接现有 Buyer Need Intelligence，并至少输出：

- Buyer Need；
- Need Type / Intent；
- Positive Need；
- Pain Point；
- 受影响 ASIN / Review 证据；
- Frequency / Strength；
- Coverage；
- Confidence；
- 主要竞品是否已满足；
- 与推荐产品方向的关系。

Buyer Need 应与 Product Attribute / Competitor / Demand–Supply Gap 互相可追溯。

---

## 5. Product Direction / 产品初步筛选要求

参考模板 `产品初步筛选范围`，系统 MUST 输出可供人工继续验证的产品方向，而不是自动做“做 / 不做”决策。

每个方向至少应包含：

- direction_id；
- 产品类型；
- 关键结构 / 容量；
- 材质；
- 安装方式；
- 套装件数；
- 建议价格带；
- 对应 Buyer Need；
- 对应市场证据；
- 主要直接竞品；
- 进入逻辑；
- 关键验证项；
- 风险；
- confidence / limitations。

推荐方向必须能够解释“为什么”，不能只是 AI 文本建议。

---

## 6. Sample Plan / 样品类型要求

参考模板 `样品类型`，系统 SHOULD 生成样品验证计划：

- 优先级；
- 样品类型；
- 核心规格；
- 材质；
- 安装方式；
- 建议配置；
- 目标价格；
- 直接竞品；
- 竞品销量参考；
- 样品验证目的；
- 必测风险点。

样品计划是“进一步研究建议”，不是自动采购指令。

---

## 7. Competitor Shortlist / 竞品收集要求

参考模板 `竞品收集`，系统 MUST 支持输出直接竞品清单，至少包含：

- 优先级；
- Brand；
- ASIN；
- Monthly Sales；
- Price；
- Rating；
- Review Count；
- Listing Age；
- Material；
- Mounting Type；
- Product Type；
- FBA Fee；
- 对应 Product Direction；
- 选择理由；
- 商品链接。

竞品选择理由应基于可验证规则，例如销量、结构代表性、Buyer Need 覆盖、价格带、头部地位或直接替代关系。

---

## 8. Unit Economics / 价格与成本核算要求

参考模板 `价格核算`，系统 SHOULD 将“利润率”从单一毛利字段升级为可解释的 Unit Economics。

至少支持：

- Selling Price；
- Referral Fee；
- FBA Fee；
- Purchase Cost；
- Headhaul / Inbound Freight；
- Packaging / Prep；
- Ad Cost 假设；
- Return / Damage Allowance；
- Other Variable Cost；
- Gross Profit；
- Contribution Profit；
- Net Margin / Contribution Margin；
- Break-even CPC / ACoS 或等价广告容忍空间（后续增强）。

模板中的“30%整套出厂采购价上限”可以作为参考情景，但不得硬编码为所有品类的唯一采购价算法。

成本输入缺失时必须显示 `PARTIAL` / `UNAVAILABLE` 和具体缺口。

---

## 9. Risk / Compliance 要求

### 9.1 知识产权

系统不得输出法律结论式的“侵权 / 不侵权”。

应输出：

- Risk Level：LOW / MEDIUM / HIGH / UNKNOWN；
- 可能涉及的商标 / 外观 / 结构 / 声明风险；
- 触发风险的结构或文案；
- Evidence；
- 推荐人工核查事项；
- 明确免责声明。

### 9.2 Product Claim / Safety

对于“防锈、承重、不伤墙、防水”等可验证声明，应区分：

- Seller Claim；
- Provider Observation；
- Review Evidence；
- Test Result（未来可接入）；
- System Inference。

不能因为标题写了 `rustproof` 就自动确认“真实防锈”。

---

## 10. Keyword Demand Analysis / 关键词需求分析集成

### 10.1 关键架构决策

关键词分析当前由**单独的 Keyword Intelligence 项目**负责。

因此本项目明确采用：

> **后续融合，不重复开发。**

当前 Amazon Product Intelligence 项目不得为了 Market Report 再实现一套独立的关键词抓取、清洗、聚类、搜索意图、趋势和关键词机会评分核心算法。

### 10.2 Keyword Intelligence 项目职责

外部 Keyword Intelligence 项目负责或未来负责：

- Keyword Collection；
- Keyword Cleaning / Normalization；
- Search Volume；
- Trend / Growth；
- Seasonality；
- Keyword Clustering；
- Search Intent；
- Demand Classification；
- Keyword Competition；
- CPC / Bid 等关键词竞争数据；
- Keyword Opportunity / Demand Score；
- Keyword Evidence / Provenance。

### 10.3 本项目职责

Amazon Product Intelligence / Market Report 负责：

1. 接收外部 Keyword Intelligence 的版本化输出；
2. 验证输入合同；
3. 保留 source project / source version / provenance；
4. 将 Keyword / Demand 与 ASIN、Product Attribute、Buyer Need、Competition 关联；
5. 生成 Demand × Supply Gap；
6. 在 XLSX / Markdown 中展示关键词需求分析；
7. 外部关键词数据不可用时仍允许市场报告降级运行。

### 10.4 推荐的外部集成合同

最终字段名应由两个项目共同冻结，当前需求至少预留以下语义：

```text
KeywordIntelligenceSnapshot
├── snapshot_id
├── source_project
├── source_version
├── marketplace
├── category_or_scope
├── generated_at
├── data_window
├── keywords[]
│   ├── keyword_id
│   ├── keyword
│   ├── normalized_keyword
│   ├── search_volume
│   ├── trend
│   ├── growth_rate
│   ├── seasonality
│   ├── search_intent
│   ├── demand_cluster_id
│   ├── relevance
│   ├── competition
│   ├── cpc_or_bid
│   ├── opportunity_score
│   ├── buyer_need_links[]
│   ├── evidence_ids[]
│   └── limitations[]
├── provenance[]
└── limitations[]
```

该结构只是**语义预留**，不是本任务冻结 JSON Schema。

### 10.5 最终 Market Report 的关键词展示 — MUST WHEN AVAILABLE

当外部 Keyword Intelligence 数据为 `AVAILABLE` 时，最终报告至少应输出：

- Keyword；
- Search Volume；
- Search Trend；
- Growth；
- Seasonality；
- Search Intent；
- Demand Cluster；
- 相关 Buyer Need；
- Product Relevance；
- Competition；
- CPC（数据可得时）；
- Opportunity / Demand Score；
- Evidence / Limitations。

但关键词机会排序不得仅按 Search Volume 排名。

---

## 11. Demand × Supply Gap / 需求供给缺口

Keyword Intelligence 接入后，Market Report SHOULD 形成以下交叉链路：

```text
Keyword Demand
      ×
Buyer Need / Pain Point
      ×
True Competitor Product Supply
      ↓
Demand–Supply Gap
```

每个 Gap 至少应说明：

- 需求是什么；
- 哪些关键词支持；
- 搜索需求强度；
- 哪些 Buyer Need / Review 支持；
- 当前竞品如何覆盖；
- 未满足部分是什么；
- 可能的产品方向；
- 主要风险；
- Evidence / Confidence / Limitation。

不能仅因为关键词出现或一条差评就声明存在市场缺口。

---

## 12. Seller Geography / 卖家结构

参考模板，中国卖家占比属于市场结构的重要观察。

系统 SHOULD 输出：

- Seller Location；
- Listing Count；
- Listing Share；
- Sales；
- Sales Share；
- Revenue / Revenue Share（数据可得时）。

卖家所在地字段需要保留来源和解析状态；不能仅凭品牌名推断国家。

---

## 13. Data Semantics / Evidence / Confidence

所有 Market Report 指标必须遵循现有 Evidence First 原则。

### 13.1 数据状态

必须能够区分：

- `OBSERVED`
- `PROVIDER_ESTIMATE`
- `RESOLVED`
- `DERIVED`
- `UNKNOWN`
- `MISSING`
- `QUERY_RETURNED_EMPTY`
- 数值 `0`

### 13.2 关键指标必须带口径

例如“市场容量”必须说明：

- 基于全量 Provider 候选还是 True Competitor Set；
- Parent / Child 聚合口径；
- 时间周期；
- Marketplace；
- 样本覆盖率；
- 是否为 Provider Estimate；
- 是否存在重复 / 缺失风险。

### 13.3 Conclusion Traceability

综合说明中的重要结论必须尽可能回溯到：

```text
Conclusion
  ↓
Metric / Distribution / Buyer Need / Competitor
  ↓
Resolved / Derived Evidence
  ↓
Provider Observation / Estimate
```

---

## 14. Delivery Architecture / 交付架构

当前架构方向保持不变：

```text
Intelligence Models
        ↓
Market Report JSON / Typed Contract
        ↓
Operator Delivery
   ├── XLSX
   └── Markdown
```

明确要求：

- Excel 不是计算事实源；
- Markdown 和 XLSX 必须来自同一个 validated Market Report；
- 交付层不得自行发明新业务结论；
- 同一报告的核心结论应在不同交付格式之间一致；
- Excel 可拥有更丰富的表格与运营视图，但不能绕过 Report / Evidence 层产生不可追溯结论。

---

## 15. 参考模板 Sheet → 系统能力映射

| 模板 Sheet | 系统对应能力 | 最终要求 |
|---|---|---|
| 综合说明 | Executive Summary / Decision Support | MUST |
| 类目 | Category / Scope / Sample | MUST |
| 市场调研 | Market Size / Trend / Concentration | MUST |
| 竞品数据 | Competitor Detail + Product Intelligence | MUST |
| 不同维度分析 | Distribution / Segmentation | MUST |
| 自动化配置 | Excel 内部配置 | NOT A PRODUCT CONTRACT |
| 原始数据源 | Evidence / Data Appendix | MUST 保留证据，展示形式可重构 |
| 关键词1—数据源 | External Keyword Intelligence Integration | MUST WHEN AVAILABLE；不重复开发 |
| 分析模型对比 | Internal Analytics / Validation | OPTIONAL DELIVERY / INTERNAL |
| top100—日单量分析 | Top Competitor Operational View | SHOULD |
| 产品初步筛选范围 | Product Direction | MUST |
| 价格核算 | Unit Economics | SHOULD / 立项前关键 |
| 样品类型 | Sample Validation Plan | SHOULD |
| 竞品收集 | Competitor Shortlist | MUST |
| 自动化辅助 | Internal Derived Layer | NOT A PRODUCT CONTRACT |

---

## 16. 优先级

### P0 — Market Report 正式可用前必须完成

- Executive Summary；
- Category / Scope / Sample；
- Market Size；
- Competition；
- Product Attribute Distribution；
- Price / Review / Rating / Listing Age / FBA 等核心分布；
- Competitor Detail；
- Buyer Need；
- Product Direction；
- Competitor Shortlist；
- Provenance / Limitation；
- XLSX / Markdown 一致交付。

### P1 — 产品立项质量增强

- Unit Economics；
- Seller Geography；
- Top Competitor Operational View；
- Sample Plan；
- 更完整趋势与季节性；
- 风险筛查。

### P1-EXT — 外部项目成熟后融合

- Keyword Demand Analysis；
- Keyword → Buyer Need Mapping；
- Keyword → ASIN / Product Supply Mapping；
- Demand × Supply Gap；
- Keyword Opportunity Ranking。

关键词模块属于最终目标中的必备能力，但**不构成本项目当前重复开发任务**。

### P2 — 后续增强

- 真实三个月逐月预测；
- 更完整广告经济模型；
- 更完整知识产权外部数据检索；
- 供应链 / 样品测试结果反馈闭环；
- 历史版本横向对比。

---

## 17. 与当前 `market-report-v0.1` 的关系

当前 `market-report-v0.1` 已经形成稳定的核心合同和 Operator Delivery。

本需求文档**不要求直接修改现有 v0.1**。

下一步应先做 Gap Analysis：

```text
Reference Template Requirements
            ↓
Current market-report-v0.1
            ↓
Coverage / Missing / Partial Matrix
            ↓
Versioning Decision
            ↓
market-report-v0.2 或扩展子合同
```

禁止为了匹配模板直接向现有稳定 Schema 随意塞字段。

任何 Schema 扩展必须：

- 版本化；
- 有 backward compatibility 决策；
- 有 deterministic serialization；
- 有 validation；
- 有 fixtures；
- 有 delivery tests；
- 不破坏现有 Buyer Need / Competition / Opportunity 指纹和稳定合同，除非明确进行版本升级。

---

## 18. 下一阶段建议开发顺序

```text
本需求 V0.1 冻结
      ↓
Current Market Report Gap Audit
      ↓
业务模块分组与版本策略
      ↓
Market Report Contract Extension
      ↓
Market / Distribution / Competitor Views
      ↓
Unit Economics / Product Direction / Shortlist
      ↓
Operator XLSX / Markdown Expansion
      ↓
Keyword Intelligence External Contract（外部项目成熟后）
      ↓
Demand × Supply Gap
```

不应现在为了关键词 Sheet 重写一个 Keyword Intelligence Engine。

---

## 19. 验收标准

本需求进入实现后，最终至少应满足：

1. 使用一个真实 Amazon 类目可以从 API / Canonical Evidence 自动生成 Market Report；
2. 报告能覆盖参考模板的核心业务结论，而不是要求人工维护 Excel 公式；
3. 能输出市场规模、竞争、属性、分布、竞品、Buyer Need 和产品方向；
4. 重要指标具有明确的 period / scope / aggregation 口径；
5. Parent / Child 不重复计数；
6. Unknown / Missing 不被写成 0；
7. Provider Estimate 不被伪装成 Observed Fact；
8. 趋势预测不足时能够安全降级；
9. “侵权”只做风险筛查，不做法律判断；
10. 利润模型明确费用范围，不用单一毛利率冒充最终净利润；
11. Keyword Intelligence 不在本项目重复开发；
12. 外部 Keyword Intelligence 可通过版本化合同后续接入；
13. 关键词不可用时 Market Report 仍可运行并明确标记限制；
14. Keyword 数据可用后可以形成 Keyword × Buyer Need × Supply 的交叉分析；
15. XLSX 与 Markdown 来源于同一 validated Report，核心结论一致；
16. 所有重要结论尽可能具备 evidence / provenance / limitations；
17. 系统输出建议，但最终产品立项仍由人工决策。

---

## 20. 本次明确冻结的产品决策

1. `浴室淋浴置物架市场调研.xlsx` 作为 Market Report 的重要参考验收样板。
2. 不要求 1:1 复制 Excel Sheet、公式或人工辅助结构。
3. 最终报告必须覆盖模板中的核心市场、竞品、属性、成本和选品决策信息。
4. Buyer Need 是最终 Market Report 的核心组成部分。
5. Keyword Demand Analysis 是最终 Market Report 的目标能力。
6. Keyword Intelligence 由独立项目负责，本项目后续通过合同融合，避免重复开发。
7. 最终融合目标是 `Keyword Demand × Buyer Need × Product Supply`，形成 Demand–Supply Gap。
8. 当前 `market-report-v0.1` 保持稳定；后续先做 Gap Audit，再决定 v0.2 或扩展合同。
9. Excel 继续作为 Operator Delivery，不成为系统事实源。
10. 任何重要市场结论必须保留口径、证据、置信度与限制。

---

**End of Market Report Reference Template Requirements V0.1**
