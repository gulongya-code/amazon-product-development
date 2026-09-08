# SP-043B Operator Market Report Business Decision Layer V0.3

## Baseline and Git boundary

- Baseline HEAD and upstream: `a44ca8010783b9d8a4de0c693c3af6537f27a154`.
- Starting branch: `codex/task-sp-043a-final-market-intelligence-integration`.
- Work branch: `codex/task-sp-043b-operator-market-report-v0-3`.
- Starting index: empty. No modified tracked files.
- One pre-existing untracked SP-042H validation document remains unrelated and excluded.
- Preserved stash: `stash@{0}`, `4e42cf86c7018790af36cb092b0938e02466ec5e`.
  It was not applied, popped or deleted.
- Remote SP-043A head was verified at the exact baseline. The SP-043B branch did
  not exist remotely before publication. The default/release branch remains
  `codex/release-market-report-v0.1` at `4db2c52e8f62d8c23db923338c68bb9f2500b5a1`.
- No merge, rebase, default/release update or final-release tag is part of this task.

The task authorizes an additive report-layer feature branch/commit, with business
value explicitly awaiting human review. It does not reopen or change the released
Semantic/Route acceptance gates.

## Architecture and unchanged engines

The existing provider-neutral integration pipeline is reused unchanged. The new
report builder consumes its bound governed dataset, Semantic and Route results,
and Competition/Opportunity references. It validates upstream IDs/fingerprints,
projects descriptive metrics on the exact released memberships, then produces a
canonical immutable V0.3 report and one shared localized presentation spec.

The renderer contains no category/provider classification logic. The existing
V0.1/V0.2 renderers and contracts remain intact. Only the package-data declaration
is added to the existing project metadata; implementation resides in a new
report-owned module. The normative report extension is documented in
`docs/requirements/OPERATOR_MARKET_REPORT_V0_3.md`.

Zero diff from the baseline was verified for all four released trees:

| Tree | Unchanged Git tree fingerprint |
|---|---|
| Semantic Engine V2 | `46483a0e050defac0847aa11201f44fd3a33c017` |
| Route Discovery V2 | `be3db5f0e37cff0c61e5fe68186decf134d630b2` |
| Category semantic profiles | `48dd7cd2b469f832d103f011678d205a7cb1ff5c` |
| Route configuration | `f6a14ac7201d4f57a9009e88eb01bc70a8d378b8` |

Raw semantic-profile file SHA-256 values are also unchanged:

- Shower Caddy: `c23d9a1798cf8dc43188be43b310708c1d91f5bcc75f18b05c902e17e73aa076`.
- Air Fryer: `b53f2ab02e264911c0e3db8b4bc19362ec483dcd8fcd4d3c16fa7c488108e524`.

Final SP-043B implementation source-bundle SHA-256:
`c20d9c3de932bee125d38346ed87d9b9b0744bbd45ddf3d67d14666151d6c36d`.
This hashes canonical JSON of sorted path/raw-file-SHA pairs for the eight V0.3
module/renderer files, private runner, report profile and package metadata.

## Hierarchy and business metrics

- Each released Route belongs to exactly one display family. The family totals
  are recomputed from disjoint listing sets; no duplicate Route membership is
  introduced. Family and mechanism rollups are alternative, non-additive views.
- Wall-mount children can be compared by adhesive, suction and unspecified
  mechanism across structural forms. Recessed/built-in is independent. No
  unspecified mounting evidence becomes screw/mechanical authority.
- Shower Caddy price bands are `[0,10)`, `[10,20)`, `[20,40)`, and `[40,+infinity)`
  USD, plus unknown. Generic fallback boundaries are 10/25/50/100 USD. These are
  explicit report-policy intervals, not semantic or release thresholds.
- Review bands are 0–50, 51–200, 201–1000 and 1001+, plus unknown. Low-review
  demand share and the number of low-review listings with observed positive sales
  prevent a low median from being presented as automatic opportunity.
- Inclusive 180/365-day windows expose known/unknown age, new sales share, median
  sales/reviews and paired-cohort efficiency. Missing age is not old. Derived age
  is bound to governed dates. Success counts/shares remain unavailable because
  no governed success definition exists.
- Private top-brand/seller tables show listing/sales shares, price/review medians,
  Top 1/3/5 and long tail, with explicit identity and sales coverage.
- Growth uses valid current/prior reconstruction, not an average of percentages.
  Explanation facts carry reason codes, JSON pointers and exact values. Thin
  growth coverage cannot alone trigger priority research.

## Decision readiness and localization

Technical report status is separate from business decision readiness. The report
warning policy uses 50% minimum assigned coverage, 80% minimum sales evidence and
50% high-unassigned-exposure boundary. These govern presentation only and do not
alter any released threshold. Every recommendation is scoped to covered Routes,
not the whole category. Missing Buyer Needs, costs and margin block launch claims.

Chinese is the default locale. The same data and renderer support en-US. All 15
sheet names, business headers, known Route labels, conclusions, explanations,
warnings, availability labels and eleven human-review questions are localized.
Technical IDs and machine reason pointers remain in Audit. Buyer Needs are not
inferred from titles, claims or special features.

## Regression qualification

The final full repository suite ran to completion in 191.73 seconds with no
300-second process limit:

- 1,652 passed.
- 13 skipped.
- 550 subtests passed.
- 1 exactly reproduced, already accepted Windows OOXML fingerprint exception.
- 0 new failures and 0 errors.

The exception is
`tests/test_xlsx_delivery_v0_1.py::XlsxDeliveryV01Tests::test_ruleset_identity_filename_and_media_type`,
line 221:

- Expected: `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`.
- Observed: `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.

Both hashes and the exact assertion match the accepted SP-043A/SP-042P exception.
The suite's nonzero exit code is not hidden or relabeled as an unconditional pass.

JUnit class-name subsets (overlapping, not additive) include 218 Market Report,
46 SP-043B, 74 Route Discovery, 42 Competition, 128 Opportunity, 39 evidence,
59 Semantic and 30 deterministic tests passed. XLSX has 31 passed plus the above
exception. These cover V0.1/V0.2 compatibility, integration, localization,
evidence/provenance, determinism, private boundaries and category isolation.

An initial focused run completed all assertions but encountered a Windows shared
pytest temporary-directory cleanup permission error. It was not counted as a
successful run. Subsequent runs used dedicated temporary/cache directories.
The initial development full suite also reproduced only the same accepted OOXML
exception; the counts above are from the final frozen implementation.

Compile validation and `git diff --check` passed. The focused SP-043B/SP-043A/
provider-neutral-input run passed 64 tests. The final full suite also ran the
Artifact Tool integration test, including round-trip equality, blank human
inputs and source-text formula-injection protection. No runtime skip was used
for that test in qualification.

## Final private generation and determinism

Final reports are generated outside Git in the external SP-043B private
boundary's `final` directory. Initial diagnostic outputs are separate and are
not the accepted deliverables. Each final category has:

- `market_report_v0_3.json`
- `operator_market_report_zh_cn.xlsx`
- `operator_market_report_zh_cn.md`
- `operator_market_report_en_us.md` (i18n/determinism comparison)

| Category | Accepted | Primary | Assigned | Unclassified | Review required | Routes | Families |
|---|---:|---:|---:|---:|---:|---:|---:|
| Shower Caddy | 998 | 787 | 714 | 229 | 55 | 14 | 7 |
| Air Fryer | 300 | 162 | 64 | 233 | 3 | 11 | 11 |

All accepted/primary/assignment counts and every Route ID/member count match
SP-043A. The following upstream semantic fingerprints also match exactly:

| Result | Shower Caddy | Air Fryer |
|---|---|---|
| Semantic | `1887dde9ee4dfd08804321b04494812689342acfe3e32acb73d958949bdd3b0d` | `0e9ae0c2940cb0df6b2a91c267802ce995233c783512f1550ec6bbe717588cbe` |
| Route | `39628ba872bb6b0e51cc0aab7feaac45f5cd3d56bd92ba144aac45973515f0d3` | `0512eb98a08b093158969d06ed43821dcca9f4dd885e046e6a83ad9deef8fe4b` |

Shower Caddy has 71.54% listing coverage and 83.50% observed-sales coverage by
assigned Routes. Portable is the largest family by sales share (37.82%). The
wall-mounted family has 277 products and 332,771 estimated monthly units, or
35.83% of assigned-market sales. Within that family:

| Mechanism | Products | Estimated monthly units | Family sales share |
|---|---:|---:|---:|
| Adhesive | 49 | 170,610 | 51.27% |
| Suction cup | 73 | 50,314 | 15.12% |
| Unspecified wall mount | 155 | 111,847 | 33.61% |

These are rollups of released child Routes, not additional membership. The
report's descriptive triage yields 1 priority-research, 3 low-priority and 10
watch Routes. None is a launch recommendation.

Air Fryer has 21.33% listing coverage and 20.42% observed-sales coverage by
assigned Routes. All 11 Routes are `LIMITED_COVERAGE_OBSERVATION`. No strong Route
opportunity recommendation is issued. Its compound operation descriptions remain
unchanged; the report does not invent broader architectural families.

Both complete governed pipelines and report aggregations ran twice. JSON,
hierarchy, mechanism rollups, price bands, review bands, new-product layers,
zh-CN Markdown and en-US Markdown matched. Delivery also ran twice. Final
presentation-only count formatting and seller-estimate disclosure were rerendered
and verified twice from the unchanged frozen JSON; the full suite was then rerun.

| Final artifact | Shower Caddy | Air Fryer |
|---|---|---|
| Report semantic fingerprint | `ccb1e683672640c01a3242ec1baebf9d643f91ec7cdf3ce6835af39939f4bd86` | `5a6a832f50f30ebbde8b4bf4b31d95b589d0fb63876ad618f6df12ac7f8cfef0` |
| JSON SHA-256 | `ad87b16b102e6026dfddbb671c1ae7510b452738dde045f15d17ddbb7002adde` | `2548d157593f2b9aae705cbb445fe4e74541b41474a610c3651a945af0068904` |
| zh-CN Markdown SHA-256 | `dc65ca064bdd932f76c049fb23e633cef4fa126c899b5eacadc1d2887726ba57` | `212381d908676e1513c86b065da3a222287e9a94cd784fce540104cd2b342bd5` |
| Workbook content representation | `65ddc37c79926250c2119fd8eb2856e6bcc27ea276a380e6052160ead2714c34` | `0509c1753f2e578b28f96db9766d9d30a848c3c69d3c6a803051229230c113d0` |

Raw ZIP hashes differ across repeated XLSX builds due to container metadata;
this is explicitly recorded, not claimed as byte equality. The workbook gate
compares cell content, number formats, table ranges, validation and frozen panes.

The Spreadsheets skill guided typed values, explicit missingness, separate human
inputs, Artifact Tool authoring and visual QA. All 30 sheets were visually
reviewed, with additional competition/secondary-table checks. Independent
read-only XLSX validation matched every table cell to the localized projection,
found zero formulas/errors, and confirmed 22 blank human input cells per workbook
(44 total). No known Chinese Route labels were left untranslated.

## Privacy and file scope

The 14-file checkpoint contains only the eight new report module/renderer files,
report-only profile, runner, package-data declaration, sanitized tests, contract
documentation and this validation document. No released engine/profile/config
implementation is staged. The source scan found zero secrets, absolute private
paths or ASIN literals. Against the actual two inputs, 1,298 ASINs and 1,277
distinct nontrivial titles produced zero matches in checkpoint content.

Private report JSON/XLSX/Markdown, real brand/seller details, raw listings and QA
previews remain local outside Git. The pre-existing unrelated validation document
and preserved stash are excluded. Exact staged scope and index/worktree state are
verified again immediately around commit/publication.

## Technical verdict

`SP-043B OPERATOR MARKET REPORT V0.3: TECHNICAL PASS`

`REAL CHINESE REPORTS: GENERATED`

This qualification recognizes only the exact, previously accepted OOXML
environment exception. It does not claim business-value acceptance.

## Commit and publication identity

The feature commit is the commit containing this validation document. Its exact
SHA is reported in the final task handoff and verified against the remote branch;
embedding a commit's own SHA in its contents would change that SHA.

Only `codex/task-sp-043b-operator-market-report-v0-3` may be published. Private
reports, private brand/seller data, real listing titles and ASIN-grain records
are excluded. The unrelated document and stash remain untouched.

## Human business-value acceptance

`BUSINESS VALUE HUMAN REVIEW: PENDING`

The eleven human verdict/notes pairs are not inferred or migrated. Technical
acceptance does not declare business usefulness or launch readiness.
