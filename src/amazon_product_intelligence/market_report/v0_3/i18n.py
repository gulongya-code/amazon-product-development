"""One locale catalog for both Markdown and XLSX. No parallel report logic."""

LOCALES = ("zh-CN", "en-US")

_PAIRS = {
    "summary": ("执行摘要", "Executive Summary"), "market": ("市场概览", "Market Overview"),
    "hierarchy": ("市场结构树", "Market Structure"), "families": ("路线家族对比", "Route Families"),
    "routes": ("路线明细", "Route Details"), "prices": ("价格带分析", "Price Bands"),
    "reviews": ("评论门槛", "Review Barriers"), "new": ("新品表现", "New Entrants"),
    "brands": ("品牌竞争", "Brand Competition"), "sellers": ("卖家竞争", "Seller Competition"),
    "opportunities": ("机会分析", "Opportunity Analysis"), "buyer": ("买家需求", "Buyer Needs"),
    "risks": ("风险与限制", "Risks and Limitations"), "human": ("业务价值审核", "Business Value Review"),
    "audit": ("审计与溯源", "Audit and Lineage"),
    "question": ("决策问题", "Decision question"), "answer": ("解读与指标依据", "Interpretation and metric basis"),
    "metric": ("指标", "Metric"), "value": ("数值", "Value"), "basis": ("口径／依据", "Basis"),
    "family": ("路线家族", "Route family"), "route": ("产品路线", "Product route"), "mechanism": ("细分／固定方式", "Sub-route / mechanism"),
    "specificity": ("定义状态", "Definition status"), "definition": ("已有路线定义", "Released route definition"),
    "products": ("商品数", "Listings"), "listing_share": ("商品占比", "Listing share"),
    "assigned_product_share": ("已分配商品占比", "Share of assigned listings"),
    "sales": ("月销量（件）", "Monthly sales (units)"), "sales_share": ("销量占比", "Sales share"),
    "revenue": ("月销售额（美元）", "Monthly revenue (USD)"), "revenue_share": ("销售额占比", "Revenue share"),
    "median_price": ("价格中位数（美元）", "Median price (USD)"), "median_reviews": ("评论数中位数", "Median reviews"),
    "median_rating": ("评分中位数", "Median rating"), "demand_efficiency": ("需求效率", "Demand efficiency"),
    "mom": ("销量环比", "Sales MoM"), "yoy": ("销量同比", "Sales YoY"),
    "coverage": ("观测覆盖率", "Observation coverage"), "sales_coverage": ("销量数据覆盖率", "Sales-data coverage"),
    "price_band": ("价格区间（美元）", "Price band (USD)"), "review_band": ("评论数区间", "Review-count band"),
    "low_sales": ("低评论商品销量占比", "Low-review sales share"), "selling": ("低评论有销量商品数", "Low-review listings selling"),
    "low_median_sales": ("低评论商品月销量中位数", "Low-review median sales"),
    "age": ("上架天数上限（含）", "Maximum age, inclusive"), "age_known": ("有上架天数商品数", "Known-age listings"),
    "age_unknown": ("缺上架天数商品数", "Unknown-age listings"), "median_sales": ("月销量中位数", "Median monthly sales"),
    "new_share": ("新品销量占路线销量", "New sales / route sales"), "new_efficiency": ("新品需求效率", "New-entrant demand efficiency"),
    "success": ("成功新品数／占比", "Successful entrants / share"), "scope": ("分析层级", "Scope"),
    "entity": ("品牌／卖家名称", "Brand / seller name"), "ranking": ("销量顺序", "Sales rank"),
    "top1": ("前一名占比", "Top 1 share"), "top3": ("前三名占比", "Top 3 share"), "top5": ("前五名占比", "Top 5 share"),
    "tail": ("前五名外长尾占比", "Long tail outside Top 5"), "identity_coverage": ("身份覆盖率", "Identity coverage"),
    "conclusion": ("研究结论", "Research conclusion"), "support": ("支持研究的信号", "Supporting signals"),
    "concern": ("需要关注的问题", "Concerns"), "context": ("补充指标", "Context metrics"),
    "human_verdict": ("人工判断（留空待填）", "Human verdict (blank)"), "notes": ("备注（人工填写）", "Notes (human)"),
    "status": ("状态", "Status"), "UNKNOWN": ("未知／缺失", "Unknown / missing"), "UNAVAILABLE": ("不可用", "Unavailable"),
    "AVAILABLE": ("可用", "Available"), "PARTIAL": ("部分可用", "Partially available"),
    "accepted": ("纳入数据集的商品数", "Accepted listings"), "assigned": ("已分配路线商品数", "Assigned listings"),
    "unclassified": ("未分类商品数", "Unclassified listings"), "review_required": ("待语义复核商品数", "Review-required listings"),
    "primary_cohort": ("主要产品群商品数", "Primary-cohort listings"),
    "unresolved_exposure": ("未分配商品暴露", "Unassigned exposure"),
    "GENERATED_VALIDATED": ("技术报告已生成并通过结构校验", "Technical report generated and structurally validated"),
    "READY_FOR_ROUTE_COMPARISON": ("可比较已覆盖路线，尚不能作上市决策", "Ready to compare covered Routes; not launch-ready"),
    "LIMITED_ROUTE_COMPARISON": ("仅可观察局部路线，不能代表全品类", "Limited Route observation; not category-representative"),
    "LIMITED_ROUTE_COVERAGE": ("路线覆盖不足：仅分析已分配子集，不能据此提出全品类机会结论。", "Limited Route coverage: analysis covers the assigned subset, not whole-category opportunities."),
    "INSUFFICIENT_DEMAND_DATA": ("需求数据不足：强研究推荐已受限。", "Insufficient demand evidence: strong research recommendations are restricted."),
    "HIGH_UNRESOLVED_EXPOSURE": ("未分配商品占比较高，市场结构存在明显盲区。", "High unassigned exposure leaves a material gap in the market structure."),
    "BUYER_NEED_DATA_MISSING": ("缺少受治理的评论／搜索词需求证据，买家需求不可用。", "Buyer Needs unavailable: no governed review or search-term evidence."),
    "NO_GOVERNED_REVIEW_OR_SEARCH_EVIDENCE": ("未提供受治理的评论或搜索词。标题、卖点和特殊功能不作为买家需求证据。", "No governed reviews or search terms. Titles, claims and special features are not Buyer Need evidence."),
    "THIRD_PARTY_ESTIMATES": ("销量及销售额为第三方估算值。", "Sales and revenue are third-party estimates."),
    "OBSERVED_EXPORT_NOT_TOTAL_ADDRESSABLE_MARKET": ("市场规模指本次导出样本，不等于完整可寻址市场。", "Market size means this export sample, not the total addressable market."),
    "MISSING_NOT_ZERO": ("缺失值不填零。占比使用已观测销量，覆盖率不足会影响比较。", "Missing is not zero. Shares use observed sales; incomplete coverage limits comparisons."),
    "ASSIGNED_SUBSET_ONLY": ("家族／路线销量占比均以已分配路线商品为总体。", "Family/Route sales shares use assigned listings as the population."),
    "UNASSIGNED_MEMBERSHIP_NOT_INFERRED": ("未分类及待复核商品没有推定路线归属，无法计算其具体家族暴露。", "Unclassified/review-required listings have no inferred membership; family-specific exposure is unavailable."),
    "MARGIN_DATA_UNAVAILABLE": ("成本、广告费用与利润数据不可用，不能据此确认盈利能力。", "Cost, advertising expense and margin are unavailable; profitability is unconfirmed."),
    "NO_GOVERNED_SUCCESS_DEFINITION": ("没有受治理的成功新品定义，只提供描述性指标。", "No governed successful-entrant definition; descriptive metrics only."),
    "NOT_A_LAUNCH_RECOMMENDATION": ("研究优先级不是上市推荐，业务价值仍待人工审核。", "Research priority is not a launch recommendation; business value awaits human review."),
    "EVIDENCE_LIMITED_FALLBACK": ("证据有限的兜底路线", "Evidence-limited fallback"),
    "DEFINED_BY_GOVERNED_FEATURES": ("按受治理结构定义", "Defined by governed features"),
    "PRIORITY_RESEARCH": ("优先研究：结合已显示的需求信号，下一步验证差异化与成本。", "Priority research: validate differentiation and costs against the displayed demand signals."),
    "WATCH": ("继续观察：目前信号未达到本报告的优先研究或低优先级条件。", "Watch: current signals meet neither the report's priority-research nor low-priority conditions."),
    "LOW_PRIORITY": ("低优先级：需求效率低于均值，暂无正增长或高效率新品信号支持。", "Low priority: below-par demand efficiency with no positive growth or above-par new-entrant signal."),
    "INSUFFICIENT_EVIDENCE": ("证据不足：先补需求数据，暂不作强机会判断。", "Insufficient evidence: obtain demand data before a strong opportunity judgment."),
    "LIMITED_COVERAGE_OBSERVATION": ("局部观察：路线覆盖不足，暂停强机会推荐。", "Subset observation: low Route coverage blocks strong opportunity recommendations."),
    "MARKET_SIZE": ("样本市场有多大？", "How large is the observed market?"),
    "ROUTE_COVERAGE": ("路线覆盖多少市场？", "How much of the market is covered?"),
    "LARGEST_ROUTE": ("销量占比最大的路线", "Largest Route by sales share"),
    "LARGEST_FAMILY": ("销量占比最大的家族", "Largest family by sales share"),
    "STRONGEST_YOY": ("数据覆盖充分的最强同比信号", "Strongest YoY signal with sufficient coverage"),
    "STRONGEST_MOM": ("数据覆盖充分的最强环比信号", "Strongest MoM signal with sufficient coverage"),
    "LOWEST_REVIEW_MEDIAN": ("最低评论中位数：不等同于机会", "Lowest median reviews: not automatically an opportunity"),
    "STRONGEST_LOW_REVIEW_DEMAND": ("低评论商品销量占比最高的路线", "Strongest low-review demand share"),
    "STRONGEST_INCUMBENT": ("品牌头部销量集中度最高的路线", "Highest leading-brand sales concentration"),
    "RESEARCH_DIRECTION": ("值得进一步研究的方向", "Direction for further research"),
    "LOW_PRIORITY_DIRECTION": ("低优先级方向", "Low-priority direction"),
    "KEY_UNCERTAINTY": ("关键不确定性", "Key uncertainty"),
    "DECISION_READY": ("是否可以据此决策？", "Is the report decision-ready?"),
    "no_direction": ("当前没有满足规则且证据充分的方向。请查看覆盖限制和具体路线指标。", "No sufficiently supported direction meets the policy. See coverage limitations and Route metrics."),
    "launch_decision_ready": ("是否支持上市决策", "Launch-ready"),
    "strong_route_research_allowed": ("是否允许强研究推荐", "Strong research recommendation allowed"),
    "business_decision_readiness": ("商业决策就绪程度", "Business decision readiness"),
    "technical_report_status": ("技术报告状态", "Technical report status"),
    "assigned_coverage": ("商品路线覆盖率", "Assigned-listing coverage"),
    "assigned_observed_sales_share_of_market": ("已分配路线销量占全样本已观测销量", "Assigned sales / all observed sales"),
    "hierarchy_note": ("家族为展示汇总，子路线互斥。结构名称保留既有路线含义，不重新分类。壁挂兜底不推断固定方式；嵌入架构独立。", "Families are display aggregates of disjoint Routes; structure names preserve released meanings without reclassification. Wall fallbacks do not infer fixing mechanisms; recessed architecture stays independent."),
    "band_note": ("区间左闭右开，缺失值单列。销量占比以该路线已观测销量为分母；需求效率使用销量有值的同一批商品。", "Bands include the lower bound and exclude the upper. Unknowns are separate. Sales shares use Route observed sales; efficiency uses a paired sales-known cohort."),
    "review_note": ("低评论上限见表。低评论不自动代表机会，请同时看销量占比、有销量商品数与新品表现。", "See the low-review cutoff. Low reviews alone do not imply opportunity: compare demand share, selling listings and new entrants."),
    "new_note": ("天数窗口上限见表，窗口嵌套不可相加。新品效率仅比较年龄与销量同时可用的商品。未知年龄不算老品；有缺失时，新品销量占全路线销量仅为已确认新品的下限。", "Age-window limits are shown in the table; nested windows must not be added. Efficiency uses listings with both age and sales. Unknown age is not old; new sales / all Route sales is a confirmed-new lower bound when age is missing."),
    "competition_note": ("排名依据已知身份的关联商品估算销量，不等于卖家实际成交份额。占比不含未知身份，销量缺失会影响集中度。前五名外为长尾。", "Ranked by estimated sales of products linked to known identities, not actual seller transaction share. Unknown identities are excluded; missing sales limit concentration. Long tail is outside Top 5."),
    "report_policy_note": ("就绪阈值仅控制报告提示，不修改任何语义、路线或发布验收门槛。", "Readiness thresholds only control report warnings, never Semantic, Route or release gates."),
    "snapshot_note": ("受治理数据快照；分析值由报告生成器计算。源数据变化后需重新生成。人工判断栏留空。", "Governed snapshot; analysis is calculated by the report builder. Regenerate after source changes. Human verdicts remain blank."),
    "human_note": ("请逐项独立填写判断与备注。技术验证不代替业务价值判断。", "Enter independent judgments and notes. Technical validation does not decide business value."),
    "sales_basis": ("已分配路线的已观测销量", "Observed sales of assigned Routes"),
    "family_sales_share": ("家族内销量占比", "Within-family sales share"),
    "mechanism_rollup": ("家族内固定方式对比（汇总视图，不与上表相加）", "Within-family mechanism comparison (rollup; not additive to the table above)"),
    "listing_concentration": ("按商品数集中度", "Listing concentration"), "sales_concentration": ("按销量集中度", "Sales concentration"),
    "route_family": ("家族", "Family"), "route_scope": ("路线", "Route"),
    "minimum_route_coverage": ("报告最低路线覆盖提示线", "Report minimum Route coverage"),
    "minimum_sales_coverage": ("报告最低销量证据提示线", "Report minimum sales coverage"),
    "high_unresolved_exposure": ("报告高未分配暴露提示线", "Report high unassigned exposure"),
    "low_review_max": ("低评论上限（含）", "Low-review maximum, inclusive"),
    "price_boundaries": ("价格带边界（美元）", "Price boundaries (USD)"),
    "review_boundaries": ("评论带左闭边界", "Review-band lower boundaries"),
    "new_product_days": ("新品天数窗口", "New-product day windows"),
    "title": ("标题证据覆盖率", "Title evidence coverage"), "structured": ("结构参数覆盖率", "Structured evidence coverage"),
}

_VALUES = {
    "shower caddies": "淋浴置物架", "air fryers": "空气炸锅",
    "no_specific_mechanism": "未定义具体固定方式",
    "wall_mounted": "壁挂家族", "wall_mount": "壁挂", "wall_mount_unspecified": "壁挂（固定方式未指定）",
    "portable": "便携式", "recessed_niche": "嵌入式壁龛", "recessed_or_builtin": "嵌入／内置式",
    "hanging_mount": "悬挂式", "tension_pole": "伸缩顶杆式", "freestanding": "独立落地式",
    "adhesive": "胶粘", "suction_cup": "吸盘", "screw_fixed": "螺丝固定", "mechanical_fastening": "机械固定",
    "corner_shelf": "转角架", "no_installation": "无需安装", "other_structure": "其他结构",
    "product_form": "产品形态", "installation_architecture": "安装架构", "attachment_mechanism": "固定方式",
    "operation_mechanism": "操作机制", "structural_form": "结构形态", "wall": "壁挂固定",
    "programmable": "可编程", "automatic shut-off": "自动断电", "temperature control": "温控", "timer": "定时",
    "dual zone features": "双区功能", "5 sensors": "5个传感器", "unlimited range": "不限范围",
    "stain resistant": "耐污", "4 cooking presets": "4种预设烹饪", "450°f hi-fry technology": "450°F高温炸制技术",
    "digital touch controls": "数字触控", "dishwasher-safe basket and rack": "炸篮和烤架可机洗",
    "adjustable rack": "可调烤架", "large capacity": "大容量", "removable crumb tray": "可拆屑盘", "steam feature": "蒸汽功能",
}

_FACTS = {
    "ROUTE_SALES": ("月销量 {v} 件。", "Monthly sales: {v} units."),
    "ROUTE_SALES_SHARE": ("已分配市场销量占比 {v}。", "Share of assigned-market sales: {v}."),
    "MEDIAN_PRICE": ("价格中位数 {v} 美元。", "Median price: USD {v}."),
    "MEDIAN_REVIEWS": ("评论数中位数 {v}。", "Median reviews: {v}."),
    "LARGEST_SALES_SHARE": ("本路线销量占比最高，为 {v}。", "Largest Route sales share: {v}."),
    "POSITIVE_MOM": ("已观测销量环比增长 {v}。", "Observed sales MoM growth: {v}."),
    "POSITIVE_YOY": ("已观测销量同比增长 {v}。", "Observed sales YoY growth: {v}."),
    "NONPOSITIVE_MOM": ("已观测销量环比 {v}，未呈正增长。", "Observed sales MoM: {v}, not positive."),
    "NONPOSITIVE_YOY": ("已观测销量同比 {v}，未呈正增长。", "Observed sales YoY: {v}, not positive."),
    "GROWTH_COVERAGE_MOM": ("环比可重建证据覆盖率 {v}。", "MoM reconstruction coverage: {v}."),
    "GROWTH_COVERAGE_YOY": ("同比可重建证据覆盖率 {v}。", "YoY reconstruction coverage: {v}."),
    "DEMAND_ABOVE_PAR": ("需求效率 {v}，高于已分配市场均值1。", "Demand efficiency {v}, above assigned-market parity of 1."),
    "DEMAND_AT_OR_BELOW_PAR": ("需求效率 {v}，未高于已分配市场均值1。", "Demand efficiency {v}, not above assigned-market parity of 1."),
    "LOW_REVIEW_DEMAND_SHARE": ("低评论商品贡献该路线已观测销量的 {v}。", "Low-review listings contribute {v} of observed Route sales."),
    "LOW_REVIEW_SELLING_PRODUCTS": ("低评论且月销量大于0的商品有 {v} 个。", "Low-review listings with positive monthly sales: {v}."),
    "BRAND_TOP1": ("已知品牌的头部品牌销量占比 {v}。", "Leading-brand share of known-brand sales: {v}."),
    "SELLER_TOP1": ("已知卖家的头部卖家销量占比 {v}。", "Leading-seller share of known-seller sales: {v}."),
    "BRAND_IDENTITY_COVERAGE": ("品牌身份覆盖率 {v}。", "Brand identity coverage: {v}."),
    "SELLER_IDENTITY_COVERAGE": ("卖家身份覆盖率 {v}。", "Seller identity coverage: {v}."),
    "NEW_PRODUCT_EFFICIENCY": ("首个新品窗口的需求效率 {v}，低于1时不能仅凭新品数量判断进入空间。", "First new-product window demand efficiency: {v}; below 1, entrant count alone does not establish room to enter."),
    "AGE_COVERAGE": ("上架天数证据覆盖率 {v}。", "Listing-age evidence coverage: {v}."),
    "UNSPECIFIED_MOUNT": ("壁挂固定方式证据不足，该路线为兜底，不应解读为螺丝安装。", "Wall fixing is unspecified; this fallback must not be read as screw-mounted."),
    "COMPOUND_DEFINITION": ("路线保留原有复合操作描述，报告未把这些描述拆成新的结构真值。", "The Route retains a compound operation description; the report does not split it into new structural truth."),
    "CATEGORY_ROUTE_COVERAGE": ("全样本商品路线覆盖率为 {v}，结论仅覆盖已分配商品。", "Assigned coverage of all sample listings is {v}; conclusions cover assigned listings only."),
}

QUESTIONS = (
    ("产品路线划分是否符合真实市场结构？", "Does the product-route breakdown reflect the real market structure?"),
    ("Route层级和细分是否容易理解？", "Are Route hierarchy and subsegments easy to understand?"),
    ("是否能清楚比较不同路线的市场大小？", "Can market size be compared clearly across Routes?"),
    ("是否能判断价格带机会？", "Can price-band opportunities be assessed?"),
    ("是否能判断评论/竞争门槛？", "Can review and competition barriers be assessed?"),
    ("是否能看出新品进入空间？", "Can room for new entrants be assessed?"),
    ("是否能识别至少一个值得继续研究的方向？", "Can at least one direction for further research be identified?"),
    ("是否能识别至少一个低优先级方向？", "Can at least one low-priority direction be identified?"),
    ("报告结论是否都有数据依据？", "Are all report conclusions supported by data?"),
    ("与原始Listing表相比，是否明显提高决策效率？", "Does the report materially improve decision efficiency over the raw listing table?"),
    ("如果今天要选品，你是否会使用这份报告决定下一步？", "Would you use this report to decide the next product-research step today?"),
)


def _index(locale):
    if locale not in LOCALES:
        raise ValueError("unsupported locale")
    return LOCALES.index(locale)


def text(key, locale):
    return _PAIRS[key][_index(locale)]


def label(value, locale):
    _index(locale)
    if ":" in value:
        dimension, values = value.split(":", 1)
        return label(dimension, locale) + "：" + label(values, locale)
    if "|" in value:
        return " / ".join(label(v, locale) for v in value.split("|"))
    if "," in value:
        return "、".join(label(v.strip(), locale) for v in value.split(",")) if locale == "zh-CN" else ", ".join(label(v.strip(), locale) for v in value.split(","))
    if locale == "en-US":
        return value.replace("_", " ").title()
    return _VALUES.get(value.casefold(), "未翻译的受治理结构值：" + value)


def route_label(route, locale):
    if route["hierarchy"]["fallback_label"]:
        parts = [label(v, locale) for f in route["features"] if f["dimension"] == "product_form" for v in f["values"]]
        parts.append(label("wall_mount_unspecified", locale))
    else:
        parts = list(dict.fromkeys(label(v, locale) for f in route["features"] for v in f["values"]))
    return route["route_number"] + " " + " / ".join(parts)


def formatted(value, locale, *, percent=False):
    if value is None:
        return text("UNAVAILABLE", locale)
    if type(value) is bool:
        return ("是" if value else "否") if locale == "zh-CN" else ("Yes" if value else "No")
    if isinstance(value, (int, float)):
        return f"{value:.2%}" if percent else f"{value:,.2f}".removesuffix(".00")
    return text(value, locale) if value in _PAIRS else str(value)


def fact_text(fact, locale):
    code = fact["code"]
    percent = any(x in code for x in ("SHARE", "COVERAGE", "MOM", "YOY", "TOP1"))
    return _FACTS[code][_index(locale)].format(v=formatted(fact["value"], locale, percent=percent))


def question(number, locale):
    return QUESTIONS[number - 1][_index(locale)]
