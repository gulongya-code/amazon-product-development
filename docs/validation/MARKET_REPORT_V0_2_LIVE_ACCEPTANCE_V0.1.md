# Market Report V0.2 Live Acceptance V0.1

Status: **BLOCKED — SMOKE_AUTHENTICATION_AND_CREDIT_GATE**

Task: TASK-SP-039G

Validation date: 2026-08-25 (Asia/Shanghai)

Marketplace/category: Amazon US / dog water bottle

## 1. Baseline, runtime, and release gate

- Validation branch: `codex/task-sp-039g-v0-2-controlled-live-acceptance`.
- Required and observed starting commit: `5ff3a5aea1625f498e9455caad7665fb577f3ce0`.
- Workspace and staging were clean before editing and before the live invocation.
- Python `3.12.13`, pytest `9.1.1`, zlib runtime/build `1.3.2`, openpyxl `3.1.5`.
- XiYou credential status before the live invocation: `CONFIGURED`; no credential value was printed.
- Baseline focused tests: `227 passed, 3 skipped, 7 subtests passed`.
- Baseline full suite: `1112 passed, 16 skipped, 497 subtests passed`.
- Baseline `git diff --check`: passed.

The sole temporary code change removed only the SP-039F request-validation condition
that rejected explicit `market-report-v0.2` live mode. V0.1 remained the default,
the exact supported-version set and request fingerprint were unchanged, and no
Provider operation, endpoint, business formula, classifier, or retry was added.

Because the smoke failed, that temporary release-gate change was reverted. The
accepted fixture-only V0.2 gate remains in production; this validation does not
release V0.2 live mode to colleagues.

## 2. Offline preflight

No live call occurred before all preflight checks passed.

- Gate and Production Pipeline/reliability tests: `49 passed, 7 subtests passed`.
- Full offline preflight: `1116 passed, 16 skipped, 497 subtests passed`.
- Explicit V0.2 live request was structurally accepted during preflight.
- Missing live configuration failed before transport with zero executed operations.
- Offline live-shaped fixture execution used exactly one `asin_info` and three
  `asin_keywords` logical operations for the fixed 3-ASIN cohort.
- Existing endpoints remained `/v1/asins/info` and
  `/v1/asins/research/list/period`.
- V0.1 default, V0.2 fixture E2E, delivery, checkpoint/resume, output ownership,
  Operator Workflow, and Batch regressions passed.
- `git diff --check`: passed.

All preflight tests used fixtures/mocks and made zero XiYou network calls.

## 3. Controlled live invocation

Exactly one live Production Pipeline invocation was attempted:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --category-name "dog water bottle" \
  --output-dir C:\Users\Administrator\AppData\Local\Temp\sp039g-smoke-20260825-4c78a9 \
  --mode live \
  --report-version market-report-v0.2 \
  --run-id sp039g-live-smoke
```

Credentials and authorization headers are omitted.

| Run | Final status | Logical operations | Transport attempts | Credit semantics | Provider-reported credits |
| --- | --- | ---: | ---: | --- | --- |
| 1-ASIN smoke | FAILED | 1 | 1 | `LIVE_PROVIDER_REPORTED` | unavailable |
| 3-ASIN full acceptance | NOT RUN | 0 | 0 | N/A | N/A |

Smoke operation/attempt evidence:

| Operation | Logical status | Attempts | Attempt status | Provider error | Credits |
| --- | --- | ---: | --- | --- | --- |
| `asin_info` | FAILED | 1 | FAILED | `AUTHENTICATION` | unavailable |

The outer failure was `PROVIDER_FAILURE` / `RESOLUTION_EXHAUSTED` at
`provider_resolution`. It was non-retryable. No `asin_keywords`, discovery,
variation, trend, order, review, seller, fee, or other Provider operation ran.
No live resume or manual rerun was attempted.

## 4. Smoke gate and credit audit

The smoke did not satisfy the mandatory `SUCCEEDED 1/1` gate. Provider credit
metadata was unavailable, so neither the `<=3` smoke credit condition nor a
truthful cumulative `<=12` audit could be established.

The full-run decision was therefore **NO-GO**. The second permitted invocation was
not consumed. SP-039G ended with one live Pipeline invocation total.

## 5. Artifact and semantic validation

The fresh output contained only the failure manifest:

| Artifact | Result | Size | SHA-256 |
| --- | --- | ---: | --- |
| `run_manifest.json` | present | 4,745 bytes | `da55ecee2b932cd4008e6ded828e8e5ca506145680088cf4f0d5f2e05c93a9db` |
| `market_report.json` | not produced | 0 | N/A |
| `operator_market_report.xlsx` | not produced | 0 | N/A |
| `operator_market_report.md` | not produced | 0 | N/A |

The manifest truthfully records requested/produced version
`market-report-v0.2`, `delivery_status=FAILED`, one failed `asin_info` logical
operation and attempt, zero checkpoints, no report ID, and failure manifest written
last. Market Report, schema validation, and delivery stages were skipped after the
Provider failure.

Because no V0.2 JSON/XLSX/Markdown was produced, strict V0.2 validation,
cross-artifact parity, portable workbook fingerprinting, live provider-vs-report
consistency, and colleague-facing operator acceptance could not be performed. No
missing evidence was converted to zero or fabricated to bypass the failure.

## 6. Secret and artifact safety

- API-key value matches across every persisted smoke file: `0`.
- Authorization-literal matches across every persisted smoke file: `0`.
- No raw live Provider response, checkpoint, JSON report, XLSX, or Markdown is
  committed as evidence.
- The committed document contains only sanitized operation names, counts, states,
  non-secret hashes, and error categories.
- The live output remains outside the repository.

## 7. Post-live offline regressions

All tests after the live attempt were offline:

- SP-039B–F, V0.1/V0.2 delivery/pipeline, reliability/resume, Operator Workflow,
  and Batch focused matrix: `236 passed, 16 skipped, 11 subtests passed`.
- Final full suite: `1112 passed, 16 skipped, 497 subtests passed`.
- `git diff --check`: passed.

No production or frozen Intelligence source remains modified. Query Intent V0.3,
Taxonomy V0.2, Semantic Normalization V0.1, Buyer Need, Competition, Opportunity,
Product Intelligence, V0.1 default behavior, SP-039B–F, recovery, Operator Workflow,
Batch, and XLSX portability behavior remain at the accepted baseline.

## 8. Limitations and verdict

Current credentials were present but were rejected by the Provider on the first
allowed operation. This task cannot distinguish credential invalidity, expiration,
or Provider-side authorization policy without another separately approved live
invocation. Issue #30 explicitly forbids a smoke rerun after a failed gate, so no
diagnostic live request was made.

Final verdict: **BLOCKED — SMOKE_AUTHENTICATION_AND_CREDIT_GATE**.

V0.2 remains fixture-only and V0.1 remains the default. No 3-ASIN acceptance, live
release, batch rollout, or post-SP-039G capability expansion was started.
