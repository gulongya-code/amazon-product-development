# Xiyou MCP Selection-System Architecture Discovery

**Discovery date:** 2026-08-13 (Asia/Shanghai)  
**Mode:** Read-only architecture discovery  
**Decision status:** Blocked by missing Xiyou connection and missing system checkout

## Executive conclusion

### Recommendation: KEEP CURRENT ARCHITECTURE (interim no-change decision)

This is a risk-control recommendation, not an endorsement of the current design. There is not enough observed evidence to justify `EVOLVE ARCHITECTURE` or `MAJOR REFACTOR JUSTIFIED` because:

1. No Xiyou MCP server, tools, or resources are exposed to this Codex task.
2. The configured local MCP server list contains only `node_repl`; no Xiyou entry is present.
3. The supplied workspace contains no application files, datasets, schemas, or Git objects to audit.
4. Therefore the real-market probe and existing-architecture audit cannot be performed truthfully.

No production code, datasets, schemas, or credentials were read or changed. This report is the only new file.

## 1. Evidence and discovery boundary

### Observed MCP inventory

| Surface | Observed result |
|---|---|
| Callable tools whose name/description contains `xiyou` | None |
| MCP resource servers returned by discovery | `codex_apps` only |
| MCP resource templates | None |
| Xiyou resources | None |
| Locally configured named MCP servers | `node_repl` only |
| Amazon market-research tools | None |

The `codex_apps` resources concern installed OpenAI templates, GitHub, and Sites. They do not expose Xiyou or Amazon research data. The general `node_repl` MCP is an execution helper, not a market-data provider.

### Workspace inventory

The workspace root contains empty `.git/` and `.agents/` directories and **zero files**. Git reports that the directory is not a repository. Consequently, there is no observable implementation to support claims about the current data model, taxonomy, parent/child handling, keyword model, analysis model, sales allocation, provider coupling, or bottlenecks.

## 2. Xiyou MCP capability matrix

`U` means **unavailable / unverified**, not unsupported by Xiyou. No negative product claim should be inferred from this table.

| Class | Capability | Status | Tool(s) | Marketplace | Query entity | History | Pagination / limits | Auth | Important limitation |
|---|---|---:|---|---|---|---|---|---|---|
| A | Keyword demand | U | Not exposed | U | Keyword: U | U | U | U | Cannot probe |
| B | Keyword trends | U | Not exposed | U | Keyword: U | U | U | U | Cannot probe |
| C | ABA / search-frequency data | U | Not exposed | U | Keyword/ASIN: U | U | U | U | Cannot probe |
| D | Keyword to ASIN relationships | U | Not exposed | U | Keyword/ASIN: U | U | U | U | Cannot probe |
| E | ASIN to keyword traffic sources | U | Not exposed | U | ASIN/parent: U | U | U | U | Cannot probe |
| F | Organic rank | U | Not exposed | U | Keyword/ASIN: U | U | U | U | Cannot probe |
| G | Sponsored rank | U | Not exposed | U | Keyword/ASIN: U | U | U | U | Cannot probe |
| H | SERP | U | Not exposed | U | Keyword: U | U | U | U | Cannot probe |
| I | ASIN sales/revenue estimates | U | Not exposed | U | ASIN/parent: U | U | U | U | Cannot probe |
| J | Parent/child relationships | U | Not exposed | U | ASIN/parent: U | U | U | U | Cannot probe |
| K | Variant/size information | U | Not exposed | U | ASIN/parent: U | U | U | U | Cannot probe |
| L | Category rank | U | Not exposed | U | ASIN: U | U | U | U | Cannot probe |
| M | Pricing | U | Not exposed | U | ASIN: U | U | U | U | Cannot probe |
| N | Reviews/ratings | U | Not exposed | U | ASIN: U | U | U | U | Cannot probe |
| O | Brand/seller | U | Not exposed | U | ASIN: U | U | U | U | Cannot probe |
| P | Listing age/history | U | Not exposed | U | ASIN: U | U | U | U | Cannot probe |
| Q | Historical ASIN trends | U | Not exposed | U | ASIN/parent: U | U | U | U | Cannot probe |

### Relevant tool schemas

No Xiyou tool schema was returned, so there are no sample input or output schemas to report. Inventing schemas from vendor expectations would undermine this architecture decision.

### Rate limits and authentication

No request could be sent to Xiyou, so rate-limit headers, throttling behavior, quota units, authentication scheme, and authorization scope are all unknown. No credential values were inspected or printed.

## 3. Real-market probe

The required terms were not submitted because no Xiyou query tool is callable:

- `compression ball valve`
- `1/4 compression valve`
- `1/4 shut off valve`
- `refrigerator water line shut off valve`
- `swamp cooler parts`

Therefore Xiyou's ability to distinguish the following chain remains unverified:

`Keyword -> customer demand/use case -> product type -> parent product -> variant/size -> competitors`

The probe must preserve ambiguity rather than force one keyword into one product type. At minimum, a valid rerun should compare SERP ASIN overlap, parent grouping, browse/category signals, title/bullet attributes, sizes, traffic-source relationships, and sales estimates across the five phrases.

## 4. Existing-system architecture audit

| Audit area | Finding |
|---|---|
| Existing data model | Not observable; no files or schemas supplied |
| Product taxonomy | Not observable |
| Parent/child model | Not observable |
| Keyword model | Not observable |
| Market-analysis model | Not observable |
| Sales-allocation logic | Not observable |
| Data-source coupling | Not observable |
| Architectural bottlenecks | Not observable |

The proposition that the current model is `Keyword -> Product` was provided in the task, but could not be verified in implementation. Whether it should become `Keyword -> Demand -> Product` cannot be decided from actual system and Xiyou evidence in this run.

## 5. Conditional target architecture

This is a decision framework, not an approved refactor. It becomes justified if the rerun demonstrates that keywords map to multiple intents/use cases or product types, and Xiyou provides enough relationship evidence to resolve those mappings with useful confidence.

1. **Source adapters** — provider-specific request/response translation, authentication boundary, retries, quotas, pagination, and marketplace normalization. Xiyou identifiers and payloads stop here.
2. **Raw evidence** — immutable response envelope and payload, including provider, tool/version, observation time, marketplace, exact query/input, pagination cursor, and request/run ID.
3. **Canonical entities** — `Keyword`, `DemandIntent`, `UseCase`, `ProductType`, `ProductFamily`/parent, `OfferableVariant`/child ASIN, `Brand`, `Seller`, `Category`, and explicit typed relationships.
4. **Derived features** — normalized demand, trend slope, rank stability, SERP overlap, sponsored share, price/review distributions, parent-level deduplication, and variant coverage. Every value references its supporting evidence.
5. **Market analysis** — define markets as demand/use-case and product-type intersections, with explicit inclusion rules and parent/child aggregation policy.
6. **Opportunity scoring** — versioned scoring model over derived features; preserve component values, weights, uncertainty, and model version.
7. **LLM reasoning** — proposes or labels demand intents and taxonomy mappings but never replaces evidence; emits structured claims with confidence and evidence references.
8. **Evidence/audit trail** — append-only lineage from conclusions to features to observations, recording source, observed-at time, marketplace, exact input, transforms, confidence/provenance, and code/model version.

### Provider-neutral evidence envelope (illustrative)

```json
{
  "evidence_id": "...",
  "provider": "xiyou",
  "capability": "serp",
  "provider_tool": "<observed tool name>",
  "provider_tool_version": "<if exposed>",
  "observed_at": "2026-08-13T...+08:00",
  "marketplace": "<observed marketplace code>",
  "input": { "keyword": "compression ball valve" },
  "page": { "cursor": null, "number": 1 },
  "raw_payload_ref": "...",
  "provenance": { "request_id": "...", "collection_run_id": "..." }
}
```

This shape is deliberately illustrative and must not be mistaken for a Xiyou schema.

## 6. What Xiyou newly enables

No newly enabled capability can be claimed in this run. On rerun, the strongest architecture-changing evidence would be:

- bidirectional keyword/ASIN relationships with ranks or traffic shares;
- parent-child resolution and variant attributes;
- historical keyword, rank, pricing, sales, or ASIN series;
- SERP results distinguishing organic and sponsored placements;
- query-level demand or ABA/search-frequency measures;
- stable marketplace-aware identifiers and observation timestamps.

## 7. Keep / modify / remove decisions

Per-module decisions are impossible without the modules. The safe decision ledger is:

| Scope | Decision now | Decision gate |
|---|---|---|
| Production modules | KEEP unchanged | Inspect checkout and trace dependencies |
| Existing datasets/schemas | KEEP unchanged | Profile semantics and lineage before migration |
| Xiyou integration | DO NOT ADD yet | Obtain actual tool schemas and probe results |
| Provider-neutral adapter boundary | PROPOSE only | Confirm Xiyou capability granularity |
| Raw evidence/provenance layer | PROPOSE only | Confirm response metadata and history behavior |
| Demand entity between keyword and product | PROPOSE conditionally | Demonstrate repeatable multi-intent/product-type mappings |
| Existing sales allocation | KEEP pending audit | Compare child-, parent-, and demand-level totals and avoid double counting |
| Existing modules for removal | NONE | Require usage/dependency evidence and replacement plan |

## 8. Recommended migration sequence (after discovery succeeds)

1. Connect Xiyou read-only and snapshot its complete tool/resource schemas.
2. Run the five-term probe in one marketplace and record raw responses and metadata.
3. Check pagination, repeatability, history boundaries, error behavior, quotas, and parent/child semantics.
4. Supply and audit the actual system checkout, schemas, and representative non-production data.
5. Map each current field and calculation to evidence, canonical entity, or derived feature.
6. Write architecture decision records for provider isolation, demand modeling, parent-level aggregation, and sales allocation.
7. Add a provider-neutral evidence layer alongside the current path; do not replace it initially.
8. Backfill a small validation cohort and reconcile old versus new outputs.
9. Introduce `DemandIntent` only if measured ambiguity and decision value justify it.
10. Migrate scoring/analysis consumers incrementally with audit comparisons and rollback gates.

## 9. Risks and unknowns

- Xiyou connection/registration and authentication requirements.
- Exact tools, schemas, field semantics, units, nullability, and versioning.
- Supported Amazon marketplaces and locale behavior.
- Parent ASIN input/output behavior and child completeness.
- Historical coverage, granularity, corrections, and survivorship bias.
- Organic versus sponsored identification quality.
- Sales/revenue estimation methodology and whether parent/child values double count.
- Pagination stability, maximum page depth, rate limits, concurrency, and quota cost.
- Result timestamps versus collection timestamps.
- Current system architecture, production constraints, consumers, and data volumes.
- Whether a demand layer improves accuracy enough to justify migration cost.

## 10. Rerun prerequisites and acceptance criteria

Provide a new task/session in which:

1. The Xiyou MCP appears in the callable MCP tool inventory (not merely in a config file), with read-only credentials already managed by the client.
2. The Amazon market-research repository is actually checked out into the workspace, including schema/migration definitions and architecture documentation where available.
3. A non-production or read-only marketplace scope is authorized for the five test keywords.

The discovery is complete only when the report replaces every `U` with observed support/non-support, includes actual redacted sample schemas and probe evidence, traces current implementation paths, and bases the final architecture recommendation on those observations.
