import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [inputPath, outputPath, previewDirectory] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("usage: operator_market_report.mjs <input.json> <output.xlsx> [preview-dir]");
}

const report = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();

const COLORS = {
  navy: "#17324D",
  blue: "#2F75B5",
  paleBlue: "#DCE6F1",
  lightBlue: "#EAF2F8",
  gray: "#667085",
  paleGray: "#F2F4F7",
  line: "#D0D5DD",
  white: "#FFFFFF",
  green: "#E2F0D9",
  amber: "#FFF2CC",
  red: "#FCE4D6",
};

const sortedJsonValue = (value) => {
  if (Array.isArray(value)) return value.map(sortedJsonValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, sortedJsonValue(value[key])]),
    );
  }
  return value;
};

const compactJson = (value) => {
  if (value === null || value === undefined) return "UNAVAILABLE";
  if (typeof value === "object") return JSON.stringify(sortedJsonValue(value));
  return String(value);
};

const evidence = (values) => values?.length ? [...values].sort().join(", ") : "UNAVAILABLE";
const limitations = (values) => values?.length ? [...values].sort().join("; ") : "None recorded.";
const availableValue = (metric) => metric.availability === "UNAVAILABLE" ? "UNAVAILABLE" : compactJson(metric.value);

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
  };
  sheet.getRange("A2").format.rowHeight = 24;
  sheet.freezePanes.freezeRows(3);
  return sheet;
}

function styleHeader(range) {
  range.format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white },
    borders: { preset: "outside", style: "thin", color: COLORS.blue },
    verticalAlignment: "center",
    wrapText: true,
  };
  range.format.rowHeight = 28;
}

function styleBody(range) {
  range.format = {
    borders: {
      insideHorizontal: { style: "thin", color: COLORS.line },
      bottom: { style: "thin", color: COLORS.line },
    },
    verticalAlignment: "top",
    wrapText: true,
  };
}

function statusColor(range, status) {
  range.format.fill = status === "AVAILABLE" ? COLORS.green : status === "PARTIAL" ? COLORS.amber : COLORS.red;
}

function distributionValue(value) {
  if (!value || typeof value !== "object") return compactJson(value);
  const labels = [["minimum", "Min"], ["maximum", "Max"], ["mean", "Mean"], ["median", "Median"]];
  const parts = labels.filter(([key]) => value[key] !== undefined).map(([key, label]) => `${label}: ${value[key]}`);
  return parts.length ? parts.join(" | ") : compactJson(value);
}

const overview = baseSheet(
  "Market Overview",
  "Operator Market Report",
  `${report.category.category_name} · ${report.category.marketplace} · ${report.report_id}`,
  "D",
);
overview.getRange("A4:B15").values = [
  ["Category", report.category.category_name],
  ["Marketplace", report.category.marketplace],
  ["Category Scope", report.category.scope],
  ["Sample Size", report.sample.sample_size],
  ["Unique ASIN Count", report.sample.unique_asin_count],
  ["ASIN Coverage", report.sample.asin_coverage ?? "UNAVAILABLE"],
  ["Data Window", report.data_window.period],
  ["Window Start", report.data_window.start_at ?? "UNAVAILABLE"],
  ["Window End", report.data_window.end_at ?? "UNAVAILABLE"],
  ["Report ID", report.report_id],
  ["Report Version", report.report_version],
  ["Pipeline Version", report.pipeline_version],
];
overview.getRange("A4:A15").format = {
  fill: COLORS.paleBlue,
  font: { bold: true, color: COLORS.navy },
  borders: { preset: "inside", style: "thin", color: COLORS.line },
};
styleBody(overview.getRange("B4:B15"));
overview.getRange("B7:B8").format.numberFormat = "#,##0";
if (typeof report.sample.asin_coverage === "number") {
  overview.getRange("B9").format.numberFormat = "0.0%";
}
overview.getRange("B11:B12").format.numberFormat = 'yyyy-mm-dd"T"hh:mm:ss"Z"';
overview.mergeCells("A17:D17");
overview.getRange("A17:D17").values = [["Data Limitations"]];
styleHeader(overview.getRange("A17:D17"));
const allLimitations = [...new Set([
  ...(report.limitations ?? []),
  ...(report.sample.limitations ?? []),
  ...(report.data_window.limitations ?? []),
  ...(report.buyer_needs.limitations ?? []),
  ...report.buyer_needs.needs.flatMap((item) => item.limitations ?? []),
  ...(report.competition.limitations ?? []),
  ...[
    report.competition.competition_level,
    report.competition.asin_count,
    report.competition.brand_count,
    report.competition.price_distribution,
    report.competition.rating_distribution,
    report.competition.review_distribution,
  ].flatMap((metric) => metric.limitations ?? []),
  ...(report.opportunity_score.limitations ?? []),
])].sort();
const overviewLimits = allLimitations.length ? allLimitations : ["No limitations recorded."];
overview.getRange(`A18:D${17 + overviewLimits.length}`).values = overviewLimits.map((value) => ["•", value, "", ""]);
styleBody(overview.getRange(`A18:D${17 + overviewLimits.length}`));
overview.getRange("A:A").format.columnWidth = 24;
overview.getRange("B:B").format.columnWidth = 74;
overview.getRange("C:D").format.columnWidth = 12;

const buyer = baseSheet(
  "Buyer Need Analysis",
  "Buyer Need Analysis",
  `Source: ${report.buyer_needs.source_record_id} · Validation: ${report.buyer_needs.validation_status}`,
  "E",
);
buyer.getRange("A4:E4").values = [["Buyer Need", "Share", "Confidence", "Validation Status", "Evidence"]];
styleHeader(buyer.getRange("A4:E4"));
const needs = [...report.buyer_needs.needs];
const buyerRows = needs.map((item) => [
  item.need_label,
  item.share ?? "UNAVAILABLE",
  item.confidence,
  item.validation_status,
  evidence(item.evidence_ids),
]);
if (buyerRows.length) {
  buyer.getRange(`A5:E${4 + buyerRows.length}`).values = buyerRows;
  styleBody(buyer.getRange(`A5:E${4 + buyerRows.length}`));
  buyer.getRange(`B5:B${4 + buyerRows.length}`).format.numberFormat = "0.0%";
}
buyer.getRange("A:A").format.columnWidth = 28;
buyer.getRange("B:B").format.columnWidth = 12;
buyer.getRange("C:D").format.columnWidth = 20;
buyer.getRange("E:E").format.columnWidth = 84;
buyer.freezePanes.freezeRows(4);

const competition = baseSheet(
  "Competition Analysis",
  "Competition Analysis",
  `Source records: ${[...report.competition.source_record_ids].sort().join(", ")}`,
  "D",
);
competition.getRange("A4:D4").values = [["Indicator", "Availability", "Value", "Evidence"]];
styleHeader(competition.getRange("A4:D4"));
const metricOrder = [
  ["Competition Level", report.competition.competition_level],
  ["ASIN Count", report.competition.asin_count],
  ["Brand Count", report.competition.brand_count],
  ["Price Distribution", report.competition.price_distribution],
  ["Rating Distribution", report.competition.rating_distribution],
  ["Review Distribution", report.competition.review_distribution],
];
const competitionRows = metricOrder.map(([label, metric]) => [
  label,
  metric.availability,
  metric.availability === "UNAVAILABLE" ? "UNAVAILABLE" : distributionValue(metric.value),
  evidence(metric.evidence_ids),
]);
competition.getRange("A5:D10").values = competitionRows;
styleBody(competition.getRange("A5:D10"));
for (let index = 0; index < competitionRows.length; index += 1) {
  statusColor(competition.getRange(`B${5 + index}`), competitionRows[index][1]);
}
competition.getRange("A:A").format.columnWidth = 28;
competition.getRange("B:B").format.columnWidth = 18;
competition.getRange("C:C").format.columnWidth = 64;
competition.getRange("D:D").format.columnWidth = 78;
competition.freezePanes.freezeRows(4);

const opportunity = baseSheet(
  "Opportunity Analysis",
  "Opportunity Assessment",
  `Candidate: ${report.opportunity_score.candidate_id}`,
  "F",
);
opportunity.getRange("A4:B8").values = [
  ["Opportunity Score", report.opportunity_score.score_value ?? "UNAVAILABLE"],
  ["Confidence", report.opportunity_score.confidence],
  ["Score Status", report.opportunity_score.score_status],
  ["Policy", report.opportunity_score.policy_version],
  ["Policy Fingerprint", report.opportunity_score.policy_fingerprint],
];
opportunity.getRange("A4:A8").format = {
  fill: COLORS.paleBlue,
  font: { bold: true, color: COLORS.navy },
  borders: { preset: "inside", style: "thin", color: COLORS.line },
};
styleBody(opportunity.getRange("B4:B8"));
opportunity.getRange("B4").format.numberFormat = "0.0";
opportunity.getRange("A10:F10").values = [["Dimension", "Score", "Contribution", "Maximum", "Explanation", "Evidence"]];
styleHeader(opportunity.getRange("A10:F10"));
const dimensions = [...report.opportunity_score.dimensions];
const dimensionRows = dimensions.map((item) => [
  item.dimension.replaceAll("_", " "),
  item.score_value ?? "UNAVAILABLE",
  item.contribution ?? "UNAVAILABLE",
  item.max_contribution,
  item.explanation,
  evidence(item.evidence_ids),
]);
if (dimensionRows.length) {
  opportunity.getRange(`A11:F${10 + dimensionRows.length}`).values = dimensionRows;
  styleBody(opportunity.getRange(`A11:F${10 + dimensionRows.length}`));
  opportunity.getRange(`B11:D${10 + dimensionRows.length}`).format.numberFormat = "0.0";
}
const riskRow = 12 + dimensionRows.length;
opportunity.mergeCells(`A${riskRow}:F${riskRow}`);
opportunity.getRange(`A${riskRow}:F${riskRow}`).values = [["Risks and Limitations"]];
styleHeader(opportunity.getRange(`A${riskRow}:F${riskRow}`));
const riskValues = [
  ...report.opportunity_score.risks.map((value) => `Risk: ${value}`),
  ...report.opportunity_score.limitations.map((value) => `Limitation: ${value}`),
];
const renderedRisks = riskValues.length ? riskValues : ["None recorded."];
opportunity.getRange(`A${riskRow + 1}:F${riskRow + renderedRisks.length}`).values = renderedRisks.map((value) => ["•", value, "", "", "", ""]);
styleBody(opportunity.getRange(`A${riskRow + 1}:F${riskRow + renderedRisks.length}`));
opportunity.getRange("A:A").format.columnWidth = 30;
opportunity.getRange("B:B").format.columnWidth = 36;
opportunity.getRange("C:D").format.columnWidth = 16;
opportunity.getRange("E:E").format.columnWidth = 66;
opportunity.getRange("F:F").format.columnWidth = 78;
opportunity.freezePanes.freezeRows(10);

// Save the authored workbook before preview rendering.  Keeping preview work after
// export prevents the artifact runtime's render cache from affecting the XLSX file.
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

if (previewDirectory) {
  await fs.mkdir(previewDirectory, { recursive: true });
  for (const name of ["Market Overview", "Buyer Need Analysis", "Competition Analysis", "Opportunity Analysis"]) {
    const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
    const safeName = name.toLowerCase().replaceAll(" ", "_");
    await fs.writeFile(`${previewDirectory}/${safeName}.png`, new Uint8Array(await preview.arrayBuffer()));
  }
}
