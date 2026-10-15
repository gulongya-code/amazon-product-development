# SP-041S1 Private Cross-Category Calibration Runbook V1.1

Status: **READY_FOR_PRIVATE_EXECUTION — REAL MULTI_CATEGORY ASSETS REQUIRED**

## 1. Purpose

Provide a repeatable, privacy-safe operator/Codex procedure for the remaining Issue #55 hard gate.

This runbook does not change production semantics. It defines how to use multiple real SellerSprite-style market exports to validate the frozen V1.1 semantic architecture without committing private market data.

## 2. Required starting state

- Branch: `codex/task-sp-041s1-cross-category-semantic-calibration`
- Baseline ancestry must include `6446c36618180d6a4b32b58c6801efd4f9f916fa`.
- Workspace/staging clean before calibration-related code or report changes.
- Real market workbooks/CSVs remain outside the Git repository.
- Existing SP-041A/B/C/D regressions remain the compatibility baseline.
- SP-041E remains frozen.

If the workspace contains unexpected changes, stop rather than reset/stash/discard them.

## 3. Qualifying calibration data

Use `4–6` materially different product categories in total, with approximately `200–500` listings for each added category where practical.

The corpus should collectively test:

1. installation/structure-heavy semantics;
2. capacity + operation semantics;
3. compatibility/accessory/replacement-heavy semantics;
4. powered/electronic operation semantics;
5. size/material-heavy semantics;
6. bundle/multipack semantics.

A category is useful only if its export contains enough listing-grain evidence to compare Title and structured/dedicated fields. A keyword-only, advertising-only, single-SKU or summary-only workbook does not qualify as a market semantic calibration asset.

Do not force all six patterns if the available real market data cannot support them. Record the uncovered semantic patterns explicitly.

## 4. Private asset rules

Never commit, log to repository artifacts, or paste into GitHub Issues:

- ASINs;
- listing Titles;
- brands;
- sellers;
- prices tied to individual listings;
- raw rows;
- source workbook/CSV bytes;
- private absolute paths;
- user/customer identifiers;
- API credentials/tokens.

Allowed repository evidence is limited to aggregate counts/rates, version/fingerprint identifiers that cannot reconstruct private rows, methodology, rule/profile versions and bounded privacy-safe operator conclusions.

## 5. Calibration pipeline

For each category perform the following logical stages:

`real external export`

`-> SP-041B governed market dataset`

`-> evidence extraction by source class`

`-> candidate normalized attribute/value observations`

`-> Universal Semantic Role projection candidate`

`-> evidence relationship classification`

`-> Product Role candidate`

`-> route-critical evidence eligibility candidate`

`-> privacy-safe aggregate matrix`

S1 may use minimal deterministic calibration tooling, but must not silently replace accepted production parser/route behavior before the calibration conclusions are approved.

## 6. Required aggregate matrix

For each category and Semantic Role/dimension report at least:

```text
accepted_listing_count
role_or_dimension
eligible_listing_count

title_observed_count / rate
structured_observed_count / rate
both_observed_count / rate
agreement_count / rate
complementary_count / rate
compatible_multi_value_count / rate
true_conflict_count / rate
route_critical_conflict_count / rate
unavailable_count / rate

optional_bullet_highlight_observed_count / rate
product_role_governed_count / rate
route_critical_evidence_available_count / rate
```

Every rate must carry its denominator definition. Missing evidence must not be included as zero-valued facts.

## 7. Relationship classification review

Privately review a bounded sample from each relationship class, especially:

- Title-only evidence;
- structured-only evidence;
- apparent conflicts;
- compatible multi-value evidence;
- Product Role ambiguity;
- route-critical conflict.

The operator review should answer:

1. Are the two pieces of evidence actually discussing the same semantic dimension?
2. Can both values coexist on the same physical product?
3. Is the difference merely marketing wording or a real structural difference?
4. Would this conflict change Product Identity, Product Role or the primary product architecture?
5. Is a source-preference rule justified for this dimension across the category, or only for one example?

Do not commit the examples themselves; commit only aggregate review outcomes.

## 8. Product Role review

For each category calculate privacy-safe counts/rates for:

- `PRIMARY_PRODUCT`;
- `ACCESSORY`;
- `REPLACEMENT`;
- `REFILL`;
- `BUNDLE`;
- `UNKNOWN`;
- genuine role-level `REVIEW_REQUIRED`.

Privately verify bounded samples so that:

- included accessories do not turn a primary product into an accessory;
- replacement compatibility wording is not mistaken for a primary product;
- pack count alone does not force `BUNDLE`;
- missing non-critical facets do not affect Product Role.

## 9. Route-eligibility calibration

For each category record which Universal Semantic Roles appear to be:

- `CORE`;
- `SECONDARY`;
- `FACET_ONLY`;
- `IGNORE`.

The default expectation is that Material, Functional Feature, Cosmetic and Quantity remain facet-only. A promotion must include cross-listing evidence that the dimension materially changes product architecture/use rather than merely differentiating a variant or selling point.

Do not define final route names during this step.

## 10. Privacy-safe category summary

Commit one sanitized summary per category with a neutral calibration identifier rather than private product content when necessary.

Suggested structure:

```text
calibration_category_id
category_semantic_pattern
accepted_listing_count
source_field_coverage_summary
semantic_role_coverage_summary
evidence_relationship_summary
product_role_distribution
route_eligibility_decisions
unvalidated_dimensions
calibration_fingerprint
operator_review_status
```

If a public/non-sensitive category label is approved for documentation, it may be used; otherwise use a neutral identifier such as `CAL_CATEGORY_01`.

## 11. Cross-category synthesis

After all available categories are processed, compare:

- which Semantic Roles were needed in every category;
- which roles were category-conditional;
- which evidence sources were reliable for which semantic dimensions;
- where Title commonly supplements structured evidence;
- where structured fields are necessary for exact facts;
- where apparent source disagreement is mostly complementary rather than conflicting;
- which dimensions consistently behave as facets;
- which dimensions can legitimately become route-core in some categories;
- which Product Role failure modes repeat across categories.

Only then propose V2 numeric acceptance thresholds.

## 12. V2 threshold derivation

For each proposed threshold document:

```text
metric_name
observed_range_across_categories
median_or_relevant_distribution
proposed_gate
business_reason
false_positive_risk
false_negative_risk
categories_that_stress_the_gate
```

Do not set a threshold solely because it is a round number or because the existing private category happened to produce that value.

Required gate families include:

- Product Role coverage;
- key Semantic Role coverage;
- true-conflict / route-critical-conflict behavior;
- route assignment coverage;
- unclassified/review-required rates;
- route fragmentation/small-route rate;
- candidate route market coverage;
- bounded human intra-route consistency;
- candidate material distinctness;
- deterministic replay/fingerprint stability;
- zero generic-engine code changes for a newly calibrated category.

## 13. LLM usage during calibration

Prefer deterministic extraction and aggregate analysis first.

If LLM is used during S1, restrict it to candidate discovery/mapping proposals and record:

- model identifier;
- prompt/version identifier;
- purpose;
- category calibration ID;
- input tokens;
- output tokens;
- accepted/rejected proposal counts.

LLM output must not silently mutate production profiles or become authoritative route membership.

## 14. Required local validation before S1 PASS

After any calibration tooling/report changes:

1. focused SP-041S1 tests for any new tooling;
2. SP-041A/B/C/D focused regressions;
3. affected Product Intelligence / Market Report / pipeline regressions;
4. full pytest;
5. `git diff --check`;
6. secret-pattern scan;
7. private-path scan;
8. ASIN/raw-market-row leakage scan for new repository delta;
9. confirm no new XLSX/CSV/private-market asset entered Git;
10. confirm branch workspace/staging clean after commit/push.

Known baseline exceptions may only be carried forward if reproduced unchanged from the required baseline and documented explicitly.

## 15. Promotion rule

SP-041S1 may be promoted to:

`PASS — CROSS_CATEGORY_SEMANTIC_CALIBRATION_V1_1`

only after:

- multiple materially different real categories have been calibrated, or remaining coverage gaps are explicitly bounded and accepted;
- aggregate evidence matrices exist;
- Product Role and Universal Semantic Role model survives bounded operator review;
- route-eligible versus facet-only policy is supported by real evidence;
- V2 quantitative acceptance gates are derived from observed distributions;
- reuse/license decisions remain valid;
- local validation and privacy scans pass;
- no private market data is committed.

Until then the authoritative status is:

`IN_PROGRESS — PRIVATE_MULTI_CATEGORY_CALIBRATION_REQUIRED`
