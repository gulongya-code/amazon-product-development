# SP-042P Route Discovery V2 release closeout

## Release boundary

- Repository baseline and release parent: `fae0579b0c0a7001de7944ac9f5f3749c12efc4d`.
- Release branch: `codex/task-sp-042g-shower-caddy-final-human-remediation`.
- Scope: the validated SP-042I, SP-042K, and SP-042N semantic-authority,
  Route projection, governed profile, replay-gate, and regression changes.
- No Market Report or broader product-system release is asserted.
- No private workbook, governed basis, completed review, listing-grain replay,
  listing reference, title, evidence row, credential, or secret is included.

Issue #57 prohibited commit and push until the matching governed human review
completed and the final acceptance boundary returned its sole permitted PASS
verdict. That condition is now satisfied. This closeout does not change Semantic
Engine or Route Discovery runtime behavior.

## Release fingerprints

The implementation source bundle uses
`sha256-canonical-path-content-v1`: SHA-256 over canonical JSON containing the
sorted repository-relative path and raw SHA-256 for each changed production,
profile, and replay-runner file.

- Implementation source bundle:
  `83bd454979462d7e1c764f64be16a89ca380cbfb2c48feab1837e07723b91c1e`.
- Shower Caddy profile raw SHA-256:
  `c23d9a1798cf8dc43188be43b310708c1d91f5bcc75f18b05c902e17e73aa076`.
- Shower Caddy profile contract fingerprint:
  `59d5bb2b4b765f259421390d1a3cd993cb6127c7973197844de466e3808ea7f3`.
- Shower Caddy Route configuration fingerprint:
  `2b8bbf505579e9eefe5d36be94a50c1286ebbce7496679c0d46f32a3d8fa9f15`.
- Final Shower Caddy semantic result fingerprint:
  `235fed02a1bd11384850ae6f3455a6e046def7c0ddbb1c1ed0c708e7452d61df`.
- Final Shower Caddy Route result fingerprint:
  `39833578efb37f626c2557f856f29d60e72607a192c9c7a489b879b487f13b1e`.

## Final governed acceptance

- Accepted Shower Caddy listings: `998`.
- Primary cohort: `787`.
- Assigned: `714`.
- Unclassified: `229`.
- `REVIEW_REQUIRED`: `55 / 998 = 5.5110%`.
- Operator-facing Routes: `14`.
- Candidates: `5`.
- Acceptance gates: `22 / 22` passed; failed gates: `0`.
- Privacy leak count: `0`.
- Governed review rows: `42 / 42`.
- Explicit governed human booleans: `252 / 252`.
- Bounded intra-route consistency: `100%`.
- Candidate minimum business sense: `PASS`.
- Operator Route safety: `PASS`.

The completed review matched the frozen contract, sample identity, calibration,
row order, Route references, listing references, Route definitions, and immutable
row content. Only the six governed `human_review` Boolean fields changed; no
human value was inferred from the Route-level review.

## Validation

- Compile validation over `src`, `scripts`, and `tests`: `PASS`.
- SP-042I, SP-042K, SP-042N, Semantic Engine V2, Route Discovery V2,
  private-replay contract, evidence, provenance, determinism, and isolation
  regressions: `145 passed`.
- Final private replay: `PASS — ROUTE_DISCOVERY_V2`.
- Full repository suite: `1588 passed, 13 skipped, 550 subtests passed`, with
  the single accepted Windows OOXML package-content fingerprint exception.
- Accepted OOXML exception: expected
  `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5`;
  observed
  `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b`.
- An initial full run used an overly long Windows temporary path and encountered
  one path-length `FileNotFoundError`. The exact node passed with a short
  temporary path, and the complete short-path rerun left only the accepted
  OOXML exception above.
- Semantic, Route, evidence, provenance, determinism, and category-isolation
  regressions: `0`.

The SP-042N regression that prohibits listing-specific shared-engine logic uses
a generic ASIN-pattern scan. It contains no private listing identifier and does
not change runtime behavior.

## Release content and exclusions

The release commit contains the governed Shower Caddy profile, shared semantic
authority capability, Route projection and fallback-label capability, aggregate
private-replay checks, affected existing tests, SP-042I/SP-042K/SP-042N regression
tests, and this sanitized closeout.

The pre-existing `SP_042H_AUTHORIZED_HUMAN_REVIEW_CLOSEOUT.md` worktree file is
unrelated to this release commit and remains excluded. The preserved SP-041R2
stash remains untouched. All private acceptance artifacts remain external and
untracked.

## Verdict

```text
FORMAL GOVERNED HUMAN RECORDING: PASS
AUTHORIZED HUMAN REVIEW: PASS
FINAL ROUTE DISCOVERY V2 RELEASE GATE: PASS — CLOSED
```

This document is part of the release-closeout commit, so it does not embed that
commit's self-referential SHA. The exact commit and remote verification are
recorded in the publication handoff.
