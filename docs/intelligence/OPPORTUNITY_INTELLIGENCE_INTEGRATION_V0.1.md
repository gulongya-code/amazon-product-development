# Opportunity Intelligence Integration V0.1

## Purpose and boundary

Opportunity Intelligence Integration V0.1 creates one immutable,
evidence-backed `OpportunityCandidateSnapshot` from existing upstream snapshots.
It is a read-only integration layer:

```text
BuyerNeedMapSnapshot
CategoryProductMapSnapshot
SupplyDemandGapSnapshot
CompetitionIntelligenceSnapshotV0_1
CanonicalProductAttributeProfile
MarketAnalysisResult | explicit UNKNOWN economic evidence
        -> OpportunityCandidateSnapshot
```

The layer does not modify the Opportunity Intelligence Foundation, Buyer Need Map,
Category Product Map, Supply/Demand Gap, Competition Intelligence, Product Attribute
Profile, Market Analysis, or Opportunity Scoring modules.

It does not calculate a score, rank candidates, calculate profit, margin, ROI, or
return, use an AI model, or issue a product-development instruction.

## Candidate contract

`OpportunityCandidateSnapshot` contains:

- deterministic `candidate_id`;
- the exact `category_scope` from Category Product Map;
- an evidence-backed `segment_definition` and `product_attribute_segment`;
- `need_cluster_id`;
- typed Gap, Competition, and Economic references;
- a categorical confidence value;
- one evidence-state classification;
- `OpportunityEvidenceBundle`; and
- diagnostics.

All public integration models are frozen, slotted dataclasses. Content identities
use `deterministic_id`; input sequence ordering cannot change a candidate identity.

## Evidence bundle

The bundle contains five independent areas:

| Area | Contents |
|---|---|
| Demand | Buyer Need Cluster, Demand Metrics, Search Evidence, Review Evidence |
| Supply | Product Coverage, Attribute Distribution, Existing Products |
| Competition | Market Concentration, Top ASIN Dominance, Brand Concentration, Review Barrier, Price Competition |
| Gap | Gap Type and Gap Strength, retaining Gap reliability |
| Economic | Price Band, Sales Availability, Revenue Availability, Market Size Signal |

Economic evidence has only `AVAILABLE`, `PARTIAL`, or `UNKNOWN` availability. It
does not contain a profit, margin, ROI, or return field.

Every bundle includes references to Buyer Need Map, Category Product Map,
Supply/Demand Gap, Competition Intelligence, and every supplied Product Attribute
Profile. Economic evidence references Market Analysis when supplied; otherwise it
records an explicit `UNKNOWN_ECONOMIC_EVIDENCE` reference and limitation.

## Competition integration

Competition is independent evidence. It never changes
`SupplyDemandGapSnapshot.gap_type`.

The present Competition Intelligence Foundation is an auditable inventory, not a
concentration or price-competition calculation. This integration therefore applies
these conservative mappings:

- market concentration remains `UNKNOWN` without a governed metric;
- keyword relationship records make top-ASIN evidence `PARTIAL`, but do not create
  a governed top-ASIN cohort or dominance level;
- brand concentration remains `UNKNOWN` without resolved brand concentration
  evidence;
- observed review statistics remain `PARTIAL` without a top-ASIN barrier policy;
- observed price statistics remain `PARTIAL`, explicitly labelled as not equivalent
  to price competition.

No observed-product count is interpreted as market concentration, and no observed
price distribution is interpreted as price competition.

Future upstream evidence may create an `AVAILABLE` Competition Evidence record with
an explicit `HIGH`, `MEDIUM`, or `LOW` categorical level. The integration layer
does not invent that level from raw inventory counts.

## Candidate classification

`OpportunityCandidateType` is closed to:

- `POTENTIAL_ENTRY_AREA`
- `NEEDS_VALIDATION`
- `HIGH_COMPETITION_AREA`
- `LOW_DEMAND_AREA`
- `INSUFFICIENT_EVIDENCE`

The classifier is an ordered rule set, not a weighted formula:

| Evidence state | Classification |
|---|---|
| Demand or Supply unavailable; Gap unavailable or insufficient | `INSUFFICIENT_EVIDENCE` |
| Low Demand Gap | `LOW_DEMAND_AREA` |
| High Demand + Low Supply + available Low Competition | `POTENTIAL_ENTRY_AREA` |
| High Demand + Low Supply + High/Partial/Unknown Competition | `NEEDS_VALIDATION` |
| High Demand + High Supply + available High Competition | `HIGH_COMPETITION_AREA` |
| High Demand + High Supply + other Competition state | `NEEDS_VALIDATION` |

This means a high-demand/low-supply gap with high competition remains a validation
state; it is not converted into a positive conclusion.

## Confidence

`OpportunityConfidence` has `HIGH`, `MEDIUM`, `LOW`, and `UNKNOWN` values. It is
not used in classification and cannot be used as an Opportunity Score.

- `UNKNOWN`: Demand, Supply, or Gap reliability is unknown, or a core evidence area
  is unavailable.
- `LOW`: core evidence exists but Competition or Economic evidence is unknown, or a
  core reliability is low.
- `MEDIUM`: core evidence exists and one or more evidence areas is partial, or a
  core reliability is medium.
- `HIGH`: Demand, Supply, Gap, Competition, and Economic evidence are all available
  and Gap reliability is high.

## Validation and traceability

`OpportunityCandidateRequest` fails closed when category scope, marketplace,
Buyer Need Map, Category Product Map, Gap, cluster, or profile continuity differs.
It accepts only built upstream snapshot types. The candidate builder retains all
input objects by reference and never mutates them.

Missing evidence is recorded as explicit evidence IDs and diagnostics. It is never
silently converted to zero or erased from a candidate that is classified as
`INSUFFICIENT_EVIDENCE`.

## Intentional limits

V0.1 does not provide:

- Opportunity Scoring integration;
- a recommended product or product-development decision;
- brand concentration, seller concentration, market concentration, or price
  competition formulas;
- profit, margin, ROI, cost, or return calculations;
- UI, workbook, spreadsheet, or export work; or
- an AI, LLM, embedding, or automated product-choice mechanism.

Those concerns require separately governed source evidence and acceptance criteria.
