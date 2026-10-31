# Which analysis should I use?

> This is the user guide for RNPLens 0.4. The optional Assistant reads a frozen copy of an earlier version of this
> page (`assistant/rnplens_assistant/docs/`, its evaluated reference text). That copy still describes Diagnose,
> which the Assistant's plan checks refuse.

You have protein–RNA complex structures that were already predicted, for example by AlphaFold 3, Boltz-2, Chai-1,
RF3, RoseTTAFold2NA or a docking program. RNPLens does not predict structures and does not reduce a prediction to
one score. Each tool answers a different question, and the outputs of different tools are never combined.

## Start here

| what you have | use | what it tells you |
|---|---|---|
| a prediction **and** an experimental structure of the same complex | **Evaluate** | how close the prediction is: interface accuracy (DockQ, DockQ class, fnat, iRMSD, LRMSD) and whether the prediction could be evaluated at all; RNA shape, RNA placement and protein geometry (the four-axis geometry route) are blocked in this version, see below |
| predictions **without** an experimental structure, from one or more engines or runs | **Report** | whether the outputs propose the same binding surface, the same residue–nucleotide contacts and the same RNA pose, and which alternative interface hypotheses exist |

Evaluate and Report can be run on the same predictions; they answer different questions and their outputs stay
separate. Evaluate is the only tool that measures correctness, and it needs an experimental reference. Diagnose
(file validity and candidate disagreement) is not available in RNPLens 0.4; its reference material is in
[diagnose.md](diagnose.md).

## Three rules for reading any result

1. **Agreement is not correctness.** Outputs can agree with each other and all be wrong in the same way.
   Agreement and disagreement are descriptive; RNPLens never converts them into a probability of being correct.
2. **A missing score is not zero.** An output that cannot be scored is reported as a named outcome (`NO_VALUE`,
   `INELIGIBLE_POLYMER_ABSENT`, `TECHNICAL_FAILURE`, …) with the reason. Do not average it in as 0.
3. **Accuracy and validity are different questions.** A well-formed, physically valid structure can be far from
   the experimental complex; Evaluate measures accuracy, while Report's eligibility check only establishes that an
   output can be compared.

## What each reported value means

| value | tool | reference needed | unit and range | better is | read it as |
|---|---|---|---|---|---|
| DockQ | Evaluate | yes | 0–1 | higher | interface accuracy; classes incorrect < 0.23 ≤ acceptable < 0.49 ≤ medium < 0.80 ≤ high |
| fnat | Evaluate | yes | 0–1 | higher | fraction of experimental residue–nucleotide contacts reproduced |
| iRMSD, LRMSD | Evaluate | yes | Å, ≥ 0 | lower | interface and ligand (RNA) RMSD of the DockQ calculation |
| RNA internal C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | **blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14). Definition: RNA shape, after superposing the RNAs |
| RNA placement C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | **blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14). Definition: where the RNA sits, after superposing the proteins |
| protein internal Cα RMSD | Evaluate | yes | Å, ≥ 0 | lower | **blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14). Definition: whole-construct protein geometry (includes domain arrangement; grows with length) |
| `dockq.status`, `geometry.status` | Evaluate | yes | `SCORED` / `NO_VALUE` (DockQ); `COMPUTED` / `NO_VALUE` / `BLOCKED` (geometry) | — | whether the value exists; the failing stage and reason are recorded. The geometry values are blocked in this version and are not computed. |
| surface agreement | Report | no | 0–1 | — | weighted Jaccard overlap of the protein interface residues proposed by two outputs or engines |
| register agreement | Report | no | 0–1 | — | weighted Jaccard overlap of the residue–nucleotide contacts (5 Å); stricter than surface agreement |
| RNA pose difference | Report | no | Å, ≥ 0 | — | RNA C4′ RMSD between two outputs after superposing their proteins |
| contact support | Report | no | count of engines | — | how many engines propose a contact (each engine counts once) |
| interface hypotheses | Report | no | groups of engines | — | engines grouped by register agreement at 0.3, 0.5 and 0.7; listed, never ranked. With one engine there is always exactly one hypothesis: read the repeat agreement instead |
| repeat agreement | Report | no | surface and register 0–1, pose Å | — | the same three agreement measures between the runs of one engine; computed only when the engine has exactly two eligible outputs (otherwise absent: not computed, not zero) |

"—" means there is no better direction: high agreement is not evidence of correctness, and low agreement is not
evidence of error.

> **Four-axis geometry is blocked.** Evaluate's four-axis geometry route (protein-internal Cα RMSD, RNA-internal C4′
> RMSD, RNA placement C4′ RMSD) is blocked because of a residue-correspondence defect found on 2026-10-14; its
> values are not computed and must not be reported. DockQ, DockQ class, fnat, iRMSD and LRMSD remain available
> under their own definitions (the DockQ calculation). They are not replacements for the four-axis decomposition:
> iRMSD and LRMSD do not separate RNA shape, RNA placement and protein geometry.

## Labels for engines

| tool | how the engine is given | accepted |
|---|---|---|
| Evaluate | `--engine` or `prediction.engine`: a free label recorded in the result | any text |
| Report | `outputs[].engine` in the contract | exactly `AF3`, `BOLTZ2`, `CHAI1`, `RF3`, `RF2NA` or `OTHER` |

## Construct sequences from engine input files

Evaluate and Report need the protein and RNA sequences that were given to the predictor:
- Boltz-2 YAML: `sequences[].protein.sequence` and `sequences[].rna.sequence`;
- AlphaFold 3 JSON: `sequences[].protein.sequence` and `sequences[].rna.sequence`;
- Chai-1 FASTA: the `>protein|…` and `>rna|…` records.

Write each to a FASTA file (or pass the string) with `--protein-seq` and `--rna-seq`, and give Report the lengths in
`construct.protein_length` and `construct.rna_length`.

## Exit status

The exit codes of the public commands, including code 5 for a blocked capability, are listed in
[capabilities.md](capabilities.md#7-scope-of-v040).

Nothing is written when a run is refused.

## Common questions

**My predictions agree strongly. Is the complex right?** Not necessarily. Agreement shows that the outputs
propose the same interface; they can share the same error. Only Evaluate, with an experimental structure, measures
correctness.

**Which engine is best for my complex?** RNPLens does not answer this. It never recommends an engine, and Report
lists alternative hypotheses without ranking them.

**One output has no value. Should I treat it as a failure with score 0?** No. Report the named outcome and its
reason. A file that lacks the RNA chain is not a poor prediction of the complex; it is not a prediction of it.

**Can I use RNPLens on DNA, multi-protein or multi-RNA assemblies?** Evaluate and Report require one protein entity
and one RNA entity (any copy number). Other compositions are outside what RNPLens was built and qualified for.

**My experimental structure is an NMR ensemble or cryo-EM model.** Evaluate scores against the single model you
supply; results depend on that choice and should be reported with it.

See also: [quickstart.md](quickstart.md), [interpretation.md](interpretation.md), [limitations.md](limitations.md),
[output_formats.md](output_formats.md).
