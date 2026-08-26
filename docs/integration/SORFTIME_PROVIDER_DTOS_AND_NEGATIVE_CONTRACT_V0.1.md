# Sorftime Provider DTOs and Negative Contract V0.1

Status: `SP-040B COMPLETE — OFFLINE DTO BOUNDARY`

This document records the provider-only DTO boundary delivered by GitHub Issue
#38. It starts from baseline `f2fcaa6d3a9b311ec526c45a073f80e2a0a4fe23`
and follows the evidence limits in
`SORFTIME_PROVIDER_CONTRACT_AND_MIGRATION_AUDIT_V0.1.md`. It does not implement
SP-040C mapping, transport, provider selection, pipeline integration, Renderer,
Intelligence, or report behavior.

## Reuse audit

The implementation reuses the repository's `JsonContract` decoder for exact
field names, recursive typed decoding, and unknown-field rejection. It reuses
`canonical_json` and `deterministic_id` for stable serialization and request
identity. HTTP and provider-business failures use the existing
`ProviderConnectorError` and `ProviderErrorCode` ontology; no parallel error
taxonomy was introduced.

The existing `ProviderOperation`, `ProviderCapability`, `ProviderConfig`,
`ProviderFetchStatus`, SP-040A Sorftime declarations/fixtures, and XiYou DTO test
structure were audited. They remain unchanged because SP-040B adds no connector
execution, capability selection, fetch state, or Canonical mapping. Sorftime
field spelling, sentinel rules, bounded result semantics, and US domain evidence
remain provider-specific.

## Request contracts

| Operation | Exact body fields | Fail-closed rules |
| --- | --- | --- |
| `ProductRequest` | `ASIN`, optional `Trend`, `QueryTrendStartDt`, `QueryTrendEndDt` | ASIN is exactly ten uppercase alphanumerics; Trend is only 1 or 2; dates are never inferred; a range must have both dates in order |
| `ProductVariations` | `Asin`, `PageIndex`, optional `IsSalesVolume` | Provider casing is preserved; PageIndex starts at 1; omitted sales-volume intent stays omitted/false and is never enabled implicitly |
| `ASINRequestKeyword` | `ASIN`, `PageIndex`, `PageSize` | PageIndex starts at 1; PageSize is 20..200; no pagination loop or widening is represented |

Transport domain context is outside every business body. Request DTOs have no
credential, Authorization, header, URL, session, or client field. Request IDs
are deterministic over the operation, exact provider body, and frozen domain
context.

## Frozen marketplace context

Only `domain=1` is accepted: Amazon US, marketplace `US`, currency `USD`, local
minor-unit exponent 2. Any other domain fails configuration validation. Listings
in provider documentation are not treated as accepted runtime mappings.

## Envelope and error boundary

Each operation has a strict successful envelope with exactly `RequestLeft`,
`RequestConsumed`, `Code`, `Message`, and `Data`. `Code=0` is required for typed
success. HTTP status is checked before envelope decoding, so an HTTP failure
cannot become a synthetic provider success. A nonzero business `Code` is a
provider bad-response error, not an HTTP/auth error.

Missing `Data`, explicit null `Data`, malformed `Data`, and unknown envelope or
nested fields are distinct deterministic schema failures. Empty pages are valid
bounded empty observations, not zero demand/sales. A page not fetched is not
represented as an empty page.

## ProductRequest response

The typed data slice contains `Asin`, `ParentAsin`, `VariationASIN`,
`VariationASINCount`, `Attribute`, and the nine observed nullable trend fields.
The accepted `Trend=2` fixture requires those trend fields to remain null. Counts,
variation identity uniqueness, requested-ASIN echo, and attribute row shape are
validated. Attribute rows preserve only ASIN plus observed `Color`/`Size` pairs.
A self-parent value is retained as provider data but does not prove a distinct
parent edge. Unknown product fields and raw-payload passthrough are rejected.

## ProductVariations response

Rows retain `Asin`, `ItemIndex`, `ItemTotal`, the exact observed Color/Size
property pairs, and `SalesAmount`. Row identities and indices must be unique,
ItemTotal must agree across the page, and returned rows cannot exceed the page's
declared total. The current bounded page does not prove family completeness or a
parent topology.

`SalesAmount=-1` is exposed only as `UNKNOWN` with numeric sales unavailable. It
is never exposed as `-1` or converted to zero. Other negative values fail. A
nonnegative sales value is accepted only when the request explicitly set
`IsSalesVolume=true`; omission cannot manufacture sales evidence.

## ASINRequestKeyword response

Rows retain keyword text, organic position, traffic share, 30-day search-volume
evidence, and CPC. CPC is preserved as source local minor units with explicit
USD/exponent-2 metadata; major-unit conversion is a derived `Decimal`, never an
implicit reinterpretation of the source value. Organic position is limited to
the documented/observed first three result pages. Local observation time is
preserved while timezone remains explicitly unknown.

The response exposes no provider total, marks completeness false, and describes
only the approximate last-30-day/first-three-pages result slice. Twenty returned
rows mean one bounded page, not a complete keyword universe. Missing rows are not
zero demand. Sponsored-placement data remains unavailable; nonempty sponsored
fields fail closed until separately proven.

## Fixture provenance

Fixtures under `tests/fixtures/sorftime_dtos/v0_1` are deliberately small,
sanitized JSON projections:

- `product_request_success.json`: sanitized accepted-evidence projection from
  the bounded SP-040A success facts; no raw response or secret material.
- `product_variations_success.json`: sanitized accepted-evidence projection of
  the ten-row page and `-1` unknown sentinel.
- `asin_request_keyword_success.json`: synthetic contract fixture with clearly
  synthetic keyword identities; it exercises the accepted 20-row bounded shape
  without reconstructing a raw live response.

All fixture content is deterministic, contract-relevant, and free of auth,
headers, endpoints, account identifiers, and provider payload extensions.

## Negative-contract matrix

| # | Required case | Deterministic assertion |
| ---: | --- | --- |
| 1 | ProductRequest success | strict typed envelope/data |
| 2 | ProductRequest missing Data | schema mismatch, state `missing` |
| 3 | ProductRequest null Data | schema mismatch, state `null` |
| 4 | ProductRequest nonzero Code | provider bad response |
| 5 | Variation-count mismatch | rejected |
| 6 | Malformed Attribute | rejected |
| 7 | Valid ten-row variations page | strict typed page |
| 8 | SalesAmount -1 | `UNKNOWN`, numeric value unavailable |
| 9 | Missing variation ASIN | rejected |
| 10 | Duplicate variation ASIN | rejected |
| 11 | Malformed property | rejected |
| 12 | ItemTotal mismatch | rejected |
| 13 | Valid bounded 20-row keyword page | typed, incomplete bounded slice |
| 14 | Missing keyword | rejected |
| 15 | Malformed organic position | rejected |
| 16 | Invalid traffic share | rejected |
| 17 | CPC minor-unit boundary | explicit USD minor units; zero accepted |
| 18 | Sponsored data unknown | unavailable; unsupported evidence rejected |
| 19 | Request/PageSize mismatch | rejected |
| 20 | Unknown fields | rejected at envelope and nested levels |
| 21 | HTTP failure | existing transport/auth error, never typed success |
| 22 | Secret-like persisted fields | rejected; DTO graph has no auth fields |
| 23 | JSON determinism | canonical round-trip and ordering verified |
| 24 | Network construction | socket and URL opener denied by test guards |

Additional cases cover request casing, invalid ASIN/date/trend/page bounds,
request/response ASIN mismatch, self-parent semantics, malformed/null rows,
unsupported sales values, duplicate keyword identity, page-4 organic position,
CPC range errors, synthetic fixture markers, and US-only domain rejection.

## Validation record

- Pre-change focused SP-040A: `93 passed, 91 subtests passed`.
- Pre-change relevant provider-neutral: `119 passed, 42 subtests passed`.
- Pre-change full suite: `1117 passed, 16 skipped, 506 subtests passed, 1 failed`.
- The sole baseline failure is the existing XLSX Renderer logical-fingerprint
  assertion; Renderer and golden files are outside SP-040B and remain unchanged.
- New SP-040B focused suite: `50 passed`.
- Combined SP-040A/SP-040B, XiYou/provider-neutral, Canonical, and Data Cleaning
  group: `262 passed, 133 subtests passed`.
- Frozen Intelligence, V0.1/V0.2 Market Report, Production Pipeline,
  reliability, and Batch group: `400 passed, 8 skipped, 56 subtests passed`.
- Post-change full suite: `1167 passed, 16 skipped, 506 subtests passed, 1 failed`.
- The sole post-change failure is the same test with the same expected and actual
  OOXML hashes as the baseline, so it is classified
  `BASELINE_RENDERER_NONREGRESSION`. The 50 additional passing tests are exactly
  the new SP-040B focused suite.

## Known limitations and handoff

Provider error-envelope fields beyond the proven success envelope are unknown;
HTTP failures and nonzero provider codes therefore fail closed using existing
provider-neutral error categories. Product family completeness, parent topology
from ProductVariations, positive sales window semantics, provider keyword totals,
later-page completeness, sponsored placement, timestamp timezone, and broader
domain mappings remain unproven.

SP-040C may later consume these DTOs to map only accepted evidence into the
existing Canonical model. SP-040C was not started here.
