# Calculated Field Specification V0.1

Status: TASK-SP-018D1 audited baseline with TASK-SP-018D2A count-formula disposition

Source matrix: `docs/integration/API_FIELD_COVERAGE_MATRIX_V0.1.md`

Workbook contract: Operator Workbook V0.2

Machine-readable authority: `amazon_product_intelligence.calculations.audit_v0_1`

## 1. Acceptance summary

| Gate | Result |
|---|---:|
| CALCULATED rows mechanically extracted from coverage matrix | 99 |
| `CalculatedFieldSpec` entries | 99 |
| Missing entries | 0 |
| Duplicate entries | 0 |
| Formula-defined | 12 |
| Formula-partial | 0 |
| Formula-unspecified | 1 |
| Business-decision-required | 0 |
| Blocked-by-source-field | 0 |
| Classification-review-required | 86 |
| Production count fields implemented | 7 |

`CALCULATED` in the API coverage matrix means “system-produced”; it does not mean “must be implemented by the generic Calculation Engine.” This audit retains existing layer ownership and marks uncertain classifications instead of duplicating business logic.

## 2. Specification contract

Every one of the 99 entries is an immutable machine-readable `CalculatedFieldSpec` containing:

- `field_id`, Workbook sheet and display name;
- Canonical field/semantic description and category;
- calculation tier, output type, and unit;
- typed direct and calculated dependencies;
- formula status and explicit formula/algorithm reference;
- missing-input, zero, invalid-input, and partial-input policy;
- calculation version and optional rule ID;
- provenance requirement;
- formula confidence and quality implication;
- implementation status and notes.

The Python companion is the complete per-field matrix. This Markdown document is its review index, policy interpretation, dependency audit, and D2 handoff. Automated tests compare its 99 source pairs to the Markdown coverage matrix, so a missing or duplicate field fails the suite.

## 3. Classification

| Tier/category | Count | Interpretation |
|---|---:|---|
| Base deterministic | 16 | Product/rank presentation fields plus recommendation evidence count. Both defined count fields are implemented; the remainder stay in existing owners. |
| Market | 16 | Market overview and exact product-structure aggregation. Three count fields are implemented and four formulas remain explicitly deferred. |
| Competition | 10 | Relationship evidence presentation. Relationship evidence count is implemented; variation evidence count is semantically blocked. |
| Keyword | 11 | Demand/query presentation. Its one defined count field is implemented. |
| Profit/cost | 0 | No existing CALCULATED Workbook field belongs here. |
| Composite score | 14 | Existing Opportunity and Scoring outputs; not reimplemented. |
| AI/decision | 12 | Existing Recommendation outputs; classification review prevents placement in the deterministic engine. |
| Other | 20 | Export, XLSX location, and lineage metadata; not business formulas. |
| **Total** | **99** | |

## 4. Formula and policy classes

| Code | Formula status | Count | Output/type/unit rule | Dependency rule | Missing/zero/invalid/partial rule | Version/provenance/quality | Implementation |
|---|---|---:|---|---|---|---|---|
| `D` | `DEFINED` | 12 | Exact type/unit is listed in the D2 table; currency is always explicit input currency. | Explicit Canonical/System dependency; `Observed Share` has two calculated dependencies. | `REQUIRE_ALL`; known present empty collections may count as zero; zero/False remain data; unsafe inputs block; no partial result. | Rule IDs are stable; seven production count formulas use `v0.1-count-formula`; the other five retain `v0.1-specification`; all Canonical values/evidence/provenance/quality/fingerprints required; confidence `CONFIRMED`. | `IMPLEMENTED` 7; `BLOCKED_BY_SEMANTIC_AMBIGUITY` 1; `READY_FOR_IMPLEMENTATION` but explicitly deferred 4. |
| `U` | `FORMULA_UNSPECIFIED` | 1 | String/no physical unit. | Dated Canonical trend observations. | Never generate text on missing/unknown/invalid input; zero does not imply a trend. | No rule ID; specification version only; confidence `UNSPECIFIED`. | `FORMULA_MISSING`. |
| `R` | `CLASSIFICATION_REVIEW_REQUIRED` | 86 | Existing Workbook schema type; no new unit semantics. | Existing owning-layer record or metadata, typed in the companion spec. | No generic execution is authorized; existing owner keeps its rules and lineage. | No generic rule ID; formula confidence `NOT_APPLICABLE`. | `CLASSIFICATION_REVIEW`; do not duplicate existing logic. |

No field is classified as partial, business-decision-required, or blocked-by-source because the current issue is either missing formula definition (`U`) or incorrect generic-calculation ownership (`R`). Future accepted requirements may change those counts through a versioned audit.

## 5. Calculation Specification Matrix — 99-field index

Legend: `D` = defined D2 candidate; `U` = formula unspecified; `R` = classification review. Full Canonical description, category, output contract, typed dependencies, formula reference, policies, version, provenance, confidence, quality implication, and notes live in the machine-readable companion identified above.

### 01_市场概览 — 7

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 1 | `workbook.market_overview.observed_product_count` | Observed Product Count | D |
| 2 | `workbook.market_overview.data_sources` | Data Sources | R |
| 3 | `workbook.market_overview.evidence_backed_trend` | Evidence-backed Trend | U |
| 4 | `workbook.market_overview.risk_alerts` | Risk Alerts | R |
| 5 | `workbook.market_overview.evidence_quality` | Evidence Quality | R |
| 6 | `workbook.market_overview.analysis_limitations` | Analysis Limitations | R |
| 7 | `workbook.market_overview.snapshot_id` | Snapshot ID | R |

### 02_产品数据库 — 11

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 8 | `workbook.product_database.title_state` | Title State | R |
| 9 | `workbook.product_database.price_state` | Price State | R |
| 10 | `workbook.product_database.rating_state` | Rating State | R |
| 11 | `workbook.product_database.sales_evidence_type` | Sales Evidence Type | R |
| 12 | `workbook.product_database.child_count` | Child Count | D |
| 13 | `workbook.product_database.data_sources` | Data Sources | R |
| 14 | `workbook.product_database.data_state` | Data State | R |
| 15 | `workbook.product_database.conflict_state` | Conflict State | R |
| 16 | `workbook.product_database.time_period_status` | Time / Period Status | R |
| 17 | `workbook.product_database.product_snapshot_id` | Product Snapshot ID | R |
| 18 | `workbook.product_database.output_row_id` | Output Row ID | R |

### 03_TOP产品分析 — 4

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 19 | `workbook.top_products.rank_provider` | Rank Provider | R |
| 20 | `workbook.top_products.rank_status` | Rank Status | R |
| 21 | `workbook.top_products.data_limitations` | Data Limitations | R |
| 22 | `workbook.top_products.rank_observation_id` | Rank Observation ID | R |

### 04_关键词需求分析 — 11

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 23 | `workbook.keyword_demand.search_volume_state` | Search Volume State | R |
| 24 | `workbook.keyword_demand.cpc_state` | CPC State | R |
| 25 | `workbook.keyword_demand.aba_rank_state` | ABA Rank State | R |
| 26 | `workbook.keyword_demand.difficulty_state` | Difficulty State | R |
| 27 | `workbook.keyword_demand.related_product_count` | Related Product Count | D |
| 28 | `workbook.keyword_demand.query_direction` | Query Direction | R |
| 29 | `workbook.keyword_demand.query_status` | Query Status | R |
| 30 | `workbook.keyword_demand.provider` | Provider | R |
| 31 | `workbook.keyword_demand.period_status` | Period Status | R |
| 32 | `workbook.keyword_demand.limitations` | Limitations | R |
| 33 | `workbook.keyword_demand.demand_snapshot_id` | Demand Snapshot ID | R |

### 05_市场竞争证据 — 10

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 34 | `workbook.competition_evidence.relationship_direction` | Relationship Direction | R |
| 35 | `workbook.competition_evidence.observed_relationship` | Observed Relationship | R |
| 36 | `workbook.competition_evidence.observed_relationship_type` | Observed Relationship Type | R |
| 37 | `workbook.competition_evidence.provider` | Provider | R |
| 38 | `workbook.competition_evidence.evidence_count` | Evidence Count | D |
| 39 | `workbook.competition_evidence.evidence_classification` | Evidence Classification | R |
| 40 | `workbook.competition_evidence.variation_evidence_count` | Variation Evidence Count | D |
| 41 | `workbook.competition_evidence.query_status` | Query Status | R |
| 42 | `workbook.competition_evidence.limitations` | Limitations | R |
| 43 | `workbook.competition_evidence.competition_output_row_id` | Competition Output Row ID | R |

### 06_产品结构分析 — 9

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 44 | `workbook.product_structure.product_count` | Product Count | D |
| 45 | `workbook.product_structure.observed_share` | Observed Share | D |
| 46 | `workbook.product_structure.sales_evidence_summary` | Sales Evidence Summary | R |
| 47 | `workbook.product_structure.minimum_comparable_price` | Minimum Comparable Price | D |
| 48 | `workbook.product_structure.maximum_comparable_price` | Maximum Comparable Price | D |
| 49 | `workbook.product_structure.data_state` | Data State | R |
| 50 | `workbook.product_structure.provider_count` | Provider Count | D |
| 51 | `workbook.product_structure.limitations` | Limitations | R |
| 52 | `workbook.product_structure.member_product_ids` | Member Product IDs | D |

### 07_机会分析 — 14

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 53 | `workbook.opportunity_analysis.demand_signal` | Demand Signal | R |
| 54 | `workbook.opportunity_analysis.competition_signal` | Competition Signal | R |
| 55 | `workbook.opportunity_analysis.product_signal` | Product Signal | R |
| 56 | `workbook.opportunity_analysis.signal_classification` | Signal Classification | R |
| 57 | `workbook.opportunity_analysis.missing_evidence` | Missing Evidence | R |
| 58 | `workbook.opportunity_analysis.risk_evidence` | Risk Evidence | R |
| 59 | `workbook.opportunity_analysis.score_factor` | Score Factor | R |
| 60 | `workbook.opportunity_analysis.rule_process_score` | Rule Process Score | R |
| 61 | `workbook.opportunity_analysis.score_status` | Score Status | R |
| 62 | `workbook.opportunity_analysis.score_reference` | Score Reference | R |
| 63 | `workbook.opportunity_analysis.score_interpretation` | Score Interpretation | R |
| 64 | `workbook.opportunity_analysis.explanation_reference` | Explanation Reference | R |
| 65 | `workbook.opportunity_analysis.limitations` | Limitations | R |
| 66 | `workbook.opportunity_analysis.opportunity_output_row_id` | Opportunity Output Row ID | R |

These fields are already owned by Opportunity Intelligence and Opportunity Scoring. `Rule Process Score` therefore remains a reference to the existing audited rule process; D1 does not register a second score formula or copy any existing constants.

### 08_行动建议 — 13

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 67 | `workbook.action_recommendations.recommendation_type` | Recommendation Type | R |
| 68 | `workbook.action_recommendations.recommendation_display_label` | Recommendation Display Label | R |
| 69 | `workbook.action_recommendations.reason` | Reason | R |
| 70 | `workbook.action_recommendations.rule_reference` | Rule Reference | R |
| 71 | `workbook.action_recommendations.policy_status` | Policy Status | R |
| 72 | `workbook.action_recommendations.conflict_status` | Conflict Status | R |
| 73 | `workbook.action_recommendations.missing_requirements` | Missing Requirements | R |
| 74 | `workbook.action_recommendations.evidence_references` | Evidence References | R |
| 75 | `workbook.action_recommendations.evidence_count` | Evidence Count | D |
| 76 | `workbook.action_recommendations.limitations` | Limitations | R |
| 77 | `workbook.action_recommendations.recommendation_record_id` | Recommendation Record ID | R |
| 78 | `workbook.action_recommendations.source_snapshot_id` | Source Snapshot ID | R |
| 79 | `workbook.action_recommendations.operator_output_row_id` | Operator Output Row ID | R |

Recommendation Type, label, reason, rule/policy/conflict state, requirements, limitations, and identities remain Recommendation/Output contracts. Classification as `R` does not make them AI-generated; it states that they do not belong in the generic deterministic calculation package.

### 09_数据审计 — 20

| # | Field ID | Display name | Class |
|---:|---|---|---|
| 80 | `workbook.data_audit.audit_record_id` | Audit Record ID | R |
| 81 | `workbook.data_audit.source_sheet` | Source Sheet | R |
| 82 | `workbook.data_audit.display_row_key` | Display Row Key | R |
| 83 | `workbook.data_audit.excel_row` | Excel Row | R |
| 84 | `workbook.data_audit.display_field` | Display Field | R |
| 85 | `workbook.data_audit.excel_cell` | Excel Cell | R |
| 86 | `workbook.data_audit.export_row_id` | Export Row ID | R |
| 87 | `workbook.data_audit.output_row_id` | Output Row ID | R |
| 88 | `workbook.data_audit.evidence_id` | Evidence ID | R |
| 89 | `workbook.data_audit.provider` | Provider | R |
| 90 | `workbook.data_audit.source_tool` | Source Tool | R |
| 91 | `workbook.data_audit.source_field` | Source Field | R |
| 92 | `workbook.data_audit.raw_evidence_reference` | Raw Evidence Reference | R |
| 93 | `workbook.data_audit.collection_run_id` | Collection Run ID | R |
| 94 | `workbook.data_audit.transformation_run_id` | Transformation Run ID | R |
| 95 | `workbook.data_audit.mapping_version` | Mapping Version | R |
| 96 | `workbook.data_audit.canonical_reference_id` | Canonical Reference ID | R |
| 97 | `workbook.data_audit.lineage_id` | Lineage ID | R |
| 98 | `workbook.data_audit.source_snapshot_id` | Source Snapshot ID | R |
| 99 | `workbook.data_audit.source_bundle_fingerprint` | Source Bundle Fingerprint | R |

All 20 are identity, presentation-location, export, or lineage metadata. They remain deterministic in their current owners, but are not business formulas for the Calculation Engine.

## 6. Dependency audit

| Dependency/implementation state | Count |
|---|---:|
| `IMPLEMENTED` | 7 |
| `BLOCKED_BY_SEMANTIC_AMBIGUITY` | 1 |
| `READY_FOR_IMPLEMENTATION` (explicitly deferred) | 4 |
| `FORMULA_MISSING` | 1 |
| `CLASSIFICATION_REVIEW` | 86 |
| `BLOCKED_BY_DEPENDENCY` | 0 |
| Unknown calculated dependencies | 0 |
| Cycles in audited graph | 0 |
| **Audited fields** | **99** |

The registry also has automated negative tests proving that an unknown calculated dependency and an A → B → C → A cycle fail explicitly. The audited graph itself validates cleanly.

Default existing-owner dependencies are explicit and typed:

| Sheet/domain | Existing owner dependency | Type |
|---|---|---|
| Market overview | `intelligence.opportunity_snapshot` | `SYSTEM_RECORD` |
| Product database/structure presentation fields | `intelligence.product_snapshot` | `SYSTEM_RECORD` |
| TOP products | `operator_output.top_product_row` | `SYSTEM_RECORD` |
| Keyword demand | `intelligence.demand_snapshot` | `SYSTEM_RECORD` |
| Competition evidence | `intelligence.competition_snapshot` | `SYSTEM_RECORD` |
| Opportunity/scoring | `scoring.opportunity_scoring_record` | `SYSTEM_RECORD` |
| Recommendation outputs | `recommendation.recommendation_record` | `SYSTEM_RECORD`; rule-based decision output, with no AI execution in D1 |
| Data audit | `operator_export.lineage_record` | `METADATA` |

These dependencies document ownership; they are not executable generic formulas.

## 7. SP-018D2 defined candidates and D2A disposition

This order is the deterministic registry topological order. It is not a priority or business ranking.

| Order | Field | Tier | Output/unit | Formula | Dependencies | D2A disposition |
|---:|---|---|---|---|---|---|
| 1 | `workbook.action_recommendations.evidence_count` | Base | integer/count | Count distinct evidence references on the exact recommendation record. | `recommendation.evidence_references` | `IMPLEMENTED`; exact governed record collection. |
| 2 | `workbook.competition_evidence.evidence_count` | Competition | integer/count | Count validated relationship-evidence records in the exact group. | `canonical.grouped_relationship_evidence` | `IMPLEMENTED`; count is explicitly not competition strength. |
| 3 | `workbook.competition_evidence.variation_evidence_count` | Competition | integer/count | Count validated explicit variation edges in the exact group. | `canonical.grouped_variation_relationships` | `BLOCKED_BY_SEMANTIC_AMBIGUITY`; current Workbook group exposes evidence records, not one accepted edge-identity collection. |
| 4 | `workbook.keyword_demand.related_product_count` | Keyword | integer/count | Count distinct products in valid relationships for the exact direction/scope. | `canonical.directional_product_keyword_relationships` | `IMPLEMENTED`; direction and scope are explicit. |
| 5 | `workbook.market_overview.observed_product_count` | Market | integer/count | Count distinct validated ProductIdentity values in the explicit snapshot. | `canonical.snapshot_product_identities` | `IMPLEMENTED`; bounded observed set, never total market. |
| 6 | `workbook.product_database.child_count` | Base | integer/count | Count distinct valid explicit child edges for exact parent/marketplace. | `canonical.explicit_child_relationships` | `IMPLEMENTED`; explicit valid edge IDs only. |
| 7 | `workbook.product_structure.maximum_comparable_price` | Market | decimal/explicit currency | Maximum resolved price with identical currency, scope, and period semantics. | `canonical.comparable_price_observations` | `DEFERRED`; no D2A evaluator. |
| 8 | `workbook.product_structure.member_product_ids` | Market | array[string]/n.a. | Sorted distinct validated IDs in exact product-type group. | `canonical.group_product_identities` | `DEFERRED`; no D2A evaluator. |
| 9 | `workbook.product_structure.minimum_comparable_price` | Market | decimal/explicit currency | Minimum resolved price with identical currency, scope, and period semantics. | `canonical.comparable_price_observations` | `DEFERRED`; no D2A evaluator. |
| 10 | `workbook.product_structure.product_count` | Market | integer/count | Count distinct validated IDs in exact product-type group. | `canonical.group_product_identities` | `IMPLEMENTED`; exact group, never market size. |
| 11 | `workbook.product_structure.observed_share` | Market | decimal/ratio | Product Count divided by Observed Product Count. | Calculated fields at orders 10 and 5 | `DEFERRED`; no D2A ratio evaluator. |
| 12 | `workbook.product_structure.provider_count` | Market | integer/count | Count distinct providers retained in group Canonical provenance. | `canonical.group_evidence_provenance` | `IMPLEMENTED`; lineage count, never confidence. |

All 12 retain `DEFINED` formula status. D2A independently accepted seven strict count formulas, kept one count blocked instead of equating variation edges with evidence records, and explicitly deferred the four non-count/aggregation candidates. No deferred or blocked field has an evaluator.

## 8. Explicit non-candidates

- `Evidence-backed Trend`: dated observations exist, but no accepted trend direction, threshold, aggregation window, tie, or text-rendering algorithm exists. Its status is `FORMULA_UNSPECIFIED`.
- Opportunity/score fields: existing Scoring records are projected; no second formula or hidden weight is introduced.
- Recommendation fields: existing rule/policy/recommendation records are projected; they do not migrate into this engine.
- Audit identities and XLSX locations: existing Export/XLSX deterministic metadata remains in its owning layer.
- State, limitation, provider, snapshot, and output-ID projections: owning layers already define their semantics and lineage; classification must be accepted before any migration.

## 9. Formula implementation result

Production count fields implemented through SP-018D2A: **7**.

The seven fields share one provider-neutral evaluator over an already-normalized, authoritative tuple of Canonical or governed record identity strings. It returns the tuple length, including zero for a present empty tuple. It rejects duplicate, malformed, or non-deterministically ordered collections instead of silently establishing a second dedupe authority. Missing, unknown, invalid, and failed-normalization states are blocked by the existing engine before evaluation. Decimal, price, ratio, scoring, AI, and decision formulas remain unchanged and unregistered.
