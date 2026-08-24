import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [inputPath, outputPath, previewDirectory] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("usage: batch_selection_summary.mjs <input.json> <output.xlsx> [preview-dir]");
}
const result = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();

const COLORS = {
  navy: "#17324D",
  blue: "#2F75B5",
  paleBlue: "#DCE6F1",
  lightBlue: "#EAF2F8",
  gray: "#667085",
  line: "#D0D5DD",
  white: "#FFFFFF",
  green: "#E2F0D9",
  amber: "#FFF2CC",
  red: "#FCE4D6",
};

const text = (value, fallback = "UNAVAILABLE") => value === null || value === undefined || value === "" ? fallback : String(value);
const action = (candidate) => candidate.operator_action ?? "UNAVAILABLE — candidate failed";
const statusFill = (status) => status === "SUCCEEDED" ? COLORS.green : status === "FAILED" ? COLORS.red : COLORS.amber;
const claimValue = (claim) => {
  const value = claim?.value;
  if (value && typeof value === "object" && typeof value.share === "number") {
    return `${(value.share * 100).toFixed(1)}% ASIN coverage`;
  }
  if (value === null || value === undefined) return "null / UNAVAILABLE";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
};
const claims = (items, maximum = 3) => items?.length
  ? items.slice(0, maximum).map((item) => `${text(item.label)} [${text(item.status)}]: ${claimValue(item)}`).join("; ")
  : "UNAVAILABLE";
const missing = (items, maximum = 3) => items?.length
  ? items.slice(0, maximum).map((item) => `${text(item.label)} [${text(item.status)}]`).join("; ")
  : "UNAVAILABLE";
const nextAction = (candidate) => candidate.next_actions?.length
  ? `[P${candidate.next_actions[0].priority}] ${candidate.next_actions[0].action}`
  : "UNAVAILABLE";
const opportunityValue = (candidate) => candidate.opportunity_score_value === null || candidate.opportunity_score_value === undefined
  ? `null (${text(candidate.opportunity_score_status)})`
  : candidate.opportunity_score_value;
const providerUsage = (candidate) => {
  const usage = candidate.provider_usage;
  return `logical=${usage.logical_operation_count}; new attempts=${usage.new_transport_attempts}; executed=${usage.executed_operations}; checkpoint replayed=${usage.checkpoint_replayed_operations}; source reused=${usage.reused_source_operations}; credits=${text(usage.current_run_observed_credits, "null")}; ${usage.credit_semantics}`;
};
const artifactReference = (candidate, name, path) => {
  const filename = String(path).split(/[\\/]/).at(-1);
  const prefix = candidate.execution_source === "REUSED_SUCCESS"
    ? "source batch"
    : "current batch";
  return `${prefix}/candidates/${candidate.candidate_id}/${filename ?? name}`;
};

function baseSheet(name, title, subtitle, columns) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.mergeCells(`A1:${columns}1`);
  sheet.getRange(`A1:${columns}1`).values = [[title]];
  sheet.getRange(`A1:${columns}1`).format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1").format.rowHeight = 34;
  sheet.mergeCells(`A2:${columns}2`);
  sheet.getRange(`A2:${columns}2`).values = [[subtitle]];
  sheet.getRange(`A2:${columns}2`).format = {
    fill: COLORS.lightBlue,
    font: { color: COLORS.gray, italic: true, size: 10 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A2").format.rowHeight = 28;
  return sheet;
}

function styleTable(sheet, address, headerAddress, bodyAddress) {
  sheet.getRange(headerAddress).format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(headerAddress).format.rowHeight = 34;
  if (bodyAddress) {
    sheet.getRange(bodyAddress).format = {
      borders: { insideHorizontal: { style: "thin", color: COLORS.line }, bottom: { style: "thin", color: COLORS.line } },
      verticalAlignment: "top",
      wrapText: true,
    };
  }
  const table = sheet.tables.add(address, true, `${sheet.name.replaceAll(" ", "").replaceAll("/", "")}Table`);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  table.showBandedRows = true;
}

const candidates = result.candidates;
const summary = baseSheet(
  "Batch Summary",
  "Batch Product Selection — Operator Triage",
  `${result.batch_id} · ${result.status} · ranking ${result.ranking_status} · candidate-ID display order is not opportunity ranking`,
  "N",
);
const summaryHeaders = [[
  "Candidate ID", "Run Status", "Operator Action", "Evidence Readiness", "Why This Action",
  "Opportunity Status", "Opportunity Value", "Ranking", "Competition Status", "Top Buyer Needs",
  "Top Missing Evidence", "Next Action", "Provider Usage", "Execution Source",
]];
const summaryRows = candidates.map((candidate) => [
  candidate.candidate_id,
  candidate.production_run_status,
  action(candidate),
  text(candidate.evidence_readiness),
  text(candidate.action_reason, "Candidate failed before operator workflow delivery."),
  text(candidate.opportunity_score_status),
  opportunityValue(candidate),
  candidate.ranking_status,
  text(candidate.competition_status),
  claims(candidate.top_buyer_need_themes),
  missing(candidate.top_missing_evidence),
  nextAction(candidate),
  providerUsage(candidate),
  candidate.execution_source,
]);
summary.getRange("A4:N4").values = summaryHeaders;
if (summaryRows.length) summary.getRange(`A5:N${4 + summaryRows.length}`).values = summaryRows;
styleTable(summary, `A4:N${4 + summaryRows.length}`, "A4:N4", summaryRows.length ? `A5:N${4 + summaryRows.length}` : null);
summary.freezePanes.freezeRows(4);
summary.freezePanes.freezeColumns(1);
const widths = [18, 15, 22, 19, 48, 20, 18, 16, 20, 34, 34, 42, 38, 20];
widths.forEach((width, index) => summary.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width);
for (let index = 0; index < candidates.length; index += 1) {
  const row = 5 + index;
  summary.getRange(`A${row}:N${row}`).format.rowHeight = 78;
  summary.getRange(`B${row}`).format.fill = statusFill(candidates[index].production_run_status);
  summary.getRange(`C${row}`).format.fill = candidates[index].production_run_status === "FAILED" ? COLORS.red : COLORS.amber;
}

const actionsSheet = baseSheet("Candidate Actions", "Candidate Actions", "Existing operator-workflow-v0.1 actions and next checks; no batch ranking", "G");
const actionRows = candidates.flatMap((candidate) => candidate.next_actions?.length
  ? candidate.next_actions.map((item) => [candidate.candidate_id, candidate.production_run_status, action(candidate), item.priority, item.trigger_status, item.action, item.reason])
  : [[candidate.candidate_id, candidate.production_run_status, action(candidate), null, "UNAVAILABLE", "UNAVAILABLE", "Candidate failed or no governed next action is available."]]
);
actionsSheet.getRange("A4:G4").values = [["Candidate ID", "Run Status", "Operator Action", "Priority", "Trigger", "Next Check", "Why"]];
if (actionRows.length) actionsSheet.getRange(`A5:G${4 + actionRows.length}`).values = actionRows;
styleTable(actionsSheet, `A4:G${4 + actionRows.length}`, "A4:G4", actionRows.length ? `A5:G${4 + actionRows.length}` : null);
actionsSheet.freezePanes.freezeRows(4);
[18, 15, 22, 10, 18, 52, 52].forEach((width, index) => actionsSheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width);
if (actionRows.length) actionsSheet.getRange(`A5:G${4 + actionRows.length}`).format.rowHeight = 44;

const gapsSheet = baseSheet("Evidence Gaps", "Evidence Gaps", "Explicit missing states copied from each candidate operator workflow; missing does not mean zero", "E");
const gapRows = candidates.flatMap((candidate) => candidate.top_missing_evidence?.length
  ? candidate.top_missing_evidence.map((item) => [candidate.candidate_id, item.label, item.status, item.reason, (item.provenance_reference_ids ?? []).join("; ")])
  : [[candidate.candidate_id, "UNAVAILABLE", candidate.production_run_status === "FAILED" ? "FAILED" : "UNAVAILABLE", "No gap summary is available.", "UNAVAILABLE"]]
);
gapsSheet.getRange("A4:E4").values = [["Candidate ID", "Evidence", "Status", "Reason", "Provenance"]];
if (gapRows.length) gapsSheet.getRange(`A5:E${4 + gapRows.length}`).values = gapRows;
styleTable(gapsSheet, `A4:E${4 + gapRows.length}`, "A4:E4", gapRows.length ? `A5:E${4 + gapRows.length}` : null);
gapsSheet.freezePanes.freezeRows(4);
[18, 32, 18, 52, 54].forEach((width, index) => gapsSheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width);
if (gapRows.length) gapsSheet.getRange(`A5:E${4 + gapRows.length}`).format.rowHeight = 48;

const healthSheet = baseSheet("Run Health", "Run Health & Provider Usage", `${result.usage.billing_note}; current-run credits=${text(result.usage.current_run_observed_credits, "null")}`, "L");
const healthRows = candidates.map((candidate) => {
  const usage = candidate.provider_usage;
  const health = candidate.run_health ?? {};
  return [candidate.candidate_id, candidate.production_run_status, candidate.execution_source, text(health.retried), text(health.resumed), usage.logical_operation_count, usage.new_transport_attempts, usage.executed_operations, usage.checkpoint_replayed_operations, usage.reused_source_operations, text(usage.current_run_observed_credits, "null"), usage.credit_semantics];
});
healthSheet.getRange("A4:L4").values = [["Candidate ID", "Run Status", "Execution Source", "Retried", "Resumed", "Logical Ops", "New Attempts", "Executed", "Checkpoint Replayed", "Source Reused", "Current Credits", "Credit Semantics"]];
if (healthRows.length) healthSheet.getRange(`A5:L${4 + healthRows.length}`).values = healthRows;
styleTable(healthSheet, `A4:L${4 + healthRows.length}`, "A4:L4", healthRows.length ? `A5:L${4 + healthRows.length}` : null);
healthSheet.freezePanes.freezeRows(4);
[18, 15, 20, 12, 12, 14, 14, 14, 20, 16, 16, 24].forEach((width, index) => healthSheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width);
if (healthRows.length) healthSheet.getRange(`A5:L${4 + healthRows.length}`).format.rowHeight = 28;

const auditSheet = baseSheet("Audit Lineage", "Audit / Lineage", `${result.semantic_fingerprint} · source batch ${text(result.source_batch_directory)}`, "D");
const auditRows = candidates.flatMap((candidate) => {
  const base = [[candidate.candidate_id, "candidate_fingerprint", candidate.candidate_fingerprint, "Batch input identity"]];
  if (candidate.operator_semantic_fingerprint) base.push([candidate.candidate_id, "operator_semantic_fingerprint", candidate.operator_semantic_fingerprint, "Operator intelligence identity"]);
  for (const [name, path] of Object.entries(candidate.artifact_paths)) base.push([candidate.candidate_id, `artifact:${name}`, artifactReference(candidate, name, path), candidate.artifact_hashes[name] ?? "UNAVAILABLE"]);
  for (const lineage of candidate.lineage_reference_ids) base.push([candidate.candidate_id, "lineage", lineage, "Governed source reference"]);
  return base;
});
auditSheet.getRange("A4:D4").values = [["Candidate ID", "Reference Type", "Reference / Path", "Hash / Meaning"]];
if (auditRows.length) auditSheet.getRange(`A5:D${4 + auditRows.length}`).values = auditRows;
styleTable(auditSheet, `A4:D${4 + auditRows.length}`, "A4:D4", auditRows.length ? `A5:D${4 + auditRows.length}` : null);
auditSheet.freezePanes.freezeRows(4);
[18, 30, 84, 68].forEach((width, index) => auditSheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width);
if (auditRows.length) auditSheet.getRange(`A5:D${4 + auditRows.length}`).format.rowHeight = 38;

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

if (previewDirectory) {
  await fs.mkdir(previewDirectory, { recursive: true });
  for (const sheet of workbook.worksheets.items) {
    const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
    const filename = sheet.name.toLowerCase().replaceAll(" ", "_").replaceAll("/", "_");
    await fs.writeFile(`${previewDirectory}/${filename}.png`, new Uint8Array(await preview.arrayBuffer()));
  }
}
