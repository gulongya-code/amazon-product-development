# SP-035A Reverse-Keyword Contract Parity Addendum

Status: **PASS — READY_TO_RESUME_SP035**

Task: TASK-SP-035A
Validation date: 2026-08-24 (Asia/Shanghai)

## 1. Baseline and scope

- Repository baseline branch: `codex/release-market-report-v0.1`.
- Required and observed baseline: `5f9a017c8e15689994a27a53929e395a8f8d518e`.
- Validation branch: `codex/task-sp-035a-reverse-keyword-parity`.
- Python: `3.12.13` from the bundled workspace runtime.
- Workspace and staging were clean before editing.
- `XIYOU_API_KEY`: configured; the credential value was never printed or persisted.
- Baseline focused tests: `15 passed, 4 subtests passed in 5.44s`.
- Baseline full suite: `934 passed, 490 subtests passed in 190.67s`.

The change is limited to the Production Pipeline XiYou request boundary, safe error
projection, focused tests, and this addendum. No Intelligence model, Buyer Need rule,
Competition formula, Opportunity scoring policy, Market Report schema, or XLSX design
was changed.

## 2. Root-cause confirmation

The merged Production Pipeline sent the reverse-keyword request with only:

```json
{
  "asin": "<ASIN>",
  "country": "<marketplace>"
}
```

The checked-in successful SP-032E capture for the same `asin_keywords` operation and
the controlled ASIN `B09265WXY5` records:

```json
{
  "asin": "B09265WXY5",
  "country": "US",
  "page": 1,
  "pageSize": 20,
  "period": "last7days",
  "sort": {"field": "traffic", "order": "desc"}
}
```

That capture returned 20 rows for one provider-reported credit. The official XiYou
page for `POST /v1/asins/research/list/period` also defines `asin`, `country`, `page`,
`pageSize`, `period`, and `sort` as the reverse-keyword request contract:

`https://openapi-doc.xydc.com/331502595e0`

Repository evidence and provider documentation therefore support contract parity;
the fix does not guess a new endpoint or operation.

## 3. Repaired request contract

Every Production Pipeline `asin_keywords` request now uses the fixed project-owned
bounded helper and exactly this shape:

```json
{
  "asin": "<normalized ASIN>",
  "country": "<marketplace>",
  "page": 1,
  "pageSize": 20,
  "period": "last7days",
  "sort": {"field": "traffic", "order": "desc"}
}
```

There is no configuration switch, pagination loop, retry, discovery request, or new
endpoint. The parameters flow through the normal immutable `ProviderRequest`, safe
transport summary, adaptation context, and request/provenance identity.

## 4. Safe resolver diagnostics

The Production Pipeline still exposes the outer `PROVIDER_FAILURE` and original
`provider_error_code`. For an exhausted resolver only, it now optionally preserves:

```json
"resolver_attempts": [
  {
    "provider_id": "xiyou",
    "status": "FAILED",
    "error_code": "SCHEMA_MISMATCH"
  }
]
```

The projection is allowlisted:

- provider ID must be the Production Pipeline provider `xiyou`;
- status must be an existing `ProviderAttemptStatus` value;
- error code must be null or an existing `ProviderErrorCode` value;
- only `provider_id`, `status`, and `error_code` are retained.

Unknown provider IDs, statuses, error codes, raw bodies, headers, exception text, and
arbitrary connector details are discarded. Tests distinguish `SCHEMA_MISMATCH`,
`FIELD_MISSING` with null error code, and HTTP-style `PROVIDER_UNAVAILABLE` without
preserving injected secret fields.

## 5. Offline gate

All offline checks completed before the live invocation and made zero XiYou calls:

- Compile check: passed.
- Production Pipeline focused: `17 passed, 4 subtests passed in 7.17s`.
- Buyer Need fingerprints plus Market Report version: `2 passed in 0.66s`.
- Full suite: `936 passed, 490 subtests passed in 145.77s`.
- `git diff --check`: passed.

After the smoke, an additional fixture-only provenance assertion was added and all
final offline gates were rerun without another live call: focused
`17 passed, 4 subtests passed in 5.01s`, frozen fingerprints/version
`2 passed in 0.73s`, and full suite
`936 passed, 490 subtests passed in 122.37s`.

The final full suite used Python 3.12.10 with zlib 1.3.1 and openpyxl 3.1.5,
matching the repository's frozen XLSX byte-fingerprint environment. The desktop
artifact-renderer Node paths and the already-installed rapidfuzz dependency were
provided locally; no dependency download or network access occurred.

Focused coverage proves exact reverse-keyword parameters, one operation per ASIN, no
pagination/retry, zero-network fixture execution, deterministic report output, safe
nested diagnostics, secret safety, output ownership, frozen fingerprints, and frozen
Market Report version.

## 6. Controlled live re-smoke

Exactly one SP-035A live invocation was made after the offline gate:

```text
amazon-intel run \
  --market US \
  --asin B09265WXY5 \
  --category-name "dog water bottle" \
  --output-dir outputs/task-sp-035a/smoke-5f9a017-20260824 \
  --mode live \
  --run-id sp035a-smoke-5f9a017-20260824
```

| Check | Result |
| --- | --- |
| Final status | `SUCCEEDED` |
| Requested/resolved | `1/1` |
| Operations | `asin_info`, `asin_keywords` |
| Operation count | 2 |
| Duplicate/retry calls | 0 |
| Credit semantics | `LIVE_PROVIDER_REPORTED` |
| SP-035A observed credits | 2.0 |
| Fixture fallback | none |
| 3-ASIN run | not performed |

Stage states were `COMPLETE` except the existing truthful
`category_competition=PARTIAL` and `opportunity_intelligence_scoring=PARTIAL` states.
The unavailable numeric Opportunity score remained explicit rather than becoming a
fake zero.

## 7. Artifact validation

The fresh output directory contained exactly the four current-run artifacts:

| Artifact | Size | SHA-256 / validation |
| --- | ---: | --- |
| `market_report.json` | 33,259 | `c82cd55f0d463aaf05d97e89c485c04459fe4276afb0443bb3bd9fa903bf8b64` |
| `operator_market_report.xlsx` | 10,050 | `f9b68d411e5ac64547f404a73899a46e18bc8d5b5d8643d75379d6aad8524532` |
| `operator_market_report.md` | 10,448 | `c896a2cb3fda0312a07f6ed02294f57e7cf74ce7a5ebbdf0b811cdc2500cf771` |
| `run_manifest.json` | 5,147 | `d488410f3e0408aebb5f92c954a64ad9f619843e3be51b779e52a97602767f5e` |

- Serialized Market Report validation passed as `market-report-v0.1`.
- Report ID: `market-report:b015adc2fc7124cdec43a69e5b1402c786d5b2594b239e82ddcfd9452b9fb06b`.
- XLSX begins with `504B0304` (`PK`) and is non-empty.
- Markdown is non-empty.
- Manifest final stage is `COMPLETE` and every artifact path belongs to the fresh
  current-run directory.

The live output files are not committed; hashes and sanitized evidence in this
addendum are sufficient.

## 8. Secret and credit audit

- CLI stdout/stderr API-key match: `false`.
- All JSON/Markdown/Manifest output API-key matches: `false`.
- XLSX API-key match: `false`.
- Output filename API-key match: `false`.
- No raw provider response, authorization header, API key, or live binary is committed.

Credit audit:

| Task | Observed credits |
| --- | ---: |
| SP-035 blocked smoke | 1.0 |
| SP-035A repaired smoke | 2.0 |
| Cumulative | **3.0** |

SP-035A is within its `<=3` gate, and the cumulative value is within the hard `<=4`
gate.

## 9. Frozen regression evidence

- Buyer Need Query Intent V0.3:
  `75f5accba6ad961e65849e0ee46933d361434144c251b512ae639d6523d21755`.
- Buyer Need Taxonomy V0.2:
  `8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6`.
- Semantic Normalization V0.1:
  `49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2`.
- Market Report: `market-report-v0.1`.

## 10. Verdict and remaining boundary

**PASS — READY_TO_RESUME_SP035**

The one-ASIN production path now succeeds with the validated bounded reverse-keyword
contract. This task does not validate a 3-ASIN cohort or claim market
representativeness; that remains exclusively in TASK-SP-035 under its own separate
live-cost gate.
