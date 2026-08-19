# Canonical Directional Query Execution Evidence V0.1

Status: Level 3 additive contract patch
Task: `TASK-SP-007B`

## 1. Problem statement

The five Canonical Data Contracts V0.1 observation kinds describe facts that have concrete canonical subjects. A directional provider query can also complete successfully and return an explicitly empty result set. That event has no product-keyword relationship to publish, but it is still material execution evidence.

Before this patch, XiYou retained a forward empty query in raw evidence and an adapter diagnostic only. A consumer restricted to `CanonicalEvidenceBundle` could not distinguish an explicitly empty execution from an unknown outcome, unsupported execution, or lost adapter-local diagnostic. Product Intelligence therefore could not pass a complete canonical boundary to Demand Intelligence without reopening provider-specific data.

Absence cannot mean empty: no record may mean that a query was never executed, its payload kind was unsupported, collection failed before transformation, or the bundle was serialized before this additive field existed. Only an explicit execution record with `EXPLICIT_EMPTY` proves that one scoped provider query returned an empty result.

A `DataQualityIssue` is also insufficient. It records a quality or mapping problem and may block a field, but an explicitly empty successful execution is not itself a defect. An adapter diagnostic is outside the canonical bundle and is not a stable downstream contract. Neither can substitute for the outcome record.

A fake `ProductKeywordRelationshipObservation` would be invalid because that observation requires both a real `ProductIdentity` and a real `KeywordIdentity`. Creating a placeholder product for an empty forward query would convert absence of results into fabricated domain evidence and corrupt relationship identity, lineage, and later competition analysis.

## 2. Contract boundary

`DirectionalQueryExecutionRecord` is an immutable canonical evidence record independent of the five observation kinds. It does not fabricate a product, keyword, metric, zero, demand judgment, market size, or competitor count.

Each record contains:

- a deterministic `query_execution_id`;
- the relationship direction;
- exactly one canonical query subject;
- an explicit execution outcome;
- optional references to concrete relationship observations;
- complete raw, collection, mapping, and transformation provenance;
- optional data-quality issue references.

The record is stored in `CanonicalEvidenceBundle.query_execution_records`, while `TransformationRunRecord.output_query_execution_ids` exposes the run-to-output back-reference.

## 3. Directional query subjects

Subjects are strict and nullable only as a pair:

| Direction | Required subject | Forbidden subject |
|---|---|---|
| `KEYWORD_TO_PRODUCT` | `query_keyword` | `query_product` |
| `PRODUCT_TO_KEYWORD` | `query_product` | `query_keyword` |

Request context cannot be promoted into the opposite subject type. A forward empty result therefore remains a keyword query; it does not invent a placeholder product.

## 4. Outcomes

`QueryExecutionOutcome` has four fail-closed values:

- `RESULTS_RETURNED`: one or more concrete relationship observation references are required;
- `EXPLICIT_EMPTY`: the provider response explicitly establishes an empty result and no relationship references are allowed;
- `OUTCOME_UNKNOWN`: execution occurred but the available evidence cannot safely establish results or explicit emptiness; no relationship references are allowed;
- `EXECUTION_FAILED`: the directional execution failed; no relationship references are allowed.

`EXPLICIT_EMPTY` is evidence about one executed query, not a universal claim of zero demand, zero competitors, zero market size, or permanent absence.

## 5. Observation references

Every referenced output must resolve to a `ProductKeywordRelationshipObservation` in the same bundle. Its direction and query-facing subject must match the record, and its transformation provenance must match the execution record. Metric, product fact, review, and child-product observations are invalid query results.

## 6. Lineage and validation

Bundle validation requires each query execution record to resolve its:

- raw evidence record;
- collection run;
- mapping specification;
- transformation run;
- quality issues;
- related relationship observations.

The containing transformation run must list the query execution ID. Orphan records, wrong output types, direction or subject mismatches, transformation mismatches, and issue-reference mismatches fail closed. A successful transformation may publish observations, query execution records, or both. A failed transformation may publish neither.

## 7. Serialization and compatibility

The patch is additive to schema version string `0.1`:

- old serialized transformation runs without `output_query_execution_ids` decode with an empty tuple;
- old serialized bundles without `query_execution_records` decode with an empty tuple;
- new serialization emits both fields deterministically;
- the existing five observation contracts and their identity functions are unchanged.

Unknown fields, invalid enum values, wrong primitives, identity mismatches, non-string mapping keys, non-finite numbers, and mutable-container aliasing continue to fail closed under the existing contract rules.

## 8. Deterministic identity

`query_execution_id()` hashes canonical JSON identity material and emits the prefix `qex:`. The material includes direction, the strict query subject, outcome, related observation IDs, source record ID, collection ID, mapping ID, transformation ID, and quality issue IDs. Mapping key order, process hash state, local paths, current time, and object representations are not identity inputs.

Replaying the same evidence produces the same query execution ID. Changing its outcome, subject, lineage, or related results changes the ID. The record constructor verifies that the supplied ID matches its content.

## 9. XiYou adapter behavior

Provider adapter ruleset `provider-adapters-v0.1.5` and XiYou adapter version `0.1.5` retain the directional execution evidence introduced in V0.1.2 for both audited legacy query mappings and their HTTP V2 root equivalents. V0.1.5 additionally separates the live-verified direct-root variation and BSR mappings from legacy sanitized envelopes:

- `xiyou_keyword_to_asin_mapping_v1_1`;
- `xiyou_asin_to_keyword_mapping_v1_1`.

A populated result publishes `RESULTS_RETURNED` with references to all safely emitted relationship observations. An explicitly empty `data.list` publishes `EXPLICIT_EMPTY`, keeps raw response status `EMPTY`, emits no fake relationship, and completes the transformation successfully. A non-empty response from which no safe relationship can be published is `OUTCOME_UNKNOWN` rather than empty.

Raw-evidence and unchanged relationship-observation identities remain stable. Transformation IDs and bundle fingerprints change deterministically where versioned execution material or the new query record changes.

## 10. Downstream interpretation

Product Intelligence V0.1 remains unchanged. It may receive bundles containing the new independent record without reinterpreting provider payloads or adapter diagnostics. Demand Intelligence may later consume the canonical record to distinguish populated, explicit-empty, unknown, and failed directional evidence.

This patch does not implement Product Intelligence aggregation changes, Demand Intelligence, relevance, true-competitor selection, market reconstruction, demand or competition judgments, scoring, cross-provider resolution, persistence, transport, or live provider calls.

## 11. Known limits

- Only audited XiYou directional query payloads emit this record; this behavior was introduced in V0.1.2 and remains unchanged in V0.1.5.
- The captured fixture set contains a forward explicit-empty query; reverse explicit-empty behavior is supported by the same contract and adapter path but is not asserted as captured provider evidence.
- Provider traffic methodology, keyword-estimate derivation, ranking codes beyond audited values, and query result completeness remain unknown.
- Empty query evidence is scoped to its exact query, provider response, retrieval time, marketplace, mapping, and transformation lineage.
