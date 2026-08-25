# Sorftime Provider Contract and Migration Audit V0.1

Status: TASK-SP-040A complete; migration is blocked pending contract evidence
Audit date: 2026-08-25
Baseline: `d9e47579e6f9219b0747c7bba2914517a9892c35`
Decision: `NOT YET PROVEN`
Verdict: `BLOCKED — SORFTIME_CONTRACT_GAP`

## 1. Scope and non-operation statement

This is a contract-discovery, dependency-audit, and migration-design artifact. It does not implement, configure, authenticate, or execute a provider. No connector behavior, Canonical semantics, Intelligence behavior, scoring, report schema, renderer, secret handling, or default report version changed.

Provider operation counts for this audit are:

- Sorftime provider operations: `0`
- XiYou provider operations: `0`

The answer to the completion question is **NOT YET PROVEN**. Sorftime's current official public pages establish a broad capability catalogue, 14 named Amazon marketplaces, usage-based pricing, and API/CLI contract correspondence. They do not publicly establish enough field-level response schema, grain, pagination/completeness, history, domain-ID, missingness, or per-interface cost semantics to prove a safe migration of the critical Canonical requirements. This audit therefore fails closed.

## 2. Evidence boundary

### 2.1 Authoritative external sources reviewed

- [Sorftime official API/CLI service catalogue](https://www.sorftime.com/en-US/api): names the Amazon category, product, review, keyword, monitoring, and account interfaces; describes `CategoryRequest` as Best Sellers with history, `CategoryProducts` as all hot-selling category products, `AsinSalesVolume` as officially disclosed child sales, and identifies usage-based billing.
- [Sorftime official CLI page](https://www.sorftime.com/zh-CN/cli): states that CLI method names, request parameters, and returned structures correspond to the API; shows JSON output with `Code`, `Data`, and `RequestLeft`; and demonstrates a `ProductRequest` with a numeric `domain` argument.

The CLI is a legitimate future contract-discovery option because Sorftime states that it mirrors the API. SP-040A did not install, configure, authenticate, or execute it.

### 2.2 Repository evidence reviewed

The audit traced the production flow and contracts through:

- `connectors`, `adapters`, `data_cleaning`, `contracts`, and provider capability declarations;
- `production_pipeline`, recovery/checkpoint logic, batch selection, real-data validation, and organic keyword discovery;
- Competition, Category Product Map, Buyer Need, Opportunity, Market Report V0.1/V0.2, and operator delivery;
- checked-in sanitized XiYou and Sorftime fixtures and all related tests;
- existing provider, Canonical, provenance, field-coverage, and V0.2 contract documentation.

Checked-in Sorftime fixtures prove how the existing offline adapter behaves against those fixtures. They do **not** prove the current live Sorftime API contract. Existing `provider-tool://sorftime/...` operations are logical placeholders, not documented production HTTP endpoints.

### 2.3 Evidence limits

The official public pages do not expose a complete unauthenticated field catalogue or a versioned schema for the audited interfaces. The official page's labels and illustrative JSON are capability evidence, not proof of every response field. Third-party wrappers, mirrors, GitHub repositories, and search snippets were not promoted to authoritative contract evidence.

## 3. Repository dependency inventory

Repository-wide case-insensitive inventory at the baseline found:

- 280 Python source modules, of which 26 mention XiYou and 254 do not;
- 34 Python test modules mentioning XiYou;
- 55 documentation files mentioning XiYou;
- 115 XiYou-referencing source/test/document files in total.

Tests and historical validation documents are migration inputs but are not runtime provider coupling. The 26 source modules are classified below.

| ID | File/module | Consumer | Provider-specific dependency | Canonical concept | Criticality | Sorftime candidate | Classification / risk |
|---|---|---|---|---|---|---|---|
| XD-001 | `adapters/__init__.py` | import surface | XiYou adapter export | adapter selection | Low | export future Sorftime mapper | `DEAD_OR_VALIDATION_ONLY`; low |
| XD-002 | `adapters/xiyou_snapshot.py` | snapshot adapter | XiYou snapshot envelope | raw evidence | Medium | Sorftime snapshot adapter | `XIYOU_COUPLED_REPLACEABLE`; medium |
| XD-003 | `adapters/xiyou_v0_1.py` | Canonical mapping | XiYou roots, fields, sentinels, ranks, position codes | product/keyword/rank | High | separate Sorftime mapper | `XIYOU_COUPLED_REPLACEABLE`; high |
| XD-004 | `batch_product_selection/models.py` | batch request | default and validation require `xiyou` | provider selection | High | explicit provider ID | `XIYOU_COUPLED_REQUIRES_REFACTOR`; high |
| XD-005 | `competition_analysis/builder_v0_1.py` | diagnostic text | XiYou-specific limitation wording | variation evidence | Low | provider-neutral wording later | `DEAD_OR_VALIDATION_ONLY`; low |
| XD-006 | `connectors/__init__.py` | import surface | XiYou exports | connector selection | Low | existing generic exports | `DEAD_OR_VALIDATION_ONLY`; low |
| XD-007 | `connectors/xiyou_client.py` | live client | XiYou environment/header/auth contract | transport | High | future Sorftime client | `XIYOU_COUPLED_REPLACEABLE`; high |
| XD-008 | `connectors/xiyou_v0_1.py` | provider declaration | XiYou operations, endpoints, payload kinds, capabilities | provider-to-Canonical | High | future Sorftime operations | `XIYOU_COUPLED_REPLACEABLE`; high |
| XD-009 | `data_cleaning/cli.py` | operator CLI | XiYou provider/default options | cleaning entrypoint | Medium | explicit registry selection | `XIYOU_COUPLED_REQUIRES_REFACTOR`; medium |
| XD-010 | `organic_keyword_discovery/__init__.py` | legacy workflow exports | XiYou-specific workflow types | keyword discovery | Low | `ASINRequestKeyword` candidate | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; medium |
| XD-011 | `organic_keyword_discovery/__main__.py` | legacy CLI | XiYou credit gates/options | cost control | Medium | unknown Sorftime cost model | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-012 | `organic_keyword_discovery/capture.py` | live capture | XiYou operations and request/response shapes | reverse keywords | High | `ASINRequestKeyword` | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-013 | `organic_keyword_discovery/holdout_cli_v0_1.py` | holdout CLI | XiYou-specific controls | keyword validation | Medium | no proven parity | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-014 | `organic_keyword_discovery/holdout_v0_1.py` | holdout runner | XiYou pagination, credits, fields | cohort/reverse keywords | High | `ASINRequestKeyword` | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-015 | `organic_keyword_discovery/pilot.py` | pilot runner | XiYou acquisition assumptions | buyer-need evidence | Medium | unproven keyword set | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-016 | `organic_keyword_discovery/runner.py` | keyword runner | XiYou client/result semantics | buyer-need evidence | High | unproven keyword set | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-017 | `organic_keyword_discovery/temporal_holdout_cli_v0_1.py` | temporal CLI | XiYou credit controls | temporal validation | Medium | unknown Sorftime cost/history | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-018 | `organic_keyword_discovery/temporal_holdout_v0_1.py` | temporal holdout | XiYou pagination, credits, country, page size | temporal keyword evidence | High | keyword history candidates | `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`; high |
| XD-019 | `production_pipeline/cli.py` | production CLI | XiYou default/provider presentation | provider selection | High | explicit provider config | `XIYOU_COUPLED_REQUIRES_REFACTOR`; high |
| XD-020 | `production_pipeline/models.py` | run contract | provider default is `xiyou`; XiYou-shaped credit semantics | provider/cost | High | provider-neutral run policy | `XIYOU_COUPLED_REQUIRES_REFACTOR`; high |
| XD-021 | `production_pipeline/orchestrator.py` | production runtime | rejects non-XiYou; constructs XiYou transport; hard-codes `asin_info`, `asin_keywords`, request body, environment, replay | all live acquisition | Critical | generic acquisition plan + Sorftime provider | `XIYOU_COUPLED_REQUIRES_REFACTOR`; critical |
| XD-022 | `production_pipeline/providers.py` | acquisition helpers | `country`, page 1/20, `last7days`, traffic sort, XiYou reason allowlist, `cost_credits` | reverse keyword/cost/errors | Critical | Sorftime-specific planner behind neutral interface | `XIYOU_COUPLED_REQUIRES_REFACTOR`; critical |
| XD-023 | `production_pipeline/recovery.py` | checkpoint/replay | imports XiYou operations; provider ID and operation set hard-coded | resumability/idempotence | Critical | provider-qualified operation catalogue | `XIYOU_COUPLED_REQUIRES_REFACTOR`; critical |
| XD-024 | `real_data_validation/live_pipeline.py` | validation runtime | XiYou live client/operations | live acceptance | High | Sorftime validation harness later | `XIYOU_COUPLED_REQUIRES_REFACTOR`; high |
| XD-025 | `real_data_validation/report.py` | validation report | XiYou provider labels/expectations | validation evidence | Medium | provider-neutral evidence | `XIYOU_COUPLED_REQUIRES_REFACTOR`; medium |
| XD-026 | `schemas/canonical_mapping.py` | schema inventory | XiYou source-field paths | source mapping metadata | Medium | separate Sorftime mapping specs | `XIYOU_COUPLED_REPLACEABLE`; medium |

Classification totals are: 5 `XIYOU_COUPLED_REPLACEABLE`, 9 `XIYOU_COUPLED_REQUIRES_REFACTOR`, 9 `XIYOU_ONLY_NO_CURRENT_REPLACEMENT`, 3 `DEAD_OR_VALIDATION_ONLY`, and 0 XiYou-referencing modules classified as `PROVIDER_NEUTRAL`.

### 3.1 Provider-neutral boundary already present

The migration should reuse, not duplicate:

- `DataProvider`, `AdapterBackedProvider`, `ProviderCapability`, `ProviderOperation`, `ProviderConfig`, injected transports, `ProviderRegistry`, and `ProviderResolver`;
- `ProviderFetchStatus` (`RETURNED`, `EMPTY`, `FIELD_MISSING`) and `ProviderErrorCode` (`CONFIGURATION`, `AUTHENTICATION`, `RATE_LIMIT`, `TIMEOUT`, `NETWORK`, `BAD_RESPONSE`, `SCHEMA_MISMATCH`, `PROVIDER_UNAVAILABLE`, `FIELD_UNAVAILABLE`, and resolution errors);
- the existing Adapter → `CanonicalEvidenceBundle` → Cleaning boundary;
- all Canonical, Competition, Buyer Need, Opportunity, Market Report, and delivery models.

The main architectural violation is composition: the generic provider foundation exists, but the production orchestrator bypasses generic composition by constructing a concrete `XiYouProvider` and XiYou request plans.

## 4. Canonical requirement inventory

The inventory starts from existing repository consumers, not Sorftime. `CURRENT` means necessary to reproduce today's bounded live V0.2 path; `TARGET` means already represented/consumed by current Canonical, Intelligence, Category Map, or report contracts and needed for semantic completeness; `FUTURE` is data-gated enrichment and not an initial acceptance prerequisite.

| ID | Canonical datum / semantic definition | Entity / time / marketplace grain | Parent-child / denominator rule | Nullable | Priority | Current source |
|---|---|---|---|---|---|---|
| C01 | ASIN: normalized 10-character product identity | product; instant; one marketplace | identity at declared grain | No | CURRENT | XiYou `asin_info` |
| C02 | Marketplace: normalized report/product/query scope | marketplace; request + observation | never infer from currency | No | CURRENT | operator + XiYou `country` |
| C03 | Title: observed listing title candidate | product; instant | child/family value not interchangeable | Yes | CURRENT | XiYou `asin_info` |
| C04 | Brand: observed brand candidate | product; instant | not seller/manufacturer substitute | Yes | TARGET | existing Sorftime fixture |
| C05 | Category identity: node/name/path candidate | category/product; dated when ranked | category granularity explicit | Yes | CURRENT | operator category + XiYou BSR context |
| C06 | Category-universe membership | category × product × observation window | declared child/parent/family grain | Yes | TARGET | no current complete source |
| C07 | Category completeness and denominator | exact cohort/window | total, included, excluded, unknown, pagination | Yes | TARGET | current explicit input cohort only |
| C08 | Parent ASIN: explicit valid parent identity | product relationship; observed time | self-parent is not an edge | Yes | TARGET | XiYou variations / fixture |
| C09 | Child ASIN variation edge | parent-child relationship; observed time | explicit unique edge only | Yes | TARGET | XiYou variations / fixture |
| C10 | Variation property and count | child/family; observed time | count policy must name rows/edges/children | Yes | TARGET | XiYou/Sorftime fixtures |
| C11 | Structured product attributes | child/product; instant | source fact; conflicts retained | Yes | TARGET | existing Sorftime fixture |
| C12 | Fulfillment | product/offer; instant | listing/offer scope explicit | Yes | TARGET | existing Sorftime fixture |
| C13 | Seller identity | seller/offer; instant | never reuse brand | Yes | FUTURE | unconfirmed |
| C14 | Current price | product/offer; instant | no family aggregation by default | Yes | CURRENT | XiYou `asin_info` |
| C15 | Price currency | metric × marketplace | ISO currency must be explicit/governed | Yes | CURRENT | XiYou response/context |
| C16 | Rating | product; instant; five-star unit | no averaging across incompatible grains | Yes | CURRENT | XiYou `asin_info` |
| C17 | Review count | product; instant | listing total, not fetched-review count | Yes | CURRENT | XiYou `asin_info` |
| C18 | Estimated product monthly sales | product; documented period/method | estimate label and product grain mandatory | Yes | TARGET | existing Sorftime fixture; method unresolved |
| C19 | Official disclosed child sales | child × date/window | not equal to estimated product sales | Yes | TARGET | no current live source |
| C20 | Revenue estimate | product/category × period | price × sales only under approved method | Yes | TARGET | unavailable in current V0.2 |
| C21 | BSR/rank value | product × exact category × date | rank context required | Yes | TARGET | XiYou BSR |
| C22 | BSR context | category ID/name/root + date/precision | ranks across categories not comparable | Yes | TARGET | XiYou BSR |
| C23 | Listing date/age | product × observation date | age is derived from governed listing date | Yes | FUTURE | not current live path |
| C24 | Price history | product × dated observation | no retrieval-time substitution | Yes | TARGET | XiYou info trends |
| C25 | Rating history | product × dated observation | exact time grain/lookback required | Yes | TARGET | XiYou info trends |
| C26 | Review-count history | product × dated observation | exact time grain/lookback required | Yes | TARGET | XiYou info trends |
| C27 | Sales history | product/child × dated period | method and grain preserved per series | Yes | TARGET | XiYou/Sorftime candidates |
| C28 | Category trend | category × dated period | category identity and denominator required | Yes | TARGET | no current live source |
| C29 | Keyword identity/text | keyword × marketplace × locale | raw and normalized text distinct | No | CURRENT | XiYou reverse keywords |
| C30 | Keyword locale | keyword identity | not inferred from country without policy | No | CURRENT | operator metadata; provider unavailable |
| C31 | ASIN reverse-keyword relationship | product → keyword × query window | direction, channel, rank, pagination retained | Yes | CURRENT | XiYou `asin_keywords` |
| C32 | Category reverse keywords | category → keyword × query window | not equivalent to ASIN reverse lookup | Yes | FUTURE | no current path |
| C33 | Keyword search volume | keyword × explicit period | provider estimate/method/unit retained | Yes | TARGET | XiYou keyword info |
| C34 | Search-volume trend | keyword × dated period | trend points, grain, and lookback explicit | Yes | TARGET | XiYou keyword trends |
| C35 | CPC and currency | keyword × marketplace × period | bid/average concepts not conflated | Yes | TARGET | XiYou keyword info |
| C36 | Competition difficulty | keyword × provider scale/period | provider scale/method mandatory | Yes | TARGET | XiYou keyword info; method unresolved |
| C37 | Keyword-result products | keyword → product × result window | bounded result set is not a market universe | Yes | TARGET | XiYou forward query |
| C38 | Current keyword-product rank/channel | keyword-product × time/channel | organic/sponsored codes remain distinct | Yes | TARGET | XiYou forward/reverse query |
| C39 | ASIN keyword rank history | keyword-product × dated time/channel | exact historical ranking semantic | Yes | TARGET | XiYou trend candidates |
| C40 | Raw review evidence | review × product/variant × date | raw text cannot be replaced by a summary | Yes | FUTURE | existing Sorftime fixture only |
| C41 | Provider review summary | product × provider method/window | separate non-authoritative enrichment | Yes | FUTURE | no current canonical authority |
| C42 | Evidence/provenance/availability envelope | every observation/query | exact request, source grain, missingness, conflict | No | CURRENT | existing Canonical contracts |

Totals: 42 concepts; 12 CURRENT, 25 TARGET, and 5 FUTURE. The unresolved semantics are identified in Sections 6 and 7; no unresolved value may be converted to zero or an inferred equivalent.

## 5. Official Sorftime interface catalogue audit

`Mapping` below evaluates whether the official public contract is sufficient for Canonical integration, not whether the marketing catalogue names a similar feature.

| Interface | Official public description | Initial migration role | Mapping |
|---|---|---|---|
| `CategoryTree` | category tree | category identity discovery | PARTIAL |
| `CategoryRequest` | category Best Sellers with historical lookup | bounded ranked cohort candidate | PARTIAL |
| `CategorySearchFromName` | find category by name | operator category resolution | PARTIAL |
| `CategoryProducts` | all hot-selling category products | category universe candidate | UNPROVEN |
| `CategoryTrend` | market historical trend | category trend candidate | PARTIAL |
| `ProductRequest` | product details including product trend | current product facts/history candidate | PARTIAL |
| `ProductSearchFromName` | search product by name | future discovery only | PARTIAL |
| `ProductSearch` | product search | future discovery only | PARTIAL |
| `AsinSalesVolume` | officially disclosed child sales | separate child-sales metric | PARTIAL |
| `ProductVariations` | product child data | family topology candidate | PARTIAL |
| `ProductRealtimeRequest` | realtime product query | future refresh | PARTIAL |
| `ProductRealtimeRequestStatusQuery` | realtime product-query status | future async workflow | PARTIAL |
| `ProductReviewsQuery` | product reviews | raw-review candidate | PARTIAL |
| `ProductReviewsCollection` | realtime review collection | future enrichment | PARTIAL |
| `ProductReviewsCollectionStatusQuery` | review collection status | future async workflow | PARTIAL |
| `ProductCustomersSay` | CustomerSay review analysis | non-authoritative enrichment only | PARTIAL |
| `SimilarProductFeature` | similar-product feature analysis | future vocabulary enrichment | PARTIAL |
| `KeywordQuery` | keyword query | keyword discovery candidate | PARTIAL |
| `KeywordSearchResults` | keyword search-result products for recent 15 days | bounded result-products candidate | PARTIAL |
| `KeywordRequest` | keyword detail including volume/CPC trend | keyword metrics candidate | PARTIAL |
| `KeywordSearchResultTrend` | keyword result-product trend | result trend candidate | PARTIAL |
| `CategoryRequestKeyword` | category reverse keywords | future category-keyword evidence | PARTIAL |
| `ASINRequestKeyword` | ASIN reverse keywords | current Buyer Need input candidate | PARTIAL |
| `KeywordProductRanking` | historical keyword result products | historical product-ranking candidate | PARTIAL |
| `ASINKeywordRanking` | ASIN rank trend under keyword | ASIN-keyword rank history candidate | PARTIAL |
| `KeywordExtends` | extended keywords | future discovery only | PARTIAL |

The audit also reviewed `ProductSearch`, realtime product/status, collection/status, and the review-analysis interfaces to determine whether they belong in the minimum set. They do not.

## 6. Canonical-to-Sorftime coverage matrix

| Canonical requirement(s) | Sorftime candidate / public semantic | Status | Required transform and match finding | Blocking? |
|---|---|---|---|---|
| C01 ASIN | `ProductRequest` request `asin` in official CLI example | PARTIAL | normalize and verify observed identity; response identity/schema unproven | YES |
| C02 marketplace | numeric `domain`; 14 named sites | PARTIAL | explicit offline marketplace↔domain map; only example context for US/domain 1 | YES |
| C03 title | `ProductRequest` product detail | PARTIAL | map only versioned response field; nullability unproven | YES |
| C04 brand | `ProductRequest` candidate | UNPROVEN | no authoritative public field/schema | NO for current; YES for target |
| C05 category identity | `CategoryTree`, `CategorySearchFromName`, `ProductRequest` | PARTIAL | node/name/path normalization; identity and hierarchy schema unproven | YES |
| C06-C07 category universe/denominator | `CategoryProducts`, `CategoryRequest` | UNPROVEN | prove ranked-vs-complete set, limits, pagination, totals, history, product grain | YES |
| C08-C10 parent/child/variations | `ProductVariations`, `AsinSalesVolume` | PARTIAL | explicit edges, child identity, self-parent, count, property, sentinel policies unproven | YES |
| C11 attributes | `ProductRequest` candidate | UNPROVEN | approved field-by-field mapper only | YES for target |
| C12 fulfillment | `ProductRequest` candidate | UNPROVEN | offer/listing scope and enum semantics unproven | YES for target |
| C13 seller | no specifically documented field/interface | NO_MATCH | keep unavailable; do not substitute brand | NO for initial |
| C14-C17 price/currency/rating/review count | `ProductRequest` and product trend label | PARTIAL | field names, currency source, units, nullability, current-vs-history shape unproven | YES |
| C18 estimated product sales | `ProductRequest` product detail/trend | PARTIAL | preserve provider estimate; exact method, grain, and period unproven | YES for target |
| C19 official child sales | `AsinSalesVolume` explicitly described as official disclosed child sales | PARTIAL | distinct metric; response/date/grain/nullability schema unproven | YES for target |
| C20 revenue | no public field-level evidence | NO_MATCH | only derive later under governed calculation policy | YES for target |
| C21-C22 BSR/rank/context | `ProductRequest`, `CategoryRequest` are possible candidates | UNPROVEN | rank kind/category/root/date/precision not established | YES |
| C23 listing date/age | `ProductRequest` possible candidate | UNPROVEN | listing-date field and semantics not public | NO for initial |
| C24-C27 product histories | `ProductRequest` “includes product trend”; `AsinSalesVolume` | PARTIAL | series fields, price/rating/review/sales split, grain, time grain, lookback unproven | YES |
| C28 category trend | `CategoryTrend` | PARTIAL | metric contents, denominator, time grain, lookback unproven | YES |
| C29 keyword identity | keyword interfaces accept/query keywords by name | PARTIAL | verify response identity and normalization source | YES for target |
| C30 keyword locale | no public locale field | NO_MATCH | operator policy may supply locale, but provider cannot be credited | YES for keyword identity |
| C31 ASIN reverse keywords | `ASINRequestKeyword` | PARTIAL | result fields, direction, rank/channel, period, totals and pagination unproven | YES |
| C32 category reverse keywords | `CategoryRequestKeyword` | PARTIAL | category identity, result semantics, period and pagination unproven | NO for initial |
| C33-C35 search volume/trend/CPC | `KeywordRequest` explicitly names search-volume/CPC trend | PARTIAL | values, units, currency, estimate method, period, series schema unproven | YES for target |
| C36 difficulty | `KeywordQuery`/`KeywordRequest` possible candidates | UNPROVEN | scale and method not documented | NO for current; YES for target |
| C37 result products | `KeywordSearchResults` explicitly limited to recent 15 days | PARTIAL | retain bounded window; totals, pages, completeness, rank schema unproven | YES for target |
| C38-C39 rank/channel/history | `KeywordProductRanking`, `ASINKeywordRanking`, `KeywordSearchResultTrend` | PARTIAL | rank basis, channel codes, time grain, lookback, list completeness unproven | YES for target |
| C40 raw reviews | `ProductReviewsQuery`; collection/status pair | PARTIAL | prove raw text, review/product/variant identity, dates, pagination and missingness | NO for initial |
| C41 provider summary | `ProductCustomersSay` | PARTIAL | keep separately labeled; cannot replace C40 | NO |
| C42 provenance/availability | CLI example `Code`, `Data`, `RequestLeft`; Canonical system metadata | PARTIAL | adapter must add retrieval, requested/observed identity, grain, mapping, raw ref, missing/conflict states | YES |

### 6.1 Required summary coverage matrix

| Capability | Current Need | Current Provider | Sorftime Candidate | Mapping | Blocking? |
|---|---|---|---|---|---|
| Product details | identity/current facts | XiYou | `ProductRequest` | PARTIAL | YES |
| Variations | family grain/topology | XiYou + offline fixture | `ProductVariations` | PARTIAL | YES |
| Category products | universe/denominator | explicit input cohort only | `CategoryProducts`, `CategoryRequest` | UNPROVEN | YES |
| Category trends | historical market context | unavailable live | `CategoryTrend` | PARTIAL | YES |
| Sales | distinct estimate/official child metrics | limited/unavailable report projection | `ProductRequest`, `AsinSalesVolume` | PARTIAL | YES |
| Price history | dated product metric | XiYou trend capability | `ProductRequest` | PARTIAL | YES |
| Rating/reviews | current counts/ratings | XiYou | `ProductRequest` | PARTIAL | YES |
| BSR/rank history | contextual rank series | XiYou | no proven exact candidate | UNPROVEN | YES |
| ASIN keywords | current Buyer Need input | XiYou | `ASINRequestKeyword` | PARTIAL | YES |
| Category keywords | future/category demand | unavailable live | `CategoryRequestKeyword` | PARTIAL | NO initial / YES target |
| Search volume | keyword estimate with period/method | XiYou | `KeywordRequest` | PARTIAL | YES target |
| CPC | keyword currency metric | XiYou | `KeywordRequest` | PARTIAL | YES target |
| Keyword ranking | contextual current/history | XiYou | `KeywordProductRanking`, `ASINKeywordRanking` | PARTIAL | YES target |
| Raw reviews | direct Buyer Need evidence option | offline fixture only | `ProductReviewsQuery` | PARTIAL | NO initial |

No critical field is classified `EXACT` because the public official contract does not establish all required field, grain, time, parent-child, nullability, and completeness semantics. Similar interface names are not sufficient.

## 7. Critical semantic findings and blocker register

| Gap | Status | Finding / required proof | Risk |
|---|---|---|---|
| SG-01 product identity | PARTIAL | Request ASIN is shown, but observed response identity and mismatch behavior are not publicly specified. | cross-product contamination |
| SG-02 parent/child | PARTIAL | `ProductVariations` exists, but edge direction, parent identity, self-parent, child completeness, and count semantics are not public. | mixed grain / double count |
| SG-03 marketplace/domain | PARTIAL | 14 sites are named; the complete numeric domain mapping is absent. Only an illustrative US request uses domain 1. | cross-market data |
| SG-04 sales | PARTIAL | Official child sales and estimated/product trend concepts are distinct; response fields, periods, methods, and grains are not public. | false equivalence |
| SG-05 category universe | UNPROVEN | “all hot-selling products” does not prove a complete category universe, ranking limit, page coverage, total semantics, or history. | invalid denominator and competitor population |
| SG-06 history | PARTIAL | Product/category/keyword trend interfaces exist, but series schema, time grain, timezone, lookback, and missing periods are unspecified publicly. | invalid trend comparison |
| SG-07 keyword relationships | PARTIAL | Reverse/query/ranking interfaces exist; pagination, result totals, rank basis, channels, period and empty semantics are unspecified. | Buyer Need evidence drift |
| SG-08 reviews | PARTIAL | Query/collection/summary capabilities exist; raw text fields, review identity, variant grain, pagination, and summary method are not proven. | summary substituted for evidence |
| SG-09 BSR/rank | UNPROVEN | No official public contract proves BSR value with category/root/date context or equivalence to any named trend. | incomparable ranks |
| SG-10 locale | NO_MATCH | No public response locale mapping was established. | unstable keyword identity |
| SG-11 revenue | NO_MATCH | No documented exact canonical revenue source was established. | fabricated economics |
| SG-12 availability | PARTIAL | A success envelope example exists; field omission, explicit null, empty, unsupported, partial, error, and rate-limit behavior per interface are not fully documented. | missing converted to zero |
| SG-13 cost | UNPROVEN | Usage billing and remaining-request example exist, but per-interface units/costs, batch billing, polling costs, and universal balance fields are unknown. | uncontrolled spend |

SG-05 alone triggers the task's blocking rule: the Category Product Map denominator and competitor population cannot be reproduced safely from public contract evidence. SG-06 and SG-09 independently trigger the historical-data blocker.

## 8. Marketplace/domain mapping candidate

The project accepts normalized uppercase marketplace text and the current production tests validate `US`. Sorftime publicly names the following Amazon sites. This is only a candidate identity table; numeric domain IDs remain `UNKNOWN` except that the official CLI illustration associates its US example with `domain 1`. That illustration is not sufficient proof for a complete production mapping.

| Project marketplace | Sorftime named site | Sorftime domain ID | Status |
|---|---|---|---|
| US | United States | 1 (illustrative example only) | PARTIAL |
| UK | United Kingdom | UNKNOWN | UNPROVEN |
| DE | Germany | UNKNOWN | UNPROVEN |
| FR | France | UNKNOWN | UNPROVEN |
| IN | India | UNKNOWN | UNPROVEN |
| CA | Canada | UNKNOWN | UNPROVEN |
| JP | Japan | UNKNOWN | UNPROVEN |
| ES | Spain | UNKNOWN | UNPROVEN |
| IT | Italy | UNKNOWN | UNPROVEN |
| MX | Mexico | UNKNOWN | UNPROVEN |
| AE | United Arab Emirates | UNKNOWN | UNPROVEN |
| AU | Australia | UNKNOWN | UNPROVEN |
| BR | Brazil | UNKNOWN | UNPROVEN |
| SA | Saudi Arabia | UNKNOWN | UNPROVEN |

SP-040B must freeze only evidence-backed mappings in fixtures/DTO contract metadata; SP-040D/E must reject unknown mappings before transport.

## 9. Provenance, availability, and missingness design

### 9.1 Reuse the existing evidence model

Every Sorftime result must enter the existing `RawEvidenceRecord`, `TransformationProvenance`, `Provenance`, observation/query record, and `CanonicalEvidenceBundle`. The required shape is:

| Requirement | Existing destination | Sorftime rule |
|---|---|---|
| provider | `provider` | stable `sorftime`, never payload free text |
| interface/method | `source_tool` / operation | exact versioned interface name |
| retrieval time | `retrieved_at` | connector clock with timezone; not observation time |
| marketplace | request/subject scope | mapped domain plus normalized marketplace; both retained |
| requested identity | sanitized request | ASIN/category/keyword only; no credential material |
| observed identity | product/keyword/category identity + source record identity | validate equality or record conflict |
| source grain | subject/scope/time/rank context | product/child/category/keyword/review and period explicit |
| transformation | mapping/code versions and run IDs | Sorftime-specific mapper, existing Canonical model |
| availability/missingness | value presence, result status, fetch status | preserve null/missing/empty/error |
| conflict status | existing conflict/resolution records | do not resolve inside connector |
| immutable evidence | content reference/fingerprint + raw reference | sanitized, content-addressed evidence boundary |

### 9.2 Mapping to existing states

No new production enum is proposed in this audit.

| Provider outcome | Existing project representation |
|---|---|
| successful present field | `ProviderFetchStatus.RETURNED`, `PresenceStatus.PRESENT` |
| successful directional empty list | `ProviderFetchStatus.EMPTY`, query `EMPTY`/`QUERY_RETURNED_EMPTY` semantics |
| field omitted | `ProviderFetchStatus.FIELD_MISSING`, `PresenceStatus.MISSING` |
| explicit JSON null | `PresenceStatus.EXPLICIT_NULL` |
| documented unsupported capability | capability unavailable / `FIELD_UNAVAILABLE` |
| authentication failure | `ProviderErrorCode.AUTHENTICATION` |
| rate limit | `ProviderErrorCode.RATE_LIMIT` |
| provider/network/timeout/bad schema | matching existing sanitized error code |

Descriptive terms such as “not returned” or “unsupported” may appear in diagnostics, but are not new runtime enum values. Missing, omitted, unsupported, partial, error, and rate-limited values never become numeric zero.

## 10. Cost-risk model

Official evidence establishes usage-based billing, account balance/usage interfaces (`CoinQuery`, `CoinStream`, `RequestStreamMonth`), and an illustrative `RequestLeft` response member. It does not prove that every request returns remaining balance or that interfaces share a cost.

| Planned slice | Cost risk | Evidence-based control |
|---|---|---|
| `ProductRequest` for N ASINs | UNKNOWN; batching and billing unit unproven | contract-test batch limits; cache by marketplace/ASIN/freshness |
| `ASINRequestKeyword` per ASIN | Potentially high because current pipeline loops per ASIN | bounded pages/keywords; cache by ASIN/window; no rerun on deterministic errors |
| `CategoryProducts` / `CategoryRequest` | Potentially high for pagination/history | require total/page/cost contract before universe crawl; cache category snapshots |
| trend interfaces | Potentially high with ASIN × metric × window expansion | request only report-required windows; immutable shared cache |
| realtime collection/status pairs | Potentially high due start + polling | exclude from minimum; bounded status polling and idempotency later |
| reviews | Potentially high due pages and collection | future-only; cache raw pages; separate collection from query |

All numeric cost estimates, per-interface credits, polling charges, batch discounts, and retry charges remain `UNKNOWN`. A future connector must record provider-reported cost/balance only when the exact contract proves its meaning; absence remains unknown, not zero.

## 11. Minimum and future interface sets

### 11.1 Minimum V0.2 Acceptance Set

The current production V0.2 path receives an explicit ASIN cohort and explicit category name. It executes one product acquisition followed by one reverse-keyword acquisition per ASIN, then projects unsupported market economics, true-competitor membership, distributions, and competitor details as unavailable. Therefore the smallest **provisional** interface set for reproducing today's bounded output is:

1. `ProductRequest` — product identity/current title/price/rating/review-count candidates.
2. `ASINRequestKeyword` — product-to-keyword relationships used by Buyer Need V0.3.

This set is not approved for implementation/live acceptance until the blockers for fields, marketplace, pagination, empty/error behavior, and provenance are resolved. `CategoryProducts` is not added merely to make the list look complete: it becomes mandatory only when the Category Product Map/competitor universe is promoted from today's explicit input cohort to a provider category universe. At that point SG-05 must be resolved first.

### 11.2 Future Enrichment Set

- category discovery/universe/trend: `CategoryTree`, `CategorySearchFromName`, `CategoryRequest`, `CategoryProducts`, `CategoryTrend`;
- product family/sales/history: `ProductVariations`, `AsinSalesVolume`;
- keyword demand/rank: `KeywordRequest`, `KeywordSearchResults`, `KeywordSearchResultTrend`, `CategoryRequestKeyword`, `KeywordProductRanking`, `ASINKeywordRanking`, `KeywordQuery`, `KeywordExtends`;
- reviews/understanding: `ProductReviewsQuery`, `ProductReviewsCollection`, `ProductReviewsCollectionStatusQuery`, `ProductCustomersSay`, `SimilarProductFeature`;
- realtime refresh: `ProductRealtimeRequest`, `ProductRealtimeRequestStatusQuery`;
- discovery: `ProductSearch`, `ProductSearchFromName`.

## 12. Replacement architecture and XiYou preservation

Reuse the existing abstraction:

```text
explicit ProviderConfig / acquisition plan
        |
        +-- XiYouProvider -- XiYou mapper
        |
        +-- SorftimeProvider -- Sorftime DTO validator -- Sorftime mapper
                                      |
                                      v
                           CanonicalEvidenceBundle
                                      |
                    Cleaning / Intelligence / Market Report V0.2
```

Required design boundaries for later tasks:

1. Provider DTOs validate Sorftime envelope and fields without becoming Canonical models.
2. The Sorftime mapper owns field names, units, sentinel/null rules, domain mapping, identity validation, pagination, and source grain.
3. The generic connector owns sanitized transport, retries, errors, registry, explicit selection, and raw evidence capture.
4. Production orchestration requests Canonical capabilities or provider-neutral acquisition intents. It must not contain provider field names or endpoint payloads.
5. Recovery checkpoints are provider-qualified and operation-contract-versioned. A checkpoint from one provider must never replay as another.
6. Downstream Cleaning, Intelligence, V0.2, JSON/XLSX/Markdown remain unchanged unless a separately approved semantic correction is made.

Recommended XiYou state: **LEGACY**. It remains installed and fixture-tested for regression/replay and may be explicitly selected, but it should not be silently chosen, automatically used as fallback, or remain the default live provider. `FALLBACK` is not recommended until cross-provider equivalence and cost/consent policy are explicitly approved.

## 13. Test migration plan

### Contract fixtures

- sanitize and check in one success, empty, missing, explicit-null, malformed, authentication-error metadata-only, rate-limit metadata-only, and pagination fixture for each minimum interface;
- include observed/request identity mismatch and marketplace/domain mismatch fixtures;
- record source-contract date/version and remove all credential material.

### Mapper and semantic tests

- Sorftime DTO → existing Canonical observations for exact approved fields only;
- parent/self-parent/child, category, keyword direction, channel, time, unit, and currency grain tests;
- distinct tests for estimated product sales versus official child sales;
- missing/null/unsupported/error never become zero;
- provider summary never replaces raw review evidence;
- unrecognized fields/codes/sentinels fail closed or remain diagnostic.

### Determinism and parity

- identical fixtures produce byte-identical canonical semantic content and stable IDs;
- XiYou fixture → Canonical and Sorftime fixture → Canonical must satisfy shared downstream contracts only where the audit later marks equivalence; provider payload equality is irrelevant;
- preserve provider/method/period/grain differences even when numeric values happen to match.

### Downstream regression and accidental-network protection

- retain current Canonical, Cleaning, Competition, Category Map, Buyer Need, Opportunity, V0.1/V0.2, and renderer fixtures;
- run with provider credential/base-url variables removed and inject only fixture transports;
- patch/deny socket and HTTP transport construction in offline suites; assert provider operation counters remain zero;
- require an explicit, separate live gate in SP-040F/G. Unit, contract, mapper, parity, and regression suites must never enter it.

## 14. Proposed implementation sequence

1. **SP-040B — Official Contract Evidence + Sanitized Fixtures + Provider DTOs.** Obtain versioned official schema evidence without business integration; resolve minimum-interface domain, envelope, field, missingness, pagination, and cost contracts. If evidence remains unavailable, stop blocked.
2. **SP-040C — Sorftime Mapper to Existing Canonical Model.** Implement only proven minimum fields, grain/provenance/missingness rules, fixture tests, and provider parity contracts.
3. **SP-040D — Sorftime Client/Connector.** Replace logical placeholder operations with documented transport contracts, strict DTO validation, sanitized errors, bounded retry, cost evidence, and no downstream changes.
4. **SP-040E — Explicit Provider Selection + Pipeline/Recovery Integration.** Remove XiYou-only composition/request planners, add provider-qualified checkpoints, keep XiYou LEGACY and explicitly selectable, and preserve fixture-only default safety.
5. **SP-040F — Sorftime Minimal Live Smoke.** One bounded minimum-set smoke with a predeclared operation/cost ceiling and sanitized evidence.
6. **SP-040G — Sorftime V0.2 Full Live Acceptance.** Run only after SP-040F and contract gates pass; validate current V0.2 output and all post-live offline regressions.
7. **Later enrichment tasks.** Category universe, histories, reviews, and expanded keyword contracts each require separate semantic/cost acceptance before use.

No later task is started by this audit.

## 15. Acceptance decision

The repository already has the correct provider-neutral Canonical and downstream boundaries, so a migration need not fork the Intelligence Model or Market Report. However, the public official Sorftime contract is insufficient to prove critical field semantics, category-universe completeness, historical grains, BSR context, marketplace mappings, or missingness/cost behavior.

Safe answer: **NOT YET PROVEN**.
Final verdict: **BLOCKED — SORFTIME_CONTRACT_GAP**.

## 16. Offline validation record

All provider credential and base-URL environment variables were removed from the test subprocesses. No live flag was passed, pytest cache creation was disabled, and the test-created temporary directories were removed after completion.

- focused provider/Canonical/Cleaning/V0.1/V0.2 report boundaries: `355 passed, 124 subtests passed`;
- full repository suite: `1113 passed, 16 skipped, 497 subtests passed`;
- accidental-network protection: `PASS` — live entrypoints require explicit gates, relevant fixture tests mock or reject HTTP, no provider configuration was supplied, and provider operations remained zero.
