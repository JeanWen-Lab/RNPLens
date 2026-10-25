# Out-of-sample validation of the licensed diagnostic statements (2026-09-29)

> **Historical record (`SCORE_DECOMP_V1` residue correspondence; banner added 2026-10-23, nothing below edited).**
> The native protein-error values in this report were computed with the residue correspondence found defective on
> 2026-10-14: for 317 of the 807 protein rows the residue pairs were incorrect, and 46 rows have no
> construct-position correspondence (geometry correspondence audit of 2026-10-15). This report is kept unchanged.
> The corrected recomputation of the same preregistered analysis (`CONSTRUCT_POSITION_V2`, rule revision R2) gives:
> - ρ 0.530 [0.455, 0.598] on 761 targets / 435 protein clusters (the 807 admitted targets less the 46 without
>   correspondence), instead of 0.525 [0.450, 0.593] on 807 / 456;
> - a very-high-minus-low band difference in median protein error of 1.42 Å [1.22, 1.69], instead of 9.76 Å;
> - a test-partition ρ of 0.642 [0.487, 0.759], instead of 0.586.
>
> This is corrected research evidence, not a re-qualification; Diagnose remains BLOCKED in RNPLens 0.4. The
> "+0.530" in the table below is the development margin over placement error, a different quantity.

Preregistered: `PREREGISTRATION.json`, with the protocol, cohort and **analysis script** digests all frozen
before any native error existed on this cohort. `unblind_analysis.py` (sha256 `7d192542a88f1bd3...`) was
written before the answer was available and refuses any association the protocol did not declare.
`BUILD_ID` unchanged at `21734060bd4d6920`. No prediction, docking, candidate generation, training or target
reselection.

## 1. Headline

**Claim 1 PASSES out of sample, and the effect is much smaller than development said.**

| | development | out of sample |
|---|---|---|
| targets / clusters | 65 / 58 | **807 / 456** |
| protein disagreement vs protein error | +0.869 [+0.765, +0.927] | **+0.525 [+0.450, +0.593]** |
| beats RNA-conformation error by | +0.452 [+0.232, +0.686] | +0.234 [+0.136, +0.332] |
| beats placement error by | +0.530 [+0.307, +0.763] | +0.129 [+0.050, +0.208] |
| verdict on the same frozen bar | PASS | **PASS** |

The specificity replicates: protein disagreement still predicts protein error better than it predicts either
RNA axis, both paired differences excluding zero. But the correlation **shrank by 0.34**, and the two
intervals do not overlap in either direction -- 0.525 sits outside the development interval, and 0.869 sits
outside the out-of-sample interval. The development estimate, on 65 targets, was optimistic.

**This is not a depth artefact.** Development's own pre-registered depth control gave +0.813 [+0.680, +0.893]
from five candidates on the development cohort, and this cohort has five. The difference is the cohort, not
the sampling budget.

## 2. The practical secondary separates decisively

The declared secondary was the reference-band contrast, using the quartile boundaries already shipped with
the package and bound by sha256, so no cutoff could be chosen after the fact:

| band | targets | median protein error |
|---|---|---|
| low | 119 | **0.59 A** |
| very high | 368 | **10.35 A** |
| difference | | **+9.76 A [+7.69, +11.79]** |

A seventeen-fold difference in median protein error between the bands the software assigns, with no
recalibration. For a user this is the more useful form of the result than the correlation: the banding the
report already prints separates targets whose protein is essentially right from targets whose protein is
badly wrong.

**The band distribution shifted, and was not adjusted.** On the development cohort the bands were quartiles
by construction, about a quarter each. Here 368 of 807 targets land in the top band and 119 in the bottom,
so this cohort is markedly more variable than the one the reference was built on. The protocol declared in
advance that such a shift is a fact to disclose and never a reason to move a boundary, and no boundary was
moved.

## 3. Declared secondary: the family-disjoint subset

On the 118 targets that are additionally in the benchmark's own test split (91 clusters), the primary
association is **+0.586 [+0.408, +0.724]** -- consistent with the full cohort and, if anything, slightly
stronger. The result is not carried by targets that share a family with the benchmark's training split.

## 4. Claim 2 could not be tested here, and that was declared before looking

Only **13** targets outside the development 59 carry three or more engines with a native present. The
protocol declared Claim 2 descriptive-only on this cohort before any value was computed, and no
cross-engine number is reported from it. **The cross-engine RNA statement remains validated only on its
development cohort.** It is the reason the prospective campaign is still needed, and it is now the campaign's
primary purpose rather than one of two.

## 5. The blinded sequence, and what is checkable about it

| step | what happened |
|---|---|
| protocol frozen | sha256 recorded before the diagnostic ran |
| analysis script frozen | sha256 recorded before any native error existed |
| cohort frozen | 825 ordered ids, sha256 `1ede4f8ff6dc08c4...` |
| diagnostic run | 825 reports, **0 abstentions**; the runner verified at run time that no candidate path lies under the natives directory |
| sealed | 825 reports / 1,650 files checksummed into `SEAL.json`, which also confirmed no report references the natives directory |
| seal exercised | refuses to be rewritten; detects a one-byte edit and names the file; passes again once restored |
| unblinded | seal verified first -- the script refuses to run otherwise -- then natives read for the first time on this cohort |

Exclusions, all declared in advance and none outcome-based: **0** diagnostic abstentions; **18** targets
excluded because the native could not be scored (`native_no_contacting_pair`, `rna_pairs_lt_3`), leaving
807 of 825.

## 6. What this changes

**Power the prospective campaign on 0.5, not 0.87.** Using the development estimate would under-power the
campaign by a wide margin. The out-of-sample interval [+0.450, +0.593] is the honest input.

**Prefer the band contrast as the reported practical result.** It is large, it uses frozen boundaries, and
it survived a cohort whose disagreement distribution is visibly different from the reference.

**Report the shrinkage in the manuscript.** A development-to-out-of-sample drop from 0.87 to 0.52, on a
pre-registered criterion with the metric and reference untouched, is itself evidence for the paper's
evaluation-contract argument: an effect measured on 65 targets and re-measured on 807 moved by 0.34 without
anyone changing a definition.

## 7. What this still does not establish

These structures may lie in the engines' training data, so this is out-of-sample for the **diagnostic** and
not for the **engine**. Nothing here is post-cutoff, nothing is calibrated, disagreement still measures
variance and not bias, and the statements ruled unsupported in development remain refused in code:
placement attribution, probability of correctness, best-engine recommendation, RNA shape versus placement
within engine, and protein specificity across engines.

The sealed external cohort was **not** used. `external_cohort_protocol_v3.json` reserves its 97 clusters for
one sealed confirmatory evaluation and seals exactly the accuracy quantities this validation needs, so
spending it here would have consumed another experiment's only independent evidence. The prospective
campaign should acquire an `EXT_FUTURE`-style cohort of clusters deposited after that protocol's freeze.
