# Market Research Workbook Template Contract V1.0

Date: 2026-08-26
Status: planning contract; no raw user market rows are included.

## Workbook structure

Visible sheets, in order:

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

Hidden support sheets:

- 自动化配置
- 原始数据源
- 关键词1—数据源
- 自动化辅助

The four support sheets are ordinary hidden sheets, not VeryHidden.

## Raw-source header contract

`原始数据源` contains 66 columns. Mapping is by header name, never by physical column index.

`图片, ASIN, SKU, 详细参数, 品牌, 品牌链接, 商品标题, 商品详情页链接, 商品主图, 父ASIN, 类目路径, 大类目, 大类BSR, 大类BSR增长数, 大类BSR增长率, 小类目, 小类BSR, 月销量, 销量环比增长率, 销量同比增长率, 月销售额($), 子体销量, 子体销售额($), 变体数, 价格($), prime价格($), Coupon, Q&A, 评分数, 月新增评分数, 评分, 留评率, FBA($), 毛利率, 评级, 上架时间, 上架天数, 配送方式, 买家运费($), LQS, 卖家数, BuyBox卖家, BuyBox类型, 卖家所属地, 卖家信息, 卖家首页, Best Seller标识, Amazon's Choice, New Release标识, A+页面, 视频介绍, SP广告, 品牌故事, 品牌广告, 秒杀, AC关键词, 商品重量, 商品重量（单位换算）, 商品尺寸, 商品尺寸（单位换算）, 包装重量, 包装重量（单位换算）, 包装尺寸, 包装尺寸（单位换算）, 包装尺寸分段, 标签`

MVP out-of-scope fields: `LQS`, `SP广告`, `CPF绿标` (not present as a raw header but explicitly excluded). Original provider `毛利率` is reference-only and is not the system's target-margin truth.

## Formula / dependency contract

Observed approximate formula census in the reference workbook:

- 市场调研: ~3
- 不同维度分析: ~1,150
- 自动化配置: ~2
- 关键词1—数据源: ~961
- 分析模型对比: ~108
- 自动化辅助: ~24,514

Total approximate formula cells: ~26,738.

Important named ranges/definitions observed:

- `PivotSourceKeyword` derives from `关键词1—数据源` with dynamic height tied to raw-source ASIN count.
- `PivotSourceCompetitor` derives from `自动化辅助` with dynamic height tied to raw-source ASIN count.
- AutoFilter ranges exist on `竞品数据`, `关键词1—数据源`, and `原始数据源`.
- `可选蓝色参数` points into `自动化配置` and is treated as configurable business input.

## Reuse policy

- Preserve formulas that are correct and category-neutral.
- Move hard-coded thresholds to configuration where practical.
- Critical metrics used by JSON/AI must also be reproducible in code; Excel is an operator mirror, not the only calculation engine.
- `价格核算` in the reference workbook is value-oriented; V1 rebuilds its calculation contract around a configurable target gross margin, default 30%.
- Workbook structure drift must fail closed or produce an explicit compatibility diagnostic.
- Raw user workbook and the 998-row market dataset remain external acceptance assets and are not committed to Git.

## Product-selection semantics

Before a product direction is locked:

- `产品初步筛选范围` shows candidate Product Archetypes.
- `样品类型` shows hypotheses / sampling directions.
- `竞品收集` may show representative ASINs but must not label them Direct Competitors.

Only after `DIRECTION_LOCKED` may the system produce a Direct Competitor Set.
