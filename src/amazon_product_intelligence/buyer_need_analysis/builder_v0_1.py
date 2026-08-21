"""Deterministic Buyer Need candidate builder V0.1."""

from __future__ import annotations

from dataclasses import dataclass
import re

from amazon_product_intelligence.contracts import Severity, deterministic_id
from amazon_product_intelligence.normalization import normalize_keyword_text

from .errors import BuyerNeedValidationError
from .models import (
    BUYER_NEED_RULESET_VERSION,
    BuyerNeedCandidate,
    BuyerNeedCandidateStatus,
    BuyerNeedCategoryContext,
    BuyerNeedConfidence,
    BuyerNeedConfidenceLevel,
    BuyerNeedDiagnostic,
    BuyerNeedEvidence,
    BuyerNeedLabelStrategy,
    BuyerNeedMatchStrength,
    BuyerNeedProductContext,
    BuyerNeedTaxonomyEntry,
    BuyerNeedTaxonomyRegistry,
    BuyerNeedTextEvidence,
    BuyerNeedTextSourceType,
    BuyerNeedTextSpan,
    BuyerNeedType,
    build_text_evidence,
    product_context_from_identity,
    unknown_category_context,
    unknown_product_context,
)
from .taxonomy import BUYER_NEED_TAXONOMY_V0_1


@dataclass(frozen=True)
class _RuleMatch:
    entry: BuyerNeedTaxonomyEntry
    label: str
    span: BuyerNeedTextSpan


class BuyerNeedCandidateBuilder:
    """Identify evidence-backed candidates without estimating demand size."""

    ruleset_version = BUYER_NEED_RULESET_VERSION

    def __init__(
        self,
        *,
        taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_1,
    ) -> None:
        if not isinstance(taxonomy, BuyerNeedTaxonomyRegistry):
            raise BuyerNeedValidationError("candidate builder requires BuyerNeedTaxonomyRegistry")
        self._taxonomy = taxonomy

    def build(
        self,
        text_evidence: BuyerNeedTextEvidence,
        *,
        product_context: BuyerNeedProductContext | None = None,
        category_context: BuyerNeedCategoryContext | None = None,
    ) -> tuple[BuyerNeedCandidate, ...]:
        if not isinstance(text_evidence, BuyerNeedTextEvidence):
            raise BuyerNeedValidationError("candidate builder input must be BuyerNeedTextEvidence")
        resolved_product_context = product_context or self._derive_product_context(text_evidence)
        resolved_category_context = category_context or unknown_category_context()
        if not isinstance(resolved_product_context, BuyerNeedProductContext):
            raise BuyerNeedValidationError("candidate product_context has a wrong type")
        if not isinstance(resolved_category_context, BuyerNeedCategoryContext):
            raise BuyerNeedValidationError("candidate category_context has a wrong type")

        matches = self._match(text_evidence)
        if not matches:
            return (
                self._unknown_candidate(
                    text_evidence=text_evidence,
                    product_context=resolved_product_context,
                    category_context=resolved_category_context,
                ),
            )
        candidates = tuple(
            self._candidate_from_match(
                text_evidence=text_evidence,
                match=match,
                product_context=resolved_product_context,
                category_context=resolved_category_context,
            )
            for match in matches
        )
        return tuple(sorted(candidates, key=lambda item: item.need_id))

    def _match(self, text_evidence: BuyerNeedTextEvidence) -> tuple[_RuleMatch, ...]:
        source_text = text_evidence.raw_text
        input_span = text_evidence.span
        fragment = source_text[input_span.start : input_span.end]
        selected: dict[tuple[BuyerNeedType, str, str], _RuleMatch] = {}
        for entry in self._taxonomy.entries:
            if text_evidence.source_type not in entry.applicable_source_types:
                continue
            for pattern in entry.regex_patterns:
                for result in re.finditer(pattern, fragment, flags=re.IGNORECASE):
                    start = input_span.start + result.start()
                    end = input_span.start + result.end()
                    matched_text = source_text[start:end]
                    label = (
                        entry.canonical_label
                        if entry.label_strategy is BuyerNeedLabelStrategy.CANONICAL
                        else normalize_keyword_text(matched_text)
                    )
                    candidate = _RuleMatch(
                        entry=entry,
                        label=label,
                        span=BuyerNeedTextSpan(
                            start=start,
                            end=end,
                            matched_text=matched_text,
                        ),
                    )
                    key = (entry.need_type, label, entry.taxonomy_need_id)
                    current = selected.get(key)
                    if current is None or (
                        candidate.span.start,
                        candidate.span.end,
                        candidate.span.matched_text,
                    ) < (
                        current.span.start,
                        current.span.end,
                        current.span.matched_text,
                    ):
                        selected[key] = candidate
        return tuple(
            sorted(
                selected.values(),
                key=lambda item: (
                    item.span.start,
                    item.span.end,
                    item.entry.need_type.value,
                    item.label,
                    item.entry.taxonomy_need_id,
                ),
            )
        )

    def _candidate_from_match(
        self,
        *,
        text_evidence: BuyerNeedTextEvidence,
        match: _RuleMatch,
        product_context: BuyerNeedProductContext,
        category_context: BuyerNeedCategoryContext,
    ) -> BuyerNeedEvidence:
        matched_evidence = build_text_evidence(
            raw_text=text_evidence.raw_text,
            source_type=text_evidence.source_type,
            source_reference=text_evidence.source_reference,
            span=match.span,
        )
        confidence = self._confidence(
            source_type=text_evidence.source_type,
            strength=match.entry.match_strength,
            taxonomy_need_id=match.entry.taxonomy_need_id,
        )
        extraction_rule_id = deterministic_id(
            "buyer-need-rule",
            {
                "ruleset_version": self.ruleset_version,
                "taxonomy_version": self._taxonomy.taxonomy_version,
                "taxonomy_need_id": match.entry.taxonomy_need_id,
            },
        )
        payload = {
            "need_type": match.entry.need_type,
            "need_label": match.label,
            "source_text": text_evidence.raw_text,
            "normalized_text": text_evidence.normalized_text,
            "evidence_source": text_evidence.source_type,
            "product_context": product_context,
            "category_context": category_context,
            "confidence": confidence,
            "status": BuyerNeedCandidateStatus.CANDIDATE,
            "source_evidence": (matched_evidence,),
            "diagnostics": (),
            "taxonomy_version": self._taxonomy.taxonomy_version,
            "ruleset_version": self.ruleset_version,
            "taxonomy_need_id": match.entry.taxonomy_need_id,
            "extraction_rule_id": extraction_rule_id,
        }
        return BuyerNeedEvidence(
            need_id=deterministic_id("buyer-need", payload),
            **payload,
        ).validate_against_taxonomy(self._taxonomy)

    def _unknown_candidate(
        self,
        *,
        text_evidence: BuyerNeedTextEvidence,
        product_context: BuyerNeedProductContext,
        category_context: BuyerNeedCategoryContext,
    ) -> BuyerNeedEvidence:
        diagnostic_payload = {
            "code": "NO_DETERMINISTIC_NEED_RULE_MATCH",
            "severity": Severity.INFO,
            "text_id": text_evidence.text_id,
            "message": (
                "No Buyer Need v0.1 taxonomy rule matched this text; UNKNOWN is preserved "
                "instead of guessing."
            ),
        }
        diagnostic = BuyerNeedDiagnostic(
            diagnostic_id=deterministic_id("buyer-need-diagnostic", diagnostic_payload),
            **diagnostic_payload,
        )
        payload = {
            "need_type": BuyerNeedType.UNKNOWN,
            "need_label": "UNKNOWN",
            "source_text": text_evidence.raw_text,
            "normalized_text": text_evidence.normalized_text,
            "evidence_source": text_evidence.source_type,
            "product_context": product_context,
            "category_context": category_context,
            "confidence": BuyerNeedConfidence(
                level=BuyerNeedConfidenceLevel.UNKNOWN,
                basis=(),
                ruleset_version=self.ruleset_version,
            ),
            "status": BuyerNeedCandidateStatus.UNKNOWN,
            "source_evidence": (text_evidence,),
            "diagnostics": (diagnostic,),
            "taxonomy_version": self._taxonomy.taxonomy_version,
            "ruleset_version": self.ruleset_version,
            "taxonomy_need_id": None,
            "extraction_rule_id": None,
        }
        return BuyerNeedEvidence(
            need_id=deterministic_id("buyer-need", payload),
            **payload,
        ).validate_against_taxonomy(self._taxonomy)

    def _confidence(
        self,
        *,
        source_type: BuyerNeedTextSourceType,
        strength: BuyerNeedMatchStrength,
        taxonomy_need_id: str,
    ) -> BuyerNeedConfidence:
        if strength is BuyerNeedMatchStrength.WEAK:
            level = BuyerNeedConfidenceLevel.LOW
        else:
            level = {
                BuyerNeedTextSourceType.SEARCH_TERM: BuyerNeedConfidenceLevel.HIGH,
                BuyerNeedTextSourceType.REVIEW: BuyerNeedConfidenceLevel.HIGH,
                BuyerNeedTextSourceType.TITLE: BuyerNeedConfidenceLevel.MEDIUM,
                BuyerNeedTextSourceType.BULLET: BuyerNeedConfidenceLevel.MEDIUM,
                BuyerNeedTextSourceType.DESCRIPTION: BuyerNeedConfidenceLevel.LOW,
            }[source_type]
        return BuyerNeedConfidence(
            level=level,
            basis=(
                f"source_type:{source_type.value}",
                f"match_strength:{strength.value}",
                f"taxonomy_need_id:{taxonomy_need_id}",
                "confidence_represents_classification_evidence_not_demand_size",
            ),
            ruleset_version=self.ruleset_version,
        )

    @staticmethod
    def _derive_product_context(
        text_evidence: BuyerNeedTextEvidence,
    ) -> BuyerNeedProductContext:
        product_identity = text_evidence.source_reference.product_identity
        if product_identity is None:
            return unknown_product_context()
        return product_context_from_identity(product_identity)


BuyerNeedCandidateBuilderV0_1 = BuyerNeedCandidateBuilder


__all__ = (
    "BuyerNeedCandidateBuilder",
    "BuyerNeedCandidateBuilderV0_1",
)
