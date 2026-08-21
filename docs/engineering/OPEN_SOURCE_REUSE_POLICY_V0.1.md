# Open Source Reuse Policy V0.1

Status: **ACTIVE**
Effective date: 2026-08-19

## 1. Principle

For every non-trivial new capability, the project must search for reusable code before building from scratch.

Mandatory search order:

```text
1. Current amazon_product_intelligence codebase
2. Existing internal systems, especially amazon_ads_optimizer
3. Mature open-source GitHub projects
4. Build new only when reuse is unsuitable
```

The objective is to reduce duplicated engineering effort while keeping licensing, security, correctness, maintainability, and provenance under control.

## 2. Required disposition

Every reuse audit must end with exactly one primary disposition:

- `REUSE_AS_IS` — use an existing internal module or external dependency without changing its core implementation.
- `WRAP_AND_REUSE` — retain the reusable implementation and add a project-owned adapter or contract layer.
- `COPY_AND_ADAPT` — copy a limited, license-compatible implementation into the project, preserving provenance and adapting it to project contracts.
- `BUILD_NEW` — implement project-owned code because reuse does not satisfy the requirements.

Preference order:

```text
REUSE_AS_IS
  > WRAP_AND_REUSE
  > COPY_AND_ADAPT
  > BUILD_NEW
```

## 3. Mandatory Open Source Reuse Audit

Before implementation, record:

1. Capability being built.
2. Internal code searched.
3. GitHub/open-source projects searched.
4. Candidate repositories/packages.
5. License for each serious candidate.
6. Maintenance status and release recency.
7. Python/runtime compatibility.
8. Dependency size and operational complexity.
9. Security or network behavior.
10. Test coverage / reliability evidence.
11. Fit with project data contracts.
12. Selected disposition and rationale.

A feature must not be reimplemented simply because custom code is easy to write.

## 4. Prefer dependency use over source copying

For established libraries, prefer installing and pinning a package rather than copying its source into this repository.

Reasons:

- security fixes remain obtainable
- upgrades are traceable
- upstream ownership stays clear
- less code is maintained internally
- license handling is usually clearer

Use `COPY_AND_ADAPT` only when:

- the useful logic is small and separable
- package integration would introduce disproportionate complexity
- the license permits the intended use
- provenance is recorded
- copied code is covered by project tests

## 5. License gate

No external source code may be copied until its license is identified and reviewed.

General engineering rule:

- Permissive licenses such as MIT / BSD / Apache-2.0 are typically easier to integrate, but attribution and notice obligations still apply.
- Copyleft licenses such as GPL / AGPL require explicit compatibility review before copying, linking, distributing, or deploying.
- Repositories with no clear license are **reference-only by default** and must not be copied into production code.

This document is an engineering policy, not legal advice. If commercial distribution or SaaS obligations are uncertain, escalate for license review.

## 6. Provenance requirements for COPY_AND_ADAPT

Every copied external implementation must record:

- upstream repository URL
- upstream project name
- upstream commit SHA or release tag
- upstream file path(s)
- upstream license
- date imported
- files copied
- local modifications
- reason dependency installation was not used

The repository must maintain `THIRD_PARTY_NOTICES.md` or equivalent provenance records.

Do not copy snippets from unknown or unattributed sources.

## 7. Internal reuse from amazon_ads_optimizer

The advertising optimizer should be checked first for relevant capabilities.

Known reusable areas include:

- text normalization
- deterministic text similarity
- search intent concepts
- semantic relevance contracts
- product fact/evidence boundaries
- search-term demand taxonomy
- demand-type input derivation
- demand evidence and confidence patterns

The advertising optimizer's demand taxonomy includes concepts aligned with this project:

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

Reuse must preserve the distinction between product identity, product facts, semantic relevance, and commercial evidence.

## 8. Open-source candidates to evaluate

These are **candidates, not pre-approved dependencies**. Each must pass the audit and PoC before adoption.

### Specification and unit extraction

- `quantulum3`
  - candidate use: quantity/unit extraction from unstructured listing text
  - examples: oz, ml, liter, inch, pack count
  - verify category-specific behavior before adoption

### Unit conversion / canonicalization

- `Pint`
  - candidate use: unit conversion and canonical numeric representation
  - project-specific category bins remain project logic

### String similarity / normalization

- `RapidFuzz`
  - already used in `amazon_ads_optimizer`
  - candidate use: deterministic normalization-support and fuzzy matching
  - must not be treated as semantic truth by itself

### Semantic embeddings

- `sentence-transformers`
  - candidate use: embeddings, semantic similarity, paraphrase grouping
  - evaluate model size, CPU/GPU cost, multilingual performance, and local/offline operation

### Topic / demand clustering

- `BERTopic`
  - candidate use: grouping buyer-language expressions into interpretable demand themes
  - evaluate stability, outlier behavior, dataset-size requirements, and dependency weight

### Cluster labeling / keyword extraction

- `KeyBERT`
  - candidate use: representative words/phrases for cluster interpretation
  - AI-generated labels must remain traceable to source terms

Additional candidates should be searched when a new module begins.

## 9. Areas where from-scratch implementation is discouraged

Do not start from scratch without a documented reuse audit for:

- embeddings
- generic semantic similarity
- clustering algorithms
- topic modeling
- dimensionality reduction
- unit parsing
- unit conversion
- keyword/keyphrase extraction
- sentiment analysis
- aspect extraction
- fuzzy matching
- generic anomaly detection
- standard statistical algorithms

Project-owned engineering effort should focus on Amazon-specific logic:

- canonical product attribute contracts
- category-specific normalization rules
- demand taxonomy and evidence requirements
- weighting and denominator definitions
- supply coverage
- demand/supply gap interpretation
- Amazon data provenance
- operator-facing outputs
- safety and confidence handling

## 10. Testing requirements

Any external or reused component must have project-owned tests covering:

- deterministic normalization where expected
- category-specific edge cases
- unit/attribute conflicts
- missing fields
- ambiguous phrases
- incompatible specifications
- serialization
- offline/no-network behavior where required
- source provenance
- fallback behavior
- reproducibility of the project-facing contract

Upstream tests do not replace project integration tests.

## 11. Immediate application

This policy applies immediately to:

1. Product Attribute Extraction
2. Category Product Map
3. Buyer Need Analysis
4. Semantic Clustering
5. Supply / Demand Gap Analysis

The next Codex task should begin with an Open Source Reuse Audit and small PoC before full implementation.
