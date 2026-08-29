"""Strict Category Semantic Profile V1.1 schema, loader, and fingerprint."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, TypeVar

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.listing_attribute_map.rule_pack import QuantityKind
from amazon_product_intelligence.product_attribute_extraction.models import (
    AttributeConfidenceLevel,
)

from .errors import SemanticEngineV2Error
from .models import (
    ConsumptionLifecycle,
    QuantitySubtype,
    RelationRole,
    RoleRelevance,
    SemanticScope,
    SemanticSourceClass,
    UniversalSemanticRole,
)


CATEGORY_SEMANTIC_PROFILE_SCHEMA_VERSION = "category-semantic-profile-v1.1"
SEMANTIC_NORMALIZATION_VERSION = "semantic-normalization-v2.0"

_TOP_KEYS = {
    "schema_version", "profile_id", "version", "category_scope",
    "category_aliases", "normalization_version", "source_authorization",
    "source_policies", "attribute_aliases", "value_aliases", "fact_rules",
    "identity_rules", "relation_rules", "lifecycle_rules", "coexistence_rules",
    "true_conflict_rules", "route_critical_conflict_rules",
    "quantity_scope_rules", "cohort_policy",
}
_SOURCE_POLICY_KEYS = {
    "policy_id", "role", "dimension", "primary_sources", "corroborating_sources",
    "fallback_sources", "forbidden_sources", "exact_specification",
    "multi_value", "relevance", "route_critical",
}
_ALIAS_KEYS = {"alias_id", "alias", "canonical"}
_FACT_RULE_KEYS = {
    "rule_id", "role", "dimension", "sources", "source_keys", "match_phrases",
    "exclusions", "value_mode", "normalized_value", "quantity_kind",
    "semantic_scope", "quantity_subtype", "confidence",
}
_IDENTITY_RULE_KEYS = {
    "rule_id", "sources", "phrases", "exclusions", "identity", "is_target", "priority",
}
_DECISION_RULE_KEYS = {"rule_id", "sources", "phrases", "exclusions", "result", "priority"}
_COEXISTENCE_KEYS = {"rule_id", "left_dimension", "right_dimension"}
_CONFLICT_KEYS = {"rule_id", "dimension", "values"}
_QUANTITY_SCOPE_KEYS = {
    "rule_id", "source_keys", "quantity_kind", "semantic_scope", "quantity_subtype",
}
_COHORT_KEYS = {
    "policy_id", "version", "analysis_mode", "target_identity_values",
    "primary_relation_roles", "non_primary_relation_roles",
}


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    policy_id: str
    role: UniversalSemanticRole
    dimension: str
    primary_sources: tuple[SemanticSourceClass, ...]
    corroborating_sources: tuple[SemanticSourceClass, ...]
    fallback_sources: tuple[SemanticSourceClass, ...]
    forbidden_sources: tuple[SemanticSourceClass, ...]
    exact_specification: bool
    multi_value: bool
    relevance: RoleRelevance
    route_critical: bool


@dataclass(frozen=True, slots=True)
class AliasRule:
    alias_id: str
    alias: str
    canonical: str


@dataclass(frozen=True, slots=True)
class FactRule:
    rule_id: str
    role: UniversalSemanticRole
    dimension: str
    sources: tuple[SemanticSourceClass, ...]
    source_keys: tuple[str, ...]
    match_phrases: tuple[str, ...]
    exclusions: tuple[str, ...]
    value_mode: str
    normalized_value: Any
    quantity_kind: QuantityKind | None
    semantic_scope: SemanticScope | None
    quantity_subtype: QuantitySubtype | None
    confidence: AttributeConfidenceLevel


@dataclass(frozen=True, slots=True)
class IdentityRule:
    rule_id: str
    sources: tuple[SemanticSourceClass, ...]
    phrases: tuple[str, ...]
    exclusions: tuple[str, ...]
    identity: str
    is_target: bool
    priority: int


@dataclass(frozen=True, slots=True)
class DecisionRule:
    rule_id: str
    sources: tuple[SemanticSourceClass, ...]
    phrases: tuple[str, ...]
    exclusions: tuple[str, ...]
    result: str
    priority: int


@dataclass(frozen=True, slots=True)
class CoexistenceRule:
    rule_id: str
    left_dimension: str
    right_dimension: str


@dataclass(frozen=True, slots=True)
class ConflictRule:
    rule_id: str
    dimension: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QuantityScopeRule:
    rule_id: str
    source_keys: tuple[str, ...]
    quantity_kind: QuantityKind
    semantic_scope: SemanticScope
    quantity_subtype: QuantitySubtype | None


@dataclass(frozen=True, slots=True)
class APDCohortPolicy:
    policy_id: str
    version: str
    analysis_mode: str
    target_identity_values: tuple[str, ...]
    primary_relation_roles: tuple[RelationRole, ...]
    non_primary_relation_roles: tuple[RelationRole, ...]


@dataclass(frozen=True, slots=True)
class CategorySemanticProfileV1_1:
    profile_id: str
    version: str
    category_scope: str
    category_aliases: tuple[str, ...]
    normalization_version: str
    source_authorization: tuple[SemanticSourceClass, ...]
    source_policies: tuple[SourcePolicy, ...]
    attribute_aliases: tuple[AliasRule, ...]
    value_aliases: tuple[AliasRule, ...]
    fact_rules: tuple[FactRule, ...]
    identity_rules: tuple[IdentityRule, ...]
    relation_rules: tuple[DecisionRule, ...]
    lifecycle_rules: tuple[DecisionRule, ...]
    coexistence_rules: tuple[CoexistenceRule, ...]
    true_conflict_rules: tuple[ConflictRule, ...]
    route_critical_conflict_rules: tuple[ConflictRule, ...]
    quantity_scope_rules: tuple[QuantityScopeRule, ...]
    cohort_policy: APDCohortPolicy
    fingerprint: str
    schema_version: str = CATEGORY_SEMANTIC_PROFILE_SCHEMA_VERSION

    @property
    def identity(self) -> str:
        return f"{self.profile_id}@{self.version}"

    def supports_category(self, category: str) -> bool:
        candidate = _normalize(category)
        return candidate in {self.category_scope, *self.category_aliases}

    def source_policy(self, dimension: str) -> SourcePolicy:
        try:
            return next(item for item in self.source_policies if item.dimension == dimension)
        except StopIteration as exc:
            raise SemanticEngineV2Error(
                "PROFILE_POLICY_MISSING", f"no source policy for dimension {dimension}"
            ) from exc

    def canonical_attribute_key(self, value: str) -> str:
        normalized = _normalize(value)
        return next(
            (item.canonical for item in self.attribute_aliases if item.alias == normalized),
            normalized,
        )

    def canonical_value(self, value: str) -> str:
        normalized = _normalize(value)
        return next(
            (item.canonical for item in self.value_aliases if item.alias == normalized),
            normalized,
        )

    def quantity_scope_authorization(self, rule: FactRule) -> QuantityScopeRule:
        """Return the one explicit scope authorization for a measurement rule.

        Source keys are a set at evaluation time, so their JSON ordering is not
        semantically significant.  All other quantity metadata must match exactly.
        Missing or ambiguous authorization is a profile error, including for profile
        objects constructed without the strict JSON loader.
        """

        if rule.value_mode != "MEASUREMENT":
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"fact rule {rule.rule_id} is not a MEASUREMENT rule",
            )
        signature = (
            frozenset(rule.source_keys), rule.quantity_kind,
            rule.semantic_scope, rule.quantity_subtype,
        )
        matches = tuple(
            item for item in self.quantity_scope_rules
            if (
                frozenset(item.source_keys), item.quantity_kind,
                item.semantic_scope, item.quantity_subtype,
            ) == signature
        )
        if len(matches) != 1:
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"MEASUREMENT rule {rule.rule_id} requires exactly one explicit "
                "quantity_scope_rules authorization",
            )
        return matches[0]


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _object(value: Any, path: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be object")
    unknown = sorted(set(value) - keys)
    missing = sorted(keys - set(value))
    if unknown or missing:
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", f"{path} unknown={unknown} missing={missing}"
        )
    return value


def _text(value: Any, path: str, *, normalize: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be text")
    result = " ".join(value.split())
    return result.casefold() if normalize else result


def _texts(value: Any, path: str, *, allow_empty: bool = False, normalize: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be list")
    result = tuple(_text(item, f"{path}[]", normalize=normalize) for item in value)
    if len(result) != len(set(result)):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} has duplicates")
    return result


E = TypeVar("E")


def _enum(enum_type: type[E], value: Any, path: str) -> E:
    try:
        return enum_type(_text(value, path).upper())  # type: ignore[call-arg]
    except ValueError as exc:
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} is invalid") from exc


def _enums(enum_type: type[E], value: Any, path: str, *, allow_empty: bool = False) -> tuple[E, ...]:
    values = _texts(value, path, allow_empty=allow_empty, normalize=False)
    result = tuple(_enum(enum_type, item, f"{path}[]") for item in values)
    if len(result) != len(set(result)):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} has duplicate enums")
    return result


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be boolean")
    return value


def _priority(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be nonnegative integer")
    return value


def _optional_enum(enum_type: type[E], value: Any, path: str) -> E | None:
    return None if value is None else _enum(enum_type, value, path)


def _aliases(values: Any, path: str) -> tuple[AliasRule, ...]:
    if not isinstance(values, list):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be list")
    result = []
    for index, raw in enumerate(values):
        item = _object(raw, f"{path}[{index}]", _ALIAS_KEYS)
        result.append(AliasRule(
            alias_id=_text(item["alias_id"], "alias_id"),
            alias=_text(item["alias"], "alias", normalize=True),
            canonical=_text(item["canonical"], "canonical", normalize=True),
        ))
    return tuple(result)


def _decision_rules(values: Any, path: str, allowed: type[RelationRole] | type[ConsumptionLifecycle]) -> tuple[DecisionRule, ...]:
    if not isinstance(values, list) or not values:
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", f"{path} must be nonempty list")
    result = []
    for index, raw in enumerate(values):
        item = _object(raw, f"{path}[{index}]", _DECISION_RULE_KEYS)
        result_value = _enum(allowed, item["result"], "result").value
        if result_value in {"UNKNOWN", "REVIEW_REQUIRED"}:
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"{path} cannot author UNKNOWN/REVIEW_REQUIRED as governed facts",
            )
        result.append(DecisionRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            sources=_enums(SemanticSourceClass, item["sources"], "sources"),
            phrases=_texts(item["phrases"], "phrases"),
            exclusions=_texts(item["exclusions"], "exclusions", allow_empty=True),
            result=result_value, priority=_priority(item["priority"], "priority"),
        ))
    return tuple(result)


def load_category_semantic_profile(path: str | Path) -> CategorySemanticProfileV1_1:
    candidate = Path(path)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SemanticEngineV2Error(
            "PROFILE_READ_FAILED", "profile must be readable UTF-8 JSON"
        ) from exc
    top = _object(payload, "profile", _TOP_KEYS)
    if top["schema_version"] != CATEGORY_SEMANTIC_PROFILE_SCHEMA_VERSION:
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "unsupported schema_version")
    if top["normalization_version"] != SEMANTIC_NORMALIZATION_VERSION:
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "unsupported normalization_version")
    authorization = _enums(
        SemanticSourceClass, top["source_authorization"], "source_authorization"
    )

    policies: list[SourcePolicy] = []
    for index, raw in enumerate(top["source_policies"]):
        item = _object(raw, f"source_policies[{index}]", _SOURCE_POLICY_KEYS)
        policy = SourcePolicy(
            policy_id=_text(item["policy_id"], "policy_id"),
            role=_enum(UniversalSemanticRole, item["role"], "role"),
            dimension=_text(item["dimension"], "dimension", normalize=True),
            primary_sources=_enums(SemanticSourceClass, item["primary_sources"], "primary_sources"),
            corroborating_sources=_enums(
                SemanticSourceClass, item["corroborating_sources"],
                "corroborating_sources", allow_empty=True,
            ),
            fallback_sources=_enums(
                SemanticSourceClass, item["fallback_sources"], "fallback_sources", allow_empty=True
            ),
            forbidden_sources=_enums(
                SemanticSourceClass, item["forbidden_sources"], "forbidden_sources", allow_empty=True
            ),
            exact_specification=_boolean(item["exact_specification"], "exact_specification"),
            multi_value=_boolean(item["multi_value"], "multi_value"),
            relevance=_enum(RoleRelevance, item["relevance"], "relevance"),
            route_critical=_boolean(item["route_critical"], "route_critical"),
        )
        used_sources = {
            *policy.primary_sources, *policy.corroborating_sources, *policy.fallback_sources,
        }
        if used_sources - set(authorization):
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID", "source policy uses unauthorized source"
            )
        if used_sources & set(policy.forbidden_sources):
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID", "source is both allowed and forbidden"
            )
        policies.append(policy)

    fact_rules: list[FactRule] = []
    for index, raw in enumerate(top["fact_rules"]):
        item = _object(raw, f"fact_rules[{index}]", _FACT_RULE_KEYS)
        mode = _text(item["value_mode"], "value_mode").upper()
        if mode not in {"FIXED", "SOURCE_VALUE", "MEASUREMENT"}:
            raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "invalid value_mode")
        sources = _enums(SemanticSourceClass, item["sources"], "sources")
        if set(sources) - set(authorization):
            raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "fact rule source unauthorized")
        normalized_value = item["normalized_value"]
        if mode == "FIXED" and normalized_value is None:
            raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "FIXED rule requires value")
        if mode != "FIXED" and normalized_value is not None:
            raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "non-FIXED rule value must be null")
        if mode == "SOURCE_VALUE" and SemanticSourceClass.LISTING_TITLE in sources:
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                "Title evidence cannot be passed through as a semantic fact value",
            )
        kind = _optional_enum(QuantityKind, item["quantity_kind"], "quantity_kind")
        scope = _optional_enum(SemanticScope, item["semantic_scope"], "semantic_scope")
        subtype = _optional_enum(QuantitySubtype, item["quantity_subtype"], "quantity_subtype")
        role = _enum(UniversalSemanticRole, item["role"], "role")
        if mode == "MEASUREMENT" and (kind is None or scope is None):
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID", "MEASUREMENT rule requires kind and scope"
            )
        if role is UniversalSemanticRole.QUANTITY and subtype is None:
            raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "QUANTITY rule requires subtype")
        fact_rules.append(FactRule(
            rule_id=_text(item["rule_id"], "rule_id"), role=role,
            dimension=_text(item["dimension"], "dimension", normalize=True),
            sources=sources,
            source_keys=_texts(item["source_keys"], "source_keys", allow_empty=True),
            match_phrases=_texts(item["match_phrases"], "match_phrases", allow_empty=True),
            exclusions=_texts(item["exclusions"], "exclusions", allow_empty=True),
            value_mode=mode, normalized_value=normalized_value, quantity_kind=kind,
            semantic_scope=scope, quantity_subtype=subtype,
            confidence=_enum(AttributeConfidenceLevel, item["confidence"], "confidence"),
        ))

    identity_rules: list[IdentityRule] = []
    for index, raw in enumerate(top["identity_rules"]):
        item = _object(raw, f"identity_rules[{index}]", _IDENTITY_RULE_KEYS)
        sources = _enums(SemanticSourceClass, item["sources"], "sources")
        if set(sources) - set(authorization):
            raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "identity source unauthorized")
        identity_rules.append(IdentityRule(
            rule_id=_text(item["rule_id"], "rule_id"), sources=sources,
            phrases=_texts(item["phrases"], "phrases"),
            exclusions=_texts(item["exclusions"], "exclusions", allow_empty=True),
            identity=_text(item["identity"], "identity", normalize=True),
            is_target=_boolean(item["is_target"], "is_target"),
            priority=_priority(item["priority"], "priority"),
        ))
    if not any(SemanticSourceClass.LISTING_TITLE in item.sources for item in identity_rules):
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", "Product Identity requires a Title primary/co-primary rule"
        )

    coexistence = tuple(
        CoexistenceRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            left_dimension=_text(item["left_dimension"], "left_dimension", normalize=True),
            right_dimension=_text(item["right_dimension"], "right_dimension", normalize=True),
        )
        for item in (
            _object(raw, f"coexistence_rules[{index}]", _COEXISTENCE_KEYS)
            for index, raw in enumerate(top["coexistence_rules"])
        )
    )

    def conflicts(name: str) -> tuple[ConflictRule, ...]:
        result: list[ConflictRule] = []
        for index, raw in enumerate(top[name]):
            item = _object(raw, f"{name}[{index}]", _CONFLICT_KEYS)
            values = _texts(item["values"], "values", allow_empty=True)
            if len(values) == 1:
                raise SemanticEngineV2Error(
                    "PROFILE_SCHEMA_INVALID",
                    f"{name}[{index}].values must be empty or contain at least two values",
                )
            result.append(ConflictRule(
                rule_id=_text(item["rule_id"], "rule_id"),
                dimension=_text(item["dimension"], "dimension", normalize=True),
                values=values,
            ))
        return tuple(result)

    quantity_rules = tuple(
        QuantityScopeRule(
            rule_id=_text(item["rule_id"], "rule_id"),
            source_keys=_texts(item["source_keys"], "source_keys"),
            quantity_kind=_enum(QuantityKind, item["quantity_kind"], "quantity_kind"),
            semantic_scope=_enum(SemanticScope, item["semantic_scope"], "semantic_scope"),
            quantity_subtype=_optional_enum(
                QuantitySubtype, item["quantity_subtype"], "quantity_subtype"
            ),
        )
        for item in (
            _object(raw, f"quantity_scope_rules[{index}]", _QUANTITY_SCOPE_KEYS)
            for index, raw in enumerate(top["quantity_scope_rules"])
        )
    )

    cohort_raw = _object(top["cohort_policy"], "cohort_policy", _COHORT_KEYS)
    cohort = APDCohortPolicy(
        policy_id=_text(cohort_raw["policy_id"], "policy_id"),
        version=_text(cohort_raw["version"], "version"),
        analysis_mode=_text(cohort_raw["analysis_mode"], "analysis_mode").upper(),
        target_identity_values=_texts(
            cohort_raw["target_identity_values"], "target_identity_values"
        ),
        primary_relation_roles=_enums(
            RelationRole, cohort_raw["primary_relation_roles"], "primary_relation_roles"
        ),
        non_primary_relation_roles=_enums(
            RelationRole, cohort_raw["non_primary_relation_roles"],
            "non_primary_relation_roles",
        ),
    )
    if cohort.analysis_mode != "PRIMARY_ONLY":
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "S2 supports PRIMARY_ONLY mode")
    if set(cohort.primary_relation_roles) & set(cohort.non_primary_relation_roles):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "cohort role sets overlap")

    profile = CategorySemanticProfileV1_1(
        profile_id=_text(top["profile_id"], "profile_id"),
        version=_text(top["version"], "version"),
        category_scope=_text(top["category_scope"], "category_scope", normalize=True),
        category_aliases=_texts(top["category_aliases"], "category_aliases", allow_empty=True),
        normalization_version=top["normalization_version"],
        source_authorization=authorization,
        source_policies=tuple(policies),
        attribute_aliases=_aliases(top["attribute_aliases"], "attribute_aliases"),
        value_aliases=_aliases(top["value_aliases"], "value_aliases"),
        fact_rules=tuple(fact_rules), identity_rules=tuple(identity_rules),
        relation_rules=_decision_rules(top["relation_rules"], "relation_rules", RelationRole),
        lifecycle_rules=_decision_rules(
            top["lifecycle_rules"], "lifecycle_rules", ConsumptionLifecycle
        ),
        coexistence_rules=coexistence,
        true_conflict_rules=conflicts("true_conflict_rules"),
        route_critical_conflict_rules=conflicts("route_critical_conflict_rules"),
        quantity_scope_rules=quantity_rules, cohort_policy=cohort,
        fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
    )
    all_ids = [
        *(item.policy_id for item in profile.source_policies),
        *(item.alias_id for item in profile.attribute_aliases),
        *(item.alias_id for item in profile.value_aliases),
        *(item.rule_id for item in profile.fact_rules),
        *(item.rule_id for item in profile.identity_rules),
        *(item.rule_id for item in profile.relation_rules),
        *(item.rule_id for item in profile.lifecycle_rules),
        *(item.rule_id for item in profile.coexistence_rules),
        *(item.rule_id for item in profile.true_conflict_rules),
        *(item.rule_id for item in profile.route_critical_conflict_rules),
        *(item.rule_id for item in profile.quantity_scope_rules),
        profile.cohort_policy.policy_id,
    ]
    if len(all_ids) != len(set(all_ids)):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "rule/policy IDs must be unique")
    measurement_rules = tuple(
        item for item in profile.fact_rules if item.value_mode == "MEASUREMENT"
    )
    for item in measurement_rules:
        if not item.source_keys:
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"MEASUREMENT rule {item.rule_id} requires explicit source_keys",
            )
        profile.quantity_scope_authorization(item)
    measurement_signatures = {
        (
            frozenset(item.source_keys), item.quantity_kind,
            item.semantic_scope, item.quantity_subtype,
        )
        for item in measurement_rules
    }
    unused_quantity_rules = sorted(
        item.rule_id for item in profile.quantity_scope_rules
        if (
            frozenset(item.source_keys), item.quantity_kind,
            item.semantic_scope, item.quantity_subtype,
        ) not in measurement_signatures
    )
    if unused_quantity_rules:
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID",
            f"quantity scope authorizations lack MEASUREMENT rules: {unused_quantity_rules}",
        )
    dimensions = {item.dimension for item in profile.source_policies}
    if len(dimensions) != len(profile.source_policies):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "source policy dimensions duplicate")
    missing_policies = sorted({item.dimension for item in profile.fact_rules} - dimensions)
    if missing_policies:
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", f"fact rules lack source policies: {missing_policies}"
        )
    mandatory_dimensions = {"product_identity", "relation_role", "consumption_lifecycle"}
    if mandatory_dimensions - dimensions:
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", "identity/relation/lifecycle source policies are required"
        )
    authorized = set(profile.source_authorization)
    authoritative_rules = (
        *profile.identity_rules, *profile.relation_rules, *profile.lifecycle_rules,
    )
    if any(set(item.sources) - authorized for item in authoritative_rules):
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", "authoritative rule uses unauthorized source"
        )
    if any(
        SemanticSourceClass.LLM_DERIVED_CANDIDATE in item.sources
        for item in authoritative_rules
    ):
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", "LLM candidates cannot author identity or Product Role"
        )
    policy_by_dimension = {item.dimension: item for item in profile.source_policies}

    def validate_rule_sources(
        *, rule_id: str, dimension: str,
        sources: tuple[SemanticSourceClass, ...],
    ) -> None:
        policy = policy_by_dimension.get(dimension)
        if policy is None:
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"rule {rule_id} lacks source policy for dimension {dimension}",
            )
        forbidden = set(sources) & set(policy.forbidden_sources)
        if forbidden:
            names = sorted(item.value for item in forbidden)
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"rule {rule_id} uses forbidden source for {dimension}: {names}",
            )
        governed = {
            *policy.primary_sources,
            *policy.corroborating_sources,
            *policy.fallback_sources,
        }
        outside_policy = set(sources) - governed
        if outside_policy:
            names = sorted(item.value for item in outside_policy)
            raise SemanticEngineV2Error(
                "PROFILE_SCHEMA_INVALID",
                f"rule {rule_id} uses source outside {dimension} policy: {names}",
            )

    for item in profile.fact_rules:
        validate_rule_sources(
            rule_id=item.rule_id, dimension=item.dimension, sources=item.sources,
        )
    for dimension, rules in (
        ("product_identity", profile.identity_rules),
        ("relation_role", profile.relation_rules),
        ("consumption_lifecycle", profile.lifecycle_rules),
    ):
        for item in rules:
            validate_rule_sources(
                rule_id=item.rule_id, dimension=dimension, sources=item.sources,
            )

    if any(item.dimension not in policy_by_dimension for item in (
        *profile.true_conflict_rules, *profile.route_critical_conflict_rules,
    )):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "conflict rule lacks source policy")
    if any(
        not policy_by_dimension[item.dimension].route_critical
        for item in profile.route_critical_conflict_rules
    ):
        raise SemanticEngineV2Error(
            "PROFILE_SCHEMA_INVALID", "route-critical rule requires route-critical source policy"
        )
    if any(
        item.left_dimension not in dimensions or item.right_dimension not in dimensions
        for item in profile.coexistence_rules
    ):
        raise SemanticEngineV2Error("PROFILE_SCHEMA_INVALID", "coexistence rule lacks source policy")
    return profile


__all__ = (
    "APDCohortPolicy", "AliasRule", "CATEGORY_SEMANTIC_PROFILE_SCHEMA_VERSION",
    "CategorySemanticProfileV1_1", "CoexistenceRule", "ConflictRule",
    "DecisionRule", "FactRule", "IdentityRule", "QuantityScopeRule",
    "SEMANTIC_NORMALIZATION_VERSION", "SourcePolicy",
    "load_category_semantic_profile",
)
