"""Strict, data-only category rule packs for SP-041C."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json

from .errors import CategoryRulePackError


RULE_PACK_SCHEMA_VERSION = "category-rule-pack-v1.0"
DIMENSIONS = (
    "product_form", "mounting_or_usage_mode", "material_family",
    "size_or_capacity", "pack_count", "use_case", "compatibility",
    "operation_mode", "power_mode", "special_features", "color",
    "dimensions", "weight",
)


class SourceKind(StrEnum):
    STRUCTURED_PARAMETERS = "STRUCTURED_PARAMETERS"
    DEDICATED_FIELD = "DEDICATED_FIELD"
    SKU = "SKU"
    TITLE = "TITLE"


class MatchMode(StrEnum):
    EXACT = "EXACT"
    PHRASE = "PHRASE"
    TOKEN_SET = "TOKEN_SET"


class QuantityKind(StrEnum):
    COUNT = "COUNT"
    LENGTH = "LENGTH"
    MASS = "MASS"
    VOLUME = "VOLUME"
    DIMENSIONS = "DIMENSIONS"


class MeasurementScope(StrEnum):
    ITEM = "ITEM"
    PACKAGE = "PACKAGE"
    UNSPECIFIED = "UNSPECIFIED"


@dataclass(frozen=True, slots=True)
class ValueRule:
    rule_id: str
    dimension: str
    result: str
    sources: tuple[SourceKind, ...]
    keys_or_fields: tuple[str, ...]
    match_mode: MatchMode
    match_values: tuple[str, ...]
    exclusions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PassthroughRule:
    rule_id: str
    dimension: str
    sources: tuple[SourceKind, ...]
    keys_or_fields: tuple[str, ...]
    list_delimiter: str | None


@dataclass(frozen=True, slots=True)
class MeasurementRule:
    rule_id: str
    dimension: str
    quantity_kind: QuantityKind
    sources: tuple[SourceKind, ...]
    keys_or_fields: tuple[str, ...]
    scope: MeasurementScope
    allow_bare_count: bool


@dataclass(frozen=True, slots=True)
class NegativeRule:
    rule_id: str
    dimension: str
    sources: tuple[SourceKind, ...]
    when_any: tuple[str, ...]
    unless_any: tuple[str, ...]
    blocked_values: tuple[str, ...]
    note: str


@dataclass(frozen=True, slots=True)
class CategoryRulePack:
    rule_pack_id: str
    version: str
    category: str
    category_aliases: tuple[str, ...]
    value_rules: tuple[ValueRule, ...]
    passthrough_rules: tuple[PassthroughRule, ...]
    measurement_rules: tuple[MeasurementRule, ...]
    negative_rules: tuple[NegativeRule, ...]
    fingerprint: str

    @property
    def identity(self) -> str:
        return f"{self.rule_pack_id}@{self.version}"


_TOP_KEYS = {
    "schema_version", "rule_pack_id", "version", "category",
    "category_aliases", "value_rules", "passthrough_rules",
    "measurement_rules", "negative_rules",
}
_VALUE_KEYS = {
    "rule_id", "dimension", "result", "sources", "keys_or_fields",
    "match_mode", "match_values", "exclusions",
}
_PASS_KEYS = {
    "rule_id", "dimension", "sources", "keys_or_fields", "list_delimiter",
}
_MEASURE_KEYS = {
    "rule_id", "dimension", "quantity_kind", "sources", "keys_or_fields",
    "scope", "allow_bare_count",
}
_NEG_KEYS = {
    "rule_id", "dimension", "sources", "when_any", "unless_any",
    "blocked_values", "note",
}


def _object(value: Any, path: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} must be an object"
        )
    unknown = sorted(set(value) - keys)
    missing = sorted(keys - set(value))
    if unknown or missing:
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID",
            f"{path} unknown={unknown} missing={missing}",
        )
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} must be non-empty text"
        )
    return " ".join(value.split())


def _texts(
    value: Any, path: str, *, nonempty: bool = True
) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} must be a JSON list"
        )
    result = tuple(_text(item, f"{path}[]").casefold() for item in value)
    if len(result) != len(set(result)):
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} contains duplicates"
        )
    return result


def _sources(value: Any, path: str) -> tuple[SourceKind, ...]:
    try:
        return tuple(SourceKind(item.upper()) for item in _texts(value, path))
    except ValueError as exc:
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} contains an invalid source"
        ) from exc


def _dimension(value: Any, path: str) -> str:
    result = _text(value, path)
    if result not in DIMENSIONS:
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} is not supported"
        )
    return result


def _enum(enum_type: type[StrEnum], value: Any, path: str) -> Any:
    try:
        return enum_type(_text(value, path).upper())
    except ValueError as exc:
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", f"{path} is invalid"
        ) from exc


def load_category_rule_pack(path: str | Path) -> CategoryRulePack:
    candidate = Path(path)
    try:
        raw = candidate.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CategoryRulePackError(
            "RULE_PACK_READ_FAILED", "rule pack must be readable UTF-8 JSON"
        ) from exc

    top = _object(payload, "rule_pack", _TOP_KEYS)
    if top["schema_version"] != RULE_PACK_SCHEMA_VERSION:
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", "schema_version is unsupported"
        )

    value_rules: list[ValueRule] = []
    for index, raw_rule in enumerate(top["value_rules"]):
        item = _object(raw_rule, f"value_rules[{index}]", _VALUE_KEYS)
        value_rules.append(ValueRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            dimension=_dimension(item["dimension"], "dimension"),
            result=_text(item["result"], "result").casefold(),
            sources=_sources(item["sources"], "sources"),
            keys_or_fields=_texts(item["keys_or_fields"], "keys_or_fields"),
            match_mode=_enum(MatchMode, item["match_mode"], "match_mode"),
            match_values=_texts(item["match_values"], "match_values"),
            exclusions=_texts(
                item["exclusions"], "exclusions", nonempty=False
            ),
        ))

    passthrough_rules: list[PassthroughRule] = []
    for index, raw_rule in enumerate(top["passthrough_rules"]):
        item = _object(raw_rule, f"passthrough_rules[{index}]", _PASS_KEYS)
        delimiter = item["list_delimiter"]
        if delimiter is not None:
            delimiter = _text(delimiter, "list_delimiter")
        passthrough_rules.append(PassthroughRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            dimension=_dimension(item["dimension"], "dimension"),
            sources=_sources(item["sources"], "sources"),
            keys_or_fields=_texts(item["keys_or_fields"], "keys_or_fields"),
            list_delimiter=delimiter,
        ))

    measurement_rules: list[MeasurementRule] = []
    for index, raw_rule in enumerate(top["measurement_rules"]):
        item = _object(
            raw_rule, f"measurement_rules[{index}]", _MEASURE_KEYS
        )
        if type(item["allow_bare_count"]) is not bool:
            raise CategoryRulePackError(
                "RULE_PACK_SCHEMA_INVALID",
                "allow_bare_count must be boolean",
            )
        measurement_rules.append(MeasurementRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            dimension=_dimension(item["dimension"], "dimension"),
            quantity_kind=_enum(
                QuantityKind, item["quantity_kind"], "quantity_kind"
            ),
            sources=_sources(item["sources"], "sources"),
            keys_or_fields=_texts(item["keys_or_fields"], "keys_or_fields"),
            scope=_enum(MeasurementScope, item["scope"], "scope"),
            allow_bare_count=item["allow_bare_count"],
        ))

    negative_rules: list[NegativeRule] = []
    for index, raw_rule in enumerate(top["negative_rules"]):
        item = _object(raw_rule, f"negative_rules[{index}]", _NEG_KEYS)
        negative_rules.append(NegativeRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            dimension=_dimension(item["dimension"], "dimension"),
            sources=_sources(item["sources"], "sources"),
            when_any=_texts(item["when_any"], "when_any"),
            unless_any=_texts(
                item["unless_any"], "unless_any", nonempty=False
            ),
            blocked_values=_texts(item["blocked_values"], "blocked_values"),
            note=_text(item["note"], "note"),
        ))

    all_rules = [
        *value_rules, *passthrough_rules, *measurement_rules, *negative_rules
    ]
    rule_ids = [item.rule_id for item in all_rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise CategoryRulePackError(
            "RULE_PACK_SCHEMA_INVALID", "rule_id values must be unique"
        )

    fingerprint = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return CategoryRulePack(
        rule_pack_id=_text(top["rule_pack_id"], "rule_pack_id"),
        version=_text(top["version"], "version"),
        category=_text(top["category"], "category").casefold(),
        category_aliases=_texts(
            top["category_aliases"], "category_aliases", nonempty=False
        ),
        value_rules=tuple(value_rules),
        passthrough_rules=tuple(passthrough_rules),
        measurement_rules=tuple(measurement_rules),
        negative_rules=tuple(negative_rules),
        fingerprint=fingerprint,
    )


__all__ = (
    "CategoryRulePack", "DIMENSIONS", "MatchMode", "MeasurementRule",
    "MeasurementScope", "NegativeRule", "PassthroughRule", "QuantityKind",
    "RULE_PACK_SCHEMA_VERSION", "SourceKind", "ValueRule",
    "load_category_rule_pack",
)
