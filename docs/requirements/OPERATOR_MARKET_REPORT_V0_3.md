# Operator Market Report V0.3

## Ownership and compatibility

This is an additive, report-owned extension of the SP-043A integrated result.
The V0.1, V0.2, Semantic V2, Route V2, Competition and Opportunity public
contracts remain unchanged. Nothing in this module is passed upstream to an
intelligence engine. Report display rules and warning thresholds are not Route
classification rules, candidate gates, or release-acceptance thresholds.

The public entry point is `build_operator_market_report(integrated, profile=...)`.
It requires a bound SP-043A result, validates dataset/Semantic/Route IDs and
fingerprints, and emits `operator-market-report-v0.3`. The immutable report stores
canonical JSON. Its fingerprint includes configuration, metrics, hierarchy,
machine-readable explanations, human-review questions, and upstream lineage.
Human verdicts/notes must be null. The model never migrates prior decisions.

## Population and hierarchy

Released Route membership is authoritative. The builder rejects duplicate
members or disagreement with the released ASSIGNED partition. Every Route
belongs to exactly one report family. A family aggregates the union of its
mutually exclusive child Routes. Medians, growth and concentration are recomputed
from that union, not averaged from child metrics. Membership fingerprints bind
the source populations without publishing listing identifiers in the report.
An additional mechanism comparison rolls the same child Routes up within each
family. Its shares and efficiency use that family as denominator, so an operator
can compare fixing mechanisms across product forms without adding raw rows.
It is labeled as a non-additive alternative view, not extra membership.

Explicit report-profile rules match exact dimension/value pairs in listed order.
The supplied display profile keeps recessed/built-in independent, groups wall
children together, and preserves portable, hanging, tension and freestanding
architectures. Generic fallback uses an entire governed dimension-value tuple;
it does not split compound structured observations. An unspecified wall fixing
remains visibly evidence-limited and never becomes a mechanical/screw claim.
If architectural family evidence is absent, the generic family remains the
original structural description; no new architecture is invented.

UNCLASSIFIED and REVIEW_REQUIRED listings are excluded from Route/family totals.
Their overall exposure is shown, but family-specific exposure is UNAVAILABLE:
there is no reliable membership with which to allocate it.

## Metric policy

- Sample market totals cover the accepted export, not the total addressable market.
- Family/Route sales and revenue shares use the assigned population's observed
  sales/revenue. Unknown values are excluded, with explicit count/coverage context.
- Empty sets sum to zero under `EMPTY_SET_ZERO`; a nonempty set with no available
  observation is UNAVAILABLE, not zero.
- Price/review medians use nearest rank. Price bands are nonnegative, left-closed,
  right-open intervals, plus an unknown bucket. Generic USD boundaries are
  10/25/50/100. The supplied display profile uses 10/20/40. Labels are configuration
  choices, not inferred market segments or quality claims.
- Default review bands are 0–50, 51–200, 201–1000, and 1001+. The default low-review
  maximum is 50, inclusive. Show observed demand contribution and positive-sales
  listing count alongside review barriers. Low reviews alone do not imply opportunity.
- Demand efficiency is sales share divided by listing share using the same
  sales-known cohort. An unavailable/zero demand denominator is not replaced.
- New-product windows are inclusive 180 and 365 days. They overlap and must not
  be added. Explicit normalized age takes precedence. If age is missing, the
  governed observation date minus valid first-available date may be used, with
  derivation counts. Future/invalid dates remain unavailable. Unknown age is not
  old. Confirmed-new sales divided by all observed Route sales is a lower bound
  when age is missing; efficiency uses the age-and-sales-known cohort.
- Successful-entrant number/share remains UNAVAILABLE: there is no governed
  definition of success in the supplied system. No success threshold is introduced.
- Growth is `sum(current)/sum(current/(1+growth))-1` on valid paired observations,
  consistent with the released growth representation. Rates at or below -100%,
  zero prior-sales reconstruction and missing pairs are excluded and counted.
- Brand/seller display normalization is whitespace and case only. No corporate
  affiliation is inferred. Rank by observed sales, then listing count and name.
  Top 1/3/5 and long-tail shares state known-identity denominators and sales/identity
  coverage. Unknown identities do not silently join a named entity.

## Interpretation and decision readiness

Every opportunity fact carries a reason code, exact JSON pointer, value, and
role (support/context/concern). The model verifies the referenced value. Both
renderers localize the same facts and conclusion code; there is no LLM-generated
advice, semantic reclassification or hidden score.

The default report-warning policy requires at least 50% assigned-listing coverage,
80% observed sales coverage, and no more than 50% unassigned exposure for strong
Route research triage. These are explicit conservative presentation policies,
not existing release gates or claims of whole-category representativeness.

Priority research requires above-par demand efficiency and either largest Route
sales share or positive growth with sufficient reconstruction coverage. Low
priority requires below-par demand efficiency without positive observed growth
or above-par new-product efficiency. Otherwise the Route is watched, evidence is
insufficient, or it is explicitly a limited-coverage observation. The released
candidate identities/priorities are retained separately and are not rewritten.

Even when ready for Route comparison, the report is not launch-ready. Buyer
Needs remain unavailable without governed review/search-term inputs. Costs,
advertising expense and margin are not fabricated. Sample size, coverage and
uncertainty remain visible beside interpretation.

## Localization and delivery

The same presentation spec produces zh-CN (default) and en-US Markdown/XLSX.
Chinese includes all 15 sheets, business headers, known governed Route labels,
explanations, warnings, availability and eleven human questions. An unknown
translation is explicitly flagged, never silently relabeled semantically.
Technical identifiers and reason pointers belong in Audit.

The XLSX is an analytical snapshot calculated by the report builder, not a new
listing-data store. Regenerate when governed inputs change. Only the human
review fields are intended for operator decisions. Artifact Tool authors XLSX;
an independent read-only round trip checks every table cell, typed numbers,
blank human inputs and absence of executable source-text formulas. JSON,
localized Markdown, workbook content/format/table/validation representation,
hierarchy and all distribution layers are deterministic. Raw ZIP metadata is
recorded separately from semantic/content equality.

## Privacy

Private reports may contain aggregate brand/seller names but no ASIN-grain
listing records or titles. The private runner requires input/output paths to
resolve outside the repository and rejects unsafe category output keys. No
private report, corpus, named real entity, or machine-specific private path is
permitted in committed validation documentation. Sanitized tests use fixtures.

Technical acceptance never fills human answers or declares business-value PASS.
