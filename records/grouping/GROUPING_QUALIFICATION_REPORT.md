# Grouping (Function 6): descriptive qualification on development pools A and B

> **Integrator's notice (16 Oct 2026, added after the report was written; no number below was changed).**
>
> **What "pool B" means in this report.** "Pool B" denotes the **pool B target list** (216 targets) grouped from the
> current full-run Boltz-2 files `PCfold3D-RNP/outputs/rnp/fullrun/boltz_out/boltz_results_<T>/` (5 samples per
> target). These are **not the structures of the Rank study's pool B corpus**:
> - only 16 of 1,080 contact sets match `RNPLens-Rank/derived/poolB_contacts.json`;
> - every `rank_corpus.tsv` row fails the iptm join.
>
> The contracts document pointed the track at this folder. That was the integrator's error. The pool-B rows are
> therefore reference-free descriptive properties of those full-run predictions for the pool B targets, and the
> pool B retrospective was correctly not computed. The true source of the Rank pool B corpus is unidentified.
>
> **Display change after the freeze.** After the code freeze, one display-only change was made to the difference
> map: fractions are printed unreduced (for example 0/26 rather than 0/1). It is recorded in
> `POST_FREEZE_DISPLAY_FIX.md`. No qualification number depends on it.


**Label: exploratory, development-pool, descriptive.** No selection, ranking or accuracy-improvement claim is made
or implied, and no manuscript claim is proposed from these numbers. Spec B v2 section 5 with Amendments 1–4
(`records/grouping/`). Code commit of the reference-free run: `5f1156f8938f197be6cf33329eb1ebdf7975cf3e`; freeze record `CODE_FREEZE.md` committed
before any label file was opened; Amendment 4 (label-file column names, join check) followed the first, refused
run of the retrospective script for pool B. Every number below is read from the JSON outputs named in each section.

## 1. Inputs and engine designation (`summary_pool{A,B}.json`)
| | pool A | pool B |
|---|---|---|
| targets listed / completed | 64 / 64 | 216 / 216 |
| structures / Report-eligible | 3200 / 3200 | 1080 / 1080 |
| eligible structures with no interface contact | 0 | 0 |
| ineligible states | none | none |
| targets where model_0 has the highest confidence_score | 64 | 216 |
| targets whose model order is non-increasing in confidence_score | 64 | 216 |

Designation rule: the engine's `model_0`. Boltz-2 writes models in descending `confidence_score`, which the
counts above confirm for every target, so `model_0` is also the structure `rnplens import` designates. Hence the
baselines "top-m by confidence" and "designated plus next m − 1" coincide on these pools (Amendment 1, A1.9).

## 2. Reference-free properties per threshold
Per-target values summarised as median (mean; min–max) over targets. Groups are level-2 (register) groups,
including a no-interface group where present (Amendments 1 and 3).

**Pool A (50 samples per target)**

| t | groups per target | surface groups per target | singleton fraction of groups | singleton fraction of structures | reduction factor | mean R to representative | targets with one group |
|---|---|---|---|---|---|---|---|
| 0.3 | 2.00 (8.81; 1.00–50.00) | 1.00 (1.47; 1.00–6.00) | 0.000 (0.226; 0.000–1.000) | 0.000 (0.118; 0.000–1.000) | 25.00 (28.35; 1.00–50.00) | 0.764 (0.706; 0.332–0.972) (n=63) | 31 |
| 0.5 | 4.50 (13.92; 1.00–50.00) | 1.50 (4.19; 1.00–45.00) | 0.225 (0.346; 0.000–1.000) | 0.020 (0.214; 0.000–1.000) | 11.25 (23.78; 1.00–50.00) | 0.804 (0.769; 0.548–0.972) (n=60) | 26 |
| 0.7 | 11.00 (21.19; 1.00–50.00) | 4.50 (12.98; 1.00–50.00) | 0.500 (0.462; 0.000–1.000) | 0.130 (0.373; 0.000–1.000) | 5.24 (21.72; 1.00–50.00) | 0.834 (0.838; 0.701–0.972) (n=53) | 25 |

Group-size histogram (number of groups of each size, all targets):
- t = 0.3: 1: 376, 2: 59, 3: 26, 4: 10, 5: 4, 6: 7, 7: 7, 8: 2, 9: 2, 10: 3, 11: 3, 12: 2, 13: 5, 14: 2, 15: 3, 17: 2, 18: 1, 19: 1, 20: 1, 23: 1, 24: 2, 25: 2, 28: 2, 30: 2, 33: 1, 38: 1, 39: 1, 43: 1, 45: 1, 47: 2, 48: 1, 50: 31
- t = 0.5: 1: 685, 2: 74, 3: 31, 4: 15, 5: 8, 6: 11, 7: 6, 8: 4, 9: 1, 10: 2, 11: 4, 12: 2, 13: 5, 15: 1, 19: 2, 23: 1, 26: 1, 27: 1, 28: 1, 30: 1, 33: 1, 39: 2, 43: 1, 44: 1, 46: 2, 47: 1, 48: 1, 50: 26
- t = 0.7: 1: 1193, 2: 77, 3: 26, 4: 7, 5: 4, 6: 4, 7: 5, 8: 1, 9: 2, 11: 1, 15: 1, 18: 1, 25: 1, 27: 1, 30: 1, 39: 1, 43: 1, 44: 1, 46: 1, 47: 2, 50: 25

**Pool B (5 poses per target)**

| t | groups per target | surface groups per target | singleton fraction of groups | singleton fraction of structures | reduction factor | mean R to representative | targets with one group |
|---|---|---|---|---|---|---|---|
| 0.3 | 1.00 (1.67; 1.00–5.00) | 1.00 (1.07; 1.00–3.00) | 0.000 (0.171; 0.000–1.000) | 0.000 (0.111; 0.000–1.000) | 5.00 (3.89; 1.00–5.00) | 0.709 (0.710; 0.312–1.000) (n=211) | 137 |
| 0.5 | 2.00 (2.15; 1.00–5.00) | 1.00 (1.38; 1.00–5.00) | 0.000 (0.302; 0.000–1.000) | 0.000 (0.217; 0.000–1.000) | 2.50 (3.27; 1.00–5.00) | 0.769 (0.761; 0.500–1.000) (n=195) | 99 |
| 0.7 | 3.00 (3.01; 1.00–5.00) | 2.00 (2.14; 1.00–5.00) | 0.667 (0.527; 0.000–1.000) | 0.400 (0.451; 0.000–1.000) | 1.67 (2.55; 1.00–5.00) | 0.842 (0.841; 0.700–1.000) (n=148) | 67 |

Group-size histogram (number of groups of each size, all targets):
- t = 0.3: 1: 120, 2: 56, 3: 25, 4: 22, 5: 137
- t = 0.5: 1: 234, 2: 73, 3: 27, 4: 31, 5: 99
- t = 0.7: 1: 487, 2: 54, 3: 18, 4: 24, 5: 67

## 3. Order invariance
- Pool A: 64 targets × 5 permutations (seed 20261016); targets with any difference in the groups, dendrogram or pairwise documents: **0**.
- Pool B: 216 targets × 5 permutations (seed 20261016); targets with any difference in the groups, dendrogram or pairwise documents: **0**.

## 4. Subsampling stability (adjusted Rand index, 20 subsets of floor(0.8 n), seed 20261016)
| pool | t | per-target mean ARI | targets with all 20 subsets ARI = 1 |
|---|---|---|---|
| A | 0.3 | 1.000 (0.967; 0.650–1.000) | 39 of 64 |
| A | 0.5 | 1.000 (0.972; 0.798–1.000) | 38 of 64 |
| A | 0.7 | 1.000 (0.957; 0.500–1.000) | 42 of 64 |
| B | 0.3 | 1.000 (0.990; 0.550–1.000) | 207 of 216 |
| B | 0.5 | 1.000 (0.978; 0.550–1.000) | 193 of 216 |
| B | 0.7 | 1.000 (0.968; 0.300–1.000) | 191 of 216 |

Pool B (subsets of 4 of 5 poses) is shown for completeness only; with 5 candidates the index is not meaningful (Spec B v2 §5).

## 5. Fixed inspection budget: diversity, redundancy, coverage of alternatives (pool A)
Shown set: the designated structure, then group representatives at t = 0.5 in display order (never by size).
Baselines are size-matched (m = size of the shown set). Values: mean over targets (median in brackets).
Diversity = mean pairwise 1 − R; redundancy = number of shown pairs with R ≥ 0.5; coverage = fraction of the
target's t = 0.5 groups with a member in the set. This describes what a fixed-size set covers; it is not a recommendation.

**Pool A (64 targets)**

| k | shown size, mean (median) | targets shown < k | set | diversity | redundancy | coverage |
|---|---|---|---|---|---|---|
| 3 | 2.58 (3.0) | 26 | grouping shown set | 0.457 (0.487) | 0.86 (1.0) | 0.554 (0.450) |
|  |  |  | random (expected, 200 draws) | 0.484 (0.487) | 0.86 (1.0) | 0.527 (0.390) |
|  |  |  | top-m by confidence | 0.423 (0.332) | 1.08 (1.0) | 0.503 (0.240) |
|  |  |  | designated + next m−1 by confidence | 0.423 (0.332) | 1.08 (1.0) | 0.503 (0.240) |
| 5 | 3.67 (5.0) | 29 | grouping shown set | 0.502 (0.626) | 0.91 (1.0) | 0.646 (0.900) |
|  |  |  | random (expected, 200 draws) | 0.485 (0.506) | 1.64 (1.0) | 0.563 (0.485) |
|  |  |  | top-m by confidence | 0.423 (0.388) | 2.33 (1.0) | 0.529 (0.308) |
|  |  |  | designated + next m−1 by confidence | 0.423 (0.388) | 2.33 (1.0) | 0.529 (0.308) |
| all | 14.67 (5.5) | – | grouping shown set | 0.538 (0.712) | 1.55 (1.0) | 1.000 (1.000) |
|  |  |  | random (expected, 200 draws) | 0.485 (0.506) | 7.75 (2.8) | 0.796 (0.927) |
|  |  |  | top-m by confidence | 0.436 (0.385) | 11.98 (3.0) | 0.747 (0.934) |
|  |  |  | designated + next m−1 by confidence | 0.436 (0.385) | 11.98 (3.0) | 0.747 (0.934) |

**Pool B, for completeness (5 candidates; computed because the retrospective part needs pool B's shown sets, Amendment 3 A3.4)**

| k | shown size, mean (median) | targets shown < k | set | diversity | redundancy | coverage |
|---|---|---|---|---|---|---|
| 3 | 2.38 (2.0) | 116 | grouping shown set | 0.482 (0.499) | 0.63 (1.0) | 0.923 (1.000) |
|  |  |  | random (expected, 200 draws) | 0.457 (0.442) | 0.80 (0.9) | 0.858 (0.822) |
|  |  |  | top-m by confidence | 0.422 (0.393) | 0.92 (1.0) | 0.824 (1.000) |
|  |  |  | designated + next m−1 by confidence | 0.422 (0.393) | 0.92 (1.0) | 0.824 (1.000) |
| 5 | 2.71 (2.0) | 195 | grouping shown set | 0.491 (0.526) | 0.63 (1.0) | 1.000 (1.000) |
|  |  |  | random (expected, 200 draws) | 0.457 (0.442) | 0.88 (1.0) | 0.918 (1.000) |
|  |  |  | top-m by confidence | 0.428 (0.398) | 1.00 (1.0) | 0.886 (1.000) |
|  |  |  | designated + next m−1 by confidence | 0.428 (0.398) | 1.00 (1.0) | 0.886 (1.000) |
| all | 2.71 (2.0) | – | grouping shown set | 0.491 (0.526) | 0.63 (1.0) | 1.000 (1.000) |
|  |  |  | random (expected, 200 draws) | 0.457 (0.442) | 0.88 (1.0) | 0.918 (1.000) |
|  |  |  | top-m by confidence | 0.428 (0.398) | 1.00 (1.0) | 0.886 (1.000) |
|  |  |  | designated + next m−1 by confidence | 0.428 (0.398) | 1.00 (1.0) | 0.886 (1.000) |

Coverage of the grouping shown set is high partly by construction: it is built from one representative per group.
Its redundancy is not zero because the rule shows the designated structure and, when that structure is not its group's
representative, also the representative of the same group; two members of one register group usually have R >= 0.5.
"All representatives" covers every group by definition (coverage 1).

## 6. Contacts parity with the Rank study (`contacts_parity_pool{A,B}.json`)
- Pool A: 3200 structures compared; identical contact sets 3200 (fraction 1.0000); pooled Jaccard 1.0000; absent from the Rank file 0.
- Pool B: 1080 structures compared; identical contact sets 16 (fraction 0.0148); pooled Jaccard 0.5062; absent from the Rank file 0.

Pool A reproduces the Rank study's structure-level contacts exactly. Pool B does not. Together with the iptm join check
in section 7, this indicates that the Rank study's pool B records (`poolB_contacts.json`, `rank_corpus.tsv`) describe
different Boltz-2 coordinate files than those now at the specified pool B path. Grouping itself always recomputes contacts
from the files through Report's `interface_contacts`, so the reference-free results above are unaffected.

## 7. Retrospective inspection-set accuracy coverage (secondary, reference-based, descriptive)
Computed after the code freeze from the frozen labels, read only. It measures whether a small inspection set retains an
acceptable proposal. It does not test whether RNPLens can tell which one it is, and it is not a selection or accuracy result.

**Pool A** (`coverage_poolA.json`; label columns entry_id, sample_index, dockq; 50 of 64 labelled targets have an acceptable eligible candidate, DockQ ≥ 0.23; eligible structures without a label: 0).

| setting | shown size, mean | set | ≥ 1 acceptable structure | ≥ 1 structure within 0.05 of the highest-DockQ candidate |
|---|---|---|---|---|
| k = 3 | 2.46 | grouping shown set | 0.840 | 0.640 |
|  |  | random (expected) | 0.788 | 0.563 |
|  |  | top-m by confidence | 0.880 | 0.600 |
|  |  | designated + next m−1 | 0.880 | 0.600 |
| k = 5 | 3.30 | grouping shown set | 0.860 | 0.640 |
|  |  | random (expected) | 0.818 | 0.609 |
|  |  | top-m by confidence | 0.940 | 0.700 |
|  |  | designated + next m−1 | 0.940 | 0.700 |
| all representatives | 10.34 | grouping shown set | 0.960 | 0.740 |
|  |  | random (expected) | 0.922 | 0.738 |
|  |  | top-m by confidence | 0.980 | 0.760 |
|  |  | designated + next m−1 | 0.980 | 0.760 |

- Fraction of targets where the representative of the highest-DockQ candidate's t = 0.5 group is within 0.05 DockQ of it: 0.580 (n = 50).
- For context, the designated structure alone is acceptable in 0.820 of these targets (n = 50).
- Pool A's label file has no `iptm` column, so the Amendment 4 join check could not run there (rows checked: 0). Its join rests on the `entry_id`/`sample_index` mapping, supported by the exact contacts parity in section 6.

Comparison per setting, read descriptively (grouping shown set vs random expectation and vs top-m by confidence):
- k = 3: >= 1 acceptable: 0.840, higher than random (0.788) and lower than confidence-ordered (0.880); within 0.05: 0.640, higher than random (0.563) and higher than confidence-ordered (0.600).
- k = 5: >= 1 acceptable: 0.860, higher than random (0.818) and lower than confidence-ordered (0.940); within 0.05: 0.640, higher than random (0.609) and lower than confidence-ordered (0.700).
- all representatives: >= 1 acceptable: 0.960, higher than random (0.922) and lower than confidence-ordered (0.980); within 0.05: 0.740, higher than random (0.738) and lower than confidence-ordered (0.760).

With 50 targets these differences are a few targets each (one target = 0.02). They are not tested, and nothing here
supports using groups or representatives to select a structure.

**Pool B: not computed.** Under Amendment 4, every `rank_corpus.tsv` row for the 216 targets was checked against the
iptm in the corresponding `confidence_<T>_model_<pose>.json`: 1080 rows checked, 1080 mismatched. The labels cannot be joined to the
structure files that were grouped, so no pool B coverage is reported and no label value was used (`coverage_poolB.json`:
0 targets with labels after the join check).

## 8. Interpretation limits
- Development pools only, one engine (Boltz-2), one run per target; repeated samples of one model are not independent evidence.
- The cuts 0.3/0.5/0.7 are Report's sensitivity settings, not calibrated levels; group counts depend strongly on the cut.
- With 5 poses (pool B), grouping mostly restates pairwise agreement.
- RNA conformation difference (Q) is unavailable, so proposals that differ only in RNA-internal conformation are not separated.
- The retrospective coverage is secondary and reference-based. It does not show that RNPLens can identify the acceptable member.
