# SP-041A Internal Reuse Audit

Date: 2026-08-26
Baseline: `a0cf42685c75d5f611ce40c99b96d8cb731d45ba`
Branch: `codex/task-sp-041a-template-contract-freeze`

This audit was completed before SP-041A implementation. The workspace and
staging area were clean and `HEAD` equalled the required baseline exactly.

## Search scope

The repository was searched for contract serialization, canonical JSON,
deterministic identity/fingerprinting, workbook rendering, sheet visibility,
formula handling, network-denial fixtures, evidence/provenance, and metric
context implementations.

## Reuse decisions

| Internal component | Decision | SP-041A use |
|---|---|---|
| `contracts.v0_1.JsonContract` | Reuse | Strict JSON round-trip for the new immutable template contracts. |
| `contracts.v0_1.canonical_json` | Reuse | Canonical material for schema, formula, dependency, and audit fingerprints. |
| `contracts.v0_1.deterministic_id` | Reuse | Stable contract identifiers where a namespaced identifier is required. |
| `operator_workbook.models` | Pattern reuse | Follow immutable dataclasses, fail-closed validation, exact field checks, and explicit serialization errors. No V0.2 business semantics are changed. |
| `operator_workbook.builder_v0_2` / `xlsx_delivery` | Pattern reuse | Reuse existing `openpyxl` dependency and workbook safety conventions. The existing builders are not modified because they generate different products. |
| `MetricContextEnvelope`, Evidence/Provenance | Reference only for this task | SP-041A inventories a workbook contract and emits no new market metric or provider evidence. These remain authoritative for later tasks. |
| `production_pipeline.providers` fixture replay | Reference only | Confirms the established zero-network test pattern. Production Pipeline is not imported or modified. |

## Rejected internal coupling

- The V0.2 nine-sheet Operator Workbook schema cannot be extended into this
  contract: SP-041A freezes a different 11-visible/4-hidden template and must
  not weaken the existing nine-sheet ruleset.
- Xlsx Delivery V0.1 intentionally escapes formulas and emits formula-free
  workbooks, so it is not a formula-audit implementation.
- Market Report V0.1/V0.2 and Production Pipeline models are not modified or
  reused as storage for template-specific rules.

## Required tests following from reuse

- strict JSON round-trip and unknown-field rejection;
- deterministic schema/formula/dependency/threshold fingerprints;
- exact visible/hidden sheet contract and header-name validation;
- formula audit through the already-installed `openpyxl` dependency;
- a socket-construction deny test proving the audit path performs no external
  network calls;
- affected V0.2/XLSX regressions plus the full test suite.
