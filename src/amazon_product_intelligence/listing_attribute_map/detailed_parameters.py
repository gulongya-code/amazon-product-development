"""Deterministic parser for governed ``Key: Value | Key: Value`` evidence."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.normalization.rules import normalize_text

from .errors import DetailedParameterParseError


DETAILED_PARAMETER_PARSER_VERSION = "detailed-parameter-parser-v1.0"


def _clean(value: str) -> str:
    outcome = normalize_text(value, None)
    return "" if outcome.normalized_value is None else str(outcome.normalized_value)


def normalize_parameter_key(value: str) -> str:
    """Normalize presentation-only key differences; never infer an alias."""

    return _clean(value).casefold()


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredParameter:
    parameter_id: str
    source_key: str
    source_value: str
    normalized_key: str
    normalized_value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "parameter_id": self.parameter_id,
            "source_key": self.source_key,
            "source_value": self.source_value,
            "normalized_key": self.normalized_key,
            "normalized_value": self.normalized_value,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ParameterConflict:
    conflict_id: str
    normalized_key: str
    parameter_ids: tuple[str, ...]
    normalized_values: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "normalized_key": self.normalized_key,
            "parameter_ids": list(self.parameter_ids),
            "normalized_values": list(self.normalized_values),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ParameterParseIssue:
    segment_index: int
    code: str

    def to_dict(self) -> dict[str, object]:
        return {"segment_index": self.segment_index, "code": self.code}


@dataclass(frozen=True, slots=True, kw_only=True)
class DetailedParameterParseResult:
    parser_version: str
    source_text: str
    parameters: tuple[StructuredParameter, ...]
    conflicts: tuple[ParameterConflict, ...]
    issues: tuple[ParameterParseIssue, ...]
    duplicate_pair_count: int
    semantic_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "parser_version": self.parser_version,
            "source_text": self.source_text,
            "parameters": [item.to_dict() for item in self.parameters],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "issues": [item.to_dict() for item in self.issues],
            "duplicate_pair_count": self.duplicate_pair_count,
            "semantic_fingerprint": self.semantic_fingerprint,
        }

    @property
    def conflicted_keys(self) -> frozenset[str]:
        return frozenset(item.normalized_key for item in self.conflicts)


def parse_detailed_parameters(value: str) -> DetailedParameterParseResult:
    if not isinstance(value, str):
        raise DetailedParameterParseError(
            "DETAIL_PARAMETERS_TYPE_INVALID",
            "detailed parameters must be text",
        )
    source_text = _clean(value)
    unique: dict[tuple[str, str], StructuredParameter] = {}
    issues: list[ParameterParseIssue] = []
    duplicate_count = 0
    for index, segment in enumerate(source_text.split("|"), 1):
        candidate = segment.strip()
        if not candidate:
            issues.append(ParameterParseIssue(segment_index=index, code="EMPTY_SEGMENT"))
            continue
        if ":" not in candidate:
            issues.append(ParameterParseIssue(segment_index=index, code="MISSING_KEY_VALUE_DELIMITER"))
            continue
        raw_key, raw_value = candidate.split(":", 1)
        source_key = _clean(raw_key)
        source_value = _clean(raw_value)
        if not source_key:
            issues.append(ParameterParseIssue(segment_index=index, code="EMPTY_KEY"))
            continue
        if not source_value:
            issues.append(ParameterParseIssue(segment_index=index, code="EMPTY_VALUE"))
            continue
        normalized_key = source_key.casefold()
        normalized_value = source_value.casefold()
        identity = {"normalized_key": normalized_key, "normalized_value": normalized_value}
        pair = StructuredParameter(
            parameter_id=deterministic_id("structured-parameter", identity),
            source_key=source_key,
            source_value=source_value,
            normalized_key=normalized_key,
            normalized_value=normalized_value,
        )
        key = (normalized_key, normalized_value)
        if key in unique:
            duplicate_count += 1
        else:
            unique[key] = pair

    parameters = tuple(sorted(unique.values(), key=lambda item: (item.normalized_key, item.normalized_value)))
    by_key: dict[str, list[StructuredParameter]] = {}
    for item in parameters:
        by_key.setdefault(item.normalized_key, []).append(item)
    conflicts: list[ParameterConflict] = []
    for key in sorted(by_key):
        members = by_key[key]
        values = tuple(sorted({item.normalized_value for item in members}))
        if len(values) < 2:
            continue
        payload = {
            "normalized_key": key,
            "parameter_ids": tuple(sorted(item.parameter_id for item in members)),
            "normalized_values": values,
        }
        conflicts.append(
            ParameterConflict(
                conflict_id=deterministic_id("structured-parameter-conflict", payload),
                **payload,
            )
        )
    issues_tuple = tuple(sorted(issues, key=lambda item: (item.segment_index, item.code)))
    # Presentation casing, spacing, segment order, and source snippets are
    # deliberately excluded from semantic identity. They remain available in
    # ``to_dict`` for audit evidence.
    semantic_material = {
        "parser_version": DETAILED_PARAMETER_PARSER_VERSION,
        "parameters": [
            {
                "parameter_id": item.parameter_id,
                "normalized_key": item.normalized_key,
                "normalized_value": item.normalized_value,
            }
            for item in parameters
        ],
        "conflicts": [item.to_dict() for item in conflicts],
        "issue_codes": sorted(item.code for item in issues_tuple),
        "duplicate_pair_count": duplicate_count,
    }
    import hashlib

    fingerprint = hashlib.sha256(canonical_json(semantic_material).encode("utf-8")).hexdigest()
    return DetailedParameterParseResult(
        parser_version=DETAILED_PARAMETER_PARSER_VERSION,
        source_text=source_text,
        parameters=parameters,
        conflicts=tuple(conflicts),
        issues=issues_tuple,
        duplicate_pair_count=duplicate_count,
        semantic_fingerprint=fingerprint,
    )


__all__ = (
    "DETAILED_PARAMETER_PARSER_VERSION",
    "DetailedParameterParseResult",
    "ParameterConflict",
    "ParameterParseIssue",
    "StructuredParameter",
    "normalize_parameter_key",
    "parse_detailed_parameters",
)
