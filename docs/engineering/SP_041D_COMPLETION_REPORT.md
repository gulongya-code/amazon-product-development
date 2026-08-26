# TASK-SP-041D Completion Report

## A. Baseline/runtime/workspace

- Required and actual starting HEAD: `bcefe61e8bbd1a253663eece60a234b124a3f111`.
- Required parent confirmed: `50e2661a2eb45dc0a7cc46275f14edc6f7301a3d`.
- Dedicated branch: `codex/task-sp-041d-product-map-route-opportunity`.
- Clean start and staging were confirmed before edits; no unexpected work was reset, stashed, or discarded.
- Runtime: Python 3.14.4; pytest 9.1.1.
- Pre-change focused baseline: 425 passed, 111 subtests passed.
- Pre-change full baseline: 1 failed, 1404 passed, 13 skipped, 550 subtests passed. The sole failure was the known Windows OOXML fingerprint difference.

## B. Internal reuse audit

Completed and documented before algorithm implementation in `SP_041D_INTERNAL_REUSE_AUDIT.md`. Direct reuse includes SP-041B/SP-041C contracts, canonical JSON/deterministic IDs, Market Report V0.2 availability/evidence/completeness/reference contracts, and `MetricContextEnvelope`. Category Product Map and strict config patterns were adapted without invoking semantically different frozen builders. Semantic clustering and frozen Opportunity Score semantics were not reused or changed.

## C. Public GitHub/License audit

Completed and documented before algorithm implementation in `SP_041D_PUBLIC_GITHUB_REUSE_AUDIT.md`, including exact queries, repositories/files, licenses, selection decisions, attribution, configuration needs, and semantic tests. Final disposition: `NO_EXTERNAL_COPY_SELECTED`. No dependency, code, model, data, or test vector was copied; no new attribution obligation was created.

## D. Files added/modified

- Two versioned category route configs under `config/route_discovery/`.
- Internal/public audit, implementation guide, and this A–Y completion report under `docs/engineering/`.
- Full-chain local CLI `scripts/build_product_route_opportunity.py`.
- New `amazon_product_intelligence.product_route_opportunity` package with strict config, contracts, Product Map join, metrics, route engine, errors, and public exports.
- Focused acceptance suite `tests/test_product_route_opportunity_v1.py`.
- No frozen Market Report, Opportunity Score, provider, renderer, golden, workbook, or production-pipeline implementation file changed.

## E. Product Map record contract

`ProductMapRecord` joins SP-041B and SP-041C by exact listing ASIN set and fails closed on ID/fingerprint/grain mismatch. It preserves child ASIN identity, parent evidence without collapse, normalized attributes/conflicts/evidence, sales/revenue estimate provenance, price, rating/reviews, listing date/age, brand/seller, MoM/YoY, governed rank fields, new-product flag/threshold provenance, availability, limitations, IDs, and fingerprints.

## F. Route membership model

Every accepted listing receives exactly one `ASSIGNED`, `UNCLASSIFIED`, or `REVIEW_REQUIRED` membership. Each has at most one primary route. Core conflicts remain visible and require review; insufficient known attributes and below-minimum-size groups are unclassified. Secondary descriptors never create additional share membership.

## G. Route discovery method/config/versioning

Method `EXACT_KNOWN_STRUCTURAL_ATTRIBUTE_SIGNATURE`, engine `product-route-engine-v1.0`. Only available governed structural values enter the signature. Missing values emit no equality signal. Category feature inclusion, minimum evidence/size, cosmetic exclusion, candidate diversity, age threshold, and percentile method live in strict fingerprinted JSON. Color is explicitly forbidden as a V1 core dimension. No randomness or cluster enumeration identity exists.

## H. Cross-category portability proof

The same Product Map, route engine, metric, and candidate code produced four synthetic Shower Caddies routes and three synthetic Dog Water Bottle routes. Only accepted SP-041C rule packs and SP-041D data-only route configs differed. No category conditional or parser/engine fork was added.

## I. Route identity/explainability/determinism

Routes expose deterministic ID/fingerprint/label, canonical defining attributes, bounded secondary descriptors, member count/references, membership/evidence IDs, assignment limitations, attribute coverage, method/version/config fingerprint, and separate metrics. Input reversal and runtime timestamp changes preserve memberships, IDs, labels, route fingerprints, and result fingerprint.

## J. Route Listing Share / Sales Share denominators

Listing share uses route assigned count / all assigned count and accounts for unclassified/review-required exclusions. Sales share uses route available monthly-sales estimates / all available monthly-sales estimates across assigned routes, with missing sales excluded and SellerSprite third-party-estimate limitations. Synthetic listing and sales shares each sum to one within tolerance.

## K. Demand Efficiency calculation and interpretation boundary

`route_sales_share / route_listing_share`; underlying shares remain visible. Every metric states that the index is structural demand-vs-listing evidence, not profit, margin, conversion, procurement economics, or a commercial guarantee.

## L. MoM/YoY growth reconstruction + coverage

Input growth is a decimal fraction. Each valid prior is `current / (1 + growth)` and aggregate growth is `sum(current) / sum(prior) - 1`, calculated with Decimal. MoM and YoY are separate. Current-sales, growth-rate, and reconstruction coverage are published; missing pairs and `g <= -1` are excluded/flagged. Tests prove the result differs from an arithmetic percentage average.

## M. New-product metrics

Route new-product listing share, sales share, and demand efficiency use known ages only and preserve sales-estimate semantics. No authoritative numeric repository threshold existed, so the 180-day V1 threshold and source classification are explicit in each versioned config. Missing age remains unknown, never old.

## N. Review barrier / price opportunity evidence

Nearest-rank p25/median/p75 distributions publish counts and coverage. Limitations explicitly keep both outputs descriptive and prohibit automatic ease/profit conclusions.

## O. Brand/seller/product concentration metrics

Distinct listing-weighted and available-sales-weighted brand/seller top-1/top-3/top-5 and HHI metrics are produced, plus available-sales product concentration. Unknown identities are excluded and counted rather than merged; sales weighting uses only available estimates.

## P. Structural feature adoption evidence

Configured material, mounting/operation, capacity/pack, and special-feature distributions report known/unknown counts and known-evidence prevalence. Missing attributes are excluded rather than counted as non-adoption; output is descriptive, not causal.

## Q. Route-level governed result/fingerprint

`ProductRouteOpportunityResult` is an independent deterministic contract containing upstream IDs/fingerprints, engine/config identity, membership counts, Product Map records, memberships, routes/scorecards, registered denominators/references, candidate state, and sanitized diagnostics. Runtime timestamps are absent from semantic identity.

## R. Candidate 3–5 route selection + diversity/reason codes

Selection uses explicit evidence reason codes and deterministic lexicographic priority; no opaque total score exists. A configured greedy minimum structural-distance constraint suppresses near duplicates. Sufficient fixtures return 3–4 candidates; a strict-diversity and fewer-route fixture returns `INSUFFICIENT_EVIDENCE` with no forced candidates. No representative ASIN is selected.

## S. Mandatory private real-market replay — sanitized counts/coverage/fingerprints

- `PRIVATE_REAL_MARKET_REPLAY = NOT_RUN`.
- A header-level search of the workspace, project parent, Downloads, and Desktop found zero qualifying current SellerSprite acceptance assets.
- No real source path, ASIN, title, brand, seller, price, row, or detailed parameter was persisted or printed.
- Per the Issue hard gate, synthetic completion cannot be promoted to PASS.

## T. Network/provider/credential/LLM accounting

SP-041D production code constructs zero network clients/calls, reads zero provider credentials, and imports no AI/LLM client. Route membership is deterministic governed code only. No Sorftime/XiYou/provider call, review-text buyer-need inference, or AI override exists.

## U. Privacy/secret/ASIN leakage scan

- Secret-pattern scan: clean.
- New workbook/CSV/raw-data file scan: zero committed candidates.
- Production code and SP-041D documents contain no literal ASIN.
- Three literal ASIN-pattern values in tests (`B000000050` through `B000000052`) are explicit synthetic fixtures only; remaining test ASINs are generated synthetic values.
- Sanitized CLI test proves no ASIN/title/brand/seller/price/path is printed and no detailed replay output is persisted.

## V. Focused/affected/full regressions

- New SP-041D suite: 12 passed.
- SP-041A/B/C plus affected Product Intelligence, Opportunity, Market Report, and Production Pipeline: 395 passed, 101 subtests passed.
- Post-change full suite: 1 failed, 1416 passed, 13 skipped, 550 subtests passed.
- Sole failure is identical to the exact-baseline exception: `tests/test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`; expected `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`, actual `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.
- No OOXML renderer/golden/delivery file was modified.

## W. Git/diff/status

Dedicated branch, whitespace check, staged review, secret/privacy scans, commit, push, and final clean workspace/staging are completion requirements and are performed as release hygiene for this report. The branch contains SP-041D scope only.

## X. SP-041E readiness

The independent result exposes stable routes, members, evidence, scorecards, candidates, and upstream/config fingerprints suitable as a future SP-041E input. SP-041E representative roles, medoids, direction lock, and Direct Competitors were not started.

## Y. Final verdict

`BLOCKED — PRIVATE_REAL_MARKET_REPLAY_REQUIRED`
