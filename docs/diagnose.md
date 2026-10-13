# RNPLens Diagnose — validity and candidate disagreement

Diagnose looks at candidate structures without any experimental reference. It answers two questions: are these
outputs usable structures at all, and how much do the candidates disagree with each other?

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

- **Protein side.** Validated out of sample (807 targets, 456 protein clusters, ρ = 0.525 [0.450, 0.593]), at a
  smaller effect than its development estimate. It overlaps substantially with the engine's own confidence: after
  accounting for protein length, protein pTM and mean pLDDT, the association falls to 0.167 [0.069, 0.265], and at a
  20% review budget its advantage over pTM alone does not resolve. Read it alongside the engine's confidence.
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
