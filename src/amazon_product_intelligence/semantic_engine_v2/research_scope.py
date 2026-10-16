"""Project upstream scope without inferring Route membership or sales allocation."""

from collections import Counter
from hashlib import sha256

from amazon_product_intelligence.contracts import canonical_json

from .models import RESEARCH_SCOPE_GROUPS, SemanticEngineV2Result


def build_research_scope_summary(result: SemanticEngineV2Result) -> dict | None:
    scoped = [item for item in result.listings if item.research_scope is not None]
    if not scoped:
        return None
    if len(scoped) != result.listing_count:
        raise ValueError("research scope must partition the complete semantic population")
    groups = []
    for group in RESEARCH_SCOPE_GROUPS:
        members = sorted(item.upstream_record_fingerprint for item in scoped
                         if item.research_scope.group == group)
        groups.append({"group": group, "listing_count": len(members),
                       "member_record_fingerprints": members,
                       "membership_fingerprint": sha256(canonical_json(members).encode()).hexdigest()})
    packaging = Counter(item.research_scope.packaging_status for item in scoped)
    core_count = sum(item["listing_count"] for item in groups if item["group"].startswith("CORE_"))
    return {
        "contract_version": "listing-research-scope-summary-v1",
        "semantic_result_id": result.result_id,
        "semantic_result_fingerprint": result.semantic_fingerprint,
        "dataset_fingerprint": result.upstream_dataset_fingerprint,
        "profile_fingerprint": result.profile_fingerprint,
        "policies": [{"policy_id": key, "policy_version": version} for key, version in sorted({
            (item.research_scope.policy_id, item.research_scope.policy_version) for item in scoped})],
        "listing_count": len(scoped), "core_listing_count": core_count,
        "groups": groups, "packaging_counts": dict(sorted(packaging.items())),
        "grain": "ONE_LISTING_ONE_MEMBERSHIP",
        "limitations": ["SCOPE_IS_NOT_ROUTE_ASSIGNMENT", "SOURCE_CLAIMS_NOT_VERIFIED_PRODUCT_TRUTH",
                        "NO_COMPONENT_COUNT_OR_SALES_ALLOCATION", "NOT_WHOLE_MARKET_COVERAGE"],
    }
