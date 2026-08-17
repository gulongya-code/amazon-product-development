# Amazon Product Development System — Existing Architecture Audit V1

**审计日期：** 2026-08-13（Asia/Shanghai）  
**审计模式：** READ ONLY（除本报告外无写入）  
**证据范围：** 当前工作区、当前可见工具契约、既有发现报告  
**最终结论：** **B. EVOLVE CURRENT ARCHITECTURE（有条件、保守结论）**  
**结论置信度：** 低——当前工作区没有产品系统实现、数据或有效 Git 历史可供验证

> 重要解释：此处的 `EVOLVE CURRENT ARCHITECTURE` 是风险控制决策，不是对现有实现的技术背书，也不是开始下一阶段开发的授权。由于没有观察到现有系统，不能合理证明需要 `PARTIAL REBUILD` 或 `FULL REBUILD`；同时，新产品开发流程和架构原则已经明确改变，不能把 `KEEP CURRENT ARCHITECTURE` 当作目标方向。正确动作是保持未知实现不动，先恢复证据，再以旁路、可回滚方式演进。

## 0. 审计范围、方法与证据等级

### 0.1 允许与禁止

本次仅执行目录盘点、文本读取、文件类型/哈希检查、Git 有效性检查和当前工具契约检查。没有修改生产代码、数据、数据库、Excel、schema、配置、目录结构或 Git 历史；没有移动或删除文件；没有 commit、push、migration 或下一阶段实现。唯一新增文件是本报告。

### 0.2 观察到的审计边界

| 项目 | 实际观察 |
|---|---|
| 工作区普通文件 | 1 个：`ARCHITECTURE_DISCOVERY_REPORT.md` |
| 源码、配置、schema、migration | 0 个 |
| 测试与 fixture | 0 个 |
| Excel / CSV / TSV | 0 个 |
| Parquet / DuckDB / SQLite / SQL | 0 个 |
| `.git` | 目录存在但为空；当前目录不是有效 Git 仓库 |
| `.agents` | 空目录 |
| 既有报告 | 2026-08-13 的 Xiyou 架构发现报告；它也记载当时缺少系统 checkout 和数据 |
| 本次 Xiyou 可见性 | 当前会话可见 43 个 `xydc_mcp` 工具契约；没有执行数据查询 |

### 0.3 证据等级

| 等级 | 定义 | 本报告用法 |
|---|---|---|
| OBSERVED | 可由当前文件、目录、命令结果或工具 schema 直接复核 | 文件数量、Git 无效、工具名称/参数契约 |
| REPORTED | 仅由既有报告陈述，本次没有底层材料重验 | 旧任务当时看不到 Xiyou、未拿到系统 checkout |
| PROPOSED | 面向新目标的设计建议，不代表已实现 | 目标架构、迁移顺序、接口边界 |
| UNKNOWN / NOT OBSERVED | 当前证据不能回答 | 所有现有实现状态、SellerSprite 字段流、算法与数据质量 |

`NOT OBSERVED` 不等于“不存在”或“未实现”。在没有仓库和样本的情况下，把未知写成否定结论同样属于猜测。

## 1. Executive Summary

本轮不能完成“现有架构事实审计”的核心验证，因为应被审计的代码、数据模型、Excel 样本、数据库、测试和 Git 历史均未出现在工作区。现有唯一材料是一份发现报告，而不是系统实现。因此：

1. 24 个重点能力全部只能标为 `UNKNOWN / NOT OBSERVED`，不能认定已完成，也不能认定缺失。
2. SellerSprite importer、原始字段、sheet、Raw/Standard/Derived 流转、Parent/Child、销量/收入、BSR、关键词与历史回归样本均不可验证。
3. 子体销量分摊算法和旧 Opportunity/Candidate Score 均不可验证；没有证据支持继续优化、启用、冻结或删除某个具体实现。
4. 当前会话确实暴露了 43 个 Xiyou MCP 工具的输入契约和描述，说明未来 adapter capability 可以覆盖 ASIN、变体、关键词、流量/排名、订单趋势、BSR、类目市场规模等表面能力。但是没有调用返回结果，字段类型、缺失值、时间口径、估算方法、父子体去重、分页稳定性和授权范围仍是 `UNVERIFIED`。
5. 新目标明确要求 provider independence、Fact → Insight → Decision 分层和字段级 provenance。无论旧实现如何，这三项都应成为演进门槛，但不能据此直接推定旧架构需要重写。
6. 最终选择 **B. EVOLVE CURRENT ARCHITECTURE**：冻结破坏性变更，在恢复真实 checkout 和代表性样本后，先建立 provider-neutral contract、canonical model、provenance 和 quality gates，再逐个消费者迁移。只有届时发现核心模块与新边界不可分离、且旁路迁移成本高于替换时，才升级为 `C. PARTIAL REBUILD`。当前证据不支持 `D. FULL REBUILD`。

## 2. Current Architecture

### 2.1 可验证的当前形态

当前工作区可验证形态只有：

```text
亚马逊市场分析/
├── .agents/                         # 空目录
├── .git/                            # 空目录；不是有效 Git 仓库
└── ARCHITECTURE_DISCOVERY_REPORT.md # 既有发现报告
```

没有可建立依赖图的包、服务、入口、任务、数据库定义或 UI。因此“当前架构”本身为 `UNKNOWN`。

### 2.2 无法验证的架构问题

- 单体、分层单体、任务脚本或服务化结构：`UNKNOWN`
- 运行语言、框架、部署形态、调度方式：`UNKNOWN`
- 数据库/对象存储/文件布局：`UNKNOWN`
- Raw / Standard / Derived 是否为正式分层：`UNKNOWN`
- UI 与分析层是否共享模型：`UNKNOWN`
- Provider 字段是否进入核心模型：`UNKNOWN`
- LLM 是否被调用、如何约束：`UNKNOWN`
- 产品机会的生命周期和决策记录：`UNKNOWN`

### 2.3 既有报告的使用限制

`ARCHITECTURE_DISCOVERY_REPORT.md` 可证明一次先前审计也缺少 system checkout，并提出过条件式目标架构。它不能证明任何生产模块实际存在或不存在，也不能作为代码级模块库存替代品。本次还观察到旧报告所述“Xiyou 不可见”已不再适用于当前会话：现在工具契约可见，但实际响应仍未验证。

## 3. Current Data Flow

### 3.1 现有流转

没有 importer、表、文件、任务定义或日志，因此无法画出真实数据流：

```text
SellerSprite / 其他 provider
    ── UNKNOWN ──> Raw
    ── UNKNOWN ──> Standard
    ── UNKNOWN ──> Derived / Analysis
    ── UNKNOWN ──> UI / Score / Decision
```

所有箭头、持久化介质、批次边界、重跑语义、幂等性和失败处理均为 `UNKNOWN`。

### 3.2 需要恢复后验证的链路证据

每一条真实链路至少要能回答：入口文件/任务、输入文件指纹、provider、marketplace、snapshot、字段映射版本、转换代码版本、输出表/文件、质量状态、行数变化、拒绝记录、下游消费者和重跑结果。缺少其中任一项，都不能宣称端到端可追溯。

## 4. SellerSprite Excel Pipeline Audit

### 4.1 专项结论

工作区没有 `.xlsx`、`.xls`、`.csv`、`.tsv`，也没有 importer 或 mapping 文件。SellerSprite 管线审计状态为 **BLOCKED BY MISSING EVIDENCE**，不是“未实现”。

| 要求 | 审计结果 | 所需证据 |
|---|---|---|
| 1. 实际读取过的 Excel 类型 | UNKNOWN | 历史样本、导入日志、fixture、文件指纹清单 |
| 2. 文件名 / sheet | UNKNOWN | 样本目录和 importer sheet 选择逻辑 |
| 3. 原始字段 | UNKNOWN | 未改动的表头、sheet schema 快照 |
| 4. 字段映射 | UNKNOWN | mapper、映射表、版本记录 |
| 5. 进入 Raw 的字段 | UNKNOWN | Raw schema/Parquet schema/落库 DDL |
| 6. 进入 Standard 的字段 | UNKNOWN | canonical/standard schema 与转换代码 |
| 7. 进入 Derived 的字段 | UNKNOWN | 派生公式、任务、输出 schema |
| 8. Parent / Child 处理 | UNKNOWN | ASIN 关系模型、聚合与去重测试 |
| 9. Sales / Revenue 处理 | UNKNOWN | 单位、币种、周期、聚合口径、公式 |
| 10. BSR 处理 | UNKNOWN | 类目路径、排名类型、snapshot 逻辑 |
| 11. Keyword 是否来自 SellerSprite | UNKNOWN | 关键词导入入口与来源字段 |
| 12. 真实回归样本 | NOT OBSERVED | 脱敏 fixture 或只读样本库 |
| 13. 样本规模 | UNKNOWN | 文件数、sheet 数、行列数、日期和站点 |
| 14. 是否可重新运行 | UNKNOWN | 环境锁定、命令、依赖、golden output |
| 15. 特有字段泄漏 | UNKNOWN | 核心模型/分析代码的字段引用扫描 |

### 4.2 能否改造成 provider adapter

**结论：POTENTIALLY YES，但 UNVERIFIED。** 没有实现可评估可拆分性。只有满足以下验收条件，才可判定为可改造而非重写：

- 读取、sheet 识别、列别名和 provider 清洗可以收敛在 `providers/sellersprite/`；
- mapper 输出 provider-neutral canonical records；
- Standard 与 Analysis 不 import SellerSprite 类型、不引用 SellerSprite 列名；
- 原始值和来源字段保持可追溯；
- provider 新增字段不会无意改变核心分析；
- 真实历史文件可生成可复现的 golden outputs。

建议的责任边界（仅设计建议）：

```text
providers/
└── sellersprite/
    ├── importer     # 文件识别、sheet 读取、原始单元格解析
    ├── schema       # provider 输入版本和列别名
    ├── mapper       # provider record -> canonical record
    └── capability   # 可提供的实体、指标、粒度、站点、历史范围
```

`schema` 不应成为全局 schema；`mapper` 不应计算市场洞察；`capability` 不应把“工具声称支持”写成“当前账号/样本已验证”。

### 4.3 Excel 恢复后的只读验证协议

1. 对每个样本计算指纹，不改文件。
2. 记录文件名、大小、修改时间、sheet、used range、表头和行数。
3. 将空白、重复表头、合并单元格、公式、文本数字、日期/币种/百分比逐项剖析。
4. 用 importer 只读执行，输出到隔离临时位置；比较重复运行结果。
5. 建立 `source_field -> raw_field -> canonical_field -> derived_field -> consumer` 映射矩阵。
6. 对销量、收入、BSR、Parent/Child、关键词各抽样追踪至少一条完整 lineage。

## 5. Module Inventory

没有生产模块可列出。以下库存用于逐项回应审计范围；`module / file` 均未观察到。

| # | 能力 / 预期模块 | module / file | actual status | dependencies / input / output |
|---:|---|---|---|---|
| 1 | SellerSprite Excel / CSV Import | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 2 | Excel schema / 字段映射 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 3 | Raw Layer | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 4 | Standard Layer | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 5 | Derived / Analysis Layer | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 6 | Parquet | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 7 | DuckDB | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 8 | ASIN / Parent / Variant 模型 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 9 | 商品分类 taxonomy | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 10 | 产品规格解析 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 11 | BSR | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 12 | 销量 / Revenue | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 13 | 子体销量逻辑 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 14 | Keyword 数据 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 15 | Keyword Analysis | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 16 | Market Analysis | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 17 | Competitor Analysis | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 18 | Candidate / Opportunity Score | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 19 | UI | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 20 | LLM / AI | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 21 | 数据质量机制 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 22 | source / snapshot / provenance | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 23 | 测试与回归样本 | NOT OBSERVED | UNKNOWN | UNKNOWN |
| 24 | SellerSprite 历史真实 Excel | NOT OBSERVED | UNKNOWN | UNKNOWN |

## 6. KEEP / MODIFY / FREEZE / REMOVE Matrix

### 6.1 处置规则在证据缺失时的应用

用户要求只能使用四种决策。对没有文件的“具体模块”做 KEEP/MODIFY/FREEZE/REMOVE 会制造不存在的审计精度。因此本表按当前可观察资产和待恢复模块类别给出**临时决策**，所有代码级决策必须在 checkout 恢复后重审。

| module / file | current purpose | implementation | input → output | decision | reason | migration implication | risk |
|---|---|---|---|---|---|---|---|
| `ARCHITECTURE_DISCOVERY_REPORT.md` | 保存先前发现结论 | 已存在，可读取 | 先前盘点 → 报告 | KEEP | 有历史审计价值 | 作为时间点证据，不作为生产真相 | 旧结论可能过期 |
| 空 `.git/` | 名义 Git 目录 | 无效/无对象 | 无 | FREEZE | 不应在审计中修复或删除 | 由 owner 提供正确 checkout | 易被误认成仓库 |
| 空 `.agents/` | UNKNOWN | 空 | 无 | FREEZE | 无证据支持用途或删除 | 不影响迁移 | 用途未知 |
| 未提供的生产模块 | UNKNOWN | NOT OBSERVED | UNKNOWN | FREEZE | 缺证据时禁止改动 | 恢复后逐文件审计 | 延误，但避免误删 |
| 潜在 SellerSprite importer | provider 文件导入（假定范围） | UNKNOWN | Excel/CSV → UNKNOWN | MODIFY | 若存在，应隔离 provider 细节 | 保持输入兼容，新增 canonical 输出 | 字段语义/兼容回归 |
| 潜在 Raw layer | 保存来源事实（目标职责） | UNKNOWN | provider payload → raw | MODIFY | 必须补 provenance/immutability 才符合目标 | 旁路加入 envelope 与批次标识 | 存储增长、隐私 |
| 潜在 Standard layer | provider-neutral facts（目标职责） | UNKNOWN | raw → canonical | MODIFY | 新原则要求 provider independence | 版本化映射和双写对账 | 语义漂移 |
| 潜在 Derived/Analysis | 派生指标和分析 | UNKNOWN | canonical → metrics | MODIFY | 必须区分 fact/derived/estimate | 输出带 calculation/version/quality | 下游兼容 |
| 潜在子体销量分摊 | 父销量向子体估算 | UNKNOWN | parent metric → child estimates | FREEZE | 未证明算法、授权或质量门 | 若存在，先阻断其作为事实传播 | 历史报告变化 |
| 潜在总分决策 | 机会综合分数 | UNKNOWN | metrics → score/decision | MODIFY | score 只能是 evidence，不得替代决策 | 解耦 score 与 state/decision | 用户行为依赖旧总分 |
| 潜在 LLM 自由文本链路 | 洞察生成 | UNKNOWN | facts? → narrative? | MODIFY | 需结构化输入输出和引用 | 增加 fact package/contract | 幻觉、不可复核 |
| 潜在 provider-specific 分析代码 | 直接消费供应商字段 | UNKNOWN | provider schema → analysis | MODIFY | 与 provider independence 冲突 | 通过 adapter/canonical strangler 迁移 | 隐藏耦合 |

**REMOVE：本轮无建议。** 没有依赖、调用、运行或替代证据，任何 REMOVE 建议都不合格。

## 7. Existing Data Model Audit

### 7.1 现有模型

未观察到 class、DDL、JSON schema、Parquet schema、DuckDB catalog 或字段文档，故为 `UNKNOWN`。

### 7.2 新模型的最低必要实体（PROPOSED）

| Entity | 关键标识/关系 | 说明 |
|---|---|---|
| ProviderObservation | observation_id, provider, capability, collected_at | 一次外部观察，不等同于规范事实 |
| SourceArtifact | artifact_id, file/API request, hash, snapshot_date | Excel/API 原始来源 |
| FieldEvidence | value, source_field, source artifact, quality | 字段级可追溯证据 |
| Marketplace | country/site/currency/timezone | 禁止隐式站点 |
| Product / ASIN | asin, marketplace | 子体/可售商品事实 |
| ProductFamily / Parent | parent_asin, relation interval | 关系带观察时间和来源 |
| VariantAttribute | dimension/value/unit | 规格标准化并保留原文 |
| CategoryNode / Assignment | taxonomy/version/path | BSR 必须引用具体类目节点 |
| Keyword | normalized + locale + marketplace | 保留原始 query |
| DemandIntent / UseCase / Need | hypothesis/evidence/status | 属 Insight 层，不伪装成 Fact |
| MetricObservation | metric, value, unit, period, grain | 搜索、销量、收入、价格、BSR 等 |
| DerivedMetric | formula/version/input refs | 可重复计算 |
| Estimate | method/version/assumptions/confidence | 与 provider fact 和 derived 分开 |
| Opportunity | state, scope, owner | 产品开发工作区主实体 |
| Evidence / Inference / Hypothesis / Unknown | typed claim records | 机会诊断的认识边界 |
| ProductConcept / BusinessCase / SupplierValidation | versioned artifacts | 每阶段可审计 |
| Decision | GO/HOLD/NO-GO, rationale, approver | 人类最终决策和历史 |

### 7.3 provenance 最低字段

`value`, `source`, `source_field`, `snapshot_date`, `collected_at`, `collection_method`, `confidence/quality_status` 是最低要求，还建议加入 `marketplace`, `entity_grain`, `metric_period`, `unit/currency`, `provider_schema_version`, `mapper_version`, `raw_artifact_hash`, `transformation_run_id`。

## 8. Provider Coupling Audit

### 8.1 现有耦合

没有核心代码和 schema，无法扫描 SellerSprite 列名、Xiyou payload 字段或 API DTO 引用。结果：`UNKNOWN`。

### 8.2 当前可验证的 Xiyou contract 表面

本次会话可见 43 个工具契约。以下是按描述归纳的 capability groups；这只证明“工具 schema 对当前会话可见”，不证明账号授权、数据质量或运行结果：

- ASIN 基础信息、标题/主图变化、价格/评分趋势；
- ASIN 订单近 30 天与月趋势；
- ASIN 流量、关键词、排名和流量趋势；
- ASIN BSR 趋势和变体关系；
- 关键词基础指标、ABA 周趋势、关键词反查 ASIN、月度竞争格局；
- 类目、品牌、价格段、评分分布、关键词、季节性、市场规模、排行榜；
- 类目接口显式出现 `child` / `parent` 聚合能力；部分接口需要 resourceId。

仍为 `UNVERIFIED`：实际响应 schema、字段类型和 nullability、精确时间/销量/收入口径、估算来源、父子体完整性、历史修订、货币处理、分页/限流、授权范围、source timestamp、稳定 ID、服务版本和 SLA。本次没有调用市场数据接口，因此没有把描述当成事实数据。

### 8.3 必要隔离

```text
External provider
  -> Provider Adapter (provider DTO, auth, pagination, retries)
  -> Raw Observation Envelope (immutable reference)
  -> Canonical Mapper (versioned)
  -> Canonical Fact Store
  -> Derived / Estimate / Insight
  -> Opportunity evidence package
```

核心层只依赖 `ProviderAdapter` 和 canonical contracts；不能依赖 `SellerSprite` sheet 名、中文表头或 Xiyou tool DTO。Capability Matrix 应按 provider + marketplace + entity + metric + grain + history + quality 记录，并允许 `UNKNOWN`。

## 9. Fact / Derived / Estimate Boundary Audit

### 9.1 现有边界

没有数据字典、公式或代码，无法判断当前是否混用。状态：`UNKNOWN`，风险：高。

### 9.2 建议分类规则

| 类型 | 含义 | 示例 | 必须记录 |
|---|---|---|---|
| RAW OBSERVATION | provider/file 原样提供 | SellerSprite 单元格、Xiyou response field | provider、source_field、snapshot、raw ref |
| CANONICAL FACT | 仅做确定性标准化 | 货币代码、ASIN、标准日期、明确单位转换 | mapper/version/input ref |
| DERIVED | 从事实确定性计算 | 集中度、份额、增长率、财务算式 | formula/version/input refs |
| PROVIDER ESTIMATE | provider 声称/估算的数据 | provider 销量/收入估计 | provider method 若未知则标 unknown |
| INTERNAL ESTIMATE | 系统算法估算 | 父销量向子体分摊 | method/version/assumption/confidence |
| INSIGHT / HYPOTHESIS | 解释性结论 | 意图、场景、需求、差异化假设 | evidence refs/LLM version/confidence |
| DECISION | 人类认可的动作 | GO/HOLD/NO-GO | approver/time/rationale/history |

禁止仅因字段名叫 `sales` 就把它当作确定事实；其真实类别取决于来源方法、周期和粒度。

### 9.3 子体销量估算专项

当前没有发现算法文件、配置、输出或测试，因此以下问题均为 `UNKNOWN`：父体销量是否分摊、分摊公式、是否正式启用、authorization/quality gate、下游是否当真值。

**临时处置：FREEZE（如果实现存在）。** 这里的 FREEZE 指不再优化或扩大使用；不是关闭生产逻辑。恢复代码后优先检查：

1. 父体值是 provider 聚合值、子体和，还是单独估算；
2. 权重来自 reviews、rank、price、variation availability 或其他 proxy；
3. 权重日期是否与销量周期一致；
4. 缺失子体/断货/新增变体如何处理；
5. 是否守恒、是否负值、是否双计；
6. 输出是否明确标记 `INTERNAL_ESTIMATE`；
7. UI、score、business case 是否将估算当事实。

未经这些验证，不得把分摊值用于 GO/HOLD/NO-GO 的决定性证据。

### 9.4 旧 Opportunity / Candidate Score 专项

没有发现需求、竞争、利润、趋势或综合分数代码/配置/输出，故全部 `UNKNOWN`。若恢复后发现“单一总分直接生成产品开发结论”，处置应为 `MODIFY`：保留可解释组件作为证据，分数记录版本、权重、输入和不确定性；Opportunity Diagnosis 与 Decision 独立存在，最终决定由人确认。

## 10. Missing Capabilities

下表的“缺失”严格表示**当前证据中没有观察到**，不等于生产系统一定没有。

| Capability | observed status | target priority | acceptance signal |
|---|---|---:|---|
| Provider Registry | NOT OBSERVED | P0 | 注册 provider/version/marketplace/capability |
| Provider Adapter Interface | NOT OBSERVED | P0 | 核心层不 import provider DTO |
| Provider Capability Matrix | NOT OBSERVED | P0 | 支持/不支持/未知及验证时间 |
| Canonical Market Data Model | NOT OBSERVED | P0 | provider-neutral, grain/unit/time explicit |
| Data Provenance | NOT OBSERVED | P0 | 结果追至 raw artifact/source field |
| Data Confidence / Quality | NOT OBSERVED | P0 | 状态、规则、异常与阻断门 |
| Opportunity | NOT OBSERVED | P0 | 稳定 ID、scope、owner、history |
| Opportunity Workspace | NOT OBSERVED | P1 | 阶段证据和产物聚合 |
| Opportunity State Machine | NOT OBSERVED | P0 | 合法转换、审批、历史 |
| Demand Intelligence | NOT OBSERVED | P1 | evidence-backed demand records |
| Keyword Intent Classification | NOT OBSERVED | P1 | structured output + citations |
| Application / Use-case Map | NOT OBSERVED | P1 | many-to-many relationships |
| Customer Need Map | NOT OBSERVED | P1 | needs linked to evidence |
| Competitor Intelligence | NOT OBSERVED | P1 | market scope and parent policy |
| Review Intelligence | NOT OBSERVED | P1 | source excerpts/ASIN/snapshot trace |
| Market Structure Analysis | NOT OBSERVED | P1 | deterministic facts + interpretations split |
| Opportunity Diagnosis | NOT OBSERVED | P0 | typed evidence/inference/unknowns |
| Evidence | NOT OBSERVED | P0 | immutable referenceable records |
| Inference / Hypothesis | NOT OBSERVED | P0 | author/model, confidence, evidence refs |
| Unknown / Blocking Unknown | NOT OBSERVED | P0 | explicit gate effect |
| Product Concept Builder | NOT OBSERVED | P2 | versioned concepts and assumptions |
| Product Specification Draft | NOT OBSERVED | P2 | trace to needs/gaps/compliance |
| Differentiation / Gap Matrix | NOT OBSERVED | P2 | evidence-backed competitor comparison |
| Business Case | NOT OBSERVED | P1 | scenario/version/assumptions |
| Unit Economics | NOT OBSERVED | P1 | formula-driven and source-traced |
| Scenario Analysis | NOT OBSERVED | P1 | base/upside/downside + sensitivity |
| Supplier Validation | NOT OBSERVED | P2 | claim, source, status, owner |
| Compliance Validation | NOT OBSERVED | P1 | marketplace/category gates |
| Decision Center | NOT OBSERVED | P0 | evidence package and owner decision |
| GO / HOLD / NO-GO | NOT OBSERVED | P0 | human decision, not score alias |
| Decision History | NOT OBSERVED | P0 | append-only revisions |
| LLM Fact Package | NOT OBSERVED | P1 | bounded versioned facts |
| LLM Input Contract | NOT OBSERVED | P1 | schema, token/source policy |
| LLM Structured Output | NOT OBSERVED | P1 | validated schema, retry/reject rules |
| LLM Evidence Citation | NOT OBSERVED | P0 | every material claim links evidence |

## 11. Proposed Target Architecture

### 11.1 分层

```text
[SellerSprite Excel] [Xiyou MCP] [Other API/CSV] [Manual Import]
             │ provider-specific, read boundary
             ▼
 Provider Registry + Adapter + Capability Matrix
             ▼
 Raw Artifact / Observation Store
 (immutable ref, hash, source field, snapshot, collection run)
             ▼
 Canonical Market Data
 (ASIN/parent/variant/category/keyword/metric/time/grain/unit)
             ▼
 Deterministic Derived + Estimate Registry + Quality Gates
             ▼
 Evidence Store / Fact Package
             ▼
 Opportunity Workspace & State Machine
 Discovery → Demand → Validation → Diagnosis → Concept
 → Business Case → Supplier Validation → Decision
             ▼
 Human Decision Center: GO / HOLD / NO-GO + history

LLM sidecar: structured Insight/Hypothesis only; reads fact package,
emits citations/confidence/unknowns; never mutates canonical facts.
```

### 11.2 关键契约

- `ProviderAdapter.collect(request) -> ObservationBatch`
- `CanonicalMapper.map(observation, mapping_version) -> CanonicalRecord[] + Reject[]`
- `QualityEvaluator.evaluate(record/batch) -> QualityResult`
- `DerivationEngine.compute(definition_version, inputs) -> DerivedMetric`
- `EstimateEngine.estimate(method_version, assumptions, inputs) -> Estimate`
- `FactPackageBuilder.build(opportunity_id, cutoff) -> LLMFactPackage`
- `DecisionService.record(decision, approver, evidence_refs) -> DecisionHistory`

接口名称仅为概念，不是创建代码的指令。

### 11.3 Opportunity 状态与门

每阶段产出不是一个总分，而是一组 evidence、hypothesis、unknown 和 gate result。`HOLD` 应能引用 blocking unknown；`NO-GO` 应保留原因和当时证据；重新开启应创建历史事件而不是覆盖旧决定。

## 12. Migration Strategy

采用 strangler/parallel-run，而不是原地重写：

1. **恢复证据，不改生产：** 提供正确只读 checkout、schema、代表性脱敏数据和运行说明。
2. **建立基线：** 固化现有输入、输出、关键指标、UI 截图/导出和 golden datasets。
3. **画真实 lineage：** 从 SellerSprite/Xiyou 字段追到分析、score 和 UI。
4. **先隔离输入：** 在旧流程旁建立 adapter + observation envelope，不替换旧消费者。
5. **定义 canonical model：** 通过 ADR 明确 grain、period、currency、parent/child、BSR/category 和 keyword 语义。
6. **双写/并行映射：** 对同一输入生成旧输出和 canonical 输出，逐字段对账。
7. **分离 derived/estimate：** 保留旧值，但增加类型、公式版本、confidence 和 lineage。
8. **引入 opportunity/evidence：** 让新工作区消费经过验证的 canonical facts；旧 UI 暂时不动。
9. **结构化 LLM：** 仅在 fact package 和引用机制通过后接入 insight/hypothesis。
10. **迁移消费者：** Keyword → Market → Competitor → Business Case → Decision，逐个切换并保留回退。
11. **退役评估：** 只有调用为零、历史可访问、替代已对账、owner 批准后，才提出 REMOVE。

### 12.1 升级为 PARTIAL REBUILD 的门槛

若恢复后同时观察到以下情况，可将结论升级为 `C`：provider 字段贯穿核心实体与 UI；数据粒度/身份模型无法表达 parent-child 和 snapshot；没有可复现基线；核心算法将 estimate 当 fact 且难以隔离；替换的总成本/风险低于逐步迁移。没有这些证据，不应升级。

`FULL REBUILD` 还需要额外证明：几乎所有业务能力不可复用、迁移/并行运行不可行、数据历史可安全保留、完整替代方案和回滚/切换计划已获批准。本轮完全不满足。

## 13. Recommended Development Sequence

本序列是审计后的建议，不授权自动进入开发：

| 阶段 | 工作 | exit gate |
|---:|---|---|
| 0 | Evidence recovery | checkout、样本、schema、测试、运行说明齐备 |
| 1 | Baseline & lineage | 关键旧输出可重复，字段链路可追踪 |
| 2 | Provider contracts | SellerSprite/Xiyou 细节停在 adapter |
| 3 | Raw + provenance | raw artifact 可指纹、批次可重放 |
| 4 | Canonical model | identity/grain/time/unit/category ADR 批准 |
| 5 | Quality + fact boundaries | fact/derived/estimate 可机器区分 |
| 6 | Opportunity/evidence | state、unknown、decision history 可审计 |
| 7 | Demand/competitor intelligence | insight 有引用，事实可复算 |
| 8 | Concept/business case/supplier | 假设、场景、合规和供应验证版本化 |
| 9 | LLM contracts | structured input/output/citation 全部验证 |
| 10 | UI/decision center migration | GO/HOLD/NO-GO 由人确认，可回溯 |
| 11 | Selective retirement | 零调用、对账、回退、owner 批准 |

最先开发的不应是新总分或子体销量估算优化；应先补齐证据边界和 canonical/provenance 基础。

## 14. Risks

| 风险 | 等级 | 影响 | 缓解 |
|---|---:|---|---|
| 当前不是实际 system checkout | Critical | 审计无法评价实现 | 提供正确只读仓库/快照 |
| 把 NOT OBSERVED 当成不存在 | Critical | 错误重建或重复功能 | 统一证据标签和复审门 |
| SellerSprite 历史样本丢失 | High | 无法保证兼容和回归 | 恢复只读样本、指纹、脱敏 fixture |
| Provider 字段泄漏 | High | 更换 provider 触发全链路变更 | adapter + canonical contract |
| 父子体双计/错误分摊 | High | 市场容量和 business case 错误 | 明确 grain、守恒测试、estimate 标识 |
| 销量/收入口径不透明 | High | 事实与估算混淆 | period/currency/method/provenance 必填 |
| BSR 未绑定类目与时间 | High | 排名不可比较 | category node + snapshot |
| Opportunity score 替代判断 | High | 假精确决策 | score 仅作 evidence，人工决定 |
| LLM 无引用解释 | High | 幻觉进入产品结论 | fact package + structured citations |
| Xiyou schema 描述被当运行事实 | Medium | 错误能力规划 | capability 分 schema-visible/runtime-verified |
| 旧报告时点结论过期 | Medium | 误判连接状态 | 每次报告记录 observed_at |
| 无 Git 历史/依赖图 | High | 无法判断活跃代码和 REMOVE | 恢复 refs/tags/branches 和运行 telemetry |
| 数据隐私与原始响应保存 | Medium | 合规/访问风险 | 分级权限、脱敏、retention policy |

## 15. Unknowns

### 15.1 仓库与运行

- 正确仓库位置、分支、tag、commit、模块 owner；
- 语言、依赖、部署、调度和环境；
- 数据库、文件存储、表和 retention；
- 生产/测试运行入口及最近成功运行。

### 15.2 SellerSprite

- 导出类型、版本、站点、sheet、原始字段和列别名；
- 真实样本是否仍存在、规模、敏感性和可重跑性；
- 字段 mapping、Raw/Standard/Derived schema；
- 销量、收入、BSR、关键词、Parent/Child 的来源与粒度；
- 特有字段是否泄漏到分析/UI。

### 15.3 分析与决策

- taxonomy、规格解析、市场边界和竞品选择逻辑；
- 子体销量算法、启用状态、授权和质量门；
- candidate/opportunity score 定义、权重、版本和用途；
- UI 是否把 estimate/score 呈现为事实/决定；
- LLM provider、prompt、输入输出、引用和人工复核。

### 15.4 Xiyou

- 43 个可见工具在当前授权下哪些可成功运行；
- 实际 response schema、单位、nullability、error/pagination/rate limit；
- 订单/销量/收入/流量分数的计算方法和置信度；
- parent/child 关系的完整性、历史和站点支持；
- 数据发生时间与采集时间；
- 当前账户和站点的 capability 差异。

## 16. Decisions Required From Product Owner

1. 指定本次应审计的实际仓库/只读快照及基准 commit。
2. 决定是否提供历史 SellerSprite 文件；若敏感，批准脱敏 fixture 与字段清单替代方案。
3. 明确必须保持完全兼容的旧输出、UI、报告和消费者。
4. 批准 canonical identity/grain 原则：marketplace、ASIN、parent、variant、category、keyword、metric period。
5. 明确 provider 提供的销量/收入是否一律按 `PROVIDER_ESTIMATE` 管理，除非有可验证定义。
6. 决定旧子体销量估算若存在，是否允许继续展示；建议仅保留并显著标记，不扩大使用。
7. 决定 opportunity score 的产品定位；建议“证据摘要”，不得直接映射最终决定。
8. 指定 GO/HOLD/NO-GO 的审批角色、允许的状态转换和审计保留期。
9. 定义 blocking unknown 的处理：哪些未知必须 HOLD，哪些可接受风险后继续。
10. 决定 Xiyou 的验证范围、站点、预算/配额和只读授权；在实际响应验证前保持 UNVERIFIED。
11. 指定数据质量失败的行为：reject、quarantine、warn 或 block decision。
12. 批准迁移方式：建议旁路并行、逐消费者切换，不批准大爆炸重写。

## 17. Final Conclusion

### 选择：B. EVOLVE CURRENT ARCHITECTURE

理由如下：

- **不选 A（KEEP CURRENT ARCHITECTURE）：** 新系统的职责已经从“筛高销量低竞争商品”扩展为跨需求、市场、产品、财务、供应链和决策历史的产品开发系统。provider independence、Fact/Insight/Decision 和 provenance 是明确的新增架构门槛，完全保持原状不足以表达目标。
- **选择 B（EVOLVE）：** 当前没有任何实现证据支持破坏性判断。最安全且与目标一致的策略，是保留未知旧系统，通过 adapter、canonical model、provenance、quality、evidence 和 opportunity state 逐层旁路演进；每一步都可对账、回退和单独验收。
- **暂不选 C（PARTIAL REBUILD）：** 它可能最终正确，但必须先证明某些核心模块无法隔离或迁移。本轮没有源码、依赖、运行、数据模型或测试，证据不足。
- **不选 D（FULL REBUILD）：** 没有任何可量化证据证明全部旧能力不可复用，也没有基线、替代覆盖、数据迁移和切换方案。现在提出全量重建风险最大。

### 审计后的立即行动

保持生产系统和数据不变。下一步不是编码，而是由 Product Owner 提供实际只读 checkout、代表性 SellerSprite 样本/fixture、schema、运行说明和关键旧输出。材料齐备后，应重跑本报告第 4、5、6、7、8、9 节并把所有 `UNKNOWN` 收敛为可引用的 `OBSERVED`，再批准任何实现、迁移或删除决策。

---

**完整性声明：** 本报告没有把文件缺失推断成能力缺失，没有假设 Xiyou 的实际返回能力，没有提出实际删除，没有修改任何既有文件。审计期间唯一创建的资产是本报告。
