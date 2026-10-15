"""Deterministic descriptive metrics on disjoint governed membership sets.

Missing observations are never zero. Shares expose their observed denominator;
paired-cohort efficiencies use the same listings for demand and listing shares.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from hashlib import sha256
from math import ceil
from typing import Any

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.route_discovery_input import ROUTE_INPUT_FIELD_MAPPINGS

FIELDS = {
    "sales": "estimated_monthly_sales", "revenue": "estimated_monthly_revenue",
    "price": "price", "reviews": "review_count", "rating": "rating",
    "age": "listing_age_days", "mom": "sales_mom_growth", "yoy": "sales_yoy_growth",
    "brand": "brand", "seller": "seller", "title": "title",
}
HEADERS = {x.canonical_name: x.target_header for x in ROUTE_INPUT_FIELD_MAPPINGS}


def project_record(record, *, observed_date=None):
    fields = {x.header: x for x in record.fields}
    result = {"reference": record.asin}
    for key, canonical in FIELDS.items():
        field = fields.get(HEADERS.get(canonical))
        value = field.value if field is not None and field.import_status.value == "NORMALIZED" else None
        if key in {"brand", "seller", "title"}:
            result[key] = str(value).strip() if value is not None and str(value).strip() else None
        else:
            try:
                value = Decimal(str(value)) if value is not None and not isinstance(value, bool) else None
                if value is not None and (not value.is_finite() or (key not in {"mom", "yoy"} and value < 0)):
                    value = None
            except Exception:
                value = None
            result[key] = value
    details = fields.get("详细参数")
    result["structured"] = details is not None and details.import_status.value == "NORMALIZED" and details.value is not None
    result["age_method"] = "EXPLICIT_LISTING_AGE" if result["age"] is not None else "UNAVAILABLE"
    if result["age"] is None and observed_date:
        first = fields.get(HEADERS.get("first_available_date"))
        if first is not None and first.import_status.value == "NORMALIZED" and first.value is not None:
            try:
                age = (date.fromisoformat(observed_date) - date.fromisoformat(str(first.value))).days
                if age >= 0:
                    result["age"] = Decimal(age)
                    result["age_method"] = "GOVERNED_OBSERVED_DATE_MINUS_FIRST_AVAILABLE_DATE"
            except (ValueError, TypeError):
                pass
    return result


def number(value):
    return None if value is None else float(value)


def ratio(a, b):
    return number(Decimal(str(a)) / Decimal(str(b))) if a is not None and b is not None and b > 0 else None


def metric(value, included, total, method, **context):
    return {
        "value": number(value), "availability": "UNAVAILABLE" if value is None else "AVAILABLE" if included == total else "PARTIAL",
        "included_count": included, "population_count": total, "unknown_count": total - included,
        "coverage": ratio(included, total) if total else 0.0, "method": method,
        **context,
    }


def total(rows, field):
    values = [r[field] for r in rows if r[field] is not None]
    return metric(sum(values, Decimal(0)) if values or not rows else None, len(values), len(rows), "EMPTY_SET_ZERO" if not rows else "SUM_OBSERVED", field=field)


def median(rows, field):
    values = sorted(r[field] for r in rows if r[field] is not None)
    return metric(values[max(0, ceil(len(values) / 2) - 1)] if values else None, len(values), len(rows), "NEAREST_RANK_P50", field=field)


def subset_share(rows, population, field):
    numerator = total(rows, field)
    denominator = total(population, field)
    return metric(ratio(numerator["value"], denominator["value"]), denominator["included_count"], len(population), "OBSERVED_SUBSET_SUM_DIV_OBSERVED_POPULATION_SUM", numerator=numerator["value"], denominator=denominator["value"], numerator_known=numerator["included_count"], numerator_population=len(rows))


def efficiency(rows, population):
    known = [r for r in population if r["sales"] is not None]
    subset = [r for r in rows if r["sales"] is not None]
    sales_share = subset_share(subset, known, "sales")["value"]
    listing_share = ratio(len(subset), len(known))
    return metric(ratio(sales_share, listing_share), len(known), len(population), "PAIRED_SALES_SHARE_DIV_PAIRED_LISTING_SHARE", sales_share=sales_share, listing_share=listing_share, subset_count=len(subset))


def growth(rows, field):
    eligible = [r for r in rows if r["sales"] is not None and r[field] is not None and r[field] > -1 and r["sales"] > 0]
    current = sum((r["sales"] for r in eligible), Decimal(0))
    prior = sum((r["sales"] / (1 + r[field]) for r in eligible), Decimal(0))
    value = current / prior - 1 if prior > 0 else None
    return metric(value, len(eligible), len(rows), "SUM_CURRENT_DIV_SUM_RECONSTRUCTED_PRIOR_MINUS_ONE", current_sales=number(current) if eligible else None, reconstructed_prior_sales=number(prior) if eligible else None, invalid_reconstruction_count=sum(r["sales"] is not None and r[field] is not None and (r[field] <= -1 or r["sales"] <= 0) for r in rows))


def bands(rows, field, boundaries):
    result = []
    lower = Decimal(0)
    for index, upper in enumerate((*boundaries, None)):
        members = [r for r in rows if r[field] is not None and r[field] >= lower and (upper is None or r[field] < Decimal(str(upper)))]
        result.append({"band_id": f"{field}-{index}", "lower_inclusive": number(lower), "upper_exclusive": upper, "products": len(members), "listing_share": ratio(len(members), len(rows)), "sales": total(members, "sales"), "sales_share": subset_share(members, rows, "sales"), "median_reviews": median(members, "reviews"), "demand_efficiency": efficiency(members, rows)})
        if upper is not None:
            lower = Decimal(str(upper))
    unknown = [r for r in rows if r[field] is None]
    result.append({"band_id": "UNKNOWN", "lower_inclusive": None, "upper_exclusive": None, "products": len(unknown), "listing_share": ratio(len(unknown), len(rows)), "sales": total(unknown, "sales"), "sales_share": subset_share(unknown, rows, "sales"), "median_reviews": median(unknown, "reviews"), "demand_efficiency": efficiency(unknown, rows)})
    assert sum(r["products"] for r in result) == len(rows)
    return result


def entrants(rows, days):
    known = [r for r in rows if r["age"] is not None]
    recent = [r for r in known if r["age"] <= days]
    paired = [r for r in known if r["sales"] is not None]
    share = subset_share(recent, rows, "sales")
    share["interpretation"] = "CONFIRMED_NEW_SALES_SHARE_LOWER_BOUND_WHEN_AGE_UNKNOWN"
    share["age_unknown_count"] = len(rows) - len(known)
    if len(known) != len(rows) and share["value"] is not None:
        share["availability"] = "PARTIAL"
    return {"maximum_age_days_inclusive": days, "products": len(recent), "age_known": len(known), "age_unknown": len(rows) - len(known), "listing_share_known_age": ratio(len(recent), len(known)), "sales": total(recent, "sales"), "sales_share_route": share, "sales_share_known_age": subset_share(recent, known, "sales"), "median_sales": median(recent, "sales"), "median_reviews": median(recent, "reviews"), "demand_efficiency": efficiency(recent, paired), "success_count": None, "success_share": None, "success_availability": "UNAVAILABLE", "success_reason": "NO_GOVERNED_SUCCESS_DEFINITION", "nested_windows_not_additive": True}


def competition(rows, field, top_n):
    groups = defaultdict(list)
    for row in rows:
        if row[field] is not None:
            groups[" ".join(row[field].split()).casefold()].append(row)
    known = [r for r in rows if r[field] is not None]
    entities = []
    for key, members in sorted(groups.items()):
        entities.append({"name": sorted(set(r[field] for r in members))[0], "products": len(members), "listing_share": ratio(len(members), len(known)), "sales": total(members, "sales"), "sales_share": subset_share(members, known, "sales"), "median_price": median(members, "price"), "median_reviews": median(members, "reviews")})
    entities.sort(key=lambda r: (r["sales"]["value"] is None, -(r["sales"]["value"] or 0), -r["products"], r["name"].casefold(), r["name"]))
    listing_shares = sorted((e["listing_share"] for e in entities), reverse=True)
    sales_shares = sorted((e["sales_share"]["value"] for e in entities if e["sales_share"]["value"] is not None), reverse=True)
    def concentration(values):
        return {**{f"top_{n}": sum(values[:n]) if values else None for n in (1, 3, 5)}, "long_tail": max(0.0, 1 - sum(values[:5])) if values else None}
    return {"entity_count": len(groups), "known_identity": len(known), "unknown_identity": len(rows)-len(known), "identity_coverage": ratio(len(known), len(rows)), "sales_coverage": total(known, "sales"), "ranking_basis": "KNOWN_IDENTITY_OBSERVED_SALES_DESC_THEN_LISTINGS_THEN_NAME", "denominator": "KNOWN_IDENTITY_LISTINGS_AND_OBSERVED_SALES", "listing_concentration": concentration(listing_shares), "sales_concentration": concentration(sales_shares), "top_entities": entities[:top_n]}


def aggregate(rows, assigned, profile):
    low = [r for r in rows if r["reviews"] is not None and r["reviews"] <= profile.low_review_max]
    return {
        "products": len(rows), "membership_fingerprint": sha256(canonical_json(sorted(r["reference"] for r in rows)).encode()).hexdigest(),
        "assigned_product_share": ratio(len(rows), len(assigned)), "sales": total(rows, "sales"), "sales_share": subset_share(rows, assigned, "sales"),
        "revenue": total(rows, "revenue"), "revenue_share": subset_share(rows, assigned, "revenue"),
        "median_price": median(rows, "price"), "median_reviews": median(rows, "reviews"), "median_rating": median(rows, "rating"),
        "demand_efficiency": efficiency(rows, assigned), "mom": growth(rows, "mom"), "yoy": growth(rows, "yoy"),
        "new_products": [entrants(rows, d) for d in profile.new_product_days],
        "price_bands": bands(rows, "price", profile.price_boundaries), "review_bands": bands(rows, "reviews", profile.review_boundaries),
        "low_review": {"maximum_reviews_inclusive": profile.low_review_max, "products": len(low), "selling_products": sum(r["sales"] is not None and r["sales"] > 0 for r in low), "sales": total(low, "sales"), "sales_share": subset_share(low, rows, "sales"), "demand_efficiency": efficiency(low, [r for r in rows if r["reviews"] is not None]), "median_sales": median(low, "sales")},
        "brands": competition(rows, "brand", profile.top_n), "sellers": competition(rows, "seller", profile.top_n),
        "evidence_coverage": {"title": ratio(sum(r["title"] is not None for r in rows), len(rows)), "structured": ratio(sum(r["structured"] for r in rows), len(rows)), **{k: ratio(sum(r[k] is not None for r in rows), len(rows)) for k in ("sales", "price", "reviews", "age")}},
        "age_derivation_counts": {method: sum(r.get("age_method", "EXPLICIT_LISTING_AGE" if r["age"] is not None else "UNAVAILABLE") == method for r in rows) for method in ("EXPLICIT_LISTING_AGE", "GOVERNED_OBSERVED_DATE_MINUS_FIRST_AVAILABLE_DATE", "UNAVAILABLE")},
        "unresolved_exposure": {"availability": "UNAVAILABLE", "value": None, "reason": "UNASSIGNED_MEMBERSHIP_NOT_INFERRED"},
    }
