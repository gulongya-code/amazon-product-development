"""Fixed presentation schema for Operator Workbook V0.2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldSpec:
    chinese_name: str
    english_name: str
    data_type: str
    source: str
    default_hidden: bool = False
    width: float = 18.0
    operator_use: str = "运营查看与筛选"


@dataclass(frozen=True, slots=True)
class SheetSpec:
    key: str
    name: str
    purpose: str
    warning: str
    row_grain: str
    hidden: bool
    fields: tuple[FieldSpec, ...]


def _fields(
    source: str,
    values: tuple[tuple[str, str, str, bool, float], ...],
) -> tuple[FieldSpec, ...]:
    return tuple(
        FieldSpec(
            chinese_name=chinese,
            english_name=english,
            data_type=data_type,
            source=source,
            default_hidden=hidden,
            width=width,
        )
        for chinese, english, data_type, hidden, width in values
    )


SHEET_SPECS: tuple[SheetSpec, ...] = (
    SheetSpec(
        key="market_overview",
        name="01_市场概览",
        purpose="当前证据覆盖的市场范围、信号、风险与限制摘要",
        warning="仅展示现有证据范围；不构成市场规模、趋势或机会保证。",
        row_grain="MARKETPLACE_CATEGORY_EVIDENCE_INDICATOR",
        hidden=False,
        fields=_fields(
            "Opportunity Intelligence / Evidence Evaluation",
            (
                ("市场站点", "Marketplace", "TEXT", False, 14),
                ("类目候选", "Category Candidate", "TEXT_OR_STATE", False, 22),
                ("市场规模证据指标", "Market Size Evidence Metric", "TEXT", False, 28),
                ("指标值", "Metric Value", "NUMBER_OR_TEXT", False, 18),
                ("单位", "Unit", "TEXT", False, 18),
                ("已观察产品数", "Observed Product Count", "INTEGER", False, 16),
                ("数据来源", "Data Sources", "TEXT_LIST", False, 24),
                ("主要趋势", "Evidence-backed Trend", "TEXT_OR_STATE", False, 32),
                ("风险提示", "Risk Alerts", "TEXT_LIST", False, 36),
                ("证据质量", "Evidence Quality", "ENUM_LIST", False, 30),
                ("分析限制", "Analysis Limitations", "TEXT_LIST", False, 38),
                ("快照 ID", "Snapshot ID", "ID", True, 18),
            ),
        ),
    ),
    SheetSpec(
        key="product_database",
        name="02_产品数据库",
        purpose="核心产品筛选与证据状态查看",
        warning="候选值保持未裁决；估算不作为 observed fact。",
        row_grain="EXACT_PRODUCT_IDENTITY",
        hidden=False,
        fields=_fields(
            "Product Intelligence / Evidence Evaluation / Operator Output",
            (
                ("ASIN", "ASIN", "TEXT_ID", False, 16),
                ("市场站点", "Marketplace", "TEXT", False, 12),
                ("标题", "Display Title", "TEXT_OR_STATE", False, 42),
                ("标题状态", "Title State", "ENUM", False, 20),
                ("品牌", "Brand", "TEXT_OR_STATE", False, 18),
                ("类目", "Category", "TEXT_OR_STATE", False, 20),
                ("产品类型", "Product Type", "TEXT_OR_STATE", False, 20),
                ("价格", "Price", "DECIMAL_OR_STATE", False, 14),
                ("币种", "Price Currency", "TEXT", False, 12),
                ("价格状态", "Price State", "ENUM", False, 18),
                ("Rating", "Rating", "DECIMAL_OR_STATE", False, 12),
                ("Rating 状态", "Rating State", "ENUM", False, 18),
                ("Review 数量证据", "Review Evidence Count", "INTEGER_OR_STATE", False, 18),
                ("BSR", "BSR", "INTEGER_OR_STATE", False, 14),
                ("BSR 类目上下文", "BSR Context", "TEXT_OR_STATE", False, 24),
                ("销量证据", "Sales Evidence Value", "NUMBER_OR_STATE", False, 18),
                ("销量证据单位", "Sales Evidence Unit", "TEXT_OR_STATE", False, 18),
                ("销量证据类型", "Sales Evidence Type", "ENUM_OR_STATE", False, 20),
                ("Variation 角色", "Variation Role", "ENUM_OR_STATE", False, 18),
                ("Parent ASIN", "Parent ASIN", "TEXT_ID_OR_STATE", False, 16),
                ("Child 数量", "Child Count", "INTEGER", False, 14),
                ("属性摘要", "Attribute Summary", "TEXT_LIST", False, 34),
                ("卖家", "Seller", "TEXT_OR_STATE", False, 18),
                ("FBA", "FBA Status", "BOOLEAN_ENUM_OR_STATE", False, 14),
                ("数据来源", "Data Sources", "TEXT_LIST", False, 24),
                ("数据状态", "Data State", "ENUM", False, 20),
                ("冲突状态", "Conflict State", "ENUM", False, 20),
                ("时间/周期状态", "Time / Period Status", "ENUM", True, 22),
                ("Product Snapshot ID", "Product Snapshot ID", "ID", True, 18),
                ("Output Row ID", "Output Row ID", "ID", True, 18),
            ),
        ),
    ),
    SheetSpec(
        key="top_products",
        name="03_TOP产品分析",
        purpose="查看有显式来源与上下文的排名或市场表现证据",
        warning="来源排名证据不代表最佳产品或平台推荐。",
        row_grain="EXPLICIT_RANK_EVIDENCE_RECORD",
        hidden=False,
        fields=_fields(
            "Product Intelligence",
            (
                ("产品", "Product ASIN", "TEXT_ID", False, 16),
                ("标题", "Display Title", "TEXT_OR_STATE", False, 38),
                ("市场站点", "Marketplace", "TEXT", False, 12),
                ("来源排名", "Source Rank Value", "INTEGER_OR_STATE", False, 14),
                ("排名指标", "Rank Metric", "TEXT_OR_STATE", False, 20),
                ("排名上下文", "Rank Context", "TEXT_OR_STATE", False, 26),
                ("Channel", "Channel", "ENUM_OR_STATE", False, 14),
                ("排名来源", "Rank Provider", "TEXT_OR_STATE", False, 16),
                ("排名状态", "Rank Status", "ENUM", False, 18),
                ("排名周期", "Rank Period", "TEXT_OR_STATE", False, 22),
                ("价格", "Price", "DECIMAL_OR_STATE", False, 14),
                ("Review", "Review Evidence Count", "INTEGER_OR_STATE", False, 16),
                ("Rating", "Rating Evidence", "DECIMAL_OR_STATE", False, 14),
                ("产品特点", "Product Features", "TEXT_LIST", False, 34),
                ("数据限制", "Data Limitations", "TEXT_LIST", False, 34),
                ("Rank Observation ID", "Rank Observation ID", "ID", True, 18),
            ),
        ),
    ),
    SheetSpec(
        key="keyword_demand",
        name="04_关键词需求分析",
        purpose="关键词指标、方向查询、渠道和关联产品证据",
        warning="方向性查询与 Provider 指标不构成需求保证。",
        row_grain="KEYWORD_PROVIDER_DIRECTION_CHANNEL",
        hidden=False,
        fields=_fields(
            "Demand Intelligence / Evidence Evaluation",
            (
                ("Keyword", "Keyword", "TEXT", False, 24),
                ("市场站点", "Marketplace", "TEXT", False, 12),
                ("Locale", "Locale", "TEXT", True, 12),
                ("Search Volume", "Search Volume", "NUMBER_OR_STATE", False, 16),
                ("Search Volume 状态", "Search Volume State", "ENUM", False, 20),
                ("Search Volume 单位", "Search Volume Unit", "TEXT_OR_STATE", True, 20),
                ("CPC", "CPC", "DECIMAL_OR_STATE", False, 12),
                ("CPC 币种", "CPC Currency", "TEXT_OR_STATE", False, 12),
                ("CPC 状态", "CPC State", "ENUM", False, 18),
                ("ABA Rank", "ABA Rank", "INTEGER_OR_STATE", False, 14),
                ("ABA Rank 状态", "ABA Rank State", "ENUM", False, 18),
                ("Difficulty", "Difficulty", "NUMBER_OR_STATE", False, 14),
                ("Difficulty 状态", "Difficulty State", "ENUM", False, 18),
                ("关联产品数", "Related Product Count", "INTEGER", False, 16),
                ("关联产品", "Related Product ASINs", "TEXT_ID_LIST", False, 28),
                ("Channel", "Channel", "ENUM_LIST", False, 18),
                ("Query Direction", "Query Direction", "ENUM", False, 22),
                ("Query 状态", "Query Status", "ENUM", False, 18),
                ("Provider", "Provider", "TEXT", False, 16),
                ("估算方法状态", "Estimate Method Status", "ENUM_OR_STATE", False, 20),
                ("周期状态", "Period Status", "ENUM", True, 18),
                ("限制", "Limitations", "TEXT_LIST", False, 36),
                ("Demand Snapshot ID", "Demand Snapshot ID", "ID", True, 18),
            ),
        ),
    ),
    SheetSpec(
        key="competition_evidence",
        name="05_市场竞争证据",
        purpose="产品与关键词的观察关系、渠道和来源证据",
        warning="关系证据不是竞争强度、市场份额或竞品排名。",
        row_grain="PRODUCT_KEYWORD_RELATIONSHIP_EVIDENCE_GROUP",
        hidden=False,
        fields=_fields(
            "Competition Intelligence / Operator Output",
            (
                ("产品", "Product ASIN", "TEXT_ID", False, 16),
                ("Keyword", "Keyword", "TEXT_OR_STATE", False, 24),
                ("Relationship Direction", "Relationship Direction", "ENUM", False, 22),
                ("Relationship", "Observed Relationship", "TEXT", False, 32),
                ("Relationship Type", "Observed Relationship Type", "ENUM", False, 22),
                ("Channel", "Channel", "ENUM", False, 14),
                ("Provider", "Provider", "TEXT", False, 16),
                ("Evidence 数量", "Evidence Count", "INTEGER", False, 16),
                ("Evidence Classification", "Evidence Classification", "ENUM", False, 22),
                ("Variation Evidence 数量", "Variation Evidence Count", "INTEGER", False, 20),
                ("Query 状态", "Query Status", "ENUM_OR_STATE", False, 18),
                ("限制", "Limitations", "TEXT_LIST", False, 36),
                ("Competition Output Row ID", "Competition Output Row ID", "ID", True, 18),
            ),
        ),
    ),
    SheetSpec(
        key="product_structure",
        name="06_产品结构分析",
        purpose="依据 exact 产品事实观察类型、价格与属性结构",
        warning="当前证据分组不是聚类、市场份额或产品偏好。",
        row_grain="EXACT_OBSERVED_PRODUCT_TYPE_GROUP",
        hidden=False,
        fields=_fields(
            "Product Intelligence / Evidence Evaluation",
            (
                ("市场站点", "Marketplace", "TEXT", False, 12),
                ("产品类型", "Product Type", "TEXT_OR_STATE", False, 22),
                ("产品数量", "Product Count", "INTEGER", False, 14),
                ("产品占比", "Observed Share", "PERCENTAGE_OR_STATE", False, 14),
                ("销量证据摘要", "Sales Evidence Summary", "TEXT", False, 30),
                ("最低价格", "Minimum Comparable Price", "DECIMAL_OR_STATE", False, 16),
                ("最高价格", "Maximum Comparable Price", "DECIMAL_OR_STATE", False, 16),
                ("币种", "Currency", "TEXT_OR_STATE", False, 12),
                ("主要特点", "Observed Feature Inventory", "TEXT_LIST", False, 34),
                ("数据状态", "Data State", "ENUM", False, 18),
                ("Provider 数量", "Provider Count", "INTEGER", False, 16),
                ("限制", "Limitations", "TEXT_LIST", False, 36),
                ("Member Product IDs", "Member Product IDs", "ID_LIST", True, 22),
            ),
        ),
    ),
    SheetSpec(
        key="opportunity_analysis",
        name="07_机会分析",
        purpose="并列展示信号、缺失、风险和既有 score reference",
        warning="信号与规则过程分值不构成机会保证或成功概率。",
        row_grain="OPPORTUNITY_OUTPUT_GROUP_SCORE_CALCULATION",
        hidden=False,
        fields=_fields(
            "Opportunity Intelligence / Opportunity Scoring / Operator Output",
            (
                ("产品", "Product", "TEXT_ID_OR_STATE", False, 20),
                ("Demand Signal", "Demand Signal", "TEXT_LIST", False, 32),
                ("Competition Signal", "Competition Signal", "TEXT_LIST", False, 32),
                ("Product Signal", "Product Signal", "TEXT_LIST", False, 32),
                ("Signal Classification", "Signal Classification", "ENUM_LIST", False, 22),
                ("Missing Evidence", "Missing Evidence", "TEXT_LIST", False, 30),
                ("Risk", "Risk Evidence", "TEXT_LIST", False, 34),
                ("Score Factor", "Score Factor", "TEXT", False, 22),
                ("规则过程分值", "Rule Process Score", "INTEGER_OR_STATE", False, 16),
                ("Score Status", "Score Status", "ENUM", False, 18),
                ("Score Reference", "Score Reference", "ID", False, 20),
                ("Score Interpretation", "Score Interpretation", "TEXT", False, 30),
                ("Explanation Reference", "Explanation Reference", "ID", True, 20),
                ("限制", "Limitations", "TEXT_LIST", False, 36),
                ("Opportunity Output Row ID", "Opportunity Output Row ID", "ID", True, 18),
            ),
        ),
    ),
    SheetSpec(
        key="action_recommendations",
        name="08_行动建议",
        purpose="复核 Recommendation Framework 输出并记录独立人工状态",
        warning="规则生成的复核记录不是购买建议或自动选品结论。",
        row_grain="RECOMMENDATION_GENERATION_RECORD",
        hidden=False,
        fields=_fields(
            "Recommendation Framework / Operator Output / Workbook UI",
            (
                ("产品", "Product", "TEXT_ID_OR_STATE", False, 20),
                ("Recommendation Type", "Recommendation Type", "ENUM", False, 26),
                ("建议显示标签", "Recommendation Display Label", "TEXT", False, 18),
                ("Reason", "Reason", "TEXT", False, 36),
                ("Rule Reference", "Rule Reference", "ID", False, 20),
                ("Policy Status", "Policy Status", "ENUM", False, 18),
                ("Conflict Status", "Conflict Status", "ENUM", False, 18),
                ("Missing Requirements", "Missing Requirements", "TEXT_LIST", False, 28),
                ("Evidence", "Evidence References", "ID_LIST", False, 30),
                ("Evidence 数量", "Evidence Count", "INTEGER", False, 16),
                ("Limitation", "Limitations", "TEXT_LIST", False, 36),
                ("人工状态", "Manual Review Status", "ENUM_EDITABLE", False, 18),
                ("Recommendation Record ID", "Recommendation Record ID", "ID", True, 20),
                ("Source Snapshot ID", "Source Snapshot ID", "ID", True, 20),
                ("Operator Output Row ID", "Operator Output Row ID", "ID", True, 20),
            ),
        ),
    ),
    SheetSpec(
        key="data_audit",
        name="09_数据审计",
        purpose="展示字段到 Canonical lineage 的端到端追溯",
        warning="只包含安全引用，不包含 raw provider payload 或秘密字段。",
        row_grain="DISPLAY_FIELD_LINEAGE_REFERENCE",
        hidden=True,
        fields=_fields(
            "XLSX / Operator Export / Operator Output / Canonical Lineage",
            (
                ("审计记录 ID", "Audit Record ID", "ID", True, 18),
                ("来源 Sheet", "Source Sheet", "TEXT", True, 20),
                ("展示行键", "Display Row Key", "ID", True, 18),
                ("Excel 行号", "Excel Row", "INTEGER", True, 14),
                ("展示字段", "Display Field", "TEXT", True, 24),
                ("Excel Cell", "Excel Cell", "TEXT", True, 14),
                ("Operator Export Row ID", "Export Row ID", "ID_OR_STATE", True, 20),
                ("Operator Output Row ID", "Output Row ID", "ID", True, 20),
                ("Evidence ID", "Evidence ID", "ID", True, 20),
                ("Provider", "Provider", "TEXT", True, 16),
                ("Source Tool", "Source Tool", "TEXT", True, 20),
                ("Source Field", "Source Field", "TEXT", True, 28),
                ("Raw Reference", "Raw Evidence Reference", "ID", True, 20),
                ("Collection Run", "Collection Run ID", "ID", True, 20),
                ("Transformation", "Transformation Run ID", "ID", True, 20),
                ("Mapping Version", "Mapping Version", "TEXT", True, 24),
                ("Canonical Reference", "Canonical Reference ID", "ID", True, 20),
                ("Lineage", "Lineage ID", "ID", True, 20),
                ("Source Snapshot", "Source Snapshot ID", "ID", True, 20),
                ("Bundle Fingerprint", "Source Bundle Fingerprint", "SHA256_LIST", True, 24),
            ),
        ),
    ),
)


EXPECTED_SHEET_NAMES = tuple(item.name for item in SHEET_SPECS)
EXPECTED_FIELD_COUNT = sum(len(item.fields) for item in SHEET_SPECS)

if EXPECTED_FIELD_COUNT != 157:  # pragma: no cover - import-time contract guard
    raise RuntimeError(f"Operator Workbook V0.2 field schema must contain 157 fields, got {EXPECTED_FIELD_COUNT}")


__all__ = (
    "EXPECTED_FIELD_COUNT",
    "EXPECTED_SHEET_NAMES",
    "FieldSpec",
    "SHEET_SPECS",
    "SheetSpec",
)
