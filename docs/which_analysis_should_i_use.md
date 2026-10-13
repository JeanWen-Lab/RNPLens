# Which analysis should I use?

You have protein–RNA complex structures that were already predicted, for example by AlphaFold 3, Boltz-2, Chai-1,
RF3, RoseTTAFold2NA or a docking program. RNPLens does not predict structures and does not reduce a prediction to
one score. Each tool answers a different question, and the outputs of different tools are never combined.

## Start here

| what you have | use | what it tells you |
|---|---|---|
| a prediction **and** an experimental structure of the same complex | **Evaluate** | how close the prediction is: interface accuracy (DockQ, fnat, iRMSD, LRMSD), RNA shape, RNA placement and protein geometry, and whether the prediction could be evaluated at all |
| predictions **without** an experimental structure, from one or more engines or runs | **Report** | whether the outputs propose the same binding surface, the same residue–nucleotide contacts and the same RNA pose, and which alternative interface hypotheses exist |
| several predictions **without** an experimental structure | **Diagnose** | whether each file is a usable protein–RNA complex, and where the predictions disagree (protein, RNA), relative to a frozen reference, within the validated conditions below |

Report and Diagnose can be run on the same predictions; they answer different questions and their outputs stay
separate. Evaluate is the only tool that measures correctness, and it needs an experimental reference.

## Three rules for reading any result

1. **Agreement is not correctness.** Outputs can agree with each other and all be wrong in the same way.
   Agreement and disagreement are descriptive; RNPLens never converts them into a probability of being correct.
2. **A missing score is not zero.** An output that cannot be scored is reported as a named outcome (`NO_VALUE`,
   `INELIGIBLE_POLYMER_ABSENT`, `TECHNICAL_FAILURE`, …) with the reason. Do not average it in as 0.
3. **Accuracy and validity are different questions.** A well-formed, physically valid structure can be far from
   the experimental complex; Evaluate measures accuracy, Diagnose's validity stage checks usability.

## What each reported value means

| value | tool | reference needed | unit and range | better is | read it as |
|---|---|---|---|---|---|
| DockQ | Evaluate | yes | 0–1 | higher | interface accuracy; classes incorrect < 0.23 ≤ acceptable < 0.49 ≤ medium < 0.80 ≤ high |
| fnat | Evaluate | yes | 0–1 | higher | fraction of experimental residue–nucleotide contacts reproduced |
| iRMSD, LRMSD | Evaluate | yes | Å, ≥ 0 | lower | interface and ligand (RNA) RMSD of the DockQ calculation |
| RNA internal C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | RNA shape, after superposing the RNAs |
| RNA placement C4′ RMSD | Evaluate | yes | Å, ≥ 0 | lower | where the RNA sits, after superposing the proteins |
| protein internal Cα RMSD | Evaluate | yes | Å, ≥ 0 | lower | whole-construct protein geometry (includes domain arrangement; grows with length) |
| `dockq_status`, `geometry_status` | Evaluate | yes | `SCORED` / `NO_VALUE` | — | whether the value exists; the failing stage and reason are recorded |
| surface agreement | Report | no | 0–1 | — | weighted Jaccard overlap of the protein interface residues proposed by two outputs or engines |
| register agreement | Report | no | 0–1 | — | weighted Jaccard overlap of the residue–nucleotide contacts (5 Å); stricter than surface agreement |
| RNA pose difference | Report | no | Å, ≥ 0 | — | RNA C4′ RMSD between two outputs after superposing their proteins |
| contact support | Report | no | count of engines | — | how many engines propose a contact (each engine counts once) |
| interface hypotheses | Report | no | groups of outputs | — | outputs grouped by register agreement at 0.3, 0.5 and 0.7; listed, never ranked |
| validity class | Diagnose | no | `VALID` / `TECHNICAL_FAILURE` / `STRUCTURAL_FAILURE` | — | whether a file is a usable protein–RNA complex |
| protein, RNA disagreement | Diagnose | no | Å, ≥ 0 | — | median pairwise RMSD among the supplied structures for that component |
| band and percentile | Diagnose | no | low / typical / high / very high | — | where the disagreement sits in the frozen development reference, not among your structures |
| placement disagreement | Diagnose | no | Å | — | measured and reported, deliberately **not** interpreted (attribution was tested and did not hold) |

"—" means there is no better direction: high agreement is not evidence of correctness, and low agreement is not
evidence of error.

## When is a Diagnose statement validated?

Diagnose's statements were validated on particular inputs, and Diagnose checks every run against them. Outside
these conditions it refuses, unless you add `--allow-outside-validated-domain`; the report then carries a
prominent "Outside the validated domain" notice and records the reasons in `report.json` under `applicability`.

| mode | validated conditions | evidence | statement licensed |
|---|---|---|---|
| `within_engine` | candidates of **Boltz-2** (declare `--engine BOLTZ2`); **5 to 50** valid candidates; each structure **one protein chain and one RNA chain** | development: 65 targets, 50 candidates each, depth control at 5; out of sample: 807 targets, 5 candidates each (ρ 0.525 [0.450, 0.593], smaller than in development) | protein-side disagreement tracks protein error. The RNA statement cannot separate RNA shape from placement in this mode |
| `cross_engine` | one designated output from each of **3 or more** of Boltz-2, Chai-1, RF3, RoseTTAFold2NA (declare each with `--engine`); one protein chain and one RNA chain each | development only: 59 targets, four engines; **not tested out of sample** | RNA-conformation disagreement tracks RNA-conformation error. The protein statement is not resolved as specific here |

What is checked: the declared engine labels, the number of valid structures and the chain composition of each
file. What cannot be checked: that the labels are true, the engine versions (the reference used boltz 2.2.1,
chai_lab 0.6.1, RF3 from rc-foundry 0.2.0 and the RoseTTAFold2NA weights `RF2NA_apr23.pt`, as installed on the
study host), sampling settings, and whether your complexes resemble the reference cohorts. Those are deposited
PDB complexes of one protein and one RNA, with RNA lengths of 5–417 nt (median 68) in the within-engine reference
and 4–227 nt (median 31) in the cross-engine reference. AlphaFold 3 is outside both modes: its designated output could not be
verified when the reference was built.

Even inside the domain, a Diagnose statement is triage, not a verdict. On the out-of-sample cohort the
protein-side association fell from ρ 0.525 to 0.167 once protein length, protein pTM and mean protein pLDDT were
accounted for. Read it next to the engine's own per-chain confidence, not instead of it.

## Common questions

**My predictions agree strongly. Is the complex right?** Not necessarily. Agreement shows that the outputs
propose the same interface; they can share the same error. Only Evaluate, with an experimental structure, measures
correctness.

**Which engine is best for my complex?** RNPLens does not answer this. Diagnose refuses a best-engine
recommendation, and Report lists alternative hypotheses without ranking them.

**One output has no value. Should I treat it as a failure with score 0?** No. Report the named outcome and its
reason. A file that lacks the RNA chain is not a poor prediction of the complex; it is not a prediction of it.

**Can I use RNPLens on DNA, multi-protein or multi-RNA assemblies?** Evaluate and Report require one protein entity
and one RNA entity (any copy number). Diagnose statements are validated only for one protein chain and one RNA
chain. Other compositions are outside what RNPLens was built and qualified for.

**My experimental structure is an NMR ensemble or cryo-EM model.** Evaluate scores against the single model you
supply; results depend on that choice and should be reported with it.

See also: [quickstart.md](quickstart.md), [interpretation.md](interpretation.md), [limitations.md](limitations.md),
[output_formats.md](output_formats.md).
