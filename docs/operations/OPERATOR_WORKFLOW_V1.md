# Operator Workflow V1

## Purpose and boundary

Operator Workflow V1 turns the validated Production Pipeline result into a short
evidence-triage workflow for an Amazon operator. The first XLSX sheet and the first
Markdown section answer what to do next, why, what is known, what is missing, the
main risks, and which evidence to collect.

It is not an automatic product-selection, purchase, launch, investment, revenue,
profitability, or success-probability decision. `market_report.json` remains
`market-report-v0.1`.

## Mandatory reuse audit

The implementation inspected the existing public surfaces before adding the thin
`operator-workflow-v0.1` composition contract.

| Public surface | Reuse decision | Reason |
|---|---|---|
| Decision Framework V0.1 | Reuse public ruleset identity and `INSUFFICIENT_EVIDENCE` semantic; do not execute | Production Pipeline does not expose the complete Evidence Evaluation, Conflict Resolution, and Evidence Policy request chain. Reconstructing it would fabricate governed inputs. |
| Recommendation Framework V0.1 | Reuse the governed mapping `INSUFFICIENT_EVIDENCE` → `EVIDENCE_COLLECTION_RECOMMENDED` | This is the existing explicit missing-evidence behavior. The workflow records `GOVERNED_SEMANTIC_MAPPING_ONLY`, not a fabricated full recommendation snapshot. |
| Operator Output V0.1 | Reuse presentation boundary, recommendation vocabulary, lineage-first design, and ruleset identity; do not execute | Its strict request requires Product, Demand, Competition, Opportunity, Scoring, and Recommendation snapshots with a complete source chain. The current production path cannot legally satisfy all six. |
| Operator Workbook V0.2 | Reuse summary-first design, static values, visible states, freeze panes, readable widths, status colors, and audit-last principle | Its strict builder likewise requires the unavailable full snapshot chain. Production therefore enhances the existing Market Report delivery workbook instead of creating fake source snapshots or a parallel workbook. |
| Operator Export / XLSX delivery | Reuse deterministic rendering, safe scalar display, static workbook output, and artifact ownership behavior | No second output artifact or manual conversion command is added. |
| Market Report delivery | Reuse directly | The validated report remains the single intelligence source for the improved XLSX and Markdown. |
| Production run/recovery summaries | Reuse directly | Attempts, retries, credits, replay counts, and resume lineage are runtime facts, not Intelligence inputs. |

The exact adapter gap is machine-readable in every workflow snapshot. A future task
may supply the missing governed snapshots, but must not reconstruct them from display
rows.

## Operator actions

| Action | Meaning |
|---|---|
| `ADVANCE_REVIEW` | Evidence supports continuing to a deeper human validation stage. It is not a launch or purchase instruction. |
| `COLLECT_EVIDENCE` | Material evidence is missing. Complete the named checks before advancing. |
| `FURTHER_REVIEW` | Evidence, conflicts, risks, or a framework adapter gap require human review. |
| `BLOCKED` | A governed policy or evidence condition prevents normal recommendation processing. |
| `NOT_APPLICABLE` | No governed recommendation rule applies to the current evidence. |

Current Production Pipeline reports with a `PENDING_DATA` Opportunity score or
unavailable Competition metrics conservatively produce `COLLECT_EVIDENCE`, sourced
from Recommendation Framework V0.1's governed insufficient-evidence semantic.

## Evidence states are not zero

| State | Meaning |
|---|---|
| `PARTIAL` | Some evidence exists, but the section or metric is incomplete. |
| `UNKNOWN` | The system cannot determine the value or semantic safely. |
| `UNAVAILABLE` | The required evidence is absent from the validated inputs. |
| `PENDING_DATA` | A governed calculation is waiting for required inputs; its numeric value remains null. |

These labels must never be read as numeric zero. A zero is displayed only when a
validated source explicitly provides the numeric value zero.

## Reading the operator outputs

Open `operator_market_report.xlsx` on the first sheet, `Operator Summary`, or open
`operator_market_report.md` at `Operator Brief`.

1. Read **Operator Action**, **Why This Action**, and **Evidence Readiness**.
2. Review **Top Opportunity Themes** as buyer-need evidence, not guaranteed demand.
3. Review **Top Risks / Blockers** and **Missing Evidence** before using a score.
4. Execute the prioritized **Recommended Next Checks**. Each check names its trigger,
   reason, and audit references.
5. Use the detailed Buyer Need, Competition, and Opportunity sections for evidence.
6. Use the workflow ID, semantic fingerprint, evidence IDs, and Market Report
   provenance for audit.

Buyer Need shares describe the validated evidence sample. Competition metrics retain
their explicit availability. Opportunity dimensions retain `UNKNOWN` and null values
until their governed inputs exist.

## How next actions are generated

Next actions are deterministic projections of explicit evidence states:

- unavailable Competition metrics request the named missing competition evidence;
- `UNKNOWN` Opportunity dimensions request their required demand, economic, or
  competition inputs;
- partial Buyer Need themes request review/bullet validation;
- incomplete product-attribute segments request inspection of the named dimension;
- an unavailable observation window requests comparable dated evidence.

No free-form market recommendation, ranking, profit estimate, or hidden score is
generated. Every action retains provenance references and an explicit priority.

## Run health, credits, and recovery

The executive block shows:

- pipeline status;
- whether additional transport attempts indicate retry;
- whether the run resumed and its source run ID;
- logical provider operations and transport attempts;
- newly executed and checkpoint-replayed operation counts;
- observed credits and their machine-readable semantics.

`FIXTURE_REFERENCE` credits are useful fixture metadata and are explicitly labelled
**not billed**. `LIVE_PROVIDER_REPORTED` means provider-observed live consumption; it
does not expose credentials. Resume runtime health may differ from uninterrupted
runtime health, while the operator action, evidence claims, and next actions remain
equivalent for equivalent validated evidence.

## Normal production command

No new command is required. A normal existing `amazon-intel run ...` invocation
automatically creates:

- `market_report.json` (`market-report-v0.1`);
- `operator_market_report.xlsx` with `Operator Summary` first;
- `operator_market_report.md` with `Operator Brief` first;
- `run_manifest.json` containing the versioned operator workflow snapshot.

SP-037 validation uses checked-in fixtures only. It makes zero XiYou live calls and
spends zero billed credits.
