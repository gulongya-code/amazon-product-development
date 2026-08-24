from __future__ import annotations

import json
from pathlib import Path

import pytest

from amazon_product_intelligence.market_report.v0_2.models import (
    Availability,
    MarketSizeSection,
    PresenceStatus,
    ProductGrainV0_2,
    ScopeContext,
    TrueCompetitorSetSection,
)


FIXTURES = Path(__file__).parent / "fixtures" / "market_report_v0_2"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("name", "contract_type"),
    (
        ("sp039b_scope_child_asin.json", ScopeContext),
        ("sp039b_market_size_unavailable.json", MarketSizeSection),
        (
            "sp039b_true_competitor_review_required.json",
            TrueCompetitorSetSection,
        ),
    ),
)
def test_checked_in_sp039b_fixtures_strictly_round_trip(name, contract_type):
    payload = load_fixture(name)
    contract = contract_type.from_dict(payload)
    assert contract.to_dict() == payload


def test_scope_fixture_declares_child_grain_and_duplicate_control():
    scope = ScopeContext.from_dict(load_fixture("sp039b_scope_child_asin.json"))
    assert scope.product_grain is ProductGrainV0_2.CHILD_ASIN
    assert scope.unsafe_aggregate_guard is False
    assert scope.included_grain_entity_count == 2


def test_unavailable_market_size_fixture_never_encodes_missing_as_zero():
    section = MarketSizeSection.from_dict(
        load_fixture("sp039b_market_size_unavailable.json")
    )
    assert section.availability is Availability.UNAVAILABLE
    assert section.monthly_sales.value is None
    assert section.monthly_revenue.value is None
    assert section.monthly_sales.presence_status is PresenceStatus.MISSING
    assert section.monthly_revenue.presence_status is PresenceStatus.MISSING


def test_review_required_fixture_cannot_feed_aggregate_competitor_metrics():
    section = TrueCompetitorSetSection.from_dict(
        load_fixture("sp039b_true_competitor_review_required.json")
    )
    assert section.availability is Availability.PARTIAL
    assert section.review_required_count == 1
    assert section.unsafe_aggregate_guard is True
    assert section.included_cohort_reference_id is None
    assert section.included_denominator_reference_id is None


def test_fixture_payloads_do_not_contain_delivery_or_future_section_fields():
    forbidden = {
        "renderer",
        "pipeline",
        "xlsx",
        "markdown",
        "distributions",
        "competitor_details",
        "buyer_need_links",
        "product_directions",
        "competitor_shortlist",
        "executive_summary",
        "external_integrations",
    }
    for path in FIXTURES.glob("sp039b_*.json"):
        payload = json.dumps(load_fixture(path.name), sort_keys=True)
        assert not any(f'"{name}"' in payload for name in forbidden)
