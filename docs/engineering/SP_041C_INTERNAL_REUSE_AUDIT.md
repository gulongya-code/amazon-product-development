# SP-041C Internal Reuse Audit

Date: 2026-08-26
Issue: `#53 TASK-SP-041C`
Required baseline: `50e2661a2eb45dc0a7cc46275f14edc6f7301a3d`

This audit was completed before implementation changes. `HEAD` matched the
required baseline, the worktree/index were clean, and the dedicated branch was
created directly from that commit.

## Search surface

The audit searched `src/`, `scripts/`, `tests/`, `docs/`, and the SP-041C
section of `origin/codex/planning-hybrid-market-analysis-v1` for text
normalization/tokenization, deterministic identity and JSON, availability and
evidence status, provenance, unit parsing, attribute extraction, conflicts,
Category Product Map semantics, and strict versioned configuration loading.

## Selected reuse

| Existing component | Reuse mode | SP-041C use |
|---|---|---|
| `contracts.JsonContract`, `canonical_json`, `deterministic_id`, `Unit` | direct reuse | strict immutable JSON contracts, stable identities/fingerprints, and canonical units |
| `contracts.PresenceStatus`, `NormalizationStatus`, `SemanticStatus` | direct reuse | interpret SP-041B field availability without converting missing evidence into facts |
| `normalization.rules.normalize_text` and `normalization.models.json_value` | wrapped/direct reuse | conservative text cleanup and Decimal/date-safe JSON material |
| SP-041B `GovernedMarketDatasetV1`, `ListingRecordV1`, `NormalizedField` | direct upstream contract | preserve accepted listing ASIN grain, field statuses, dataset identity, and record fingerprints |
| `product_attribute_extraction.AttributeConfidenceLevel` | direct reuse | categorical confidence derived from evidence priority, never a fabricated probability |
| `product_attribute_extraction.quantity` | reviewed pattern reuse | explicit Decimal conversion factors and fail-closed unsupported-unit behavior; its V0.1 candidate model is not reused because it is coupled to a different source contract |
| `product_attribute_extraction.resolver` | algorithm-policy adaptation | exact agreement deduplication, deterministic ordering, and conflict preservation without confidence voting |
| `opportunity_scoring.scoring.config_loader` | loader-pattern adaptation | explicit JSON path/ID, UTF-8 decode, strict mapping validation, no implicit latest/default lookup |
| `category_product_map` coverage/denominator patterns | reference-only internal reuse | deterministic coverage accounting only; no distributions, routes, combinations, shares, or scoring are invoked |

## Frozen components not modified

| Component | Decision | Reason |
|---|---|---|
| Product Attribute Extraction V0.1 models/registry/pipeline | do not modify | its upstream is `ProductIntelligenceSnapshotV0_1`, its dimensions/taxonomy are frozen, and its global aliases would not satisfy category-pack isolation |
| Category Product Map V0.1 builder | do not invoke | it aggregates distributions/combinations and is downstream of attribute profiles; SP-041C only produces the independent per-listing Product Attribute Map |
| Product Intelligence V0.1 | do not adapt as an input | SP-041C's normative upstream is the SP-041B governed market dataset |
| generic Conflict Resolution foundation | do not instantiate | it resolves Canonical provider observations, not rule-pack attribute candidates; its fail-closed policy is reused conceptually |
| Production Pipeline and Market Report | forbidden | changing their provider or frozen business semantics is outside Issue #53 |

## Necessary SP-041C-specific contracts

A small independent adapter is necessary because no frozen internal contract
represents all required V1 dimensions (`product_form`,
`mounting_or_usage_mode`, `material_family`, `size_or_capacity`, `pack_count`,
`operation_mode`, `power_mode`, `special_features`, `dimensions`, and
`weight`) while consuming SP-041B listing fields. New contracts will still use
the shared identity/JSON/unit/confidence primitives and will not create an
alternative Canonical evidence system.

Category-specific aliases, negative rules, source authorization, and value
mappings must live in strict versioned JSON rule packs. Generic code may only
parse governed syntax, exact quantities/units, and deterministic rule
structures.

## Regression obligations

Tests must protect SP-041A/SP-041B contracts, existing normalization and
Product Intelligence behavior, evidence precedence, conflicts, rule-pack
strictness, pack-vs-pocket/tier/shelf separation, no-drilling negatives,
cross-category portability, stable fingerprints, zero network/credentials/LLM,
and input immutability.
