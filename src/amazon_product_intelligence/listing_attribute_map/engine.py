"""Deterministic cross-category listing attribute mapping engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.product_attribute_extraction.models import (
    AttributeConfidenceLevel,
)
from amazon_product_intelligence.sellersprite_import.models import (
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
)

from .detailed_parameters import (
    DETAILED_PARAMETER_PARSER_VERSION,
    DetailedParameterParseResult,
    parse_detailed_parameters,
)
from .errors import ListingAttributeMapError
from .measurements import (
    MEASUREMENT_PARSER_VERSION,
    parse_measurement,
)
from .models import (
    AttributeConflict,
    AttributeSlot,
    AttributeSlotStatus,
    AttributeValue,
    AttributeValueStatus,
    EvidenceReference,
    LISTING_ATTRIBUTE_ENGINE_VERSION,
    ProductAttributeMapV1,
    ProductAttributeRecord,
)
from .rule_pack import (
    DIMENSIONS,
    CategoryRulePack,
    MatchMode,
    SourceKind,
)


_SOURCE_PRIORITY = {
    SourceKind.STRUCTURED_PARAMETERS: 1,
    SourceKind.DEDICATED_FIELD: 2,
    SourceKind.SKU: 3,
    SourceKind.TITLE: 4,
}
_SOURCE_CONFIDENCE = {
    SourceKind.STRUCTURED_PARAMETERS: AttributeConfidenceLevel.HIGH,
    SourceKind.DEDICATED_FIELD: AttributeConfidenceLevel.HIGH,
    SourceKind.SKU: AttributeConfidenceLevel.MEDIUM,
    SourceKind.TITLE: AttributeConfidenceLevel.LOW,
}
_MULTI_DIMENSIONS = frozenset({
    "use_case", "compatibility", "special_features", "dimensions",
    "weight",
})


@dataclass(frozen=True, slots=True)
class _Datum:
    kind: SourceKind
    field: str
    key: str | None
    text: str
    normalized_text: str
    record_fingerprint: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    dimension: str
    value: Any
    value_key: str
    status: AttributeValueStatus
    datum: _Datum
    rule_id: str
    evidence: EvidenceReference


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalized(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def _snippet(value: str) -> str:
    normalized = _normalized(value)
    return normalized[:160]


def _evidence(
    datum: _Datum, *, rule_id: str, rule_pack: CategoryRulePack
) -> EvidenceReference:
    material = {
        "kind": datum.kind.value,
        "field": datum.field,
        "key": datum.key,
        "snippet": _snippet(datum.text),
        "upstream_record_fingerprint": datum.record_fingerprint,
        "rule_id": rule_id,
        "rule_pack_version": rule_pack.version,
    }
    return EvidenceReference(
        evidence_id=deterministic_id("attribute-evidence", material),
        source_kind=datum.kind,
        source_priority=_SOURCE_PRIORITY[datum.kind],
        source_field=datum.field,
        source_key=datum.key,
        source_snippet=_snippet(datum.text),
        upstream_record_fingerprint=datum.record_fingerprint,
        confidence=_SOURCE_CONFIDENCE[datum.kind],
        rule_id=rule_id,
        rule_pack_version=rule_pack.version,
    )


def _field_data(record: ListingRecordV1) -> dict[str, _Datum]:
    result: dict[str, _Datum] = {}
    for field in record.fields:
        if (
            field.import_status is not ImportValueStatus.NORMALIZED
            or field.value is None
        ):
            continue
        text = " ".join(str(field.value).split())
        result[field.header.casefold()] = _Datum(
            kind=SourceKind.DEDICATED_FIELD,
            field=field.header,
            key=None,
            text=text,
            normalized_text=text.casefold(),
            record_fingerprint=record.record_fingerprint,
        )
    return result


def _structured_data(
    record: ListingRecordV1, fields: dict[str, _Datum]
) -> tuple[DetailedParameterParseResult | None, tuple[_Datum, ...]]:
    source = fields.get("\u8be6\u7ec6\u53c2\u6570".casefold())
    if source is None:
        return None, ()
    parsed = parse_detailed_parameters(source.text)
    data = tuple(
        _Datum(
            kind=SourceKind.STRUCTURED_PARAMETERS,
            field="\u8be6\u7ec6\u53c2\u6570",
            key=item.normalized_key,
            text=item.source_value,
            normalized_text=item.normalized_value,
            record_fingerprint=record.record_fingerprint,
        )
        for item in parsed.parameters
    )
    return parsed, data


def _source_data(
    record: ListingRecordV1,
) -> tuple[DetailedParameterParseResult | None, tuple[_Datum, ...]]:
    fields = _field_data(record)
    parsed, structured = _structured_data(record, fields)
    data = list(structured)
    for header, datum in fields.items():
        if header == "\u8be6\u7ec6\u53c2\u6570".casefold():
            continue
        if header == "sku":
            kind = SourceKind.SKU
        elif header == "\u5546\u54c1\u6807\u9898".casefold():
            kind = SourceKind.TITLE
        else:
            kind = SourceKind.DEDICATED_FIELD
        data.append(_Datum(
            kind=kind,
            field=datum.field,
            key=None,
            text=datum.text,
            normalized_text=datum.normalized_text,
            record_fingerprint=datum.record_fingerprint,
        ))
    return parsed, tuple(sorted(
        data,
        key=lambda item: (
            _SOURCE_PRIORITY[item.kind], item.field.casefold(),
            item.key or "", item.normalized_text,
        ),
    ))


def _selected(
    data: Iterable[_Datum],
    *,
    sources: tuple[SourceKind, ...],
    keys_or_fields: tuple[str, ...],
) -> tuple[_Datum, ...]:
    allowed_sources = frozenset(sources)
    allowed = frozenset(keys_or_fields)
    return tuple(
        item for item in data
        if item.kind in allowed_sources
        and (
            (item.key is not None and item.key.casefold() in allowed)
            or (item.key is None and item.field.casefold() in allowed)
        )
    )


def _matches(text: str, mode: MatchMode, patterns: tuple[str, ...]) -> bool:
    normalized = _normalized(text)
    if mode is MatchMode.EXACT:
        return normalized in patterns
    if mode is MatchMode.PHRASE:
        return any(
            re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", normalized)
            for pattern in patterns
        )
    tokens = frozenset(re.findall(r"\w+", normalized))
    return any(
        frozenset(re.findall(r"\w+", pattern)).issubset(tokens)
        for pattern in patterns
    )


def _value_key(value: Any) -> str:
    return canonical_json(value)


def _candidate(
    *,
    dimension: str,
    value: Any,
    status: AttributeValueStatus,
    datum: _Datum,
    rule_id: str,
    rule_pack: CategoryRulePack,
) -> _Candidate:
    return _Candidate(
        dimension=dimension,
        value=value,
        value_key=_value_key(value),
        status=status,
        datum=datum,
        rule_id=rule_id,
        evidence=_evidence(datum, rule_id=rule_id, rule_pack=rule_pack),
    )


def _collect_candidates(
    data: tuple[_Datum, ...], rule_pack: CategoryRulePack
) -> tuple[dict[str, list[_Candidate]], list[str]]:
    result: dict[str, list[_Candidate]] = defaultdict(list)
    limitations: list[str] = []

    for rule in rule_pack.value_rules:
        for datum in _selected(
            data, sources=rule.sources,
            keys_or_fields=rule.keys_or_fields,
        ):
            if any(
                _matches(datum.normalized_text, MatchMode.PHRASE, (term,))
                for term in rule.exclusions
            ):
                continue
            if _matches(
                datum.normalized_text, rule.match_mode, rule.match_values
            ):
                result[rule.dimension].append(_candidate(
                    dimension=rule.dimension,
                    value=rule.result,
                    status=AttributeValueStatus.DERIVED_RULE,
                    datum=datum,
                    rule_id=rule.rule_id,
                    rule_pack=rule_pack,
                ))

    for rule in rule_pack.passthrough_rules:
        for datum in _selected(
            data, sources=rule.sources,
            keys_or_fields=rule.keys_or_fields,
        ):
            values = (
                datum.text.split(rule.list_delimiter)
                if rule.list_delimiter is not None
                else [datum.text]
            )
            for value in values:
                normalized = _normalized(value)
                if not normalized:
                    continue
                result[rule.dimension].append(_candidate(
                    dimension=rule.dimension,
                    value=normalized,
                    status=AttributeValueStatus.OBSERVED,
                    datum=datum,
                    rule_id=rule.rule_id,
                    rule_pack=rule_pack,
                ))

    for rule in rule_pack.measurement_rules:
        for datum in _selected(
            data, sources=rule.sources,
            keys_or_fields=rule.keys_or_fields,
        ):
            parsed = parse_measurement(
                datum.text,
                quantity_kind=rule.quantity_kind,
                scope=rule.scope,
                allow_bare_count=rule.allow_bare_count,
            )
            if parsed.measurement is None:
                limitations.append(
                    f"{rule.dimension}:{rule.rule_id}:{parsed.issue_code}"
                )
                continue
            result[rule.dimension].append(_candidate(
                dimension=rule.dimension,
                value=parsed.measurement.to_dict(),
                status=AttributeValueStatus.OBSERVED,
                datum=datum,
                rule_id=rule.rule_id,
                rule_pack=rule_pack,
            ))

    for negative in rule_pack.negative_rules:
        negative_data = [
            item for item in data
            if item.kind in negative.sources
            and any(term in item.normalized_text for term in negative.when_any)
            and not any(
                term in item.normalized_text for term in negative.unless_any
            )
        ]
        if not negative_data:
            continue
        retained: list[_Candidate] = []
        for item in result[negative.dimension]:
            block = (
                str(item.value).casefold() in negative.blocked_values
                and any(
                    _SOURCE_PRIORITY[neg.kind]
                    <= _SOURCE_PRIORITY[item.datum.kind]
                    for neg in negative_data
                )
            )
            if block:
                limitations.append(
                    f"{negative.dimension}:{negative.rule_id}:BLOCKED"
                )
            else:
                retained.append(item)
        result[negative.dimension] = retained

    return result, sorted(set(limitations))


def _attribute_value(
    candidate: _Candidate,
    agreeing: tuple[_Candidate, ...],
    rule_pack: CategoryRulePack,
) -> AttributeValue:
    evidence_ids = tuple(sorted({
        item.evidence.evidence_id for item in agreeing
    }))
    material = {
        "dimension": candidate.dimension,
        "value": candidate.value,
        "status": candidate.status.value,
        "evidence_ids": evidence_ids,
        "rule_id": candidate.rule_id,
        "rule_pack_version": rule_pack.version,
    }
    return AttributeValue(
        value_id=deterministic_id("attribute-value", material),
        value=candidate.value,
        status=candidate.status,
        confidence=candidate.evidence.confidence,
        evidence_ids=evidence_ids,
        rule_id=candidate.rule_id,
        rule_pack_version=rule_pack.version,
    )


def _resolve_slot(
    dimension: str,
    candidates: list[_Candidate],
    *,
    parsed: DetailedParameterParseResult | None,
    limitations: tuple[str, ...],
    rule_pack: CategoryRulePack,
) -> AttributeSlot:
    dimension_limitations = tuple(sorted(
        item for item in limitations if item.startswith(f"{dimension}:")
    ))
    if not candidates:
        status = (
            AttributeSlotStatus.REVIEW_REQUIRED
            if dimension_limitations
            else AttributeSlotStatus.UNAVAILABLE
        )
        return AttributeSlot(
            dimension=dimension,
            status=status,
            values=(),
            review_candidates=(),
            conflicts=(),
            limitations=dimension_limitations,
        )

    by_value: dict[str, list[_Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_value[candidate.value_key].append(candidate)
    value_heads = [
        sorted(
            group,
            key=lambda item: (
                _SOURCE_PRIORITY[item.datum.kind],
                item.rule_id,
                item.value_key,
            ),
        )[0]
        for group in by_value.values()
    ]
    top_priority = min(
        _SOURCE_PRIORITY[item.datum.kind] for item in value_heads
    )
    top = sorted(
        (
            item for item in value_heads
            if _SOURCE_PRIORITY[item.datum.kind] == top_priority
        ),
        key=lambda item: (item.value_key, item.rule_id),
    )
    selected = (
        sorted(
            value_heads,
            key=lambda item: (item.value_key, item.rule_id),
        )
        if dimension in _MULTI_DIMENSIONS
        else top[:1]
    )
    values = tuple(
        _attribute_value(
            item, tuple(by_value[item.value_key]), rule_pack
        )
        for item in selected
    )
    review_values = tuple(
        _attribute_value(
            item, tuple(by_value[item.value_key]), rule_pack
        )
        for item in value_heads
    )

    relevant_keys = {
        item.datum.key for item in candidates
        if item.datum.kind is SourceKind.STRUCTURED_PARAMETERS
        and item.datum.key is not None
    }
    structured_conflict = (
        parsed is not None
        and bool(parsed.conflicted_keys.intersection(relevant_keys))
    )
    top_conflict = (
        dimension not in _MULTI_DIMENSIONS and len(top) > 1
    )
    conflicts: list[AttributeConflict] = []
    if structured_conflict or top_conflict:
        code = (
            "STRUCTURED_SEMANTIC_KEY_CONFLICT"
            if structured_conflict
            else "SAME_PRIORITY_VALUE_CONFLICT"
        )
        ids = tuple(sorted(item.value_id for item in review_values))
        conflicts.append(AttributeConflict(
            conflict_id=deterministic_id(
                "attribute-conflict",
                {"dimension": dimension, "code": code, "values": ids},
            ),
            code=code,
            dimension=dimension,
            candidate_value_ids=ids,
            note="Conflicting evidence requires operator review.",
        ))
        return AttributeSlot(
            dimension=dimension,
            status=AttributeSlotStatus.REVIEW_REQUIRED,
            values=(),
            review_candidates=review_values,
            conflicts=tuple(conflicts),
            limitations=dimension_limitations,
        )

    lower_disagreement = dimension not in _MULTI_DIMENSIONS and any(
        item.value_key not in {choice.value_key for choice in selected}
        and _SOURCE_PRIORITY[item.datum.kind] > top_priority
        for item in value_heads
    )
    extra_limitations = list(dimension_limitations)
    if lower_disagreement:
        extra_limitations.append(
            f"{dimension}:LOWER_PRIORITY_DISAGREEMENT_RECORDED"
        )
    return AttributeSlot(
        dimension=dimension,
        status=AttributeSlotStatus.AVAILABLE,
        values=values,
        review_candidates=(),
        conflicts=(),
        limitations=tuple(sorted(extra_limitations)),
    )


def _map_record(
    record: ListingRecordV1, rule_pack: CategoryRulePack
) -> ProductAttributeRecord:
    parsed, data = _source_data(record)
    candidates, limitation_list = _collect_candidates(data, rule_pack)
    limitations = tuple(limitation_list)
    attributes = tuple(
        _resolve_slot(
            dimension,
            candidates.get(dimension, []),
            parsed=parsed,
            limitations=limitations,
            rule_pack=rule_pack,
        )
        for dimension in DIMENSIONS
    )
    used_evidence_ids = {
        evidence_id
        for slot in attributes
        for value in (*slot.values, *slot.review_candidates)
        for evidence_id in value.evidence_ids
    }
    evidence_by_id = {
        item.evidence.evidence_id: item.evidence
        for group in candidates.values()
        for item in group
    }
    evidence = tuple(
        evidence_by_id[evidence_id]
        for evidence_id in sorted(used_evidence_ids)
    )
    mapped_structured_keys = {
        item.datum.key
        for group in candidates.values()
        for item in group
        if item.datum.kind is SourceKind.STRUCTURED_PARAMETERS
        and item.datum.key is not None
    }
    record_limitations = tuple(sorted({
        *(
            f"STRUCTURED_PARAMETERS:{issue.code}"
            for issue in (() if parsed is None else parsed.issues)
        ),
        *(
            f"STRUCTURED_PARAMETERS:UNMAPPED_CONFLICT:{conflict.normalized_key}"
            for conflict in (() if parsed is None else parsed.conflicts)
            if conflict.normalized_key not in mapped_structured_keys
        ),
    }))
    review_count = sum(
        slot.status is AttributeSlotStatus.REVIEW_REQUIRED
        for slot in attributes
    ) + len(record_limitations)
    conflict_count = sum(len(slot.conflicts) for slot in attributes) + sum(
        item.startswith("STRUCTURED_PARAMETERS:UNMAPPED_CONFLICT:")
        for item in record_limitations
    )
    logical = {
        "asin": record.asin,
        "upstream_record_fingerprint": record.record_fingerprint,
        "structured_parameter_fingerprint":
            None if parsed is None else parsed.semantic_fingerprint,
        "evidence": [item.to_dict() for item in evidence],
        "attributes": [item.to_dict() for item in attributes],
        "record_limitations": list(record_limitations),
        "review_required_count": review_count,
        "conflict_count": conflict_count,
    }
    fingerprint = _hash(logical)
    return ProductAttributeRecord(
        record_id=deterministic_id(
            "product-attribute-record",
            {"asin": record.asin, "semantic_fingerprint": fingerprint},
        ),
        semantic_fingerprint=fingerprint,
        asin=record.asin,
        upstream_record_fingerprint=record.record_fingerprint,
        structured_parameter_fingerprint=(
            None if parsed is None else parsed.semantic_fingerprint
        ),
        evidence=evidence,
        attributes=attributes,
        record_limitations=record_limitations,
        review_required_count=review_count,
        conflict_count=conflict_count,
    )


def build_product_attribute_map(
    dataset: GovernedMarketDatasetV1,
    *,
    rule_pack: CategoryRulePack,
) -> ProductAttributeMapV1:
    if not isinstance(dataset, GovernedMarketDatasetV1):
        raise ListingAttributeMapError(
            "UPSTREAM_DATASET_INVALID",
            "dataset must be GovernedMarketDatasetV1",
        )
    category = _normalized(dataset.category)
    accepted_categories = {
        rule_pack.category, *rule_pack.category_aliases
    }
    if category not in accepted_categories:
        raise ListingAttributeMapError(
            "CATEGORY_RULE_PACK_MISMATCH",
            "dataset category is not authorized by the selected rule pack",
        )
    records = tuple(
        _map_record(record, rule_pack)
        for record in sorted(dataset.records, key=lambda item: item.asin)
    )
    coverage = tuple(
        (
            dimension,
            sum(
                next(
                    slot for slot in record.attributes
                    if slot.dimension == dimension
                ).status is AttributeSlotStatus.AVAILABLE
                for record in records
            ),
        )
        for dimension in DIMENSIONS
    )
    mapped = sum(
        any(
            slot.status is AttributeSlotStatus.AVAILABLE
            for slot in record.attributes
        )
        for record in records
    )
    review_count = sum(
        record.review_required_count for record in records
    )
    conflict_count = sum(record.conflict_count for record in records)
    logical = {
        "contract_version": "product-attribute-map-v1.0",
        "upstream_dataset_id": dataset.dataset_id,
        "upstream_semantic_fingerprint": dataset.semantic_fingerprint,
        "rule_pack_id": rule_pack.rule_pack_id,
        "rule_pack_version": rule_pack.version,
        "rule_pack_fingerprint": rule_pack.fingerprint,
        "parser_version": DETAILED_PARAMETER_PARSER_VERSION,
        "measurement_parser_version": MEASUREMENT_PARSER_VERSION,
        "engine_version": LISTING_ATTRIBUTE_ENGINE_VERSION,
        "coverage": coverage,
        "records": [record.to_dict() for record in records],
    }
    fingerprint = _hash(logical)
    return ProductAttributeMapV1(
        dataset_id=deterministic_id(
            "product-attribute-map",
            {
                "upstream_dataset_id": dataset.dataset_id,
                "semantic_fingerprint": fingerprint,
            },
        ),
        semantic_fingerprint=fingerprint,
        upstream_dataset_id=dataset.dataset_id,
        upstream_semantic_fingerprint=dataset.semantic_fingerprint,
        rule_pack_id=rule_pack.rule_pack_id,
        rule_pack_version=rule_pack.version,
        rule_pack_fingerprint=rule_pack.fingerprint,
        parser_version=DETAILED_PARAMETER_PARSER_VERSION,
        measurement_parser_version=MEASUREMENT_PARSER_VERSION,
        engine_version=LISTING_ATTRIBUTE_ENGINE_VERSION,
        listing_count=len(records),
        mapped_listing_count=mapped,
        review_required_count=review_count,
        conflict_count=conflict_count,
        coverage=coverage,
        records=records,
    )


__all__ = ("build_product_attribute_map",)
