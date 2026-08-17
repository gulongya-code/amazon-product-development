# Canonical Data Model V0.1

Status: design contract only  
Task: TASK-SP-003; revised by TASK-SP-003D
Serialization: JSON-compatible, provider-independent, snake_case

Revision marker: `DESIGN_SCHEMA_REVISION — TRANSFORMATION_PROVENANCE_V0.1`

## 1. Purpose and boundaries

This model is the stable boundary between provider adapters and downstream intelligence. It records what a source reported; it does not turn every report into truth. Downstream code must not consume provider JSON or provider field names directly.

The four layers are:

1. **Raw provider evidence**: immutable retained responses.
2. **Canonical observation**: source claims mapped into stable contracts.
3. **Validation and resolution**: comparability, quality, conflict, and resolution decisions.
4. **Resolved evidence**: field-level downstream input that retains candidates, provenance, conflicts, uncertainty, and gaps.

V0.1 defines contracts only. It does not implement adapters, Product Intelligence, Demand Intelligence, relevance, market reconstruction, or scoring.

## 2. Shared conventions

### 2.1 Identity

`ProductIdentity` is uniquely keyed by `marketplace + asin`.

| Field | Required | Semantics |
|---|---:|---|
| `product_id` | yes | Deterministic canonical identifier derived from normalized marketplace and ASIN. |
| `marketplace` | yes | Stable marketplace code, e.g. `US`. |
| `asin` | yes | Uppercase Amazon ASIN. |
| `parent_asin` | no | Nullable relationship fact, not part of product identity. |
| `identity_status` | yes | `CONFIRMED`, `PARTIAL`, `CONFLICTED`, or `UNKNOWN`. |

Brand, category, SKU, and parent ASIN are not primary identity components: they can change, vary by source, or describe relationships. Provider-specific IDs never define canonical identity.

`KeywordIdentity` is keyed by `marketplace + locale + normalized_text`. It retains `raw_text` separately so normalization is auditable.

### 2.2 Subject reference

Every observation contains:

```json
{
  "subject": {
    "subject_type": "PRODUCT",
    "subject_id": "product:US:B0GTQZ9C19",
    "marketplace": "US"
  }
}
```

`subject_type` supports `PRODUCT`, `KEYWORD`, `CATEGORY`, `BRAND`, `MARKETPLACE`, and `PRODUCT_KEYWORD_RELATIONSHIP`.

### 2.3 Presence and result states

Absence is never encoded as numeric zero or an empty string.

`presence_status`:

- `PRESENT`: a value was explicitly returned; `0` is valid when returned.
- `EXPLICIT_NULL`: the provider explicitly returned null.
- `MISSING`: the field was absent from the source record.
- `UNKNOWN`: the source cannot establish the value.
- `QUERY_RETURNED_EMPTY`: a valid query returned no records.
- `NOT_APPLICABLE`: the dimension does not apply.

`result_status` applies to a query or observation set: `POPULATED`, `EMPTY_OBSERVATION`, `PARTIAL`, `FAILED`, or `UNKNOWN`.

### 2.4 Semantic status

`semantic_status` is `CONFIRMED`, `SEMANTICS_UNCONFIRMED`, `UNPARSED`, or `INVALID`. A provider field name is never sufficient proof of meaning. Mapping must store the documented provider semantic and its validation status.

### 2.5 Scope

```json
{
  "scope": {
    "scope_type": "ASIN",
    "scope_status": "CONFIRMED",
    "scope_subject_id": "product:US:B0GTQZ9C19"
  }
}
```

`scope_type` supports `ASIN`, `PARENT_ASIN`, `CHILD_ASIN`, `KEYWORD`, `CATEGORY`, `BRAND`, and `MARKETPLACE`. `scope_status` is `CONFIRMED` or `SCOPE_UNCONFIRMED`. Unknown parent/child grain must remain unconfirmed.

### 2.6 Time and freshness

```json
{
  "time": {
    "observed_at": null,
    "observed_at_status": "UNKNOWN",
    "retrieved_at": "2026-08-14T07:44:59.345Z",
    "period_start": null,
    "period_end": null,
    "period_type": "ROLLING_30_DAYS",
    "timezone": null
  }
}
```

`retrieved_at` is required for ingestion. It must never be copied into an unknown `observed_at`. Period types include `INSTANT`, `ROLLING_15_DAYS`, `ROLLING_30_DAYS`, `CALENDAR_DAY`, `CALENDAR_WEEK`, `CALENDAR_MONTH`, `CUSTOM`, and `UNKNOWN`.

### 2.7 Value and unit envelope

Every fact or metric uses a value envelope:

```json
{
  "value": {
    "presence_status": "PRESENT",
    "raw_value": "1000 pascal",
    "normalized_value": 1000,
    "value_type": "NUMBER",
    "unit": {
      "dimension": "PRESSURE",
      "unit_code": "Pa",
      "unit_system": "SI"
    },
    "normalization_status": "NORMALIZED",
    "semantic_status": "CONFIRMED"
  }
}
```

`value_type` supports `STRING`, `NUMBER`, `INTEGER`, `BOOLEAN`, `DATE`, `DATETIME`, `OBJECT`, and `LIST`. `normalization_status` is `NOT_ATTEMPTED`, `NORMALIZED`, `FAILED`, `AMBIGUOUS`, or `NOT_APPLICABLE`. A unit is structured data, not display text. Unknown or non-convertible units retain raw values.

### 2.8 Collection and transformation provenance

Source provenance and transformation provenance are related but distinct:

```text
RawEvidenceRecord R1
  └─ collection_run_id C1
       └─ mapping_version V1
            └─ transformation_run_id T1
                 └─ Canonical Observation revision O1
```

- `collection_run_id` identifies one concrete provider collection execution. A batch may share it, but unrelated provider calls must not accidentally share it. It is execution identity, not product/keyword/business-subject identity.
- `raw_evidence_reference` identifies one immutable raw record or payload. It is not interchangeable with `collection_run_id`; one collection run may produce many raw evidence records.
- `mapping_version` identifies the versioned Raw Provider Evidence → Canonical mapping contract. It is mandatory for every formal adapter output and cannot be `UNKNOWN`.
- `transformation_run_id` identifies one concrete execution of mapping/normalization. It is distinct from collection and may be a UUID/ULID or another execution ID.
- `provider_schema_version` records the Provider payload/tool contract version. It is always serialized as a version-status object. If no honest version or fingerprint exists, serialize `{"status":"UNKNOWN","value":null,"source":"UNKNOWN"}`; never invent `"1"`.
- `transformation_code_version` records the exact Git commit, build, package, ruleset, or other deterministic code revision when known. It uses the same explicit known/unknown principle and does not require a release system to exist now.
- `transformed_at` is the system timestamp at which the output was produced. It does not replace source `observed_at` or collection `retrieved_at`.
- `transformation_status` on an emitted observation is `SUCCESS` or `PARTIAL`. A `FAILED` execution emits no Canonical Observation and is represented by a `TransformationRunRecord` with an empty `output_observation_ids` array and linked quality issues/error diagnostics.

The embedded `TransformationProvenance` contract is:

| Field | Required | UNKNOWN / serialization rule |
|---|---:|---|
| `collection_run_id` | yes | Non-empty execution ID; not a business ID. |
| `provider_schema_version` | yes | Version-status object; explicit `UNKNOWN` object is valid. |
| `mapping_version` | yes | Non-empty versioned mapping contract ID; `UNKNOWN` is invalid for formal adapter output. |
| `transformation_run_id` | yes | Non-empty execution ID. |
| `transformation_code_version` | yes | Version-status object; explicit `UNKNOWN` is valid during early/local execution. |
| `raw_evidence_reference` | yes | Immutable raw record reference; exactly one primary raw input for a source observation. |
| `transformed_at` | yes | RFC 3339 date-time. |
| `transformation_status` | yes | `SUCCESS` or `PARTIAL` for an emitted observation. |

`adapter_version` and `normalization_version` are not separate V0.1 fields: if they independently affect output semantics, they must be incorporated into the mandatory `mapping_version` or captured by `transformation_code_version`. `input_observation_ids` does not apply to Raw → Canonical source observations; multi-observation inputs belong to resolution/derived lineage.

The run-level record exists so failed and partially successful transformations remain auditable even when no observation was produced. It records provider, collection and transformation IDs, provider schema/code/mapping versions, start/completion timestamps, input raw references, output observation revision IDs, status, and quality issue IDs. A run processes raw evidence from one collection execution under one mapping version; cross-collection evidence combination belongs to resolution or derived processing.

OpenLineage run/input/output and versioning concepts were used only as a conceptual cross-check. The canonical contract remains project-owned, does not wrap OpenLineage, and has no OpenLineage dependency.

## 3. Common observation envelope

All observation types contain:

| Field | Required | Semantics |
|---|---:|---|
| `semantic_observation_id` | yes | Deterministic identity of the source-reported real-world observation, stable across reprocessing. |
| `observation_id` | yes | Deterministic canonical content-revision ID derived from `semantic_observation_id` plus canonical semantic content. |
| `schema_version` | yes | `0.1`. |
| `observation_kind` | yes | Contract discriminator. |
| `subject` | yes | Canonical subject reference. |
| `evidence_type` | yes | `OBSERVED` or `PROVIDER_ESTIMATE` at this layer. |
| `value` | yes | Presence/value/unit/semantic envelope. |
| `scope` | yes | Explicit measurement grain. |
| `time` | yes | Observation, retrieval, and period fields. |
| `provenance` | yes | Source metadata plus required `TransformationProvenance`, tracing collection, mapping, transformation, and immutable raw evidence. |
| `quality_issue_ids` | yes | Array; empty when none. |
| `result_status` | yes | Query/record outcome. |

Confidence is optional and cannot replace provenance or semantic status. If present it contains `score`, `method`, and `status`; an unexplained score is invalid.

## 4. Canonical observation types

### 4.1 ProductFactObservation

Used for title, brand, category, material, size, interface, color, style, quantity, description, technical specifications, and parent relationship.

Additional fields:

- `dimension`: stable canonical dimension such as `title`, `material`, `maximum_operating_pressure`.
- `fact_group`: `IDENTITY_RELATED`, `ATTRIBUTE`, `TECHNICAL`, `DESCRIPTION`, `VARIATION`, or `OTHER`.
- `provider_semantic`: provider documentation or observed meaning, never inferred only from the source field name.

Conflicting values coexist as distinct observations.

### 4.2 MetricObservation

Used for `price`, `rating`, `review_count`, `orders`, `estimated_monthly_sales`, `revenue`, `bsr`, and `traffic`.

Additional fields:

- `metric`: stable canonical metric name.
- `measurement_type`: `OBSERVED` or `PROVIDER_ESTIMATE`; it must agree with `evidence_type`.
- `metric_semantic`: documented meaning, population, and exclusions.
- `currency`: ISO code when the unit dimension is currency.
- `rank_context`: optional category ID/name and rank type for BSR or other ranks.

`orders` and `estimated_monthly_sales` are separate metrics. Period and scope are mandatory for meaningful comparison, even when their status is unknown.

### 4.3 KeywordMetricObservation

Used for `search_volume`, `aba_search_frequency_rank`, `competition_difficulty`, `cpc`, `suggested_bid`, and `trend`.

Additional fields:

- `keyword`: `KeywordIdentity`.
- `metric` and `metric_semantic`.
- `estimate_method_status`: `DOCUMENTED`, `PARTIALLY_DOCUMENTED`, or `UNKNOWN`.
- `range`: optional lower/upper value for CPC or bid ranges.

### 4.4 ProductKeywordRelationshipObservation

Direction is mandatory and never normalized away.

| Field | Required | Semantics |
|---|---:|---|
| `relationship_id` | yes | Deterministic relationship-observation ID. |
| `product` | yes | Product identity. |
| `keyword` | yes | Keyword identity. |
| `direction` | yes | `KEYWORD_TO_PRODUCT` or `PRODUCT_TO_KEYWORD`. |
| `relationship_type` | yes | `CANDIDATE_MEMBERSHIP`, `RANK`, `TRAFFIC`, `CLICK_SHARE`, or `OTHER`. |
| `channel` | yes | `ORGANIC`, `SPONSORED`, `MIXED`, or `UNKNOWN`. |
| `rank` | no | Rank value plus page/page-rank/total-rank context. |
| `traffic` | no | Metric value envelope. |
| `query_result_status` | yes | Includes `EMPTY_OBSERVATION`. |

An empty forward query is evidence about that query, not proof that market size is zero and not permission to delete reverse evidence.

### 4.5 ReviewObservation

Fields include `review_observation_id`, product identity, provider review identity, rating, title, body, review date, variant, and helpful votes. Each optional value uses the presence envelope. For example, unavailable helpful votes are `UNKNOWN` or `MISSING`, never `0`.

## 5. Validation entities

### 5.1 DataQualityIssue

```json
{
  "issue_id": "dqi:...",
  "issue_code": "UNIT_SEMANTIC_CONFLICT",
  "severity": "MATERIAL",
  "subject": {"subject_type": "PRODUCT", "subject_id": "product:US:B0G2Q22W6D", "marketplace": "US"},
  "dimension": "maximum_operating_pressure",
  "message": "Values use pascal, WOG, and PSI semantics and cannot be safely merged.",
  "blocking": true,
  "blocking_scope": "FIELD",
  "source_references": ["obs:pressure:attribute", "obs:pressure:title", "obs:pressure:description"],
  "created_at": "2026-08-14T00:00:00Z"
}
```

Severity is `INFO`, `WARNING`, `MATERIAL`, or `BLOCKING`. `blocking_scope` is `NONE`, `FIELD`, `SUBJECT`, or `BUNDLE`; V0.1 defaults to field-level blocking so unrelated evidence remains usable.

### 5.2 ConflictRecord and ResolvedEvidence

`ConflictRecord` classifies comparable or non-comparable candidate observations. `ResolvedEvidence` is a field-level result containing:

- `resolution_id`, subject, dimension/metric, and `evidence_type: RESOLVED`;
- all `candidate_observation_ids`;
- `conflict_id` and `conflict_status` when applicable;
- `resolution_status`;
- a nullable resolved `value`;
- `resolution_method` and optional policy/version;
- quality issues, uncertainty, and provenance chain.

Unresolved evidence has `value.presence_status = UNKNOWN`; it does not invent a value.

## 6. Downstream input contracts

### 6.1 ResolvedProductEvidence

Provider-independent bundle containing:

- `identity`;
- field-level `facts` and `attributes`;
- `technical_evidence`, `description_evidence`, and `variation_evidence`;
- `metric_evidence`;
- `conflicts`, `unresolved_gaps`, `quality_issues`;
- observation and raw provenance references.

One unresolved technical field does not invalidate the whole product.

### 6.2 CanonicalKeywordEvidence

Provider-independent bundle containing keyword identity, marketplace, search-volume evidence, competition evidence, trend evidence, product relationship references, provider metadata through provenance, conflicts, and quality issues. It contains evidence only; it does not parse intent or build demand profiles.

## 7. Deterministic identity design

IDs are reproducible from canonical inputs; V0.1 intentionally does not select or implement a hash algorithm. Random UUID/ULID values are acceptable for execution IDs, but not as the sole material for semantic observation identity.

### 7.1 Semantic observation identity

`semantic_observation_id` answers: “which source-reported real-world observation is this?” Ordered material includes:

1. normalized `provider` and `source_tool`;
2. canonical subject identity and marketplace;
3. observation kind and stable metric/dimension;
4. relationship direction/channel/type when applicable;
5. stable `source_record_identity` and source position/discriminator when one record contains repeated values;
6. source-declared `observed_at` and period identity when known; otherwise an explicit `UNKNOWN` token rather than `retrieved_at`.

It excludes collection and transformation execution/version metadata. A corrected mapping of the same source record therefore continues to describe the same semantic observation.

### 7.2 Canonical content revision identity

`observation_id` identifies the exact canonical semantic-content revision. It is derived from:

- `semantic_observation_id`;
- presence state and normalized semantic value;
- unit and normalization/semantic status;
- evidence/measurement type;
- canonical scope and source-declared observation/period semantics;
- other observation-kind-specific canonical fields that change downstream meaning.

Raw display formatting, collection timestamps, retrieval timestamps, mapping/code versions, and run IDs are excluded. Consequently:

- V1 and V2 mappings that produce identical canonical semantic content produce the same `semantic_observation_id` and `observation_id`;
- a mapping fix that changes a wrongly interpreted unit/value/scope keeps the same `semantic_observation_id` but produces a new `observation_id` revision;
- each execution is still independently recorded by `transformation_run_id`, whose run record points to the emitted `observation_id`.

`observation_id` is a semantic-content revision identity, not a transformation-emission key. When two runs reproduce the same revision, the materialized emission identity is the pair (`transformation_run_id`, `observation_id`): both envelopes may coexist with distinct embedded transformation provenance, and both run records point to the same revision ID. An implementation that deduplicates the revision object must retain every `TransformationRunRecord`; it must not replace T1 provenance with T2 provenance.

Conflict and resolution candidate references target exact `observation_id` revisions. Old observation revisions and old transformation runs remain append-only and auditable; a new revision never silently overwrites them.

### 7.3 Field inclusion decision

| Candidate field | Semantic identity | Content revision identity | Transformation identity / lineage | Reason |
|---|---:|---:|---:|---|
| `provider` | yes | inherited | recorded | Distinguishes source claims without creating provider-specific business fields. |
| subject identity | yes | inherited | referenced | Identifies the observed business subject. |
| metric/dimension/kind | yes | inherited | referenced | Identifies the observed concept. |
| source record identity | yes | inherited | recorded | Distinguishes provider records. |
| source-declared `observed_at`/period | yes when known; explicit unknown token otherwise | inherited | recorded | Separates real observation events/windows without substituting retrieval time. |
| `collection_run_id` | no | no | yes | Collection execution is not the real-world observation. |
| `provider_schema_version` | no | no | yes | Version explains interpretation, not observed reality. |
| `mapping_version` | no | no | yes | Reprocessing must not automatically create a new semantic/content ID when output is unchanged. |
| `transformation_run_id` | no | no | yes | Execution instance only. |
| `transformation_code_version` | no | no | yes | Code lineage only; content changes are captured by the content revision ID. |

### 7.4 Other deterministic IDs

| Object | Prefix | Ordered identity inputs |
|---|---|---|
| Raw evidence | `raw:` | provider, source tool, sanitized request fingerprint, retrieved_at, response fingerprint |
| Semantic observation | `obss:` | ordered material in 7.1 |
| Observation content revision | `obs:` | semantic observation ID plus canonical semantic content fingerprint |
| Relationship observation | `rel:` | semantic observation ID plus product ID, keyword ID, direction, relationship type, channel, and canonical content |
| Conflict | `cfl:` | sorted candidate observation revision IDs, subject, dimension, conflict status |
| Resolution | `res:` | sorted candidate observation revision IDs, subject, dimension, resolution policy/version |

Canonicalization rules, ID format version, collision behavior, and hashing are implementation-phase decisions and must be deterministic-test fixtures.

### 7.5 Reprocessing acceptance cases

**Same semantic output:** Raw `R1` from collection `C1` is mapped by `V1/T1` and later `V2/T2`. If both outputs have identical canonical semantic content `X`, both IDs remain stable; `T1` and `T2` are separate run records pointing to the same observation revision.

**Mapping bug fix:** If `V1/T1` interpreted a field as `Pa` and `V2/T2` correctly interprets it as `psi`, the semantic observation ID remains stable while the observation content-revision ID changes. The old revision remains addressable; a quality issue links the affected raw evidence, collection, mapping, transformation run, and old/new observation revisions. No provenance is overwritten.

**Schema version unknown:** A mapping may proceed when the provider exposes no version, provided `provider_schema_version.status = UNKNOWN`, the raw fingerprint remains available, and mapping semantics are otherwise safe. Guessing a provider version is invalid.

## 8. Example observation

```json
{
  "semantic_observation_id": "obss:design-example:rating:xiyou",
  "observation_id": "obs:design-example:rating:xiyou",
  "schema_version": "0.1",
  "observation_kind": "METRIC",
  "subject": {"subject_type": "PRODUCT", "subject_id": "product:US:B0GTQZ9C19", "marketplace": "US"},
  "metric": "rating",
  "measurement_type": "OBSERVED",
  "evidence_type": "OBSERVED",
  "value": {
    "presence_status": "PRESENT",
    "raw_value": "4.6",
    "normalized_value": 4.6,
    "value_type": "NUMBER",
    "unit": {"dimension": "RATING", "unit_code": "stars_5", "unit_system": "DOMAIN"},
    "normalization_status": "NORMALIZED",
    "semantic_status": "CONFIRMED"
  },
  "scope": {"scope_type": "ASIN", "scope_status": "CONFIRMED", "scope_subject_id": "product:US:B0GTQZ9C19"},
  "time": {"observed_at": null, "observed_at_status": "UNKNOWN", "retrieved_at": "2026-08-14T07:44:59.345Z", "period_start": null, "period_end": null, "period_type": "INSTANT", "timezone": null},
  "metric_semantic": "Displayed product rating on a five-star scale",
  "provenance": {
    "provider": "xiyou",
    "source_tool": "batch_product_info",
    "source_field": "stars",
    "source_record_identity": "US:B0GTQZ9C19",
    "retrieved_at": "2026-08-14T07:44:59.345Z",
    "transformation": {
      "collection_run_id": "collection:design-example:xiyou:C1",
      "provider_schema_version": {"status": "UNKNOWN", "value": null, "source": "UNKNOWN"},
      "mapping_version": "xiyou_product_info_mapping_v1",
      "transformation_run_id": "transform:design-example:xiyou:T1",
      "transformation_code_version": {"status": "KNOWN", "value": "design-revision-003d", "scheme": "RULESET_VERSION"},
      "raw_evidence_reference": "raw:design-example:xiyou-product",
      "transformed_at": "2026-08-14T08:00:00Z",
      "transformation_status": "SUCCESS"
    }
  },
  "quality_issue_ids": [],
  "result_status": "POPULATED"
}
```

Provider names appear only in provenance and mapping examples, never as canonical business fields.

## 9. Parent/child representation review

The current contract can represent `parent_asin`, child `ProductIdentity`, `PARENT_ASIN`/`CHILD_ASIN` scope, and a `parent_product_relationship` fact with provenance. This is sufficient for later aggregation design. No aggregation or deduplication policy is added here.

`DEFERRED_TO_MARKET_RECONSTRUCTION_DESIGN`

## 10. Single-provider mode and guarantees

- An observation requires one valid source, not two providers.
- With one source, validation may emit `ONE_SOURCE_ONLY`; this is not `INVALID`.
- Multi-provider evidence improves corroboration but is not an ingestion prerequisite.
- Conflicts never silently overwrite observations.
- Unit, semantic, identity, and critical-scope conflicts fail closed at the affected field.
- Provider removal or addition does not require changes to the canonical contracts.

## 11. Explicit non-goals

No runtime adapter classes, extraction functions, demand profiles, relevance logic, candidate reconstruction, opportunity scores, provider preference rules, latest-wins rules, or averaging rules are defined here.

## 12. Backward design review

`DESIGN_SCHEMA_REVISION - TRANSFORMATION_PROVENANCE_V0.1` is a deliberate design-contract revision, not a production data migration.

- Earlier SP-003 examples that omit `semantic_observation_id`, `provenance.transformation`, or the bundle-level `transformation_runs` collection are not valid instances of the revised formal schema.
- Descriptive snippets remain explanatory only unless they explicitly state that they are complete schema instances.
- The first implementation work must use this revised contract directly; it must not implement the superseded pre-revision shape and then rely on an implicit migration.
- No compatibility adapter, migration executable, persistence change, or business workflow is introduced by TASK-SP-003D.
