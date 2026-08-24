# Production Reliability & Recovery V0.1

## Reliability boundary

SP-036 adds runtime recovery around the existing Production Pipeline. It does not
change XiYou endpoints or request payloads, Buyer Need rules, Competition formulas,
Opportunity scoring semantics, `market-report-v0.1`, or the XLSX design.

Fixture mode remains a zero-network path. SP-036 itself was implemented and validated
only with checked-in fixtures and deterministic fault injection; live retry/recovery
validation is deferred to a separately authorized task.

## Bounded retry

Live production construction uses the project-owned `BoundedTransientRetryPolicy`
with a default maximum of two transport attempts for one logical provider operation:
the initial attempt plus at most one retry. There is no sleep loop, automatic third
attempt, pagination retry, resolver retry, or hidden endpoint call.

Only safely classified transient errors are retried:

- `NETWORK`
- `TIMEOUT`
- `PROVIDER_UNAVAILABLE`

Authentication/configuration failures, rate limits, bad responses, schema mismatch,
field unavailability, and resolver exhaustion do not independently authorize a new
transport attempt. Exhausting the two-attempt transient limit is reported as
`BOUNDED_RETRY_EXHAUSTED`.

`provider_summary` distinguishes:

- `operation_count`: logical operations, including checkpoint replays;
- `transport_attempt_count`: newly executed transport attempts;
- `executed_operation_count`: logical operations sent to the current provider runtime;
- `replayed_operation_count`: logical operations restored offline;
- `logical_operations[]`: operation identity, source, status, attempt count, checkpoint;
- `transport_attempts[]`: ordinal, status, safe error code, and observed credits.

Credits are summed across every current-run transport attempt when the provider makes
them available. Replayed checkpoints have zero current-run transport attempts and do
not re-attribute historical credits. Fixture values remain `FIXTURE_REFERENCE` and
are explicitly not billed; live values remain `LIVE_PROVIDER_REPORTED`.

## Atomic checkpoints

After a provider response has passed the existing audited adapter, the run writes one
JSON checkpoint atomically under:

```text
<output-dir>/checkpoints/<checkpoint-hash>.json
```

Each `production-provider-checkpoint-v0.1` checkpoint binds the provider, logical
operation, Canonical field, normalized request parameters, marketplace, immutable run
request fingerprint, exact provider operation contract, adapter ruleset version,
adaptation context, safe response payload/metadata, Raw Evidence identity, and an
integrity SHA-256. Resume replays the stored provider response through the current
audited XiYou adapter; it does not implement a second Canonical mapping.

Checkpoints never persist environment variables, credentials, secret headers, or raw
exception strings. Credential-like keys are rejected recursively. Unsupported
versions, malformed JSON, missing inventory entries, altered integrity hashes, unsafe
content, or mapping-contract mismatches fail with typed recovery errors and are never
silently accepted.

The four managed operator artifacts remain unchanged. The checkpoint directory is
internal recovery evidence and is listed separately in the manifest `recovery`
section, not attributed as a normal operator artifact.

## Resume workflow

Resume is explicit. Keep the failed source directory unchanged and select a new,
empty destination:

```bash
amazon-intel run \
  --market US \
  --asin B0DWB00001 \
  --asin B0DWB00002 \
  --asin B0DWB00003 \
  --output-dir outputs/resumed-run \
  --mode live \
  --category-name "dog water bottle" \
  --resume-from outputs/failed-run
```

Before provider construction or access, the pipeline verifies that the source is a
compatible failed run and that marketplace, sorted explicit ASIN cohort, provider
preference/config reference, execution mode, category scope, endpoint contract, and
adapter identity match. A mismatch returns `INCOMPATIBLE_RESUME_SOURCE`. The source
directory is read-only. The destination still enforces managed-artifact and recovery-
checkpoint ownership protection; no `--overwrite` exists.

Successfully checkpointed `asin_info` and per-ASIN `asin_keywords` operations are
replayed offline and copied into the new run's checkpoint set with source lineage.
Only missing logical operations may reach the current provider runtime. This makes a
second recovery possible if a resumed run also fails.

## Incomplete explicit cohorts

A transient failure after some ASIN operations does not turn the reduced set into a
successful cohort. The failure manifest and successful checkpoints survive, but the
run status is `FAILED`; `market_report.json`, XLSX, and Markdown are not delivered.
After resume completes every requested ASIN, the pipeline rebuilds Cleaning,
Intelligence, Market Report, schema validation, and delivery from the complete
acquisition set.

Fixture fault injection verifies that an uninterrupted successful run and a failed
run followed by resume produce byte-equivalent parsed `market_report.json` content
for the same explicit input. Runtime lineage, checkpoint ownership, attempt counts,
and current-run credits may differ by design.
