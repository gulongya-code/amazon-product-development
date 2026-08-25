# Market Report V0.2 Live Re-Acceptance R2 V0.1

Status: **BLOCKED — AUTHENTICATION**

Task: TASK-SP-039G-R2 / Issue #34

Validation date: 2026-08-25 (Asia/Shanghai)

Marketplace/category: Amazon US / dog water bottle

## A. Baseline, runtime, and workspace

- Required and observed starting HEAD: `b0d32f0147c5126507c523ad9155355a3eb6c764`.
- Validation branch: `codex/task-sp-039g-r2-correct-key-live-acceptance`.
- Workspace and staging were clean before editing and live access.
- Python `3.12.13`, pytest `9.1.1`, zlib `1.3.2`, openpyxl `3.1.5`.
- The SP-039G and SP-039G-R1 blocked records remain unchanged.

## B. Corrected credential environment precheck

- The operator explicitly reported that the corrected local environment matches the
  current XiYou dashboard OpenAPI V2 key. No key or key hash was supplied to this record.
- `XIYOU_API_KEY`: `CONFIGURED`; its value was never printed or hashed.
- `XIYOU_API_BASE_URL`: exact `https://openapi.xydc.com` origin.
- Credential boundary whitespace: absent.
- Credential control characters: absent.
- A Windows User-scoped key was not available to the validating process, so the
  process/User comparison was not applicable under the required "when available" rule.
- The same secret-safe checks passed immediately before live access.

## C. Authentication-contract non-change audit

The frozen XiYou V2 contract remained unchanged:

| Contract item | Runtime | Result |
| --- | --- | --- |
| Origin | exact configured `https://openapi.xydc.com` | PASS |
| Request | JSON POST | PASS |
| Auth version | `X-Auth-Version: 2.0` | PASS |
| Credential header | ephemeral `X-Api-Key` | PASS |
| V1 signing headers | `X-Client-Id` / `X-Timestamp` / `X-Sign` absent | PASS |
| `asin_info` | `POST /v1/asins/info` | PASS |
| `asin_keywords` | `POST /v1/asins/research/list/period` | PASS |
| Reverse-keyword request | accepted `page` / `pageSize` / `period` / `traffic desc` shape | PASS |

No connector, endpoint, auth header, provider reason allowlist, retry category, or
request shape changed.

## D. Offline preflight

- Before editing, a corrected full-suite launch passed:
  `1113 passed, 16 skipped, 497 subtests passed`.
- The first harness launch lacked the repository `src` path and stopped during
  collection. A second launch proved `1101` tests but exposed six child-process import
  failures and six temporary-directory setup errors. These were test-harness environment
  issues, not product assertion failures; no live access occurred.
- Supplying an inherited absolute `PYTHONPATH` and an ASCII writable basetemp made the
  affected focused set pass: `13 passed`.
- After the bounded fixture-only gate removal, the credential-cleared focused matrix
  passed: `442 passed, 16 skipped, 37 subtests passed`.
- The post-removal credential-cleared full suite passed before live access:
  `1113 passed, 16 skipped, 497 subtests passed`.
- Explicit V0.2 live request construction passed only while the bounded gate removal was
  present. The supported-version set and V0.1 omitted-version default were unchanged.
- Unknown versions and missing live configuration remained pre-transport failures.
- Fixture V0.2 E2E, V0.1 compatibility, retry/checkpoint/resume/output ownership,
  safe auth diagnostics, SP-039B–F, frozen Intelligence, Operator, Batch, and XLSX
  checks were green.
- Test processes had both `XIYOU_API_KEY` and `XIYOU_API_BASE_URL` removed and made zero
  XiYou network calls.
- Pre-live `git diff --check` passed.

## E. Smoke command, operations, attempts, and credits

Exactly one fresh-output Production Pipeline live invocation was made with this
credential-omitted command shape:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --category-name "dog water bottle" \
  --output-dir <external-fresh-r2-smoke-dir> \
  --mode live \
  --report-version market-report-v0.2
```

Final status was `FAILED`; requested/resolved was `1/0`.

| Operation | Logical status | Source | Attempts | HTTP | Provider error | Provider reason | Trace ID | Credits |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| `asin_info` | FAILED | `NEW_PROVIDER` | 1 | 401 | `AUTHENTICATION` | unavailable | `20260825TN09UIUY68BTE0QV34JR2JQZDVN3W675` | unavailable |

Authentication was non-retryable. No `asin_keywords` operation ran. Provider credit
semantics were `LIVE_PROVIDER_REPORTED`, but provider-reported credits were unavailable.
No smoke rerun, manual retry, live resume, direct HTTP diagnostic, discovery, or other
Provider operation occurred.

## F. Smoke artifacts, V0.2 truth, and parity

| Artifact | Result | Bytes | SHA-256 / package fingerprint |
| --- | --- | ---: | --- |
| `run_manifest.json` | present | 4,902 | `a2978ec21f34e2d752797f61b9237b2bebdb5366c5960937529f551ef06dddb2` |
| `market_report.json` | not produced | 0 | N/A |
| `operator_market_report.xlsx` | not produced | 0 | N/A |
| `operator_market_report.md` | not produced | 0 | N/A |

The manifest records requested version `market-report-v0.2`, failed delivery, one failed
logical operation, one transport attempt, no checkpoint, and unavailable credits.
Strict V0.2 report validation, report ID/semantic fingerprint, OOXML package fingerprint,
truth-state checks, and JSON/XLSX/Markdown parity are N/A because the report artifacts
were not produced.

## G. Full-run go/no-go

**NO-GO.** The smoke failed status, resolved-count, operation-count, credit, artifact,
truth, and parity gates. The three-ASIN invocation was therefore prohibited.

## H. Full acceptance command and operation result

The approved full command shape was not invoked:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --asin B0GGR3F5KZ \
  --asin B0H235BRVX \
  --category-name "dog water bottle" \
  --output-dir <external-fresh-r2-full-dir> \
  --mode live \
  --report-version market-report-v0.2
```

Full-run logical operations: `0`; transport attempts: `0`; credits: N/A.

## I. Cumulative credit audit

Smoke provider-reported credits were unavailable, so neither the smoke `<=3` gate nor
the cumulative R2 `<=12` gate can be established. No second or third live invocation
occurred, and no zero-credit inference was made.

## J. Full artifacts and parity

N/A because the full acceptance invocation was prohibited by the failed smoke gate.

## K. Provider-vs-report consistency

No report was produced. No extra API access was used to obtain diagnostic or comparison
data. Missing economics, competitor authority, Product Direction, Shortlist,
Opportunity, Keyword, and Executive Summary evidence was not fabricated or converted
to zero.

## L. Operator acceptance

Not performed because no operator XLSX or Markdown artifact was produced.

## M. Secret safety

- Persisted credential-value matches across the managed live output: `0`.
- Persisted raw `X-Api-Key` literal matches: `0`.
- Persisted raw authorization literal matches: `0`.
- Checkpoint files: `0`.
- Captured stdout/stderr contained only the generic sanitized failure and manifest path;
  it contained no credential, header, provider body, or arbitrary provider exception.
- No raw live payload, live report JSON, XLSX, Markdown, or credential is committed.
- The live output remains outside the repository.

## N. Validation evidence

This file is a new sanitized R2 historical record. It does not overwrite or reinterpret
the SP-039G or R1 records and retains only allowlisted status/trace/credit facts,
operation counts, artifact metadata, gate decisions, and offline test results.

## O. Frozen and post-live regressions

After restoring the fixture-only gate, the credential-cleared focused matrix passed:

`442 passed, 16 skipped, 37 subtests passed`

It covered SP-039B–F, connector and Production Pipeline behavior, reliability/resume,
V0.1 report/default/delivery, V0.2 fixture delivery/integration, Operator Workflow,
Batch, Buyer Need frozen fingerprints, Competition/Opportunity/Product Intelligence,
and XLSX portability/content fingerprints.

## P. Post-live full-suite result

The credential-cleared full suite passed:

`1113 passed, 16 skipped, 497 subtests passed`

All post-live testing was offline. No automated live tests ran.

## Q. Final live-gate and default-version state

The temporary V0.2 live gate removal was restored after the failed smoke. Explicit
V0.2 live mode is again rejected at request construction; V0.2 remains fixture-only;
V0.1 remains the omitted-version default. Batch V0.2, category expansion, discovery,
and post-V0.2 capabilities remain disabled/unimplemented.

## R. Final verdict

**BLOCKED — AUTHENTICATION**

## S. Branch, remote, and workspace

Work was performed only on `codex/task-sp-039g-r2-correct-key-live-acceptance` from the
exact required baseline. The sanitized record is committed and pushed on this branch;
the exact final commit and clean workspace/staging state are reported in the task
completion response.
