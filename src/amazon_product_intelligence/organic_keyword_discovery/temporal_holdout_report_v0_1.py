"""Markdown report renderer for TASK-SP-032F."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections import Counter
from decimal import Decimal
from typing import Any


def _pct(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return f"{Decimal(str(value)) * Decimal(100):.2f}%"


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _special_summary(name: str, payload: Mapping[str, Any]) -> tuple[Any, ...]:
    current = payload["sp032f"]
    previous = payload["sp032e"]
    return (
        name,
        previous.get("relation_count"),
        current.get("relation_count"),
        previous.get("source_asin_count"),
        current.get("source_asin_count"),
        _pct(previous.get("precision")),
        _pct(current.get("precision")),
        payload["decision"],
    )


def render_temporal_holdout_report(result: Mapping[str, Any]) -> str:
    window = result["temporal_window"]
    fingerprints = result["frozen_fingerprints"]
    credit = result["credit_audit"]
    corpus = result["corpus"]
    resolution = result["buyer_need_resolution"]
    precision = result["precision_audit"]["summary"]
    comparison = result["comparison_sp032e_vs_sp032f"]
    error_rows = result["error_pattern_replication"]["categories"]
    exclusion_counts = Counter(
        item["exclusion_reason"] for item in result["cohort_exclusions"]
    )
    versions = fingerprints["start"]["versions"]

    comparison_rows = [
        ("Raw relations", comparison["raw_relations"]["sp032e"], comparison["raw_relations"]["sp032f"], "—"),
        ("Unique keywords", comparison["unique_keywords"]["sp032e"], comparison["unique_keywords"]["sp032f"], "—"),
        ("True Need Resolution", _pct(comparison["true_need_resolution_rate"]["sp032e"]), _pct(comparison["true_need_resolution_rate"]["sp032f"]), "—"),
        ("Unresolved Rate", _pct(comparison["unresolved_rate"]["sp032e"]), _pct(comparison["unresolved_rate"]["sp032f"]), "—"),
        ("Need Precision", _pct(comparison["need_precision"]["sp032e"]), _pct(comparison["need_precision"]["sp032f"]), f"{comparison['need_precision']['delta_percentage_points']} pp"),
        ("NON_NEED Precision", _pct(comparison["non_need_precision"]["sp032e"]), _pct(comparison["non_need_precision"]["sp032f"]), f"{comparison['non_need_precision']['delta_percentage_points']} pp"),
    ]
    intent_labels = (
        "NEED_CANDIDATE",
        "PRODUCT_OBJECT",
        "BRAND_MODEL",
        "ACCESSORY_RELATED",
        "BROAD_QUERY",
        "OUT_OF_SCOPE",
        "AMBIGUOUS",
    )
    intent_rows = [
        (
            label,
            comparison["intent_distribution"]["sp032e"].get(label, 0),
            comparison["intent_distribution"]["sp032f"].get(label, 0),
        )
        for label in intent_labels
    ]
    cohort_rows = [
        (
            index,
            item["asin"],
            item.get("parent_asin") or "UNKNOWN",
            item["provider_page"],
            item["provider_response_rank"],
            item["provider_total"],
            item["selection_reason"],
        )
        for index, item in enumerate(result["cohort"], 1)
    ]
    special_rows = [
        _special_summary("Integrated Bowl", result["integrated_bowl_replication"]),
        _special_summary("Collapsible", result["collapsible_replication"]),
        _special_summary("Crate Compatibility", result["crate_replication"]),
    ]
    insulated = result["insulated_replication"]
    outdoor = result["outdoor_portability_replication"]
    outdoor_expression_rows = [
        (
            label,
            outdoor["sp032e_expression_stats"]["expressions"][label]["relation_count"],
            outdoor["sp032f_expression_stats"]["expressions"][label]["relation_count"],
            outdoor["sp032e_expression_stats"]["expressions"][label]["source_asin_count"],
            outdoor["sp032f_expression_stats"]["expressions"][label]["source_asin_count"],
        )
        for label in ("portable", "travel", "walking", "hiking")
    ]

    lines = [
        "# ORGANIC BUYER NEED TEMPORAL HOLDOUT V0.1",
        "",
        "## 1. Executive decision",
        "",
        f"**TASK-SP-032F COMPLETE — {result['overfit_replication_decision']}**",
        "",
        f"The unique next recommendation is **{result['next_step_unique_recommendation']}**",
        "",
        "This result answers whether the TASK-SP-032E 81.63% Need Precision finding replicates under an independent cohort and a different explicit provider window. It does not modify the frozen Taxonomy or rules.",
        "",
        "## 2. Baseline and frozen versions",
        "",
        f"- Baseline commit: `{result['baseline_commit']}`",
        f"- Taxonomy: `{versions['buyer_need_taxonomy']}`",
        f"- Buyer Need rules: `{versions['buyer_need_rules']}`",
        f"- Intent rules: `{versions['buyer_need_intent_rules']}`",
        f"- Semantic contract: `{versions['semantic_clustering_contract']}`",
        f"- Semantic rules: `{versions['semantic_clustering_rules']}`",
        f"- Start/end fingerprints identical: **{fingerprints['identical']}**",
        "- Taxonomy/Rules modified: **0**",
        "",
        _table(
            ("Registry", "Identity", "SHA-256"),
            [
                (name, value["identity"], value["sha256"])
                for name, value in fingerprints["start"]["registries"].items()
            ],
        ),
        "",
        "## 3. Temporal window and provider contract",
        "",
        f"- TASK-SP-032E period: `{window['previous_period']}`",
        f"- TASK-SP-032F period: `{window['new_period']}`",
        f"- Semantics: {window['period_semantics']}",
        f"- Selection timing: {window['selection_timing']}",
        "- Provider API overview: <https://openapi-doc.xydc.com/>",
        "- Previous reverse contract: <https://openapi-doc.xydc.com/331502595e0>",
        "- Monthly reverse contract: <https://openapi-doc.xydc.com/331594504e0>",
        "- Monthly cohort contract: <https://openapi-doc.xydc.com/451506681e0>",
        "",
        "The recent reverse contract exposes `last7days`; the monthly endpoint is therefore used for the preselected latest complete calendar month (2026-07). No provider result was inspected before choosing the window.",
        "",
        "## 4. Independent cohort",
        "",
        f"- Marketplace: `{result['marketplace']}`",
        f"- Category: {result['category_scope']}",
        "- Seed query: `dog water bottle`",
        f"- Independent Child ASINs: **{len(result['cohort'])}**",
        f"- Historical exclusions: **{result['historical_asin_count']}**",
        f"- Overlap with prior 120 ASINs: **{result['historical_overlap_count']}**",
        f"- Provider total: **{result['cohort_provider_total']}**",
        "- Selection: page 1, provider traffic descending, response order; exclude prior 120, deduplicate, then take first 100.",
        f"- Excluded rows encountered before the 100th selected ASIN: **{dict(sorted(exclusion_counts.items()))}**",
        "",
        "## 5. API calls and credits",
        "",
        _table(
            ("Measure", "Value"),
            (
                ("Estimated credits", credit["estimated_credits"]),
                ("Credit gate", credit["gate_credits"]),
                ("Actual known credits", credit["known_credits"]),
                ("Unknown-credit calls", credit["unknown_credit_call_count"]),
                ("Request count", credit["request_count"]),
            ),
        ),
        "",
        _table(
            ("Operation", "Calls", "Known credits"),
            [
                (
                    operation,
                    sum(call["operation"] == operation for call in credit["calls"]),
                    sum((call["credits"] or 0) for call in credit["calls"] if call["operation"] == operation),
                )
                for operation in sorted({call["operation"] for call in credit["calls"]})
            ],
        ),
        "",
        "## 6. Organic discovery corpus",
        "",
        _table(
            ("Measure", "Value"),
            (
                ("Raw ASIN-keyword relations", corpus["raw_relation_count"]),
                ("Unique keywords", corpus["unique_keyword_count"]),
                ("Cross-ASIN duplicate relations", corpus["duplicate_keyword_count"]),
                ("Source ASINs", corpus["source_asin_count"]),
                ("Successful ASINs", corpus["coverage"]["successful_source_asin_count"]),
                ("Failed ASINs", corpus["coverage"]["failed_source_asin_count"]),
                ("Empty ASINs", corpus["coverage"]["empty_source_asin_count"]),
                ("Traffic availability", corpus["traffic_availability"]),
                ("Organic rank availability", corpus["rank_distribution"]),
            ),
        ),
        "",
        "## 7. Frozen Taxonomy v0.2 results",
        "",
        _table(("Intent", "SP-032E", "SP-032F"), intent_rows),
        "",
        _table(
            ("Resolution", "SP-032F count"),
            [(key, value) for key, value in result["resolution_distribution"].items()],
        ),
        "",
        f"True Need Resolution: **{_pct(resolution['true_need_resolution_rate'])}**. Unresolved Rate: **{_pct(resolution['buyer_need_unresolved_rate'])}**.",
        "",
        "## 8. Precision audit",
        "",
        _table(
            ("Audit group", "Selected", "Correct", "Incorrect", "Ambiguous", "Unreviewed", "Precision"),
            [
                (
                    group,
                    row["selected_count"],
                    row["correct_count"],
                    row["incorrect_count"],
                    row["ambiguous_count"],
                    row["unreviewed_count"],
                    _pct(row["precision"]),
                )
                for group, row in precision.items()
            ],
        ),
        "",
        "The deterministic sample uses the same SP-032E rule: top 50 unique NEED_CANDIDATE terms and an intent-stratified 30-term NON_NEED sample. AMBIGUOUS is excluded from the precision denominator; no label standard was changed.",
        "Exact normalized terms previously adjudicated in SP-032E retain that judgement; SP-032F independently reviews new terms and may explicitly override only with a recorded reason. The companion annotations file records this reference policy.",
        "",
        "## 9. SP-032E vs SP-032F",
        "",
        _table(("Metric", "SP-032E", "SP-032F", "Delta"), comparison_rows),
        "",
        _table(
            ("Buyer Need cluster", "SP-032E relations", "SP-032F relations"),
            [
                (
                    label,
                    comparison["buyer_need_distribution"]["sp032e"].get(label, 0),
                    comparison["buyer_need_distribution"]["sp032f"].get(label, 0),
                )
                for label in sorted(
                    set(comparison["buyer_need_distribution"]["sp032e"])
                    | set(comparison["buyer_need_distribution"]["sp032f"])
                )
            ],
        ),
        "",
        "## 10. Need-specific replication",
        "",
        _table(
            ("Need", "E relations", "F relations", "E ASINs", "F ASINs", "E precision", "F precision", "Decision"),
            special_rows,
        ),
        "",
        f"Crate remains **EXPERIMENTAL**; expression diversity in SP-032F is **{result['crate_replication']['expression_diversity']}**. It was not promoted.",
        "",
        f"Insulated remains **PROPOSAL_ONLY**. SP-032F dog-specific/generic/branded relations: **{insulated['sp032f']['exact_dog_related_relation_count']} / {insulated['sp032f']['generic_relation_count']} / {insulated['sp032f']['branded_relation_count']}**; source ASINs: **{insulated['sp032f']['source_asin_count']}**; decision: **{insulated['decision']}**.",
        "",
        f"Outdoor Portability decision: **{outdoor['decision']}**. SP-032E raw outdoor relations/ASINs: **{outdoor['sp032e']['outdoor_raw_organic_relation_count']} / {outdoor['sp032e']['outdoor_source_asin_count']}**; SP-032F: **{outdoor['sp032f']['outdoor_raw_organic_relation_count']} / {outdoor['sp032f']['outdoor_source_asin_count']}**. This comparison uses raw frozen-rule expressions, not inferred Demand Share.",
        "",
        _table(
            ("Expression", "E relations", "F relations", "E ASINs", "F ASINs"),
            outdoor_expression_rows,
        ),
        "",
        "## 11. Error-pattern replication",
        "",
        _table(
            ("Category", "SP-032E", "SP-032F", "Replication"),
            [
                (row["category"], row["sp032e_count"], row["sp032f_count"], row["replication"])
                for row in error_rows
            ],
        ),
        "",
        f"Major error patterns reproduced: **{result['error_pattern_replication']['major_patterns_reproduced']}**.",
        "",
        "## 12. Overfit replication decision",
        "",
        f"Final decision: **{result['overfit_replication_decision']}**.",
        "",
        f"Need Precision moved from **{_pct(comparison['need_precision']['sp032e'])}** to **{_pct(comparison['need_precision']['sp032f'])}**, a **{comparison['need_precision']['delta_percentage_points']} percentage-point** change. The decision combines that result with independent reproduction of the two principal SP-032E error classes; it does not treat a low score alone as proof.",
        "",
        "## 13. Limitations",
        "",
        *[f"- {item}" for item in result["limitations"]],
        "",
        "## 14. Unique next task",
        "",
        f"**{result['next_step_unique_recommendation']}**",
        "",
        "No alternate next task is recommended in this validation decision.",
        "",
        "## Appendix A — 100-ASIN cohort",
        "",
        _table(
            ("#", "ASIN", "Parent ASIN", "Page", "Rank", "Provider total", "Selection reason"),
            cohort_rows,
        ),
        "",
        "## Appendix B — Fingerprinted source files",
        "",
        _table(
            ("File", "SHA-256"),
            [(name, digest) for name, digest in fingerprints["start"]["source_files"].items()],
        ),
        "",
        "The complete relation lineage, precision items, keyword expressions, provider request/response references, exclusion log, and operation-level credit audit are preserved in the companion analysis and raw checkpoint JSON files.",
    ]
    return "\n".join(lines) + "\n"


__all__ = ("render_temporal_holdout_report",)
