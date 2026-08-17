# Canonical Data Contracts V0.1 — Runtime Implementation

Status: Level 3 implementation contract
Task: `TASK-SP-004`

## Scope

This package implements the current Level 2 canonical evidence design directly. It provides immutable, JSON-compatible Python value objects and cross-record validation for:

- explicit `PRESENT`, `EXPLICIT_NULL`, `MISSING`, `UNKNOWN`, `QUERY_RETURNED_EMPTY`, and `NOT_APPLICABLE` states;
- product, keyword, semantic-observation, and canonical-content-revision identities;
- raw evidence references, collection runs, mapping versions, transformation runs, and code/schema version status;
- all five V0.1 canonical observation kinds;
- data-quality, conflict, and resolved-evidence records;
- bundle-level lineage and reference integrity.

The implementation intentionally has no third-party dependencies. It does not install or require `jsonschema`, Pydantic, or a provider SDK.

## Package boundary

Import contracts from:

```python
from amazon_product_intelligence.contracts.v0_1 import CanonicalEvidenceBundle
```

All contracts expose `to_dict()` and strict `from_dict()` methods for JSON-compatible round trips. Unknown fields, missing required fields, invalid enum strings, and wrong primitive types fail closed. `canonical_json()` is stable and is used only as deterministic identity material. SHA-256 identifiers include type-specific prefixes (`raw:`, `keyword:`, `obss:`, `obs:`, `rel:`, `cfl:`, and `res:`).

Identity material accepts only JSON-compatible values with string mapping keys and finite numbers. Mapping keys are sorted during serialization; unordered sets, date-time objects, NaN, infinity, and other implicit representations are rejected. Contract mappings and nested collections are detached from caller-owned mutable containers.

## Fail-closed rules

Construction rejects unsafe local states, including:

- coercing missing, null, empty, or unknown evidence to a value;
- filling an unknown source observation time from retrieval time;
- unknown or empty formal mapping versions;
- embedding a failed transformation in a source observation;
- publishing a present value for an unresolved/deferred/rejected resolution;
- marking a mapping/normalization issue without collection, transformation, and mapping lineage.

Bundle validation additionally rejects orphan or wrong-type raw evidence, transformation, observation, conflict, resolution, and quality-issue references. A resolution linked to a conflict must match its subject, dimension, candidate set, conflict status, and outcome. Reprocessing is legal: two transformation runs may point to the same canonical content-revision ID when semantic output is unchanged, but the same revision ID cannot hide different canonical content.

## Verification

No package installation is required:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

The tests cover explicit missing/null/unknown/zero states, all five observation types, deterministic reprocessing and ID ordering, strict serialization round trips, immutable container boundaries, mapping-fix revisions, failed runs, resolved and unresolved conflicts, duplicate identities, wrong-type/orphan references, invalid resolution targets, full lineage checks, and field-level fail-closed behavior.

## Non-goals

TASK-SP-004 does not implement provider adapters, provider transport, extraction, Product Intelligence, Demand Intelligence, relevance, market reconstruction, scoring, persistence, retention policy, provider priority, latest-wins, or averaging rules.
