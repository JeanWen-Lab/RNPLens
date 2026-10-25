# RNPLens Diagnose — validity and candidate disagreement (BLOCKED in 0.4)

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
conditions are in [which_analysis_should_i_use.md](which_analysis_should_i_use.md#when-is-a-diagnose-statement-validated).
Outside them Diagnose refuses and lists the reasons. With `--allow-outside-validated-domain` it computes the values
anyway; `report.json` then records `applicability.status = "outside_validated_domain"` with the reasons and
`outside_domain_accepted_by_user = true`, and the HTML page opens with an "Outside the validated domain" notice.
The check changes no computed value.
