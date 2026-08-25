# Market Report V0.2 Live Re-Acceptance R3 V0.1

## A. Baseline, runtime, and workspace

- Task: `TASK-SP-039G-R3` / GitHub Issue #37.
- Branch: `codex/task-sp-039g-r3-proven-key-final-live-acceptance`.
- Exact starting commit: `4db2c52e8f62d8c23db923338c68bb9f2500b5a1`.
- Workspace and staging were clean before any edit or live access.
- Runtime: Python 3.12.13, pytest 9.1.1, zlib 1.3.2, openpyxl 3.1.5.
- The baseline kept Market Report V0.2 fixture-only and Market Report V0.1 as the
  omitted-version default.

## B. R2A credential identity status

R2A was acknowledged as `PASS — EXACT_CODEX_KEY_IDENTITY_PROVEN`. No R2A probe
input, output, hash, or derived credential material was read into or persisted by
this validation record.

Immediately before live access, secret-safe checks established that the process
credential was configured, the base URL was the exact governed XiYou origin, and
the credential contained neither boundary whitespace nor control characters. No
credential value, length, hash, prefix, or suffix was printed or persisted.

## C. Authentication-contract non-change audit

The existing audited contract remained frozen:

- JSON POST to the governed XiYou origin;
- the audited V2 protocol header;
- the audited credential-header injection;
- no V1 signing headers;
- `POST /v1/asins/info` for `asin_info`;
- `POST /v1/asins/research/list/period` for `asin_keywords`;
- the existing page-1, page-size-20, last-7-days, traffic-descending reverse-keyword
  request shape;
- authentication remained non-retryable; and
- R1 diagnostics remained allowlist-only.

No auth header, credential injection, endpoint, request shape, retry rule, provider
adapter, Intelligence contract, formula, or classifier changed.

## D. Offline preflight

The only temporary release-gate code change removed the explicit V0.2 live rejection
from `ProductionRunRequest`; the corresponding test was changed only to prove explicit
V0.2 live opt-in while preserving the V0.1 default. After the live stop rule fired,
both changes were fully restored.

Offline checks proved:

- the exact branch and baseline;
- the supported report-version set and V0.1 default were unchanged;
- unknown report versions fail at the request boundary;
- missing live configuration fails before transport construction;
- V0.2 fixture E2E remained green;
- only `asin_info` and bounded `asin_keywords` were reachable in this path;
- authentication was non-retryable and diagnostics were allowlisted;
- SP-039B-F, connector, Production Pipeline, reliability/resume, Operator Workflow,
  Batch, Buyer Need, Competition, Opportunity, Product Intelligence, and XLSX checks
  were green; and
- automated tests ran with live credential configuration removed and made zero live
  calls.

The first clean baseline full suite passed 1,113 tests with 16 skipped and 497
subtests. A focused post-gate matrix passed 487 tests with 16 skipped and 117
subtests. The final pre-live full suite again passed 1,113 tests with 16 skipped and
497 subtests.

One earlier harness attempt encountered six pytest setup errors because the default
Windows temporary root was inaccessible. It made zero live calls. Re-running with an
explicit workspace-owned pytest base temp produced the clean result above.

## E. Smoke command, operations, attempts, and credits

Exactly one fresh-output Production Pipeline live invocation was made with this
credential-omitted command shape:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --category-name "dog water bottle" \
  --output-dir <external-fresh-r3-smoke-dir> \
  --mode live \
  --report-version market-report-v0.2
```

Final status was `FAILED`; requested/resolved was `1/0`.

| Operation | Logical status | Source | Attempts | HTTP | Provider error | Provider reason | Trace ID | Credits |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| `asin_info` | FAILED | `xiyou` | 1 | 401 | `AUTHENTICATION` | unavailable | `20260825APN506TDAYABHT14H8PCH2F5EKXJT4LX` | unavailable |

Authentication was non-retryable. No `asin_keywords` operation ran. Provider credit
semantics were `LIVE_PROVIDER_REPORTED`, but provider-reported credits were
unavailable. No smoke rerun, manual retry, live resume, direct HTTP diagnostic,
discovery, or other provider operation occurred.

## F. Smoke artifacts, V0.2 truth, and parity

| Artifact | State | Bytes | SHA-256 / package fingerprint |
| --- | --- | ---: | --- |
| `run_manifest.json` | present | 4,868 | `4ed1c47ae02ea9522267d34aa10927f0a23a0d4755fb20145faea780f2bd551e` |
| `market_report.json` | not produced | 0 | N/A |
| `operator_market_report.xlsx` | not produced | 0 | N/A |
| `operator_market_report.md` | not produced | 0 | N/A |

The manifest records requested version `market-report-v0.2`, failed delivery, one
failed logical operation, one transport attempt, no checkpoint, and unavailable
credits. V0.2 validation, report identity, semantic fingerprint, truth-state checks,
OOXML content fingerprint, and JSON/XLSX/Markdown parity are N/A because report
artifacts were not produced.

## G. Full-run go/no-go

**NO-GO.** The first authenticated `asin_info` operation returned HTTP 401 /
`AUTHENTICATION`, so the Issue #37 special stop rule prohibited the three-ASIN run.

## H. Full acceptance command and operation result

The approved full command shape was not invoked:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --asin B0GGR3F5KZ \
  --asin B0H235BRVX \
  --category-name "dog water bottle" \
  --output-dir <external-fresh-r3-full-dir> \
  --mode live \
  --report-version market-report-v0.2
```

Full-run logical operations: `0`; transport attempts: `0`; credits: N/A.

## I. Cumulative credit audit

Smoke provider-reported credits were unavailable, so neither the smoke `<=3` gate
nor the cumulative R3 `<=12` gate can be established. Missing metadata was not
treated as zero. No second or third live invocation occurred.

## J. Full artifacts and parity

N/A because the full acceptance invocation was prohibited by the authentication stop
rule.

## K. Provider-vs-report consistency

No report was produced. No extra provider access was used to obtain diagnostic or
comparison data. Missing economics, competitor authority, Product Direction,
Shortlist, Opportunity, Keyword, and Executive Summary evidence was not fabricated
or converted to zero.

## L. Operator acceptance

Not performed because no operator XLSX or Markdown artifact was produced.

## M. Secret safety

- Persisted credential-value matches in the managed live output: `0`.
- Persisted raw credential-header literal matches: `0`.
- Persisted raw authorization literal matches: `0`.
- Persisted R2A probe-variable-name matches: `0`.
- Captured stdout/stderr contained only the generic sanitized failure and manifest
  path; it contained no credential, auth header, provider body, or arbitrary provider
  exception.
- No raw live payload, report JSON, XLSX, Markdown, checkpoint, credential, or R2A
  probe material is committed.
- The managed live output remains outside the repository.

## N. Validation evidence

This file is a new sanitized R3 historical record. It does not overwrite or
reinterpret the SP-039G, R1, or R2 records. It retains only allowlisted
status/reason/trace/credit facts, operation counts, artifact metadata, gate decisions,
and offline test results.

## O. Frozen and post-live regressions

After restoring the fixture-only gate, the credential-cleared focused matrix passed:

```text
487 passed, 16 skipped, 117 subtests passed
```

It covered SP-039B-F, provider connectors/adapters, Production Pipeline,
reliability/resume, V0.1 default/report/delivery, V0.2 fixture
integration/delivery, Operator Workflow, Batch, Buyer Need, Competition,
Opportunity, Product Intelligence, and XLSX portability/content fingerprints.

All post-live regression testing was offline and made zero live calls.

## P. Post-live full-suite result

The credential-cleared full suite passed:

```text
1113 passed, 16 skipped, 497 subtests passed
```

## Q. Final V0.2 live-gate and default-version state

The temporary explicit V0.2 live gate removal was restored immediately after the
failed smoke. Explicit V0.2 live mode is again rejected at request construction;
V0.2 remains fixture-only; V0.1 remains the omitted-version default. Batch V0.2,
category expansion, discovery, and post-V0.2 capabilities remain
disabled/unimplemented.

## R. Final verdict

**BLOCKED — AUTHENTICATION**

R2A had already proven the exact Codex process credential identity. The remaining
cause therefore requires investigation of current XiYou key/account/provider
authorization rather than blind client-side changes or retries.

## S. Branch, remote, and workspace

Work was performed only on
`codex/task-sp-039g-r3-proven-key-final-live-acceptance` from the exact required
baseline. This sanitized record is the only intended final repository change. The
exact final commit, push state, and clean workspace/staging state are reported in the
task completion response.
