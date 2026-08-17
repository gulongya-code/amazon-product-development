# Evidence and Provenance Model V0.1

Status: design contract only  
Task: TASK-SP-003; revised by TASK-SP-003D

Revision marker: `DESIGN_SCHEMA_REVISION — TRANSFORMATION_PROVENANCE_V0.1`

## 1. Evidence lifecycle

The model separates claims from conclusions:

```text
RawEvidenceRecord
  -> collection execution
  -> provider mapping / normalization transformation
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
| `collection_run_id` | yes | One concrete collection execution; a batch may share it, but unrelated provider calls must not share it accidentally. |
| `provider` | yes | Source system name. |
| `source_tool` | yes | Tool/operation identifier. |
| `provider_schema_version` | yes | Explicit version-status object. Unknown is serialized, never guessed. |
| `sanitized_request` | yes | Request parameters with credentials and tokens removed or masked. |
| `retrieved_at` | yes | Capture timestamp. |
| `response_status` | yes | `SUCCESS`, `EMPTY`, `PARTIAL`, or `FAILED`. |
| `media_type` | yes | Usually `application/json`. |
| `content_reference` | yes | Immutable URI/path/object reference. |
| `content_fingerprint` | yes | Algorithm-versioned content fingerprint; implementation deferred. |
| `pagination` | no | Cursor/page/limit/completeness metadata. |
| `error` | no | Sanitized error type and message. |

Raw responses are retained without silent edits. A separate sanitized diagnostic representation may be generated, but must not replace the original evidence. Secrets must never enter provenance, IDs, logs, or exported examples.

`collection_run_id` is not a raw record reference. One collection run can create multiple `RawEvidenceRecord` objects, including page-level or batch-member records. A failed provider call may still have a collection run and a raw diagnostic record with `response_status = FAILED`.

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
  "transformation": {
    "collection_run_id": "collection:...:C1",
    "provider_schema_version": {"status": "UNKNOWN", "value": null, "source": "UNKNOWN"},
    "mapping_version": "provider_product_detail_mapping_v1",
    "transformation_run_id": "transform:...:T1",
    "transformation_code_version": {"status": "KNOWN", "value": "<git-commit-or-build>", "scheme": "GIT_COMMIT"},
    "raw_evidence_reference": "raw:...",
    "transformed_at": "2026-08-14T08:30:00Z",
    "transformation_status": "SUCCESS"
  }
}
```

Required source fields are `provider`, `source_tool`, `source_field`, `source_record_identity`, `retrieved_at`, and `transformation`. The nested transformation contract owns the primary `raw_evidence_reference`. The observation envelope owns canonical time and scope; provenance repeats source time/scope when useful to document what the provider actually declared.

`source_field` is a trace pointer, not a canonical dimension. `provider_documentation_reference` is required when semantics depend on embedded tool documentation, as with Sorftime `SalesAmount` being documented as variation sales volume.

### 4.1 Version-status serialization

Provider schema version is required as an object, not necessarily as a known value:

```json
{"status":"KNOWN","value":"2026-07-tool-contract","source":"MCP_TOOL_OR_SERVER"}
```

or:

```json
{"status":"UNKNOWN","value":null,"source":"UNKNOWN"}
```

Allowed known sources are `PROVIDER_DECLARED`, `MCP_TOOL_OR_SERVER`, `SCHEMA_FINGERPRINT`, and `LOCAL_CONTRACT`. A local fingerprint may be used only when its algorithm/version is recorded by implementation; it must not be mislabeled as provider-declared.

Transformation code version uses:

```json
{"status":"KNOWN","value":"<revision>","scheme":"GIT_COMMIT"}
```

with schemes `GIT_COMMIT`, `BUILD_VERSION`, `PACKAGE_VERSION`, `RULESET_VERSION`, or `OTHER`. When genuinely unavailable, serialize `{"status":"UNKNOWN","value":null,"scheme":"UNKNOWN"}`. Unknown is legitimate; omission or fabricated versions are not.

### 4.2 TransformationProvenance

| Field | Required | Meaning and policy |
|---|---:|---|
| `collection_run_id` | yes | Collection execution that produced the primary raw input. |
| `provider_schema_version` | yes | Explicit known/unknown provider contract version. |
| `mapping_version` | yes | Versioned provider Raw → Canonical mapping rule. Mandatory and never `UNKNOWN` for formal adapter output. |
| `transformation_run_id` | yes | Concrete mapping/normalization execution. |
| `transformation_code_version` | yes | Exact code/rules revision when known; explicit unknown otherwise. |
| `raw_evidence_reference` | yes | Immutable primary raw record. Never replaced by collection ID. |
| `transformed_at` | yes | Transformation output timestamp; not source observation time. |
| `transformation_status` | yes | `SUCCESS` or `PARTIAL` when an observation exists. |

No separate `adapter_version` or `normalization_version` is added in V0.1. A semantic change in either must change `mapping_version`; executable packaging/revision belongs in `transformation_code_version`. `input_observation_ids` is excluded from source observations because their single primary input is raw evidence.

### 4.3 TransformationRunRecord and failures

The bundle-level `TransformationRunRecord` represents one mapping execution independently of its outputs. Required fields are:

- provider;
- `collection_run_id`;
- `provider_schema_version`;
- `mapping_version`;
- `transformation_run_id`;
- `transformation_code_version`;
- `started_at` and nullable `completed_at`;
- `status`: `SUCCESS`, `PARTIAL`, or `FAILED`;
- `input_raw_evidence_references`;
- `output_observation_ids` (may be empty only when no output was produced, normally `FAILED`);
- `quality_issue_ids`.

This is not a workflow state machine. It is the minimum audit record needed to show that a transformation failed, partially succeeded, or emitted no observation. Sanitized operational error detail remains in raw diagnostics/quality issues rather than in canonical business values.

### 4.4 Collection versus transformation

```text
Raw R1 / collection C1
  mapping V1 / transformation T1 -> Observation revision O1

Raw R1 / collection C1
  mapping V2 / transformation T2 -> Observation revision O1 or O2
```

Collection is reused because the immutable raw input is reused. Transformation is new because the mapping execution is new. A transformation run consumes raw evidence from one collection execution under one mapping version; combining observations from multiple collections belongs to resolution or a later derived process.

## 5. Observation and resolution lineage

An observation carries exactly one primary `raw_evidence_reference` inside `provenance.transformation`. It also carries a stable `semantic_observation_id` and an exact canonical content-revision `observation_id`. If one canonical observation needs multiple raw records, it is already a resolution or derived result and must not masquerade as a source observation.

`semantic_observation_id` excludes collection and transformation metadata. `observation_id` adds a deterministic fingerprint of canonical semantic content. `TransformationRunRecord` retains each execution independently:

- Same raw, new mapping, same semantic content: semantic and content-revision IDs remain stable; both transformation runs point to that revision.
- Same raw, mapping bug fixed, changed canonical unit/value/scope: semantic ID remains stable, content-revision ID changes; old and new revisions remain auditable.
- Random UUID/ULID is suitable for `collection_run_id` and `transformation_run_id`, not as the sole semantic observation ID.

An observation revision ID is not an emission primary key. The pair (`transformation_run_id`, `observation_id`) identifies a materialized emission. Reprocessing may therefore emit two envelopes with the same revision ID and different embedded transformation provenance, or may deduplicate the revision object while preserving both run records. Either representation must remain append-only and must never overwrite T1 lineage with T2 lineage.

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

Resolution lineage references exact observation content revisions. It does not select a transformation run as the business truth. When audit requires execution history, each candidate revision can be traced through the transformation run records to mapping/code versions and immutable raw evidence.

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

- Every observation resolves through `provenance.transformation` to an existing raw evidence record and matching collection run.
- Every formal adapter observation has a non-unknown `mapping_version`.
- Provider schema/code versions are explicit known/unknown objects; unknown values are never fabricated.
- Every observation-producing `transformation_run_id` resolves to a run record whose output list contains that exact observation revision ID.
- A failed transformation can be audited with an empty output list and does not create a fake missing/zero observation.
- Every resolution resolves to all candidate observations and then to raw evidence.
- Provider documentation used to establish semantics is referenced.
- Sanitized requests retain enough parameters to reproduce scope without secrets.
- Raw evidence is immutable; corrections create new evidence and observations.
- Observation and retrieval times remain distinct.
- A resolution never deletes or rewrites a candidate.
- Provider-specific fields appear only in provenance/mapping, not downstream contracts.

## 11. Required design cases

### Case A — collection plus transformation

`R1/C1 + V1/T1 -> O1` is valid when `O1` contains the primary raw reference, mandatory mapping version, execution IDs, version-status objects, and transform timestamp/status.

### Case B — reprocessing the same raw evidence

`R1/C1 + V2/T2` is a new transformation, not a new collection. If canonical semantic content is identical, the semantic and content-revision observation IDs remain stable while `T1` and `T2` both remain in lineage.

### Case C — Provider schema version unknown

`provider_schema_version = {"status":"UNKNOWN","value":null,"source":"UNKNOWN"}` is valid. Mapping may proceed only when the source field semantics are otherwise safe; unknown schema version can still create a quality warning. Guessing a version is prohibited.

### Case D — mapping bug fix

When V1 misinterprets a unit and V2 corrects it, the same semantic observation gets a new content-revision ID. T1/V1 and T2/V2, their outputs, and the affected quality issue remain append-only. No provenance is silently replaced.

### Case E — pressure conflict origin

For `1000 pascal`, `1000 WOG`, and `1000 PSI`, each observation traces to its raw field/text span and transformation. A `DataQualityIssue.origin_stage` plus collection/transformation/mapping links identifies whether the inconsistency already existed in raw provider evidence or was introduced by mapping/normalization.

### Case F — single provider

A Sorftime-only chain `Raw -> Collection -> Mapping -> Canonical Observation` is complete and valid. No provenance field or transformation run requires a second provider.

## 12. Retention and security boundary

V0.1 does not set retention duration or storage technology. Implementations must support immutable references, content integrity checks, access control, and token masking. Authentication values are never data provenance and must not be serialized in any canonical contract.
