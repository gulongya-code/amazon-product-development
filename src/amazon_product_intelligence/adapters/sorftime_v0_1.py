"""Audited offline Sorftime mapping slice V0.1.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import replace
import json
import re
from typing import Any, Mapping

from amazon_product_intelligence.contracts import (
    BlockingScope,
    Channel,
    EstimateMethodStatus,
    EvidenceType,
    FactGroup,
    NormalizationStatus,
    OriginStage,
    PeriodType,
    PresenceStatus,
    ProductKeywordRelationshipObservation,
    QueryExecutionOutcome,
    RelationshipDirection,
    RelationshipType,
    ResultStatus,
    ScopeStatus,
    ScopeType,
    SemanticStatus,
    Severity,
    SubjectRef,
    SubjectType,
    Unit,
    ValueType,
    deterministic_id,
)

from .base import (
    AdaptationContext,
    AdaptationResult,
    MappingDisposition,
    MappingSpecification,
    _AdapterSession,
    _collection_failure,
    _prepare_session,
    absent_value,
    keyword_identity,
    normalized_asin,
    product_identity,
    product_subject,
    strict_number,
    value_envelope,
)


def _spec(
    payload_kind: str,
    source_tool: str,
    mapping_version: str,
    *,
    version: str = "0.1",
) -> MappingSpecification:
    return MappingSpecification(
        specification_id=f"sorftime.{payload_kind}",
        version=version,
        mapping_version=mapping_version,
        provider="sorftime",
        payload_kind=payload_kind,
        source_tool=source_tool,
    )


_MAPPING_SPECIFICATIONS: Mapping[str, MappingSpecification] = {
    "product_detail": _spec(
        "product_detail", "product_detail", "sorftime_product_detail_mapping_v1"
    ),
    "product_variations": _spec(
        "product_variations",
        "product_variations",
        "sorftime_variations_mapping_v1_1",
        version="0.1.1",
    ),
    "product_reviews": _spec(
        "product_reviews", "product_reviews", "sorftime_reviews_mapping_v1"
    ),
    "asin_keywords": _spec(
        "asin_keywords",
        "ASINRequestKeyword",
        "sorftime_asin_to_keyword_mapping_v1",
        version="0.1.2",
    ),
}


_ATTRIBUTE_DIMENSIONS: Mapping[str, tuple[str, FactGroup]] = {
    "Material": ("material", FactGroup.ATTRIBUTE),
    "Brand": ("brand", FactGroup.IDENTITY_RELATED),
    "Item dimensions L x W x H": ("item_dimensions", FactGroup.TECHNICAL),
    "Exterior Finish": ("exterior_finish", FactGroup.ATTRIBUTE),
    "Inlet Connection Size": ("inlet_connection_size", FactGroup.TECHNICAL),
    "Inlet Connection Type": ("inlet_connection_type", FactGroup.TECHNICAL),
    "Outlet Connection Type": ("outlet_connection_type", FactGroup.TECHNICAL),
    "Maximum Operating Pressure": ("maximum_operating_pressure", FactGroup.TECHNICAL),
    "Number of Ports": ("number_of_ports", FactGroup.TECHNICAL),
    "Outlet Connection Size": ("outlet_connection_size", FactGroup.TECHNICAL),
    "Color": ("color", FactGroup.ATTRIBUTE),
    "Style": ("style", FactGroup.ATTRIBUTE),
    "Number of Pieces": ("quantity", FactGroup.ATTRIBUTE),
    "Size": ("size", FactGroup.ATTRIBUTE),
    "Weave Type": ("weave_type", FactGroup.ATTRIBUTE),
    "Item Weight": ("item_weight", FactGroup.TECHNICAL),
}


def _marketplace_subject(session: _AdapterSession) -> SubjectRef:
    marketplace = session.context.marketplace
    return SubjectRef(
        subject_type=SubjectType.MARKETPLACE,
        subject_id=f"marketplace:{marketplace}",
        marketplace=marketplace,
    )


def _fail(
    session: _AdapterSession,
    code: str,
    message: str,
    source_locator: str,
) -> AdaptationResult:
    return _collection_failure(
        provider=session.provider,
        adapter_version=session.adapter_version,
        payload_kind=session.context.payload_kind,
        payload=session.payload,
        context=session.context,
        mapping_specification=session.mapping_specification,
        code=code,
        message=message,
        source_locator=source_locator,
    )


def _report_fields(
    session: _AdapterSession,
    record: Mapping[str, Any],
    *,
    locator: str,
    mapped: set[str],
    ignored: Mapping[str, str] | None = None,
) -> None:
    ignored = ignored or {}
    for key in sorted(record):
        if key in mapped:
            continue
        path = f"{locator}.{key}"
        if key in ignored:
            session.diagnostic(
                code="SOURCE_FIELD_INTENTIONALLY_IGNORED",
                message=ignored[key],
                source_locator=path,
                disposition=MappingDisposition.OUT_OF_SCOPE,
                affects_status=False,
            )
        else:
            session.diagnostic(
                code="UNMAPPED_SOURCE_FIELD",
                message="Raw field is retained but has no approved V0.1 canonical mapping.",
                source_locator=path,
                disposition=MappingDisposition.SEMANTICS_UNCONFIRMED,
            )


def _record_issue(
    session: _AdapterSession,
    *,
    subject: SubjectRef,
    dimension: str,
    code: str,
    message: str,
    locator: str,
    blocking_scope: BlockingScope = BlockingScope.FIELD,
) -> str:
    session.diagnostic(
        code=code,
        message=message,
        source_locator=locator,
        disposition=MappingDisposition.SEMANTICS_UNCONFIRMED,
        blocking=blocking_scope is not BlockingScope.NONE,
    )
    return session.quality_issue(
        code=code,
        subject=subject,
        dimension=dimension,
        message=f"{locator}: {message}",
        severity=Severity.WARNING,
        blocking_scope=blocking_scope,
        origin_stage=OriginStage.RAW_EVIDENCE,
    )


def _string_value(raw: str, *, semantic_status: SemanticStatus = SemanticStatus.CONFIRMED) -> Any:
    return value_envelope(
        presence_status=PresenceStatus.PRESENT,
        raw_value=raw,
        normalized_value=raw,
        value_type=ValueType.STRING,
        normalization_status=NormalizationStatus.NOT_APPLICABLE,
        semantic_status=semantic_status,
    )


def _sorftime_envelope(
    session: _AdapterSession,
    *,
    data_must_be_list: bool,
) -> tuple[Mapping[str, Any], Any] | AdaptationResult:
    doc = session.payload.get("doc")
    data = session.payload.get("data")
    if not isinstance(doc, MappingABC):
        return _fail(session, "MALFORMED_PROVIDER_ENVELOPE", "Sorftime doc must be an object.", "$.doc")
    expected = (tuple, list) if data_must_be_list else MappingABC
    if not isinstance(data, expected):
        description = "array" if data_must_be_list else "object"
        return _fail(
            session,
            "MALFORMED_PROVIDER_ENVELOPE",
            f"Sorftime data must be an {description}.",
            "$.data",
        )
    _report_fields(session, session.payload, locator="$", mapped={"doc", "data"})
    return doc, data


def _request_asin(session: _AdapterSession) -> str | None:
    candidates = {
        candidate
        for key in ("asin", "Asin", "ASIN")
        if (candidate := normalized_asin(session.context.sanitized_request.get(key))) is not None
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def _add_direct_string_fact(
    session: _AdapterSession,
    *,
    record: Mapping[str, Any],
    key: str,
    locator: str,
    product: Any,
    dimension: str,
    fact_group: FactGroup,
    source_identity: str,
    provider_semantic: str,
) -> Any | None:
    raw = record.get(key)
    if isinstance(raw, str):
        return session.add_product_fact(
            product=product,
            dimension=dimension,
            fact_group=fact_group,
            value=_string_value(raw),
            source_field=f"data.{key}",
            source_record_identity=source_identity,
            provider_semantic=provider_semantic,
            discriminator=locator,
        )
    if key in record:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension=dimension,
            code="INVALID_PRIMITIVE_TYPE",
            message=f"{key} must be a string; no observation emitted.",
            locator=locator,
        )
    return None


def _add_product_metric(
    session: _AdapterSession,
    *,
    record: Mapping[str, Any],
    key: str,
    locator: str,
    product: Any,
    metric: str,
    source_identity: str,
    unit: Unit,
    evidence_type: EvidenceType,
    semantic: str,
    integer: bool = False,
    currency: str | None = None,
    period_type: PeriodType = PeriodType.INSTANT,
) -> Any | None:
    raw = record.get(key)
    if key not in record:
        return None
    numeric = strict_number(raw)
    if numeric is None or (integer and type(raw) is not int) or numeric < 0:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension=metric,
            code="INVALID_METRIC_PRIMITIVE",
            message=f"{key} must be a finite non-negative {'integer' if integer else 'number'}.",
            locator=locator,
        )
        return None
    return session.add_metric(
        product=product,
        metric=metric,
        value=value_envelope(
            presence_status=PresenceStatus.PRESENT,
            raw_value=raw,
            normalized_value=numeric,
            value_type=ValueType.INTEGER if integer else ValueType.NUMBER,
            unit=unit,
            normalization_status=NormalizationStatus.NORMALIZED,
            semantic_status=SemanticStatus.CONFIRMED,
        ),
        source_field=f"data.{key}",
        source_record_identity=source_identity,
        metric_semantic=semantic,
        evidence_type=evidence_type,
        currency=currency,
        period_type=period_type,
    )


def _parse_attributes(
    session: _AdapterSession,
    *,
    record: Mapping[str, Any],
    product: Any,
    source_identity: str,
) -> list[Any]:
    raw = record.get("attributes")
    if raw is None and "attributes" in record:
        session.diagnostic(
            code="EXPLICIT_NULL_ATTRIBUTES",
            message="Explicit null attributes are retained and are not treated as an empty attribute set.",
            source_locator="$.data.attributes",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
        return []
    if not isinstance(raw, str):
        if "attributes" in record:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="structured_attributes",
                code="INVALID_ATTRIBUTES_PRIMITIVE",
                message="attributes must be the audited JSON-encoded string.",
                locator="$.data.attributes",
            )
        return []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="structured_attributes",
            code="INVALID_ATTRIBUTES_JSON",
            message="attributes string is not valid JSON.",
            locator="$.data.attributes",
        )
        return []
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="structured_attributes",
            code="INVALID_ATTRIBUTES_OBJECT",
            message="decoded attributes must be an object with string keys.",
            locator="$.data.attributes",
        )
        return []
    pressure_observations: list[Any] = []
    for key in sorted(decoded):
        locator = f"$.data.attributes.{key}"
        if key not in _ATTRIBUTE_DIMENSIONS:
            session.diagnostic(
                code="UNMAPPED_STRUCTURED_ATTRIBUTE",
                message="Structured attribute is retained but its canonical dimension is not approved.",
                source_locator=locator,
                disposition=MappingDisposition.SEMANTICS_UNCONFIRMED,
            )
            continue
        raw_value = decoded[key]
        dimension, fact_group = _ATTRIBUTE_DIMENSIONS[key]
        if not isinstance(raw_value, str):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension=dimension,
                code="INVALID_ATTRIBUTE_PRIMITIVE",
                message="Audited structured attribute value must be a string.",
                locator=locator,
            )
            continue
        if key == "Maximum Operating Pressure":
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s+pascal", raw_value, flags=re.IGNORECASE)
            if match is None:
                _record_issue(
                    session,
                    subject=product_subject(product),
                    dimension=dimension,
                    code="UNSUPPORTED_PRESSURE_UNIT",
                    message="Only the audited '<number> pascal' attribute form is executable.",
                    locator=locator,
                )
                continue
            number = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
            observation = session.add_product_fact(
                product=product,
                dimension=dimension,
                fact_group=fact_group,
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=raw_value,
                    normalized_value=number,
                    value_type=ValueType.NUMBER,
                    unit=Unit(dimension="PRESSURE", unit_code="Pa", unit_system="SI"),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"attributes.{key}",
                source_record_identity=source_identity,
                provider_semantic="Maximum Operating Pressure structured attribute",
                discriminator=f"attribute:{key}",
            )
            pressure_observations.append(observation)
        else:
            session.add_product_fact(
                product=product,
                dimension=dimension,
                fact_group=fact_group,
                value=_string_value(raw_value),
                source_field=f"attributes.{key}",
                source_record_identity=source_identity,
                provider_semantic=f"Structured product attribute: {key}",
                discriminator=f"attribute:{key}",
            )
    return pressure_observations


def _audited_pressure_spans(
    session: _AdapterSession,
    *,
    record: Mapping[str, Any],
    product: Any,
    source_identity: str,
) -> list[Any]:
    observations: list[Any] = []
    title = record.get("title")
    if isinstance(title, str):
        match = re.search(r"(?<![0-9])([0-9]+(?:\.[0-9]+)?)\s+WOG\b", title, flags=re.IGNORECASE)
        if match is not None:
            number = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
            observation = session.add_product_fact(
                product=product,
                dimension="maximum_operating_pressure",
                fact_group=FactGroup.TECHNICAL,
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=match.group(0),
                    normalized_value=number,
                    value_type=ValueType.NUMBER,
                    unit=Unit(dimension="PRESSURE", unit_code="WOG", unit_system="SERVICE_RATING"),
                    normalization_status=NormalizationStatus.AMBIGUOUS,
                    semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                ),
                source_field="data.title#span:WOG",
                source_record_identity=source_identity,
                provider_semantic="Audited title text span containing WOG service/rating evidence",
                discriminator="title-pressure-wog",
                result_status=ResultStatus.PARTIAL,
            )
            issue_id = _record_issue(
                session,
                subject=product_subject(product),
                dimension="maximum_operating_pressure",
                code="WOG_SEMANTICS_UNCONFIRMED",
                message="WOG is retained as a service/rating designation and is not treated as PSI.",
                locator="$.data.title#span:WOG",
            )
            session.attach_issue((observation.observation_id,), issue_id)
            observations.append(observation)
    description = record.get("description")
    if isinstance(description, str):
        match = re.search(r"(?<![0-9])([0-9]+(?:\.[0-9]+)?)\s+PSI\b", description, flags=re.IGNORECASE)
        if match is not None:
            number = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
            observations.append(
                session.add_product_fact(
                    product=product,
                    dimension="maximum_operating_pressure",
                    fact_group=FactGroup.TECHNICAL,
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=match.group(0),
                        normalized_value=number,
                        value_type=ValueType.NUMBER,
                        unit=Unit(
                            dimension="PRESSURE",
                            unit_code="psi",
                            unit_system="US_CUSTOMARY",
                        ),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field="data.description#span:PSI",
                    source_record_identity=source_identity,
                    provider_semantic="Audited description text span containing PSI pressure evidence",
                    discriminator="description-pressure-psi",
                )
            )
    return observations


def _product_detail(
    session: _AdapterSession,
    doc: Mapping[str, Any],
    record: Mapping[str, Any],
) -> AdaptationResult:
    asin = normalized_asin(record.get("asin"))
    request_asin = _request_asin(session)
    if asin is None or (request_asin is not None and request_asin != asin):
        return _fail(
            session,
            "INVALID_PRODUCT_IDENTITY",
            "Product detail ASIN is invalid or disagrees with request context.",
            "$.data.asin",
        )
    product = product_identity(session.context.marketplace, asin)
    source_identity = f"{session.context.marketplace}:{asin}"

    _add_direct_string_fact(
        session,
        record=record,
        key="title",
        locator="$.data.title",
        product=product,
        dimension="title",
        fact_group=FactGroup.IDENTITY_RELATED,
        source_identity=source_identity,
        provider_semantic="Product title",
    )
    _add_direct_string_fact(
        session,
        record=record,
        key="brand",
        locator="$.data.brand",
        product=product,
        dimension="brand",
        fact_group=FactGroup.IDENTITY_RELATED,
        source_identity=source_identity,
        provider_semantic="Brand",
    )
    _add_direct_string_fact(
        session,
        record=record,
        key="category",
        locator="$.data.category",
        product=product,
        dimension="category",
        fact_group=FactGroup.IDENTITY_RELATED,
        source_identity=source_identity,
        provider_semantic="Product category",
    )
    _add_direct_string_fact(
        session,
        record=record,
        key="node_id",
        locator="$.data.node_id",
        product=product,
        dimension="category_node_id",
        fact_group=FactGroup.IDENTITY_RELATED,
        source_identity=source_identity,
        provider_semantic="Amazon category node identifier",
    )
    _add_direct_string_fact(
        session,
        record=record,
        key="description",
        locator="$.data.description",
        product=product,
        dimension="description",
        fact_group=FactGroup.DESCRIPTION,
        source_identity=source_identity,
        provider_semantic="Product description containing HTML tags",
    )

    parent_raw = record.get("parent_asin")
    if isinstance(parent_raw, str):
        parent = normalized_asin(parent_raw)
        if parent is None:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="parent_product_relationship",
                code="INVALID_PARENT_ASIN",
                message="parent_asin is not a valid ASIN.",
                locator="$.data.parent_asin",
            )
        elif parent == asin:
            session.diagnostic(
                code="SELF_PARENT_SEMANTICS_UNCONFIRMED",
                message="Self-valued parent_asin is retained in raw evidence and is not published as a relationship.",
                source_locator="$.data.parent_asin",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        else:
            session.add_product_fact(
                product=product,
                dimension="parent_product_relationship",
                fact_group=FactGroup.VARIATION,
                value=_string_value(parent),
                source_field="data.parent_asin",
                source_record_identity=source_identity,
                provider_semantic="Provider-reported parent ASIN",
            )
    elif "parent_asin" in record:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="parent_product_relationship",
            code="INVALID_PRIMITIVE_TYPE",
            message="parent_asin must be a string.",
            locator="$.data.parent_asin",
        )

    currency = session.context.currency
    if currency is not None:
        _add_product_metric(
            session,
            record=record,
            key="price",
            locator="$.data.price",
            product=product,
            metric="price",
            source_identity=source_identity,
            unit=Unit(dimension="CURRENCY", unit_code=currency, unit_system="ISO_4217"),
            evidence_type=EvidenceType.OBSERVED,
            semantic="Selling price",
            currency=currency,
        )
    elif "price" in record:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="price",
            code="CURRENCY_CONTEXT_MISSING",
            message="Price is not published without explicit context currency.",
            locator="$.data.price",
        )
    _add_product_metric(
        session,
        record=record,
        key="star_rating",
        locator="$.data.star_rating",
        product=product,
        metric="rating",
        source_identity=source_identity,
        unit=Unit(dimension="RATING", unit_code="stars_5", unit_system="DOMAIN"),
        evidence_type=EvidenceType.OBSERVED,
        semantic="Displayed star rating on a five-star scale",
    )
    _add_product_metric(
        session,
        record=record,
        key="review_count",
        locator="$.data.review_count",
        product=product,
        metric="review_count",
        source_identity=source_identity,
        unit=Unit(dimension="COUNT", unit_code="reviews", unit_system="DOMAIN"),
        evidence_type=EvidenceType.OBSERVED,
        semantic="Displayed number of reviews",
        integer=True,
    )

    pressure_observations = _parse_attributes(
        session,
        record=record,
        product=product,
        source_identity=source_identity,
    )
    pressure_observations.extend(
        _audited_pressure_spans(
            session,
            record=record,
            product=product,
            source_identity=source_identity,
        )
    )
    if len(pressure_observations) > 1:
        observation_ids = tuple(item.observation_id for item in pressure_observations)
        issue_id = session.quality_issue(
            code="UNIT_SEMANTIC_CONFLICT",
            subject=product_subject(product),
            dimension="maximum_operating_pressure",
            message=(
                "Audited pressure evidence uses distinct pascal, WOG, and/or PSI semantics; values remain "
                "separate and unresolved with no conversion."
            ),
            source_references=(session.raw_evidence_id,) + observation_ids,
            severity=Severity.MATERIAL,
            blocking_scope=BlockingScope.FIELD,
            origin_stage=OriginStage.RAW_EVIDENCE,
        )
        session.diagnostic(
            code="UNIT_SEMANTIC_CONFLICT",
            message="Pressure candidates remain separate; no unit conversion or preferred value is produced.",
            source_locator="$.data",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            blocking=True,
        )
        session.attach_issue(observation_ids, issue_id)

    monthly_sales = record.get("monthly_sales_volume")
    if "monthly_sales_volume" in record:
        numeric = strict_number(monthly_sales)
        if numeric is None or numeric < 0:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="estimated_monthly_sales",
                code="INVALID_MONTHLY_SALES_PRIMITIVE",
                message="monthly_sales_volume must be a finite non-negative number.",
                locator="$.data.monthly_sales_volume",
            )
        else:
            observation = session.add_metric(
                product=product,
                metric="estimated_monthly_sales",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=monthly_sales,
                    normalized_value=numeric,
                    value_type=ValueType.NUMBER,
                    unit=Unit(dimension="COUNT", unit_code="units", unit_system="PROVIDER"),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                ),
                source_field="data.monthly_sales_volume",
                source_record_identity=source_identity,
                metric_semantic="Provider monthly sales volume; month, capture method, and estimate method unconfirmed",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                period_type=PeriodType.UNKNOWN,
                result_status=ResultStatus.PARTIAL,
                documentation_reference=f"{session.raw_evidence_id}#doc.monthly_sales_volume",
            )
            issue_id = _record_issue(
                session,
                subject=product_subject(product),
                dimension="estimated_monthly_sales",
                code="SALES_METHOD_PERIOD_UNCONFIRMED",
                message="The month, capture method, and estimate method are not supplied by the payload.",
                locator="$.data.monthly_sales_volume",
            )
            session.attach_issue((observation.observation_id,), issue_id)

    session.diagnostic(
        code="BULLET_POINTS_NOT_PRESENT",
        message="Description is preserved as description evidence and is not relabeled as bullet points.",
        source_locator="$.data.description",
        disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        affects_status=False,
    )
    _report_fields(
        session,
        record,
        locator="$.data",
        mapped={
            "asin",
            "parent_asin",
            "title",
            "price",
            "star_rating",
            "review_count",
            "brand",
            "node_id",
            "category",
            "attributes",
            "description",
            "monthly_sales_volume",
        },
        ignored={
            "main_image": "Image processing is out of scope.",
            "coupon": "Coupon normalization is outside this mapping slice.",
            "seller_name": "Seller analysis is out of scope.",
            "online_date": "Listing-age analysis is out of scope.",
            "days_on_shelf": "Listing-age analysis is out of scope.",
            "variation_count": "Variation records are handled by product_variations payloads.",
            "delivery_type": "Fulfillment analysis is out of scope.",
            "fba_fee": "Profit analysis is out of scope.",
            "fbm_delivery_fee": "Profit analysis is out of scope.",
            "top_category": "Provider display summary is retained; direct category/node fields are mapped.",
            "subcategory": "Provider display summary is retained; direct category/node fields are mapped.",
            "monthly_sales_amount": "Revenue mapping is outside this audited slice.",
            "package_size_cm": "Package normalization is outside this mapping slice.",
            "weight_g": "Package normalization is outside this mapping slice.",
            "gross_profit": "Profit analysis is out of scope.",
            "gross_profit_rate": "Profit analysis is out of scope.",
            "a_plus": "A+ content extraction is out of scope.",
        },
    )
    _report_fields(
        session,
        doc,
        locator="$.doc",
        mapped=set(record),
        ignored={key: "Provider field documentation is retained as provenance metadata." for key in doc},
    )
    return session.finish()


def _variation_property_facts(
    session: _AdapterSession,
    *,
    product: Any,
    raw_property: str,
    row_index: int,
    source_identity: str,
) -> None:
    approved = {"Size": "size", "Color": "color"}
    for part_index, part in enumerate(raw_property.split(",")):
        if ":" not in part:
            session.diagnostic(
                code="UNPARSED_VARIATION_PROPERTY",
                message="Variation property fragment is retained but not parsed.",
                source_locator=f"$.data[{row_index}].Property",
                disposition=MappingDisposition.SEMANTICS_UNCONFIRMED,
            )
            continue
        key, value = (item.strip() for item in part.split(":", 1))
        dimension = approved.get(key)
        if dimension is None:
            session.diagnostic(
                code="UNMAPPED_VARIATION_PROPERTY",
                message="Only audited Size and Color variation properties are executable.",
                source_locator=f"$.data[{row_index}].Property",
                disposition=MappingDisposition.SEMANTICS_UNCONFIRMED,
            )
            continue
        session.add_product_fact(
            product=product,
            dimension=dimension,
            fact_group=FactGroup.VARIATION,
            value=_string_value(value),
            source_field=f"data[{row_index}].Property#{key}",
            source_record_identity=source_identity,
            provider_semantic=f"Child variation property {key}",
            scope_type=ScopeType.CHILD_ASIN,
            discriminator=f"property:{part_index}:{key}",
        )


def _product_variations(
    session: _AdapterSession,
    doc: Mapping[str, Any],
    rows: Any,
) -> AdaptationResult:
    query_asin = _request_asin(session)
    if query_asin is None:
        return _fail(
            session,
            "MISSING_REQUEST_IDENTITY",
            "sanitized_request.asin is required as the variation query identity.",
            "context.sanitized_request.asin",
        )
    session.diagnostic(
        code="VARIATION_PARENT_SEMANTICS_UNCONFIRMED",
        message=(
            "The request ASIN is query context, not a response-confirmed parent; "
            "child facts are retained without directed parent relationships."
        ),
        source_locator="context.sanitized_request.asin",
        disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
    )
    valid_totals = {
        row.get("ItemTotal")
        for row in rows
        if isinstance(row, MappingABC)
        and type(row.get("ItemTotal")) is int
        and row.get("ItemTotal") > 0
    }
    provider_total = next(iter(valid_totals)) if len(valid_totals) == 1 else None
    returned_indexes = {
        row.get("ItemIndex")
        for row in rows
        if isinstance(row, MappingABC)
        and type(row.get("ItemIndex")) is int
        and row.get("ItemIndex") > 0
    }
    complete_index_set = (
        provider_total is not None
        and len(rows) == provider_total
        and returned_indexes == set(range(1, provider_total + 1))
    )
    session.raw_evidence = replace(
        session.raw_evidence,
        response_status=("SUCCESS" if complete_index_set else "PARTIAL"),
        pagination={
            "request_page": session.context.sanitized_request.get(
                "PageIndex", session.context.sanitized_request.get("pageIndex")
            ),
            "request_page_size": None,
            "returned_count": len(rows),
            "provider_total": provider_total,
            "collection_status": (
                "COMPLETE_INDEX_SET" if complete_index_set else "PARTIAL_OR_INCONSISTENT_INDEX_SET"
            ),
        },
    )
    sales_doc = doc.get("sales_amount")
    sales_semantics_confirmed = (
        isinstance(sales_doc, str)
        and "sales volume" in sales_doc.casefold()
        and "-1" in sales_doc
    )
    for index, row in enumerate(rows):
        locator = f"$.data[{index}]"
        if not isinstance(row, MappingABC):
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="variation",
                code="INVALID_RECORD_TYPE",
                message="Variation row must be an object.",
                locator=locator,
            )
            continue
        child_asin = normalized_asin(row.get("Asin"))
        raw_property = row.get("Property")
        item_index = row.get("ItemIndex")
        item_total = row.get("ItemTotal")
        if (
            child_asin is None
            or not isinstance(raw_property, str)
            or type(item_index) is not int
            or type(item_total) is not int
            or item_index < 1
            or item_total < 1
        ):
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="variation",
                code="INVALID_VARIATION_IDENTITY_OR_PRIMITIVE",
                message="Variation requires valid child ASIN, string Property, and positive integer indexes.",
                locator=locator,
                blocking_scope=BlockingScope.SUBJECT,
            )
            continue
        product = product_identity(session.context.marketplace, child_asin)
        source_identity = (
            f"{session.context.marketplace}:query-context:{query_asin}:{child_asin}:{item_index}"
        )
        _variation_property_facts(
            session,
            product=product,
            raw_property=raw_property,
            row_index=index,
            source_identity=source_identity,
        )
        sales_raw = row.get("SalesAmount")
        if not sales_semantics_confirmed:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="estimated_sales_volume",
                code="SALES_AMOUNT_SEMANTICS_UNCONFIRMED",
                message="SalesAmount is not mapped without returned documentation proving sales-volume semantics.",
                locator=f"{locator}.SalesAmount",
            )
        elif type(sales_raw) not in {int, float} or isinstance(sales_raw, bool):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="estimated_sales_volume",
                code="INVALID_SALES_AMOUNT_PRIMITIVE",
                message="SalesAmount must be a finite numeric primitive; booleans are rejected.",
                locator=f"{locator}.SalesAmount",
            )
        elif sales_raw == -1:
            session.add_metric(
                product=product,
                metric="estimated_sales_volume",
                value=absent_value(
                    PresenceStatus.UNKNOWN,
                    ValueType.NUMBER,
                    semantic_status=SemanticStatus.CONFIRMED,
                    unit=Unit(dimension="COUNT", unit_code="units", unit_system="PROVIDER"),
                ),
                source_field=f"data[{index}].SalesAmount",
                source_record_identity=source_identity,
                metric_semantic="Provider sentinel -1 means no recent captured page-published value, not zero sales",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                period_type=PeriodType.UNKNOWN,
                scope_type=ScopeType.CHILD_ASIN,
                result_status=ResultStatus.PARTIAL,
                provider_method="Most recently captured page-published child sales figure within 15 days",
                documentation_reference=f"{session.raw_evidence_id}#doc.sales_amount",
            )
            session.diagnostic(
                code="PROVIDER_SENTINEL_UNKNOWN",
                message="SalesAmount -1 is preserved as UNKNOWN, never negative sales or zero.",
                source_locator=f"{locator}.SalesAmount",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        elif sales_raw < 0:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="estimated_sales_volume",
                code="UNSUPPORTED_SALES_SENTINEL",
                message="Only documented -1 and non-negative SalesAmount values are supported.",
                locator=f"{locator}.SalesAmount",
            )
        else:
            session.add_metric(
                product=product,
                metric="estimated_sales_volume",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=sales_raw,
                    normalized_value=sales_raw,
                    value_type=ValueType.NUMBER,
                    unit=Unit(dimension="COUNT", unit_code="units", unit_system="PROVIDER"),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"data[{index}].SalesAmount",
                source_record_identity=source_identity,
                metric_semantic=(
                    "Variation sales volume from the most recently captured page-published figure within 15 days; "
                    "not revenue"
                ),
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                period_type=PeriodType.UNKNOWN,
                scope_type=ScopeType.CHILD_ASIN,
                provider_method="Most recently captured page-published child sales figure within 15 days",
                documentation_reference=f"{session.raw_evidence_id}#doc.sales_amount",
            )
        _report_fields(
            session,
            row,
            locator=locator,
            mapped={"Asin", "Property", "SalesAmount", "ItemIndex", "ItemTotal"},
        )
    _report_fields(
        session,
        doc,
        locator="$.doc",
        mapped={"asin", "property", "sales_amount", "item_index", "item_total"},
    )
    return session.finish()


def _asin_keywords(
    session: _AdapterSession,
    doc: Mapping[str, Any],
    rows: Any,
) -> AdaptationResult:
    query_asin = _request_asin(session)
    if query_asin is None:
        return _fail(
            session,
            "MISSING_REQUEST_IDENTITY",
            "sanitized_request ASIN is required for reverse relationship identity.",
            "context.sanitized_request.ASIN",
        )
    relationship_doc = doc.get("relationship")
    if not (
        isinstance(relationship_doc, str)
        and "last 30 days" in relationship_doc.casefold()
        and "first 3 pages" in relationship_doc.casefold()
    ):
        return _fail(
            session,
            "MISSING_RELATIONSHIP_CONTRACT",
            "ASINRequestKeyword requires audited first-3-pages and last-30-days documentation.",
            "$.doc.relationship",
        )

    product = product_identity(session.context.marketplace, query_asin)
    page_index = session.context.sanitized_request.get(
        "PageIndex", session.context.sanitized_request.get("pageIndex")
    )
    page_size = session.context.sanitized_request.get(
        "PageSize", session.context.sanitized_request.get("pageSize")
    )
    session.raw_evidence = replace(
        session.raw_evidence,
        response_status=("EMPTY" if not rows else "PARTIAL"),
        pagination={
            "request_page": page_index,
            "request_page_size": page_size,
            "returned_count": len(rows),
            "provider_total": None,
            "collection_status": "EXPLICIT_EMPTY" if not rows else "BOUNDED_PAGE_TOTAL_UNKNOWN",
        },
    )
    if not rows:
        session.add_query_execution(
            query_product=product,
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
            outcome=QueryExecutionOutcome.EXPLICIT_EMPTY,
            related_relationship_observation_ids=(),
            source_field="data",
            source_record_identity=product.product_id,
        )
        session.diagnostic(
            code="QUERY_RETURNED_EMPTY",
            message="A successful bounded ASINRequestKeyword query returned no rows; this is not zero demand.",
            source_locator="$.data",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        return session.finish()

    for index, row in enumerate(rows):
        locator = f"$.data[{index}]"
        if not isinstance(row, MappingABC):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="product_keyword_relationship",
                code="INVALID_RECORD_TYPE",
                message="ASINRequestKeyword row must be an object.",
                locator=locator,
            )
            continue
        keyword_record = row.get("Keyword")
        if not isinstance(keyword_record, MappingABC):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="product_keyword_relationship",
                code="INVALID_KEYWORD_RECORD",
                message="Keyword must be an object.",
                locator=f"{locator}.Keyword",
            )
            continue
        keyword_text = keyword_record.get("Keyword")
        if not isinstance(keyword_text, str) or not keyword_text.strip():
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="product_keyword_relationship",
                code="INVALID_KEYWORD_IDENTITY",
                message="Keyword.Keyword must be non-empty text.",
                locator=f"{locator}.Keyword.Keyword",
            )
            continue

        keyword = keyword_identity(session.context.marketplace, session.context.locale, keyword_text)
        source_identity = (
            f"{session.context.marketplace}:{query_asin}:{keyword.normalized_text}:"
            f"{RelationshipDirection.PRODUCT_TO_KEYWORD.value}"
        )
        session.add_relationship(
            product=product,
            keyword=keyword,
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
            relationship_type=RelationshipType.CANDIDATE_MEMBERSHIP,
            channel=Channel.UNKNOWN,
            value=value_envelope(
                presence_status=PresenceStatus.PRESENT,
                raw_value=True,
                normalized_value=True,
                value_type=ValueType.BOOLEAN,
                normalization_status=NormalizationStatus.NOT_APPLICABLE,
                semantic_status=SemanticStatus.CONFIRMED,
            ),
            source_field=f"data[{index}]",
            source_record_identity=source_identity,
            provider_semantic=(
                "ASIN gained exposure for this keyword within the first three search-result pages "
                "during the provider's last-30-day lookup window"
            ),
            evidence_type=EvidenceType.OBSERVED,
            query_result_status=ResultStatus.POPULATED,
            period_type=PeriodType.ROLLING_30_DAYS,
            discriminator=f"row:{index}:membership",
        )

        search_position = row.get("SearchPosition")
        search_position_date = row.get("SearchPositionDate")
        position_type = row.get("PositionType")
        if isinstance(search_position, str) and search_position.strip():
            rank = {
                "position": search_position,
                "position_date": search_position_date,
                "position_type": position_type,
            }
            session.add_relationship(
                product=product,
                keyword=keyword,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                relationship_type=RelationshipType.RANK,
                channel=Channel.ORGANIC,
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=rank,
                    normalized_value=rank,
                    value_type=ValueType.OBJECT,
                    normalization_status=NormalizationStatus.NOT_APPLICABLE,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"data[{index}].SearchPosition",
                source_record_identity=source_identity,
                provider_semantic="Provider-documented organic exposure position; timestamp timezone is not inferred",
                evidence_type=EvidenceType.OBSERVED,
                query_result_status=ResultStatus.POPULATED,
                rank=rank,
                period_type=PeriodType.ROLLING_30_DAYS,
                discriminator=f"row:{index}:organic-rank",
            )

        show_share_raw = row.get("ShowShare")
        show_share = strict_number(show_share_raw)
        if show_share is not None and 0 <= show_share <= 100:
            traffic = value_envelope(
                presence_status=PresenceStatus.PRESENT,
                raw_value=show_share_raw,
                normalized_value=show_share,
                value_type=ValueType.NUMBER,
                unit=Unit(dimension="RATIO", unit_code="percent", unit_system="PROVIDER"),
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=SemanticStatus.CONFIRMED,
            )
            session.add_relationship(
                product=product,
                keyword=keyword,
                direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
                relationship_type=RelationshipType.TRAFFIC,
                channel=Channel.UNKNOWN,
                value=traffic,
                traffic=traffic,
                source_field=f"data[{index}].ShowShare",
                source_record_identity=source_identity,
                provider_semantic="Traffic share contributed by this keyword within the ASIN reverse-lookup result",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                query_result_status=ResultStatus.POPULATED,
                period_type=PeriodType.ROLLING_30_DAYS,
                discriminator=f"row:{index}:show-share",
            )
        elif "ShowShare" in row:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="traffic",
                code="INVALID_SHOW_SHARE",
                message="ShowShare must be a finite percentage from 0 through 100.",
                locator=f"{locator}.ShowShare",
            )

        keyword_source = f"data[{index}].Keyword"
        search_volume_raw = keyword_record.get("SearchVolume")
        search_volume = strict_number(search_volume_raw)
        if search_volume is not None and search_volume >= 0:
            observation = session.add_keyword_metric(
                keyword=keyword,
                metric="search_volume",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=search_volume_raw,
                    normalized_value=search_volume,
                    value_type=ValueType.NUMBER,
                    unit=Unit(dimension="COUNT", unit_code="searches_per_30_days", unit_system="PROVIDER"),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                ),
                source_field=f"{keyword_source}.SearchVolume",
                source_record_identity=source_identity,
                metric_semantic="Provider 30-day search-volume estimate; derivation method is not documented",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                estimate_method_status=EstimateMethodStatus.PARTIALLY_DOCUMENTED,
                period_type=PeriodType.ROLLING_30_DAYS,
                result_status=ResultStatus.PARTIAL,
            )
            issue_id = _record_issue(
                session,
                subject=observation.subject,
                dimension="search_volume",
                code="SEARCH_VOLUME_METHOD_UNCONFIRMED",
                message="The 30-day window is documented, but the provider estimate method is unavailable.",
                locator=f"{locator}.Keyword.SearchVolume",
            )
            session.attach_issue((observation.observation_id,), issue_id)
        elif "SearchVolume" in keyword_record:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="search_volume",
                code="INVALID_SEARCH_VOLUME_PRIMITIVE",
                message="SearchVolume must be a finite non-negative number.",
                locator=f"{locator}.Keyword.SearchVolume",
            )

        cpc_raw = keyword_record.get("Cpc")
        cpc_range_raw = keyword_record.get("CpcRange")
        cpc = strict_number(cpc_raw)
        cpc_range = (
            tuple(strict_number(item) for item in cpc_range_raw)
            if isinstance(cpc_range_raw, (tuple, list)) and len(cpc_range_raw) == 2
            else ()
        )
        if (
            cpc is not None
            and cpc >= 0
            and len(cpc_range) == 2
            and all(item is not None and item >= 0 for item in cpc_range)
            and session.context.marketplace == "US"
            and session.context.currency == "USD"
        ):
            session.add_keyword_metric(
                keyword=keyword,
                metric="cpc",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=cpc_raw,
                    normalized_value=cpc / 100,
                    value_type=ValueType.NUMBER,
                    unit=Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217"),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"{keyword_source}.Cpc",
                source_record_identity=source_identity,
                metric_semantic="Provider CPC precise bid converted from documented US local minor units",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                estimate_method_status=EstimateMethodStatus.PARTIALLY_DOCUMENTED,
                range_value={
                    "minimum": cpc_range[0] / 100,
                    "maximum": cpc_range[1] / 100,
                    "currency": "USD",
                },
            )
        elif "Cpc" in keyword_record or "CpcRange" in keyword_record:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="cpc",
                code="INVALID_CPC_VALUE_RANGE_OR_CONTEXT",
                message="CPC requires non-negative values, a two-value range, US marketplace, and explicit USD context.",
                locator=f"{locator}.Keyword.Cpc",
            )

        _report_fields(
            session,
            keyword_record,
            locator=f"{locator}.Keyword",
            mapped={"Keyword", "SearchVolume", "Cpc", "CpcRange"},
            ignored={
                key: "Captured keyword enrichment is retained but outside the minimum SP-040A executable mapping."
                for key in keyword_record
                if key not in {"Keyword", "SearchVolume", "Cpc", "CpcRange"}
            },
        )
        _report_fields(
            session,
            row,
            locator=locator,
            mapped={"Keyword", "ShowShare", "SearchPosition", "SearchPositionDate", "PositionType"},
            ignored={
                "ShowType": "Display exposure label is retained; executable channel comes from documented position fields.",
                "AdPosition": "Sponsored-position mapping is deferred because the live page contained no ad evidence.",
                "AdPositionDate": "Sponsored-position mapping is deferred because the live page contained no ad evidence.",
            },
        )

    related_ids = tuple(
        item.observation_id
        for item in session.observations
        if isinstance(item, ProductKeywordRelationshipObservation)
        and item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
        and item.product == product
    )
    session.add_query_execution(
        query_product=product,
        direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
        outcome=(
            QueryExecutionOutcome.RESULTS_RETURNED
            if related_ids
            else QueryExecutionOutcome.OUTCOME_UNKNOWN
        ),
        related_relationship_observation_ids=related_ids,
        source_field="data",
        source_record_identity=product.product_id,
        quality_issue_ids=tuple(item.issue_id for item in session.issues),
    )
    _report_fields(
        session,
        doc,
        locator="$.doc",
        mapped={"relationship", "show_share", "search_position", "search_volume", "cpc"},
    )
    return session.finish()


def _optional_text_envelope(
    session: _AdapterSession,
    *,
    row: Mapping[str, Any],
    key: str,
    locator: str,
) -> Any | None:
    if key not in row:
        return absent_value(PresenceStatus.MISSING, ValueType.STRING)
    raw = row[key]
    if raw is None:
        return absent_value(PresenceStatus.EXPLICIT_NULL, ValueType.STRING)
    if isinstance(raw, str):
        return _string_value(raw)
    _record_issue(
        session,
        subject=_marketplace_subject(session),
        dimension="review",
        code="INVALID_REVIEW_PRIMITIVE",
        message=f"{key} must be a string, missing, or explicit null.",
        locator=locator,
    )
    return None


def _product_reviews(
    session: _AdapterSession,
    doc: Mapping[str, Any],
    rows: Any,
) -> AdaptationResult:
    asin = _request_asin(session)
    if asin is None:
        return _fail(
            session,
            "MISSING_REQUEST_IDENTITY",
            "sanitized_request.asin is required for review product identity.",
            "context.sanitized_request.asin",
        )
    product = product_identity(session.context.marketplace, asin)
    for index, row in enumerate(rows):
        locator = f"$.data[{index}]"
        if not isinstance(row, MappingABC):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="review",
                code="INVALID_REVIEW_RECORD",
                message="Review row must be an object.",
                locator=locator,
            )
            continue
        rating_raw = row.get("star_rating")
        date_raw = row.get("review_date")
        body_raw = row.get("content")
        if (
            strict_number(rating_raw) is None
            or not 1 <= float(rating_raw) <= 5
            or not isinstance(date_raw, str)
            or re.fullmatch(r"\d{8}", date_raw) is None
            or not isinstance(body_raw, str)
        ):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="review",
                code="UNSTABLE_OR_MALFORMED_REVIEW_IDENTITY",
                message=(
                    "Review requires finite 1-5 rating, yyyyMMdd date, and string body to establish a stable "
                    "source identity; no review observation emitted."
                ),
                locator=locator,
            )
            continue
        title = _optional_text_envelope(
            session,
            row=row,
            key="title",
            locator=f"{locator}.title",
        )
        variant = _optional_text_envelope(
            session,
            row=row,
            key="variant_attribute",
            locator=f"{locator}.variant_attribute",
        )
        if title is None or variant is None:
            continue
        provider_review_identity = deterministic_id(
            "sorftime-review-source",
            {
                "marketplace": session.context.marketplace,
                "asin": asin,
                "source_index": index,
                "review": row,
            },
        )
        normalized_date = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        rating = value_envelope(
            presence_status=PresenceStatus.PRESENT,
            raw_value=rating_raw,
            normalized_value=float(rating_raw),
            value_type=ValueType.NUMBER,
            unit=Unit(dimension="RATING", unit_code="stars_5", unit_system="DOMAIN"),
            normalization_status=NormalizationStatus.NORMALIZED,
            semantic_status=SemanticStatus.CONFIRMED,
        )
        body = _string_value(body_raw)
        review_date = value_envelope(
            presence_status=PresenceStatus.PRESENT,
            raw_value=date_raw,
            normalized_value=normalized_date,
            value_type=ValueType.DATE,
            normalization_status=NormalizationStatus.NORMALIZED,
            semantic_status=SemanticStatus.CONFIRMED,
        )
        helpful_votes = absent_value(PresenceStatus.MISSING, ValueType.INTEGER)
        session.add_review(
            product=product,
            provider_review_identity=provider_review_identity,
            rating=rating,
            title=title,
            body=body,
            review_date=review_date,
            variant=variant,
            helpful_votes=helpful_votes,
            source_field=f"data[{index}]",
            source_record_identity=f"{session.context.marketplace}:{asin}:{provider_review_identity}",
            observed_at=None,
        )
        _report_fields(
            session,
            row,
            locator=locator,
            mapped={"star_rating", "review_date", "title", "content", "variant_attribute"},
        )
    session.diagnostic(
        code="HELPFUL_VOTES_MISSING",
        message="Provider review payload does not supply helpful votes; observations use MISSING, never zero.",
        source_locator="$.data[*].helpful_votes",
        disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        affects_status=False,
    )
    _report_fields(
        session,
        doc,
        locator="$.doc",
        mapped={"variant_attribute", "review_date", "star_rating", "title", "content"},
    )
    return session.finish()


class SorftimeAdapterV0_1:
    """Offline audited Sorftime adapter with no provider transport."""

    provider = "sorftime"
    adapter_version = "0.1.1"
    supported_payload_kinds = tuple(_MAPPING_SPECIFICATIONS)
    mapping_specifications = _MAPPING_SPECIFICATIONS

    def adapt(self, payload: Any, context: AdaptationContext) -> AdaptationResult:
        prepared = _prepare_session(
            provider=self.provider,
            adapter_version=self.adapter_version,
            mapping_specifications=self.mapping_specifications,
            payload=payload,
            context=context,
        )
        if isinstance(prepared, AdaptationResult):
            return prepared
        envelope = _sorftime_envelope(
            prepared,
            data_must_be_list=context.payload_kind in {
                "product_variations",
                "product_reviews",
                "asin_keywords",
            },
        )
        if isinstance(envelope, AdaptationResult):
            return envelope
        doc, data = envelope
        if context.payload_kind == "product_detail":
            return _product_detail(prepared, doc, data)
        if context.payload_kind == "product_variations":
            return _product_variations(prepared, doc, data)
        if context.payload_kind == "asin_keywords":
            return _asin_keywords(prepared, doc, data)
        return _product_reviews(prepared, doc, data)


__all__ = ("SorftimeAdapterV0_1",)
