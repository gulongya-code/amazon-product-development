"""Shared localized tables consumed by both Markdown and workbook renderers."""

from __future__ import annotations

from . import i18n

PERCENT = "0.0%"
NUMBER = "#,##0.00"
COUNT = "#,##0"


def workbook_spec(report, locale="zh-CN"):
    data = report.to_dict()
    t = lambda k: i18n.text(k, locale)
    rl = lambda r: i18n.route_label(r, locale)
    fl = lambda f: i18n.label(f, locale)
    na = t("UNAVAILABLE")
    sheets = []

    def sheet(key, note=""):
        result = {"key": key, "name": t(key), "title": t(key), "note": note, "tables": []}
        sheets.append(result)
        return result

    def table(target, headers, rows, formats=None, title="", widths=None):
        target["tables"].append({"title": title, "headers": [t(h) for h in headers], "rows": [[na if v is None else v for v in r] for r in rows], "formats": formats or [None] * len(headers), "widths": widths or [32 if i == 0 else 18 for i in range(len(headers))]})

    def metric_value(value):
        return value["value"] if isinstance(value, dict) else value

    def stats(target, collection, name):
        table(target, [name, "products", "assigned_product_share", "sales", "sales_share", "median_price", "median_reviews", "demand_efficiency", "sales_coverage"],
              [[label, r["products"], r["assigned_product_share"], r["sales"]["value"], r["sales_share"]["value"], r["median_price"]["value"], r["median_reviews"]["value"], r["demand_efficiency"]["value"], r["sales"]["coverage"]] for label, r in collection],
              [None, COUNT, PERCENT, COUNT, PERCENT, NUMBER, COUNT, NUMBER, PERCENT], widths=[44, 11, 15, 16, 14, 16, 15, 14, 14])
        table(target, [name, "revenue", "revenue_share", "median_rating", "mom", "yoy", "new_efficiency", "age_known", "age_unknown"],
              [[label, r["revenue"]["value"], r["revenue_share"]["value"], r["median_rating"]["value"], r["mom"]["value"], r["yoy"]["value"], r["new_products"][0]["demand_efficiency"]["value"], r["new_products"][0]["age_known"], r["new_products"][0]["age_unknown"]] for label, r in collection],
              [None, NUMBER, PERCENT, NUMBER, PERCENT, PERCENT, NUMBER, COUNT, COUNT], title=t("new"), widths=[44, 20, 14, 14, 14, 14, 17, 15, 15])
        table(target, [name, "metric", "coverage"],
              [[label, t(key) if key in {"title", "structured", "sales", "age"} else t("median_reviews") if key == "reviews" else t("median_price"), v] for label, r in collection for key, v in r["evidence_coverage"].items()],
              [None, None, PERCENT], title=t("coverage"), widths=[44, 24, 16])

    readiness = data["decision_readiness"]
    warning = " ".join(t(code) for code in readiness["codes"])
    headline = t(readiness["business_decision_readiness"]) + " " + warning
    summary = sheet("summary", headline)
    by_number = {r["route_number"]: rl(r) for r in data["routes"]}
    def basis_name(path):
        parts = path.split("/")
        key = parts[-2] if parts[-1] in {"value", "coverage"} else parts[-1]
        mapping = {"top_1": "top1", "strong_route_research_allowed": "strong_route_research_allowed"}
        key = mapping.get(key, key)
        if key == "classification":
            key = "conclusion"
        if key == "availability":
            key = "buyer"
        label = t(key)
        return label + (" " + t("coverage") if parts[-1] == "coverage" else "")
    rows = []
    for item in data["executive_summary"]:
        entity = item["entity"]
        parts = [by_number.get(entity, fl(entity))] if entity is not None else []
        if not item["facts"]:
            parts.append(na)
        for fact in item["facts"]:
            path = fact["path"]
            pct = "coverage_counts" not in path and any(x in path for x in ("share", "coverage", "/mom/", "/yoy/", "top_1"))
            parts.append(basis_name(path) + "：" + i18n.formatted(fact["value"], locale, percent=pct))
        if item["question"] in {"RESEARCH_DIRECTION", "LOW_PRIORITY_DIRECTION"} and entity is None:
            parts.append(t("no_direction"))
        rows.append([t(item["question"]), "\n".join(parts)])
    table(summary, ["question", "answer"], rows, widths=[38, 115])

    market = sheet("market", t("OBSERVED_EXPORT_NOT_TOTAL_ADDRESSABLE_MARKET"))
    table(market, ["metric", "value", "basis"], [[t(k), v, t("market")] for k, v in data["coverage_counts"].items()] + [[t(k), data["market"][k]["value"], t("MISSING_NOT_ZERO")] for k in ("sales", "revenue", "median_price", "median_reviews", "median_rating")], [None, NUMBER, None], widths=[38, 24, 85])
    market["tables"][0]["row_formats"] = [[None, COUNT if i < len(data["coverage_counts"]) or key in {"sales", "median_reviews"} else NUMBER, None] for i, key in enumerate([*data["coverage_counts"], "sales", "revenue", "median_price", "median_reviews", "median_rating"])]
    table(market, ["metric", "value", "basis"], [[t(k), readiness[k], t("ASSIGNED_SUBSET_ONLY")] for k in ("assigned_coverage", "unresolved_exposure", "assigned_observed_sales_share_of_market")], [None, PERCENT, None], widths=[42, 24, 80])

    structure = sheet("hierarchy", t("hierarchy_note"))
    family_order = {f["family_id"]: i for i, f in enumerate(data["families"])}
    table(structure, ["family", "route", "mechanism", "specificity", "products", "sales", "sales_share"], [[fl(r["hierarchy"]["family_id"]), rl(r), " / ".join(fl(v) for v in r["hierarchy"]["mechanism_values"]) or (fl("wall_mount_unspecified") if r["hierarchy"]["fallback_label"] else na), t(r["hierarchy"]["specificity"]), r["products"], r["sales"]["value"], r["sales_share"]["value"]] for r in sorted(data["routes"], key=lambda r: (family_order[r["hierarchy"]["family_id"]], r["hierarchy"]["mechanism_values"], r["route_number"]))], [None, None, None, None, COUNT, COUNT, PERCENT], widths=[36, 52, 25, 24, 11, 17, 14])
    table(structure, ["family", "mechanism", "products", "sales", "family_sales_share", "median_price", "median_reviews", "demand_efficiency"], [[fl(g["family_id"]), fl(g["mechanism_id"]), g["products"], g["sales"]["value"], g["sales_share"]["value"], g["median_price"]["value"], g["median_reviews"]["value"], g["demand_efficiency"]["value"]] for g in data["mechanism_groups"]], [None, None, COUNT, COUNT, PERCENT, NUMBER, COUNT, NUMBER], title=t("mechanism_rollup"), widths=[36, 52, 16, 24, 20, 20, 18, 18])

    families = sheet("families", t("ASSIGNED_SUBSET_ONLY") + " " + t("UNASSIGNED_MEMBERSHIP_NOT_INFERRED"))
    stats(families, [(fl(f["family_id"]), f) for f in data["families"]], "family")
    routes = sheet("routes", t("ASSIGNED_SUBSET_ONLY"))
    stats(routes, [(rl(r), r) for r in data["routes"]], "route")

    for key, field, table_key, heading in (("prices", "price", "price_bands", "price_band"), ("reviews", "reviews", "review_bands", "review_band")):
        target = sheet(key, t("band_note") + (" " + t("review_note") if key == "reviews" else ""))
        band_rows = []
        for route in data["routes"]:
            for b in route[table_key]:
                if b["band_id"] == "UNKNOWN":
                    name = t("UNKNOWN")
                else:
                    lo, hi = b["lower_inclusive"], b["upper_exclusive"]
                    name = f"{lo:g}–{hi-1:g}" if field == "reviews" and hi is not None else f"[{lo:g}, {hi:g})" if hi is not None else f"≥ {lo:g}"
                    configured = data["report_profile"]["labels"].get(b["band_id"], {}).get(locale)
                    if configured:
                        name += " " + configured
                band_rows.append([rl(route), name, b["products"], b["listing_share"], b["sales"]["value"], b["sales_share"]["value"], b["median_reviews"]["value"], b["demand_efficiency"]["value"], b["sales"]["coverage"]])
        table(target, ["route", heading, "products", "listing_share", "sales", "sales_share", "median_reviews", "demand_efficiency", "sales_coverage"], band_rows, [None, None, COUNT, PERCENT, COUNT, PERCENT, COUNT, NUMBER, PERCENT], widths=[46, 35, 11, 14, 15, 14, 15, 14, 14])
        if key == "reviews":
            # Place the decision-useful barrier summary before the detailed bands.
            detail = target["tables"].pop()
            table(target, ["route", "low_review_max", "products", "selling", "low_sales", "low_median_sales", "median_reviews"], [[rl(r), r["low_review"]["maximum_reviews_inclusive"], r["low_review"]["products"], r["low_review"]["selling_products"], r["low_review"]["sales_share"]["value"], r["low_review"]["median_sales"]["value"], r["median_reviews"]["value"]] for r in data["routes"]], [None, COUNT, COUNT, COUNT, PERCENT, COUNT, COUNT], widths=[46, 18, 12, 22, 20, 24, 19])
            target["tables"].append(detail)

    new = sheet("new", t("new_note") + " " + t("NO_GOVERNED_SUCCESS_DEFINITION"))
    table(new, ["route", "age", "products", "age_known", "age_unknown", "new_share", "median_sales", "median_reviews", "new_efficiency", "success"], [[rl(r), n["maximum_age_days_inclusive"], n["products"], n["age_known"], n["age_unknown"], n["sales_share_route"]["value"], n["median_sales"]["value"], n["median_reviews"]["value"], n["demand_efficiency"]["value"], na] for r in data["routes"] for n in r["new_products"]], [None, COUNT, COUNT, COUNT, COUNT, PERCENT, COUNT, COUNT, NUMBER, None], widths=[46, 17, 11, 18, 18, 19, 18, 17, 19, 22])

    scopes = [(t("route_family"), fl(f["family_id"]), f) for f in data["families"]] + [(t("route_scope"), rl(r), r) for r in data["routes"]]
    for key in ("brands", "sellers"):
        target = sheet(key, t("competition_note"))
        table(target, ["scope", "route", "basis", "top1", "top3", "top5", "tail", "identity_coverage", "sales_coverage"], [[scope, name, t(basis), *[r[key][basis][k] for k in ("top_1", "top_3", "top_5", "long_tail")], r[key]["identity_coverage"], r[key]["sales_coverage"]["coverage"]] for scope, name, r in scopes for basis in ("sales_concentration", "listing_concentration")], [None, None, None, PERCENT, PERCENT, PERCENT, PERCENT, PERCENT, PERCENT], widths=[11, 46, 22, 14, 14, 14, 20, 15, 15])
        table(target, ["scope", "route", "ranking", "entity", "products", "listing_share", "sales", "sales_share", "median_price", "median_reviews"], [[scope, name, i+1, e["name"], e["products"], e["listing_share"], e["sales"]["value"], e["sales_share"]["value"], e["median_price"]["value"], e["median_reviews"]["value"]] for scope, name, r in scopes for i, e in enumerate(r[key]["top_entities"])], [None, None, COUNT, None, COUNT, PERCENT, COUNT, PERCENT, NUMBER, COUNT], widths=[11, 46, 12, 40, 11, 14, 16, 15, 18, 18])

    opportunities = sheet("opportunities", headline + " " + t("NOT_A_LAUNCH_RECOMMENDATION"))
    table(opportunities, ["route", "conclusion", "support", "concern", "context"], [[by_number[e["route_number"]], t(e["classification"]), *["\n".join(i18n.fact_text(f, locale) for f in e["facts"] if f["role"] == role) or na for role in ("support", "concern", "context")]] for e in data["opportunity_explanations"]], widths=[46, 48, 55, 70, 70])
    buyer = sheet("buyer", t("NO_GOVERNED_REVIEW_OR_SEARCH_EVIDENCE"))
    table(buyer, ["metric", "status", "basis"], [[t("buyer"), na, t("BUYER_NEED_DATA_MISSING")]], widths=[30, 20, 100])
    risks = sheet("risks", t("report_policy_note"))
    table(risks, ["question", "answer"], [[t("risks"), t(code)] for code in (*readiness["codes"], *data["limitations"])], widths=[26, 115])
    table(risks, ["metric", "value", "basis"], [[t(k), data["report_profile"][k], t("report_policy_note")] for k in ("minimum_route_coverage", "minimum_sales_coverage", "high_unresolved_exposure")], [None, PERCENT, None], widths=[42, 22, 100])
    for k in ("price_boundaries", "review_boundaries", "new_product_days"):
        table(risks, ["metric", "value"], [[t(k), ", ".join(str(x) for x in data["report_profile"][k])]], widths=[45, 70])

    human = sheet("human", t("human_note"))
    table(human, ["question", "human_verdict", "notes"], [[i18n.question(r["question_id"], locale), "", ""] for r in data["business_value_review"]], widths=[75, 27, 80])
    human["human_input"] = True

    audit = sheet("audit", t("snapshot_note"))
    table(audit, ["metric", "value"], [[k, str(v)] for k, v in data["source_lineage"].items()] + [["report_fingerprint", data["semantic_fingerprint"]], ["report_contract", data["contract_version"]]], widths=[46, 110])
    table(audit, ["route", "definition", "basis"], [[rl(r), "; ".join(f["dimension"]+"="+",".join(f["values"]) for f in r["features"]), r["route_id"]] for r in data["routes"]], widths=[50, 85, 85])
    table(audit, ["route", "basis", "value"], [[e["route_number"], f["code"] + " " + f["path"], str(f["value"])] for e in data["opportunity_explanations"] for f in e["facts"]], widths=[15, 100, 35])
    return {"contract_version": "operator-workbook-spec-v0.3", "locale": locale, "report_fingerprint": data["semantic_fingerprint"], "category": fl(data["category"]), "generated_at": data["generated_at"], "sheets": sheets}


def markdown(report, locale="zh-CN"):
    spec = workbook_spec(report, locale)
    def escape(value, fmt=None):
        value = i18n.formatted(value, locale, percent=fmt == PERCENT)
        return value.replace("|", "\\|").replace("\n", "<br>").replace("\r", "")
    lines = [f"# {i18n.text('summary', locale)}", "", spec["category"], "", spec["generated_at"], ""]
    for sheet in spec["sheets"]:
        lines.extend([f"## {sheet['name']}", "", sheet["note"], ""])
        for table in sheet["tables"]:
            if table["title"]:
                lines.extend([f"### {table['title']}", ""])
            lines.extend(["| " + " | ".join(escape(h) for h in table["headers"]) + " |", "| " + " | ".join("---" for _ in table["headers"]) + " |"])
            lines.extend("| " + " | ".join(escape(v, f) for v, f in zip(row, table["formats"])) + " |" for row in table["rows"])
            lines.append("")
    return "\n".join(lines) + "\n"
