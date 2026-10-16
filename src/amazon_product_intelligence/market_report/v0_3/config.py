"""Report-only display/analysis policy. Never passed to Semantic or Route engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from amazon_product_intelligence.contracts import canonical_json


@dataclass(frozen=True)
class ReportProfile:
    profile_id: str = "generic-operator-report-v0.3"
    category: str | None = None
    currency: str = "USD"
    price_boundaries: tuple[float, ...] = (10, 25, 50, 100)
    review_boundaries: tuple[int, ...] = (51, 201, 1001)
    low_review_max: int = 50
    new_product_days: tuple[int, ...] = (180, 365)
    top_n: int = 5
    minimum_route_coverage: float = 0.5
    minimum_sales_coverage: float = 0.8
    high_unresolved_exposure: float = 0.5
    growth_minimum_pairs: int = 3
    growth_near_total_decline: float = -0.99
    growth_maximum_prior_share: float = 0.5
    growth_maximum_leave_one_out_delta: float = 0.2
    family_rules: tuple[dict[str, Any], ...] = ()
    labels: dict[str, dict[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        from math import isfinite
        if self.currency != "USD":
            raise ValueError("current governed monetary input mapping supports USD only")
        for values in (self.price_boundaries, self.review_boundaries, self.new_product_days):
            if not values or any(isinstance(x, bool) or not isfinite(x) or x <= 0 for x in values):
                raise ValueError("band boundaries must be finite positive values")
            if tuple(sorted(set(values))) != tuple(values):
                raise ValueError("band boundaries must be strictly increasing")
        if any(type(x) is not int for x in (*self.review_boundaries, *self.new_product_days)):
            raise ValueError("review and age boundaries must be integers")
        if type(self.top_n) is not int or self.top_n < 5 or self.low_review_max < 0:
            raise ValueError("top_n must support Top 5 and low-review maximum must be nonnegative")
        if any(not 0 <= x <= 1 for x in (self.minimum_route_coverage, self.minimum_sales_coverage, self.high_unresolved_exposure)):
            raise ValueError("report readiness fractions must be in [0, 1]")
        if type(self.growth_minimum_pairs) is not int or self.growth_minimum_pairs < 3:
            raise ValueError("growth requires at least three pairs")
        if not (-1 < self.growth_near_total_decline < 0):
            raise ValueError("near-total decline must be between -1 and 0")
        if not 0 < self.growth_maximum_prior_share <= 1 or not 0 < self.growth_maximum_leave_one_out_delta <= 1:
            raise ValueError("growth influence limits must be in (0, 1]")
        for rule in self.family_rules:
            if set(rule) != {"dimension", "value", "family"} or not all(isinstance(x, str) and x for x in rule.values()):
                raise ValueError("family rules require dimension, exact value and family")

    def to_dict(self):
        from dataclasses import asdict
        return json.loads(canonical_json(asdict(self)))

    @property
    def fingerprint(self):
        return sha256(canonical_json(self.to_dict()).encode()).hexdigest()


def load_report_profile(path: Path) -> ReportProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("price_boundaries", "review_boundaries", "new_product_days", "family_rules"):
        if key in data:
            data[key] = tuple(data[key])
    return ReportProfile(**data)
