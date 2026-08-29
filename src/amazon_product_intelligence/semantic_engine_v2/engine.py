"""Generic deterministic Semantic Engine V2 driven only by strict profiles."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Iterable

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.listing_attribute_map.detailed_parameters import (
    parse_detailed_parameters,
)
from amazon_product_intelligence.listing_attribute_map.measurements import parse_measurement
from amazon_product_intelligence.listing_attribute_map.rule_pack import MeasurementScope
from amazon_product_intelligence.market_report.v0_2.models.common import (
    Availability,
    ReferenceKind,
    build_reference,
)
from amazon_product_intelligence.product_attribute_extraction.models import (
    AttributeConfidenceLevel,
)
from amazon_product_intelligence.sellersprite_import.models import (
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
)

from .errors import SemanticEngineV2Error
from .models import (
    APDMarketCohortEligibility,
    CohortEligibilityState,
    ConsumptionLifecycle,
    EvidenceRelationship,
    EvidenceRelationshipState,
    ListingSemanticResult,
    ProductIdentity,
    ProductRole,
    RelationRole,
    SEMANTIC_ENGINE_VERSION,
    SemanticDecisionStatus,
    SemanticEngineV2Result,
    SemanticEvidenceReference,
    SemanticFact,
    SemanticFactStatus,
    SemanticScope,
    SemanticSourceClass,
    UniversalSemanticRole,
    build_evidence_relationship,
    build_semantic_fact,
)
from .profile import (
    CategorySemanticProfileV1_1,
    ConflictRule,
    DecisionRule,
    FactRule,
    IdentityRule,
)


_TITLE_HEADER = "\u5546\u54c1\u6807\u9898"
_DETAIL_HEADER = "\u8be6\u7ec6\u53c2\u6570"
_PROVIDER_CATEGORY_HEADERS = frozenset(("\u7c7b\u76ee\u8def\u5f84", "\u5927\u7c7b\u76ee", "\u5c0f\u7c7b\u76ee"))


@dataclass(frozen=True, slots=True)
class _Observation:
    source_class: SemanticSourceClass
    source_field: str
    source_key: str | None
    text: str
    normalized_text: str
    source_content_fingerprint: str
    upstream_record_fingerprint: str


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split()).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _matches(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    if any(ord(char) > 127 for char in phrase):
        return phrase in text
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _source_for_field(header: str) -> SemanticSourceClass:
    if header == _TITLE_HEADER:
        return SemanticSourceClass.LISTING_TITLE
    if header.casefold() == "sku":
        return SemanticSourceClass.AUTHORIZED_SKU
    if header in _PROVIDER_CATEGORY_HEADERS:
        return SemanticSourceClass.PROVIDER_CATEGORY_CONTEXT
    return SemanticSourceClass.DEDICATED_GOVERNED_FIELD


def _observation(
    *, source_class: SemanticSourceClass, source_field: str,
    source_key: str | None, text: str, record_fingerprint: str,
) -> _Observation:
    normalized = _normalize(text)
    return _Observation(
        source_class=source_class, source_field=source_field,
        source_key=None if source_key is None else _normalize(source_key),
        text=" ".join(str(text).split()), normalized_text=normalized,
        source_content_fingerprint=_hash({
            "source_class": source_class.value, "source_field": source_field,
            "source_key": source_key, "normalized_text": normalized,
            "upstream_record_fingerprint": record_fingerprint,
        }),
        upstream_record_fingerprint=record_fingerprint,
    )


def _observations(
    record: ListingRecordV1,
    profile: CategorySemanticProfileV1_1,
) -> tuple[tuple[_Observation, ...], tuple[str, ...]]:
    result: list[_Observation] = []
    limitations: list[str] = []
    for field in record.fields:
        if field.import_status is not ImportValueStatus.NORMALIZED or field.value is None:
            continue
        if field.header == _DETAIL_HEADER:
            parsed = parse_detailed_parameters(str(field.value))
            for parameter in parsed.parameters:
                result.append(_observation(
                    source_class=SemanticSourceClass.STRUCTURED_PARAMETERS,
                    source_field=field.header,
                    source_key=profile.canonical_attribute_key(parameter.normalized_key),
                    text=parameter.source_value,
                    record_fingerprint=record.record_fingerprint,
                ))
            limitations.extend(
                f"DETAIL_PARSE_ISSUE:{item.code}" for item in parsed.issues
            )
            limitations.extend(
                f"DETAIL_PARAMETER_CONFLICT:{item.normalized_key}" for item in parsed.conflicts
            )
            continue
        source = _source_for_field(field.header)
        if source not in profile.source_authorization:
            continue
        result.append(_observation(
            source_class=source, source_field=field.header,
            source_key=profile.canonical_attribute_key(field.header),
            text=str(field.value), record_fingerprint=record.record_fingerprint,
        ))
    return tuple(sorted(result, key=lambda item: (
        item.source_class.value, item.source_field.casefold(), item.source_key or "",
        item.normalized_text, item.source_content_fingerprint,
    ))), tuple(sorted(set(limitations)))


def _rule_observations(
    observations: tuple[_Observation, ...],
    *,
    sources: tuple[SemanticSourceClass, ...],
    source_keys: tuple[str, ...] = (),
    phrases: tuple[str, ...],
    exclusions: tuple[str, ...],
) -> tuple[_Observation, ...]:
    allowed_sources = set(sources)
    allowed_keys = set(source_keys)
    result = []
    for item in observations:
        if item.source_class not in allowed_sources:
            continue
        if allowed_keys and (item.source_key or "") not in allowed_keys:
            continue
        if exclusions and any(_matches(item.normalized_text, term) for term in exclusions):
            continue
        if phrases and not any(_matches(item.normalized_text, term) for term in phrases):
            continue
        result.append(item)
    return tuple(result)


def _evidence(
    observation: _Observation,
    *,
    rule_id: str,
) -> SemanticEvidenceReference:
    material = {
        "source_class": observation.source_class.value,
        "source_field": observation.source_field,
        "source_key": observation.source_key,
        "source_content_fingerprint": observation.source_content_fingerprint,
        "upstream_record_fingerprint": observation.upstream_record_fingerprint,
        "profile_rule_id": rule_id,
    }
    return SemanticEvidenceReference(
        evidence_id=deterministic_id("semantic-evidence-v2", material),
        source_class=observation.source_class,
        source_field=observation.source_field, source_key=observation.source_key,
        source_content_fingerprint=observation.source_content_fingerprint,
        upstream_record_fingerprint=observation.upstream_record_fingerprint,
        profile_rule_id=rule_id,
    )


def _measurement_scope(scope: SemanticScope) -> MeasurementScope:
    if scope is SemanticScope.PACKAGE:
        return MeasurementScope.PACKAGE
    if scope is SemanticScope.UNSPECIFIED:
        return MeasurementScope.UNSPECIFIED
    return MeasurementScope.ITEM


def _fact_from_observation(
    record: ListingRecordV1,
    observation: _Observation,
    evidence: SemanticEvidenceReference,
    *,
    role: UniversalSemanticRole,
    dimension: str,
    normalized_value: Any,
    rule_id: str,
    profile: CategorySemanticProfileV1_1,
    confidence: AttributeConfidenceLevel,
    quantity_kind: str | None = None,
    semantic_scope: SemanticScope | None = None,
    quantity_subtype: Any = None,
    limitations: tuple[str, ...] = (),
) -> SemanticFact:
    return build_semantic_fact(
        listing_reference=record.asin,
        upstream_record_fingerprint=record.record_fingerprint,
        role=role, dimension=dimension, normalized_value=normalized_value,
        availability=Availability.AVAILABLE,
        fact_status=SemanticFactStatus.DETERMINISTIC_DERIVED,
        confidence=confidence, source_classes=(observation.source_class,),
        evidence_ids=(evidence.evidence_id,), quantity_kind=quantity_kind,
        semantic_scope=semantic_scope, quantity_subtype=quantity_subtype,
        profile_id=profile.profile_id, profile_version=profile.version,
        profile_fingerprint=profile.fingerprint, rule_id=rule_id,
        limitations=limitations, review_reason_codes=(),
    )


def _fact_rules(
    record: ListingRecordV1,
    observations: tuple[_Observation, ...],
    profile: CategorySemanticProfileV1_1,
) -> tuple[list[SemanticFact], list[SemanticEvidenceReference], list[str]]:
    facts: list[SemanticFact] = []
    evidence: list[SemanticEvidenceReference] = []
    limitations: list[str] = []
    for rule in profile.fact_rules:
        for item in _rule_observations(
            observations, sources=rule.sources, source_keys=rule.source_keys,
            phrases=rule.match_phrases, exclusions=rule.exclusions,
        ):
            value: Any
            quantity_kind = None if rule.quantity_kind is None else rule.quantity_kind.value
            semantic_scope = rule.semantic_scope
            quantity_subtype = rule.quantity_subtype
            if rule.value_mode == "FIXED":
                value = rule.normalized_value
            elif rule.value_mode == "SOURCE_VALUE":
                value = profile.canonical_value(item.normalized_text)
            else:
                authorization = profile.quantity_scope_authorization(rule)
                quantity_kind = authorization.quantity_kind.value
                semantic_scope = authorization.semantic_scope
                quantity_subtype = authorization.quantity_subtype
                parsed = parse_measurement(
                    item.text, quantity_kind=authorization.quantity_kind,
                    scope=_measurement_scope(authorization.semantic_scope),
                    allow_bare_count=authorization.quantity_kind.value == "COUNT",
                )
                if parsed.measurement is None:
                    limitations.append(
                        f"MEASUREMENT_REJECTED:{rule.rule_id}:{parsed.issue_code}"
                    )
                    continue
                value = parsed.measurement.to_dict()
            evidence_item = _evidence(item, rule_id=rule.rule_id)
            evidence.append(evidence_item)
            facts.append(_fact_from_observation(
                record, item, evidence_item, role=rule.role, dimension=rule.dimension,
                normalized_value=value, rule_id=rule.rule_id, profile=profile,
                confidence=rule.confidence, quantity_kind=quantity_kind,
                semantic_scope=semantic_scope,
                quantity_subtype=quantity_subtype,
            ))
    return facts, evidence, limitations


def _identity_facts(
    record: ListingRecordV1, observations: tuple[_Observation, ...],
    profile: CategorySemanticProfileV1_1,
) -> tuple[list[SemanticFact], list[SemanticEvidenceReference]]:
    facts: list[SemanticFact] = []
    evidence: list[SemanticEvidenceReference] = []
    for rule in profile.identity_rules:
        for item in _rule_observations(
            observations, sources=rule.sources, phrases=rule.phrases,
            exclusions=rule.exclusions,
        ):
            evidence_item = _evidence(item, rule_id=rule.rule_id)
            evidence.append(evidence_item)
            confidence = (
                AttributeConfidenceLevel.HIGH
                if item.source_class is SemanticSourceClass.LISTING_TITLE
                else AttributeConfidenceLevel.MEDIUM
            )
            facts.append(_fact_from_observation(
                record, item, evidence_item, role=UniversalSemanticRole.PRODUCT_IDENTITY,
                dimension="product_identity",
                normalized_value={"identity": rule.identity, "is_target": rule.is_target},
                rule_id=rule.rule_id, profile=profile, confidence=confidence,
            ))
    return facts, evidence


def _decision_facts(
    record: ListingRecordV1, observations: tuple[_Observation, ...],
    profile: CategorySemanticProfileV1_1,
    *, rules: tuple[DecisionRule, ...], dimension: str,
) -> tuple[list[SemanticFact], list[SemanticEvidenceReference]]:
    facts: list[SemanticFact] = []
    evidence: list[SemanticEvidenceReference] = []
    for rule in rules:
        for item in _rule_observations(
            observations, sources=rule.sources, phrases=rule.phrases,
            exclusions=rule.exclusions,
        ):
            evidence_item = _evidence(item, rule_id=rule.rule_id)
            evidence.append(evidence_item)
            facts.append(_fact_from_observation(
                record, item, evidence_item, role=UniversalSemanticRole.PRODUCT_ROLE,
                dimension=dimension, normalized_value=rule.result,
                rule_id=rule.rule_id, profile=profile,
                confidence=(
                    AttributeConfidenceLevel.HIGH
                    if item.source_class is SemanticSourceClass.LISTING_TITLE
                    else AttributeConfidenceLevel.MEDIUM
                ),
            ))
    return facts, evidence


def _rule_priority(profile: CategorySemanticProfileV1_1, fact: SemanticFact) -> int:
    rules: Iterable[Any]
    if fact.dimension == "product_identity":
        rules = profile.identity_rules
    elif fact.dimension == "relation_role":
        rules = profile.relation_rules
    elif fact.dimension == "consumption_lifecycle":
        rules = profile.lifecycle_rules
    else:
        return 0
    return next(item.priority for item in rules if item.rule_id == fact.rule_id)


def _value_key(fact: SemanticFact) -> str:
    return canonical_json(fact.normalized_value)


def _conflict_value_token(fact: SemanticFact) -> str:
    value = fact.normalized_value
    return _normalize(value) if isinstance(value, str) else canonical_json(value).casefold()


def _matches_explicit_conflict_values(
    rule: ConflictRule,
    observed_values: set[str],
) -> bool:
    return bool(rule.values) and len(observed_values & set(rule.values)) >= 2


def _relationship_for_dimension(
    listing_reference: str,
    role: UniversalSemanticRole,
    dimension: str,
    facts: tuple[SemanticFact, ...],
    profile: CategorySemanticProfileV1_1,
) -> EvidenceRelationship:
    policy = profile.source_policy(dimension)
    if not facts:
        return build_evidence_relationship(
            listing_reference=listing_reference, role=role, dimension=dimension,
            state=EvidenceRelationshipState.UNAVAILABLE, fact_ids=(), evidence_ids=(),
            profile_rule_ids=(policy.policy_id,), reason_codes=("EVIDENCE_UNAVAILABLE",),
            route_critical=False,
        )
    values = {_value_key(item) for item in facts}
    sources = {source for item in facts for source in item.source_classes}
    title = SemanticSourceClass.LISTING_TITLE in sources
    non_title = bool(sources - {SemanticSourceClass.LISTING_TITLE})
    state: EvidenceRelationshipState
    reasons: tuple[str, ...]
    critical = False
    if len(values) == 1:
        if title and non_title:
            state, reasons = EvidenceRelationshipState.AGREES, ("NORMALIZED_VALUES_AGREE",)
        elif title:
            state, reasons = EvidenceRelationshipState.SOURCE_ONLY_TITLE, ("ONLY_TITLE_EVIDENCE",)
        else:
            state, reasons = EvidenceRelationshipState.SOURCE_ONLY_STRUCTURED, (
                "ONLY_STRUCTURED_OR_GOVERNED_FIELD_EVIDENCE",
            )
    else:
        conflict_rules = [
            item for item in profile.true_conflict_rules if item.dimension == dimension
        ]
        route_rules = [
            item for item in profile.route_critical_conflict_rules if item.dimension == dimension
        ]
        conflict_value_tokens = {_conflict_value_token(item) for item in facts}
        explicitly_matched_rules = [
            item for item in (*conflict_rules, *route_rules)
            if _matches_explicit_conflict_values(item, conflict_value_tokens)
        ]
        conflict_declared = (
            not policy.multi_value or bool(explicitly_matched_rules)
        )
        if not conflict_declared:
            state, reasons = EvidenceRelationshipState.COMPATIBLE_MULTI_VALUE, (
                "PROFILE_ALLOWS_MULTI_VALUE_COEXISTENCE",
            )
        else:
            minimum = min(_rule_priority(profile, item) for item in facts)
            best = [item for item in facts if _rule_priority(profile, item) == minimum]
            best_values = {_value_key(item) for item in best}
            best_conflict_value_tokens = {_conflict_value_token(item) for item in best}
            best_primary_sources = {
                source for item in best for source in item.source_classes
                if source in policy.primary_sources
            }
            applicable_route_rules = [
                item for item in route_rules
                if not item.values or _matches_explicit_conflict_values(
                    item, best_conflict_value_tokens
                )
            ]
            applicable_true_conflict_rules = [
                item for item in conflict_rules
                if not item.values or _matches_explicit_conflict_values(
                    item, conflict_value_tokens
                )
            ]
            critical = (
                bool(applicable_route_rules)
                and len(best_values) > 1
                and bool(best_primary_sources)
            )
            if critical:
                state, reasons = EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT, (
                    "MUTUALLY_EXCLUSIVE_PRIMARY_EVIDENCE",
                    *(item.rule_id for item in applicable_route_rules),
                )
            else:
                state, reasons = EvidenceRelationshipState.TRUE_CONFLICT, (
                    "DISTINCT_NON_COEXISTING_VALUES",
                    *(item.rule_id for item in applicable_true_conflict_rules),
                    *(
                        item.rule_id for item in explicitly_matched_rules
                        if item in route_rules
                    ),
                )
    return build_evidence_relationship(
        listing_reference=listing_reference, role=role, dimension=dimension,
        state=state, fact_ids=tuple(item.fact_id for item in facts),
        evidence_ids=tuple(evidence for item in facts for evidence in item.evidence_ids),
        profile_rule_ids=(policy.policy_id, *(item.rule_id for item in facts)),
        reason_codes=reasons, route_critical=critical,
    )


def _relationships(
    listing_reference: str,
    facts: tuple[SemanticFact, ...],
    profile: CategorySemanticProfileV1_1,
) -> tuple[EvidenceRelationship, ...]:
    by_dimension: dict[str, list[SemanticFact]] = defaultdict(list)
    for fact in facts:
        by_dimension[fact.dimension].append(fact)
    result = [
        _relationship_for_dimension(
            listing_reference, policy.role, policy.dimension,
            tuple(sorted(by_dimension.get(policy.dimension, ()), key=lambda item: item.fact_id)),
            profile,
        )
        for policy in profile.source_policies
    ]
    for rule in profile.coexistence_rules:
        left = tuple(by_dimension.get(rule.left_dimension, ()))
        right = tuple(by_dimension.get(rule.right_dimension, ()))
        if not left or not right:
            continue
        combined = tuple(sorted((*left, *right), key=lambda item: item.fact_id))
        result.append(build_evidence_relationship(
            listing_reference=listing_reference, role=left[0].role,
            dimension=f"{rule.left_dimension}+{rule.right_dimension}",
            state=EvidenceRelationshipState.COMPLEMENTARY,
            fact_ids=tuple(item.fact_id for item in combined),
            evidence_ids=tuple(evidence for item in combined for evidence in item.evidence_ids),
            profile_rule_ids=(rule.rule_id,),
            reason_codes=("DIFFERENT_SEMANTIC_QUESTIONS_CAN_COEXIST",),
            route_critical=False,
        ))
    return tuple(sorted(result, key=lambda item: item.relationship_id))


def _select(
    facts: tuple[SemanticFact, ...],
    profile: CategorySemanticProfileV1_1,
) -> tuple[SemanticDecisionStatus, Any, tuple[SemanticFact, ...], tuple[str, ...]]:
    if not facts:
        return SemanticDecisionStatus.UNKNOWN, None, (), ("NO_GOVERNED_EVIDENCE",)
    minimum = min(_rule_priority(profile, item) for item in facts)
    best = tuple(sorted(
        (item for item in facts if _rule_priority(profile, item) == minimum),
        key=lambda item: item.fact_id,
    ))
    values = {_value_key(item) for item in best}
    if len(values) != 1:
        return (
            SemanticDecisionStatus.REVIEW_REQUIRED, None, best,
            ("EQUAL_PRIORITY_MUTUALLY_EXCLUSIVE_EVIDENCE",),
        )
    return SemanticDecisionStatus.GOVERNED, best[0].normalized_value, best, (
        "PROFILE_PRIORITY_AND_EVIDENCE_RESOLVED",
    )


def _identity(
    facts: tuple[SemanticFact, ...], profile: CategorySemanticProfileV1_1,
) -> ProductIdentity:
    candidates = tuple(item for item in facts if item.dimension == "product_identity")
    status, value, selected, reasons = _select(candidates, profile)
    if status is not SemanticDecisionStatus.GOVERNED:
        return ProductIdentity(
            status=status, normalized_identity=None, is_target_identity=None,
            fact_ids=tuple(item.fact_id for item in selected),
            evidence_ids=tuple(sorted({e for item in selected for e in item.evidence_ids})),
            reason_codes=reasons,
        )
    return ProductIdentity(
        status=status, normalized_identity=value["identity"],
        is_target_identity=bool(value["is_target"]),
        fact_ids=tuple(item.fact_id for item in selected),
        evidence_ids=tuple(sorted({e for item in selected for e in item.evidence_ids})),
        reason_codes=reasons,
    )


def _product_role(
    facts: tuple[SemanticFact, ...], profile: CategorySemanticProfileV1_1,
) -> ProductRole:
    relation_facts = tuple(item for item in facts if item.dimension == "relation_role")
    lifecycle_facts = tuple(
        item for item in facts if item.dimension == "consumption_lifecycle"
    )
    relation_status, relation_value, relation_selected, relation_reasons = _select(
        relation_facts, profile
    )
    lifecycle_status, lifecycle_value, lifecycle_selected, lifecycle_reasons = _select(
        lifecycle_facts, profile
    )
    return ProductRole(
        relation_role=(
            RelationRole(relation_value)
            if relation_status is SemanticDecisionStatus.GOVERNED
            else RelationRole.REVIEW_REQUIRED
            if relation_status is SemanticDecisionStatus.REVIEW_REQUIRED
            else RelationRole.UNKNOWN
        ),
        relation_status=relation_status,
        relation_fact_ids=tuple(item.fact_id for item in relation_selected),
        relation_reason_codes=relation_reasons,
        consumption_lifecycle=(
            ConsumptionLifecycle(lifecycle_value)
            if lifecycle_status is SemanticDecisionStatus.GOVERNED
            else ConsumptionLifecycle.REVIEW_REQUIRED
            if lifecycle_status is SemanticDecisionStatus.REVIEW_REQUIRED
            else ConsumptionLifecycle.UNKNOWN
        ),
        lifecycle_status=lifecycle_status,
        lifecycle_fact_ids=tuple(item.fact_id for item in lifecycle_selected),
        lifecycle_reason_codes=lifecycle_reasons,
    )


def _cohort(
    identity: ProductIdentity, role: ProductRole,
    profile: CategorySemanticProfileV1_1,
    *, route_critical_fact_ids: tuple[str, ...] = (),
) -> APDMarketCohortEligibility:
    policy = profile.cohort_policy
    evidence = tuple(sorted({
        *identity.fact_ids, *role.relation_fact_ids, *route_critical_fact_ids,
    }))
    if route_critical_fact_ids:
        state, eligible, reasons = (
            CohortEligibilityState.REVIEW_REQUIRED, False,
            ("ROUTE_CRITICAL_CONFLICT_REQUIRES_REVIEW",),
        )
    elif identity.status is SemanticDecisionStatus.REVIEW_REQUIRED or role.relation_status is SemanticDecisionStatus.REVIEW_REQUIRED:
        state, eligible, reasons = (
            CohortEligibilityState.REVIEW_REQUIRED, False,
            ("IDENTITY_OR_RELATION_ROLE_REVIEW_REQUIRED",),
        )
    elif identity.status is SemanticDecisionStatus.UNKNOWN or role.relation_status is SemanticDecisionStatus.UNKNOWN:
        state, eligible, reasons = (
            CohortEligibilityState.UNKNOWN, False,
            ("IDENTITY_OR_RELATION_ROLE_UNKNOWN",),
        )
    elif not identity.is_target_identity or identity.normalized_identity not in policy.target_identity_values:
        state, eligible, reasons = (
            CohortEligibilityState.OFF_TARGET_EXCLUDED, False,
            ("PRODUCT_IDENTITY_OUTSIDE_TARGET_MARKET",),
        )
    elif role.relation_role in policy.non_primary_relation_roles:
        state, eligible, reasons = (
            CohortEligibilityState.NON_PRIMARY_EXCLUDED, False,
            ("NON_PRIMARY_RELATION_ROLE_EXCLUDED_IN_PRIMARY_ONLY_MODE",),
        )
    elif role.relation_role in policy.primary_relation_roles:
        state, eligible, reasons = (
            CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE, True,
            ("TARGET_IDENTITY_AND_PRIMARY_RELATION_ROLE",),
        )
    else:
        state, eligible, reasons = (
            CohortEligibilityState.UNKNOWN, False, ("RELATION_ROLE_NOT_AUTHORIZED",),
        )
    return APDMarketCohortEligibility(
        state=state, eligible_for_primary_cohort=eligible,
        policy_id=policy.policy_id, policy_version=policy.version,
        evidence_fact_ids=evidence, reason_codes=reasons,
    )


def _listing_result(
    record: ListingRecordV1,
    profile: CategorySemanticProfileV1_1,
) -> ListingSemanticResult:
    observations, observation_limitations = _observations(record, profile)
    facts, evidence, fact_limitations = _fact_rules(record, observations, profile)
    identity_facts, identity_evidence = _identity_facts(record, observations, profile)
    relation_facts, relation_evidence = _decision_facts(
        record, observations, profile, rules=profile.relation_rules,
        dimension="relation_role",
    )
    lifecycle_facts, lifecycle_evidence = _decision_facts(
        record, observations, profile, rules=profile.lifecycle_rules,
        dimension="consumption_lifecycle",
    )
    all_facts = tuple(sorted(
        (*facts, *identity_facts, *relation_facts, *lifecycle_facts),
        key=lambda item: item.fact_id,
    ))
    all_evidence = tuple(sorted(
        {
            item.evidence_id: item
            for item in (*evidence, *identity_evidence, *relation_evidence, *lifecycle_evidence)
        }.values(),
        key=lambda item: item.evidence_id,
    ))
    relationships = _relationships(record.asin, all_facts, profile)
    identity = _identity(all_facts, profile)
    product_role = _product_role(all_facts, profile)
    critical_dimensions = {
        item.dimension for item in relationships
        if item.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
    }
    review_reasons: set[str] = set()
    if critical_dimensions:
        review_reasons.update(
            f"ROUTE_CRITICAL_CONFLICT:{dimension}" for dimension in critical_dimensions
        )
        if "product_identity" in critical_dimensions:
            identity = ProductIdentity(
                status=SemanticDecisionStatus.REVIEW_REQUIRED,
                normalized_identity=None, is_target_identity=None,
                fact_ids=identity.fact_ids, evidence_ids=identity.evidence_ids,
                reason_codes=tuple(sorted({*identity.reason_codes, "ROUTE_CRITICAL_IDENTITY_CONFLICT"})),
            )
        if "relation_role" in critical_dimensions:
            product_role = ProductRole(
                relation_role=RelationRole.REVIEW_REQUIRED,
                relation_status=SemanticDecisionStatus.REVIEW_REQUIRED,
                relation_fact_ids=product_role.relation_fact_ids,
                relation_reason_codes=tuple(sorted({
                    *product_role.relation_reason_codes, "ROUTE_CRITICAL_RELATION_CONFLICT"
                })),
                consumption_lifecycle=product_role.consumption_lifecycle,
                lifecycle_status=product_role.lifecycle_status,
                lifecycle_fact_ids=product_role.lifecycle_fact_ids,
                lifecycle_reason_codes=product_role.lifecycle_reason_codes,
            )
    route_critical_fact_ids = tuple(sorted({
        fact_id for item in relationships
        if item.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
        for fact_id in item.fact_ids
    }))
    cohort = _cohort(
        identity, product_role, profile,
        route_critical_fact_ids=route_critical_fact_ids,
    )
    role_coverage = tuple(
        (
            role,
            Availability.AVAILABLE
            if any(item.role is role for item in all_facts)
            else Availability.UNAVAILABLE,
        )
        for role in UniversalSemanticRole
    )
    limitations = tuple(sorted({*observation_limitations, *fact_limitations}))
    logical = {
        "listing_reference": record.asin,
        "upstream_record_fingerprint": record.record_fingerprint,
        "evidence": [item.to_dict() for item in all_evidence],
        "facts": [item.to_dict() for item in all_facts],
        "relationships": [item.to_dict() for item in relationships],
        "product_identity": identity.to_dict(), "product_role": product_role.to_dict(),
        "market_cohort_eligibility": cohort.to_dict(),
        "role_coverage": {role.value: state.value for role, state in role_coverage},
        "review_reason_codes": sorted(review_reasons), "limitations": list(limitations),
    }
    return ListingSemanticResult(
        listing_result_id=deterministic_id("listing-semantic-result-v2", logical),
        semantic_fingerprint=_hash(logical), listing_reference=record.asin,
        upstream_record_fingerprint=record.record_fingerprint,
        evidence=all_evidence, facts=all_facts, relationships=relationships,
        product_identity=identity, product_role=product_role,
        market_cohort_eligibility=cohort, role_coverage=role_coverage,
        review_reason_codes=tuple(sorted(review_reasons)), limitations=limitations,
    )


def build_semantic_engine_v2_result(
    dataset: GovernedMarketDatasetV1,
    *,
    profile: CategorySemanticProfileV1_1,
) -> SemanticEngineV2Result:
    """Transform governed listing evidence into deterministic semantic facts."""

    if not profile.supports_category(dataset.category):
        raise SemanticEngineV2Error(
            "PROFILE_CATEGORY_MISMATCH", "dataset category is outside profile scope"
        )
    if len({item.asin for item in dataset.records}) != len(dataset.records):
        raise SemanticEngineV2Error("LISTING_GRAIN_INVALID", "duplicate listing identities")
    listings = tuple(sorted(
        (_listing_result(record, profile) for record in dataset.records),
        key=lambda item: item.listing_reference,
    ))
    dataset_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="governed-market-dataset",
        target_id=dataset.dataset_id, target_version=dataset.contract_version,
        content_fingerprint=dataset.semantic_fingerprint,
    )
    profile_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="category-semantic-profile",
        target_id=profile.profile_id, target_version=profile.version,
        content_fingerprint=profile.fingerprint,
    )
    references = tuple(sorted(
        (dataset_reference, profile_reference), key=lambda item: item.reference_id
    ))
    relationship_counts = Counter(
        relationship.state.value
        for listing in listings for relationship in listing.relationships
    )
    identity_counts = Counter(item.product_identity.status.value for item in listings)
    relation_counts = Counter(item.product_role.relation_role.value for item in listings)
    lifecycle_counts = Counter(
        item.product_role.consumption_lifecycle.value for item in listings
    )
    cohort_counts = Counter(item.market_cohort_eligibility.state.value for item in listings)
    role_coverage = tuple(
        (
            role.value,
            sum(dict(item.role_coverage)[role] is Availability.AVAILABLE for item in listings),
            len(listings),
        )
        for role in UniversalSemanticRole
    )
    review_count = sum(
        bool(item.review_reason_codes)
        or item.product_identity.status is SemanticDecisionStatus.REVIEW_REQUIRED
        or item.product_role.relation_status is SemanticDecisionStatus.REVIEW_REQUIRED
        or item.product_role.lifecycle_status is SemanticDecisionStatus.REVIEW_REQUIRED
        for item in listings
    )
    unknown_identity_count = sum(
        item.product_identity.status is SemanticDecisionStatus.UNKNOWN for item in listings
    )
    diagnostics = (
        ("listing_count", len(listings)),
        ("fact_count", sum(len(item.facts) for item in listings)),
        ("relationship_count", sum(len(item.relationships) for item in listings)),
        ("contains_private_listing_values", False),
        ("network_calls", 0), ("llm_authoritative_decisions", 0),
    )
    logical = {
        "contract_version": "semantic-engine-result-v2.0",
        "upstream_dataset_id": dataset.dataset_id,
        "upstream_dataset_fingerprint": dataset.semantic_fingerprint,
        "semantic_engine_version": SEMANTIC_ENGINE_VERSION,
        "profile_id": profile.profile_id, "profile_version": profile.version,
        "profile_fingerprint": profile.fingerprint, "listing_count": len(listings),
        "listings": [item.to_dict() for item in listings],
        "references": [item.to_dict() for item in references],
        "role_coverage_summary": [
            {"role": role, "available_count": available, "total_count": total}
            for role, available, total in role_coverage
        ],
        "relationship_state_counts": dict(sorted(relationship_counts.items())),
        "identity_status_counts": dict(sorted(identity_counts.items())),
        "relation_role_counts": dict(sorted(relation_counts.items())),
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "cohort_state_counts": dict(sorted(cohort_counts.items())),
        "review_listing_count": review_count,
        "unknown_identity_count": unknown_identity_count,
        "diagnostics": {key: value for key, value in diagnostics},
    }
    return SemanticEngineV2Result(
        result_id=deterministic_id("semantic-engine-result-v2", logical),
        semantic_fingerprint=_hash(logical),
        upstream_dataset_id=dataset.dataset_id,
        upstream_dataset_fingerprint=dataset.semantic_fingerprint,
        semantic_engine_version=SEMANTIC_ENGINE_VERSION,
        profile_id=profile.profile_id, profile_version=profile.version,
        profile_fingerprint=profile.fingerprint, listing_count=len(listings),
        listings=listings, references=references, role_coverage_summary=role_coverage,
        relationship_state_counts=tuple(sorted(relationship_counts.items())),
        identity_status_counts=tuple(sorted(identity_counts.items())),
        relation_role_counts=tuple(sorted(relation_counts.items())),
        lifecycle_counts=tuple(sorted(lifecycle_counts.items())),
        cohort_state_counts=tuple(sorted(cohort_counts.items())),
        review_listing_count=review_count, unknown_identity_count=unknown_identity_count,
        diagnostics=diagnostics,
    )


__all__ = ("build_semantic_engine_v2_result",)
