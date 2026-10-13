# RNPLens Evaluate — reference-based evaluation

Evaluate scores **one** predicted protein–RNA complex against **one** experimental reference. It needs the
experimental structure; use [Report](report.md) or [Diagnose](diagnose.md) when you have none.

```
rnplens evaluate run      --input contract.json --out DIR      # or --prediction/--reference/--protein-seq/--rna-seq
rnplens evaluate validate --input contract.json                # check a contract without scoring
rnplens evaluate selftest [--profile portable|reference]       # regression fixtures
rnplens evaluate provenance [--full]                           # versions and frozen-source hashes
```

## Inputs

- the prediction (`.pdb` or `.cif`), residues numbered 1..L along each construct;
- the experimental reference (mmCIF with `label_seq_id`), one protein entity and one RNA entity, any copy number;
- the construct sequences that were given to the predictor (protein; RNA in ACGU), as strings or FASTA files.

The JSON contract `RNPBENCH_EVALUATE_INPUT_V1` and every rule are in [INPUT_CONTRACT.md](INPUT_CONTRACT.md); a test
checks that the document and the code agree. Evaluate does not choose a designated output from a pool of
candidates: you choose which output to evaluate, and `prediction.designated_output` only records that choice.

## Two routes, reported separately

| route | correspondence | values |
|---|---|---|
| **DockQ** (`RNPBENCH_SCORING_V3_CONSTRUCT_POSITION_DOCKQ_2_1_3`) | construct position, over all admissible chain mappings | DockQ (and class), fnat, iRMSD, LRMSD, selected mapping, pairs in/out of frame |
| **geometry** (frozen four-axis decomposition) | sequence alignment, on the contacting protein–RNA chain pair | RNA internal C4′ RMSD, RNA placement C4′ RMSD after protein superposition, protein internal Cα RMSD |

Because the correspondences differ, one route can return a value where the other returns NO VALUE. The two are
never merged.

## No value is never zero

An output that cannot be scored (no admissible mapping, a missing polymer, unusable numbering, …) gets
`dockq_status NO_VALUE` or `geometry_status NO_VALUE` with the failing stage and the reason. `result.csv`
leaves the value fields empty and `summary.txt` prints `NO VALUE (not zero)`. Missing chains, residue-numbering
problems and partial references are covered by the bundled regression fixtures.

## Reported, not corrected

Differences between the construct, the reference entity and the prediction (modified residues, numbering offsets,
unresolved positions) are reported and never silently corrected. Positions missing from the experimental
structure are unknown, not confirmed non-contacts.

## Interpretation

- DockQ summarises interface accuracy; its class uses the standard DockQ boundaries (incorrect < 0.23 ≤
  acceptable < 0.49 ≤ medium < 0.80 ≤ high). fnat is the fraction of native residue–nucleotide contacts reproduced.
- RNA internal RMSD measures RNA shape; RNA placement RMSD measures where the RNA sits once the proteins are
  superposed. A prediction can have the right RNA shape in the wrong place, or the reverse.
- Whole-construct protein Cα RMSD reflects domain arrangement as well as fold and scales with length; it is not a
  domain-level fold-accuracy measure.
- These are accuracy measurements of one prediction against one reference, not a confidence estimate, and they
  depend on the reference representation chosen (for example one NMR model rather than the ensemble).

Frozen numerical tolerances of the portable profile: [validation/PORTABLE_QUALIFICATION_CONTRACT.md](validation/PORTABLE_QUALIFICATION_CONTRACT.md).
