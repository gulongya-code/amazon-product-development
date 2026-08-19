# Opportunity Result → Operator Workbook Mapping V0.1

- Document version: `opportunity-result-workbook-mapping-v0.1`
- Target contract: `OpportunityResult` V0.1
- Workbook contract: Operator Workbook V0.2, 9 sheets / 157 fixed fields

## 1. Scope and status meanings

This document prepares a future Workbook Adapter mapping. It does not change the
Workbook schema, write workbook cells, redefine any of F001–F157, or authorize an
Opportunity Score.

| Status | Meaning |
|---|---|
| `AVAILABLE` | An existing Workbook field has compatible type and business meaning. A future adapter may project the result without redefining that field. |
| `MAPPING_REQUIRED` | A nearby existing field may carry a governed projection, but ownership, formatting, or semantic compatibility must be approved before implementation. |
| `UNAVAILABLE` | No existing field can safely carry the result, or the value is intentionally unavailable in V0.1. The adapter must not substitute another field. |

## 2. Result-field mapping

| Result field | Workbook field | Status | Notes |
|---|---|---|---|
| `result_status` | F117 `Score Status` | `MAPPING_REQUIRED` | F117 currently describes the existing rule-process calculation. It must not be silently repurposed; an explicit versioned adapter decision is required. |
| `score_value` | F116 `Rule Process Score` | `UNAVAILABLE` | `score_value` is always `null`. F116 keeps its existing process-score meaning and must not be populated from this result. |
| `score_version` | None | `UNAVAILABLE` | V0.1 remains `BUSINESS_DECISION_REQUIRED`; F118 is a calculation reference, not a version field. |
| `dimension_results[DEMAND_POTENTIAL]` | F109 `Demand Signal` | `MAPPING_REQUIRED` | F109 can display neutral demand evidence text, but a future adapter must define status/evidence formatting without generating a demand conclusion. |
| `dimension_results[COMPETITION_ACCESSIBILITY]` | F110 `Competition Signal` | `MAPPING_REQUIRED` | F110 can display neutral evidence only; it must not become a high/low competition label. |
| `dimension_results[PRODUCT_ECONOMICS_READINESS]` | F111 `Product Signal` | `MAPPING_REQUIRED` | The current field is broader than economics readiness. A governed projection is required and must not imply profitability. |
| `confidence` | None | `UNAVAILABLE` | No existing fixed field has the same structured qualitative-confidence contract. Confidence must not be flattened into a score. |
| `completeness` | F112 `Signal Classification`; F121 `Limitations` | `MAPPING_REQUIRED` | Existing fields can expose selected labels/limitations, but they cannot carry the full structured completeness record without an approved projection. |
| `risks` | F114 `Risk Evidence` | `AVAILABLE` | Compatible neutral risk/limitation inventory. Preserve risk IDs and evidence references; do not add severity, probability, or penalty. |
| `missing_inputs` | F113 `Missing Evidence` | `AVAILABLE` | Compatible missing-input list. Preserve missing identifiers; never convert missing values to zero. |
| `explanations[].summary` | F119 `Score Interpretation` | `MAPPING_REQUIRED` | Only verbatim dimension explanations may be projected. F119 currently belongs to the process-score view and cannot be overwritten without governance. |
| `explanations[].explanation_id` | F120 `Explanation Reference` | `MAPPING_REQUIRED` | The field type is compatible, but row-grain and dimension-to-row mapping remain to be defined. |
| `configuration` | F121 `Limitations` | `MAPPING_REQUIRED` | A future adapter may expose `BUSINESS_DECISION_REQUIRED` as a limitation; the structured configuration cannot be embedded here. |
| Opportunity product identity | F108 `Product` | `UNAVAILABLE` | `OpportunityResult` receives dimension results and contains no product identity. A future adapter needs an external governed identity join; evidence must not be used to guess it. |
| Opportunity output identity | F122 `Opportunity Output Row ID` | `UNAVAILABLE` | The aggregator does not create Operator Output row IDs. This is owned by the downstream Operator Output layer. |

## 3. Provenance mapping

| Result field | Workbook field | Status | Notes |
|---|---|---|---|
| `provenance[].provenance_id` | F155 `Lineage ID` | `MAPPING_REQUIRED` | Type is compatible, but the future output/export lineage record must explicitly bind the opportunity result to the displayed row. |
| `provenance[].canonical_field` | F154 `Canonical Reference ID` | `MAPPING_REQUIRED` | A field name is not automatically a Canonical record ID. The adapter requires the owning Canonical reference. |
| `provenance[].source` | F147 `Provider` | `AVAILABLE` | Project the declared source identity only; credentials are never included. |
| `provenance[].source_field` | F149 `Source Field` | `AVAILABLE` | Exact source locator can be preserved unchanged. |
| `provenance[].raw_evidence_id` | F150 `Raw Evidence Reference` | `AVAILABLE` | Reference only. Raw payload must never be copied into the Workbook. |
| `provenance[].snapshot_id` | F156 `Source Snapshot ID` | `AVAILABLE` | Preserve the immutable source snapshot identifier. |
| `provenance[].timestamp` | None | `UNAVAILABLE` | No existing audit field has the same timestamp meaning. Do not substitute collection-run or Excel-render time. |
| Source operation/tool | F148 `Source Tool` | `UNAVAILABLE` | The current result provenance does not carry a separate source-tool field; it must not be inferred from the source name. |

F146–F157 remain the existing audit fields. The future adapter must create one-to-many
lineage rows where required; it must not compress multiple providers, snapshots, or
evidence records into a fabricated single source.

## 4. Adapter boundary

The future Workbook Adapter may only:

1. project existing result values into fields marked `AVAILABLE`;
2. implement a versioned, approved projection for `MAPPING_REQUIRED` rows;
3. emit an explicit unavailable state for `UNAVAILABLE` rows;
4. retain dimension, evidence, risk, explanation, and provenance references;
5. keep `score_value` blank/null and configuration at
   `BUSINESS_DECISION_REQUIRED`.

It must not calculate a score, derive a recommendation, write “值得开发”, alter the
Workbook row grain, or modify the 157-field schema.
