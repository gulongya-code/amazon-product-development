# TASK-SP-042A Route Discovery V2 to Market Report V0.2 integration

Date: 2026-08-29

Baseline: `da651cf397a0b4c6d1a1b991359c6d68d3b3ca25`

Branch: `codex/task-sp-042a-route-discovery-market-report-integration`

## Purpose

SP-042A adds one narrow, deterministic boundary from the completed Route
Discovery V2 result contract to the existing Market Report V0.2 data flow.  The
integration is reference-only: the Route V2 result remains the authority for
route identity, membership, semantic features, market metrics, denominators,
evidence, and limitations.

This task does not change Route Discovery V2 core code, provider code, live
acquisition, or the Market Report V0.2 top-level schema.

## Pre-implementation reuse audit

| Existing component | Decision | SP-042A use |
| --- | --- | --- |
| `RouteDiscoveryV2Result` and nested V2 contracts | `REUSE_AS_IS` | Exact input authority; IDs, fingerprints, membership states, route identities, candidates, references, metrics, and denominators are revalidated, never rebuilt. |
| `canonical_json` / `deterministic_id` conventions | `REUSE_AS_IS` | Projection, attachment, reference, provenance, and evidence identities remain content-derived. |
| Market Report V0.2 `external_integrations` | `REUSE_AS_IS` | Approved optional attachment registry; avoids a top-level schema redesign. |
| Market Report `ContractReference` | `REUSE_AS_IS` | The exact Route V2 result ID/version/fingerprint is attached in the already approved `product-intelligence` namespace. |
| Market Report provenance/evidence registry | `REUSE_AS_IS` | Carries one deterministic derived-result evidence record and one source provenance record linked to the exact Route V2 result. |
| `compose_market_report_v0_2` | `EXTEND_NARROWLY` | Accepts optional evidence-registry limitations so recomposition preserves the complete existing registry state. Default behavior is unchanged. |
| SP-041D route metrics and denominators | `REFERENCE_ONLY` | Preserved inside the content-addressed Route V2 result; not converted to Market Report distributions or market-size metrics. |
| Product Route Opportunity V1 route semantics | `DO_NOT_USE` | No fallback, identity translation, or legacy route reconstruction. |

No external dependency, copied algorithm, provider call, network call, or new
license obligation was introduced.

## Integration flow

```text
exact RouteDiscoveryV2Result
  -> revalidate source result and required lineage/reference registry
  -> deterministic RouteDiscoveryV2MarketReportProjection
       - sorted unique route IDs
       - sorted unique denominator IDs
       - exact external source reference
       - one derived evidence record
       - one source provenance record
       - one external integration attachment
  -> exact MarketReportSnapshotV0_2 compatibility gate
       - CHILD_ASIN report grain
       - exact report cohort target ID + fingerprint == Route upstream dataset
       - exact listing-count agreement
       - known route-metric marketplace agreement
  -> merge by identity and recompose through compose_market_report_v0_2
  -> strict MarketReportSnapshotV0_2
```

The projection entry point is `project_route_discovery_v2(source)`.  The report
entry point is `integrate_route_discovery_v2(report, source)`.

## Input contract

`project_route_discovery_v2` accepts an exact `RouteDiscoveryV2Result` with:

- contract `route-discovery-v2-result-v1.0`;
- engine `route-discovery-v2.0`;
- valid content-derived result/route/member IDs and fingerprints;
- unique route, denominator, reference, metric, and candidate identities;
- exactly one required dataset, semantic-result, profile, config, and listing
  grain reference matching declared lineage;
- route and denominator reference sets exactly matching the projected source
  identities;
- contiguous candidate priorities and a candidate status consistent with the
  selected count; and
- metric references that resolve inside the Route V2 registry and retain the
  Route V2 listing-grain reference.

`integrate_route_discovery_v2` additionally accepts an exact, already valid
`MarketReportSnapshotV0_2`.  The report analysis-cohort reference must identify
the Route V2 upstream dataset by both target ID and content fingerprint.  Equal
counts alone never establish cohort compatibility.

## Output contract and ordering

`RouteDiscoveryV2MarketReportProjection` is a strict, content-addressed V0.2
integration contract.  Route IDs and denominator IDs are sorted lexically only
after their Route V2 semantic identities have been decided.  The sort is a
serialization rule and never decides membership, compatibility, or preference.

Report merge collections use their existing stable identity keys:

- attachments by `attachment_id`;
- references by `reference_id`;
- provenance by `provenance_id`; and
- evidence by `evidence_id`.

Equal identities with equal content are idempotent.  Equal identities with
different content fail closed.  At most one `route-discovery-v2` attachment may
exist in a report; attaching the same result again returns the existing report,
while attaching a different result fails closed.

## Availability and insufficient evidence

The attachment never upgrades Route V2 evidence:

- no viable routes -> `UNAVAILABLE` with
  `ROUTE_DISCOVERY_V2_NO_VIABLE_ROUTES`;
- viable routes plus unclassified memberships, review-required memberships, or
  insufficient candidate evidence -> `PARTIAL` with explicit limitation codes;
- viable routes, no unresolved membership, and selected candidate evidence ->
  `AVAILABLE`;
- no confidence field or synthetic confidence is created.

`ROUTE_DISCOVERY_V2_METRICS_REMAIN_SOURCE_OWNED` is always retained.  It makes
explicit that SP-042A does not reinterpret metric values, denominator IDs,
periods, or grain inside a Market Report core section.

## Provenance and evidence propagation

The external `product-intelligence` reference preserves the exact Route V2
result ID, result contract version, and semantic fingerprint.  A deterministic
report provenance record points to that same result.  A deterministic `DERIVED`
evidence record proves the attached projection and resolves to the external
reference and provenance record.

The complete upstream fact/evidence/relationship and denominator graph remains
inside the content-addressed Route V2 result.  SP-042A neither copies partial
subgraphs into the report nor relabels their evidence semantics.

## Fail-closed guarantees

Stable integration error codes cover:

- wrong or malformed input type/shape/version;
- invalid Route V2 source contract;
- duplicate route, denominator, reference, metric, or candidate identities;
- missing or incompatible source lineage/reference records;
- orphan metric references or changed product grain;
- invalid candidate ordering/status;
- incompatible report grain, cohort, count, or marketplace; and
- conflicting report attachment/reference/provenance/evidence identities.

There is no legacy fallback, count-only cohort join, marketplace guess, route
repair, duplicate suppression by value, or provider-backed retry.

## Files changed

- `src/amazon_product_intelligence/market_report/v0_2/builder.py`
- `src/amazon_product_intelligence/market_report/v0_2/integrations/__init__.py`
- `src/amazon_product_intelligence/market_report/v0_2/integrations/route_discovery_v2.py`
- `tests/test_route_discovery_v2_market_report_integration.py`
- `docs/engineering/SP_042A_ROUTE_DISCOVERY_V2_MARKET_REPORT_INTEGRATION.md`
- `docs/validation/SP_042A_COMPLETION_REPORT.md`

## Explicit non-goals

- Route Discovery V2 redesign or acceptance reclassification;
- modification of `src/amazon_product_intelligence/route_discovery_v2/**`;
- modification of the private replay script;
- provider, Sorftime, XiYou, credential, network, or live acquisition work;
- projection of route metrics into Market Report core metric/distribution
  sections;
- representative ASIN, Direct Competitor, procurement, SP-042B, or SP-042C;
- Market Report renderer or Operator Delivery changes.

## Known limitations and follow-up dependencies

- The SP-041R2 completion report at this baseline records the bounded human
  intra-route review gate as unavailable.  This integration preserves that
  limitation and does not turn automated Route V2 output into human acceptance.
- Empty/no-viable-route results attach as unavailable evidence; they do not
  create an empty-market conclusion.
- Route metrics remain externally referenced until a separately approved,
  jointly versioned Market Report section contract defines exact compatible
  cohort/window/grain/denominator semantics.
- A caller must compose the Market Report analysis cohort from the same governed
  dataset ID and fingerprint before attachment.  No implicit dataset mapping is
  provided.
- SP-042B and SP-042C remain unstarted.
