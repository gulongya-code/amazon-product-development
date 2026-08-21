# Open Source Reuse Audit Template

Use this template before implementing any non-trivial reusable capability.

## Capability

- Task / requirement:
- Required behavior:
- Inputs:
- Outputs:
- Performance constraints:
- Offline/network constraints:

## 1. Current project search

- Files/modules reviewed:
- Reusable components:
- Gaps:

## 2. Internal system search

### amazon_ads_optimizer

- Files/modules reviewed:
- Reusable components:
- Contract compatibility:
- Reuse option:

## 3. GitHub / open-source search

| Candidate | Repo/package | License | Maintenance | Runtime fit | Dependency cost | Test quality | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## 4. Security / license gate

- License identified:
- Attribution required:
- Copyleft concern:
- Network calls:
- Data exfiltration concern:
- Native/binary dependencies:
- Known security concern:
- Approved for PoC:

## 5. PoC results

- Dataset:
- Accuracy / qualitative result:
- Edge cases:
- Runtime:
- Memory:
- Reproducibility:
- Failure modes:

## 6. Decision

Choose one:

- `REUSE_AS_IS`
- `WRAP_AND_REUSE`
- `COPY_AND_ADAPT`
- `BUILD_NEW`

Rationale:

## 7. Provenance

If `COPY_AND_ADAPT`:

- upstream URL:
- upstream commit/tag:
- source file(s):
- license:
- imported date:
- local destination:
- modifications:
- third-party notice updated:

## 8. Project-owned tests required

- [ ] positive cases
- [ ] negative/conflict cases
- [ ] missing-data cases
- [ ] ambiguity cases
- [ ] canonicalization edge cases
- [ ] serialization
- [ ] provenance
- [ ] deterministic behavior where expected
- [ ] no-network behavior where required
- [ ] fallback behavior
