"""Immutable public data models for Operator Output Layer V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)

from .errors import (
    OperatorOutputSerializationError,
    OperatorOutputValidationError,
)


OPERATOR_OUTPUT_RULESET_VERSION = "operator-output-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_KEYS = (
    "competition_intelligence",
    "demand_intelligence",
    "opportunity_intelligence",
    "opportunity_scoring",
    "product_intelligence",
    "recommendation_framework",
)
_SOURCE_SPECS = {
    "product_intelligence": (
        "product-intelligence-v0.1",
        "snapshot",
        {
            "snapshot_id", "ruleset_version", "target_product_identity", "scope",
            "included_product_identities", "source_bundle_fingerprints",
            "variation_topology", "product_fact_evidence_sets",
            "product_metric_series", "review_evidence_summary",
            "evidence_coverage_summary", "quality_issue_references",
            "out_of_scope_observation_references", "lineage_index", "diagnostics",
        },
    ),
    "demand_intelligence": (
        "demand-intelligence-v0.1",
        "demand-snapshot",
        {
            "snapshot_id", "ruleset_version", "target_keyword_identity",
            "source_bundle_fingerprints", "keyword_metric_evidence_sets",
            "relationship_evidence_groups", "query_execution_evidence",
            "related_product_evidence_inventory", "evidence_coverage",
            "quality_issue_references", "out_of_scope_evidence_references",
            "diagnostics", "lineage_index",
        },
    ),
    "competition_intelligence": (
        "competition-intelligence-v0.1",
        "competition-snapshot",
        {
            "snapshot_id", "ruleset_version", "source_bundle_fingerprints",
            "observed_product_inventory", "relationship_evidence_graph",
            "variation_evidence", "keyword_relationship_evidence",
            "keyword_evidence", "coverage", "quality_issue_references",
            "diagnostics", "lineage_index",
        },
    ),
    "opportunity_intelligence": (
        "opportunity-intelligence-v0.1",
        "opportunity-snapshot",
        {
            "snapshot_id", "ruleset_version", "source_bundle_fingerprints",
            "observed_signals", "derived_signals", "missing_evidence",
            "risk_evidence", "coverage", "quality_issue_references",
            "diagnostics", "lineage_index",
        },
    ),
    "opportunity_scoring": (
        "opportunity-scoring-v0.1",
        "opportunity-scoring-snapshot",
        {
            "snapshot_id", "ruleset_version", "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id", "source_policy_snapshot_id",
            "source_decision_snapshot_id", "source_bundle_fingerprints",
            "score_factors", "components", "calculations", "explanations",
            "coverage", "diagnostics", "lineage_index",
        },
    ),
    "recommendation_framework": (
        "recommendation-framework-v0.1",
        "recommendation-framework-snapshot",
        {
            "snapshot_id", "ruleset_version", "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id", "source_policy_snapshot_id",
            "source_decision_snapshot_id", "source_scoring_snapshot_id",
            "source_bundle_fingerprints", "recommendation_rules",
            "applicability_records", "generation_records", "explanations",
            "coverage", "diagnostics", "lineage_index",
        },
    ),
}
_FORBIDDEN_EXPORT_KEYS = {
    "api_credential", "api_credentials", "api_key", "api_secret",
    "authorization", "credential", "credentials", "hidden_metadata",
    "password", "raw_payload", "secret", "token",
}


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OperatorOutputValidationError(
            f"{path} must contain finite JSON data: {exc}"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OperatorOutputValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperatorOutputValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise OperatorOutputValidationError(
            f"{path} must be a non-negative integer"
        )
    return value


def _mapping(value: Any, path: str, *, allow_empty: bool = True) -> Mapping[str, Any]:
    frozen = _freeze_json(value, path)
    if not isinstance(frozen, MappingABC) or (not allow_empty and not frozen):
        raise OperatorOutputValidationError(f"{path} must be an object")
    return frozen


def _mapping_rows(
    value: Sequence[Mapping[str, Any]], path: str, *, allow_empty: bool = True
) -> tuple[Mapping[str, Any], ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise OperatorOutputValidationError(f"{path} must not be empty")
    frozen = tuple(_mapping(item, f"{path}[{index}]") for index, item in enumerate(values))
    ordered = tuple(sorted(frozen, key=canonical_json))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise OperatorOutputValidationError(f"{path} must not contain duplicates")
    _reject_forbidden_export_keys(ordered, path)
    return ordered


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise OperatorOutputValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise OperatorOutputValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise OperatorOutputValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise OperatorOutputValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise OperatorOutputValidationError(f"{path} contains duplicates")
    return ordered


def _reject_forbidden_export_keys(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, item in value.items():
            normalized = key.strip().lower()
            if normalized in _FORBIDDEN_EXPORT_KEYS:
                raise OperatorOutputValidationError(
                    f"{path} contains forbidden export field {key!r}"
                )
            _reject_forbidden_export_keys(item, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            _reject_forbidden_export_keys(item, f"{path}[{index}]")


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def _row_identity(model: JsonContract, prefix: str) -> str:
    payload = model.to_dict()
    payload.pop("output_row_id")
    payload.pop("lineage_reference_ids")
    return deterministic_id(prefix, payload)


def _identifier_values(value: Any, key: str = "") -> set[str]:
    values: set[str] = set()
    if isinstance(value, MappingABC):
        for child_key, child in value.items():
            values.update(_identifier_values(child, child_key))
    elif isinstance(value, (tuple, list)):
        if key.endswith("_ids"):
            values.update(item for item in value if type(item) is str and item.strip())
        for child in value:
            values.update(_identifier_values(child, key))
    elif key.endswith("_id") and type(value) is str and value.strip():
        values.add(value)
    return values


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    payload = bundle.to_dict()
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _validate_source_snapshot(
    payload: Mapping[str, Any], *, source_name: str, fingerprints: set[str]
) -> Mapping[str, Any]:
    if not isinstance(payload, MappingABC):
        raise OperatorOutputValidationError(f"{source_name} snapshot must be an object")
    ruleset, prefix, fields = _SOURCE_SPECS[source_name]
    if set(payload) != fields:
        missing = sorted(fields - set(payload))
        extra = sorted(set(payload) - fields)
        raise OperatorOutputValidationError(
            f"invalid {source_name} snapshot fields; missing={missing}, extra={extra}"
        )
    frozen = _freeze_json(payload, f"{source_name} snapshot")
    if frozen["ruleset_version"] != ruleset:
        raise OperatorOutputValidationError(
            f"unsupported {source_name} ruleset version"
        )
    snapshot_id = _text(frozen["snapshot_id"], f"{source_name}.snapshot_id")
    source_fingerprints = _unique_texts(
        frozen["source_bundle_fingerprints"],
        f"{source_name}.source_bundle_fingerprints",
        allow_empty=False,
    )
    if any(_SHA256.fullmatch(item) is None for item in source_fingerprints):
        raise OperatorOutputValidationError(
            f"{source_name} fingerprints must be SHA-256 hex"
        )
    if not set(source_fingerprints) <= fingerprints:
        raise OperatorOutputValidationError(
            f"{source_name} references a canonical bundle outside the request"
        )
    identity_payload = dict(frozen)
    identity_payload.pop("snapshot_id")
    if snapshot_id != deterministic_id(prefix, identity_payload):
        raise OperatorOutputValidationError(
            f"{source_name} snapshot identity mismatch"
        )
    _reject_forbidden_export_keys(frozen, f"{source_name} snapshot")
    return frozen


class _OperatorOutputModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OperatorOutputSerializationError:
            raise
        except (
            OperatorOutputValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise OperatorOutputSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductOutputRow(_OperatorOutputModel):
    """Table-oriented product evidence view without candidate resolution."""

    output_row_id: str
    asin: str
    marketplace: str
    title: tuple[Mapping[str, Any], ...]
    product_facts: tuple[Mapping[str, Any], ...]
    metrics: tuple[Mapping[str, Any], ...]
    variation_information: Mapping[str, Any]
    review_summary: Mapping[str, Any]
    data_quality_indicators: tuple[Mapping[str, Any], ...]
    source_snapshot_id: str
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("output_row_id", "asin", "marketplace", "source_snapshot_id"):
            _text(getattr(self, name), f"ProductOutputRow.{name}")
        object.__setattr__(self, "title", _mapping_rows(self.title, "product.title"))
        object.__setattr__(
            self, "product_facts", _mapping_rows(self.product_facts, "product.product_facts")
        )
        object.__setattr__(self, "metrics", _mapping_rows(self.metrics, "product.metrics"))
        object.__setattr__(
            self, "variation_information", _mapping(self.variation_information, "product.variation_information")
        )
        object.__setattr__(self, "review_summary", _mapping(self.review_summary, "product.review_summary"))
        object.__setattr__(
            self,
            "data_quality_indicators",
            _mapping_rows(self.data_quality_indicators, "product.data_quality_indicators"),
        )
        object.__setattr__(
            self,
            "lineage_reference_ids",
            _unique_texts(self.lineage_reference_ids, "product.lineage_reference_ids", allow_empty=False),
        )
        if self.output_row_id != _row_identity(self, "operator-product-row"):
            raise OperatorOutputValidationError("product output_row_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class KeywordOutputRow(_OperatorOutputModel):
    """Table-oriented directional keyword evidence view."""

    output_row_id: str
    keyword: Mapping[str, Any]
    keyword_metrics: tuple[Mapping[str, Any], ...]
    query_status: tuple[Mapping[str, Any], ...]
    related_products: tuple[Mapping[str, Any], ...]
    channels: tuple[str, ...]
    providers: tuple[str, ...]
    limitations: tuple[str, ...]
    source_snapshot_id: str
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("output_row_id", "source_snapshot_id"):
            _text(getattr(self, name), f"KeywordOutputRow.{name}")
        object.__setattr__(self, "keyword", _mapping(self.keyword, "keyword.keyword", allow_empty=False))
        for name in ("keyword_metrics", "query_status", "related_products"):
            object.__setattr__(self, name, _mapping_rows(getattr(self, name), f"keyword.{name}"))
        for name, allow_empty in (
            ("channels", True), ("providers", True), ("limitations", False),
            ("lineage_reference_ids", False),
        ):
            object.__setattr__(
                self, name, _unique_texts(getattr(self, name), f"keyword.{name}", allow_empty=allow_empty)
            )
        if self.output_row_id != _row_identity(self, "operator-keyword-row"):
            raise OperatorOutputValidationError("keyword output_row_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionOutputRow(_OperatorOutputModel):
    """One observed product-keyword evidence grouping, not a competitor list."""

    output_row_id: str
    product_endpoint: Mapping[str, Any]
    keyword_relationship: Mapping[str, Any]
    relationship_type: str
    channel: str
    provider: str
    evidence_count: int
    variation_evidence: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]
    source_snapshot_id: str
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "output_row_id", "relationship_type", "channel", "provider", "source_snapshot_id",
        ):
            _text(getattr(self, name), f"CompetitionOutputRow.{name}")
        object.__setattr__(
            self, "product_endpoint", _mapping(self.product_endpoint, "competition.product_endpoint", allow_empty=False)
        )
        object.__setattr__(
            self, "keyword_relationship", _mapping(self.keyword_relationship, "competition.keyword_relationship", allow_empty=False)
        )
        _count(self.evidence_count, "competition.evidence_count")
        if self.evidence_count == 0:
            raise OperatorOutputValidationError("competition evidence_count must be positive")
        object.__setattr__(
            self, "variation_evidence", _mapping_rows(self.variation_evidence, "competition.variation_evidence")
        )
        for name in ("limitations", "lineage_reference_ids"):
            object.__setattr__(
                self, name, _unique_texts(getattr(self, name), f"competition.{name}", allow_empty=False)
            )
        if self.output_row_id != _row_identity(self, "operator-competition-row"):
            raise OperatorOutputValidationError("competition output_row_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityOutputRow(_OperatorOutputModel):
    """Existing opportunity evidence and score references without scoring."""

    output_row_id: str
    product: tuple[Mapping[str, Any], ...]
    signals: tuple[Mapping[str, Any], ...]
    missing_evidence: tuple[Mapping[str, Any], ...]
    risk_evidence: tuple[Mapping[str, Any], ...]
    score_references: tuple[Mapping[str, Any], ...]
    explanation_references: tuple[Mapping[str, Any], ...]
    source_snapshot_ids: tuple[str, ...]
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.output_row_id, "OpportunityOutputRow.output_row_id")
        for name in (
            "product", "signals", "missing_evidence", "risk_evidence",
            "score_references", "explanation_references",
        ):
            object.__setattr__(self, name, _mapping_rows(getattr(self, name), f"opportunity.{name}"))
        for name in ("source_snapshot_ids", "lineage_reference_ids"):
            object.__setattr__(
                self, name, _unique_texts(getattr(self, name), f"opportunity.{name}", allow_empty=False)
            )
        if self.output_row_id != _row_identity(self, "operator-opportunity-row"):
            raise OperatorOutputValidationError("opportunity output_row_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationOutputRow(_OperatorOutputModel):
    """Existing recommendation record rendered without new recommendation logic."""

    output_row_id: str
    recommendation_type: str
    rule_reference: Mapping[str, Any]
    explanation: Mapping[str, Any]
    evidence_references: tuple[str, ...]
    limitations: tuple[str, ...]
    source_record_id: str
    source_snapshot_id: str
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "output_row_id", "recommendation_type", "source_record_id",
            "source_snapshot_id",
        ):
            _text(getattr(self, name), f"RecommendationOutputRow.{name}")
        object.__setattr__(
            self, "rule_reference", _mapping(self.rule_reference, "recommendation.rule_reference", allow_empty=False)
        )
        object.__setattr__(
            self, "explanation", _mapping(self.explanation, "recommendation.explanation", allow_empty=False)
        )
        for name in ("evidence_references", "limitations", "lineage_reference_ids"):
            object.__setattr__(
                self, name, _unique_texts(getattr(self, name), f"recommendation.{name}", allow_empty=False)
            )
        if self.output_row_id != _row_identity(self, "operator-recommendation-row"):
            raise OperatorOutputValidationError("recommendation output_row_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputLineageReference(_OperatorOutputModel):
    """Output-row link to a serialized source record and canonical emission."""

    output_lineage_id: str
    output_row_id: str
    output_view: str
    source_snapshot_id: str
    source_record_id: str
    source_lineage_id: str
    canonical_reference_id: str
    canonical_reference_type: str
    semantic_observation_id: str | None
    transformation_run_id: str
    mapping_version: str
    raw_evidence_id: str
    collection_run_id: str
    provider: str
    source_tool: str
    source_field: str
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "output_lineage_id", "output_row_id", "output_view", "source_snapshot_id",
            "source_record_id", "source_lineage_id", "canonical_reference_id",
            "canonical_reference_type", "transformation_run_id", "mapping_version",
            "raw_evidence_id", "collection_run_id", "provider", "source_tool", "source_field",
        ):
            _text(getattr(self, name), f"OutputLineageReference.{name}")
        _optional_text(self.semantic_observation_id, "OutputLineageReference.semantic_observation_id")
        if self.output_view not in {"PRODUCT", "KEYWORD", "COMPETITION_EVIDENCE", "OPPORTUNITY", "RECOMMENDATION"}:
            raise OperatorOutputValidationError("unsupported output view")
        if self.canonical_reference_type not in {"OBSERVATION", "QUERY_EXECUTION"}:
            raise OperatorOutputValidationError("unsupported canonical reference type")
        if self.canonical_reference_type == "OBSERVATION" and self.semantic_observation_id is None:
            raise OperatorOutputValidationError("observation lineage requires semantic_observation_id")
        object.__setattr__(
            self,
            "source_bundle_fingerprints",
            _unique_texts(
                self.source_bundle_fingerprints,
                "OutputLineageReference.source_bundle_fingerprints",
                allow_empty=False,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise OperatorOutputValidationError("lineage fingerprints must be SHA-256 hex")
        if self.output_lineage_id != deterministic_id(
            "operator-output-lineage", _without_id(self, "output_lineage_id")
        ):
            raise OperatorOutputValidationError("output_lineage_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputDiagnostic(_OperatorOutputModel):
    """Deterministic output-boundary diagnostic."""

    diagnostic_id: str
    code: str
    severity: str
    message: str
    source_snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("diagnostic_id", "code", "severity", "message"):
            _text(getattr(self, name), f"OutputDiagnostic.{name}")
        if self.severity not in {"INFO", "WARNING", "MATERIAL", "BLOCKING"}:
            raise OperatorOutputValidationError("invalid output diagnostic severity")
        object.__setattr__(
            self, "source_snapshot_ids", _unique_texts(
                self.source_snapshot_ids, "OutputDiagnostic.source_snapshot_ids", allow_empty=False
            )
        )
        if self.diagnostic_id != deterministic_id(
            "operator-output-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise OperatorOutputValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputCoverageSummary(_OperatorOutputModel):
    """Mechanical coverage counts for the five output tables."""

    product_row_count: int
    keyword_row_count: int
    competition_row_count: int
    opportunity_row_count: int
    recommendation_row_count: int
    source_snapshot_count: int
    lineage_reference_count: int
    diagnostic_count: int

    def __post_init__(self) -> None:
        for name in (
            "product_row_count", "keyword_row_count", "competition_row_count",
            "opportunity_row_count", "recommendation_row_count", "source_snapshot_count",
            "lineage_reference_count", "diagnostic_count",
        ):
            _count(getattr(self, name), f"OutputCoverageSummary.{name}")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorOutputRequest(_OperatorOutputModel):
    """Canonical bundles plus six immutable serialized source snapshots."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    product_intelligence_snapshot: Mapping[str, Any]
    demand_intelligence_snapshot: Mapping[str, Any]
    competition_intelligence_snapshot: Mapping[str, Any]
    opportunity_intelligence_snapshot: Mapping[str, Any]
    opportunity_scoring_snapshot: Mapping[str, Any]
    recommendation_framework_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise OperatorOutputValidationError(
                "canonical_bundles must contain CanonicalEvidenceBundle values"
            )
        for bundle in bundles:
            bundle.validate()
        ordered = tuple(sorted(bundles, key=bundle_fingerprint))
        fingerprints = tuple(bundle_fingerprint(item) for item in ordered)
        if len(set(fingerprints)) != len(fingerprints):
            raise OperatorOutputValidationError("canonical_bundles contain duplicate content")
        object.__setattr__(self, "canonical_bundles", ordered)
        fingerprint_set = set(fingerprints)
        for source_name in _SOURCE_KEYS:
            field_name = f"{source_name}_snapshot"
            object.__setattr__(
                self,
                field_name,
                _validate_source_snapshot(
                    getattr(self, field_name),
                    source_name=source_name,
                    fingerprints=fingerprint_set,
                ),
            )
        scoring = self.opportunity_scoring_snapshot
        recommendation = self.recommendation_framework_snapshot
        if recommendation["source_scoring_snapshot_id"] != scoring["snapshot_id"]:
            raise OperatorOutputValidationError(
                "recommendation source scoring snapshot does not match request"
            )
        for name in (
            "source_evaluation_snapshot_id", "source_conflict_resolution_snapshot_id",
            "source_policy_snapshot_id", "source_decision_snapshot_id",
        ):
            if recommendation[name] != scoring[name]:
                raise OperatorOutputValidationError(
                    f"recommendation and scoring {name} do not match"
                )


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorOutputSnapshotV0_1(_OperatorOutputModel):
    """Auditable, deterministic five-table operator output snapshot."""

    snapshot_id: str
    ruleset_version: str
    source_bundle_fingerprints: tuple[str, ...]
    source_snapshot_ids: Mapping[str, str]
    product_rows: tuple[ProductOutputRow, ...]
    keyword_rows: tuple[KeywordOutputRow, ...]
    competition_rows: tuple[CompetitionOutputRow, ...]
    opportunity_rows: tuple[OpportunityOutputRow, ...]
    recommendation_rows: tuple[RecommendationOutputRow, ...]
    coverage: OutputCoverageSummary
    diagnostics: tuple[OutputDiagnostic, ...]
    lineage_index: tuple[OutputLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "OperatorOutputSnapshotV0_1.snapshot_id")
        if self.ruleset_version != OPERATOR_OUTPUT_RULESET_VERSION:
            raise OperatorOutputValidationError("unsupported operator output ruleset")
        object.__setattr__(
            self,
            "source_bundle_fingerprints",
            _unique_texts(
                self.source_bundle_fingerprints,
                "operator source_bundle_fingerprints",
                allow_empty=False,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise OperatorOutputValidationError("operator fingerprints must be SHA-256 hex")
        source_ids = _mapping(self.source_snapshot_ids, "operator source_snapshot_ids", allow_empty=False)
        if set(source_ids) != set(_SOURCE_KEYS):
            raise OperatorOutputValidationError("operator source_snapshot_ids fields mismatch")
        for key, value in source_ids.items():
            _text(value, f"operator source_snapshot_ids.{key}")
        if len(set(source_ids.values())) != len(source_ids):
            raise OperatorOutputValidationError("source snapshot identities must be unique")
        object.__setattr__(self, "source_snapshot_ids", source_ids)
        row_specs = (
            ("product_rows", ProductOutputRow, "PRODUCT"),
            ("keyword_rows", KeywordOutputRow, "KEYWORD"),
            ("competition_rows", CompetitionOutputRow, "COMPETITION_EVIDENCE"),
            ("opportunity_rows", OpportunityOutputRow, "OPPORTUNITY"),
            ("recommendation_rows", RecommendationOutputRow, "RECOMMENDATION"),
        )
        for name, expected, _ in row_specs:
            object.__setattr__(
                self,
                name,
                _typed_unique(getattr(self, name), expected, f"operator {name}", lambda item: item.output_row_id),
            )
        object.__setattr__(
            self,
            "diagnostics",
            _typed_unique(self.diagnostics, OutputDiagnostic, "operator diagnostics", lambda item: item.diagnostic_id),
        )
        object.__setattr__(
            self,
            "lineage_index",
            _typed_unique(
                self.lineage_index, OutputLineageReference, "operator lineage_index", lambda item: item.output_lineage_id
            ),
        )
        if not isinstance(self.coverage, OutputCoverageSummary):
            raise OperatorOutputValidationError("operator coverage must be OutputCoverageSummary")
        rows = tuple(row for name, _, _ in row_specs for row in getattr(self, name))
        row_ids = [row.output_row_id for row in rows]
        if len(row_ids) != len(set(row_ids)):
            raise OperatorOutputValidationError("output row identities must be globally unique")
        lineage_by_id = {item.output_lineage_id: item for item in self.lineage_index}
        referenced: set[str] = set()
        source_values = set(source_ids.values())
        expected_views = {
            row.output_row_id: view
            for name, _, view in row_specs
            for row in getattr(self, name)
        }
        for row in rows:
            row_payload = row.to_dict()
            source_record_ids = _identifier_values(row_payload)
            source_record_ids.discard(row.output_row_id)
            source_record_ids.difference_update(row.lineage_reference_ids)
            allowed_sources = (
                set(row.source_snapshot_ids)
                if isinstance(row, OpportunityOutputRow)
                else {row.source_snapshot_id}
            )
            for lineage_id in row.lineage_reference_ids:
                lineage = lineage_by_id.get(lineage_id)
                if lineage is None or lineage.output_row_id != row.output_row_id:
                    raise OperatorOutputValidationError("output row has broken lineage reference")
                if (
                    lineage.source_snapshot_id not in source_values
                    or lineage.source_snapshot_id not in allowed_sources
                ):
                    raise OperatorOutputValidationError(
                        "output lineage source snapshot is absent or belongs to another view"
                    )
                if lineage.output_view != expected_views[row.output_row_id]:
                    raise OperatorOutputValidationError(
                        "output lineage view does not match its row"
                    )
                if not set(lineage.source_bundle_fingerprints) <= set(
                    self.source_bundle_fingerprints
                ):
                    raise OperatorOutputValidationError(
                        "output lineage fingerprint is absent from the snapshot"
                    )
                if lineage.source_record_id not in source_record_ids:
                    raise OperatorOutputValidationError(
                        "output lineage source record is absent from its row: "
                        f"view={lineage.output_view}, source_record_id={lineage.source_record_id}"
                    )
                referenced.add(lineage_id)
        if referenced != set(lineage_by_id):
            raise OperatorOutputValidationError("operator lineage must be referenced exactly once")
        expected_coverage = coverage_from_rows(
            product_rows=self.product_rows,
            keyword_rows=self.keyword_rows,
            competition_rows=self.competition_rows,
            opportunity_rows=self.opportunity_rows,
            recommendation_rows=self.recommendation_rows,
            source_snapshot_ids=self.source_snapshot_ids,
            lineage=self.lineage_index,
            diagnostics=self.diagnostics,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise OperatorOutputValidationError("operator output coverage mismatch")
        expected_id = deterministic_id(
            "operator-output-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise OperatorOutputSerializationError(
                "snapshot_id does not match operator output content"
            )

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        values = _tuple(bundles, "bundles")
        if not values or any(not isinstance(item, CanonicalEvidenceBundle) for item in values):
            raise OperatorOutputValidationError("bundles must contain canonical bundles")
        for bundle in values:
            bundle.validate()
        fingerprints = {bundle_fingerprint(item) for item in values}
        if fingerprints != set(self.source_bundle_fingerprints):
            raise OperatorOutputValidationError("validation bundle fingerprints mismatch")
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        emissions: dict[tuple[str, str], tuple[Any, set[str], str]] = {}
        for bundle in values:
            fingerprint = bundle_fingerprint(bundle)
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                prior = runs.get(run.transformation_run_id)
                if prior is not None and canonical_json(prior) != canonical_json(run):
                    raise OperatorOutputValidationError("transformation run identity collision")
                runs[run.transformation_run_id] = run
            records = tuple((item, "OBSERVATION") for item in bundle.observations) + tuple(
                (item, "QUERY_EXECUTION") for item in bundle.query_execution_records
            )
            for record, reference_type in records:
                reference_id = (
                    record.observation_id if reference_type == "OBSERVATION" else record.query_execution_id
                )
                run_id = record.provenance.transformation.transformation_run_id
                key = (reference_id, run_id)
                prior = emissions.get(key)
                if prior is not None and canonical_json(prior[0]) != canonical_json(record):
                    raise OperatorOutputValidationError("canonical emission identity collision")
                if prior is None:
                    emissions[key] = (record, {fingerprint}, reference_type)
                else:
                    prior[1].add(fingerprint)
        for lineage in self.lineage_index:
            key = (lineage.canonical_reference_id, lineage.transformation_run_id)
            emission = emissions.get(key)
            if emission is None or emission[2] != lineage.canonical_reference_type:
                raise OperatorOutputValidationError("operator lineage canonical reference is absent")
            record, emission_fingerprints, reference_type = emission
            provenance = record.provenance
            transformation = provenance.transformation
            run = runs.get(lineage.transformation_run_id)
            expected_semantic = getattr(record, "semantic_observation_id", None)
            expected_output_ids = (
                run.output_observation_ids if reference_type == "OBSERVATION" else run.output_query_execution_ids
            ) if run is not None else ()
            if (
                run is None
                or lineage.canonical_reference_id not in expected_output_ids
                or lineage.raw_evidence_id not in raw_ids
                or lineage.raw_evidence_id not in run.input_raw_evidence_references
                or transformation.raw_evidence_reference != lineage.raw_evidence_id
                or transformation.mapping_version != lineage.mapping_version
                or transformation.collection_run_id != lineage.collection_run_id
                or provenance.provider != lineage.provider
                or provenance.source_tool != lineage.source_tool
                or provenance.source_field != lineage.source_field
                or expected_semantic != lineage.semantic_observation_id
                or not set(lineage.source_bundle_fingerprints) <= emission_fingerprints
            ):
                raise OperatorOutputValidationError("operator lineage does not replay against canonical bundles")
        return self

    def to_json(self) -> str:
        return canonical_json(self)

    def to_table_rows(self) -> dict[str, tuple[dict[str, Any], ...]]:
        """Return flat, deterministic rows whose values are CSV-safe scalars."""

        def flatten(row: JsonContract) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in row.to_dict().items():
                result[key] = value if value is None or type(value) in {str, bool, int, float} else canonical_json(value)
            return result

        return {
            "product": tuple(flatten(item) for item in self.product_rows),
            "keyword": tuple(flatten(item) for item in self.keyword_rows),
            "competition_evidence": tuple(flatten(item) for item in self.competition_rows),
            "opportunity": tuple(flatten(item) for item in self.opportunity_rows),
            "recommendation": tuple(flatten(item) for item in self.recommendation_rows),
        }


def coverage_from_rows(
    *,
    product_rows: Sequence[ProductOutputRow],
    keyword_rows: Sequence[KeywordOutputRow],
    competition_rows: Sequence[CompetitionOutputRow],
    opportunity_rows: Sequence[OpportunityOutputRow],
    recommendation_rows: Sequence[RecommendationOutputRow],
    source_snapshot_ids: Mapping[str, str],
    lineage: Sequence[OutputLineageReference],
    diagnostics: Sequence[OutputDiagnostic],
) -> OutputCoverageSummary:
    return OutputCoverageSummary(
        product_row_count=len(product_rows),
        keyword_row_count=len(keyword_rows),
        competition_row_count=len(competition_rows),
        opportunity_row_count=len(opportunity_rows),
        recommendation_row_count=len(recommendation_rows),
        source_snapshot_count=len(source_snapshot_ids),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
    )


__all__ = (
    "OPERATOR_OUTPUT_RULESET_VERSION",
    "OperatorOutputRequest",
    "OperatorOutputSnapshotV0_1",
    "ProductOutputRow",
    "KeywordOutputRow",
    "CompetitionOutputRow",
    "OpportunityOutputRow",
    "RecommendationOutputRow",
    "OutputCoverageSummary",
    "OutputLineageReference",
    "OutputDiagnostic",
)
