# TASK-SP-041R2 completion report

Issue: `#57 TASK-SP-041R2 — Route Discovery V2`

Report date: 2026-08-29

This report contains sanitized aggregate evidence only. It contains no private
workbook path, source row, listing reference, title, brand, seller, price, or
operator decision.

## A. Baseline/runtime/workspace

- Repository: `gulongya-code/amazon-product-development`.
- Branch: `codex/task-sp-041r2-route-discovery-v2`.
- Required and actual starting HEAD: `ac8d66afed2fc11e20986bae46e09f6c78708ecf`.
- Upstream at start: `origin/codex/task-sp-041r2-route-discovery-v2` at the same
  commit.
- Start gate: origin fetched; exact branch/HEAD verified; workspace and staging
  clean before the reuse audit or implementation edit.
- Runtime: Python `3.14.4`; pytest `9.1.1`.
- Exact-baseline focused gate: `105 passed`.
- Exact-baseline affected gate: `421 passed, 5 skipped, 115 subtests passed`.
- Exact-baseline full suite: `1457 passed, 13 skipped, 550 subtests passed`, with
  the single accepted Windows OOXML fingerprint mismatch reproduced exactly:
  expected `89ffe...`, actual `84e5...`.

The final workspace is intentionally uncommitted because section U is an Issue
#57 hard blocker. No private acceptance artifact has been staged.

## B. S2 authority confirmation

- The accepted Semantic Engine V2 result remains the sole Product Identity,
  Product Role, evidence-relationship, conflict, and APD market-cohort authority.
- Route V2 validates dataset ID/fingerprint, listing-grain fingerprints, profile
  ID/version/fingerprint, and route-config authority before projection.
- Accepted S2 authority match: `5 / 5` calibration categories.
- Accepted calibrated-category authority match: `5 / 5`.
- Route V2 performs no raw-text identity/role/cohort reclassification.
- Non-primary assignments into a primary route: `0` across the five-category
  replay.

## C. Route V2 targeted reuse audit

The required audit was the first implementation artifact. Its disposition is:

- `REUSE_AS_IS`: accepted S2 contracts and profiles, canonical ID primitives,
  SP-041D route metrics, product grain, provenance, and candidate market-evidence
  reason codes;
- `EXTEND`: expose the accepted governed market-field projection and candidate
  metric reasons so both V1 and V2 use one implementation;
- `REPLACE_IN_V2`: V1 exact-known structural signatures and facet-driven
  candidate distance only;
- new third-party dependencies: `0`;
- copied/adapted public algorithms: `0`;
- new license obligations: `0`;
- public GitHub/license audit disposition: `RETAIN_ACCEPTED_AUDITS`.

Authority: `docs/engineering/SP_041R2_TARGETED_IMPLEMENTATION_REUSE_AUDIT.md`.

## D. Files added/modified

Modified accepted reuse boundaries:

- `src/amazon_product_intelligence/product_route_opportunity/engine.py`;
- `src/amazon_product_intelligence/product_route_opportunity/product_map.py`.

Added allowed R2 material:

- six files under `src/amazon_product_intelligence/route_discovery_v2/`;
- five strict category configs under `config/route_discovery_v2/`;
- `scripts/run_route_discovery_v2_private_replay.py`;
- `tests/test_route_discovery_v2.py`;
- `tests/test_route_discovery_v2_private_replay.py`;
- two engineering documents and this validation report.

No S2 contract/profile, SP-041D metric formula, private calibration asset, Shared
Semantic Core package, KWS integration, representative-ASIN, Direct Competitor,
procurement-ceiling, or SP-041E file was added or changed.

## E. Semantic route-feature projection

`SP-041B governed dataset + accepted S2 result` is joined at listing grain. The
projection exposes only dimensions authorized by the accepted profile/config and
preserves role, dimension, complete normalized value sets, complete defining
value sets, profile/source-policy lineage, fact/evidence/relationship references,
conflicts, and limitations.

Primary sources are preferred, governed fallback is used only when primary facts
are absent, and corroborating-only observations remain diagnostic. Missing and
corroborating-only facts cannot manufacture a route value. `FACET_ONLY` cannot
define a route, while a profile `SECONDARY` dimension requires explicit config
promotion. Five production configs have no secondary promotion.

## F. Route discovery method/config/version

- Method: `PROFILE_AUTHORIZED_HIERARCHICAL_SPARSE_SEMANTIC_CONSENSUS`.
- Engine: `route-discovery-v2.0`.
- Result contract: `route-discovery-v2-result-v1.0`.
- Membership contract: `route-membership-v2.0`.

The generic engine retains all defining values and uses configuration-ordered
hierarchical grouping. A viable base requires the configured support floor.
Later dimensions refine only when at least two different exact single-value
buckets independently meet that floor. Sparse/multi-value remainders either form
a supported broad parent or attach only to one uniquely intersecting child.

After viable routes exist, an unresolved signature is compared using all shared
known dimensions: at least one dimension must be shared and every shared
value-set must intersect. Zero matches is `UNCLASSIFIED`, one is `ASSIGNED`, and
multiple matches is `REVIEW_REQUIRED`. Missingness, corroborating-only evidence,
market metrics, row order, lexical order, and canonical sort order cannot create
equality or break ambiguity. A compatible attachment never mutates the existing
route definition or route ID.

## G. Membership/result contract

- Exactly one membership state per accepted listing.
- At most one primary route per listing.
- `ASSIGNED` references exactly one existing route; other states reference none.
- Listing count equals assigned + unclassified + review-required.
- Route members and membership IDs must match the assigned-membership mapping.
- IDs and fingerprints are validated against their exact canonical logical
  content.
- Memberships retain the listing's own defining signature, evidence, reason
  codes, profile/config lineage, and limitations, including unique-attachment or
  multiple-compatible-route ambiguity.
- Product grain remains `LISTING_ASIN_NO_PARENT_COLLAPSE`.

## H. Determinism/canonical route identity

- Canonical JSON/value-set ordering and content-derived IDs are used throughout.
- Reversed input plus changed runtime/import timestamp replay: semantic match
  `5 / 5`; Route V2 result/route fingerprint match `5 / 5`.
- Repeated same-input mismatch count: `0`.
- Timestamp/runtime metadata is excluded from semantic identity.
- Route ID uses only method/version, profile/config fingerprints, and canonical
  profile-authorized defining features; compatible attachments do not mutate it.

Deterministic Route V2 result fingerprints:

| Calibration category | Result fingerprint |
| --- | --- |
| Shower Caddy | `24094764d99b5438bfbb1a4cd8bd33ce674e6961595fd605bd634811ff2736f1` |
| Dog Water Bottle | `85c594cab225675292dcc7c8f7f477191786fa4c74e14927a10c82283d3c23ba` |
| Vacuum Filter | `4590f78aa99b9f9b32fe0c20dbfd4c18bd44f9ffd08b929a4c949fb38e52970b` |
| Food Storage Container Sets | `597333ac2f9a31ad77f4a51d42675ab535d74320357a914ab7919ec4480d78af` |
| Air Fryer mixed market | `736862843bb5a71630dcf9958f01de6eabaed50ccb0b38dfe1eebacde8b02839` |

## I. Retained SP-041D metric parity

- `product_route_opportunity/metrics.py`: unchanged from the required baseline.
- Governed market fields reuse one V1/V2 implementation.
- Candidate market-evidence reason codes reuse the accepted SP-041D helper.
- Frozen metric-contract match: `5 / 5` categories.
- Listing-share and available-sales-share denominator invariants are enforced.
- Growth reconstruction, availability/limitation semantics, review and price
  distributions, new-product threshold, and `NEAREST_RANK` remain unchanged.

## J. Candidate selection/diversity

Qualification uses frozen SP-041D market evidence only after route semantics are
formed. Selection performs a deterministic pairwise-clique search from five down
to three. Every selected pair must have contradictory known values on at least
one shared route-eligible dimension and meet the configured semantic-distance
floor. Broad-vs-specific missingness and facet-only variation cannot manufacture
diversity. Fewer than three qualifying routes returns `INSUFFICIENT_EVIDENCE`.

Shower result: `5` candidates, `351` members, `10` candidate pairs, pairwise
route-eligible-difference violations `0`, and facet-only distinct pairs `0`.
Air Fryer result: `5` candidates, `43` members, with the same two violation
counts at `0`. No representative listing or ASIN is selected.

## K. Same-998 Shower V1 vs V2 comparison

| Measure | Frozen V1 | Route V2 |
| --- | ---: | ---: |
| Accepted listings | 998 | 998 |
| Assigned | 297 (29.7595%) | 725 (72.6453%) |
| Unclassified | 562 (56.3126%) | 268 (26.8537%) |
| Review required | 139 (13.9279%) | 5 (0.5010%) |
| Routes | 80 | 57 |
| Size-2 routes | 45 / 80 (56.2500%) | 0 / 57 (0.0000%) |
| Candidate members | 41 | 351 |
| Candidate coverage of assigned | 13.8047% | 48.4138% |
| Candidate coverage of accepted | 4.1082% | 35.1703% |
| Repeated fingerprint mismatches | 0 | 0 |

The V1 replay reproduced all frozen counts on the exact same corpus before the
V2 comparison.

## L. Frozen quantitative gate results

| Frozen Issue #57 gate | Required | Actual | Result |
| --- | ---: | ---: | --- |
| Assigned route coverage | >= 59.5190% | 72.6453% | PASS |
| Unclassified rate | <= 28.1563% | 26.8537% | PASS |
| Review-required rate | <= 6.9640% | 0.5010% | PASS |
| Size-2 route share | <= 28.1250% | 0.0000% | PASS |
| Candidate coverage of assigned | >= 27.6094% | 48.4138% | PASS |
| Candidate coverage of accepted | >= 8.2164% | 35.1703% | PASS |
| Bounded human intra-route consistency | >= 95% | unavailable | **FAIL / BLOCKED** |
| Facet-only distinct candidate pairs | 0 | 0 | PASS |
| Generic-engine category patches | 0 | 0 | PASS |
| Repeated route fingerprint match | 100% | 100% | PASS |
| Private data leakage | 0 | 0 | PASS |

All six numeric corpus/fragmentation/coverage gates pass without changing their
frozen thresholds. The human gate is not inferred from the blank sample.

## M. Five-category portability aggregates

Rates below use accepted-listing count as denominator, matching the Shower
acceptance convention. Candidate coverage is shown as assigned / accepted.

| Category | Accepted / eligible | Assigned | Unclassified | Review | Routes / size-2 | Candidates / members | Candidate coverage | Replay time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Shower Caddy | 998 / 868 | 725 (72.6453%) | 268 (26.8537%) | 5 (0.5010%) | 57 / 0 | 5 / 351 | 48.4138% / 35.1703% | 40.385 s |
| Dog Water Bottle | 400 / 280 | 0 (0.0000%) | 400 (100.0000%) | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 8.213 s |
| Vacuum Filter | 300 / 0 | 0 (0.0000%) | 300 (100.0000%) | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 9.769 s |
| Food Storage Container Sets | 150 / 99 | 0 (0.0000%) | 150 (100.0000%) | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 3.007 s |
| Air Fryer mixed market | 300 / 162 | 64 (21.3333%) | 233 (77.6667%) | 3 (1.0000%) | 11 / 0 | 5 / 43 | 67.1875% / 14.3333% | 9.869 s |

Sanitized route-size histograms (`member_count x route_count`):

- Shower: `3x16, 4x9, 5x5, 6x2, 7x4, 8x5, 9x2, 11x1, 12x1, 13x2, 15x2, 16x1, 18x1, 23x1, 26x1, 46x1, 58x1, 87x1, 165x1`.
- Air Fryer: `3x3, 4x4, 5x1, 7x1, 10x1, 17x1`.
- The other three replays emitted no route and therefore no route-size bucket.

Sanitized route-defining distributions:

- Shower: `INSTALLATION_ARCHITECTURE` / `installation_architecture` appears in
  50 routes covering 675 assigned members; `ATTACHMENT_MECHANISM` /
  `attachment_mechanism` appears in 34 routes covering 262 members. A route may
  contain both dimensions, so these counts overlap.
- Air Fryer: `OPERATION_MECHANISM` / `operation_mechanism` appears in 11 routes
  covering 64 assigned members.
- Dog and Food each had only one eligible listing with a defining fact on the
  configured route dimension, below the route support floor. Vacuum had no S2
  PRIMARY_ONLY-eligible listing. R2 therefore returned no route rather than
  fabricating portability coverage.

Total private replay: `2,148` listings and `73.189 s` wall clock. All five used
the same generic engine and passed authority, metric-parity, determinism,
non-primary leakage, category-patch, network/provider/LLM, and aggregate-privacy
checks. Issue #57 freezes category-specific numeric thresholds only for Shower;
no new universal pass percentage was invented for the other categories.

## N. Operator intra-route consistency

A new external, private, all-blank deterministic sample was generated:

- sampled routes: `57 / 57`;
- sampled rows: `171`, at most three per route and below the 209-row bound;
- candidate routes represented: `5 / 5`;
- strata represented: candidate, largest, minimum-size boundary, sparse,
  former-V1-fragmentation-risk proxy, and general routes;
- nonblank operator decisions: `0`.

No completed route-specific operator review was supplied. Consequently:

- reviewed rows: `0`;
- intra-route consistency: unavailable, not zero and not inferred;
- the required `>= 95%` human consistency gate: not satisfied;
- route safety checks and candidate minimum business sense: not satisfied.

## O. Facet-only split/leakage safety

- Route identity dimensions outside profile/config authority: `0`.
- Facet-only candidate distinctions: `0`.
- Candidate pairs without a route-eligible semantic difference: `0`.
- Non-primary assignments to primary routes: `0`.
- Missing facts used as equality: `0` by contract and focused tests.
- Corroborating-only facts used as route identity: `0` by projection/engine
  contract and focused tests.
- Completed human accessory/off-target and facet-only route-coherence review:
  unavailable; this remains part of section U.

## P. Network/provider/credential/LLM accounting

Runtime counters across the five-category replay:

- network calls: `0`;
- provider calls: `0`;
- credential accesses: `0`;
- authoritative LLM decisions: `0`.

Static R2 source checks:

- network-client imports: `0`;
- provider-client references: `0`;
- credential reads: `0`;
- LLM-client imports: `0`;
- generic category-literal control-flow patches: `0`;
- representative-ASIN, Direct Competitor, and procurement-ceiling capabilities:
  `0`.

Route discovery remains deterministic when network and LLM access are absent.

## Q. Privacy/leakage scan

- Aggregate replay privacy leak count: `0`.
- Private source assets committed/staged: `0`.
- Private XLSX/CSV/source assets in Git delta: `0`.
- Raw private listing references, rows, titles, brands, sellers, and prices in
  Git delta: `0`.
- Private path/workbook-name leakage in Git delta: `0`.
- Secret/token/key leakage in Git delta: `0`.
- The listing-grain blank review sample and aggregate replay evidence remain
  outside Git.

The repository test fixture contains one intentionally synthetic ASIN-shaped
scanner value; it is generated test data and not a private calibration value.

## R. Focused/affected/full regressions

Final post-implementation results:

- R2/S2/SP-041A/B/C/D focused group: `142 passed` across 14 test files.
- Exact reconstructed 25-file affected Product Intelligence/Opportunity/Market
  Report/pipeline group: `421 passed, 5 skipped, 115 subtests passed`; this
  exactly matches the required-HEAD baseline result.
- Full pytest with an external temporary base (required by the private-output
  safety test): pending final captured result.
- `compileall`: PASS.

The known Windows OOXML exception is acceptable only if the final full run
reproduces the exact baseline mismatch and no renderer/golden behavior changed.

## S. Git/diff/status

- `git diff --check`: pending final scan.
- Current HEAD remains the required starting commit.
- Staging: empty.
- Commit: not created.
- Push: not performed.
- Issue update: not performed.

This is required behavior while section U prevents PASS. The allowed code,
config, tests, and documentation remain intact in the uncommitted worktree.

## T. Downstream readiness

The deterministic R2 implementation and all automated private-replay gates are
ready for the bounded operator step. Downstream authorization is **not** ready:
Shared Semantic Core extraction, KWS cutover, representative ASIN selection,
Direct Competitors, procurement ceiling, SP-041E, and later work must not start
from this blocked verdict.

## U. Exact blockers/limitations

Exact blocker: the final Route V2 blank sample has not been completed by a human
operator and returned as the matching completed-review input. Therefore Issue
#57 cannot calculate or prove:

1. bounded human intra-route consistency `>= 95%`;
2. coherent Product Identity and relation-role cohort in reviewed routes;
3. route-eligible structural architecture and absence of accessory/off-target or
   facet-only route identity in reviewed rows; and
4. minimum business sense for all five selected Shower candidate routes.

No label may be fabricated, repaired, inferred from S1 review data, or supplied
by an LLM. The completed file must match the generated Route V2 review sample ID
and remain outside Git. Until then, Issue #57 forbids commit, push, Issue closure,
or downstream work.

Portability limitation, not an additional frozen failure: three non-Shower
categories had insufficient accepted S2 route-defining coverage to emit routes.
The engine correctly returned unclassified/insufficient evidence; Issue #57
defines those categories as portability/safety evidence and does not freeze a
new coverage percentage for them.

## V. Final verdict

`BLOCKED — ROUTE_V2_ACCEPTANCE_GATE_FAILED`

PASS is not granted. The only permissible PASS string remains
`PASS — ROUTE_DISCOVERY_V2` after the exact human gate in section U is completed
and every final regression/privacy/git gate remains satisfied.
