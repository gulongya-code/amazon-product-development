# Data Conflict and Resolution Model V0.1

Status: design contract only  
Task: TASK-SP-003

## 1. Resolution principle

Resolution is field-level evidence assessment, not record overwrite. It first decides whether observations are comparable, then measures agreement, and only then decides whether a canonical value is safe. Provider priority, averaging, and latest-wins behavior are outside V0.1.

## 2. Comparability gate

Candidate observations must pass these checks in order:

1. **Identity**: same canonical subject and marketplace.
2. **Dimension**: same canonical fact or metric.
3. **Semantic**: same measured concept and population.
4. **Scope**: compatible ASIN/parent/child/keyword/category grain.
5. **Period**: compatible window type, boundaries, and timezone.
6. **Unit**: same unit or safe, documented conversion.
7. **Direction/channel**: compatible relationship direction and organic/sponsored context.

Failure does not discard evidence. It emits a conflict/quality issue and normally leaves the field unresolved.

## 3. Conflict taxonomy

| Status | Meaning | Default field action |
|---|---|---|
| `CONSISTENT` | Equivalent after deterministic normalization or within a declared non-material tolerance. | May resolve deterministically. |
| `MINOR_DIFFERENCE` | Comparable values differ slightly below a material threshold. | Preserve both; may resolve only under a versioned policy; non-blocking by default. |
| `MATERIAL_DIFFERENCE` | Comparable values differ materially. | `UNRESOLVED`; no averaging. |
| `SEMANTIC_CONFLICT` | Labels appear related but documented meaning/population differs or is unconfirmed. | `UNRESOLVED`. |
| `UNIT_CONFLICT` | Units are inconsistent, ambiguous, or non-convertible. | `UNRESOLVED`. |
| `DIRECTIONAL_CONFLICT` | Forward/reverse or channel-specific relationship evidence is asymmetric or contradictory. | Preserve directions; no market-empty inference. |
| `ONE_SOURCE_ONLY` | Exactly one valid source observation exists. | Valid evidence; resolution policy-dependent, never automatically invalid. |
| `NOT_DIRECTLY_COMPARABLE` | Observations are valid but period/scope/metric semantics do not match. | Keep as separate evidence; do not calculate a difference. |
| `UNKNOWN` | There is insufficient information to classify. | `UNRESOLVED`. |

Conflict threshold values are versioned policy inputs, not hard-coded into the core schema. The audit cases below are acceptance fixtures for V0.1.

## 4. ConflictRecord

```json
{
  "conflict_id": "cfl:design-example:rating",
  "subject": {"subject_type": "PRODUCT", "subject_id": "product:US:B0GTQZ9C19", "marketplace": "US"},
  "dimension": "rating",
  "candidate_observation_ids": ["obs:rating:4.6", "obs:rating:4.1"],
  "conflict_status": "MATERIAL_DIFFERENCE",
  "comparability": {
    "identity": "PASS",
    "dimension": "PASS",
    "semantic": "PASS",
    "scope": "PASS",
    "period": "PASS",
    "unit": "PASS",
    "direction": "NOT_APPLICABLE"
  },
  "difference": {"absolute": 0.5, "relative": 0.1087, "unit_code": "stars_5"},
  "severity": "MATERIAL",
  "blocking": true,
  "blocking_scope": "FIELD",
  "resolution_status": "UNRESOLVED",
  "explanation": "Comparable ratings differ materially; no selection or averaging policy exists."
}
```

## 5. Resolution states

- `UNRESOLVED`: no safe canonical value.
- `RESOLVED_DETERMINISTIC`: exact/normalized equivalence or other unambiguous rule.
- `RESOLVED_BY_POLICY`: an explicit, versioned policy selected a value; policy ID is mandatory.
- `NOT_REQUIRED`: observations intentionally remain separate, e.g. different metrics.
- `DEFERRED`: resolution requires external semantics, unit mapping, or identity review.
- `REJECTED_INPUT`: an observation failed validation; it remains in lineage.

A resolution includes all candidates, status, nullable resolved value, method, policy/version, conflict reference, and quality issues.

## 6. Acceptance cases from audited evidence

### 6.1 Consistent title

XiYou and Sorftime report effectively the same B0GTQZ9C19 title. After deterministic whitespace/case-safe normalization, status is `CONSISTENT`. The resolved display title may use a lossless deterministic rule only if both normalized forms are equivalent; both originals remain observations.

### 6.2 Rating 4.6 versus 4.1

Both observations are five-star ASIN ratings for B0GTQZ9C19, so they pass comparability. The result is `MATERIAL_DIFFERENCE`, `resolution_status = UNRESOLVED`, and no value `4.35` is created. Retrieval timestamps and unknown source observation timestamps remain attached to each candidate.

### 6.3 Review count 75 versus 78

Both are comparable ASIN review counts. The accepted fixture classification is `MINOR_DIFFERENCE`. Both integers remain; the issue is non-blocking at product level. A later policy may select a value, but V0.1 does not.

### 6.4 Orders versus monthly sales

XiYou's last-30-day orders and Sorftime's monthly sales volume are distinct canonical metrics with incompletely aligned windows/methods and possibly unconfirmed parent/child scope. Classification is `NOT_DIRECTLY_COMPARABLE`, not a numeric difference. Both remain valid provider estimates in separate evidence slots.

### 6.5 Pressure: pascal, WOG, and PSI

Audited B0G2Q22W6D evidence contains:

- structured attribute: `1000 pascal`;
- title text: `1000 WOG`;
- description text: `1000 PSI`.

The system creates three `ProductFactObservation` records for `maximum_operating_pressure`, preserving raw text and source fields. `Pa` and `psi` are physical pressure units, while `WOG` is a service/rating designation whose conversion semantics cannot be assumed. The conflict is `UNIT_CONFLICT` with an additional `SEMANTIC_CONFLICT` quality issue. Resolution is `UNRESOLVED`; numeric equality (`1000`) is ignored until unit semantics are confirmed. No candidate is silently selected or converted.

### 6.6 Directional keyword evidence

For B0G2Q22W6D and keyword `1/2 ball valve`, reverse evidence (`PRODUCT_TO_KEYWORD`) contains organic/sponsored rank records while the forward query (`KEYWORD_TO_PRODUCT`) returns an empty candidate set. The relationship assessment is:

```json
{
  "directional_status": "ONE_SIDED_REVERSE",
  "conflict_status": "DIRECTIONAL_CONFLICT",
  "forward_result_status": "EMPTY_OBSERVATION",
  "reverse_result_status": "POPULATED",
  "market_empty": null
}
```

The asymmetry may arise from query coverage, ranking cutoffs, freshness, or semantics. It does not prove an empty market.

### 6.7 Single-provider product attribute

A structured attribute reported only by Sorftime is classified `ONE_SOURCE_ONLY`. It remains a valid observation and can flow downstream as unresolved or policy-accepted evidence. Lack of a second source is a coverage fact, not invalidity.

## 7. Directional consistency model

Relationship sets are assessed with:

- `CONSISTENT`: compatible forward and reverse evidence exists.
- `ONE_SIDED_FORWARD`: only `KEYWORD_TO_PRODUCT` is populated.
- `ONE_SIDED_REVERSE`: only `PRODUCT_TO_KEYWORD` is populated.
- `CONFLICT`: both exist but contradict on a comparable rank/membership claim.
- `UNKNOWN`: one or both directions failed or cannot be semantically assessed.

These directional statuses coexist with the top-level `DIRECTIONAL_CONFLICT` taxonomy when asymmetry needs quality handling. Forward and reverse observations are never merged into one source-less edge.

## 8. Missing versus zero rules

1. A literal provider value `0` is a present value.
2. An absent field is `MISSING`.
3. An explicit null is `EXPLICIT_NULL`.
4. A successful no-row query is `QUERY_RETURNED_EMPTY` / `EMPTY_OBSERVATION`.
5. A failed query is not empty evidence.
6. None of missing, null, empty, or failed states may be coerced to zero.

## 9. Fail-closed and do-not-over-block boundary

Fail closed at the affected field for identity conflicts, critical specification conflicts, unknown parent/child scope, incompatible semantics, and ambiguous/non-convertible units. A field-level unresolved state prevents unsafe canonical values while retaining other usable fields.

Escalate beyond field level only when the subject identity itself is unsafe or a downstream contract declares that field mandatory. Minor review-count differences, missing helpful votes, or one-source-only attributes do not block the product bundle.

## 10. Deterministic versus policy resolution

Allowed deterministic examples:

- identical normalized scalar and identical unit/semantics;
- exact unit conversion using an approved unit registry and matching semantics;
- lossless string normalization that preserves display candidates.

Not allowed without a later versioned policy:

- provider always wins;
- newest retrieval wins;
- mean/median of provider estimates;
- selecting the largest or smallest value;
- treating a more detailed source as automatically correct.

## 11. Open policy inputs

Implementation must later define versioned tolerances per metric, approved unit registry, corroboration requirements for critical fields, freshness policy, provider-semantic registry, and human-review workflow. Their absence does not prevent observation ingestion; it limits resolution to deterministic cases.
