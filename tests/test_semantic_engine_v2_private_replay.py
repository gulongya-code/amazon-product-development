from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from scripts.run_semantic_engine_v2_private_replay import (
    OperatorReviewInput,
    _operator_gate_results,
    _operator_metrics,
    _operator_rows,
)


HEADERS = (
    "样本ID", "校准类目", "ASIN", "中文商品说明", "我的建议操作",
    "我的市场范围建议", "我的商品角色建议", "为什么这么判断（中文）",
    "你重点看什么", "你的决定", "你修改的市场范围",
    "你修改的商品角色", "你的备注", "最终市场范围", "最终商品角色",
)


def _write_review(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "01_中文辅助审核"
    sheet.append(HEADERS)
    rows = (
        ("淋浴置物架", "主商品", None, None, None, None),
        ("淋浴置物架", "主商品", "修改", "其他商品", None, None),
        ("狗狗便携饮水瓶", "主商品", "接受我的判断", "核心目标商品", None, "主商品"),
        ("吸尘器滤芯/过滤系统", "替换件", "修改", "目标周边配件/替换/耗材", "耗材", "耗材"),
        ("空气炸锅", "耗材", "修改", "目标周边配件/替换/耗材", "耗材", "耗材"),
        ("食品收纳盒套装", "主商品", "需要和我讨论", "相关目标商品", None, "待讨论"),
        ("食品收纳盒套装", "UNKNOWN", "接受我的判断", "相关目标商品", None, "UNKNOWN"),
        ("空气炸锅", "配件", "接受我的判断", "其他商品", None, "配件"),
    )
    for index, (category, proposed_role, decision, final_scope, override_role, final_role) in enumerate(rows):
        sheet.append((
            f"S-{index:02d}", category, f"SYNTHETIC-{index:03d}", None, None,
            final_scope, proposed_role, None, None, decision, None, override_role,
            None, final_scope, final_role,
        ))
    workbook.save(path)
    workbook.close()


def test_original_xlsx_projection_excludes_only_unscorable_inputs(tmp_path: Path) -> None:
    path = tmp_path / "operator-review.xlsx"
    _write_review(path)

    review = _operator_rows(path)

    assert review.source_format == "XLSX"
    assert review.raw_row_count == 8
    assert review.valid_decision_row_count == 7
    assert review.malformed_decision_excluded_count == 1
    assert review.malformed_relation_label_excluded_count == 1
    assert len(review.rows) == 7
    assert sum(row["expected_relation_role"] is not None for row in review.rows) == 6
    assert {row["expected_relation_role"] for row in review.rows} >= {
        "UNKNOWN", "REVIEW_REQUIRED",
    }
    assert review.consumable_lifecycle_label_count == 2
    consumables = [
        row for row in review.rows
        if row["expected_consumption_lifecycle"] == "CONSUMABLE"
    ]
    assert [row["expected_relation_role"] for row in consumables] == [
        "REPLACEMENT", "ACCESSORY",
    ]
    tags = [tag for row in review.rows for tag in row["boundary_tags"]]
    assert tags.count("NONPRIMARY") == 2
    assert tags.count("OBVIOUS_OTHER") == 2
    assert tags.count("USE_CASE_ONLY") == 2


def test_legacy_json_keeps_unknown_and_review_in_agreement_labels(tmp_path: Path) -> None:
    path = tmp_path / "operator-review.json"
    path.write_text(json.dumps([
        {
            "calibration_id": "CAL_SHOWER_CADDY",
            "listing_reference": "SYNTHETIC-UNKNOWN",
            "expected_relation_role": "UNKNOWN",
            "expected_primary_cohort": False,
            "boundary_tags": ["OBVIOUS_OTHER"],
        },
        {
            "calibration_id": "CAL_AIR_FRYER_MIXED",
            "listing_reference": "SYNTHETIC-REVIEW",
            "expected_relation_role": "REVIEW_REQUIRED",
            "expected_primary_cohort": False,
            "boundary_tags": ["USE_CASE_ONLY"],
        },
    ]), encoding="utf-8")

    review = _operator_rows(path)

    assert [row["expected_relation_role"] for row in review.rows] == [
        "UNKNOWN", "REVIEW_REQUIRED",
    ]


def _listing(
    reference: str, relation: str, *, eligible: bool, target_identity: bool | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        listing_reference=reference,
        product_role=SimpleNamespace(
            relation_role=SimpleNamespace(value=relation),
            consumption_lifecycle=SimpleNamespace(value="UNKNOWN"),
        ),
        product_identity=SimpleNamespace(is_target_identity=target_identity),
        market_cohort_eligibility=SimpleNamespace(
            eligible_for_primary_cohort=eligible,
        ),
        facts=(),
    )


def _review_rows() -> OperatorReviewInput:
    rows = (
        {
            "calibration_id": "CAL_AIR_FRYER_MIXED",
            "listing_reference": "OTHER",
            "expected_relation_role": "PRIMARY_PRODUCT",
            "expected_primary_cohort": False,
            "boundary_tags": ["OBVIOUS_OTHER"],
        },
        {
            "calibration_id": "CAL_AIR_FRYER_MIXED",
            "listing_reference": "ACCESSORY",
            "expected_relation_role": "ACCESSORY",
            "expected_primary_cohort": False,
            "boundary_tags": ["NONPRIMARY"],
        },
        {
            "calibration_id": "CAL_AIR_FRYER_MIXED",
            "listing_reference": "USE-CASE",
            "expected_relation_role": "UNKNOWN",
            "expected_primary_cohort": False,
            "boundary_tags": ["USE_CASE_ONLY"],
        },
    )
    return OperatorReviewInput(rows, 3, 3, 0, 0, 0, "JSON")


def test_operator_boundaries_have_denominators_and_use_target_identity() -> None:
    listings = (
        _listing("OTHER", "PRIMARY_PRODUCT", eligible=False, target_identity=False),
        _listing("ACCESSORY", "ACCESSORY", eligible=False, target_identity=True),
        _listing("USE-CASE", "UNKNOWN", eligible=False, target_identity=False),
    )
    metrics = _operator_metrics(
        {"CAL_AIR_FRYER_MIXED": SimpleNamespace(listings=listings)},
        _review_rows(),
    )

    assert metrics["obvious_other_sample_count"] == 1
    assert metrics["nonprimary_sample_count"] == 1
    assert metrics["use_case_only_sample_count"] == 1
    assert metrics["use_case_identity_include_count"] == 0
    gates = _operator_gate_results(metrics)
    assert gates["obvious_other_false_include_zero"]
    assert gates["nonprimary_leakage_zero"]
    assert gates["use_case_identity_include_zero"]

    use_case_target = tuple(
        _listing(item.listing_reference, item.product_role.relation_role.value,
                 eligible=item.market_cohort_eligibility.eligible_for_primary_cohort,
                 target_identity=True if item.listing_reference == "USE-CASE" else item.product_identity.is_target_identity)
        for item in listings
    )
    changed = _operator_metrics(
        {"CAL_AIR_FRYER_MIXED": SimpleNamespace(listings=use_case_target)},
        _review_rows(),
    )
    assert changed["use_case_identity_include_count"] == 1
    assert not _operator_gate_results(changed)["use_case_identity_include_zero"]


def test_product_boundary_gates_do_not_pass_without_review_samples() -> None:
    metrics = _operator_metrics({}, OperatorReviewInput((), 0, 0, 0, 0, 0, "NONE"))
    gates = _operator_gate_results(metrics)
    assert not gates["obvious_other_false_include_zero"]
    assert not gates["nonprimary_leakage_zero"]
    assert not gates["use_case_identity_include_zero"]
