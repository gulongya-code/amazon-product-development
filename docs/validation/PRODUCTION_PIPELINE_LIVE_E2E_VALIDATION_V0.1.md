# Production Pipeline Live E2E Validation V0.1

Status: **BLOCKED — LIVE_PROVIDER_ACQUISITION**

Task: TASK-SP-035
Marketplace/category: Amazon US / dog water bottle
Validation date: 2026-08-24 (Asia/Shanghai)

## 1. Baseline and live gate

- Repository baseline branch: `codex/release-market-report-v0.1`.
- Required and observed baseline: `f6ab24eedb3e7420a7e741e062e7f866df02feb9`.
- Validation branch: `codex/task-sp-035-live-validation`.
- Python: `3.12.13` from the bundled workspace runtime.
- Workspace and staging were clean before tests and the live invocation.
- `XIYOU_API_KEY`: configured; the value was never printed or persisted.
- XiYou base URL: configured for the process from the existing audited repository endpoint;
  it is not credential material.
- Baseline focused tests: `15 passed, 4 subtests passed in 4.64s`.
- Baseline full suite: `934 passed, 490 subtests passed in 159.44s`.

No live call occurred until the baseline, sample, credential status, and tests were
recorded. The production path retained `NoRetryPolicy`; no fixture fallback was used.

## 2. Deterministic sample selection

No discovery operation was performed. The source is the checked-in SP-032E capture:

`docs/validation/ORGANIC_BUYER_NEED_HOLDOUT_100_V0.1.raw.json`

Source SHA-256:
`2e02caf775633a9248ee74e56e48ee60bba15be9d095878c8c4a63070d2acc29`.

The source status is `COMPLETE`, marketplace is US, query is `dog water bottle`, and
the cohort preserves provider order after the frozen SP-032B exclusion. Selection is
the first three cohort entries, with no hand-picking:

| Order | ASIN | Saved provider rank | Saved `asin_keywords` evidence |
| --- | --- | ---: | --- |
| 1 | `B09265WXY5` | 21 | 20 rows, 1 provider-reported credit |
| 2 | `B0GGR3F5KZ` | 22 | 20 rows, 1 provider-reported credit |
| 3 | `B0H235BRVX` | 23 | 20 rows, 1 provider-reported credit |

The saved cohort rows also carry real product title, price, rating, and review-count
evidence, establishing prior dog-water-bottle membership and successful adaptation.

## 3. Live invocations and cost gate

Exactly one live pipeline invocation was made:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --category-name "dog water bottle" \
  --output-dir outputs/task-sp-035/smoke-f6ab24e-20260824 \
  --mode live \
  --run-id sp035-smoke-f6ab24e-20260824
```

Credentials and authorization headers are omitted.

| Run | Status | Operations | Count | Credit semantics | Credits |
| --- | --- | --- | ---: | --- | ---: |
| 1-ASIN smoke | FAILED | `asin_info`, `asin_keywords` | 2 | `LIVE_PROVIDER_REPORTED` | 1.0 |
| 3-ASIN validation | NOT RUN | none | 0 | N/A | 0.0 |

The smoke credit sub-gate passed: metadata was available, credits were 1.0 (<=3),
only allowed operations occurred, and there was no duplicate or retry. The smoke
success gate failed at acquisition, so the 3-ASIN invocation was prohibited and was
not attempted. Total SP-035 observed live credits are **1.0**, within the hard budget
of 12.

## 4. Smoke stage result

| Stage | Status | Evidence/result |
| --- | --- | --- |
| input_validation | COMPLETE | Explicit ASIN, live mode, and category accepted |
| provider_resolution | COMPLETE | XiYou selected; one `asin_info` raw evidence ID recorded |
| acquisition | FAILED | `PROVIDER_FAILURE`; outer code `RESOLUTION_EXHAUSTED` |
| data_cleaning | SKIPPED | Earlier acquisition failure |
| category_competition | SKIPPED | Earlier acquisition failure |
| buyer_need_v0_3 | SKIPPED | Earlier acquisition failure |
| opportunity_intelligence_scoring | SKIPPED | Earlier acquisition failure |
| market_report | SKIPPED | Earlier acquisition failure |
| schema_validation | SKIPPED | Earlier acquisition failure |
| operator_delivery | SKIPPED | Earlier acquisition failure |
| run_manifest | COMPLETE | Failure manifest written last |

Requested/resolved count was `1/0`. The observable failure occurred while resolving
`relationship.product_to_keyword` from the one allowed `asin_keywords` operation.
The current failure boundary preserves `RESOLUTION_EXHAUSTED` but not the nested
provider-attempt reason, so the saved evidence cannot distinguish HTTP rejection,
field omission, or live payload adaptation failure without another paid request.

## 5. Artifact validation

Only the current-run failure manifest exists; no stale artifact was attributed to the
run and the output directory was fresh.

| Artifact | Exists | Size | SHA-256 / result |
| --- | --- | ---: | --- |
| `run_manifest.json` | yes | 3,222 bytes | `c477d041b6339368f9d90b05b680c3785fa0d0acbb3b5c9ef05dc38a69a18aaa` |
| `market_report.json` | no | 0 | Not produced after acquisition failure |
| `operator_market_report.xlsx` | no | 0 | Not produced; XLSX header check unavailable |
| `operator_market_report.md` | no | 0 | Not produced |

The manifest references only itself, records the final manifest stage as `COMPLETE`,
and reports live credit semantics truthfully. SP-034A output-ownership behavior remains
covered by the passing focused regression tests.

## 6. Live evidence and report consistency

The saved SP-032E provenance contains these prior observations; they are sample
selection evidence, not claims about the failed smoke response on 2026-08-24:

| ASIN | Saved title (abbreviated) | Price | Reviews | Rating |
| --- | --- | ---: | ---: | ---: |
| `B09265WXY5` | Portable Dog Water Bottle, Foldable... Pink, 12oz | 9.99 USD | 1,224 | 4.4 |
| `B0GGR3F5KZ` | Cibaabo 53oz Large Dog Water Bottle... | 24.98 USD | 45 | 4.8 |
| `B0H235BRVX` | Portable Dog Water Bottle Attachment... | 6.99 USD | 61 | 4.0 |

No final Market Report was produced, so a current live-vs-report consistency check
cannot be performed. No extra provider operation was made to fill that evidence gap.
Competition and Opportunity stages were skipped rather than populated with fake zeroes.

## 7. Secret safety

- CLI stdout/stderr was checked in memory before display: API key match `false`.
- Failure manifest API key match: `false`.
- Output filename API key match: `false`.
- No raw live provider response, API key, authorization header, or live output binary
  is committed as validation evidence.
- The committed report contains only sanitized ASINs, operation names, counts, credits,
  hashes, stage states, and previously checked-in sample facts.

## 8. Frozen and offline regressions

Post-live checks used fixtures/mocks and made zero XiYou calls:

- Production Pipeline focused: `15 passed, 4 subtests passed in 5.47s`.
- Buyer Need fingerprints plus Market Report version: `2 passed in 0.70s`.
- Full suite: `934 passed, 490 subtests passed in 186.50s`.
- `git diff --check`: passed.

Frozen values remain:

- Buyer Need Query Intent V0.3:
  `75f5accba6ad961e65849e0ee46933d361434144c251b512ae639d6523d21755`.
- Buyer Need Taxonomy V0.2:
  `8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6`.
- Semantic Normalization V0.1:
  `49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2`.
- Market Report version: `market-report-v0.1`.

No production or frozen Intelligence source was modified.

## 9. Limitations and follow-up

The acceptance gate cannot pass because the 1-ASIN live pipeline did not succeed and
the required 3-ASIN end-to-end artifacts were therefore not produced.

Proposed follow-up: a bounded provider-contract diagnostic task should preserve a
credential-safe nested provider attempt code/status for `asin_keywords`, then perform
one separately approved cost-gated reproduction. It must not change Buyer Need rules,
Competition formulas, Opportunity scoring semantics, Market Report schema, or XLSX
design, and it must not add retries or fixture fallback.

## 10. Verdict

**BLOCKED — LIVE_PROVIDER_ACQUISITION**

The validation stopped after the first failed smoke exactly as required. One live
invocation, two allowed operations, no retries, no discovery, no fallback, and 1.0
total provider-reported credit were observed.
