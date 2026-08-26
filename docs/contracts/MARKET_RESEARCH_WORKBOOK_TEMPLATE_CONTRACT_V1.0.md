# Market Research Workbook Template Contract V1.0

Date: 2026-08-26
Ruleset: `operator-template-contract-v1.0`
Status: frozen by TASK-SP-041A

The normative machine-readable contract is
`MARKET_RESEARCH_WORKBOOK_TEMPLATE_CONTRACT_V1.schema.json`. Runtime constants
and fail-closed validation live in
`amazon_product_intelligence.operator_template_contract`.

## Workbook structure

Visible sheets, in exact visible order:

1. 综合说明
2. 类目
3. 市场调研
4. 竞品数据
5. 不同维度分析
6. 分析模型对比
7. top100—日单量分析
8. 产品初步筛选范围
9. 价格核算
10. 样品类型
11. 竞品收集

Hidden support sheets (ordinary `hidden`, never `veryHidden`):

- 自动化配置
- 原始数据源
- 关键词1—数据源
- 自动化辅助

The validator requires exactly these 15 names, the exact visible order, and
the four hidden states. Structural drift fails closed.

## Raw-source contract

`原始数据源` has exactly 66 unique headers. Mapping is by exact header name,
never by column index; column order may change. Every field is classified as
`CORE`, `OPTIONAL`, or `OUT_OF_SCOPE` in the machine schema.

- `LQS` and `SP广告` are `OUT_OF_SCOPE`; CPF绿标 is explicitly outside MVP
  and is not one of the 66 headers.
- provider `毛利率` is optional reference evidence only and is never
  procurement truth.
- SellerSprite monthly sales/revenue are third-party estimates.
- missing, blank, NA, or parse failure never becomes numeric zero.

No raw rows or original workbook bytes are part of this contract.

## Formula and dependency contract

The planning/reference census is frozen as approximate context:

| Sheet | Approximate formulas |
|---|---:|
| 市场调研 | 3 |
| 不同维度分析 | 1,150 |
| 自动化配置 | 2 |
| 关键词1—数据源 | 961 |
| 分析模型对比 | 108 |
| 自动化辅助 | 24,514 |
| **Total** | **26,738** |

The read-only auditor records exact local counts and SHA-256 fingerprints from
sorted `(sheet, coordinate, exact formula, token signature, disposition)`
records. It does not calculate or rewrite formulas. Numeric formula literals
are extracted with the installed `openpyxl.formula.Tokenizer`, so digits in
cell references are not misreported as business thresholds.

Required dependencies:

- named ranges `PivotSourceKeyword`, `PivotSourceCompetitor`, `可选蓝色参数`;
- AutoFilters on `竞品数据`, `关键词1—数据源`, and `原始数据源`;
- tables and pivots are inventoried when present.

## Formula responsibility classification

| Area | Classification |
|---|---|
| category-neutral support and presentation formulas | `REUSE_AS_FORMULA` |
| numeric bands and hard-coded business literals | `MOVE_TO_CONFIG` |
| market/decision metrics consumed by JSON or AI | `IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL` |
| provider gross margin and the current value-only price-calculation results | `DEPRECATED` |

`价格核算` values are not accepted as a calculation contract. The 30% default
target gross margin is frozen as configuration metadata only; implementation
belongs to SP-041F, not SP-041A.

The exact external reference-workbook values for price, review, review-rate,
FBA, listing-age, new-product-window, and category-semantic thresholds remain
marked `EXTERNAL_REFERENCE_WORKBOOK_VALUE_REQUIRES_LOCAL_AUDIT`. The auditor
produces their deterministic literal inventory when that private workbook is
available; SP-041A does not invent missing values.

## Product-selection semantics

Before `DIRECTION_LOCKED`:

- `产品初步筛选范围` means candidate Product Archetypes;
- `样品类型` means hypotheses and sampling directions;
- `竞品收集` may contain representative ASINs only and may not label them
  Direct Competitors.

Only after `DIRECTION_LOCKED` may a Direct Competitor Set exist.

## Reproducible local audit

```powershell
.\.venv\Scripts\python.exe scripts\audit_operator_template_v1.py `
  --workbook "C:\path\to\private-template.xlsx" --validate
```

The command writes only sanitized contract metadata to stdout. It does not
emit workbook data rows, call a provider, construct a network client, or write
back to the workbook.
