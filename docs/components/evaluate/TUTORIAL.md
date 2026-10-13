# Tutorial: evaluate a predicted protein–RNA complex with `rnpbench evaluate`

You need three things: a predicted complex, the experimental structure as mmCIF, and the protein and RNA construct sequences that the prediction was made from.

## 1. Install

```bash
conda env create -f environment.yml      # Python 3.11 with the pinned DockQ 2.1.3, gemmi, Biopython, NumPy, SciPy
conda activate rnpbench-evaluate
pip install .                             # run in the package directory; provides the `rnpbench` command
```

Alternatively, inside any Python 3.10–3.12 virtual environment, run `pip install ".[test]"`.

## 2. Check the installation reproduces the frozen benchmark values

```bash
rnpbench selftest --profile portable          # on any platform
rnpbench selftest --profile reference         # on the reference platform (Linux x86-64): requires every value bit-identical
python -m pytest tests                        # from the source directory; RNPBENCH_PROFILE=reference|portable
```

The self-test scores the bundled fixtures and compares every value with the released RNPBench records:
- five benchmark fixtures: an ordinary complex, a short RNA, a partial reference, non-uniform residue numbering and equivalent interface copies;
- four constructed controls: RNA chain removed, residues renumbered, protein residues replaced by alanine (a metric refusal), and chain labels swapped.

The **portable** profile (`rnpbench_evaluate/profiles/portable_numerical_profile_v1.json`, frozen before testing) allows the following, and nothing else:
- 1e-5 Å on unrounded RMSD values;
- 1e-7 on unrounded DockQ values.

Everything else must be exactly equal: displayed values, DockQ classes, chain mapping, residue correspondence, status, no-value reasons and every integer count. All deviations are listed, including those within tolerance.

## 3. Evaluate the worked example

```bash
cd examples
rnpbench evaluate --input example_input.json --out my_result
# or, without a JSON file:
rnpbench evaluate --prediction 7K9D_prediction.pdb --reference 7K9D_reference.cif \
    --protein-seq 7K9D_protein.fasta --rna-seq 7K9D_rna.fasta --target-id 7K9D --out my_result2
```

The output directory holds:
- `summary.txt`: a short human-readable report (see `example_output/summary.txt`);
- `result.json`: every value, the selected chain mapping, all candidate outcomes, residue-correspondence counts, the construct/reference/prediction correspondence checks, validity and provenance (input checksums, software versions, checksums of the frozen scoring sources);
- `result.csv`: one row with the main values. Missing values are written `NO_VALUE`.

An existing output directory is never overwritten.

## 4. Reading the result

- **DockQ** is the released RNPBench value: the first interface of the best admissible chain mapping, under **construct-position** residue correspondence. The classes follow the standard DockQ bins: < 0.23 incorrect, < 0.49 acceptable, < 0.80 medium, otherwise high.
- **Geometry** comes from a **separate** frozen route that matches residues by **sequence alignment**:
  - **RNA internal C4′ RMSD** measures the RNA's own shape;
  - **RNA placement C4′ RMSD** measures where the RNA sits once the proteins are superposed;
  - **protein Cα RMSD** is computed over the whole construct.

  The two routes can disagree about whether an input is scoreable. Each route's status is reported separately.
- **NO VALUE** means the frozen rules give no number for this input. It is not zero and must not be averaged as zero. The report states the stage and the reason.
- **Correspondence notes** are reported, never corrected. In the worked example the report says `rna construct differs from the reference entity at 1 G/X`: the deposited 7K9D RNA starts with a 5′-triphosphate guanosine (GTP), while the construct, and the prediction, have G. The geometry route therefore uses 59 of the 60 nucleotides.

## 5. What this tool does not do

- It scores **one user-supplied prediction at a time**. It does **not** run structure prediction and does **not** choose among several engine samples: you supply the output to evaluate, and `designated_output` only records which output that is.
- It gives no confidence or probability of correctness. All values are reference-based accuracy measurements.
- It handles one protein entity and one RNA entity per evaluation. DNA, ligands and modified-nucleotide chemistry are outside the frozen scope.
