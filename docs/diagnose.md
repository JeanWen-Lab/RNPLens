# RNPLens Diagnose — validity and candidate disagreement (not available in 0.4.0)

Diagnose looks at candidate structures without any experimental reference. It answers two questions: are these
outputs usable structures at all, and how much do the candidates disagree with each other?

> **0.4 status: BLOCKED.** Diagnose is blocked in the public 0.4 interface until it is re-qualified: its statements
> about association with error and its validated domain rest on evidence that was recomputed under the corrected
> residue correspondence (`CONSTRUCT_POSITION_V2`, records of 2026-10-15; see the protein side below). The statements
> have not been re-qualified against it ([limitations.md](limitations.md)). `rnplens diagnose run`, `preflight` and
> `validity` refuse with
> `DIAGNOSE_BLOCKED` and **exit code 5**, and read or write nothing; `rnplens analyse` never runs Diagnose and
> `--with-diagnose` (`analyse`, `update`) is refused the same way. `rnplens diagnose selftest` and `rnplens selftest`
> still run the internal contract checks and the example regression (software checks, not interpretation); their
> display shows `Diagnose interpretation BLOCKED (checked, not shown)` in place of Diagnose's example statements. The frozen rc3 component is
> unchanged. The rest of this page describes the rc3 tool, for reference only; none of it is a 0.4 result.

> Disagreement is a **review flag, not a calibrated correctness score**. Low disagreement does **not** guarantee an
> accurate structure: candidates that are all wrong in the same way look consistent.

```
rnplens diagnose validity  STRUCTURES...
rnplens diagnose run       STRUCTURES... --mode within_engine --engine BOLTZ2 --target ID --out DIR [--request request.json]
                           [--allow-outside-validated-domain]
rnplens diagnose run       STRUCTURES... --mode cross_engine  --target ID --engine LABEL ... --out DIR
rnplens diagnose preflight request.json
rnplens diagnose selftest  [--profile portable|reference]
```

## Validity

Each file is classified as `VALID`, `TECHNICAL_FAILURE` (file absent or empty, does not load, not exactly
one model, a non-finite coordinate) or `STRUCTURAL_FAILURE` (well-formed, but no contacting protein–RNA chain
pair, or no resolved protein or RNA residues); the reason is recorded in `detail`. Neither failure is a low-quality complex, and neither is scored as zero.

## Disagreement

`run` computes the median pairwise value, across the valid candidates, of three decomposition axes: protein
internal Cα RMSD, RNA internal C4′ RMSD and RNA placement C4′ RMSD.

- `within_engine`: several samples of one engine, declared with `--engine` (at least two valid structures are
  needed to compute anything; the statements are validated for 5–50 Boltz-2 candidates).
- `cross_engine`: one designated output per engine, with an `--engine` label for each structure in order;
  at least three engines must supply a valid structure, and several candidates of one engine are refused.

Each value is placed in a frozen benchmark reference distribution (`within_engine`: 65 targets, 58 protein
clusters, one engine; `cross_engine`: 59 targets, four engines) and named as a band (for example `typical` or
`high`). A band says where the value sits in that development reference, not among your structures.

## Two statements, with different evidence

- **Protein side (rc3 statement; its out-of-sample figure is historical).** rc3 cites the preregistered out-of-sample
  result of 2026-09-29: ρ = 0.525 [0.450, 0.593] on 807 targets (456 protein clusters). That value used the
  superseded letter-matching residue correspondence (`SCORE_DECOMP_V1`) for the native protein error and is kept
  only as a historical record. Recomputed with the corrected construct-position correspondence
  (`CONSTRUCT_POSITION_V2`, rule revision R2), the same preregistered analysis gives **ρ = 0.530 [0.455, 0.598] on
  761 targets (435 protein clusters)**: the 807 admitted targets less 46 whose protein residues have no
  construct-position correspondence with the native. Both are smaller than the development estimate. Under the
  corrected values the statement overlaps more with the engine's own confidence than rc3 states:
  - after accounting for protein length, protein pTM and mean pLDDT, the association is −0.080 [−0.184, 0.025]
    (rc3, historical: 0.167 [0.069, 0.265]);
  - at a 20% review budget, protein pTM alone recovers more highest-error targets than disagreement (−7.8
    percentage points [−14.1, −2.9]; rc3, historical: an advantage over pTM that did not resolve);
  - the median protein error of the very-high disagreement band exceeds that of the low band by 1.42 Å
    [1.22, 1.69] (rc3 validation record, historical: 9.76 Å).

  These corrected values are research evidence, not a re-qualification: Diagnose remains BLOCKED in 0.4, and the
  frozen rc3 component and its bundled example output still print the historical 0.525 / 807 text. Read any
  disagreement value alongside the engine's confidence.
- **RNA side.** Rests on its development cohort only and awaits prospective validation. In `within_engine` mode
  it cannot separate RNA shape from RNA placement.

Diagnose refuses three statements and records the refusal in every report: attribution of error to RNA
placement, any probability of correctness, and a best-engine recommendation. The placement disagreement is
reported under `measured_but_not_attributed`.

## Preflight

`preflight` validates a prediction request before you run an engine: allowed entity types and ions, standard
alphabets, both polymers present, and an explicit declaration of MSA/template use for every protein chain.

## Outputs

`report.json` (`validity`, `disagreement`, `diagnosis` with `statements`, `refused_statements` and
`measured_but_not_attributed`, `limits`, `sampling_budget_note`, `preflight`) and a self-contained `report.html`.
A directory that already holds a report is refused.

The preregistered out-of-sample evaluation of the protein-side statement, its protocol and results are in
[validation/](validation/).

## Validated applicability (0.2.0rc3)

Every run is checked against the conditions under which its statements were validated: the declared engine(s),
the number of valid structures and the chain composition of each file (one protein chain and one RNA chain). The
conditions are listed [below](#when-is-a-diagnose-statement-validated-020rc3).
Outside them Diagnose refuses and lists the reasons. With `--allow-outside-validated-domain` it computes the values
anyway; `report.json` then records `applicability.status = "outside_validated_domain"` with the reasons and
`outside_domain_accepted_by_user = true`, and the HTML page opens with an "Outside the validated domain" notice.
The check changes no computed value.

> The sections below were moved here from the analysis guide. They describe the 0.2.0rc3 tool. The out-of-sample
> figures they quote (ρ 0.525 on 807 targets) are historical; the corrected values are given in
> [Two statements, with different evidence](#two-statements-with-different-evidence).

## Values in Diagnose reports (0.2.0rc3)

| value | tool | reference needed | unit and range | better is | read it as |
|---|---|---|---|---|---|
| validity class | Diagnose | no | `VALID` / `TECHNICAL_FAILURE` / `STRUCTURAL_FAILURE` | — | whether a file is a usable protein–RNA complex |
| protein, RNA disagreement | Diagnose | no | Å, ≥ 0 | — | median pairwise RMSD among the supplied structures for that component |
| band and percentile | Diagnose | no | low / typical / high / very high | — | where the disagreement sits in the frozen development reference, not among your structures; band rules below |
| placement disagreement | Diagnose | no | Å | — | measured and reported, deliberately **not** interpreted (attribution was tested and did not hold) |

## When is a Diagnose statement validated? (0.2.0rc3)

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

## How Diagnose bands are assigned (0.2.0rc3)

Each disagreement value is placed in the frozen development reference distribution of the same mode and axis (65
targets within engine, 59 across engines). With q1, median and q3 the quartiles of that reference:

| band | rule |
|---|---|
| low | value ≤ q1 |
| typical | q1 < value ≤ median |
| high | median < value ≤ q3 |
| very high | value > q3 |

So a value just above the reference median is already "high" (in the bundled example, 0.89 Å against a median of
0.853 Å, at the 52nd percentile). The bands are coarse positions in the reference, not thresholds of concern; the
exact percentile is reported with every statement, and the quartiles and median are in `report.json`.

## Terms in Diagnose reports (0.2.0rc3)

| term | meaning |
|---|---|
| ρ (rho) | Spearman correlation, across targets (weighted equally per protein cluster), between the disagreement on an axis and the actual error on the same axis |
| `margin_over_off_diagonals` | how much larger that correlation is than the correlations of the same disagreement with the two other error axes; positive means the statement is specific to its own component |
| `component_specific` | whether that specificity held under the frozen criterion; when false, the statement names what it cannot be separated from |
| out-of-sample ρ | the same correlation on targets not used in development (within engine: 0.525, against 0.869 in development) |
| "transport shrinkage" | the drop from the development to the out-of-sample correlation (0.869 − 0.525 = 0.344); "plan with 0.5" means expect the out-of-sample strength |
| `cohortP_disagreement.tsv`, `cohortE_disagreement.tsv` | the frozen reference distributions (within engine, cross engine) shipped with RNPLens |
| percentile ordinals | statement texts print ordinals mechanically ("52th"); the text is frozen with the regression references and is kept unchanged |

Engine labels: Diagnose records any `--engine` text; for the validated domain `BOLTZ2`, `CHAI1`, `RF3` and `RF2NA` are
recognised, ignoring case, spaces, `-` and `_` (so `Boltz-2` counts as `BOLTZ2`).

In 0.2.0rc3, exit status 1 meant that Diagnose refused the run (outside the validated domain, too few valid
structures, an existing report). In RNPLens 0.4 every Diagnose command exits with 5 (`DIAGNOSE_BLOCKED`).

## Reference: 0.2.0rc3 command examples (refused in 0.4.0)

Diagnose is blocked in the public 0.4 interface until it is re-qualified ([diagnose.md](diagnose.md)). The commands
below refuse with `DIAGNOSE_BLOCKED` and exit code 5, and write nothing. What follows them describes the rc3 tool,
for reference only.

```bash
rnplens diagnose validity examples/reference_free/diagnose_7K9D/*.pdb > OUT/B2_diagnose_validity.json   # 0.4: exit 5; the shell redirect leaves an empty file
rnplens diagnose run examples/reference_free/diagnose_7K9D/*.pdb --mode within_engine --engine BOLTZ2 --target 7K9D --out OUT/B2_diagnose_7K9D
```

`validity` classifies each file as `VALID`, `TECHNICAL_FAILURE` or `STRUCTURAL_FAILURE` (here 5 of 5 `VALID`).
`run` writes `report.json` and `report.html` with the protein-side and RNA-side disagreement, where each sits in the
frozen benchmark reference, the statements it refuses to make, and its limits (see [diagnose.md](diagnose.md)).

For the cross-engine mode give one structure per engine and an `--engine` label for each, in order:

```bash
rnplens diagnose run boltz.pdb chai.cif rf3.cif rf2na.pdb --mode cross_engine --target MYTARGET \
    --engine BOLTZ2 --engine CHAI1 --engine RF3 --engine RF2NA --out OUT/cross
```
