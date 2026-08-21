# Market Overview

| Field | Value |
|---|---|
| Category | dog water bottle |
| Marketplace | US |
| Category Scope | Amazon US > Pet Supplies > Dog Travel Water Bottles |
| Sample Size | 100 |
| Unique ASIN Count | 100 |
| ASIN Coverage | 25.0% |
| Data Window | last7days |
| Window Start | 2026-08-10T00:00:00Z |
| Window End | 2026-08-16T23:59:59Z |
| Report ID | `market-report:2e16daae9cffb31c8cd5ec1f49570054f99f10351a9f3320d57d215e3af1f0f2` |
| Report Version | `market-report-v0.1` |
| Pipeline Version | `market-report-pipeline-v0.1` |

# Buyer Need Analysis

| Buyer Need | Share | Confidence | Validation Status | Evidence |
|---|---:|---|---|---|
| Outdoor Portability | 27.0% | UNKNOWN | V0.3_STABLE | buyer-need:portable-001, buyer-need:portable-002 |
| Leak Prevention | 19.0% | UNKNOWN | V0.3_STABLE | buyer-need:leak-001, buyer-need:leak-002 |

# Competition Analysis

| Indicator | Availability | Value | Evidence |
|---|---|---|---|
| Competition Level | AVAILABLE | MEDIUM | competition-level:set-001 |
| ASIN Count | AVAILABLE | 100 | calculation:observed-product-count |
| Brand Count | AVAILABLE | 42 | brand-observation:set-001 |
| Price Distribution | AVAILABLE | {"maximum":"39.99","mean":"18.72","median":"16.99","minimum":"6.99"} | price-observation:set-001 |
| Rating Distribution | AVAILABLE | {"maximum":"5.0","mean":"4.42","median":"4.5","minimum":"3.1"} | rating-observation:set-001 |
| Review Distribution | AVAILABLE | {"maximum":"45000","mean":"2380","median":"620","minimum":"8"} | review-count-observation:set-001 |
| Competition Concentration | AVAILABLE | {"top_5_asin_share":0.31,"top_5_brand_share":0.38} | competition-concentration:set-001 |

# Opportunity Assessment

| Field | Value |
|---|---|
| Opportunity Score | 82.0 |
| Confidence | LOW |
| Score Status | CALCULATED_PARTIAL |
| Policy | `opportunity-score-policy-v0.1` |
| Policy Fingerprint | `sha256:fixture-policy-fingerprint` |

## Explanation

| Dimension | Score | Contribution | Maximum | Explanation | Evidence |
|---|---:|---:|---:|---|---|
| Competition Favorability | 75.0 | 15.0 | 20.0 | Existing competition evaluation reports medium concentration. | competition-concentration:set-001 |
| Demand Strength | 83.333333 | 25.0 | 30.0 | Strong cohort recurrence in the existing Buyer Need output. | buyer-need:portable-001 |
| Economic Evidence | 66.666667 | 10.0 | 15.0 | Price evidence exists; sales and revenue remain partial. | price-observation:set-001 |
| Evidence Confidence | 100.0 | 10.0 | 10.0 | The score preserves source confidence independently from score. | cohort:dog-water-bottle:100 |
| Supply Gap | 88.0 | 22.0 | 25.0 | Existing gap evaluation reports a strong supply gap. | gap-evidence:portable-leak-proof |

### Risks

- Sales Evidence Partial

# Data Limitations

- ASIN coverage is cohort recurrence, not Demand Share.
- ASIN_COVERAGE_IS_COHORT_RECURRENCE_NOT_DEMAND_SHARE
- Economic evidence is partial.
- Per-cluster confidence is unavailable in the V0.3 validation snapshot.
- SOURCE_CLUSTER_CONFIDENCE_UNAVAILABLE

## Evidence and Provenance

| Source Module | Source Version | Source Record | Availability | Evidence | Limitations |
|---|---|---|---|---|---|
| market_analysis | market-analysis-v0.1 | market-analysis:fixture-dog-water-bottle | AVAILABLE | price-observation:set-001 | None recorded. |
| opportunity_scoring | opportunity-scoring-integration-v0.1 | evidence-based-opportunity-score:fixture-dog-water-bottle | PARTIAL | buyer-need:leak-001, buyer-need:portable-001, cohort:dog-water-bottle:100, competition-concentration:set-001, gap-evidence:portable-leak-proof, opportunity-reference:buyer-needs, opportunity-reference:economic, price-observation:set-001 | Economic evidence is partial. |
| economic_evidence | opportunity-scoring-integration-v0.1 | economic-evidence:fixture-dog-water-bottle | AVAILABLE | opportunity-reference:economic, price-observation:set-001 | SALES_AND_REVENUE_EVIDENCE_PARTIAL |
| category_product_map | category-product-map-v0.1 | category-product-map:fixture-dog-water-bottle | AVAILABLE | attribute-evidence:capacity-set-001, attribute-evidence:material-set-001 | None recorded. |
| buyer_need_map | opportunity-scoring-integration-v0.1 | buyer-need-analysis:fixture-dog-water-bottle | AVAILABLE | buyer-need:leak-001, buyer-need:portable-001, opportunity-reference:buyer-needs | None recorded. |
| market_report_pipeline_input | market-report-pipeline-v0.1 | validation-fixture:market-report:dog-water-bottle | AVAILABLE | clean-run:dog-water-bottle:100, cohort:dog-water-bottle:100 | None recorded. |
| buyer_need_analysis | buyer-need-intent-rules-v0.3 | buyer-need-analysis:fixture-dog-water-bottle | AVAILABLE | buyer-need:leak-001, buyer-need:leak-002, buyer-need:portable-001, buyer-need:portable-002 | None recorded. |
| competition_analysis | competition-analysis-v0.1 | competition-analysis:fixture-dog-water-bottle | AVAILABLE | rating-observation:set-001, review-count-observation:set-001 | None recorded. |
