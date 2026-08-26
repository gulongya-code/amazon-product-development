# TASK-SP-041D Internal Reuse Audit

- Audit date: 2026-08-26
- Required baseline: `bcefe61e8bbd1a253663eece60a234b124a3f111`
- Required parent: `50e2661a2eb45dc0a7cc46275f14edc6f7301a3d`
- Audit timing: completed before route-discovery implementation
- Scope boundary: TASK-SP-041D only; no SP-041E representative-ASIN or downstream work

## Decision

SP-041D will extend the repository's governed contracts rather than create a parallel evidence or metric framework. Existing listing-grain import and attribute-map contracts are the authoritative inputs. Existing deterministic identity, JSON serialization, availability, evidence, completeness, metric-sample, provenance-reference, and denominator concepts will be reused directly where their semantics match.

## Direct reuse

| Existing component | Reuse decision | SP-041D use |
| --- | --- | --- |
| `GovernedMarketDatasetV1`, `ListingRecordV1`, `NormalizedField` | Direct | Listing-grain market facts, source evidence, availability, normalized values, import issues, and dataset fingerprint. |
| `ProductAttributeMapV1`, `ProductAttributeRecord`, `AttributeSlot` | Direct | Governed structural attributes, conflicts, review state, record identity, and upstream fingerprint. |
| `JsonContract`, `canonical_json`, `deterministic_id` | Direct | Canonical output, stable IDs, fingerprints, deterministic ordering. |
| Market Report V0.2 `Availability`, `PresenceStatus`, `EvidenceSemantics`, `CompletenessStatus` | Direct | Explicit metric availability and evidence semantics; unknown is never converted to zero. |
| Market Report V0.2 `MetricContextEnvelope`, `MetricSampleContext`, `build_metric_context`, `unavailable_metric` | Direct | Route metric values, sample counts, denominator references, coverage, method policy, provenance, and limitations. Decimal arithmetic is used before the contract's finite numeric serialization boundary. |
| Market Report V0.2 `ContractReference` helpers | Direct | Upstream dataset/map/config and governed denominator references. |

## Pattern reuse with an SP-041D contract

| Existing component | Reuse decision | Reason |
| --- | --- | --- |
| Category Product Map distributions and coverage | Adapt pattern | Reuse explicit eligible/unknown/member counts, denominator identity, ratio formatting, and fail-closed coverage patterns. Its frozen builder is not invoked because its input and output semantics differ from route discovery. |
| Opportunity configuration loader | Adapt pattern | Reuse strict external JSON configuration, schema/version validation, unknown-key rejection, and deterministic fingerprinting. Opportunity-score semantics are not reused or changed. |
| Semantic clustering deterministic sorting and traceability | Adapt pattern only | Stable ordering and trace concepts are useful, but buyer-need lexical/AI membership is not a valid structural product-route algorithm. |

## Explicit non-reuse

- Do not invoke or modify the frozen Opportunity Score, Market Report, workbook, or production-pipeline semantics.
- Do not use `semantic_clustering` membership rules: they operate on buyer-need text and would create a semantic collision with structural attributes.
- Do not use parent-product collapsing or representative-ASIN selection. SP-041D remains listing-grain and preserves parent evidence only.
- Do not call SellerSprite, Sorftime, any provider API, AI membership, credentials, or procurement logic.
- Do not treat missing structural attributes as equality, false, zero, or an absent feature.

## Threshold audit

The operator-template ruleset exposes `listing_age_bands` and `new_product_window` as external placeholders rather than authoritative numeric policy. No authoritative new-product threshold was found in the required baseline. SP-041D must therefore externalize a versioned threshold in its route configuration, publish its source classification, and include its version/fingerprint in result provenance. It must not silently invent or embed the threshold in algorithm code.

## Planning-branch read-only review

The SP-041D section of `origin/codex/planning-hybrid-market-analysis-v1` was reviewed read-only. It confirms listing-grain Product Map, deterministic attribute-route discovery, explicit denominators, reconstructed prior-period growth, and the private real-market replay gate. No planning-branch code was merged or copied, and no SP-041E content is implemented.

## Baseline evidence

- Exact baseline checked before development: `bcefe61e8bbd1a253663eece60a234b124a3f111`.
- Focused pre-change suite: 425 passed, 111 subtests passed.
- Full pre-change suite: 1 failed, 1404 passed, 13 skipped, 550 subtests passed.
- The sole full-suite failure is pre-existing: `tests/test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type` expects ruleset identity `89ffe16d...` while the exact baseline produces `84e5aed6...`.
- A sanitized search found no qualifying private SellerSprite fixture in the workspace, project parent, Downloads, or Desktop at audit time. This does not relax the mandatory private replay gate.
