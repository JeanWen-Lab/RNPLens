# RNPBench-Diagnose

Reference-free diagnostics for a predicted protein--RNA complex. Given candidate structures that already
exist, it reports whether each output is a valid, evaluable complex, and **which side of the complex the
structures disagree about**.

It launches no prediction, offers no probability of correctness, and refuses one attribution that was
measured and did not hold.

## Why only two statements

Component disagreement was measured against component error on two cohorts, under a protocol frozen before
any agreement quantity was computed. The two cohorts licensed **different** statements, and neither licensed
a placement attribution:

| statement | licensed by | Spearman rho | beats the other components by |
|---|---|---|---|
| the protein side, within one engine's candidate pool | 65 targets, 58 protein clusters, 50 candidates each | **+0.869** [+0.765, +0.927] | +0.452 and +0.530 |
| **the same, validated out of sample** | **807 targets, 456 protein clusters, disjoint from development** | **+0.525** [+0.450, +0.593] | **+0.234 and +0.129** |
| the RNA's conformation, across three or more engines | 59 targets, 59 protein clusters, four engines | **+0.901** [+0.800, +0.952] | +0.421 and +0.207 |
| *the RNA side, within one engine* | same as row 1 | +0.843 [+0.740, +0.906] | **fails**: +0.080 [-0.012, +0.213] against placement error |
| *the protein side, across engines* | same as row 2 | +0.639 [+0.424, +0.789] | **fails**: +0.155 [-0.084, +0.380] against RNA error |
| *placement attribution* | both cohorts | +0.766 / +0.681 | **fails in both**: -0.008 [-0.092, +0.069] and -0.084 [-0.277, +0.109] |

So the API is shaped by what held. `attribute_placement()` raises and cites both measurements; the placement
disagreement is still computed and still reported, under `measured_but_not_attributed`, because hiding it
would be worse than labelling it. In `within_engine` mode the RNA statement says *the RNA* and explicitly
notes it cannot separate shape from placement. In `cross_engine` mode the protein statement is marked not
component-specific.

Controls behind those numbers: partialling on chain length leaves them largely intact; label shuffling
collapses them to zero; and the within-engine signal is unchanged from **5** candidates.

## Complementary, not independent

This tool reports **complementary triage information**. It is not a replacement for the engine's own
confidence, and on the out-of-sample cohort it does not measurably outperform it. Adjusting the
protein-side association for protein length, protein pTM and mean protein pLDDT takes it from
**0.525** to **0.167** [0.069, 0.265] — still resolved, but most of the unadjusted association is
shared with protein pTM. At a fixed 20% review budget, disagreement recovers **53.7%** of
highest-quintile-error targets against **51.2%** for protein pTM, and that paired difference,
**+2.5 percentage points [-3.2, +7.4]**, does not resolve.

Use it alongside per-chain confidence. Two things it adds that a confidence number does not: an
explicit statement of which component is implicated, and an explicit refusal where the attribution
was measured and did not hold.

## Out-of-sample status, and the asymmetry between the two statements

The **protein-side** statement has been validated on a cohort disjoint from its development cohort, under a
protocol whose analysis script was frozen before any experimental structure was read. It passed the same
criterion, at a **substantially smaller effect**: rho 0.525 [0.450, 0.593] against 0.869 in development,
with a matched five-candidate development control of 0.813 ruling out sampling depth as the explanation. The
practical stratification survived without recalibration: median protein error 0.59 A in the frozen low band
against 10.34 A in the very high band, a difference of 9.76 A [7.69, 11.79], monotone across all four bands.

Plan with **0.5, not 0.87**.

The **RNA-side** statement has *not* been validated out of sample: only 13 out-of-sample targets carry three
or more engines, which was declared descriptive-only in advance. It rests on its development cohort. The
package records this asymmetry per statement under `evidence["out_of_sample"]`, and the report prints it.

A band therefore names a position in the **frozen development reference**, never a quantile of the
structures in front of you. Out of sample that reference did not reproduce the new cohort -- 368 of 807
targets landed in the top band where development had a quarter by construction -- and the boundaries were
deliberately not recalibrated. That the bands stayed discriminative under that shift is what makes the
frozen interpretation usable.

## Install and run

No dependencies beyond the standard library for `preflight` and `report`. `validity` and `disagreement`
need `numpy` and the project's frozen scoring module `score_decomp` on `sys.path`; if it is absent they
**refuse** rather than degrade.

    python -m rnpbench_diagnose.cli preflight request.json

    python -m rnpbench_diagnose.cli validity pred/*.pdb

    python -m rnpbench_diagnose.cli diagnose --mode within_engine --out report_dir \
        --target 1C9S --request request.json pred/1C9S_model_*.pdb

    python -m rnpbench_diagnose.cli diagnose --mode cross_engine --out report_dir --target 24BR \
        --engine BOLTZ2 --engine CHAI1 --engine RF3 --engine RF2NA \
        boltz.pdb chai.cif rf3.cif rf2na.pdb

`diagnose` writes `report.json` and a self-contained `report.html`, and refuses a directory that already
holds a report.

## The four stages

**preflight** validates a request and refuses: an unrecognised key; a name that is not a plain token; an
entity type other than protein chain, RNA sequence or permitted ion; a missing protein or RNA chain; any ion
outside ZN, MG and CL; a sequence outside the standard alphabet; and any protein chain that does not
*declare* its MSA or template use, including declaring that none was used. Each gate mirrors one already
enforced in the project's preparation path; `verify_against_upstream()` checks the restatement still matches
that source when it is reachable.

**validity** classifies each output as `VALID`, `TECHNICAL_FAILURE` or `STRUCTURAL_FAILURE`. That separation
is the point: a file that will not parse, carries more than one model, or has a non-finite coordinate is a
technical failure, while a well-formed file with no contacting protein--RNA pair is a structural failure.
Neither is a low-quality complex and neither should be scored as zero.

**disagreement** computes the median pairwise value of the three benchmark decomposition axes across the
structures supplied, without reading any reference structure. The routine was gated against the frozen
`score_decomp.four_axes` and agreed on all three axes to within 1e-9 on 36 candidates.

**report** emits the JSON record and the HTML page. `render_html` refuses to produce a page without the
limits block.

## What it will not do

`probability of correctness`, `best engine recommendation` and `placement attribution` are listed in
`REFUSED_STATEMENTS` and are not implementable through this API. The report states, in the page itself:
these are statements about disagreement and not about correctness; disagreement measures variance and not
bias, so candidates that are all wrong in the same way look consistent; the correlations were measured on
cohorts used in the benchmark's own development and are not blind validation; and error is not attributed to
placement separately from shape.

## Sampling budget

The report carries the measured budget note rather than a recommendation dressed as a finding: on the
benchmark population the candidate a user receives improves by about 4 percentage points from 1 to 5
samples and about 3.5 more from 5 to 50, while the best candidate present improves by about 21. Deeper
sampling produces better complexes than the engine's own ranking can identify. The diagnostic is available
from 5 candidates.

## Reference distributions

`reference/` ships the two cohort tables with their digests, used only to say where an observed value sits
relative to the benchmark. They are not a calibration set. If they are absent the package refuses to band a
value rather than inventing a threshold. `reference/REFERENCE.json` records what each table is, its
population, and that AF3 was excluded from the cross-engine table because its designated output was not
verifiable.

## Tests

`python3 tests/test_contract.py` -- 16 contract checks. They do not test arithmetic; they test that the
package cannot be made to say something the measurements do not support.
