from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from amazon_product_intelligence.connectors import TransportResponse
from amazon_product_intelligence.organic_keyword_discovery.capture import (
    XiYouLiveCaptureClient,
)
from amazon_product_intelligence.organic_keyword_discovery.holdout_v0_1 import (
    HOLDOUT_ASIN_COUNT,
    SP032B_PILOT_ASINS,
    HoldoutCreditPlan,
    OrganicHoldoutLiveCaptureV0_1,
    _outdoor_bias,
    analyze_holdout_checkpoint,
    load_json_object,
    select_holdout_cohort,
)
from amazon_product_intelligence.organic_keyword_discovery.runner import (
    CreditApprovalRequired,
)


def _rank() -> list[dict[str, object]]:
    return [
        {
            "page": 1,
            "pageRank": 4,
            "position": "or",
            "rankTime": "2026-08-20T00:00:00-07:00",
            "totalRank": 4,
        }
    ]


def _reverse_row(term: str, organic: int) -> dict[str, object]:
    return {
        "country": "US",
        "searchTerm": term,
        "ranks": _rank(),
        "trafficSummary": {
            "traffic": {"organic": organic, "advertising": 0, "total": organic}
        },
    }


class _HoldoutTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.asins = tuple(f"B{index:09d}" for index in range(1, 111))

    def execute(self, request):
        self.calls.append(request.operation)
        if request.operation == "keyword_asin_analysis":
            ordered = (*sorted(SP032B_PILOT_ASINS), *self.asins)
            payload = {
                "list": [
                    {
                        "asin": asin,
                        "parentAsin": f"P{index:09d}" if index % 2 else None,
                        "country": "US",
                        "ranks": _rank(),
                    }
                    for index, asin in enumerate(ordered, 1)
                ],
                "total": 662,
            }
        elif request.operation == "asin_keywords":
            index = int(str(request.parameters["asin"])[1:])
            terms = (
                "leakproof dog water bottle",
                "dog water bottle",
                "dog water bottle with built in bowl",
                "PupFlask insulated water bottle",
            )
            payload = {
                "list": [
                    _reverse_row(terms[index % len(terms)], 1000 - index),
                    _reverse_row("portable dog water bottle", 500 - index),
                ],
                "total": 2,
            }
        elif request.operation == "keyword_info":
            payload = {
                "list": [
                    {
                        "searchTerm": term,
                        "abaReport": {
                            "reportFromDate": "2026-08-09",
                            "reportToDate": "2026-08-15",
                            "searchFrequencyRank": 1000 + index,
                            "weeklySearchVolume": 5000 - index,
                        },
                    }
                    for index, term in enumerate(request.parameters["searchTerms"])
                ],
                "total": len(request.parameters["searchTerms"]),
            }
        else:
            raise AssertionError(request.operation)
        return TransportResponse(
            status_code=200,
            payload=payload,
            metadata={"cost_credits": "1"},
        )


class OrganicKeywordHoldoutTests(unittest.TestCase):
    def test_credit_gate_blocks_before_capture(self) -> None:
        plan = HoldoutCreditPlan(gate_credits=101)
        self.assertEqual(102, plan.estimated_total_credits)
        with self.assertRaises(CreditApprovalRequired):
            plan.enforce()

    def test_cohort_selection_excludes_frozen_pilot_and_keeps_order(self) -> None:
        pilot = sorted(SP032B_PILOT_ASINS)
        holdout = [f"B{index:09d}" for index in range(1, 101)]
        payload = {"list": [{"asin": asin} for asin in (*pilot, *holdout)], "total": 662}

        selected = select_holdout_cohort(payload)

        self.assertEqual(HOLDOUT_ASIN_COUNT, len(selected))
        self.assertEqual(holdout, [item["asin"] for item in selected])
        self.assertFalse(set(holdout) & SP032B_PILOT_ASINS)
        self.assertEqual(21, selected[0]["provider_response_rank"])

    def test_outdoor_raw_detector_mirrors_frozen_taxonomy_inflections(self) -> None:
        relations = [
            {
                "normalized_keyword": term,
                "resolution": "RESOLVED_BUYER_NEED",
                "buyer_needs": [{"need_label": label}],
                "source_asin": f"B{index:09d}",
            }
            for index, (term, label) in enumerate(
                (
                    ("dog bottle for a walk", "walking"),
                    ("dog bottle for hikes", "outdoor hiking"),
                    ("dog bottle travelled", "travel"),
                    ("portable dog bottle", "portable"),
                ),
                1,
            )
        ]

        result = _outdoor_bias(relations)

        self.assertEqual(4, result["outdoor_raw_organic_relation_count"])
        self.assertEqual(4, result["outdoor_matched_need_relation_count"])
        self.assertEqual("DATA_DRIVEN_DOMINANCE", result["judgement"])

    def test_checkpointed_live_run_is_resumable_and_offline_replayable(self) -> None:
        transport = _HoldoutTransport()
        client = XiYouLiveCaptureClient(
            environment={"XIYOU_API_KEY": "test-only"},
            transport=transport,
            retrieved_at="2026-08-21T00:00:00+00:00",
        )
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint_path = Path(temporary) / "holdout.json"
            runner = OrganicHoldoutLiveCaptureV0_1(
                client,
                baseline_commit="c25d9e",
                checkpoint_path=checkpoint_path,
            )

            checkpoint = runner.run()
            first_call_count = len(transport.calls)
            resumed = runner.run()

            self.assertEqual("COMPLETE", checkpoint["status"])
            self.assertEqual(102, first_call_count)
            self.assertEqual(first_call_count, len(transport.calls))
            self.assertEqual(checkpoint, resumed)
            self.assertEqual(100, len(checkpoint["reverse_captures"]))
            self.assertEqual(checkpoint, load_json_object(checkpoint_path))

            result = analyze_holdout_checkpoint(checkpoint)
            self.assertEqual(200, result["corpus"]["raw_relation_count"])
            self.assertEqual(5, result["corpus"]["unique_keyword_count"])
            self.assertEqual(102, result["credit_audit"]["known_credits"])
            self.assertTrue(result["success_criteria"]["holdout_independent"])
            self.assertEqual(
                "INSUFFICIENT_EVIDENCE",
                result["generalization_judgement"],
            )


if __name__ == "__main__":
    unittest.main()
