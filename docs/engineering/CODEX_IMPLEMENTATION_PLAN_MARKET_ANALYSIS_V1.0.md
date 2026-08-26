# Codex 实施方案 — 亚马逊市场分析系统 V1.0

版本：V1.0（2026-08-26）

## 0. 当前工程基线

- Repository: `gulongya-code/amazon-product-development`
- 当前前置任务：GitHub Issue #50 `TASK-SP-040G — Sorftime Market Report V0.2 Full Live Acceptance`
- Issue #50 当前 required baseline: `ce2a86b142f03c5a7a3b54c263d613b79955c6ec`
- 新的 `SP-041*` 工作流从 **SP-040G 最终 accepted commit** 开始。
- 不绕过现有 V0.1/V0.2 严格合同，不把新模板逻辑塞进 Sorftime provider contract。

## 1. 产品决策（必须冻结）

1. SellerSprite 手动导出负责类目市场广度，目标支持 `50–1500 Listings`。
2. Sorftime 不重复抓取全市场；只用于候选路线的代表性 ASIN，以及方向锁定后的直接竞品深挖。
3. 用户当前模板为正式 Operator Template V1：**11 visible Sheets + 4 hidden Sheets**。
4. 当前模板约有 `26,738` 个公式；正确公式优先复用，但关键指标必须同时在代码层计算，供 JSON/AI/自动验收使用。
5. 产品路线（Product Archetype）先于直接竞品。`DIRECTION_LOCKED` 之前禁止生成 Direct Competitor Set。
6. 目标毛利率默认 `30%`，倒推整套/单件出厂采购成本上限；默认不含头程、广告、退货损耗。
7. `LQS`、`CPF绿标`、`SP广告` 暂不进入 MVP。
8. 用户真实 998 行市场数据和 7.6MB 模板仅作本地外部验收资产，未经明确批准不得提交 Git。

## 1A. Public GitHub Reuse Gate（SP-041 全系列前置门）

任何新模块动工前必须先在 GitHub 公共仓库搜索相似实现，并按许可证分类：

- `DIRECT_REUSE_ALLOWED`：MIT / Apache-2.0 / BSD 等可复用；优先采用成熟组件或小范围移植，并保留许可证要求。
- `DEPENDENCY_REUSE`：优先直接依赖成熟库（例如 scikit-learn），不要复制算法实现。
- `REFERENCE_ONLY`：无 LICENSE、All Rights Reserved 或授权不明确；只允许借鉴架构/测试思路，不得复制实现。
- `REJECTED`：与本项目语义、数据合同、安全要求或维护成本不匹配。

每个 SP-041 Task 的开工顺序必须是：`internal reuse audit -> public GitHub reuse audit -> license gate -> minimal implementation plan -> code`。

首轮结果冻结在 `docs/engineering/PUBLIC_GITHUB_REUSE_AUDIT_V1.0.md`。重点候选包括 Nexscope MIT 项目、Sorftime MIT CLI、scikit-learn BSD 组件；无许可证或限制许可的相似选品项目仅作参考。

## 2. 统一工程纪律

每一个 Task 都必须：

1. 从 required baseline 创建 dedicated branch。
2. 开始前记录 HEAD、branch、workspace/staging、Python/pytest、focused/full-suite baseline。
3. 先做 reuse audit；优先复用 `JsonContract`、`canonical_json`、`deterministic_id`、Evidence/Provenance、`MetricContextEnvelope`、V0.2 distributions、provider-neutral delivery/pipeline。
4. 每个 Task 只做自己的 acceptance gate，不提前开始下一 Task。
5. 自动测试必须 `0 external network calls`。
6. live provider 调用只有任务明确授权时才允许，并必须有 hard budget。
7. 用户真实模板/数据不进入 fixture；仓库只保存合成/脱敏/最小 fixture。
8. 完成后运行 focused tests、affected regressions、full pytest、`git diff --check`、staged diff、secret scan。
9. Completion report 必须包含：baseline、files changed、tests、network/API accounting、known limitations、commit/push/workspace、primary verdict。

---

# TASK-SP-041A — Template Contract Freeze & Formula Audit

Branch: `codex/task-sp-041a-template-contract-freeze`

## Objective

把用户模板从“参考 Excel”升级为版本化、可 fail-closed 的 Operator Template Contract。该任务只做合同、公式、依赖审计，不写新业务逻辑。

## Scope

- 冻结 11 个 visible Sheet：综合说明、类目、市场调研、竞品数据、不同维度分析、分析模型对比、top100—日单量分析、产品初步筛选范围、价格核算、样品类型、竞品收集。
- 冻结 4 个 hidden Sheet：自动化配置、原始数据源、关键词1—数据源、自动化辅助。
- 冻结 `原始数据源` 66 个表头名称及语义状态：`CORE / OPTIONAL / OUT_OF_SCOPE`。
- 记录 formula census：市场调研 ≈ 3；不同维度分析 ≈ 1,150；自动化配置 ≈ 2；关键词1—数据源 ≈ 961；分析模型对比 ≈ 108；自动化辅助 ≈ 24,514。
- 建立 formula fingerprint / dependency inventory。
- 提取所有硬编码业务阈值：价格带、Review 分档、留评率、FBA、上架时间、新品窗口、类目语义规则等。
- 分类：`REUSE_AS_FORMULA / MOVE_TO_CONFIG / IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL / DEPRECATED`。
- 明确 `价格核算` 当前为 value-only，不把现有结果当计算合同。
- 新增模板合同文档和机器可读 schema。

## Forbidden

- 不修改 Production Pipeline。
- 不修改 Market Report V0.1/V0.2 业务语义。
- 不重写模板公式。
- 不提交用户 998 行数据/原始模板。
- Sorftime/XiYou live calls = 0。

## Required tests

- sheet names/order/visible state contract。
- 66 header contract。
- template schema fingerprint determinism。
- formula census/fingerprint。
- hard-coded threshold inventory deterministic。
- network construction denied。

## Acceptance gate

`PASS — TEMPLATE_CONTRACT_V1_FROZEN` requires: 11+4 Sheet contract frozen；66-field contract frozen；formula inventory reproducible；hard-coded business rule inventory auditable；raw user data not committed；affected/full regressions no new failure；branch committed/pushed clean。

---

# TASK-SP-041B — SellerSprite Import Contract & Adapter

Branch: `codex/task-sp-041b-sellersprite-import-adapter`

## Objective

让 SellerSprite XLSX/CSV 手动导出成为类目级 Market Dataset 的主要输入入口。

## Scope

- 新增 provider-neutral `MarketImportRequest` / `ImportedMarketDataset`（命名以 reuse audit 为准）。
- 字段按 **header name** 映射，不依赖列号。
- 支持列顺序随机化、可选列缺失、多余未知列诊断。
- 支持 `50–1500 Listings`；超过上限明确 fail，不静默截断。
- ASIN 验证、重复检测、空行过滤；parent/variation evidence 不自动扩展 requested cohort。
- 记录 source type、source filename、SHA-256、source row、imported_at、marketplace/category、source semantics。
- 数值/单位规范化：USD、百分比、日期、重量、尺寸。
- `missing / blank / NA / parse failure != 0`。
- SellerSprite 月销量、销售额等标记为 `THIRD_PARTY_ESTIMATE`，不得表述为 Amazon 官方销量。
- 增加显式 Operator/CLI 入口，例如 `--market-import <file>`；不得与 live provider 模式隐式混用。

## Forbidden

SellerSprite API = 0；Sorftime credential read = 0；不改变 Buyer Need/Competition/Opportunity 现有公式；不把 SellerSprite 毛利率当成最终利润真值。

## Required tests

66-field complete fixture；missing/shuffled/extra columns；invalid/duplicate ASIN；blank row；percent/date/NA/invalid numeric；1500-row boundary；source ID determinism；external local replay using current 998-row file（not committed）；network deny。

## Acceptance gate

`PASS — SELLERSPRITE_IMPORT_V1` requires: current 998-row dataset imports successfully；shuffled columns produce same semantics；missing data never becomes zero；imported dataset can feed Product Map stage；XiYou/Sorftime existing paths unchanged；branch committed/pushed clean。

---

# TASK-SP-041C — Listing Attribute Parser & CategoryRulePack

Branch: `codex/task-sp-041c-listing-attribute-parser`

## Objective

通过代码把 Listing 详细参数/Title/SKU 转换为可跨类目计算的标准产品属性；类目规则必须外置。

## Scope

- Parser for `Key:Value | Key:Value` 详细参数。
- 通用属性至少包含：`product_form / mounting_or_usage_mode / material_family / size_or_capacity / pack_count / use_case / compatibility / operation_mode / power_mode / special_features / color / dimensions/weight`。
- 证据优先级：structured params > dedicated fields > SKU > Title > AI inference。
- 每个属性带 `evidence_status / confidence / source field or snippet`。
- 严格区分 Pack/Piece/Set 与 Pocket/Tier/Shelf/Layer。
- `No Drilling` 单独出现不得自动判为 adhesive。
- 新增 versioned `CategoryRulePack`。
- 当前 Shower Caddies 规则从模板自动化配置迁移为脱敏 rule fixture。
- AI 只能解决歧义或给 cluster 命名，不能覆盖明确结构化事实。

## Forbidden

不把“便携/壁挂/伸缩杆”做成全局枚举；不为 Shower Caddies 修改通用 parser 逻辑；Sorftime enrichment = 0。

## Required tests

mesh portable / adhesive / hanging / tension pole / floor standing；material synonym families；pack-vs-pocket collision；`No Drilling` negative case；casing/order determinism；second-category synthetic fixture without code change；ambiguous conflict → `REVIEW_REQUIRED`。

## Acceptance gate

`PASS — CROSS_CATEGORY_LISTING_PARSER_V1` requires: current template high-frequency products classify deterministically；CategoryRulePack externalized；second category uses same generic code；ambiguity never silently picks a false fact；branch committed/pushed clean。

---

# TASK-SP-041D — Product Map, Route Discovery & Opportunity Metrics

Branch: `codex/task-sp-041d-product-map-route-opportunity`

## Objective

从“市场商品池”自动形成产品路线（Product Archetypes），并在路线层计算结构性机会。

## Scope

- 建立 `ProductMapRecord`：ASIN + normalized attributes + sales/price/review/age/seller evidence。
- route membership 由确定性属性规则/相似度决定；AI 不负责成员归属。
- 路线指标：Route Sales Share、Route Listing Share、Demand Efficiency、aggregate MoM/YoY、new-product sales share/efficiency、Review barrier、price opportunity、brand/product/seller concentration、content adoption（有数据时）。
- 聚合 growth：用行级 current sales + growth rate 还原上期销量，再聚合；invalid/-100%/missing 降 coverage，不硬算。
- 每条路线输出 `coverage / limitations / evidence refs`。
- “差异化空间”拆成 structural opportunity（本 Task）与 user-problem opportunity（后续 Sorftime/Review）。
- 候选 3–5 路线加入 diversity constraint，避免近义路线重复。
- 路线分数必须拆维度输出，不允许单个黑盒总分作为唯一依据。

## Forbidden

Demand Efficiency 不得叫“利润机会”；不根据少量评论推全市场需求；不创建 Direct Competitor Set；不修改 frozen Opportunity Score 语义。

## Required tests

sales/listing shares sum checks；growth reconstruction and missing coverage；concentration formulas；input permutation determinism；diversity dedupe；all-unavailable / partial evidence；current 998-row external replay。

## Acceptance gate

`PASS — PRODUCT_MAP_ROUTE_OPPORTUNITY_V1` requires: current 998 rows form multiple explainable routes；every route has members/evidence/coverage/metrics；3–5 candidate routes materially different；missing growth/metrics do not become zero；outputs ready for template/AI consumption。

---

# TASK-SP-041E — Representative ASIN Selection & Direction State Machine

Branch: `codex/task-sp-041e-representative-asin-direction-gate`

## Objective

保证正确选品时序：先研究代表性商品，产品方向锁定后才定义直接竞品。

## Scope

State machine: `MARKET_DISCOVERY → ROUTE_CANDIDATES → ROUTE_ENRICHMENT → DIRECTION_PROPOSED → DIRECTION_LOCKED → DIRECT_COMPETITOR_REVIEW`。

Representative roles per route（默认3–5）：`TOP_SELLER / TYPICAL_MEDOID / NEW_OR_LOW_REVIEW_PERFORMER / PRICE_BOUNDARY_OR_PREMIUM / optional ANOMALY`。每个选择输出 `reason_codes`。

Direct Competitor builder requires state=`DIRECTION_LOCKED`、locked product archetype、key attributes、price target/range、use case / buyer need boundary。

必须兼容现有：Product Directions = `HYPOTHESIS`；Competitor Shortlist = `REVIEW_ORDER_NOT_RANK`。

## Forbidden

未锁定方向不得称“直接竞品”；Representative ASIN 不是商品排名；Sorftime live calls = 0。

## Acceptance gate

`PASS — REPRESENTATIVE_ASIN_DIRECTION_GATE_V1` requires: each route has explainable representatives；member-shortage fallback deterministic；Direct Competitor builder fails closed before `DIRECTION_LOCKED`；direction changes invalidate/recompute direct competitors。

---

# TASK-SP-041F — 30% Gross-Margin Procurement Ceiling

Branch: `codex/task-sp-041f-procurement-ceiling`

## Objective

把当前 value-only 的“价格核算”升级为正式代码模型。

## Business formula

```text
MaxProcurementUSD
= SellingPriceUSD × (1 − TargetGrossMargin)
  − ReferralFeeUSD
  − FBAFeeUSD
  − OtherPlatformFeesUSD

MaxProcurementCNY
= max(0, MaxProcurementUSD × FX_USD_CNY)

UnitProcurementCeilingCNY
= MaxProcurementCNY ÷ PackCount
```

If `MaxProcurementUSD <= 0` → `目标不可达`。

## Scope

`EconomicsConfig`: target_gross_margin default `0.30`、category referral fee rate / override、FX USD→CNY、other platform fees、rounding policy。

Inputs: selling price、FBA fee、Pack、referral rate/fee、optional human `EstimatedSupplierCost`。

Outputs: set/unit procurement ceiling CNY、target feasibility、coverage/limitations、safety gap、`可达 / 偏紧 / 不可达 / 缺数据`。

MVP明确不含：头程、广告、退货损耗；这些属于后续净利模型。

## Forbidden

SellerSprite 毛利率不得作为最终采购成本真值；缺 FBA 不得当0；referral fee 不得对所有类目盲目写死同一个值。

## Acceptance gate

`PASS — PROCUREMENT_CEILING_30PCT_V1` requires: code/JSON/Excel formula semantics一致；missing data → PARTIAL；negative ceiling → 目标不可达；Pack>1 unit cost correct；manual supplier estimate comparison works。

---

# TASK-SP-041G — 11-Sheet Operator Template Delivery

Branch: `codex/task-sp-041g-operator-template-delivery`

## Objective

把目标 Excel 正式接为系统 Operator Delivery，不新造一份不同结构的报表。

## Scope

- 读取 SP-041A Template Contract。
- 安全刷新 `原始数据源`：只覆盖数据区域，不删除列/Sheet/公式结构。
- 刷新 `自动化配置`、`关键词1—数据源`、`自动化辅助`。
- 4 hidden sheets 在最终 artifact 中保持 hidden。
- 复用 whitelisted formula；硬编码阈值迁移为 config/code。
- 关键指标代码计算，并与 Excel mirror 做 parity check。
- 自动生成综合说明、产品初步筛选范围、样品类型（HYPOTHESIS）、竞品收集（遵守 direction state gate）。
- 价格核算使用 SP-041F 新模型，不复用旧 value-only 结果。
- 输出 `operator_market_report.xlsx / market_analysis_snapshot.json / run_manifest.json`。

## Forbidden

不依赖用户打开 Excel 后才能得到 JSON/AI 关键结果；不改变 11 visible Sheet 名称；不显示 4 hidden sheets 给普通用户；用户原模板/真实数据不提交 Git。

## Required tests

11 visible + 4 hidden contract；formula error scan；50 / 998 external / 1500 rows；code-vs-formula parity；workbook structural reopen/save validation。

## Acceptance gate

`PASS — OPERATOR_TEMPLATE_V1_DELIVERY` requires: current real template can be regenerated from imported data；key market metrics match contracted definitions；hidden sheet contract preserved；price sheet uses new procurement model；workbook valid and operator-readable。

---

# TASK-SP-041H — Targeted Sorftime Enrichment Planner

Branch: `codex/task-sp-041h-targeted-sorftime-enrichment`

## Objective

把 Sorftime 限制为“按需深挖”，并在系统里显式控制成本。

## Scope

新增 `EnrichmentPlan`：ASIN、route_id、representative/direct-competitor role、requested operations、max operations、reason。

Default route research budget: max representative ASIN=`25`（可配置）；all-market imported ASIN enrichment=`0 by default`。

复用已接受 Sorftime contracts：ProductRequest、ASINRequestKeyword。

关键词证据继续保持既有边界：approximately 30-day / first-three-pages / incomplete universe。

Review / Customer Say 若要接入，必须先做独立 provider-contract acceptance；不得在本 Task 顺带扩大未证明语义。

必须支持完全 offline 运行：Sorftime 缺失/失败时，SellerSprite 基础市场报告仍能成功，只是深度 evidence 标 PARTIAL/NOT_ATTACHED。

## Forbidden

不使用 CategoryProducts 自动抓 500–1000 商品作为 MVP 默认路径；不深挖全部 imported ASIN；不引入 sponsored semantics；不隐藏 API usage。

## Acceptance gate

`PASS — TARGETED_SORFTIME_ENRICHMENT_V1` requires: only representative / locked direct competitors are eligible；hard API budget enforced；usage accounting visible；provider failure does not destroy base report；no automatic fallback。

---

# TASK-SP-041I — Full E2E, Cross-Category & Release Acceptance

Branch: `codex/task-sp-041i-full-template-acceptance`

## Objective

证明系统不仅复刻当前 Shower Caddies，还能在换类目后自动形成不同的产品路线。

## Acceptance scenarios

### Scenario 1 — Current real template replay

998 Listings Shower Caddies。SellerSprite import → Product Map → routes → candidate directions → procurement ceiling → 11-Sheet output。对比原模板的 market totals、distributions、concentration、Top100、route structure、price analysis。

### Scenario 2 — Second category

至少一个不同真实类目。通用代码不变，仅替换/生成 `CategoryRulePack`。必须生成与 Shower Caddies 不同的产品路线。若开发期没有第二真实文件，可先用 synthetic fixture；正式 release 前要求真实第二类目。

### Optional controlled Sorftime acceptance

仅对 representative ASIN 做一次受控 enrichment；hard budget / usage / no fallback。

## Required validation

all SP-041 focused tests；existing Sorftime/XiYou regressions；Canonical/Data Cleaning；Buyer Need/Competition/Opportunity/Product Intelligence frozen regressions；V0.1/V0.2 reports/delivery；full pytest；determinism rerun；1500-row performance sanity；formula error scan；`git diff --check` / staged diff / secret scan。

## Final acceptance

`PASS — MARKET_ANALYSIS_TEMPLATE_V1_FULL_ACCEPTANCE` requires: current 998-row real dataset produces operator-readable 11-Sheet report；second category produces different valid Product Archetypes without generic-code edits；route → representative ASIN → proposed direction → locked direction → direct competitor sequence enforced；30% procurement ceiling correct and auditable；Sorftime optional enrichment budget-controlled and non-blocking；no raw user data/template leakage；no new regressions；branch committed/pushed clean。

---

## 最快可用路径

`SP-040G → SP-041A → SP-041B → SP-041C → SP-041D → SP-041F → SP-041G`

达到这里，即使 Sorftime 完全关闭，也可以实现：**上传 SellerSprite 市场数据 → 自动清洗 → Product Map → 产品路线 → 市场机会 → 30%采购成本上限 → 11-Sheet Excel**。

然后：`SP-041E → SP-041H → SP-041I`，补上代表性 ASIN、Sorftime 深挖、用户需求/痛点、方向锁定后的直接竞品，以及跨类目正式验收。

## 工程时间估算（非承诺）

- 离线模板 MVP：约 `2–4` 个专注开发工作日量级，主要风险是导入脏数据、公式依赖和 CategoryRulePack 抽象。
- Sorftime 深挖 + 跨类目验收：再约 `1–3` 个工作日量级，主要取决于 Review/Customer Say 合同和第二类目真实数据。
