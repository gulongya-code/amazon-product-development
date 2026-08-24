# SP-034 Open Source Reuse Audit

Status: **COMPLETE**
Task: `TASK-SP-034 — Production E2E Pipeline Orchestrator V0.1`

## Capability

Compose the existing provider, normalization, intelligence, Market Report, validation,
and operator-delivery APIs into one deterministic offline/live production run contract
and CLI.

## Search record

1. Current project: reviewed the connector registry/resolver, XiYou connector and
   transport, Data Cleaning service, Product Intelligence and attribute extraction,
   Category Product Map, Competition Analysis/Intelligence, Buyer Need V0.3,
   Semantic Clustering, Opportunity Intelligence/scoring integration, Market Report
   adapters/builder/schema validator, and Operator Report Delivery. Also reviewed the
   existing data-cleaning CLI and live competition validation script.
2. Internal patterns: the existing `src/` CLIs, immutable dataclass contracts,
   deterministic IDs, injected provider transports, atomic JSON writers, and
   secret-safe connector errors provide the required patterns. No separate
   `amazon_ads_optimizer` checkout is present in this repository; no code was copied.
3. Open source: considered Typer, Click, Prefect, Dagster, Airflow, and Luigi as
   possible CLI/workflow candidates. Their framework/runtime surface is unnecessary
   for a fixed eleven-stage synchronous V0.1 pipeline. The standard-library
   `argparse` entry point is sufficient.

## Candidate assessment

| Candidate | License | Maintenance/runtime | Dependency and network behavior | Contract fit |
|---|---|---|---|---|
| Existing project public APIs | Project-owned | Already covered by the project suite; Python 3.12 | No new dependency; fixture transport is offline | Exact fit |
| `argparse` | Python Software Foundation License | Python standard library | Zero added dependency/network | Exact CLI fit |
| Click / Typer | BSD-3-Clause / MIT | Mature | Adds CLI dependency | Useful but unnecessary |
| Prefect | Apache-2.0 | Mature | Large orchestration/runtime surface | Disproportionate for fixed local stages |
| Dagster | Apache-2.0 | Mature | Large dependency and service surface | Disproportionate |
| Airflow | Apache-2.0 | Mature | Scheduler/database/service infrastructure | Conflicts with SP-034 non-goals |
| Luigi | Apache-2.0 | Mature | Additional workflow framework | No material benefit for V0.1 |

No external source was copied. External candidates were evaluated from their known
package/license characteristics only; implementation does not depend on them.

## Disposition

Primary disposition: **WRAP_AND_REUSE**.

The implementation retains the existing public APIs and adds only a project-owned,
versioned orchestration contract, a zero-network fixture transport, an acquired-result
replay adapter so Data Cleaning does not spend a second provider operation, artifact
manifest handling, and an `argparse` CLI. It does not add a workflow framework,
change intelligence rules, or reconstruct Market Report section semantics already
owned by existing adapters.

## Security, reliability, and tests

- Live credentials remain environment-owned and pass only through the existing
  redacted `ProviderCredential` boundary.
- Fixture runs instantiate no HTTP transport and record zero network calls.
- Provider operation and credit summaries contain only safe operation names,
  counts, credit metadata, and provenance IDs.
- Project-owned tests cover deterministic replay, fail-fast input behavior, typed
  provider/schema/delivery failures, artifact and manifest contracts, CLI exit codes,
  credential redaction, and frozen Buyer Need/Market Report regressions.
