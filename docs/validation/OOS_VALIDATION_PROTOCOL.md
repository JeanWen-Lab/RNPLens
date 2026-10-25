# Frozen protocol: out-of-sample validation of the two licensed diagnostic statements (2026-09-29)

**Frozen before any native error was computed on this cohort, and before the analysis script was run.**
No prediction, docking, candidate generation, training or target reselection: every coordinate read was
already on disk. `BUILD_ID` unchanged at `21734060bd4d6920`.

## 0. What this is, and what it is not

This is an **out-of-sample generalisation test with procedural blinding**. It is **not** the post-cutoff
prospective campaign. Two different blindness requirements were separated deliberately:

| requirement | what it buys | satisfied here |
|---|---|---|
| analyst blinding: the native is not read until the reports are sealed | the diagnostic cannot be tuned to the answer | **yes**, by construction below |
| engine novelty: the target post-dates every engine's training cutoff | the result represents a user's genuinely new case | **no** -- these structures may be in engine training data |

So a pass here establishes that the two statements generalise to targets the diagnostic has never seen. It
does **not** establish that they hold on post-cutoff targets, and the manuscript wording must say so.

## 1. The sealed external cohort must not be used, and is not used

`external_cohort_protocol_v3.json` reserves `EXT_CONFIRM_V1` (97 clusters) for **"ONE sealed external
confirmatory evaluation"**, and its `sealed_until_model_freeze` list covers exactly the quantities this
validation needs -- baseline DockQ, target difficulty, class-specific model performance. Spending it here
would break that seal and consume the only independent evidence reserved for another experiment, which the
protocol's own reasoning about `EXT_PILOT` explicitly warns against. It is therefore **excluded**. Only the
`permitted_now` operations on that cohort remain available, and none is used below.

The post-cutoff prospective campaign, when authorised, should acquire an `EXT_FUTURE`-style cohort of
clusters deposited after the v3 freeze, disjoint from the sealed 97, under that protocol's stated rules.

## 2. Cohort, frozen before anything was run

**Claim 1, within-engine.** Every target in `outputs/rnp/fullrun/boltz_out` carrying at least two stored
candidates, whose native is present and which appears in the split table, **excluding the union of the two
diagnostic development cohorts** (65 within-engine + 59 cross-engine = 122 distinct targets):

| | |
|---|---|
| targets | **825** |
| protein clusters | **466** |
| candidates per target | 5 for all 825 |
| split membership | 704 train, 121 test |

Five candidates is the depth at which the within-engine signal was shown to be unchanged
(+0.813 [+0.680, +0.893] against +0.869 at fifty), so the cohort is usable at its stored depth and no
deeper sampling is needed or permitted.

**Claim 2, cross-engine.** Only **13** targets outside the development 59 carry three or more engines with a
native present. That cannot support a confirmatory test. Claim 2 is therefore **descriptive only** here, is
declared so now rather than after seeing it, and remains the reason the prospective campaign is needed.

## 3. The two primary endpoints, unchanged from development

**Claim 1.** Target-level Spearman correlation between within-engine **protein** disagreement and native
**protein** error, at the protein-cluster unit (equal-cluster mean of target-level values), 95%
target-bootstrap intervals, 10,000 resamples, seed 20260929.

**Claim 2.** The same for cross-engine RNA-conformation disagreement against RNA-internal RMSD, reported
descriptively on 13 targets with no confirmatory claim attached.

The success bar for Claim 1 is the **same bar development used**, not an easier one: the diagonal
correlation's interval must exclude zero **and** the diagonal must beat both off-diagonal correlations in
its row, paired over the same cluster resample.

**Nothing is recalibrated.** The metric is the shipped metric; the reference distributions are the two
digest-bound tables shipped in the package and are not recomputed on this cohort; the report wording is the
shipped wording. No new protein or RNA metric may be introduced after the natives are exposed.

## 4. One practical secondary per mode, chosen now

**The reference-band contrast.** Difference in median native error between targets whose disagreement falls
in the shipped reference distribution's **top** band and those in its **bottom** band, with a 95% bootstrap
interval on the difference.

The band boundaries are the quartiles of the reference tables already shipped with the package and bound by
sha256, so **no cutoff can be chosen after the fact** -- this is why this secondary was preferred over a
free threshold. The package's own `_band()` assigns them.

**Underpowered rule, declared now.** If either band holds fewer than 5 targets, the secondary is reported as
**underpowered** and not as a failure. The reference distributions were built on the development cohorts, so
the bands need not split this cohort evenly; that shift is a fact to disclose, never a reason to move a
boundary.

## 5. The blinded sequence, and how each step is checkable

1. This protocol is written and its sha256 recorded **before** step 3.
2. `unblind_analysis.py` is written and its sha256 recorded **before** any native error exists. The script
   computes only the associations named in section 3 and 4 and refuses any other pairing.
3. `campaign_run.py` runs the package on the 825 targets. It opens **no native**: the diagnostic reads only
   candidate structures, and the runner has no native path in scope.
4. `seal_reports.py` checksums every report and writes `SEAL.json`, which also records that no native file
   was read, verified by scanning each report for any path under the natives directory.
5. The seal is verified before the natives are exposed.
6. Native error is computed, per target, by the frozen scoring module.
7. `unblind_analysis.py` computes only the preregistered associations.
8. Every target is reported, including diagnostic abstentions and exclusions, with counts.

## 6. Exclusions, declared now

A target whose candidates cannot be parsed, or which yields fewer than two usable structures, is excluded
and counted as a **diagnostic abstention** -- the package refusing rather than guessing -- and abstentions
are reported separately from failures. A target whose native cannot be scored is excluded and counted. No
target is excluded for its result.

## 7. What a pass and a failure each mean

A pass means the protein-side statement generalises to 825 unseen targets under the same metric, the same
reference distribution and the same wording, with no recalibration. It does not make the statement
calibrated, does not extend it to post-cutoff targets, and does not license the statements ruled
unsupported in development: placement attribution, probability of correctness, best-engine recommendation,
RNA shape versus placement within engine, and protein specificity across engines. Those stay refused in
code throughout.

A failure would mean the development result did not generalise, and the prospective campaign should not be
run on the strength of it.
