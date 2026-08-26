"""Typed interpretation of the frozen SP-041A 66-header contract."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.operator_template_contract.schema_v1 import (
    RAW_HEADER_CONTRACTS,
)

from .models import EvidenceSemantics


MIN_HEADER_MATCH_COUNT = 5
MAX_HEADER_SCAN_ROWS = 20
MAX_LISTING_ROWS = 1500
PREFERRED_RAW_SHEET = "原始数据源"
HEADER_ALIASES_V1: dict[str, str] = {}


@dataclass(frozen=True, slots=True)
class FieldSpec:
    header: str
    requirement: str
    value_type: str
    evidence_semantics: EvidenceSemantics


_ASIN = {"ASIN", "父ASIN"}
_URL = {"品牌链接", "商品详情页链接", "商品主图", "卖家首页"}
_RANK = {"大类BSR", "小类BSR"}
_NONNEGATIVE_INTEGER = {
    "月销量",
    "子体销量",
    "变体数",
    "Q&A",
    "评分数",
    "月新增评分数",
    "上架天数",
    "卖家数",
}
_SIGNED_INTEGER = {"大类BSR增长数"}
_MONEY = {"月销售额($)", "子体销售额($)", "价格($)", "prime价格($)", "FBA($)", "买家运费($)"}
_PERCENTAGE = {"大类BSR增长率", "销量环比增长率", "销量同比增长率", "留评率", "毛利率"}
_RATING = {"评分"}
_DATE = {"上架时间"}
_BOOLEAN = {
    "Best Seller标识",
    "Amazon's Choice",
    "New Release标识",
    "A+页面",
    "视频介绍",
    "品牌故事",
    "品牌广告",
    "秒杀",
}


def _value_type(header: str) -> str:
    for name, members in (
        ("ASIN", _ASIN),
        ("URL", _URL),
        ("RANK", _RANK),
        ("NONNEGATIVE_INTEGER", _NONNEGATIVE_INTEGER),
        ("SIGNED_INTEGER", _SIGNED_INTEGER),
        ("MONEY_USD", _MONEY),
        ("PERCENTAGE", _PERCENTAGE),
        ("RATING", _RATING),
        ("DATE", _DATE),
        ("BOOLEAN", _BOOLEAN),
    ):
        if header in members:
            return name
    return "TEXT"


def _evidence_semantics(note: str) -> EvidenceSemantics:
    if "REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH" in note:
        return EvidenceSemantics.REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH
    if "third-party" in note.casefold() or "THIRD_PARTY_ESTIMATE" in note:
        return EvidenceSemantics.THIRD_PARTY_ESTIMATE
    return EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE


FIELD_SPECS = tuple(
    FieldSpec(
        header=contract.header if hasattr(contract, "header") else contract.name,
        requirement=contract.requirement.value,
        value_type=_value_type(contract.name),
        evidence_semantics=_evidence_semantics(contract.semantic_note),
    )
    for contract in RAW_HEADER_CONTRACTS
)
FIELD_SPEC_BY_HEADER = {spec.header: spec for spec in FIELD_SPECS}
CONTRACT_HEADERS = frozenset(FIELD_SPEC_BY_HEADER)
CORE_HEADERS = tuple(spec.header for spec in FIELD_SPECS if spec.requirement == "CORE")
OUT_OF_SCOPE_HEADERS = frozenset(
    spec.header for spec in FIELD_SPECS if spec.requirement == "OUT_OF_SCOPE"
)


def normalize_header(value: object) -> str | None:
    """Apply presentation trimming and an explicit versioned alias map only."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    return HEADER_ALIASES_V1.get(candidate, candidate)


def header_match_count(values: tuple[object, ...]) -> int:
    mapped = {normalize_header(value) for value in values}
    return len(CONTRACT_HEADERS.intersection(item for item in mapped if item is not None))


def is_header_candidate(values: tuple[object, ...]) -> bool:
    mapped = tuple(normalize_header(value) for value in values)
    return "ASIN" in mapped and header_match_count(values) >= MIN_HEADER_MATCH_COUNT


__all__ = (
    "CONTRACT_HEADERS",
    "CORE_HEADERS",
    "FIELD_SPECS",
    "FIELD_SPEC_BY_HEADER",
    "HEADER_ALIASES_V1",
    "MAX_HEADER_SCAN_ROWS",
    "MAX_LISTING_ROWS",
    "MIN_HEADER_MATCH_COUNT",
    "OUT_OF_SCOPE_HEADERS",
    "PREFERRED_RAW_SHEET",
    "FieldSpec",
    "header_match_count",
    "is_header_candidate",
    "normalize_header",
)
