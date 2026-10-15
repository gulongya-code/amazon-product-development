# SP-042F Route Taxonomy & Eligibility Remediation

## A. Baseline

- Dedicated branch: `codex/task-sp-042f-route-taxonomy-eligibility-remediation`
- Exact implementation baseline: `0c0d075e0ece80cfdb03dd1c63773b8bd3a53f13`
- Start status after the authorized preservation operation: worktree clean; index clean; `git status --short` and `git diff --cached --stat` produced no entries.
- Python: `3.14.4`
- pytest: `9.1.1`
- Preserved SP-041R2 stash: `stash@{0}`, object `4e42cf86c7018790af36cb092b0938e02466ec5e`. Its untracked parent is `a49d9ebebcd68790084e0fa2a677e6eee90a5d45`; the stash contains the authorized 2 tracked and 17 untracked files. It was not applied, popped, or deleted.
- No fetch, pull, merge, rebase, push, main update, live provider access, or other-worktree access was performed.

## B. Human-review findings consumed

Both authoritative private SP-042E findings artifacts were read before implementation and left unchanged. They report 19 of 57 explicit route verdicts (11 PASS, 8 FAIL) plus 5 additional findings whose verdicts intentionally remain blank. They are remediation evidence only and were not reused as release authority.

The systemic findings used here were: accessory/component leakage into primary-product routing; installation synonym fragmentation; portable/freestanding conflation; unrestricted Special Feature promotion into attachment mechanism; soft-feature route fragmentation; marketing/malformed structural values; conflicting structured/title evidence; and mixed physical product identities.

No private listing rows, titles, ASINs, workbooks, or findings were copied into the repository. All new repository fixtures are synthetic.

## C. Reuse/dependency audit

| Capability | Decision | Implementation |
|---|---|---|
| Semantic taxonomy and canonical facts | EXTEND | Reuse profile fact rules and add closed Shower Caddy installation, attachment, and product-form mappings. |
| Normalization | REFACTOR | Replace structural `SOURCE_VALUE` pass-through with governed fixed canonical values; retain the existing normalization engine. |
| Evidence authority | REUSE | Continue using source policies and evidence relationships; make structured parameters and titles auditable primary evidence for installation. |
| Provenance | REUSE | Preserve Semantic Fact/Evidence IDs, upstream fingerprints, relationships, route feature lineage, and membership evidence links. |
| Conflict resolution | EXTEND | Reuse route-critical conflict handling and authorize it for installation architecture. |
| Product identity | EXTEND | Reuse priority/exclusion rules and add portable, niche, corner-shelf, and component boundaries. |
| Relation role | EXTEND | Reuse PRIMARY/ACCESSORY/REPLACEMENT roles and broaden semantic component/replacement patterns. |
| Route eligibility | REFACTOR | Restrict route dimensions to structural form, installation architecture, and attachment mechanism; keep functional features facet-only. |
| Sparse-route compatibility | EXTEND | Reuse generic sparse attachment, adding a role-driven `STRUCTURAL_FORM` boundary without category literals. |
| Deterministic IDs and ordering | REUSE | Retain canonical serialization, deterministic IDs, stable sorting, grouping, candidate selection, and fingerprints. |
| Buyer Need / Feature classification | REUSE/EXTEND | Reuse `FUNCTIONAL_FEATURE`; route Special Feature evidence there with `FACET_ONLY` relevance. |

No duplicate contract or category-specific engine branch was introduced. The Semantic Engine V2 and Route Discovery V2 schema versions remain unchanged.

## D. Root-cause analysis

The profile aliased `special feature` to `attachment` and then used unrestricted `SOURCE_VALUE` rules for both installation and attachment dimensions. Any structured or title fragment could therefore become route-defining structural truth. At the same time, the identity/relation exclusions covered only a narrow set of accessories, and the route engine could sparsely attach a signature with missing product-form evidence to a form-specific route. Together these mechanisms produced polluted dimensions, mixed product roles, and combinatorial route fragmentation.

## E. Taxonomy changes

- Canonical installation values are now `wall_mount`, `hanging_mount`, `tension_pole`, `freestanding`, `recessed_or_builtin`, and `no_installation`.
- `free standing`/`freestanding`/floor-standing surface forms converge to `freestanding`; `tension mount`/`tension pole`/`pole mount` converge to `tension_pole`.
- Portable products use `product_form=portable` and `installation_architecture=no_installation`; they are not inferred as freestanding from Special Feature text.
- Recessed niches and corner shelves have distinct product identities and structural forms.
- Attachment values are closed to governed physical mechanisms: adhesive, suction cup, screw/drilled, hook/hanging, clamp, and tension.
- `Special Feature` is preserved as `functional_feature` evidence. Arbitrary marketing, benefit, durability, and material values cannot enter structural dimensions.
- Ambiguous fragments such as `no` and marketing phrases have no matching canonical structural rule and fail closed.

Profile fingerprint: `c3b943fe1ad480ad348855a15e7f52a77d1ec79385382beffe7cf5f2fb342e09`.

## F. Route-eligibility changes

The governed route hierarchy is now `product_form`, `installation_architecture`, then `attachment_mechanism`. `functional_feature` is explicitly facet-only and is rejected by route-authority validation if promoted. Package count remains descriptive/adoption evidence, not route identity.

Sparse-cluster resolution treats every profile-authorized `STRUCTURAL_FORM` dimension as an identity boundary: evidence missing on only one side cannot bridge into or out of a form-specific route. The rule is generic and role-driven. Route config fingerprint: `2b8bbf505579e9eefe5d36be94a50c1286ebbce7496679c0d46f32a3d8fa9f15`.

## G. Accessory/product-role changes

Governed identity and relation rules now recognize replacement/spare components, fit-for-product baskets, clips, stickers/pads, suction-cup replacements, and extenders as off-target, ACCESSORY, or REPLACEMENT evidence. They remain auditable in semantic output but cannot silently enter the PRIMARY_ONLY route cohort. This is phrase-class governance, not an ASIN blacklist.

## H. Conflict/evidence handling

Structured Mounting Type and title structure are both retained as evidence. When they support incompatible installation values, the existing evidence relationship model emits `ROUTE_CRITICAL_CONFLICT`; Route V2 leaves the listing unassigned and sends it to review. No evidence is overwritten. The private replay adds aggregate-only integrity checks for evidence/fact/relationship links, feature-view lineage, membership evidence, category isolation, and privacy.

## I. Files changed

- `config/category_semantic_profiles/shower_caddies.v1_1.json`
- `config/route_discovery_v2/shower_caddies.v2.json`
- `src/amazon_product_intelligence/route_discovery_v2/engine.py`
- `scripts/run_route_discovery_v2_private_replay.py`
- `tests/test_sp_042f_route_taxonomy_eligibility.py`
- `tests/test_semantic_engine_v2.py`
- `tests/test_route_discovery_v2.py`
- `tests/test_route_discovery_v2_acceptance.py`
- `tests/test_route_discovery_v2_private_replay.py`
- `tests/test_route_discovery_v2_market_report_integration.py`
- this report

## J. Focused tests

- New SP-042F focused suite: **21 passed, 0 failed**.
- Affected Semantic Engine V2 suites: **41 passed, 0 failed**.
- Affected Route Discovery V2, acceptance, private replay, and Market Report projection suites: **61 passed, 0 failed**.
- Evidence/provenance/conflict/source-contract suites: **56 passed, 37 subtests passed, 0 failed**.
- Explicit category-product-map and cross-category authority-isolation gate: **9 passed, 0 failed**.

The focused suite covers all required synonym, product-form, accessory/replacement, Special Feature, malformed/marketing, conflict/provenance, determinism, evidence hardening, and category-isolation cases using sanitized synthetic records.

## K. Full regression results

- Full offline suite: **1539 passed, 13 skipped, 550 subtests passed, 1 failed**.
- The sole failure is the already accepted Windows OOXML package fingerprint difference in `test_xlsx_delivery_v0_1.py`: actual `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`, expected `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`. The xlsx test and implementation are unchanged from exact baseline, and the mismatch reproduces independently. No task-related regression remains.
- `python -m compileall -q src scripts tests`: exit 0.
- `git diff --check`: exit 0.

## L. Private replay comparison

The authorized five-category replay remained OFFLINE_PRIVATE_REPLAY: no network/provider/credential/LLM calls, no synthetic fallback, and no modification of original private assets.

| Category | Listings | Primary cohort | Assigned | Unclassified | Review | Routes | Candidates | Provenance / isolation violations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Shower Caddy | 998 | 650 | 600 | 203 | 195 | 15 | 5 | 0 / 0 |
| Dog Water Bottle | 400 | 280 | 0 | 400 | 0 | 0 | 0 | 0 / 0 |
| Vacuum Filter | 300 | 0 | 0 | 300 | 0 | 0 | 0 | 0 / 0 |
| Food Storage Set | 150 | 99 | 0 | 150 | 0 | 0 | 0 | 0 / 0 |
| Air Fryer Mixed | 300 | 162 | 64 | 233 | 3 | 11 | 5 | 0 / 0 |

Shower Caddy comparison: cohort `868 -> 650`, assigned `725 -> 600`, unclassified `268 -> 203`, review `5 -> 195`, routes `57 -> 15`, candidates `5 -> 5`, and candidate members `351 -> 371`. Non-primary assigned count remains 0.

Fragmentation decreased because arbitrary SOURCE_VALUE and Special Feature combinations no longer create route identities, while installation synonyms converge before grouping. The 15 remaining routes are not accepted merely because the count is lower: they retain explicit structural justification across product form, installation, and physical attachment. Portable, recessed-niche, and corner-shelf forms remain separate rather than being over-collapsed. The higher review count is deliberate fail-closed behavior for preserved installation conflicts.

Run1/Run2 (normal/reversed input) match in all five categories for both semantic and route results. New Shower Caddy semantic fingerprint: `5e9edc6726bfe1b3043309b92566da3d610ba5400062496b788798639ad9d84c`; route fingerprint: `5a68396bb465fcd4154caddc910b8cd308f8d80e01155e26d6acf4e7af7f351e`. Privacy leak count is 0. Automated/private remediation gate: **PASS**.

## M. Remaining known issues

- 195 Shower Caddy records contain route-critical installation conflicts and intentionally require review; they are not silently routed.
- 90 Shower Caddy records remain semantically UNKNOWN and 63 are OFF_TARGET_EXCLUDED. New unseen wording fails closed until a governed profile update supplies evidence.
- The unrelated Windows OOXML fingerprint difference remains as documented above.
- External human judgment is still required for route coherence and business sense. No final release PASS is asserted.

## N. New human-review package

The new governed basis has review sample ID `f042ec6debe4d0e7c8d1d9692dfb2cc35d05d0083e6c469c9e24b40edc469d36`: 45 rows covering all 15 Shower Caddy routes at 3 samples per route. All six governed boolean decision fields are null and notes are empty (0 non-null verdicts). A concise guide and binding manifest are generated in the external private SP-042F package after the single commit so they can bind to its exact HEAD; the final handoff records the exact private path and hashes. Prior SP-042E verdicts are not copied.

## O. Final git status

Before commit, the worktree contains only the intended files listed in section I and the index is otherwise clean. The final handoff records post-commit `git status --short`, HEAD, and stash retention checks. No private output is tracked.

## P. Commit SHA

This report is part of the single final commit, so its own immutable SHA cannot be self-embedded without creating a second commit. The exact commit SHA is recorded by `git rev-parse HEAD` in the final handoff and in the external human-review binding manifest.

**AUTOMATED/PRIVATE REMEDIATION GATE: PASS**

**FINAL RELEASE: BLOCKED — AUTHORIZED_HUMAN_ROUTE_REVIEW_PENDING**
