# Category Product Map & Buyer Need Map Vision V0.1

## Purpose

Transform a large set of Amazon ASINs into a structured explanation of:

- what products exist
- how product specifications are distributed
- what buyers are trying to achieve
- which needs are well supplied
- which needs appear under-supplied
- which concrete product configurations deserve deeper validation

## A. Category Product Map

### A1. Attribute extraction

For each product, extract structured facts from authoritative data sources:

```text
ASIN
parent/variation identity
product type
capacity
dimensions
material
structure
operating method
features
compatibility
pack quantity
audience
use case
problem solved
price
sales / revenue evidence
review evidence
source provenance
confidence
```

A fact must remain `UNKNOWN` when evidence is missing. Missing evidence must not be interpreted as universal compatibility/support.

### A2. Canonicalization

Normalize equivalent expressions into common representations.

Examples:

```text
20 oz / 20oz / ~600 ml / 0.6 L
2-pack / pack of 2 / 2 count
stainless / stainless steel / SS (only when context safely supports it)
```

Canonicalization should preserve raw source values and references.

### A3. Market structure outputs

For every commercially meaningful dimension, calculate:

- ASIN count
- ASIN share
- estimated unit-sales share when available
- estimated revenue share when available
- average/median price
- review distribution
- top-product concentration
- new-product presence

Support cross-dimensional segments:

```text
capacity + material
capacity + feature
material + use case
audience + specification
feature + problem solved
```

## B. Buyer Need Map

### B1. Evidence sources

Use multiple sources where available:

- Amazon search/query evidence
- advertising search terms
- review text
- titles/bullets
- listing attributes
- Q&A/customer-language sources
- search volume or equivalent demand metrics

Keep source types separate so a review-mention percentage cannot silently become a search-demand percentage.

### B2. Demand taxonomy

Reuse internal demand concepts where possible and extend only when needed.

Core dimensions:

- product object
- attribute
- specification
- use case
- audience
- compatibility
- problem/solution
- brand/model
- accessory/related-product
- alternative-product
- broad exploration
- unrelated demand

### B3. Semantic grouping

Different phrases may express the same need:

```text
"doesn't leak"
"leak proof"
"no water spills in my bag"
"keeps water from dripping"
```

These can be grouped into a leak-prevention demand cluster when semantic and evidence checks support the mapping.

Semantic similarity is supporting evidence, not authority. Fatal specification conflicts or incompatible product boundaries override a high similarity score.

### B4. Buyer-need metrics

Do not emit an undefined single percentage.

Possible metrics:

```text
query_count_share
search_volume_share
review_mention_share
review_product_coverage
supply_product_coverage
sales_share_of_matching_products
revenue_share_of_matching_products
composite_demand_index
```

Every metric must publish its denominator, weighting, evidence window, and coverage.

## C. Supply / Demand Gap

Join the Buyer Need Map with product supply coverage.

Example:

```text
Demand cluster: large-dog + large-capacity + leakproof
Demand evidence: strong
Supply coverage: low
Sales performance of matching products: strong
Competition: moderate
Conclusion: candidate gap for deeper product validation
```

The gap engine must distinguish:

- high demand / high supply
- high demand / low supply
- low demand / high supply
- low demand / low supply
- insufficient evidence

## D. Role of Opportunity Scoring

Opportunity Scoring becomes an aggregation layer over interpretable evidence.

A score should be decomposable into:

- demand
- supply gap
- competition
- sales/revenue evidence
- trend
- concentration
- confidence / data coverage

The operator must be able to inspect why a score was produced.

## E. Proposed architecture

```text
Data acquisition
  -> Cleaning / Canonical Data Model
  -> Product Attribute Extraction
  -> Unit & Attribute Canonicalization
  -> Category Product Map
  -> Text Evidence Normalization
  -> Internal Relevance / Demand Taxonomy Reuse
  -> Semantic Embedding / Clustering (after PoC)
  -> Buyer Need Map
  -> Supply / Demand Gap
  -> Competition
  -> Opportunity Scoring
  -> AI Analysis / Operator Workbook
```

## F. Development guardrails

1. Reuse before build.
2. Preserve provenance.
3. Do not invent missing facts.
4. Do not collapse incompatible specs because text is similar.
5. Define denominators before reporting percentages.
6. Separate product supply from buyer demand.
7. Separate review-language prevalence from search demand.
8. AI labels clusters; evidence remains inspectable.
9. Prefer deterministic preprocessing around probabilistic NLP.
10. Build PoCs with real Amazon samples before locking dependencies.

## G. Next milestone

A small PoC should prove that the system can:

1. take a real category sample;
2. extract at least several specification/attribute dimensions;
3. normalize units;
4. produce attribute distributions;
5. group semantically equivalent buyer-language phrases;
6. map them to demand taxonomy dimensions;
7. report at least two explicit demand-share metrics;
8. produce a first supply/demand gap table with source evidence.
