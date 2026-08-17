# GITHUB REUSABLE COMPONENT AUDIT V0.1

- Task: `TASK-SP-003C`
- Project: 亚马逊智能选品系统（Amazon US）
- Audit date: 2026-08-14
- Repository baseline: `7e2aaf3163d0521538b66627170efba4d9e78704`
- Branch: `main`
- Audit mode: GitHub read-only inspection; no clone, install, code copy, integration, commit, push, tag, PR, or remote creation
- Architecture authority: `docs/requirements/亚马逊智能选品系统_产品需求与核心架构说明_V0.2.md` and the current Level 2 canonical/evidence designs

## A. Executive Summary

### Decision

`REUSE_OPPORTUNITIES_FOUND`

This is a component-level decision, not approval to import a repository wholesale. No audited component clears the conservative `REUSE_DIRECTLY` gate today. Three areas merit a later, separately approved adaptation task:

1. Generic provider-call infrastructure and contract-test patterns from `cosjef/keepa_MCP`.
2. Run/input/output/schema-version lineage patterns from `OpenLineage/OpenLineage` for designing Transformation Provenance.
3. Dependency-free authenticated request, secret-hygiene, payload-catalog, and repository-validation patterns from `nexscope-ai/amazon-data-api`.

The system's differentiating semantics remain `BUILD_OURS`: Canonical Observation, presence/missing/zero, evidence types, transformation provenance contract, conflict and resolution, Product Intelligence, Demand Intelligence, Product–Demand Relevance, True Competitor, Market Reconstruction, and provider disagreement.

The two Sorftime/Sif seed repositories are especially unsuitable for direct reuse. They lack a complete root license grant and contain committed credential values. Several candidates also coerce absent provider fields to `0`, equate keyword metrics with demand, treat retrieved products as competitors, or embed opportunity thresholds. Those behaviors conflict with the frozen Evidence-First / Provider-Agnostic architecture.

### Recommended posture

| Layer | Posture |
|---|---|
| Provider transport, error normalization, throttling, typed tool inputs | `ADAPT_AND_REUSE`, behind our Provider Adapter contract |
| Transformation run envelope and lineage vocabulary | `REFERENCE` now; consider `ADAPT` after Level 2 design/schema remediation |
| Raw evidence manifests, immutable capture, canonicalization | `BUILD_OURS` |
| Review/keyword workflows and report layouts | `REFERENCE_ONLY`; reuse only generic patterns after independent validation |
| Business scoring, competitor logic, demand/relevance semantics | `BUILD_OURS`; reject external hard-coded rules |

### SP-004 gate

`TASK-SP-004` remains `NOT READY`. OpenLineage is useful design evidence, but it does not add the required project-specific `collection_run_id`, `provider_schema_version`, `mapping_version`, and `transformation_run_id` semantics to the authoritative Level 2 design and JSON Schema. This audit does not modify those files and therefore does not clear the blocker.

## B. Search Method

### Baseline and write boundary

Before discovery, Git state was recorded as:

- valid worktree: yes;
- `HEAD`: `7e2aaf3163d0521538b66627170efba4d9e78704`;
- branch: `main`;
- remotes: none;
- staging: empty;
- pre-existing untracked files, not owned or modified by this task:
  - `ARCHITECTURE_AUDIT_PRODUCT_DEVELOPMENT_V1.md`;
  - `ARCHITECTURE_DISCOVERY_REPORT.md`;
  - `docs/requirements/亚马逊智能选品系统_产品需求与核心架构说明_V0.2.md`.

The only project artifact created by this task is this report.

### Queries

The GitHub repository search inspected the top 10 results where available for each required query:

1. `amazon product research`
2. `amazon product research MCP`
3. `amazon competitor analysis`
4. `amazon keyword research`
5. `amazon market research`
6. `amazon review analysis`
7. `amazon product intelligence`
8. `amazon seller research`
9. `sorftime MCP amazon`
10. `amazon evidence provenance`

Focused follow-ups were also run for:

- `transformation provenance lineage JSON Schema`
- `data lineage provenance Python JSON Schema`
- `OpenLineage provenance`

The official `OpenLineage/OpenLineage` repository was then directly inspected because generic Amazon provenance search results were low relevance and did not surface a mature transformation-lineage standard.

### Candidate accounting

- 71 distinct repositories appeared across the 10 required search result sets.
- Three mandatory seeds not present in those result sets were added directly.
- Two focused-provenance results and the official OpenLineage repository were considered.
- Total distinct repository records considered: 77.
- Final deeply audited independent repositories: 8.

The 8 deep audits all included actual tree inspection, legal files, entrypoints/business modules, dependencies, tests or their absence, representative source, and security behavior. README-only review was not used for final decisions.

### Fork and copied-repository removal

The five mandatory seeds report `fork=false` in GitHub metadata and were treated as the originals for this audit. Search-result duplication was removed before ranking. Confirmed exclusions include:

| Excluded repository | Evidence | Disposition |
|---|---|---|
| `hkxiaoyao/amazon-sorftime-research-MCP-skill` | GitHub reports `fork=true`; parent is `liangdabiao/amazon-sorftime-research-MCP-skill` | exclude fork |
| `lucy6116/amazon-sorftime-research-MCP-skill` | GitHub reports `fork=true`; same parent | exclude fork |
| `asl4/amazon-sorftime-research-MCP-skill` | reports `fork=false`, but shares exact blob hashes for `CLAUDE.md` and the Chinese requirements file with the seed | exclude copied lineage, no material component-level advantage established |
| `reloadggg/amazon-skills` | GitHub reports `fork=true`; parent is `maijushidai/amazon-skill` | exclude fork |
| `stamns/amazon-skills` | GitHub reports `fork=true`; same parent | exclude fork |

Other same-theme repositories were excluded after first-pass relevance screening when they were coursework notebooks, sentiment demos, prompt copies, thin API advertisements, unrelated blockchain provenance projects, or lacked meaningful reusable infrastructure. They were not counted as deep audits merely to reach a quota.

### Evidence standard and limitations

- Metadata and content were read from GitHub on the audit date; activity, stars, and forks are point-in-time indicators.
- License classification used actual `LICENSE`/`COPYING`/`NOTICE`, package metadata, source headers, and README declarations. GitHub's license badge alone was not accepted.
- Candidate test suites were inspected but not executed. No candidate was cloned or installed.
- Hosted provider behavior, API terms, account quotas, and endpoint availability were not exercised. An open-source client license does not grant rights to a hosted API or its data.
- Security findings identify committed credential material without reproducing the secret values. All credential strings are intentionally masked in this report.

## C. Repository Matrix

| Repository | Upstream/original | Description / type | Branch | Archived | Language | Last push | Stars / forks | Repository-level conclusion |
|---|---|---|---|---|---|---|---|---|
| [`liangdabiao/amazon-sorftime-research-MCP-skill`](https://github.com/liangdabiao/amazon-sorftime-research-MCP-skill) | yes; `fork=false` | Sorftime/XiYou/Sif/SellerSprite agent skills, scripts, and generated reports; mixed prompt/workflow asset plus provider-coupled utilities | `main` | no | Python | 2026-07-08 | 705 / 106 | `REJECT` direct reuse; limited `REFERENCE_ONLY` workflow value |
| [`liangdabiao/sif-amazon-research`](https://github.com/liangdabiao/sif-amazon-research) | yes; `fork=false` | Sif MCP HTTP client, tool wrappers, analysis modules, Express API, and UI | `main` | no | JavaScript | 2026-06-12 | 22 / 7 | `REJECT` direct reuse; generic MCP flow is `REFERENCE_ONLY` |
| [`nexscope-ai/Amazon-Skills`](https://github.com/nexscope-ai/Amazon-Skills) | yes; `fork=false` | 50+ Amazon prompt/skill assets with a few small scripts | `main` | no | Python | 2026-07-23 | 537 / 89 | `REFERENCE_ONLY`; not a reusable application/core library |
| [`aws-samples/analyze-customer-reviews-through-amazon-bedrock`](https://github.com/aws-samples/analyze-customer-reviews-through-amazon-bedrock) | yes; `fork=false` | S3 → Lambda → Bedrock → DynamoDB → SNS review-summary sample | `main` | no | Python | 2024-10-01 | 4 / 0 | `REFERENCE_ONLY`; cloud/provider coupling and no evidence contract |
| [`omkarcloud/amazon-scraper`](https://github.com/omkarcloud/amazon-scraper) | yes; `fork=false` | Despite its name, mainly a Botasaurus/RapidAPI client wrapper for search and product calls | `master` | no | Python | 2026-06-29 | 227 / 19 | `REJECT` integration; simple retry/pagination ideas only |
| [`cosjef/keepa_MCP`](https://github.com/cosjef/keepa_MCP) | yes; `fork=false` | TypeScript Keepa MCP server with Zod schemas, client throttling, and Jest tests | `main` | no | TypeScript | 2026-02-11 | 31 / 11 | `ADAPT_AND_REUSE` selected infrastructure only; reject business scoring |
| [`nexscope-ai/amazon-data-api`](https://github.com/nexscope-ai/amazon-data-api) | yes; `fork=false` | Hosted-API catalog, dependency-free sample clients, payload fixtures, secret scan, CI validation | `main` | no | Python | 2026-08-12 | 7 / 0 | `ADAPT_AND_REUSE` adapter/test patterns only; hosted API remains optional provider |
| [`OpenLineage/OpenLineage`](https://github.com/OpenLineage/OpenLineage) | yes; `fork=false` | Mature cross-language lineage specification, clients, facets, versioning, tests | `main` | no | Java | 2026-08-14 | 2600 / 512 | `REFERENCE` for core provenance; `ADAPT_AND_REUSE` only for an optional lineage envelope/export |

None is approved for wholesale adoption. No repository-level score can override the component decisions below.

## D. License Audit

| Repository | Files actually checked | Classification | Direct-use gate | Future obligations / issues |
|---|---|---|---|---|
| `liangdabiao/amazon-sorftime-research-MCP-skill` | root tree, README, representative Python files and headers; no `LICENSE`, `COPYING`, or `NOTICE` | `NO_LICENSE` | `REFERENCE_ONLY`; code copying prohibited | Public visibility is not a license. Separately authored report/data provenance is also unclear. |
| `liangdabiao/sif-amazon-research` | root tree, README, `package.json`, representative JS headers; no legal file | `UNCLEAR_LICENSE` | `REJECT_DIRECT_REUSE` | `package.json` says MIT, but no root license text/copyright grant exists. Clarification is required before copying. |
| `nexscope-ai/Amazon-Skills` | root `LICENSE`, README, skill files, scripts | `PERMISSIVE — MIT` | legally eligible, technically `REFERENCE_ONLY` | If substantial code/text is distributed, retain the Nexscope AI copyright and MIT permission notice. |
| AWS review sample | root `LICENSE`, source, CloudFormation | `PERMISSIVE — MIT-0` | legally eligible, technically `REFERENCE_ONLY` | MIT No Attribution imposes no attribution condition; preserve origin/license as engineering practice. AWS service terms are separate. |
| `omkarcloud/amazon-scraper` | root `LICENSE`, README, source, `SECURITY.md`, dependencies | `PERMISSIVE — MIT` | legally eligible, technically rejected | Retain Chetan Jain copyright and MIT notice. RapidAPI/API/data terms are separate. |
| `cosjef/keepa_MCP` | root `LICENSE`, `package.json`, source and tests | `PERMISSIVE — MIT` | eligible for later selected adaptation | Retain Jeffrey Costa copyright and MIT notice. Keepa API/data terms and key requirements are separate. |
| `nexscope-ai/amazon-data-api` | root `LICENSE`, README, source, CI, `SECURITY.md` | `PERMISSIVE — MIT` | eligible for later selected adaptation | Retain Nexscope copyright and MIT notice. Hosted Nexscope service/account terms are separate and explicitly stated in README. |
| `OpenLineage/OpenLineage` | root `LICENSE`, `NOTICE.txt`, Python subproject license/metadata, source SPDX headers | `PERMISSIVE — Apache-2.0` | eligible for later selected adaptation | Ship Apache-2.0 text, mark modified files, retain applicable notices, include applicable `NOTICE.txt` attributions, and respect trademark/patent clauses. |

Legal conclusion: three repositories are viable only for reference (`NO_LICENSE` or incomplete grant), while five have permissive licenses. Permissive licensing does not cure architectural mismatch, provider lock-in, poor tests, or security problems.

## E. Component Reuse Findings

### E.1 Formal reuse matrix

| Repository | Component | License | Architecture fit | Provider coupling | Dependency risk | Test quality | Decision |
|---|---|---|---|---|---|---|---|
| Sorftime skill | SSE decoding / encoding repair | no license | medium as ingestion utility; no provenance contract | high | low runtime, but undeclared environment assumptions | ad-hoc script tests only | `REFERENCE_ONLY` |
| Sorftime skill | raw-response/report directory conventions | no license | partial; raw response is kept in some flows but no immutable manifest/hash/run lineage | high | medium | no contract tests | `REFERENCE_ONLY` |
| Sorftime skill | provider field adapter and market KPI/scoring | no license | poor; missing values default to zero, US is hard-coded, thresholds define business truth | high | low | no adequate semantic tests | `REJECT` |
| Sorftime skill | MCP configuration and API client | no license | poor | high | curl/subprocess plus provider endpoints | none | `REJECT` — committed credentials |
| Sif research | generic JSON-RPC initialize / `tools/list` / `tools/call` flow | unclear | medium as a protocol sketch | medium/high | Node core | live example only | `REFERENCE_ONLY` |
| Sif research | error envelope and parallel keyword calls | unclear | partial; retains `rawData` but normalizes missing fields to zero/defaults | high | low | live endpoint script, no mocks/CI | `REFERENCE_ONLY` |
| Sif research | demand/opportunity/competitor modules | unclear | poor; hard-coded scores and fallbacks (`0`, `stable`, `medium`, `50`) become business meaning | high | low | no semantic tests | `REJECT` |
| Sif research | Express reports/UI | unclear | low/medium utility, but broad CORS and sync local side effects | high | Express/CORS | no server tests | `REJECT` |
| Amazon-Skills | product/keyword/review/competitor workflows | MIT | useful discovery checklists, not evidence-bearing implementation | medium | web-search/agent runtime | no workflow tests | `REFERENCE_ONLY` |
| Amazon-Skills | FBA/fee and tariff calculators | MIT | low; dated rates and domain assumptions require independent source verification | medium | mostly standard library | no tests observed | `REFERENCE_ONLY` |
| Amazon-Skills | Amazon autocomplete shell collector | MIT | low/medium for candidate generation only | medium | Bash, curl, Python | no tests | `REJECT` direct reuse — unsafe interpolation and silent network/error handling |
| AWS review sample | event-driven review-analysis pipeline | MIT-0 | medium as a deployment pattern | high (AWS + Bedrock) | S3, Lambda, Bedrock, DynamoDB, SNS, CloudFormation | no tests | `REFERENCE_ONLY` |
| AWS review sample | LLM sentiment/action-items JSON | MIT-0 | poor as canonical evidence; model output is parsed and persisted as truth without raw lineage/validation | high | Anthropic model via Bedrock | no tests | `REJECT` for business semantics |
| Amazon scraper | request/retry/pagination sketch | MIT | low; errors are collapsed and raw response provenance is not captured | high (RapidAPI product) | Botasaurus, requests, casefy, hosted API | no tests | `REFERENCE_ONLY` |
| Amazon scraper | search/product data ingestion | MIT | poor for core; results are emitted directly and cache/output are mutable | high | RapidAPI subscription and credits | no tests | `REJECT` |
| Keepa MCP | typed MCP input schemas and tool registration | MIT | high if separated from Keepa/domain semantics | medium | MCP SDK, Zod, TypeScript | schema unit tests present | `ADAPT_AND_REUSE` |
| Keepa MCP | throttling, timeout, token/error normalization, batch slicing | MIT | medium/high inside a provider adapter | high at source, removable by interface extraction | Axios | partial unit tests; network mocking not comprehensive | `ADAPT_AND_REUSE` |
| Keepa MCP | category/deal/opportunity/profit calculations | MIT | poor; heuristic thresholds, invented competition assumptions, missing/default coercions | high | same | insufficient semantic validation | `REJECT` |
| Keepa MCP | provider mocks/schema fixtures | MIT | medium/high as testing pattern | medium | Jest/ts-jest | present; no visible CI/coverage artifact | `ADAPT_AND_REUSE` |
| Amazon Data API | dependency-free bearer client shell, slug validation, timeout | MIT | high inside optional Provider Adapter | high endpoint coupling, structurally isolatable | Python stdlib or Node 18 | examples validated by CI, not behavior tests | `ADAPT_AND_REUSE` |
| Amazon Data API | payload catalog and secret-hygiene validator | MIT | high for adapter fixtures/repository checks | low/medium | Python stdlib + GitHub Actions | deterministic CI validation | `ADAPT_AND_REUSE` |
| Amazon Data API | hosted market/opportunity outputs | MIT code; service terms separate | poor as canonical truth; methods/estimates are provider-defined | high | hosted API/account credits | no provider-behavior tests | `REFERENCE_ONLY` / adapter only |
| OpenLineage | run/job/input/output event envelope and schema version URI | Apache-2.0 | high as lineage vocabulary; not the project's full provenance contract | none | JSON Schema alone is low; full client is medium/high | extensive spec, unit and integration tests | `REFERENCE_ONLY` for core design; optional `ADAPT_AND_REUSE` export |
| OpenLineage | parent/root run and processing/source-code facets | Apache-2.0 | high inspiration for transformation execution context | none | modular schema; client optional | facet fixtures and CI | `REFERENCE_ONLY` |
| OpenLineage | Python serialization/client | Apache-2.0 | medium/poor for canonical core because serialization drops null/empty fields and semantics target jobs/datasets | none | attrs, dateutil, YAML, requests, httpx; optional Kafka/cloud stacks | strong, configured 90% coverage floor | `REJECT` direct core reuse; `ADAPT` only behind translation boundary |

### E.2 Provider / MCP infrastructure

Best candidate: `cosjef/keepa_MCP`, followed by the minimal clients in `nexscope-ai/amazon-data-api`.

Reusable ideas are explicit timeout, input schema validation, rate-delay handling, batch bounds, provider error categories, environment-based secrets, and testable tool registration. The provider-specific field models and scores must stay inside an adapter or be removed. Neither project supplies the complete retry/backoff/jitter/quota/circuit-breaker/tracing contract required by this system.

The Sif JSON-RPC client is a readable protocol sketch but has no mock-driven tests, retry policy, response-size limit, status handling, or safe complete license. It is not an adoption candidate.

### E.3 Raw evidence capture

No audited repository implements the required complete chain:

`immutable raw payload + deterministic content identity + request metadata + provider/tool/schema version + collection run + manifest + transformation run + mapping version`.

Some Sorftime workflows save raw SSE and some Sif modules return `rawData`; those are useful observations, not a trustworthy evidence subsystem. Omkar writes cache/output files but does not make them immutable or lineage-addressed. Therefore raw evidence capture is `BUILD_OURS`.

### E.4 Serialization and contract infrastructure

Keepa MCP shows useful Zod input schema and unit-test patterns. OpenLineage shows versioned JSON Schema identifiers, generated typed models, explicit run states, UUID validation, and schema fixtures. These are implementation references, not substitutes for the project's presence/evidence/conflict semantics.

OpenLineage's Python serializer intentionally omits null/empty nested values in inspected tests. That is incompatible with the project's requirement that `UNKNOWN`, `MISSING`, `EXPLICIT_NULL`, `QUERY_RETURNED_EMPTY`, and numeric zero remain distinguishable. A translation layer would be mandatory.

### E.5 Provenance and lineage

OpenLineage is the only mature candidate found. Its strongest applicable patterns are:

- globally unique run identity;
- run lifecycle states;
- producer and resolvable schema-version URI;
- input/output dataset references;
- parent/root run relationships;
- processing engine/adapter version;
- source-code location and deployed version;
- versioned, independently testable facets.

It does not directly define the project's provider observation identity, raw evidence reference, field mapping version, presence status, evidence type, or conflict/resolution chain. The project's Level 1 requirements remain authoritative. Recommendation: use OpenLineage as a design cross-check and possibly expose an optional OpenLineage-compatible event later; do not make it the canonical storage contract.

### E.6 Product/review/keyword/similarity/report/test utilities

- Product parsing: no provider-agnostic, well-tested Amazon listing normalizer was found among the audited repositories. `BUILD_OURS` behind provider adapters.
- Review normalization: AWS provides an event pipeline example, not dedupe/normalization/evidence semantics. `BUILD_OURS`; LLM topic extraction remains `REFERENCE_ONLY`.
- Keyword processing: autocomplete and provider query orchestration can generate candidates; they cannot define Demand Intelligence. Generic normalization/dedupe may be implemented independently.
- Similarity: none of the deep-audited projects provides a project-compatible final relevance model. Similarity may only generate candidates or assist dedupe.
- Reporting: low-coupling report/CLI structures exist, but the strongest examples either lack a license, are prompt assets, or mix business assumptions. Build a small project-native renderer; reference layouts only.
- Testing: Keepa's schema tests, Nexscope's payload/secret validation, and OpenLineage's JSON fixtures/version/serialization tests are the strongest reusable patterns.

## F. SP-004 Reuse Findings

| SP-004 area | Best evidence | Classification | Recommendation |
|---|---|---|---|
| Typed model framework | Keepa Zod schemas; OpenLineage generated models | `REFERENCE` | Select the project's own typed framework and author contracts from frozen semantics. Do not copy a repository model wholesale. |
| Serialization | OpenLineage Serde and fixtures | `REFERENCE` | Build ours; preserve explicit absence states and deterministic canonical JSON. Do not adopt null-dropping behavior. |
| Enum / presence model | no aligned candidate | `BUILD_OURS` | Define the full project presence state machine; no candidate distinguishes all required states. |
| JSON Schema | OpenLineage draft 2020-12, `$id`, facets, schema tests | `ADAPT` pattern | Use versioning/test patterns after a separate approved Level 2 remediation; project schema content remains ours. |
| Deterministic identity | OpenLineage validates UUID run IDs, but does not define deterministic observation IDs | `BUILD_OURS` | Define canonical identity inputs, normalization, hashing/UUID policy, collision/version rules. |
| Transformation provenance | OpenLineage run/input/output/parent/source facets | `REFERENCE` / optional `ADAPT` | Map concepts to project-specific collection/mapping/transformation context; do not replace required fields. |
| Validation | Keepa Zod tests; OpenLineage schema fixtures | `ADAPT` pattern | Reuse test structure and fail-closed validation approach, not domain rules. |
| Conflict representation | no aligned candidate | `BUILD_OURS` | Preserve project conflict taxonomy, units, semantics, provider disagreement and unresolved outcomes. |

Overall SP-004 recommendation: `BUILD_OURS`, informed by selected validation/versioning/lineage patterns. The audit finds no codebase whose canonical contract semantics are sufficiently aligned for direct adoption.

The current blocker remains unchanged: Transformation Provenance must first be incorporated into the authoritative Level 2 Technical Design and JSON Schema through a separate approved task. This report neither performs nor authorizes that change.

## G. Future Module Findings

### Provider Adapter

`ADAPT_AND_REUSE` generic transport/schema/test patterns from Keepa MCP and Amazon Data API. Each provider must remain an infrastructure plug-in. Provider results must be retained as raw evidence before mapping; hosted API terms and quotas require separate approval.

### Product Intelligence

`BUILD_OURS`. External field parsers can later be assessed within individual adapters, but the product concept, attribute evidence, variations, units, uncertainty, and derived intelligence contracts are project-owned.

### Demand Intelligence

`BUILD_OURS`. Amazon-Skills and Sif offer keyword workflows and provider fields, but frequently equate keywords/search volume/opportunity scores with demand. Only candidate collection, normalization, and dedupe utilities may be adapted.

### Product–Demand Relevance

`BUILD_OURS`. No candidate implements the required multi-evidence semantics. String/embedding similarity may only produce candidates or preprocessing clusters.

### Market Reconstruction

`BUILD_OURS`. Search result sets, Keepa results, or provider competitor outputs cannot be accepted as True Competitors without project relevance and evidence validation.

### Review / Demand–Supply Gap

`BUILD_OURS` for review normalization, dedupe, evidence linkage, issue taxonomy, and gap inference. AWS's event-driven summary flow is `REFERENCE_ONLY`; model summaries must be stored as derived evidence with prompt/model/version/input lineage and validation.

### Reporting / UI

Build a small project-native Markdown/JSON/HTML reporting layer. Layout and progress patterns can be referenced, but no candidate currently clears both license and architecture/test gates for direct import.

### Testing infrastructure

`ADAPT_AND_REUSE` patterns: provider mocks and schema boundary cases from Keepa; payload catalog, secret scan, and CI validation from Amazon Data API; JSON Schema/serialization/version fixtures from OpenLineage. Add project-specific tests for missing-vs-zero, units, directionality, provider disagreement, provenance reproducibility, and fail-closed conflict handling.

## H. Reuse Risks

### Licensing

1. Two high-relevance seed repositories do not provide a complete root license grant.
2. Prompt/report repositories may include generated data or third-party text whose provenance is not established by the repository license.
3. Hosted API/data access terms remain separate from open-source client licenses.
4. Apache-2.0 adaptations require modification notices and applicable `NOTICE.txt` handling.

### Architecture and business semantics

1. Multiple sources use `x || 0`, default `stable/medium`, or default opportunity scores, violating Missing ≠ Zero and fail-closed semantics.
2. Sif, Sorftime, Keepa, RapidAPI, AWS, and Nexscope business models are provider-coupled.
3. External opportunity thresholds and weighted scores are unvalidated business rules and stay `REFERENCE_ONLY` or `REJECT`.
4. Search result or provider competitor lists do not establish True Competitor status.
5. Keyword/autocomplete signals do not establish Demand Intelligence.
6. LLM summaries are derived claims, not raw observation or resolved truth.

### Dependency and operations

1. Full OpenLineage clients and integrations add more dependencies than the narrow provenance need warrants.
2. AWS review sample requires multiple managed services and a specific Bedrock model.
3. Omkar depends on Botasaurus plus a commercial RapidAPI product despite the scraper name.
4. Keepa and Nexscope require provider accounts, keys, quotas, and separate service availability.
5. Several repositories have no retry jitter, circuit breaker, observability, bounded response size, or production-grade rate-limit policy.

### Maintenance and tests

1. Sorftime and Sif test files are mostly live/ad-hoc scripts, not deterministic suites.
2. Amazon-Skills, AWS review sample, and Omkar have no meaningful behavior tests in the inspected tree.
3. Keepa has useful tests but limited network/error mocking and no visible CI workflow.
4. Amazon Data API validates documentation/payload consistency, not hosted API semantics.
5. OpenLineage has the strongest maintenance/test posture but its domain and serialization rules differ from ours.

### Security

1. `liangdabiao/amazon-sorftime-research-MCP-skill/.mcp.json` contains committed credential values for multiple providers. Values are not reproduced here. Treat them as exposed and rotate/revoke them; do not copy the file.
2. `liangdabiao/sif-amazon-research/config.json` contains a committed Sif credential despite the repository's own ignore guidance. Treat it as exposed and rotate/revoke it.
3. Amazon-Skills' autocomplete shell embeds user input into `python3 -c`; crafted quotes can alter executed Python. It also performs silent network calls without a timeout or explicit HTTP failure handling.
4. Sorftime's client places the API key in a URL used by a subprocess, increasing process/log/history exposure risk.
5. AWS sample logs model response objects and processed output; review content and sensitive payloads need redaction/retention policy.
6. Any scraper/API integration requires legal, privacy, marketplace-term, and data-retention review before production use.

## I. Recommended Reuse Backlog

These are proposals only. None is implemented or authorized by this audit.

### REUSE-001 — Generic provider transport contract

- candidate: `cosjef/keepa_MCP`
- component: timeout, throttling, batch bounds, error normalization, typed MCP tool inputs
- source license: MIT
- target future task: dedicated Provider Adapter infrastructure task after canonical contracts are ready
- expected benefit: reduce repeated transport boilerplate and establish consistent adapter behavior
- required adaptation: remove Keepa models/scores, add retry/backoff/jitter, tracing, raw capture, quota state, normalized errors, and project interfaces
- risk: high provider coupling in source; partial tests only

### REUSE-002 — Transformation lineage design cross-check

- candidate: `OpenLineage/OpenLineage`
- component: run lifecycle, input/output references, parent/root run, producer/schema version, processing/source-code facets
- source license: Apache-2.0
- target future task: separately approved Level 2 Transformation Provenance design/schema remediation, before SP-004
- expected benefit: mature vocabulary and test/versioning patterns reduce omissions
- required adaptation: add project-specific collection, provider schema, mapping, transformation, raw evidence, presence, and observation identity semantics
- risk: adopting the full client would be excessive; serializer semantics can erase explicit absence

### REUSE-003 — Secure minimal provider client shell

- candidate: `nexscope-ai/amazon-data-api`
- component: environment-only token, validated endpoint slug, bounded request, dependency-free clients
- source license: MIT
- target future task: optional Nexscope provider-adapter spike, only if product owner approves the provider and its service terms
- expected benefit: small dependency footprint and clear authentication/error boundary
- required adaptation: add retries, tracing, raw immutable capture, response schema validation, provenance, and provider-neutral output mapping
- risk: hosted-provider lock-in, credits, data-method opacity

### REUSE-004 — Contract and fixture testing patterns

- candidates: `cosjef/keepa_MCP`, `OpenLineage/OpenLineage`, `nexscope-ai/amazon-data-api`
- component: schema boundary tests, deterministic payload fixtures, schema-version checks, secret scan, catalog consistency
- source licenses: MIT / Apache-2.0
- target future task: SP-004 test design after blocker clearance
- expected benefit: stronger fail-closed contracts and reproducibility
- required adaptation: add project presence, unit, direction, conflict, identity, and transformation-provenance cases
- risk: copying fixtures without matching semantics would create false confidence

### REUSE-005 — Review pipeline architecture reference

- candidate: `aws-samples/analyze-customer-reviews-through-amazon-bedrock`
- component: event-driven ingestion → model → persistence → notification topology
- source license: MIT-0
- target future task: later Review / Demand–Supply Gap architecture exploration
- expected benefit: a concise reference for decoupled batch processing
- required adaptation: cloud-neutral boundaries, raw evidence retention, dedupe, prompt/model/version lineage, output validation, PII/log controls
- risk: AWS/model lock-in and unvalidated model-as-truth behavior

### REUSE-006 — Provider error and secret-hygiene checklist

- candidates: `nexscope-ai/amazon-data-api`, `cosjef/keepa_MCP`
- component: 401/402/403/429/5xx categories, token exhaustion, environment secrets, public-file secret scan
- source licenses: MIT
- target future task: Provider Adapter non-functional requirements
- expected benefit: consistent operator-visible failures without leaking credentials
- required adaptation: project error codes, retryability, provider/raw request references, redaction tests
- risk: provider meanings differ and must not be flattened blindly

## J. Explicit BUILD_OURS List

The following remain project-owned even if generic libraries are later used:

1. Canonical Observation semantics and deterministic observation identity.
2. Evidence Type semantics: observed, provider estimate, resolved, derived, and their legal transitions.
3. Presence model: unknown, missing, explicit null, empty query result, semantic uncertainty, provider sentinel, and numeric zero.
4. Raw Evidence manifest, immutable storage policy, request/response identity, hashing, retention, and replay.
5. Transformation Provenance contract: collection run, provider schema version, mapping version, transformation run/code version, input/output references.
6. Unit, period, scope, direction, and semantic compatibility rules.
7. Conflict taxonomy, validation, fail-closed behavior, and unresolved representation.
8. Resolution model and provider disagreement handling; no silent averaging.
9. Product Intelligence contract and provider-agnostic product/variation/attribute semantics.
10. Demand Intelligence contract and keyword-to-demand transformation.
11. Product–Demand Relevance semantics; similarity remains auxiliary only.
12. True Competitor logic and Market Reconstruction.
13. Demand–Supply Gap and Opportunity Intelligence business semantics.
14. Human final-decision boundary and explanation/evidence requirements.
15. Project-specific security, logging, redaction, audit, and credential-handling policy.

## Final Decision

`REUSE_OPPORTUNITIES_FOUND`

Reason: mature and permissively licensed infrastructure patterns exist for provider transport, schema/test fixtures, secret hygiene, and lineage vocabulary. They can reduce future implementation risk only after being isolated behind project contracts. The core evidence and intelligence semantics are not available in a sufficiently aligned external repository and must remain `BUILD_OURS`.

No reuse backlog item is implemented by this task. `TASK-SP-004` has not started and remains blocked.
