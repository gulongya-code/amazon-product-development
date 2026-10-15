# TASK-SP-042C Route Discovery V2 independent acceptance

Report date: 2026-08-29

Release recommendation: **PASS WITH CONDITIONS**

This is an independent automated contract, replay-boundary, configuration, and
compatibility acceptance of SP-041R2. It does not claim a fresh run over private
calibration workbooks and does not replace the human route-coherence gate recorded
in the SP-041R2 completion report.

## A. Baseline

- Required and actual starting commit:
  `da651cf397a0b4c6d1a1b991359c6d68d3b3ca25`.
- Required and actual branch:
  `codex/task-sp-042c-route-discovery-acceptance`.
- Starting worktree and index: clean.
- No fetch, pull, push, rebase, merge, other-worktree access, provider access, or
  GitHub access was performed.
- Reviewed artifacts: SP-041R2 completion report and engineering contract, Route
  Discovery V2 package, all five configs and accepted profiles, the private replay
  runner, focused tests, evidence/provenance contracts, and the Product Route
  Opportunity V1 compatibility changes.

## B. Scope and gap analysis

Existing SP-041R2 tests already covered hierarchical sparse grouping, multi-value
consensus, same-process reversed-order/timestamp determinism, primary-cohort
gating, route-critical conflicts, candidate diversity, metric invariants, strict
unknown-key rejection, aggregate privacy scanning, and blank human-review
fail-closed behavior.

The independent gaps were:

1. cross-process/hash-seed determinism;
2. frozen identity and exact authority of every current category config;
3. pairwise category isolation;
4. empty, single-product, duplicate-product, missing-identity, missing-optional,
   malformed-observation, and unknown-route boundaries;
5. end-to-end resolution of route claims to exact S2 fact/evidence IDs;
6. direct rejection of unsupported claims by the public feature contract; and
7. explicit replay data-mode disclosure plus dynamic no-overwrite and no-synthetic-
   fallback behavior.

Dedicated acceptance tests were added only for those gaps. Existing conflict,
sparse, repeated-input, reverse-order, and Product Route Opportunity tests were
reused as acceptance evidence rather than duplicated.

## C. Acceptance matrix

| Area | Independent evidence | Result |
| --- | --- | --- |
| Repeated identical input | Existing full-result equality plus the new two-process replay of identical synthetic governed input | PASS |
| Process/order independence | Different `PYTHONHASHSEED` processes produce byte-identical result JSON; existing reversed-record/timestamp tests remain green | PASS |
| Stable route identity | Full result, route IDs, membership IDs, and fingerprints remain canonical across the above runs | PASS |
| Duplicate suppression | Duplicate listing identities fail in accepted S2 before routing; duplicate route IDs fail in the V2 result contract | PASS |
| Category isolation | Every current config rejects every other current config's canonical category | PASS |
| Evidence attribution | Every feature fact/evidence ID resolves to its exact S2 listing; defining values equal defining-fact values; membership and route evidence unions are exact | PASS |
| Unsupported claims | A failing regression proved the public feature contract accepted a defining value without facts/evidence; the minimally hardened contract now rejects it | PASS after fix |
| Missing evidence | Defining values now require defining facts and evidence; defining fact IDs must be a subset of observed fact IDs | PASS after fix |
| Configurations | All and only the five current configs load, match frozen fingerprints, retain exact dimensions, have unique identities/scopes, and pass profile authority validation | PASS |
| Empty input | Returns zero listings/routes/candidates with `INSUFFICIENT_EVIDENCE` | PASS |
| One product | Cannot satisfy route support and remains unclassified | PASS |
| Duplicate product | Rejected at the accepted S2 listing-grain boundary | PASS |
| Sparse observations | Existing broad-parent, unique-attachment, ambiguity, and unclassified tests remain green | PASS |
| Malformed observations | Produce no fabricated route and remain explicitly unclassified | PASS |
| Conflicting observations | Existing route-critical conflict test remains `REVIEW_REQUIRED` with no primary route | PASS |
| Unknown route/category | Unknown candidate route references and cross-category authority are rejected | PASS |
| Missing optional signals | Route identity remains valid while sales/price metrics remain unavailable rather than imputed | PASS |
| Missing required identity | Missing Product Identity is not admitted to an assigned route | PASS |
| Replay determinism | Runner performs reversed-order/timestamp semantic and route comparisons; engine equality is also proven across independent processes | PASS for code path; fresh private corpus not run |
| Replay non-destructive | Existing output is never overwritten; manifest input bytes remain unchanged on importer failure | PASS |
| Replay data clarity | Aggregate report now states offline/private caller-declared mode and explicitly disables live-provider, fixture, and synthetic-fallback modes | PASS |
| Replay fail-closed | Missing private input propagates immediately; no profile, fixture, or synthetic success path is invoked | PASS |
| V1 regression | All affected Product Route Opportunity V1 tests pass | PASS |

## D. Configuration evidence

| Category config | Frozen fingerprint | Route dimensions | Result |
| --- | --- | --- | --- |
| Air fryers | `65bf8f75e8130d0f4b46fa19d43f391647a0472f587ed9d13f4b2392d27c69bc` | `structural_form`, `operation_mechanism` | PASS |
| Dog water bottles | `7aea673fff8e1649cd2ac99d0b509c9d1aa61769dd196ad7d2b35c500c5ba620` | `operation_mechanism` | PASS |
| Food storage containers | `4a2dd049d3c0bd90c8cb223b08da82299a6ad382ef75929a4ac8a7bb5da1fea2` | `structural_form` | PASS |
| Shower caddies | `cb863460d239978e461d4902906a5a7171e5069a820cb0305b09ad818de3edc3` | `installation_architecture`, `attachment_mechanism` | PASS |
| Vacuum replacement filters | `80a9b88f5822a3b22c1dcbac9de2abc4ce4be005a2b7e6b1f0714c9f7b82c2f1` | `compatibility` | PASS |

No secondary dimension is promoted by a shipped config. Adoption dimensions are
exactly the union of route and descriptor dimensions for each config, and current
category/alias scopes do not overlap.

## E. Defects and hardening

### RDV2-ACCEPT-001 — unsupported defining claim accepted without evidence

- Severity: **HIGH** (fail-closed evidence/provenance contract).
- Initial regression result: `1 failed`; `RouteDiscoveryV2Error` was not raised.
- Cause: `SemanticRouteFeature` checked only that defining values were included in
  observed values. It did not require any fact/evidence IDs or validate that
  defining fact IDs referenced observed feature facts.
- Resolution: minimal immutable-contract validation in
  `route_discovery_v2/models.py`; no grouping, candidate, metric, or semantic
  decision logic changed.
- Final regression result: PASS.

### RDV2-ACCEPT-002 — replay data mode was implicit

- Severity: **MEDIUM** (acceptance/replay transparency).
- Cause: the runner behavior was offline and private by construction, but the
  aggregate result did not explicitly distinguish private replay from live,
  fixture, or synthetic modes.
- Resolution: aggregate results now include an explicit `data_disclosure` object
  declaring caller-supplied external private calibration, no live provider access,
  no fixture mode, and no synthetic fallback.
- Production route semantics were not modified.

### Known unrelated baseline exception

The full suite reproduces the accepted Windows OOXML package fingerprint mismatch:
expected `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`,
actual `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.
No workbook or delivery source was changed by SP-042C.

## F. Exact validation results

- Pre-change focused baseline:
  `49 passed in 10.09s` across existing Route V2, private replay, and affected
  Product Route Opportunity V1 tests.
- Defect proof before fix:
  `1 failed in 2.85s` for the unsupported-defining-claim regression.
- New independent acceptance file after hardening, final rerun:
  `14 passed in 4.30s`.
- Existing Route Discovery V2 and private replay tests, final rerun:
  `37 passed in 6.02s`.
- New plus existing Route V2 and replay tests:
  `51 passed in 9.72s`.
- Affected Product Route Opportunity V1 tests, final rerun:
  `12 passed in 3.45s`.
- Environment-qualification rerun for two subprocess tests:
  `2 passed in 64.41s`.
- Broadest practical full suite in the isolated runtime:
  `1508 passed, 13 skipped, 550 subtests passed, 1 failed in 399.44s`.
  The sole failure is the exact known OOXML exception above.
- `compileall` over `src`, `scripts`, and the new acceptance file: PASS.
- `git diff --check`: PASS before this report; repeated at finalization.

## G. Files changed

- `tests/test_route_discovery_v2_acceptance.py`: dedicated independent acceptance
  and replay-hardening tests.
- `src/amazon_product_intelligence/route_discovery_v2/models.py`: minimal
  evidence fail-closed contract fix.
- `scripts/run_route_discovery_v2_private_replay.py`: explicit replay data-mode
  disclosure.
- `docs/validation/SP_042C_ROUTE_DISCOVERY_V2_INDEPENDENT_ACCEPTANCE.md`: this
  report.

Production source was modified: **YES**, limited to the one proven evidence
contract defect. No Market Report integration, provider/Sorftime production
adapter, intelligence-semantic redesign, SP-042A, or SP-042B work was performed.

## H. Determinism and provenance verdict

Automated determinism and provenance acceptance: **PASS**.

- canonical result material is stable across input reversal, timestamp noise, and
  separate processes with different hash seeds;
- route definitions cannot be emitted from missing or corroborating-only evidence;
- every emitted defining claim is attributable to accepted S2 facts/evidence; and
- private replay has no runner-provided live-provider, fixture, synthetic-fallback,
  or overwrite success path.

## I. Conditions and release recommendation

Recommendation: **PASS WITH CONDITIONS**.

The implementation, configs, replay boundary, and affected V1 compatibility
surface pass automated acceptance after the minimal defect fix. Unconditional
release acceptance is not granted because:

1. private calibration assets were not available to this lane, so the five-category
   private replay was not freshly executed here; and
2. the SP-041R2 completion report's external human intra-route consistency and
   route-safety review remains incomplete.

Those conditions require the authorized external private replay and human review;
they must not be replaced by fixtures, synthetic data, or LLM-inferred labels.

## J. Finalization

Final commit SHA and final Git status are reported in the task handoff after the
local commit is created.
