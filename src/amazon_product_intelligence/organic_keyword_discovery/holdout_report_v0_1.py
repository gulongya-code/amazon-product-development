"""Markdown report for TASK-SP-032E."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def _cell(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _percent(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return _cell(value)


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def render_holdout_report(result: Mapping[str, Any]) -> str:
    corpus = result["corpus"]
    credits = result["credit_audit"]
    resolution = result["buyer_need_resolution"]
    precision = result["precision_audit"]
    need_precision = precision["summary"]["NEED_CANDIDATE"]
    non_need_precision = precision["summary"]["NON_NEED"]
    bowl = result["integrated_bowl_validation"]
    collapsible = result["collapsible_validation"]
    crate = result["crate_validation"]
    insulated = result["insulated_validation"]
    outdoor = result["outdoor_portability_bias"]
    unknown = result["unknown_audit"]

    lines = [
        "# TASK-SP-032E — 100-ASIN Organic Discovery Holdout Validation v0.1",
        "",
        "**TASK-SP-032E COMPLETE**",
        "",
        f"- Baseline: `{result['baseline_commit']}`",
        f"- Analysis ID: `{result['analysis_id']}`",
        f"- Final judgement: **{result['generalization_judgement']}**",
        f"- Category: {result['category_scope']}",
        f"- Marketplace / period: `{result['marketplace']}` / `{result['period']}`",
        "- Important: ASIN coverage below is cohort recurrence, **not Demand Share**.",
        "",
        "## 1. Cohort and independence",
        "",
        result["cohort_selection_method"],
        "",
        f"- Provider total: **{_cell(result['cohort_provider_total'])}**",
        f"- Holdout ASIN count: **{len(result['cohort'])}**",
        f"- Frozen pilot exclusion count: **{len(result['pilot_excluded_asins'])}**",
        f"- Pilot overlap: **{0 if result['success_criteria']['holdout_independent'] else 'FAILED'}**",
        "- Parent ASIN is retained when the provider row supplies it; otherwise it remains UNKNOWN.",
        "",
    ]
    lines.extend(
        _table(
            ("#", "Child ASIN", "Parent ASIN", "Provider page", "Response rank"),
            [
                (
                    index,
                    item["asin"],
                    item.get("parent_asin"),
                    item["provider_page"],
                    item["provider_response_rank"],
                )
                for index, item in enumerate(result["cohort"], 1)
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 2. API calls and credits",
            "",
            f"- Pre-call estimate: **{credits['estimated_credits']} credits**",
            f"- Gate: **{credits['gate_credits']} credits**",
            f"- Executed calls: **{credits['request_count']}**",
            f"- Provider-reported known credits: **{credits['known_credits']}**",
            f"- Calls without credit metadata: **{credits['unknown_credit_call_count']}**",
            "",
        ]
    )
    lines.extend(
        _table(
            ("#", "Operation", "ASIN", "Page", "Page size / terms", "Rows", "Total", "Credits", "X-Cost-Credits"),
            [
                (
                    index,
                    call["operation"],
                    call.get("source_asin"),
                    call["parameters"].get("page"),
                    call["parameters"].get("pageSize")
                    or len(call["parameters"].get("searchTerms", [])),
                    call["returned_rows"],
                    call.get("provider_total"),
                    call.get("credits"),
                    call.get("x_cost_credits"),
                )
                for index, call in enumerate(credits["calls"], 1)
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 3. Raw keyword corpus",
            "",
            f"- Raw ASIN-keyword relations: **{corpus['raw_relation_count']}**",
            f"- Unique keywords: **{corpus['unique_keyword_count']}**",
            f"- Cross-ASIN duplicates: **{corpus['duplicate_keyword_count']}**",
            f"- Source ASINs: **{corpus['source_asin_count']}**",
            f"- Successful source coverage: **{_percent(corpus['coverage']['source_asin_success_share'])}**",
            f"- Rank availability: `{_cell(corpus['rank_distribution'])}`",
            f"- Traffic availability: `{_cell(corpus['traffic_availability'])}`",
            "",
            "### Top 100 organic discovered terms",
            "",
        ]
    )
    lines.extend(
        _table(
            ("#", "Keyword", "Relations", "ASIN count", "ASIN coverage", "Provider traffic", "Best organic rank"),
            [
                (
                    index,
                    item["keyword"],
                    item["relation_count"],
                    item["asin_coverage_count"],
                    _percent(item["asin_coverage_share"]),
                    item.get("provider_traffic_sum"),
                    item.get("best_organic_rank"),
                )
                for index, item in enumerate(result["top_100_organic_terms"], 1)
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 4. Intent distribution",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Intent", "Relations", "Share of raw relations"),
            [
                (intent, count, _percent(str(count / corpus["raw_relation_count"])))
                for intent, count in result["intent_distribution"].items()
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 5. Buyer Need resolution",
            "",
            f"- Resolved Buyer Need relations: **{resolution['resolved_buyer_need_relations']}**",
            f"- Explicit NON_NEED relations: **{resolution['explicit_non_need_relations']}**",
            f"- UNKNOWN Need Candidate relations: **{resolution['unknown_need_candidate_relations']}**",
            f"- AMBIGUOUS relations: **{resolution['ambiguous_relations']}**",
            f"- True Need Resolution Rate: **{_percent(resolution['true_need_resolution_rate'])}**",
            f"- Buyer Need unresolved rate: **{_percent(resolution['buyer_need_unresolved_rate'])}**",
            f"- NON_NEED share: **{_percent(resolution['non_need_share'])}**",
            "- NON_NEED contributes to resolution coverage; it is not Buyer Need coverage.",
            "",
            "## 6. Semantic clusters",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Cluster", "Need records", "Relations", "Source ASINs", "ASIN coverage", "Expressions"),
            [
                (
                    item["cluster_label"],
                    item["need_count"],
                    item["relation_count"],
                    item["source_asin_count"],
                    _percent(item["asin_coverage"]),
                    "; ".join(item["expressions"][:12]),
                )
                for item in result["semantic_clusters"]
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 7. Manual precision audit",
            "",
            f"- NEED_CANDIDATE: selected **{need_precision['selected_count']}**, correct **{need_precision['correct_count']}**, incorrect **{need_precision['incorrect_count']}**, ambiguous **{need_precision['ambiguous_count']}**, precision **{_percent(need_precision['precision'])}**.",
            f"- NON_NEED: selected **{non_need_precision['selected_count']}**, correct **{non_need_precision['correct_count']}**, incorrect **{non_need_precision['incorrect_count']}**, ambiguous **{non_need_precision['ambiguous_count']}**, precision **{_percent(non_need_precision['precision'])}**.",
            "- AMBIGUOUS is excluded from the precision denominator.",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Group", "Keyword", "Predicted intent", "Predicted resolution", "Manual label", "Reason"),
            [
                (
                    item["audit_group"],
                    item["keyword"],
                    item["predicted_intent"],
                    item["predicted_resolution"],
                    item["manual_label"],
                    item.get("manual_reason"),
                )
                for item in precision["items"]
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 8. Integrated Bowl holdout validation",
            "",
            f"- Relations / source ASINs / coverage: **{bowl['relation_count']} / {bowl['source_asin_count']} / {_percent(bowl['asin_coverage'])}**",
            f"- False positives: **{bowl['false_positive_count']}**",
            f"- Precision: **{_percent(bowl['precision'])}**",
            f"- Expressions: `{_cell(bowl['expressions'])}`",
            f"- Judgement: **{bowl['judgement']}**",
            "",
            "## 9. Collapsible holdout validation",
            "",
            f"- Relations / source ASINs / coverage: **{collapsible['relation_count']} / {collapsible['source_asin_count']} / {_percent(collapsible['asin_coverage'])}**",
            f"- True / false positives: **{collapsible['true_positive_count']} / {collapsible['false_positive_count']}**",
            f"- Precision: **{_percent(collapsible['precision'])}**",
            f"- Recall observation: **{_percent(collapsible['recall_observation'])}**",
            f"- Expressions: `{_cell(collapsible['expressions'])}`",
            "",
            "## 10. Crate compatibility experimental validation",
            "",
            f"- Relations / source ASINs: **{crate['relation_count']} / {crate['source_asin_count']}**",
            f"- False positives / precision: **{crate['false_positive_count']} / {_percent(crate['precision'])}**",
            f"- Expressions: `{_cell(crate['expressions'])}`",
            f"- Judgement: **{crate['judgement']}** (no taxonomy promotion performed)",
            "",
            "## 11. Insulated proposal validation",
            "",
            f"- Relations / source ASINs / coverage: **{insulated['relation_count']} / {insulated['source_asin_count']} / {_percent(insulated['asin_coverage'])}**",
            f"- Dog-related / generic / branded relations: **{insulated['exact_dog_related_relation_count']} / {insulated['generic_relation_count']} / {insulated['branded_relation_count']}**",
            f"- False positives: **{insulated['false_positive_count']}**",
            f"- Judgement: **{insulated['judgement']}** (no taxonomy change performed)",
            "",
            "## 12. Outdoor Portability bias recheck",
            "",
            f"- Outdoor among matched Need relations: **{outdoor['outdoor_matched_need_relation_count']} / {outdoor['matched_need_relation_count']} ({_percent(outdoor['outdoor_share_within_matched_need_relations'])})**",
            f"- Outdoor in raw organic relations: **{outdoor['outdoor_raw_organic_relation_count']} / {outdoor['raw_organic_relation_count']} ({_percent(outdoor['outdoor_share_within_raw_organic_relations'])})**",
            f"- Source ASIN coverage: **{outdoor['outdoor_source_asin_count']} / 100 ({_percent(outdoor['outdoor_source_asin_coverage'])})**",
            f"- Judgement: **{outdoor['judgement']}**",
            "",
            "## 13. New UNKNOWN audit",
            "",
            f"- Unresolved relations: **{unknown['relation_count']}**",
            f"- Unique unresolved terms: **{unknown['unique_term_count']}**",
            f"- New vs 20-ASIN pilot: **{unknown['new_unique_term_count']}**",
            f"- Category distribution: `{_cell(unknown['category_distribution'])}`",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Term", "Raw expressions", "Relations", "ASINs", "New vs pilot", "Audit category", "Reason"),
            [
                (
                    item["normalized_keyword"],
                    "; ".join(item["raw_expressions"]),
                    item["relation_count"],
                    item["source_asin_count"],
                    item["new_vs_20_asin_pilot"],
                    item["category"],
                    item.get("reason"),
                )
                for item in unknown["terms"]
            ],
        )
    )

    enrichment = result["keyword_enrichment"]
    lines.extend(
        [
            "",
            "## 14. Optional Top-30 keyword enrichment",
            "",
            f"- Executed: **{enrichment['executed']}**",
            "- Selection used ASIN coverage, provider traffic, organic rank, and stable text order.",
            "- `query_origin` remains `ASIN_REVERSE_RETURNED`.",
            "",
        ]
    )
    if enrichment["items"]:
        lines.extend(
            _table(
                ("Keyword", "Search volume", "ABA rank", "CPC", "Difficulty", "Origin"),
                [
                    (
                        item["keyword"],
                        item.get("search_volume"),
                        item.get("aba_rank"),
                        item.get("cpc"),
                        item.get("difficulty"),
                        item["query_origin"],
                    )
                    for item in enrichment["items"]
                ],
            )
        )

    lines.extend(
        [
            "",
            "## 15. Success criteria",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Criterion", "Result"),
            [(key, value) for key, value in result["success_criteria"].items()],
        )
    )
    lines.extend(
        [
            "",
            "## 16. Generalization judgement",
            "",
            f"**{result['generalization_judgement']}**",
            "",
            "This judgement is evidence aggregation over the frozen v0.2 implementation. No taxonomy, intent, semantic, gap, scoring, or policy rule was changed during the holdout.",
            "",
            "## 17. Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in result["limitations"])
    lines.extend(
        [
            "",
            "## 18. Next step — one recommendation",
            "",
            result["next_step_unique_recommendation"],
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ("render_holdout_report",)
