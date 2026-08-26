# SP-041B Public GitHub Reuse and License Audit

Date: 2026-08-26
Issue: `#52 TASK-SP-041B`
Outcome: `NO_EXTERNAL_SOURCE_COPY_SELECTED`

This audit was completed before implementation changes. Public repository and
license evidence was reviewed for deterministic CSV/XLSX header discovery,
schema validation, and typed tabular imports.

## Search queries

- `site:github.com Python openpyxl detect header row XLSX CSV schema MIT license`
- `site:github.com Python CSV header mapping typed rows validation MIT license`
- `site:github.com frictionlessdata frictionless-py LICENSE table schema CSV`
- `site:github.com pandas-dev pandas LICENSE CSV Excel read`

## Candidates

| Candidate | License evidence | Decision | Reason / obligation |
|---|---|---|---|
| CPython `Lib/csv.py` | PSF License in `python/cpython/LICENSE` | selected as standard-library dependency | use `csv.reader` only; retain the interpreter's normal PSF distribution terms; no source copied |
| openpyxl 3.1.5 | installed package metadata reports MIT; upstream source URL is `foss.heptapod.net/openpyxl/openpyxl` | selected existing dependency | read local workbooks with `read_only=True`, `data_only=False`, and no mutation; no source copied or vendored |
| `frictionlessdata/frictionless-py` | MIT, `LICENSE.md` | rejected | broad table/resource framework adds remote-source and schema behavior beyond Issue scope |
| `pandas-dev/pandas` | BSD-3-Clause, `LICENSE` | rejected | large dependency and automatic dtype inference can erase explicit missing/parse-failure semantics |
| `wireservice/csvkit` | MIT, `COPYING` | rejected | CLI and inference surface is unnecessary for a narrow governed adapter |
| `alan-turing-institute/CleverCSV` | MIT, `LICENSE` | rejected | dialect inference is deliberately out of scope; V1 accepts deterministic comma-separated UTF-8 only |
| `frictionlessdata/datapackage-py` / `tabulator-py` | MIT-family project licenses | rejected | legacy/broad abstractions duplicate smaller internal contracts and add no required capability |

## Selected design constraints

1. No public repository source code or test fixture is copied.
2. CSV decoding is strict UTF-8 or UTF-8-SIG and uses the standard Excel CSV
   dialect. `csv.Sniffer.has_header()` is expressly not used because it is a
   heuristic and conflicts with contract-based discovery.
3. XLSX access uses the already-installed openpyxl dependency only. Workbook
   bytes are read without formula execution, image extraction, or mutation.
4. Header discovery is implemented locally from the frozen SP-041A 66-field
   contract: exact names, versioned explicit aliases only, no fuzzy/case-based
   matching, and a bounded initial-row scan.
5. New behavior is covered by project-owned synthetic fixtures. No private
   SellerSprite export, credential, path, listing scalar, or ASIN is added.

## License conclusion

The implementation introduces no new package and no copied external code.
Normal dependency notices for Python and the existing MIT openpyxl package are
sufficient; no attribution file change is required for SP-041B.
