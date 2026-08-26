"""Frozen Operator Template V1 schema declared without user workbook data."""

from __future__ import annotations

from .models import (
    OPERATOR_TEMPLATE_RULESET_VERSION,
    DependencyRequirement,
    FormulaCensusReference,
    FormulaDisposition,
    FormulaPolicy,
    OperatorTemplateContractV1,
    ProductSelectionSemantic,
    RawHeaderContract,
    RawHeaderRequirement,
    SheetContract,
    SheetVisibility,
    ThresholdRule,
    template_schema_fingerprint,
)


VISIBLE_SHEET_NAMES = (
    "综合说明",
    "类目",
    "市场调研",
    "竞品数据",
    "不同维度分析",
    "分析模型对比",
    "top100—日单量分析",
    "产品初步筛选范围",
    "价格核算",
    "样品类型",
    "竞品收集",
)

HIDDEN_SHEET_NAMES = (
    "自动化配置",
    "原始数据源",
    "关键词1—数据源",
    "自动化辅助",
)


def _header(
    name: str,
    requirement: RawHeaderRequirement,
    note: str,
) -> RawHeaderContract:
    return RawHeaderContract(
        name=name,
        requirement=requirement,
        semantic_note=note,
    )


_C = RawHeaderRequirement.CORE
_O = RawHeaderRequirement.OPTIONAL
_X = RawHeaderRequirement.OUT_OF_SCOPE

RAW_HEADER_CONTRACTS = (
    _header("图片", _O, "operator display helper"),
    _header("ASIN", _C, "listing identity"),
    _header("SKU", _C, "listing/variation identity evidence"),
    _header("详细参数", _C, "structured listing attribute evidence"),
    _header("品牌", _C, "brand identity"),
    _header("品牌链接", _O, "operator display link"),
    _header("商品标题", _C, "listing title evidence"),
    _header("商品详情页链接", _C, "listing source link"),
    _header("商品主图", _C, "listing image evidence"),
    _header("父ASIN", _C, "variation family evidence"),
    _header("类目路径", _C, "category scope evidence"),
    _header("大类目", _C, "major category scope"),
    _header("大类BSR", _C, "third-party rank estimate"),
    _header("大类BSR增长数", _C, "third-party rank change estimate"),
    _header("大类BSR增长率", _C, "third-party rank change estimate"),
    _header("小类目", _C, "minor category scope"),
    _header("小类BSR", _C, "third-party rank estimate"),
    _header("月销量", _C, "THIRD_PARTY_ESTIMATE; missing is not zero"),
    _header("销量环比增长率", _C, "third-party growth estimate"),
    _header("销量同比增长率", _C, "third-party growth estimate"),
    _header("月销售额($)", _C, "THIRD_PARTY_ESTIMATE; missing is not zero"),
    _header("子体销量", _C, "third-party variation estimate"),
    _header("子体销售额($)", _C, "third-party variation estimate"),
    _header("变体数", _C, "variation count evidence"),
    _header("价格($)", _C, "observed/estimated selling price"),
    _header("prime价格($)", _O, "optional Prime price"),
    _header("Coupon", _O, "optional promotion evidence"),
    _header("Q&A", _O, "optional engagement evidence"),
    _header("评分数", _C, "review barrier evidence"),
    _header("月新增评分数", _O, "optional review growth estimate"),
    _header("评分", _C, "rating evidence"),
    _header("留评率", _O, "optional estimated review-rate evidence"),
    _header("FBA($)", _C, "observed fee input; missing is not zero"),
    _header("毛利率", _O, "REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH"),
    _header("评级", _O, "provider display classification"),
    _header("上架时间", _C, "listing age evidence"),
    _header("上架天数", _C, "listing age evidence"),
    _header("配送方式", _O, "optional fulfilment evidence"),
    _header("买家运费($)", _O, "optional buyer shipping fee"),
    _header("LQS", _X, "MVP non-blocker"),
    _header("卖家数", _C, "seller concentration evidence"),
    _header("BuyBox卖家", _C, "seller concentration evidence"),
    _header("BuyBox类型", _O, "optional Buy Box evidence"),
    _header("卖家所属地", _O, "optional seller geography evidence"),
    _header("卖家信息", _O, "optional seller metadata"),
    _header("卖家首页", _O, "optional seller link"),
    _header("Best Seller标识", _O, "optional content/badge evidence"),
    _header("Amazon's Choice", _O, "optional content/badge evidence"),
    _header("New Release标识", _O, "optional content/badge evidence"),
    _header("A+页面", _O, "optional content-adoption evidence"),
    _header("视频介绍", _O, "optional content-adoption evidence"),
    _header("SP广告", _X, "MVP non-blocker"),
    _header("品牌故事", _O, "optional content-adoption evidence"),
    _header("品牌广告", _O, "optional content-adoption evidence"),
    _header("秒杀", _O, "optional promotion evidence"),
    _header("AC关键词", _O, "optional keyword evidence"),
    _header("商品重量", _C, "raw product weight evidence"),
    _header("商品重量（单位换算）", _C, "normalized product weight evidence"),
    _header("商品尺寸", _C, "raw product dimensions evidence"),
    _header("商品尺寸（单位换算）", _C, "normalized product dimensions evidence"),
    _header("包装重量", _O, "optional raw package weight"),
    _header("包装重量（单位换算）", _O, "optional normalized package weight"),
    _header("包装尺寸", _O, "optional raw package dimensions"),
    _header("包装尺寸（单位换算）", _O, "optional normalized package dimensions"),
    _header("包装尺寸分段", _O, "optional package-size band"),
    _header("标签", _O, "operator display helper"),
)


FORMULA_POLICIES = (
    FormulaPolicy(
        sheet_name="市场调研",
        range_ref="*",
        disposition=FormulaDisposition.IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL,
        numeric_literals_to_config=True,
        rationale="market metrics consumed by JSON/AI require code parity",
    ),
    FormulaPolicy(
        sheet_name="不同维度分析",
        range_ref="*",
        disposition=FormulaDisposition.REUSE_AS_FORMULA,
        numeric_literals_to_config=True,
        rationale="preserve category-neutral formulas; externalize bands",
    ),
    FormulaPolicy(
        sheet_name="自动化配置",
        range_ref="*",
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        numeric_literals_to_config=True,
        rationale="this sheet is the operator-facing configuration surface",
    ),
    FormulaPolicy(
        sheet_name="关键词1—数据源",
        range_ref="*",
        disposition=FormulaDisposition.REUSE_AS_FORMULA,
        numeric_literals_to_config=False,
        rationale="preserve provider-neutral keyword support formulas",
    ),
    FormulaPolicy(
        sheet_name="分析模型对比",
        range_ref="*",
        disposition=FormulaDisposition.IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL,
        numeric_literals_to_config=True,
        rationale="decision metrics require deterministic code parity",
    ),
    FormulaPolicy(
        sheet_name="自动化辅助",
        range_ref="*",
        disposition=FormulaDisposition.REUSE_AS_FORMULA,
        numeric_literals_to_config=True,
        rationale="preserve auditable helper formulas; externalize thresholds",
    ),
    FormulaPolicy(
        sheet_name="价格核算",
        range_ref="*",
        disposition=FormulaDisposition.DEPRECATED,
        numeric_literals_to_config=True,
        rationale="reference workbook is value-only; SP-041F owns the code model",
    ),
)


FORMULA_CENSUS_REFERENCE = (
    FormulaCensusReference(sheet_name="市场调研", approximate_count=3),
    FormulaCensusReference(sheet_name="不同维度分析", approximate_count=1150),
    FormulaCensusReference(sheet_name="自动化配置", approximate_count=2),
    FormulaCensusReference(sheet_name="关键词1—数据源", approximate_count=961),
    FormulaCensusReference(sheet_name="分析模型对比", approximate_count=108),
    FormulaCensusReference(sheet_name="自动化辅助", approximate_count=24514),
)


DEPENDENCY_REQUIREMENTS = (
    DependencyRequirement(
        kind="NAMED_RANGE", name="PivotSourceKeyword", sheet_name=None,
        required=True,
    ),
    DependencyRequirement(
        kind="NAMED_RANGE", name="PivotSourceCompetitor", sheet_name=None,
        required=True,
    ),
    DependencyRequirement(
        kind="NAMED_RANGE", name="可选蓝色参数", sheet_name=None,
        required=True,
    ),
    DependencyRequirement(
        kind="AUTO_FILTER", name="竞品数据", sheet_name="竞品数据",
        required=True,
    ),
    DependencyRequirement(
        kind="AUTO_FILTER", name="关键词1—数据源", sheet_name="关键词1—数据源",
        required=True,
    ),
    DependencyRequirement(
        kind="AUTO_FILTER", name="原始数据源", sheet_name="原始数据源",
        required=True,
    ),
)


_EXTERNAL_VALUE = "EXTERNAL_REFERENCE_WORKBOOK_VALUE_REQUIRES_LOCAL_AUDIT"
THRESHOLD_RULES = (
    ThresholdRule(
        rule_id="target_gross_margin",
        source="requirements-v1.0",
        frozen_value="0.30",
        value_verified=True,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="default target margin is configurable; SP-041F implements it",
    ),
    ThresholdRule(
        rule_id="price_bands", source="不同维度分析",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="formula tokenizer inventory supplies exact local literals",
    ),
    ThresholdRule(
        rule_id="review_count_bands", source="不同维度分析",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="review thresholds are business configuration",
    ),
    ThresholdRule(
        rule_id="review_rate_bands", source="不同维度分析",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="provider review-rate thresholds are not universal truth",
    ),
    ThresholdRule(
        rule_id="fba_fee_bands", source="不同维度分析",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="fee bands must remain explicit and auditable",
    ),
    ThresholdRule(
        rule_id="listing_age_bands", source="不同维度分析",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="listing-age bands are configurable business rules",
    ),
    ThresholdRule(
        rule_id="new_product_window", source="自动化配置",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="new-product window cannot be inferred or hard-coded globally",
    ),
    ThresholdRule(
        rule_id="category_semantic_rules", source="自动化配置",
        frozen_value=_EXTERNAL_VALUE, value_verified=False,
        disposition=FormulaDisposition.MOVE_TO_CONFIG,
        rationale="category semantics belong in a later CategoryRulePack",
    ),
    ThresholdRule(
        rule_id="provider_gross_margin", source="原始数据源.毛利率",
        frozen_value="REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH",
        value_verified=True,
        disposition=FormulaDisposition.DEPRECATED,
        rationale="provider margin cannot determine procurement truth",
    ),
)


PRODUCT_SELECTION_SEMANTICS = (
    ProductSelectionSemantic(
        sheet_name="产品初步筛选范围",
        before_direction_locked="CANDIDATE_PRODUCT_ARCHETYPES",
        after_direction_locked="LOCKED_DIRECTION_CONTEXT",
        direct_competitor_label_allowed_before_lock=False,
    ),
    ProductSelectionSemantic(
        sheet_name="样品类型",
        before_direction_locked="HYPOTHESES_AND_SAMPLING_DIRECTIONS",
        after_direction_locked="LOCKED_DIRECTION_SAMPLE_SPECIFICATIONS",
        direct_competitor_label_allowed_before_lock=False,
    ),
    ProductSelectionSemantic(
        sheet_name="竞品收集",
        before_direction_locked="REPRESENTATIVE_ASINS_ONLY",
        after_direction_locked="DIRECT_COMPETITOR_SET_ALLOWED",
        direct_competitor_label_allowed_before_lock=False,
    ),
)


_SHEETS = tuple(
    SheetContract(name=name, ordinal=index, visibility=SheetVisibility.VISIBLE)
    for index, name in enumerate(VISIBLE_SHEET_NAMES, 1)
) + tuple(
    SheetContract(name=name, ordinal=index, visibility=SheetVisibility.HIDDEN)
    for index, name in enumerate(HIDDEN_SHEET_NAMES, len(VISIBLE_SHEET_NAMES) + 1)
)


TEMPLATE_CONTRACT_V1 = OperatorTemplateContractV1(
    ruleset_version=OPERATOR_TEMPLATE_RULESET_VERSION,
    sheets=_SHEETS,
    raw_headers=RAW_HEADER_CONTRACTS,
    formula_policies=FORMULA_POLICIES,
    formula_census_reference=FORMULA_CENSUS_REFERENCE,
    dependencies=DEPENDENCY_REQUIREMENTS,
    threshold_rules=THRESHOLD_RULES,
    product_selection_semantics=PRODUCT_SELECTION_SEMANTICS,
    raw_header_mapping_policy="BY_EXACT_HEADER_NAME_NOT_COLUMN_INDEX",
    numeric_missing_policy="MISSING_BLANK_NA_PARSE_FAILURE_NEVER_ZERO",
    provider_gross_margin_semantics="REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH",
    external_network_calls_allowed=False,
)

TEMPLATE_SCHEMA_FINGERPRINT = template_schema_fingerprint(TEMPLATE_CONTRACT_V1)


__all__ = (
    "DEPENDENCY_REQUIREMENTS",
    "FORMULA_CENSUS_REFERENCE",
    "FORMULA_POLICIES",
    "HIDDEN_SHEET_NAMES",
    "PRODUCT_SELECTION_SEMANTICS",
    "RAW_HEADER_CONTRACTS",
    "TEMPLATE_CONTRACT_V1",
    "TEMPLATE_SCHEMA_FINGERPRINT",
    "THRESHOLD_RULES",
    "VISIBLE_SHEET_NAMES",
)
