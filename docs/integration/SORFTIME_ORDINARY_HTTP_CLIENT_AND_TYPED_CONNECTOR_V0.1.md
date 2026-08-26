# Sorftime Ordinary HTTP Client and Typed Connector V0.1

Status: `SP-040D COMPLETE — OFFLINE HTTP CONTRACT`

This document records the ordinary HTTP boundary implemented for GitHub Issue
#40 from required baseline `cac97ad3acd9af42796626a02002c5cb29de2c65`.
SP-040D is production-capable code verified only with injected transports and
fake openers. It does not register Sorftime in the Production Pipeline, change
provider selection, or make a live request.

## Exact HTTP contract

The production origin is pinned to `https://standardapi.sorftime.com`. The
public client exposes only these typed POST operations:

| Operation | Endpoint | Structured query | Exact request DTO |
| --- | --- | --- | --- |
| `ProductRequest` | `/api/ProductRequest` | `domain=1` | `SorftimeProductRequest` |
| `ProductVariations` | `/api/ProductVariations` | `domain=1` | `SorftimeProductVariationsRequest` |
| `ASINRequestKeyword` | `/api/ASINRequestKeyword` | `domain=1` | `SorftimeAsinRequestKeywordRequest` |

The content type is `application/json;charset=UTF-8`. Only US / domain 1 / USD
is accepted. Query data is represented separately from endpoint and JSON body,
then encoded deterministically by the shared transport. Raw endpoint query
strings remain rejected.

## Credential boundary

`SORFTIME_API_KEY` contains only the raw Account-SK. The client constructs the
project-owned `BasicAuth ` prefix at the final HTTP header boundary using the
existing ephemeral credential abstraction. The credential value is excluded
from repr and safe serialization. Public headers and query parameters cannot
carry or override the credential, and control-character values fail before
I/O.

Origin validation runs before credential construction. Scheme downgrade,
alternate/look-alike host, userinfo, port, path, query, fragment, and whitespace
variations are rejected. The historical arbitrary `SORFTIME_API_BASE_URL` and
Sorftime `X-Api-Key` client behavior are not part of the public client.

## DTO-first success flow

```text
exact SP-040B request DTO
    -> ProviderOperation + TransportRequest
    -> injected ProviderTransport / HttpJsonTransport
    -> HTTP status classification
    -> exact SP-040B response parser and Code=0 validation
    -> SorftimeDtoMapperV0_1
    -> existing AdaptationResult / CanonicalEvidenceBundle / ProviderFetchResult
```

The client has no arbitrary endpoint/body `request` method and no raw-dict mock
success method. The provider-neutral `ProviderRequest` boundary constructs and
validates one exact DTO before calling the typed client. Malformed 2xx payloads,
unknown fields, nonzero business codes, and request/response mismatches cannot
reach the mapper.

## Error and retry policy

HTTP 401/403 maps to non-retryable `AUTHENTICATION`; 429 maps to `RATE_LIMIT`;
408/504 maps to transient `TIMEOUT`; 5xx maps to transient
`PROVIDER_UNAVAILABLE`; other non-2xx statuses map to non-retryable
`BAD_RESPONSE`. Strict DTO failures use `BAD_RESPONSE` or `SCHEMA_MISMATCH` at
the established boundary.

The default client uses `NoRetryPolicy`, so one method call performs one HTTP
attempt. An explicitly injected `BoundedTransientRetryPolicy` can retry only
the existing transient categories and never exceeds `ProviderConfig.max_attempts`.
There is no sleeping, backoff loop, pagination loop, or implicit sales-volume
request.

## Usage and capability boundary

`RequestConsumed` and `RequestLeft` are preserved in
`SorftimeUsageEvidence` on the typed operation result. They are runtime-only,
credential-free counters and are excluded from Canonical observations, raw
evidence projections, and semantic fingerprints. Missing usage remains
representable as unknown; no XiYou credit equivalence is inferred.

The public `SorftimeProvider` advertises only fields emitted by the accepted
SP-040C mapper slice. Historical reviews, prices, ratings, category, brand,
broader marketplaces, trends/history, sponsored data, and positive-sales
semantics are absent. The former raw adapter is retained only as the explicitly
named internal `LegacySorftimeFixtureProvider` for historical Data Cleaning
fixture regression; its `provider-tool://` operations cannot become the public
ordinary-HTTP path.

## Offline acceptance record

- Real Sorftime HTTP operations: `0`
- Sorftime CLI live operations: `0`
- XiYou live operations: `0`
- Billed Sorftime requests: `0`
- New SP-040D contract scenarios: `37 passed`
- Combined SP-040A/B/C/D, connector, XiYou, Canonical, and Data Cleaning:
  `331 passed, 133 subtests passed`
- Frozen Intelligence, Market Report, Production Pipeline, Batch, and Renderer:
  `530 passed, 5 skipped, 88 subtests passed, 1 failed`
- Full suite: `1236 passed, 16 skipped, 506 subtests passed, 1 failed`.
- The frozen-group failure reproduces the exact baseline XLSX logical hash
  mismatch (`84e5...` actual versus `89ff...` expected) and is classified
  `BASELINE_RENDERER_NONREGRESSION`.

SP-040E must perform explicit provider selection and pipeline/recovery
integration later. It was not started by SP-040D.
