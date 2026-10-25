# Four-axis geometry in the public 0.4 interface: entry-point inventory (written before any code change)

Track release-docs-r3, base `589485b`, 17 Oct 2026. Owner item 3A: no public RNPLens 0.4 entry point may show or
write the known-defective four-axis geometry values as computed results. The frozen rc3 Evaluate implementation
stays byte-identical; the protection goes in the public wrapper (`src/rnplens/cli.py`). This file is committed
before the code change that it governs.

## Affected values

The four-axis geometry route of Evaluate (`rnpbench_evaluate`, configuration `RNPBENCH_FOUR_AXIS_DECOMPOSITION_SCORE_DECOMP_V1`)
pairs model and reference residues by sequence alignment (the defective letter-matching step, stop report 2026-10-14).
Every number it produces is affected:
- values: `prot_internal_ca_rmsd`, `rna_internal_c4_rmsd` (the affected RNA-conformation measurement of Evaluate),
  `rna_placement_c4_rmsd`;
- counts from the same alignment: `n_prot_aligned`, `n_prot_native`, `n_prot_pose`, `n_rna_aligned`, `n_rna_native`,
  `n_rna_pose`; in `result.csv`: `n_protein_pairs`, `n_rna_pairs`;
- route texts that can carry route results: `exclusion` / `geometry_exclusion`, `no_value_note`, and the status
  (`COMPUTED` / `NO_VALUE`).

Not part of the route's results, and kept: `configuration` (an identifier), `correspondence_note` (fixed text),
`chains_used` (the chain pair, also used by the DockQ route's reporting), all required by the output schema.

Other RNA-conformation measurements that the owner lists as blocked: the RNA conformation difference between
candidates (Specification B "Q") is never computed (grouping states it is unavailable); Diagnose's RNA-side
disagreement is blocked with Diagnose (r2, exit 5). Report's RNA pose difference and grouping's P use Report's
construct-position route, not the defective alignment, and are not affected.

## Where the frozen component surfaces them (observed at 589485b)

`rnplens evaluate run` (dispatched unchanged to `rnpbench.cli` -> `rnpbench_evaluate`) prints a "Structural
geometry" section to stdout and writes the values into `result.json` (`geometry` block), `result.csv` (columns
`geometry_status` ... `geometry_exclusion`) and `summary.txt` (the same section as stdout). `rnplens evaluate
selftest` and `rnplens selftest` print per-fixture `geometry COMPUTED` and, on deviations or failures, lines such as
`geometry.rna_internal_c4_rmsd expected 0.7509... got 0.7509...`.

## Inventory: entry point -> fields -> behaviour (before -> chosen r3 behaviour)

| # | entry point | geometry fields reachable before r3 | chosen behaviour in r3 | why this choice |
|---|---|---|---|---|
| E1 | `rnplens evaluate run` stdout | "Structural geometry" section with three values and counts | **suppress**: the section is replaced by `Structural geometry: BLOCKED in RNPLens 0.4 ...`; "wrote:" names the user's files | the same command carries the qualified DockQ route, so refusing it would also remove qualified metrics; suppression keeps DockQ, fnat, iRMSD and LRMSD and states the block explicitly |
| E2 | `rnplens evaluate run` -> `OUT/result.json` | `geometry` block | **suppress**: `geometry` keeps `status: "BLOCKED"`, `configuration`, `correspondence_note`, `chains_used`, plus `blocked_reason` and `fields_withheld`; every value, count and exclusion text removed; a `rnplens_public_output` record lists the filter and the SHA-256 of each unfiltered component file (hashes only) | schema-valid, explicit status, no value |
| E3 | `rnplens evaluate run` -> `OUT/result.csv` | `geometry_status`, `protein_internal_ca_rmsd`, `rna_internal_c4_rmsd`, `rna_placement_c4_rmsd`, `n_protein_pairs`, `n_rna_pairs`, `geometry_exclusion` | **suppress**: columns kept (stable header), values empty, `geometry_status` = `BLOCKED`, `geometry_exclusion` = `GEOMETRY_BLOCKED_IN_0.4` | an empty CSV cell is "no value" in this format |
| E4 | `rnplens evaluate run` -> `OUT/summary.txt` | same section as stdout | **suppress**, as E1 | |
| E5 | `rnplens evaluate run` -> unfiltered files | the frozen component writes all files at once | the component writes into a **private temporary directory** (under `--workdir` if given), which is deleted after the filtered files are published; **no unfiltered copy is kept** in the user's output | the owner allows a raw copy only if clearly marked; not keeping one is simpler and leaves nothing to misread |
| E6 | `rnplens evaluate run` -> `OUT/rnplens_run.json` | none (hashes) | unchanged; it now hashes the published (filtered) files | |
| E7 | `rnplens evaluate validate`, `rnplens evaluate provenance`, `rnplens provenance`, `rnplens --version` | none (checked: no value printed) | pass through unchanged; tests assert no geometry value | |
| E8 | `rnplens evaluate selftest`, `rnplens selftest` (and, for Diagnose's example statements only, `rnplens diagnose selftest`; integrator follow-up, see DOCS_AUDIT R3-C3) | per-fixture `geometry COMPUTED`/`NO_VALUE`; geometry values on deviation and FAIL lines | **suppress in display**: `geometry COMPUTED` -> `geometry BLOCKED (checked, not shown)`; numbers on `geometry.*` lines masked as `<withheld>`; the regression check itself still runs on the frozen code and the verdict and exit code are unchanged | the self-test proves the frozen component is unchanged (J7 infrastructure) without displaying the values |
| E9 | `rnplens analyse --reference` (summary.json, summary.html, `evaluate/sNNN/*`, `analysis.log`) | summary/HTML already withhold (`evaluate_withheld`); the per-structure `evaluate/sNNN/` files and the log tail held the raw values | covered by E1-E5: analyse runs `python -m rnplens evaluate run`, so its files and log are filtered; summary unchanged | single control point |
| E10 | `rnplens compare` (`comparison_summary.*`, `evaluate/{before,after}/T/*`, `evaluate_runs.json`) | per-target Evaluate files and failure tails held the raw values; the comparison itself already uses the DockQ route only | covered by E1-E5 (compare runs `python -m rnplens evaluate run`) | |
| E11 | `rnplens update` / incremental re-runs, `rnplens clarify --resume` | through analyse | covered by E9 | |
| E12 | `rnplens assist` menu items A-F | no item takes a reference; item A runs analyse without a reference | no change; covered by E9 if a reference is ever given | |
| E13 | `rnplens explain` | could quote any field of an analysis file by evidence ID, e.g. `evaluate/s001/result.json#/geometry/rna_internal_c4_rmsd` | covered: the file no longer holds the value; the summary's `evaluate_withheld` statement is kept | |
| E14 | `rnplens export-methods` | summary-based sentences (withheld statement); the provenance manifest lists file hashes only | covered by E9 | |
| E15 | follow-up evidence summary (`rnplens_assistant.followup`) | summary.json only; reports `geometry_four_axis` as `TOOL_BLOCKED` | no change | |
| E16 | assistant tools (`evaluate_against_reference`, `compare_prediction_sets`), MCP server, registry | run `rnplens analyse --reference` / `compare`; evidence built from summary DockQ fields only; geometry recorded `TOOL_BLOCKED` | covered by E9/E10; no change to the pinned assistant sources | |
| E17 | viewer pages (`rnplens view`) | no Evaluate data | no change; scanned in the tests | |
| E18 | `examples/run_examples.sh` (`A_evaluate_7K9D/`) | as E1-E4 | covered by E1-E5 | |
| E19 | repository documentation: README Example 1 output and `docs/images/example_evaluate.png`; `docs/quickstart.md`; `docs/evaluate.md` | printed rc3 geometry values as example output | README and docs show the r3 output; the image is re-rendered from the r3 `summary.txt` | not an entry point, but it displays the values as example results |
| E21 (added 2026-10-18, owner decision F1) | the component packages' own command lines: `python -m rnpbench evaluate run\|selftest`, `python -m rnpbench selftest`, `python -m rnpbench toolkit selftest`, `python -m rnpbench diagnose …`, `python -m rnpbench.cli …`, `python -m rnpbench_evaluate[.cli] evaluate\|selftest`, `python -m rnpbench_diagnose[.cli\|.*] …`, `python -m rnpbench_core.*`, other submodules (`python -m rnpbench.evaluate` …), the same packages run by path; no console scripts other than `rnplens` are installed | geometry values (Evaluate) and Diagnose interpretation, unfiltered (0.4 audit F1) | **refuse**: each component package calls `rnplens.legacy_routes.refuse_blocked_route()` on import; when the interpreter was started as one of these command lines with a verb that would show a blocked result it prints `LEGACY_ROUTE_REFUSED` with the `rnplens` command to use and exits 5 before anything runs. Unaffected: help/`--version`/`validate`/`provenance`, every Report verb, library imports and `python -c` (the route `rnplens` uses). Residual by design: the eight pinned frozen sources run by file path (they import nothing that could carry the check; checked in a sandbox without the study data, seven stop at a fixed study-host path and `canonical/pos_adapter.py` prints 0/0 checks and writes an empty control record to /tmp (or, with `--stage population`, an empty file under the study path); none shows a blocked value; on the study host they would read and overwrite research files) | owner decision 2026-10-18: wrapper-level refusal; frozen implementation and its internal imports unchanged (`tests/test_legacy_route_refusal.py`) |
| E20 | `examples/expected_output/A_evaluate_7K9D/*` (rc3 expected outputs, incl. `selftest` fixtures in the frozen component) | rc3 values | **unchanged** (frozen historical records; DockQ parity is tested against them); marked historical in README and `examples/expected_output/README.md` is not edited | the owner's rule keeps frozen records unchanged |

## Tests required (each entry point)

A geometry value from the 7K9D fixture (the unrounded values and their printed roundings `0.75`, `1.79`, `0.52` in
their printed context, and the alignment counts in context) must not appear in stdout, stderr or any written file of
E1-E4, E8, E9, E10, E11 (through analyse), E13, E14, E17, E18; E7 prints none. DockQ, DockQ class, fnat, iRMSD and LRMSD
must be numerically identical to the rc3 expected outputs (`examples/expected_output/A_evaluate_7K9D/result.json`),
through `evaluate run` and through `analyse --reference`.
