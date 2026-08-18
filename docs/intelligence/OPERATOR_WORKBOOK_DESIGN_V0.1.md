# Amazon Product Intelligence Workbook V1.0 — Product Design V0.1

## Design status and boundary

本文件定义下一版本运营 Excel 的产品结构，不是实现任务。

设计基线：

    branch: main
    HEAD: 55fe25cc6f6e293d8acd6dd0d9351b5e5e47fc94
    subject: feat: add xlsx operator delivery v0.1

本设计只规定 Sheet、字段、用户流程、数据来源映射和展示逻辑。它不授权修改 Canonical Evidence、Intelligence、Evidence Evaluation、Conflict Resolution、Evidence Policy、Decision Framework、Opportunity Scoring、Recommendation Framework 或现有后端模型。

V1.0 的定位是把现有“审计型数据输出”转换为“摘要优先、证据可追溯”的运营工作簿。所有业务值必须来自现有已验证记录；Excel 层不得补全事实、选择冲突候选、重算分数或生成新建议。

## A. Product Goal

### A.1 Product definition

产品名称：

    Amazon Product Intelligence Workbook V1.0

目标是让亚马逊运营在一个可筛选、可复核的工作簿中完成：

- 市场调研；
- 产品筛选；
- 显式排名证据查看；
- 关键词分析；
- 市场关系证据查看；
- 产品结构观察；
- 机会证据与风险复核；
- 行动建议的人工状态管理；
- 从任一展示值回到 Canonical lineage。

### A.2 Product principles

1. 摘要优先：运营字段在前，审计引用在后。
2. 证据不裁决：单一候选可以机械展示；多个不同候选只显示候选状态，不选择“正确值”。
3. 缺失不补零：missing、explicit null、unknown、empty query、zero 和 not available 必须区分。
4. 估算不伪装：Provider estimate 必须保留 estimate/evidence/method status。
5. 排名有上下文：任何 Rank 必须同时显示 Provider、rank context、channel、period 或 observation status。
6. 限制常驻：竞争、机会和建议页面的语义限制不能默认隐藏。
7. 审计可下钻：每个展示行都能通过隐藏审计表回到 Output、Export、Canonical、Transformation 和 Raw Evidence Reference。
8. 静态可重复：生成态工作簿不使用随机 ID、当前时间或 Excel 公式重算分析结果。
9. 人工输入隔离：只有“人工状态”属于运营编辑；它不回写或改变后端分析快照。

### A.3 Explicit non-goals

V1.0 不提供：

- 市场规模保证；
- 需求保证；
- “最佳产品”判断；
- 竞品排名；
- 成功概率；
- 自动选品；
- 购买建议；
- 未经来源支持的 CPC、Difficulty、销量、趋势或类目值；
- 跨 Provider 的隐式取舍、平均或最终事实裁决。

## B. User Persona

### B.1 Primary persona

主要用户是负责新品调研、产品组合、关键词与竞争研究的亚马逊运营。

| Persona dimension | Definition |
|---|---|
| 工作目标 | 快速缩小调研范围，并知道下一步需要补什么证据 |
| 常用工具 | Excel 筛选、排序、冻结窗格、颜色状态、复制 ASIN/Keyword |
| 关注字段 | ASIN、标题、价格、Rating、Review、BSR、销量证据、关键词指标、风险、限制 |
| 主要痛点 | JSON 太长、关键值埋藏、状态不可筛选、排名来源不明确、建议容易被误读 |
| 风险 | 把 estimate 当 observed fact；把 evidence count 当竞争强度；把 score 当成功概率 |
| 需要的保障 | 可见限制、明确来源、候选状态、完整 lineage、人工复核入口 |

### B.2 Secondary persona

数据审计或产品负责人会使用隐藏的“数据审计”表验证来源、转换与展示值，但不应通过该表直接修改证据。

### B.3 Core operator questions

- 当前文件覆盖了哪些市场、品类候选和产品？
- 哪些产品拥有可比较的价格、Rating、Review、BSR 或销量证据？
- 一个 TOP 位置来自哪个 Provider、什么排名语义和时间范围？
- Keyword 指标是否存在、缺失还是方法未知？
- 产品与 Keyword 之间是什么方向的关系证据？
- Opportunity 中有哪些信号、缺失证据和风险？
- Score 是可用、缺失、冲突可见还是被 Policy 阻塞？
- Recommendation 是什么规则记录，下一步应人工做什么？
- 任一值如何追溯到 Canonical observation 和 Raw Evidence Reference？

## C. Workbook Structure

### C.1 Sheet order

| Ordinal | Sheet name | Default visibility | Row grain | Primary use | Future page |
|---:|---|---|---|---|---|
| 1 | 01_市场概览 | Visible | Marketplace × category candidate × evidence indicator | 打开文件后的市场范围、风险和限制摘要 | Dashboard 首页 |
| 2 | 02_产品数据库 | Visible | One exact product identity | 核心产品筛选与证据状态查看 | 产品列表 / 产品详情 |
| 3 | 03_TOP产品分析 | Visible | One explicit rank evidence record | 查看有来源和上下文的主要产品位置 | 市场表现页面 |
| 4 | 04_关键词需求分析 | Visible | Keyword identity × provider × direction × channel | 关键词指标、查询状态和关联产品 | Keyword 页面 |
| 5 | 05_市场竞争证据 | Visible | One product-keyword relationship evidence group | 查看关系、渠道、Provider 和证据数量 | 竞争证据页面 |
| 6 | 06_产品结构分析 | Visible | One exact observed product-type group | 查看产品类型、价格和属性分布 | 产品结构页面 |
| 7 | 07_机会分析 | Visible | Opportunity output group × score calculation | 信号、缺失、风险和 score reference 复核 | Opportunity 页面 |
| 8 | 08_行动建议 | Visible | One recommendation generation record | 人工复核与状态管理 | Review Queue |
| 9 | 09_数据审计 | Hidden | One displayed field/cell × lineage reference | 端到端数据追溯 | Audit / Lineage Drawer |

### C.2 Navigation and layout

- 每张可见表第 1 行为标题，第 2 行显示 snapshot、范围和固定语义警告，第 3 行为字段表头。
- 冻结位置为 A4，使标题、上下文和表头在滚动时持续可见。
- 第 3 行到最后数据行启用筛选。
- 身份、状态和核心指标列在左侧；Provider、period、候选状态紧邻业务值；长 ID 和审计字段置于最右并默认隐藏。
- 不在数据区合并单元格；不把多个语义不同的值拼成不可筛选的大段 JSON。
- 固定状态使用一致颜色：可用为中性蓝/绿，missing 或 unknown 为灰色，conflict/policy blocked/risk 为橙/红色。颜色只帮助扫描，文本状态始终保留。
- 主表行高以摘要可读为准；长详情不直接展开到 30K 字符。
- 生成态只写静态、已验证值。不得用 Excel 公式重算 score、trend、recommendation 或 evidence quality。
- “人工状态”使用数据验证下拉框，是唯一默认可编辑的业务列。

### C.3 Display-state vocabulary

展示层使用以下受控状态，不覆盖来源状态：

| Display state | Meaning |
|---|---|
| PRESENT | 来源中存在可展示值 |
| MISSING | 来源明确记录缺失 |
| EXPLICIT_NULL | Provider 明确返回 null |
| UNKNOWN | 语义、时间、单位或方法未知 |
| EMPTY_QUERY_RESULT | 查询成功但结果为空；不是零需求 |
| MULTIPLE_CANDIDATES | 存在多个不同候选；未裁决 |
| NOT_AVAILABLE | 当前快照没有对应字段证据 |
| NOT_COMPARABLE | 单位、币种、时间或语义不可安全比较 |
| POLICY_BLOCKED | Policy 阻止产生可用结果 |
| REVIEW_REQUIRED | 需要人工复核 |

### C.4 Mechanical display rules

允许的展示操作只有：

- 直接复制；
- 从已验证 mapping 中提取标量；
- 稳定排序；
- 相同语义、相同单位和相同币种下的计数、最小值、最大值；
- ID 数量统计；
- 机器码到人类标签的一对一显示映射，同时保留原机器码；
- 固定限制文案；
- 用户在“人工状态”中的独立输入。

禁止的展示操作包括：

- 从多个候选中选择偏好值；
- 对不同 Provider 或不同语义的值求平均；
- 单位、币种或时间窗口不明确时进行换算或比较；
- 从排名关系推导竞争强度；
- 从空查询推导零需求；
- 从 score 推导成功概率；
- 从 recommendation 推导购买结论。

## D. Sheet Definitions

### D.1 01_市场概览

目标：运营打开文件后立即理解“当前证据覆盖了什么”，而不是看到市场保证。

设计：

- 顶部摘要区显示已观察产品数、Provider 数、信号数、缺失证据数和风险证据数。
- 明细表一行表示一个 Marketplace、类目候选和证据指标组合。
- “市场规模指标”只显示现有 Opportunity signal 或 canonical metric；没有安全市场规模证据时显示 NOT_AVAILABLE。
- “已观察产品数”是当前证据中的 product identity count，不是市场产品总数。
- “主要趋势”只复制已有带时间语义的 signal/explanation；没有趋势记录时显示 NOT_AVAILABLE。
- 风险和分析限制始终可见。

### D.2 02_产品数据库

目标：作为运营主要工作表，用一行查看一个 exact product identity。

设计：

- ASIN、Marketplace、标题、品牌和类目位于最左侧。
- 单一 distinct present candidate 可机械显示；多个候选时业务值留空或显示 MULTIPLE_CANDIDATES，并将候选详情关联到审计表。
- 价格、Rating、Review、BSR、销量证据必须显示单位、币种、evidence type、Provider 和状态。
- 销量字段命名为“销量证据”，不能命名为“销量事实”。
- Variation、Seller、FBA 和属性仅从 Product Intelligence 已组织证据投影。
- 默认排序为 Marketplace、ASIN，避免暗示产品优劣。

### D.3 03_TOP产品分析

目标：快速查看具有显式排名或市场表现证据的产品。

设计：

- TOP 表不是系统重新排名；只纳入存在显式 rank evidence 的记录。
- 默认排序可以使用来源 rank value，但必须在同一 Provider、rank context、channel 和可比较 period 内进行。
- 跨 Provider、跨类目或跨 rank semantic 不混排。
- 每行必须显示 Rank Source、Rank Context 和 Rank Status。
- 没有显式 rank evidence 时显示空状态页，不用其他指标代替排名。
- 固定提示：“来源排名证据，不代表最佳产品或平台推荐。”

### D.4 04_关键词需求分析

目标：查看 Keyword 指标、方向性查询、渠道和关联产品证据。

设计：

- Keyword Text、Marketplace、Provider、Direction 和 Channel 是主要筛选字段。
- Search Volume、CPC、ABA Rank、Difficulty 只在对应 KeywordMetricEvidenceSet 存在时显示。
- 每个指标旁显示状态、单位/币种、period 和 method status。
- Query Status 区分 populated、empty、unknown、failed 等来源状态。
- Related Product Count 是当前证据 inventory 数量，不是市场竞争者总量。
- 固定提示：“方向性查询和估算指标不构成需求保证。”

### D.5 05_市场竞争证据

目标：展示产品与 Keyword 的观察关系，避免“竞品排名”误导。

设计：

- Sheet 名固定为“市场竞争证据”，不得使用“竞品排名”。
- 一行表示一个 product-keyword relationship evidence group。
- Product、Keyword、Direction、Relationship、Channel、Provider 和 Evidence Count 为主列。
- Relationship Type 为来源关系语义；RANK 也不自动等于竞争排名。
- Evidence Count 只表示当前组的证据数量。
- 固定提示：“关系证据不是竞争强度、市场份额或竞品排名。”

### D.6 06_产品结构分析

目标：依据现有 Product Intelligence facts 观察产品类型和属性分布。

设计：

- 只按 exact normalized product_type/category candidate 分组，不使用模型聚类或人工推断。
- 多候选产品计入 MULTIPLE_CANDIDATES，不静默分配到某一类型。
- 产品数量是当前快照的 unique product identity count。
- 价格范围只在相同币种、单位、measurement type 和可比较时间语义内计算。
- 销量证据保持原值、单位和方法状态；不跨语义汇总。
- “主要特点”是现有属性的频次 inventory，不表示卖点或偏好。

### D.7 07_机会分析

目标：并列展示 demand、competition、product signal、缺失证据、风险和现有 score reference。

设计：

- 三类 signal 分列，保留 classification、type 和来源。
- Missing Evidence 与 Risk 始终可见。
- Score Result 可以显示现有 ScoreCalculationRecord.result_value，但必须同时显示 result_status 和 process_interpretation。
- Score 不可用时显示状态，不补零。
- Score 名称使用“规则过程分值”，不得显示“成功率”或“机会概率”。
- 固定提示：“信号与规则过程分值不构成机会保证。”

### D.8 08_行动建议

目标：让运营复核现有 Recommendation Framework 输出，并记录独立人工状态。

设计：

- Recommendation Type、Reason 和 Limitation 来源于既有 recommendation generation/explanation。
- Product 只在 lineage 能机械解析为单一 product identity 时显示；否则显示 MULTIPLE/UNRESOLVED。
- Recommendation Display Label 是机器码的一对一中文标签，不改变 recommendation type。
- 人工状态允许值：未复核、进一步调研、补充数据、人工审核、已复核。
- 人工状态不写回 Recommendation Framework，不改变 score、decision 或 evidence。
- 固定提示：“规则生成的复核记录，不是购买建议或自动选品结论。”

### D.9 09_数据审计

目标：提供 Excel Row → Export Row → Operator Output → Canonical Lineage 的完整追溯。

设计：

- Sheet 默认隐藏，但不是加密或安全边界。
- 一行表示一个展示字段/cell 与一个 lineage reference 的连接。
- Raw Reference 只保存 raw_evidence_id 或安全引用，不包含 raw provider payload。
- 不包含 token、credential、secret、authorization、private key、password 或 internal metadata。
- 由运营取消隐藏后可按 Sheet、Row Key、Evidence ID、Provider、Transformation Run 等筛选。

## E. Field Dictionary

### E.0 Source abbreviations

| Abbreviation | Source |
|---|---|
| PI | ProductIntelligenceSnapshotV0_1 |
| DI | DemandIntelligenceSnapshotV0_1 |
| CI | CompetitionIntelligenceSnapshotV0_1 |
| OI | OpportunityIntelligenceSnapshotV0_1 |
| EE | EvidenceEvaluationSnapshotV0_1 |
| OS | OpportunityScoringSnapshotV0_1 |
| RF | RecommendationFrameworkSnapshotV0_1 |
| OO | OperatorOutputSnapshotV0_1 |
| OE | OperatorExportSnapshotV0_1 |
| XD | XlsxDeliverySnapshotV0_1 |
| UI | Workbook-only operator input |

“展示=是”表示字段存在于该 Sheet。“默认隐藏=是”表示字段保留在表中但初始折叠/隐藏。

### E.1 01_市场概览

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 市场站点 | Marketplace | Text | OI signal subject / canonical scope | 是 | 否 | 区分站点；不能跨站点汇总 |
| 类目候选 | Category Candidate | Text / Nullable | OI signals from product fact evidence | 是 | 否 | 只展示现有候选；多候选显示 MULTIPLE_CANDIDATES |
| 市场规模证据指标 | Market Size Evidence Metric | Text | OI signals / canonical metrics | 是 | 否 | 标识来源指标，不把任意 envelope total 当市场规模 |
| 指标值 | Metric Value | Number / Text / Nullable | OI OpportunitySignalEvidence.evidence_attributes | 是 | 否 | 直接展示已有值；缺失为 NOT_AVAILABLE |
| 单位 | Unit | Text / Nullable | OI signal evidence attributes | 是 | 否 | 单位未知时显示 UNKNOWN，不换算 |
| 已观察产品数 | Observed Product Count | Integer | OI coverage.product_identity_count | 是 | 否 | 当前证据 inventory，不是市场产品总数 |
| 数据来源 | Data Sources | Text List | EE support_records.providers / sources | 是 | 否 | 快速识别 Provider 和 source tool |
| 主要趋势 | Evidence-backed Trend | Text / Nullable | OI signal/explanation with time semantics | 是 | 否 | 只复制已有趋势记录；否则 NOT_AVAILABLE |
| 风险提示 | Risk Alerts | Text List | OI risk_evidence | 是 | 否 | 展示风险类型与短消息，不生成概率 |
| 证据质量 | Evidence Quality | Enum List | EE quality_profiles | 是 | 否 | 显示 source diversity、period、completeness、consistency |
| 分析限制 | Analysis Limitations | Text List | OI missing_evidence, risk_evidence; EE diagnostics | 是 | 否 | 常驻显示未知、缺失和冲突边界 |
| 快照 ID | Snapshot ID | ID | OI.snapshot_id / EE.snapshot_id | 是 | 是 | 用于刷新对比和审计定位 |

### E.2 02_产品数据库

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| ASIN | ASIN | Text ID | PI.target/included_product_identities.asin; OO product_rows.asin | 是 | 否 | 产品主识别和筛选 |
| 市场站点 | Marketplace | Text | PI product identity.marketplace; OO product_rows.marketplace | 是 | 否 | 防止跨站点混合 |
| 标题 | Display Title | Text / Nullable | PI fact sets dimension=title candidates.normalized_value | 是 | 否 | 仅单一 present candidate 直接显示 |
| 标题状态 | Title State | Enum | PI ProductFactEvidenceSet.candidate_state | 是 | 否 | 标识不存在、单候选或多候选 |
| 品牌 | Brand | Text / Nullable | PI fact sets dimension=brand | 是 | 否 | 单一候选显示；不裁决冲突 |
| 类目 | Category | Text / Nullable | PI fact sets category-related dimensions | 是 | 否 | 保留 candidate state |
| 产品类型 | Product Type | Text / Nullable | PI fact sets dimension=product_type/type | 是 | 否 | 用于产品结构筛选；不得推断类型 |
| 价格 | Price | Decimal / Nullable | PI metric series metric=price candidates.normalized_value | 是 | 否 | 仅展示可用价格证据 |
| 币种 | Price Currency | Text / Nullable | PI ProductMetricSeries.currency | 是 | 否 | 与价格同时显示 |
| 价格状态 | Price State | Enum | PI metric presence_counts / candidate status | 是 | 否 | 区分 missing/null/unknown/multiple |
| Rating | Rating | Decimal / Nullable | PI rating fact/metric evidence or review summary inventory | 是 | 否 | 只展示已有 rating 证据，不从样本直方图伪造总体评分 |
| Rating 状态 | Rating State | Enum | PI candidate presence/candidate state | 是 | 否 | 说明 rating 是否可用 |
| Review 数量证据 | Review Evidence Count | Integer / Nullable | PI review_evidence_summary.review_observation_count or explicit metric | 是 | 否 | 明确是供应证据样本或显式 metric |
| BSR | BSR | Integer / Nullable | PI metric series with rank semantic | 是 | 否 | 必须和 rank context、Provider 一起使用 |
| BSR 类目上下文 | BSR Context | Text / Nullable | PI ProductMetricSeries.rank_context | 是 | 否 | 防止无上下文排名 |
| 销量证据 | Sales Evidence Value | Number / Text / Nullable | PI product_metric_series matching sales semantic | 是 | 否 | 保留 observed/estimate 和来源方法状态 |
| 销量证据单位 | Sales Evidence Unit | Text / Nullable | PI ProductMetricSeries.unit | 是 | 否 | 不进行未批准换算 |
| 销量证据类型 | Sales Evidence Type | Enum | PI measurement_type / evidence_type | 是 | 否 | 区分 observed 与 estimate |
| Variation 角色 | Variation Role | Enum / Nullable | PI variation_topology nodes/edges | 是 | 否 | 展示 parent/child/unknown，不扩展 scope |
| Parent ASIN | Parent ASIN | Text ID / Nullable | PI variation_topology | 是 | 否 | 仅确认关系可直接显示 |
| Child 数量 | Child Count | Integer | PI variation_topology confirmed edges | 是 | 否 | 当前确认 edge inventory 数量 |
| 属性摘要 | Attribute Summary | Text List | PI fact evidence sets for approved attributes | 是 | 否 | 显示已有结构化属性，不补全未批准属性 |
| 卖家 | Seller | Text / Nullable | PI fact evidence set dimension=seller | 是 | 否 | 只显示证据候选 |
| FBA | FBA Status | Boolean / Enum / Nullable | PI fact evidence set dimension=fulfillment/FBA | 是 | 否 | 未知状态不转为 false |
| 数据来源 | Data Sources | Text List | PI candidate.provider/source_tool | 是 | 否 | 识别数据覆盖来源 |
| 数据状态 | Data State | Enum | PI candidate/presence/candidate states | 是 | 否 | 统一展示 PRESENT、UNKNOWN、MULTIPLE 等 |
| 冲突状态 | Conflict State | Enum | EE conflicts / quality profile.consistency | 是 | 否 | 冲突可见但不解决 |
| 时间/周期状态 | Time / Period Status | Enum | PI metric period_type, observed_at_status; EE profile | 是 | 是 | 判断指标是否可比较 |
| Product Snapshot ID | Product Snapshot ID | ID | PI.snapshot_id / OO product_rows.source_snapshot_id | 是 | 是 | 审计与版本定位 |
| Output Row ID | Output Row ID | ID | OO ProductOutputRow.output_row_id | 是 | 是 | 连接数据审计表 |

### E.3 03_TOP产品分析

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 产品 | Product ASIN | Text ID | PI metric subject identity / OO product row | 是 | 否 | 排名记录对应产品 |
| 标题 | Display Title | Text / Nullable | PI title fact candidate | 是 | 否 | 辅助识别，不参与排序 |
| 市场站点 | Marketplace | Text | Product identity.marketplace | 是 | 否 | 排名比较边界 |
| 来源排名 | Source Rank Value | Integer / Nullable | PI metric candidate with rank semantic | 是 | 否 | 只显示显式来源排名 |
| 排名指标 | Rank Metric | Text | PI ProductMetricSeries.metric / metric_semantic | 是 | 否 | 说明 BSR、organic rank 等语义 |
| 排名上下文 | Rank Context | Text | PI ProductMetricSeries.rank_context | 是 | 否 | 类目、关键词或其他上下文 |
| Channel | Channel | Enum / Nullable | Canonical relationship/rank evidence | 是 | 否 | 区分 ORGANIC、SPONSORED、UNKNOWN |
| 排名来源 | Rank Provider | Text | PI candidate.provider | 是 | 否 | 所有排名必须显示来源 |
| 排名状态 | Rank Status | Enum | candidate presence/result/method status | 是 | 否 | 防止 unknown 被当作排名 |
| 排名周期 | Rank Period | Text / Nullable | PI period_type/start/end/observed_at_status | 是 | 否 | 只在可比较周期内排序 |
| 价格 | Price | Decimal / Nullable | PI price metric evidence | 是 | 否 | 市场表现旁的参考值 |
| Review | Review Evidence Count | Integer / Nullable | PI review summary / explicit metric | 是 | 否 | 明确样本或 metric 语义 |
| Rating | Rating Evidence | Decimal / Nullable | PI rating evidence | 是 | 否 | 不推导总体评分 |
| 产品特点 | Product Features | Text List | PI approved fact evidence sets | 是 | 否 | 只展示已有属性候选 |
| 数据限制 | Data Limitations | Text List | PI diagnostics; EE profiles/conflicts | 是 | 否 | 固定提示不是最佳产品 |
| Rank Observation ID | Rank Observation ID | ID | PI candidate.observation_id | 是 | 是 | 审计定位 |

### E.4 04_关键词需求分析

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| Keyword | Keyword | Text | DI.target_keyword_identity.normalized_text | 是 | 否 | 主要筛选和复制字段 |
| 市场站点 | Marketplace | Text | DI keyword identity.marketplace | 是 | 否 | 防止跨站点混合 |
| Locale | Locale | Text | DI keyword identity.locale | 是 | 是 | 语言和规范化审计 |
| Search Volume | Search Volume | Number / Nullable | DI keyword metric set metric=search_volume | 是 | 否 | 缺失显示 NOT_AVAILABLE，不补零 |
| Search Volume 状态 | Search Volume State | Enum | DI metric candidate_state/presence | 是 | 否 | 显示 present/null/multiple/unknown |
| Search Volume 单位 | Search Volume Unit | Text / Nullable | DI metric set.unit | 是 | 是 | 单位未知不换算 |
| CPC | CPC | Decimal / Nullable | DI metric set metric=CPC | 是 | 否 | 只在现有证据中显示 |
| CPC 币种 | CPC Currency | Text / Nullable | DI metric semantic/candidate evidence | 是 | 否 | 与 CPC 同时显示 |
| CPC 状态 | CPC State | Enum | DI candidate state/presence | 是 | 否 | 不存在时 NOT_AVAILABLE |
| ABA Rank | ABA Rank | Integer / Nullable | DI metric set matching ABA rank semantic | 是 | 否 | 必须显示语义和 Provider |
| ABA Rank 状态 | ABA Rank State | Enum | DI candidate state/presence | 是 | 否 | 避免空值误解 |
| Difficulty | Difficulty | Number / Text / Nullable | DI metric set matching difficulty semantic | 是 | 否 | 不在 Excel 层计算；无证据时 NOT_AVAILABLE |
| Difficulty 状态 | Difficulty State | Enum | DI candidate state/presence | 是 | 否 | 说明来源状态 |
| 关联产品数 | Related Product Count | Integer | DI related_product_evidence inventory | 是 | 否 | 当前证据数量，不是市场竞品总量 |
| 关联产品 | Related Product ASINs | Text ID List | DI related_product_evidence.product identity | 是 | 否 | 支持后续产品筛选 |
| Channel | Channel | Enum / List | DI relationship/query evidence.channels | 是 | 否 | 区分 ORGANIC、SPONSORED、UNKNOWN |
| Query Direction | Query Direction | Enum | DI query/relationship direction | 是 | 否 | 区分 Keyword→Product 与 Product→Keyword |
| Query 状态 | Query Status | Enum | DI QueryExecutionEvidenceItem.result/presence status | 是 | 否 | 区分 populated、empty、failed、unknown |
| Provider | Provider | Text | DI candidate/query lineage.provider | 是 | 否 | 指标和查询来源 |
| 估算方法状态 | Estimate Method Status | Enum / Nullable | DI KeywordMetricCandidate.estimate_method_status | 是 | 否 | Provider 方法未知时明确显示 |
| 周期状态 | Period Status | Enum | DI metric period fields / EE profile | 是 | 是 | 判断时间可比性 |
| 限制 | Limitations | Text List | DI diagnostics/out-of-scope; fixed boundary labels | 是 | 否 | 常驻显示“不构成需求保证” |
| Demand Snapshot ID | Demand Snapshot ID | ID | DI.snapshot_id / OO keyword row.source_snapshot_id | 是 | 是 | 审计定位 |

### E.5 05_市场竞争证据

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 产品 | Product ASIN | Text ID | CI relationship product endpoint | 是 | 否 | 关系的一端 |
| Keyword | Keyword | Text | CI relationship keyword identity | 是 | 否 | 关系的另一端 |
| Relationship Direction | Relationship Direction | Enum | CI CompetitionRelationshipEvidence.direction | 是 | 否 | 防止方向混淆 |
| Relationship | Observed Relationship | Text | CI relationship evidence attributes | 是 | 否 | 现有关系摘要，不生成竞争判断 |
| Relationship Type | Observed Relationship Type | Enum | OO CompetitionOutputRow.relationship_type / CI source type | 是 | 否 | RANK 也只表示来源关系类型 |
| Channel | Channel | Enum | CI relationship channel | 是 | 否 | ORGANIC、SPONSORED、UNKNOWN |
| Provider | Provider | Text | CI relationship provider | 是 | 否 | 明确来源 |
| Evidence 数量 | Evidence Count | Integer | OO competition row.evidence_count / CI group inventory | 是 | 否 | 仅证据条数 |
| Evidence Classification | Evidence Classification | Enum | CI evidence.classification | 是 | 否 | 区分 OBSERVED 与 DERIVED_SIGNAL |
| Variation Evidence 数量 | Variation Evidence Count | Integer | CI variation evidence inventory | 是 | 否 | 当前 variation 证据条数 |
| Query 状态 | Query Status | Enum / Nullable | CI linked query evidence when available | 是 | 否 | 空查询不等于无竞争 |
| 限制 | Limitations | Text List | CI diagnostics; OO limitations | 是 | 否 | 固定显示“不是竞争强度或排名” |
| Competition Output Row ID | Competition Output Row ID | ID | OO CompetitionOutputRow.output_row_id | 是 | 是 | 审计定位 |

### E.6 06_产品结构分析

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 市场站点 | Marketplace | Text | PI product identity.marketplace | 是 | 否 | 聚合边界 |
| 产品类型 | Product Type | Text / State | PI exact product_type fact candidates | 是 | 否 | 不推断；多候选进入 MULTIPLE_CANDIDATES |
| 产品数量 | Product Count | Integer | Stable unique PI product identities per exact type | 是 | 否 | 当前证据 inventory 数量 |
| 产品占比 | Observed Share | Percentage / Nullable | Mechanical count / in-scope observed product count | 是 | 否 | 只表示当前证据覆盖占比，不是市场份额 |
| 销量证据摘要 | Sales Evidence Summary | Text | PI sales metric candidates with unit/method | 是 | 否 | 并列现有证据，不跨语义汇总 |
| 最低价格 | Minimum Comparable Price | Decimal / Nullable | Mechanical min of comparable PI price evidence | 是 | 否 | 仅相同币种、单位和时间语义 |
| 最高价格 | Maximum Comparable Price | Decimal / Nullable | Mechanical max of comparable PI price evidence | 是 | 否 | 不可比较时 NOT_COMPARABLE |
| 币种 | Currency | Text / Nullable | PI ProductMetricSeries.currency | 是 | 否 | 价格范围比较边界 |
| 主要特点 | Observed Feature Inventory | Text List | Exact PI fact dimensions/value frequency | 是 | 否 | 频次 inventory，不表示卖点 |
| 数据状态 | Data State | Enum | PI candidate states; EE quality profiles | 是 | 否 | 说明分组可靠边界 |
| Provider 数量 | Provider Count | Integer | Unique PI candidate providers | 是 | 否 | 数据覆盖描述，不是信心分 |
| 限制 | Limitations | Text List | PI diagnostics / fixed aggregation limits | 是 | 否 | 显示候选、可比性和覆盖限制 |
| Member Product IDs | Member Product IDs | ID List | PI included product identities | 是 | 是 | 结构组审计 |

### E.7 07_机会分析

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 产品 | Product | Text ID / State | OI signal subjects; OO opportunity row.product | 是 | 否 | 单一 identity 显示；多个显示 MULTIPLE/UNRESOLVED |
| Demand Signal | Demand Signal | Text List | OI signals with demand source/type | 是 | 否 | 展示已有 signal，不生成需求结论 |
| Competition Signal | Competition Signal | Text List | OI competition-related signals | 是 | 否 | 关系/证据 signal，不生成强度 |
| Product Signal | Product Signal | Text List | OI product fact/metric/review signals | 是 | 否 | 展示现有 product signal |
| Signal Classification | Signal Classification | Enum List | OI OpportunitySignalEvidence.classification | 是 | 否 | 区分 OBSERVED_SIGNAL 与 DERIVED_SIGNAL |
| Missing Evidence | Missing Evidence | Text List | OI missing_evidence_inventory | 是 | 否 | 明确下一步缺什么 |
| Risk | Risk Evidence | Text List | OI risk_evidence | 是 | 否 | 只描述证据限制，无概率 |
| Score Factor | Score Factor | Text | OS ScoreFactorDefinition.name | 是 | 否 | 说明分值因素 |
| 规则过程分值 | Rule Process Score | Integer / Nullable | OS ScoreCalculationRecord.result_value | 是 | 否 | 0–100 过程结果，不是成功概率 |
| Score Status | Score Status | Enum | OS ScoreCalculationRecord.result_status | 是 | 否 | 不可用时不补零 |
| Score Reference | Score Reference | ID | OS calculation_id / OO score_references | 是 | 否 | 复核现有计算 |
| Score Interpretation | Score Interpretation | Text | OS process_interpretation / explanation | 是 | 否 | 固定说明无 recommendation/decision 含义 |
| Explanation Reference | Explanation Reference | ID | OS ScoreExplanationRecord.explanation_id | 是 | 是 | 审计定位 |
| 限制 | Limitations | Text List | OI risk/missing; OS explanation and fixed boundary | 是 | 否 | 固定显示“不是机会保证” |
| Opportunity Output Row ID | Opportunity Output Row ID | ID | OO OpportunityOutputRow.output_row_id | 是 | 是 | 连接审计表 |

### E.8 08_行动建议

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 产品 | Product | Text ID / State | RF lineage evidence subjects | 是 | 否 | 仅唯一可解析产品显示，否则 UNRESOLVED |
| Recommendation Type | Recommendation Type | Enum | RF generation.recommendation_type; OO recommendation row | 是 | 否 | 保留原机器码 |
| 建议显示标签 | Recommendation Display Label | Text | Fixed one-to-one presentation mapping | 是 | 否 | 例如“进一步复核”，不改变原 type |
| Reason | Reason | Text | RF explanation.rule_explanation / process interpretation | 是 | 否 | 现有解释的简短展示 |
| Rule Reference | Rule Reference | ID | RF generation.rule_id | 是 | 否 | 说明规则来源 |
| Policy Status | Policy Status | Enum | RF applicability.policy_status | 是 | 否 | Policy blocked 必须明显 |
| Conflict Status | Conflict Status | Enum | RF applicability.conflict_status | 是 | 否 | 冲突持续可见 |
| Missing Requirements | Missing Requirements | Text List | RF applicability.missing_evidence_requirements | 是 | 否 | 指导补充数据 |
| Evidence | Evidence References | ID List | RF generation.input_evidence_ids | 是 | 否 | 审计当前建议使用的证据 |
| Evidence 数量 | Evidence Count | Integer | Mechanical count of input_evidence_ids | 是 | 否 | 便于扫描，不表示支持强度 |
| Limitation | Limitations | Text List | RF explanation.limitations; OO limitations | 是 | 否 | 固定显示“不是购买建议” |
| 人工状态 | Manual Review Status | Enum / Editable | UI only | 是 | 否 | 未复核、进一步调研、补充数据、人工审核、已复核 |
| Recommendation Record ID | Recommendation Record ID | ID | RF recommendation_generation_id | 是 | 是 | 审计定位 |
| Source Snapshot ID | Source Snapshot ID | ID | RF.snapshot_id / OO source_snapshot_id | 是 | 是 | 版本定位 |
| Operator Output Row ID | Operator Output Row ID | ID | OO RecommendationOutputRow.output_row_id | 是 | 是 | 连接数据审计表 |

### E.9 09_数据审计

| 中文名称 | English Name | 类型 | 数据来源 | 展示 | 默认隐藏 | 运营用途与显示逻辑 |
|---|---|---|---|---|---|---|
| 审计记录 ID | Audit Record ID | ID | Deterministic presentation identity | 是 | 是 | 唯一定位审计行 |
| 来源 Sheet | Source Sheet | Text | XD worksheet definition | 是 | 是 | 回到可见 Sheet |
| 展示行键 | Display Row Key | ID | V1 presentation row identity | 是 | 是 | 定位运营行 |
| Excel 行号 | Excel Row | Integer | XD cell/row mapping | 是 | 是 | 物理工作簿定位 |
| 展示字段 | Display Field | Text | V1 field dictionary name | 是 | 是 | 定位具体字段 |
| Excel Cell | Excel Cell | Text | XD CellRenderRecord.coordinate | 是 | 是 | 精确单元格追溯 |
| Operator Export Row ID | Export Row ID | ID | OE ExportRowRecord.export_row_id | 是 | 是 | 连接 Export |
| Operator Output Row ID | Output Row ID | ID | OE/OO lineage | 是 | 是 | 连接 Output |
| Evidence ID | Evidence ID | ID | Canonical observation/source record ID | 是 | 是 | 证据主引用 |
| Provider | Provider | Text | Canonical/XD lineage.provider | 是 | 是 | 识别来源 |
| Source Tool | Source Tool | Text | Canonical/XD lineage.source_tool | 是 | 是 | 识别采集工具 |
| Source Field | Source Field | Text | Canonical/XD lineage.source_field | 是 | 是 | 识别来源字段 |
| Raw Reference | Raw Evidence Reference | ID | lineage.raw_evidence_id | 是 | 是 | 只保存引用，不保存 raw payload |
| Collection Run | Collection Run ID | ID | lineage.collection_run_id | 是 | 是 | 采集批次追溯 |
| Transformation | Transformation Run ID | ID | lineage.transformation_run_id | 是 | 是 | 转换追溯 |
| Mapping Version | Mapping Version | Text | lineage.mapping_version | 是 | 是 | 映射规则追溯 |
| Canonical Reference | Canonical Reference ID | ID | lineage canonical observation/query reference | 是 | 是 | Canonical 记录定位 |
| Lineage | Lineage ID | ID | XD/OE/OO lineage ID | 是 | 是 | 端到端链路定位 |
| Source Snapshot | Source Snapshot ID | ID | PI/DI/CI/OI/OS/RF/OO/OE/XD snapshot IDs | 是 | 是 | 版本边界 |
| Bundle Fingerprint | Source Bundle Fingerprint | SHA-256 List | lineage.source_bundle_fingerprints | 是 | 是 | Canonical bundle 完整性检查 |

## F. Data Source Mapping

### F.1 Sheet-to-source matrix

| Sheet | Primary source | Secondary source | Presentation operation | Prohibited interpretation |
|---|---|---|---|---|
| 01_市场概览 | OI signals, missing evidence, risks, coverage | EE support/quality/conflict profiles | 标量投影、计数、固定限制 | 市场规模或趋势保证 |
| 02_产品数据库 | PI facts, metrics, variation, reviews | EE quality/conflicts; OO row IDs | 单一候选投影、状态显示 | 最终事实裁决 |
| 03_TOP产品分析 | PI explicit rank metric evidence | PI facts/metrics for context | 同语义范围内稳定排序 | 最佳产品、跨来源排名 |
| 04_关键词需求分析 | DI metrics, query, relationship, related products | EE quality/conflicts | 指标分列、状态分列 | 需求保证、空查询=零需求 |
| 05_市场竞争证据 | CI relationships/variations/graph | OO competition rows | 关系字段拆分、证据计数 | 竞品排名、竞争强度 |
| 06_产品结构分析 | PI product facts and comparable metrics | EE profile/diagnostics | exact grouping、可比范围统计 | 聚类、卖点推断、市场份额 |
| 07_机会分析 | OI signals/missing/risks | OS components/calculations/explanations | 并列展示现有记录 | 成功概率、机会保证 |
| 08_行动建议 | RF generation/applicability/explanation | OO recommendation rows; UI status | 标签映射、人工状态 | 购买建议、自动选择 |
| 09_数据审计 | XD/OE/OO lineage | Canonical references and upstream snapshots | 一对多 lineage 展开 | raw payload 泄露 |

### F.2 End-to-end lineage

    Visible Workbook Field
             ↓
    V1 Presentation Row Key
             ↓
    XLSX Cell / Export Row
             ↓
    Operator Output Row
             ↓
    Intelligence / Evaluation / Score / Recommendation Record
             ↓
    Canonical Observation or Query Execution
             ↓
    Transformation Run + Mapping Version
             ↓
    Raw Evidence Reference + Collection Run

每个可见行至少保留一个隐藏 Row Key。任何由多个来源记录构成的摘要都必须在 09_数据审计 中展开为多条 lineage，而不是只保留一个代表来源。

### F.3 Candidate projection

| Source condition | Visible value | Visible state | Audit behavior |
|---|---|---|---|
| One distinct present candidate | Candidate normalized value | PRESENT | 保存全部 candidate lineage |
| No present candidate | Blank | MISSING / EXPLICIT_NULL / UNKNOWN | 保存非 present evidence lineage |
| Multiple distinct present candidates | Blank or “Multiple candidates” | MULTIPLE_CANDIDATES | 展开全部候选，不选择值 |
| Unit/currency/period mismatch | Blank aggregate | NOT_COMPARABLE | 列出所有原值和语义 |
| Metric absent from snapshot | Blank | NOT_AVAILABLE | 不生成 observation 或 lineage |
| Empty directional query | 0 related rows only for that execution | EMPTY_QUERY_RESULT | 保留 query execution lineage，不推导需求 |

### F.4 Manual status separation

人工状态保存在 Workbook UI 层：

- 默认值为“未复核”；
- 不参与 snapshot ID、score 或 recommendation 计算；
- 不改变后端 source record；
- 如未来需要上传，必须进入独立的 operator workflow contract，而不是写回 Canonical Evidence。

## G. Operator Workflow

### Step 1 — 查看市场概览

运营先确认 Marketplace、类目候选、已观察产品数、Provider、风险和分析限制。若市场规模证据、趋势或时间语义为 NOT_AVAILABLE/UNKNOWN，不进入“市场已验证”的结论。

### Step 2 — 筛选产品数据库

按 Marketplace、Product Type、Price State、Rating State、BSR Context、Sales Evidence Type、Data State 和 Conflict State 筛选。复制 ASIN 前先确认关键指标的 Provider、单位和时间状态。

### Step 3 — 查看 TOP 产品

只在同一 Rank Provider、Rank Metric、Rank Context、Channel 和可比较 Period 内排序。该步骤用于查看来源排名记录，不用于挑选“最佳产品”。

### Step 4 — 查看关键词需求

筛选 Keyword、Provider、Direction、Channel 和 Query Status。Search Volume、CPC、ABA Rank、Difficulty 必须分别检查 State、Unit/Currency、Period 和 Estimate Method Status。

### Step 5 — 查看市场竞争证据

从产品或 Keyword 下钻关系行，确认 Direction、Observed Relationship Type、Channel、Provider 和 Evidence Count。不得将 Evidence Count 或 RANK relationship 转为竞争强度。

### Step 6 — 查看机会分析

并列阅读 Demand、Competition、Product Signal、Missing Evidence 和 Risk。只有 result_status 可用时才展示规则过程分值；分值不得解释为成功概率。

### Step 7 — 人工复核建议

阅读 Recommendation Type、Reason、Policy/Conflict Status、Missing Requirements、Evidence 和 Limitation，再选择人工状态：进一步调研、补充数据、人工审核或已复核。该状态不改变系统建议。

### Audit drill-down

任何步骤发现异常时：

1. 复制隐藏 Row Key 或 Output Row ID；
2. 取消隐藏 09_数据审计；
3. 筛选 Source Sheet 和 Display Row Key；
4. 检查 Evidence ID、Provider、Transformation、Mapping Version 和 Raw Reference；
5. 回到原业务表记录人工复核状态，不编辑审计值。

## H. Future Dashboard Mapping

### H.1 Page mapping

| Workbook Sheet | Future dashboard page | Primary components | Filters | Drill-down |
|---|---|---|---|---|
| 01_市场概览 | Dashboard 首页 | Coverage cards、risk panel、evidence indicator table | Marketplace、category、provider | Evidence profile / risk detail |
| 02_产品数据库 | 产品列表 | Filterable grid、state badges、candidate drawer | ASIN、brand、type、price/rating state | 产品详情、候选证据 |
| 03_TOP产品分析 | 市场表现 | Rank-context table、source badge | Provider、rank metric、context、channel、period | Rank observation detail |
| 04_关键词需求分析 | Keyword 页面 | Metric cards、query status、related products | Keyword、provider、direction、channel、status | Metric candidates、query execution |
| 05_市场竞争证据 | 竞争证据页面 | Relationship grid / evidence graph | Product、keyword、channel、provider、type | Relationship and variation evidence |
| 06_产品结构分析 | 产品结构页面 | Exact-type distribution、comparable price range | Marketplace、type、currency、state | Member products and candidates |
| 07_机会分析 | Opportunity 页面 | Signal panels、missing/risk list、score status | Product、signal type、risk、score status | Score explanation and lineage |
| 08_行动建议 | Review Queue | Recommendation list、manual-status control | Type、policy、conflict、manual status | Rule、explanation、evidence |
| 09_数据审计 | Audit Drawer | Lineage timeline、record inspector | Evidence ID、provider、snapshot、row key | Canonical / transformation references |

### H.2 Shared dashboard entities

Excel 与未来 Dashboard 应共享以下稳定实体键：

- Product ID / ASIN + Marketplace；
- Keyword ID；
- Output Row ID；
- Export Row ID；
- Recommendation Generation ID；
- Score Calculation ID；
- Evidence / Observation ID；
- Lineage ID；
- Snapshot ID；
- Source Bundle Fingerprint。

这些键用于页面间导航，不用于业务排序或偏好。

### H.3 Presentation contract needed for implementation

未来实现应新增独立、版本化的 Workbook Presentation Contract，而不是修改现有 Intelligence 或 Scoring 模型。该 contract 至少需要：

- 九张 Sheet 的固定顺序与字段定义；
- row grain 和 deterministic row key；
- candidate projection state；
- visible/hidden column metadata；
- human label 与 raw code 的一对一映射；
- manual-status column metadata；
- visible row 到完整 lineage 的交叉引用；
- fixed warnings 和 limitations；
- deterministic serialization and workbook rendering identity。

本设计没有实现该 contract，也没有修改现有五表 XLSX Delivery V0.1。

## Verification checklist

- Workbook 产品目标、用户和非目标已定义；
- 九张 Sheet 的顺序、可见性、粒度和用途已定义；
- 每个字段均定义中文名、英文名、类型、来源、展示、默认隐藏和运营用途；
- 每张 Sheet 的来源和禁止解释已定义；
- 七步运营流程和审计下钻已定义；
- 九张 Sheet 到未来 Dashboard 页面的映射已定义；
- 所有 aggregation 均限定为机械、可比语义内的展示操作；
- 未提出后端模型、Evidence、Decision、Scoring 或 Recommendation 逻辑修改；
- 未生成代码、测试或 Git 提交。

### Implementation acceptance notes

Operator Workbook V0.2 独立验收记录以下显式差异，避免将实现能力静默描述为设计能力：

1. `03_TOP产品分析` 在没有显式 rank evidence 时保留一条 `NOT_AVAILABLE` 空状态记录，而不是完全无数据行。原因是运营者仍需看到 ASIN、Marketplace、限制和“非最佳产品”警告；影响是该 Sheet 的数据行数为 1，但不会生成、替代或推断排名。
2. `09_数据审计` 当前采用“展示行 × lineage reference”粒度，`Display Field` 为 `ROW_LINEAGE`、`Excel Cell` 为 `ROW:<n>`，未宣称单元格级来源归属。原因是 Operator Output V0.1 只提供行级 lineage inventory，没有字段到 lineage 的已验证绑定；将每条行 lineage 笛卡尔复制给每个单元格会制造伪精度。影响是任一展示行可完整追到真实 Operator Export Row、Operator Output Row、Source Snapshot 和 Canonical lineage，但精确单元格级归因留待未来 presentation contract 提供后实现。
