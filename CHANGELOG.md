# Changelog

## 0.2.0rc3 — release candidate (not released)

- **Diagnose applicability domain enforced.** Each run is checked against the conditions under which its
  statements were validated: Boltz-2 candidates, 5–50 per target, for `within_engine`; designated outputs of
  three or more of Boltz-2, Chai-1, RF3 and RoseTTAFold2NA for `cross_engine`; one protein chain and one RNA
  chain per structure for both. Outside these conditions Diagnose refuses with the reasons, unless
  `--allow-outside-validated-domain` is given; the report then records and displays that it is outside the
  validated domain. `within_engine` now takes `--engine`. No computed value changed. `report.json` gains
  `applicability`; the Diagnose example-regression reference gained exactly that key and the declared engine.
- **Run record.** Every `run` writes `rnplens_run.json`: RNPLens release, command, and SHA-256 of every input and
  output file.
- **Output schemas.** JSON Schemas for Evaluate, Report, Diagnose and the run record (`docs/schemas/`), with tests.
- **Security.** A Report `case_id` that is a path (contains `/`, `\`, a control character, or starts with `.`) is
  refused; previously it could make Report fail after writing part of its output. Tests check that hostile
  identifiers and file names are escaped in the HTML pages. New `SECURITY.md` and an issue template.
- **Removed** the import alias `rnpbench_predict`, which no RNPLens tool used.
- **Documentation.** New `docs/which_analysis_should_i_use.md` (choosing a tool, a table of every reported value,
  Diagnose's validated conditions), `docs/paper_reproducibility.md`, `examples/DATA_PROVENANCE.tsv` and screenshots
  of genuine outputs in the README.

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
