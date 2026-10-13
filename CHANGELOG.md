# Changelog

## 0.2.0rc2 — release candidate (not released)

- **One public name.** All human-readable text now uses RNPLens: the help and error messages of every command and
  verb, self-test lines, the heading of Evaluate's `summary.txt`, and the titles, headings and provenance line of
  the Report and Diagnose HTML pages. The change was made by an enumerated table of exact-match text replacements;
  no computation, JSON key, schema, contract or configuration identifier, or frozen scorer file changed. Report's
  stored example page received the same three replacements. Remaining historical identifiers are listed in
  `docs/identifiers.md`.
- **Commands.** Only `rnplens` is installed. The compatibility commands `rnpbench`, `rnpbench-evaluate`,
  `rnpbench-report` and `rnpbench-diagnose` were removed; the same operations are `rnplens evaluate|report|diagnose`.
- **Licence.** MIT (`LICENSE`).
- **Documentation.** The verbatim component READMEs and tutorial were replaced by the RNPLens guides; the frozen
  validation records moved to `docs/validation/`. New `docs/identifiers.md`.
- **Expected outputs** of the worked examples regenerated; they differ from rc1 only in the display strings above.

## 0.2.0rc1 — release candidate (not released)

First distribution candidate of RNPLens.

- **Distribution.** One installable Python distribution, `rnplens`, replacing the five internal component
  distributions of the qualified component set 0.2.0.dev1.
- **Command.** New `rnplens` command (`evaluate`, `report`, `diagnose`, `selftest`, `provenance`,
  `example-contract`, `--version`), a dispatch-only wrapper.
- **Implementation unchanged.** The six component import packages were byte-identical to the qualified
  0.2.0.dev1 set, including the eight hash-verified frozen scorer files, the regression fixtures and the expected
  outputs.
- **Documentation and examples.** README, user guides, two end-to-end examples with expected outputs, and a
  GitHub Actions workflow (Ubuntu and macOS; Python 3.10–3.12).
- **Not included.** Internal fixtures of AlphaFold 3, Chai-1, RF2NA and RF3 outputs, Report's internal acceptance
  suite and benchmark adapter, the benchmark resource itself, and qualification records.

## History of the implementation (internal, before the public name)

- Component set 0.2.0.dev1 (2026-10-10, internal identifier "RNPBench toolkit"): internally qualified on Linux
  x86-64 (Python 3.10–3.12) and on a clean macOS arm64 installation; not released.
- Its components: Evaluate 0.1.1, Report 1.0.0 (first called Predict), Diagnose 0.2.1.
