# Opportunity Intelligence Foundation V0.1

## 1. Status and boundary

Opportunity Intelligence V0.1 is an immutable, deterministic evidence-availability
view over `CanonicalEvidenceBundle`. Its ruleset identifier is exactly:

```text
opportunity-intelligence-v0.1
```

The executable boundary is:

```text
CanonicalEvidenceBundle
        -> OpportunityIntelligenceRequest
        -> OpportunityIntelligenceBuilderV0_1
        -> OpportunityIntelligenceSnapshotV0_1
```

Opportunity production code imports only `amazon_product_intelligence.contracts`,
relative Opportunity modules, and the Python standard library. It does not import
or consume Adapter results, `ProductIntelligenceSnapshot`,
`DemandIntelligenceSnapshot`, or `CompetitionIntelligenceSnapshot`.

The layer answers only this question:

```text
Which opportunity-related evidence-existence signals, explicit absences, and
evidence limitations are represented by the supplied canonical bundles?
```

It does not answer whether a product is worth selecting or entering.

## 2. Architecture discovery

The existing intelligence layers establish useful read-model concepts without
becoming Opportunity dependencies:

- Product Intelligence organizes product facts, metrics, variation evidence,
  reviews, and coverage.
- Demand Intelligence organizes keyword metrics, directional query outcomes,
  keyword-product relationships, and coverage.
- Competition Intelligence organizes observed products, keyword relationship
  evidence, confirmed variations, and a non-concluding evidence graph.

All of those concepts originate in canonical source records. Opportunity V0.1
therefore consumes the canonical records directly and independently. This avoids a
hidden Product-to-Demand-to-Competition-to-Opportunity business-logic chain.

## 3. Public API

`amazon_product_intelligence.opportunity_intelligence` explicitly exports:

- `OPPORTUNITY_INTELLIGENCE_RULESET_VERSION`;
- `OpportunityIntelligenceRequest`;
- `OpportunityIntelligenceSnapshotV0_1`;
- `OpportunityIntelligenceBuilderV0_1`;
- the Opportunity validation, serialization, and identity error hierarchy;
- signal classification, signal type, source type, missing kind, and risk type
  enumerations; and
- immutable signal, missing inventory, risk, coverage, diagnostic, quality, and
  lineage models.

The request accepts a non-empty sequence of canonical bundles only. It has no
score, threshold, weight, target outcome, provider preference, or decision input.

## 4. Signal classification

The closed classification namespace is:

```text
OBSERVED_SIGNAL
DERIVED_SIGNAL
MISSING_EVIDENCE_SIGNAL
RISK_EVIDENCE
```

An observed signal is a structural projection of one canonical observation or
query execution. A derived signal is a deterministic evidence-presence view whose
supporting observed signal IDs, source record IDs, providers, source tools, and
lineage remain explicit.

A missing signal records only that one V0.1 category was not found. Risk evidence
records a source limitation. Neither class expresses product quality, market
quality, probability, desirability, or a decision.

## 5. Observed signals

Every supplied canonical observation and directional query execution produces one
observed signal. The source roles are:

```text
PRODUCT_FACT
PRODUCT_METRIC
KEYWORD_METRIC
KEYWORD_PRODUCT_RELATIONSHIP
QUERY_EXECUTION
REVIEW
```

Observed signals retain their exact source record ID, product and keyword
identities where applicable, provider, source tool, structural evidence attributes,
and complete lineage.

Structural attributes preserve the boundaries needed for audit:

- product facts retain dimension, fact group, presence, semantic state, scope, and
  time;
- product metrics retain metric, semantic, measurement/evidence type, currency,
  unit, scope, and time;
- keyword metrics retain metric, estimate-method status, range, unit, scope, and
  time;
- relationships retain direction, channel, relationship type, query status, rank,
  and traffic without aggregation;
- queries retain direction, exact outcome, and referenced result count; and
- reviews retain the review identity and component presence states.

Canonical values such as missing, explicit null, unknown, numeric zero, and present
remain distinct in the source evidence attributes. Signal existence never upgrades
an unknown or absent value into a present fact.

## 6. Derived signals

V0.1 creates only these mechanical evidence-presence views:

```text
PRODUCT_EVIDENCE_PRESENT
KEYWORD_EVIDENCE_PRESENT
RELATIONSHIP_EVIDENCE_PRESENT
CONFIRMED_VARIATION_EVIDENCE_PRESENT
```

Product and keyword views group exact canonical identities and list all supporting
observed signals. Relationship views retain exact direction and channel boundaries.
They do not connect products or keywords beyond the canonical relationship records
that support the view.

The complete canonical `KeywordIdentity` is the grouping boundary. For example,
the audited fixtures contain `1/2 Ball Valve` and `1/2 ball valve` with the same
normalized keyword ID but different raw text. V0.1 preserves them as distinct exact
identity values rather than silently discarding either source representation.

Derived signals do not average values, prefer a provider, resolve a conflict,
calculate a trend, or create a new observed fact.

## 7. Missing evidence inventory

`MissingEvidenceInventory` always evaluates this closed category set:

```text
PRODUCT_FACT_EVIDENCE
PRODUCT_METRIC_EVIDENCE
KEYWORD_EVIDENCE
KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE
QUERY_EXECUTION_EVIDENCE
COMPETITION_RELATED_EVIDENCE
VARIATION_EVIDENCE
REVIEW_EVIDENCE
PRICE_EVIDENCE
```

The evaluation is bundle-wide because V0.1 has no target product or target keyword
input. A category appears in `items` only when no qualifying canonical record is
present in any supplied bundle.

The exact rules are deliberately structural:

- keyword evidence is present when a canonical keyword identity occurs in a
  keyword metric, relationship, or forward query;
- competition-related evidence is present when a keyword-product relationship or
  present confirmed variation relationship exists;
- variation evidence requires a present confirmed `child_product_relationship` or
  `parent_product_relationship` fact;
- price evidence requires a canonical product metric named exactly `price`,
  `sale_price`, or `list_price` after case folding; and
- all remaining categories require their corresponding canonical record class.

The inventory interpretation is fixed as:

```text
MISSING_EVIDENCE_IS_NOT_NEGATIVE_EVIDENCE
```

An empty missing inventory means only that every evaluated category has at least one
record. It is not a completeness claim.

## 8. Risk evidence

Risk evidence records evidence limitations only. V0.1 has no severity, probability,
weight, risk level, or score. The closed risk types are:

```text
UNKNOWN_PERIOD
UNKNOWN_OBSERVATION_TIME
PROVIDER_METHOD_UNDECLARED
SINGLE_PROVIDER_EVIDENCE
QUERY_OUTCOME_LIMITATION
REVIEW_EVIDENCE_ABSENT
```

The triggering rules use canonical fields directly:

- `UNKNOWN_PERIOD` groups observations whose `TimeWindow.period_type` is `UNKNOWN`;
- `UNKNOWN_OBSERVATION_TIME` groups observations whose observed-at status is
  `UNKNOWN`;
- `PROVIDER_METHOD_UNDECLARED` groups provider-estimate observations whose
  provenance has no declared provider method;
- `SINGLE_PROVIDER_EVIDENCE` applies when all signal source records originate from
  exactly one provider;
- `QUERY_OUTCOME_LIMITATION` applies to canonical query outcomes other than
  `RESULTS_RETURNED`; and
- `REVIEW_EVIDENCE_ABSENT` references the explicit missing-review item.

Source-backed risk evidence carries complete source lineage. An absence-backed risk
references the corresponding missing evidence ID. No limitation changes the value
or classification of its source evidence.

## 9. Product, demand, and competition boundaries

Opportunity signals may reference exact product identities, exact keyword
identities, canonical directional relationships, populated or non-populated query
outcomes, and confirmed parent-child variations.

Confirmed variation direction is normalized as follows:

- `child_product_relationship`: subject is parent, normalized value is child;
- `parent_product_relationship`: normalized value is parent, subject is child.

Products sharing a parent do not receive a sibling relationship. Products sharing a
keyword do not receive a product-to-product relationship. The existence of product,
demand, or competition-related evidence does not establish a product opportunity.

## 10. Coverage

`OpportunityCoverageSummary` inventories:

- bundles, raw references, and transformation runs;
- observed, derived, missing, and risk evidence counts;
- exact product and keyword identities;
- product facts, product metrics, keyword metrics, relationships, queries, reviews,
  and confirmed variation observations;
- competition-related source records;
- providers and source tools;
- signal types and query outcomes;
- canonical quality issues and Opportunity diagnostics.

Coverage is bookkeeping only. It has no percentage, completeness assessment,
confidence, trust, rank, weight, or score.

## 11. Replayable lineage

Every source-backed observed, derived, and risk item connects to an
`OpportunityLineageReference`:

```text
canonical observation or directional query ID
        -> transformation_run_id
        -> mapping_version
        -> raw_evidence_id
        -> collection_run_id
        -> source bundle fingerprint
```

The reference also retains canonical source type, semantic observation identity and
kind when applicable, provider, source tool, and source field.

`validate_against_bundles()` verifies the exact bundle fingerprint set and replays
every reference through the canonical record, transformation output, mapping
version, raw evidence, and collection boundaries. It rejects wrong bundle types,
duplicate fingerprints, orphan records, wrong source types, identity collisions,
transformation mismatches, mapping mismatches, raw-reference mismatches, collection
mismatches, and fingerprint mismatches. The lineage index must exactly equal the
lineage referenced by public evidence items. Canonical quality issue references are
also replayed exactly.

## 12. Immutability, identity, and serialization

Requests and snapshots use frozen, slotted dataclasses. Input sequences are detached
as tuples. JSON-like attributes are copied and recursively frozen as mapping proxies
and tuples. Supplied canonical bundles are immutable contract objects.

Bundle fingerprints use SHA-256 over order-insensitive top-level canonical bundle
content. All snapshot sequences use explicit stable sort keys. Content identities
use canonical JSON through `deterministic_id` and do not use current time, UUIDs,
randomness, `hash()`, `repr()`, or filesystem order.

Strict `from_dict()` round trips nested contracts and enums, rejects unknown fields
and invalid values, and rejects a snapshot whose ID does not match all serialized
content.

## 13. Audited fixture integration

The integration tests execute real Adapter V0.1.2 paths for:

- XiYou keyword metrics;
- XiYou populated keyword-to-product query;
- XiYou product-to-keyword reverse query;
- XiYou variations;
- Sorftime product detail; and
- Sorftime product reviews.

Their combined canonical evidence produces:

```text
6 bundles
39 observed signals
15 derived signals
4 exact product identities
3 exact keyword identity values
10 keyword-product relationship observations
2 directional query executions
3 confirmed variation observations
1 review observation
0 missing V0.1 categories
3 evidence-limitation risk types
```

The three limitations are unknown period, unknown observation time, and undeclared
provider method. These counts and limitations make no product or market conclusion.

## 14. Explicit non-goals and residual limits

V0.1 does not produce product selection, market entry or rejection decisions,
profit/revenue/ROI predictions, investment decisions, automated selection, winning
product detection, market timing, growth forecasts, risk scoring, rankings, or any
AI-authored business recommendation.

It also does not decide which evidence is more important, whether an evaluated
category is sufficiently covered, whether products compete, whether demand is high
or low, or whether a product is good or bad. Those decisions require separately
versioned architecture, rules, and acceptance criteria.
