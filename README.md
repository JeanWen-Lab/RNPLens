# RNPLens

**Evaluation and diagnostic tools for protein–RNA complex predictions.**

> **Status: release candidate `0.2.0rc3` — not yet publicly released.** MIT licence, subject to institutional
> (ANU) intellectual-property approval before public release. The software accompanies a manuscript in
> preparation; see [Citation](#citation).

**New to RNPLens? Start with [Which analysis should I use?](docs/which_analysis_should_i_use.md)**

RNPLens helps researchers examine protein–RNA complex structures that have **already been predicted** (for example by
AlphaFold 3, Boltz-2, Chai-1, RoseTTAFold-family models or docking), identify where a prediction may be limited,
and produce reproducible, machine-readable assessments.

**RNPLens does not predict structures.** It does not generate complexes from sequence, does not pick a "best"
structure for you, and gives **no calibrated probability that a structure or an interface is correct**.

## What can RNPLens do?

| tool | question it answers | input | experimental structure needed? |
|---|---|---|---|
| **Evaluate** | How close is this prediction to the experimental structure? | one predicted complex, one experimental mmCIF, the construct sequences | **yes** |
| **Report** | Do several predictions of the same complex propose the same interface? | two or more predicted complexes (one or several engines) | no |
| **Diagnose** | Are the outputs valid structures, and how much do the candidates disagree? | candidate structures (samples of one engine, or one per engine) | no |

Each tool answers a different question, and their outputs are never combined into a single score.

- **Evaluate** reports two independent routes side by side: a DockQ route (DockQ, fnat, iRMSD, LRMSD with construct-position residue correspondence over all admissible chain mappings) and a geometry route (RNA conformation C4′ RMSD, RNA placement after protein superposition, protein Cα RMSD). An output that cannot be scored is reported as **NO VALUE** with the stage and reason — never as zero.
- **Report** measures agreement on the binding surface, on the exact residue–nucleotide contacts (contact register) and on RNA pose, and groups engines into interface hypotheses. **Agreement among predicted structures is descriptive evidence, not a calibrated probability of structural correctness.** Engines can agree and still be wrong.
- **Diagnose** separates technically broken files from structural failures from valid outputs, and measures protein-side and RNA-side disagreement among candidates relative to a frozen benchmark reference. Disagreement is a **review flag**, not a correctness score; **low disagreement does not guarantee an accurate structure** (candidates that are all wrong in the same way look consistent). The protein-side signal has been checked out of sample but overlaps substantially with the engine's own confidence (pTM, pLDDT); the RNA-side statement has not been validated out of sample.

## Quick start

Requirements: CPython 3.10, 3.11 or 3.12 on Linux or macOS; no GPU. Dependencies are pinned and installed from PyPI
(DockQ 2.1.3, gemmi 0.6.5, biopython 1.84, numpy 1.26.4, scipy 1.13.1; matplotlib only for Report's HTML page).

```bash
git clone <repository-url>      # URL to be supplied at release
cd RNPLens
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[html]"
rnplens --version
rnplens selftest                # about 20 s on a laptop CPU; prints PASS for all three tools
```

`rnplens --help`, `rnplens evaluate --help`, `rnplens report --help` and `rnplens diagnose --help` describe every
command; `rnplens <tool> <verb> --help` lists a verb's options.

Run both worked examples below in one step (the output directory must not exist; nothing is ever overwritten):

```bash
bash examples/run_examples.sh rnplens_example_outputs
```

## Example 1 — Reference-based evaluation

A Boltz-2 prediction of PDB [7K9D](https://www.rcsb.org/structure/7K9D) (98-residue protein, 60-nt RNA) scored
against the deposited structure. Inputs are in `examples/reference_based/`: `7K9D_prediction.pdb`,
`7K9D_reference.cif`, the construct sequences `7K9D_protein.fasta` and `7K9D_rna.fasta`, and `example_input.json`,
which names them.

```bash
cd examples/reference_based
rnplens evaluate validate --input example_input.json
rnplens evaluate run --input example_input.json --out ../../out_evaluate_7K9D
```

Outputs: `result.json` (full record, including correspondence, chain mapping, SHA-256 of every input and of the
frozen scorer sources), `result.csv` (one row), `summary.txt`:

```
DockQ (frozen RNPLens scoring configuration, construct-position correspondence)
  DockQ 0.936  [high]   fnat 0.927   iRMSD 0.434 A   LRMSD 1.780 A
  chain mapping AB:AB (best of 1 admissible); residue pairs in frame 148, out of frame 0, indeterminate 0

Structural geometry (frozen four-axis decomposition; alignment-based correspondence)
  RNA internal C4' RMSD 0.75 A over 59 nt
  RNA placement C4' RMSD after protein superposition 1.79 A
  protein internal CA RMSD 0.52 A over 89 residues (whole construct; scales with length)
...
  rna construct differs from the reference entity at 1 G/X (X = modified residue in the reference); reported, not corrected
```

How to read it: DockQ summarises interface accuracy; fnat is the fraction of native residue–nucleotide contacts
reproduced. The geometry route separates whether the RNA has the right shape (internal RMSD) from whether it sits
in the right place on the protein (placement RMSD). Whole-construct protein RMSD reflects domain arrangement and is
not a domain-level fold-accuracy measure. Positions that are missing from the experimental structure are unknown,
not confirmed non-contacts. The bundled reference is a reduced copy of PDB 7K9D whose RNA sequence record lists
the 5′-triphosphate guanosine as `X`, so it is reported as a construct–reference difference and left uncorrected.
(With the full RCSB file the canonical sequence record lists it as `G`, and the construct then equals the reference
entity; the scores are identical. Evaluate compares against `_entity_poly.pdbx_seq_one_letter_code_can` when the
file has it.) These are accuracy measurements of one prediction, not a confidence estimate.

## Example 2 — Reference-free assessment

Run these from the repository root (after Example 1: `cd ../..`). No experimental structure is read. Inputs are in `examples/reference_free/`: the top-ranked output of two independent
Boltz-2 runs of 7K9D with their confidence files (`report_7K9D/`), and the five samples of one Boltz-2 run
(`diagnose_7K9D/`).

**Interface agreement (Report).** Report requires absolute paths; `example-contract` writes a filled-in contract.

```bash
rnplens example-contract examples/reference_free --out contract.json
rnplens report validate contract.json
rnplens report run contract.json --out out_report_7K9D
```

Outputs: `result.json`, `contacts_by_output.json` and a self-contained HTML page. For this example, with one engine,
Report describes **repeat agreement** between the two runs: binding-surface agreement 0.88, contact-register
agreement 0.89, RNA pose difference 0.96 Å; 47 distinct residue–nucleotide contacts were proposed, one interface
hypothesis (with a single engine there is always exactly one, so read the repeat agreement instead).
Cross-engine agreement needs outputs from several engines.

**Validity and candidate disagreement (Diagnose).**

```bash
rnplens diagnose validity examples/reference_free/diagnose_7K9D/*.pdb
rnplens diagnose run examples/reference_free/diagnose_7K9D/*.pdb --mode within_engine --engine BOLTZ2 --target 7K9D --out out_diagnose_7K9D
```

Outputs: `report.json` and `report.html`. All five samples are `VALID`. The diagnosis reads:

```
The protein is variable across the candidates: disagreement 0.89 A, high relative to the frozen development
reference (52th percentile of 65 development targets).
The RNA (this mode cannot separate its shape from its placement) is consistent across the candidates:
disagreement 0.56 A, typical relative to the frozen development reference (25th percentile of 65 development targets).
```

Diagnose explicitly refuses to attribute error to RNA placement, to give a probability of correctness or to
recommend an engine; every report carries these limits. It also checks that the run is inside the conditions
under which its statements were validated (here: 5 Boltz-2 candidates, one protein and one RNA chain each) and
refuses otherwise unless you pass `--allow-outside-validated-domain`; see
[docs/which_analysis_should_i_use.md](docs/which_analysis_should_i_use.md#when-is-a-diagnose-statement-validated).

Every `run` also writes `rnplens_run.json` next to the results: the RNPLens release, the command, and the SHA-256
of every input and output file.

The full expected outputs of both examples, with the platform they were produced on, are in
[`examples/expected_output/`](examples/expected_output/). See [docs/quickstart.md](docs/quickstart.md) for a
field-by-field walk-through.

## Interpreting results responsibly

RNPLens keeps apart quantities that are easily conflated:

- structural accuracy (Evaluate) vs physical validity of the file (Diagnose `validity`);
- RNA conformation vs RNA placement;
- binding-surface agreement vs exact contact-register agreement;
- reference-free agreement (Report, Diagnose) vs known accuracy (Evaluate);
- available structural outputs vs scoreable outputs;
- native-informed diagnostics in the manuscript vs the deployable, reference-free tools here.

See [docs/interpretation.md](docs/interpretation.md) and [docs/limitations.md](docs/limitations.md).

## Documentation

[which analysis should I use?](docs/which_analysis_should_i_use.md) ·
[installation](docs/installation.md) · [quick start](docs/quickstart.md) · [Evaluate](docs/evaluate.md) ·
[Report](docs/report.md) · [Diagnose](docs/diagnose.md) · [output formats](docs/output_formats.md) ·
[interpretation](docs/interpretation.md) · [limitations](docs/limitations.md) ·
[reproducibility](docs/reproducibility.md) · [Evaluate input contract](docs/INPUT_CONTRACT.md) ·
[identifiers](docs/identifiers.md) · [validation records](docs/validation/) · [output schemas](docs/schemas/) ·
[example data provenance](examples/DATA_PROVENANCE.tsv) · [software vs study reproducibility](docs/paper_reproducibility.md)

## Provenance of the implementation

RNPLens distributes the evaluation, reporting and diagnostic procedures developed and qualified for the
accompanying study. Their computations are unchanged from the internally qualified component set, and the frozen
scorer files are verified by SHA-256 at run time. A few machine-readable identifiers keep the project's earlier
internal prefix so that this stays verifiable; they are listed in [docs/identifiers.md](docs/identifiers.md). The
study's benchmark resource (its entries, partitions and score stores) is **not** part of this repository, and the
software version is independent of the manuscript's evidence build identifier. See
[docs/reproducibility.md](docs/reproducibility.md), and [docs/paper_reproducibility.md](docs/paper_reproducibility.md)
for what this repository does and does not reproduce of the study.

## Citation

If you use RNPLens, please cite the accompanying manuscript (in preparation; citation details will be added on
publication) and the software release. See [`CITATION.cff`](CITATION.cff). No DOI has been issued yet.

## Licence

RNPLens is released under the [MIT licence](LICENSE), subject to institutional (ANU) intellectual-property
approval before public release. Third-party dependencies keep their own licences. Every bundled structure is listed
with its origin, terms and attribution in [examples/DATA_PROVENANCE.tsv](examples/DATA_PROVENANCE.tsv) (see also
[docs/dependencies.md](docs/dependencies.md)). Security issues: see [SECURITY.md](SECURITY.md).
