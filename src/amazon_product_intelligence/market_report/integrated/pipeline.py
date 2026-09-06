"""Provider-neutral production orchestration for Route-aware Market Reports."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
    CompetitionIntelligenceSnapshotV0_1,
)
from amazon_product_intelligence.competition_intelligence.models import bundle_fingerprint
from amazon_product_intelligence.contracts import CanonicalEvidenceBundle
from amazon_product_intelligence.opportunity_intelligence import (
    OpportunityIntelligenceBuilderV0_1,
    OpportunityIntelligenceRequest,
    OpportunityIntelligenceSnapshotV0_1,
)
from amazon_product_intelligence.route_discovery_input import (
    RouteDiscoveryInputContext,
    RouteDiscoveryInputPackage,
    build_route_discovery_input,
)
from amazon_product_intelligence.route_discovery_v2 import (
    RouteDiscoveryV2Config,
    RouteDiscoveryV2Result,
    build_route_discovery_v2,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CategorySemanticProfileV1_1,
    SemanticEngineV2Result,
    build_semantic_engine_v2_result,
)

from .builder import build_route_aware_market_report
from .models import IntegratedMarketReport


INTEGRATED_MARKET_REPORT_PIPELINE_VERSION = (
    "provider-neutral-route-market-report-pipeline-v1.0"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class IntegratedMarketIntelligenceResult:
    """All typed stages required to audit one integrated report run."""

    route_input: RouteDiscoveryInputPackage
    semantic_result: SemanticEngineV2Result
    route_result: RouteDiscoveryV2Result
    competition_result: CompetitionIntelligenceSnapshotV0_1
    opportunity_result: OpportunityIntelligenceSnapshotV0_1
    market_report: IntegratedMarketReport
    pipeline_version: str = INTEGRATED_MARKET_REPORT_PIPELINE_VERSION


def run_final_market_intelligence(
    *,
    canonical_bundles: tuple[CanonicalEvidenceBundle, ...],
    input_context: RouteDiscoveryInputContext,
    semantic_profile: CategorySemanticProfileV1_1,
    route_config: RouteDiscoveryV2Config,
    generated_at: str,
) -> IntegratedMarketIntelligenceResult:
    """Run the accepted engines from Canonical evidence without provider selection."""

    if not canonical_bundles:
        raise ValueError("canonical_bundles must not be empty")
    fingerprints = tuple(sorted(bundle_fingerprint(item) for item in canonical_bundles))
    route_input = build_route_discovery_input(
        canonical_bundles,
        context=input_context,
    )
    semantic = build_semantic_engine_v2_result(
        route_input.dataset,
        profile=semantic_profile,
    )
    routes = build_route_discovery_v2(
        route_input.dataset,
        semantic,
        profile=semantic_profile,
        config=route_config,
    )
    competition = CompetitionIntelligenceBuilderV0_1().build(
        CompetitionIntelligenceRequest(canonical_bundles=canonical_bundles)
    )
    opportunity = OpportunityIntelligenceBuilderV0_1().build(
        OpportunityIntelligenceRequest(canonical_bundles=canonical_bundles)
    )
    report = build_route_aware_market_report(
        generated_at=generated_at,
        canonical_bundle_fingerprints=fingerprints,
        route_input=route_input,
        semantic_result=semantic,
        route_result=routes,
        competition_result=competition,
        opportunity_result=opportunity,
    )
    return IntegratedMarketIntelligenceResult(
        route_input=route_input,
        semantic_result=semantic,
        route_result=routes,
        competition_result=competition,
        opportunity_result=opportunity,
        market_report=report,
    )


__all__ = (
    "INTEGRATED_MARKET_REPORT_PIPELINE_VERSION",
    "IntegratedMarketIntelligenceResult",
    "run_final_market_intelligence",
)
