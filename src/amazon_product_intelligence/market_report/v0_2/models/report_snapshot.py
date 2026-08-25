"""Complete strict P0 analytical graph for Market Report V0.2."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from amazon_product_intelligence.contracts import canonical_json, deterministic_id

from ..version import MARKET_REPORT_V0_2_VERSION, REPORT_SNAPSHOT_CONTRACT_VERSION
from .buyer_need_links import BuyerNeedLinkSection
from .buyer_needs import BuyerNeedProjection
from .common import ContractReference, MarketReportV0_2ValidationError, ReferenceKind, V0_2Contract, texts
from .competitor_details import CompetitorDetailSection
from .competitor_shortlist import CompetitorShortlistSection
from .competitor_structure import CompetitorStructureSection
from .distributions import DistributionSectionItem
from .evidence_registry import ALLOWED_EXTERNAL_NAMESPACES, EvidenceRegistry, ReportProvenanceRecord
from .executive_summary import ExecutiveSummarySection
from .external_integrations import ExternalIntegrationsRegistry
from .market_size import MarketSizeSection
from .opportunity import OpportunityProjectionV0_2
from .product_directions import ProductDirectionSection
from .report_context import CategoryContextV0_2, DataWindowContextV0_2, ReportMetadataV0_2, SampleContextV0_2
from .sanitized_appendix import SanitizedAppendixSection
from .scope_context import ProductGrainV0_2, ScopeContext
from .true_competitor_set import TrueCompetitorSetSection


_OWNED_ID_FIELDS = frozenset(
    {
        "appendix_reference_id", "attachment_id", "category_id", "claim_id", "direction_id",
        "distribution_id", "disposition_id", "field_id", "link_id", "metric_id", "projection_id",
        "item_id", "record_id", "registry_id", "sample_id", "scope_context_id", "section_id", "segment_id",
        "set_id", "window_id",
    }
)


def _walk(value: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, ContractReference):
        return
    if is_dataclass(value):
        owner = next((getattr(value, item.name) for item in fields(value) if item.name in _OWNED_ID_FIELDS), None)
        yield owner, value
        for item in fields(value):
            child = getattr(value, item.name)
            if is_dataclass(child):
                yield from _walk(child)
            elif isinstance(child, (tuple, list)):
                for nested in child:
                    if is_dataclass(nested):
                        yield from _walk(nested)


def _owned_ids(snapshot: "MarketReportSnapshotV0_2") -> Counter[str]:
    counts: Counter[str] = Counter()
    for owner, _ in _walk(snapshot):
        if owner is not None:
            counts[owner] += 1
    return counts


def _reference_requests(snapshot: "MarketReportSnapshotV0_2") -> tuple[tuple[str | None, str], ...]:
    requested: list[tuple[str | None, str]] = []
    for owner, value in _walk(snapshot):
        for item in fields(value):
            if item.name in _OWNED_ID_FIELDS:
                continue
            if item.name == "provenance_reference_ids" or item.name.endswith("evidence_ids"):
                continue
            child = getattr(value, item.name)
            if item.name.endswith("_reference_id") and isinstance(child, str):
                requested.append((owner, child))
            elif item.name.endswith("_reference_ids") and isinstance(child, (tuple, list)):
                requested.extend((owner, nested) for nested in child if isinstance(nested, str))
    return tuple(requested)


def _string_values(snapshot: "MarketReportSnapshotV0_2", suffix: str) -> set[str]:
    values: set[str] = set()
    for _, value in _walk(snapshot):
        for item in fields(value):
            child = getattr(value, item.name)
            if item.name.endswith(suffix):
                if isinstance(child, str):
                    values.add(child)
                elif isinstance(child, (tuple, list)):
                    values.update(nested for nested in child if isinstance(nested, str))
    return values


def _semantic_payload(snapshot: "MarketReportSnapshotV0_2") -> dict[str, Any]:
    payload = snapshot.to_dict()
    metadata = payload["metadata"]
    payload["metadata"] = {
        "report_version": metadata["report_version"],
        "contract_version": metadata["contract_version"],
        "producer_version": metadata["producer_version"],
    }
    payload["data_window"].pop("retrieved_at", None)
    return payload


def semantic_fingerprint_for(snapshot: "MarketReportSnapshotV0_2") -> str:
    return "sha256:" + sha256(canonical_json(_semantic_payload(snapshot)).encode("utf-8")).hexdigest()


def report_id_for(*, semantic_fingerprint: str, generated_at: str) -> str:
    return deterministic_id(
        "market-report-v0.2",
        {"report_version": MARKET_REPORT_V0_2_VERSION, "semantic_fingerprint": semantic_fingerprint, "generated_at": generated_at},
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketReportSnapshotV0_2(V0_2Contract):
    contract_version: str
    metadata: ReportMetadataV0_2
    category: CategoryContextV0_2
    sample: SampleContextV0_2
    data_window: DataWindowContextV0_2
    scope_context: ScopeContext
    market_size: MarketSizeSection
    true_competitor_set: TrueCompetitorSetSection
    competitor_structure: CompetitorStructureSection
    distributions: tuple[DistributionSectionItem, ...]
    competitor_details: tuple[CompetitorDetailSection, ...]
    buyer_needs: BuyerNeedProjection
    buyer_need_links: BuyerNeedLinkSection
    product_directions: ProductDirectionSection
    competitor_shortlist: CompetitorShortlistSection
    opportunity_score: OpportunityProjectionV0_2
    executive_summary: ExecutiveSummarySection
    evidence_registry: EvidenceRegistry
    sanitized_appendix: SanitizedAppendixSection
    external_integrations: ExternalIntegrationsRegistry
    provenance: tuple[ReportProvenanceRecord, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != REPORT_SNAPSHOT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported Market Report V0.2 snapshot contract")
        expected_types = (
            (self.metadata, ReportMetadataV0_2, "metadata"), (self.category, CategoryContextV0_2, "category"),
            (self.sample, SampleContextV0_2, "sample"), (self.data_window, DataWindowContextV0_2, "data_window"),
            (self.scope_context, ScopeContext, "scope_context"), (self.market_size, MarketSizeSection, "market_size"),
            (self.true_competitor_set, TrueCompetitorSetSection, "true_competitor_set"),
            (self.competitor_structure, CompetitorStructureSection, "competitor_structure"),
            (self.buyer_needs, BuyerNeedProjection, "buyer_needs"), (self.buyer_need_links, BuyerNeedLinkSection, "buyer_need_links"),
            (self.product_directions, ProductDirectionSection, "product_directions"),
            (self.competitor_shortlist, CompetitorShortlistSection, "competitor_shortlist"),
            (self.opportunity_score, OpportunityProjectionV0_2, "opportunity_score"),
            (self.executive_summary, ExecutiveSummarySection, "executive_summary"),
            (self.evidence_registry, EvidenceRegistry, "evidence_registry"),
            (self.sanitized_appendix, SanitizedAppendixSection, "sanitized_appendix"),
            (self.external_integrations, ExternalIntegrationsRegistry, "external_integrations"),
        )
        for value, expected, name in expected_types:
            if not isinstance(value, expected):
                raise MarketReportV0_2ValidationError(f"{name} has a wrong type")
        distributions = tuple(sorted(self.distributions, key=lambda item: item.distribution_id))
        details = tuple(sorted(self.competitor_details, key=lambda item: item.section_id))
        if any(not isinstance(item, DistributionSectionItem) for item in distributions):
            raise MarketReportV0_2ValidationError("distributions contain an invalid section")
        if any(not isinstance(item, CompetitorDetailSection) for item in details):
            raise MarketReportV0_2ValidationError("competitor_details contain an invalid section")
        if len({item.distribution_id for item in distributions}) != len(distributions):
            raise MarketReportV0_2ValidationError("distribution IDs must be unique")
        if len({item.section_id for item in details}) != len(details):
            raise MarketReportV0_2ValidationError("competitor detail section IDs must be unique")
        provenance = tuple(sorted(self.provenance, key=lambda item: item.provenance_id))
        if not provenance or any(not isinstance(item, ReportProvenanceRecord) for item in provenance):
            raise MarketReportV0_2ValidationError("snapshot requires report provenance")
        if len({item.provenance_id for item in provenance}) != len(provenance):
            raise MarketReportV0_2ValidationError("report provenance IDs must be unique")
        object.__setattr__(self, "distributions", distributions)
        object.__setattr__(self, "competitor_details", details)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "limitations", texts(self.limitations, "report limitations"))
        self._validate_context()
        self._validate_graph()
        expected_fingerprint = semantic_fingerprint_for(self)
        if self.metadata.semantic_fingerprint != expected_fingerprint:
            raise MarketReportV0_2ValidationError("semantic_fingerprint does not match the complete analytical graph")

    def _validate_context(self) -> None:
        marketplace_values = {
            self.category.marketplace,
            self.scope_context.marketplace,
            self.market_size.marketplace,
            self.competitor_structure.marketplace,
            *(item.marketplace for item in self.distributions),
        }
        if len(marketplace_values) != 1:
            raise MarketReportV0_2ValidationError("category/scope/section marketplace identities conflict")
        if self.category.source_reference_id != self.scope_context.category_reference_id:
            raise MarketReportV0_2ValidationError("category and ScopeContext do not share one source identity")
        cohort = self.scope_context.analysis_cohort_reference_id
        if self.sample.analysis_cohort_reference_id != cohort or self.market_size.cohort_reference_id != cohort:
            raise MarketReportV0_2ValidationError("sample/cohort graph is incompatible")
        if (
            self.scope_context.product_grain is ProductGrainV0_2.CHILD_ASIN
            and self.sample.unique_asin_count != self.scope_context.included_grain_entity_count
        ):
            raise MarketReportV0_2ValidationError("CHILD_ASIN sample count does not match the declared grain cohort")
        period_references = {
            reference_id
            for _, value in _walk(self)
            for item in fields(value)
            if item.name == "period_reference_id"
            for reference_id in (getattr(value, item.name),)
            if reference_id is not None
        }
        if period_references and period_references != {self.data_window.source_reference_id}:
            raise MarketReportV0_2ValidationError("metric observation periods do not agree with the report data window")
        if self.scope_context.product_grain is ProductGrainV0_2.MIXED_UNRESOLVED:
            if not self.market_size.unsafe_aggregate_guard or not self.competitor_structure.unsafe_aggregate_guard:
                raise MarketReportV0_2ValidationError("unresolved product grain cannot publish unsafe aggregates")
            if any(not item.unsafe_aggregate_guard for item in self.distributions):
                raise MarketReportV0_2ValidationError("unresolved product grain cannot validate distributions")

    def _validate_graph(self) -> None:
        references = {item.reference_id: item for item in self.evidence_registry.references}
        embedded: dict[str, ContractReference] = {}
        for _, value in _walk(self):
            for item in fields(value):
                child = getattr(value, item.name)
                candidates = (child,) if isinstance(child, ContractReference) else child if isinstance(child, (tuple, list)) else ()
                for candidate in candidates:
                    if isinstance(candidate, ContractReference):
                        prior = embedded.get(candidate.reference_id)
                        if prior is not None and prior != candidate:
                            raise MarketReportV0_2ValidationError("duplicate reference identity has conflicting content")
                        embedded[candidate.reference_id] = candidate
        missing_registry = sorted(set(embedded) - set(references))
        if missing_registry:
            raise MarketReportV0_2ValidationError(f"evidence registry omits represented references: {missing_registry}")
        for reference_id, record in embedded.items():
            if references[reference_id] != record:
                raise MarketReportV0_2ValidationError("evidence registry reference content conflicts with a section")
        requests = _reference_requests(self)
        orphan_reference_ids = sorted({reference_id for _, reference_id in requests} - set(references))
        if orphan_reference_ids:
            raise MarketReportV0_2ValidationError(f"snapshot contains orphan references: {orphan_reference_ids}")
        owned = _owned_ids(self)
        duplicate_owned = sorted(value for value, count in owned.items() if count != 1)
        if duplicate_owned:
            raise MarketReportV0_2ValidationError(f"report-local IDs are not globally unique: {duplicate_owned}")
        provenance_ids = {item.provenance_id for item in self.provenance}
        missing_provenance = sorted(_string_values(self, "provenance_reference_ids") - provenance_ids)
        if missing_provenance:
            raise MarketReportV0_2ValidationError(f"snapshot contains missing provenance references: {missing_provenance}")
        evidence_ids = {item.evidence_id for item in self.evidence_registry.evidence}
        missing_evidence = sorted(_string_values(self, "evidence_ids") - evidence_ids)
        if missing_evidence:
            raise MarketReportV0_2ValidationError(f"evidence registry omits represented evidence: {missing_evidence}")
        for reference in references.values():
            if reference.kind is ReferenceKind.EXTERNAL_PROVENANCE:
                if reference.namespace not in ALLOWED_EXTERNAL_NAMESPACES:
                    raise MarketReportV0_2ValidationError(f"unapproved external namespace: {reference.namespace}")
                if not set(reference.provenance_reference_ids) <= provenance_ids:
                    raise MarketReportV0_2ValidationError("external reference has missing provenance")
            else:
                if not reference.namespace.startswith("market-report-v0.2.") or not reference.target_version:
                    raise MarketReportV0_2ValidationError("report-local reference requires the V0.2 namespace and target version")
                if owned[reference.target_id] != 1:
                    raise MarketReportV0_2ValidationError(f"report-local reference does not resolve exactly once: {reference.reference_id}")
        edges: dict[str, set[str]] = defaultdict(set)
        for owner, reference_id in requests:
            reference = references[reference_id]
            if reference.kind is ReferenceKind.REPORT_LOCAL and owner is not None:
                edges[owner].add(reference.target_id)
        self._reject_cycles(edges)

    @staticmethod
    def _reject_cycles(edges: Mapping[str, set[str]]) -> None:
        active: set[str] = set()
        complete: set[str] = set()
        def visit(node: str) -> None:
            if node in active:
                raise MarketReportV0_2ValidationError("semantic reference cycle detected")
            if node in complete:
                return
            active.add(node)
            for target in edges.get(node, ()):
                visit(target)
            active.remove(node)
            complete.add(node)
        for node in tuple(edges):
            visit(node)

    def validate(self) -> "MarketReportSnapshotV0_2":
        self.__post_init__()
        return self

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":") if indent is None else None, indent=indent)


__all__ = ("MarketReportSnapshotV0_2", "report_id_for", "semantic_fingerprint_for")
