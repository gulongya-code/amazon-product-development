"""Reference-only Route Discovery V2 integration for Market Report V0.2.

The source result remains the authority for route identity, membership, metrics,
denominators, and evidence lineage.  This module validates that authority and
attaches its content-addressed result through the existing external-integration
registry.  It never reconstructs a route or converts a route metric into a
Market Report core metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, TypeVar

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.product_route_opportunity.models import (
    CandidateSelectionStatus,
)
from amazon_product_intelligence.route_discovery_v2.config import (
    ROUTE_V2_ENGINE_VERSION,
    ROUTE_V2_RESULT_CONTRACT_VERSION,
)
from amazon_product_intelligence.route_discovery_v2.errors import RouteDiscoveryV2Error
from amazon_product_intelligence.route_discovery_v2.models import RouteDiscoveryV2Result

from ..builder import compose_market_report_v0_2
from ..models.common import (
    Availability,
    ContractReference,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    ReferenceKind,
    V0_2Contract,
    build_reference,
    identity,
    texts,
)
from ..models.evidence_registry import EvidenceRecord, ReportProvenanceRecord
from ..models.external_integrations import (
    ExternalIntegrationAttachment,
    ExternalIntegrationState,
    build_external_attachment,
    build_external_integrations,
)
from ..models.report_snapshot import MarketReportSnapshotV0_2
from ..models.scope_context import ProductGrainV0_2


ROUTE_DISCOVERY_V2_MARKET_REPORT_PROJECTION_VERSION = (
    "market-report-v0.2-route-discovery-v2-projection-v1.0"
)
ROUTE_DISCOVERY_V2_INTEGRATION_NAME = "route-discovery-v2"
_SOURCE_NAMESPACE = "product-intelligence"
_LISTING_GRAIN = "LISTING_ASIN_NO_PARENT_COLLAPSE"


class RouteDiscoveryV2MarketReportIntegrationError(MarketReportV0_2ValidationError):
    """A stable fail-closed error raised at the Route V2/report boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteDiscoveryV2MarketReportProjection(V0_2Contract):
    """Deterministic attachment material projected from one strict V2 result."""

    projection_id: str
    contract_version: str
    availability: Availability
    source_result_id: str
    source_result_contract_version: str
    source_semantic_fingerprint: str
    upstream_dataset_id: str
    upstream_dataset_fingerprint: str
    semantic_profile_fingerprint: str
    route_config_fingerprint: str
    listing_count: int
    assigned_count: int
    unclassified_count: int
    review_required_count: int
    route_ids: tuple[str, ...]
    denominator_ids: tuple[str, ...]
    candidate_selection_status: CandidateSelectionStatus
    source_reference: ContractReference
    attachment: ExternalIntegrationAttachment
    provenance: ReportProvenanceRecord
    evidence: EvidenceRecord
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != ROUTE_DISCOVERY_V2_MARKET_REPORT_PROJECTION_VERSION:
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_VERSION_UNSUPPORTED",
                "unsupported Route Discovery V2 Market Report projection version",
            )
        if not isinstance(self.availability, Availability):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "projection availability is invalid",
            )
        if not isinstance(self.candidate_selection_status, CandidateSelectionStatus):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "candidate status is invalid",
            )
        route_ids = texts(self.route_ids, "Route V2 projection route IDs")
        denominator_ids = texts(
            self.denominator_ids, "Route V2 projection denominator IDs",
        )
        limitations = texts(
            self.limitations, "Route V2 projection limitations",
            allow_empty=self.availability is Availability.AVAILABLE,
        )
        if self.listing_count != (
            self.assigned_count
            + self.unclassified_count
            + self.review_required_count
        ):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "membership counts do not reconcile",
            )
        if self.availability is Availability.UNAVAILABLE and route_ids:
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID",
                "unavailable projection cannot expose viable route identities",
            )
        if self.source_reference.target_id != self.source_result_id:
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "source reference identity differs",
            )
        if self.source_reference.content_fingerprint != self.source_semantic_fingerprint:
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "source reference fingerprint differs",
            )
        if self.attachment.external_reference_id != self.source_reference.reference_id:
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "attachment source reference differs",
            )
        if self.attachment.provenance_reference_ids != (self.provenance.provenance_id,):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "attachment provenance differs",
            )
        if self.evidence.source_reference_ids != (self.source_reference.reference_id,):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "evidence source reference differs",
            )
        if self.evidence.provenance_reference_ids != (self.provenance.provenance_id,):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "evidence provenance differs",
            )
        object.__setattr__(self, "route_ids", route_ids)
        object.__setattr__(self, "denominator_ids", denominator_ids)
        object.__setattr__(self, "limitations", limitations)
        if self.projection_id != identity(
            "market-report-v0.2-route-discovery-v2-projection",
            self,
            "projection_id",
        ):
            raise RouteDiscoveryV2MarketReportIntegrationError(
                "ROUTE_V2_PROJECTION_INVALID", "projection ID does not match content",
            )


def _fail(code: str, message: str) -> None:
    raise RouteDiscoveryV2MarketReportIntegrationError(code, message)


def _validate_source_unchecked(source: Any) -> RouteDiscoveryV2Result:
    if type(source) is not RouteDiscoveryV2Result:
        _fail(
            "ROUTE_V2_INPUT_TYPE_INVALID",
            "input must be an exact RouteDiscoveryV2Result contract",
        )
    try:
        source.__post_init__()
    except RouteDiscoveryV2Error as exc:
        raise RouteDiscoveryV2MarketReportIntegrationError(
            "ROUTE_V2_INPUT_CONTRACT_INVALID", str(exc),
        ) from exc
    if source.contract_version != ROUTE_V2_RESULT_CONTRACT_VERSION:
        _fail("ROUTE_V2_INPUT_VERSION_INCOMPATIBLE", "result contract version differs")
    if source.route_engine_version != ROUTE_V2_ENGINE_VERSION:
        _fail("ROUTE_V2_INPUT_VERSION_INCOMPATIBLE", "route engine version differs")

    route_ids = tuple(item.route_id for item in source.routes)
    denominator_ids = tuple(item.denominator_id for item in source.denominators)
    reference_ids = tuple(item.reference_id for item in source.references)
    if len(route_ids) != len(set(route_ids)):
        _fail("ROUTE_V2_DUPLICATE_ROUTE_ID", "route identities must be unique")
    if len(denominator_ids) != len(set(denominator_ids)):
        _fail("ROUTE_V2_DUPLICATE_DENOMINATOR_ID", "denominator identities must be unique")
    if len(reference_ids) != len(set(reference_ids)):
        _fail("ROUTE_V2_DUPLICATE_REFERENCE_ID", "source references must be unique")
    if any(type(item) is not ContractReference for item in source.references):
        _fail("ROUTE_V2_SOURCE_REFERENCE_INVALID", "source reference has a wrong type")

    references = {item.reference_id: item for item in source.references}
    _require_source_reference(
        source,
        namespace="governed-market-dataset",
        target_id=source.upstream_dataset_id,
        target_version=None,
        content_fingerprint=source.upstream_dataset_fingerprint,
    )
    _require_source_reference(
        source,
        namespace="semantic-engine-v2-result",
        target_id=source.upstream_semantic_result_id,
        target_version=None,
        content_fingerprint=source.upstream_semantic_fingerprint,
    )
    _require_source_reference(
        source,
        namespace="category-semantic-profile",
        target_id=source.semantic_profile_id,
        target_version=source.semantic_profile_version,
        content_fingerprint=source.semantic_profile_fingerprint,
    )
    _require_source_reference(
        source,
        namespace="route-discovery-v2-config",
        target_id=source.route_config_id,
        target_version=source.route_config_version,
        content_fingerprint=source.route_config_fingerprint,
    )
    grain_reference = _require_source_reference(
        source,
        namespace="product-grain",
        target_id=_LISTING_GRAIN,
        target_version="1.0",
        content_fingerprint=None,
    )
    route_reference_targets = {
        item.target_id for item in source.references
        if item.namespace == "product-route-v2"
    }
    route_references = tuple(
        item for item in source.references
        if item.namespace == "product-route-v2"
    )
    if (
        len(route_references) != len(route_ids)
        or any(
            item.kind is not ReferenceKind.REPORT_LOCAL
            for item in route_references
        )
        or route_reference_targets != set(route_ids)
        or any(
            item.target_version != ROUTE_V2_ENGINE_VERSION
            for item in route_references
        )
    ):
        _fail(
            "ROUTE_V2_ROUTE_REFERENCE_MISMATCH",
            "route references do not match projected route identities",
        )
    denominator_reference_targets = {
        item.target_id for item in source.references
        if item.namespace == "product-route-opportunity-denominator"
    }
    denominator_references = tuple(
        item for item in source.references
        if item.namespace == "product-route-opportunity-denominator"
    )
    if (
        len(denominator_references) != len(denominator_ids)
        or any(
            item.kind is not ReferenceKind.REPORT_LOCAL
            for item in denominator_references
        )
        or denominator_reference_targets != set(denominator_ids)
        or any(item.target_version != "1.0" for item in denominator_references)
    ):
        _fail(
            "ROUTE_V2_DENOMINATOR_REFERENCE_MISMATCH",
            "denominator references do not match source denominators",
        )

    candidate_routes = tuple(item.route_id for item in source.candidates)
    priorities = tuple(item.priority for item in source.candidates)
    if len(candidate_routes) != len(set(candidate_routes)):
        _fail("ROUTE_V2_DUPLICATE_CANDIDATE_ROUTE", "candidate routes must be unique")
    if priorities != tuple(range(1, len(priorities) + 1)):
        _fail("ROUTE_V2_CANDIDATE_ORDER_INVALID", "candidate priorities must be contiguous")
    if (
        source.candidate_selection_status is CandidateSelectionStatus.SELECTED
        and len(source.candidates) < 3
    ) or (
        source.candidate_selection_status
        is CandidateSelectionStatus.INSUFFICIENT_EVIDENCE
        and source.candidates
    ):
        _fail(
            "ROUTE_V2_CANDIDATE_STATE_INVALID",
            "candidate status and selected candidate count disagree",
        )

    for route in source.routes:
        metric_names = tuple(name for name, _ in route.metrics)
        if len(metric_names) != len(set(metric_names)):
            _fail("ROUTE_V2_DUPLICATE_METRIC_NAME", "route metric names must be unique")
        for _, metric in route.metrics:
            requested = {
                *metric.subject_reference_ids,
                *(
                    (metric.cohort_reference_id,)
                    if metric.cohort_reference_id is not None else ()
                ),
                *(
                    (metric.denominator_reference_id,)
                    if metric.denominator_reference_id is not None else ()
                ),
                *(
                    (metric.product_grain_reference_id,)
                    if metric.product_grain_reference_id is not None else ()
                ),
                *(
                    (metric.period_reference_id,)
                    if metric.period_reference_id is not None else ()
                ),
            }
            if requested - set(references):
                _fail(
                    "ROUTE_V2_METRIC_REFERENCE_ORPHANED",
                    "route metric contains a reference absent from the source registry",
                )
            if metric.product_grain_reference_id != grain_reference.reference_id:
                _fail(
                    "ROUTE_V2_METRIC_GRAIN_INCOMPATIBLE",
                    "route metric does not retain listing-ASIN grain",
                )
    return source


def _require_source_reference(
    source: RouteDiscoveryV2Result,
    *,
    namespace: str,
    target_id: str,
    target_version: str | None,
    content_fingerprint: str | None,
) -> ContractReference:
    matches = tuple(
        item for item in source.references if item.namespace == namespace
    )
    if len(matches) != 1:
        _fail(
            "ROUTE_V2_REQUIRED_REFERENCE_MISSING",
            f"exactly one {namespace} reference is required",
        )
    reference = matches[0]
    if (
        reference.kind is not ReferenceKind.REPORT_LOCAL
        or reference.target_id != target_id
    ):
        _fail(
            "ROUTE_V2_REQUIRED_REFERENCE_INCOMPATIBLE",
            f"{namespace} reference identity differs",
        )
    if target_version is not None and reference.target_version != target_version:
        _fail(
            "ROUTE_V2_REQUIRED_REFERENCE_INCOMPATIBLE",
            f"{namespace} reference version differs",
        )
    if reference.content_fingerprint != content_fingerprint:
        _fail(
            "ROUTE_V2_REQUIRED_REFERENCE_INCOMPATIBLE",
            f"{namespace} reference fingerprint differs",
        )
    return reference


def _validate_source(source: Any) -> RouteDiscoveryV2Result:
    try:
        return _validate_source_unchecked(source)
    except RouteDiscoveryV2MarketReportIntegrationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise RouteDiscoveryV2MarketReportIntegrationError(
            "ROUTE_V2_INPUT_MALFORMED", "Route V2 input shape is malformed",
        ) from exc


def _projection_state(
    source: RouteDiscoveryV2Result,
) -> tuple[Availability, tuple[str, ...]]:
    limitations = {"ROUTE_DISCOVERY_V2_METRICS_REMAIN_SOURCE_OWNED"}
    if not source.routes:
        limitations.add("ROUTE_DISCOVERY_V2_NO_VIABLE_ROUTES")
        return Availability.UNAVAILABLE, tuple(sorted(limitations))
    partial = False
    if source.unclassified_count:
        partial = True
        limitations.add("ROUTE_DISCOVERY_V2_UNCLASSIFIED_MEMBERSHIPS_PRESENT")
    if source.review_required_count:
        partial = True
        limitations.add("ROUTE_DISCOVERY_V2_REVIEW_REQUIRED_MEMBERSHIPS_PRESENT")
    if source.candidate_selection_status is CandidateSelectionStatus.INSUFFICIENT_EVIDENCE:
        partial = True
        limitations.add("ROUTE_DISCOVERY_V2_CANDIDATE_EVIDENCE_INSUFFICIENT")
    return (
        Availability.PARTIAL if partial else Availability.AVAILABLE,
        tuple(sorted(limitations)),
    )


def project_route_discovery_v2(
    source: RouteDiscoveryV2Result,
) -> RouteDiscoveryV2MarketReportProjection:
    """Project one strict Route V2 result into reference-only report material."""

    source = _validate_source(source)
    availability, limitations = _projection_state(source)
    source_identity = {
        "source_result_id": source.result_id,
        "source_result_contract_version": source.contract_version,
        "source_semantic_fingerprint": source.semantic_fingerprint,
    }
    provenance_id = deterministic_id(
        "market-report-v0.2-route-discovery-v2-provenance", source_identity,
    )
    source_reference = build_reference(
        kind=ReferenceKind.EXTERNAL_PROVENANCE,
        namespace=_SOURCE_NAMESPACE,
        target_id=source.result_id,
        target_version=source.contract_version,
        content_fingerprint=source.semantic_fingerprint,
        provenance_reference_ids=(provenance_id,),
    )
    evidence_id = deterministic_id(
        "market-report-v0.2-route-discovery-v2-evidence",
        {
            **source_identity,
            "source_reference_id": source_reference.reference_id,
            "route_ids": sorted(item.route_id for item in source.routes),
            "denominator_ids": sorted(
                item.denominator_id for item in source.denominators
            ),
        },
    )
    provenance = ReportProvenanceRecord(
        provenance_id=provenance_id,
        source_namespace=_SOURCE_NAMESPACE,
        source_version=source.contract_version,
        source_record_id=source.result_id,
        availability=availability,
        content_fingerprint=source.semantic_fingerprint,
        evidence_ids=(evidence_id,),
        limitations=limitations,
    )
    evidence = EvidenceRecord(
        evidence_id=evidence_id,
        semantics=EvidenceSemantics.DERIVED,
        source_reference_ids=(source_reference.reference_id,),
        provenance_reference_ids=(provenance_id,),
        content_fingerprint=source.semantic_fingerprint,
        limitations=limitations,
    )
    attachment = build_external_attachment(
        integration_name=ROUTE_DISCOVERY_V2_INTEGRATION_NAME,
        integration_version=source.contract_version,
        availability=availability,
        external_reference_id=source_reference.reference_id,
        provenance_reference_ids=(provenance_id,),
        limitations=limitations,
    )
    content = {
        "contract_version": ROUTE_DISCOVERY_V2_MARKET_REPORT_PROJECTION_VERSION,
        "availability": availability,
        **source_identity,
        "upstream_dataset_id": source.upstream_dataset_id,
        "upstream_dataset_fingerprint": source.upstream_dataset_fingerprint,
        "semantic_profile_fingerprint": source.semantic_profile_fingerprint,
        "route_config_fingerprint": source.route_config_fingerprint,
        "listing_count": source.listing_count,
        "assigned_count": source.assigned_count,
        "unclassified_count": source.unclassified_count,
        "review_required_count": source.review_required_count,
        "route_ids": tuple(sorted(item.route_id for item in source.routes)),
        "denominator_ids": tuple(sorted(
            item.denominator_id for item in source.denominators
        )),
        "candidate_selection_status": source.candidate_selection_status,
        "source_reference": source_reference,
        "attachment": attachment,
        "provenance": provenance,
        "evidence": evidence,
        "limitations": limitations,
    }
    return RouteDiscoveryV2MarketReportProjection(
        projection_id=deterministic_id(
            "market-report-v0.2-route-discovery-v2-projection", content,
        ),
        **content,
    )


T = TypeVar("T")


def _merge_unique(
    existing: Iterable[T],
    added: Iterable[T],
    *,
    key: Callable[[T], str],
    conflict_code: str,
) -> tuple[T, ...]:
    merged: dict[str, T] = {}
    for item in (*tuple(existing), *tuple(added)):
        item_key = key(item)
        prior = merged.get(item_key)
        if prior is not None and prior != item:
            _fail(conflict_code, f"conflicting identity: {item_key}")
        merged[item_key] = item
    return tuple(merged[item_key] for item_key in sorted(merged))


def _validate_report_compatibility(
    report: MarketReportSnapshotV0_2,
    projection: RouteDiscoveryV2MarketReportProjection,
    source: RouteDiscoveryV2Result,
) -> None:
    if report.scope_context.product_grain is not ProductGrainV0_2.CHILD_ASIN:
        _fail(
            "ROUTE_V2_REPORT_GRAIN_INCOMPATIBLE",
            "Route V2 listing-ASIN grain requires Market Report CHILD_ASIN grain",
        )
    references = {
        item.reference_id: item for item in report.evidence_registry.references
    }
    cohort_reference = references.get(
        report.scope_context.analysis_cohort_reference_id
    )
    if cohort_reference is None:
        _fail(
            "ROUTE_V2_REPORT_COHORT_REFERENCE_MISSING",
            "report analysis cohort reference is absent",
        )
    if (
        cohort_reference.target_id != projection.upstream_dataset_id
        or cohort_reference.content_fingerprint
        != projection.upstream_dataset_fingerprint
    ):
        _fail(
            "ROUTE_V2_REPORT_COHORT_INCOMPATIBLE",
            "report cohort does not exactly identify the Route V2 upstream dataset",
        )
    if report.sample.unique_asin_count != projection.listing_count:
        _fail(
            "ROUTE_V2_REPORT_LISTING_COUNT_INCOMPATIBLE",
            "report sample and Route V2 listing counts differ",
        )
    marketplaces = {
        metric.marketplace
        for route in source.routes
        for _, metric in route.metrics
        if metric.marketplace is not None
    }
    if marketplaces and marketplaces != {report.scope_context.marketplace}:
        _fail(
            "ROUTE_V2_REPORT_MARKETPLACE_INCOMPATIBLE",
            "route metrics and report scope marketplaces differ",
        )


def integrate_route_discovery_v2(
    report: MarketReportSnapshotV0_2,
    source: RouteDiscoveryV2Result,
) -> MarketReportSnapshotV0_2:
    """Attach a compatible Route V2 result to an existing strict V0.2 snapshot."""

    if type(report) is not MarketReportSnapshotV0_2:
        _fail(
            "ROUTE_V2_REPORT_INPUT_TYPE_INVALID",
            "report must be an exact MarketReportSnapshotV0_2 contract",
        )
    report.validate()
    source = _validate_source(source)
    projection = project_route_discovery_v2(source)
    _validate_report_compatibility(report, projection, source)

    existing_route_attachments = tuple(
        item for item in report.external_integrations.attachments
        if item.integration_name == ROUTE_DISCOVERY_V2_INTEGRATION_NAME
    )
    if existing_route_attachments:
        if existing_route_attachments == (projection.attachment,):
            return report
        _fail(
            "ROUTE_V2_REPORT_DUPLICATE_INTEGRATION",
            "a different Route Discovery V2 result is already attached",
        )

    attachments = _merge_unique(
        report.external_integrations.attachments,
        (projection.attachment,),
        key=lambda item: item.attachment_id,
        conflict_code="ROUTE_V2_REPORT_ATTACHMENT_CONFLICT",
    )
    external_integrations = build_external_integrations(
        state=ExternalIntegrationState.ATTACHED,
        attachments=attachments,
        limitations=tuple(sorted({
            *report.external_integrations.limitations,
            *projection.limitations,
        })),
    )
    references = _merge_unique(
        report.evidence_registry.references,
        (projection.source_reference,),
        key=lambda item: item.reference_id,
        conflict_code="ROUTE_V2_REPORT_REFERENCE_CONFLICT",
    )
    provenance = _merge_unique(
        report.provenance,
        (projection.provenance,),
        key=lambda item: item.provenance_id,
        conflict_code="ROUTE_V2_REPORT_PROVENANCE_CONFLICT",
    )
    evidence = _merge_unique(
        report.evidence_registry.evidence,
        (projection.evidence,),
        key=lambda item: item.evidence_id,
        conflict_code="ROUTE_V2_REPORT_EVIDENCE_CONFLICT",
    )
    return compose_market_report_v0_2(
        generated_at=report.metadata.generated_at,
        producer_version=report.metadata.producer_version,
        operational_metadata=report.metadata.operational_metadata,
        category=report.category,
        sample=report.sample,
        data_window=report.data_window,
        scope_context=report.scope_context,
        market_size=report.market_size,
        true_competitor_set=report.true_competitor_set,
        competitor_structure=report.competitor_structure,
        distributions=report.distributions,
        competitor_details=report.competitor_details,
        buyer_needs=report.buyer_needs,
        buyer_need_links=report.buyer_need_links,
        product_directions=report.product_directions,
        competitor_shortlist=report.competitor_shortlist,
        opportunity_score=report.opportunity_score,
        executive_summary=report.executive_summary,
        sanitized_appendix=report.sanitized_appendix,
        external_integrations=external_integrations,
        provenance=provenance,
        evidence=evidence,
        references=references,
        evidence_registry_limitations=report.evidence_registry.limitations,
        limitations=report.limitations,
    )


__all__ = (
    "ROUTE_DISCOVERY_V2_INTEGRATION_NAME",
    "ROUTE_DISCOVERY_V2_MARKET_REPORT_PROJECTION_VERSION",
    "RouteDiscoveryV2MarketReportIntegrationError",
    "RouteDiscoveryV2MarketReportProjection",
    "integrate_route_discovery_v2",
    "project_route_discovery_v2",
)
