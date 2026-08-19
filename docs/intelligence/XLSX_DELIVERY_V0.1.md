# XLSX Operator Delivery Foundation V0.1

## 1. Purpose

XLSX Operator Delivery V0.1 将一个经过验证的、序列化的 Operator Export Snapshot 渲染为实际可打开的 Excel 工作簿：

```text
Operator Export Snapshot
          ↓
XLSX Delivery Builder
          ↓
amazon_product_analysis.xlsx
```

规则集版本固定为：

```text
xlsx-delivery-v0.1
```

本层只负责文件渲染，不重新分析数据，不计算 score，不生成 recommendation，也不修改 evidence、decision 或 Operator Output。

## 2. Dependency boundary

生产代码只使用：

- Python 标准库；
- 环境中已经存在的 `openpyxl` XLSX 生成库；
- `xlsx_delivery` 包内相对模块。

当前验收运行时为 Python 3.12.10、openpyxl 3.1.5。任务未安装依赖、未修改 `pyproject.toml`、未访问网络。

生产包不导入 Contracts、Adapters、Operator Export、Operator Output 或任何 intelligence、evaluation、policy、decision、scoring、recommendation 模块。输入是 Operator Export Snapshot 的序列化映射。

## 3. Public API

公开 API 严格限定为：

```text
XLSX_DELIVERY_RULESET_VERSION
XlsxDeliveryRequest
XlsxDeliverySnapshotV0_1
XlsxDeliveryBuilderV0_1
XlsxDeliveryError
XlsxDeliveryValidationError
XlsxDeliverySerializationError
WorkbookStyleDefinition
WorksheetRenderDefinition
CellRenderRecord
WorkbookDeliveryRecord
DeliveryCoverageSummary
DeliveryLineageReference
DeliveryDiagnostic
```

基本用法：

```python
request = XlsxDeliveryRequest(
    operator_export_snapshot=serialized_operator_export,
)
delivery = XlsxDeliveryBuilderV0_1().build(request)

# 内存字节
xlsx_bytes = delivery.to_xlsx_bytes()

# 创建实际文件；目标文件必须尚不存在
delivery.write_xlsx("amazon_product_analysis.xlsx")
```

`write_xlsx()` 要求固定文件名，并使用 exclusive create，避免静默覆盖已有文件。

## 4. Workbook contract

工作簿名称固定为：

```text
amazon_product_analysis.xlsx
```

媒体类型固定为：

```text
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

工作表名称及顺序固定为：

1. `01_产品数据`
2. `02_关键词需求`
3. `03_竞争证据`
4. `04_机会分析`
5. `05_建议与复核`

不允许增加 metadata sheet、隐藏 sheet 或重新排序。

## 5. Worksheet layout and formatting

每张工作表均包含：

- 第 1 行：合并的 title row；
- 第 2 行：固定 column header；
- 第 3 行起：Operator Export data rows；
- `A2` freeze panes，用于冻结第一行；
- 从 header 到最后 data row 的 auto filter；
- 固定且可读的列宽；
- title、header、body 的字体、颜色、边框、对齐和自动换行；
- 确定性的行高和页面宽度设置。

所有样式由 `WorkbookStyleDefinition` 固化并参与 Snapshot 身份计算。

## 6. Fixed columns

### 01_产品数据

```text
ASIN
Marketplace
Title
Product Facts
Metrics
Variation
Reviews
Quality Indicators
Source Reference
```

### 02_关键词需求

```text
Keyword
Metrics
Query Status
Related Products
Channels
Providers
Limitations
```

### 03_竞争证据

```text
Product Endpoint
Relationship Evidence
Relationship Type
Channel
Provider
Evidence Count
Variation Evidence
Limitations
```

Operator Export 的 `Keyword Relationship` 已经包含 relationship evidence 和 relationship type。XLSX 层只将这两个现有值拆到两个可读列，不执行竞争判断、排名或评分。

### 04_机会分析

```text
Product
Signals
Missing Evidence
Risk Evidence
Score References
Explanation References
```

### 05_建议与复核

```text
Recommendation Type
Rule Reference
Explanation
Evidence References
Limitations
```

Opportunity 和 Recommendation 工作表只展示已有引用和记录，不执行新计算或生成。

## 7. Excel cell length safety

Excel 单元格最多安全容纳约 32K 字符。基准 Operator Export 中存在超过该限制的 JSON 值，因此 V0.1 不依赖 openpyxl 的静默截断行为。

规则如下：

- 单个文本分块最大 30,000 字符；
- 超长值按原字符顺序拆成确定性的 continuation rows；
- 同一来源行的短列只出现在第一个分块行，后续对应单元格为空；
- 每个 continuation row 和 cell 都保留同一 Source Export Row 与 lineage；
- 按 `chunk_index` 拼接并移除安全转义前缀，可以重建原始文本。

基准 fixture 有 17 个 Source Export Rows，实际渲染为 22 个 Excel data rows，共 152 个 data cells；332 条 lineage 不因分块而重复或丢失。

## 8. Formula injection protection

任何文本分块在去除前导空白后以以下字符开头时：

```text
=
+
-
@
```

写入前都会增加 leading apostrophe，并将单元格 number format 固定为文本。测试会重新打开工作簿并确认危险内容不是 formula cell。

固定标题和表头同样只作为文本写入。V0.1 不生成任何公式。

## 9. Sensitive-data boundary

Request 会递归检查普通映射、数组以及 JSON 文本单元格，拒绝包括以下类型的键：

```text
raw_payload
raw_provider_payload
credential / credentials
access_token / refresh_token
client_secret / api_secret
password
private_key
authorization
hidden_metadata / internal_metadata
```

复合键会先进行大小写和分隔符规范化，再执行 suffix 检查。敏感字段不会进入 XLSX bytes。

## 10. Determinism

Workbook、worksheet、cell、lineage、diagnostic 和 delivery snapshot 身份均使用：

```text
prefix + ":" + SHA256(canonical JSON)
```

XLSX 二进制确定性包括：

- 固定 core document properties；
- 保存后规范化 openpyxl 自动写入的 modified timestamp；
- ZIP entries 按名称排序；
- 所有 ZIP timestamps 固定为 `1980-01-01 00:00:00`；
- 固定 compression level 和 file attributes；
- 固定 sheet、row、cell 和 relationship 创建顺序。

不使用当前时间、UUID、random、进程 hash、`repr()`、文件系统顺序或 locale。

基准 fixture 的结果为：

```text
snapshot_id: xlsx-delivery-snapshot:2a316fc50778d888a450753a4ab1e1fa26567219246e8f8e5f1a467746e0eab4
content_sha256: 5003d07e7c6172291338c01a0a71a80ce9fef36949cfc5040f4793eeb9659657
size_bytes: 52267
worksheets: 5
source_export_rows: 17
rendered_rows: 22
cells: 152
lineage_references: 332
```

这些数字是验收 fixture 证据，不是任意生产输入的固定数量承诺。

## 11. Lineage

每个 data cell 固定连接：

```text
XLSX Cell / Continuation Row
    ↓
Source Export Row
    ↓
Source Export Lineage
    ↓
Operator Output Row / Lineage
    ↓
Source Intelligence Snapshot / source_lineage_id
    ↓
Canonical Observation or Query Execution
    ↓
Transformation Run
    ↓
Raw Evidence Reference
```

`validate_against_export_snapshot()` 会逐字段复核 lineage，并机械重建期望的工作表、分块行、单元格坐标和值。以下情况会被拒绝：

- orphan lineage；
- 缺失 Export Row 或 Export Lineage；
- 错误 worksheet、table 或 sheet；
- cell、row、lineage、workbook 或 snapshot 身份不匹配；
- bundle fingerprint 不匹配；
- 改写或丢失的导出值；
- 重复或不完整的 inventory。

## 12. Serialization and immutability

Request 会复制、验证、规范化并深度冻结 Operator Export mapping。Delivery Snapshot 及全部公开 records 均为 frozen dataclass；嵌套 mappings 使用只读代理，arrays 使用 tuples。

实际 XLSX bytes 以 base64 保存在 `WorkbookDeliveryRecord` 中，并同时记录 SHA-256 与字节数。反序列化时会严格验证 base64、digest、size、未知字段及所有交叉引用。

支持：

```text
to_dict()
to_json()
from_dict()
to_xlsx_bytes()
write_xlsx()
```

严格 round-trip 保持 Snapshot ID、XLSX digest 和文件字节不变。

## 13. V0.1 limitations

- continuation rows 是 Excel 单元格长度限制下的无损传输策略；消费方若需要原始长 JSON，应按来源行、列和 `chunk_index` 重组；
- 不提供公式、图表、数据透视表、宏、外部链接或隐藏工作表；
- 不重新解释 unknown、missing、null、zero 或 empty query；
- 不修改任何 score、decision、recommendation 或 evidence；
- 二进制可重复性依赖规则集指定的渲染逻辑及记录在 metadata 中的 openpyxl renderer version。
