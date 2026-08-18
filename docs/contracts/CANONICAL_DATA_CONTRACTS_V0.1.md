# Canonical Data Contracts V0.1 — Runtime Implementation

Status: Level 3 implementation contract
Tasks: `TASK-SP-004`, `TASK-SP-007B`

## Scope

This package implements the current Level 2 canonical evidence design directly. It provides immutable, JSON-compatible Python value objects and cross-record validation for:

- explicit `PRESENT`, `EXPLICIT_NULL`, `MISSING`, `UNKNOWN`, `QUERY_RETURNED_EMPTY`, and `NOT_APPLICABLE` states;
- product, keyword, semantic-observation, and canonical-content-revision identities;
- raw evidence references, collection runs, mapping versions, transformation runs, and code/schema version status;
- all five V0.1 canonical observation kinds;
- independent directional query execution evidence for populated, explicit-empty, unknown, and failed outcomes;
- data-quality, conflict, and resolved-evidence records;
- bundle-level lineage and reference integrity.

The implementation intentionally has no third-party dependencies. It does not install or require `jsonschema`, Pydantic, or a provider SDK.

## Package boundary

Import contracts from:

```python
from amazon_product_intelligence.contracts.v0_1 import (
    CanonicalEvidenceBundle,
    DirectionalQueryExecutionRecord,
    QueryExecutionOutcome,
    query_execution_id,
)
```

All contracts expose `to_dict()` and strict `from_dict()` methods for JSON-compatible round trips. Unknown fields, missing required fields, invalid enum strings, and wrong primitive types fail closed. `canonical_json()` is stable and is used only as deterministic identity material. SHA-256 identifiers include type-specific prefixes (`raw:`, `keyword:`, `obss:`, `obs:`, `qex:`, `rel:`, `cfl:`, and `res:`).

`DirectionalQueryExecutionRecord` is independent of the five observation kinds. It preserves the exact keyword-to-product or product-to-keyword query subject, an explicit `QueryExecutionOutcome`, related relationship-observation references when results exist, and full raw/collection/mapping/transformation lineage. It never invents a relationship target or converts an empty result into a zero-valued metric. `CanonicalEvidenceBundle.query_execution_records` and `TransformationRunRecord.output_query_execution_ids` provide validated forward and back references.

Identity material accepts only JSON-compatible values with string mapping keys and finite numbers. Mapping keys are sorted during serialization; unordered sets, date-time objects, NaN, infinity, and other implicit representations are rejected. Contract mappings and nested collections are detached from caller-owned mutable containers.

## Fail-closed rules

Construction rejects unsafe local states, including:

- coercing missing, null, empty, or unknown evidence to a value;
- filling an unknown source observation time from retrieval time;
- unknown or empty formal mapping versions;
- embedding a failed transformation in a source observation;
- publishing a present value for an unresolved/deferred/rejected resolution;
- marking a mapping/normalization issue without collection, transformation, and mapping lineage.

Bundle validation additionally rejects orphan or wrong-type raw evidence, transformation, observation, query-execution, conflict, resolution, and quality-issue references. Query result references must resolve to product-keyword relationships with matching direction, query subject, and transformation provenance. A resolution linked to a conflict must match its subject, dimension, candidate set, conflict status, and outcome. Reprocessing is legal: two transformation runs may point to the same canonical content-revision ID when semantic output is unchanged, but the same revision ID cannot hide different canonical content.

The query-execution addition keeps the schema version string at `0.1` and is decode-compatible with old serialized data: missing `output_query_execution_ids` and `query_execution_records` fields default to empty tuples. New serialization emits both fields deterministically. See `docs/design/CANONICAL_QUERY_EXECUTION_EVIDENCE_V0.1.md` for the full additive boundary.

## Verification

No package installation is required:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

The tests cover explicit missing/null/unknown/zero states, all five observation types, directional query outcomes and strict subjects, deterministic reprocessing and ID ordering, strict serialization round trips, immutable container boundaries, mapping-fix revisions, failed runs, resolved and unresolved conflicts, duplicate identities, wrong-type/orphan references, invalid resolution targets, full lineage checks, and field-level fail-closed behavior.

## Non-goals

TASK-SP-004 does not implement provider adapters, provider transport, extraction, Product Intelligence, Demand Intelligence, relevance, market reconstruction, scoring, persistence, retention policy, provider priority, latest-wins, or averaging rules.
