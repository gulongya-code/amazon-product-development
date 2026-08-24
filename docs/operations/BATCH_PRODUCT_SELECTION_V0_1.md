# Batch Product Selection V0.1

## What this workflow does

Batch Product Selection V0.1 runs several explicit candidate cohorts through the
existing Production Pipeline, one candidate at a time. It then creates one batch
brief that groups candidates by the existing `operator-workflow-v0.1` action.

A candidate is an explicit ASIN analysis cohort. It is not automatically a complete
market sample, and a one-ASIN cohort is not silently treated as representative of a
category. The workflow does not perform discovery or expand the supplied ASINs.

This is evidence triage. It is not a profitability estimate, product-attractiveness
ranking, purchase instruction, or automatic market-entry decision.

## Prepare a batch file

Start from `docs/examples/product_selection_batch_v0_1.json`.

Required rules:

- use `product-selection-batch-v0.1`;
- choose a lowercase path-safe `batch_id` and unique lowercase path-safe
  `candidate_id` values;
- provide explicit 10-character ASINs for every candidate;
- do not repeat an ASIN inside a candidate or repeat the same ASIN cohort under a
  second candidate ID;
- provide marketplace, category, mode, provider preference, and the credential-safe
  provider configuration reference explicitly;
- do not add seed keywords or discovery inputs.

Candidate IDs are sorted deterministically. Their display position is not an
opportunity or profitability rank.

## Run the batch

```text
amazon-intel batch \
  --batch-file docs/examples/product_selection_batch_v0_1.json \
  --output-dir outputs/batch-001
```

The output directory must not already exist. Batch input and resume compatibility
are checked before any candidate provider runtime is constructed.

CLI exit behavior is explicit:

- `0`: every candidate completed successfully and batch status is `SUCCEEDED`;
- `1`: candidate outcomes are `PARTIAL` or `FAILED`; aggregate artifacts describe
  which candidates require recovery;
- `2`: shared input, output ownership, resume compatibility, source integrity, or
  aggregate delivery failed.

Candidates execute sequentially in candidate-ID order. Each new or resumed
candidate uses `ProductionPipelineOrchestrator` and receives its normal directory:

```text
<batch-output>/
  batch_selection_result.json
  batch_selection_summary.xlsx
  batch_selection_summary.md
  candidates/
    <candidate-id>/
      market_report.json
      operator_market_report.xlsx
      operator_market_report.md
      run_manifest.json
      checkpoints/
```

A failed candidate retains only the artifacts that the Production Pipeline safely
attributes to that failed run. It is never turned into a successful partial report,
and later independent candidates continue.

## Read the action groups

The batch copies the exact candidate action, recommendation type, evidence
readiness, reason, and next checks from `operator-workflow-v0.1`.

Allowed actions are:

- `ADVANCE_REVIEW`;
- `COLLECT_EVIDENCE`;
- `FURTHER_REVIEW`;
- `BLOCKED`;
- `NOT_APPLICABLE`.

Evidence readiness describes whether the inputs are adequate for the governed
workflow. It does not measure market attractiveness. When comparable governed
Opportunity scores do not exist, ranking is explicitly `UNAVAILABLE`.

`PENDING_DATA`, `UNKNOWN`, `UNAVAILABLE`, and `PARTIAL` stay visible. A null
Opportunity score is rendered as null, never numeric zero.

## Batch outputs

Open `batch_selection_summary.xlsx` on `Batch Summary` for a concise operator view.
The remaining sheets contain candidate actions, evidence gaps, run health, and audit
lineage. Filters, frozen headers, visible run failures, and explicit missing states
support non-developer review.

Open `batch_selection_summary.md` for the same actions and statuses in a text brief.
`batch_selection_result.json` is the machine-readable audit contract. The JSON,
XLSX, and Markdown copy the same per-candidate operator semantics.

Detailed candidate evidence remains in the normal per-candidate Market Report,
operator XLSX, Markdown, and manifest referenced by the batch summaries.

## Resume a partial batch

Use a fresh destination and retain the source batch unchanged:

```text
amazon-intel batch \
  --batch-file docs/examples/product_selection_batch_v0_1.json \
  --output-dir outputs/batch-002 \
  --resume-from outputs/batch-001
```

Before provider access, the workflow validates the batch input fingerprint,
candidate inventory, candidate fingerprints, source manifests, artifact ownership,
and hashes.

- A previously successful candidate is reused only after all four normal artifacts
  pass integrity checks. The new aggregate references those immutable source
  artifacts and makes no provider call for that candidate.
- A previously failed candidate is delegated to the existing Production Pipeline
  with its source candidate directory as `resume_from`. SP-036 validates and replays
  its checkpoints; the batch layer does not implement another checkpoint format.
- The resume destination is always fresh and the source batch is never modified.

Operator semantic fingerprints, actions, and next checks remain equal to an
uninterrupted equivalent run. Runtime health may differ because checkpoint replay
and source reuse are runtime facts.

## Usage and credits

The batch records total logical operations, new transport attempts, newly executed
operations, SP-036 checkpoint replays, successful-source reuse, and current-run
observed credits.

`FIXTURE_REFERENCE` credits remain useful fixture metadata and are explicitly
labelled not billed. `LIVE_PROVIDER_REPORTED` remains a separate provider-observed
semantic. Incompatible credit semantics are never added into one misleading total.

SP-038 implementation and automated acceptance use fixture mode only: XiYou live
calls are zero and billed credits are zero. Live batch validation is deferred to a
separately authorized task.
