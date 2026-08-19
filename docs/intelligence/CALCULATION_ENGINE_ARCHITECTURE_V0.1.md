# Calculation Engine Architecture V0.1

Status: TASK-SP-018D1 foundation

Engine version: `calculation-engine-foundation-v0.1`

Input boundary: resolved, normalized Canonical values

Provider boundary: provider-neutral

## 1. Purpose and boundary

The Calculation Engine is a deterministic execution boundary for explicitly approved formulas. A field name is never treated as a formula. The engine does not own existing Product, Demand, Competition, Opportunity, Scoring, Recommendation, Operator Output, Export, or Workbook presentation rules.

The engine:

- registers immutable calculated-field specifications and optional evaluator functions;
- validates calculated-to-calculated dependencies;
- produces a deterministic topological execution plan;
- executes only the requested dependency closure;
- blocks unsafe Canonical inputs without selecting a provider;
- isolates a failed field and blocks only its calculated descendants;
- emits versioned results with complete input lineage and fingerprints.

The engine does not:

- infer a formula from a display name;
- resolve competing provider candidates;
- convert currencies or guess units;
- call XiYou, Sorftime, SellerSprite, another API, an LLM, or a clock;
- implement the 99 Workbook projections in bulk;
- replace existing scoring or recommendation frameworks.

## 2. Components

| Component | Responsibility |
|---|---|
| `CalculatedFieldSpec` | Immutable field contract: owner, tier, dependencies, formula status, type/unit, missing and invalid policies, version, provenance, confidence, and implementation status. |
| `CalculatedFieldRegistry` | Specification/evaluator registration, duplicate detection, lookup, unknown-dependency validation, cycle detection, and topological order. |
| `CalculationPlan` | Requested fields, full calculated dependency closure, deterministic execution order, external inputs, and structurally blocked fields/reasons. |
| `CalculationInput` | One already-resolved Canonical value with presence, normalization, semantic, resolution, unit, evidence, Provenance, and quality state. |
| `CalculationEngine` | Input validation, policy propagation, partial execution, evaluator isolation, and result assembly. |
| `CalculationResult` | Value or explicit non-success status, input fields, issues, rule/version, and calculated provenance. |
| `CalculationProvenance` | Run/configuration versions, normalized input lineage, calculated dependency result IDs, and stable input/output fingerprints. |
| `functions.py` | Formula-neutral Decimal, ratio, unit, and currency safety helpers. It contains no Workbook business formula. |
| `audit_v0_1.py` | Machine-readable 99/99 Workbook V0.2 calculated-field audit and D2-ready specification set. |

## 3. Dependency graph

Dependencies are explicit typed edges:

```text
CANONICAL_INPUT / SYSTEM_RECORD / METADATA / MANUAL / AI_LAYER
                              ↓
                     Calculated Field A
                              ↓ CALCULATED_FIELD
                     Calculated Field B
```

Registry validation performs a deterministic depth-first topological traversal. Unknown calculated dependencies raise `UnknownCalculationDependencyError`. A back edge raises `CalculationDependencyCycleError` with the discovered cycle path. External dependencies do not need to be registered as calculated fields.

The audited graph contains one deliberate calculated-to-calculated example:

```text
workbook.product_structure.product_count ─┐
                                             ├→ workbook.product_structure.observed_share
workbook.market_overview.observed_product_count ─┘
```

`Observed Share` is defined as an observed-set ratio, never market share. Its evaluator is intentionally deferred to D2.

## 4. Planning and partial execution

`plan(requested_fields)` expands only calculated dependencies required by the request. It reports:

- requested fields;
- deterministic execution order;
- external dependency IDs;
- formula-status, evaluator, and calculated-dependency blockers.

`calculate(requested_fields, inputs, context)` executes that same closure. An unrelated registered field is not executed. A failed dependency blocks descendants with `DEPENDENCY_BLOCKED`; independent requested fields continue.

The D1 audited registry contains specifications only. It registers no production evaluator, so even the 12 D2-ready fields report `EVALUATOR_NOT_REGISTERED`. Tests use fake formulas to prove extensibility without placing invented rules in production code.

## 5. Canonical input gate

The engine accepts only `CalculationInput`, which keeps upstream semantics explicit. A usable present input must be:

- `PresenceStatus.PRESENT`;
- `NormalizationStatus.NORMALIZED` (or the explicit not-applicable state before presence propagation);
- `SemanticStatus.CONFIRMED`;
- resolved or explicitly not requiring cross-source resolution;
- free of blocking Canonical `DataQualityIssue` records;
- backed by at least one evidence reference and existing Canonical `Provenance` record.

Raw provider candidates are outside this boundary. An unresolved input is `DEPENDENCY_BLOCKED`; the engine never chooses XiYou, Sorftime, or any other provider.

## 6. Missing, unknown, null, zero, and empty

| Input state | Default safe result |
|---|---|
| dependency absent | `MISSING_INPUT` |
| `MISSING` | `MISSING_INPUT` |
| `EXPLICIT_NULL` | `MISSING_INPUT`, with the original state retained on the input |
| `QUERY_RETURNED_EMPTY` | `MISSING_INPUT`, unless the upstream contract explicitly supplies a present empty collection |
| `UNKNOWN` | `UNKNOWN_INPUT` |
| `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| unresolved candidate | `DEPENDENCY_BLOCKED` |
| invalid/ambiguous/unconfirmed/blocking quality | `INVALID_INPUT` |
| present `0` | valid data |
| present `False` | valid data |
| present empty collection | valid data |

Each specification declares a `MissingPolicy`; there is no global coercion. `REQUIRE_ALL` blocks on any unusable dependency. `ALLOW_PARTIAL` and `IGNORE_MISSING` may execute when at least one declared value remains, and the result is marked `PARTIAL`. Other policy values remain explicit specification vocabulary and default to safe propagation until an approved formula defines their behavior. No missing, unknown, or invalid value silently becomes zero.

## 7. Numeric, unit, and currency safety

- Decimal helpers preserve `Decimal` and convert explicit finite integers, floats, or numeric strings without using binary-float arithmetic internally.
- A zero denominator becomes `DIVISION_BY_ZERO`; it never crashes, produces infinity/NaN, or returns zero.
- Mixed units become `UNIT_MISMATCH`.
- Monetary inputs require explicit ISO currency units. Missing or mixed currencies become `CURRENCY_MISMATCH`.
- No FX lookup or implicit conversion exists.

These helpers are formula-neutral. D1 has zero production formula implementations.

## 8. Failure and error model

| Boundary | Error/result |
|---|---|
| unknown requested field | `UnknownCalculatedFieldError` |
| duplicate registration | `DuplicateCalculatedFieldError` |
| unknown calculated dependency | `UnknownCalculationDependencyError` |
| dependency cycle | `CalculationDependencyCycleError` |
| unsafe business input | typed `CalculationStatus` result |
| undefined formula/evaluator | `FORMULA_UNDEFINED` result |
| zero denominator | `DIVISION_BY_ZERO` result |
| unit/currency mismatch | `UNIT_MISMATCH` / `CURRENCY_MISMATCH` result |
| evaluator contract/domain failure | `FAILED` result with sanitized issue |

Unexpected evaluator exceptions are isolated at the extension boundary. Their type may be recorded, but raw exception text is not exposed because it could contain source data.

## 9. Provenance and multi-source lineage

A successful result is system-derived and traces:

```text
CalculationResult
  → calculation_rule_id + calculation_version
  → explicit input fields and calculated dependency result IDs
  → normalized input values + unit + presence/normalization/semantic/resolution state
  → Canonical evidence references + quality issue IDs
  → every original Canonical Provenance record
  → provider/source/transformation/raw evidence reference
```

Provider identity appears only inside retained Canonical provenance. A multi-source result preserves all source provenances; it is not labeled as belonging to one provider. This extends the existing lineage with a calculation step and does not create a second source-provenance model.

## 10. Versioning, determinism, and idempotency

Every executable specification requires stable `calculation_rule_id` and `calculation_version`. The explicit `CalculationContext` supplies a calculation run ID and configuration version. Business weights or thresholds are not hard-coded; a future composite rule must reference an accepted versioned configuration.

Result identity and fingerprints are derived only from canonical serialized content:

- specification field/rule/version;
- normalized inputs and all lineage;
- calculated dependency results;
- explicit configuration version;
- output value, unit, status, and issues.

There is no current time, random ID, mutable global state, unversioned external API, or AI dependency. Equal content and context therefore produce equal serialized results.

## 11. Extension rule

Adding a calculation requires:

1. an accepted `CalculatedFieldSpec` with a documented formula source;
2. fully declared dependencies, type, unit, missing/invalid/partial policy, rule ID, and version;
3. an evaluator returning `CalculationOutcome` rather than a raw value;
4. registry registration and focused tests;
5. independent acceptance before default production registration.

No Calculation Engine core change is required. Formula confidence must be `CONFIRMED` or `DOCUMENTED`; inferred or unspecified formulas remain non-executable.

## 12. D1 scope result

| Item | Result |
|---|---:|
| Workbook CALCULATED fields audited | 99 |
| Machine-readable specifications | 99 |
| Formula-defined D2 candidates | 12 |
| Formula unspecified | 1 |
| Classification review required | 86 |
| Production evaluators implemented | 0 |
| Audited graph unknown calculated dependencies | 0 |
| Audited graph cycles | 0 |

The detailed audit and candidate order are in [Calculated Field Specification V0.1](CALCULATED_FIELD_SPECIFICATION_V0.1.md).
