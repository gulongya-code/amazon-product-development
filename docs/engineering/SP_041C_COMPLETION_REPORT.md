# SP-041C Completion Report

Issue: `#53 TASK-SP-041C`
Required baseline: `50e2661a2eb45dc0a7cc46275f14edc6f7301a3d`
Branch: `codex/task-sp-041c-listing-attribute-parser`

## A-V acceptance record

**A — Baseline gate.** Development began from the exact required baseline with
a clean index/worktree. The dedicated branch was created directly at that
commit.

**B — Internal reuse audit.** Completed before implementation and recorded in
`SP_041C_INTERNAL_REUSE_AUDIT.md`.

**C — Public GitHub/license audit.** Completed before implementation and
recorded in `SP_041C_PUBLIC_GITHUB_REUSE_AUDIT.md`. Outcome:
`NO_EXTERNAL_COPY_SELECTED`; no dependency or copied asset was added.

**D — Governed upstream.** The engine accepts only SP-041B
`GovernedMarketDatasetV1` and preserves dataset/record fingerprints and ASIN
grain.

**E — Structured parser.** The fixed `Key: Value | Key: Value` parser
deduplicates equivalent repetitions and surfaces same-key different-value
conflicts.

**F — Required dimensions.** All 13 required dimensions are emitted in fixed
order, including explicit `UNAVAILABLE` and `REVIEW_REQUIRED` states.

**G — Evidence and provenance.** Values contain categorical confidence,
source field/key/snippet/ref, upstream fingerprint, rule ID/version, and
`OBSERVED` or `DERIVED_RULE` status.

**H — Evidence precedence.** Structured > dedicated > explicitly authorized
SKU > explicitly authorized title is deterministic; lower evidence cannot
overwrite higher evidence.

**I — Category isolation.** Generic parsing/measurement/resolution contains no
Shower Caddies ontology. Category semantics are external strict JSON.

**J — Negative boundaries.** Tests freeze pack vs pocket/tier/shelf/layer,
no-drilling and wall-mounted vs adhesive, hanging specificity, title
non-override, material source specificity, and ambiguous unit behavior.

**K — Numeric safety.** Exact full-string patterns and `Decimal` normalize
length, mass, volume, dimensions, and counts while preserving original values,
units, and item/package scope.

**L — Shower Caddies pack.** Sanitized V1.0 configuration covers product form,
mounting, material family, capacity/count, general attributes, dimensions, and
weight.

**M — Second category proof.** Dog Water Bottles uses the same parser and
engine with configuration only.

**N — Product Attribute Map.** Dataset and records include stable IDs,
semantic fingerprints, upstream identity, rule-pack identity, parser versions,
coverage, counts, evidence, review items, and conflicts.

**O — Determinism.** Tests cover casing/spacing/order invariance, repeated
equivalent input, repeated builds, and timestamp-free output identity.

**P — Narrow API/CLI.** Public library functions and a local-only CLI are
provided. CLI output is exclusive and sanitized.

**Q — Privacy/security.** No provider call, network access, credential, raw
private fixture, LLM, AI inference, or full local path is introduced.

**R — Focused validation.** `185 passed, 70 subtests passed`, including
SP-041A, SP-041B, normalization, conflicts, existing attribute/category maps,
and all SP-041C tests.

**S — Full regression.** `1404 passed, 13 skipped, 550 subtests passed`;
one known baseline failure remained and no new failure was introduced.

**T — Known unrelated baseline failure.** The pre-change full suite had one
existing OOXML canonical-hash failure in
`test_ruleset_identity_filename_and_media_type`. The post-change run produced
the same expected hash `89ffe16d...` and actual hash `84e5aed6...`.

**U — Private replay.** `PRIVATE_REAL_LISTING_REPLAY = NOT_RUN`. No authorized
private SellerSprite file was required for acceptance and no private artifact
was committed.

**V — Verdict.** PASS — CROSS_CATEGORY_LISTING_ATTRIBUTE_PARSER_V1

## Forbidden-scope attestation

No SP-041D or later work was started. This change does not create archetypes,
routes, scores, representatives, direct-competitor decisions, procurement
truth, workbook/report/pipeline integration, provider/network behavior, or AI
logic.
