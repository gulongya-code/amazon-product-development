// Localized presentation spec -> XLSX. Requires the installed Artifact Tool
// runtime; no category/provider logic or metric recomputation lives here.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [specPath, outputPath, qaRoot] = process.argv.slice(2);
if (!specPath || !outputPath) throw new Error('usage: renderer.mjs SPEC OUTPUT [QA_DIRECTORY]');
const spec = JSON.parse(await fs.readFile(specPath, 'utf8'));
if (spec.contract_version !== 'operator-workbook-spec-v0.3') throw new Error('unsupported spec');
const wb = Workbook.create();
const layouts = [];
const safe = value => typeof value === 'string' && /^[=+@-]/.test(value) ? `'${value}` : value;
const width = value => [...String(value ?? '')].reduce((n, c) => n + (c.charCodeAt(0) > 255 ? 2 : 1), 0);
function wrapLine(text, limit) {
  const lines = [];
  let line = '', size = 0;
  for (const c of text) {
    const n = width(c);
    if (size + n > limit) { lines.push(line); line = ''; size = 0; }
    line += c; size += n;
  }
  if (line) lines.push(line);
  return lines;
}
for (const [sheetIndex, item] of spec.sheets.entries()) {
  const sheet = wb.worksheets.add(item.name);
  sheet.showGridLines = false;
  if (sheetIndex < 5) sheet.tabColor = '#24476B';
  let row = 2;
  sheet.getCell(row - 1, 0).values = [[safe(`${item.title}  ${spec.category}`)]];
  sheet.getCell(row - 1, 0).format.font = {name:'Arial', size:16, bold:true, color:'#17324D'};
  sheet.getCell(row - 1, 0).format.rowHeight = 29;
  row += 2;
  const noteLines = wrapLine(item.note, 140);
  for (const line of noteLines) {
    const cell = sheet.getCell(row - 1, 0);
    cell.values = [[safe(line)]];
    cell.format.font = {name:'Arial', size:11, color: sheetIndex === 0 || item.key === 'opportunities' ? '#9A3412' : '#46566A'};
    cell.format.wrapText = false;
    cell.format.rowHeight = 22;
    row++;
  }
  row++;
  const tables = [];
  // Column widths are shared by tables on a sheet. Select the largest requested
  // width for each column so secondary sections cannot clip the primary view.
  const widths = [];
  for (const table of item.tables) for (const [i, value] of table.widths.entries()) widths[i] = Math.max(widths[i] || 0, value);
  for (const table of item.tables) {
    if (table.title) {
      sheet.getCell(row - 1, 0).values = [[safe(table.title)]];
      sheet.getCell(row - 1, 0).format.font = {name:'Arial', size:12, bold:true, color:'#17324D'};
      row += 2;
    }
    const start = row;
    const matrix = [table.headers, ...table.rows].map(r => r.map(safe));
    const ncols = table.headers.length;
    const range = sheet.getRangeByIndexes(start - 1, 0, matrix.length, ncols);
    range.values = matrix;
    range.format.font = {name:'Arial', size:11, color:'#243447'};
    range.format.verticalAlignment = 'center';
    range.format.wrapText = true;
    for (const [i, requested] of widths.entries()) {
      sheet.getRangeByIndexes(start - 1, i, matrix.length, 1).format.columnWidth = requested;
    }
    const header = sheet.getRangeByIndexes(start - 1, 0, 1, ncols);
    header.format.fill = '#24476B';
    header.format.font = {name:'Arial', size:11, bold:true, color:'#FFFFFF'};
    header.format.horizontalAlignment = 'center';
    for (const [i, dataRow] of matrix.entries()) {
      const lines = Math.max(...dataRow.map((value, j) => String(value ?? '').split('\n').reduce((n, line) => n + Math.max(1, Math.ceil(width(line) / (widths[j] - 3))), 0)));
      sheet.getRangeByIndexes(start - 1 + i, 0, 1, ncols).format.rowHeight = Math.max(i === 0 ? 40 : 30, 18 * lines + 12);
      if (i > 0 && i % 2 === 0) sheet.getRangeByIndexes(start - 1 + i, 0, 1, ncols).format.fill = '#F1F5F9';
    }
    for (const [j, fmt] of table.formats.entries()) if (fmt && table.rows.length) {
      const body = sheet.getRangeByIndexes(start, j, table.rows.length, 1);
      body.setNumberFormat(fmt);
      body.format.horizontalAlignment = 'right';
    }
    for (const [i, formats] of (table.row_formats || []).entries()) {
      for (const [j, fmt] of formats.entries()) if (fmt) sheet.getCell(start + i, j).setNumberFormat(fmt);
    }
    const last = start + matrix.length - 1;
    if (matrix.length > 1) {
      const native = sheet.tables.add(`A${start}:${String.fromCharCode(64+ncols)}${last}`, true, `Report${sheetIndex + 1}Table${tables.length + 1}`);
      native.showFilterButton = !item.human_input;
    }
    if (item.human_input) {
      const input = sheet.getRangeByIndexes(start, 1, 11, 2);
      // Empty strings in a presentation spec become genuinely blank XLSX cells.
      input.clear({applyTo:'contents'});
      input.format.fill = '#FFF2CC';
      sheet.getRangeByIndexes(start, 1, 11, 1).dataValidation = {rule:{type:'list', values: spec.locale === 'zh-CN' ? ['是','否','无法判断'] : ['Yes','No','Unable to judge']}};
    }
    tables.push({start, last, columns:ncols});
    row = last + 3;
  }
  if (row > 30) { sheet.freezePanes.freezeRows(tables[0].start); sheet.freezePanes.freezeColumns(item.key === 'summary' ? 1 : 2); }
  layouts.push({name:item.name, key:item.key, tables, last:row-3});
}
wb.recalculate();
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'formula errors'});
if (qaRoot) {
  await fs.mkdir(qaRoot,{recursive:true});
  await fs.writeFile(path.join(qaRoot,'inspection.ndjson'),errors.ndjson);
  for (const [i, layout] of layouts.entries()) {
    // Inspect the opening view of each sheet and every secondary table.
    for (const [j, table] of layout.tables.entries()) {
      const endCol = String.fromCharCode(64 + Math.min(table.columns, 10));
      const firstRow = j === 0 ? 1 : table.start;
      const endRow = Math.min(table.last, table.start + (layout.key === 'opportunities' ? 2 : 5));
      const preview = await wb.render({sheetName:layout.name,range:`A${firstRow}:${endCol}${endRow}`,scale:1,format:'png'});
      await fs.writeFile(path.join(qaRoot,`${String(i+1).padStart(2,'0')}_${j+1}.png`),new Uint8Array(await preview.arrayBuffer()));
    }
  }
  await fs.writeFile(path.join(qaRoot,'layouts.json'),JSON.stringify(layouts,null,2));
}
await fs.mkdir(path.dirname(outputPath),{recursive:true});
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(outputPath);
console.log(JSON.stringify({sheets:layouts.length,spec_sha256:createHash('sha256').update(JSON.stringify(spec)).digest('hex'),output:path.basename(outputPath)}));
