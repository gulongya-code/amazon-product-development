# SP-035 Resumed 3-ASIN Live E2E Final Validation Addendum

Status: **PASS**

Task: TASK-SP-035

Resume gate: Issue #3 comment `5390139733`

Validation date: 2026-08-24 (Asia/Shanghai)

This addendum preserves the original blocked SP-035 validation report and the
SP-035A repair addendum as historical evidence. It records only the resumed final
3-ASIN validation. No raw live response, credential, or live binary is committed.

## 1. Baseline, branch, workspace, and credential status

- Required baseline: `7f725cad0b6b036c3c8ab4e49b27093c2d4cd69e`.
- Observed remote release baseline:
  `origin/codex/release-market-report-v0.1` at the required commit.
- Fresh validation branch:
  `codex/task-sp-035-live-validation-resume`, created directly from that remote
  release baseline.
- The old SP-035 validation branch was not reused.
- Baseline bundled Python: 3.12.13.
- Frozen XLSX regression runtime: Python 3.12.10, zlib 1.3.1, openpyxl 3.1.5.
- Workspace and staging were clean before validation.
- `XIYOU_API_KEY`: configured. Its value was never printed or persisted.
- The public XiYou base URL was provided only to the live process.

Pre-live zero-network gates:

- Production Pipeline focused: `17 passed, 4 subtests passed in 4.48s`.
- Full suite: `936 passed, 490 subtests passed in 162.72s`.
- XiYou calls and credits from tests: zero.

## 2. Deterministic sample provenance

The Resume Gate fixes this exact order:

1. `B09265WXY5`
2. `B0GGR3F5KZ`
3. `B0H235BRVX`

The cohort comes from the checked-in
`ORGANIC_BUYER_NEED_HOLDOUT_100_V0.1.raw.json` SP-032 evidence. The source rows
are provider response ranks 21, 22, and 23 for the Amazon US dog-water-bottle
cohort. Each ASIN also has a previously successful 20-row reverse-keyword capture.
No discovery or sample-selection provider call was made.

## 3. Single resumed live invocation

The repaired SP-035A 1-ASIN smoke was not repeated. Exactly one resumed live
pipeline invocation was performed:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --asin B0GGR3F5KZ \
  --asin B0H235BRVX \
  --category-name "dog water bottle" \
  --output-dir outputs/task-sp-035/resume-3asin-7f725ca-20260824 \
  --mode live \
  --run-id sp035-resume-3asin-7f725ca-20260824
```

| Check | Observed result |
| --- | --- |
| Process exit | `0` |
| Final status | `SUCCEEDED` |
| Requested/resolved | `3/3` |
| Credit semantics | `LIVE_PROVIDER_REPORTED` |
| Provider | `xiyou` |
| Operations | `asin_info`, `asin_keywords`, `asin_keywords`, `asin_keywords` |
| Operation count | `4` |
| Resumed credits | `6.0` |
| Retry/duplicate | none |
| Discovery | none |
| Pagination loop | none |
| Fixture fallback | none |
| Other endpoint | none |

No variations, BSR, orders, review, or other provider operation occurred.

## 4. Stage-by-stage result

| Stage | Status | Evidence summary |
| --- | --- | --- |
| input_validation | `COMPLETE` | Fresh managed-output ownership validated |
| provider_resolution | `COMPLETE` | XiYou selected |
| acquisition | `COMPLETE` | Four minimum provider operations acquired |
| data_cleaning | `COMPLETE` | Canonical cleaning `SUCCESS` |
| category_competition | `PARTIAL` | Missing competition metrics remain unavailable |
| buyer_need_v0_3 | `COMPLETE` | Frozen V0.3/stable semantic path completed |
| opportunity_intelligence_scoring | `PARTIAL` | Missing score inputs remain unknown |
| market_report | `COMPLETE` | `market-report-v0.1` written |
| schema_validation | `COMPLETE` | Serialized JSON validated |
| operator_delivery | `COMPLETE` | XLSX and Markdown written |
| run_manifest | `COMPLETE` | Manifest written last |

The truthful `PARTIAL` states do not prevent the successful end-to-end production
run because unavailable fields are explicit and excluded rather than replaced by
numeric zero.

## 5. Current-run artifact validation

The fresh directory contained exactly the four managed current-run artifacts:

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `market_report.json` | 41,123 | `5d679a43ce6d533d7009fd21e5d6fe20264738e9fc5c5ffcd40b0e38393010fc` |
| `operator_market_report.xlsx` | 10,715 | `cdad04bff398a08a675cfb5861e76136c55101850ccaff41d2ba60b20c8d72ef` |
| `operator_market_report.md` | 14,120 | `6211d353737591e367a6511460cd6ee1f0919adec0dce27f4cfed4acc1c05f4d` |
| `run_manifest.json` | 5,545 | `e4f1a8de64cd98ab62dfaecee9a4317661c95a4248befede3cce3a80a55f7792` |

- Market Report schema validation: passed.
- Report version: `market-report-v0.1`.
- Report ID:
  `market-report:66b26b3f55b751c546bc2eee3bed42b74213588d618c3fe595555dc6519ef0e2`.
- XLSX is non-empty and begins with `PK`.
- Markdown is non-empty.
- Manifest's final stage is `run_manifest=COMPLETE`.
- Manifest has four artifact paths, all under the fresh current-run directory.

## 6. Current live canonical evidence versus final report

An offline identity replay used the frozen XiYou adapter's canonical observation-ID
contract against the evidence IDs serialized in the completed report. Each metric
mapping had exactly one solution, including the provider entity order:

| ASIN | Current price | Current reviews | Current rating |
| --- | ---: | ---: | ---: |
| `B09265WXY5` | 9.99 USD | 1,224 | 4.4 |
| `B0GGR3F5KZ` | 24.98 USD | 46 | 4.8 |
| `B0H235BRVX` | 7.49 USD | 68 | 3.9 |

The final report contains the same complete three-observation distributions:

- price: minimum 7.49, median 9.99, maximum 24.98 USD;
- reviews: minimum 46, median 68, maximum 1,224;
- rating: minimum 3.9, median 4.4, maximum 4.8.

The Market Report intentionally does not restate exact product title strings. The
current live title-derived canonical attribute distribution was compared offline
with the three checked-in source titles. The cohort semantics agree exactly:

- `B09265WXY5`: portable, foldable, leakproof, 12 oz capacity;
- `B0GGR3F5KZ`: portable, leakproof, 14/21/53 oz capacities;
- `B0H235BRVX`: portable, foldable, silicone.

The final report records portable 3/3, foldable 2/3, leakproof 2/3, silicone 1/3,
and the corresponding four normalized capacity values. It makes no contradictory
title claim. All checks after the live invocation used only completed local
artifacts and checked-in evidence; no further provider call was made.

## 7. Truthful partial and unavailable evidence

- Competition status is `PARTIAL`.
- `brand_count`, `competition_concentration`, and `competition_level` have
  `value=null` and `availability=UNAVAILABLE`, not zero.
- Opportunity score status is `PENDING_DATA` with `score_value=null`.
- Every unavailable opportunity dimension has `status=UNKNOWN`,
  `score_value=null`, and `contribution=null`.
- The report explicitly states that unavailable metrics were excluded without
  numeric zero.

## 8. Secret-safety evidence

- Live CLI stdout/stderr API-key match: `false`.
- Four artifact API-key matches: `0`.
- Output filename API-key match: `false`.
- XLSX binary API-key match: `false`.
- No credential, authorization header, raw response, or live binary is committed.

## 9. Credit audit

| Live phase | Provider-reported credits |
| --- | ---: |
| Original SP-035 blocked smoke | 1.0 |
| SP-035A repaired smoke | 2.0 |
| Resumed final 3-ASIN run | 6.0 |
| **Cumulative** | **9.0** |

Credit semantics for the resumed run are `LIVE_PROVIDER_REPORTED`. The cumulative
9.0 credits remain within the Resume Gate maximum of 12.

## 10. Frozen and post-live regressions

Frozen fingerprints:

- Buyer Need Query Intent V0.3:
  `75f5accba6ad961e65849e0ee46933d361434144c251b512ae639d6523d21755`.
- Buyer Need Taxonomy V0.2:
  `8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6`.
- Semantic Normalization V0.1:
  `49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2`.
- Market Report: `market-report-v0.1`.

Post-live zero-network gates:

- Production Pipeline focused: `17 passed, 4 subtests passed in 6.06s`.
- Frozen fingerprints plus Market Report version: `2 passed in 0.65s`.
- Full suite: `936 passed, 490 subtests passed in 168.20s`.
- `git diff --check`: passed.

No frozen Intelligence source was modified.

## 11. Limitations and verdict

This three-ASIN cohort validates production execution and truthful reporting; it
does not establish market representativeness. Exact current title strings are not
serialized by `market-report-v0.1`; the validation therefore compares the current
title-derived canonical attribute distribution and confirms that the report makes
no contradictory title claim. Missing Competition and Opportunity adapters remain
explicit limitations and are not defects introduced by this validation.

**Final verdict: PASS.**
