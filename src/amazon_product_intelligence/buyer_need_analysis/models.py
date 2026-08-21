"""Immutable, evidence-first Buyer Need Analysis contracts V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any, Mapping, Self

from amazon_product_intelligence.category_product_map import (
    CategoryProductMapSnapshot,
    CategoryScope,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    KeywordIdentity,
    PresenceStatus,
    ProductIdentity,
    Provenance,
    ReviewObservation,
    Severity,
    deterministic_id,
)
from amazon_product_intelligence.demand_intelligence import DemandLineageReference
from amazon_product_intelligence.normalization import normalize_keyword_text
from amazon_product_intelligence.product_intelligence import LineageReference

from .errors import BuyerNeedSerializationError, BuyerNeedValidationError


BUYER_NEED_CONTRACT_VERSION = "buyer-need-contract-v0.1"
BUYER_NEED_TAXONOMY_VERSION = "buyer-need-taxonomy-v0.1"
BUYER_NEED_RULESET_VERSION = "buyer-need-rules-v0.1"


class BuyerNeedType(StrEnum):
    USE_CASE = "USE_CASE"
    AUDIENCE = "AUDIENCE"
    PROBLEM_SOLUTION = "PROBLEM_SOLUTION"
    ATTRIBUTE_NEED = "ATTRIBUTE_NEED"
    SPECIFICATION_PREFERENCE = "SPECIFICATION_PREFERENCE"
    COMPATIBILITY = "COMPATIBILITY"
    UNKNOWN = "UNKNOWN"


class BuyerNeedTextSourceType(StrEnum):
    SEARCH_TERM = "SEARCH_TERM"
    REVIEW = "REVIEW"
    TITLE = "TITLE"
    BULLET = "BULLET"
    DESCRIPTION = "DESCRIPTION"


class BuyerNeedSourceReferenceType(StrEnum):
    KEYWORD_IDENTITY = "KEYWORD_IDENTITY"
    REVIEW_OBSERVATION = "REVIEW_OBSERVATION"
    PRODUCT_FACT_OBSERVATION = "PRODUCT_FACT_OBSERVATION"


class BuyerNeedConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class BuyerNeedCandidateStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    UNKNOWN = "UNKNOWN"


class BuyerNeedContextStatus(StrEnum):
    KNOWN = "KNOWN"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class BuyerNeedMatchStrength(StrEnum):
    EXPLICIT = "EXPLICIT"
    WEAK = "WEAK"


class BuyerNeedLabelStrategy(StrEnum):
    CANONICAL = "CANONICAL"
    MATCH_NORMALIZED = "MATCH_NORMALIZED"


class BuyerNeedEvidenceRequirement(StrEnum):
    EXPLICIT_TEXT_SPAN = "EXPLICIT_TEXT_SPAN"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise BuyerNeedValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise BuyerNeedValidationError(f"{path} must be a sequence")
    return tuple(value)


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    payload = model.to_dict()
    payload.pop(field_name)
    return deterministic_id(prefix, payload)


class _BuyerNeedModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except BuyerNeedValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise BuyerNeedSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedTextSpan(_BuyerNeedModel):
    start: int
    end: int
    matched_text: str

    def __post_init__(self) -> None:
        if type(self.start) is not int or self.start < 0:
            raise BuyerNeedValidationError("text span start must be a non-negative integer")
        if type(self.end) is not int or self.end <= self.start:
            raise BuyerNeedValidationError("text span end must follow start")
        _text(self.matched_text, "BuyerNeedTextSpan.matched_text")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedSourceReference(_BuyerNeedModel):
    source_reference_id: str
    reference_type: BuyerNeedSourceReferenceType
    reference_id: str
    canonical_observation_id: str | None
    product_identity: ProductIdentity | None
    keyword_identity: KeywordIdentity | None
    provenance: Provenance | None
    product_lineage: LineageReference | None
    demand_lineage: DemandLineageReference | None

    def __post_init__(self) -> None:
        if not isinstance(self.reference_type, BuyerNeedSourceReferenceType):
            raise BuyerNeedValidationError("source reference type is invalid")
        _text(self.reference_id, "BuyerNeedSourceReference.reference_id")
        _optional_text(
            self.canonical_observation_id,
            "BuyerNeedSourceReference.canonical_observation_id",
        )
        if self.product_identity is not None and not isinstance(
            self.product_identity, ProductIdentity
        ):
            raise BuyerNeedValidationError("source product_identity has a wrong type")
        if self.keyword_identity is not None and not isinstance(
            self.keyword_identity, KeywordIdentity
        ):
            raise BuyerNeedValidationError("source keyword_identity has a wrong type")
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise BuyerNeedValidationError("source provenance has a wrong type")
        if self.product_lineage is not None and not isinstance(
            self.product_lineage, LineageReference
        ):
            raise BuyerNeedValidationError("source product lineage has a wrong type")
        if self.demand_lineage is not None and not isinstance(
            self.demand_lineage, DemandLineageReference
        ):
            raise BuyerNeedValidationError("source demand lineage has a wrong type")
        if self.product_lineage is not None and self.demand_lineage is not None:
            raise BuyerNeedValidationError("one text source cannot claim two lineage systems")

        if self.reference_type is BuyerNeedSourceReferenceType.KEYWORD_IDENTITY:
            if self.keyword_identity is None or self.reference_id != self.keyword_identity.keyword_id:
                raise BuyerNeedValidationError(
                    "keyword source reference must preserve its KeywordIdentity"
                )
            if self.product_identity is not None or self.provenance is not None:
                raise BuyerNeedValidationError(
                    "keyword identity reference cannot invent product or provenance context"
                )
            if self.product_lineage is not None:
                raise BuyerNeedValidationError("keyword source cannot use product lineage")
        elif self.reference_type is BuyerNeedSourceReferenceType.REVIEW_OBSERVATION:
            if (
                self.product_identity is None
                or self.canonical_observation_id is None
                or self.provenance is None
            ):
                raise BuyerNeedValidationError(
                    "review source requires ASIN identity, canonical observation, and provenance"
                )
            if self.keyword_identity is not None or self.demand_lineage is not None:
                raise BuyerNeedValidationError("review source cannot claim keyword lineage")
        else:
            if (
                self.product_identity is None
                or self.canonical_observation_id is None
                or self.provenance is None
            ):
                raise BuyerNeedValidationError(
                    "product text source requires ASIN identity, observation, and provenance"
                )
            if self.keyword_identity is not None or self.demand_lineage is not None:
                raise BuyerNeedValidationError("product text source cannot claim keyword lineage")

        if self.product_lineage is not None:
            if self.product_lineage.observation_id != self.canonical_observation_id:
                raise BuyerNeedValidationError("product lineage observation mismatch")
            if self.provenance is not None and (
                self.product_lineage.provider != self.provenance.provider
                or self.product_lineage.source_tool != self.provenance.source_tool
                or self.product_lineage.raw_evidence_id
                != self.provenance.transformation.raw_evidence_reference
            ):
                raise BuyerNeedValidationError("product lineage provenance mismatch")
        if self.demand_lineage is not None and self.keyword_identity is None:
            raise BuyerNeedValidationError("demand lineage requires KeywordIdentity context")
        if self.source_reference_id != _identity(
            "buyer-need-source-reference", self, "source_reference_id"
        ):
            raise BuyerNeedValidationError("source_reference_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedTextEvidence(_BuyerNeedModel):
    text_id: str
    raw_text: str
    normalized_text: str
    source_type: BuyerNeedTextSourceType
    source_reference: BuyerNeedSourceReference
    span: BuyerNeedTextSpan

    def __post_init__(self) -> None:
        _text(self.raw_text, "BuyerNeedTextEvidence.raw_text")
        _text(self.normalized_text, "BuyerNeedTextEvidence.normalized_text")
        if not isinstance(self.source_type, BuyerNeedTextSourceType):
            raise BuyerNeedValidationError("text evidence source_type is invalid")
        if not isinstance(self.source_reference, BuyerNeedSourceReference):
            raise BuyerNeedValidationError("text evidence source_reference has a wrong type")
        if not isinstance(self.span, BuyerNeedTextSpan):
            raise BuyerNeedValidationError("text evidence span has a wrong type")
        expected_normalized = normalize_keyword_text(self.raw_text)
        if self.normalized_text != expected_normalized:
            raise BuyerNeedValidationError(
                "normalized_text must use the existing canonical keyword text normalizer"
            )
        if self.span.end > len(self.raw_text):
            raise BuyerNeedValidationError("text evidence span exceeds raw_text")
        if self.raw_text[self.span.start : self.span.end] != self.span.matched_text:
            raise BuyerNeedValidationError("text evidence span does not match raw_text")
        expected_reference = {
            BuyerNeedTextSourceType.SEARCH_TERM: BuyerNeedSourceReferenceType.KEYWORD_IDENTITY,
            BuyerNeedTextSourceType.REVIEW: BuyerNeedSourceReferenceType.REVIEW_OBSERVATION,
            BuyerNeedTextSourceType.TITLE: BuyerNeedSourceReferenceType.PRODUCT_FACT_OBSERVATION,
            BuyerNeedTextSourceType.BULLET: BuyerNeedSourceReferenceType.PRODUCT_FACT_OBSERVATION,
            BuyerNeedTextSourceType.DESCRIPTION: BuyerNeedSourceReferenceType.PRODUCT_FACT_OBSERVATION,
        }[self.source_type]
        if self.source_reference.reference_type is not expected_reference:
            raise BuyerNeedValidationError("text source type and source reference type disagree")
        if self.source_type is BuyerNeedTextSourceType.SEARCH_TERM:
            keyword = self.source_reference.keyword_identity
            assert keyword is not None
            if self.raw_text != keyword.raw_text or self.normalized_text != keyword.normalized_text:
                raise BuyerNeedValidationError("search-term text must preserve its KeywordIdentity text")
        if self.text_id != _identity("buyer-need-text", self, "text_id"):
            raise BuyerNeedValidationError("text_id does not match text evidence content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedProductContext(_BuyerNeedModel):
    status: BuyerNeedContextStatus
    product_identities: tuple[ProductIdentity, ...]
    attribute_profile_ids: tuple[str, ...]
    product_intelligence_snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, BuyerNeedContextStatus):
            raise BuyerNeedValidationError("product context status is invalid")
        products = _tuple(self.product_identities, "product context identities")
        profiles = _tuple(self.attribute_profile_ids, "product context profile ids")
        snapshots = _tuple(
            self.product_intelligence_snapshot_ids,
            "product context snapshot ids",
        )
        if any(not isinstance(item, ProductIdentity) for item in products):
            raise BuyerNeedValidationError("product context contains a wrong identity type")
        if any(type(item) is not str or not item.strip() for item in profiles + snapshots):
            raise BuyerNeedValidationError("product context identifiers require non-empty text")
        if (
            len({item.product_id for item in products}) != len(products)
            or len(set(profiles)) != len(profiles)
            or len(set(snapshots)) != len(snapshots)
        ):
            raise BuyerNeedValidationError("product context values must be unique")
        has_context = bool(products or profiles or snapshots)
        if self.status is BuyerNeedContextStatus.UNKNOWN and has_context:
            raise BuyerNeedValidationError("UNKNOWN product context cannot publish identifiers")
        if self.status is BuyerNeedContextStatus.KNOWN and not products:
            raise BuyerNeedValidationError("KNOWN product context requires ProductIdentity")
        if self.status is BuyerNeedContextStatus.PARTIAL and not has_context:
            raise BuyerNeedValidationError("PARTIAL product context requires partial identifiers")
        object.__setattr__(
            self,
            "product_identities",
            tuple(sorted(products, key=lambda item: item.product_id)),
        )
        object.__setattr__(self, "attribute_profile_ids", tuple(sorted(profiles)))
        object.__setattr__(
            self,
            "product_intelligence_snapshot_ids",
            tuple(sorted(snapshots)),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedCategoryContext(_BuyerNeedModel):
    status: BuyerNeedContextStatus
    category_scope: CategoryScope | None
    category_map_id: str | None
    category_label: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, BuyerNeedContextStatus):
            raise BuyerNeedValidationError("category context status is invalid")
        if self.category_scope is not None and not isinstance(self.category_scope, CategoryScope):
            raise BuyerNeedValidationError("category context scope has a wrong type")
        _optional_text(self.category_map_id, "BuyerNeedCategoryContext.category_map_id")
        _optional_text(self.category_label, "BuyerNeedCategoryContext.category_label")
        has_context = any(
            item is not None
            for item in (self.category_scope, self.category_map_id, self.category_label)
        )
        if self.status is BuyerNeedContextStatus.UNKNOWN and has_context:
            raise BuyerNeedValidationError("UNKNOWN category context cannot publish context")
        if self.status is BuyerNeedContextStatus.KNOWN and (
            self.category_scope is None or self.category_map_id is None
        ):
            raise BuyerNeedValidationError(
                "KNOWN category context requires category scope and map id"
            )
        if self.status is BuyerNeedContextStatus.PARTIAL and not has_context:
            raise BuyerNeedValidationError("PARTIAL category context requires partial context")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedConfidence(_BuyerNeedModel):
    level: BuyerNeedConfidenceLevel
    basis: tuple[str, ...]
    ruleset_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.level, BuyerNeedConfidenceLevel):
            raise BuyerNeedValidationError("buyer need confidence level is invalid")
        basis = _tuple(self.basis, "buyer need confidence basis")
        if any(type(item) is not str or not item.strip() for item in basis):
            raise BuyerNeedValidationError("buyer need confidence basis requires text")
        if len(set(basis)) != len(basis):
            raise BuyerNeedValidationError("buyer need confidence basis must be unique")
        _text(self.ruleset_version, "BuyerNeedConfidence.ruleset_version")
        if self.level is BuyerNeedConfidenceLevel.UNKNOWN and basis:
            raise BuyerNeedValidationError("UNKNOWN confidence cannot claim a basis")
        if self.level is not BuyerNeedConfidenceLevel.UNKNOWN and not basis:
            raise BuyerNeedValidationError("known confidence requires an explicit basis")
        object.__setattr__(self, "basis", tuple(sorted(basis)))


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedDiagnostic(_BuyerNeedModel):
    diagnostic_id: str
    code: str
    severity: Severity
    text_id: str
    message: str

    def __post_init__(self) -> None:
        _text(self.code, "BuyerNeedDiagnostic.code")
        if not isinstance(self.severity, Severity):
            raise BuyerNeedValidationError("buyer need diagnostic severity is invalid")
        _text(self.text_id, "BuyerNeedDiagnostic.text_id")
        _text(self.message, "BuyerNeedDiagnostic.message")
        if self.diagnostic_id != _identity(
            "buyer-need-diagnostic", self, "diagnostic_id"
        ):
            raise BuyerNeedValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedTaxonomyEntry(_BuyerNeedModel):
    taxonomy_need_id: str
    need_type: BuyerNeedType
    canonical_label: str
    definition: str
    regex_patterns: tuple[str, ...]
    applicable_source_types: tuple[BuyerNeedTextSourceType, ...]
    match_strength: BuyerNeedMatchStrength
    label_strategy: BuyerNeedLabelStrategy
    evidence_requirement: BuyerNeedEvidenceRequirement

    def __post_init__(self) -> None:
        if not isinstance(self.need_type, BuyerNeedType) or self.need_type is BuyerNeedType.UNKNOWN:
            raise BuyerNeedValidationError("taxonomy entry requires a concrete need type")
        _text(self.canonical_label, "BuyerNeedTaxonomyEntry.canonical_label")
        _text(self.definition, "BuyerNeedTaxonomyEntry.definition")
        patterns = _tuple(self.regex_patterns, "taxonomy regex patterns")
        sources = _tuple(self.applicable_source_types, "taxonomy source types")
        if not patterns or any(type(item) is not str or not item for item in patterns):
            raise BuyerNeedValidationError("taxonomy entry requires regex patterns")
        if not sources or any(not isinstance(item, BuyerNeedTextSourceType) for item in sources):
            raise BuyerNeedValidationError("taxonomy entry requires source types")
        if len(set(patterns)) != len(patterns) or len(set(sources)) != len(sources):
            raise BuyerNeedValidationError("taxonomy patterns and source types must be unique")
        for pattern in patterns:
            try:
                re.compile(pattern, flags=re.IGNORECASE)
            except re.error as exc:
                raise BuyerNeedValidationError(
                    f"invalid taxonomy regex pattern {pattern!r}: {exc}"
                ) from exc
        if not isinstance(self.match_strength, BuyerNeedMatchStrength):
            raise BuyerNeedValidationError("taxonomy match strength is invalid")
        if not isinstance(self.label_strategy, BuyerNeedLabelStrategy):
            raise BuyerNeedValidationError("taxonomy label strategy is invalid")
        if not isinstance(self.evidence_requirement, BuyerNeedEvidenceRequirement):
            raise BuyerNeedValidationError("taxonomy evidence requirement is invalid")
        object.__setattr__(self, "regex_patterns", tuple(sorted(patterns)))
        object.__setattr__(
            self,
            "applicable_source_types",
            tuple(sorted(sources, key=lambda item: item.value)),
        )
        if self.taxonomy_need_id != _identity(
            "buyer-need-taxonomy-entry", self, "taxonomy_need_id"
        ):
            raise BuyerNeedValidationError("taxonomy_need_id does not match entry content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedTaxonomyRegistry(_BuyerNeedModel):
    registry_id: str
    taxonomy_version: str
    entries: tuple[BuyerNeedTaxonomyEntry, ...]

    def __post_init__(self) -> None:
        _text(self.taxonomy_version, "BuyerNeedTaxonomyRegistry.taxonomy_version")
        entries = _tuple(self.entries, "BuyerNeedTaxonomyRegistry.entries")
        if not entries or any(not isinstance(item, BuyerNeedTaxonomyEntry) for item in entries):
            raise BuyerNeedValidationError("buyer need taxonomy requires entries")
        if len({item.taxonomy_need_id for item in entries}) != len(entries):
            raise BuyerNeedValidationError("taxonomy entry ids must be unique")
        required_types = set(BuyerNeedType) - {BuyerNeedType.UNKNOWN}
        if {item.need_type for item in entries} != required_types:
            raise BuyerNeedValidationError(
                "buyer need taxonomy must cover every supported concrete need type"
            )
        object.__setattr__(
            self,
            "entries",
            tuple(sorted(entries, key=lambda item: item.taxonomy_need_id)),
        )
        if self.registry_id != _identity(
            "buyer-need-taxonomy", self, "registry_id"
        ):
            raise BuyerNeedValidationError("registry_id does not match taxonomy content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedEvidence(_BuyerNeedModel):
    need_id: str
    need_type: BuyerNeedType
    need_label: str
    source_text: str
    normalized_text: str
    evidence_source: BuyerNeedTextSourceType
    product_context: BuyerNeedProductContext
    category_context: BuyerNeedCategoryContext
    confidence: BuyerNeedConfidence
    status: BuyerNeedCandidateStatus
    source_evidence: tuple[BuyerNeedTextEvidence, ...]
    diagnostics: tuple[BuyerNeedDiagnostic, ...]
    taxonomy_version: str
    ruleset_version: str
    taxonomy_need_id: str | None
    extraction_rule_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.need_type, BuyerNeedType):
            raise BuyerNeedValidationError("buyer need type is invalid")
        _text(self.need_label, "BuyerNeedEvidence.need_label")
        _text(self.source_text, "BuyerNeedEvidence.source_text")
        _text(self.normalized_text, "BuyerNeedEvidence.normalized_text")
        if not isinstance(self.evidence_source, BuyerNeedTextSourceType):
            raise BuyerNeedValidationError("buyer need evidence source is invalid")
        if not isinstance(self.product_context, BuyerNeedProductContext):
            raise BuyerNeedValidationError("buyer need product context has a wrong type")
        if not isinstance(self.category_context, BuyerNeedCategoryContext):
            raise BuyerNeedValidationError("buyer need category context has a wrong type")
        if not isinstance(self.confidence, BuyerNeedConfidence):
            raise BuyerNeedValidationError("buyer need confidence has a wrong type")
        if not isinstance(self.status, BuyerNeedCandidateStatus):
            raise BuyerNeedValidationError("buyer need candidate status is invalid")
        evidence = _tuple(self.source_evidence, "buyer need source evidence")
        diagnostics = _tuple(self.diagnostics, "buyer need diagnostics")
        if len(evidence) != 1 or not isinstance(evidence[0], BuyerNeedTextEvidence):
            raise BuyerNeedValidationError(
                "Buyer Need v0.1 requires exactly one explicit text evidence item"
            )
        if any(not isinstance(item, BuyerNeedDiagnostic) for item in diagnostics):
            raise BuyerNeedValidationError("buyer need diagnostics contain a wrong type")
        if len({item.diagnostic_id for item in diagnostics}) != len(diagnostics):
            raise BuyerNeedValidationError("buyer need diagnostics must be unique")
        source = evidence[0]
        if (
            source.raw_text != self.source_text
            or source.normalized_text != self.normalized_text
            or source.source_type is not self.evidence_source
        ):
            raise BuyerNeedValidationError("buyer need fields must preserve source text evidence")
        source_product = source.source_reference.product_identity
        if (
            source_product is not None
            and source_product not in self.product_context.product_identities
        ):
            raise BuyerNeedValidationError("buyer need product context omits evidence ASIN")
        _text(self.taxonomy_version, "BuyerNeedEvidence.taxonomy_version")
        _text(self.ruleset_version, "BuyerNeedEvidence.ruleset_version")
        if self.confidence.ruleset_version != self.ruleset_version:
            raise BuyerNeedValidationError("buyer need confidence ruleset mismatch")
        _optional_text(self.taxonomy_need_id, "BuyerNeedEvidence.taxonomy_need_id")
        _optional_text(self.extraction_rule_id, "BuyerNeedEvidence.extraction_rule_id")
        if self.status is BuyerNeedCandidateStatus.UNKNOWN:
            if (
                self.need_type is not BuyerNeedType.UNKNOWN
                or self.need_label != "UNKNOWN"
                or self.confidence.level is not BuyerNeedConfidenceLevel.UNKNOWN
                or self.taxonomy_need_id is not None
                or self.extraction_rule_id is not None
                or not diagnostics
            ):
                raise BuyerNeedValidationError(
                    "UNKNOWN candidate cannot publish an inferred need and requires diagnostics"
                )
        else:
            if (
                self.need_type is BuyerNeedType.UNKNOWN
                or self.confidence.level is BuyerNeedConfidenceLevel.UNKNOWN
                or self.taxonomy_need_id is None
                or self.extraction_rule_id is None
            ):
                raise BuyerNeedValidationError(
                    "identified candidate requires taxonomy, rule, type, and known confidence"
                )
        object.__setattr__(self, "source_evidence", tuple(evidence))
        object.__setattr__(
            self,
            "diagnostics",
            tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        )
        if self.need_id != _identity("buyer-need", self, "need_id"):
            raise BuyerNeedValidationError("need_id does not match Buyer Need content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_taxonomy(
        self,
        registry: BuyerNeedTaxonomyRegistry,
    ) -> Self:
        if not isinstance(registry, BuyerNeedTaxonomyRegistry):
            raise BuyerNeedValidationError("taxonomy validation requires a registry")
        if self.taxonomy_version != registry.taxonomy_version:
            raise BuyerNeedValidationError("buyer need taxonomy version mismatch")
        if self.status is BuyerNeedCandidateStatus.UNKNOWN:
            return self.validate()
        entry = next(
            (
                item
                for item in registry.entries
                if item.taxonomy_need_id == self.taxonomy_need_id
            ),
            None,
        )
        if entry is None:
            raise BuyerNeedValidationError("buyer need taxonomy entry is absent")
        if (
            entry.need_type is not self.need_type
            or self.evidence_source not in entry.applicable_source_types
        ):
            raise BuyerNeedValidationError("buyer need taxonomy boundary mismatch")
        span = self.source_evidence[0].span
        if not any(
            re.fullmatch(pattern, span.matched_text, flags=re.IGNORECASE)
            for pattern in entry.regex_patterns
        ):
            raise BuyerNeedValidationError("buyer need evidence span does not replay its rule")
        expected_label = (
            entry.canonical_label
            if entry.label_strategy is BuyerNeedLabelStrategy.CANONICAL
            else normalize_keyword_text(span.matched_text)
        )
        if self.need_label != expected_label:
            raise BuyerNeedValidationError("buyer need label does not match taxonomy strategy")
        expected_rule_id = deterministic_id(
            "buyer-need-rule",
            {
                "ruleset_version": self.ruleset_version,
                "taxonomy_version": self.taxonomy_version,
                "taxonomy_need_id": entry.taxonomy_need_id,
            },
        )
        if self.extraction_rule_id != expected_rule_id:
            raise BuyerNeedValidationError("buyer need extraction rule id mismatch")
        return self.validate()


# Candidate and evidence intentionally share one canonical contract rather than
# creating duplicate semantic representations.
BuyerNeedCandidate = BuyerNeedEvidence


def build_source_reference(
    *,
    reference_type: BuyerNeedSourceReferenceType,
    reference_id: str,
    canonical_observation_id: str | None = None,
    product_identity: ProductIdentity | None = None,
    keyword_identity: KeywordIdentity | None = None,
    provenance: Provenance | None = None,
    product_lineage: LineageReference | None = None,
    demand_lineage: DemandLineageReference | None = None,
) -> BuyerNeedSourceReference:
    payload = {
        "reference_type": reference_type,
        "reference_id": reference_id,
        "canonical_observation_id": canonical_observation_id,
        "product_identity": product_identity,
        "keyword_identity": keyword_identity,
        "provenance": provenance,
        "product_lineage": product_lineage,
        "demand_lineage": demand_lineage,
    }
    return BuyerNeedSourceReference(
        source_reference_id=deterministic_id("buyer-need-source-reference", payload),
        **payload,
    )


def build_text_evidence(
    *,
    raw_text: str,
    source_type: BuyerNeedTextSourceType,
    source_reference: BuyerNeedSourceReference,
    span: BuyerNeedTextSpan | None = None,
) -> BuyerNeedTextEvidence:
    _text(raw_text, "build_text_evidence.raw_text")
    selected_span = span or BuyerNeedTextSpan(
        start=0,
        end=len(raw_text),
        matched_text=raw_text,
    )
    payload = {
        "raw_text": raw_text,
        "normalized_text": normalize_keyword_text(raw_text),
        "source_type": source_type,
        "source_reference": source_reference,
        "span": selected_span,
    }
    return BuyerNeedTextEvidence(
        text_id=deterministic_id("buyer-need-text", payload),
        **payload,
    )


def build_search_term_text_evidence(
    keyword_identity: KeywordIdentity,
    *,
    demand_lineage: DemandLineageReference | None = None,
) -> BuyerNeedTextEvidence:
    if not isinstance(keyword_identity, KeywordIdentity):
        raise BuyerNeedValidationError("search term evidence requires KeywordIdentity")
    reference = build_source_reference(
        reference_type=BuyerNeedSourceReferenceType.KEYWORD_IDENTITY,
        reference_id=keyword_identity.keyword_id,
        keyword_identity=keyword_identity,
        demand_lineage=demand_lineage,
    )
    return build_text_evidence(
        raw_text=keyword_identity.raw_text,
        source_type=BuyerNeedTextSourceType.SEARCH_TERM,
        source_reference=reference,
    )


def build_review_text_evidence(
    observation: ReviewObservation,
    *,
    product_lineage: LineageReference | None = None,
) -> BuyerNeedTextEvidence:
    if not isinstance(observation, ReviewObservation):
        raise BuyerNeedValidationError("review text evidence requires ReviewObservation")
    if (
        observation.body.presence_status is not PresenceStatus.PRESENT
        or type(observation.body.raw_value) is not str
        or not observation.body.raw_value.strip()
    ):
        raise BuyerNeedValidationError("review body must contain present text")
    reference = build_source_reference(
        reference_type=BuyerNeedSourceReferenceType.REVIEW_OBSERVATION,
        reference_id=observation.review_observation_id,
        canonical_observation_id=observation.observation_id,
        product_identity=observation.product,
        provenance=observation.provenance,
        product_lineage=product_lineage,
    )
    return build_text_evidence(
        raw_text=observation.body.raw_value,
        source_type=BuyerNeedTextSourceType.REVIEW,
        source_reference=reference,
    )


def unknown_product_context() -> BuyerNeedProductContext:
    return BuyerNeedProductContext(
        status=BuyerNeedContextStatus.UNKNOWN,
        product_identities=(),
        attribute_profile_ids=(),
        product_intelligence_snapshot_ids=(),
    )


def product_context_from_identity(
    product_identity: ProductIdentity,
    *,
    attribute_profile_ids: Sequence[str] = (),
    product_intelligence_snapshot_ids: Sequence[str] = (),
) -> BuyerNeedProductContext:
    if not isinstance(product_identity, ProductIdentity):
        raise BuyerNeedValidationError("product context requires ProductIdentity")
    return BuyerNeedProductContext(
        status=BuyerNeedContextStatus.KNOWN,
        product_identities=(product_identity,),
        attribute_profile_ids=tuple(attribute_profile_ids),
        product_intelligence_snapshot_ids=tuple(product_intelligence_snapshot_ids),
    )


def unknown_category_context() -> BuyerNeedCategoryContext:
    return BuyerNeedCategoryContext(
        status=BuyerNeedContextStatus.UNKNOWN,
        category_scope=None,
        category_map_id=None,
        category_label=None,
    )


def category_context_from_map(
    snapshot: CategoryProductMapSnapshot,
    *,
    category_label: str | None = None,
) -> BuyerNeedCategoryContext:
    if not isinstance(snapshot, CategoryProductMapSnapshot):
        raise BuyerNeedValidationError(
            "category context requires CategoryProductMapSnapshot"
        )
    return BuyerNeedCategoryContext(
        status=BuyerNeedContextStatus.KNOWN,
        category_scope=snapshot.category_scope,
        category_map_id=snapshot.map_id,
        category_label=category_label,
    )


__all__ = (
    "BUYER_NEED_CONTRACT_VERSION",
    "BUYER_NEED_TAXONOMY_VERSION",
    "BUYER_NEED_RULESET_VERSION",
    "BuyerNeedType",
    "BuyerNeedTextSourceType",
    "BuyerNeedSourceReferenceType",
    "BuyerNeedConfidenceLevel",
    "BuyerNeedCandidateStatus",
    "BuyerNeedContextStatus",
    "BuyerNeedMatchStrength",
    "BuyerNeedLabelStrategy",
    "BuyerNeedEvidenceRequirement",
    "BuyerNeedTextSpan",
    "BuyerNeedSourceReference",
    "BuyerNeedTextEvidence",
    "BuyerNeedProductContext",
    "BuyerNeedCategoryContext",
    "BuyerNeedConfidence",
    "BuyerNeedDiagnostic",
    "BuyerNeedTaxonomyEntry",
    "BuyerNeedTaxonomyRegistry",
    "BuyerNeedEvidence",
    "BuyerNeedCandidate",
    "build_source_reference",
    "build_text_evidence",
    "build_search_term_text_evidence",
    "build_review_text_evidence",
    "unknown_product_context",
    "product_context_from_identity",
    "unknown_category_context",
    "category_context_from_map",
)
