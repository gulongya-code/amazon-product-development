# Product Intelligence Priority Decision — 2026-08-19

Status: **ACTIVE**  
Scope: Amazon product intelligence / product development system  
Decision date: 2026-08-19

## 1. Core product direction

The system must not stop at API ingestion, generic cleaning, competition analysis, or a single opportunity score.

The primary user value is to turn a category into an understandable market structure:

1. What product specifications, attributes, structures, materials, sizes, functions, package quantities, and price bands exist?
2. What share of the market does each specification or attribute represent?
3. What different buyer needs exist, and how large is each need?
4. Which buyer needs are already over-supplied, and which needs have weak supply relative to demand?
5. Which concrete product configurations deserve further product-development research?

Target pipeline:

```text
Amazon / third-party data
    -> cleaning and canonicalization
    -> product attribute extraction
    -> category product map
    -> buyer need analysis
    -> semantic clustering / demand taxonomy
    -> supply-demand gap analysis
    -> competition analysis
    -> opportunity scoring
    -> AI product-development conclusion
```

Competition and opportunity scoring remain useful, but they move downstream. They must consume the category structure and buyer-demand evidence rather than replace it.

## 2. First priority: Product Attribute Extraction + Category Product Map

The next main development line is product-attribute extraction and normalization.

Examples of dimensions:

- capacity / volume
- dimensions / size
- material
- structure
- operating method
- feature
- compatibility
- pack quantity
- color where commercially meaningful
- intended audience
- use case
- problem solved
- price band

Equivalent expressions must be normalized before statistics are calculated. Example:

```text
20 OZ
20oz
~600 ml
0.6 L
```

These should be mapped to a canonical numeric/unit representation when they describe the same physical specification.

The Category Product Map should support at least:

- ASIN share by attribute/specification
- estimated unit-sales share by attribute/specification when reliable sales evidence exists
- estimated revenue share by attribute/specification when reliable revenue evidence exists
- average/median price
- review-count distribution
- new-product share
- top-product concentration
- cross-dimension combinations, e.g. `large capacity + stainless steel + leakproof`

A raw ASIN-count percentage must not be presented as market demand by itself.

## 3. Second priority: Buyer Need Map

Buyer demand should be derived from multiple evidence sources when available:

- search terms / search queries
- reviews
- listing titles and bullets
- product attributes and selling points
- Q&A or similar customer-language sources when legally and technically available
- Amazon-provided demand/search-volume evidence when available

The system should classify and cluster demand into a stable taxonomy. Existing demand concepts from the advertising optimization system should be reused where applicable, including:

- CORE_PRODUCT
- PRODUCT_ATTRIBUTE
- SPECIFICATION
- USE_CASE
- AUDIENCE
- COMPATIBILITY
- PROBLEM_SOLUTION
- BRAND_OR_MODEL
- ACCESSORY_OR_RELATED_PRODUCT
- ALTERNATIVE_PRODUCT
- BROAD_EXPLORATION
- UNRELATED_DEMAND

Semantic clustering is used to merge different expressions of the same buyer need. Example:

```text
for hiking
long walks
travel with my dog
easy to carry outdoors
```

These may form an `outdoor / travel portability` cluster when the evidence supports that interpretation.

## 4. Demand share must be evidence-aware

Do not report one universal "buyer need share" unless the denominator and weighting are explicit.

Prefer separate metrics such as:

- search-query share
- search-volume-weighted demand share
- review-mention share
- review-product coverage share
- product-supply coverage share
- estimated sales/revenue share of products satisfying the need
- composite demand index only when its formula and inputs are explicit

This prevents false precision such as treating 20% of review mentions as 20% of total category purchasing demand.

## 5. Third priority: Supply / Demand Gap

The most valuable output is not a generic score but an interpretable gap statement.

Example structure:

| Need / configuration | Demand evidence | Supply coverage | Sales evidence | Competition | Conclusion |
|---|---:|---:|---:|---|---|
| basic plastic bottle | high | very high | medium | high | low priority |
| large capacity | high | medium | high | medium | investigate |
| large capacity + leakproof | high | low | high | lower | high-priority gap |
| insulated | medium | very low | promising | low | validate |

The final AI conclusion should point to a concrete configuration and cite its evidence, rather than only outputting an opaque opportunity score.

## 6. Development order

Effective immediately, development priority is:

1. Product Attribute Extraction
2. Canonical specification/unit normalization
3. Category Product Map
4. Buyer Need taxonomy reuse from `amazon_ads_optimizer`
5. Semantic clustering and synonym/phrase consolidation
6. Buyer Need Map
7. Supply / Demand Gap analysis
8. Feed these results into Competition and Opportunity Scoring

## 7. Immediate next engineering task

Before building new NLP or clustering code, run an **Open Source Reuse Audit + small PoC**.

The PoC should use a small real Amazon sample and verify:

- specification extraction
- unit normalization
- attribute canonicalization
- search/review text normalization
- semantic grouping of equivalent buyer-language expressions
- mapping clusters into the project demand taxonomy
- preservation of source evidence and confidence

Only after the PoC should the final implementation architecture be locked.

## 8. Non-goals for the next task

The next task should not:

- redesign the entire scoring system
- remove existing cleaning/competition/scoring work
- build a vector database before proving it is needed
- treat similarity alone as buyer-demand truth
- make AI-generated product facts authoritative without evidence
- calculate demand percentages without a defined denominator

Existing work remains reusable; the project direction is being re-ordered around category structure and buyer demand.
