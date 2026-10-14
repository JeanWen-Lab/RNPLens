# Installation

## Requirements

- CPython **3.10, 3.11 or 3.12** (3.13 is not supported: the pinned numpy 1.26.4 and scipy 1.13.1 have no 3.13 wheels).
- Linux (x86-64) or macOS (arm64). These are the platforms on which this release candidate was qualified
  (see [reproducibility.md](reproducibility.md)). Windows has not been tested.
- No GPU, no model weights, no network service and no credentials. RNPLens reads structure files you already have.

## Install from a clone

```bash
git clone <repository-url>      # URL to be supplied at release
cd RNPLens
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[html]"
```

`[html]` adds matplotlib, needed only for the figures on Report's HTML page; without it, Report still writes its
JSON output and Evaluate and Diagnose are unaffected. `[test]` adds pytest. A non-editable install
(`python -m pip install .`) also works.

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

## Troubleshooting

- `ERROR: Package 'rnplens' requires a different Python` — use Python 3.10–3.12.
- `DockQ version ... is not the pinned 2.1.3` — reinstall into a clean environment. Evaluate refuses to run with
  another DockQ unless `--allow-unpinned` is given, and then records that the results are not the frozen
  configuration.
- Report's HTML page has no figures — install the `html` extra.
