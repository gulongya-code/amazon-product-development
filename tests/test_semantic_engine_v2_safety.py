from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CohortEligibilityState,
    EvidenceRelationshipState,
    SemanticEngineV2Error,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from amazon_product_intelligence.sellersprite_import.models import (
    EvidenceSemantics,
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
    NormalizedField,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_PROFILE = ROOT / "config/category_semantic_profiles/dog_water_bottles.v1_1.json"
TITLE_HEADER = "\u5546\u54c1\u6807\u9898"


def _write_profile(tmp_path: Path, payload: dict[str, object]) -> Path:
    target = tmp_path / "profile.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def _dataset(category: str, title: str) -> GovernedMarketDatasetV1:
    field = NormalizedField(
        header=TITLE_HEADER,
        requirement="OPTIONAL",
        value_type="TEXT",
        value=title,
        import_status=ImportValueStatus.NORMALIZED,
        presence_status=PresenceStatus.PRESENT,
        normalization_status=NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.CONFIRMED,
        evidence_semantics=EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE,
    )
    record = ListingRecordV1(
        asin="B000000001",
        parent_asin=None,
        source_row=2,
        fields=(field,),
        record_fingerprint="record-fingerprint-B000000001",
    )
    return GovernedMarketDatasetV1(
        dataset_id="gmdv1-safety-synthetic",
        semantic_fingerprint="upstream-semantic-fingerprint",
        source_type="CSV",
        source_basename="synthetic.csv",
        source_file_sha256="0" * 64,
        imported_at="2026-08-29T00:00:00+00:00",
        marketplace="US",
        category=category,
        observed_date="2026-08-29",
        observed_date_status="KNOWN",
        source_sheet=None,
        header_row=1,
        source_row_count=1,
        accepted_listing_count=1,
        unique_asin_count=1,
        duplicate_row_count=0,
        rejected_row_count=0,
        quarantined_row_count=0,
        missing_core_field_summary=(),
        unmapped_headers=(),
        out_of_scope_headers=(),
        records=(record,),
        row_outcomes=(),
    )


def _conflict_profile_payload(
    *, multi_value: bool, conflict_values: list[str],
) -> dict[str, object]:
    payload = json.loads(BASE_PROFILE.read_text(encoding="utf-8"))
    payload["source_policies"].append({
        "policy_id": "s2-test-route-critical-policy",
        "role": "COMPATIBILITY",
        "dimension": "s2_test_route_dimension",
        "primary_sources": ["LISTING_TITLE"],
        "corroborating_sources": [],
        "fallback_sources": [],
        "forbidden_sources": [],
        "exact_specification": False,
        "multi_value": multi_value,
        "relevance": "CORE",
        "route_critical": True,
    })
    for suffix in ("alpha", "beta", "gamma"):
        payload["fact_rules"].append({
            "rule_id": f"s2-test-route-fact-{suffix}",
            "role": "COMPATIBILITY",
            "dimension": "s2_test_route_dimension",
            "sources": ["LISTING_TITLE"],
            "source_keys": [],
            "match_phrases": [f"s2 {suffix} signal"],
            "exclusions": [],
            "value_mode": "FIXED",
            "normalized_value": suffix,
            "quantity_kind": None,
            "semantic_scope": None,
            "quantity_subtype": None,
            "confidence": "HIGH",
        })
    payload["route_critical_conflict_rules"].append({
        "rule_id": "s2-test-route-conflict",
        "dimension": "s2_test_route_dimension",
        "values": conflict_values,
    })
    payload["identity_rules"].append({
        "rule_id": "s2-test-target-identity",
        "sources": ["LISTING_TITLE"],
        "phrases": ["s2 synthetic target"],
        "exclusions": [],
        "identity": "s2 synthetic target",
        "is_target": True,
        "priority": 0,
    })
    payload["relation_rules"].append({
        "rule_id": "s2-test-primary-relation",
        "sources": ["LISTING_TITLE"],
        "phrases": ["s2 synthetic target"],
        "exclusions": [],
        "result": "PRIMARY_PRODUCT",
        "priority": 0,
    })
    payload["cohort_policy"]["target_identity_values"].append("s2 synthetic target")
    return payload


def _conflict_result(
    tmp_path: Path,
    *,
    multi_value: bool,
    conflict_values: list[str],
    title_signals: str,
):
    payload = _conflict_profile_payload(
        multi_value=multi_value,
        conflict_values=conflict_values,
    )
    profile = load_category_semantic_profile(_write_profile(tmp_path, payload))
    return build_semantic_engine_v2_result(
        _dataset(
            payload["category_scope"],
            f"S2 Synthetic Target {title_signals}",
        ),
        profile=profile,
    )


def _route_relationship(result):
    return next(
        item for item in result.listings[0].relationships
        if item.dimension == "s2_test_route_dimension"
    )


def test_non_identity_route_critical_conflict_blocks_cohort_and_counts_review(
    tmp_path: Path,
) -> None:
    result = _conflict_result(
        tmp_path,
        multi_value=True,
        conflict_values=["alpha", "beta"],
        title_signals="S2 Alpha Signal S2 Beta Signal",
    )

    listing = result.listings[0]
    relationship = _route_relationship(result)
    assert relationship.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
    assert listing.market_cohort_eligibility.state is CohortEligibilityState.REVIEW_REQUIRED
    assert not listing.market_cohort_eligibility.eligible_for_primary_cohort
    assert listing.market_cohort_eligibility.reason_codes == (
        "ROUTE_CRITICAL_CONFLICT_REQUIRES_REVIEW",
    )
    assert set(relationship.fact_ids) <= set(
        listing.market_cohort_eligibility.evidence_fact_ids
    )
    assert listing.review_reason_codes == (
        "ROUTE_CRITICAL_CONFLICT:s2_test_route_dimension",
    )
    assert result.review_listing_count == 1


def test_explicit_conflict_set_does_not_capture_unlisted_multi_value(
    tmp_path: Path,
) -> None:
    result = _conflict_result(
        tmp_path,
        multi_value=True,
        conflict_values=["alpha", "beta"],
        title_signals="S2 Alpha Signal S2 Gamma Signal",
    )

    listing = result.listings[0]
    assert _route_relationship(result).state is EvidenceRelationshipState.COMPATIBLE_MULTI_VALUE
    assert listing.market_cohort_eligibility.state is CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
    assert listing.review_reason_codes == ()
    assert result.review_listing_count == 0


def test_empty_conflict_values_do_not_declare_multi_value_conflict(
    tmp_path: Path,
) -> None:
    result = _conflict_result(
        tmp_path,
        multi_value=True,
        conflict_values=[],
        title_signals="S2 Alpha Signal S2 Beta Signal",
    )

    listing = result.listings[0]
    assert _route_relationship(result).state is EvidenceRelationshipState.COMPATIBLE_MULTI_VALUE
    assert listing.market_cohort_eligibility.state is CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
    assert listing.review_reason_codes == ()
    assert result.review_listing_count == 0


def test_empty_conflict_values_elevate_existing_single_value_policy_conflict(
    tmp_path: Path,
) -> None:
    result = _conflict_result(
        tmp_path,
        multi_value=False,
        conflict_values=[],
        title_signals="S2 Alpha Signal S2 Beta Signal",
    )

    listing = result.listings[0]
    assert _route_relationship(result).state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
    assert listing.market_cohort_eligibility.state is CohortEligibilityState.REVIEW_REQUIRED
    assert listing.review_reason_codes == (
        "ROUTE_CRITICAL_CONFLICT:s2_test_route_dimension",
    )
    assert result.review_listing_count == 1


def test_single_value_conflict_set_is_rejected(tmp_path: Path) -> None:
    payload = _conflict_profile_payload(
        multi_value=True,
        conflict_values=["alpha"],
    )

    with pytest.raises(
        SemanticEngineV2Error,
        match="values must be empty or contain at least two values",
    ):
        load_category_semantic_profile(_write_profile(tmp_path, payload))


def test_provider_category_context_cannot_author_product_identity(
    tmp_path: Path,
) -> None:
    payload = json.loads(BASE_PROFILE.read_text(encoding="utf-8"))
    identity_rule = next(
        item for item in payload["identity_rules"]
        if item["rule_id"] == "dog-identity-target"
    )
    identity_rule["sources"] = ["PROVIDER_CATEGORY_CONTEXT"]

    with pytest.raises(
        SemanticEngineV2Error,
        match=r"dog-identity-target uses source outside product_identity policy",
    ):
        load_category_semantic_profile(_write_profile(tmp_path, payload))


def test_dimension_policy_forbidden_source_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(BASE_PROFILE.read_text(encoding="utf-8"))
    quantity_rule = next(
        item for item in payload["fact_rules"]
        if item["rule_id"] == "dog-package-count"
    )
    quantity_rule["sources"] = ["LISTING_TITLE"]

    with pytest.raises(
        SemanticEngineV2Error,
        match=r"dog-package-count uses forbidden source for package_count",
    ):
        load_category_semantic_profile(_write_profile(tmp_path, payload))


@pytest.mark.parametrize(
    ("collection", "rule_id", "dimension"),
    (
        ("fact_rules", "dog-operation-title", "operation_mechanism"),
        ("relation_rules", "dog-relation-primary", "relation_role"),
        ("lifecycle_rules", "dog-lifecycle-durable", "consumption_lifecycle"),
    ),
)
def test_rule_source_allowed_in_another_context_cannot_cross_dimension_policy(
    tmp_path: Path, collection: str, rule_id: str, dimension: str,
) -> None:
    payload = json.loads(BASE_PROFILE.read_text(encoding="utf-8"))
    rule = next(
        item for item in payload[collection] if item["rule_id"] == rule_id
    )
    rule["sources"] = ["AUTHORIZED_SKU"]

    with pytest.raises(
        SemanticEngineV2Error,
        match=rf"{rule_id} uses source outside {dimension} policy",
    ):
        load_category_semantic_profile(_write_profile(tmp_path, payload))


def test_measurement_rule_without_exact_quantity_scope_authorization_fails_closed(
    tmp_path: Path,
) -> None:
    payload = json.loads(BASE_PROFILE.read_text(encoding="utf-8"))
    measurement_rule = next(
        item for item in payload["fact_rules"]
        if item["value_mode"] == "MEASUREMENT"
    )
    measurement_rule["source_keys"] = ["s2 unauthorized measurement source"]

    with pytest.raises(
        SemanticEngineV2Error,
        match="requires exactly one explicit quantity_scope_rules authorization",
    ):
        load_category_semantic_profile(_write_profile(tmp_path, payload))


def test_ambiguous_quantity_scope_authorization_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(BASE_PROFILE.read_text(encoding="utf-8"))
    measurement_rule = next(
        item for item in payload["fact_rules"]
        if item["value_mode"] == "MEASUREMENT"
    )
    authorization = next(
        item for item in payload["quantity_scope_rules"]
        if (
            set(item["source_keys"]) == set(measurement_rule["source_keys"])
            and item["quantity_kind"] == measurement_rule["quantity_kind"]
            and item["semantic_scope"] == measurement_rule["semantic_scope"]
            and item["quantity_subtype"] == measurement_rule["quantity_subtype"]
        )
    )
    duplicate = deepcopy(authorization)
    duplicate["rule_id"] = "s2-test-duplicate-quantity-authorization"
    payload["quantity_scope_rules"].append(duplicate)

    with pytest.raises(
        SemanticEngineV2Error,
        match="requires exactly one explicit quantity_scope_rules authorization",
    ):
        load_category_semantic_profile(_write_profile(tmp_path, payload))
