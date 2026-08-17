"""Provider-neutral adapter boundary for audited V0.1 mappings."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from amazon_product_intelligence.contracts import (
    BlockingScope,
    CanonicalEvidenceBundle,
    CanonicalObservation,
    Channel,
    CodeVersionScheme,
    ContractValidationError,
    DataQualityIssue,
    EstimateMethodStatus,
    EvidenceType,
    FactGroup,
    KeywordIdentity,
    KeywordMetricObservation,
    MetricObservation,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    OriginStage,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    Provenance,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    RawEvidenceRecord,
    RelationshipDirection,
    RelationshipType,
    ResultStatus,
    ReviewObservation,
    Scope,
    ScopeStatus,
    ScopeType,
    SemanticStatus,
    Severity,
    SubjectRef,
    SubjectType,
    TimeWindow,
    TransformationCodeVersion,
    TransformationProvenance,
    TransformationRunRecord,
    TransformationStatus,
    Unit,
    ValueEnvelope,
    ValueType,
    VersionStatus,
    canonical_json,
    deterministic_id,
    keyword_id,
    observation_revision_id,
    product_id,
    raw_evidence_id,
    relationship_observation_id,
    semantic_observation_id,
)


ADAPTER_RULESET_VERSION = "provider-adapters-v0.1"
_ASIN = re.compile(r"^[A-Z0-9]{10}$")


class AdapterError(ValueError):
    """Base exception for invalid adapter API usage."""


class AdapterContextError(AdapterError):
    """Raised when required explicit adaptation context is invalid."""


class MappingDisposition(StrEnum):
    """Authority classification for a source mapping or diagnostic."""

    APPROVED_EXECUTABLE = "APPROVED_EXECUTABLE"
    APPROVED_WITH_EXPLICIT_UNKNOWN = "APPROVED_WITH_EXPLICIT_UNKNOWN"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"
    SEMANTICS_UNCONFIRMED = "SEMANTICS_UNCONFIRMED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class AdapterFailureLevel(StrEnum):
    """Failure boundary used by structured adapter results."""

    COLLECTION = "COLLECTION"
    RECORD = "RECORD"
    FIELD = "FIELD"


@dataclass(frozen=True, slots=True, kw_only=True)
class MappingSpecification:
    """Identity of one audited Raw Provider Evidence to Canonical mapping."""

    specification_id: str
    version: str
    mapping_version: str
    provider: str
    payload_kind: str
    source_tool: str
    disposition: MappingDisposition = MappingDisposition.APPROVED_EXECUTABLE

    def __post_init__(self) -> None:
        for name in (
            "specification_id",
            "version",
            "mapping_version",
            "provider",
            "payload_kind",
            "source_tool",
        ):
            _require_text(name, getattr(self, name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "specification_id": self.specification_id,
            "version": self.version,
            "mapping_version": self.mapping_version,
            "provider": self.provider,
            "payload_kind": self.payload_kind,
            "source_tool": self.source_tool,
            "disposition": self.disposition.value,
        }


def _unknown_provider_schema() -> ProviderSchemaVersion:
    return ProviderSchemaVersion(
        status=VersionStatus.UNKNOWN,
        value=None,
        source=ProviderSchemaSource.UNKNOWN,
    )


def _adapter_code_version() -> TransformationCodeVersion:
    return TransformationCodeVersion(
        status=VersionStatus.KNOWN,
        value=ADAPTER_RULESET_VERSION,
        scheme=CodeVersionScheme.RULESET_VERSION,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class AdaptationContext:
    """Explicit deterministic context for one offline adaptation execution."""

    provider: str
    payload_kind: str
    source_tool: str
    marketplace: str
    locale: str
    retrieved_at: str
    transformed_at: str
    collection_run_id: str
    sanitized_request: Mapping[str, Any] = field(default_factory=dict)
    currency: str | None = None
    provider_schema_version: ProviderSchemaVersion = field(default_factory=_unknown_provider_schema)
    transformation_code_version: TransformationCodeVersion = field(default_factory=_adapter_code_version)

    def __post_init__(self) -> None:
        for name in (
            "provider",
            "payload_kind",
            "source_tool",
            "marketplace",
            "locale",
            "collection_run_id",
        ):
            try:
                _require_text(name, getattr(self, name))
            except AdapterError as exc:
                raise AdapterContextError(str(exc)) from exc
        if self.marketplace != self.marketplace.strip().upper():
            raise AdapterContextError("marketplace must be normalized uppercase text")
        if self.locale != self.locale.strip().lower():
            raise AdapterContextError("locale must be normalized lowercase text")
        if self.currency is not None:
            if self.currency != self.currency.strip().upper() or len(self.currency) != 3:
                raise AdapterContextError("currency must be a normalized three-letter code")
        for name in ("retrieved_at", "transformed_at"):
            try:
                _validate_datetime(name, getattr(self, name))
            except AdapterError as exc:
                raise AdapterContextError(str(exc)) from exc
        try:
            frozen_request = _freeze_json(self.sanitized_request, "sanitized_request")
        except AdapterError as exc:
            raise AdapterContextError(str(exc)) from exc
        if not isinstance(frozen_request, MappingABC):
            raise AdapterContextError("sanitized_request must be a mapping")
        object.__setattr__(self, "sanitized_request", frozen_request)


@dataclass(frozen=True, slots=True, kw_only=True)
class AdapterDiagnostic:
    """Non-exception mapping coverage or field-quality diagnostic."""

    code: str
    message: str
    source_locator: str
    disposition: MappingDisposition
    blocking: bool = False
    raw_evidence_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source_locator": self.source_locator,
            "disposition": self.disposition.value,
            "blocking": self.blocking,
            "raw_evidence_reference": self.raw_evidence_reference,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AdapterFailure:
    """Structured fail-closed error returned without canonical observations."""

    code: str
    message: str
    level: AdapterFailureLevel
    source_locator: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "level": self.level.value,
            "source_locator": self.source_locator,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AdaptationStatistics:
    """Small deterministic summary of a mapping execution."""

    mapped_observation_count: int
    quality_issue_count: int
    diagnostic_count: int
    error_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "mapped_observation_count": self.mapped_observation_count,
            "quality_issue_count": self.quality_issue_count,
            "diagnostic_count": self.diagnostic_count,
            "error_count": self.error_count,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AdaptationResult:
    """Auditable adapter output wrapping one validated canonical bundle."""

    provider: str
    adapter_version: str
    payload_kind: str
    mapping_specification: MappingSpecification | None
    raw_evidence: RawEvidenceRecord | None
    raw_snapshot: Any
    bundle: CanonicalEvidenceBundle
    diagnostics: tuple[AdapterDiagnostic, ...]
    errors: tuple[AdapterFailure, ...]
    statistics: AdaptationStatistics

    @property
    def succeeded(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "adapter_version": self.adapter_version,
            "payload_kind": self.payload_kind,
            "mapping_specification": (
                self.mapping_specification.to_dict() if self.mapping_specification is not None else None
            ),
            "raw_evidence": self.raw_evidence.to_dict() if self.raw_evidence is not None else None,
            "raw_snapshot": _thaw_json(self.raw_snapshot),
            "bundle": self.bundle.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "errors": [item.to_dict() for item in self.errors],
            "statistics": self.statistics.to_dict(),
        }


@runtime_checkable
class ProviderAdapter(Protocol):
    """Minimal provider-neutral interface implemented by audited adapters."""

    provider: str
    adapter_version: str
    supported_payload_kinds: tuple[str, ...]

    def adapt(self, payload: Any, context: AdaptationContext) -> AdaptationResult:
        """Adapt one explicit provider payload without transport or side effects."""


def _require_text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"{name} must be a non-empty string")


def _validate_datetime(name: str, value: str) -> None:
    try:
        TimeWindow(
            observed_at=None,
            observed_at_status=ObservedAtStatus.UNKNOWN,
            retrieved_at=value,
            period_start=None,
            period_end=None,
            period_type=PeriodType.UNKNOWN,
            timezone=None,
        )
    except ContractValidationError as exc:
        raise AdapterError(f"{name} must be an RFC 3339 date-time") from exc


def _freeze_json(value: Any, path: str = "$") -> Any:
    if isinstance(value, MappingABC):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise AdapterError(f"{path} mapping keys must be strings")
            frozen[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item, f"{path}[{index}]") for index, item in enumerate(value))
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise AdapterError(f"{path} must not contain NaN or infinity")
        return value
    raise AdapterError(f"{path} contains unsupported JSON type {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, MappingABC):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw_json(item) for item in value]
    return value


def _snapshot_json(payload: Any) -> tuple[Any, str]:
    try:
        serialized = canonical_json(payload)
    except ContractValidationError as exc:
        raise AdapterError(str(exc)) from exc
    detached = json.loads(serialized)
    return _freeze_json(detached), sha256(serialized.encode("utf-8")).hexdigest()


def normalized_asin(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper()
    return candidate if _ASIN.fullmatch(candidate) else None


def strict_number(value: Any, *, allow_numeric_string: bool = False) -> int | float | None:
    """Return a finite non-boolean number under an explicitly selected policy."""

    if type(value) is int:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if allow_numeric_string and isinstance(value, str) and re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?", value):
        parsed = float(value) if "." in value else int(value)
        return parsed if math.isfinite(float(parsed)) else None
    return None


def product_identity(marketplace: str, asin: str, *, parent_asin: str | None = None) -> ProductIdentity:
    return ProductIdentity(
        product_id=product_id(marketplace, asin),
        marketplace=marketplace,
        asin=asin,
        parent_asin=parent_asin,
        identity_status="CONFIRMED",
    )


def keyword_identity(marketplace: str, locale: str, raw_text: str) -> KeywordIdentity:
    normalized = " ".join(raw_text.split()).casefold()
    return KeywordIdentity(
        keyword_id=keyword_id(marketplace, locale, normalized),
        marketplace=marketplace,
        locale=locale,
        normalized_text=normalized,
        raw_text=raw_text,
    )


def product_subject(product: ProductIdentity) -> SubjectRef:
    return SubjectRef(
        subject_type=SubjectType.PRODUCT,
        subject_id=product.product_id,
        marketplace=product.marketplace,
    )


def keyword_subject(keyword: KeywordIdentity) -> SubjectRef:
    return SubjectRef(
        subject_type=SubjectType.KEYWORD,
        subject_id=keyword.keyword_id,
        marketplace=keyword.marketplace,
    )


def relationship_subject(
    product: ProductIdentity,
    keyword: KeywordIdentity,
) -> SubjectRef:
    subject_id = deterministic_id(
        "relationship-subject",
        {"product_id": product.product_id, "keyword_id": keyword.keyword_id},
    )
    return SubjectRef(
        subject_type=SubjectType.PRODUCT_KEYWORD_RELATIONSHIP,
        subject_id=subject_id,
        marketplace=product.marketplace,
    )


def value_envelope(
    *,
    presence_status: PresenceStatus,
    raw_value: Any,
    normalized_value: Any,
    value_type: ValueType,
    unit: Unit | None = None,
    normalization_status: NormalizationStatus = NormalizationStatus.NOT_ATTEMPTED,
    semantic_status: SemanticStatus = SemanticStatus.CONFIRMED,
) -> ValueEnvelope:
    return ValueEnvelope(
        presence_status=presence_status,
        raw_value=raw_value,
        normalized_value=normalized_value,
        value_type=value_type,
        unit=unit,
        normalization_status=normalization_status,
        semantic_status=semantic_status,
    )


def absent_value(
    status: PresenceStatus,
    value_type: ValueType,
    *,
    semantic_status: SemanticStatus = SemanticStatus.CONFIRMED,
    unit: Unit | None = None,
) -> ValueEnvelope:
    return value_envelope(
        presence_status=status,
        raw_value=None,
        normalized_value=None,
        value_type=value_type,
        unit=unit,
        normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        semantic_status=semantic_status,
    )


class _AdapterSession:
    """Internal deterministic builder shared by concrete adapters."""

    def __init__(
        self,
        *,
        provider: str,
        adapter_version: str,
        mapping_specification: MappingSpecification,
        context: AdaptationContext,
        payload: Mapping[str, Any],
        raw_response_status: str = "SUCCESS",
    ) -> None:
        self.provider = provider
        self.adapter_version = adapter_version
        self.mapping_specification = mapping_specification
        self.context = context
        snapshot, response_fingerprint = _snapshot_json(payload)
        if not isinstance(snapshot, MappingABC):
            raise AdapterError("provider payload must be a mapping")
        self.raw_snapshot = snapshot
        request_fingerprint = sha256(canonical_json(context.sanitized_request).encode("utf-8")).hexdigest()
        self.raw_evidence_id = raw_evidence_id(
            provider=provider,
            source_tool=context.source_tool,
            sanitized_request_fingerprint=f"sha256:v1:{request_fingerprint}",
            retrieved_at=context.retrieved_at,
            response_fingerprint=f"sha256:v1:{response_fingerprint}",
        )
        self.raw_evidence = RawEvidenceRecord(
            raw_evidence_id=self.raw_evidence_id,
            collection_run_id=context.collection_run_id,
            provider=provider,
            source_tool=context.source_tool,
            provider_schema_version=context.provider_schema_version,
            sanitized_request=context.sanitized_request,
            retrieved_at=context.retrieved_at,
            response_status=raw_response_status,
            media_type="application/json",
            content_reference=f"inline:{self.raw_evidence_id}",
            content_fingerprint=f"sha256:v1:{response_fingerprint}",
        )
        self.transformation_run_id = deterministic_id(
            "transform",
            {
                "provider": provider,
                "adapter_version": adapter_version,
                "mapping_version": mapping_specification.mapping_version,
                "collection_run_id": context.collection_run_id,
                "raw_evidence_id": self.raw_evidence_id,
                "transformed_at": context.transformed_at,
                "transformation_code_version": context.transformation_code_version,
            },
        )
        self.observations: list[CanonicalObservation] = []
        self.issues: list[DataQualityIssue] = []
        self.diagnostics: list[AdapterDiagnostic] = []
        self.errors: list[AdapterFailure] = []
        self._partial = False

    @property
    def payload(self) -> Mapping[str, Any]:
        return self.raw_snapshot

    def diagnostic(
        self,
        *,
        code: str,
        message: str,
        source_locator: str,
        disposition: MappingDisposition,
        blocking: bool = False,
        affects_status: bool = True,
    ) -> None:
        self.diagnostics.append(
            AdapterDiagnostic(
                code=code,
                message=message,
                source_locator=source_locator,
                disposition=disposition,
                blocking=blocking,
                raw_evidence_reference=self.raw_evidence_id,
            )
        )
        self._partial = self._partial or affects_status

    def quality_issue(
        self,
        *,
        code: str,
        subject: SubjectRef,
        dimension: str | None,
        message: str,
        source_references: Sequence[str] | None = None,
        severity: Severity = Severity.WARNING,
        blocking_scope: BlockingScope = BlockingScope.FIELD,
        origin_stage: OriginStage = OriginStage.RAW_EVIDENCE,
    ) -> str:
        references = tuple(source_references or (self.raw_evidence_id,))
        issue_id = deterministic_id(
            "dqi",
            {
                "provider": self.provider,
                "mapping_version": self.mapping_specification.mapping_version,
                "raw_evidence_id": self.raw_evidence_id,
                "code": code,
                "subject": subject,
                "dimension": dimension,
                "message": message,
                "source_references": sorted(references),
            },
        )
        issue = DataQualityIssue(
            issue_id=issue_id,
            issue_code=code,
            severity=severity,
            subject=subject,
            dimension=dimension,
            message=message,
            blocking=blocking_scope is not BlockingScope.NONE,
            blocking_scope=blocking_scope,
            source_references=references,
            created_at=self.context.transformed_at,
            origin_stage=origin_stage,
            collection_run_id=(self.context.collection_run_id if origin_stage is OriginStage.COLLECTION else None),
            transformation_run_id=(
                self.transformation_run_id
                if origin_stage in {OriginStage.MAPPING, OriginStage.NORMALIZATION}
                else None
            ),
            mapping_version=(
                self.mapping_specification.mapping_version
                if origin_stage in {OriginStage.MAPPING, OriginStage.NORMALIZATION}
                else None
            ),
        )
        if issue_id not in {item.issue_id for item in self.issues}:
            self.issues.append(issue)
        self._partial = True
        return issue_id

    def attach_issue(self, observation_ids: Sequence[str], issue_id: str) -> None:
        wanted = set(observation_ids)
        updated: list[CanonicalObservation] = []
        for observation in self.observations:
            if observation.observation_id in wanted and issue_id not in observation.quality_issue_ids:
                observation = replace(
                    observation,
                    quality_issue_ids=observation.quality_issue_ids + (issue_id,),
                    result_status=ResultStatus.PARTIAL,
                )
            updated.append(observation)
        self.observations = updated

    def _transformation(self) -> TransformationProvenance:
        return TransformationProvenance(
            collection_run_id=self.context.collection_run_id,
            provider_schema_version=self.context.provider_schema_version,
            mapping_version=self.mapping_specification.mapping_version,
            transformation_run_id=self.transformation_run_id,
            transformation_code_version=self.context.transformation_code_version,
            raw_evidence_reference=self.raw_evidence_id,
            transformed_at=self.context.transformed_at,
            transformation_status=TransformationStatus.SUCCESS,
        )

    def _provenance(
        self,
        *,
        source_field: str,
        source_record_identity: str,
        provider_semantic: str | None,
        semantic_status: SemanticStatus,
        provider_method: str | None = None,
        documentation_reference: str | None = None,
    ) -> Provenance:
        return Provenance(
            provider=self.provider,
            source_tool=self.context.source_tool,
            source_field=source_field,
            source_record_identity=source_record_identity,
            retrieved_at=self.context.retrieved_at,
            transformation=self._transformation(),
            provider_semantic=provider_semantic,
            semantic_validation_status=semantic_status,
            provider_method=provider_method,
            provider_documentation_reference=documentation_reference,
        )

    def _time(
        self,
        *,
        observed_at: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        period_type: PeriodType = PeriodType.UNKNOWN,
        timezone: str | None = None,
    ) -> TimeWindow:
        return TimeWindow(
            observed_at=observed_at,
            observed_at_status=(ObservedAtStatus.KNOWN if observed_at is not None else ObservedAtStatus.UNKNOWN),
            retrieved_at=self.context.retrieved_at,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            timezone=timezone,
        )

    def add_product_fact(
        self,
        *,
        product: ProductIdentity,
        dimension: str,
        fact_group: FactGroup,
        value: ValueEnvelope,
        source_field: str,
        source_record_identity: str,
        provider_semantic: str,
        evidence_type: EvidenceType = EvidenceType.OBSERVED,
        observed_at: str | None = None,
        period_type: PeriodType = PeriodType.UNKNOWN,
        scope_type: ScopeType = ScopeType.ASIN,
        scope_status: ScopeStatus = ScopeStatus.CONFIRMED,
        discriminator: str = "",
        issue_ids: tuple[str, ...] = (),
        result_status: ResultStatus = ResultStatus.POPULATED,
    ) -> ProductFactObservation:
        subject = product_subject(product)
        scope = Scope(
            scope_type=scope_type,
            scope_status=scope_status,
            scope_subject_id=(subject.subject_id if scope_status is ScopeStatus.CONFIRMED else None),
        )
        time = self._time(observed_at=observed_at, period_type=period_type)
        semantic_id = semantic_observation_id(
            provider=self.provider,
            source_tool=self.context.source_tool,
            subject=subject,
            observation_kind=ObservationKind.PRODUCT_FACT,
            dimension=dimension,
            source_record_identity=source_record_identity,
            observed_at=observed_at,
            period_identity={"period_type": period_type.value, "start": None, "end": None},
            discriminator=discriminator or source_field,
        )
        revision_id = observation_revision_id(
            semantic_id,
            {
                "kind": ObservationKind.PRODUCT_FACT,
                "dimension": dimension,
                "fact_group": fact_group,
                "evidence_type": evidence_type,
                "value": value,
                "scope": scope,
                "observed_at": observed_at,
                "period_type": period_type,
                "provider_semantic": provider_semantic,
            },
        )
        observation = ProductFactObservation(
            semantic_observation_id=semantic_id,
            observation_id=revision_id,
            observation_kind=ObservationKind.PRODUCT_FACT,
            subject=subject,
            evidence_type=evidence_type,
            value=value,
            scope=scope,
            time=time,
            provenance=self._provenance(
                source_field=source_field,
                source_record_identity=source_record_identity,
                provider_semantic=provider_semantic,
                semantic_status=value.semantic_status,
            ),
            quality_issue_ids=issue_ids,
            result_status=result_status,
            dimension=dimension,
            fact_group=fact_group,
            provider_semantic=provider_semantic,
        )
        self.observations.append(observation)
        return observation

    def add_metric(
        self,
        *,
        product: ProductIdentity,
        metric: str,
        value: ValueEnvelope,
        source_field: str,
        source_record_identity: str,
        metric_semantic: str,
        evidence_type: EvidenceType,
        currency: str | None = None,
        rank_context: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
        period_type: PeriodType = PeriodType.UNKNOWN,
        scope_type: ScopeType = ScopeType.ASIN,
        scope_status: ScopeStatus = ScopeStatus.CONFIRMED,
        discriminator: str = "",
        issue_ids: tuple[str, ...] = (),
        result_status: ResultStatus = ResultStatus.POPULATED,
        provider_method: str | None = None,
        documentation_reference: str | None = None,
    ) -> MetricObservation:
        subject = product_subject(product)
        scope = Scope(
            scope_type=scope_type,
            scope_status=scope_status,
            scope_subject_id=(subject.subject_id if scope_status is ScopeStatus.CONFIRMED else None),
        )
        time = self._time(observed_at=observed_at, period_type=period_type)
        semantic_id = semantic_observation_id(
            provider=self.provider,
            source_tool=self.context.source_tool,
            subject=subject,
            observation_kind=ObservationKind.METRIC,
            dimension=metric,
            source_record_identity=source_record_identity,
            observed_at=observed_at,
            period_identity={"period_type": period_type.value, "start": None, "end": None},
            discriminator=discriminator or source_field,
        )
        revision_id = observation_revision_id(
            semantic_id,
            {
                "kind": ObservationKind.METRIC,
                "metric": metric,
                "measurement_type": evidence_type,
                "value": value,
                "scope": scope,
                "observed_at": observed_at,
                "period_type": period_type,
                "currency": currency,
                "rank_context": rank_context,
                "metric_semantic": metric_semantic,
            },
        )
        observation = MetricObservation(
            semantic_observation_id=semantic_id,
            observation_id=revision_id,
            observation_kind=ObservationKind.METRIC,
            subject=subject,
            evidence_type=evidence_type,
            value=value,
            scope=scope,
            time=time,
            provenance=self._provenance(
                source_field=source_field,
                source_record_identity=source_record_identity,
                provider_semantic=metric_semantic,
                semantic_status=value.semantic_status,
                provider_method=provider_method,
                documentation_reference=documentation_reference,
            ),
            quality_issue_ids=issue_ids,
            result_status=result_status,
            metric=metric,
            measurement_type=evidence_type,
            metric_semantic=metric_semantic,
            currency=currency,
            rank_context=rank_context,
        )
        self.observations.append(observation)
        return observation

    def add_keyword_metric(
        self,
        *,
        keyword: KeywordIdentity,
        metric: str,
        value: ValueEnvelope,
        source_field: str,
        source_record_identity: str,
        metric_semantic: str,
        evidence_type: EvidenceType,
        estimate_method_status: EstimateMethodStatus,
        range_value: Mapping[str, Any] | None = None,
        period_type: PeriodType = PeriodType.UNKNOWN,
        discriminator: str = "",
        issue_ids: tuple[str, ...] = (),
        result_status: ResultStatus = ResultStatus.POPULATED,
    ) -> KeywordMetricObservation:
        subject = keyword_subject(keyword)
        scope = Scope(
            scope_type=ScopeType.KEYWORD,
            scope_status=ScopeStatus.CONFIRMED,
            scope_subject_id=keyword.keyword_id,
        )
        time = self._time(period_type=period_type)
        semantic_id = semantic_observation_id(
            provider=self.provider,
            source_tool=self.context.source_tool,
            subject=subject,
            observation_kind=ObservationKind.KEYWORD_METRIC,
            dimension=metric,
            source_record_identity=source_record_identity,
            observed_at=None,
            period_identity={"period_type": period_type.value, "start": None, "end": None},
            discriminator=discriminator or source_field,
        )
        revision_id = observation_revision_id(
            semantic_id,
            {
                "kind": ObservationKind.KEYWORD_METRIC,
                "keyword": keyword,
                "metric": metric,
                "evidence_type": evidence_type,
                "value": value,
                "scope": scope,
                "period_type": period_type,
                "estimate_method_status": estimate_method_status,
                "range": range_value,
                "metric_semantic": metric_semantic,
            },
        )
        observation = KeywordMetricObservation(
            semantic_observation_id=semantic_id,
            observation_id=revision_id,
            observation_kind=ObservationKind.KEYWORD_METRIC,
            subject=subject,
            evidence_type=evidence_type,
            value=value,
            scope=scope,
            time=time,
            provenance=self._provenance(
                source_field=source_field,
                source_record_identity=source_record_identity,
                provider_semantic=metric_semantic,
                semantic_status=value.semantic_status,
            ),
            quality_issue_ids=issue_ids,
            result_status=result_status,
            keyword=keyword,
            metric=metric,
            metric_semantic=metric_semantic,
            estimate_method_status=estimate_method_status,
            range=range_value,
        )
        self.observations.append(observation)
        return observation

    def add_relationship(
        self,
        *,
        product: ProductIdentity,
        keyword: KeywordIdentity,
        direction: RelationshipDirection,
        relationship_type: RelationshipType,
        channel: Channel,
        value: ValueEnvelope,
        source_field: str,
        source_record_identity: str,
        provider_semantic: str,
        evidence_type: EvidenceType,
        query_result_status: ResultStatus,
        rank: Mapping[str, Any] | None = None,
        traffic: ValueEnvelope | None = None,
        observed_at: str | None = None,
        period_type: PeriodType = PeriodType.UNKNOWN,
        discriminator: str = "",
        issue_ids: tuple[str, ...] = (),
        result_status: ResultStatus = ResultStatus.POPULATED,
    ) -> ProductKeywordRelationshipObservation:
        subject = relationship_subject(product, keyword)
        scope = Scope(
            scope_type=ScopeType.ASIN,
            scope_status=ScopeStatus.CONFIRMED,
            scope_subject_id=product.product_id,
        )
        time = self._time(observed_at=observed_at, period_type=period_type)
        relationship_identity = {
            "product_id": product.product_id,
            "keyword_id": keyword.keyword_id,
            "direction": direction,
            "relationship_type": relationship_type,
            "channel": channel,
        }
        semantic_id = semantic_observation_id(
            provider=self.provider,
            source_tool=self.context.source_tool,
            subject=subject,
            observation_kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
            dimension=relationship_type.value,
            source_record_identity=source_record_identity,
            observed_at=observed_at,
            period_identity={"period_type": period_type.value, "start": None, "end": None},
            discriminator=discriminator or source_field,
            relationship_identity=relationship_identity,
        )
        relationship_id = relationship_observation_id(
            semantic_id=semantic_id,
            product=product,
            keyword=keyword,
            direction=direction,
            relationship_type=relationship_type,
            channel=channel,
            canonical_content={"value": value, "rank": rank, "traffic": traffic},
        )
        revision_id = observation_revision_id(
            semantic_id,
            {
                "kind": ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
                "relationship_id": relationship_id,
                "relationship_identity": relationship_identity,
                "value": value,
                "rank": rank,
                "traffic": traffic,
                "scope": scope,
                "observed_at": observed_at,
                "period_type": period_type,
                "query_result_status": query_result_status,
            },
        )
        observation = ProductKeywordRelationshipObservation(
            semantic_observation_id=semantic_id,
            observation_id=revision_id,
            observation_kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
            subject=subject,
            evidence_type=evidence_type,
            value=value,
            scope=scope,
            time=time,
            provenance=self._provenance(
                source_field=source_field,
                source_record_identity=source_record_identity,
                provider_semantic=provider_semantic,
                semantic_status=value.semantic_status,
            ),
            quality_issue_ids=issue_ids,
            result_status=result_status,
            relationship_id=relationship_id,
            product=product,
            keyword=keyword,
            direction=direction,
            relationship_type=relationship_type,
            channel=channel,
            query_result_status=query_result_status,
            rank=rank,
            traffic=traffic,
        )
        self.observations.append(observation)
        return observation

    def add_review(
        self,
        *,
        product: ProductIdentity,
        provider_review_identity: str,
        rating: ValueEnvelope,
        title: ValueEnvelope,
        body: ValueEnvelope,
        review_date: ValueEnvelope,
        variant: ValueEnvelope,
        helpful_votes: ValueEnvelope,
        source_field: str,
        source_record_identity: str,
        observed_at: str | None,
    ) -> ReviewObservation:
        subject = product_subject(product)
        scope = Scope(
            scope_type=ScopeType.ASIN,
            scope_status=ScopeStatus.CONFIRMED,
            scope_subject_id=product.product_id,
        )
        time = self._time(observed_at=observed_at, period_type=PeriodType.UNKNOWN)
        semantic_id = semantic_observation_id(
            provider=self.provider,
            source_tool=self.context.source_tool,
            subject=subject,
            observation_kind=ObservationKind.REVIEW,
            dimension="review",
            source_record_identity=source_record_identity,
            observed_at=observed_at,
            period_identity={"period_type": PeriodType.UNKNOWN.value, "start": None, "end": None},
            discriminator=provider_review_identity,
        )
        review_observation_id = deterministic_id(
            "review",
            {"semantic_observation_id": semantic_id, "provider_review_identity": provider_review_identity},
        )
        revision_id = observation_revision_id(
            semantic_id,
            {
                "kind": ObservationKind.REVIEW,
                "review_observation_id": review_observation_id,
                "rating": rating,
                "title": title,
                "body": body,
                "review_date": review_date,
                "variant": variant,
                "helpful_votes": helpful_votes,
                "observed_at": observed_at,
            },
        )
        observation = ReviewObservation(
            semantic_observation_id=semantic_id,
            observation_id=revision_id,
            observation_kind=ObservationKind.REVIEW,
            subject=subject,
            evidence_type=EvidenceType.OBSERVED,
            value=body,
            scope=scope,
            time=time,
            provenance=self._provenance(
                source_field=source_field,
                source_record_identity=source_record_identity,
                provider_semantic="Provider review record",
                semantic_status=SemanticStatus.CONFIRMED,
            ),
            quality_issue_ids=(),
            result_status=ResultStatus.POPULATED,
            review_observation_id=review_observation_id,
            product=product,
            provider_review_identity=provider_review_identity,
            rating=rating,
            title=title,
            body=body,
            review_date=review_date,
            variant=variant,
            helpful_votes=helpful_votes,
        )
        self.observations.append(observation)
        return observation

    def finish(self) -> AdaptationResult:
        run_status = TransformationStatus.PARTIAL if self._partial or not self.observations else TransformationStatus.SUCCESS
        materialized: list[CanonicalObservation] = []
        for observation in self.observations:
            transform = replace(
                observation.provenance.transformation,
                transformation_status=run_status,
            )
            materialized.append(
                replace(
                    observation,
                    provenance=replace(observation.provenance, transformation=transform),
                )
            )
        self.observations = materialized
        run = TransformationRunRecord(
            provider=self.provider,
            collection_run_id=self.context.collection_run_id,
            provider_schema_version=self.context.provider_schema_version,
            mapping_version=self.mapping_specification.mapping_version,
            transformation_run_id=self.transformation_run_id,
            transformation_code_version=self.context.transformation_code_version,
            started_at=self.context.transformed_at,
            completed_at=self.context.transformed_at,
            status=run_status,
            input_raw_evidence_references=(self.raw_evidence_id,),
            output_observation_ids=tuple(item.observation_id for item in self.observations),
            quality_issue_ids=tuple(item.issue_id for item in self.issues),
        )
        bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(self.raw_evidence_id,),
            transformation_runs=(run,),
            observations=tuple(self.observations),
            conflicts=(),
            resolutions=(),
            quality_issues=tuple(self.issues),
        )
        return AdaptationResult(
            provider=self.provider,
            adapter_version=self.adapter_version,
            payload_kind=self.context.payload_kind,
            mapping_specification=self.mapping_specification,
            raw_evidence=self.raw_evidence,
            raw_snapshot=self.raw_snapshot,
            bundle=bundle,
            diagnostics=tuple(self.diagnostics),
            errors=tuple(self.errors),
            statistics=AdaptationStatistics(
                mapped_observation_count=len(self.observations),
                quality_issue_count=len(self.issues),
                diagnostic_count=len(self.diagnostics),
                error_count=len(self.errors),
            ),
        )


def _collection_failure(
    *,
    provider: str,
    adapter_version: str,
    payload_kind: str,
    payload: Any,
    context: AdaptationContext | None,
    mapping_specification: MappingSpecification | None,
    code: str,
    message: str,
    source_locator: str | None = None,
) -> AdaptationResult:
    raw_snapshot: Any = None
    raw_record: RawEvidenceRecord | None = None
    raw_ids: tuple[str, ...] = ()
    if context is not None:
        try:
            snapshot, response_fingerprint = _snapshot_json(payload)
            raw_snapshot = snapshot
            request_fingerprint = sha256(canonical_json(context.sanitized_request).encode("utf-8")).hexdigest()
            raw_id = raw_evidence_id(
                provider=context.provider,
                source_tool=context.source_tool,
                sanitized_request_fingerprint=f"sha256:v1:{request_fingerprint}",
                retrieved_at=context.retrieved_at,
                response_fingerprint=f"sha256:v1:{response_fingerprint}",
            )
            raw_record = RawEvidenceRecord(
                raw_evidence_id=raw_id,
                collection_run_id=context.collection_run_id,
                provider=context.provider,
                source_tool=context.source_tool,
                provider_schema_version=context.provider_schema_version,
                sanitized_request=context.sanitized_request,
                retrieved_at=context.retrieved_at,
                response_status="FAILED",
                media_type="application/json",
                content_reference=f"inline:{raw_id}",
                content_fingerprint=f"sha256:v1:{response_fingerprint}",
                error={"code": code, "message": message},
            )
            raw_ids = (raw_id,)
        except (AdapterError, ContractValidationError):
            raw_snapshot = None
            raw_record = None
            raw_ids = ()
    bundle = CanonicalEvidenceBundle(
        raw_evidence_references=raw_ids,
        transformation_runs=(),
        observations=(),
        conflicts=(),
        resolutions=(),
        quality_issues=(),
    )
    failure = AdapterFailure(
        code=code,
        message=message,
        level=AdapterFailureLevel.COLLECTION,
        source_locator=source_locator,
    )
    return AdaptationResult(
        provider=provider,
        adapter_version=adapter_version,
        payload_kind=payload_kind,
        mapping_specification=mapping_specification,
        raw_evidence=raw_record,
        raw_snapshot=raw_snapshot,
        bundle=bundle,
        diagnostics=(),
        errors=(failure,),
        statistics=AdaptationStatistics(
            mapped_observation_count=0,
            quality_issue_count=0,
            diagnostic_count=0,
            error_count=1,
        ),
    )


def _prepare_session(
    *,
    provider: str,
    adapter_version: str,
    mapping_specifications: Mapping[str, MappingSpecification],
    payload: Any,
    context: AdaptationContext,
) -> _AdapterSession | AdaptationResult:
    if context.provider.casefold() != provider.casefold():
        return _collection_failure(
            provider=provider,
            adapter_version=adapter_version,
            payload_kind=context.payload_kind,
            payload=payload,
            context=context,
            mapping_specification=None,
            code="UNSUPPORTED_PROVIDER",
            message=f"adapter {provider!r} cannot process provider {context.provider!r}",
        )
    specification = mapping_specifications.get(context.payload_kind)
    if specification is None:
        return _collection_failure(
            provider=provider,
            adapter_version=adapter_version,
            payload_kind=context.payload_kind,
            payload=payload,
            context=context,
            mapping_specification=None,
            code="UNSUPPORTED_PAYLOAD_KIND",
            message=f"payload kind {context.payload_kind!r} is not supported",
        )
    if context.source_tool != specification.source_tool:
        return _collection_failure(
            provider=provider,
            adapter_version=adapter_version,
            payload_kind=context.payload_kind,
            payload=payload,
            context=context,
            mapping_specification=specification,
            code="SOURCE_TOOL_MISMATCH",
            message=(
                f"payload kind {context.payload_kind!r} requires source tool "
                f"{specification.source_tool!r}"
            ),
        )
    if not isinstance(payload, MappingABC):
        return _collection_failure(
            provider=provider,
            adapter_version=adapter_version,
            payload_kind=context.payload_kind,
            payload=payload,
            context=context,
            mapping_specification=specification,
            code="MALFORMED_TOP_LEVEL_PAYLOAD",
            message="provider payload must be a JSON object",
            source_locator="$",
        )
    try:
        return _AdapterSession(
            provider=provider,
            adapter_version=adapter_version,
            mapping_specification=specification,
            context=context,
            payload=payload,
        )
    except (AdapterError, ContractValidationError) as exc:
        return _collection_failure(
            provider=provider,
            adapter_version=adapter_version,
            payload_kind=context.payload_kind,
            payload=payload,
            context=context,
            mapping_specification=specification,
            code="INVALID_JSON_PAYLOAD",
            message=str(exc),
            source_locator="$",
        )


__all__ = (
    "ADAPTER_RULESET_VERSION",
    "AdapterError",
    "AdapterContextError",
    "MappingDisposition",
    "AdapterFailureLevel",
    "MappingSpecification",
    "AdaptationContext",
    "AdapterDiagnostic",
    "AdapterFailure",
    "AdaptationStatistics",
    "AdaptationResult",
    "ProviderAdapter",
)
