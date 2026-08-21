from __future__ import annotations

import unittest

from amazon_product_intelligence.connectors import TransportResponse
from amazon_product_intelligence.organic_keyword_discovery import (
    CreditApprovalRequired,
    CreditPlan,
    OrganicBuyerNeedDiscoveryPilot,
    OrganicKeywordDiscoveryRunner,
    QueryOrigin,
    QueryRole,
    XiYouLiveCaptureClient,
)


ASINS = ("B0CDV36NF6", "B0CBQFKXP2")


def _rank() -> list[dict[str, object]]:
    return [
        {
            "page": 1,
            "position": "sb",
            "rankTime": "2026-08-20T00:00:00-07:00",
        },
        {
            "page": 1,
            "pageRank": 4,
            "position": "or",
            "rankTime": "2026-08-20T00:00:00-07:00",
            "totalRank": 4,
        }
    ]


def _reverse_row(term: str, *, organic: int) -> dict[str, object]:
    return {
        "country": "US",
        "searchTerm": term,
        "ranks": _rank(),
        "trafficSummary": {
            "traffic": {"organic": organic, "advertising": 0, "total": organic}
        },
    }


class _DynamicXiYouTransport:
    def execute(self, request):
        if request.operation == "keyword_asin_analysis":
            rows = [
                {
                    "asin": asin,
                    "country": "US",
                    "ranks": _rank(),
                    "trafficSummary": {
                        "traffic": {"organic": 100 - index, "advertising": 0, "total": 100 - index}
                    },
                }
                for index, asin in enumerate(ASINS)
            ]
            payload = {"list": rows, "total": 658}
        elif request.operation == "asin_keywords":
            asin = request.parameters["asin"]
            unique = (
                "large capacity dog water bottle"
                if asin == ASINS[0]
                else "dog water bottle for hiking"
            )
            payload = {
                "list": [
                    _reverse_row("leakproof dog water bottle", organic=200),
                    _reverse_row(unique, organic=100),
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
                        "competitiveDifficulty": 40 + index,
                        "costPerClick": {
                            "value": "1.20",
                            "minSuggestedBid": "1.00",
                            "maxSuggestedBid": "1.50",
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


def _client() -> XiYouLiveCaptureClient:
    return XiYouLiveCaptureClient(
        environment={"XIYOU_API_KEY": "test-only"},
        transport=_DynamicXiYouTransport(),
        retrieved_at="2026-08-21T00:00:00+00:00",
    )


class OrganicKeywordDiscoveryTests(unittest.TestCase):
    def test_credit_gate_stops_before_provider_access(self) -> None:
        plan = CreditPlan.for_pilot(asin_count=29, max_pages=1, gate_credits=30)
        self.assertEqual(plan.estimated_total_credits, 31)
        with self.assertRaises(CreditApprovalRequired):
            plan.enforce()

    def test_reverse_runner_preserves_cross_asin_keyword_lineage(self) -> None:
        result = OrganicKeywordDiscoveryRunner(_client()).run(ASINS)

        self.assertEqual(result.corpus.asin_keyword_relation_count, 4)
        self.assertEqual(result.corpus.unique_keyword_count, 3)
        self.assertEqual(result.corpus.duplicate_keyword_count, 1)
        repeated = [
            item
            for item in result.records
            if item.normalized_text == "leakproof dog water bottle"
        ]
        self.assertEqual({item.source_asin for item in repeated}, set(ASINS))
        self.assertTrue(all(item.query_role is QueryRole.DISCOVERED_CANDIDATE for item in repeated))
        self.assertTrue(all(item.query_origin is QueryOrigin.ASIN_REVERSE_RETURNED for item in repeated))
        self.assertTrue(all(item.provider_returned and not item.human_seeded for item in repeated))
        self.assertTrue(all(item.discovery_id in result.lineage_by_discovery_id for item in repeated))

    def test_end_to_end_pilot_keeps_discovery_origin_through_clusters(self) -> None:
        result = OrganicBuyerNeedDiscoveryPilot(
            _client(),
            baseline_commit="c25d9eebf74cf0c80f99c3202666f57eee3b13eb",
            asin_count=2,
            page_size=20,
            max_pages=1,
            credit_gate=30,
        ).run()

        self.assertEqual(result.request_count, 4)
        self.assertEqual(result.known_credits, 4)
        self.assertEqual(len(result.cohort.asins), 2)
        self.assertGreater(len(result.clustering.clusters), 0)
        self.assertEqual(len(result.keyword_validation), 3)
        self.assertTrue(result.success_criteria["criterion_1_not_human_preset"])
        self.assertTrue(result.success_criteria["criterion_3_asin_request_response_term_lineage"])
        self.assertTrue(result.success_criteria["criterion_4_cluster_to_discovered_keyword_lineage"])
        self.assertTrue(
            all(item.query_origin is QueryOrigin.ASIN_REVERSE_RETURNED for item in result.keyword_validation)
        )
        clustered_ids = {
            need_id for cluster in result.clustering.clusters for need_id in cluster.source_need_ids
        }
        linked_ids = {need_id for link in result.buyer_need_links for need_id in link.need_ids}
        self.assertLessEqual(clustered_ids, linked_ids)
        self.assertTrue(
            all(
                metric.share is None
                for metric in result.buyer_need_map.demand_metrics
                if metric.metric_type.value == "SEARCH_DEMAND_SHARE"
            )
        )


if __name__ == "__main__":
    unittest.main()
