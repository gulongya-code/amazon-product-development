"""Audited offline XiYou mapping slice V0.1.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import replace
from typing import Any, Mapping

from amazon_product_intelligence.contracts import (
    BlockingScope,
    Channel,
    ContractValidationError,
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
        specification_id=f"xiyou.{payload_kind}",
        version=version,
        mapping_version=mapping_version,
        provider="xiyou",
        payload_kind=payload_kind,
        source_tool=source_tool,
    )


_MAPPING_SPECIFICATIONS: Mapping[str, MappingSpecification] = {
    "asin_info": _spec("asin_info", "get_asin_info", "xiyou_product_info_mapping_v1"),
    "asin_variations": _spec(
        "asin_variations",
        "get_asin_variations",
        "xiyou_variations_mapping_v1_1",
        version="0.1.1",
    ),
    "asin_orders_last_30_days": _spec(
        "asin_orders_last_30_days",
        "get_asin_orders_last_30_days",
        "xiyou_orders_30d_mapping_v1",
    ),
    "asin_bsr_trends": _spec(
        "asin_bsr_trends", "get_asin_bsr_trends", "xiyou_bsr_trends_mapping_v1"
    ),
    "keyword_info": _spec("keyword_info", "get_keyword_info", "xiyou_keyword_info_mapping_v1"),
    "keyword_asin_analysis": _spec(
        "keyword_asin_analysis",
        "get_keyword_asin_analysis",
        "xiyou_keyword_to_asin_mapping_v1_1",
        version="0.1.1",
    ),
    "asin_keywords": _spec(
        "asin_keywords",
        "get_asin_keywords",
        "xiyou_asin_to_keyword_mapping_v1_1",
        version="0.1.1",
    ),
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


def _xiyou_data(session: _AdapterSession) -> Mapping[str, Any] | AdaptationResult:
    payload = session.payload
    status = payload.get("status")
    if type(status) is not int or status != 200:
        return _fail(session, "UNSUPPORTED_PROVIDER_STATUS", "XiYou status must be integer 200", "$.status")
    data = payload.get("data")
    if not isinstance(data, MappingABC):
        return _fail(session, "MALFORMED_PROVIDER_ENVELOPE", "XiYou data must be an object", "$.data")
    _report_fields(
        session,
        payload,
        locator="$",
        mapped={"data", "status"},
        ignored={"cost_credits": "Provider billing metadata is retained only in raw evidence."},
    )
    return data


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


def _string_value(raw: str) -> Any:
    return value_envelope(
        presence_status=PresenceStatus.PRESENT,
        raw_value=raw,
        normalized_value=raw,
        value_type=ValueType.STRING,
        normalization_status=NormalizationStatus.NOT_APPLICABLE,
        semantic_status=SemanticStatus.CONFIRMED,
    )


def _product_info(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    entities = data.get("entities")
    if not isinstance(entities, (tuple, list)):
        return _fail(session, "MALFORMED_PROVIDER_ENVELOPE", "data.entities must be an array", "$.data.entities")
    _report_fields(session, data, locator="$.data", mapped={"entities"})
    for index, record in enumerate(entities):
        locator = f"$.data.entities[{index}]"
        if not isinstance(record, MappingABC):
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="product_record",
                code="INVALID_RECORD_TYPE",
                message="Product record must be an object; record omitted.",
                locator=locator,
            )
            continue
        asin = normalized_asin(record.get("asin"))
        country = record.get("country")
        if asin is None or country != session.context.marketplace:
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="product_identity",
                code="INVALID_PRODUCT_IDENTITY",
                message="Record requires a valid ASIN and matching marketplace country.",
                locator=locator,
                blocking_scope=BlockingScope.SUBJECT,
            )
            continue
        product = product_identity(session.context.marketplace, asin)
        subject = product_subject(product)
        source_identity = f"{session.context.marketplace}:{asin}"

        title = record.get("title")
        if isinstance(title, str):
            session.add_product_fact(
                product=product,
                dimension="title",
                fact_group=FactGroup.IDENTITY_RELATED,
                value=_string_value(title),
                source_field=f"data.entities[{index}].title",
                source_record_identity=source_identity,
                provider_semantic="Displayed product title",
            )
        elif "title" in record:
            _record_issue(
                session,
                subject=subject,
                dimension="title",
                code="INVALID_PRIMITIVE_TYPE",
                message="title must be a string; no title observation emitted.",
                locator=f"{locator}.title",
            )

        price_raw = record.get("price")
        if "price" in record and price_raw is not None:
            price = strict_number(price_raw, allow_numeric_string=True)
            currency = record.get("currency")
            if price is None or not isinstance(currency, str) or len(currency.strip()) != 3:
                _record_issue(
                    session,
                    subject=subject,
                    dimension="price",
                    code="INVALID_PRICE_PRIMITIVE_OR_UNIT",
                    message="price requires an approved numeric primitive/string and three-letter currency.",
                    locator=f"{locator}.price",
                )
            else:
                currency = currency.strip().upper()
                session.add_metric(
                    product=product,
                    metric="price",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=price_raw,
                        normalized_value=price,
                        value_type=ValueType.NUMBER,
                        unit=Unit(dimension="CURRENCY", unit_code=currency, unit_system="ISO_4217"),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field=f"data.entities[{index}].price",
                    source_record_identity=source_identity,
                    metric_semantic="Displayed product selling price",
                    evidence_type=EvidenceType.OBSERVED,
                    currency=currency,
                    period_type=PeriodType.INSTANT,
                )

        stars_raw = record.get("stars")
        if "stars" in record and stars_raw is not None:
            stars = strict_number(stars_raw, allow_numeric_string=True)
            if stars is None or not 0 <= float(stars) <= 5:
                _record_issue(
                    session,
                    subject=subject,
                    dimension="rating",
                    code="INVALID_RATING_PRIMITIVE",
                    message="stars must be a finite number on the approved five-star scale.",
                    locator=f"{locator}.stars",
                )
            else:
                session.add_metric(
                    product=product,
                    metric="rating",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=stars_raw,
                        normalized_value=stars,
                        value_type=ValueType.NUMBER,
                        unit=Unit(dimension="RATING", unit_code="stars_5", unit_system="DOMAIN"),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field=f"data.entities[{index}].stars",
                    source_record_identity=source_identity,
                    metric_semantic="Displayed product rating on a five-star scale",
                    evidence_type=EvidenceType.OBSERVED,
                    period_type=PeriodType.INSTANT,
                )

        ratings_raw = record.get("ratings")
        if "ratings" in record and ratings_raw is not None:
            if type(ratings_raw) is not int or ratings_raw < 0:
                _record_issue(
                    session,
                    subject=subject,
                    dimension="review_count",
                    code="INVALID_REVIEW_COUNT_PRIMITIVE",
                    message="ratings must be a non-negative integer; booleans are rejected.",
                    locator=f"{locator}.ratings",
                )
            else:
                session.add_metric(
                    product=product,
                    metric="review_count",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=ratings_raw,
                        normalized_value=ratings_raw,
                        value_type=ValueType.INTEGER,
                        unit=Unit(dimension="COUNT", unit_code="reviews", unit_system="DOMAIN"),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field=f"data.entities[{index}].ratings",
                    source_record_identity=source_identity,
                    metric_semantic="Displayed rating/review count",
                    evidence_type=EvidenceType.OBSERVED,
                    period_type=PeriodType.INSTANT,
                )

        _report_fields(
            session,
            record,
            locator=locator,
            mapped={"asin", "country", "title", "price", "currency", "stars", "ratings"},
            ignored={
                "amazonUrl": "Listing URL is retained in raw evidence; URL observation is out of scope.",
                "bigPicUrl": "Image processing is out of scope for V0.1.",
                "smallPicUrl": "Image processing is out of scope for V0.1.",
                "picUrl": "Image processing is out of scope for V0.1.",
            },
        )
    return session.finish()


def _variations(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    asin = normalized_asin(data.get("asin"))
    country = data.get("country")
    if asin is None or country != session.context.marketplace:
        return _fail(
            session,
            "INVALID_PRODUCT_IDENTITY",
            "Variation payload requires valid asin and matching country.",
            "$.data",
        )
    query_product = product_identity(session.context.marketplace, asin)
    source_identity = f"{session.context.marketplace}:{asin}"
    parent_raw = data.get("parentAsin")
    parent: str | None = None
    if isinstance(parent_raw, str) and parent_raw:
        parent = normalized_asin(parent_raw)
        if parent is None:
            _record_issue(
                session,
                subject=product_subject(query_product),
                dimension="parent_product_relationship",
                code="INVALID_PARENT_ASIN",
                message="parentAsin is not a valid ASIN.",
                locator="$.data.parentAsin",
            )
    elif parent_raw == "":
        session.diagnostic(
            code="EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED",
            message="Empty parentAsin is retained and is not treated as proof of a standalone listing.",
            source_locator="$.data.parentAsin",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
    elif parent_raw is None:
        session.diagnostic(
            code=(
                "NULL_VARIATION_PARENT_UNCONFIRMED"
                if "parentAsin" in data
                else "MISSING_VARIATION_PARENT_UNCONFIRMED"
            ),
            message="No explicit parent ASIN is available, so family members are not converted to directed edges.",
            source_locator="$.data.parentAsin",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
    elif parent_raw is not None:
        _record_issue(
            session,
            subject=product_subject(query_product),
            dimension="parent_product_relationship",
            code="INVALID_PRIMITIVE_TYPE",
            message="parentAsin must be a string.",
            locator="$.data.parentAsin",
        )

    children = data.get("childAsins")
    confirmed_children: dict[str, str] = {}
    if not isinstance(children, (tuple, list)):
        _record_issue(
            session,
            subject=product_subject(query_product),
            dimension="child_product_relationship",
            code="INVALID_PRIMITIVE_TYPE",
            message="childAsins must be an array.",
            locator="$.data.childAsins",
        )
    else:
        if not children:
            session.diagnostic(
                code="EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED",
                message="Empty childAsins is retained and is not converted to a zero variation fact.",
                source_locator="$.data.childAsins",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        for index, child_raw in enumerate(children):
            child = normalized_asin(child_raw)
            if child is None:
                _record_issue(
                    session,
                    subject=product_subject(query_product),
                    dimension="child_product_relationship",
                    code="INVALID_CHILD_ASIN",
                    message="Child relationship omitted because the value is not a valid ASIN.",
                    locator=f"$.data.childAsins[{index}]",
                )
                continue
            if child in confirmed_children:
                session.diagnostic(
                    code="DUPLICATE_VARIATION_MEMBER_NOT_PUBLISHED",
                    message="A duplicate childAsins member remains in raw evidence and is not published twice.",
                    source_locator=f"$.data.childAsins[{index}]",
                    disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
                )
                continue
            confirmed_children[child] = f"data.childAsins[{index}]"

    if parent is not None:
        if asin not in confirmed_children:
            session.diagnostic(
                code="QUERY_AS_CHILD_NOT_CONFIRMED",
                message=(
                    "The query ASIN is not present in childAsins; parentAsin alone does not authorize "
                    "publishing the query ASIN as a child."
                ),
                source_locator="$.data.childAsins",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        parent_product = product_identity(session.context.marketplace, parent)
        for child, source_field in confirmed_children.items():
            if child == parent:
                session.diagnostic(
                    code="VARIATION_SELF_MEMBER_NOT_PUBLISHED",
                    message="A parent appearing in its own member set remains raw evidence and is not a self-loop.",
                    source_locator=f"$.{source_field}",
                    disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
                )
                continue
            session.add_product_fact(
                product=parent_product,
                dimension="child_product_relationship",
                fact_group=FactGroup.VARIATION,
                value=_string_value(child),
                source_field=source_field,
                source_record_identity=source_identity,
                provider_semantic="Provider-reported child ASIN under explicit parentAsin",
                scope_type=ScopeType.PARENT_ASIN,
                discriminator=f"explicit-parent-child:{parent}:{child}",
            )
    if "lastUpdatedTime" in data:
        session.diagnostic(
            code="OBSERVATION_TIMEZONE_UNCONFIRMED",
            message="lastUpdatedTime lacks a timezone and is retained only in raw evidence.",
            source_locator="$.data.lastUpdatedTime",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
        )
    _report_fields(
        session,
        data,
        locator="$.data",
        mapped={"asin", "country", "parentAsin", "childAsins", "lastUpdatedTime"},
    )
    return session.finish()


def _orders(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    country = data.get("country")
    entities = data.get("entities")
    if country != session.context.marketplace or not isinstance(entities, (tuple, list)):
        return _fail(
            session,
            "MALFORMED_PROVIDER_ENVELOPE",
            "Orders payload requires matching country and an entities array.",
            "$.data",
        )
    for index, record in enumerate(entities):
        locator = f"$.data.entities[{index}]"
        if not isinstance(record, MappingABC):
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="orders",
                code="INVALID_RECORD_TYPE",
                message="Orders record must be an object.",
                locator=locator,
            )
            continue
        asin = normalized_asin(record.get("asin"))
        orders = record.get("orders")
        if asin is None:
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="orders",
                code="INVALID_PRODUCT_IDENTITY",
                message="Orders record has no valid ASIN.",
                locator=locator,
            )
            continue
        product = product_identity(session.context.marketplace, asin)
        if type(orders) is not int or orders < 0:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="orders",
                code="INVALID_ORDERS_PRIMITIVE",
                message="orders must be a non-negative integer; booleans are rejected.",
                locator=f"{locator}.orders",
            )
            continue
        observation = session.add_metric(
            product=product,
            metric="orders",
            value=value_envelope(
                presence_status=PresenceStatus.PRESENT,
                raw_value=orders,
                normalized_value=orders,
                value_type=ValueType.INTEGER,
                unit=Unit(dimension="COUNT", unit_code="orders", unit_system="PROVIDER"),
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            ),
            source_field=f"data.entities[{index}].orders",
            source_record_identity=f"{session.context.marketplace}:{asin}",
            metric_semantic=(
                "Provider recent-30-day orders metric; exact boundaries, method, and parent/child grain "
                "are unconfirmed"
            ),
            evidence_type=EvidenceType.PROVIDER_ESTIMATE,
            period_type=PeriodType.ROLLING_30_DAYS,
            scope_type=ScopeType.ASIN,
            scope_status=ScopeStatus.SCOPE_UNCONFIRMED,
            result_status=ResultStatus.PARTIAL,
        )
        issue_id = _record_issue(
            session,
            subject=product_subject(product),
            dimension="orders",
            code="ORDERS_METHOD_AND_SCOPE_UNCONFIRMED",
            message="Exact window boundaries, estimate method, and parent/child scope are not documented.",
            locator=f"{locator}.orders",
        )
        session.attach_issue((observation.observation_id,), issue_id)
        _report_fields(session, record, locator=locator, mapped={"asin", "orders"})
    _report_fields(session, data, locator="$.data", mapped={"country", "entities"})
    return session.finish()


def _bsr(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    asin = normalized_asin(data.get("asin"))
    if asin is None or data.get("country") != session.context.marketplace:
        return _fail(session, "INVALID_PRODUCT_IDENTITY", "BSR payload identity is invalid.", "$.data")
    product = product_identity(session.context.marketplace, asin)
    categories: dict[str, Mapping[str, Any]] = {}
    category_tree = data.get("categoryTree")
    if isinstance(category_tree, (tuple, list)):
        for item in category_tree:
            if isinstance(item, MappingABC) and isinstance(item.get("categoryId"), str):
                categories[item["categoryId"]] = item
    else:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="bsr",
            code="INVALID_CATEGORY_TREE",
            message="categoryTree must be an array.",
            locator="$.data.categoryTree",
        )
    trends = data.get("trends")
    if not isinstance(trends, (tuple, list)):
        return _fail(session, "MALFORMED_PROVIDER_ENVELOPE", "BSR trends must be an array.", "$.data.trends")
    for row_index, row in enumerate(trends):
        if not isinstance(row, MappingABC):
            continue
        source_date = row.get("date")
        values = row.get("values")
        if not isinstance(source_date, str) or not isinstance(values, (tuple, list)):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="bsr",
                code="INVALID_BSR_ROW",
                message="BSR row requires a date string and values array.",
                locator=f"$.data.trends[{row_index}]",
            )
            continue
        for value_index, item in enumerate(values):
            locator = f"$.data.trends[{row_index}].values[{value_index}]"
            if not isinstance(item, MappingABC):
                continue
            category_id = item.get("categoryId")
            rank = item.get("rank")
            if not isinstance(category_id, str) or type(rank) is not int or rank < 0:
                _record_issue(
                    session,
                    subject=product_subject(product),
                    dimension="bsr",
                    code="INVALID_BSR_PRIMITIVE",
                    message="BSR requires string categoryId and non-negative integer rank.",
                    locator=locator,
                )
                continue
            category = categories.get(category_id, {})
            session.add_metric(
                product=product,
                metric="bsr",
                value=value_envelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=rank,
                    normalized_value=rank,
                    value_type=ValueType.INTEGER,
                    unit=Unit(dimension="RANK", unit_code="bsr", unit_system="AMAZON"),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                ),
                source_field=f"data.trends[{row_index}].values[{value_index}].rank",
                source_record_identity=f"{session.context.marketplace}:{asin}:{source_date}:{category_id}",
                metric_semantic=f"Provider-reported daily BSR for source date {source_date}",
                evidence_type=EvidenceType.OBSERVED,
                rank_context={
                    "category_id": category_id,
                    "category_name": category.get("name"),
                    "root": category.get("root"),
                    "source_date": source_date,
                    "date_precision": "CALENDAR_DATE",
                },
                period_type=PeriodType.CALENDAR_DAY,
                discriminator=f"{source_date}:{category_id}",
            )
    if "dateRangeNotice" in data:
        session.diagnostic(
            code="SOURCE_FIELD_INTENTIONALLY_IGNORED",
            message="dateRangeNotice is retained as raw provider documentation metadata.",
            source_locator="$.data.dateRangeNotice",
            disposition=MappingDisposition.DOCUMENTATION_ONLY,
            affects_status=False,
        )
    _report_fields(
        session,
        data,
        locator="$.data",
        mapped={"asin", "country", "categoryTree", "trends", "dateRangeNotice"},
    )
    return session.finish()


def _null_keyword_metric(
    session: _AdapterSession,
    *,
    keyword: Any,
    metric: str,
    source_field: str,
    source_identity: str,
    evidence_type: EvidenceType,
    semantic_status: SemanticStatus,
) -> None:
    session.add_keyword_metric(
        keyword=keyword,
        metric=metric,
        value=absent_value(
            PresenceStatus.EXPLICIT_NULL,
            ValueType.NUMBER,
            semantic_status=semantic_status,
        ),
        source_field=source_field,
        source_record_identity=source_identity,
        metric_semantic=f"Provider explicitly returned null for {metric}",
        evidence_type=evidence_type,
        estimate_method_status=EstimateMethodStatus.UNKNOWN,
        period_type=PeriodType.UNKNOWN,
        result_status=ResultStatus.PARTIAL,
    )


def _keyword_info(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    rows = data.get("list")
    if not isinstance(rows, (tuple, list)):
        return _fail(session, "MALFORMED_PROVIDER_ENVELOPE", "data.list must be an array.", "$.data.list")
    for index, row in enumerate(rows):
        locator = f"$.data.list[{index}]"
        if not isinstance(row, MappingABC):
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="keyword",
                code="INVALID_RECORD_TYPE",
                message="Keyword record must be an object.",
                locator=locator,
            )
            continue
        search_term = row.get("searchTerm")
        if not isinstance(search_term, str) or not search_term.strip():
            _record_issue(
                session,
                subject=_marketplace_subject(session),
                dimension="keyword",
                code="INVALID_KEYWORD_IDENTITY",
                message="searchTerm must be a non-empty string.",
                locator=f"{locator}.searchTerm",
            )
            continue
        keyword = keyword_identity(session.context.marketplace, session.context.locale, search_term)
        source_identity = f"{session.context.marketplace}:{keyword.normalized_text}"
        aba = row.get("abaReport")
        if "abaReport" not in row:
            session.diagnostic(
                code="SOURCE_FIELD_MISSING",
                message="abaReport is absent; missing is not explicit null or zero.",
                source_locator=f"{locator}.abaReport",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        elif aba is None:
            _null_keyword_metric(
                session,
                keyword=keyword,
                metric="search_volume",
                source_field=f"data.list[{index}].abaReport",
                source_identity=source_identity,
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            )
            _null_keyword_metric(
                session,
                keyword=keyword,
                metric="aba_search_frequency_rank",
                source_field=f"data.list[{index}].abaReport",
                source_identity=source_identity,
                evidence_type=EvidenceType.OBSERVED,
                semantic_status=SemanticStatus.CONFIRMED,
            )
        elif isinstance(aba, MappingABC):
            start = aba.get("reportFromDate")
            end = aba.get("reportToDate")
            period_note = (
                f"Provider report window {start} through {end}; date-only boundaries and timezone remain in raw evidence"
                if isinstance(start, str) and isinstance(end, str)
                else "Provider weekly report window boundaries are incomplete"
            )
            volume_raw = aba.get("weeklySearchVolume")
            volume = strict_number(volume_raw)
            if volume is None:
                _record_issue(
                    session,
                    subject=SubjectRef(
                        subject_type=SubjectType.KEYWORD,
                        subject_id=keyword.keyword_id,
                        marketplace=keyword.marketplace,
                    ),
                    dimension="search_volume",
                    code="INVALID_SEARCH_VOLUME_PRIMITIVE",
                    message="weeklySearchVolume must be a finite number; booleans are rejected.",
                    locator=f"{locator}.abaReport.weeklySearchVolume",
                )
            else:
                observation = session.add_keyword_metric(
                    keyword=keyword,
                    metric="search_volume",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=volume_raw,
                        normalized_value=volume,
                        value_type=ValueType.NUMBER,
                        unit=Unit(dimension="COUNT", unit_code="searches_per_week", unit_system="PROVIDER"),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                    ),
                    source_field=f"data.list[{index}].abaReport.weeklySearchVolume",
                    source_record_identity=source_identity,
                    metric_semantic=f"Weekly search volume; provider derivation is unconfirmed. {period_note}",
                    evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                    estimate_method_status=EstimateMethodStatus.UNKNOWN,
                    period_type=PeriodType.CALENDAR_WEEK,
                    result_status=ResultStatus.PARTIAL,
                )
                issue_id = _record_issue(
                    session,
                    subject=observation.subject,
                    dimension="search_volume",
                    code="SEARCH_VOLUME_METHOD_UNCONFIRMED",
                    message="The weekly window is known but the provider derivation/estimate method is not.",
                    locator=f"{locator}.abaReport.weeklySearchVolume",
                )
                session.attach_issue((observation.observation_id,), issue_id)
            rank_raw = aba.get("searchFrequencyRank")
            if type(rank_raw) is int and rank_raw >= 0:
                session.add_keyword_metric(
                    keyword=keyword,
                    metric="aba_search_frequency_rank",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=rank_raw,
                        normalized_value=rank_raw,
                        value_type=ValueType.INTEGER,
                        unit=Unit(dimension="RANK", unit_code="aba_sfr", unit_system="AMAZON"),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field=f"data.list[{index}].abaReport.searchFrequencyRank",
                    source_record_identity=source_identity,
                    metric_semantic=f"Provider-reported ABA search frequency rank. {period_note}",
                    evidence_type=EvidenceType.OBSERVED,
                    estimate_method_status=EstimateMethodStatus.DOCUMENTED,
                    period_type=PeriodType.CALENDAR_WEEK,
                )
            else:
                _record_issue(
                    session,
                    subject=SubjectRef(
                        subject_type=SubjectType.KEYWORD,
                        subject_id=keyword.keyword_id,
                        marketplace=keyword.marketplace,
                    ),
                    dimension="aba_search_frequency_rank",
                    code="INVALID_ABA_RANK_PRIMITIVE",
                    message="searchFrequencyRank must be a non-negative integer.",
                    locator=f"{locator}.abaReport.searchFrequencyRank",
                )
            _report_fields(
                session,
                aba,
                locator=f"{locator}.abaReport",
                mapped={"reportFromDate", "reportToDate", "weeklySearchVolume", "searchFrequencyRank"},
                ignored={"topAsins": "ABA top-ASIN shares are outside this audited mapping slice."},
            )
        elif aba is not None:
            _record_issue(
                session,
                subject=SubjectRef(
                    subject_type=SubjectType.KEYWORD,
                    subject_id=keyword.keyword_id,
                    marketplace=keyword.marketplace,
                ),
                dimension="search_volume",
                code="INVALID_ABA_REPORT_TYPE",
                message="abaReport must be an object or explicit null.",
                locator=f"{locator}.abaReport",
            )

        difficulty_raw = row.get("competitiveDifficulty")
        if "competitiveDifficulty" not in row:
            session.diagnostic(
                code="SOURCE_FIELD_MISSING",
                message="competitiveDifficulty is absent; missing is not explicit null or zero.",
                source_locator=f"{locator}.competitiveDifficulty",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        elif difficulty_raw is None:
            _null_keyword_metric(
                session,
                keyword=keyword,
                metric="competition_difficulty",
                source_field=f"data.list[{index}].competitiveDifficulty",
                source_identity=source_identity,
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            )
        elif "competitiveDifficulty" in row:
            difficulty = strict_number(difficulty_raw)
            if difficulty is None:
                _record_issue(
                    session,
                    subject=SubjectRef(
                        subject_type=SubjectType.KEYWORD,
                        subject_id=keyword.keyword_id,
                        marketplace=keyword.marketplace,
                    ),
                    dimension="competition_difficulty",
                    code="INVALID_DIFFICULTY_PRIMITIVE",
                    message="competitiveDifficulty must be a finite number.",
                    locator=f"{locator}.competitiveDifficulty",
                )
            else:
                observation = session.add_keyword_metric(
                    keyword=keyword,
                    metric="competition_difficulty",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=difficulty_raw,
                        normalized_value=difficulty,
                        value_type=ValueType.NUMBER,
                        unit=Unit(dimension="SCORE", unit_code="xiyou_difficulty", unit_system="PROVIDER"),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                    ),
                    source_field=f"data.list[{index}].competitiveDifficulty",
                    source_record_identity=source_identity,
                    metric_semantic="Provider competition/difficulty score; scale semantics are unconfirmed",
                    evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                    estimate_method_status=EstimateMethodStatus.UNKNOWN,
                    result_status=ResultStatus.PARTIAL,
                )
                issue_id = _record_issue(
                    session,
                    subject=observation.subject,
                    dimension="competition_difficulty",
                    code="DIFFICULTY_SCALE_UNCONFIRMED",
                    message="Provider scale and method are not documented.",
                    locator=f"{locator}.competitiveDifficulty",
                )
                session.attach_issue((observation.observation_id,), issue_id)

        cpc = row.get("costPerClick")
        if "costPerClick" not in row:
            session.diagnostic(
                code="SOURCE_FIELD_MISSING",
                message="costPerClick is absent; missing is not explicit null or zero.",
                source_locator=f"{locator}.costPerClick",
                disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            )
        elif cpc is None:
            _null_keyword_metric(
                session,
                keyword=keyword,
                metric="cpc",
                source_field=f"data.list[{index}].costPerClick",
                source_identity=source_identity,
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                semantic_status=SemanticStatus.CONFIRMED,
            )
        elif isinstance(cpc, MappingABC):
            value_raw = cpc.get("value")
            minimum_raw = cpc.get("minSuggestedBid")
            maximum_raw = cpc.get("maxSuggestedBid")
            numeric = strict_number(value_raw, allow_numeric_string=True)
            minimum = strict_number(minimum_raw, allow_numeric_string=True)
            maximum = strict_number(maximum_raw, allow_numeric_string=True)
            if numeric is None or minimum is None or maximum is None or session.context.currency is None:
                _record_issue(
                    session,
                    subject=SubjectRef(
                        subject_type=SubjectType.KEYWORD,
                        subject_id=keyword.keyword_id,
                        marketplace=keyword.marketplace,
                    ),
                    dimension="cpc",
                    code="INVALID_CPC_VALUE_OR_CURRENCY",
                    message="CPC requires approved numeric strings and an explicit context currency.",
                    locator=f"{locator}.costPerClick",
                )
            else:
                session.add_keyword_metric(
                    keyword=keyword,
                    metric="cpc",
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=value_raw,
                        normalized_value=numeric,
                        value_type=ValueType.NUMBER,
                        unit=Unit(
                            dimension="CURRENCY",
                            unit_code=session.context.currency,
                            unit_system="ISO_4217",
                        ),
                        normalization_status=NormalizationStatus.NORMALIZED,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field=f"data.list[{index}].costPerClick.value",
                    source_record_identity=source_identity,
                    metric_semantic="Provider CPC/suggested-bid estimate",
                    evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                    estimate_method_status=EstimateMethodStatus.PARTIALLY_DOCUMENTED,
                    range_value={
                        "minimum": minimum,
                        "maximum": maximum,
                        "currency": session.context.currency,
                    },
                )
            _report_fields(
                session,
                cpc,
                locator=f"{locator}.costPerClick",
                mapped={"value", "minSuggestedBid", "maxSuggestedBid"},
            )
        elif "costPerClick" in row:
            _record_issue(
                session,
                subject=SubjectRef(
                    subject_type=SubjectType.KEYWORD,
                    subject_id=keyword.keyword_id,
                    marketplace=keyword.marketplace,
                ),
                dimension="cpc",
                code="INVALID_CPC_TYPE",
                message="costPerClick must be an object or explicit null.",
                locator=f"{locator}.costPerClick",
            )

        _report_fields(
            session,
            row,
            locator=locator,
            mapped={"searchTerm", "abaReport", "competitiveDifficulty", "costPerClick"},
            ignored={
                "clickConversionRate": "Conversion-rate analysis is out of scope.",
                "organicRotation": "Provider rotation semantics are unconfirmed and out of scope.",
            },
        )
    _report_fields(
        session,
        data,
        locator="$.data",
        mapped={"list"},
        ignored={"total": "Row count is retained in raw evidence and is not a market-size metric."},
    )
    return session.finish()


def _request_text(session: _AdapterSession, key: str) -> str | None:
    value = session.context.sanitized_request.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _map_relationship_row(
    session: _AdapterSession,
    *,
    row: Mapping[str, Any],
    row_index: int,
    product: Any,
    keyword: Any,
    direction: RelationshipDirection,
    locator: str,
) -> None:
    source_identity = (
        f"{session.context.marketplace}:{product.asin}:{keyword.normalized_text}:{direction.value}"
    )
    membership = session.add_relationship(
        product=product,
        keyword=keyword,
        direction=direction,
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
        source_field=locator,
        source_record_identity=source_identity,
        provider_semantic="Provider returned this product-keyword pair in the requested direction",
        evidence_type=EvidenceType.OBSERVED,
        query_result_status=ResultStatus.POPULATED,
        discriminator=f"row:{row_index}:membership",
    )
    del membership

    ranks = row.get("ranks")
    if ranks is not None and not isinstance(ranks, (tuple, list)):
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="product_keyword_rank",
            code="INVALID_RANKS_TYPE",
            message="ranks must be an array.",
            locator=f"{locator}.ranks",
        )
    elif isinstance(ranks, (tuple, list)):
        for rank_index, rank in enumerate(ranks):
            rank_locator = f"{locator}.ranks[{rank_index}]"
            if not isinstance(rank, MappingABC):
                _record_issue(
                    session,
                    subject=product_subject(product),
                    dimension="product_keyword_rank",
                    code="INVALID_RANK_RECORD",
                    message="Rank record must be an object.",
                    locator=rank_locator,
                )
                continue
            position = rank.get("position")
            channel = {"or": Channel.ORGANIC, "sb": Channel.SPONSORED}.get(position)
            if channel is None:
                session.diagnostic(
                    code="RANK_POSITION_CODE_UNCONFIRMED",
                    message="Only audited or/sb position codes are executable; raw rank is retained.",
                    source_locator=f"{rank_locator}.position",
                    disposition=MappingDisposition.SEMANTICS_UNCONFIRMED,
                )
                continue
            observed_at = rank.get("rankTime") if isinstance(rank.get("rankTime"), str) else None
            try:
                observation = session.add_relationship(
                    product=product,
                    keyword=keyword,
                    direction=direction,
                    relationship_type=RelationshipType.RANK,
                    channel=channel,
                    value=value_envelope(
                        presence_status=PresenceStatus.PRESENT,
                        raw_value=dict(rank),
                        normalized_value=dict(rank),
                        value_type=ValueType.OBJECT,
                        normalization_status=NormalizationStatus.NOT_APPLICABLE,
                        semantic_status=SemanticStatus.CONFIRMED,
                    ),
                    source_field=rank_locator.removeprefix("$.") if rank_locator.startswith("$.") else rank_locator,
                    source_record_identity=source_identity,
                    provider_semantic=(
                        "Organic rank record" if channel is Channel.ORGANIC else "Sponsored rank record"
                    ),
                    evidence_type=EvidenceType.OBSERVED,
                    query_result_status=ResultStatus.POPULATED,
                    rank=dict(rank),
                    observed_at=observed_at,
                    discriminator=f"row:{row_index}:rank:{rank_index}:{position}",
                )
                del observation
            except ContractValidationError:
                _record_issue(
                    session,
                    subject=product_subject(product),
                    dimension="product_keyword_rank",
                    code="INVALID_RANK_TIME_OR_PRIMITIVE",
                    message="Rank record failed strict canonical validation and was omitted.",
                    locator=rank_locator,
                )

    traffic_summary = row.get("trafficSummary")
    traffic = traffic_summary.get("traffic") if isinstance(traffic_summary, MappingABC) else None
    if isinstance(traffic, MappingABC):
        for raw_key, channel in (("organic", Channel.ORGANIC), ("advertising", Channel.SPONSORED)):
            raw_value = traffic.get(raw_key)
            numeric = strict_number(raw_value)
            if numeric is None:
                if raw_key in traffic:
                    _record_issue(
                        session,
                        subject=product_subject(product),
                        dimension="traffic",
                        code="INVALID_TRAFFIC_PRIMITIVE",
                        message="Traffic value must be a finite number; booleans are rejected.",
                        locator=f"{locator}.trafficSummary.traffic.{raw_key}",
                    )
                continue
            envelope = value_envelope(
                presence_status=PresenceStatus.PRESENT,
                raw_value=raw_value,
                normalized_value=numeric,
                value_type=ValueType.NUMBER,
                unit=Unit(dimension="TRAFFIC", unit_code="provider_traffic", unit_system="PROVIDER"),
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            )
            observation = session.add_relationship(
                product=product,
                keyword=keyword,
                direction=direction,
                relationship_type=RelationshipType.TRAFFIC,
                channel=channel,
                value=envelope,
                source_field=f"{locator}.trafficSummary.traffic.{raw_key}".removeprefix("$."),
                source_record_identity=source_identity,
                provider_semantic="Provider traffic summary; unit, method, and exact period are unconfirmed",
                evidence_type=EvidenceType.PROVIDER_ESTIMATE,
                query_result_status=ResultStatus.POPULATED,
                traffic=envelope,
                period_type=PeriodType.UNKNOWN,
                discriminator=f"row:{row_index}:traffic:{raw_key}",
                result_status=ResultStatus.PARTIAL,
            )
            issue_id = _record_issue(
                session,
                subject=observation.subject,
                dimension="traffic",
                code="TRAFFIC_METHOD_PERIOD_UNCONFIRMED",
                message="Provider traffic unit, method, and exact period are not documented.",
                locator=f"{locator}.trafficSummary.traffic.{raw_key}",
            )
            session.attach_issue((observation.observation_id,), issue_id)
        _report_fields(
            session,
            traffic,
            locator=f"{locator}.trafficSummary.traffic",
            mapped={"organic", "advertising"},
            ignored={
                "total": "Total traffic is retained but not merged with channel-specific evidence.",
                "organicGrowthRate": "Traffic growth analysis is out of scope.",
                "advertisingGrowthRate": "Traffic growth analysis is out of scope.",
                "totalGrowthRate": "Traffic growth analysis is out of scope.",
            },
        )
    elif traffic_summary is not None:
        _record_issue(
            session,
            subject=product_subject(product),
            dimension="traffic",
            code="INVALID_TRAFFIC_SUMMARY_TYPE",
            message="trafficSummary.traffic must be an object.",
            locator=f"{locator}.trafficSummary",
        )
    if isinstance(traffic_summary, MappingABC):
        _report_fields(
            session,
            traffic_summary,
            locator=f"{locator}.trafficSummary",
            mapped={"traffic"},
            ignored={
                "trafficAcquisitionRate": "Acquisition-rate analysis is out of scope.",
                "trafficRatio": "Traffic-ratio analysis is out of scope.",
            },
        )


def _keyword_to_asin(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    query = _request_text(session, "keyword")
    if query is None:
        return _fail(
            session,
            "MISSING_REQUEST_IDENTITY",
            "sanitized_request.keyword is required for forward relationship identity.",
            "context.sanitized_request.keyword",
        )
    keyword = keyword_identity(session.context.marketplace, session.context.locale, query)
    rows = data.get("list")
    total = data.get("total")
    if not isinstance(rows, (tuple, list)) or type(total) is not int or total < 0:
        return _fail(
            session,
            "MALFORMED_PROVIDER_ENVELOPE",
            "Forward relationship data requires list array and non-negative integer total.",
            "$.data",
        )
    if not rows:
        session.raw_evidence = replace(session.raw_evidence, response_status="EMPTY")
        session.add_query_execution(
            query_keyword=keyword,
            direction=RelationshipDirection.KEYWORD_TO_PRODUCT,
            outcome=QueryExecutionOutcome.EXPLICIT_EMPTY,
            related_relationship_observation_ids=(),
            source_field="data.list",
            source_record_identity=keyword.keyword_id,
        )
        session.diagnostic(
            code="QUERY_RETURNED_EMPTY",
            message=(
                "Valid Keyword to ASIN query returned no rows. This is not market_size, demand, "
                "competitor_count, or a zero-valued metric."
            ),
            source_locator="$.data.list",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        _report_fields(
            session,
            data,
            locator="$.data",
            mapped={"list"},
            ignored={"total": "Provider row count is not a market-size metric."},
        )
        return session.finish()
    for index, row in enumerate(rows):
        locator = f"$.data.list[{index}]"
        if not isinstance(row, MappingABC):
            _record_issue(
                session,
                subject=SubjectRef(
                    subject_type=SubjectType.KEYWORD,
                    subject_id=keyword.keyword_id,
                    marketplace=keyword.marketplace,
                ),
                dimension="product_keyword_relationship",
                code="INVALID_RECORD_TYPE",
                message="Forward relationship row must be an object.",
                locator=locator,
            )
            continue
        asin = normalized_asin(row.get("asin"))
        country = row.get("country")
        if asin is None or country != session.context.marketplace:
            _record_issue(
                session,
                subject=SubjectRef(
                    subject_type=SubjectType.KEYWORD,
                    subject_id=keyword.keyword_id,
                    marketplace=keyword.marketplace,
                ),
                dimension="product_keyword_relationship",
                code="INVALID_PRODUCT_IDENTITY",
                message="Forward row requires valid ASIN and matching country.",
                locator=locator,
            )
            continue
        product = product_identity(session.context.marketplace, asin)
        _map_relationship_row(
            session,
            row=row,
            row_index=index,
            product=product,
            keyword=keyword,
            direction=RelationshipDirection.KEYWORD_TO_PRODUCT,
            locator=locator,
        )
        _report_fields(
            session,
            row,
            locator=locator,
            mapped={"asin", "country", "ranks", "trafficSummary"},
            ignored={"asinInfo": "Embedded product profile is not remapped inside relationship payloads."},
        )
    _report_fields(
        session,
        data,
        locator="$.data",
        mapped={"list"},
        ignored={"total": "Provider row count is retained but is not a market-size metric."},
    )
    related_ids = tuple(
        item.observation_id
        for item in session.observations
        if isinstance(item, ProductKeywordRelationshipObservation)
        and item.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
        and item.keyword == keyword
    )
    session.add_query_execution(
        query_keyword=keyword,
        direction=RelationshipDirection.KEYWORD_TO_PRODUCT,
        outcome=(
            QueryExecutionOutcome.RESULTS_RETURNED
            if related_ids
            else QueryExecutionOutcome.OUTCOME_UNKNOWN
        ),
        related_relationship_observation_ids=related_ids,
        source_field="data.list",
        source_record_identity=keyword.keyword_id,
        quality_issue_ids=tuple(item.issue_id for item in session.issues),
    )
    return session.finish()


def _asin_to_keyword(session: _AdapterSession, data: Mapping[str, Any]) -> AdaptationResult:
    request_asin = normalized_asin(_request_text(session, "asin"))
    if request_asin is None:
        return _fail(
            session,
            "MISSING_REQUEST_IDENTITY",
            "sanitized_request.asin is required for reverse relationship identity.",
            "context.sanitized_request.asin",
        )
    product = product_identity(session.context.marketplace, request_asin)
    rows = data.get("list")
    total = data.get("total")
    if not isinstance(rows, (tuple, list)) or type(total) is not int or total < 0:
        return _fail(
            session,
            "MALFORMED_PROVIDER_ENVELOPE",
            "Reverse relationship data requires list array and non-negative integer total.",
            "$.data",
        )
    if not rows:
        session.raw_evidence = replace(session.raw_evidence, response_status="EMPTY")
        session.add_query_execution(
            query_product=product,
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
            outcome=QueryExecutionOutcome.EXPLICIT_EMPTY,
            related_relationship_observation_ids=(),
            source_field="data.list",
            source_record_identity=product.product_id,
        )
        session.diagnostic(
            code="QUERY_RETURNED_EMPTY",
            message=(
                "Valid ASIN to Keyword query returned no rows. This is not demand, relevance, "
                "or a zero-valued metric."
            ),
            source_locator="$.data.list",
            disposition=MappingDisposition.APPROVED_WITH_EXPLICIT_UNKNOWN,
            affects_status=False,
        )
        _report_fields(
            session,
            data,
            locator="$.data",
            mapped={"list"},
            ignored={"total": "Provider row count is retained but is not a demand metric."},
        )
        return session.finish()
    for index, row in enumerate(rows):
        locator = f"$.data.list[{index}]"
        if not isinstance(row, MappingABC):
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="product_keyword_relationship",
                code="INVALID_RECORD_TYPE",
                message="Reverse relationship row must be an object.",
                locator=locator,
            )
            continue
        search_term = row.get("searchTerm")
        country = row.get("country")
        if not isinstance(search_term, str) or not search_term.strip() or country != session.context.marketplace:
            _record_issue(
                session,
                subject=product_subject(product),
                dimension="product_keyword_relationship",
                code="INVALID_KEYWORD_IDENTITY",
                message="Reverse row requires non-empty searchTerm and matching country.",
                locator=locator,
            )
            continue
        keyword = keyword_identity(session.context.marketplace, session.context.locale, search_term)
        _map_relationship_row(
            session,
            row=row,
            row_index=index,
            product=product,
            keyword=keyword,
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
            locator=locator,
        )
        _report_fields(
            session,
            row,
            locator=locator,
            mapped={"searchTerm", "country", "ranks", "trafficSummary"},
        )
    _report_fields(
        session,
        data,
        locator="$.data",
        mapped={"list"},
        ignored={"total": "Provider row count is retained but is not a demand metric."},
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
        source_field="data.list",
        source_record_identity=product.product_id,
        quality_issue_ids=tuple(item.issue_id for item in session.issues),
    )
    return session.finish()


class XiYouAdapterV0_1:
    """Offline audited XiYou adapter with V0.1.2 provenance rules."""

    provider = "xiyou"
    adapter_version = "0.1.2"
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
        data = _xiyou_data(prepared)
        if isinstance(data, AdaptationResult):
            return data
        handlers = {
            "asin_info": _product_info,
            "asin_variations": _variations,
            "asin_orders_last_30_days": _orders,
            "asin_bsr_trends": _bsr,
            "keyword_info": _keyword_info,
            "keyword_asin_analysis": _keyword_to_asin,
            "asin_keywords": _asin_to_keyword,
        }
        return handlers[context.payload_kind](prepared, data)


__all__ = ("XiYouAdapterV0_1",)
