# Provider Connector Architecture V0.1

Status: TASK-SP-018B implementation contract
Baseline: `442b0e8a05b54d5595992f9b4191c162b3cc3a47`
Runtime: Python 3.12, standard library only

> Provider implementations are replaceable infrastructure adapters. Core business logic must not depend on any concrete third-party provider.

## 1. Scope and boundary

This foundation implements the provider acquisition boundary before cleaning, conflict resolution, calculated fields, AI analysis, and Workbook projection:

```text
Third-party transport
        -> DataProvider
        -> existing audited ProviderAdapter
        -> AdaptationResult
        -> CanonicalEvidenceBundle
        -> ProviderRegistry / ProviderResolver
```

It deliberately does not implement:

- production HTTP clients or real API calls;
- credential provisioning or storage;
- the 99 `CALCULATED` Workbook fields;
- provider weighting, conflict resolution, normalization policy, scoring, recommendations, or Workbook writes;
- SellerSprite or any other undocumented production connector.

The transport is injected. Tests use fixture-backed stubs only, so no account, credit, rate limit, or production data is touched.

## 2. Package structure

| Module | Responsibility |
|---|---|
| `connectors.base` | `DataProvider` protocol and shared adapter-backed fetch flow. |
| `connectors.models` | Configuration, capability, credential-free request, and field-result models. |
| `connectors.transport` | Transport, credential injection envelope, timeout, and bounded retry extension points. |
| `connectors.registry` | Registration, enable/disable, configuration, capability lookup, and priority ordering. |
| `connectors.resolver` | Provider-neutral field selection and fallback. |
| `connectors.errors` | Unified sanitized error categories. |
| `connectors.xiyou_v0_1` | XiYou operations and audited capability declarations. |
| `connectors.sorftime_v0_1` | Sorftime tool operations and audited capability declarations. |

No existing business, intelligence, Canonical, Adapter, Workbook, or export module imports a concrete connector.

## 3. Provider interface

`DataProvider` is a runtime-checkable structural protocol:

```python
class DataProvider(Protocol):
    provider_id: str
    display_name: str
    capabilities: tuple[ProviderCapability, ...]

    def capability(self, canonical_field: str) -> ProviderCapability | None: ...
    def fetch(
        self,
        request: ProviderRequest,
        configuration: ProviderConfig,
    ) -> ProviderFetchResult: ...
```

Stable IDs are machine-readable lowercase values such as `xiyou` and `sorftime`. Display labels are separate and have no business semantics.

`AdapterBackedProvider` implements the shared workflow. A concrete provider supplies only:

- operation descriptions;
- capability descriptions;
- its existing audited offline Adapter;
- an injected transport.

The shared workflow does not contain `if provider == "xiyou"` or equivalent provider-specific branches.

## 4. Provider Registry

`ProviderRegistry` owns runtime registrations and configurations. It supports:

```python
registry.register(provider, configuration)
registry.get("xiyou")
registry.enabled()
registry.set_enabled("sorftime", False)
registry.set_priority("xiyou", 20)
registry.capabilities("metric.price")
registry.candidates("metric.price")
```

Duplicate registration and unknown IDs produce stable connector errors. Enabled providers and field candidates are deterministic: lower configured priority is tried first, then stable `provider_id` breaks ties.

The generic `build_registry()` composition helper accepts `(DataProvider, ProviderConfig)` pairs. Adding another provider does not require a change to the registry or resolver.

## 5. Configuration

`ProviderConfig` contains no credential value. It carries:

| Field | Purpose |
|---|---|
| `provider_id` | Stable registration identity. |
| `enabled` | Whether this provider participates in resolution. |
| `priority` | Default provider ordering; lower values run first. |
| `credential_env` | Environment-variable name, never its value. |
| `timeout_seconds` | Per-attempt transport boundary. |
| `max_attempts` | Hard bound from 1 through 5. |
| `field_priorities` | Optional per-Canonical-field priority override. |

The generic environment loader recognizes:

```text
API_PROVIDER_<PROVIDER_ID>_ENABLED
API_PROVIDER_<PROVIDER_ID>_PRIORITY
API_PROVIDER_<PROVIDER_ID>_TIMEOUT_SECONDS
API_PROVIDER_<PROVIDER_ID>_MAX_ATTEMPTS
```

The actual secret remains in the separately named environment variable referenced by `credential_env`. Missing credentials raise `CONFIGURATION` before transport execution. A disabled provider does not require a credential and is skipped by resolution.

No provider is compiled as a global primary provider. Default and field-level priority are configuration data.

## 6. Capability model

`ProviderCapability` expresses:

```text
provider_id
canonical_field
capability_status
source_field
endpoint
operation
payload_kind
priority
notes
Canonical selector
```

The allowed Provider capability states are exactly:

- `AVAILABLE`
- `PARTIAL`
- `UNAVAILABLE`
- `UNKNOWN`

`CALCULATED` intentionally does not exist in this enum. Calculation is a later internal system responsibility and cannot be claimed by a provider.

An `AVAILABLE` or `PARTIAL` capability must identify a source field, endpoint/tool, operation, payload kind, and Canonical selector. `UNAVAILABLE` and `UNKNOWN` entries intentionally have no executable operation.

Current immutable semantic boundaries remain:

- `keyword.locale`: `UNAVAILABLE`;
- `workflow.manual_review_status`: `UNAVAILABLE`;
- `product.seller`: `UNKNOWN`;
- `keyword.estimate_method_status`: `UNKNOWN`.

Sorftime capabilities are limited to fields confirmed by the audited repository evidence. The logical `provider-tool://sorftime/...` locator is intentionally not presented as a public HTTP endpoint.

## 7. XiYou foundation

The XiYou connector describes the SP-018A P0 operations already supported by `XiYouAdapterV0_1`:

| Operation | Endpoint | Adapter payload kind |
|---|---|---|
| ASIN current facts | `/v1/asins/info` | `asin_info` |
| Variations | `/v1/asins/variations` | `asin_variations` |
| Recent orders | `/v1/asins/orders` | `asin_orders_last_30_days` |
| BSR trend | `/v1/asins/bsrInfo/trends/daily` | `asin_bsr_trends` |
| Keyword metrics | `/v1/searchTerms/info` | `keyword_info` |
| Keyword to product | `/v1/searchTerms/analysis/list/period` | `keyword_asin_analysis` |
| Product to keyword | `/v1/asins/research/list/period` | `asin_keywords` |

Forward and reverse relationship capabilities have different Canonical field identifiers and different operations. They are never merged into a source-less bidirectional edge.

XiYou authentication is represented as an ephemeral `X-Api-Key` credential plus the public `X-Auth-Version: 2.0` header. The credential is not included in safe request serialization, request `repr`, Canonical context, raw request parameters, or error details.

## 8. Sorftime foundation

The Sorftime connector describes only audited tool contracts:

| Operation | Logical locator | Adapter payload kind |
|---|---|---|
| Product detail | `provider-tool://sorftime/product_detail` | `product_detail` |
| Variations | `provider-tool://sorftime/product_variations` | `product_variations` |
| Reviews (P1) | `provider-tool://sorftime/product_reviews` | `product_reviews` |

Confirmed detail, variation, sales-estimate, and review fields are declared without guessing undocumented transport paths. A capability may be provider-confirmed while a particular response omits the field; that attempt returns `FIELD_MISSING` and permits fallback.

Provider estimates, Sorftime self-parent semantics, and the `SalesAmount = -1` sentinel retain the existing Adapter rules. The connector does not reinterpret them.

## 9. Resolution and fallback

For one `ProviderRequest.canonical_field`, the resolver performs:

```text
enabled registry entries
        -> AVAILABLE/PARTIAL candidates only
        -> configured field/provider priority
        -> provider fetch + audited adaptation
        -> RETURNED or explicit EMPTY: select
        -> FIELD_MISSING or failure: try next candidate
        -> all exhausted: RESOLUTION_EXHAUSTED
```

Fallback attempts retain only sanitized operational evidence:

```text
provider_id
attempt status
unified error code, when failed
```

An explicitly successful empty directional query is selected as `EMPTY` evidence. It is not treated as a provider failure, is not converted to zero, and does not trigger a second provider merely to manufacture a populated answer.

This resolver selects an acquisition source. It does not resolve conflicts between already collected Canonical observations and does not implement provider weighting.

## 10. Provenance and raw values

The connector creates no parallel provenance contract. It passes the provider payload and explicit context to the existing audited Adapter. The result is the existing:

```text
AdaptationResult
  -> RawEvidenceRecord
  -> CanonicalEvidenceBundle
  -> Canonical Observation
  -> Provenance
  -> TransformationProvenance
```

`ProviderFetchResult.observations` is only an index over the exact observations already contained in the bundle. Its `provenance` property returns the existing `Provenance` instances.

Consequently raw value, normalized value, presence state, provider, source field, retrieval time, collection run, mapping version, transformation run, and immutable raw reference remain available without duplication or flattening.

Request parameters are explicitly credential-free. Sensitive keys such as `api_key`, `token`, `authorization`, `cookie`, `password`, and `secret` are rejected before transport construction.

## 11. Unified error model

All transport and provider failures cross the connector boundary as `ProviderConnectorError` with a stable `ProviderErrorCode`:

| Code | Meaning |
|---|---|
| `CONFIGURATION` | Missing/invalid provider configuration or credential reference. |
| `AUTHENTICATION` | Provider rejected authentication. |
| `RATE_LIMIT` | Provider returned a rate-limit response. |
| `TIMEOUT` | Timeout response or local timeout. |
| `NETWORK` | Transport/network failure. |
| `BAD_RESPONSE` | Non-success response not covered by a more specific category. |
| `SCHEMA_MISMATCH` | Payload cannot pass the audited Adapter contract. |
| `PROVIDER_UNAVAILABLE` | Disabled/unavailable provider or server-side failure. |
| `FIELD_UNAVAILABLE` | Capability is absent, `UNKNOWN`, or `UNAVAILABLE`. |
| `DUPLICATE_PROVIDER` | Duplicate registry ID. |
| `PROVIDER_NOT_REGISTERED` | Registry lookup failed. |
| `RESOLUTION_EXHAUSTED` | All eligible candidates failed or omitted the field. |

Third-party response bodies and credential values are not copied into connector errors.

## 12. Timeout, retry, and rate-limit boundary

Every `TransportRequest` carries a positive timeout. `max_attempts` is bounded to five. The default `NoRetryPolicy` never retries.

A custom `RetryPolicy` may permit another attempt only within the configured bound. Rate-limit errors can carry sanitized `retry_after_seconds` metadata so a future production transport/policy can schedule correctly. The foundation performs no unbounded loop and introduces no hidden sleep.

This task does not ship a production HTTP transport. A later production transport must:

- inject the ephemeral credential without logging it;
- obey the timeout and retry decision;
- map provider-specific failures to the unified error model;
- sanitize headers and response diagnostics;
- avoid returning secret-bearing metadata.

## 13. Adding or replacing a provider

To add a future provider such as SellerSprite after official contracts are available:

1. implement `DataProvider`, normally by configuring `AdapterBackedProvider`;
2. add audited provider operations and capability declarations;
3. supply an offline Adapter that emits the existing Canonical contracts;
4. inject a transport;
5. create a `ProviderConfig` and register the `(provider, config)` pair;
6. add fixture-backed provider tests.

Do not modify XiYou, Sorftime, `ProviderRegistry`, `ProviderResolver`, Canonical models, business algorithms, or Workbook code.

Removing Sorftime requires disabling/removing its registry entry and transport/configuration only. XiYou-only and Sorftime-only registries are valid.

## 14. Mechanical acceptance scenarios

Automated tests cover:

1. XiYou enabled + Sorftime enabled: deterministic registry ordering.
2. XiYou enabled + Sorftime disabled: XiYou-only initialization.
3. XiYou disabled + Sorftime enabled: Sorftime-only initialization.
4. Test-only `FakeProvider`: registration and resolver execution without changing existing providers or core resolution.
5. Primary failure or field omission: fallback to the next eligible provider.
6. Returned data: existing Canonical provenance exposes provider, source field, retrieval time, status, raw value, and normalized value.

Additional tests cover duplicate registration, all four capability states, absence of `CALCULATED`, explicit empty query semantics, missing credentials, secret redaction, bounded retry, rate limit, timeout, forward/reverse direction, and exhausted resolution.

## 15. Deferred work

- Production transport implementation and credential provisioning.
- Exact Sorftime public transport schema after official documentation becomes testable.
- Broader P1/P2 operations and pagination/completeness policies per endpoint.
- Cleaning/normalization and the 99 calculated fields in their later tasks.
- Conflict policy, weighting, freshness policy, AI analysis, and Workbook/UI integration.

These deferrals do not require changing the Provider interface, Registry, Capability model, Resolver, or existing Canonical evidence contracts.
