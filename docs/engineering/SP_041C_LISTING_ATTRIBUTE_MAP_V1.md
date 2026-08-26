# Cross-Category Listing Attribute Parser V1.0

Issue: `#53 TASK-SP-041C`

## Boundary and flow

The implementation consumes only an in-memory SP-041B
`GovernedMarketDatasetV1`. It reads accepted per-ASIN records and produces a
per-ASIN `ProductAttributeMapV1`:

```text
SP-041B governed dataset
  -> structured parameter parser
  -> explicitly authorized field evidence
  -> generic exact measurement parser
  -> strict CategoryRulePack V1.0
  -> Product Attribute Map V1.0
```

It does not call a provider or network service, use AI, modify frozen pipeline
or report semantics, or build any SP-041D archetype, route, representative,
competitor, score, or recommendation.

## Evidence policy

The engine uses this fixed order:

1. `STRUCTURED_PARAMETERS`
2. `DEDICATED_FIELD`
3. `SKU`, only when a rule explicitly lists it
4. `TITLE`, only when a rule explicitly lists it

Confidence is categorical and source-derived: structured and dedicated fields
are `HIGH`, authorized SKU is `MEDIUM`, and authorized title is `LOW`.
No probability is calculated. A lower-priority disagreement cannot overwrite a
higher-priority value. Conflicting values for one normalized structured key
produce `REVIEW_REQUIRED`.

Each mapped value links to evidence containing source kind, priority, field,
structured key when applicable, bounded normalized snippet, upstream record
fingerprint, confidence, rule ID, and rule-pack version. Rule-derived values
use `DERIVED_RULE`; passthrough and exact measurement values use `OBSERVED`.

## Structured parameters

`parse_detailed_parameters` implements only the governed grammar
`Key: Value | Key: Value`. It splits a segment at its first colon, normalizes
presentation whitespace/casing for identity, deduplicates repeated equivalent
pairs, and preserves different values for the same semantic key as a conflict.
Its semantic fingerprint excludes presentation casing, whitespace, segment
order, and source snippets.

## Measurements

The generic parser accepts closed, full-string patterns and uses `Decimal`:

- length: mm, cm, m, in, ft -> cm
- mass: g, kg, oz, lb -> g
- volume: ml, L, fl oz -> L
- dimensions: three exact length components with a single unit -> cm
- count: explicit pack/piece/set syntax, or a bare integer only when the
  selected measurement rule explicitly authorizes it

Original text, numeric components, unit, and item/package scope are retained.
Bare `oz` for capacity is ambiguous. Pocket, tier, shelf, and layer counts are
not pack counts. Unsupported or ambiguous formats do not guess a value.

## Rule packs

Rule packs are external UTF-8 JSON with exact schema version
`category-rule-pack-v1.0`. The loader rejects missing/unknown fields,
unsupported enums/dimensions, duplicate rule IDs, malformed JSON, and
non-boolean controls. Rules cannot contain regexes, expressions, code, network
lookups, or implicit defaults.

Bundled synthetic packs:

- `config/category_rule_packs/shower_caddies.v1.json`
- `config/category_rule_packs/dog_water_bottle.v1.json`

The second pack proves that product form, operations, materials, features,
capacity, dimensions, and weight can be mapped by the same generic engine with
configuration only.

## Public API

```python
from amazon_product_intelligence.listing_attribute_map import (
    build_product_attribute_map,
    load_category_rule_pack,
)

rule_pack = load_category_rule_pack(
    "config/category_rule_packs/shower_caddies.v1.json"
)
result = build_product_attribute_map(dataset, rule_pack=rule_pack)
payload = result.to_json()
```

The result includes upstream dataset ID/fingerprint, rule-pack ID/version and
fingerprint, parser versions, counts, dimension coverage, record evidence,
review/conflict counts, stable record IDs, and a deterministic semantic
fingerprint. Runtime timestamps are excluded from its identity.

## CLI

```powershell
python scripts/build_product_attribute_map.py \
  --input seller-export.xlsx \
  --marketplace US \
  --category "Shower Caddies" \
  --rule-pack config/category_rule_packs/shower_caddies.v1.json \
  --observed-date 2026-08-26 \
  --output product-attribute-map.json
```

The CLI is local-only, requires an explicit rule pack and category, never
overwrites an existing output, rejects output aliasing input/config, and prints
only sanitized metadata. It reports
`private_real_listing_replay: NOT_RUN` when no authorized private replay was
performed.
