# Market Report V0.2 offline operator guide

V0.2 is an explicit opt-in report version. It is not the default and must not be used for live validation until SP-039G authorizes that work.

## Run the bundled fixture path

```powershell
amazon-intel run `
  --market US `
  --asin B0DWB00001 `
  --asin B0DWB00002 `
  --asin B0DWB00003 `
  --mode fixture `
  --report-version market-report-v0.2 `
  --output-dir outputs/sp039f-v02
```

The successful run writes `market_report.json`, `operator_market_report.xlsx`, `operator_market_report.md`, and `run_manifest.json` from one validated V0.2 snapshot. The checkpoint directory is recovery state, not a report artifact.

Omitting `--report-version` keeps the established `market-report-v0.1` behavior. The batch command does not accept V0.2 passthrough in SP-039F.

## Read the artifacts

Start with the Executive Summary and Market Overview sheets, then review Evidence Gaps and Audit - Provenance before using any analytical section. `UNAVAILABLE`, `PARTIAL`, `UNKNOWN`, `PENDING_DATA`, `NOT_ATTACHED`, and `REVIEW_REQUIRED` are meaningful states; none means zero.

Product Directions are hypotheses, not launch instructions. Competitor Shortlist order is a human-review priority, not product, opportunity, desirability, or provider rank. Provider estimates retain their evidence semantics. Keyword Intelligence remains `NOT_ATTACHED` unless a governed attachment exists; no demand value is inferred.

The manifest records requested and produced report version, report ID, artifact paths, delivery status, provider summary, runtime warnings, and recovery evidence. The XLSX raw SHA-256 audits the exact delivered file. Portability tests use the canonical OOXML package-content fingerprint, which ignores ZIP compression differences while still hashing every member name and uncompressed member byte.

## Resume and safety

The requested report version is part of the recovery fingerprint. A V0.1 checkpoint cannot be resumed as V0.2, or vice versa. Use a fresh output directory for each run. Unknown report versions fail at input validation before provider construction or access.
