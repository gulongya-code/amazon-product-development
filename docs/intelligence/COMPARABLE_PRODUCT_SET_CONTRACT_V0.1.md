# Comparable Product Set Business Contract V0.1

## 1. Contract status

| Property | V0.1 value |
|---|---|
| Contract version | `comparable-product-set-v0.1` |
| Owner | Business / Intelligence domain |
| Provider dependency | `NONE` |
| Cross-market comparability | `NOT_SUPPORTED` |
| Target in peer set | `FALSE` |
| Membership execution | `BLOCKED_BY_MEMBERSHIP_SOURCE` |
| Minimum comparable price readiness | `NO — BLOCKED BY MEMBERSHIP SOURCE` |
| Maximum comparable price readiness | `NO — BLOCKED BY MEMBERSHIP SOURCE` |

This document is the normative V0.1 business contract. It defines a governed
product-to-product relationship; it does not implement a Comparable Product Set
evaluator.

The governing rule is:

> Structural eligibility is necessary but not sufficient for business comparability.

## 2. Purpose

A **Comparable Product** is a candidate identified by a valid Canonical
`ProductIdentity` that:

1. satisfies every V0.1 structural condition in the target's exact governed
   marketplace, scope, and snapshot/observation context;
2. is not the target product itself; and
3. has a governed comparability assertion whose decision is `COMPARABLE`, whose
   target and candidate match that context, and whose evidence, version, and
   provenance are traceable.

The **Comparable Product Set** is the deterministically ordered collection of the
unique peer candidates satisfying all three conditions. Structural eligibility
alone never creates membership.

This contract gives downstream price and comparison metrics one stable business
dependency rather than allowing each formula to invent a different meaning of
"comparable".

## 3. Non-goals

V0.1 does not:

- implement `minimum_comparable_price` or `maximum_comparable_price`;
- create a production membership evaluator or choose its future authority;
- infer comparability from price, sales, BSR, reviews, rating, or revenue;
- implement a competition score, opportunity score, price-band score, or market
  share;
- use an LLM, embedding, fuzzy matching, or semantic similarity;
- change Provider, Connector, Normalization, Workbook, Trend, or Variation
  Evidence Count behavior;
- call an API or consume credentials; or
- perform cross-market mapping or cross-market comparability.

## 4. Existing concept audit

| Existing concept | What it establishes | V0.1 reuse | Comparable membership authority? |
|---|---|---|---|
| Canonical `Comparability` | Whether observations of one canonical subject have compatible identity, dimension, semantic, scope, period, unit, and direction boundaries | Reuse its fail-closed discipline only | **No.** `Canonical Comparability != Comparable Product relationship`. |
| Canonical `ProductIdentity` | Stable `(marketplace, ASIN)` product identity and `product_id` | Sole product identity authority | Yes for identity only; not for the business decision |
| Product Intelligence variation family | Confirmed, target-connected parent/child topology | Supporting structural evidence | No; a parent, child, or sibling is not automatically comparable |
| Demand related-product inventory | Product endpoints observed in directional keyword relationships | Supporting evidence with lineage | No; `related product != comparable product` |
| Competition observed-product inventory | Products observed in supplied canonical evidence | Candidate discovery and lineage | No; it is explicitly not a competitor or comparable set |
| Keyword relationships | Directional, channel-specific product-keyword evidence | Supporting evidence | No; same keyword or keyword co-occurrence is insufficient |
| Provider/API result inventory | Evidence emitted by a source | Evidence lineage only | No; response, page, or dataset membership is insufficient |
| Workbook V0.2 price projection | Local minimum/maximum over available target price candidates | Historical presentation behavior only | No; it is not a governed peer-set price aggregation |

The Workbook projection predates this contract and must not be treated as proof
that comparable-price fields are ready. This task does not redesign or modify the
Workbook.

## 5. Terminology

| Term | Meaning |
|---|---|
| Candidate universe | Products supplied for evaluation in one governed context; it may contain the target |
| Structurally eligible candidate | A non-target candidate satisfying all structural gates; this is not a comparable decision |
| Governed comparability assertion | Versioned, traceable target-to-candidate decision issued by an approved authority |
| Comparable peer | A structurally eligible candidate with a valid `COMPARABLE` assertion |
| Excluded candidate | A candidate failing a structural gate or carrying an explicit `NOT_COMPARABLE` assertion, with a reason |
| Unresolved candidate | A structurally eligible candidate for which final business comparability is not governed or cannot be resolved |
| Valid empty set | A completed governed evaluation whose candidates are explicitly disposed and whose comparable peer count is zero |

Candidate, structurally eligible, `COMPARABLE`, `NOT_COMPARABLE`, and
`UNRESOLVED` are distinct states.

## 6. Normative clause register

| Clause | Requirement |
|---|---|
| `CPS-IDENTITY-001` | Membership identity is Canonical `ProductIdentity`; titles, labels, rows, positions, and Provider keys are prohibited. |
| `CPS-MARKETPLACE-001` | Target and candidate must have the same marketplace. Cross-market comparability is not supported. |
| `CPS-CONTEXT-001` | One set is bound to one governed scope and one explicit snapshot/observation context. |
| `CPS-TARGET-001` | The target may be in the candidate universe but is excluded from the peer comparable set. |
| `CPS-STRUCTURE-001` | Structural eligibility is necessary but not sufficient for final business comparability. |
| `CPS-AUTHORITY-001` | Final membership requires a governed comparability assertion. |
| `CPS-EVIDENCE-001` | Product type, category, keyword, variation, brand, attributes/features, and Provider membership are supporting evidence only. |
| `CPS-PRICE-001` | Price and other comparison metrics do not define membership. |
| `CPS-STATE-001` | Missing, valid empty, `NOT_COMPARABLE`, and `UNRESOLVED` remain distinct. |
| `CPS-ORDER-001` | Identity uniqueness and deterministic ordering are required; ordering cannot affect decisions. |
| `CPS-LINEAGE-001` | Every membership decision retains assertion authority, evidence references, contract version, context, and provenance. |
| `CPS-DOWNSTREAM-001` | A valid governed Comparable Product Set is upstream of comparable-price aggregation. |

## 7. Identity authority

Membership uses the existing Canonical `ProductIdentity`:

```text
ProductIdentity(marketplace, ASIN)
```

The identity must pass the Canonical contract, including normalized marketplace,
normalized ASIN, and content-derived `product_id`. V0.1 never constructs identity
from title, display label, row number, Provider-specific key, temporary list index,
keyword position, category, brand, or co-occurrence.

Malformed or incomplete identity is not repaired. A candidate-specific invalid
identity is excluded with an explicit quality reason. If the target identity or
another set-level identity input is missing, the set cannot be evaluated and is
not represented as an empty set.

## 8. Marketplace boundary

Target and every candidate member must have exactly the same normalized Canonical
marketplace. A US target and UK candidate cannot enter one V0.1 set.

```text
cross-market comparability = NOT_SUPPORTED
```

There is no automatic marketplace mapping. A future cross-market policy requires
a new explicit contract version.

## 9. Snapshot and scope context

Membership is evaluated inside one explicit governed observation context. The
context consists of:

- the exact target `ProductIdentity`;
- its marketplace;
- the existing typed analysis scope;
- the exact existing snapshot ID or analysis record IDs used by the caller; and
- their existing source-bundle fingerprints and lineage where available.

V0.1 reuses existing Product/Intelligence snapshot and provenance identities. It
does not create a second snapshot system. Candidates or assertions from different
scopes, marketplaces, or snapshots/runs cannot be silently combined. Unknown or
missing set-level context prevents evaluation; it does not produce an empty set.

## 10. Structural eligibility

All conditions are required:

| Gate | Required behavior | Failure disposition |
|---|---|---|
| Canonical identity | Target and candidate are contract-valid Canonical `ProductIdentity` values | Invalid/missing identity; never auto-repair |
| Marketplace | Candidate marketplace equals target marketplace | `WRONG_MARKETPLACE` exclusion |
| Scope | Candidate and assertion belong to the exact governed analysis scope | `SCOPE_MISMATCH` exclusion or missing set input |
| Snapshot/context | Candidate and assertion belong to the exact governed snapshot/observation context | `SNAPSHOT_CONTEXT_MISMATCH` exclusion or missing set input |
| Peer boundary | Candidate `product_id` differs from target `product_id` | `TARGET_ITSELF` exclusion |

Passing every row yields **structurally eligible**, not `COMPARABLE`.

```text
structural eligibility alone sufficient? NO
```

## 11. Target exclusion

The target is allowed in the candidate universe because discovery sources may
return it. The target is always excluded from the final peer set:

```text
target_in_peer_comparable_set = false
```

This policy is part of `comparable-product-set-v0.1`. A future change requires a
new contract version.

## 12. Supporting business evidence

| Evidence | V0.1 role | Prohibited inference |
|---|---|---|
| Product type | Candidate/supporting eligibility evidence | Same type does not mean comparable; different type does not mean not comparable |
| Category | Supporting evidence | Same broad Amazon category does not create membership; different category does not automatically exclude |
| Keyword relationship | Supporting directional evidence | Same keyword, co-occurrence, or related-product status does not create membership |
| Variation relationship | Supporting structural evidence | Parent/child, sibling, or same family does not create membership |
| Brand | Supporting analysis attribute | Same or different brand alone does not decide membership |
| Attributes/features | Future comparability enhancement evidence | No capacity, size, material, feature, or use-case fuzzy/AI inference in V0.1 |
| Provider/API/dataset membership | Lineage and candidate discovery only | Same Provider response, result page, or dataset does not create membership |

Price, sales, BSR, review count, rating, and revenue are downstream comparison
metrics. V0.1 contains no percentage-band eligibility rules for them.

## 13. Business membership assertion

Final membership requires a governed comparability assertion. The following is a
conceptual contract, not a production dataclass or evaluator:

| Assertion field | Requirement |
|---|---|
| Assertion identity | Stable content identity under the approved future authority |
| Target | Exact Canonical target `ProductIdentity` |
| Candidate | Exact Canonical candidate `ProductIdentity` |
| Marketplace | Exact shared marketplace |
| Scope | Exact governed analysis scope |
| Context references | Existing snapshot/run/observation context identifiers |
| Decision | `COMPARABLE`, `NOT_COMPARABLE`, or `UNRESOLVED` |
| Authority kind/source | The approved membership source and its version |
| Evidence references | Canonical/intelligence evidence supporting the decision |
| Contract version | `comparable-product-set-v0.1` |
| Provenance | Traceable assertion, evidence, transformation, and Provider lineage |

`COMPARABLE` enters the peer set. `NOT_COMPARABLE` enters excluded candidates with
its reason. `UNRESOLVED` enters unresolved candidates and cannot be collapsed into
exclusion or an empty set.

The repository currently has no approved authority that produces this assertion.
Consequently:

```text
CONTRACT DEFINED
MEMBERSHIP SOURCE BLOCKED
MEMBERSHIP EXECUTION BLOCKED
PRICE AGGREGATION BLOCKED
P0 BUSINESS DECISION REQUIRED
```

## 14. Result contract

A future V0.1-compatible result must conceptually expose:

```text
target_identity
marketplace
scope
snapshot/context references
comparable_members
excluded_candidates with reasons
unresolved_candidates with reasons
membership assertions
evidence references
contract version
quality issues
provenance
```

The result must make it possible to answer why each candidate was included,
excluded, or left unresolved. A Boolean alone is insufficient.

## 15. Missing, empty, and unresolved semantics

| Condition | Result semantics |
|---|---|
| Required set-level identity, marketplace, scope, or context is missing | `MISSING_INPUT`; no Comparable Product Set result |
| Candidate passes structural gates but lacks sufficient governed business authority | `UNRESOLVED`; retained in unresolved candidates |
| Approved assertion explicitly says `NOT_COMPARABLE` | Excluded with assertion and reason; not unresolved |
| Governed evaluation completes and every candidate has an explicit final disposition, with zero `COMPARABLE` decisions | Valid empty Comparable Product Set |
| No usable evidence exists and evaluation cannot complete | Missing/unresolved, never a valid empty set |

Normative distinctions:

```text
missing input != empty comparable set
unknown/unresolved != empty comparable set
explicit NOT_COMPARABLE != unresolved
valid evaluated zero-member set != unable to evaluate
```

An unqualified `[]` cannot express all of these states.

## 16. Member count, uniqueness, and ordering

Membership itself has no minimum sample-size requirement. Zero, one, or many
members can be valid after governed evaluation. Downstream statistics may define
their own sample-size contract; that policy cannot change membership.

Members are unique by full Canonical `ProductIdentity`. Duplicate governed inputs
that are contractually required to be unique are a quality failure and are not
silently deduplicated to hide an upstream error. Output ordering is the stable
Canonical product identity order. Ordering exists only for serialization,
fingerprinting, and debugging and never changes a decision.

## 17. Exclusion, unresolved, and quality reasons

The V0.1 conceptual reason vocabulary includes:

```text
WRONG_MARKETPLACE
TARGET_ITSELF
SCOPE_MISMATCH
SNAPSHOT_CONTEXT_MISMATCH
INVALID_IDENTITY
EXPLICIT_NOT_COMPARABLE
INSUFFICIENT_BUSINESS_EVIDENCE
UNRESOLVED_COMPARABILITY
```

These labels document required distinguishability; they do not introduce a
production enum. `INSUFFICIENT_BUSINESS_EVIDENCE` cannot be rewritten as
`EXPLICIT_NOT_COMPARABLE`.

## 18. Provider independence

XiYou, Sorftime, and any future Provider can supply observations, relationships,
candidate discovery, and replayable lineage. None defines comparability. The same
Canonical inputs and governed assertions must produce the same business membership
regardless of Provider order or identity.

Provider lineage is retained below the system-governed assertion:

```text
Comparable Product Set
  -> governed membership assertion
  -> assertion authority and contract/rule version
  -> supporting evidence references
  -> Canonical observations
  -> transformation and Provider/source evidence
```

## 19. Provenance and fingerprinting

Every member, exclusion, and unresolved disposition retains its assertion or
structural reason, evidence references, context references, contract version, and
provenance.

When implemented through existing fingerprint infrastructure:

- the input fingerprint must cover contract version, target identity, marketplace,
  scope, exact existing context references, candidate universe, assertions, and
  evidence references;
- the output fingerprint must cover the comparable, excluded, and unresolved
  dispositions plus quality issues and the contract version;
- all collections use canonical stable ordering before hashing; and
- Provider lineage or mapping insertion order changes that do not change governed
  semantic content must not change membership.

No fingerprint implementation is added by this task.

## 20. Versioning

The formal version is:

```text
comparable_product_set_contract_version = comparable-product-set-v0.1
```

A new version is required if product type becomes a hard gate, attribute rules are
added, variation sibling policy changes, AI comparability is introduced, target
inclusion changes, cross-market comparison is introduced, or membership authority
changes.

## 21. Comparable price boundary

The only permitted dependency direction is:

```text
governed Comparable Product Set
  -> COMPARABLE members only
  -> resolved member prices with compatible currency, marketplace, scope,
     period, measurement semantics, and acceptable quality
  -> comparable price aggregation
  -> minimum_comparable_price / maximum_comparable_price
```

`NOT_COMPARABLE`, `UNRESOLVED`, missing, invalid, or structurally ineligible
candidates cannot enter aggregation. Price does not flow backward to define
membership; a target-relative price threshold would create a circular contract.

Current readiness is explicit:

```text
minimum_comparable_price ready? NO — BLOCKED BY MEMBERSHIP SOURCE
maximum_comparable_price ready? NO — BLOCKED BY MEMBERSHIP SOURCE
```

No evaluator is registered or implemented by this contract task.

## 22. Open business decisions

### P0 — Membership assertion source

**P0 BUSINESS DECISION REQUIRED**

When a candidate satisfies valid Canonical identity, same marketplace, same scope,
same snapshot/context, and non-target structural gates, what mechanism finally
confirms that it is comparable to the target?

| Option | Model | Benefits | Costs and governance impact |
|---|---|---|---|
| A | Deterministic rule set | Reproducible and easy to audit | Requires explicit category/use-case rules; can be too broad or narrow |
| B | Manual/operator confirmation | Strong initial business control | Not fully automated; expensive at scale |
| C | AI-assisted assertion | Can interpret complex attributes and use cases | Requires a separate AI contract, confidence/evidence/versioning, and human-review policy; cannot enter the current deterministic engine directly |
| D | Hybrid hard gates plus AI/operator assertion | Preserves structural safety while handling business nuance | Highest governance and architecture complexity |

V0.1 does not select A, B, C, or D. This decision directly blocks comparable-price
aggregation and affects future competition comparison and scoring.

### P1 — Conditional rule design

If A or D is selected, define the governed, category-specific evidence predicates,
tie/unknown behavior, assertion authority, and rule version before execution.

### P2 — Conditional AI and workflow design

If C or D is selected, define a separate AI assertion contract, confidence and
evidence requirements, model/rule versioning, operator override, and review audit.
If B or D is selected, define the operator review lifecycle and identity of the
reviewing authority.

## 23. Examples

### Structurally eligible but unresolved

A US non-target candidate shares the exact scope and snapshot with the target and
has valid identity. It appears for the same keyword and has the same product-type
candidate. No approved assertion source exists. Result: structurally eligible,
`UNRESOLVED`, not a comparable member.

### Explicit comparable assertion

A same-context candidate passes all gates and an approved versioned authority emits
`COMPARABLE` with evidence references. Result: included as a comparable peer.

### Explicit not-comparable assertion

A same-context candidate passes all gates but has a governed `NOT_COMPARABLE`
assertion. Result: excluded with assertion and reason, not unresolved.

### Valid empty set

A governed evaluation completes for the entire candidate universe and every
eligible candidate is explicitly `NOT_COMPARABLE`. Result: valid set with zero
members.

### Missing context

The target scope or snapshot context is absent. Result: `MISSING_INPUT`; an empty
set is prohibited.

### Structural exclusions

A UK candidate for a US target is excluded as `WRONG_MARKETPLACE`. The target
returned by a Provider search is excluded as `TARGET_ITSELF`. Neither can become a
peer through a keyword, variation, price, or Provider relationship.

## 24. Security and implementation boundary

This contract is based exclusively on repository contracts, fixtures, and static
metadata. It consumes no network, credentials, runtime secrets, or paid API data.
It introduces no production evaluator, AI, Provider mapping, Connector,
Normalization, Workbook, scoring, Trend, or Variation Evidence Count behavior.
