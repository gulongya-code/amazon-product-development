"""TASK-SP-032F independent temporal holdout with frozen V0.2 rules."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
import time
from typing import Any

from amazon_product_intelligence.buyer_need_analysis import (
    BUYER_NEED_INTENT_RULESET_VERSION,
    BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2,
    BUYER_NEED_RULESET_VERSION_V0_2,
    BUYER_NEED_TAXONOMY_VERSION_V0_2,
    BUYER_NEED_TAXONOMY_V0_2,
)
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.semantic_clustering import (
    SEMANTIC_CLUSTERING_CONTRACT_VERSION,
    SEMANTIC_CLUSTERING_RULESET_VERSION,
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
)

from .capture import XiYouLiveCaptureClient
from .holdout_v0_1 import (
    HOLDOUT_ASIN_COUNT,
    HOLDOUT_MARKETPLACE,
    HOLDOUT_QUERY,
    HOLDOUT_REVERSE_PAGE_SIZE,
    SP032B_PILOT_ASINS,
    _atomic_json_write,
    _annotations_by_term,
    _capture_record,
    _parent_asin,
    _response_rows,
    _response_total,
    _utc_now,
    analyze_holdout_checkpoint,
    load_json_object,
)
from .runner import CreditApprovalRequired


TEMPORAL_HOLDOUT_CONTRACT_VERSION = "organic-buyer-need-temporal-holdout-v0.1"
TEMPORAL_PREVIOUS_PERIOD = "last7days"
TEMPORAL_PERIOD = "2026-07"
TEMPORAL_START_MONTH = "2026-07"
TEMPORAL_END_MONTH = "2026-07"
TEMPORAL_COHORT_PAGE_SIZE = 300
TEMPORAL_CREDIT_GATE = 150
TEMPORAL_COHORT_OPERATION = "keyword_asin_analysis_monthly"
TEMPORAL_REVERSE_OPERATION = "asin_keywords_monthly"
TEMPORAL_RATE_LIMIT_SECONDS = 1.5

PROVIDER_CONTRACT_REFERENCES = {
    "api_overview": "https://openapi-doc.xydc.com/",
    "previous_reverse_contract": "https://openapi-doc.xydc.com/331502595e0",
    "monthly_reverse_contract": "https://openapi-doc.xydc.com/331594504e0",
    "monthly_cohort_contract": "https://openapi-doc.xydc.com/451506681e0",
}


class InsufficientIndependentAsins(RuntimeError):
    """Raised before reverse calls when the independent cohort cannot reach 100."""


@dataclass(frozen=True, slots=True)
class TemporalCreditPlan:
    cohort_credits: int = 15
    reverse_credits: int = HOLDOUT_ASIN_COUNT
    gate_credits: int = TEMPORAL_CREDIT_GATE

    @property
    def estimated_total_credits(self) -> int:
        return self.cohort_credits + self.reverse_credits

    def enforce(self) -> None:
        if self.estimated_total_credits > self.gate_credits:
            raise CreditApprovalRequired(
                "CREDIT APPROVAL REQUIRED: estimated total "
                f"{self.estimated_total_credits} > gate {self.gate_credits}"
            )

    def to_dict(self) -> dict[str, int]:
        return {
            "cohort_credits": self.cohort_credits,
            "reverse_credits": self.reverse_credits,
            "estimated_total_credits": self.estimated_total_credits,
            "gate_credits": self.gate_credits,
        }


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen_rule_fingerprints() -> dict[str, Any]:
    """Fingerprint executable registries and their source files without mutation."""

    package_root = Path(__file__).resolve().parents[1]
    registries = {
        "buyer_need_taxonomy_v0_2": BUYER_NEED_TAXONOMY_V0_2,
        "buyer_need_intent_registry_v0_2": BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2,
        "semantic_normalization_registry_v0_1": SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
    }
    registry_rows = {}
    for name, registry in registries.items():
        payload = registry.to_dict()
        registry_rows[name] = {
            "identity": payload["registry_id"],
            "sha256": sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        }
    source_files = (
        "buyer_need_analysis/taxonomy_v0_2.py",
        "buyer_need_analysis/intent_v0_2.py",
        "buyer_need_analysis/builder_v0_2.py",
        "semantic_clustering/rules.py",
        "semantic_clustering/builder_v0_1.py",
    )
    return {
        "versions": {
            "buyer_need_taxonomy": BUYER_NEED_TAXONOMY_VERSION_V0_2,
            "buyer_need_rules": BUYER_NEED_RULESET_VERSION_V0_2,
            "buyer_need_intent_rules": BUYER_NEED_INTENT_RULESET_VERSION,
            "semantic_clustering_contract": SEMANTIC_CLUSTERING_CONTRACT_VERSION,
            "semantic_clustering_rules": SEMANTIC_CLUSTERING_RULESET_VERSION,
        },
        "registries": registry_rows,
        "source_files": {
            relative: _file_sha256(package_root / relative) for relative in source_files
        },
    }


def _historical_asins(sp032e_checkpoint: Mapping[str, Any]) -> frozenset[str]:
    cohort = sp032e_checkpoint.get("cohort")
    if not isinstance(cohort, Sequence) or isinstance(cohort, (str, bytes)):
        raise ValueError("SP-032E checkpoint has no cohort")
    sp032e = {
        str(item["asin"]).strip().upper()
        for item in cohort
        if isinstance(item, Mapping) and isinstance(item.get("asin"), str)
    }
    if len(sp032e) != HOLDOUT_ASIN_COUNT:
        raise ValueError("SP-032E checkpoint must contain exactly 100 ASINs")
    overlap = sp032e & SP032B_PILOT_ASINS
    if overlap:
        raise ValueError("historical SP-032B and SP-032E cohorts unexpectedly overlap")
    return frozenset(SP032B_PILOT_ASINS | sp032e)


def select_temporal_cohort(
    payload: Mapping[str, Any],
    *,
    historical_asins: frozenset[str],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Select first 100 unique valid rows after the frozen 120-ASIN exclusion."""

    selected: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    observed: set[str] = set()
    for response_rank, row in enumerate(_response_rows(payload), 1):
        raw_asin = row.get("asin")
        asin = raw_asin.strip().upper() if isinstance(raw_asin, str) else None
        reason = None
        if asin is None or len(asin) != 10 or not asin.isalnum():
            reason = "INVALID_OR_MISSING_ASIN"
        elif asin in observed:
            reason = "DUPLICATE_PROVIDER_ROW"
        elif asin in SP032B_PILOT_ASINS:
            reason = "EXCLUDED_SP032B_ASIN"
        elif asin in historical_asins:
            reason = "EXCLUDED_SP032E_ASIN"
        if reason is not None:
            exclusions.append(
                {
                    "provider_response_rank": response_rank,
                    "asin": asin,
                    "exclusion_reason": reason,
                }
            )
            if asin is not None:
                observed.add(asin)
            continue
        observed.add(asin)
        selected.append(
            {
                "asin": asin,
                "parent_asin": _parent_asin(row),
                "product_grain": "CHILD_ASIN",
                "cohort_query": HOLDOUT_QUERY,
                "marketplace": HOLDOUT_MARKETPLACE,
                "period": TEMPORAL_PERIOD,
                "provider_page": 1,
                "provider_response_rank": response_rank,
                "provider_total": _response_total(payload),
                "selection_reason": (
                    "First unique valid provider row after frozen SP-032B and SP-032E exclusions"
                ),
                "provider_row": dict(row),
            }
        )
        if len(selected) == HOLDOUT_ASIN_COUNT:
            break
    return tuple(selected), tuple(exclusions)


class OrganicTemporalHoldoutLiveCaptureV0_1:
    """Credit-gated, checkpointed monthly capture for a new 100-ASIN cohort."""

    def __init__(
        self,
        capture_client: XiYouLiveCaptureClient,
        *,
        baseline_commit: str,
        checkpoint_path: str | Path,
        sp032e_checkpoint: Mapping[str, Any],
        credit_gate: int = TEMPORAL_CREDIT_GATE,
        min_request_interval_seconds: float = TEMPORAL_RATE_LIMIT_SECONDS,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        self.capture_client = capture_client
        self.baseline_commit = baseline_commit
        self.checkpoint_path = Path(checkpoint_path)
        self.sp032e_checkpoint = sp032e_checkpoint
        self.historical_asins = _historical_asins(sp032e_checkpoint)
        self.credit_plan = TemporalCreditPlan(gate_credits=credit_gate)
        self.min_request_interval_seconds = max(0.0, min_request_interval_seconds)
        self.progress = progress
        self._last_request_at: float | None = None

    def _capture(self, **kwargs: Any):
        if self._last_request_at is not None:
            remaining = self.min_request_interval_seconds - (
                time.monotonic() - self._last_request_at
            )
            if remaining > 0:
                time.sleep(remaining)
        capture = self.capture_client.capture(**kwargs)
        self._last_request_at = time.monotonic()
        return capture

    def run(self) -> dict[str, Any]:
        self.credit_plan.enforce()
        checkpoint = self._load_or_initialize()
        if checkpoint.get("status") == "COMPLETE":
            return checkpoint

        if checkpoint.get("cohort_capture") is None:
            parameters = {
                "keyword": HOLDOUT_QUERY,
                "searchTerm": HOLDOUT_QUERY,
                "country": HOLDOUT_MARKETPLACE,
                "page": 1,
                "pageSize": TEMPORAL_COHORT_PAGE_SIZE,
                "startMonth": TEMPORAL_START_MONTH,
                "endMonth": TEMPORAL_END_MONTH,
                "sort": {"field": "traffic", "order": "desc"},
            }
            capture = self._capture(
                operation=TEMPORAL_COHORT_OPERATION,
                canonical_field="relationship.keyword_to_product",
                parameters=parameters,
            )
            checkpoint["cohort_capture"] = _capture_record(
                capture, canonical_field="relationship.keyword_to_product"
            )
            selected, exclusions = select_temporal_cohort(
                capture.payload, historical_asins=self.historical_asins
            )
            checkpoint["cohort"] = list(selected)
            checkpoint["cohort_exclusions"] = list(exclusions)
            self._save(checkpoint)
            if len(selected) != HOLDOUT_ASIN_COUNT:
                checkpoint["status"] = "BLOCKED_INSUFFICIENT_INDEPENDENT_ASINS"
                self._save(checkpoint)
                raise InsufficientIndependentAsins(
                    f"provider yielded {len(selected)} independent ASINs after 120 exclusions"
                )

        asins = tuple(str(item["asin"]) for item in checkpoint["cohort"])
        captured_asins = {
            str(item["source_asin"]) for item in checkpoint["reverse_captures"]
        }
        for index, asin in enumerate(asins, 1):
            if asin in captured_asins:
                continue
            parameters = {
                "asin": asin,
                "country": HOLDOUT_MARKETPLACE,
                "page": 1,
                "pageSize": HOLDOUT_REVERSE_PAGE_SIZE,
                "startMonth": TEMPORAL_START_MONTH,
                "endMonth": TEMPORAL_END_MONTH,
                "sort": {"field": "traffic", "order": "desc"},
            }
            capture = self._capture(
                operation=TEMPORAL_REVERSE_OPERATION,
                canonical_field="relationship.product_to_keyword",
                parameters=parameters,
            )
            record = _capture_record(
                capture, canonical_field="relationship.product_to_keyword"
            )
            record["source_asin"] = asin
            checkpoint["reverse_captures"].append(record)
            self._save(checkpoint)
            if self.progress is not None:
                self.progress(index, len(asins))

        checkpoint["fingerprints_end"] = frozen_rule_fingerprints()
        checkpoint["fingerprints_identical"] = (
            checkpoint["fingerprints_start"] == checkpoint["fingerprints_end"]
        )
        if not checkpoint["fingerprints_identical"]:
            raise RuntimeError("frozen taxonomy/rules fingerprints changed during capture")
        checkpoint["status"] = "COMPLETE"
        checkpoint["completed_at"] = _utc_now()
        self._save(checkpoint)
        return checkpoint

    def _load_or_initialize(self) -> dict[str, Any]:
        if self.checkpoint_path.exists():
            checkpoint = load_json_object(self.checkpoint_path)
            expected = {
                "contract_version": TEMPORAL_HOLDOUT_CONTRACT_VERSION,
                "baseline_commit": self.baseline_commit,
                "previous_period": TEMPORAL_PREVIOUS_PERIOD,
                "period": TEMPORAL_PERIOD,
            }
            for key, value in expected.items():
                if checkpoint.get(key) != value:
                    raise ValueError(f"checkpoint {key} does not match requested run")
            if checkpoint.get("credit_plan") != self.credit_plan.to_dict():
                raise ValueError("checkpoint credit plan does not match requested run")
            return checkpoint
        return {
            "contract_version": TEMPORAL_HOLDOUT_CONTRACT_VERSION,
            "baseline_commit": self.baseline_commit,
            "retrieved_at": self.capture_client.retrieved_at,
            "created_at": _utc_now(),
            "completed_at": None,
            "status": "IN_PROGRESS",
            "category_scope": "Amazon US > Pet Supplies > Dog Travel Water Bottles",
            "marketplace": HOLDOUT_MARKETPLACE,
            "cohort_query": HOLDOUT_QUERY,
            "previous_period": TEMPORAL_PREVIOUS_PERIOD,
            "period": TEMPORAL_PERIOD,
            "period_semantics": "XiYou explicit monthly window, 2026-07 through 2026-07",
            "provider_contract_references": PROVIDER_CONTRACT_REFERENCES,
            "credit_plan": self.credit_plan.to_dict(),
            "pilot_excluded_asins": sorted(SP032B_PILOT_ASINS),
            "historical_excluded_asins": sorted(self.historical_asins),
            "fingerprints_start": frozen_rule_fingerprints(),
            "fingerprints_end": None,
            "fingerprints_identical": None,
            "cohort_capture": None,
            "cohort": [],
            "cohort_exclusions": [],
            "reverse_captures": [],
            "enrichment_capture": None,
        }

    def _save(self, checkpoint: Mapping[str, Any]) -> None:
        _atomic_json_write(self.checkpoint_path, checkpoint)


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except Exception:
        return None


def _percentage_points(current: Any, previous: Any) -> str | None:
    current_value = _decimal(current)
    previous_value = _decimal(previous)
    if current_value is None or previous_value is None:
        return None
    return f"{(current_value - previous_value) * Decimal(100):.2f}"


def _standard_replication(current: Mapping[str, Any], previous: Mapping[str, Any]) -> str:
    if int(current.get("relation_count", 0)) == 0:
        return "FAILED_TO_REPLICATE"
    current_precision = _decimal(current.get("precision"))
    previous_precision = _decimal(previous.get("precision"))
    if current_precision is None or previous_precision is None:
        return "VARIABLE"
    if (
        current_precision >= Decimal("0.90")
        and previous_precision >= Decimal("0.90")
        and abs(current_precision - previous_precision) <= Decimal("0.10")
    ):
        return "STABLE"
    return "VARIABLE"


def merge_temporal_annotations(
    annotations: Mapping[str, Any] | None,
    reference_annotations: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Reuse exact-term SP-032E judgements, with explicit SP-032F overrides."""

    if annotations is None and reference_annotations is None:
        return None
    reference = _annotations_by_term(reference_annotations)
    current = _annotations_by_term(annotations)
    merged = {term: dict(review) for term, review in reference.items()}
    for term, review in current.items():
        merged.setdefault(term, {}).update(dict(review))
    return {"term_reviews": merged}


def _error_pattern_comparison(
    current: Mapping[str, Any], previous: Mapping[str, Any]
) -> dict[str, Any]:
    aliases = {
        "PRODUCT_OR_NON_NEED_MISROUTED": "NON_NEED_MISROUTED_AS_NEED",
        "NON_NEED_MISROUTED_AS_NEED": "NON_NEED_MISROUTED_AS_NEED",
    }

    def normalized_counts(source: Mapping[str, Any]) -> Counter[str]:
        counts: Counter[str] = Counter()
        raw = source.get("category_distribution", {})
        if isinstance(raw, Mapping):
            for label, count in raw.items():
                counts[aliases.get(str(label), str(label))] += int(count)
        return counts

    current_counts = normalized_counts(current)
    previous_counts = normalized_counts(previous)
    categories = (
        "NON_NEED_MISROUTED_AS_NEED",
        "EXISTING_TAXONOMY_GAP",
        "NEW_VALID_BUYER_NEED",
        "AMBIGUOUS",
        "OTHER",
    )
    rows = []
    for category in categories:
        previous_count = previous_counts[category]
        current_count = current_counts[category]
        rows.append(
            {
                "category": category,
                "sp032e_count": previous_count,
                "sp032f_count": current_count,
                "replication": (
                    "REPEATED_ERROR_PATTERN"
                    if previous_count > 0 and current_count > 0
                    else "SAMPLE_SPECIFIC"
                    if previous_count > 0 or current_count > 0
                    else "NOT_OBSERVED"
                ),
            }
        )
    return {
        "categories": rows,
        "major_patterns_reproduced": all(
            current_counts[label] > 0
            for label in (
                "NON_NEED_MISROUTED_AS_NEED",
                "EXISTING_TAXONOMY_GAP",
            )
        ),
    }


def _outdoor_expression_stats(relations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    patterns = {
        "portable": re.compile(r"\bportable\b", re.IGNORECASE),
        "travel": re.compile(r"\btravel(?:s|ed|ing|led|ling)?\b", re.IGNORECASE),
        "walking": re.compile(r"\bwalk(?:s|ed|ing)?\b", re.IGNORECASE),
        "hiking": re.compile(r"\bhik(?:e|es|ed|ing)\b", re.IGNORECASE),
    }
    rows = {}
    union_ids: set[str] = set()
    union_asins: set[str] = set()
    for label, pattern in patterns.items():
        matched = tuple(
            row for row in relations if pattern.search(str(row["normalized_keyword"]))
        )
        union_ids.update(str(row["discovery_id"]) for row in matched)
        union_asins.update(str(row["source_asin"]) for row in matched)
        rows[label] = {
            "relation_count": len(matched),
            "source_asin_count": len({str(row["source_asin"]) for row in matched}),
        }
    return {
        "expressions": rows,
        "union_relation_count": len(union_ids),
        "union_source_asin_count": len(union_asins),
    }


def analyze_temporal_holdout(
    checkpoint: Mapping[str, Any],
    *,
    annotations: Mapping[str, Any] | None,
    sp032e_analysis: Mapping[str, Any],
    reference_annotations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay frozen V0.2 and compare the result with TASK-SP-032E."""

    if checkpoint.get("status") != "COMPLETE":
        raise ValueError("temporal checkpoint must be complete before analysis")
    current_fingerprints = frozen_rule_fingerprints()
    if checkpoint.get("fingerprints_start") != current_fingerprints:
        raise RuntimeError("frozen rules differ from the capture-start fingerprint")
    merged_annotations = merge_temporal_annotations(annotations, reference_annotations)
    base = analyze_holdout_checkpoint(checkpoint, annotations=merged_annotations)
    historical = set(str(item) for item in checkpoint["historical_excluded_asins"])
    current_asins = {str(item["asin"]) for item in checkpoint["cohort"]}
    overlap = sorted(current_asins & historical)

    e_precision = sp032e_analysis["precision_audit"]["summary"]
    f_precision = base["precision_audit"]["summary"]
    e_need = e_precision["NEED_CANDIDATE"]["precision"]
    f_need = f_precision["NEED_CANDIDATE"]["precision"]
    e_non_need = e_precision["NON_NEED"]["precision"]
    f_non_need = f_precision["NON_NEED"]["precision"]
    comparison = {
        "raw_relations": {
            "sp032e": sp032e_analysis["corpus"]["raw_relation_count"],
            "sp032f": base["corpus"]["raw_relation_count"],
        },
        "unique_keywords": {
            "sp032e": sp032e_analysis["corpus"]["unique_keyword_count"],
            "sp032f": base["corpus"]["unique_keyword_count"],
        },
        "true_need_resolution_rate": {
            "sp032e": sp032e_analysis["buyer_need_resolution"]["true_need_resolution_rate"],
            "sp032f": base["buyer_need_resolution"]["true_need_resolution_rate"],
        },
        "unresolved_rate": {
            "sp032e": sp032e_analysis["buyer_need_resolution"]["buyer_need_unresolved_rate"],
            "sp032f": base["buyer_need_resolution"]["buyer_need_unresolved_rate"],
        },
        "need_precision": {
            "sp032e": e_need,
            "sp032f": f_need,
            "delta_percentage_points": _percentage_points(f_need, e_need),
        },
        "non_need_precision": {
            "sp032e": e_non_need,
            "sp032f": f_non_need,
            "delta_percentage_points": _percentage_points(f_non_need, e_non_need),
        },
        "intent_distribution": {
            "sp032e": sp032e_analysis["intent_distribution"],
            "sp032f": base["intent_distribution"],
        },
        "buyer_need_distribution": {
            "sp032e": {
                item["cluster_label"]: item["relation_count"]
                for item in sp032e_analysis["semantic_clusters"]
            },
            "sp032f": {
                item["cluster_label"]: item["relation_count"]
                for item in base["semantic_clusters"]
            },
        },
    }

    bowl_current = base["integrated_bowl_validation"]
    bowl_previous = sp032e_analysis["integrated_bowl_validation"]
    collapsible_current = base["collapsible_validation"]
    collapsible_previous = sp032e_analysis["collapsible_validation"]
    crate_current = base["crate_validation"]
    crate_previous = sp032e_analysis["crate_validation"]
    insulated_current = base["insulated_validation"]
    insulated_previous = sp032e_analysis["insulated_validation"]

    crate_precision = _decimal(crate_current.get("precision"))
    previous_crate_precision = _decimal(crate_previous.get("precision"))
    if crate_current["relation_count"] == 0:
        crate_decision = "EVIDENCE_WEAKENED"
    elif (
        crate_current["source_asin_count"] > crate_previous["source_asin_count"]
        and crate_precision is not None
        and previous_crate_precision is not None
        and crate_precision >= previous_crate_precision
    ):
        crate_decision = "PROMOTION_EVIDENCE_STRENGTHENED"
    else:
        crate_decision = "KEEP_EXPERIMENTAL"

    if insulated_current["exact_dog_related_relation_count"] == 0:
        insulated_decision = "EVIDENCE_WEAKENED"
    elif (
        insulated_current["source_asin_count"] > insulated_previous["source_asin_count"]
        and insulated_current["false_positive_count"]
        <= insulated_previous["false_positive_count"]
    ):
        insulated_decision = "PROMOTION_EVIDENCE_STRENGTHENED"
    else:
        insulated_decision = "KEEP_PROPOSAL"

    errors = _error_pattern_comparison(
        base["unknown_audit"], sp032e_analysis["unknown_audit"]
    )
    current_outdoor_stats = _outdoor_expression_stats(base["relations"])
    previous_outdoor_stats = _outdoor_expression_stats(sp032e_analysis["relations"])
    current_outdoor = base["outdoor_portability_bias"]
    previous_outdoor = sp032e_analysis["outdoor_portability_bias"]
    current_raw = int(current_outdoor["outdoor_raw_organic_relation_count"])
    previous_raw = int(previous_outdoor["outdoor_raw_organic_relation_count"])
    current_alignment = (
        Decimal(current_outdoor["outdoor_matched_need_relation_count"])
        / Decimal(current_raw)
        if current_raw
        else Decimal(0)
    )
    previous_alignment = (
        Decimal(previous_outdoor["outdoor_matched_need_relation_count"])
        / Decimal(previous_raw)
        if previous_raw
        else Decimal(0)
    )
    if current_alignment >= Decimal("0.95") and previous_alignment >= Decimal("0.95"):
        outdoor_decision = "DATA_DRIVEN_DOMINANCE"
    elif current_alignment < Decimal("0.75") and previous_alignment < Decimal("0.75"):
        outdoor_decision = "TAXONOMY_COVERAGE_BIAS"
    else:
        outdoor_decision = "MIXED"
    audit_complete = base["success_criteria"]["manual_audit_complete"]
    need_precision = _decimal(f_need)
    required_evidence = (
        audit_complete
        and len(current_asins) == HOLDOUT_ASIN_COUNT
        and not overlap
        and checkpoint["previous_period"] != checkpoint["period"]
        and checkpoint.get("fingerprints_identical") is True
    )
    validation_conditions = {
        "cohort_count_is_100": len(current_asins) == HOLDOUT_ASIN_COUNT,
        "historical_overlap_is_zero": not overlap,
        "different_explicit_period": checkpoint["previous_period"] != checkpoint["period"],
        "frozen_fingerprints_identical": checkpoint.get("fingerprints_identical") is True,
        "manual_audit_complete": audit_complete,
        "lineage_complete": base["success_criteria"]["lineage_complete"],
        "credit_gate_respected": (
            base["credit_audit"]["known_credits"]
            <= base["credit_audit"]["gate_credits"]
        ),
    }
    required_evidence = required_evidence and all(validation_conditions.values())
    if not required_evidence or need_precision is None:
        decision = "INSUFFICIENT_EVIDENCE"
    elif need_precision < Decimal("0.90") and errors["major_patterns_reproduced"]:
        decision = "SYSTEMATIC_GENERALIZATION_PROBLEM"
    elif need_precision >= Decimal("0.90") and not errors["major_patterns_reproduced"]:
        decision = "SAMPLE_OR_TEMPORAL_VARIANCE"
    else:
        decision = "MIXED"
    next_steps = {
        "SYSTEMATIC_GENERALIZATION_PROBLEM": "TASK-SP-032G Need Precision Error Analysis",
        "SAMPLE_OR_TEMPORAL_VARIANCE": (
            "Expand the Organic Discovery cohort while keeping Taxonomy v0.2 frozen."
        ),
        "MIXED": "Run Precision Error Analysis only on stably replicated error patterns.",
        "INSUFFICIENT_EVIDENCE": "Resolve the data or independent-cohort limitation first.",
    }

    payload = {
        "contract_version": TEMPORAL_HOLDOUT_CONTRACT_VERSION,
        "analysis_id": None,
        "baseline_commit": checkpoint["baseline_commit"],
        "category_scope": checkpoint["category_scope"],
        "marketplace": checkpoint["marketplace"],
        "temporal_window": {
            "previous_period": checkpoint["previous_period"],
            "new_period": checkpoint["period"],
            "period_semantics": checkpoint["period_semantics"],
            "provider_contract_references": checkpoint["provider_contract_references"],
            "selection_timing": (
                "The latest complete calendar month was selected before provider data capture."
            ),
        },
        "frozen_fingerprints": {
            "start": checkpoint["fingerprints_start"],
            "end": current_fingerprints,
            "identical": checkpoint["fingerprints_start"] == current_fingerprints,
        },
        "cohort": checkpoint["cohort"],
        "cohort_exclusions": checkpoint["cohort_exclusions"],
        "historical_asin_count": len(historical),
        "historical_overlap_count": len(overlap),
        "historical_overlap_asins": overlap,
        "cohort_provider_total": _response_total(checkpoint["cohort_capture"]["payload"]),
        "credit_audit": base["credit_audit"],
        "corpus": base["corpus"],
        "intent_distribution": base["intent_distribution"],
        "resolution_distribution": base["resolution_distribution"],
        "buyer_need_resolution": base["buyer_need_resolution"],
        "semantic_clusters": base["semantic_clusters"],
        "precision_audit": base["precision_audit"],
        "unknown_audit": base["unknown_audit"],
        "annotation_method": {
            "standard": "TASK-SP-032E exact-term human semantic adjudication",
            "exact_term_reference_reviews": len(_annotations_by_term(reference_annotations)),
            "sp032f_reviews_or_overrides": len(_annotations_by_term(annotations)),
            "merge_rule": "Exact normalized term; SP-032F explicit label overrides reference label.",
        },
        "comparison_sp032e_vs_sp032f": comparison,
        "integrated_bowl_replication": {
            "sp032e": bowl_previous,
            "sp032f": bowl_current,
            "decision": _standard_replication(bowl_current, bowl_previous),
        },
        "collapsible_replication": {
            "sp032e": collapsible_previous,
            "sp032f": collapsible_current,
            "decision": _standard_replication(collapsible_current, collapsible_previous),
        },
        "crate_replication": {
            "status": "EXPERIMENTAL",
            "sp032e": crate_previous,
            "sp032f": crate_current,
            "expression_diversity": len(set(crate_current.get("expressions", []))),
            "decision": crate_decision,
        },
        "insulated_replication": {
            "status": "PROPOSAL_ONLY",
            "sp032e": insulated_previous,
            "sp032f": insulated_current,
            "decision": insulated_decision,
        },
        "outdoor_portability_replication": {
            "sp032e": previous_outdoor,
            "sp032f": current_outdoor,
            "sp032e_expression_stats": previous_outdoor_stats,
            "sp032f_expression_stats": current_outdoor_stats,
            "sp032e_raw_to_matched_alignment": format(previous_alignment, "f"),
            "sp032f_raw_to_matched_alignment": format(current_alignment, "f"),
            "other_major_buyer_needs": base["semantic_clusters"][:10],
            "decision": outdoor_decision,
        },
        "error_pattern_replication": errors,
        "relations": base["relations"],
        "overfit_replication_decision": decision,
        "validation_conditions": validation_conditions,
        "next_step_unique_recommendation": next_steps[decision],
        "taxonomy_rules_modified": 0,
        "limitations": [
            "Only page 1 / top 20 monthly reverse keywords were captured per ASIN.",
            "ASIN coverage is cohort recurrence, not Demand Share.",
            "Provider traffic semantics remain provider-defined and uncalibrated.",
            "Parent ASIN remains UNKNOWN when omitted by the cohort response.",
            "Manual term review is not Amazon behavioral ground truth.",
            "The cohort and keyword corpus both change, so sample and temporal effects are not separately identified.",
        ],
    }
    identity = dict(payload)
    identity.pop("analysis_id")
    payload["analysis_id"] = deterministic_id(
        "organic-buyer-need-temporal-holdout-analysis", identity
    )
    return payload


__all__ = (
    "InsufficientIndependentAsins",
    "OrganicTemporalHoldoutLiveCaptureV0_1",
    "TEMPORAL_HOLDOUT_CONTRACT_VERSION",
    "TemporalCreditPlan",
    "analyze_temporal_holdout",
    "frozen_rule_fingerprints",
    "merge_temporal_annotations",
    "select_temporal_cohort",
)
