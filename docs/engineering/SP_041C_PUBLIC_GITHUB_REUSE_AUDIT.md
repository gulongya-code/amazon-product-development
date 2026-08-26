# SP-041C Public GitHub Reuse and License Audit

Date: 2026-08-26
Issue: `#53 TASK-SP-041C`
Outcome: `NO_EXTERNAL_COPY_SELECTED`

This audit was completed before parser or rule-engine implementation. No
public source, fixture, ontology, model, or dataset will be copied.

## Search queries

- `site:github.com Python product attribute extraction key value parser LICENSE`
- `site:github.com hgrecco pint LICENSE unit parsing Python`
- `site:github.com nielstron quantulum3 LICENSE quantity extraction`
- `site:github.com json-logic json-logic-py LICENSE rule engine`
- `site:github.com microsoft Recognizers-Text LICENSE number with unit Python`
- `site:github.com pyparsing pyparsing LICENSE parser Python`
- `site:github.com scrapinghub extruct LICENSE product structured data extraction`
- `site:github.com ecommerce product attribute extraction NLP LICENSE`

## Candidates

| Candidate | License | Decision | Reason / obligation |
|---|---|---|---|
| `hgrecco/pint` | BSD-3-Clause | rejected dependency; reference-only design comparison | mature unit conversion is broader than the bounded approved units; accepting its flexible parser would weaken ambiguous-unit fail-closed semantics |
| `nielstron/quantulum3` | MIT | rejected | mixed-text quantity extraction and optional classifier/training behavior introduce heuristic ambiguity forbidden in V1 |
| `microsoft/Recognizers-Text` | MIT | rejected | broad multilingual entity recognition, alpha Python surface, and inferred text entities exceed the exact-pattern requirement |
| `pyparsing/pyparsing` | MIT | rejected | a PEG dependency is unnecessary for a governed `Key: Value | Key: Value` grammar and fixed measurement patterns |
| `json-logic/json-logic-engine` and related implementations | MIT | rejected | general executable rule trees and ecosystem/runtime differences add an unnecessary expression language; SP-041C needs a closed declarative schema |
| `xinyangz/OAMine` | Apache-2.0 | rejected | weak-supervision/open-world NLP mining is nondeterministic for this task and conflicts with the no-AI/no-clustering boundary |
| `scrapinghub/extruct` | BSD-3-Clause | rejected | extracts HTML semantic markup, not SP-041B governed listing fields or SellerSprite parameter strings |
| `ai-luizalabs/AI-PAVE-Br` | CC BY-NC-SA 4.0 dataset | rejected / reference-only | non-commercial ShareAlike data plus LLM-based extraction is incompatible; no data or code is used |

## Reviewed source and license URLs

- Pint: https://github.com/hgrecco/pint and
  https://github.com/hgrecco/pint/blob/master/LICENSE
- quantulum3: https://github.com/nielstron/quantulum3 and
  https://github.com/nielstron/quantulum3/blob/dev/LICENSE
- Recognizers-Text: https://github.com/Microsoft/recognizers-text and
  https://github.com/microsoft/Recognizers-Text/blob/master/LICENSE
- pyparsing: https://github.com/pyparsing/pyparsing and its repository LICENSE
- JSON Logic engine: https://github.com/json-logic/json-logic-engine/blob/master/LICENSE
- OAMine: https://github.com/xinyangz/OAMine and
  https://github.com/xinyangz/OAMine/blob/main/LICENSE
- extruct: https://github.com/scrapinghub/extruct and
  https://github.com/scrapinghub/extruct/blob/master/LICENSE

## Selected implementation constraints

1. Use Python stdlib `json`, `re`, `decimal`, `dataclasses`, and existing
   project contracts only; introduce no package dependency.
2. Split detailed parameters only on the explicit `|` delimiter and the first
   `:` in each segment. Empty/malformed segments remain diagnostics.
3. Use explicit rule-pack aliases and bounded token/phrase matching. No fuzzy
   similarity, statistical model, classifier, web ontology, or LLM.
4. Normalize only reviewed exact numeric+unit patterns. Unsupported or
   ambiguous units remain review-required/unavailable.
5. Treat rules as strictly validated data, not executable expressions or
   dynamic code.
6. All repository fixtures are project-owned synthetic values. No external
   product dataset or SellerSprite row is imported.

## Attribution conclusion

No external source or asset is copied and no new dependency is installed, so
SP-041C creates no new attribution-distribution obligation. The audit links
and decisions remain evidence only. Project tests, not third-party behavior,
freeze the required precedence, collision, negative, and determinism rules.
