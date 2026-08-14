# Evidence and Provenance Model V0.1

Status: design contract only  
Task: TASK-SP-003

## 1. Evidence lifecycle

The model separates claims from conclusions:

```text
RawEvidenceRecord
  -> Canonical Observation (OBSERVED or PROVIDER_ESTIMATE)
  -> validation + conflict assessment
  -> ResolvedEvidence (RESOLVED or unresolved)
  -> future analytics output (DERIVED; out of scope)
```

Every transition is additive and traceable. Raw evidence and competing observations are never overwritten by a resolution.

## 2. Evidence types

| Type | Meaning | Allowed producer |
|---|---|---|
| `OBSERVED` | A provider reports a displayed, captured, or directly observed product/market value. | Provider mapping layer |
| `PROVIDER_ESTIMATE` | A provider reports an algorithmic or third-party estimate, including sales, orders, traffic, or search volume when documented as estimated. | Provider mapping layer |
| `RESOLVED` | The system produces a field-level conclusion from one or more observations under an explicit validation/resolution method. | Resolution layer |
| `DERIVED` | A rule, model, or analytic process produces new knowledge. | Future downstream systems; not produced in TASK-SP-003 |

Evidence type is based on documented semantics, not a field name. When the semantics are unknown, preserve the candidate type, set `semantic_status = SEMANTICS_UNCONFIRMED`, and attach a quality issue. Do not upgrade it to resolved truth.

## 3. RawEvidenceRecord

Raw provider responses are immutable retained evidence.

| Field | Required | Meaning |
|---|---:|---|
| `raw_evidence_id` | yes | Deterministic identifier. |
| `provider` | yes | Source system name. |
| `source_tool` | yes | Tool/operation identifier. |
| `sanitized_request` | yes | Request parameters with credentials and tokens removed or masked. |
| `retrieved_at` | yes | Capture timestamp. |
| `response_status` | yes | `SUCCESS`, `EMPTY`, `PARTIAL`, or `FAILED`. |
| `media_type` | yes | Usually `application/json`. |
| `content_reference` | yes | Immutable URI/path/object reference. |
| `content_fingerprint` | yes | Algorithm-versioned content fingerprint; implementation deferred. |
| `pagination` | no | Cursor/page/limit/completeness metadata. |
| `error` | no | Sanitized error type and message. |

Raw responses are retained without silent edits. A separate sanitized diagnostic representation may be generated, but must not replace the original evidence. Secrets must never enter provenance, IDs, logs, or exported examples.

## 4. Provenance contract

Every important observation requires this contract:

```json
{
  "provider": "sorftime",
  "source_tool": "get_product_detail",
  "source_field": "attributes.Maximum Operating Pressure",
  "source_record_identity": "US:B0G2Q22W6D",
  "provider_semantic": "Maximum Operating Pressure attribute",
  "semantic_validation_status": "CONFIRMED",
  "observed_at": null,
  "observed_at_status": "UNKNOWN",
  "retrieved_at": "2026-08-14T08:19:21.656Z",
  "period": null,
  "scope": {"scope_type": "ASIN", "scope_status": "CONFIRMED"},
  "provider_method": null,
  "provider_documentation_reference": "raw:...#doc",
  "raw_evidence_reference": "raw:..."
}
```

Required fields are `provider`, `source_tool`, `source_field`, `source_record_identity`, `retrieved_at`, and `raw_evidence_reference`. The observation envelope owns canonical time and scope; provenance repeats source time/scope when useful to document what the provider actually declared.

`source_field` is a trace pointer, not a canonical dimension. `provider_documentation_reference` is required when semantics depend on embedded tool documentation, as with Sorftime `SalesAmount` being documented as variation sales volume.

## 5. Observation and resolution lineage

An observation carries exactly one primary `raw_evidence_reference`. If one canonical observation needs multiple raw records, it is already a resolution or derived result and must not masquerade as a source observation.

A `ResolvedEvidence` record contains:

```json
{
  "resolution_id": "res:design-example:rating",
  "evidence_type": "RESOLVED",
  "subject": {"subject_type": "PRODUCT", "subject_id": "product:US:B0GTQZ9C19", "marketplace": "US"},
  "dimension": "rating",
  "candidate_observation_ids": ["obs:rating:xiyou", "obs:rating:sorftime"],
  "conflict_id": "cfl:rating:material",
  "conflict_status": "MATERIAL_DIFFERENCE",
  "resolution_status": "UNRESOLVED",
  "value": {
    "presence_status": "UNKNOWN",
    "raw_value": null,
    "normalized_value": null,
    "value_type": "NUMBER",
    "unit": {"dimension": "RATING", "unit_code": "stars_5", "unit_system": "DOMAIN"},
    "normalization_status": "NOT_ATTEMPTED",
    "semantic_status": "CONFIRMED"
  },
  "resolution_method": "COMPARABILITY_AND_THRESHOLD_ASSESSMENT",
  "resolution_policy": null,
  "quality_issue_ids": ["dqi:rating-material-difference"],
  "lineage": {
    "observation_ids": ["obs:rating:xiyou", "obs:rating:sorftime"],
    "raw_evidence_ids": ["raw:xiyou-product", "raw:sorftime-product"]
  }
}
```

The absence of a resolved value is a valid outcome. All candidate values remain accessible through their observation IDs.

## 6. Uncertainty model

Uncertainty is represented by orthogonal, explicit states rather than a single vague confidence number:

- `presence_status`: whether the source supplied a value.
- `semantic_status`: whether its meaning is confirmed.
- `scope_status`: whether measurement grain is confirmed.
- `observed_at_status`: whether observation time is known.
- `normalization_status`: whether value/unit normalization succeeded.
- `resolution_status`: whether candidates can safely yield a canonical value.
- `quality_issue_ids`: specific, reviewable reasons.

Optional confidence is only accepted with a named method, score scale, and supporting evidence. Unknown is not encoded as low confidence; it is encoded as `UNKNOWN`.

## 7. Time and provenance rules

1. `retrieved_at` records system capture time.
2. `observed_at` records the source-declared observation time.
3. If the source does not provide observation time, `observed_at = null` and `observed_at_status = UNKNOWN`.
4. Retrieval time never substitutes for observation time.
5. Metric windows use separate `period_start`, `period_end`, and `period_type`.
6. Freshness may be computed later from these fields but is not itself a source timestamp.

## 8. Empty, missing, failed, and zero evidence

| Situation | Encoding | Interpretation |
|---|---|---|
| Provider returns numeric zero | `presence_status=PRESENT`, value `0` | A reported zero. |
| Field absent in a returned record | `MISSING` | No field-level claim. |
| Provider returns explicit null | `EXPLICIT_NULL` | Explicit null claim; semantics may need documentation. |
| Successful query returns no rows | `QUERY_RETURNED_EMPTY` plus `EMPTY_OBSERVATION` | Evidence about query result only. |
| Query fails | raw `response_status=FAILED` | No market or product inference. |
| Provider cannot establish value | `UNKNOWN` | Known uncertainty. |

Thus a forward keyword query returning zero candidates cannot become `market_size = 0`.

## 9. Evidence set and single-provider behavior

An `EvidenceSet` groups observations only by canonical subject and dimension after identity checks. It records provider count, candidate IDs, comparability outcome, and coverage. One valid observation produces a valid set with `conflict_status = ONE_SOURCE_ONLY`. It may produce resolved evidence under a transparent single-source acceptance policy, or remain unresolved if the field requires corroboration. The core model does not impose `provider_count >= 2`.

## 10. Audit invariants

- Every observation resolves to an existing raw evidence record.
- Every resolution resolves to all candidate observations and then to raw evidence.
- Provider documentation used to establish semantics is referenced.
- Sanitized requests retain enough parameters to reproduce scope without secrets.
- Raw evidence is immutable; corrections create new evidence and observations.
- Observation and retrieval times remain distinct.
- A resolution never deletes or rewrites a candidate.
- Provider-specific fields appear only in provenance/mapping, not downstream contracts.

## 11. Retention and security boundary

V0.1 does not set retention duration or storage technology. Implementations must support immutable references, content integrity checks, access control, and token masking. Authentication values are never data provenance and must not be serialized in any canonical contract.
