"""Evidence-first contracts for ASIN reverse-keyword organic discovery V0.1."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.contracts import (
    JsonContract,
    KeywordIdentity,
    Severity,
    deterministic_id,
)


ORGANIC_KEYWORD_DISCOVERY_CONTRACT_VERSION = "organic-keyword-discovery-contract-v0.1"
ORGANIC_KEYWORD_DISCOVERY_RUNNER_VERSION = "organic-keyword-discovery-runner-v0.1"


class OrganicKeywordDiscoveryError(ValueError):
    """Raised when an organic discovery contract is invalid."""


class QueryRole(StrEnum):
    DISCOVERED_CANDIDATE = "DISCOVERED_CANDIDATE"
    VALIDATION_QUERY = "VALIDATION_QUERY"


class QueryOrigin(StrEnum):
    ASIN_REVERSE_RETURNED = "ASIN_REVERSE_RETURNED"


class OrganicTrafficStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class OrganicCoverageStatus(StrEnum):
    COMPLETE_OR_SINGLE_PAGE = "COMPLETE_OR_SINGLE_PAGE"
    FIRST_PAGE_ONLY = "FIRST_PAGE_ONLY"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    UNKNOWN = "UNKNOWN"


class ProviderCallStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OrganicKeywordDiscoveryError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise OrganicKeywordDiscoveryError(f"{path} must be a non-negative integer")
    return value


def _share(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0"
    return format(Decimal(numerator) / Decimal(denominator), "f")


def _number_text(value: Any, path: str) -> str | None:
    if value is None:
        return None
    if type(value) is bool:
        raise OrganicKeywordDiscoveryError(f"{path} must be numeric text")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OrganicKeywordDiscoveryError(f"{path} must be numeric text") from exc
    if not number.is_finite() or number < 0:
        raise OrganicKeywordDiscoveryError(f"{path} must be finite and non-negative")
    return format(number, "f")


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicDiscoveryDiagnostic(JsonContract):
    diagnostic_id: str
    code: str
    severity: Severity
    message: str
    related_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.code, "diagnostic.code")
        _text(self.message, "diagnostic.message")
        if not isinstance(self.severity, Severity):
            raise OrganicKeywordDiscoveryError("diagnostic severity is invalid")
        related = tuple(sorted(set(self.related_ids)))
        if any(type(item) is not str or not item.strip() for item in related):
            raise OrganicKeywordDiscoveryError("diagnostic related ids require text")
        object.__setattr__(self, "related_ids", related)
        payload = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "related_ids": related,
        }
        if self.diagnostic_id != deterministic_id("organic-discovery-diagnostic", payload):
            raise OrganicKeywordDiscoveryError("diagnostic_id does not match content")


def build_diagnostic(
    code: str,
    message: str,
    *,
    severity: Severity = Severity.INFO,
    related_ids: Sequence[str] = (),
) -> OrganicDiscoveryDiagnostic:
    payload = {
        "code": code,
        "severity": severity,
        "message": message,
        "related_ids": tuple(sorted(set(related_ids))),
    }
    return OrganicDiscoveryDiagnostic(
        diagnostic_id=deterministic_id("organic-discovery-diagnostic", payload),
        **payload,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicKeywordRankEvidence(JsonContract):
    channel: str
    total_rank: int | None
    page: int | None
    page_rank: int | None
    rank_time: str | None

    def __post_init__(self) -> None:
        if self.channel not in {"ORGANIC", "SPONSORED"}:
            raise OrganicKeywordDiscoveryError("rank channel is invalid")
        for name in ("total_rank", "page", "page_rank"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise OrganicKeywordDiscoveryError(f"rank {name} must be non-negative")
        if self.rank_time is not None:
            _text(self.rank_time, "rank_time")


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicKeywordSourceEvidence(JsonContract):
    query_execution_id: str
    relationship_observation_ids: tuple[str, ...]
    raw_evidence_id: str
    collection_run_id: str
    transformation_run_id: str
    mapping_version: str
    provider: str
    source_tool: str
    source_fields: tuple[str, ...]
    bundle_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "query_execution_id",
            "raw_evidence_id",
            "collection_run_id",
            "transformation_run_id",
            "mapping_version",
            "provider",
            "source_tool",
            "bundle_fingerprint",
        ):
            _text(getattr(self, name), f"source_evidence.{name}")
        relationships = tuple(sorted(set(self.relationship_observation_ids)))
        fields = tuple(sorted(set(self.source_fields)))
        if not relationships or not fields:
            raise OrganicKeywordDiscoveryError("source evidence requires relationships and fields")
        object.__setattr__(self, "relationship_observation_ids", relationships)
        object.__setattr__(self, "source_fields", fields)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicKeywordDiscoveryRecord(JsonContract):
    discovery_id: str
    marketplace: str
    source_asin: str
    keyword_identity: KeywordIdentity
    provider_returned_text: str
    normalized_text: str
    query_role: QueryRole
    query_origin: QueryOrigin
    provider_returned: bool
    human_seeded: bool
    derived_from_asin: bool
    provider_operation: str
    provider_request_ref: str
    provider_response_ref: str
    period: str
    page: int
    rank: tuple[OrganicKeywordRankEvidence, ...]
    organic_traffic: str | None
    ad_traffic: str | None
    traffic_status: OrganicTrafficStatus
    coverage_status: OrganicCoverageStatus
    source_evidence: tuple[OrganicKeywordSourceEvidence, ...]
    diagnostics: tuple[OrganicDiscoveryDiagnostic, ...] = ()
    contract_version: str = ORGANIC_KEYWORD_DISCOVERY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper():
            raise OrganicKeywordDiscoveryError("marketplace must be uppercase")
        if len(self.source_asin) != 10 or not self.source_asin.isalnum() or self.source_asin != self.source_asin.upper():
            raise OrganicKeywordDiscoveryError("source_asin must be an uppercase ASIN")
        if not isinstance(self.keyword_identity, KeywordIdentity):
            raise OrganicKeywordDiscoveryError("keyword_identity has a wrong type")
        if self.keyword_identity.marketplace != self.marketplace:
            raise OrganicKeywordDiscoveryError("keyword marketplace mismatch")
        _text(self.provider_returned_text, "provider_returned_text")
        _text(self.normalized_text, "normalized_text")
        for name in (
            "provider_operation",
            "provider_request_ref",
            "provider_response_ref",
            "period",
        ):
            _text(getattr(self, name), name)
        if self.provider_returned_text != self.keyword_identity.raw_text:
            raise OrganicKeywordDiscoveryError("provider text must preserve KeywordIdentity raw text")
        if self.normalized_text != self.keyword_identity.normalized_text:
            raise OrganicKeywordDiscoveryError("normalized text must preserve KeywordIdentity")
        if self.query_role is not QueryRole.DISCOVERED_CANDIDATE:
            raise OrganicKeywordDiscoveryError("organic record must be DISCOVERED_CANDIDATE")
        if self.query_origin is not QueryOrigin.ASIN_REVERSE_RETURNED:
            raise OrganicKeywordDiscoveryError("organic record origin must be ASIN_REVERSE_RETURNED")
        if self.provider_returned is not True or self.human_seeded is not False or self.derived_from_asin is not True:
            raise OrganicKeywordDiscoveryError("organic provenance flags are invalid")
        if self.provider_operation not in {"asin_keywords", "asin_keywords_monthly"}:
            raise OrganicKeywordDiscoveryError(
                "organic record must use an audited ASIN reverse-keyword operation"
            )
        if type(self.page) is not int or self.page < 1:
            raise OrganicKeywordDiscoveryError("page must be a positive integer")
        ranks = tuple(self.rank)
        evidence = tuple(self.source_evidence)
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, OrganicKeywordRankEvidence) for item in ranks):
            raise OrganicKeywordDiscoveryError("rank contains an invalid item")
        if not evidence or any(not isinstance(item, OrganicKeywordSourceEvidence) for item in evidence):
            raise OrganicKeywordDiscoveryError("organic record requires source evidence")
        if any(not isinstance(item, OrganicDiscoveryDiagnostic) for item in diagnostics):
            raise OrganicKeywordDiscoveryError("record diagnostics contain an invalid item")
        object.__setattr__(self, "rank", tuple(sorted(ranks, key=lambda item: (item.channel, item.total_rank or 10**9))))
        object.__setattr__(self, "source_evidence", tuple(sorted(evidence, key=lambda item: item.query_execution_id)))
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)))
        organic = _number_text(self.organic_traffic, "organic_traffic")
        advertising = _number_text(self.ad_traffic, "ad_traffic")
        object.__setattr__(self, "organic_traffic", organic)
        object.__setattr__(self, "ad_traffic", advertising)
        expected_status = (
            OrganicTrafficStatus.AVAILABLE
            if organic is not None and advertising is not None
            else OrganicTrafficStatus.PARTIAL
            if organic is not None or advertising is not None
            else OrganicTrafficStatus.UNKNOWN
        )
        if self.traffic_status is not expected_status:
            raise OrganicKeywordDiscoveryError("traffic_status does not match traffic values")
        if self.contract_version != ORGANIC_KEYWORD_DISCOVERY_CONTRACT_VERSION:
            raise OrganicKeywordDiscoveryError("invalid organic discovery contract version")
        payload = self.to_dict()
        payload.pop("discovery_id")
        if self.discovery_id != deterministic_id("organic-keyword-discovery", payload):
            raise OrganicKeywordDiscoveryError("discovery_id does not match content")


def build_organic_keyword_record(**values: Any) -> OrganicKeywordDiscoveryRecord:
    payload = dict(values)
    payload.setdefault("contract_version", ORGANIC_KEYWORD_DISCOVERY_CONTRACT_VERSION)
    payload["rank"] = tuple(
        sorted(
            payload.get("rank", ()),
            key=lambda item: (item.channel, item.total_rank or 10**9),
        )
    )
    payload["source_evidence"] = tuple(
        sorted(
            payload.get("source_evidence", ()),
            key=lambda item: item.query_execution_id,
        )
    )
    payload["diagnostics"] = tuple(
        sorted(
            payload.get("diagnostics", ()),
            key=lambda item: item.diagnostic_id,
        )
    )
    payload["organic_traffic"] = _number_text(
        payload.get("organic_traffic"), "organic_traffic"
    )
    payload["ad_traffic"] = _number_text(payload.get("ad_traffic"), "ad_traffic")
    return OrganicKeywordDiscoveryRecord(
        discovery_id=deterministic_id("organic-keyword-discovery", payload),
        **payload,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicKeywordSummary(JsonContract):
    keyword_identity: KeywordIdentity
    relation_count: int
    asin_coverage_count: int
    asin_coverage_share: str
    provider_traffic_sum: str | None
    best_organic_rank: int | None
    discovery_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _count(self.relation_count, "summary.relation_count")
        _count(self.asin_coverage_count, "summary.asin_coverage_count")
        _number_text(self.asin_coverage_share, "summary.asin_coverage_share")
        _number_text(self.provider_traffic_sum, "summary.provider_traffic_sum")
        if self.best_organic_rank is not None:
            _count(self.best_organic_rank, "summary.best_organic_rank")
        discoveries = tuple(sorted(set(self.discovery_ids)))
        if len(discoveries) != self.relation_count:
            raise OrganicKeywordDiscoveryError("summary discovery count mismatch")
        object.__setattr__(self, "discovery_ids", discoveries)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicCorpusCoverage(JsonContract):
    requested_source_asin_count: int
    successful_source_asin_count: int
    failed_source_asin_count: int
    empty_source_asin_count: int
    source_asin_success_share: str
    first_page_only_asin_count: int

    def __post_init__(self) -> None:
        for name in (
            "requested_source_asin_count",
            "successful_source_asin_count",
            "failed_source_asin_count",
            "empty_source_asin_count",
            "first_page_only_asin_count",
        ):
            _count(getattr(self, name), f"coverage.{name}")
        if self.successful_source_asin_count + self.failed_source_asin_count + self.empty_source_asin_count != self.requested_source_asin_count:
            raise OrganicKeywordDiscoveryError("coverage ASIN counts do not sum to requested count")
        if self.source_asin_success_share != _share(
            self.successful_source_asin_count, self.requested_source_asin_count
        ):
            raise OrganicKeywordDiscoveryError("coverage success share mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicKeywordCorpusSnapshot(JsonContract):
    snapshot_id: str
    unique_keyword_count: int
    asin_keyword_relation_count: int
    source_asin_count: int
    duplicate_keyword_count: int
    coverage: OrganicCorpusCoverage
    rank_distribution: Mapping[str, int]
    traffic_availability: Mapping[str, int]
    top_keywords: tuple[OrganicKeywordSummary, ...]
    source_evidence: tuple[str, ...]
    diagnostics: tuple[OrganicDiscoveryDiagnostic, ...]
    runner_version: str = ORGANIC_KEYWORD_DISCOVERY_RUNNER_VERSION

    def __post_init__(self) -> None:
        for name in (
            "unique_keyword_count",
            "asin_keyword_relation_count",
            "source_asin_count",
            "duplicate_keyword_count",
        ):
            _count(getattr(self, name), name)
        if self.duplicate_keyword_count != self.asin_keyword_relation_count - self.unique_keyword_count:
            raise OrganicKeywordDiscoveryError("duplicate count must be relation count minus unique count")
        if not isinstance(self.coverage, OrganicCorpusCoverage):
            raise OrganicKeywordDiscoveryError("corpus coverage has a wrong type")
        ranks = dict(sorted(self.rank_distribution.items()))
        traffic = dict(sorted(self.traffic_availability.items()))
        if any(type(value) is not int or value < 0 for value in (*ranks.values(), *traffic.values())):
            raise OrganicKeywordDiscoveryError("corpus distributions require non-negative counts")
        object.__setattr__(self, "rank_distribution", MappingProxyType(ranks))
        object.__setattr__(self, "traffic_availability", MappingProxyType(traffic))
        object.__setattr__(self, "top_keywords", tuple(self.top_keywords))
        object.__setattr__(self, "source_evidence", tuple(sorted(set(self.source_evidence))))
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics, key=lambda item: item.diagnostic_id)))
        if self.runner_version != ORGANIC_KEYWORD_DISCOVERY_RUNNER_VERSION:
            raise OrganicKeywordDiscoveryError("invalid organic discovery runner version")
        payload = self.to_dict()
        payload.pop("snapshot_id")
        if self.snapshot_id != deterministic_id("organic-keyword-corpus", payload):
            raise OrganicKeywordDiscoveryError("corpus snapshot_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderCallAudit(JsonContract):
    call_id: str
    operation: str
    status: ProviderCallStatus
    request_ref: str
    response_ref: str | None
    source_asin: str | None
    page: int | None
    returned_count: int
    provider_total: int | None
    cost_credits: int | None
    x_cost_credits: str | None
    diagnostic: str | None

    def __post_init__(self) -> None:
        for name in ("operation", "request_ref"):
            _text(getattr(self, name), f"call.{name}")
        if not isinstance(self.status, ProviderCallStatus):
            raise OrganicKeywordDiscoveryError("call status is invalid")
        for name in ("returned_count",):
            _count(getattr(self, name), f"call.{name}")
        for name in ("provider_total", "cost_credits"):
            value = getattr(self, name)
            if value is not None:
                _count(value, f"call.{name}")
        if self.page is not None and (type(self.page) is not int or self.page < 1):
            raise OrganicKeywordDiscoveryError("call page must be positive")
        for name in ("response_ref", "source_asin", "x_cost_credits", "diagnostic"):
            value = getattr(self, name)
            if value is not None:
                _text(value, f"call.{name}")
        payload = self.to_dict()
        payload.pop("call_id")
        if self.call_id != deterministic_id("organic-provider-call", payload):
            raise OrganicKeywordDiscoveryError("call_id does not match content")


def build_call_audit(**values: Any) -> ProviderCallAudit:
    return ProviderCallAudit(
        call_id=deterministic_id("organic-provider-call", values),
        **values,
    )


def build_corpus_snapshot(
    records: Sequence[OrganicKeywordDiscoveryRecord],
    *,
    requested_asins: Sequence[str],
    failed_asins: Sequence[str] = (),
    empty_asins: Sequence[str] = (),
    diagnostics: Sequence[OrganicDiscoveryDiagnostic] = (),
) -> OrganicKeywordCorpusSnapshot:
    ordered = tuple(sorted(records, key=lambda item: item.discovery_id))
    groups: dict[str, list[OrganicKeywordDiscoveryRecord]] = defaultdict(list)
    for record in ordered:
        groups[record.keyword_identity.keyword_id].append(record)
    summaries: list[OrganicKeywordSummary] = []
    denominator = len(set(requested_asins))
    for keyword_id in sorted(groups):
        relations = groups[keyword_id]
        asins = {item.source_asin for item in relations}
        traffic_values = [Decimal(item.organic_traffic) for item in relations if item.organic_traffic is not None]
        ranks = [
            rank.total_rank
            for item in relations
            for rank in item.rank
            if rank.channel == "ORGANIC" and rank.total_rank is not None
        ]
        summaries.append(
            OrganicKeywordSummary(
                keyword_identity=relations[0].keyword_identity,
                relation_count=len(relations),
                asin_coverage_count=len(asins),
                asin_coverage_share=_share(len(asins), denominator),
                provider_traffic_sum=(format(sum(traffic_values), "f") if traffic_values else None),
                best_organic_rank=min(ranks) if ranks else None,
                discovery_ids=tuple(item.discovery_id for item in relations),
            )
        )
    summaries.sort(
        key=lambda item: (
            -item.asin_coverage_count,
            -(Decimal(item.provider_traffic_sum) if item.provider_traffic_sum is not None else Decimal("-1")),
            item.best_organic_rank if item.best_organic_rank is not None else 10**9,
            item.keyword_identity.normalized_text,
        )
    )
    failed = set(failed_asins)
    empty = set(empty_asins)
    successful = set(requested_asins) - failed - empty
    coverage = OrganicCorpusCoverage(
        requested_source_asin_count=denominator,
        successful_source_asin_count=len(successful),
        failed_source_asin_count=len(failed),
        empty_source_asin_count=len(empty),
        source_asin_success_share=_share(len(successful), denominator),
        first_page_only_asin_count=len(
            {
                item.source_asin
                for item in ordered
                if item.coverage_status is OrganicCoverageStatus.FIRST_PAGE_ONLY
            }
        ),
    )
    rank_distribution = Counter(
        "ORGANIC_RANK_AVAILABLE"
        if any(rank.channel == "ORGANIC" for rank in item.rank)
        else "ORGANIC_RANK_UNKNOWN"
        for item in ordered
    )
    traffic_availability = Counter(item.traffic_status.value for item in ordered)
    payload = {
        "unique_keyword_count": len(groups),
        "asin_keyword_relation_count": len(ordered),
        "source_asin_count": len({item.source_asin for item in ordered}),
        "duplicate_keyword_count": len(ordered) - len(groups),
        "coverage": coverage,
        "rank_distribution": dict(sorted(rank_distribution.items())),
        "traffic_availability": dict(sorted(traffic_availability.items())),
        "top_keywords": tuple(summaries),
        "source_evidence": tuple(
            sorted(
                {
                    evidence.raw_evidence_id
                    for item in ordered
                    for evidence in item.source_evidence
                }
            )
        ),
        "diagnostics": tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        "runner_version": ORGANIC_KEYWORD_DISCOVERY_RUNNER_VERSION,
    }
    return OrganicKeywordCorpusSnapshot(
        snapshot_id=deterministic_id("organic-keyword-corpus", payload),
        **payload,
    )


__all__ = (
    "ORGANIC_KEYWORD_DISCOVERY_CONTRACT_VERSION",
    "ORGANIC_KEYWORD_DISCOVERY_RUNNER_VERSION",
    "OrganicCorpusCoverage",
    "OrganicCoverageStatus",
    "OrganicDiscoveryDiagnostic",
    "OrganicKeywordCorpusSnapshot",
    "OrganicKeywordDiscoveryError",
    "OrganicKeywordDiscoveryRecord",
    "OrganicKeywordRankEvidence",
    "OrganicKeywordSourceEvidence",
    "OrganicKeywordSummary",
    "OrganicTrafficStatus",
    "ProviderCallAudit",
    "ProviderCallStatus",
    "QueryOrigin",
    "QueryRole",
    "build_call_audit",
    "build_corpus_snapshot",
    "build_diagnostic",
    "build_organic_keyword_record",
)
