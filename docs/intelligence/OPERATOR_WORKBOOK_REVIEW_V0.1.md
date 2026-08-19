# Operator Workbook Sample Delivery & Usability Review V0.1

## Review boundary

本次审查基于以下正式基线：

```text
branch: main
HEAD: 55fe25cc6f6e293d8acd6dd0d9351b5e5e47fc94
subject: feat: add xlsx operator delivery v0.1
runtime: Python 3.12.10
PYTHONPATH: src
```

样例工作簿由现有完整链路和既有验收 fixture 生成。本次任务未修改 Canonical Evidence、Intelligence、Evidence Evaluation、Conflict Resolution、Evidence Policy、Decision、Opportunity Scoring、Recommendation、Operator Output、Operator Export 或 XLSX Delivery 的任何模型、规则和实现。

本报告只评价样例工作簿的展示与运营可用性。`CHANGE` 表示下一迭代可在展示层调整；不表示修改来源数据、证据语义或分析结论。

## A. Workbook Summary

### A.1 Delivery identity

```text
filename: amazon_product_analysis.xlsx
size: 52,260 bytes
SHA-256: eaf38a07779e524b9df8caa005b94cdcb3d6a5cf60e010dd966b612439ab2508
delivery snapshot: xlsx-delivery-snapshot:c7404d4c2a70d3e1b8fdad629509c0e708d5cb0b9034be2691751148a13c5d15
operator export snapshot: operator-export-snapshot:8b0dbaa1e8b09240c5a3bacd4c1e05a46c59eb841fe5433765b9cb3e9ddec7ba
operator output snapshot: operator-output-snapshot:c1b2618855d5f26478b289882a5e46612d25adeb4b9306d52c6d1fc48bfa013b
```

### A.2 Workbook inventory

| Sheet | Source rows | Excel data rows | Columns | Review observation |
|---|---:|---:|---:|---|
| `01_产品数据` | 1 | 1 | 9 | 产品身份明显，但事实、指标、变体、评论和质量信息以长 JSON 展示 |
| `02_关键词需求` | 1 | 1 | 7 | 关键词、指标和查询状态均保留，但主要业务值埋在 JSON 中 |
| `03_竞争证据` | 10 | 10 | 8 | Channel、Provider 和 Evidence Count 易扫描，关系内容仍偏技术化 |
| `04_机会分析` | 1 | 6 | 6 | 一个来源行因 Excel 单元格长度限制拆成 6 个 continuation rows |
| `05_建议与复核` | 4 | 4 | 5 | 推荐类型和限制明显，规则、解释和证据引用过于密集 |
| **Total** | **17** | **22** | — | **152 个 data cells；332 条 delivery lineage references** |

工作簿包含且只包含规定的五张可见工作表，没有隐藏工作表。工作表顺序、标题和中文显示正确。

### A.3 Excel usability controls

| Check | Result | Notes |
|---|---|---|
| 中文显示 | PASS | 五张表的中文名称和 title row 均正常显示 |
| 冻结 | PASS | 所有工作表固定为 `A2`；第 1 行 title row 冻结 |
| 筛选 | PASS | 五张表均从第 2 行 header 到最后 data row 启用筛选 |
| 列宽 | PASS WITH LIMITATION | 列宽固定且内容可见，但总表宽较大，需要较多横向滚动 |
| 自动换行 | PASS WITH LIMITATION | 所有非空数据单元格启用换行；固定 48pt 行高无法直接展开大段 JSON |
| 长文本 | PASS FOR LOSSLESS DELIVERY | 最大单元格 30,000 字符；超长内容使用 continuation rows 无损保存 |
| 数据密度 | CHANGE | 产品表非空单元格平均约 6,953 字符；机会表约 17,000 字符，超出日常扫描负荷 |
| 字段顺序 | KEEP WITH DISPLAY CHANGES | 身份字段位于前部是正确的；摘要字段应先于审计 JSON 和 lineage 引用 |

## B. Field Review

评价含义：

- `KEEP`：字段及当前语义适合保留；允许做轻量标签或格式优化。
- `CHANGE`：字段必须保留其来源语义，但建议在展示层拆分、重命名或默认隐藏详细内容。
- `REMOVE`：从工作簿交付中移除。当前没有字段满足该条件，因为审计字段仍有用途。

### B.1 `01_产品数据`

| Field | Evaluation | Display action | Operator review |
|---|---|---|---|
| ASIN | KEEP | KEEP | `B0G2VV4RBW` 位于首列，身份明显且可筛选 |
| Marketplace | KEEP | KEEP | `US` 简洁清楚 |
| Title | CHANGE | SPLIT / RENAME | 当前是带 evidence 与 lineage 的 JSON 数组，不是可直接阅读的商品标题；建议新增只读 `Display Title`，原证据详情保留为 audit detail |
| Product Facts | CHANGE | SPLIT | 将可用的品牌、类目、价格等候选分别展示，并保留 evidence state；不得把 candidate 伪装为最终事实 |
| Metrics | CHANGE | SPLIT | 指标名称、值、单位、Provider、evidence type 与 method status 应形成可筛选列；unknown/missing/null/zero 必须继续区分 |
| Variation | CHANGE | SPLIT / HIDE DETAIL | 主视图显示 parent/child 摘要及关系状态；完整 edge JSON 默认隐藏或放入可展开详情 |
| Reviews | CHANGE | SPLIT | 优先显示 review count、rating、helpful-vote coverage 等现有摘要；完整 lineage 保留为详情 |
| Quality Indicators | CHANGE | SPLIT | 先显示 diagnostic code、严重程度和短消息；长 JSON 作为审计详情 |
| Source Reference | CHANGE | HIDE BY DEFAULT | 不可删除；建议默认隐藏完整 ID 集合，并提供短 ID 或审计展开入口 |

运营结论：产品身份清楚，数据完整性和审计性强；标题与关键指标不适合当前直接阅读方式。

### B.2 `02_关键词需求`

| Field | Evaluation | Display action | Operator review |
|---|---|---|---|
| Keyword | CHANGE | SPLIT / RENAME | 当前显示 keyword identity JSON；建议首列直接显示 normalized keyword text，并保留 marketplace/locale |
| Metrics | CHANGE | SPLIT | Search Volume、CPC 等仅在有相应证据时分别显示 Metric、Value、Unit、Provider 和 Evidence State；缺失不得显示为 0 |
| Query Status | CHANGE | SPLIT | Direction、Query Result Status 和 Presence 应为独立可筛选字段，避免运营者解析 JSON |
| Related Products | CHANGE | SPLIT | 主视图先显示 related product count 和 ASIN；详细关系证据可展开 |
| Channels | CHANGE | SPLIT | 当前数组可读但不便筛选；建议按一行一 channel 或提供原子筛选字段，继续区分 ORGANIC、SPONSORED、UNKNOWN |
| Providers | CHANGE | SPLIT | 将数组转换为筛选友好的显示值，不改变 Provider 归属 |
| Limitations | KEEP | KEEP PROMINENT | `DIRECTIONAL_QUERY_EVIDENCE_ONLY` 等限制清楚且重要，应持续可见 |

运营结论：Keyword 本身、Search Volume/CPC 等指标和 Query 状态目前不够显眼。建议增加的筛选维度仅来自现有字段：keyword text、marketplace、direction、query status、channel、provider、metric name 和 evidence state。

### B.3 `03_竞争证据`

| Field | Evaluation | Display action | Operator review |
|---|---|---|---|
| Product Endpoint | CHANGE | SPLIT | 建议直接展示 ASIN、Marketplace 和 Identity Status；完整 product identity 放入详情 |
| Relationship Evidence | CHANGE | SPLIT | 建议直接展示 Keyword、Direction 和 observed relationship 摘要 |
| Relationship Type | CHANGE | RENAME | 展示标签建议改为 `Observed Relationship Type`，明确它不是 competitor ranking |
| Channel | KEEP | KEEP | ORGANIC、SPONSORED、UNKNOWN 清晰且可筛选 |
| Provider | KEEP | KEEP | Provider 来源明确 |
| Evidence Count | KEEP | KEEP | 数量字段简单明确；只表示证据条数，不表示竞争强度 |
| Variation Evidence | CHANGE | SPLIT / HIDE DETAIL | 主视图显示是否存在及关系数量；完整 JSON 保留审计用途 |
| Limitations | KEEP | KEEP PROMINENT | `NO_COMPETITION_STRENGTH_OR_RANKING_INFERENCE` 有效防止误读，应保持明显 |

运营结论：此表是关系证据清单，不是竞品排名。`RANK` relationship type 也只能表示来源证据中的关系类型，不能改写为竞争排名。

### B.4 `04_机会分析`

| Field | Evaluation | Display action | Operator review |
|---|---|---|---|
| Product | CHANGE | SPLIT | 直接显示 ASIN/Marketplace，完整 identity JSON 作为详情 |
| Signals | CHANGE | SPLIT | 按 signal classification、channel、direction、support 和简短 message 展示；当前 30K 分块不适合运营扫描 |
| Missing Evidence | CHANGE | SPLIT | 用明确的 `None recorded` 或缺失类别摘要显示，保留 missing evidence ID 详情 |
| Risk Evidence | CHANGE | SPLIT | 风险分类和短消息应优先显示，Provider 与 lineage 放入详情 |
| Score References | CHANGE | HIDE BY DEFAULT | 保留用于复核，不应占据运营主视图；不得在展示层重算分数 |
| Explanation References | CHANGE | HIDE BY DEFAULT | 保留现有 explanation 引用，主视图显示可读摘要 |

运营结论：Signals、Missing Evidence 和 Risk Evidence 均已保留，但长 JSON 与 continuation rows 使含义不易快速理解。该表只能表达现有信号和证据状态，不构成机会保证。

### B.5 `05_建议与复核`

| Field | Evaluation | Display action | Operator review |
|---|---|---|---|
| Recommendation Type | CHANGE | RENAME FOR DISPLAY | 机器码语义明确但较长；建议增加中文或短标签，同时保留原始 type code |
| Rule Reference | CHANGE | HIDE BY DEFAULT | 规则条件 JSON 适合复核，不适合作为主视图第二列 |
| Explanation | CHANGE | SPLIT | 优先显示已有 explanation/message 的可读摘要，不生成新解释或新推荐 |
| Evidence References | CHANGE | HIDE BY DEFAULT | 审计必需但视觉密度高；通过短 ID、数量和展开详情呈现 |
| Limitations | KEEP | KEEP PROMINENT | `NO_AUTOMATIC_SELECTION`、`NO_GUARANTEE_OR_FORECAST` 等限制明显，应始终可见 |

运营结论：Recommendation Type 和 Limitations 能阻止将结果误读为购买建议；Explanation 仍需展示层提炼。任何标签优化都不得改变 `RECOMMENDATION_BLOCKED_BY_POLICY` 或 `FURTHER_REVIEW_RECOMMENDED` 的既有语义。

## C. Operator Feedback

### C.1 易懂字段

- ASIN、Marketplace；
- Competition 的 Channel、Provider、Evidence Count；
- Recommendation Type；
- 各表的 Limitations，尤其“不做竞争强度/排名推断”“不做自动选择”“不保证或预测”等限制；
- 五张表的名称、顺序和整体用途。

### C.2 难懂字段

- Product Sheet 的 Title、Product Facts、Metrics、Variation、Reviews、Quality Indicators；
- Keyword Sheet 的 Keyword、Metrics、Query Status 和 Related Products；
- Competition Sheet 的 Product Endpoint 与 Relationship Evidence；
- Opportunity Sheet 的 Signals、Risk Evidence、Score References 和 Explanation References；
- Recommendation Sheet 的 Rule Reference、Explanation 和 Evidence References。

共同原因是：字段包含可审计的结构化 JSON 和长 lineage，但没有单独的运营摘要列。固定 48pt 行高虽然控制了工作表高度，却使长文本只能通过编辑栏或展开行阅读。

### C.3 缺失的展示字段

以下是可以从现有交付值机械提取的展示字段，不是新的分析数据：

- Display Title、Keyword Text、ASIN、Marketplace；
- Metric Name、Metric Value、Unit、Provider、Evidence State；
- Query Direction、Query Result Status、Channel；
- Relationship Direction、Observed Relationship Type；
- Signal/Risk Classification、短消息和 Evidence Count；
- Recommendation Display Label、Review Status、Limitation Summary。

如果某项证据不存在，应显示 `missing` 或 `unknown`，不得猜测或填 0。

### C.4 多余字段

没有字段应从可审计交付中删除。完整 lineage、规则引用和 evidence references 对复核有价值，但在日常运营视图中应默认隐藏、折叠或移到详情区域。

## D. Next Iteration Suggestions

以下建议严格限定在展示层：

1. 在每张表中采用“运营摘要列在前、审计详情列在后”的顺序，保留所有现有源值。
2. 从现有 identity mapping 机械提取 ASIN、Marketplace、Keyword Text 和 Display Title；不进行实体裁决。
3. 将 Metrics 展开为筛选友好的长表或固定摘要列，并同时显示单位、Provider、evidence type 和 method status。
4. 将 Query Direction、Query Status、Channel、Provider、Relationship Type 和风险/信号分类变成原子筛选字段。
5. 对长 JSON 提供默认隐藏的 detail columns、分组折叠或单元格注释；不得删除 lineage。
6. 将 title row 与 header row 一起冻结，减少长表滚动时丢失字段含义的问题。
7. 对短摘要使用适当行高；对于长详情保持受控高度并提供明确的“查看详情”路径，避免 30K 文本占满主视图。
8. 为机器码增加人类可读显示标签，但原始 code 必须保留且参与审计。
9. 为 Competition、Opportunity 和 Recommendation 增加固定的语义提示：分别明确“不是竞品排名”“不是机会保证”“不是购买建议”。
10. 保持无公式、无宏、无外部链接的静态交付边界，避免在 Excel 层重算分析结果。

上述建议不要求也不授权修改 Evidence、Decision、Scoring、Recommendation 或 Canonical 数据。

## E. Security, Lineage and Determinism Review

### E.1 Security

- 逐单元格检查未发现 token、credential、secret、password、private key、authorization、raw API payload 或 internal metadata；
- 工作簿无公式、无隐藏工作表；
- JSON 内容是现有 Operator Export 字段，不是 Provider raw payload。

### E.2 Lineage

```text
17 Operator Export rows
        ↓
22 Excel data rows (including continuation rows)
        ↓
152 rendered cell records
        ↓
332 XLSX delivery lineage references
        ↓
332 Operator Export lineage references
        ↓
332 Operator Output lineage references
        ↓
Canonical lineage
```

对 152 个 cell records 逐坐标、逐值复核，差异为 0。`validate_against_export_snapshot()` 通过，continuation rows 未造成来源行或 lineage 丢失。

### E.3 Determinism

使用相同输入在独立 Python 进程中重新构建，结果与交付文件逐字节一致：

```text
SHA-256: eaf38a07779e524b9df8caa005b94cdcb3d6a5cf60e010dd966b612439ab2508
sheet order: identical
data order: identical
cell differences: 0
```

未发现变化时间戳、随机 ID 或非确定性排序。
