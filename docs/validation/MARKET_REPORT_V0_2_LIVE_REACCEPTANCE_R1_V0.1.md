# Market Report V0.2 Live Re-Acceptance R1 V0.1

Status: **BLOCKED — AUTHENTICATION**

Task: TASK-SP-039G-R1 / Issue #32

Validation date: 2026-08-25 (Asia/Shanghai)

Marketplace/category: Amazon US / dog water bottle

## A. Baseline, runtime, and workspace

- Required and observed baseline: `1302dfdb47076670a78a75e5439ad741eaf4cc8c`.
- Validation branch: `codex/task-sp-039g-r1-xiyou-v2-credential-recovery`.
- Workspace and staging were clean before branch creation and before editing.
- Python `3.12.13`, pytest `9.1.1`, zlib `1.3.2`, openpyxl `3.1.5`.
- The original blocked TASK-SP-039G record remains unchanged at
  `docs/validation/MARKET_REPORT_V0_2_LIVE_ACCEPTANCE_V0.1.md`.

## B. Human credential-recovery prerequisite

- Human recovery context was supplied by the operator.
- `XIYOU_API_KEY`: `CONFIGURED`; its value was never printed.
- Credential boundary whitespace: absent.
- Credential control characters: absent.
- `XIYOU_API_BASE_URL`: exact `https://openapi.xydc.com` origin.

## C. Official authentication-contract audit

Current official XiYou OpenAPI V2 documentation was checked at
`https://openapi-doc.xydc.com/` (document v1.0.1, updated 2026-06-25), plus the
official endpoint pages for the two operations. Repository source matched:

| Contract item | Official | Runtime | Result |
| --- | --- | --- | --- |
| Origin | `https://openapi.xydc.com` | exact configured origin | PASS |
| POST content type | `application/json` | transport sets exact header | PASS |
| Auth version | `X-Auth-Version: 2.0` | exact public header | PASS |
| Credential | `X-Api-Key` | ephemeral header injection | PASS |
| V1 signing headers | absent | `X-Client-Id` / `X-Timestamp` / `X-Sign` absent | PASS |
| `asin_info` | `POST /v1/asins/info` | exact existing operation | PASS |
| `asin_keywords` | `POST /v1/asins/research/list/period` | exact existing operation | PASS |

No connector operation, endpoint, authentication header, key regex, or key-length
rule was added or changed.

## D. Safe authentication diagnostics decision

The prior path retained HTTP classification and credits but not the official provider
`reason` or response trace. A bounded allowlist-only enhancement was added to the
Pipeline attempt summary. It may retain only HTTP status, these official reason codes,
validated trace IDs, and numeric credits:

- `APICredentialUnavailable`
- `APICredentialNotFound`
- `CreditBalanceInsufficient`
- `CreditAccountUnavailable`
- `CreditAccountNotFound`

Raw response bodies, provider messages, unknown metadata, account identifiers, request
headers, and credentials remain excluded. An offline test proves secret safety and that
HTTP 401 remains non-retryable.

## E. Offline preflight

- Focused connector, SP-039B-F, V0.1/V0.2 pipeline/delivery, reliability/resume,
  Operator Workflow, Batch, and XLSX matrix: `335 passed, 16 skipped, 93 subtests passed`.
- Full suite: `1113 passed, 16 skipped, 497 subtests passed`.
- The first full-suite launch reached `1107 passed` but six `tmp_path` setups were
  denied by the system default temp-directory permissions. Re-running in a dedicated
  writable workspace basetemp produced the green full-suite result above; there were no
  product-code test failures.
- All automated tests used fixtures/mocks and made zero XiYou network calls.
- Missing configuration and unknown version still fail before Provider access.
- Explicit V0.2 live structure was accepted only while the bounded gate removal was
  present; fixture V0.2 E2E and the V0.1 default remained green.
- Connector registry diff from the required baseline: none.
- `git diff --check`: passed.

## F. Smoke operation, attempt, and credit result

Exactly one live Pipeline invocation was made with fixed input `B09265WXY5`, market
`US`, category `dog water bottle`, and explicit `market-report-v0.2`.

| Operation | Logical status | Attempts | HTTP | Provider error | Provider reason | Trace ID | Credits |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| `asin_info` | FAILED | 1 | 401 | `AUTHENTICATION` | unavailable | `20260825S26F696JZ65PGJ7NKRTCZNCL316C13R8` | unavailable |

The failure was non-retryable. No `asin_keywords` operation ran. No smoke rerun, manual
retry, live resume, discovery, or other Provider operation occurred.

## G. Smoke artifacts, truth, and parity

| Artifact | Result | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `run_manifest.json` | present | 4,843 | `0e8c3ea85512d9d699e5385feb12d9931282a2249639fe040593f1540098c9fd` |
| `market_report.json` | not produced | 0 | N/A |
| `operator_market_report.xlsx` | not produced | 0 | N/A |
| `operator_market_report.md` | not produced | 0 | N/A |

The manifest records `FAILED`, requested/resolved `1/0`, one failed logical operation,
one transport attempt, zero checkpoints, `LIVE_PROVIDER_REPORTED` credit semantics,
unavailable credits, and failed V0.2 delivery. Strict JSON/XLSX/Markdown parity and an
OOXML content fingerprint are N/A because those artifacts were not produced.

## H. Full-run go/no-go

**NO-GO.** The smoke did not satisfy status `SUCCEEDED`, requested/resolved `1/1`, two
logical operations, available Provider credits, four valid artifacts, or V0.2 parity.

## I. 3-ASIN operation, attempt, and credit result

The approved three-ASIN invocation was not run. Operation count: `0`; transport attempt
count: `0`; credits: N/A.

## J. Cumulative credit audit

Provider-reported smoke credits were unavailable, so neither the smoke `<=3` gate nor
the cumulative `<=12` gate can be established. No second invocation was consumed.

## K. Full artifacts and parity

N/A because the full acceptance invocation was prohibited by the failed smoke gate.

## L. Provider-vs-report consistency

No report was produced. No missing economics, competitor authority, Product Direction,
Shortlist, Opportunity, or Keyword evidence was fabricated or converted to zero.

## M. Operator acceptance

Not performed because no operator XLSX or Markdown artifact was produced.

## N. Secret safety

- Persisted credential-value matches: `0`.
- Persisted non-redacted authorization/API-key literal matches: `0`.
- No raw live response, checkpoint, report JSON, XLSX, or Markdown is committed.
- The live output remains outside the repository.

## O. Validation evidence

This sanitized R1 document is new evidence. It preserves the original SP-039G blocked
record and contains only allowlisted status/reason/trace/credit diagnostics, operation
counts, artifact hashes, and gate decisions.

## P. Frozen regressions and full suite

Frozen Intelligence semantics, formulas, classifiers, endpoint mappings, request
fingerprint/resume behavior, output ownership, V0.1 compatibility, and V0.2 fixture
behavior were unchanged.

- Gate-restoration focused checks: `84 passed, 9 subtests passed`.
- Final full offline suite: `1113 passed, 16 skipped, 497 subtests passed`.
- Final `git diff --check`: passed.

## Q. Final live-gate and default-version state

The temporary V0.2 live gate removal was restored after the failed smoke. V0.2 remains
fixture-only; V0.1 remains the omitted-version default.

## R. Final verdict

**BLOCKED — AUTHENTICATION**

## S. Branch, remote, and workspace

Work was performed only on `codex/task-sp-039g-r1-xiyou-v2-credential-recovery` from
the exact required baseline. Final commit, remote push, and workspace state are reported
after this validation record is committed.
