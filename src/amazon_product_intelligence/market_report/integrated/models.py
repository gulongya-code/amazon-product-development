"""Strict aggregate contract for Route-aware Market Intelligence reports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json, deterministic_id


INTEGRATED_MARKET_REPORT_CONTRACT_VERSION = (
    "market-report-v0.2-route-intelligence-v1.0"
)
BUSINESS_VALUE_REVIEW_QUESTIONS = (
    "Does the Route breakdown represent real purchase/product alternatives?",
    "Does the report show meaningful differences between Routes?",
    "Can the operator identify at least one Route worth deeper research?",
    "Can the operator identify at least one Route that appears less attractive?",
    "Are the stated reasons supported by report data?",
    "Are important uncertainty/missing-data limitations visible?",
    "Does the report reveal something materially more useful than reviewing the raw listing table alone?",
    "Would an Amazon operator use this report to decide what to investigate next?",
)


def _json_copy(value: Any) -> Any:
    return json.loads(canonical_json(value))


@dataclass(frozen=True, slots=True, kw_only=True)
class IntegratedMarketReport:
    report_id: str
    semantic_fingerprint: str
    generated_at: str
    category: str
    marketplace: str
    source_lineage: Mapping[str, Any]
    market_overview: Mapping[str, Any]
    route_landscape: tuple[Mapping[str, Any], ...]
    route_comparison: tuple[Mapping[str, Any], ...]
    buyer_needs: Mapping[str, Any]
    competition: Mapping[str, Any]
    opportunity: Mapping[str, Any]
    risks_unknowns: tuple[Mapping[str, Any], ...]
    business_value_review: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]
    contract_version: str = INTEGRATED_MARKET_REPORT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != INTEGRATED_MARKET_REPORT_CONTRACT_VERSION:
            raise ValueError("unsupported integrated Market Report contract")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise ValueError("marketplace must be uppercase text")
        if not self.category.strip():
            raise ValueError("category must be non-empty text")
        route_rows = tuple(_json_copy(item) for item in self.route_landscape)
        route_ids = [str(item.get("route_id") or "") for item in route_rows]
        if not route_rows or any(not item for item in route_ids):
            raise ValueError("route landscape must contain identified Routes")
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route landscape contains duplicate Route identities")
        review = tuple(_json_copy(item) for item in self.business_value_review)
        if tuple(item.get("question") for item in review) != BUSINESS_VALUE_REVIEW_QUESTIONS:
            raise ValueError("business value review questions changed")
        if any(item.get("human_verdict") is not None or item.get("notes") is not None for item in review):
            raise ValueError("business value review fields must remain blank")
        overview = _json_copy(self.market_overview)
        counts = overview.get("coverage_counts", {})
        required_counts = {
            "accepted", "assigned", "unclassified", "review_required",
        }
        if set(counts) < required_counts:
            raise ValueError("market overview coverage counts are incomplete")
        if counts["accepted"] != (
            counts["assigned"] + counts["unclassified"] + counts["review_required"]
        ):
            raise ValueError("market overview coverage counts do not reconcile")
        if counts["assigned"] != sum(int(item["products"]) for item in route_rows):
            raise ValueError("Route member counts do not reconcile to assigned listings")
        required_lineage = {
            "canonical_bundle_fingerprints",
            "route_input_package_id",
            "governed_dataset_id",
            "semantic_result_id",
            "route_result_id",
            "competition_snapshot_id",
            "opportunity_snapshot_id",
        }
        lineage = _json_copy(self.source_lineage)
        if set(lineage) < required_lineage:
            raise ValueError("source lineage is incomplete")
        limitations = tuple(sorted(set(self.limitations)))
        if any(not isinstance(item, str) or not item.strip() for item in limitations):
            raise ValueError("limitations must contain non-empty text")
        object.__setattr__(self, "source_lineage", lineage)
        object.__setattr__(self, "market_overview", overview)
        object.__setattr__(self, "route_landscape", route_rows)
        object.__setattr__(
            self, "route_comparison", tuple(_json_copy(item) for item in self.route_comparison)
        )
        object.__setattr__(self, "buyer_needs", _json_copy(self.buyer_needs))
        object.__setattr__(self, "competition", _json_copy(self.competition))
        object.__setattr__(self, "opportunity", _json_copy(self.opportunity))
        object.__setattr__(
            self, "risks_unknowns", tuple(_json_copy(item) for item in self.risks_unknowns)
        )
        object.__setattr__(self, "business_value_review", review)
        object.__setattr__(self, "limitations", limitations)
        expected_fingerprint = sha256(
            canonical_json(self.semantic_dict()).encode("utf-8")
        ).hexdigest()
        if self.semantic_fingerprint != expected_fingerprint:
            raise ValueError("integrated Market Report fingerprint mismatch")
        expected_report_id = deterministic_id(
            "integrated-market-report",
            {
                "semantic_fingerprint": expected_fingerprint,
                "generated_at": self.generated_at,
            },
        )
        if self.report_id != expected_report_id:
            raise ValueError("integrated Market Report ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "generated_at": self.generated_at,
            "category": self.category,
            "marketplace": self.marketplace,
            "source_lineage": _json_copy(self.source_lineage),
            "market_overview": _json_copy(self.market_overview),
            "route_landscape": _json_copy(self.route_landscape),
            "route_comparison": _json_copy(self.route_comparison),
            "buyer_needs": _json_copy(self.buyer_needs),
            "competition": _json_copy(self.competition),
            "opportunity": _json_copy(self.opportunity),
            "risks_unknowns": _json_copy(self.risks_unknowns),
            "business_value_review": _json_copy(self.business_value_review),
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            **self.semantic_dict(),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":") if indent is None else None,
            indent=indent,
        )


def build_integrated_market_report(**content: Any) -> IntegratedMarketReport:
    material = {
        "contract_version": INTEGRATED_MARKET_REPORT_CONTRACT_VERSION,
        **content,
    }
    placeholder = IntegratedMarketReport.__new__(IntegratedMarketReport)
    for name, value in material.items():
        object.__setattr__(placeholder, name, value)
    semantic = placeholder.semantic_dict()
    fingerprint = sha256(canonical_json(semantic).encode("utf-8")).hexdigest()
    report_id = deterministic_id(
        "integrated-market-report",
        {"semantic_fingerprint": fingerprint, "generated_at": content["generated_at"]},
    )
    return IntegratedMarketReport(
        report_id=report_id,
        semantic_fingerprint=fingerprint,
        **material,
    )


__all__ = (
    "BUSINESS_VALUE_REVIEW_QUESTIONS",
    "INTEGRATED_MARKET_REPORT_CONTRACT_VERSION",
    "IntegratedMarketReport",
    "build_integrated_market_report",
)
