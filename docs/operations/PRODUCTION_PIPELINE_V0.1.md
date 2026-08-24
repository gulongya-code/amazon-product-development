# Production Pipeline V0.1 Operator Guide

## Contract

`production-run-v0.1` accepts a normalized marketplace, an explicit ASIN cohort,
provider preference/config reference, output directory, optional run ID, and an
explicit `fixture` or `live` mode. The public Python surface is
`amazon_product_intelligence.production_pipeline`.

The fixed stage order is input validation, provider resolution, acquisition, Data
Cleaning, category/competition, Buyer Need V0.3, Opportunity Intelligence/scoring,
Market Report composition, serialized schema validation, operator delivery, then the
run manifest. Every stage has an explicit machine-readable status.

## Offline validation run

Fixture mode makes zero network calls and uses the checked-in sanitized cohort:

```bash
python -m amazon_product_intelligence.production_pipeline run \
  --market US \
  --asin B0DWB00001 \
  --asin B0DWB00002 \
  --asin B0DWB00003 \
  --output-dir outputs/run-001 \
  --mode fixture
```

After installation, the equivalent console command begins with `amazon-intel run`.
The existing `OperatorReportDelivery` XLSX runtime reads
`MARKET_REPORT_NODE_EXECUTABLE` and `MARKET_REPORT_NODE_MODULES` when Node.js and its
artifact modules are not globally discoverable.

The run directory contains:

```text
market_report.json
operator_market_report.xlsx
operator_market_report.md
run_manifest.json
```

## ASIN files

`--asin-file path.txt` accepts one ASIN per line. Blank lines and lines beginning
with `#` are ignored. It may be combined with repeatable `--asin` options.

## Live boundary

Live mode is explicit and non-interactive. It reads `XIYOU_API_BASE_URL` and
`XIYOU_API_KEY` from the environment, uses the existing XiYou provider abstraction,
and never prints the credential. SP-034 has been validated only for the dog-water-
bottle Buyer Need scope, so live mode also requires
`--category-name "dog water bottle"`. Multi-product credit-spending validation is
deferred to SP-035.

No validated seed-keyword-to-ASIN cohort discovery path exists. Supplying
`--seed-keyword` therefore fails before provider construction with the typed
`UNSUPPORTED_CAPABILITY` error. Seed discovery is a follow-up capability, not a
claimed SP-034 feature.

Retries, caches, resumable checkpoints, and partial-ASIN recovery remain deferred to
SP-036. V0.1 is fail-fast: provider/schema/delivery failures are typed, the report is
validated before delivery, and a failure manifest is written last with only artifacts
that actually exist.
