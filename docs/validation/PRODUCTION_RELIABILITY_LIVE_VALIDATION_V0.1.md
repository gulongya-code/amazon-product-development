# Production Reliability Live Validation V0.1

## 1. Verdict and scope

TASK-SP-036A passed on 2026-08-24 against required baseline
`6d7dc8edc9b0d2470f31ff6f8ae557ba4c23ffac`.

The validation used exactly the fixed Amazon US cohort, in order:

1. `B09265WXY5`
2. `B0GGR3F5KZ`
3. `B0H235BRVX`

The category was `dog water bottle` and mode was `live`. There was no discovery,
fixture fallback, pagination, variation, BSR, orders, reviews, or any provider
endpoint beyond `asin_info` and `asin_keywords`.

**Final verdict: PASS.**

## 2. Baseline and pre-network gates

- Branch started at the exact required baseline.
- Python: 3.12.10.
- Workspace and staging area were clean before work.
- `XIYOU_API_KEY`: configured; its value was never printed or serialized.
- Production source/test changes before live validation: 0.
- Focused baseline: `58 passed, 9 subtests passed in 6.93s`.
- Full baseline: `946 passed, 3 skipped, 493 subtests passed in 81.80s`.
- Buyer Need fingerprints and Market Report baseline: `9 passed in 0.70s`.
- Validation wrapper compile and offline self-test: passed.

The offline self-test executed six wrapper attempts. Three were injected locally,
three delegated to a fake transport, and every injected attempt had
`delegated_to_http=false` and no credit value.

## 3. Validation-only pre-network fault injection

`scripts/validate_sp036a_live_reliability.py` wraps the real
`HttpJsonTransport` and is itself wrapped by the production `RecordingTransport`:

```text
XiYouProvider
  -> RecordingTransport
    -> SP-036A PreNetworkFaultInjectionTransport
      -> HttpJsonTransport
```

The validation-only wrapper raises the existing typed
`ProviderConnectorError(NETWORK, retryable=True)` before calling its delegate.
It does not modify production retry, checkpoint, resume, endpoint, or request
semantics.

Required deterministic schedule:

| Logical operation | Attempt 1 | Attempt 2 |
| --- | --- | --- |
| `asin_info` | real HTTP success | not executed |
| `asin_keywords:B09265WXY5` | real HTTP success | not executed |
| `asin_keywords:B0GGR3F5KZ` | local `NETWORK`, no HTTP | real HTTP success |
| `asin_keywords:B0H235BRVX` | local `NETWORK`, no HTTP | local `NETWORK`, no HTTP |

No third attempt occurred for `B0H235BRVX`.

## 4. Faulted first run

The first of exactly two pipeline invocations ended:

- status: `FAILED`;
- typed error: `BOUNDED_RETRY_EXHAUSTED`;
- logical operation count: 4;
- transport attempt count: 6;
- executed/replayed operations: 4/0;
- HTTP delegation count: 3;
- injected failure count: 3;
- final Manifest stage: `run_manifest=COMPLETE`;
- Market Report, XLSX, and Markdown: not generated.

Attempt evidence:

| Operation | Attempt | Result | HTTP delegated | Credits |
| --- | ---: | --- | --- | ---: |
| `asin_info` | 1 | success | yes | 3.0 |
| `asin_keywords:B09265WXY5` | 1 | success | yes | 1.0 |
| `asin_keywords:B0GGR3F5KZ` | 1 | injected `NETWORK` | no | 0 |
| `asin_keywords:B0GGR3F5KZ` | 2 | success | yes | 1.0 |
| `asin_keywords:B0H235BRVX` | 1 | injected `NETWORK` | no | 0 |
| `asin_keywords:B0H235BRVX` | 2 | injected `NETWORK` | no | 0 |

The first-run credit gate passed at 5.0 provider-reported credits, below the
required maximum of 6.

## 5. Checkpoint gate

Exactly three successful live operations were checkpointed. Every checkpoint passed
the production version, inventory, integrity, safe-content, request fingerprint,
operation-contract, adapter-contract, and provenance validation.

| Operation | ASIN | File SHA-256 | Integrity SHA-256 |
| --- | --- | --- | --- |
| `asin_info` | cohort | `dcaf2f5662f56350e1b5a39cc750afe167fecd7360164f06c3da7a5e6ca8afaa` | `9592ddfe6be80d776917e3898cdbd715185e151c1a3f2df1d43816712ccfbfb6` |
| `asin_keywords` | `B09265WXY5` | `2b8858d6d4a5aadc36ce02ffcc01b6d8e120d52e7746b4cf140e9b146dcbef3c` | `c3acfc6cffa6e4a4aa48ccd7b2631b87b4652d8ce10d7187cd156ac88a8fd231` |
| `asin_keywords` | `B0GGR3F5KZ` | `03434f5206f3a9a7ebd36869f3a3889d12f9c36c7c0b6d468bab61eb6295de74` | `099c9fadfc869514bb97e31984dc080774a846145935a638f44dfa1347b38ac8` |

The failed-run Manifest SHA-256 was
`ac807631ffa72313587734943360338b6f0a9e2847ed752c03657429d77a4556`.

## 6. Resume gate and source immutability

Only after every first-run gate passed, the second and final pipeline invocation used
the normal production `resume_from` path with the same marketplace, cohort, provider
preference/configuration, live mode, and category, and a fresh destination.

| Operation | Resume source | Current transport attempts | Current HTTP |
| --- | --- | ---: | --- |
| `asin_info` | checkpoint replay | 0 | no |
| `asin_keywords:B09265WXY5` | checkpoint replay | 0 | no |
| `asin_keywords:B0GGR3F5KZ` | checkpoint replay | 0 | no |
| `asin_keywords:B0H235BRVX` | new provider operation | 1 | yes |

Resume evidence:

- replayed operations: 3;
- newly executed operations: 1;
- current-run transport attempts: 1;
- current-run HTTP delegations: 1;
- newly executed endpoint: only `asin_keywords:B0H235BRVX`;
- current-run provider-reported credits: 1.0;
- historical first-run credits were not re-counted.

The failed source contained three checkpoint files and one Manifest. SHA-256 maps for
all four files were identical before and after resume; the source directory remained
byte-for-byte unchanged.

## 7. Resumed artifacts

The resumed run completed `SUCCEEDED` with requested/resolved ASINs `3/3` and report
ID `market-report:2494c953c411c1715ba621b2d867d95e9cf20caa4e8fb59f5e8a8b0db641159e`.

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `market_report.json` | 41,123 | `4142fd0778a28b4f279ddf5134e8b38022ac1106cc76f79e70fe3bf9c62f995f` |
| `operator_market_report.xlsx` | 10,712 | `65c4c0f2d3c5b5a59650286316f819f19555098567c77698876a5ef72f0bf6b6` |
| `operator_market_report.md` | 14,120 | `d48f3ebf61b2a323aaadb7e1bf2061c1916ff524377d8ac70d09357b10e23681` |
| `run_manifest.json` | 9,233 | `594a7345c70913c2b173f013483fd54eb037fbf2edb9c59284326e8c8c349248` |

Offline validation confirmed:

- `market_report.json` is valid `market-report-v0.1`;
- XLSX is non-empty and starts with `PK`;
- Markdown is non-empty;
- Manifest final stage is `run_manifest=COMPLETE`;
- all four artifact paths belong to the fresh resume destination;
- the resumed run owns four validated checkpoints.

Truthful unavailable evidence was preserved: Competition is `PARTIAL`;
`brand_count`, `competition_concentration`, and `competition_level` are
`UNAVAILABLE` with `value=null`; Opportunity is `PENDING_DATA` with
`score_value=null`; unavailable dimensions remain `UNKNOWN` with null score and
contribution.

## 8. Credit and endpoint audit

| Invocation | Real provider operations | Provider-reported credits |
| --- | ---: | ---: |
| Faulted first run | 3 | 5.0 |
| Resume | 1 | 1.0 |
| **SP-036A cumulative** | **4** | **6.0** |

The exact cumulative HTTP operation sequence was:

1. `asin_info`
2. `asin_keywords:B09265WXY5`
3. `asin_keywords:B0GGR3F5KZ`
4. `asin_keywords:B0H235BRVX`

The three injected attempts generated zero HTTP delegations and zero credits. Total
credits were available, used `LIVE_PROVIDER_REPORTED`, and remained below the hard
maximum of 8.

## 9. Secret safety

- API-key value matches across failed/resumed files: 0.
- API-key filename matches: false.
- persisted `X-Api-Key`/authorization-header matches: 0.
- injected errors stored only safe `NETWORK` classification.
- no raw exception strings or environment variables were serialized.
- no raw live response, checkpoint, Manifest, JSON, Markdown, XLSX, or output binary
  is committed; only this sanitized report and the validation-only helper are kept.

## 10. Post-live offline regressions

- SP-036/Production Pipeline focused:
  `58 passed, 9 subtests passed in 6.45s`.
- Buyer Need fingerprints and `market-report-v0.1`:
  `9 passed in 0.72s`.
- Full suite:
  `946 passed, 3 skipped, 493 subtests passed in 77.79s`.
- `git diff --check`: passed.
- Production reliability/Intelligence/Market Report/XLSX source changes: 0.

Frozen fingerprints remained:

- Query Intent V0.3:
  `75f5accba6ad961e65849e0ee46933d361434144c251b512ae639d6523d21755`;
- Taxonomy V0.2:
  `8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6`;
- Semantic Normalization V0.1:
  `49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2`.

## 11. Limitations

This validates bounded retry and checkpoint resume for one already validated
three-ASIN XiYou cohort. It does not add or validate discovery, alternative endpoints,
partial-cohort delivery, background retry, or new Intelligence behavior. Injected
failures intentionally validate the production retry state machine without creating
provider-side failing requests or consuming credits.
