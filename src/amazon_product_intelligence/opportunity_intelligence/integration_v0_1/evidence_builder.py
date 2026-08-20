"""Build an immutable Opportunity Evidence Bundle from existing snapshots only."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.buyer_need_map import (
    DemandMetricConfidenceLevel,
    DemandMetricStatus,
    DemandMetricType,
)
from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_analysis import MarketMetricStatus
from amazon_product_intelligence.product_attribute_extraction import (
    AttributeDimension,
    AttributeState,
)
from amazon_product_intelligence.supply_demand_gap import (
    GapConfidenceLevel,
    GapSignalStatus,
    GapType,
    SupplyMetricType,
)

from .models import (
    CompetitionEvidence,
    CompetitionLevel,
    CompetitionSignalEvidence,
    CompetitionSignalName,
    DemandEvidence,
    EconomicEvidence,
    OpportunityCandidateRequest,
    OpportunityConfidence,
    OpportunityEvidenceBundle,
    OpportunityEvidenceReference,
    OpportunityEvidenceSource,
    OpportunityEvidenceStatus,
    OpportunityGapEvidence,
    OpportunityMetricEvidence,
    SupplyEvidence,
)


_CONFIDENCE_RANK = {
    OpportunityConfidence.LOW: 1,
    OpportunityConfidence.MEDIUM: 2,
    OpportunityConfidence.HIGH: 3,
    OpportunityConfidence.UNKNOWN: 0,
}


@dataclass(frozen=True, slots=True)
class _ReferenceIndex:
    buyer_need_map: OpportunityEvidenceReference
    category_product_map: OpportunityEvidenceReference
    supply_demand_gap: OpportunityEvidenceReference
    competition_intelligence: OpportunityEvidenceReference
    economic: OpportunityEvidenceReference
    profile_references: tuple[OpportunityEvidenceReference, ...]

    @property
    def all(self) -> tuple[OpportunityEvidenceReference, ...]:
        return (
            self.buyer_need_map,
            self.category_product_map,
            self.supply_demand_gap,
            self.competition_intelligence,
            self.economic,
            *self.profile_references,
        )


def _reference(
    *,
    source: OpportunityEvidenceSource,
    source_id: str,
    record_ids: tuple[str, ...],
    missing: bool = False,
    limitations: tuple[str, ...] = (),
) -> OpportunityEvidenceReference:
    material = {
        "source": source,
        "source_id": source_id,
        "record_ids": tuple(sorted(record_ids)),
        "missing": missing,
        "limitations": tuple(sorted(limitations)),
    }
    return OpportunityEvidenceReference(
        reference_id=deterministic_id("opportunity-evidence-reference", material),
        **material,
    )


def _metric(
    *,
    metric_name: str,
    status: OpportunityEvidenceStatus,
    value: str | None,
    source_record_ids: tuple[str, ...],
    source_reference_ids: tuple[str, ...],
    limitations: tuple[str, ...] = (),
) -> OpportunityMetricEvidence:
    material = {
        "metric_name": metric_name,
        "status": status,
        "value": value,
        "source_record_ids": tuple(sorted(source_record_ids)),
        "source_reference_ids": tuple(sorted(source_reference_ids)),
        "limitations": tuple(sorted(limitations)),
    }
    return OpportunityMetricEvidence(
        evidence_id=deterministic_id("opportunity-metric-evidence", material),
        **material,
    )


def _competition_signal(
    *,
    signal_name: CompetitionSignalName,
    status: OpportunityEvidenceStatus,
    level: CompetitionLevel,
    source_record_ids: tuple[str, ...],
    source_reference_ids: tuple[str, ...],
    limitations: tuple[str, ...] = (),
) -> CompetitionSignalEvidence:
    material = {
        "signal_name": signal_name,
        "status": status,
        "level": level,
        "source_record_ids": tuple(sorted(source_record_ids)),
        "source_reference_ids": tuple(sorted(source_reference_ids)),
        "limitations": tuple(sorted(limitations)),
    }
    return CompetitionSignalEvidence(
        signal_id=deterministic_id("opportunity-competition-signal", material),
        **material,
    )


def _status_from_demand(status: DemandMetricStatus) -> OpportunityEvidenceStatus:
    return {
        DemandMetricStatus.AVAILABLE: OpportunityEvidenceStatus.AVAILABLE,
        DemandMetricStatus.PARTIAL: OpportunityEvidenceStatus.PARTIAL,
        DemandMetricStatus.UNKNOWN: OpportunityEvidenceStatus.UNKNOWN,
    }[status]


def _status_from_supply(status: GapSignalStatus) -> OpportunityEvidenceStatus:
    return {
        GapSignalStatus.AVAILABLE: OpportunityEvidenceStatus.AVAILABLE,
        GapSignalStatus.PARTIAL: OpportunityEvidenceStatus.PARTIAL,
        GapSignalStatus.UNKNOWN: OpportunityEvidenceStatus.UNKNOWN,
    }[status]


def _confidence(value: DemandMetricConfidenceLevel | GapConfidenceLevel) -> OpportunityConfidence:
    return OpportunityConfidence(value.value)


def _minimum_confidence(values: tuple[OpportunityConfidence, ...]) -> OpportunityConfidence:
    if not values or OpportunityConfidence.UNKNOWN in values:
        return OpportunityConfidence.UNKNOWN
    return min(values, key=lambda item: _CONFIDENCE_RANK[item])


def _aggregate_status(statuses: tuple[OpportunityEvidenceStatus, ...]) -> OpportunityEvidenceStatus:
    if not statuses or set(statuses) == {OpportunityEvidenceStatus.UNKNOWN}:
        return OpportunityEvidenceStatus.UNKNOWN
    if set(statuses) == {OpportunityEvidenceStatus.AVAILABLE}:
        return OpportunityEvidenceStatus.AVAILABLE
    return OpportunityEvidenceStatus.PARTIAL


class OpportunityEvidenceBuilderV0_1:
    """Create a candidate evidence view without mutating or reclassifying inputs."""

    def build(self, request: OpportunityCandidateRequest) -> OpportunityEvidenceBundle:
        if not isinstance(request, OpportunityCandidateRequest):
            raise TypeError("request must be OpportunityCandidateRequest")
        references = self._references(request)
        demand = self._demand(request, references)
        supply = self._supply(request, references)
        competition = self._competition(request, references)
        gap = self._gap(request, references)
        economic = self._economic(request, references)
        missing = self._missing_evidence_ids(demand, supply, competition, gap, economic)
        material = {
            "demand": demand,
            "supply": supply,
            "competition": competition,
            "gap": gap,
            "economic": economic,
            "source_references": tuple(sorted(references.all, key=lambda item: item.reference_id)),
            "missing_evidence_ids": missing,
        }
        return OpportunityEvidenceBundle(
            evidence_bundle_id=deterministic_id("opportunity-evidence-bundle", material),
            **material,
        )

    def _references(self, request: OpportunityCandidateRequest) -> _ReferenceIndex:
        gap = request.supply_demand_gap
        buyer = request.buyer_need_map
        category = request.category_product_map
        competition = request.competition_intelligence
        buyer_reference = _reference(
            source=OpportunityEvidenceSource.BUYER_NEED_MAP,
            source_id=buyer.map_id,
            record_ids=(
                gap.need_cluster_id,
                *(item.metric_result_id for item in buyer.demand_metrics if item.cluster_id == gap.need_cluster_id),
            ),
        )
        category_reference = _reference(
            source=OpportunityEvidenceSource.CATEGORY_PRODUCT_MAP,
            source_id=category.map_id,
            record_ids=(
                *(item.grain_product_id for item in category.included_products),
                *(item.distribution_id for item in category.attribute_distributions),
                *(item.segment_id for item in category.combination_segments),
            ),
        )
        gap_reference = _reference(
            source=OpportunityEvidenceSource.SUPPLY_DEMAND_GAP,
            source_id=gap.gap_id,
            record_ids=(
                *(item.metric_result_id for item in gap.demand_metrics),
                *(item.supply_metric_id for item in gap.supply_metrics),
            ),
        )
        competition_records = tuple(
            sorted(
                {
                    *(item.observation_id for item in competition.keyword_relationship_evidence),
                    *(item.observation_id for item in competition.variation_evidence),
                    *(
                        observation_id
                        for item in competition.observed_product_inventory
                        for observation_id in item.source_observation_ids
                    ),
                }
            )
        )
        competition_reference = _reference(
            source=OpportunityEvidenceSource.COMPETITION_INTELLIGENCE,
            source_id=competition.snapshot_id,
            record_ids=competition_records,
        )
        profile_references = tuple(
            _reference(
                source=OpportunityEvidenceSource.PRODUCT_ATTRIBUTE_PROFILE,
                source_id=profile.profile_id,
                record_ids=(profile.profile_id,),
            )
            for profile in request.product_attribute_profiles
        )
        if request.market_analysis is None:
            economic_reference = _reference(
                source=OpportunityEvidenceSource.UNKNOWN_ECONOMIC_EVIDENCE,
                source_id=f"economic-evidence:unknown:{gap.gap_id}",
                record_ids=(),
                missing=True,
                limitations=("MARKET_ANALYSIS_NOT_SUPPLIED",),
            )
        else:
            economic_reference = _reference(
                source=OpportunityEvidenceSource.MARKET_ANALYSIS,
                source_id=request.market_analysis.analysis_id,
                record_ids=(
                    *(item.field_id for item in request.market_analysis.count_metrics),
                    *(item.metric_id for item in request.market_analysis.numeric_summaries),
                ),
                limitations=(
                    "MARKET_ANALYSIS_IS_OBSERVED_EVIDENCE_NOT_A_PROFIT_CALCULATION",
                ),
            )
        return _ReferenceIndex(
            buyer_need_map=buyer_reference,
            category_product_map=category_reference,
            supply_demand_gap=gap_reference,
            competition_intelligence=competition_reference,
            economic=economic_reference,
            profile_references=profile_references,
        )

    def _demand(self, request: OpportunityCandidateRequest, refs: _ReferenceIndex) -> DemandEvidence:
        gap = request.supply_demand_gap
        metrics: list[OpportunityMetricEvidence] = []
        reliabilities: list[OpportunityConfidence] = []
        search_records: set[str] = set()
        review_records: set[str] = set()
        for metric in gap.demand_metrics:
            status = _status_from_demand(metric.status)
            record_ids = (metric.metric_result_id, *metric.evidence_reference_ids)
            limitations = metric.limitations
            metrics.append(
                _metric(
                    metric_name=metric.metric_type.value.casefold(),
                    status=status,
                    value=metric.share,
                    source_record_ids=record_ids,
                    source_reference_ids=(refs.buyer_need_map.reference_id,),
                    limitations=limitations,
                )
            )
            if status is not OpportunityEvidenceStatus.UNKNOWN:
                reliabilities.append(_confidence(metric.confidence.level))
            if metric.metric_type is DemandMetricType.SEARCH_DEMAND_SHARE:
                search_records.update(metric.evidence_reference_ids)
            if metric.metric_type is DemandMetricType.REVIEW_MENTION_SHARE:
                review_records.update(metric.evidence_reference_ids)
        status = _aggregate_status(tuple(item.status for item in metrics))
        material = {
            "need_cluster_id": gap.need_cluster_id,
            "metrics": tuple(sorted(metrics, key=lambda item: item.evidence_id)),
            "search_evidence_record_ids": tuple(sorted(search_records)),
            "review_evidence_record_ids": tuple(sorted(review_records)),
            "status": status,
            "reliability": _minimum_confidence(tuple(reliabilities)),
        }
        return DemandEvidence(
            demand_evidence_id=deterministic_id("opportunity-demand-evidence", material),
            **material,
        )

    def _supply(self, request: OpportunityCandidateRequest, refs: _ReferenceIndex) -> SupplyEvidence:
        gap = request.supply_demand_gap
        category = request.category_product_map
        product_coverage = next(
            item
            for item in gap.supply_metrics
            if item.metric_type is SupplyMetricType.PRODUCT_COVERAGE_SHARE
        )
        coverage_status = _status_from_supply(product_coverage.status)
        coverage = _metric(
            metric_name="product_coverage",
            status=coverage_status,
            value=product_coverage.value if isinstance(product_coverage.value, str) else None,
            source_record_ids=(product_coverage.supply_metric_id, *product_coverage.evidence_reference_ids),
            source_reference_ids=(
                refs.supply_demand_gap.reference_id,
                refs.category_product_map.reference_id,
            ),
            limitations=product_coverage.limitations,
        )
        distributions: list[OpportunityMetricEvidence] = []
        for distribution in category.attribute_distributions:
            if distribution.known_value_count == 0:
                status = OpportunityEvidenceStatus.UNKNOWN
                value = None
                limitations = ("ATTRIBUTE_DISTRIBUTION_HAS_NO_KNOWN_VALUES",)
            elif distribution.unknown_count == 0:
                status = OpportunityEvidenceStatus.AVAILABLE
                value = distribution.attribute_coverage
                limitations = ()
            else:
                status = OpportunityEvidenceStatus.PARTIAL
                value = distribution.attribute_coverage
                limitations = ("ATTRIBUTE_DISTRIBUTION_CONTAINS_UNKNOWN_PRODUCTS",)
            distributions.append(
                _metric(
                    metric_name=f"attribute_distribution:{distribution.dimension.value}",
                    status=status,
                    value=value,
                    source_record_ids=(distribution.distribution_id, *distribution.evidence_reference_ids),
                    source_reference_ids=(refs.category_product_map.reference_id,),
                    limitations=limitations,
                )
            )
        status = (
            OpportunityEvidenceStatus.UNKNOWN
            if coverage_status is OpportunityEvidenceStatus.UNKNOWN
            else _aggregate_status((coverage_status, *(item.status for item in distributions)))
        )
        reliability = (
            OpportunityConfidence.UNKNOWN
            if coverage_status is OpportunityEvidenceStatus.UNKNOWN
            else _confidence(product_coverage.confidence.level)
        )
        material = {
            "product_coverage": coverage,
            "attribute_distributions": tuple(sorted(distributions, key=lambda item: item.evidence_id)),
            "existing_product_ids": tuple(
                sorted(item.grain_product_id for item in category.included_products)
            ),
            "status": status,
            "reliability": reliability,
        }
        return SupplyEvidence(
            supply_evidence_id=deterministic_id("opportunity-supply-evidence", material),
            **material,
        )

    def _competition(
        self, request: OpportunityCandidateRequest, refs: _ReferenceIndex
    ) -> CompetitionEvidence:
        snapshot = request.competition_intelligence
        relationship_ids = tuple(
            sorted(item.observation_id for item in snapshot.keyword_relationship_evidence)
        )
        market_concentration = _competition_signal(
            signal_name=CompetitionSignalName.MARKET_CONCENTRATION,
            status=OpportunityEvidenceStatus.UNKNOWN,
            level=CompetitionLevel.UNKNOWN,
            source_record_ids=(),
            source_reference_ids=(refs.competition_intelligence.reference_id,),
            limitations=("NO_GOVERNED_MARKET_CONCENTRATION_METRIC",),
        )
        if relationship_ids:
            top_asin_dominance = _competition_signal(
                signal_name=CompetitionSignalName.TOP_ASIN_DOMINANCE,
                status=OpportunityEvidenceStatus.PARTIAL,
                level=CompetitionLevel.UNKNOWN,
                source_record_ids=relationship_ids,
                source_reference_ids=(refs.competition_intelligence.reference_id,),
                limitations=("NO_GOVERNED_TOP_ASIN_COHORT_OR_DOMINANCE_POLICY",),
            )
        else:
            top_asin_dominance = _competition_signal(
                signal_name=CompetitionSignalName.TOP_ASIN_DOMINANCE,
                status=OpportunityEvidenceStatus.UNKNOWN,
                level=CompetitionLevel.UNKNOWN,
                source_record_ids=(),
                source_reference_ids=(refs.competition_intelligence.reference_id,),
                limitations=("NO_TOP_ASIN_RELATIONSHIP_EVIDENCE",),
            )
        brand_concentration = _competition_signal(
            signal_name=CompetitionSignalName.BRAND_CONCENTRATION,
            status=OpportunityEvidenceStatus.UNKNOWN,
            level=CompetitionLevel.UNKNOWN,
            source_record_ids=(),
            source_reference_ids=(refs.competition_intelligence.reference_id,),
            limitations=("NO_GOVERNED_BRAND_CONCENTRATION_EVIDENCE",),
        )
        review_summary = self._market_summary(request, "market_analysis.product_review_count")
        if review_summary is None or review_summary.status not in {
            MarketMetricStatus.CALCULATED,
            MarketMetricStatus.PARTIAL,
        }:
            review_barrier = _competition_signal(
                signal_name=CompetitionSignalName.REVIEW_BARRIER,
                status=OpportunityEvidenceStatus.UNKNOWN,
                level=CompetitionLevel.UNKNOWN,
                source_record_ids=(),
                source_reference_ids=(refs.competition_intelligence.reference_id, refs.economic.reference_id),
                limitations=("NO_OBSERVED_REVIEW_EVIDENCE",),
            )
        else:
            review_barrier = _competition_signal(
                signal_name=CompetitionSignalName.REVIEW_BARRIER,
                status=OpportunityEvidenceStatus.PARTIAL,
                level=CompetitionLevel.UNKNOWN,
                source_record_ids=(review_summary.metric_id, *review_summary.source_observation_ids),
                source_reference_ids=(refs.competition_intelligence.reference_id, refs.economic.reference_id),
                limitations=("NO_GOVERNED_TOP_ASIN_REVIEW_BARRIER_POLICY",),
            )
        price_summary = self._market_summary(request, "market_analysis.observed_product_price")
        if price_summary is None or price_summary.status not in {
            MarketMetricStatus.CALCULATED,
            MarketMetricStatus.PARTIAL,
        }:
            price_competition = _competition_signal(
                signal_name=CompetitionSignalName.PRICE_COMPETITION,
                status=OpportunityEvidenceStatus.UNKNOWN,
                level=CompetitionLevel.UNKNOWN,
                source_record_ids=(),
                source_reference_ids=(refs.competition_intelligence.reference_id, refs.economic.reference_id),
                limitations=("NO_OBSERVED_PRICE_EVIDENCE",),
            )
        else:
            price_competition = _competition_signal(
                signal_name=CompetitionSignalName.PRICE_COMPETITION,
                status=OpportunityEvidenceStatus.PARTIAL,
                level=CompetitionLevel.UNKNOWN,
                source_record_ids=(price_summary.metric_id, *price_summary.source_observation_ids),
                source_reference_ids=(refs.competition_intelligence.reference_id, refs.economic.reference_id),
                limitations=("OBSERVED_PRICE_DISTRIBUTION_IS_NOT_PRICE_COMPETITION",),
            )
        signals = (
            market_concentration,
            top_asin_dominance,
            brand_concentration,
            review_barrier,
            price_competition,
        )
        status = _aggregate_status(tuple(item.status for item in signals))
        material = {
            "market_concentration": market_concentration,
            "top_asin_dominance": top_asin_dominance,
            "brand_concentration": brand_concentration,
            "review_barrier": review_barrier,
            "price_competition": price_competition,
            "status": status,
            "overall_level": CompetitionLevel.UNKNOWN,
            "source_reference_id": refs.competition_intelligence.reference_id,
        }
        return CompetitionEvidence(
            competition_evidence_id=deterministic_id("opportunity-competition-evidence", material),
            **material,
        )

    def _gap(self, request: OpportunityCandidateRequest, refs: _ReferenceIndex) -> OpportunityGapEvidence:
        gap = request.supply_demand_gap
        status = (
            OpportunityEvidenceStatus.UNKNOWN
            if gap.gap_type is GapType.INSUFFICIENT_EVIDENCE
            else OpportunityEvidenceStatus.AVAILABLE
        )
        material = {
            "gap_id": gap.gap_id,
            "gap_type": gap.gap_type,
            "gap_strength": gap.gap_strength,
            "reliability": _confidence(gap.confidence.level),
            "status": status,
            "source_reference_id": refs.supply_demand_gap.reference_id,
            "source_metric_ids": tuple(
                sorted(
                    (
                        *(item.metric_result_id for item in gap.demand_metrics),
                        *(item.supply_metric_id for item in gap.supply_metrics),
                    )
                )
            ),
        }
        return OpportunityGapEvidence(
            gap_evidence_id=deterministic_id("opportunity-gap-evidence", material),
            **material,
        )

    def _economic(self, request: OpportunityCandidateRequest, refs: _ReferenceIndex) -> EconomicEvidence:
        price_band = self._price_band(request, refs)
        sales = self._demand_availability(
            request,
            refs,
            DemandMetricType.SALES_ASSOCIATED_SHARE,
            "sales_availability",
        )
        revenue = self._demand_availability(
            request,
            refs,
            DemandMetricType.REVENUE_ASSOCIATED_SHARE,
            "revenue_availability",
        )
        market_size = _metric(
            metric_name="market_size_signal",
            status=OpportunityEvidenceStatus.UNKNOWN,
            value=None,
            source_record_ids=(),
            source_reference_ids=(refs.economic.reference_id,),
            limitations=("NO_GOVERNED_MARKET_SIZE_SIGNAL",),
        )
        status = _aggregate_status(
            (price_band.status, sales.status, revenue.status, market_size.status)
        )
        material = {
            "price_band": price_band,
            "sales_availability": sales,
            "revenue_availability": revenue,
            "market_size_signal": market_size,
            "status": status,
            "source_reference_id": refs.economic.reference_id,
        }
        return EconomicEvidence(
            economic_evidence_id=deterministic_id("opportunity-economic-evidence", material),
            **material,
        )

    def _price_band(
        self, request: OpportunityCandidateRequest, refs: _ReferenceIndex
    ) -> OpportunityMetricEvidence:
        values: set[str] = set()
        records: set[str] = set()
        profiles_with_value = 0
        profile_refs = tuple(item.reference_id for item in refs.profile_references)
        for profile in request.product_attribute_profiles:
            slot = next(
                (
                    item
                    for item in profile.attributes
                    if item.dimension is AttributeDimension.PRICE_BAND
                    and item.state is AttributeState.PRESENT
                    and item.resolved_value
                ),
                None,
            )
            if slot is None:
                continue
            profiles_with_value += 1
            records.add(profile.profile_id)
            values.update(item.display_value for item in slot.resolved_value)
        if not values:
            return _metric(
                metric_name="price_band",
                status=OpportunityEvidenceStatus.UNKNOWN,
                value=None,
                source_record_ids=(),
                source_reference_ids=profile_refs,
                limitations=("NO_RESOLVED_PRICE_BAND_ATTRIBUTE",),
            )
        rendered = " | ".join(sorted(values))
        if profiles_with_value == len(request.product_attribute_profiles) and len(values) == 1:
            return _metric(
                metric_name="price_band",
                status=OpportunityEvidenceStatus.AVAILABLE,
                value=rendered,
                source_record_ids=tuple(sorted(records)),
                source_reference_ids=profile_refs,
            )
        return _metric(
            metric_name="price_band",
            status=OpportunityEvidenceStatus.PARTIAL,
            value=rendered,
            source_record_ids=tuple(sorted(records)),
            source_reference_ids=profile_refs,
            limitations=("PRICE_BAND_IS_NOT_RESOLVED_FOR_EVERY_PROFILE",),
        )

    def _demand_availability(
        self,
        request: OpportunityCandidateRequest,
        refs: _ReferenceIndex,
        metric_type: DemandMetricType,
        metric_name: str,
    ) -> OpportunityMetricEvidence:
        metric = next(
            item
            for item in request.supply_demand_gap.demand_metrics
            if item.metric_type is metric_type
        )
        status = _status_from_demand(metric.status)
        return _metric(
            metric_name=metric_name,
            status=status,
            value=metric.share,
            source_record_ids=(metric.metric_result_id, *metric.evidence_reference_ids),
            source_reference_ids=(refs.buyer_need_map.reference_id,),
            limitations=metric.limitations,
        )

    @staticmethod
    def _market_summary(request: OpportunityCandidateRequest, metric_id: str):
        if request.market_analysis is None:
            return None
        return next(
            (
                item
                for item in request.market_analysis.numeric_summaries
                if item.metric_id == metric_id
            ),
            None,
        )

    @staticmethod
    def _missing_evidence_ids(
        demand: DemandEvidence,
        supply: SupplyEvidence,
        competition: CompetitionEvidence,
        gap: OpportunityGapEvidence,
        economic: EconomicEvidence,
    ) -> tuple[str, ...]:
        candidates = (
            *(item for item in demand.metrics if item.status is OpportunityEvidenceStatus.UNKNOWN),
            supply.product_coverage
            if supply.product_coverage.status is OpportunityEvidenceStatus.UNKNOWN
            else None,
            *(
                item
                for item in supply.attribute_distributions
                if item.status is OpportunityEvidenceStatus.UNKNOWN
            ),
            *(
                item
                for item in (
                    competition.market_concentration,
                    competition.top_asin_dominance,
                    competition.brand_concentration,
                    competition.review_barrier,
                    competition.price_competition,
                )
                if item.status is OpportunityEvidenceStatus.UNKNOWN
            ),
            gap if gap.status is OpportunityEvidenceStatus.UNKNOWN else None,
            *(
                item
                for item in (
                    economic.price_band,
                    economic.sales_availability,
                    economic.revenue_availability,
                    economic.market_size_signal,
                )
                if item.status is OpportunityEvidenceStatus.UNKNOWN
            ),
        )
        ids = {
            item.gap_evidence_id if isinstance(item, OpportunityGapEvidence) else item.evidence_id
            if isinstance(item, OpportunityMetricEvidence)
            else item.signal_id
            for item in candidates
            if item is not None
        }
        return tuple(sorted(ids))


__all__ = ("OpportunityEvidenceBuilderV0_1",)
