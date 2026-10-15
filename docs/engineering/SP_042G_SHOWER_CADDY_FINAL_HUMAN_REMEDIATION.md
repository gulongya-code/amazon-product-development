# SP-042G Shower Caddy Final Human-Review Remediation

## A. Baseline

- Required baseline and starting HEAD: `977d8044fd06116c25a63ff42d669a5a5f6c1664`
- Baseline parent: `0c0d075e0ece80cfdb03dd1c63773b8bd3a53f13`
- Dedicated branch: `codex/task-sp-042g-shower-caddy-final-human-remediation`
- Starting `git status --short`: empty
- Starting `git diff --cached --stat`: empty
- Python: `3.14.4`
- pytest: `9.1.1`
- Preserved SP-041R2 stash: `stash@{0}`, SHA `4e42cf86c7018790af36cb092b0938e02466ec5e`; not applied, popped, or deleted.
- No fetch, pull, merge, rebase, push, main update, live provider use, or other-worktree access was performed.

## B. Human FAIL evidence consumed

The final authorized Markdown was read from the private, HEAD-bound SP-042F package. It records 15/15 routes reviewed, 13 PASS, 2 FAIL, and 0 blank route verdicts. The two authoritative failures are:

1. Former Route 4 mixed portable basket/tote products and an evidence-insufficient caddy into `installation_architecture=freestanding`.
2. Former Route 12 placed a corner shelf supported only by ambiguous `Insert Mount` evidence into `corner_shelf + recessed_or_builtin`, alongside explicitly recessed/grout-in products.

The package binding, aggregate replay, and governed review basis were also inspected read-only. The named `SP_042F_SHOWER_CADDY_HUMAN_REVIEW_FINAL.xlsx` was not present anywhere under the current user profile after an exact-name search; no workbook was fabricated or inferred. The task prompt and final Markdown contain the complete authoritative 13/2 decision and both FAIL findings used here. No private record was copied into repository tests.

## C. Root-cause audit

| Capability | Decision | Finding / use |
|---|---|---|
| Canonical installation normalization | REFACTOR | SP-042F taxonomy is retained, but bare structured `Freestanding` and ambiguous `Insert Mount` were too authoritative. |
| Product-form classification | EXTEND | Existing `STRUCTURAL_FORM/product_form` is reused; portable title coverage is broadened. |
| Mobility / portable classification | EXTEND | Structured Special Feature `Portable` becomes corroborating product-form evidence while remaining functional-feature evidence. |
| Installation evidence authority | REFACTOR | Affirmative floor-standing evidence is required for freestanding; explicit recessed/built-in/grout-in evidence is required for recessed. |
| Semantic conflict handling | REUSE | Existing relationships and route-critical conflicts remain authoritative and auditable. |
| Evidence/provenance | EXTEND | New generic `EVIDENCE_ONLY` fact-rule mode preserves ambiguous observation lineage without publishing a canonical fact. |
| Route eligibility | REFACTOR | Sparse attachment now requires presence parity for structural-form and all route-critical dimensions. |
| Deterministic route identity | REUSE | Canonical serialization, IDs, sorting, clustering, candidate selection, and normal/reversed replay comparison are unchanged. |
| Human-review package | EXTEND | Each sampled row now exposes governed route-authoring rule/source/relationship metadata without copying raw structured values. |
| Focused regression coverage | NEW | Sanitized synthetic SP-042G cases cover both human failures and every required non-regression. |

No ASIN, category literal, or provider-specific branch was added to production engines.

## D. Changes implemented

### Portable versus freestanding

- Bare structured `free standing` / `freestanding` is retained as `EVIDENCE_ONLY_UNRESOLVED`, not published as installation architecture.
- Explicit floor-standing forms such as floor standing, floor mount, standing shower caddy, and shower-caddy stand continue to authorize `freestanding`.
- Portable basket/tote/storage-caddy title patterns authorize `product_form=portable` and `installation_architecture=no_installation`.
- Structured `Special Feature=Portable` supplies corroborating portable-form evidence. It cannot manufacture route authority on its own.
- Absence of installation evidence never implies freestanding.

### Recessed/built-in consistency

- `recessed`, `built-in`, `flush mount`, shower niche, and `grout-in` remain/are authorized as `recessed_or_builtin`.
- Ambiguous `Insert Mount` is now evidence-only and does not publish a recessed installation fact.
- A sparse signature missing a route-critical installation dimension cannot attach to a route that asserts one. It may remain unclassified or join a valid product-form-only route.

### Evidence and review usability

- `EVIDENCE_ONLY` retains source class/key, content fingerprint, upstream record fingerprint, and profile rule ID while keeping the semantic relationship unavailable.
- New review rows include `governed_route_evidence`: canonical value, profile rule, source class/key, and relationship state for every route-defining fact. Human decisions and notes remain the only editable fields.

Shower profile version is `1.1.2`; fingerprint is `47824411ba9a530d99ec1d7716ad830282614546418bed004147b90cbe589e63`.

## E. Files changed

- `config/category_semantic_profiles/shower_caddies.v1_1.json`
- `src/amazon_product_intelligence/semantic_engine_v2/profile.py`
- `src/amazon_product_intelligence/semantic_engine_v2/engine.py`
- `src/amazon_product_intelligence/route_discovery_v2/engine.py`
- `scripts/run_route_discovery_v2_private_replay.py`
- `tests/test_sp_042g_shower_caddy_final_remediation.py`
- `tests/test_route_discovery_v2.py`
- this report

## F. Focused tests

- SP-042G focused: **18 passed, 0 failed**.
- SP-042F focused: **21 passed, 0 failed**.
- Semantic Engine V2: **41 passed, 0 failed**.
- Route Discovery V2 / acceptance / replay / Market Report projection: **61 passed, 0 failed**.
- Evidence, provenance, conflict, and source contract: **56 passed, 37 subtests passed, 0 failed**.
- Category product map and cross-category authority isolation: **9 passed, 0 failed**.
- Private replay/review contract: **12 passed, 0 failed**.

The tests cover portable baskets with handles, true floor-standing organizers, no-install separation, portable-form evidence authority, explicit recessed/built-in/grout-in, tiled-wall/Insert-Mount fail-closed behavior, auditable evidence-only observations, all SP-042F canonical values, accessory isolation, and repeated/reversed determinism.

## G. Regression results

- Final full offline suite: **1557 passed, 13 skipped, 550 subtests passed, 1 failed**.
- The only failure is the previously accepted and independently reproduced Windows OOXML package fingerprint difference: actual `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`, expected `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`. The xlsx delivery implementation and test remain unchanged from the required baseline. There are **0 new failures**.
- `python -m compileall -q src scripts tests`: exit 0.
- `git diff --check`: exit 0.

## H. Private replay comparison

The authorized five-category replay remained OFFLINE_PRIVATE_REPLAY: no network, provider, credential, LLM, or synthetic-fallback activity. Original private inputs were unchanged.

| Category | Listings | Primary cohort | Assigned | Unclassified | Review | Routes | Candidates | Provenance / isolation violations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Shower Caddy | 998 | 676 | 610 | 219 | 169 | 15 | 5 | 0 / 0 |
| Dog Water Bottle | 400 | 280 | 0 | 400 | 0 | 0 | 0 | 0 / 0 |
| Vacuum Filter | 300 | 0 | 0 | 300 | 0 | 0 | 0 | 0 / 0 |
| Food Storage Set | 150 | 99 | 0 | 150 | 0 | 0 | 0 | 0 / 0 |
| Air Fryer Mixed | 300 | 162 | 64 | 233 | 3 | 11 | 5 | 0 / 0 |

Shower Caddy SP-042F -> SP-042G: cohort `650 -> 676`, assigned `600 -> 610`, unclassified `203 -> 219`, route-review `195 -> 169`, routes `15 -> 15`, candidates `5 -> 5`, candidate members `371 -> 361`. The route count is observed, not hardcoded. Non-primary assigned remains 0.

The cohort increase is an audited semantic consequence: removing false route-critical installation facts moved 26 records out of conflict-driven cohort review. Route eligibility was simultaneously tightened, so unresolved installation evidence cannot create or bridge into a structural route.

Normal/reversed runs match for semantic and route results in all five categories. Shower semantic fingerprint: `31f7fab91baf82af0a878761ee062cab3bde022f140d12a5cfc41c047ca48c2f`; route fingerprint: `919b184bff471fcc8bbe325d6f98103c8576fdefd974d8da606ca695bfd0a03f`. Privacy leak count is 0. Automated/private remediation gate: **PASS**.

## I. Former FAIL Route behavior

- Former Route 4: the two explicit portable products now resolve to the portable product-form route; the evidence-insufficient item retains bare Freestanding as evidence-only and is UNCLASSIFIED. The current freestanding route samples have affirmative standing/stand evidence.
- Former Route 12: the Insert-Mount/tiled-wall item now belongs only to the `corner_shelf` product-form route and no longer asserts recessed installation. The two explicitly recessed/grout-in products remain in `corner_shelf + recessed_or_builtin`.

These outcomes are produced by governed phrase authority and route-critical presence rules, not listing-specific exclusions.

## J. New review package

The pre-commit governed basis has sample ID `f849858742bb9bbb61c9d42ca397ca53513dd6d5000a49d3e63d0fcc291486a4`: 15 emitted routes, 3 deterministic samples per route, 45 rows total, and 0 non-null decisions / 0 non-empty notes. Every row has governed route evidence. After the single commit, the final replay, basis, binding manifest, and concise reviewer guide are regenerated in a private directory named for the exact HEAD. The final handoff records its exact paths and hashes.

SP-042F human decisions are not copied or treated as authority for the new build.

## K. Remaining known issues

- 167 listings retain route-critical installation conflicts; route-level review-required count is 169 because two additional product-form conflicts are preserved.
- Cohort states include 91 UNKNOWN and 64 OFF_TARGET_EXCLUDED records; unseen language continues to fail closed.
- The final authorized xlsx evidence artifact named by the task was absent; the final Markdown decision was available and unambiguous.
- The unrelated Windows OOXML fingerprint difference remains.
- A fresh authorized human review is required. No release PASS is declared.

## L. Final git status

Before the single commit, only the intended files in section E are modified or new. The final handoff records clean post-commit worktree/index, exact HEAD/parent, one-commit count, and preserved stash verification. No private output is tracked.

## M. Commit SHA

This report is part of the single final commit, so it cannot embed its own cryptographic SHA without creating another commit. The exact SHA is recorded by `git rev-parse HEAD` in the final handoff and the external review binding manifest.

**AUTOMATED/PRIVATE REMEDIATION GATE: PASS**

**FINAL RELEASE: BLOCKED — AUTHORIZED_HUMAN_ROUTE_REVIEW_PENDING**
