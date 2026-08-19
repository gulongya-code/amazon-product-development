# Data Cleaning End-to-End V0.1

Status: implementation complete; live validation requires a configured provider credential

## 1. Definition and boundary

Data Cleaning V1 means provider data can enter a governed, Provider-neutral pipeline and
emerge as normalized Canonical data with explicit quality and provenance:

```text
Provider
  -> production or fixture Transport
  -> AdapterBackedProvider Connector
  -> audited Provider Adapter
  -> Canonical Evidence
  -> CanonicalNormalizationPipeline
  -> mechanical Quality Summary
  -> CleanCanonicalResult
```

It does **not** mean that all 157 Workbook fields are available, calculated business
metrics are complete, AI analysis is complete, or a final product recommendation is ready.
The service has no Workbook, scoring, recommendation, Comparable Product, or AI dependency.

## 2. Reused contracts and minimal additions

The implementation reuses `DataProvider`, `AdapterBackedProvider`, `ProviderRegistry`,
`ProviderCapability`, the audited XiYou and Sorftime adapters, `CanonicalEvidenceBundle`,
`Provenance`, `DataQualityIssue`, `CanonicalNormalizationPipeline`, and the existing
normalization rule registry.

The V0.1 additions are deliberately narrow:

- `HttpJsonTransport` performs one bounded-size JSON/HTTPS request attempt.
- `BoundedTransientRetryPolicy` lets the Connector repeat only network, timeout, and
  provider-unavailable failures up to `ProviderConfig.max_attempts`.
- `DataCleaningService` fetches one audited operation, indexes its Canonical observations
  through declared selectors, normalizes each field independently, and returns a clean run.
- `CleanCanonicalResult`, `CleanFieldResult`, and `CleaningQualitySummary` are deterministic
  inspection contracts. They do not contain the full raw response.
- `python -m amazon_product_intelligence.data_cleaning` is the explicit operator entry point.

## 3. Production transport and authentication

### XiYou

The verified service origin is `https://openapi.xydc.com`. The minimal V1 live operation is
`POST /v1/asins/info`. Authentication is injected only as the `X-Api-Key` header from the
`XIYOU_API_KEY` environment-variable reference; `X-Auth-Version: 2.0` is a public header.
The credential value is excluded from repr, safe request summaries, errors, clean results,
fixtures, and documentation.

The current official OpenAPI V2 response example exposes `entities` at the response root,
whereas the earlier audited provider-tool fixture used `status/data`. The production
Connector therefore uses the distinct, versioned mapping
`xiyou_product_info_http_v2_mapping_v1`. It maps the verified top-level shape without
rewriting raw evidence and retains the legacy envelope only as an offline migration shape
with truthful source locators. This avoids treating a Transport rewrite as provenance.

References: [XiYou OpenAPI](https://openapi-doc.xydc.com/) and
[XiYou ASIN information operation](https://openapi-doc.xydc.com/335282030e0).

### Sorftime

The credential reference is `SORFTIME_API_KEY`. Sorftime fixture E2E is supported through
the existing audited provider-tool contract. No production HTTP endpoint is implemented,
because the repository audit does not establish one. Even with a configured credential,
live mode fails closed with `PROVIDER_UNAVAILABLE` rather than guessing an endpoint.

### Missing credentials

Live mode resolves credentials before transport execution. A missing value returns a
structured `BLOCKED_CONFIGURATION` result with connector error code `CONFIGURATION`; it
does not attempt HTTP and does not print the process environment or a traceback.

## 4. HTTP safety and error behavior

`HttpJsonTransport` accepts credential-free HTTPS origins and relative absolute-path
endpoints only. It sends deterministic JSON, enforces a timeout and a two-megabyte response
limit, and returns only safe response metadata (`X-Trace-Id`, `X-Cost-Credits`, numeric
`Retry-After`). Full headers are not copied into output.

Connector errors use the existing vocabulary:

| Condition | Connector result | Retry behavior |
|---|---|---|
| timeout | `TIMEOUT` | bounded |
| network failure | `NETWORK` | bounded |
| selected 5xx | `PROVIDER_UNAVAILABLE` | bounded |
| 401/403 | `AUTHENTICATION` | none |
| 429 | `RATE_LIMIT` with safe numeric retry-after metadata | none in V0.1 |
| invalid JSON / oversized response | `BAD_RESPONSE` | none |
| audited adapter mismatch | `SCHEMA_MISMATCH` | none |
| missing credential | `CONFIGURATION` | no request |
| unaudited HTTP operation | `PROVIDER_UNAVAILABLE` | no guessed request |

Rate limits are not blindly retried. Provider exception messages and response bodies are
not echoed into errors, so credentials or signed material cannot leak through third-party
details.

## 5. Clean result contract

The run ID is the existing normalization-run identity; no fourth lineage system is added.
It connects the provider request to collection, transformation, normalization, and final
quality output. `CleanCanonicalResult` contains:

- normalization `run_id`, provider, operation, retrieval time, and run status;
- stable field ordering;
- a mechanical quality summary;
- field-level raw evidence references, Canonical observation IDs, and provenance;
- mapping versions, transformation-run IDs, and query-execution IDs;
- Canonical mapping and normalization quality issues plus safe adapter diagnostics.

`CleanFieldResult` contains the Canonical field, source operation/field, capability status,
raw and mapped values, normalized value, presence/semantic/normalization statuses, unit,
normalization rule application, evidence reference, quality issues, and Canonical
provenance. It never embeds `AdaptationResult.raw_snapshot`.

Decimal values use the normalization package's deterministic string policy in JSON.
Timezone-aware timestamps remain ISO 8601 strings with their offset. Maps and output fields
are sorted; fixture runs use fixed governed timestamps and deterministic run identities.

## 6. Run and field statuses

Run statuses are `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, and `BLOCKED_CONFIGURATION`.
One missing or invalid field does not discard valid independent fields. A successful
Connector/Adapter run becomes `PARTIAL_SUCCESS` when mechanical field aggregation finds
missing, explicit-null, unknown, empty-query, invalid, partial, or quality-issue evidence.

The summary definitions are mechanical and Provider-neutral:

- `fields_observed`: field results whose presence is `PRESENT`;
- `fields_normalized`: a normalization rule produced a value different from mapped input;
- `fields_unchanged`: present normalized/not-applicable fields whose value stayed equal;
- `fields_missing`: no field observation and no field-level invalid mapping evidence;
- `fields_explicit_null`, `fields_unknown`, `fields_query_returned_empty`, and
  `fields_not_applicable`: exact Canonical presence states;
- `fields_invalid`: semantic `INVALID` or normalization `FAILED`;
- `fields_partial`: partial provider capability or ambiguous normalization;
- `quality_issue_count`: unique Canonical issue IDs from mapping and normalization.

`MISSING`, `EXPLICIT_NULL`, `UNKNOWN`, `QUERY_RETURNED_EMPTY`, `NOT_APPLICABLE`, numeric
zero, Boolean false, and an empty collection remain distinct. No absence state is converted
to zero or false.

## 7. Offline fixture operation

Run from the repository root with Python 3.12 and process-level `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = 'src'
python -m amazon_product_intelligence.data_cleaning --fixture --provider xiyou --operation asin_info
python -m amazon_product_intelligence.data_cleaning --fixture --provider sorftime --operation product_detail
```

Use `--output json` for the complete clean result, or the default `summary` for the safe
mechanical counts. `--fixture-file <path>` can select another explicitly sanitized JSON
fixture. Fixture mode injects an isolated in-memory non-secret sentinel only to cross the
existing Connector credential boundary; it never reads production credentials or opens a
network transport.

The committed schema-focused fixtures contain public test product data only. They contain
no token, account metadata, cookie, authorization header, or live response dump.

Example XiYou fixture summary:

```text
provider: xiyou
operation: asin_info
status: SUCCESS
fields_observed: 4
fields_normalized: 2
fields_unchanged: 2
fields_missing: 0
fields_unknown: 0
fields_invalid: 0
quality_issue_count: 0
```

Sorftime's fixture is intentionally `PARTIAL_SUCCESS`: its audited detail response produces
14 observed field results, one missing field, four partial field results, and five quality
issues while retaining its valid fields.

## 8. Explicit live operation

Credentials must be configured through the process environment or the operator's approved
secret-management mechanism using only these references:

```text
XIYOU_API_KEY
SORFTIME_API_KEY
```

Do not put a credential value in an argument, checked-in file, fixture, Markdown document,
or shell-history example. Merely having a credential in the environment never triggers a
request. The separate `--live` gate is also mandatory.

XiYou minimal command shape:

```powershell
$env:PYTHONPATH = 'src'
python -m amazon_product_intelligence.data_cleaning --live --provider xiyou --operation asin_info --input-json '{"entities":[{"country":"US","asin":"PUBLIC_SAMPLE_ASIN"}]}'
```

This task did not execute that command because `XIYOU_API_KEY` and `SORFTIME_API_KEY` were
both not configured. The current validation level is therefore:

```text
XiYou: READY_NOT_VALIDATED (credential NOT_CONFIGURED)
Sorftime: fixture validated; live HTTP NOT_SUPPORTED by audited contract
```

## 9. Partial failure, schema drift, and unmapped fields

Normalization remains field-isolated. If one source primitive is invalid, the adapter's
field issue is attached to the absent clean field as `UNKNOWN`/`INVALID`/`FAILED`, while
valid observations continue through normalization. A genuinely absent source field remains
`MISSING` with a null value.

Unexpected source fields are retained in raw evidence and surfaced as safe adapter
diagnostics. The service does not invent a Canonical field. Missing identity or an
unexpected provider envelope fails through the audited adapter as a controlled
`SCHEMA_MISMATCH`; no partial product identity is fabricated.

## 10. Provenance path

Every observed clean field supports this trace:

```text
CleanFieldResult.normalized_value
  -> NormalizationRuleApplication (rule/version/run/fingerprints)
  -> CleanFieldResult.mapped_value
  -> Canonical observation_id and Provenance.source_field
  -> TransformationProvenance (mapping version/run/raw reference)
  -> RawEvidenceRecord reference
  -> Provider and source operation
```

The raw content remains at the evidence boundary and is not copied into the default
operator output.

## 11. Provider replacement and tests

The service discovers operation fields from registered `ProviderCapability` records and
matches Canonical observations through `CanonicalSelector`. It contains no XiYou/Sorftime
branch. Offline tests run XiYou, Sorftime, and a structurally conforming future FakeProvider
through the same `DataCleaningService` without editing the core.

All ordinary regression tests and fixture commands are offline. Production transport is
constructed only by explicit `--live`. The transport tests inject an opener and cover
success, timeout, bounded retry, authentication failure, rate limit, 5xx, invalid JSON,
schema mismatch, response limits/error safety, and credential redaction without opening a
socket.

## 12. Known V0.1 limitations

- Live validation is not complete until an operator configures a legitimate credential and
  explicitly performs one minimal safe XiYou smoke run.
- Sorftime has no implemented live HTTP path because no audited endpoint/authentication
  placement has been approved.
- V0.1 handles one controlled request or a provider's small response; it has no pagination,
  scheduler, queue, cache, persistence, or bulk-harvest platform.
- Unknown Provider fields remain raw evidence/diagnostics until a separate Canonical mapping
  review approves them.
- Conflict resolution remains downstream. Cleaning preserves candidates and lineage; it
  does not average values or prefer a Provider.
