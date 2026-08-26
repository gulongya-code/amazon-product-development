# Sorftime Minimal Live Smoke V0.1

## Verdict

`BLOCKED — PROVIDER_CONTRACT`

The one authorized live Production Pipeline invocation reached the pinned Sorftime
ordinary-HTTP transport for `ProductRequest`, received HTTP 200, and then failed the
strict DTO/mapper boundary with the safe classification `SCHEMA_MISMATCH`.
No second operation, retry, rerun, live resume, direct API diagnostic, CLI provider
call, XiYou fallback, or `ProductVariations` call was made. The Sorftime live gate was
restored before commit.

## Baseline and runtime

- Required baseline: `9e5bd460e8ed2aafe63673aa74f0705bc3ee74e9`
- Branch: `codex/task-sp-040f-sorftime-minimal-live-smoke`
- Python: `3.12.10`
- pytest: `9.0.3`
- Initial workspace and staging: clean
- Marketplace / currency / domain: `US` / `USD` / `1`
- ASIN: `B09265WXY5`
- Category: `dog water bottle`
- Report request: default `market-report-v0.1`

## Credential prerequisite

- Launch-process `SORFTIME_API_KEY`: present and non-empty
- Windows User-scoped value: not inspected because the launch process already had the variable
- User-to-process bridge: not required and not performed
- Credential value, length, prefix, suffix, hash, authentication header, profiles, and credential files: not inspected or recorded
- Separate authentication ping: not performed

## Bounded code change and offline preflight

The temporary Sorftime live rejection was removed only long enough to validate the
smallest explicit live runtime: Sorftime-only registry, pinned origin, environment
credential reference, `NoRetryPolicy`, `max_attempts=1`, and live
`REQUEST`-usage semantics. The final non-PASS state restores the rejection while
retaining offline-testable runtime composition and usage-gate code.

Before network access:

- SP-040A–E / Sorftime / Pipeline / recovery / XiYou / Canonical / Data Cleaning / Market Report / Batch focused tests: `293 passed, 5 skipped, 180 subtests`
- Full suite: `1255 passed, 16 skipped, 550 subtests`, plus the unchanged baseline Renderer logical-fingerprint failure
- Baseline Renderer actual hash: `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`
- Acquisition plan: exactly `ProductRequest(Trend=2)` then `ASINRequestKeyword(PageIndex=1, PageSize=20)`
- Production Pipeline `ProductVariations` reachability: zero
- Repository delta secret-pattern hits: zero
- Automated live calls: zero

## Single smoke invocation

Exactly one invocation used this shape; no report-version or resume argument was supplied:

```text
amazon-intel run --market US --asin B09265WXY5 --provider sorftime \
  --category-name "dog water bottle" --output-dir <fresh-temp-output> --mode live
```

### Provider operation and attempt accounting

| Planned operation | Logical status | Transport attempts | Safe result |
|---|---:|---:|---|
| `ProductRequest` | `FAILED` | 1 | HTTP 200; strict boundary `SCHEMA_MISMATCH` |
| `ASINRequestKeyword` | not started | 0 | stopped after ProductRequest contract failure |

- Live Pipeline invocations: `1`
- New logical operations: `1`
- Total transport attempts: `1`
- Retries: `0`
- Replayed operations: `0`
- XiYou calls/fallbacks: `0`
- `ProductVariations` calls: `0`
- Sorftime CLI live calls: `0`
- Direct/ad-hoc Sorftime calls: `0`

HTTP 401/403 was not observed, so this was not classified as authentication failure.
The accepted typed-envelope usage gate was not reached: consumed and remaining are
unknown, unit remains `REQUEST`, semantics are `LIVE_PROVIDER_REPORTED`, and credits
remain null. Unknown usage was not converted to zero.

## Pipeline, artifacts, and bounded truthfulness

- Requested/resolved ASINs: `1/0`
- Input validation: complete
- Provider resolution: failed
- Canonical/Data Cleaning and all downstream Intelligence stages: not reached
- Market Report / XLSX / Markdown: not produced
- Failure manifest: produced last, 4,884 bytes
- Sanitized failure-manifest SHA-256: `c03e3a8ec32d174473d566912123fa1e07797075c2a7cd4e7c094cd0dd72671e`
- No conclusions about product facts, parent/variation scope, Buyer Need, demand,
  Competition, Opportunity, or market representativeness were drawn from the failed sample
- No raw live response, checkpoint payload, log, report binary, or credential value is committed as proof

## Secret safety

Exact runtime-credential scans of captured stdout, stderr, and the smoke output found
no match. A second label/header scan found zero occurrences of credential-bearing
header/value patterns or the credential environment name. The repository delta scan
also found zero credential-value patterns. Captured invocation logs and the local
failure manifest remain outside the repository.

## Post-live offline regressions and rollout state

- Focused post-live suite: `294 passed, 5 skipped, 180 subtests`
- Full post-live suite: `1256 passed, 16 skipped, 550 subtests`, plus only the unchanged Renderer baseline exception
- Renderer/golden files: unchanged
- Real provider calls after the one smoke: zero
- Default provider: `xiyou`
- Default report version: `market-report-v0.1`
- `market-report-v0.2 + live`: still blocked
- Batch: still XiYou-only
- Sorftime live: restored to fixture-only gate because the verdict is non-PASS
- SP-040G: not started
