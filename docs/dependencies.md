# Dependencies and third-party terms

This is a factual inventory, not legal advice. Licences were read from the installed package metadata.

## Runtime dependencies (installed from PyPI; none is copied into this repository)

| package | version | licence | role |
|---|---|---|---|
| DockQ | 2.1.3 (pinned) | MIT | DockQ route of Evaluate. The frozen adapter temporarily substitutes two DockQ 2.1.3 internal functions during one call, which is why the version is pinned; no DockQ code is copied |
| gemmi | 0.6.5 (pinned) | MPL-2.0 | structure parsing (file-level copyleft applies only to modified gemmi files; none are modified or bundled) |
| biopython | 1.84 (pinned) | Biopython License Agreement / BSD-3-Clause (BSD-style) | structure parsing, superposition |
| numpy | 1.26.4 (pinned) | BSD-3-Clause | numerics |
| scipy | 1.13.1 (pinned) | BSD-3-Clause | numerics |
| matplotlib (optional, `html`) | ≥ 3.8 (qualified with 3.9.2) | Matplotlib licence (PSF-style) | figures in Report's HTML page |
| pytest (optional, `test`) | any | MIT | tests |

Installed transitively through DockQ and matplotlib, unpinned (as in the qualified toolkit): networkx (BSD-3-Clause),
parallelbar (MIT), tqdm (MPL-2.0 AND MIT), colorama (BSD), pillow (MIT-CMU), contourpy, cycler, kiwisolver
(BSD), fonttools, pyparsing, six (MIT), packaging (Apache-2.0 OR BSD-2-Clause), python-dateutil (Apache-2.0 / BSD).

## Data in this repository

| files | content | terms |
|---|---|---|
| `examples/`, `src/rnpbench/examples/`, `src/rnpbench_report/selftest_data/` | Boltz-2 predictions of PDB 7K9D generated in the study | Boltz-2 code and weights are MIT-licensed; no output-specific terms were found. **Redistribution of these outputs awaits owner confirmation** |
| `src/rnpbench_evaluate/fixtures/` | Boltz-2 predictions and trimmed copies of the PDB entries 7K9D, 4I67, 2JEA, 4PMI and 6E4P | wwPDB archive data are CC0 1.0; the Boltz-2 outputs as above |
| `examples/reference_based/7K9D_reference.cif` | PDB entry 7K9D | CC0 1.0 |
| `src/rnpbench_diagnose/reference/` | per-target disagreement summaries (numbers only, no coordinates) from the benchmark's development cohorts, including Chai-1, RF3 and RF2NA outputs | derived values; **confirmation needed** that no engine's output terms restrict publishing such summaries |

Outputs of AlphaFold 3, Chai-1, RoseTTAFold2NA and RF3 are **not** included: their output terms are restrictive or
unverified, and they remain internal qualification fixtures.

## RNPLens's own licence

Not yet chosen; see the README.
