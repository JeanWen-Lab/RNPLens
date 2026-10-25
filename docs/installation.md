# Installation

## Requirements

- CPython **3.10, 3.11 or 3.12** (3.13 is not supported: the pinned numpy 1.26.4 and scipy 1.13.1 have no 3.13 wheels).
- Linux (x86-64) or macOS (arm64). Release candidate 0.2.0rc3 was qualified on both (Linux as the bit-identical
  reference platform, macOS with the portable profile; see [reproducibility.md](reproducibility.md)). For the 0.4
  development candidate, **Linux x86-64 is the tested interactive environment**. On macOS arm64 the toolkit runs.
  Its one known numerical parity difference (3.9 × 10⁻¹⁵ Å in one unrounded RNA pose difference, from a different
  OpenBLAS build of LAPACK `dgesdd`; `records/release/MACOS_NUMERICAL_DIFFERENCE.md`) is covered by an approved,
  narrowly scoped tolerance of 10⁻¹² Å on that single value (`records/release/TOLERANCE_POLICY_AMENDMENT_1.md`);
  every other value stays exact. The language-model modes run natively on Linux (bubblewrap) and on macOS (Seatbelt);
  one computer is enough ([install_linux.md](install_linux.md), [install_macos.md](install_macos.md)). Windows has not been tested.
- No GPU, no model weights, no network service and no credentials. RNPLens reads structure files you already have.

Paths beginning `records/`, here and in the other guides, name development and qualification records kept in
the source repository. They are not installed and are not part of the source distribution or the wheel.

## Install from a clone

```bash
git clone <repository-url>      # URL to be supplied at release
cd RNPLens
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[html]"
```

`[html]` adds matplotlib, needed only for images. Without it, `rnplens report run` (and the `report/` step of
`rnplens analyse`) writes its JSON output (`result.json`, `contacts_by_output.json`) but **writes no HTML page**;
the `analyse`, `region` and other 0.4 HTML pages are still written, with a note in place of each image. No number,
contact or verdict depends on matplotlib, and Evaluate and Diagnose are unaffected. `[test]` adds pytest. A
non-editable install
(`python -m pip install .`) also works.

**Development copies.** If you received the source as a git bundle rather than from a repository URL, use
`git clone <file>.bundle RNPLens && cd RNPLens && git checkout dev/0.4-interactive`.

### The optional assistant package (0.4)

The question menu (`rnplens assist`), region comparison, explain, the Methods export, grouping, clarify and update
need **only** the toolkit installed above. Three things also need the assistant package from the same source folder:
- **follow-ups** (`--followup local|codex`);
- the natural-language mode (`--nl`);
- `python -m rnplens_assistant replay`.

```bash
python -m pip install ./assistant
```

**Local follow-ups and replay** use no language model and need no account.
**The natural-language mode and Codex follow-ups** need your own Codex sign-in and the confinement of your system
(Linux: bubblewrap; macOS: Seatbelt, built in); see [install_linux.md](install_linux.md), [install_macos.md](install_macos.md)
and [setup_and_privacy.md](setup_and_privacy.md).
Without the assistant package, `rnplens assist --followup ...` explains what is missing and exits with code 3.

**Networks with an HTTPS proxy.** If `pip` reports a certificate verification error behind an institutional proxy,
follow your institution's instructions for pip and certificates. RNPLens itself needs no network access once
installed.

DockQ 2.1.3 may be compiled from its source distribution during installation, which needs a C compiler
(on macOS the Xcode Command Line Tools: `xcode-select --install`; on Linux `gcc`).

The runtime dependencies are pinned exactly, because the frozen scorer depends on DockQ 2.1.3 and the regression
references were produced with these versions:

| package | version |
|---|---|
| DockQ | 2.1.3 |
| gemmi | 0.6.5 |
| biopython | 1.84 |
| numpy | 1.26.4 |
| scipy | 1.13.1 |
| matplotlib (optional) | ≥ 3.8 |

Installing into an existing environment that needs other versions of these packages is not supported; use a
dedicated virtual environment.

## Check the installation

```bash
rnplens --version
rnplens selftest
```

`rnplens doctor` checks the installation. Without the `html` extra it lists **Optional matplotlib** as ACTION
REQUIRED (remedy: `pip install 'rnplens[html]'`). An optional component never makes the exit status non-zero: when
Optional matplotlib is the only check that is not READY, `rnplens doctor` exits with status 0 and its summary line ends
with "(1 of them optional; exit status 0)". Every scientific function is then available; only images are missing.

`rnplens selftest` runs Evaluate's regression fixtures, Report's public self-test and Diagnose's 18 contract checks
and example regression. It needs no internal file and should end with
`PASS: rnplens selftest {'evaluate': 0, 'report': 0, 'diagnose': 0}` (about 20–30 s). Off the reference platform the self-test
uses the frozen **portable** numerical profile: unrounded floating-point values may differ from the reference values
in their last digits (on macOS arm64 the observed differences were up to a few × 10⁻⁶ Å, in LRMSD values, against
a frozen tolerance of 10⁻⁵ Å), and every rounded value, class, count and label must match exactly. The line
`all checks bit-exact: False` is then expected and is not a failure; the verdict is the final `PASS`/`FAIL`. `--profile reference` demands
bit-identical values and is meaningful only on the reference platform.

## Commands installed

One command, `rnplens`. The internal modules behind it (see [identifiers.md](identifiers.md)) are not a public
interface.

The component packages' own command lines predate the 0.4 blocks. Where they would show a result that is BLOCKED in
0.4 (Evaluate's four-axis geometry, the Diagnose workflow or its interpretation, the frozen sources' research
drivers), they refuse with `LEGACY_ROUTE_REFUSED` and exit code 5 before anything is computed, read or written, and
name the `rnplens` command to use instead. This covers `python -m rnpbench evaluate run|selftest`, `python -m rnpbench selftest`, `python -m rnpbench toolkit selftest`, `python -m rnpbench diagnose …`, `python -m rnpbench_evaluate[.cli] evaluate|selftest`, every `python -m rnpbench_diagnose…` verb, every `python -m rnpbench_core…` module, other component submodules (e.g. `python -m rnpbench.evaluate`), and the same packages run by path. Verbs that show nothing blocked still run (`validate`,
`provenance`, help, `--version`, and every Report verb). Importing the packages from Python is unaffected
(`rnplens.legacy_routes`; `tests/test_legacy_route_refusal.py`).

## Troubleshooting

- `ERROR: Package 'rnplens' requires a different Python` — use Python 3.10–3.12.
- `rnplens: required package(s) not installed: ...` (exit code 3) — a required package (DockQ, gemmi, biopython, numpy,
  scipy) is missing from this environment. The message gives the exact `python -m pip install` command; reinstalling
  RNPLens from its wheel, sdist or clone installs all of them. `rnplens doctor` still runs and lists every check.
- `rnplens <command>: refused: ... not found: <path> (nothing was run)` (exit code 2) — an input file or folder is
  missing or of the wrong kind (for example a folder where a contract file is expected, a project folder without
  `manifest.json`, a FASTA path that does not exist). Nothing was computed or written.
- `DockQ version ... is not the pinned 2.1.3` — reinstall into a clean environment. Evaluate refuses to run with
  another DockQ unless `--allow-unpinned` is given, and then records that the results are not the frozen
  configuration.
- `rnplens report run` wrote no HTML page, or an `analyse`/`region` page says an image was not drawn — install the
  `html` extra (matplotlib).
- `rnplens doctor` lists **Optional matplotlib** as ACTION REQUIRED (exit status 0) — see *Check the installation*;
  the installation is complete for every scientific function.
