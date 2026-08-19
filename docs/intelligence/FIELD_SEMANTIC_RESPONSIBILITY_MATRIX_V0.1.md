# Workbook Field Semantic Responsibility Matrix V0.1

## 1. Purpose and boundary

This audit separates two independent questions for all 157 Operator Workbook V0.2 fields:

1. **Acquisition coverage** — whether XiYou, Sorftime, an operator, or the system can supply the value (`AVAILABLE`, `PARTIAL`, `CALCULATED`, `UNAVAILABLE`, `UNKNOWN`).
2. **Semantic responsibility** — whether the field is source data, normalized source data, evidence, status, metadata, display, aggregation, a deterministic calculation, an existing score, an existing decision output, manual input, configuration, AI analysis, or still unresolved.

The acquisition status is copied unchanged from `API_FIELD_COVERAGE_MATRIX_V0.1.md`. In particular, its broad `CALCULATED` label means “system-produced”; it is **not** an instruction to register a formula in the Calculation Engine.

This task does not change the Workbook schema, Canonical contracts, provider mappings, intelligence logic, scoring rules, recommendation rules, or the existing 99-field calculation audit. It authorizes no new evaluator.

## 2. Controlled vocabulary

| Semantic class | Meaning and owner boundary |
|---|---|
| `SOURCE` | An external/provider business field whose normalized system representation is not yet confirmed. |
| `NORMALIZED_SOURCE` | A provider/request value projected through approved Canonical normalization without business inference. |
| `AGGREGATION` | A bounded inventory, count, set, minimum, or maximum over an explicitly governed group. |
| `DETERMINISTIC_CALCULATION` | A value with an exact deterministic formula and declared dependencies. |
| `COMPOSITE_SCORE` | An existing versioned scoring-process output; not probability, confidence, rank, or recommendation. |
| `AI_ANALYSIS` | A model-authored semantic interpretation. No current Workbook V0.2 field is approved for this class. |
| `DECISION_OUTPUT` | An existing bounded rule/recommendation output; not final human judgment. |
| `MANUAL_INPUT` | Operator-owned workflow state, isolated from analysis snapshots. |
| `SYSTEM_STATUS` | Presence, conflict, policy, quality, period, query, or execution state produced by the owning framework. |
| `METADATA` | Deterministic identity, provenance, lineage, location, snapshot, or integrity metadata. |
| `DISPLAY` | A lossless label, summary, or fixed explanation projection with no new analytical meaning. |
| `EVIDENCE` | An evidence inventory, candidate, relationship, signal, risk, limitation, or reference projection. |
| `CONFIGURATION` | A versioned rule/factor identity selected by an existing framework. |
| `SEMANTIC_UNRESOLVED` | Repository evidence does not establish one safe business meaning or owner. |

Confidence values are `HIGH`, `MEDIUM`, and `UNRESOLVED`. Requirement cells use `Y` (required), `N` (not required), `C` (conditional on the field's source/record), and `?` (business decision outstanding). The compact requirement order is:

`F=<formula>; AI=<model>; M=<manual>; P=<provider>; A=<aggregation>; B=<business rule>`.

Current-status values preserve the D1/D2A audit:

- `NOT_IN_CALC_AUDIT`: not one of the 99 acquisition rows labelled `CALCULATED`;
- `CLASSIFICATION_REVIEW_REQUIRED`: one of the 86 rows audited here;
- `FORMULA_UNSPECIFIED`: the existing trend field;
- `DEFINED_IMPLEMENTED`: one of the seven D2A count evaluators;
- `DEFINED_READY`: one of the four deliberately deferred defined fields;
- `DEFINED_SEMANTIC_BLOCKED`: the variation-count field.

## 3. Evidence and authority codes

| Code | Repository evidence |
|---|---|
| `API` | `docs/integration/API_FIELD_COVERAGE_MATRIX_V0.1.md` and `DATA_SOURCE_API_MAPPING_V0.1.md` |
| `CAN` | Canonical Data Model, Evidence/Provenance Model, Conflict/Resolution Model, and normalization contract |
| `WB` | Workbook design, fixed schema, and V0.2 builder projection |
| `PI` / `DI` / `CI` / `OI` | Product, Demand, Competition, and Opportunity Intelligence V0.1 contracts |
| `EE` / `CR` | Evidence Evaluation and Conflict Resolution V0.1 contracts |
| `OS` / `RF` | Opportunity Scoring and Recommendation Framework V0.1 contracts |
| `OO` / `OE` / `XD` | Operator Output, Operator Export, and XLSX Delivery contracts |
| `CALC` | Calculated Field Specification, calculation audit, and D2A registry |

## 4. Complete 157-field semantic responsibility matrix

The row number is the fixed Workbook field order. `Evidence` records where the semantic conclusion was found; `Authority` names the contract that owns the meaning. `Next` is an implementation/governance queue, not permission to change the current owner.

| # | field_id | display_name | acquisition | current_status | semantic_class | confidence | evidence | authoritative_source | owner_layer | requirements | readiness | next | notes |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F001 | `workbook.market_overview.marketplace` | Marketplace | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,WB | MarketplaceIdentity | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Request scope and response provenance must remain distinct. |
| F002 | `workbook.market_overview.category_candidate` | Category Candidate | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | MEDIUM | API,PI,OI,WB | ProductFact candidate projection | PI/OI projection | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Candidate values remain unresolved; no preferred category. |
| F003 | `workbook.market_overview.market_size_evidence_metric` | Market Size Evidence Metric | PARTIAL | NOT_IN_CALC_AUDIT | EVIDENCE | HIGH | API,OI,WB | Opportunity evidence indicator | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | P1_DECISION | A proxy label is not a total-market fact. |
| F004 | `workbook.market_overview.metric_value` | Metric Value | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,OI,WB | ObservationValue | Canonical/OI projection | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Direct selected evidence value only. |
| F005 | `workbook.market_overview.unit` | Unit | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,WB | UnitDescriptor | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Unknown units remain unknown; no conversion. |
| F006 | `workbook.market_overview.observed_product_count` | Observed Product Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,OI,WB | Bounded snapshot identity inventory | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | IMPLEMENTED | KEEP | Distinct validated identities; never total market size. |
| F007 | `workbook.market_overview.data_sources` | Data Sources | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,EE,WB | Provenance provider inventory | Evidence Evaluation/Workbook | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Stable provenance projection, not a business aggregate. |
| F008 | `workbook.market_overview.evidence_backed_trend` | Evidence-backed Trend | CALCULATED | FORMULA_UNSPECIFIED | SEMANTIC_UNRESOLVED | UNRESOLVED | CALC,OI,WB | No approved trend contract | Unassigned | F=?;AI=?;M=N;P=C;A=?;B=Y | BUSINESS_RULE_BLOCKED | P0_DECISION | Window, direction, thresholds, ties, and renderer are undefined. |
| F009 | `workbook.market_overview.risk_alerts` | Risk Alerts | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,WB | Opportunity risk_evidence | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Limitation inventory; no severity or failure probability. |
| F010 | `workbook.market_overview.evidence_quality` | Evidence Quality | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | EE,WB | EvidenceQualityProfile | Evidence Evaluation | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Qualitative profile; no numeric weight or confidence. |
| F011 | `workbook.market_overview.analysis_limitations` | Analysis Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,EE,WB | Diagnostics and limitation codes | OI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Remains visible even with broader provider coverage. |
| F012 | `workbook.market_overview.snapshot_id` | Snapshot ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OI,CAN,WB | Opportunity snapshot identity | Opportunity Intelligence | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic content identity. |
| F013 | `workbook.product_database.asin` | ASIN | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | ProductIdentity.asin | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=N | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Exact product identity. |
| F014 | `workbook.product_database.marketplace` | Marketplace | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | ProductIdentity.marketplace | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Preserve request-scope provenance. |
| F015 | `workbook.product_database.display_title` | Display Title | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | ProductFact title candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | One candidate may display; conflict is not resolved. |
| F016 | `workbook.product_database.title_state` | Title State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | PI,WB | ProductFactEvidenceSet candidate state | Product Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Presence/candidate status, not title calculation. |
| F017 | `workbook.product_database.brand` | Brand | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | ProductFact brand candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Candidate semantics preserved. |
| F018 | `workbook.product_database.category` | Category | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | ProductFact category candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Granularity may differ by provider. |
| F019 | `workbook.product_database.product_type` | Product Type | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Approved product_type fact candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | No clustering or type inference. |
| F020 | `workbook.product_database.price` | Price | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | ProductMetric price candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Multiple provider values remain candidates. |
| F021 | `workbook.product_database.price_currency` | Price Currency | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Metric unit/currency | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Context-derived currency must retain provenance. |
| F022 | `workbook.product_database.price_state` | Price State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | PI,WB | Metric candidate/presence state | Product Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | No provider winner or average. |
| F023 | `workbook.product_database.rating` | Rating | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Rating metric candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Preserve provider differences. |
| F024 | `workbook.product_database.rating_state` | Rating State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | PI,EE,WB | Metric candidate/conflict state | PI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Never average conflicting ratings. |
| F025 | `workbook.product_database.review_evidence_count` | Review Evidence Count | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Explicit review_count metric | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Listing metric is not fetched-review record count. |
| F026 | `workbook.product_database.bsr` | BSR | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Rank metric candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Requires context and period. |
| F027 | `workbook.product_database.bsr_context` | BSR Context | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Rank context | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Prevents cross-category comparison. |
| F028 | `workbook.product_database.sales_evidence_value` | Sales Evidence Value | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Separate sales/order metrics | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Provider metrics are not aliases. |
| F029 | `workbook.product_database.sales_evidence_unit` | Sales Evidence Unit | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Metric unit/period | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Unknown method/window remains explicit. |
| F030 | `workbook.product_database.sales_evidence_type` | Sales Evidence Type | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CAN,PI,WB | EvidenceType and metric semantic | Product Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Classification keeps estimates distinct from observed facts. |
| F031 | `workbook.product_database.variation_role` | Variation Role | PARTIAL | NOT_IN_CALC_AUDIT | EVIDENCE | HIGH | API,CAN,PI,WB | Explicit variation topology | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | Only explicit valid edges establish role. |
| F032 | `workbook.product_database.parent_asin` | Parent ASIN | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Parent relationship fact value | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Self-parent semantics remain cautious. |
| F033 | `workbook.product_database.child_count` | Child Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,PI,WB | Explicit child-edge inventory | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | IMPLEMENTED | KEEP | Distinct valid explicit child edges only. |
| F034 | `workbook.product_database.attribute_summary` | Attribute Summary | PARTIAL | NOT_IN_CALC_AUDIT | DISPLAY | HIGH | PI,WB | Approved fact-candidate projection | Workbook Presentation | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | P2_DISPLAY | Lossless summary; no attribute invention. |
| F035 | `workbook.product_database.seller` | Seller | UNKNOWN | NOT_IN_CALC_AUDIT | SOURCE | HIGH | API,PI,WB | Future seller fact source | Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_GAP | PROVIDER_REVIEW | Brand or manufacturer must not substitute for seller. |
| F036 | `workbook.product_database.fba_status` | FBA Status | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Fulfillment fact candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Unknown is not false. |
| F037 | `workbook.product_database.data_sources` | Data Sources | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,PI,WB | Candidate provenance providers | Product Intelligence/Workbook | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Stable provenance display. |
| F038 | `workbook.product_database.data_state` | Data State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | PI,WB | Evidence coverage/candidate state | Product Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Separate from HTTP/provider response status. |
| F039 | `workbook.product_database.conflict_state` | Conflict State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | EE,CR,WB | Evidence conflict state | Evidence Evaluation/Conflict Resolution | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Conflict is visible and unresolved. |
| F040 | `workbook.product_database.time_period_status` | Time / Period Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | CAN,PI,EE,WB | Observation-time and period quality | PI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Retrieval time never replaces observation time. |
| F041 | `workbook.product_database.product_snapshot_id` | Product Snapshot ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | PI,WB | Product snapshot identity | Product Intelligence | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic content identity. |
| F042 | `workbook.product_database.output_row_id` | Output Row ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OO,WB | Product output-row identity | Operator Output | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Lineage join key. |
| F043 | `workbook.top_products.product_asin` | Product ASIN | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | ProductIdentity.asin | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=N | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Exact rank-record subject. |
| F044 | `workbook.top_products.display_title` | Display Title | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Title fact candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Context only; not a ranking input. |
| F045 | `workbook.top_products.marketplace` | Marketplace | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | ProductIdentity.marketplace | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Comparison boundary. |
| F046 | `workbook.top_products.source_rank_value` | Source Rank Value | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Explicit rank observation | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Workbook never creates a rank. |
| F047 | `workbook.top_products.rank_metric` | Rank Metric | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Rank semantic mapping | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | Unknown position codes remain unknown. |
| F048 | `workbook.top_products.rank_context` | Rank Context | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Rank context | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Required for interpretation. |
| F049 | `workbook.top_products.channel` | Channel | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | RelationshipChannel | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | Only approved source-code mappings are normalized. |
| F050 | `workbook.top_products.rank_provider` | Rank Provider | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,PI,WB | Rank observation provenance | Product Intelligence | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Lineage metadata, not rank calculation. |
| F051 | `workbook.top_products.rank_status` | Rank Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | PI,WB | Rank presence/context state | Product Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Missing rank is not rank zero. |
| F052 | `workbook.top_products.rank_period` | Rank Period | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Observation period | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Preserve source precision/timezone. |
| F053 | `workbook.top_products.price` | Price | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Price metric candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Reference value only. |
| F054 | `workbook.top_products.review_evidence_count` | Review Evidence Count | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Review-count metric | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Evidence semantics remain explicit. |
| F055 | `workbook.top_products.rating_evidence` | Rating Evidence | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Rating metric candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | No inferred overall rating. |
| F056 | `workbook.top_products.product_features` | Product Features | PARTIAL | NOT_IN_CALC_AUDIT | DISPLAY | HIGH | PI,WB | Approved fact-candidate summary | Workbook Presentation | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | P2_DISPLAY | Not model-generated product claims. |
| F057 | `workbook.top_products.data_limitations` | Data Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | PI,EE,WB | Rank limitation codes | PI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Includes explicit not-best-product boundary. |
| F058 | `workbook.top_products.rank_observation_id` | Rank Observation ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,PI,WB | Canonical observation identity | Product Intelligence | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic record key. |
| F059 | `workbook.keyword_demand.keyword` | Keyword | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | KeywordIdentity.normalized_text | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Raw and normalized text remain distinct. |
| F060 | `workbook.keyword_demand.marketplace` | Marketplace | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | KeywordIdentity.marketplace | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Request context may be required. |
| F061 | `workbook.keyword_demand.locale` | Locale | UNAVAILABLE | NOT_IN_CALC_AUDIT | SOURCE | HIGH | API,CAN,DI,WB | Future KeywordIdentity locale source | Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_GAP | PROVIDER_REVIEW | Country-to-locale guessing is unsafe. |
| F062 | `workbook.keyword_demand.search_volume` | Search Volume | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | KeywordMetric search_volume | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Provider estimate and report window stay visible. |
| F063 | `workbook.keyword_demand.search_volume_state` | Search Volume State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | DI,WB | Keyword metric candidate state | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Null and missing do not become zero. |
| F064 | `workbook.keyword_demand.search_volume_unit` | Search Volume Unit | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | Keyword metric unit/period | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Weekly context remains explicit. |
| F065 | `workbook.keyword_demand.cpc` | CPC | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | KeywordMetric cpc | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Preserve direct and range evidence. |
| F066 | `workbook.keyword_demand.cpc_currency` | CPC Currency | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | CPC unit/currency | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Marketplace-derived currency needs explicit provenance. |
| F067 | `workbook.keyword_demand.cpc_state` | CPC State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | DI,WB | CPC candidate state | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Explicit null remains explicit. |
| F068 | `workbook.keyword_demand.aba_rank` | ABA Rank | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | ABA rank metric | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Reported rank with period. |
| F069 | `workbook.keyword_demand.aba_rank_state` | ABA Rank State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | DI,WB | ABA rank candidate state | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | State is system-owned. |
| F070 | `workbook.keyword_demand.difficulty` | Difficulty | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | Provider difficulty metric | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Provider scale/method must be documented or unknown. |
| F071 | `workbook.keyword_demand.difficulty_state` | Difficulty State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | DI,WB | Difficulty candidate state | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | State is not the difficulty value. |
| F072 | `workbook.keyword_demand.related_product_count` | Related Product Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,DI,WB | Directional relationship inventory | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | IMPLEMENTED | KEEP | Exact direction/scope only; not competitor total. |
| F073 | `workbook.keyword_demand.related_product_asins` | Related Product ASINs | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | Relationship endpoint identities | Demand Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Completeness depends on query scope/pagination. |
| F074 | `workbook.keyword_demand.channel` | Channel | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,DI,WB | RelationshipChannel | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | Unknown provider codes stay unknown. |
| F075 | `workbook.keyword_demand.query_direction` | Query Direction | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CAN,DI,WB | QueryDirection endpoint semantic | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Forward and reverse executions remain separate. |
| F076 | `workbook.keyword_demand.query_status` | Query Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | CAN,DI,WB | QueryExecutionRecord result status | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Empty, failed, populated, and unknown differ. |
| F077 | `workbook.keyword_demand.provider` | Provider | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,DI,WB | Query/metric provenance provider | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Connector identity, not business payload calculation. |
| F078 | `workbook.keyword_demand.estimate_method_status` | Estimate Method Status | UNKNOWN | NOT_IN_CALC_AUDIT | SOURCE | HIGH | API,CAN,DI,WB | Provider method declaration | Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_GAP | PROVIDER_REVIEW | Unknown method must not be fabricated from period. |
| F079 | `workbook.keyword_demand.period_status` | Period Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | CAN,DI,EE,WB | Demand period quality state | DI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Quality state, not trend direction. |
| F080 | `workbook.keyword_demand.limitations` | Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | DI,WB | Demand diagnostics/limits | Demand Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | No demand guarantee. |
| F081 | `workbook.keyword_demand.demand_snapshot_id` | Demand Snapshot ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | DI,WB | Demand snapshot identity | Demand Intelligence | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic content identity. |
| F082 | `workbook.competition_evidence.product_asin` | Product ASIN | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,CI,WB | Relationship product endpoint | Competition Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=N | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Exact endpoint identity. |
| F083 | `workbook.competition_evidence.keyword` | Keyword | AVAILABLE | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,CI,WB | Relationship keyword endpoint | Competition Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | READY_SOURCE_MAPPING | PROVIDER_MAPPING | Exact endpoint value. |
| F084 | `workbook.competition_evidence.relationship_direction` | Relationship Direction | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CAN,CI,WB | ProductKeywordRelationship.direction | Competition Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Never infer bidirectional equivalence. |
| F085 | `workbook.competition_evidence.observed_relationship` | Observed Relationship | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CAN,CI,OO,WB | Validated relationship observation | Competition Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Evidence existence, not competitive truth. |
| F086 | `workbook.competition_evidence.observed_relationship_type` | Observed Relationship Type | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CAN,CI,OO,WB | Relationship type | Competition Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | RANK remains a relationship semantic only. |
| F087 | `workbook.competition_evidence.channel` | Channel | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,CI,WB | RelationshipChannel | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | Unknown codes remain UNKNOWN. |
| F088 | `workbook.competition_evidence.provider` | Provider | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,CI,WB | Relationship provenance provider | Competition Intelligence | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Lineage metadata. |
| F089 | `workbook.competition_evidence.evidence_count` | Evidence Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,CI,OO,WB | Exact relationship evidence group | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | IMPLEMENTED | KEEP | Count is not competition strength. |
| F090 | `workbook.competition_evidence.evidence_classification` | Evidence Classification | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CI,OI,WB | Evidence semantic class | Competition Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | No competitor ranking. |
| F091 | `workbook.competition_evidence.variation_evidence_count` | Variation Evidence Count | CALCULATED | DEFINED_SEMANTIC_BLOCKED | SEMANTIC_UNRESOLVED | UNRESOLVED | CALC,CI,OO,WB | Conflicting edge vs evidence-record grain | Unassigned | F=N;AI=N;M=N;P=C;A=?;B=Y | BUSINESS_RULE_BLOCKED | P0_DECISION | Choose edge count, evidence-record count, unique variant count, or another explicit grain. |
| F092 | `workbook.competition_evidence.query_status` | Query Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | CAN,DI,CI,WB | Linked query execution status | Competition Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Empty is query-scoped evidence, not no competition. |
| F093 | `workbook.competition_evidence.limitations` | Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | CI,OO,WB | Competition diagnostics/limits | Competition Intelligence/OO | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Prevents strength/share/ranking inference. |
| F094 | `workbook.competition_evidence.competition_output_row_id` | Competition Output Row ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OO,WB | Competition output-row identity | Operator Output | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Lineage join key. |
| F095 | `workbook.product_structure.marketplace` | Marketplace | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Product scope marketplace | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Exact aggregation boundary. |
| F096 | `workbook.product_structure.product_type` | Product Type | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,PI,WB | Exact product_type fact candidate | Product Intelligence | F=N;AI=N;M=N;P=Y;A=N;B=Y | PROVIDER_REVIEW | PROVIDER_REVIEW | No clustering; unresolved candidates remain separate. |
| F097 | `workbook.product_structure.product_count` | Product Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,PI,WB | Exact group identity inventory | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | IMPLEMENTED | KEEP | Distinct validated product identities. |
| F098 | `workbook.product_structure.observed_share` | Observed Share | CALCULATED | DEFINED_READY | DETERMINISTIC_CALCULATION | HIGH | CALC,WB | Group count divided by same-scope snapshot count | Calculation Engine | F=Y;AI=N;M=N;P=N;A=N;B=Y | READY | D2C | Denominator is the snapshot-wide distinct validated identity count for the same marketplace/scope; never market size. |
| F099 | `workbook.product_structure.sales_evidence_summary` | Sales Evidence Summary | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | DISPLAY | HIGH | PI,WB | Sales-candidate display projection | Workbook Presentation | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | P2_DISPLAY | Keep values, units, methods, and states separate. |
| F100 | `workbook.product_structure.minimum_comparable_price` | Minimum Comparable Price | CALCULATED | DEFINED_READY | AGGREGATION | HIGH | CALC,PI,WB | Comparable price candidate set | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | BUSINESS_RULE_BLOCKED | D2C | Workbook Presentation contract must version the comparable-set predicate. |
| F101 | `workbook.product_structure.maximum_comparable_price` | Maximum Comparable Price | CALCULATED | DEFINED_READY | AGGREGATION | HIGH | CALC,PI,WB | Comparable price candidate set | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | BUSINESS_RULE_BLOCKED | D2C | Same governed comparable set as minimum. |
| F102 | `workbook.product_structure.currency` | Currency | PARTIAL | NOT_IN_CALC_AUDIT | NORMALIZED_SOURCE | HIGH | API,CAN,PI,WB | Price currency/unit | Canonical/Provider mapping | F=N;AI=N;M=N;P=Y;A=N;B=C | PROVIDER_REVIEW | PROVIDER_REVIEW | Mixed currencies cannot be combined. |
| F103 | `workbook.product_structure.observed_feature_inventory` | Observed Feature Inventory | PARTIAL | NOT_IN_CALC_AUDIT | AGGREGATION | MEDIUM | API,PI,WB | Exact approved fact inventory | Product Intelligence/Workbook | F=N;AI=N;M=N;P=C;A=Y;B=Y | DEPENDENCY_BLOCKED | D2C | Requires an approved attribute set and exact group grain; no generated features. |
| F104 | `workbook.product_structure.data_state` | Data State | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | PI,EE,WB | Structure evidence/quality state | PI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Evidence state, not a quality score. |
| F105 | `workbook.product_structure.provider_count` | Provider Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,CAN,PI,WB | Exact-group provenance providers | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | IMPLEMENTED | KEEP | Provider inventory is not confidence. |
| F106 | `workbook.product_structure.limitations` | Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | PI,EE,WB | Structure diagnostics/limits | PI/EE projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Includes no-clustering and no-market-share boundaries. |
| F107 | `workbook.product_structure.member_product_ids` | Member Product IDs | CALCULATED | DEFINED_READY | AGGREGATION | HIGH | CALC,PI,WB | Exact group membership | Calculation Engine | F=N;AI=N;M=N;P=C;A=Y;B=Y | READY | D2C | Sorted distinct ProductIdentity values; membership evidence, not a score. |
| F108 | `workbook.opportunity_analysis.product` | Product | PARTIAL | NOT_IN_CALC_AUDIT | EVIDENCE | MEDIUM | API,OI,OO,WB | Opportunity subject identity/set | Opportunity Intelligence/OO | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | P1_DECISION | Multiple subjects must remain MULTIPLE or UNRESOLVED. |
| F109 | `workbook.opportunity_analysis.demand_signal` | Demand Signal | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,OO,WB | Opportunity demand signal projection | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Evidence-existence signal, not demand conclusion. |
| F110 | `workbook.opportunity_analysis.competition_signal` | Competition Signal | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,OO,WB | Opportunity relationship signal | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | No competition-strength judgment. |
| F111 | `workbook.opportunity_analysis.product_signal` | Product Signal | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,OO,WB | Opportunity product signal | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Existing structural projection only. |
| F112 | `workbook.opportunity_analysis.signal_classification` | Signal Classification | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,WB | Opportunity signal classification | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Observed/derived/missing/risk classes have no desirability meaning. |
| F113 | `workbook.opportunity_analysis.missing_evidence` | Missing Evidence | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,WB | MissingEvidenceInventory | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Missing is not negative evidence. |
| F114 | `workbook.opportunity_analysis.risk_evidence` | Risk Evidence | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,WB | Opportunity risk_evidence | Opportunity Intelligence | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | No severity, probability, or predicted failure. |
| F115 | `workbook.opportunity_analysis.score_factor` | Score Factor | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | CONFIGURATION | HIGH | OS,OO,WB | ScoreFactorDefinition identity | Opportunity Scoring | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Versioned factor configuration, not a computed score. |
| F116 | `workbook.opportunity_analysis.rule_process_score` | Rule Process Score | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | COMPOSITE_SCORE | HIGH | OS,OO,WB | ScoreCalculationRecord.result_value | Opportunity Scoring | F=Y;AI=N;M=N;P=N;A=N;B=Y | IMPLEMENTED_EXISTING_OWNER | NO_CALCULATION | Existing factor result; V0.1 emits no aggregate total or probability. |
| F117 | `workbook.opportunity_analysis.score_status` | Score Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | OS,OO,WB | ScoreCalculationRecord.result_status | Opportunity Scoring | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Blocked/missing/not-applicable never becomes zero. |
| F118 | `workbook.opportunity_analysis.score_reference` | Score Reference | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OS,OO,WB | Score calculation identity | Opportunity Scoring | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Audited record reference. |
| F119 | `workbook.opportunity_analysis.score_interpretation` | Score Interpretation | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | DISPLAY | HIGH | OS,OO,WB | Existing score explanation | Opportunity Scoring/Workbook | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Fixed bounded interpretation, not AI narrative. |
| F120 | `workbook.opportunity_analysis.explanation_reference` | Explanation Reference | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OS,OO,WB | Score explanation identity | Opportunity Scoring | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Audited explanation reference. |
| F121 | `workbook.opportunity_analysis.limitations` | Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | OI,OS,WB | Opportunity/scoring limitation codes | OI/OS projection | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | No guarantee, forecast, or selection. |
| F122 | `workbook.opportunity_analysis.opportunity_output_row_id` | Opportunity Output Row ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OO,WB | Opportunity output-row identity | Operator Output | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Lineage join key. |
| F123 | `workbook.action_recommendations.product` | Product | PARTIAL | NOT_IN_CALC_AUDIT | EVIDENCE | MEDIUM | API,RF,OO,WB | Recommendation subject identity/set | Recommendation Framework/OO | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | P1_DECISION | Only uniquely resolved product scope may display as one product. |
| F124 | `workbook.action_recommendations.recommendation_type` | Recommendation Type | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | DECISION_OUTPUT | HIGH | RF,OO,WB | RecommendationGenerationRecord type | Recommendation Framework | F=N;AI=N;M=N;P=N;A=N;B=Y | IMPLEMENTED_EXISTING_OWNER | NO_CALCULATION | Deterministic bounded advisory; not final decision or purchase advice. |
| F125 | `workbook.action_recommendations.recommendation_display_label` | Recommendation Display Label | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | DISPLAY | HIGH | RF,WB | Fixed type-to-label mapping | Workbook Presentation | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | P2_DISPLAY | One-to-one label; original machine code retained. |
| F126 | `workbook.action_recommendations.reason` | Reason | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | DECISION_OUTPUT | HIGH | RF,OO,WB | Recommendation rule explanation | Recommendation Framework | F=N;AI=N;M=N;P=N;A=N;B=Y | IMPLEMENTED_EXISTING_OWNER | NO_CALCULATION | Existing deterministic rule explanation, not generative text. |
| F127 | `workbook.action_recommendations.rule_reference` | Rule Reference | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | CONFIGURATION | HIGH | RF,OO,WB | Recommendation rule identity | Recommendation Framework | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Versioned rule configuration reference. |
| F128 | `workbook.action_recommendations.policy_status` | Policy Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | RF,OO,WB | Recommendation applicability policy status | Recommendation Framework | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Provider response status is not policy status. |
| F129 | `workbook.action_recommendations.conflict_status` | Conflict Status | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | SYSTEM_STATUS | HIGH | CR,RF,OO,WB | Recommendation applicability conflict status | Recommendation Framework | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Framework preserves conflicts; it does not resolve them. |
| F130 | `workbook.action_recommendations.missing_requirements` | Missing Requirements | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | RF,OO,WB | Applicability missing-evidence inventory | Recommendation Framework | F=N;AI=N;M=N;P=C;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Guides evidence collection, not product rejection. |
| F131 | `workbook.action_recommendations.evidence_references` | Evidence References | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | RF,OO,WB | Recommendation input evidence IDs | Recommendation Framework | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Existing audited references. |
| F132 | `workbook.action_recommendations.evidence_count` | Evidence Count | CALCULATED | DEFINED_IMPLEMENTED | AGGREGATION | HIGH | CALC,RF,OO,WB | Recommendation evidence-reference set | Calculation Engine | F=N;AI=N;M=N;P=N;A=Y;B=Y | IMPLEMENTED | KEEP | Count is not recommendation strength. |
| F133 | `workbook.action_recommendations.limitations` | Limitations | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | EVIDENCE | HIGH | RF,OO,WB | Recommendation limitation codes | Recommendation Framework | F=N;AI=N;M=N;P=N;A=N;B=Y | EXISTING_OWNER | NO_CALCULATION | Explicitly not selection, guarantee, forecast, or purchase advice. |
| F134 | `workbook.action_recommendations.manual_review_status` | Manual Review Status | UNAVAILABLE | NOT_IN_CALC_AUDIT | MANUAL_INPUT | HIGH | WB | Workbook-only operator workflow state | Operator UI | F=N;AI=N;M=Y;P=N;A=N;B=Y | IMPLEMENTED_UI | KEEP_ISOLATED | Does not write back to evidence, score, or recommendation snapshots. |
| F135 | `workbook.action_recommendations.recommendation_record_id` | Recommendation Record ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | RF,OO,WB | Recommendation generation identity | Recommendation Framework | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic record key. |
| F136 | `workbook.action_recommendations.source_snapshot_id` | Source Snapshot ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | RF,OO,WB | Recommendation source snapshot identity | Recommendation Framework/OO | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Version boundary. |
| F137 | `workbook.action_recommendations.operator_output_row_id` | Operator Output Row ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OO,WB | Recommendation output-row identity | Operator Output | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Lineage join key. |
| F138 | `workbook.data_audit.audit_record_id` | Audit Record ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | WB,XD | Deterministic audit presentation identity | Workbook/XLSX Delivery | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Presentation identity, not analytical result. |
| F139 | `workbook.data_audit.source_sheet` | Source Sheet | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | WB,XD | Workbook sheet mapping | Workbook/XLSX Delivery | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Presentation location metadata. |
| F140 | `workbook.data_audit.display_row_key` | Display Row Key | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | WB,XD | Display-row identity | Workbook/XLSX Delivery | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic row locator. |
| F141 | `workbook.data_audit.excel_row` | Excel Row | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | WB,XD | Rendered row ordinal | XLSX Delivery | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Physical location only. |
| F142 | `workbook.data_audit.display_field` | Display Field | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | WB,XD | Presentation field/row-lineage marker | Workbook/XLSX Delivery | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Current contract does not claim unsupported cell precision. |
| F143 | `workbook.data_audit.excel_cell` | Excel Cell | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | WB,XD | Rendered row/cell locator | XLSX Delivery | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Physical presentation metadata. |
| F144 | `workbook.data_audit.export_row_id` | Export Row ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OE,WB,XD | Operator Export row identity | Operator Export | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Validated output-to-export join key. |
| F145 | `workbook.data_audit.output_row_id` | Output Row ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | OO,OE,WB | Operator Output row identity | Operator Output | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Validated export-to-output join key. |
| F146 | `workbook.data_audit.evidence_id` | Evidence ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Canonical evidence identity | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Deterministic semantic record reference. |
| F147 | `workbook.data_audit.provider` | Provider | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Provenance.provider | Canonical/Lineage | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Configured provider identity, never credential content. |
| F148 | `workbook.data_audit.source_tool` | Source Tool | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Provenance.source_tool | Canonical/Lineage | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Endpoint/tool identity. |
| F149 | `workbook.data_audit.source_field` | Source Field | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Provenance.source_field | Canonical/Lineage | F=N;AI=N;M=N;P=C;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Exact mapping-owned source locator. |
| F150 | `workbook.data_audit.raw_evidence_reference` | Raw Evidence Reference | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Raw evidence identity | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Reference only; raw payload is excluded. |
| F151 | `workbook.data_audit.collection_run_id` | Collection Run ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Collection-run identity | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Contains no credential material. |
| F152 | `workbook.data_audit.transformation_run_id` | Transformation Run ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Transformation-run identity | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Mapping execution reference. |
| F153 | `workbook.data_audit.mapping_version` | Mapping Version | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Approved mapping version | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Provider schema version may separately remain unknown. |
| F154 | `workbook.data_audit.canonical_reference_id` | Canonical Reference ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Canonical observation/query identity | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Replayed against source bundles. |
| F155 | `workbook.data_audit.lineage_id` | Lineage ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Serialized lineage identity | OO/OE/Workbook | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Links presentation, output, and Canonical records. |
| F156 | `workbook.data_audit.source_snapshot_id` | Source Snapshot ID | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | PI,DI,CI,OI,OS,RF,OO,WB | Upstream snapshot identity | Owning source framework | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Immutable version boundary. |
| F157 | `workbook.data_audit.source_bundle_fingerprint` | Source Bundle Fingerprint | CALCULATED | CLASSIFICATION_REVIEW_REQUIRED | METADATA | HIGH | CAN,OO,OE,WB | Canonical bundle SHA-256 | Canonical/Lineage | F=N;AI=N;M=N;P=N;A=N;B=N | EXISTING_OWNER | NO_CALCULATION | Integrity check, not provider-supplied hash. |

## 5. Mechanical classification results

### 5.1 Full 157-field semantic counts

| Semantic class | Count |
|---|---:|
| `NORMALIZED_SOURCE` | 47 |
| `SOURCE` | 3 |
| `AGGREGATION` | 11 |
| `DETERMINISTIC_CALCULATION` | 1 |
| `COMPOSITE_SCORE` | 1 |
| `AI_ANALYSIS` | 0 |
| `DECISION_OUTPUT` | 2 |
| `MANUAL_INPUT` | 1 |
| `SYSTEM_STATUS` | 19 |
| `METADATA` | 37 |
| `DISPLAY` | 5 |
| `EVIDENCE` | 26 |
| `CONFIGURATION` | 2 |
| `SEMANTIC_UNRESOLVED` | 2 |
| **Total** | **157** |

Acquisition coverage remains exactly: `AVAILABLE=30`, `PARTIAL=24`, `CALCULATED=99`, `UNAVAILABLE=2`, `UNKNOWN=2`.

### 5.2 The 86-field classification review

All 86 original `CLASSIFICATION_REVIEW_REQUIRED` records were found, reviewed, and semantically resolved with `HIGH` confidence:

| Resolved class | Count | Calculation Engine action |
|---|---:|---|
| `METADATA` | 37 | None; keep identity/lineage owner. |
| `EVIDENCE` | 22 | None; keep intelligence/evaluation/recommendation owner. |
| `SYSTEM_STATUS` | 19 | None; keep framework state machine owner. |
| `DISPLAY` | 3 | None; keep lossless Workbook projection. |
| `DECISION_OUTPUT` | 2 | None; keep Recommendation Framework. |
| `CONFIGURATION` | 2 | None; keep versioned scoring/recommendation definitions. |
| `COMPOSITE_SCORE` | 1 | None; display existing Opportunity Scoring record. |
| **Total** | **86** | **No new evaluator** |

Audit reconciliation: source records `86`, review results `86`, missing `0`, duplicate `0`, unsupported semantic classes `0`, high-confidence resolutions `86`, medium/low/unresolved resolutions `0`.

The original 99-field audit is intentionally unchanged: `DEFINED=12`, `FORMULA_UNSPECIFIED=1`, `CLASSIFICATION_REVIEW_REQUIRED=86`. This document is the accepted semantic resolution dimension; it does not rewrite acquisition history or silently migrate existing owners.

## 6. True deterministic and aggregation backlog

### 6.1 Deterministic calculation

| Field | State | Exact responsibility |
|---|---|---|
| `workbook.product_structure.observed_share` | `READY` | `product_count / observed_product_count`, where both counts use the same marketplace and explicit snapshot scope. Zero denominator blocks the result; it never means market share. |

### 6.2 Aggregations

| State | Fields | Required action |
|---|---|---|
| `IMPLEMENTED` | Observed Product Count; Child Count; Related Product Count; Competition Evidence Count; Product Count; Provider Count; Recommendation Evidence Count | Keep the seven accepted D2A distinct-identity evaluators. |
| `READY` | Member Product IDs | Return stable sorted distinct ProductIdentity values for the exact governed group. |
| `BUSINESS_RULE_BLOCKED` | Minimum Comparable Price; Maximum Comparable Price | Encode and version the already documented same-currency, same-unit, same-measurement-semantic, same-scope, comparable-period predicate before execution. |
| `DEPENDENCY_BLOCKED` | Observed Feature Inventory | Approve the structured attribute set and exact product-type group before building a frequency inventory. |

`Data Sources`, provider fields, ID lists in audit records, evidence references, and presentation summaries can require stable sorting or projection, but that mechanical serialization does not make them business aggregations or Calculation Engine formulas.

## 7. Composite score audit

Only `Rule Process Score` is a score-class field. Its owner is the existing Opportunity Scoring V0.1 framework.

| Requirement | Status |
|---|---|
| Inputs | Existing Decision Framework evaluation and audited references are defined. |
| Weights | Not applicable in V0.1; the framework emits one fixed process result per factor and no weighted total. |
| Thresholds | Not applicable to the fixed V0.1 result-state mapping. |
| Directionality | Not applicable; the value is not a desirability score. |
| Normalization | Not applicable; V0.1 does not combine factors. |
| Missing/conflict behavior | Defined by `result_status`; unavailable states carry `null`, never zero. |
| Implementation | Already owned and implemented by Opportunity Scoring; no Calculation Engine evaluator is allowed. |

`Score Factor` and `Rule Reference` are `CONFIGURATION`; `Score Status` is `SYSTEM_STATUS`; `Score Reference` and `Explanation Reference` are `METADATA`; `Score Interpretation` is `DISPLAY`.

## 8. AI analysis audit

Approved `AI_ANALYSIS` fields: **0**.

Repository evidence explicitly describes Product, Demand, Competition, Opportunity, Evidence Evaluation, Opportunity Scoring, and Recommendation outputs as deterministic, structural, qualitative, or rule-based. `Product Features`, `Attribute Summary`, `Sales Evidence Summary`, `Score Interpretation`, `Recommendation Display Label`, and `Reason` must not be reclassified as model-authored content.

`Evidence-backed Trend` is not yet an AI field. It remains `SEMANTIC_UNRESOLVED` until a business owner chooses either a deterministic statistical rule or a model-authored analysis contract and defines audit, version, confidence, and fallback behavior.

## 9. Provider/source review queue

### P0 — blocks safe source interpretation

1. **Seller:** Which documented XiYou or Sorftime path, if any, represents seller rather than brand/manufacturer?
2. **Locale:** Can either provider return explicit locale, or must locale remain unavailable instead of being inferred from country?
3. **Estimate Method Status:** Which provider documentation or response field declares the estimation method independently of the period?
4. **Rank channel codes:** What are the documented meanings of codes beyond approved organic/sponsored mappings?

### P1 — improves comparability and coverage

1. Confirm response-vs-request authority for Marketplace across both providers.
2. Confirm currency/unit provenance for Sorftime price and XiYou CPC.
3. Confirm order/sales metric method and exact period semantics without aliasing XiYou orders, Sorftime monthly sales, and Sorftime variation `SalesAmount`.
4. Approve the conservative product-type and structured-attribute mapping set.
5. Define completeness/pagination evidence for related products and relationship inventories.

### P2 — display enhancement

1. Extend safe labels for approved attributes only after provider semantics are documented.
2. Improve rank context and period display without generating cross-provider comparisons.

## 10. Business decisions required

### P0

1. **Variation Evidence Count:** Choose exactly one unit: (A) unique valid variation edges, (B) variation evidence records attached to the exact competition row, (C) unique variant products, or (D) another named unit. Repository evidence currently supports incompatible A/B interpretations, so the accepted answer for this audit is **E — unresolved**. Define duplicate identity and scope before D2C.
2. **Evidence-backed Trend:** Decide deterministic rule vs AI analysis. Define input series, period/window, minimum observations, direction thresholds, tie/flat behavior, missing/unknown behavior, text vocabulary, audit references, and version owner.
3. **Comparable price set:** Confirm Workbook Presentation Contract as the business owner of the versioned comparability predicate; Calculation Engine may only execute the accepted predicate over Product Intelligence price candidates.

### P1

1. **Market Size Evidence Metric:** Approve which source metrics may be labelled as market-size evidence proxies and how multiple candidates display without selection.
2. **Opportunity/Recommendation Product:** Define the display behavior for zero, one, or multiple product subjects while keeping lineage exact.
3. **Observed Feature Inventory:** Approve the structured attribute allow-list, grouping identity, value equality, and frequency display.

### P2

1. Approve presentation-only formatting for attribute, feature, and sales evidence summaries.
2. Decide whether future cell-level lineage attribution is needed; current V0.2 truthfully provides row-level lineage.

## 11. Special D2A deferred fields

| Field | Semantic decision | Exact boundary | D2C readiness |
|---|---|---|---|
| Variation Evidence Count | `SEMANTIC_UNRESOLVED` | Edge count and evidence-record count are not interchangeable. | `BUSINESS_RULE_BLOCKED` |
| Observed Share | `DETERMINISTIC_CALCULATION` | Denominator is snapshot-wide distinct validated products under the same marketplace/scope, not group total and not the real market. | `READY` |
| Minimum/Maximum Comparable Price | `AGGREGATION` | Comparable set requires equal currency, unit, price semantic, scope, and comparable period; no conversion or candidate preference. | `BUSINESS_RULE_BLOCKED` pending versioned predicate ownership |
| Member Product IDs | `AGGREGATION` | Membership evidence for the exact product-type group; unique by full ProductIdentity and stably sorted by canonical identity material. | `READY` |

## 12. Next implementation batch

Recommended next task:

`TASK-SP-018D2C — Remaining Deterministic Calculations and Aggregation Semantics`

Scope it to:

1. implement `Observed Share` with same-scope dependency validation and zero-denominator blocking;
2. implement `Member Product IDs` with authoritative unique ProductIdentity input and stable ordering;
3. implement min/max price only after the versioned comparability predicate is accepted;
4. implement Observed Feature Inventory only after the attribute/group contract is accepted;
5. leave Variation Evidence Count and Evidence-backed Trend unregistered until their P0 decisions are complete.

Do not include source mapping, AI execution, scoring changes, recommendation changes, metadata projection, status generation, or Workbook redesign in D2C.

## 13. Verification invariants

- The matrix contains exactly 157 unique rows and exactly the fixed 157 Workbook field IDs.
- All five acquisition statuses match the existing coverage matrix unchanged.
- Exactly 86 rows retain the original `CLASSIFICATION_REVIEW_REQUIRED` current status, and all 86 have a legal resolved semantic class.
- The existing 99-field calculation audit, seven D2A evaluators, and five non-evaluator D2A fields remain unchanged.
- No evaluator exists for AI, manual, metadata, display, evidence, configuration, decision-output, status, unresolved, or business-rule-blocked fields.
- No Workbook, provider, Canonical, intelligence, scoring, recommendation, output, export, or XLSX production module is changed by this task.
