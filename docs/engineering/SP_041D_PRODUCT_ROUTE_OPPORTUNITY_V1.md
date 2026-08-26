# Product Map, Route Discovery & Opportunity Metrics V1.0

## Boundary

SP-041D consumes the accepted listing-grain `GovernedMarketDatasetV1` and `ProductAttributeMapV1`. It performs no provider call, credential read, LLM inference, parent-family collapse, representative-ASIN selection, Direct Competitor construction, profitability calculation, workbook rendering, or SP-041E work.

The full local flow is:

`SellerSprite local file -> SP-041B import -> SP-041C attribute map -> SP-041D Product Map -> routes -> route scorecards -> candidate routes`

## Product Map

Each accepted ASIN has one deterministic `ProductMapRecord`. It preserves the child ASIN, parent-ASIN evidence without collapsing children, upstream listing/attribute fingerprints, all SP-041C attribute availability/conflicts/evidence, governed market fields, and an explicit new-product flag. Missing fields remain `UNAVAILABLE`; they are never converted to zero, false, or an inferred negative.

Monthly sales and revenue retain `THIRD_PARTY_ESTIMATE` evidence semantics. The Product Map supports sales, revenue, price, rating, reviews, listing date/age, brand, BuyBox seller, MoM/YoY growth, and governed category/subcategory ranks when present.

## Route discovery

Method: `EXACT_KNOWN_STRUCTURAL_ATTRIBUTE_SIGNATURE`

Version: `product-route-engine-v1.0`

The route engine is category-neutral. Category differences live only in strict versioned JSON configuration. A primary signature contains available configured structural dimensions only. Missing slots do not emit a signature component, do not act as equality, and cannot create a route by themselves. Core conflicts or review-required slots yield `REVIEW_REQUIRED`; insufficient known attributes and groups below `min_route_size` yield `UNCLASSIFIED`. Every accepted listing has exactly one membership status and at most one primary route.

Route IDs depend on method/version/config fingerprint and canonical defining attributes, not row order, timestamps, or enumeration labels. Route semantic fingerprints additionally cover canonical members, evidence, limitations, coverage, descriptors, and metrics. Color is rejected as a V1 core dimension and is cosmetic in both accepted category configurations.

## Metrics and denominators

Every route metric uses the existing Market Report V0.2 `MetricContextEnvelope` and reports sample counts, coverage, availability, evidence, provenance, limitations, a governed method policy, and a registered denominator reference.

- Listing share: route assigned listings / all assigned listings. Unclassified and review-required listings are excluded and counted.
- Sales share: route available monthly-sales estimate / all available monthly-sales estimates across assigned routes. Missing sales are excluded, never zero-filled.
- Demand efficiency: sales share / listing share. This is demand-vs-listing structure only; it is not profit, margin, conversion, or a commercial guarantee.
- Growth: for each valid row, `prior = current / (1 + growth)`; route growth is `sum(current) / sum(prior) - 1`. Input growth is a decimal fraction. MoM and YoY remain distinct; `growth <= -1` and missing pairs reduce coverage.
- New product: listing share, sales share, and demand efficiency use known listing ages only. The 180-day threshold is externalized in each V1 config because the baseline repository exposes no authoritative numeric threshold. Missing age is not old.
- Review and price: nearest-rank p25/median/p75 distributions with coverage; descriptive only.
- Concentration: distinct listing-weighted and available-sales-weighted top-1/top-3/top-5 shares and HHI. Unknown brand/seller identities are excluded, counted, and never merged into a fake entity.
- Adoption: configured structural feature prevalence among listings with known evidence. Missing evidence is excluded, not treated as non-adoption.

All business arithmetic is performed with `Decimal`; finite JSON numbers are emitted only at the accepted metric-contract boundary.

## Candidate routes

Candidate selection exposes no universal or opaque total score. Routes receive explicit reason codes from available scorecard dimensions, are ordered by a deterministic lexicographic policy, and pass a configured greedy minimum structural-distance constraint. V1 returns 3–5 routes only when at least three evidence-qualified materially distinct routes remain. Otherwise it returns `INSUFFICIENT_EVIDENCE` with no forced candidates. Candidate order is research priority only.

## CLI

Detailed local output:

```powershell
.\.venv\Scripts\python.exe scripts\build_product_route_opportunity.py `
  --input <local-export.xlsx> `
  --rule-pack config\category_rule_packs\shower_caddies.v1.json `
  --route-config config\route_discovery\shower_caddies.v1.json `
  --marketplace US `
  --category "Shower Caddies" `
  --observed-date YYYY-MM-DD `
  --output <new-isolated-result.json>
```

Private acceptance replay (in-memory; no detailed result persisted):

```powershell
.\.venv\Scripts\python.exe scripts\build_product_route_opportunity.py `
  --input <private-local-export.xlsx> `
  --rule-pack <accepted-category-rule-pack.json> `
  --route-config <accepted-route-config.json> `
  --marketplace US `
  --category <category> `
  --observed-date YYYY-MM-DD `
  --sanitized-replay-only
```

The replay summary contains counts, coverage ranges, availability counts, route-size counts, fingerprints, and runtime only. It does not print ASINs, titles, brands, sellers, prices, detailed parameters, rows, or paths.

## Private replay gate

Synthetic validation cannot satisfy the mandatory private replay. If the operator's current real external SellerSprite asset is unavailable, the only valid acceptance verdict is `BLOCKED — PRIVATE_REAL_MARKET_REPLAY_REQUIRED`.
