# Public GitHub Reuse Audit V1.0

Date: 2026-08-26
Repository target: `gulongya-code/amazon-product-development`
Purpose: identify reusable public code before SP-041 implementation, while preventing license/semantic contamination.

## Decision rules

- Prefer project-internal reuse first.
- Prefer dependencies or small licensed components over copying whole applications.
- MIT / Apache-2.0 / BSD: eligible after technical review.
- No license / All Rights Reserved: reference only.
- Provider data semantics, missingness, provenance, deterministic IDs and existing strict contracts remain authoritative even when external code is reused.

## Candidates reviewed

| Repository | License status | Classification | Relevant capability | Decision |
|---|---|---|---|---|
| `nexscope-ai/Amazon-Skills` | MIT | DIRECT_REUSE_ALLOWED | Amazon product-research framework, FBA/referral fee calculator, keyword/research utilities | Reuse selected calculation/data-structure patterns where current; do not copy stale 2024 fee tables without revalidation. |
| `nexscope-ai/eCommerce-Skills` | MIT | DIRECT_REUSE_ALLOWED | Competitor-analysis and product-review-analysis frameworks | Reuse analytical decomposition/prompt constraints where compatible with evidence-first design. |
| `DannylydST/sorftime-data-cli` | MIT | DIRECT_REUSE_ALLOWED / REFERENCE | Sorftime endpoint inventory, field aliases, recipes and CLI patterns | Reuse endpoint/field documentation and small compatible utilities only; current accepted SP-040 HTTP/DTO contracts remain authoritative. |
| `scikit-learn/scikit-learn` | BSD-3-Clause | DEPENDENCY_REUSE | preprocessing, TF-IDF support ecosystem, KMeans/MiniBatchKMeans, silhouette/cluster metrics | Prefer library dependency for route discovery rather than copying clustering algorithms. |
| `tom-juntunen/target-web-fetch` | no LICENSE found in repository root | REFERENCE_ONLY | mixed numeric/categorical/text product clustering; auto-k; MiniBatchKMeans; cluster diagnostics | Architecture is highly relevant to Product Map, but code must not be copied unless licensing is clarified. Reimplement only needed ideas using licensed libraries. |
| `ericmc/amazon-product-research-playbook` | no LICENSE found | REFERENCE_ONLY | CSV import from product-research tools, scoring, refresh workflow | Reference import UX and scoring workflow only; no code copy. |
| `Umair706/amazon-omniscient` | All Rights Reserved | REFERENCE_ONLY | Amazon opportunity scoring, review clustering, FBA/profit models, product blueprints | Reference concepts only; explicitly prohibited from copying/modifying without authorization. |
| `liangdabiao/claudesdk-amazon-chat` | no LICENSE found | REFERENCE_ONLY | Chinese Amazon category-selection, keyword/review/product-research workflow | Reference workflow/testing ideas only; no code copy. |

## Reuse plan by SP-041 workstream

### SellerSprite import

No trustworthy SellerSprite-specific permissive adapter was found in the first pass. Implement a small provider-neutral header-mapping adapter in-house, while borrowing only generic CSV/XLSX validation patterns from licensed dependencies already used by the project. Do not silently fuzzy-map unknown headers. Optional fuzzy matching may only generate operator suggestions.

### Listing attribute parsing

Use deterministic parsing first. Reuse standard library/established parsing utilities where possible. External e-commerce extraction projects are useful references, but the project must keep evidence status per field and must not let LLM extraction override explicit structured facts.

### Product Map / route discovery

Use `scikit-learn` components directly for standardization, TF-IDF/SVD (if needed), KMeans/MiniBatchKMeans and validation metrics. Recreate a mixed-feature pipeline under our own contracts; the unlicensed `target-web-fetch` implementation is reference only. MVP should prefer explainable structured attributes before embeddings.

### Opportunity scoring

Reuse the decomposition idea from MIT Nexscope frameworks only where it matches our own governed metrics. Our score must remain derived from SellerSprite import semantics and existing Evidence/Provenance contracts; external fixed weights are not authoritative.

### Cost ceiling / FBA calculation

`nexscope-ai/Amazon-Skills/amazon-fba-calculator/scripts/calculator.py` is MIT and contains reusable dataclass/calculation organization. Its fee constants are dated 2024, so only structural code/patterns are eligible until current Amazon fee rules are independently validated. For MVP, imported SellerSprite FBA fee may remain the observed fee input and the 30% target-margin reverse calculation is ours.

### Sorftime deep dive

The MIT Sorftime Data CLI can support endpoint/field discovery and test fixture design. Do not replace the accepted SP-040 provider client/DTO/mapper with CLI code; accepted live wire evidence stays authoritative.

### Excel template delivery

Prefer current project renderer/template code and a minimal template adapter. Do not import a whole external reporting framework. The workbook is a contract: preserve sheet names, hidden states, formulas, named ranges/pivots where supported, and fail closed on unsupported structural drift.

## Mandatory Codex behavior

Before changing code in every SP-041 task, Codex must report:

1. public GitHub queries used;
2. candidate repositories/files;
3. license classification;
4. exact component chosen for reuse or reason for rejection;
5. whether code is copied, adapted, or merely used as a dependency/reference;
6. attribution/license files required in the repository;
7. tests proving external behavior did not weaken project contracts.

If licensing is missing or ambiguous, the default classification is `REFERENCE_ONLY`.
