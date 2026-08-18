# Operator Export Foundation V0.1

## 1. Purpose

Operator Export V0.1 将一个已经序列化并通过校验的 Operator Output Snapshot 投影为运营可消费、可审计且确定性的导出结构。该层只改变展示形式，不修改证据、分析结果、评分、决策或建议。

固定数据流为：

```text
Canonical Evidence Bundles
          ↓
Serialized Operator Output Snapshot
          ↓
Operator Export Snapshot
          ├── CSV-ready tables
          ├── workbook representation
          ├── export metadata
          └── export lineage
```

规则集版本固定为：

```text
operator-export-v0.1
```

## 2. Boundary

生产代码只依赖 Python 标准库、`amazon_product_intelligence.contracts` 和本包内相对模块。它不导入 Operator Output 或任何 intelligence、scoring、recommendation、adapter 模块；输入是 Operator Output 的序列化映射。

本层允许：

- 固定表结构和列顺序；
- 稳定的行顺序；
- CSV 序列化和 UTF-8 字节；
- 工作簿、工作表、元数据和 lineage 的结构化表示；
- 对输入、身份、来源关系和 canonical lineage 的 fail-closed 校验。

本层禁止：

- 新增或修改产品、需求、竞争或机会分析；
- 计算 demand score、competitor score 或 opportunity score；
- 生成、筛选或改写 recommendation；
- 推断缺失、未知或空查询的业务含义；
- 输出 credential、secret、token、authorization 或 raw payload。

## 3. Public API

公开接口严格限定为：

```text
OPERATOR_EXPORT_RULESET_VERSION
OperatorExportRequest
OperatorExportSnapshotV0_1
OperatorExportBuilderV0_1
OperatorExportError
OperatorExportValidationError
OperatorExportSerializationError
ExportTableDefinition
ExportSheetDefinition
ExportRowRecord
ExportWorkbookRecord
ExportCoverageSummary
ExportLineageReference
ExportDiagnostic
```

构建入口：

```python
request = OperatorExportRequest(
    canonical_bundles=canonical_bundles,
    operator_output_snapshot=serialized_operator_output,
)
snapshot = OperatorExportBuilderV0_1().build(request)
snapshot.validate_against_bundles(canonical_bundles)
```

## 4. Workbook and sheets

工作簿文件名固定为：

```text
amazon_product_analysis.xlsx
```

V0.1 提供确定性的工作簿表示，不生成或写入二进制 `.xlsx` 文件。`to_workbook_dict()` 返回包含文件名、元数据、工作表、表头、行以及 sheet lineage inventory 的 JSON-compatible 结构。

固定工作表和列如下。

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

`Source Reference` 保存来源 Operator Output row、来源 snapshot 和其 lineage reference IDs。该表不计算产品评分。

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

查询执行状态、空结果、未知状态和限制保持原样，不推导 demand score。

### 03_竞争证据

```text
Product Endpoint
Keyword Relationship
Channel
Provider
Evidence Count
Variation Evidence
Limitations
```

已有 `relationship_type` 保存在 `Keyword Relationship` 的结构化 JSON 单元格中，因此不会因固定列集合而丢失。该表不包含 competitor ranking 或 competitor score。

### 04_机会分析

```text
Product
Signals
Missing Evidence
Risk Evidence
Score References
Explanation References
```

Score 和 explanation 仅作为已有引用展示，不执行计算。

### 05_建议与复核

```text
Recommendation Type
Rule Reference
Explanation
Evidence References
Limitations
```

所有行来自已有 Recommendation Output Row，不生成新建议。

## 5. CSV contract

以下方法提供内存中的 CSV 结果：

```text
snapshot.to_csv(table_key)        -> str
snapshot.to_csv_bytes(table_key)  -> UTF-8 bytes
snapshot.to_csv_files()           -> {sheet_name.csv: bytes}
```

CSV 使用标准库 writer，规则为：

- 列严格按固定 schema 输出；
- 行按来源 Operator Output Row ID 排序；
- 复杂值先转换为 canonical JSON；
- 逗号、引号和换行由 CSV writer 安全转义；
- 行结束符固定为 LF；
- 编码固定为 UTF-8；
- 不读取目录顺序、不使用 locale。

这些方法只返回内存值，不写文件系统。

## 6. Identity and determinism

所有 table、sheet、row、workbook、diagnostic、lineage 和 snapshot ID 都采用：

```text
prefix + ":" + SHA256(canonical JSON)
```

V0.1 不使用 time、UUID、random、进程 hash、`repr()`、文件系统顺序或 locale。Canonical bundle 顺序、输入映射键顺序和独立 Python 进程不会改变输出身份或序列化结果。

基准 fixture 的确定性结果为：

```text
snapshot_id: operator-export-snapshot:8b0dbaa1e8b09240c5a3bacd4c1e05a46c59eb841fe5433765b9cb3e9ddec7ba
tables: 5
sheets: 5
rows: 17
lineage references: 332
diagnostics: 1
```

该 fixture inventory 为验收证据，不是对任意生产输入的固定行数承诺。

## 7. Lineage and validation

每条导出 lineage 固定连接：

```text
Export Row
    ↓
Operator Output Row
    ↓
Operator Output Lineage
    ↓
Source Intelligence Snapshot / Source Record
    ↓
Canonical Observation or Query Execution Record
    ↓
Transformation Run
    ↓
Raw Evidence Reference
```

每条引用显式保留 Operator Output lineage ID 和来源 intelligence `source_lineage_id`。`validate_against_bundles()` 使用 canonical bundles 重放 canonical reference、transformation run、mapping version、raw evidence、collection run、provider、source tool、source field、semantic observation ID 和 bundle fingerprint。

校验会拒绝：

- 未被任何导出行引用的 orphan lineage；
- 缺失或错误的 output row、source record 或 canonical emission；
- lineage 指向错误 table 或 sheet；
- 重复导出同一个 Operator Output lineage；
- table、sheet、row、workbook、diagnostic、lineage 或 snapshot 身份不匹配；
- bundle 或 lineage fingerprint 不匹配；
- 未知字段、无效类型、非有限 JSON、重复 ID 或不完整 inventory；
- 禁止的秘密字段或 raw payload。

## 8. Immutability and serialization

Request 在边界复制、规范化并深度冻结序列化 Operator Output。Snapshot 及其所有公开 records 为 frozen dataclass；嵌套 mappings 使用只读代理，arrays 使用 tuples。

`to_dict()` 产生 JSON-compatible 深拷贝，`to_json()` 产生 canonical JSON，`from_dict()` 严格拒绝未知或缺失字段。严格 round-trip 保持内容和身份不变。

## 9. V0.1 limitations

- 不生成二进制 `.xlsx`；
- 不直接创建、覆盖或保存 CSV 文件；
- 不提供格式、公式、图表、筛选器或单元格样式；
- 不重新解释上游 unknown、missing、null、zero 或 empty query；
- 不执行跨 Provider 裁决；
- 不提供新的评分、排名、决策或建议。

需要实际文件时，调用方可以显式保存 `to_csv_files()` 的字节，或用 `to_workbook_dict()` 驱动独立的文件渲染边界；该行为不属于 Operator Export V0.1 核心合同。
