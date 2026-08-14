# Canonical Data Model V0.1

Status: design contract only  
Task: TASK-SP-003  
Serialization: JSON-compatible, provider-independent, snake_case

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

## 3. Common observation envelope

All observation types contain:

| Field | Required | Semantics |
|---|---:|---|
| `observation_id` | yes | Deterministic observation ID. |
| `schema_version` | yes | `0.1`. |
| `observation_kind` | yes | Contract discriminator. |
| `subject` | yes | Canonical subject reference. |
| `evidence_type` | yes | `OBSERVED` or `PROVIDER_ESTIMATE` at this layer. |
| `value` | yes | Presence/value/unit/semantic envelope. |
| `scope` | yes | Explicit measurement grain. |
| `time` | yes | Observation, retrieval, and period fields. |
| `provenance` | yes | Trace to raw evidence. |
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

IDs are reproducible from canonical inputs; V0.1 intentionally does not select or implement a hash algorithm.

| Object | Prefix | Ordered identity inputs |
|---|---|---|
| Raw evidence | `raw:` | provider, source tool, sanitized request fingerprint, retrieved_at, response fingerprint |
| Observation | `obs:` | raw evidence ID, source record identity, canonical subject, kind, metric/dimension, source position |
| Relationship observation | `rel:` | raw evidence ID, product ID, keyword ID, direction, relationship type, source record identity |
| Conflict | `cfl:` | sorted candidate observation IDs, subject, dimension, conflict status |
| Resolution | `res:` | sorted candidate observation IDs, subject, dimension, resolution policy/version |

Canonicalization rules, ID format version, collision behavior, and hashing are implementation-phase decisions and must be deterministic-test fixtures.

## 8. Example observation

```json
{
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
  "provenance": {"provider": "xiyou", "source_tool": "batch_product_info", "source_field": "stars", "source_record_identity": "US:B0GTQZ9C19", "raw_evidence_reference": "raw:design-example:xiyou-product", "retrieved_at": "2026-08-14T07:44:59.345Z"},
  "quality_issue_ids": [],
  "result_status": "POPULATED"
}
```

Provider names appear only in provenance and mapping examples, never as canonical business fields.

## 9. Single-provider mode and guarantees

- An observation requires one valid source, not two providers.
- With one source, validation may emit `ONE_SOURCE_ONLY`; this is not `INVALID`.
- Multi-provider evidence improves corroboration but is not an ingestion prerequisite.
- Conflicts never silently overwrite observations.
- Unit, semantic, identity, and critical-scope conflicts fail closed at the affected field.
- Provider removal or addition does not require changes to the canonical contracts.

## 10. Explicit non-goals

No runtime adapter classes, extraction functions, demand profiles, relevance logic, candidate reconstruction, opportunity scores, provider preference rules, latest-wins rules, or averaging rules are defined here.
