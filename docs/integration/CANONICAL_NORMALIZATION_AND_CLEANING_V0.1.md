# Canonical Normalization and Cleaning V0.1

Status: TASK-SP-018C implementation baseline

Ruleset: `canonical-normalization-v0.1`

Runtime: Python 3.12 standard library only

## 1. Purpose and boundaries

This stage converts provider-mapped field candidates into consistent, validated Canonical values without replacing the original evidence. It prepares trustworthy inputs for later conflict resolution and calculations.

The governing rule is:

> Normalization rules are defined by canonical field semantics, not by concrete data providers.

The package does not import or branch on `XiYouProvider`, `SorftimeProvider`, SellerSprite, or provider identifiers. Provider-specific payload interpretation remains in each Provider Adapter. The stage does not calculate scores, trends, profit, opportunity, recommendations, or any of the 99 `CALCULATED` Workbook fields. It does not call a production API.

The boundary is:

```text
Provider raw evidence
  -> provider-owned mapping
  -> NormalizationInput
  -> CanonicalNormalizationPipeline
  -> NormalizationResult + Canonical DataQualityIssue
  -> validation/conflict-resolution boundary
  -> later calculations
```

Normalization cleans each candidate independently. It does not select a winning provider, average candidates, convert incompatible units, or create a `ResolutionRecord`.

## 2. Architecture

| Component | Responsibility |
|---|---|
| `NormalizationInput` | Immutable field candidate containing Canonical field, raw/mapped values, presence/semantic/capability state, unit, subject, evidence reference and existing `Provenance`. |
| `NormalizationContext` | Caller-supplied deterministic run ID, RFC 3339 timestamp and ruleset version. No clock or random value is read by the pipeline. |
| `NormalizerRegistry` | Maps a Canonical field to one small versioned rule. It is built once and reused by the pipeline. |
| `CanonicalNormalizationPipeline` | Applies capability and absence boundaries before field-aware rules, creates Canonical quality issues and isolates failures by field. |
| `NormalizationResult` | Preserves raw/mapped/normalized values, existing provenance, all status dimensions, quality issues and rule application lineage. |
| `NormalizationRuleApplication` | Records rule/version, run context, evidence reference, deterministic input/output fingerprints and transformation names. |

The capability vocabulary is located in the provider-neutral `provider_capabilities` module. Connector callers continue to import `CapabilityStatus` from the existing `connectors` public API; both names resolve to the same enum. This prevents normalization from importing the concrete Connector package while preserving compatibility.

The registry is deliberately not a general rule engine. A future Canonical field is added by registering one `NormalizationRule`; provider replacement requires no registry change when the Canonical field semantics are unchanged.

## 3. Input contract

`NormalizationInput` requires:

| Field | Meaning |
|---|---|
| `canonical_field` | Dotted, lowercase Canonical field identity. |
| `raw_value` | Exact value retained from the mapped Canonical observation envelope. |
| `mapped_value` | Adapter-mapped candidate presented to the field rule. |
| `presence_status` | Existing `PresenceStatus`; no parallel missing enum is introduced. |
| `semantic_status` | Existing `SemanticStatus`. Cleaning never upgrades an unconfirmed semantic into confirmed semantics. |
| `unit` | Existing Canonical `Unit`, if established. |
| `capability_status` | `AVAILABLE`, `PARTIAL`, `UNAVAILABLE`, or `UNKNOWN`; `CALCULATED` is not a provider capability. |
| `subject` | Existing Canonical `SubjectRef`. |
| `provenance` | Existing `Provenance`, including provider/source field and `TransformationProvenance`. |
| `evidence_reference` | Upstream observation/evidence reference used by lineage and quality issues. |

`NormalizationInput.from_observation(...)` adapts an existing `CanonicalObservation` without replacing its provenance. Non-present Canonical inputs carry no raw or mapped business value, matching the V0.1 `ValueEnvelope` invariant.

## 4. Output contract

`NormalizationResult` contains:

- the Canonical field and exact raw/mapped candidates;
- the typed normalized candidate;
- existing presence, semantic and provider-capability dimensions;
- existing `NormalizationStatus` (`NORMALIZED`, `FAILED`, `AMBIGUOUS`, `NOT_ATTEMPTED`, or `NOT_APPLICABLE`);
- the effective `Unit` without unsafe conversion;
- zero or more existing Canonical `DataQualityIssue` records;
- existing source `Provenance` unchanged;
- a versioned rule application record when a rule ran.

Financial and ratio results use `Decimal` in memory. This avoids binary floating-point drift. V0.1 does not force `Decimal` into the existing JSON-only `ValueEnvelope`; `NormalizationResult.to_dict()` serializes it deterministically as a decimal string. Integration that emits a new Canonical observation must use the existing observation/versioning process and merge quality issue references with bundle integrity checks. This stage intentionally does not rewrite source observations.

## 5. Missing and capability semantics

> Missing, unknown, unavailable, invalid, false, zero, and empty are not interchangeable states.

| Input state | Result behavior |
|---|---|
| `PRESENT` with `0` | Rule executes; zero remains a real value when valid for the field. |
| `PRESENT` with `False` | Boolean rule executes; false remains a real value. |
| `MISSING` | No rule runs; normalized value remains null and `MISSING_VALUE` is recorded. |
| `EXPLICIT_NULL` | No rule runs; normalized value remains null and `EXPLICIT_NULL_VALUE` is recorded. |
| `UNKNOWN` presence | No rule runs; normalized value remains null and `UNKNOWN_VALUE` is recorded. |
| `QUERY_RETURNED_EMPTY` | No demand, market, or competitor zero is inferred. |
| `NOT_APPLICABLE` | Existing `NOT_APPLICABLE` semantics are retained without inventing an issue. |
| known empty collection | A present empty tuple; distinct from a missing collection. |
| invalid present value | Raw value remains available, normalized value is null or a clearly partial value, and a typed issue is emitted. |
| `PARTIAL` capability | Known components may be cleaned, but the result stays `PARTIAL`. |
| `UNKNOWN` / `UNAVAILABLE` capability | No value is promoted or synthesized; capability state is retained. |

Consequently, missing cannot silently become `0`, unknown cannot silently become `False`, and a missing collection cannot become `[]`.

## 6. V0.1 field-aware rules

| Rule | Canonical fields | Behavior |
|---|---|---|
| ASIN | `product.asin`, `product.parent_asin` | Trim, uppercase and reuse the Canonical 10-character ASIN validator. Never generates an identifier. |
| conservative text | product title/brand/category/fulfillment/seller | NFC, outer/repeated whitespace cleanup, control-character replacement. Display case and punctuation are preserved. |
| keyword identity text | `keyword.text` | Conservative text rule plus casefold for identity comparison. No stemming, synonym expansion, clustering, embedding or AI. |
| exact decimal | `keyword.difficulty` | Finite `Decimal`; no invented business scale. |
| count | review/order/sales/search-volume and explicit child/related counts | Integral, non-negative; zero is valid, negative/fractional values are invalid. |
| money | `metric.price`, `keyword.cpc` | Parses finite `Decimal` from numeric, `$`, `US$`, `USD`, commas and whitespace. Negative amounts fail. Currency is never guessed. |
| ratio | `keyword.click_conversion_rate`, `metric.traffic_ratio` | Explicit `15%` becomes `0.15`; a bare `15` fails the 0..1 ratio range and is never globally divided by 100. |
| rank | `metric.bsr`, `keyword.aba_rank`, `relationship.rank` | Parses `#1`, `1`, `#1,234`; rank must be a positive integer and never defaults to zero. |
| rating | `metric.rating` | Exact decimal constrained only to the known 0..5 scale. No arbitrary outlier threshold. |
| boolean | `product.a_plus` | Only bool, 0/1 and explicit true/false/yes/no strings. Missing or unknown never becomes false. |
| date | `product.first_available_date` | ISO date only. |
| datetime | `observation.observed_at` | RFC 3339/ISO datetime with timezone preservation. A naive value is ambiguous; UTC is not assumed. |
| ASIN collection | `keyword.related_product_asins`, `product.child_asins` | Validate members, deduplicate by normalized ASIN and sort deterministically. Invalid members remain in raw evidence and produce a partial/ambiguous result. |

Fields that already contain structured mapped evidence (marketplace request scope, BSR context, variation/attributes, relationship observations and channel enum) do not need a second generic cleaning rule in V0.1. Their schema and semantic checks remain mapping/Canonical validation responsibilities.

## 7. Validation and quality issues

The pipeline reuses `DataQualityIssue`; it does not introduce another validation model. All normalization issues use `OriginStage.NORMALIZATION`, link the existing collection/transformation/mapping IDs, cite the evidence reference, and use deterministic issue IDs.

Machine-readable codes include:

```text
INVALID_FORMAT
MISSING_VALUE
EXPLICIT_NULL_VALUE
UNKNOWN_VALUE
EMPTY_VALUE
OUT_OF_RANGE
UNSUPPORTED_UNIT
AMBIGUOUS_CURRENCY
CURRENCY_CONFLICT
INVALID_IDENTIFIER
INVALID_MEMBER
DUPLICATE_MEMBER
CONTROL_CHARACTER_REMOVED
TIMEZONE_MISSING
NORMALIZATION_FAILED
UNSUPPORTED_FIELD
CAPABILITY_UNAVAILABLE
CAPABILITY_UNKNOWN
```

Malformed values, impossible negatives, invalid identifiers and timezone/currency ambiguity are explicit. A large but valid price is not rejected as an outlier. Statistical outlier detection is a later extension, not an implicit delete rule.

An extension rule exception is converted into a field-level `NORMALIZATION_FAILED` issue without including the input value in the error message. `normalize_many` retains caller order and continues with sibling fields.

## 8. Provenance and determinism

The trace is:

```text
Provenance.provider / source_tool / source_field
  -> TransformationProvenance.raw_evidence_reference and mapping_version
  -> NormalizationInput.raw_value and mapped_value
  -> NormalizationRuleApplication.rule_id / rule_version
  -> normalization run/version and deterministic fingerprints
  -> NormalizationResult.normalized_value
```

The existing `Provenance` object is retained exactly. The application record supplements it with cleaning execution metadata; it is not a replacement provenance hierarchy.

The pipeline reads no current clock, random source, network or AI. The caller supplies run ID and timestamp. Same input, Canonical field, registry version and context produce the same serialized result. Set-like collections use an explicit key and stable ordering. Core rules are idempotent at the normalized-value boundary.

## 9. Provider independence and replacement

Two providers presenting the same Canonical field use the same registry lookup and rule. Provider identity appears only in preserved provenance. Tests cover:

- FakeProviderA and FakeProviderB providing the same price;
- XiYou disabled with Sorftime evidence active;
- Sorftime disabled with XiYou evidence active;
- a future FakeProviderC using existing Canonical rules;
- independent normalization of conflicting XiYou/Sorftime price candidates.

No change to normalization core is required for those replacements. A provider-specific format must first be mapped by its adapter into the input contract.

## 10. Conflict-resolution boundary

For `XiYou price = "$19.99"` and `Sorftime price = "20.49"`, normalization emits two clean Decimal candidates with separate provenance. It does not choose, average, merge or prioritize them. Existing conflict/resolution contracts remain responsible for comparability, difference classification, policy and a resolved record.

Similarly, normalization does not treat a provider estimate as observed fact, equate provider-specific sales metrics, resolve Pa/WOG/PSI unit semantics, merge organic/sponsored ranks, or infer demand from an empty query.

## 11. Matrix coverage audit

Audit basis: the 157-row SP-018A matrix plus the SP-018B checked-in XiYou/Sorftime capability declarations. The Workbook matrix remains unchanged at `30 AVAILABLE / 24 PARTIAL / 99 CALCULATED / 2 UNAVAILABLE / 2 UNKNOWN`.

At the connector Canonical-field level, deduplicating the provider declarations gives:

| Audit category | Count | Fields / disposition |
|---|---:|---|
| connector `AVAILABLE`/`PARTIAL` Canonical fields | 25 | Union of the two connector capability declarations, including the separately gated P1 raw-review operation. |
| P0 `AVAILABLE`/`PARTIAL` Canonical fields | 24 | Connector field inventory excluding the documented P1 `review.raw` operation. |
| P0 normalization supported | 21 | ASIN (including explicit variation members); title; brand; category; fulfillment; price; rating; review count; BSR; orders; estimated sales; keyword search volume/ABA rank/CPC/difficulty; both directional relationship membership fields; and typed relationship `keyword.channel`. |
| P0 normalization not yet required | 3 | `product.marketplace`, `metric.bsr_context`, and `product.attributes`; these use typed request scope or structured Canonical evidence rather than a second scalar normalization. |
| separately gated P1 | 1 | `review.raw` is a structured `ReviewObservation`; its nested envelopes are already adapter-normalized and must not be treated as one text scalar. |
| blocked/unknown | 4 | `keyword.locale`, `workflow.manual_review_status`, `product.seller`, `keyword.estimate_method_status`. Their SP-018A conclusions are unchanged. |

The 25-field connector count (24 P0 plus 1 P1) is a unique Canonical-field inventory, not a replacement for the 54 Workbook rows marked `AVAILABLE` or `PARTIAL`. Several Workbook display fields map to one Canonical input or require presentation aggregation.

Additional schema-supported rules for ratio, boolean, date and ASIN collections prepare known Canonical types for later connectors without adding Workbook business fields. No `CALCULATED` formula is present in the package.

## 12. Extension guide

1. Confirm that the field exists in the Canonical or approved mapping contract.
2. Keep provider-specific extraction and format quirks in the Provider Adapter.
3. Implement a small normalizer returning typed value, existing statuses, unit, transformations and structured issue specifications.
4. Register the rule under the Canonical field with an explicit rule/version.
5. Add missing, invalid, idempotency, determinism and provider-neutral tests.
6. If semantics or units cannot be established safely, return ambiguity/issue state rather than guessing.
7. Leave competing candidate selection to conflict resolution and derived business formulas to the calculation layer.

Ruleset changes require a new normalization version or rule version so an output can always answer which cleaning logic produced it.

## 13. Acceptance gates

| Gate | Mechanical/automated evidence |
|---|---|
| Provider independence | Normalization package has no concrete provider imports or provider-name branches. |
| Missing semantics | Tests assert missing != zero, unknown != false and missing collection != empty collection. |
| Provenance | Tests assert raw/normalized/provider/source/rule/version linkage and Canonical quality issue mapping lineage. |
| Determinism | Same object and context serialize identically. |
| Idempotency | Core numeric, money, ratio, rank, ASIN and keyword normalized values are stable on a second pass. |
| Failure isolation | An invalid or exception-raising field does not destroy valid sibling results. |
| Provider replacement/future provider | Disabled-provider and FakeProvider cases use unchanged cleaning core. |
| Conflict boundary | Competing prices remain two clean candidates. |
| CALCULATED isolation | No opportunity, profit, market, scoring or recommendation formula is implemented. |

## 14. Security and follow-up

Inputs and issues contain no credential field. Rules make no network call and error messages do not echo raw values. Tests use only local fixtures/fakes.

Follow-up work belongs outside SP-018C: emission policy for new normalized Canonical observation revisions, SP-018D calculations, statistical outlier analysis, new provider adapters, real API operations, and operator presentation changes.
