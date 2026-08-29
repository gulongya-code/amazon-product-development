# TASK-SP-042A completion report

Date: 2026-08-29

## A. Baseline

- Required baseline: `da651cf`.
- Verified starting HEAD:
  `da651cf397a0b4c6d1a1b991359c6d68d3b3ca25`.
- Branch:
  `codex/task-sp-042a-route-discovery-market-report-integration`.
- Startup working tree: clean.
- No fetch, pull, push, rebase, or merge was performed.  No Git command, file
  read, or file write was performed against another worktree.

## B. Reuse audit

- Reused Route Discovery V2 result, membership, route, metric, denominator,
  reference, canonical serialization, and deterministic identity contracts as
  frozen source authority.
- Reused the existing Market Report V0.2 external-integration registry and
  evidence/provenance/reference graph as the approved extension point.
- Extended only the Market Report composer to preserve optional evidence
  registry limitations during recomposition.
- Did not copy the Route V2 algorithm, invoke legacy V1 semantics, add a
  provider, or add a dependency.

Detailed audit:
`docs/engineering/SP_042A_ROUTE_DISCOVERY_V2_MARKET_REPORT_INTEGRATION.md`.

## C. Integration decision

The integration is reference-only.  It attaches the exact Route V2 result ID,
contract version, and semantic fingerprint in the approved external
`product-intelligence` namespace.  Route/member/metric/denominator payloads
remain source-owned and content-addressed; no Market Report core analytical
section is repurposed.

Availability is deterministic and evidence-gated:

- no viable route: `UNAVAILABLE`;
- unresolved membership or insufficient candidate evidence: `PARTIAL`;
- complete viable route/candidate evidence: `AVAILABLE`.

No confidence value is created.

## D. Files changed

- `src/amazon_product_intelligence/market_report/v0_2/builder.py`
- `src/amazon_product_intelligence/market_report/v0_2/integrations/__init__.py`
- `src/amazon_product_intelligence/market_report/v0_2/integrations/route_discovery_v2.py`
- `tests/test_route_discovery_v2_market_report_integration.py`
- `docs/engineering/SP_042A_ROUTE_DISCOVERY_V2_MARKET_REPORT_INTEGRATION.md`
- `docs/validation/SP_042A_COMPLETION_REPORT.md`

No Route Discovery V2 core, provider, Sorftime, XiYou, replay, renderer, or
delivery file changed.

## E. Integration contract

- Input: exact `RouteDiscoveryV2Result` and, for attachment, exact validated
  `MarketReportSnapshotV0_2`.
- Output: a strict content-addressed projection bundle or a recomposed strict
  V0.2 snapshot containing one external attachment.
- Compatibility: exact upstream dataset target ID and fingerprint, CHILD_ASIN
  report grain, equal listing count, and equal known marketplace.
- Ordering: source semantic identity is authoritative; projected route and
  denominator IDs and merged report registries use explicit stable keys.
- Duplicates: same identity/same content is idempotent; conflicts and a second
  different Route V2 attachment fail closed.
- Provenance: exact source result ID/version/fingerprint plus deterministic
  report provenance and derived-evidence records.
- Metrics/denominators: retained in the exact source result and never
  recalculated, renamed, or rebound to a different cohort/window/grain.

## F. Tests

Runtime: local worktree `.venv`, Python 3.14, pytest 9.1.1.

- Focused integration test:
  `9 passed in 9.18s`.
- Focused integration rerun after final boundary hardening:
  `9 passed in 4.91s`.
- Final focused rerun including projection contract round-trip:
  `9 passed in 7.38s`.
- Final focused rerun after exact source-reference cardinality hardening:
  `9 passed in 6.57s`.
- Affected Route V2, Product Route Opportunity, and Market Report V0.2 group:
  initial `203 passed in 56.86s`; final post-hardening rerun
  `203 passed in 60.05s`.
- Full local suite before the final source-reference cardinality hardening:
  `1503 passed, 13 skipped, 550 subtests passed`; one known
  Windows OOXML fingerprint assertion failed after all tests ran.  It expected
  `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`
  and produced
  `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.
  This is the exact accepted baseline mismatch documented by SP-041R2; no
  renderer/delivery file changed in SP-042A.  The final focused and affected
  reruns above cover every modified code path after that hardening.
- `compileall`: PASS for `src` and `tests`.
- `git diff --check`: PASS.

The focused tests prove successful projection, empty-route behavior,
insufficient candidate evidence, repeated deterministic output, input-order
invariance, stable route ordering, unique route identity, provenance
preservation, malformed/duplicate input rejection, incompatible cohort
rejection, compatible snapshot attachment, idempotency, strict JSON round-trip,
and unchanged no-route Market Report behavior.

## G. Known limitations

- SP-041R2's baseline completion report still records the bounded human
  intra-route consistency review as unavailable.  SP-042A does not change that
  acceptance state.
- An exact governed dataset ID/fingerprint must already own the report analysis
  cohort.  Count equality is not accepted as a join.
- Empty/no-viable-route output remains unavailable evidence, not an empty-market
  or no-opportunity conclusion.
- Route metrics remain source-owned until a separately approved, jointly
  versioned report section defines compatible metric projection semantics.

## H. Explicit non-goals and follow-up dependencies

- No Route V2 redesign or core fix.
- No provider/live acquisition work.
- No Market Report top-level schema or renderer change.
- No legacy Route V1 fallback.
- No representative ASIN, Direct Competitor, procurement, SP-042B, or SP-042C.
- Any future core metric projection requires a separate approved contract for
  cohort, window, grain, denominator, and evidence semantics.

## I. Final Git state

- Commit message: `feat: integrate route discovery v2 into market report`.
- The final commit SHA and post-commit `git status` are reported in the task
  handoff because a commit cannot contain its own SHA.
