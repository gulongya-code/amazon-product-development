"""Provider-owned SellerSprite export to Canonical evidence boundary.

The adapter is intentionally confined to the acquisition/import package.  It
projects only fields governed by the provider-neutral Route input contract plus
structured parameters; downstream intelligence never selects or branches on a
provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import (
    BlockingScope,
    CanonicalEvidenceBundle,
    CodeVersionScheme,
    DataQualityIssue,
    EvidenceType,
    FactGroup,
    MetricObservation,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    OriginStage,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    Provenance,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    ResultStatus,
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
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.listing_attribute_map.detailed_parameters import (
    parse_detailed_parameters,
)
from amazon_product_intelligence.normalization.models import json_value

from .models import (
    EvidenceSemantics,
    GovernedMarketDatasetV1,
    ImportValueStatus,
    NormalizedField,
)


SELLERSPRITE_CANONICAL_MAPPING_VERSION = "sellersprite-governed-canonical-v1.1"
SELLERSPRITE_CANONICAL_ADAPTER_VERSION = "seller-export-canonical-adapter-v1.1"

# Provider documentation: https://open.sellersprite.com/api/1
# Monthly estimates/growth describe the parent link, not the selected variant.
_PARENT_METRICS = frozenset({"estimated_monthly_sales", "estimated_monthly_revenue", "sales_mom_growth", "sales_yoy_growth"})


@dataclass(frozen=True, slots=True)
class _Binding:
    header: str
    kind: ObservationKind
    name: str
    fact_group: FactGroup | None = None
    unit_dimension: str | None = None
    unit_code: str | None = None
    unit_system: str | None = None


_BINDINGS = (
    _Binding("ASIN", ObservationKind.PRODUCT_FACT, "asin", FactGroup.IDENTITY_RELATED),
    _Binding("\u5546\u54c1\u6807\u9898", ObservationKind.PRODUCT_FACT, "title", FactGroup.DESCRIPTION),
    _Binding("\u54c1\u724c", ObservationKind.PRODUCT_FACT, "brand", FactGroup.OTHER),
    _Binding("\u7c7b\u76ee\u8def\u5f84", ObservationKind.PRODUCT_FACT, "category", FactGroup.OTHER),
    _Binding("\u7236ASIN", ObservationKind.PRODUCT_FACT, "parent_product_relationship", FactGroup.VARIATION),
    _Binding("\u914d\u9001\u65b9\u5f0f", ObservationKind.PRODUCT_FACT, "fulfillment", FactGroup.OTHER),
    _Binding("\u4e0a\u67b6\u65f6\u95f4", ObservationKind.PRODUCT_FACT, "first_available_date", FactGroup.OTHER),
    _Binding("BuyBox\u5356\u5bb6", ObservationKind.PRODUCT_FACT, "seller", FactGroup.OTHER),
    _Binding("\u6708\u9500\u91cf", ObservationKind.METRIC, "estimated_monthly_sales", unit_dimension="COUNT", unit_code="units", unit_system="DOMAIN"),
    _Binding("\u5b50\u4f53\u9500\u91cf", ObservationKind.METRIC, "estimated_variation_sales", unit_dimension="COUNT", unit_code="units", unit_system="DOMAIN"),
    _Binding("\u6708\u9500\u552e\u989d($)", ObservationKind.METRIC, "estimated_monthly_revenue", unit_dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217"),
    _Binding("\u4ef7\u683c($)", ObservationKind.METRIC, "price", unit_dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217"),
    _Binding("\u8bc4\u5206\u6570", ObservationKind.METRIC, "review_count", unit_dimension="COUNT", unit_code="reviews", unit_system="DOMAIN"),
    _Binding("\u8bc4\u5206", ObservationKind.METRIC, "rating", unit_dimension="RATING", unit_code="stars_5", unit_system="DOMAIN"),
    _Binding("\u5927\u7c7bBSR", ObservationKind.METRIC, "bsr", unit_dimension="RANK", unit_code="rank", unit_system="DOMAIN"),
    _Binding("\u5c0f\u7c7bBSR", ObservationKind.METRIC, "subcategory_bsr", unit_dimension="RANK", unit_code="rank", unit_system="DOMAIN"),
    _Binding("\u9500\u91cf\u73af\u6bd4\u589e\u957f\u7387", ObservationKind.METRIC, "sales_mom_growth", unit_dimension="RATIO", unit_code="ratio", unit_system="DOMAIN"),
    _Binding("\u9500\u91cf\u540c\u6bd4\u589e\u957f\u7387", ObservationKind.METRIC, "sales_yoy_growth", unit_dimension="RATIO", unit_code="ratio", unit_system="DOMAIN"),
    _Binding("\u4e0a\u67b6\u5929\u6570", ObservationKind.METRIC, "listing_age_days", unit_dimension="COUNT", unit_code="days", unit_system="DOMAIN"),
)
_DETAIL_HEADER = "\u8be6\u7ec6\u53c2\u6570"


def _value_type(field: NormalizedField) -> ValueType:
    mapping = {
        "BOOLEAN": ValueType.BOOLEAN,
        "DATE": ValueType.DATE,
        "MONEY_USD": ValueType.NUMBER,
        "NONNEGATIVE_INTEGER": ValueType.INTEGER,
        "PERCENTAGE": ValueType.NUMBER,
        "RANK": ValueType.INTEGER,
        "RATING": ValueType.NUMBER,
        "SIGNED_INTEGER": ValueType.INTEGER,
    }
    return mapping.get(field.value_type, ValueType.STRING)


def _presence_and_value(field: NormalizedField) -> tuple[PresenceStatus, Any]:
    if field.import_status is ImportValueStatus.NORMALIZED and field.value is not None:
        return PresenceStatus.PRESENT, json_value(field.value)
    presence = field.presence_status
    if presence is PresenceStatus.PRESENT:
        presence = PresenceStatus.UNKNOWN
    return presence, None


def _evidence_type(field: NormalizedField) -> EvidenceType:
    if field.evidence_semantics is EvidenceSemantics.THIRD_PARTY_ESTIMATE:
        return EvidenceType.PROVIDER_ESTIMATE
    return EvidenceType.OBSERVED


def _time(dataset: GovernedMarketDatasetV1, *, monthly: bool) -> TimeWindow:
    observed_at = (
        None
        if dataset.observed_date is None
        else f"{dataset.observed_date}T00:00:00Z"
    )
    return TimeWindow(
        observed_at=observed_at,
        observed_at_status=(
            ObservedAtStatus.UNKNOWN if observed_at is None else ObservedAtStatus.KNOWN
        ),
        retrieved_at=dataset.imported_at,
        period_start=None,
        period_end=None,
        period_type=PeriodType.ROLLING_30_DAYS if monthly else PeriodType.INSTANT,
        timezone="UTC",
    )


def build_sellersprite_canonical_evidence(
    dataset: GovernedMarketDatasetV1,
) -> CanonicalEvidenceBundle:
    """Project one validated local export into provider-owned Canonical evidence."""

    if not isinstance(dataset, GovernedMarketDatasetV1):
        raise TypeError("dataset must be GovernedMarketDatasetV1")

    provider = "sellersprite"
    raw_reference = deterministic_id(
        "sellersprite-raw-export",
        {"sha256": dataset.source_file_sha256, "sheet": dataset.source_sheet},
    )
    collection_run_id = deterministic_id(
        "sellersprite-export-collection",
        {"raw_reference": raw_reference, "marketplace": dataset.marketplace},
    )
    transformation_run_id = deterministic_id(
        "sellersprite-canonical-transformation",
        {
            "dataset_fingerprint": dataset.semantic_fingerprint,
            "mapping_version": SELLERSPRITE_CANONICAL_MAPPING_VERSION,
        },
    )
    schema = ProviderSchemaVersion(
        status=VersionStatus.KNOWN,
        value=dataset.header_mapping_version,
        source=ProviderSchemaSource.LOCAL_CONTRACT,
    )
    code = TransformationCodeVersion(
        status=VersionStatus.KNOWN,
        value=SELLERSPRITE_CANONICAL_ADAPTER_VERSION,
        scheme=CodeVersionScheme.RULESET_VERSION,
    )
    transformation = TransformationProvenance(
        collection_run_id=collection_run_id,
        provider_schema_version=schema,
        mapping_version=SELLERSPRITE_CANONICAL_MAPPING_VERSION,
        transformation_run_id=transformation_run_id,
        transformation_code_version=code,
        raw_evidence_reference=raw_reference,
        transformed_at=dataset.imported_at,
        transformation_status=TransformationStatus.SUCCESS,
    )

    observations = []
    issues = []
    for record in sorted(dataset.records, key=lambda item: item.asin):
        subject = SubjectRef(
            subject_type=SubjectType.PRODUCT,
            subject_id=product_id(dataset.marketplace, record.asin),
            marketplace=dataset.marketplace,
        )
        scope = Scope(
            scope_type=ScopeType.ASIN,
            scope_status=ScopeStatus.CONFIRMED,
            scope_subject_id=subject.subject_id,
        )
        fields = {field.header: field for field in record.fields}

        def append_observation(
            *,
            field: NormalizedField,
            kind: ObservationKind,
            name: str,
            fact_group: FactGroup | None,
            unit: Unit | None,
            source_field: str,
            ordinal: int,
            explicit_value: Any | None = None,
        ) -> None:
            presence, value = _presence_and_value(field)
            if explicit_value is not None:
                presence, value = PresenceStatus.PRESENT, explicit_value
            quality_ids = []
            for code_value in sorted(field.issue_codes):
                issue_id = deterministic_id(
                    "sellersprite-canonical-quality-issue",
                    {
                        "record": record.record_fingerprint,
                        "source_field": source_field,
                        "code": code_value,
                        "ordinal": ordinal,
                    },
                )
                quality_ids.append(issue_id)
                issues.append(DataQualityIssue(
                    issue_id=issue_id,
                    issue_code=code_value,
                    severity=Severity.WARNING,
                    subject=subject,
                    dimension=name,
                    message=f"source import issue: {code_value}",
                    blocking=False,
                    blocking_scope=BlockingScope.NONE,
                    source_references=(raw_reference,),
                    created_at=dataset.imported_at,
                    origin_stage=OriginStage.MAPPING,
                    collection_run_id=collection_run_id,
                    transformation_run_id=transformation_run_id,
                    mapping_version=SELLERSPRITE_CANONICAL_MAPPING_VERSION,
                ))
            self_referential_parent = (
                name == "parent_product_relationship"
                and presence is PresenceStatus.PRESENT
                and str(value).strip().upper() == record.asin
            )
            if self_referential_parent:
                issue_id = deterministic_id(
                    "sellersprite-canonical-quality-issue",
                    {
                        "record": record.record_fingerprint,
                        "source_field": source_field,
                        "code": "SELF_REFERENTIAL_PARENT_ASIN",
                        "ordinal": ordinal,
                    },
                )
                quality_ids.append(issue_id)
                issues.append(DataQualityIssue(
                    issue_id=issue_id,
                    issue_code="SELF_REFERENTIAL_PARENT_ASIN",
                    severity=Severity.WARNING,
                    subject=subject,
                    dimension=name,
                    message="parent-product observation is a self-reference and is not confirmed",
                    blocking=False,
                    blocking_scope=BlockingScope.NONE,
                    source_references=(raw_reference,),
                    created_at=dataset.imported_at,
                    origin_stage=OriginStage.MAPPING,
                    collection_run_id=collection_run_id,
                    transformation_run_id=transformation_run_id,
                    mapping_version=SELLERSPRITE_CANONICAL_MAPPING_VERSION,
                ))
            identity = {
                "mapping_version": SELLERSPRITE_CANONICAL_MAPPING_VERSION,
                "record": record.record_fingerprint,
                "kind": kind.value,
                "name": name,
                "source_field": source_field,
                "ordinal": ordinal,
                "presence": presence.value,
                "value": value,
                "unit": None if unit is None else unit.to_dict(),
            }
            observation_id = deterministic_id("sellersprite-canonical-observation", identity)
            evidence_type = _evidence_type(field)
            observation_scope = scope
            if name in _PARENT_METRICS:
                parent = fields["父ASIN"]
                known = parent.import_status is ImportValueStatus.NORMALIZED and parent.value is not None
                observation_scope = Scope(
                    scope_type=ScopeType.PARENT_ASIN,
                    scope_status=ScopeStatus.CONFIRMED if known else ScopeStatus.SCOPE_UNCONFIRMED,
                    scope_subject_id=product_id(dataset.marketplace, str(parent.value)) if known else None,
                )
            elif name == "estimated_variation_sales":
                observation_scope = Scope(scope_type=ScopeType.CHILD_ASIN, scope_status=ScopeStatus.CONFIRMED, scope_subject_id=subject.subject_id)
            common = dict(
                semantic_observation_id=deterministic_id(
                    "sellersprite-semantic-observation",
                    {
                        "mapping_version": SELLERSPRITE_CANONICAL_MAPPING_VERSION,
                        "marketplace": dataset.marketplace,
                        "asin": record.asin,
                        "kind": kind.value,
                        "name": name,
                        "source_field": source_field,
                        "ordinal": ordinal,
                        "presence": presence.value,
                        "value": value,
                        "unit": None if unit is None else unit.to_dict(),
                    },
                ),
                observation_id=observation_id,
                subject=subject,
                evidence_type=evidence_type,
                value=ValueEnvelope(
                    presence_status=presence,
                    raw_value=value,
                    normalized_value=value,
                    value_type=_value_type(field),
                    unit=unit,
                    normalization_status=(
                        NormalizationStatus.AMBIGUOUS
                        if self_referential_parent
                        else NormalizationStatus.NORMALIZED
                        if presence is PresenceStatus.PRESENT
                        else NormalizationStatus.NOT_APPLICABLE
                    ),
                    semantic_status=(
                        SemanticStatus.SEMANTICS_UNCONFIRMED
                        if self_referential_parent
                        else field.semantic_status
                        if presence is PresenceStatus.PRESENT
                        else SemanticStatus.SEMANTICS_UNCONFIRMED
                    ),
                ),
                scope=observation_scope,
                time=_time(
                    dataset,
                    monthly=name in {
                        "estimated_monthly_sales",
                        "estimated_variation_sales",
                        "estimated_monthly_revenue",
                        "sales_mom_growth",
                        "sales_yoy_growth",
                    },
                ),
                provenance=Provenance(
                    provider=provider,
                    source_tool="SellerSprite local export",
                    source_field=source_field,
                    source_record_identity=record.record_fingerprint,
                    retrieved_at=dataset.imported_at,
                    transformation=transformation,
                ),
                quality_issue_ids=tuple(quality_ids),
                result_status=(
                    ResultStatus.POPULATED
                    if presence is PresenceStatus.PRESENT
                    else ResultStatus.UNKNOWN
                ),
            )
            if kind is ObservationKind.PRODUCT_FACT:
                observations.append(ProductFactObservation(
                    observation_kind=kind,
                    dimension=name,
                    fact_group=fact_group or FactGroup.OTHER,
                    provider_semantic="BUYBOX_SELLER_SNAPSHOT" if name == "seller" else None,
                    **common,
                ))
            else:
                observations.append(MetricObservation(
                    observation_kind=kind,
                    metric=name,
                    measurement_type=evidence_type,
                    metric_semantic="PARENT_LINK_ESTIMATE" if name in _PARENT_METRICS else None,
                    currency=(
                        unit.unit_code
                        if unit is not None and unit.dimension == "CURRENCY"
                        else None
                    ),
                    **common,
                ))

        for ordinal, binding in enumerate(_BINDINGS):
            field = fields[binding.header]
            unit = (
                None
                if binding.unit_dimension is None
                else Unit(
                    dimension=binding.unit_dimension,
                    unit_code=binding.unit_code,
                    unit_system=binding.unit_system,
                )
            )
            append_observation(
                field=field,
                kind=binding.kind,
                name=binding.name,
                fact_group=binding.fact_group,
                unit=unit,
                source_field=binding.header,
                ordinal=ordinal,
            )

        detail = fields[_DETAIL_HEADER]
        if detail.import_status is ImportValueStatus.NORMALIZED and detail.value is not None:
            parsed = parse_detailed_parameters(str(detail.value))
            for offset, parameter in enumerate(parsed.parameters, start=len(_BINDINGS)):
                append_observation(
                    field=detail,
                    kind=ObservationKind.PRODUCT_FACT,
                    name=parameter.normalized_key,
                    fact_group=FactGroup.ATTRIBUTE,
                    unit=None,
                    source_field=f"{_DETAIL_HEADER}.{parameter.source_key}",
                    ordinal=offset,
                    explicit_value=parameter.source_value,
                )

    ordered_observations = tuple(sorted(observations, key=lambda item: item.observation_id))
    ordered_issues = tuple(sorted(issues, key=lambda item: item.issue_id))
    run = TransformationRunRecord(
        provider=provider,
        collection_run_id=collection_run_id,
        provider_schema_version=schema,
        mapping_version=SELLERSPRITE_CANONICAL_MAPPING_VERSION,
        transformation_run_id=transformation_run_id,
        transformation_code_version=code,
        started_at=dataset.imported_at,
        completed_at=dataset.imported_at,
        status=TransformationStatus.SUCCESS,
        input_raw_evidence_references=(raw_reference,),
        output_observation_ids=tuple(item.observation_id for item in ordered_observations),
        quality_issue_ids=tuple(item.issue_id for item in ordered_issues),
    )
    return CanonicalEvidenceBundle(
        transformation_runs=(run,),
        observations=ordered_observations,
        conflicts=(),
        resolutions=(),
        quality_issues=ordered_issues,
        raw_evidence_references=(raw_reference,),
    )


__all__ = (
    "SELLERSPRITE_CANONICAL_ADAPTER_VERSION",
    "SELLERSPRITE_CANONICAL_MAPPING_VERSION",
    "build_sellersprite_canonical_evidence",
)
