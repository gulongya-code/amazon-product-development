# Canonical Provider Mapping Examples V0.1

Status: representative design examples only; not a complete adapter specification  
Task: TASK-SP-003

## 1. Evidence basis

These examples were checked against saved raw MCP responses and audit reports under:

- `research/xiyou_capability_audit_v0_1/`
- `research/sorftime_product_intelligence_audit_v0_1/`

Provider names and source fields appear only in mapping/provenance. Canonical contracts remain provider-independent.

## 2. Product fields

| Source | Source field | Canonical kind | Canonical dimension/metric | Evidence type | Notes |
|---|---|---|---|---|---|
| XiYou product info | `title` | `ProductFactObservation` | `title` | `OBSERVED` | ASIN scope; observed time absent. |
| Sorftime product detail | `title` | `ProductFactObservation` | `title` | `OBSERVED` | ASIN scope; observed time absent. |
| XiYou product info | `price` + `currency` | `MetricObservation` | `price` | `OBSERVED` | Parse numeric string; retain raw value. |
| Sorftime product detail | `price` | `MetricObservation` | `price` | `OBSERVED` | Currency comes from marketplace/context only if established; otherwise unit semantic unconfirmed. |
| XiYou product info | `stars` | `MetricObservation` | `rating` | `OBSERVED` | Five-star scale; raw string retained. |
| Sorftime product detail | `star_rating` | `MetricObservation` | `rating` | `OBSERVED` | Five-star scale. |
| XiYou product info | `ratings` | `MetricObservation` | `review_count` | `OBSERVED` | Integer count. |
| Sorftime product detail | `review_count` | `MetricObservation` | `review_count` | `OBSERVED` | Integer count. |
| Sorftime product detail | `brand` | `ProductFactObservation` | `brand` | `OBSERVED` | Brand is a mutable fact, not identity. |
| Sorftime product detail | `parent_asin` | `ProductFactObservation` | `parent_product_relationship` | `OBSERVED` | Not part of child identity. |
| Sorftime product detail | `attributes.Material` | `ProductFactObservation` | `material` | `OBSERVED` | Structured attribute; source-only evidence is allowed. |
| Sorftime product detail | `attributes.Inlet Connection Size` | `ProductFactObservation` | `inlet_connection_size` | `OBSERVED` | Normalize only with confirmed unit semantics. |
| Sorftime product detail | `description` | `ProductFactObservation` | `description` | `OBSERVED` | Keep as textual evidence; no profile extraction in V0.1. |

### Example: rating observations, not overwrite

```json
[
  {
    "observation_kind": "METRIC",
    "metric": "rating",
    "evidence_type": "OBSERVED",
    "value": {"presence_status": "PRESENT", "raw_value": "4.6", "normalized_value": 4.6, "value_type": "NUMBER", "unit": {"dimension": "RATING", "unit_code": "stars_5", "unit_system": "DOMAIN"}, "normalization_status": "NORMALIZED", "semantic_status": "CONFIRMED"},
    "provenance": {"provider": "xiyou", "source_tool": "batch_product_info", "source_field": "stars"}
  },
  {
    "observation_kind": "METRIC",
    "metric": "rating",
    "evidence_type": "OBSERVED",
    "value": {"presence_status": "PRESENT", "raw_value": 4.1, "normalized_value": 4.1, "value_type": "NUMBER", "unit": {"dimension": "RATING", "unit_code": "stars_5", "unit_system": "DOMAIN"}, "normalization_status": "NORMALIZED", "semantic_status": "CONFIRMED"},
    "provenance": {"provider": "sorftime", "source_tool": "get_product_detail", "source_field": "star_rating"}
  }
]
```

Assessment: `MATERIAL_DIFFERENCE`; preserve both, resolved value null.

## 3. Orders and sales estimates

| Source | Source field | Canonical metric | Period | Scope | Semantic status |
|---|---|---|---|---|---|
| XiYou orders | `orders` | `orders` | `ROLLING_30_DAYS` from tool contract | `SCOPE_UNCONFIRMED` if parent/child grain is not documented | `SEMANTICS_UNCONFIRMED` for estimation method |
| Sorftime product detail | `monthly_sales_volume` | `estimated_monthly_sales` | `CALENDAR_MONTH` or `UNKNOWN` unless documentation proves window | ASIN, subject to provider documentation | Provider estimate |
| Sorftime variation | `SalesAmount` | `estimated_sales_volume` | recent page capture within 15 days per returned documentation | child variation | `CONFIRMED` as sales volume; field name does not imply currency amount |

XiYou `orders` and Sorftime `monthly_sales_volume` are not aliases. For B0GTQZ9C19, `1000` orders versus `1125` monthly sales is `NOT_DIRECTLY_COMPARABLE`, not a 12.5% difference. The same applies to B0G2Q22W6D (`100` vs `333`).

## 4. Product attributes and pressure conflict

For B0G2Q22W6D, map three independent observations:

| Source location | Raw value | Canonical dimension | Unit handling |
|---|---|---|---|
| `attributes.Maximum Operating Pressure` | `1000 pascal` | `maximum_operating_pressure` | number 1000, unit `Pa`, normalized if parse is valid |
| title text | `1000 WOG` | `maximum_operating_pressure` | number 1000, unit `WOG`, normalization `AMBIGUOUS` |
| description text | `1000 PSI` | `maximum_operating_pressure` | number 1000, unit `psi`, normalized unit only; no cross-source resolution |

These are not three copies of numeric `1000`. Emit `UNIT_CONFLICT`, semantic quality issue, and `UNRESOLVED`. The title/description mappings identify text spans as evidence; they do not implement general extraction logic.

## 5. Keyword metrics

| XiYou source field | Canonical kind | Metric | Evidence type / time |
|---|---|---|---|
| `abaReport.weeklySearchVolume` | `KeywordMetricObservation` | `search_volume` | `PROVIDER_ESTIMATE`; use report period `2026-08-02` to `2026-08-08` in sample. |
| `abaReport.searchFrequencyRank` | `KeywordMetricObservation` | `aba_search_frequency_rank` | `OBSERVED` or provider-reported rank per documentation. |
| `competitiveDifficulty` | `KeywordMetricObservation` | `competition_difficulty` | `PROVIDER_ESTIMATE`; provider scale must be documented. |
| `costPerClick.value` | `KeywordMetricObservation` | `cpc` | Provider estimate; currency unit required. |
| `costPerClick.min/max` | range fields on keyword metric | `cpc` | Preserve bounds, not only midpoint. |

For `plastic spoons`, the sample weekly search volume is `41910`, search frequency rank `2922`, and report window is explicit. For industrial valve keywords where `abaReport` and CPC/difficulty are null, encode `EXPLICIT_NULL`; do not produce zeros.

## 6. Keyword-ASIN relationships

### Reverse: product to keyword

XiYou reverse keyword data maps to `ProductKeywordRelationshipObservation` with:

- `direction = PRODUCT_TO_KEYWORD`;
- keyword raw text and normalized identity;
- `relationship_type = RANK` and/or `TRAFFIC`;
- `channel = ORGANIC` for position `or`, `SPONSORED` for position `sb`;
- page, page rank, total rank, and `rankTime` retained;
- traffic summary retained as metric evidence with provider semantics.

### Forward: keyword to product

XiYou forward candidate data maps to the same relationship contract with `direction = KEYWORD_TO_PRODUCT`. A populated `plastic spoons` result produces candidate/rank relationships. The `1/2 ball valve` response with `list=[]` and `total=0` produces a query-result observation:

```json
{
  "direction": "KEYWORD_TO_PRODUCT",
  "query_result_status": "EMPTY_OBSERVATION",
  "value": {"presence_status": "QUERY_RETURNED_EMPTY", "raw_value": [], "normalized_value": null, "value_type": "LIST", "unit": null, "normalization_status": "NOT_APPLICABLE", "semantic_status": "CONFIRMED"}
}
```

When reverse evidence is populated for the same product-keyword pair, emit `directional_status = ONE_SIDED_REVERSE` and top-level `DIRECTIONAL_CONFLICT`. Do not infer `market_size = 0`.

## 7. BSR, variations, and reviews

### BSR

XiYou BSR trend rows map to one `MetricObservation` per date/category pair:

- `metric = bsr`;
- category context includes category ID, name, and root flag;
- `observed_at` uses the returned date only to its actual precision;
- scope is ASIN and category context is explicit;
- `dateRangeNotice` remains provenance/documentation metadata.

### Variations

Sorftime variation rows map to product relationship/fact observations: parent product, child ASIN, variation property, item index/total, and a distinct estimated sales-volume metric. `SalesAmount = -1` means no recent captured value per provider documentation; it must map to `UNKNOWN`/provider sentinel handling, not negative sales and not zero.

### Reviews

Sorftime review fields map as follows:

| Source | Canonical review field |
|---|---|
| ASIN request context | product identity |
| provider record identity/index | provider review identity |
| `star_rating` | rating |
| `title` | title |
| `content` | body |
| `review_date` | review date, parsed from `yyyyMMdd` |
| `variant_attribute` | variant |
| unavailable field | helpful votes with `MISSING`, never `0` |

## 8. Cross-provider fixture summary

| Case | Evidence | Result |
|---|---|---|
| Title | XiYou/Sorftime equivalent title | `CONSISTENT` |
| Rating | 4.6 vs 4.1 | `MATERIAL_DIFFERENCE`, unresolved |
| Review count | 75 vs 78 | `MINOR_DIFFERENCE`, field non-blocking |
| Demand metric | last-30-day orders vs monthly sales | `NOT_DIRECTLY_COMPARABLE` |
| Pressure | 1000 pascal/WOG/PSI | `UNIT_CONFLICT` + semantic issue, unresolved |
| Direction | reverse populated, forward empty | `DIRECTIONAL_CONFLICT`; no empty-market inference |
| Attribute | only Sorftime structured material | `ONE_SOURCE_ONLY`, valid |

## 9. Mapping rules validated by the examples

1. Map documented semantics, not source spelling.
2. Preserve raw values and source fields in provenance.
3. Keep observed time unknown when absent; retrieval time is not a substitute.
4. Preserve period, scope, unit, direction, and channel.
5. Emit separate observations before conflict assessment.
6. Treat null, missing, empty results, provider sentinels, and zero distinctly.
7. A provider can be removed or replaced without changing the canonical contracts.
