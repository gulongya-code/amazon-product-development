# Opportunity Scoring Integration V0.1

## Purpose and boundary

Opportunity Scoring Integration V0.1 adds a second, isolated input path to the
existing Opportunity Scoring package:

```text
OpportunityCandidateSnapshot
        -> OpportunityScoreInputAdapter
        -> OpportunityScoringIntegrationInput
        -> EvidenceBasedOpportunityScorerV0_1 + explicit OpportunityScorePolicy
        -> EvidenceBasedOpportunityScore
        -> OpportunityScoreExplanation
```

The integration consumes only evidence already organized by Opportunity
Intelligence Integration V0.1. It does not query Review, Search Term, ASIN,
Product Attribute, provider, canonical raw evidence, or upstream intelligence
builders.

Opportunity Intelligence remains the evidence owner. Opportunity Score is a
policy-versioned aggregation of that evidence and is not a new fact source.
Neither layer produces a product recommendation.

## Compatibility

The Candidate path is implemented in
`opportunity_scoring/integration_v0_1/`. It does not change:

- `OpportunityScoringRequest` or `OpportunityScoringSnapshotV0_1`;
- `OpportunityScoringEngineInput` or its three legacy dimensions;
- `OpportunityScoringBuilderV0_1`;
- the existing readiness evaluators;
- `BusinessScoringConfiguration`, `ScoreCalculator`, or
  `OpportunityScoreResult`; or
- any Opportunity Intelligence, Supply/Demand Gap, Buyer Need Map, Category
  Product Map, Competition Intelligence, or Foundation contract.

Legacy callers continue using the existing entrypoints. Candidate callers use
`OpportunityScoringIntegrationV0_1.score_candidate()`. No automatic dispatch,
implicit conversion, or migration changes legacy behavior.

## Input adapter

`OpportunityScoreInputAdapter` accepts exactly one
`OpportunityCandidateSnapshot`. It emits an immutable,
deterministically-identified `OpportunityScoringIntegrationInput` containing:

- `candidate_id`;
- the complete serialized `category_scope`;
- Candidate qualitative confidence;
- the closed V0.1 scoring metric catalogue;
- every referenced Opportunity Intelligence evidence identity;
- typed source references copied from the Candidate evidence bundle; and
- explicit limitations.

The adapter copies only Candidate-owned evidence and never interprets a missing
value as zero.

## Score dimensions

| Dimension | Candidate evidence | V0.1 interpretation |
|---|---|---|
| Demand Strength | Search Demand Share, Review Mention Share, Demand Confidence | Policy-declared range/category rules |
| Supply Gap | Gap Type, Gap Strength | Policy-declared categorical rules; Gap is never recomputed |
| Competition Favorability | Market Concentration, Brand Concentration, Review Barrier, Price Competition | Low/medium/high mapping only when an upstream level exists |
| Economic Evidence | Price Band, Sales Availability, Revenue Availability | Evidence presence/readiness only; no profit, margin, cost, or ROI |
| Evidence Confidence | Demand, Supply, Gap, Competition, and Economic completeness | AVAILABLE/PARTIAL evidence coverage; UNKNOWN remains excluded |

Each dimension emits one `OpportunityDimensionScore` containing its status,
dimension score, contribution, declared maximum contribution, metric traces,
calculation rule, explanation, evidence IDs, and source reference IDs.

## Policy

`OpportunityScorePolicy` is an explicit immutable artifact with:

- `policy_version`;
- five `dimension_weights`;
- one declared rule in `thresholds` for every V0.1 metric;
- `missing_data_policy`;
- `rounding_policy`;
- `confidence_rules`; and
- a content-derived SHA-256 `policy_fingerprint`.

The scorer contains no dimension weight, metric weight, threshold, category
score, rounding choice, or missing-data default. Policies are loaded by exact
path and exact version. The loader rejects `latest`, missing fields, unknown
fields, incomplete metric catalogues, invalid rules, weights that do not sum to
100, and a mismatched fingerprint.

The repository policy artifact used for contract tests assigns the example
dimension maxima 30/25/20/15/10. These values live in the policy fixture, not
the implementation.

## UNKNOWN and missing data

UNKNOWN metric inputs produce trace records with:

- the original evidence and source references;
- `raw_value=null`;
- `normalized_score=null`;
- `weighted_score=null`; and
- `UNKNOWN_EXCLUDED_NOT_ZERO`.

An entirely unavailable dimension has `score_value=null` and
`contribution=null`. Under `SKIP_RENORMALIZE`, the final score is calculated
only from eligible dimensions and the included policy weight is renormalized.
The explanation records
`MISSING_DIMENSIONS_EXCLUDED_AND_WEIGHTS_RENORMALIZED`. Under `BLOCK`, the
result becomes `PENDING_DATA` with no final numeric score.

Missing Economic Evidence therefore does not create an Economic score of zero
and does not receive an automatic positive or negative value.

## Score and confidence

Score and confidence are independent result fields:

- `score_value` is calculated only from eligible evidence metrics and the
  explicit policy;
- `confidence` preserves Candidate qualitative confidence under the V0.1
  `PRESERVE_CANDIDATE_CONFIDENCE` strategy; and
- `confidence_rules.score_multiplier` must be `false`.

Changing Candidate confidence alone cannot change the numeric score. A result
such as `score_value=85` with `confidence=LOW` is valid.

Demand Confidence is an explicit Demand evidence metric because the task input
contract names it. Its categorical score rule is visible in the metric trace;
it is not applied as a multiplier to the final score or any other dimension.

## Explanation and lineage

`OpportunityScoreExplanation` contains:

- final score;
- all five dimension breakdowns;
- every metric calculation trace;
- all Candidate source references;
- policy version;
- risks; and
- limitations.

The audit chain is:

```text
EvidenceBasedOpportunityScore
  -> OpportunityScoreExplanation
      -> OpportunityDimensionScore
          -> OpportunityMetricScoreTrace
              -> Opportunity Intelligence evidence ID
              -> Opportunity Intelligence source reference
                  -> Buyer Need Map / Category Product Map / Gap /
                     Competition / Economic interface
  -> OpportunityScorePolicy version + fingerprint
```

All public integration identities use canonical JSON and SHA-256-derived
deterministic IDs. There is no wall-clock, UUID, random, locale, or filesystem
input in score identity material.

## Validation contract for TASK-SP-031

Every score includes an `OpportunityScoreValidationContract` with:

- Category Scope;
- Candidate Count;
- evidence coverage by scoring dimension;
- availability status for every metric; and
- accumulated limitations.

TASK-SP-031 should evaluate real Candidate batches against this contract and
record at least:

1. category and marketplace continuity across every Candidate;
2. Candidate count and cohort inclusion/exclusion reasons;
3. percentage of AVAILABLE, PARTIAL, and UNKNOWN metrics by dimension;
4. observed metric ranges and category values against the pinned policy;
5. Competition signals that remain UNKNOWN because no governed upstream metric
   exists;
6. Economic evidence coverage without introducing cost or profit estimates;
7. score stability when Candidate ordering changes; and
8. replay equality for Candidate ID, policy fingerprint, score ID, explanation,
   and lineage.

## Intentional limits

V0.1 does not implement:

- AI, LLM, embeddings, generated recommendations, ranking, or candidate winner
  selection;
- profit, margin, ROI, cost, return, or revenue prediction;
- new concentration, review-barrier, or price-competition facts;
- modification of Supply/Demand Gap or Opportunity Candidate classification;
- UI, workbook, Excel, export, or presentation work; or
- a production policy registry or automatic policy selection.
