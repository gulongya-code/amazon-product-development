from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from amazon_product_intelligence.connectors import TransportResponse
from amazon_product_intelligence.organic_keyword_discovery.capture import XiYouLiveCaptureClient
from amazon_product_intelligence.organic_keyword_discovery.holdout_v0_1 import (
    SP032B_PILOT_ASINS,
    analyze_holdout_checkpoint,
)
from amazon_product_intelligence.organic_keyword_discovery.runner import CreditApprovalRequired
from amazon_product_intelligence.organic_keyword_discovery.temporal_holdout_v0_1 import (
    OrganicTemporalHoldoutLiveCaptureV0_1,
    TemporalCreditPlan,
    frozen_rule_fingerprints,
    select_temporal_cohort,
)


def _rank() -> list[dict[str, object]]:
    return [
        {
            "page": 1,
            "pageRank": 3,
            "position": "or",
            "rankTime": "2026-07-31T00:00:00-07:00",
            "totalRank": 3,
        }
    ]


class _MonthlyTransport:
    def __init__(self, historical_e: tuple[str, ...], current: tuple[str, ...]) -> None:
        self.historical_e = historical_e
        self.current = current
        self.calls: list[tuple[str, object]] = []

    def execute(self, request):
        self.calls.append((request.operation, dict(request.parameters)))
        if request.operation == "keyword_asin_analysis_monthly":
            ordered = (*sorted(SP032B_PILOT_ASINS), *self.historical_e, *self.current)
            payload = {
                "list": [
                    {
                        "asin": asin,
                        "parentAsin": f"P{index:09d}",
                        "country": "US",
                        "ranks": _rank(),
                    }
                    for index, asin in enumerate(ordered, 1)
                ],
                "total": len(ordered),
            }
        elif request.operation == "asin_keywords_monthly":
            asin = str(request.parameters["asin"])
            payload = {
                "list": [
                    {
                        "country": "US",
                        "searchTerm": "portable dog water bottle",
                        "ranks": _rank(),
                        "trafficSummary": {
                            "traffic": {"organic": 100, "advertising": 0, "total": 100}
                        },
                    },
                    {
                        "country": "US",
                        "searchTerm": f"dog water bottle {asin[-3:]}",
                        "ranks": _rank(),
                        "trafficSummary": {
                            "traffic": {"organic": 20, "advertising": 0, "total": 20}
                        },
                    },
                ],
                "total": 2,
            }
        else:
            raise AssertionError(request.operation)
        return TransportResponse(
            status_code=200,
            payload=payload,
            metadata={"cost_credits": "1"},
        )


class OrganicKeywordTemporalHoldoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.historical_e = tuple(f"E{index:09d}" for index in range(1, 101))
        self.current = tuple(f"F{index:09d}" for index in range(1, 101))
        self.e_checkpoint = {"cohort": [{"asin": asin} for asin in self.historical_e]}

    def test_credit_gate_is_enforced_before_capture(self) -> None:
        plan = TemporalCreditPlan(gate_credits=114)
        self.assertEqual(115, plan.estimated_total_credits)
        with self.assertRaises(CreditApprovalRequired):
            plan.enforce()

    def test_selection_excludes_all_historical_asins(self) -> None:
        historical = frozenset(SP032B_PILOT_ASINS | frozenset(self.historical_e))
        ordered = (*sorted(SP032B_PILOT_ASINS), *self.historical_e, *self.current)
        selected, exclusions = select_temporal_cohort(
            {"list": [{"asin": asin} for asin in ordered], "total": len(ordered)},
            historical_asins=historical,
        )
        self.assertEqual(list(self.current), [item["asin"] for item in selected])
        self.assertEqual(120, len(exclusions))
        self.assertFalse({item["asin"] for item in selected} & historical)

    def test_monthly_capture_is_checkpointed_and_replayable(self) -> None:
        transport = _MonthlyTransport(self.historical_e, self.current)
        client = XiYouLiveCaptureClient(
            environment={"XIYOU_API_KEY": "test-only"},
            transport=transport,
            retrieved_at="2026-08-21T00:00:00+00:00",
        )
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint_path = Path(temporary) / "temporal.json"
            runner = OrganicTemporalHoldoutLiveCaptureV0_1(
                client,
                baseline_commit="c25d9e",
                checkpoint_path=checkpoint_path,
                sp032e_checkpoint=self.e_checkpoint,
                min_request_interval_seconds=0,
            )
            checkpoint = runner.run()
            first_call_count = len(transport.calls)
            resumed = runner.run()

            self.assertEqual("COMPLETE", checkpoint["status"])
            self.assertEqual(101, first_call_count)
            self.assertEqual(first_call_count, len(transport.calls))
            self.assertEqual(checkpoint, resumed)
            self.assertEqual(100, len(checkpoint["reverse_captures"]))
            self.assertTrue(checkpoint["fingerprints_identical"])
            self.assertEqual(checkpoint["fingerprints_start"], frozen_rule_fingerprints())
            self.assertTrue(
                all(
                    capture["operation"] == "asin_keywords_monthly"
                    and capture["parameters"]["startMonth"] == "2026-07"
                    and "period" not in capture["parameters"]
                    for capture in checkpoint["reverse_captures"]
                )
            )

            replay = analyze_holdout_checkpoint(checkpoint)
            self.assertEqual(200, replay["corpus"]["raw_relation_count"])
            self.assertEqual(101, replay["credit_audit"]["request_count"])


if __name__ == "__main__":
    unittest.main()
