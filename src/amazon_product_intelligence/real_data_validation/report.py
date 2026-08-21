"""Markdown rendering for one completed Real Data Validation V0.1 run."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .live_pipeline import RealDataPipelineResult


def _cell(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_validation_report(
    result: RealDataPipelineResult,
    *,
    baseline_commit: str,
) -> str:
    run = result.validation_run
    provider = result.provider_summary
    coverage_rows = [
        (
            item.stage,
            item.input_count,
            item.output_count,
            item.failure_count,
            item.unknown_count,
            f"{float(item.coverage) * 100:.2f}%",
            f"{float(item.unknown_rate) * 100:.2f}%",
            item.status.value,
        )
        for item in run.coverage
    ]
    attribute_rows = [
        (
            item.dimension,
            item.correct_count,
            item.error_count,
            item.unknown_count,
            f"{float(item.accuracy) * 100:.2f}%",
            f"{float(item.known_coverage) * 100:.2f}%",
        )
        for item in result.attribute_accuracy.dimensions
    ]
    category_rows = []
    for dimension, summary in result.category_map_review["attribute_distributions"].items():
        rendered = ", ".join(
            f"{item['value']} ({item['asin_count']}, {float(item['asin_share']) * 100:.1f}%)"
            for item in summary["top_values"][:5]
        )
        category_rows.append(
            (dimension, summary["known"], summary["unknown"], summary["coverage"], rendered or "UNKNOWN")
        )
    buyer_rows = [
        (
            index,
            item["cluster_label"],
            item["search_demand_share"],
            item["demand_status"],
            item["confidence"],
            ", ".join(item["sources"]),
            item["judgement"],
        )
        for index, item in enumerate(result.buyer_need_review[:20], start=1)
    ]
    gap_rows = [
        (
            index,
            item["cluster_label"],
            item["gap_type"],
            item["gap_strength"],
            item["confidence"],
            item["judgement"],
            item["reason"],
        )
        for index, item in enumerate(result.gap_review[:20], start=1)
    ]
    ranking_rows = [
        (
            item["rank"],
            item["candidate"],
            item["score"],
            item["confidence"],
            item["candidate_status"],
            item["judgement"],
            item["reason"],
        )
        for item in result.opportunity_ranking_review
    ]
    issue_rows = [
        (
            index,
            item.category.value,
            item.severity.value,
            item.title,
            ", ".join(item.affected_modules),
            item.recommended_fix,
        )
        for index, item in enumerate(run.issue_log.issues, start=1)
    ]
    price_band = result.category_map_review.get("price_band")
    price_text = "UNKNOWN" if price_band is None else ", ".join(
        f"{key}={value}" for key, value in price_band.items()
    )
    return f"""# REAL DATA VALIDATION REPORT V0.1

Status: COMPLETE  
Task: TASK-SP-031 Real Data Validation v0.1  
Baseline commit: `{baseline_commit}`  
Validation run: `{run.run_id}`

## 1. 测试类目

- Category: {run.category_scope.category}
- Subcategory: {run.category_scope.subcategory}
- Marketplace: {run.marketplace}
- Cohort query: `{run.category_scope.cohort_query}`
- Inclusion rule: {run.category_scope.inclusion_rule}
- Analysis window: `{run.analysis_window.period_label}`
- Retrieved at: `{run.analysis_window.retrieved_at}`

该子类目属于中等复杂度 Pet Supplies：存在容量、材质、便携、漏水防护、包装数量等可解释属性，同时避免 Fashion/Electronics 的高复杂度边界。

## 2. 数据来源与规模

数据来自 [XiYou OpenAPI V2](https://openapi-doc.xydc.com/)，使用显式只读 live gate。未保存 API Key 或完整原始响应。

- 请求商品数: {provider['cohort_requested']}
- 返回唯一 ASIN: {provider['cohort_returned']}
- Provider total: {provider['provider_total']}
- 商品详情行: {provider['product_rows_returned']}
- Buyer Need 查询: {provider['need_queries_returned']}/{provider['need_queries_requested']}
- Provider 请求数: {provider['request_count']}
- Credits: {provider['cost_credits']}

## 3. Pipeline 运行结果

{_table(('阶段', '输入', '输出', '失败', 'UNKNOWN', 'Coverage', 'UNKNOWN %', '状态'), coverage_rows)}

完整链路已经执行至 Evidence-based Opportunity Score。所有 UNKNOWN 均保持为 UNKNOWN，没有填 0；相同 Candidate 与 Policy 的即时重放结果一致。

## 4. Coverage 分析

重点覆盖结论：

- Attribute coverage 由标题可验证字段决定；缺少结构化 catalog ground truth。
- Buyer Need 仅有 Search Term 来源；Review/Bullet population 为 UNKNOWN。
- Competition 可保留商品/关键词关系与评论门槛证据；Brand concentration 为 UNKNOWN。
- Economic Evidence 有 observed price；sales/revenue 为 UNKNOWN。

## 5. Attribute 验证

Sampling: {result.attribute_accuracy.sampling_method}  
Evidence basis: {result.attribute_accuracy.evidence_basis}

{_table(('维度', '正确', '错误', 'UNKNOWN', '已知值准确率', '已知覆盖率'), attribute_rows)}

这里的“正确”表示确认 assertion 与真实 provider title 文本一致，不等同于独立 Amazon catalog ground truth。UNKNOWN 不进入准确率分母。

## 6. Category Product Map 验证

Overall judgement: **{result.category_map_review['judgement']}**  
Reason: {result.category_map_review['reason']}

{_table(('维度', 'Known', 'UNKNOWN', 'Coverage', 'Top values'), category_rows)}

- Combination segments: {result.category_map_review['combination_segment_count']}
- Observed price band: {price_text}
- Price ownership note: {result.category_map_review['price_band_source']}

## 7. Buyer Need 验证

{_table(('Rank', 'Buyer Need', 'Search share', '状态', 'Confidence', '来源', '人工评价'), buyer_rows)}

这些需求都由真实 Search Term 明示触发；由于 Review 与 Bullet 证据缺失，评价最多为 POSSIBLE，不升级为已确认消费者共识。

## 8. Supply/Demand Gap 验证

{_table(('Rank', 'Need', 'Gap type', 'Strength', 'Confidence', '人工评价', '理由'), gap_rows)}

VALID_GAP 只用于 `HIGH_DEMAND_LOW_SUPPLY` 且上游证据可计算的结果；其余明确标为 FALSE_GAP 或 INSUFFICIENT_DATA。

## 9. Opportunity Score 验证

{_table(('Rank', 'Candidate', 'Score', 'Confidence', 'Candidate status', '人工评价', 'Reason/Risk'), ranking_rows)}

- Policy version: `{result.opportunity_ranking_review[0]['policy_version'] if result.opportunity_ranking_review else 'UNKNOWN'}`
- Score 与 Confidence 分离；LOW/UNKNOWN Confidence 不会被改写成 0 分。
- 排名只比较同一验证 cohort 内的 evidence aggregation，不是自动选品或利润预测。

## 10. 发现问题

{_table(('#', '分类', '严重度', '问题', '影响模块', '建议修复'), issue_rows)}

## 11. 限制

""" + "\n".join(f"- {item}" for item in run.limitations) + """

## 12. 下一阶段优化建议

1. 先补齐 audited Amazon browse-node/category inventory，避免以单关键词 cohort 代表完整类目。
2. 补齐 bullet、review text、brand 与 structured attribute 数据源，再做 Attribute/Buyer Need 独立 ground-truth calibration。
3. 补齐 sales/revenue evidence；继续保持缺失经济数据 UNKNOWN，不惩罚也不奖励。
4. TASK-SP-032 只针对本报告记录的问题做 calibration proposal；权重、taxonomy、gap threshold 的任何变化必须另起版本并回放本次 validation snapshot。
5. 建立第二类目对照（Kitchen 或 Home Improvement），检验结论是否跨类目稳定。

## 禁止范围审计

- 未修改 Opportunity Score 公式或 Policy。
- 未修改 Attribute Extraction Rules。
- 未修改 Buyer Need Taxonomy。
- 未修改 Gap Threshold。
- 未修改 Foundation/Core Model。
- 未新增 UI、Excel、利润预测或 AI 自动推荐。
"""


__all__ = ("render_validation_report",)
