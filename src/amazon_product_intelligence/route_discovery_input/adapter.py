"""Map Canonical provider observations into the governed S2/R2 listing input."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import math
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    ContractValidationError,
    EvidenceType,
    FactGroup,
    MetricObservation,
    NormalizationStatus,
    ObservationKind,
    PresenceStatus,
    ProductFactObservation,
    SemanticStatus,
    SubjectType,
    canonical_json,
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.normalization import (
    CanonicalNormalizationPipeline,
    NormalizationContext,
    NormalizationInput,
)
from amazon_product_intelligence.normalization.models import json_value
from amazon_product_intelligence.provider_capabilities import CapabilityStatus
from amazon_product_intelligence.sellersprite_import.models import (
    EvidenceSemantics,
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
    NormalizedField,
    RowDisposition,
    RowOutcome,
)
from amazon_product_intelligence.sellersprite_import.schema_v1 import (
    CORE_HEADERS,
    FIELD_SPECS,
    FIELD_SPEC_BY_HEADER,
)

from .errors import RouteDiscoveryInputError
from .models import (
    ROUTE_INPUT_CONTRACT_VERSION,
    ROUTE_INPUT_MAPPING_VERSION,
    RouteDiscoveryInputContext,
    RouteDiscoveryInputPackage,
    RouteInputAvailabilityStatus,
    RouteInputFieldAvailability,
    RouteInputFieldLineage,
    RouteInputFieldMapping,
    RouteInputIssue,
    RouteInputLineageDisposition,
)


ROUTE_INPUT_SOURCE_KIND = "CANONICAL_PROVIDER_OBSERVATIONS"


ROUTE_INPUT_FIELD_MAPPINGS = (
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="asin",
        canonical_field="product.asin", target_header="ASIN",
    ),
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="title",
        canonical_field="product.title", target_header="商品标题",
    ),
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="brand",
        canonical_field="product.brand", target_header="品牌",
    ),
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="category",
        canonical_field="product.category", target_header="类目路径",
    ),
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="parent_product_relationship",
        canonical_field="product.parent_asin", target_header="父ASIN",
    ),
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="fulfillment",
        canonical_field="product.fulfillment", target_header="配送方式",
    ),
    RouteInputFieldMapping(
        observation_kind="PRODUCT_FACT", canonical_name="first_available_date",
        canonical_field="product.first_available_date", target_header="上架时间",
    ),
    RouteInputFieldMapping(
        observation_kind="METRIC", canonical_name="estimated_monthly_sales",
        canonical_field="metric.estimated_monthly_sales", target_header="月销量",
        required_unit_dimension="COUNT",
    ),
    RouteInputFieldMapping(
        observation_kind="METRIC", canonical_name="estimated_variation_sales",
        canonical_field="metric.estimated_variation_sales", target_header="子体销量",
        required_unit_dimension="COUNT",
    ),
    RouteInputFieldMapping(
        observation_kind="METRIC", canonical_name="price",
        canonical_field="metric.price", target_header="价格($)",
        required_unit_dimension="CURRENCY", required_unit_code="USD",
    ),
    RouteInputFieldMapping(
        observation_kind="METRIC", canonical_name="review_count",
        canonical_field="metric.review_count", target_header="评分数",
        required_unit_dimension="COUNT",
    ),
    RouteInputFieldMapping(
        observation_kind="METRIC", canonical_name="rating",
        canonical_field="metric.rating", target_header="评分",
        required_unit_dimension="RATING", required_unit_code="stars_5",
    ),
    RouteInputFieldMapping(
        observation_kind="METRIC", canonical_name="bsr",
        canonical_field="metric.bsr", target_header="大类BSR",
        required_unit_dimension="RANK",
    ),
)


_MAPPING_BY_KEY = {
    (item.observation_kind, item.canonical_name): item
    for item in ROUTE_INPUT_FIELD_MAPPINGS
}
_MAPPING_BY_HEADER = {item.target_header: item for item in ROUTE_INPUT_FIELD_MAPPINGS}
_ATTRIBUTE_HEADER = "详细参数"
_ATTRIBUTE_FIELD = "product.attributes"
_ATTRIBUTE_GROUPS = frozenset((FactGroup.ATTRIBUTE, FactGroup.TECHNICAL))


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _bundle_material(bundle: CanonicalEvidenceBundle) -> dict[str, Any]:
    transformation_runs = []
    for run in bundle.transformation_runs:
        material = run.to_dict()
        for name in (
            "input_raw_evidence_references",
            "output_observation_ids",
            "quality_issue_ids",
            "output_query_execution_ids",
        ):
            material[name] = sorted(material[name])
        transformation_runs.append(material)
    return {
        "schema_version": bundle.schema_version,
        "transformation_runs": sorted(
            transformation_runs,
            key=lambda item: item["transformation_run_id"],
        ),
        "observations": sorted(
            (item.to_dict() for item in bundle.observations),
            key=lambda item: (item["observation_id"], canonical_json(item)),
        ),
        "conflicts": sorted(
            (item.to_dict() for item in bundle.conflicts),
            key=lambda item: item["conflict_id"],
        ),
        "resolutions": sorted(
            (item.to_dict() for item in bundle.resolutions),
            key=lambda item: item["resolution_id"],
        ),
        "quality_issues": sorted(
            (item.to_dict() for item in bundle.quality_issues),
            key=lambda item: item["issue_id"],
        ),
        "raw_evidence_references": sorted(bundle.raw_evidence_references),
        "query_execution_records": sorted(
            (item.to_dict() for item in bundle.query_execution_records),
            key=lambda item: item["query_execution_id"],
        ),
    }


def _empty_field(header: str) -> NormalizedField:
    spec = FIELD_SPEC_BY_HEADER[header]
    return NormalizedField(
        header=header,
        requirement=spec.requirement,
        value_type=spec.value_type,
        value=None,
        import_status=ImportValueStatus.MISSING_HEADER,
        presence_status=PresenceStatus.MISSING,
        normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
        evidence_semantics=EvidenceSemantics.UNKNOWN,
        issue_codes=("NO_COMPATIBLE_CANONICAL_OBSERVATION",),
    )


def _evidence_semantics(
    observations: Iterable[CanonicalObservation],
) -> EvidenceSemantics:
    values = {item.evidence_type for item in observations}
    if EvidenceType.PROVIDER_ESTIMATE in values:
        return EvidenceSemantics.THIRD_PARTY_ESTIMATE
    if EvidenceType.OBSERVED in values:
        return EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE
    return EvidenceSemantics.UNKNOWN


def _status_from_presence(presence: PresenceStatus) -> ImportValueStatus:
    if presence is PresenceStatus.MISSING:
        return ImportValueStatus.MISSING_HEADER
    if presence is PresenceStatus.EXPLICIT_NULL:
        return ImportValueStatus.BLANK
    return ImportValueStatus.NOT_AVAILABLE


def _availability(field: NormalizedField) -> RouteInputAvailabilityStatus:
    if "PROVIDER_CONFLICT" in field.issue_codes:
        return RouteInputAvailabilityStatus.CONFLICT
    if field.import_status is ImportValueStatus.NORMALIZED:
        return RouteInputAvailabilityStatus.AVAILABLE
    if field.import_status is ImportValueStatus.MISSING_HEADER:
        return RouteInputAvailabilityStatus.MISSING
    if field.import_status is ImportValueStatus.BLANK:
        return RouteInputAvailabilityStatus.EXPLICIT_NULL
    if field.import_status is ImportValueStatus.NOT_AVAILABLE:
        return RouteInputAvailabilityStatus.UNAVAILABLE
    return RouteInputAvailabilityStatus.INVALID


def _subject_asin(observation: CanonicalObservation, marketplace: str) -> str | None:
    if observation.subject.subject_type is not SubjectType.PRODUCT:
        return None
    prefix = f"product:{marketplace}:"
    if (
        observation.subject.marketplace != marketplace
        or not observation.subject.subject_id.startswith(prefix)
    ):
        raise RouteDiscoveryInputError(
            "INPUT_MARKETPLACE_OR_IDENTITY_MISMATCH",
            "product subject does not match the requested marketplace identity",
        )
    asin = observation.subject.subject_id[len(prefix):]
    try:
        expected = product_id(marketplace, asin)
    except ContractValidationError as exc:
        raise RouteDiscoveryInputError(
            "INPUT_PRODUCT_IDENTITY_INVALID",
            "product subject contains an invalid ASIN identity",
        ) from exc
    if expected != observation.subject.subject_id:
        raise RouteDiscoveryInputError(
            "INPUT_PRODUCT_IDENTITY_INVALID",
            "product subject is not a canonical product identity",
        )
    return asin


@dataclass(frozen=True, slots=True)
class _Candidate:
    asin: str
    mapping: RouteInputFieldMapping
    observation: CanonicalObservation
    value: Any
    import_status: ImportValueStatus
    presence_status: PresenceStatus
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    issue_codes: tuple[str, ...]
    normalization_rule_id: str | None
    valid: bool


def _mapping_for(observation: CanonicalObservation) -> RouteInputFieldMapping | None:
    if isinstance(observation, ProductFactObservation):
        return _MAPPING_BY_KEY.get((ObservationKind.PRODUCT_FACT.value, observation.dimension))
    if isinstance(observation, MetricObservation):
        return _MAPPING_BY_KEY.get((ObservationKind.METRIC.value, observation.metric))
    return None


def _candidate(
    observation: CanonicalObservation,
    asin: str,
    mapping: RouteInputFieldMapping,
    *,
    pipeline: CanonicalNormalizationPipeline,
    normalization_context: NormalizationContext,
    incompatible_codes: tuple[str, ...] = (),
) -> _Candidate:
    if observation.value.presence_status is not PresenceStatus.PRESENT:
        return _Candidate(
            asin=asin, mapping=mapping, observation=observation, value=None,
            import_status=_status_from_presence(observation.value.presence_status),
            presence_status=observation.value.presence_status,
            normalization_status=NormalizationStatus.NOT_ATTEMPTED,
            semantic_status=observation.value.semantic_status,
            issue_codes=tuple(sorted({
                f"SOURCE_{observation.value.presence_status.value}",
                *incompatible_codes,
            })),
            normalization_rule_id=None, valid=False,
        )
    normalized = pipeline.normalize(
        NormalizationInput.from_observation(
            observation,
            canonical_field=mapping.canonical_field,
            capability_status=CapabilityStatus.AVAILABLE,
        ),
        normalization_context,
    )
    issue_codes = {item.issue_code for item in normalized.issues}
    issue_codes.update(incompatible_codes)
    unit = normalized.unit
    if mapping.required_unit_dimension is not None and (
        unit is None or unit.dimension != mapping.required_unit_dimension
    ):
        issue_codes.add("INCOMPATIBLE_OR_MISSING_UNIT_DIMENSION")
    if mapping.required_unit_code is not None and (
        unit is None or unit.unit_code != mapping.required_unit_code
    ):
        issue_codes.add("INCOMPATIBLE_OR_MISSING_UNIT_CODE")
    unit_ok = not {
        "INCOMPATIBLE_OR_MISSING_UNIT_DIMENSION",
        "INCOMPATIBLE_OR_MISSING_UNIT_CODE",
    }.intersection(issue_codes)
    valid = (
        normalized.normalized_value is not None
        and normalized.normalization_status
        in {NormalizationStatus.NORMALIZED, NormalizationStatus.NOT_APPLICABLE}
        and normalized.semantic_status is not SemanticStatus.INVALID
        and unit_ok
        and not incompatible_codes
    )
    return _Candidate(
        asin=asin, mapping=mapping, observation=observation,
        value=normalized.normalized_value if valid else None,
        import_status=(
            ImportValueStatus.NORMALIZED if valid else ImportValueStatus.PARSE_FAILED
        ),
        presence_status=normalized.presence_status,
        normalization_status=(
            normalized.normalization_status if valid else NormalizationStatus.FAILED
        ),
        semantic_status=(
            normalized.semantic_status if valid else SemanticStatus.INVALID
        ),
        issue_codes=tuple(sorted(issue_codes or ({"NORMALIZATION_FAILED"} if not valid else set()))),
        normalization_rule_id=(
            None if normalized.application is None else normalized.application.rule_id
        ),
        valid=valid,
    )


def _field_from_candidates(
    mapping: RouteInputFieldMapping,
    candidates: tuple[_Candidate, ...],
) -> tuple[NormalizedField, RouteInputLineageDisposition, int, bool]:
    spec = FIELD_SPEC_BY_HEADER[mapping.target_header]
    valid = tuple(item for item in candidates if item.valid)
    invalid_present = tuple(
        item for item in candidates
        if item.import_status is ImportValueStatus.PARSE_FAILED
    )
    if valid and invalid_present:
        return (
            NormalizedField(
                header=spec.header, requirement=spec.requirement,
                value_type=spec.value_type, value=None,
                import_status=ImportValueStatus.PARSE_FAILED,
                presence_status=PresenceStatus.UNKNOWN,
                normalization_status=NormalizationStatus.FAILED,
                semantic_status=SemanticStatus.INVALID,
                evidence_semantics=_evidence_semantics(
                    item.observation for item in candidates
                ),
                issue_codes=("INCOMPATIBLE_INPUT_CANDIDATE",),
            ),
            RouteInputLineageDisposition.INVALID,
            0,
            False,
        )
    values = {canonical_json(json_value(item.value)): item.value for item in valid}
    if len(values) > 1:
        return (
            NormalizedField(
                header=spec.header, requirement=spec.requirement,
                value_type=spec.value_type, value=None,
                import_status=ImportValueStatus.PARSE_FAILED,
                presence_status=PresenceStatus.UNKNOWN,
                normalization_status=NormalizationStatus.FAILED,
                semantic_status=SemanticStatus.INVALID,
                evidence_semantics=_evidence_semantics(item.observation for item in valid),
                issue_codes=("PROVIDER_CONFLICT",),
            ),
            RouteInputLineageDisposition.CONFLICT,
            0,
            True,
        )
    if values:
        value = values[sorted(values)[0]]
        duplicate_count = max(0, len(valid) - 1)
        issues = {code for item in valid for code in item.issue_codes}
        disposition = RouteInputLineageDisposition.ACCEPTED
        if duplicate_count:
            issues.add("EQUIVALENT_DUPLICATE_OBSERVATION")
            disposition = RouteInputLineageDisposition.ACCEPTED_EQUIVALENT
        return (
            NormalizedField(
                header=spec.header, requirement=spec.requirement,
                value_type=spec.value_type, value=value,
                import_status=ImportValueStatus.NORMALIZED,
                presence_status=PresenceStatus.PRESENT,
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=(
                    SemanticStatus.SEMANTICS_UNCONFIRMED
                    if any(
                        item.semantic_status is SemanticStatus.SEMANTICS_UNCONFIRMED
                        for item in valid
                    )
                    else SemanticStatus.CONFIRMED
                ),
                evidence_semantics=_evidence_semantics(item.observation for item in valid),
                issue_codes=tuple(sorted(issues)),
            ),
            disposition,
            duplicate_count,
            False,
        )
    if not candidates:
        return _empty_field(mapping.target_header), RouteInputLineageDisposition.UNAVAILABLE, 0, False
    precedence = {
        ImportValueStatus.PARSE_FAILED: 4,
        ImportValueStatus.NOT_AVAILABLE: 3,
        ImportValueStatus.BLANK: 2,
        ImportValueStatus.MISSING_HEADER: 1,
        ImportValueStatus.NORMALIZED: 0,
    }
    selected = max(candidates, key=lambda item: (
        precedence[item.import_status], item.observation.observation_id,
    ))
    issue_codes = tuple(sorted({code for item in candidates for code in item.issue_codes}))
    return (
        NormalizedField(
            header=spec.header, requirement=spec.requirement,
            value_type=spec.value_type, value=None,
            import_status=selected.import_status,
            presence_status=selected.presence_status,
            normalization_status=selected.normalization_status,
            semantic_status=selected.semantic_status,
            evidence_semantics=_evidence_semantics(item.observation for item in candidates),
            issue_codes=issue_codes,
        ),
        (
            RouteInputLineageDisposition.INVALID
            if selected.import_status is ImportValueStatus.PARSE_FAILED
            else RouteInputLineageDisposition.UNAVAILABLE
        ),
        0,
        False,
    )


def _attribute_text(observation: ProductFactObservation) -> str | None:
    if observation.value.presence_status is not PresenceStatus.PRESENT:
        return None
    if (
        observation.value.normalization_status is NormalizationStatus.FAILED
        or observation.value.semantic_status is SemanticStatus.INVALID
    ):
        return None
    value = (
        observation.value.normalized_value
        if observation.value.normalized_value is not None
        else observation.value.raw_value
    )
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (str, int, Decimal)):
        text = str(value)
    elif isinstance(value, float) and math.isfinite(value):
        text = str(value)
    else:
        return None
    unit = observation.value.unit
    if unit is not None and unit.unit_code:
        text = f"{text} [{unit.unit_code}]"
    return " ".join(text.split()).strip() or None


def _lineage(
    candidate: _Candidate | None,
    *,
    observation: CanonicalObservation,
    asin: str,
    mapping: RouteInputFieldMapping,
    canonical_name: str,
    disposition: RouteInputLineageDisposition,
    value: Any,
    normalization_rule_id: str | None = None,
) -> RouteInputFieldLineage:
    unit = observation.value.unit
    material = {
        "asin": asin,
        "target_header": mapping.target_header,
        "canonical_field": mapping.canonical_field,
        "canonical_name": canonical_name,
        "observation_id": observation.observation_id,
        "disposition": disposition.value,
    }
    return RouteInputFieldLineage(
        lineage_id=deterministic_id("route-input-lineage", material),
        asin=asin, target_header=mapping.target_header,
        canonical_field=mapping.canonical_field, canonical_name=canonical_name,
        observation_id=observation.observation_id,
        semantic_observation_id=observation.semantic_observation_id,
        provider=observation.provenance.provider,
        source_tool=observation.provenance.source_tool,
        source_field=observation.provenance.source_field,
        raw_evidence_reference=(
            observation.provenance.transformation.raw_evidence_reference
        ),
        transformation_run_id=(
            observation.provenance.transformation.transformation_run_id
        ),
        mapping_version=observation.provenance.transformation.mapping_version,
        normalization_rule_id=(
            normalization_rule_id
            if normalization_rule_id is not None
            else (None if candidate is None else candidate.normalization_rule_id)
        ),
        presence_status=observation.value.presence_status.value,
        normalization_status=(
            observation.value.normalization_status.value
            if candidate is None else candidate.normalization_status.value
        ),
        semantic_status=(
            observation.value.semantic_status.value
            if candidate is None else candidate.semantic_status.value
        ),
        unit_dimension=None if unit is None else unit.dimension,
        unit_code=None if unit is None else unit.unit_code,
        normalized_value_fingerprint=None if value is None else _hash(json_value(value)),
        disposition=disposition,
    )


def _issue(
    code: str,
    *,
    asin: str | None,
    canonical_field: str | None,
    observation_ids: Iterable[str],
    blocking: bool,
) -> RouteInputIssue:
    ids = tuple(sorted(set(observation_ids)))
    material = {
        "code": code, "asin": asin, "canonical_field": canonical_field,
        "observation_ids": ids, "blocking": blocking,
    }
    return RouteInputIssue(
        issue_id=deterministic_id("route-input-issue", material),
        code=code, asin=asin, canonical_field=canonical_field,
        observation_ids=ids, blocking=blocking,
    )


def build_route_discovery_input(
    bundles: Iterable[CanonicalEvidenceBundle],
    *,
    context: RouteDiscoveryInputContext,
    normalization: CanonicalNormalizationPipeline | None = None,
) -> RouteDiscoveryInputPackage:
    """Build the exact governed dataset seam consumed by accepted S2 and R2.

    Provider field names are read only from Canonical provenance. Selection and
    conflict handling operate exclusively on Canonical observation semantics.
    """

    supplied = tuple(bundles)
    if not supplied:
        raise RouteDiscoveryInputError(
            "INPUT_BUNDLES_EMPTY", "at least one Canonical evidence bundle is required",
        )
    for bundle in supplied:
        if not isinstance(bundle, CanonicalEvidenceBundle):
            raise RouteDiscoveryInputError(
                "INPUT_CONTRACT_INCOMPATIBLE",
                "all inputs must be CanonicalEvidenceBundle instances",
            )
        try:
            bundle.validate()
        except (ContractValidationError, ValueError) as exc:
            raise RouteDiscoveryInputError(
                "INPUT_CANONICAL_BUNDLE_INVALID",
                "Canonical evidence bundle validation failed",
            ) from exc

    bundle_materials = tuple(sorted(
        (_bundle_material(bundle) for bundle in supplied), key=canonical_json,
    ))
    bundle_fingerprints = tuple(_hash(item) for item in bundle_materials)
    observation_index: dict[str, CanonicalObservation] = {}
    exact_duplicate_count = 0
    for bundle in supplied:
        for observation in bundle.observations:
            prior = observation_index.get(observation.observation_id)
            if prior is None:
                observation_index[observation.observation_id] = observation
            elif canonical_json(prior.to_dict()) == canonical_json(observation.to_dict()):
                exact_duplicate_count += 1
            else:
                raise RouteDiscoveryInputError(
                    "INPUT_OBSERVATION_ID_CONFLICT",
                    "one observation ID refers to incompatible Canonical content",
                )
    observations = tuple(sorted(
        observation_index.values(), key=lambda item: item.observation_id,
    ))
    canonical_conflicts: dict[str, set[str]] = {}
    blocking_quality_issue_ids = {
        issue.issue_id
        for bundle in supplied for issue in bundle.quality_issues
        if issue.blocking
    }
    for bundle in supplied:
        for conflict in bundle.conflicts:
            if conflict.conflict_status.value in {"CONSISTENT", "ONE_SOURCE_ONLY"}:
                continue
            code = f"CANONICAL_CONFLICT:{conflict.conflict_status.value}"
            for observation_id in conflict.candidate_observation_ids:
                canonical_conflicts.setdefault(observation_id, set()).add(code)
    blocking_quality: dict[str, set[str]] = {}
    for observation in observations:
        linked = set(observation.quality_issue_ids) & blocking_quality_issue_ids
        if linked:
            blocking_quality[observation.observation_id] = {
                "CANONICAL_BLOCKING_QUALITY_ISSUE"
            }
    product_observations: dict[str, list[CanonicalObservation]] = {}
    ignored_count = 0
    for observation in observations:
        asin = _subject_asin(observation, context.marketplace)
        if asin is None or not isinstance(observation, (ProductFactObservation, MetricObservation)):
            ignored_count += 1
            continue
        product_observations.setdefault(asin, []).append(observation)
    if not product_observations:
        raise RouteDiscoveryInputError(
            "INPUT_PRODUCT_OBSERVATIONS_EMPTY",
            "no product fact or product metric observations were supplied",
        )

    pipeline = normalization or CanonicalNormalizationPipeline.with_defaults()
    normalization_context = NormalizationContext(
        normalization_run_id=context.normalization_run_id,
        normalized_at=context.normalized_at,
    )
    all_lineage: list[RouteInputFieldLineage] = []
    all_availability: list[RouteInputFieldAvailability] = []
    issues: list[RouteInputIssue] = []
    records: list[ListingRecordV1] = []
    duplicate_count = exact_duplicate_count
    conflict_count = 0
    mapped_observation_ids: set[str] = set()

    for row_number, asin in enumerate(sorted(product_observations), 1):
        subject_observations = tuple(sorted(
            product_observations[asin], key=lambda item: item.observation_id,
        ))
        identity_mapping = _MAPPING_BY_KEY[(ObservationKind.PRODUCT_FACT.value, "asin")]
        identity_observations = tuple(
            item for item in subject_observations
            if isinstance(item, ProductFactObservation) and item.dimension == "asin"
        )
        if not identity_observations:
            raise RouteDiscoveryInputError(
                "INPUT_REQUIRED_IDENTITY_MISSING",
                "every product subject requires an explicit Canonical ASIN observation",
            )
        identity_candidates = tuple(
            _candidate(
                item, asin, identity_mapping, pipeline=pipeline,
                normalization_context=normalization_context,
                incompatible_codes=tuple(sorted({
                    *canonical_conflicts.get(item.observation_id, set()),
                    *blocking_quality.get(item.observation_id, set()),
                })),
            )
            for item in identity_observations
        )
        if (
            not any(item.valid for item in identity_candidates)
            or {item.value for item in identity_candidates if item.valid} != {asin}
        ):
            raise RouteDiscoveryInputError(
                "INPUT_REQUIRED_IDENTITY_INCOMPATIBLE",
                "Canonical ASIN observation does not agree with its product subject",
            )

        resolved_by_header: dict[str, NormalizedField] = {}
        lineage_by_asin: list[RouteInputFieldLineage] = []
        for mapping in ROUTE_INPUT_FIELD_MAPPINGS:
            if mapping.target_header == "ASIN":
                candidates = identity_candidates
            else:
                relevant = tuple(
                    item for item in subject_observations
                    if _mapping_for(item) == mapping
                )
                candidates = tuple(
                    _candidate(
                        item, asin, mapping, pipeline=pipeline,
                        normalization_context=normalization_context,
                        incompatible_codes=tuple(sorted({
                            *canonical_conflicts.get(item.observation_id, set()),
                            *blocking_quality.get(item.observation_id, set()),
                        })),
                    )
                    for item in relevant
                )
            field, disposition, equivalent_count, conflicted = _field_from_candidates(
                mapping, candidates,
            )
            if mapping.target_header == "ASIN":
                field = NormalizedField(
                    header=field.header, requirement=field.requirement,
                    value_type=field.value_type, value=asin,
                    import_status=ImportValueStatus.NORMALIZED,
                    presence_status=PresenceStatus.PRESENT,
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                    evidence_semantics=field.evidence_semantics,
                    issue_codes=field.issue_codes,
                )
            if (
                mapping.canonical_field == "product.parent_asin"
                and field.import_status is ImportValueStatus.NORMALIZED
                and field.value == asin
            ):
                field = NormalizedField(
                    header=field.header, requirement=field.requirement,
                    value_type=field.value_type, value=None,
                    import_status=ImportValueStatus.PARSE_FAILED,
                    presence_status=PresenceStatus.UNKNOWN,
                    normalization_status=NormalizationStatus.FAILED,
                    semantic_status=SemanticStatus.INVALID,
                    evidence_semantics=field.evidence_semantics,
                    issue_codes=("SELF_PARENT_IDENTITY_REJECTED",),
                )
                disposition = RouteInputLineageDisposition.INVALID
            resolved_by_header[mapping.target_header] = field
            duplicate_count += equivalent_count
            if conflicted:
                conflict_count += 1
                issues.append(_issue(
                    "PROVIDER_CONFLICT", asin=asin,
                    canonical_field=mapping.canonical_field,
                    observation_ids=(item.observation.observation_id for item in candidates),
                    blocking=True,
                ))
            for candidate in candidates:
                mapped_observation_ids.add(candidate.observation.observation_id)
                lineage_by_asin.append(_lineage(
                    candidate,
                    observation=candidate.observation, asin=asin, mapping=mapping,
                    canonical_name=mapping.canonical_name,
                    disposition=disposition,
                    value=(candidate.value if candidate.valid and not conflicted else None),
                ))
            all_availability.append(RouteInputFieldAvailability(
                asin=asin, target_header=mapping.target_header,
                canonical_field=mapping.canonical_field,
                status=_availability(field),
                observation_ids=tuple(sorted(
                    item.observation.observation_id for item in candidates
                )),
                reason_codes=tuple(sorted(field.issue_codes)),
            ))

        attribute_observations = tuple(
            item for item in subject_observations
            if isinstance(item, ProductFactObservation)
            and item.fact_group in _ATTRIBUTE_GROUPS
            and _mapping_for(item) is None
        )
        attribute_values: dict[tuple[str, str], tuple[str, ProductFactObservation]] = {}
        attribute_value_sets: dict[str, set[str]] = {}
        unavailable_attributes: list[ProductFactObservation] = []
        canonical_attribute_conflict = False
        for observation in attribute_observations:
            mapped_observation_ids.add(observation.observation_id)
            if blocking_quality.get(observation.observation_id):
                text = None
            else:
                text = _attribute_text(observation)
            canonical_attribute_conflict = canonical_attribute_conflict or bool(
                canonical_conflicts.get(observation.observation_id)
            )
            if text is None:
                unavailable_attributes.append(observation)
                continue
            display_key = " ".join(observation.dimension.replace("_", " ").split()).casefold()
            key = (display_key, text.casefold())
            if key in attribute_values:
                duplicate_count += 1
            else:
                attribute_values[key] = (text, observation)
            attribute_value_sets.setdefault(display_key, set()).add(text.casefold())
        attribute_conflict = any(
            len(values) > 1 for values in attribute_value_sets.values()
        ) or canonical_attribute_conflict
        attribute_mapping = RouteInputFieldMapping(
            observation_kind="PRODUCT_FACT", canonical_name="structured_attribute",
            canonical_field=_ATTRIBUTE_FIELD, target_header=_ATTRIBUTE_HEADER,
        )
        if attribute_values:
            detail_text = " | ".join(
                f"{key}: {attribute_values[(key, value)][0]}"
                for key, value in sorted(attribute_values)
            )
            spec = FIELD_SPEC_BY_HEADER[_ATTRIBUTE_HEADER]
            detail_issues = (
                ("ATTRIBUTE_CONFLICT_PRESERVED",) if attribute_conflict else ()
            )
            detail_field = NormalizedField(
                header=spec.header, requirement=spec.requirement,
                value_type=spec.value_type, value=detail_text,
                import_status=ImportValueStatus.NORMALIZED,
                presence_status=PresenceStatus.PRESENT,
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=SemanticStatus.CONFIRMED,
                evidence_semantics=_evidence_semantics(
                    item for _, item in attribute_values.values()
                ),
                issue_codes=detail_issues,
            )
            if attribute_conflict:
                issues.append(_issue(
                    "ATTRIBUTE_CONFLICT_PRESERVED", asin=asin,
                    canonical_field=_ATTRIBUTE_FIELD,
                    observation_ids=(item.observation_id for item in attribute_observations),
                    blocking=False,
                ))
        elif unavailable_attributes:
            selected_presence = unavailable_attributes[0].value.presence_status
            spec = FIELD_SPEC_BY_HEADER[_ATTRIBUTE_HEADER]
            detail_field = NormalizedField(
                header=spec.header, requirement=spec.requirement,
                value_type=spec.value_type, value=None,
                import_status=_status_from_presence(selected_presence),
                presence_status=selected_presence,
                normalization_status=NormalizationStatus.NOT_ATTEMPTED,
                semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                evidence_semantics=_evidence_semantics(unavailable_attributes),
                issue_codes=("ATTRIBUTE_DATA_UNAVAILABLE",),
            )
        else:
            detail_field = _empty_field(_ATTRIBUTE_HEADER)
        resolved_by_header[_ATTRIBUTE_HEADER] = detail_field
        attr_disposition = (
            RouteInputLineageDisposition.ATTRIBUTE_CONFLICT_PRESERVED
            if attribute_conflict else RouteInputLineageDisposition.ACCEPTED
        )
        for observation in attribute_observations:
            value = (
                None
                if blocking_quality.get(observation.observation_id)
                else _attribute_text(observation)
            )
            disposition = (
                RouteInputLineageDisposition.UNAVAILABLE
                if value is None else attr_disposition
            )
            lineage_by_asin.append(_lineage(
                None, observation=observation, asin=asin,
                mapping=attribute_mapping, canonical_name=observation.dimension,
                disposition=disposition, value=value,
            ))
        all_availability.append(RouteInputFieldAvailability(
            asin=asin, target_header=_ATTRIBUTE_HEADER,
            canonical_field=_ATTRIBUTE_FIELD, status=_availability(detail_field),
            observation_ids=tuple(sorted(
                item.observation_id for item in attribute_observations
            )),
            reason_codes=tuple(sorted(detail_field.issue_codes)),
        ))

        fields = tuple(
            resolved_by_header.get(spec.header, _empty_field(spec.header))
            for spec in FIELD_SPECS
        )
        parent_field = resolved_by_header["父ASIN"]
        parent_asin = (
            str(parent_field.value)
            if parent_field.import_status is ImportValueStatus.NORMALIZED
            and parent_field.value is not None
            and str(parent_field.value) != asin
            else None
        )
        logical_record = {
            "asin": asin, "parent_asin": parent_asin,
            "fields": [item.to_dict() for item in fields],
            "lineage": [
                item.to_dict() for item in sorted(
                    lineage_by_asin, key=lambda item: item.lineage_id,
                )
            ],
            "input_contract_version": ROUTE_INPUT_CONTRACT_VERSION,
            "mapping_version": ROUTE_INPUT_MAPPING_VERSION,
        }
        records.append(ListingRecordV1(
            asin=asin, parent_asin=parent_asin, source_row=row_number,
            fields=fields, record_fingerprint=_hash(logical_record),
        ))
        all_lineage.extend(lineage_by_asin)

    ignored_count += sum(
        item.observation_id not in mapped_observation_ids
        for item in observations
        if _subject_asin(item, context.marketplace) is not None
        and isinstance(item, (ProductFactObservation, MetricObservation))
    )
    for observation in observations:
        if observation.observation_id in mapped_observation_ids:
            continue
        if _subject_asin(observation, context.marketplace) is None:
            continue
        canonical_name = (
            observation.dimension if isinstance(observation, ProductFactObservation)
            else observation.metric if isinstance(observation, MetricObservation)
            else observation.observation_kind.value
        )
        issues.append(_issue(
            "OBSERVATION_OUTSIDE_ROUTE_INPUT_MAPPING", asin=None,
            canonical_field=canonical_name,
            observation_ids=(observation.observation_id,), blocking=False,
        ))

    sorted_records = tuple(sorted(records, key=lambda item: item.asin))
    row_outcomes = tuple(
        RowOutcome(
            source_row=item.source_row, disposition=RowDisposition.ACCEPTED,
            reason_codes=(), asin=item.asin,
        )
        for item in sorted_records
    )
    missing_core = tuple(
        (header, sum(
            next(field for field in record.fields if field.header == header).import_status
            is not ImportValueStatus.NORMALIZED
            for record in sorted_records
        ))
        for header in CORE_HEADERS
        if any(
            next(field for field in record.fields if field.header == header).import_status
            is not ImportValueStatus.NORMALIZED
            for record in sorted_records
        )
    )
    source_material = {
        "bundle_fingerprints": bundle_fingerprints,
        "raw_evidence_references": sorted({
            ref for bundle in supplied for ref in bundle.raw_evidence_references
        }),
        "transformation_run_ids": sorted({
            run.transformation_run_id
            for bundle in supplied for run in bundle.transformation_runs
        }),
    }
    source_fingerprint = _hash(source_material)
    sorted_lineage = tuple(sorted(all_lineage, key=lambda item: item.lineage_id))
    sorted_availability = tuple(sorted(
        all_availability, key=lambda item: (item.asin, item.target_header),
    ))
    sorted_issues = tuple(sorted(
        {item.issue_id: item for item in issues}.values(), key=lambda item: item.issue_id,
    ))
    dataset_material = {
        "contract_version": "governed-market-dataset-v1.0",
        "import_ruleset_version": ROUTE_INPUT_CONTRACT_VERSION,
        "header_mapping_version": ROUTE_INPUT_MAPPING_VERSION,
        "source_kind": ROUTE_INPUT_SOURCE_KIND,
        "source_fingerprint": source_fingerprint,
        "marketplace": context.marketplace,
        "category": context.category,
        "observed_date": context.observed_date,
        "records": [item.logical_dict() for item in sorted_records],
        "row_outcomes": [item.to_dict() for item in row_outcomes],
        "field_lineage": [item.to_dict() for item in sorted_lineage],
        "field_availability": [item.to_dict() for item in sorted_availability],
    }
    dataset_fingerprint = _hash(dataset_material)
    dataset = GovernedMarketDatasetV1(
        dataset_id="gmdv1-" + _hash({
            "semantic_fingerprint": dataset_fingerprint,
            "source_fingerprint": source_fingerprint,
        })[:24],
        semantic_fingerprint=dataset_fingerprint,
        source_type="CANONICAL_BUNDLE_SET",
        source_basename="canonical-provider-observations",
        source_file_sha256=source_fingerprint,
        imported_at=context.imported_at,
        marketplace=context.marketplace,
        category=context.category,
        observed_date=context.observed_date,
        observed_date_status="OBSERVED" if context.observed_date else "UNKNOWN",
        source_sheet=None, header_row=0,
        source_row_count=len(product_observations),
        accepted_listing_count=len(sorted_records),
        unique_asin_count=len(sorted_records),
        duplicate_row_count=0, rejected_row_count=0, quarantined_row_count=0,
        missing_core_field_summary=missing_core,
        unmapped_headers=tuple(sorted({
            item.canonical_field for item in sorted_issues
            if item.code == "OBSERVATION_OUTSIDE_ROUTE_INPUT_MAPPING"
            and item.canonical_field is not None
        })),
        out_of_scope_headers=(), records=sorted_records,
        row_outcomes=row_outcomes,
        import_ruleset_version=ROUTE_INPUT_CONTRACT_VERSION,
        header_mapping_version=ROUTE_INPUT_MAPPING_VERSION,
        source_kind_value=ROUTE_INPUT_SOURCE_KIND,
    )
    package_material = {
        "contract_version": ROUTE_INPUT_CONTRACT_VERSION,
        "mapping_version": ROUTE_INPUT_MAPPING_VERSION,
        "dataset_fingerprint": dataset.semantic_fingerprint,
        "provider_ids": sorted({
            item.provenance.provider for item in observations
        }),
        "source_bundle_fingerprints": bundle_fingerprints,
        "source_raw_evidence_references": source_material["raw_evidence_references"],
        "source_transformation_run_ids": source_material["transformation_run_ids"],
        "field_availability": [item.to_dict() for item in sorted_availability],
        "field_lineage": [item.to_dict() for item in sorted_lineage],
        "issues": [item.to_dict() for item in sorted_issues],
        "counts": {
            "duplicate_observations": duplicate_count,
            "conflict_fields": conflict_count,
            "ignored_observations": ignored_count,
        },
    }
    semantic_fingerprint = _hash(package_material)
    return RouteDiscoveryInputPackage(
        package_id=deterministic_id("route-discovery-input", package_material),
        semantic_fingerprint=semantic_fingerprint, dataset=dataset,
        provider_ids=tuple(package_material["provider_ids"]),
        source_bundle_fingerprints=bundle_fingerprints,
        source_raw_evidence_references=tuple(
            source_material["raw_evidence_references"]
        ),
        source_transformation_run_ids=tuple(
            source_material["transformation_run_ids"]
        ),
        field_availability=sorted_availability,
        field_lineage=sorted_lineage, issues=sorted_issues,
        duplicate_observation_count=duplicate_count,
        conflict_field_count=conflict_count,
        ignored_observation_count=ignored_count,
    )


__all__ = (
    "ROUTE_INPUT_FIELD_MAPPINGS",
    "ROUTE_INPUT_SOURCE_KIND",
    "build_route_discovery_input",
)
