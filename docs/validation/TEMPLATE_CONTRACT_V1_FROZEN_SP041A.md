# TASK-SP-041A Completion Report

Date: 2026-08-26
Issue: `#51 — Operator Template Contract Freeze & Public Reuse Gate`
Verdict: **PASS — TEMPLATE_CONTRACT_V1_FROZEN**

## A. Required baseline / runtime / workspace

- Required and verified starting HEAD:
  `a0cf42685c75d5f611ce40c99b96d8cb731d45ba`.
- Dedicated branch: `codex/task-sp-041a-template-contract-freeze`.
- Workspace and staging were clean before audits and implementation.
- Runtime: Python 3.14.4, pytest 9.1.1.
- Planning documents were read with `git show` from
  `origin/codex/planning-hybrid-market-analysis-v1`; planning history was not
  merged or cherry-picked.

## B. Internal reuse audit

Completed before code changes. Reused internal `JsonContract`,
`canonical_json`, deterministic fingerprint conventions, immutable/fail-closed
model patterns, and the existing workbook safety approach. Existing V0.2
Operator Workbook, Market Report, Evidence/Provenance, and Production Pipeline
semantics were not modified. Full details:
`docs/engineering/SP_041A_INTERNAL_REUSE_AUDIT.md`.

## C. Public GitHub reuse / license audit

Completed before code changes. Selected only dependency reuse of the already
installed MIT `openpyxl` workbook APIs and formula tokenizer. No public code
was copied or adapted; no new attribution file or dependency was required.
MIT/BSD candidates outside task scope were rejected or deferred; no-license,
EUPL, and All Rights Reserved candidates were not copied. Full queries,
candidates, files/components, classifications, obligations, and tests:
`docs/engineering/SP_041A_PUBLIC_GITHUB_REUSE_AUDIT.md`.

## D. Files added

- immutable contract models, frozen schema, and read-only auditor under
  `src/amazon_product_intelligence/operator_template_contract/`;
- a sanitized stdout-only audit command at
  `scripts/audit_operator_template_v1.py`;
- normative Markdown and machine-readable JSON contracts under
  `docs/contracts/`;
- internal/public reuse audits under `docs/engineering/`;
- synthetic in-memory workbook tests under `tests/`.

No existing Production Pipeline, Market Report V0.1/V0.2, provider, or workbook
business-logic file was modified.

## E. 11+4 workbook contract

The exact 11 visible names/order and four ordinary hidden support sheets are
frozen. The validator rejects missing/extra/renamed sheets, visible-order drift,
hidden-state drift, and `veryHidden` sheets.

## F. 66-field raw-source contract

All 66 exact names are frozen and individually classified `CORE`, `OPTIONAL`,
or `OUT_OF_SCOPE`. Validation is set-based by header name, not column index;
duplicate, missing, or unexpected headers fail closed. `LQS` and `SP广告` are
out of scope; CPF绿标 is a non-header MVP exclusion. Provider `毛利率` remains
reference only. Missing/blank/NA/parse failure is explicitly never numeric 0.

## G. Formula census / fingerprints / dependencies

- Planning census frozen as approximately 26,738 formulas:
  `3 + 1,150 + 2 + 961 + 108 + 24,514` on the six observed formula sheets.
- The read-only auditor emits exact formula counts and per-sheet SHA-256
  fingerprints from sorted exact-formula/token records.
- Required named ranges: `PivotSourceKeyword`, `PivotSourceCompetitor`,
  `可选蓝色参数`.
- Required AutoFilters: `竞品数据`, `关键词1—数据源`, `原始数据源`.
- Tables and pivots are inventoried when present.
- Repeated synthetic audit and formula-change tests prove determinism and
  sensitivity.

## H. Hard-coded threshold inventory

The machine contract inventories target margin, price bands, Review bands,
review-rate bands, FBA bands, listing-age bands, new-product window, category
semantic rules, and provider gross margin. Formula numeric operands are
extracted with `openpyxl.formula.Tokenizer`; cell-reference row numbers are not
misclassified as thresholds. The known default target margin is `0.30`.

Exact private-workbook values not present in authoritative planning documents
remain explicitly marked
`EXTERNAL_REFERENCE_WORKBOOK_VALUE_REQUIRES_LOCAL_AUDIT`; no value was guessed.

## I. Formula/config/code-mirror classification

- category-neutral support formulas: `REUSE_AS_FORMULA`;
- hard-coded numeric rules: `MOVE_TO_CONFIG`;
- JSON/AI market and decision metrics:
  `IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL`;
- provider gross margin and current value-only price results: `DEPRECATED`.

SP-041A does not implement the SP-041F price model.

## J. User-data/template safety

No original template, real listing row, ASIN dataset, or generated real-data
snapshot was added. Tests construct a minimal synthetic workbook in memory.
The audit output contains only sheet/header/formula/dependency metadata and no
data rows. A user-directory metadata search did not locate an XLSX containing
the three identifying template sheets, so external real-workbook replay was not
performed and no private asset was copied into the repository.

## K. Network accounting

- Automated external network calls: **0**.
- Provider live calls: **0**.
- Sorftime/XiYou credential reads: **0**.
- A socket-construction deny test passes for the audit path.

GitHub issue/license inspection occurred only during the mandatory pre-code
public reuse audit and was not part of automated tests.

## L. Focused / affected / full regressions

- SP-041A focused: `17 passed`.
- Affected group: `75 passed`, plus one known baseline failure.
- Development-start full baseline: `1352 passed, 13 skipped, 550 subtests`,
  one failure.
- Final full suite: `1369 passed, 13 skipped, 550 subtests`, one failure.

The sole failure before and after implementation is
`test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`:
the current Python/openpyxl runtime produces OOXML package fingerprint
`84e5aed6...` while the frozen expected value is `89ffe16d...`. SP-041A does
not modify that renderer or test. There are no new failures.

## M. Git / diff / secret scan

`compileall` and `git diff --check` pass. Staged-diff review and repository
secret scan are required immediately before commit; commit/push identity and
final clean status are reported with the task handoff.

## N. SP-041B readiness

The frozen schema exposes exact header-name requirements and missingness
semantics needed by a future SellerSprite adapter. **SP-041B was not started**:
there is no import adapter, parser, Product Map, route score, provider change,
or new business calculation in this branch.

## O. Final verdict

**PASS — TEMPLATE_CONTRACT_V1_FROZEN**

The repository contract and deterministic offline audit gate are complete.
External replay remains an explicit local follow-up only when the private
workbook is supplied; it must not result in committing raw rows or workbook
bytes.
