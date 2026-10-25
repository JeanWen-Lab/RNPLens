# Prospective campaign: revised scope (2026-09-29)

> **Historical record (banner added 2026-10-23, nothing below edited).** The 0.525 / 807 figures below predate the
> 2026-10-14 residue-correspondence correction (`SCORE_DECOMP_V1`). The corrected out-of-sample value is ρ 0.530
> [0.455, 0.598] on 761 targets / 435 protein clusters (`CONSTRUCT_POSITION_V2`, rule revision R2; the 807 admitted
> targets less 46 without a construct-position protein correspondence). It is research evidence, not a
> re-qualification; Diagnose remains BLOCKED in RNPLens 0.4. The planning guidance "rho about 0.5" is unchanged by it.

The out-of-sample validation changed what the campaign is for. This note supersedes the campaign framing in
`PIPELINE_ASSESSMENT.md` and in `DIAGNOSTIC_RESULTS.md` section 6. It changes no measurement and no
protocol; the frozen `DIAGNOSTIC_PROTOCOL.md` and `OOS_VALIDATION_PROTOCOL.md` stand as written.

## 1. Claim 1 is no longer a reason to spend inference

The within-engine protein statement has been tested on **807 targets across 456 protein clusters** disjoint
from its development cohort, blinded, with the analysis script digest-frozen before any experimental
structure was read. It passed the same criterion at rho 0.525 [0.450, 0.593]. Running new inference to test
it again would buy temporal novelty and nothing else.

## 2. Claim 2 is now the campaign's primary scientific purpose

The cross-engine RNA-conformation statement is the one component-specific diagnostic still resting on its
development cohort alone. Only **13** out-of-sample targets carry three or more engines with a scorable
reference, which was declared descriptive-only before any value was computed, so the retrospective route is
closed for it. It is the reason to run new inference, and the campaign should be designed around it rather
than around a two-claim test.

Consequence for scale: the campaign needs **three or more engines per target**, not one. That is the
dominant cost driver and it should be priced before any target list is fixed.

## 3. Power on a realistic effect

| | |
|---|---|
| do NOT plan with | the development estimate, rho 0.90 |
| plan with | **rho about 0.5** |

The one statement that has been transported to a large independent cohort moved from 0.869 to 0.525 with
identical definitions and a matched-depth control. There is no reason to assume the RNA statement transports
better than the protein one did. Planning at 0.90 would under-power the campaign badly.

## 4. Cohort: not the sealed 97

`external_cohort_protocol_v3.json` reserves `EXT_CONFIRM_V1` for one sealed external confirmatory
evaluation and seals exactly the accuracy quantities a diagnostic validation needs. It must not be consumed
here. Acquire an `EXT_FUTURE`-style cohort of clusters deposited after that protocol's freeze, disjoint from
the sealed 97, under its stated rules: no retraining, no threshold changes, no scorer changes, no
outcome-based exclusion, reported separately.

## 5. What carries over unchanged

The blinded sequence built for the out-of-sample pass transfers directly: freeze the protocol, freeze the
analysis script, run the diagnostic with no reference in scope, seal the reports with checksums, verify the
seal, then compute error. `campaign_run.py`, `seal_reports.py` and `unblind_analysis.py` need only their
cohort and mode changed, and the seal already refuses to be rewritten and detects a one-byte edit.

Two further things carry over as requirements rather than suggestions. The reference distributions must not
be recalibrated on the new cohort, because the band shift observed out of sample is exactly the situation
where recalibration would manufacture agreement. And the campaign should be powered separately to detect
**consistently-wrong candidate pools**, since disagreement measures variance and not bias, and a pool that
is uniformly wrong is the failure mode the diagnostic cannot see.

## 6. What the manuscript now says, and does not say

The protein diagnostic is in Results as validated out of sample, with the shrinkage stated rather than
smoothed, and in Supplementary Figure S15 and Table S25. The RNA diagnostic is not promoted as validated.
No application figure was created: with one statement independently validated and the other not, a headline
figure would be asymmetric. It becomes worth building once Claim 2 has prospective evidence.
