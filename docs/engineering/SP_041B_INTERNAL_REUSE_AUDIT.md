# SP-041B Internal Reuse Audit

Date: 2026-08-26
Issue: `#52 TASK-SP-041B`
Required baseline: `c7c545761030e145ada54067dcc493134dade6c3`

This audit was completed before implementation changes. The repository was on
the exact required baseline with a clean worktree and index.

## Search surface

The audit searched `src/`, `scripts/`, `tests/`, and `docs/` for the following
concepts: CSV/XLSX ingestion, exact header mapping, 66-field raw-source schema,
ASIN normalization, Decimal money and ratio handling, rank/rating/date/boolean
normalization, presence/normalization/semantic statuses, canonical JSON,
SHA-256 identity, duplicate/conflict handling, snapshots, and provider-neutral
provenance.

## Selected reuse

| Existing component | Reuse mode | SP-041B use |
|---|---|---|
| `operator_template_contract.schema_v1.RAW_HEADER_CONTRACTS` | direct import | authoritative 66-field names, CORE/OPTIONAL/OUT_OF_SCOPE classification, and semantic notes |
| `normalization.models.PresenceStatus` | direct import | distinguish present, missing, explicit-null, and unknown evidence |
| `normalization.models.NormalizationStatus` | direct import | normalized, raw, invalid, and unsupported outcomes |
| `normalization.models.SemanticStatus` | direct import | preserve observed/estimated/unknown semantics without inventing business meaning |
| `normalization.models.json_value` | direct import | JSON-safe Decimal/date conversion |
| `normalization.rules` primitive normalizers | wrapped reuse | ASIN, text, money, rank, rating, boolean, integer, and date validation |
| `contracts.canonical_json` / deterministic hashing pattern | pattern/direct reuse | stable logical serialization and identifiers |
| `ingestion.snapshot_writer` safe-name/write conventions | pattern reuse only | basename-only source identity and fail-closed output behavior |

## Rejected internal reuse

| Component | Decision | Reason |
|---|---|---|
| provider connectors and `data_cleaning.service` | rejected | would couple a local-file adapter to provider calls and provider-specific runtime behavior |
| `CanonicalNormalizationPipeline` as the importer | rejected | requires provider capabilities/provenance subjects that do not describe local SellerSprite export rows; only its primitive rules/status vocabulary is reused |
| Production Pipeline models or wiring | rejected | Issue #52 requires an isolated import surface and forbids semantic changes to the live pipeline |
| workbook template auditor/validator | rejected for row import | audits workbook structure and formulas, not governed listing-row ingestion |
| Product Attribute Map, archetype, scoring, representative/direct-competitor modules | forbidden | these belong to SP-041C or later |

## Integration boundary

SP-041B will add an isolated local XLSX/CSV adapter and governed market dataset
contract. It will not create network clients, call providers, change Market
Report output, interpret attributes into Product Archetypes, select
representatives, label direct competitors, or modify the production pipeline.

## Required regression coverage

The implementation must keep SP-041A contract tests, ingestion/data-cleaning
tests, and the full baseline suite stable. Focused SP-041B tests will cover
exact header discovery, UTF-8 CSV, type/status preservation, duplicate and
conflict behavior, deterministic fingerprints, provenance, row bounds,
zero-network behavior, and input immutability.
