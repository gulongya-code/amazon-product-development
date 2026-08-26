# SP-041A Public GitHub Reuse and License Audit

Date: 2026-08-26
Baseline: `a0cf42685c75d5f611ce40c99b96d8cb731d45ba`

This audit was completed after the internal audit and before implementation.
No public repository code was copied or adapted.

## Queries used

1. `Python openpyxl formula audit workbook fingerprint license`
2. `Python Excel formula parser xlsx MIT license`
3. `openpyxl LICENSE formula tokenizer`
4. `xlcalculator license formula parser Python`
5. Exact-repository checks for all candidates named in Issue #51 and the
   planning-branch first-pass audit.

## Candidate and license gate

| Repository/component | License reviewed | Classification | Decision and reuse mode |
|---|---|---|---|
| `openpyxl` formula tokenizer and workbook APIs | MIT; already a pinned project dependency | `DEPENDENCY_REUSE` | Selected. Use installed APIs to read formulas, defined names, filters, tables, pivots, and numeric formula tokens. No source copied. Existing dependency notices remain sufficient. |
| `nexscope-ai/Amazon-Skills` | MIT, copyright Nexscope AI | `DIRECT_REUSE_ALLOWED` | Reference only in SP-041A. Its calculation organization is relevant to later economics work, not template freezing. No attribution file is added because no code is copied. |
| `nexscope-ai/eCommerce-Skills` | MIT, copyright Nexscope AI | `DIRECT_REUSE_ALLOWED` | Reference only; competitor/review analysis is outside SP-041A. |
| `DannylydST/sorftime-data-cli` | MIT | `DIRECT_REUSE_ALLOWED` / reference | Rejected for this task. Sorftime access is forbidden and accepted SP-040 contracts remain authoritative. |
| `scikit-learn/scikit-learn` | BSD-3-Clause | `DEPENDENCY_REUSE` | Deferred to route-discovery work. Clustering is outside SP-041A and no dependency is added here. |
| `bradbase/xlcalculator` | MIT overall, with tokenizer/parsing/shunting exceptions called out in its LICENSE | `REJECTED` | Formula evaluation is out of scope; extra dependency surface and mixed component licensing are unnecessary for a deterministic formula census. |
| `PSU3D0/formualizer` | MIT OR Apache-2.0 | `REJECTED` | Capable formula engine, but evaluation/recalculation is out of scope and would add a Rust/Python dependency. |
| `knowledgestack/excel-parser` | MIT | `REJECTED` | Broad LLM/RAG parsing stack exceeds this contract-only task. The local implementation needs only existing `openpyxl` APIs. |
| `vinci1it2000/formulas` | EUPL-1.1+ | `REJECTED` | License is outside the task's permissive reuse allowlist and formula evaluation is unnecessary. |
| `tom-juntunen/target-web-fetch` | No root `LICENSE` found (GitHub contents API 404) | `REFERENCE_ONLY` | No code copied. Product clustering is also outside SP-041A. |
| `ericmc/amazon-product-research-playbook` | No root `LICENSE` found (GitHub contents API 404) | `REFERENCE_ONLY` | No code copied. |
| `Umair706/amazon-omniscient` | Proprietary, All Rights Reserved | `REFERENCE_ONLY` | Use/copy/modification expressly prohibited; no code copied. |
| `liangdabiao/claudesdk-amazon-chat` | No root `LICENSE` found (GitHub contents API 404) | `REFERENCE_ONLY` | No code copied. |

## Exact selected component

Only dependency reuse is selected: the project's existing `openpyxl>=3.1.5,<4`
installation, including `load_workbook`, workbook/sheet metadata, and
`openpyxl.formula.Tokenizer`. SP-041A supplies its own small contract-specific
canonicalization and validation around those APIs by reusing internal
`canonical_json`; it does not copy tokenizer or parser implementations.

## Obligations

- No new third-party source or binary dependency is introduced.
- No new attribution file is required because no external code is copied and
  the selected dependency already exists in project metadata.
- If future work copies a substantial MIT/BSD component, its copyright and
  permission notice must be retained at that time.

## Contract-preservation tests

- formulas are inventoried, never evaluated or rewritten;
- formula fingerprints change when formula text changes and remain stable for
  repeated reads;
- numeric literals are obtained from tokenizer operands, not confused with
  row numbers in cell references;
- missing/blank raw fields remain contract metadata and are never coerced to
  numeric zero;
- exact sheet visibility/order and 66 header names fail closed on drift;
- network socket construction is denied during audit tests.
