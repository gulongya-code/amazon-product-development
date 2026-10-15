# TASK-SP-041R2 targeted implementation reuse audit

Audit date: 2026-08-29

Baseline: `ac8d66afed2fc11e20986bae46e09f6c78708ecf`

This audit was completed before adding Route Discovery V2 implementation code. It is intentionally narrower than the public dependency audits already accepted by S1 and SP-041D.

## Decision

Route Discovery V2 will be a small APD-local extension over the accepted Semantic Engine V2 and Product Route Opportunity V1 metric implementation. It will not introduce a dependency, copy an external implementation, create another semantic package, or change an accepted semantic or market-metric formula.

The rejected V1 exact-known-attribute signature is the only route identity strategy being replaced. S2 remains the sole authority for Product Identity, Product Role, conflicts, profile lineage, and `PRIMARY_ONLY` cohort eligibility.

## Internal component classification

| Existing component | Classification | Route V2 use |
| --- | --- | --- |
| `semantic_engine_v2.models.SemanticEngineV2Result` and listing/fact contracts | `REUSE_AS_IS` | Authoritative upstream semantic result and fact/evidence lineage. |
| S2 `ProductIdentity`, `ProductRole`, and `APDMarketCohortEligibility` | `REUSE_AS_IS` | Gate discovery through the published `PRIMARY_ONLY` decision; never recalculate from raw text. |
| `CategorySemanticProfileV1_1.source_policies` and `RoleRelevance` | `REUSE_AS_IS` | Validate that configured route dimensions are profile-authorized and promoted. |
| S2 relationship/conflict states | `REUSE_AS_IS` | Preserve true and route-critical conflicts; route-critical conflict remains review authority. |
| Category Semantic Profile JSON files | `REUSE_AS_IS` | Category vocabulary and semantic extraction stay in data, outside generic route control flow. |
| `contracts.canonical_json` and `contracts.deterministic_id` | `REUSE_AS_IS` | Canonical route identity, memberships, references, and stable fingerprints. |
| SP-041D `product_route_opportunity.metrics.build_route_metrics` | `REUSE_AS_IS` | Retain listing/sales shares, Demand Efficiency, growth reconstruction, new-product, distribution, concentration, adoption, denominator, coverage, and limitation formulas exactly. |
| SP-041D market-field projection in `product_map.py` | `EXTEND` | Expose/refactor the existing governed market-field projection so an S2-backed metric record can reuse it without requiring SP-041C route identity. V1 behavior must remain byte-for-byte equivalent under its regressions. |
| SP-041D product-grain/reference primitives | `REUSE_AS_IS` | Keep listing ASIN grain with no parent collapse and preserve governed market provenance. |
| SP-041D route metric/candidate reason helpers | `EXTEND` | Reuse metric qualification and deterministic ordering; calculate diversity from Route V2 route-eligible semantic definitions only. |
| SP-041D membership/result concepts | `EXTEND` | Preserve `ASSIGNED`, `UNCLASSIFIED`, and `REVIEW_REQUIRED`, while adding S2/profile/config lineage and membership fingerprints required by Issue #57. |
| SP-041D exact-known structural signature | `REPLACE_IN_V2` | Replace as the primary route identity with deterministic, ordered hierarchical sparse semantic consensus over S2-authorized defining values. V1 remains available for comparison/regression. |
| SP-041D facet-driven distance over V1 defining attributes | `REPLACE_IN_V2` | Candidate distinctness is computed only from Route V2 route-eligible semantics. |
| SP-041C listing-attribute map as a Route V2 dependency | `DEPRECATE_AFTER_V2` | Retained for V1 and regressions, but Route V2 consumes SP-041B plus accepted S2 output and does not bypass S2. |

## Smallest safe extension boundary

The new package may contain only:

- strict versioned Route V2 configuration and profile-authorization validation;
- a semantic route-feature projection over S2 facts;
- deterministic ordered hierarchical sparse semantic-consensus grouping, membership, route, and pairwise-distinct candidate contracts;
- an S2-to-existing-metric record adapter;
- a sanitized aggregate-only private replay boundary and focused tests.

It must not contain category-name branches, semantic extraction rules, raw-title Product Identity logic, Product Role rules, market-metric formula copies, provider calls, credentials, LLM decisions, representative ASIN selection, Direct Competitor logic, or procurement logic.

## Algorithm reuse decision

Repository search found no accepted internal Route V2 implementation to import as-is. The required grouping is small enough to implement with project-local canonical sets, deterministic ordering, bounded compatibility rules, and a bounded candidate-clique search. No general clustering, graph, numerical, or machine-learning dependency is justified.

The V2 strategy therefore uses only Python standard-library data structures and existing repository primitives. The complete configured route-dimension order remains authoritative, and each present route dimension retains every profile-authorized `defining_values` entry in the listing signature; no first-value reduction occurs, and corroborating-only observations never become route identity. The first available config-ordered dimension supplies the full-value-set base. Viable bases meet the configured size floor; a tiny base can merge only with one uniquely compatible same-dimension viable base while preserving a non-empty combined consensus, otherwise it remains unresolved during hierarchical construction.

Later configured dimensions refine a viable node only when at least two distinct exact single-value buckets each independently meet the size floor. Missing, multi-value, and rare remainders form a broad parent when collectively viable. When that remainder is too small, only a multi-value signature with one uniquely intersecting viable child can attach directly during hierarchical construction.

After viable hierarchical routes exist, the generic resolver evaluates every still-unresolved group that has a real defining signature against the complete route definitions. Compatibility requires at least one shared dimension and a non-empty value-set intersection on every shared dimension. Zero compatible routes becomes `UNCLASSIFIED`, one becomes `ASSIGNED`, and multiple become `REVIEW_REQUIRED`. Missing dimensions and corroborating-only evidence cannot create equality; market metrics, lexical order, input order, and canonical sorting cannot break an ambiguity. Canonical serialization and ordering serve determinism only. Candidate selection retains frozen SP-041D qualification and searches deterministically from five candidates down to three for a clique whose every pair has contradictory known route semantics and meets the configured semantic-distance floor.

The local replay CLI is an acceptance boundary, not a new production or semantic authority. It writes only a sanitized aggregate summary plus an explicitly external listing-grain review artifact with blank operator decision cells. Neither the generic engine nor the replay path contains category-specific control-flow branches, network/provider calls, or authoritative LLM decisions.

## Public GitHub and license disposition

Issue #57 explicitly retains the broad public audits completed by S1 and SP-041D unless this task adds a dependency or copies/adapts an external algorithm. The accepted baseline already contains:

- `docs/engineering/SP_041S1_REUSE_AUDIT_V1_1.md`;
- `docs/engineering/SP_041S1_CROSS_SYSTEM_REUSE_AUDIT_V1_1.md`;
- `docs/engineering/SP_041D_PUBLIC_GITHUB_REUSE_AUDIT.md`;
- `docs/engineering/OPEN_SOURCE_REUSE_POLICY_V0.1.md`.

Route V2 adds no dependency and uses no copied or adapted public implementation. Consequently:

- new third-party package count: `0`;
- copied/adapted external algorithm count: `0`;
- new license obligations: `0`;
- new dependency security/determinism review required: `NO`;
- public audit disposition: `RETAIN_ACCEPTED_AUDITS`.

If implementation later requires any external package or copied algorithm, work must stop and this audit must be reopened before that code is added.

## Frozen boundaries confirmed

- S2 Product Identity, Product Role, relationships, conflicts, and cohort contracts are unchanged.
- SP-041D business metric formulas and denominator semantics are unchanged.
- Category-specific knowledge remains in accepted semantic profiles or versioned route config, never generic Python branches.
- Route membership remains deterministic without network, provider, credential, or LLM availability.
- Private calibration assets and listing-grain review material remain external to Git.
- Shared Semantic Core extraction, KWS cutover, representative ASINs, Direct Competitors, procurement ceiling, SP-041E, and later tasks are out of scope.

## Pre-implementation gate status

- exact required branch and baseline: `PASS`;
- clean workspace and staging before this audit: `PASS`;
- focused S2/SP-041A-D baseline: `105 passed`;
- affected baseline: `421 passed, 5 skipped, 115 subtests passed`;
- full exact-baseline run: `1457 passed, 13 skipped, 550 subtests passed`; the sole OOXML fingerprint failure exactly reproduced the accepted baseline mismatch;
- internal reuse decision: `COMPLETE`;
- public reuse/license decision: `NO_NEW_AUDIT_TRIGGER`.

Verdict: `APPROVED_TO_IMPLEMENT_ROUTE_DISCOVERY_V2_WITHIN_ISSUE_57_SCOPE`.
