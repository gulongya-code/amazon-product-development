"""Markdown report renderer for the organic discovery pilot."""

from __future__ import annotations

from .pilot import OrganicDiscoveryPilotResult


def _cell(value: object) -> str:
    return str(value if value is not None else "UNKNOWN").replace("|", "\\|").replace("\n", " ")


def render_organic_discovery_report(result: OrganicDiscoveryPilotResult) -> str:
    corpus = result.discovery.corpus
    classification = result.classification_summary()
    clusters = result.cluster_operational_metrics()
    criteria = dict(result.success_criteria)
    lines = [
        "# ORGANIC BUYER NEED DISCOVERY PILOT V0.1",
        "",
        "Status: **COMPLETE**" if criteria["organic_discovery_success"] else "Status: **PARTIAL**",
        "",
        f"- Baseline commit: `{result.baseline_commit}`",
        f"- Run ID: `{result.run_id}`",
        "- Marketplace: `US`",
        "- Cohort: Pet Supplies > Dog Travel Water Bottles",
        "- Discovery origin: `ASIN_REVERSE_RETURNED`",
        "- Discovery role: `DISCOVERED_CANDIDATE`",
        "- Human seeded: `false`",
        "",
        "## 1. ASIN 样本",
        "",
        f"确定性策略：{result.cohort.strategy}。Provider cohort total={_cell(result.cohort.provider_total)}。",
        "TASK-SP-031 报告只保存了 cohort 规则和统计，没有保存200个 ASIN identity 列表；因此本次按相同 `dog water bottle / last7days / traffic desc` 合同重新获取当前 Top 20。Provider total 已从 SP-031 的658变为本次的662，本样本不是历史响应的 byte-for-byte 子集。",
        "",
        "| # | ASIN |",
        "|---:|---|",
    ]
    lines.extend(f"| {index} | `{asin}` |" for index, asin in enumerate(result.cohort.asins, 1))
    lines.extend(
        [
            "",
            "## 2. API 调用与 Credits",
            "",
            f"调用前预计 credits：**{result.credit_plan.estimated_total_credits}**；gate：**{result.credit_plan.gate_credits}**。",
            f"完成执行请求：**{result.completed_run_request_count}**；前置失败执行请求：**{result.prior_live_request_count}**；任务累计请求：**{result.request_count}**。",
            f"完成执行已知 credits：**{result.completed_run_known_credits}**；前置计入 credits：**{result.prior_live_credits_accounted}**；任务累计 accounted credits：**{result.known_credits}**；完成执行中 credit 未回传调用：**{result.unknown_credit_call_count}**。",
            (f"前置执行说明：{result.prior_live_usage_note}" if result.prior_live_usage_note else "前置执行说明：无。"),
            "",
            "| # | Operation | ASIN | Page | Returned | Provider total | X-Cost-Credits | Status |",
            "|---:|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for index, call in enumerate(result.provider_calls, 1):
        lines.append(
            f"| {index} | `{call.operation}` | {_cell(call.source_asin)} | {_cell(call.page)} | "
            f"{call.returned_count} | {_cell(call.provider_total)} | {_cell(call.x_cost_credits or call.cost_credits)} | {call.status.value} |"
        )
    lines.extend(
        [
            "",
            "## 3. Keyword Corpus",
            "",
            f"- Raw ASIN-keyword relations: **{corpus.asin_keyword_relation_count}**",
            f"- Unique keywords: **{corpus.unique_keyword_count}**",
            f"- Cross-relation duplicates: **{corpus.duplicate_keyword_count}**",
            f"- ASINs with returned keyword evidence: **{corpus.source_asin_count}/{len(result.cohort.asins)}**",
            f"- First-page-only ASINs: **{corpus.coverage.first_page_only_asin_count}**",
            f"- Traffic availability: `{dict(corpus.traffic_availability)}`",
            "",
            "> Keyword frequency and ASIN coverage are discovery coverage only. They are not Search Demand Share. Provider traffic is not Search Volume.",
            "",
            "## 4. Top 50 discovered search terms",
            "",
            "| # | Search term | ASIN coverage | Coverage share | Provider traffic support | Best organic rank |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for index, item in enumerate(corpus.top_keywords[:50], 1):
        lines.append(
            f"| {index} | {_cell(item.keyword_identity.raw_text)} | {item.asin_coverage_count} | "
            f"{item.asin_coverage_share} | {_cell(item.provider_traffic_sum)} | {_cell(item.best_organic_rank)} |"
        )
    lines.extend(
        [
            "",
            "## 5. Buyer Need 分类",
            "",
            f"- Matched Buyer Need objects: **{classification['matched_buyer_need_count']}**",
            f"- Matched keyword relations: **{classification['matched_relation_count']}**",
            f"- UNKNOWN keyword relations: **{classification['unknown_relation_count']}**",
            f"- UNKNOWN ratio: **{classification['unknown_relation_share']}**",
            f"- Need type distribution: `{classification['buyer_need_type_distribution']}`",
            "",
            "Taxonomy 未识别的 provider-returned term 保持 UNKNOWN；本任务没有修改 Taxonomy 或规则以提高 Recall。",
            "",
            "## 6. Semantic Clusters / Top Organic Buyer Needs",
            "",
            "| # | Cluster | Member count | Keyword relations | Source ASINs | ASIN coverage share |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for index, cluster in enumerate(clusters, 1):
        lines.append(
            f"| {index} | {_cell(cluster['cluster_label'])} | {cluster['cluster_member_count']} | "
            f"{cluster['discovered_keyword_relation_count']} | {cluster['source_asin_count']} | "
            f"{cluster['asin_coverage_share']} |"
        )
    lines.extend(
        [
            "",
            "每个 cluster 的 `need_id` 均通过 `buyer_need_links` 回溯到 discovery record；record 继续回溯到 source ASIN、query execution、raw response 和 `searchTerm`。",
            "",
            "## 7. Buyer Need Map",
            "",
            f"- Map ID: `{result.buyer_need_map.map_id}`",
            f"- Cluster count: **{result.buyer_need_map.coverage.cluster_count}**",
            f"- Source evidence count: **{result.buyer_need_map.coverage.source_evidence_count}**",
            "- Search Demand Share: **UNKNOWN**（没有完整 search population denominator）",
            "- Review Mention Share: **UNKNOWN**",
            "- Sales/Revenue associated shares: **UNKNOWN**",
            "",
            "本报告仅额外发布 Discovered Keyword Count、ASIN Coverage Count/Share、Cluster Member Count 与流量证据可用性。",
            "",
            "## 8. keyword_info validation enrichment",
            "",
            "Top 20 由 ASIN coverage、provider traffic support、organic rank 和稳定文本排序确定。`keyword_info` 只做 enrichment，不改变 `query_origin=ASIN_REVERSE_RETURNED`。",
            "",
            "| # | Keyword | Search volume | ABA rank | CPC | Difficulty | Status |",
            "|---:|---|---:|---:|---:|---:|---|",
        ]
    )
    for index, item in enumerate(result.keyword_validation, 1):
        lines.append(
            f"| {index} | {_cell(item.keyword_text)} | {_cell(item.search_volume)} | {_cell(item.aba_rank)} | "
            f"{_cell(item.cpc)} | {_cell(item.difficulty)} | {item.availability_status} |"
        )
    lines.extend(
        [
            "",
            "## 9. 新发现需求表达",
            "",
        ]
    )
    examples = criteria.get("new_expression_examples", [])
    if examples:
        lines.extend(f"- `{_cell(item)}`" for item in examples)
    else:
        lines.append("- 本样本没有找到与 SP-031 23 个 preset Query 完全不同且被当前 Taxonomy 匹配的新表达。")
    lines.extend(
        [
            "",
            "## 10. Provenance 与成功标准",
            "",
            "| Criterion | Result |",
            "|---|---|",
            f"| Discovery Query 不是 HUMAN_PRESET | {'PASS' if criteria['criterion_1_not_human_preset'] else 'FAIL'} |",
            f"| 至少一个 Provider-returned keyword | {'PASS' if criteria['criterion_2_provider_returned_keyword'] else 'FAIL'} |",
            f"| ASIN → request → response → searchTerm | {'PASS' if criteria['criterion_3_asin_request_response_term_lineage'] else 'FAIL'} |",
            f"| Cluster → need_id → discovered keyword | {'PASS' if criteria['criterion_4_cluster_to_discovered_keyword_lineage'] else 'FAIL'} |",
            f"| 至少一个新需求表达 | {'PASS' if criteria['criterion_5_new_expression_vs_sp031_presets'] else 'NOT OBSERVED'} |",
            "",
            f"Organic Buyer Need Discovery success: **{'YES' if criteria['organic_discovery_success'] else 'PARTIAL'}**",
            "",
            "## 11. 数据限制",
            "",
            "- 样本是 `dog water bottle` keyword cohort 的 top-traffic 20 ASIN，不是 Browse Node census。",
            "- SP-031 未持久化原200个 ASIN identity；本次为相同合同的当前确定性重建，Provider total 由658变为662。",
            "- 每个 ASIN 仅获取 reverse keyword 第一页、最多20条；不能代表完整 ASIN keyword population。",
            "- Provider traffic 单位、方法和精确窗口未确认，不能替代 Search Volume。",
            "- `keyword_info` 只覆盖 Top 20 discovered terms，不能作为完整 denominator。",
            "- Taxonomy Recall 未在本任务校准；UNKNOWN 不代表没有 Buyer Need。",
            "- 未使用 Review、Bullet、Q&A 或 AI/LLM/Embedding。",
            "",
            "## 12. 下一阶段建议",
            "",
            "1. 先复核本次 Top UNKNOWN search terms，再单独立项做 Taxonomy coverage audit；不要在本任务内改规则。",
            "2. 若 lineage 和 credits 稳定，再扩大到100 ASIN；继续设置明确 credits gate。",
            "3. 增加 Review/Bullet evidence 后进行 source-mixed discovery，但保持 source origin 分离。",
            "4. 获得 Browse Node/category cohort denominator 后，再讨论类目覆盖和 Demand Share。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ("render_organic_discovery_report",)
