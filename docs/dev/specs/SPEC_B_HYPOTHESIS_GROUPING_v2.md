# RNPLens 0.4: Specification B v2, binding-hypothesis grouping and difference maps

**Status.** Frozen on 16 Oct 2026, before any grouping code was written or any pool was grouped. The sha256 of this
file is recorded in `records/SPEC_B_v2_FREEZE.md`.
- **Basis.** Specification B v1 (`RNPLens_dev_0.3/specs/SPEC_B_HYPOTHESIS_GROUPING_v1.md`, 2026-10-14), amended to
  the owner's 16 Oct 2026 authorisation, which approved implementing Specification B with its safeguards.
- **Every change from v1 is marked [v2].** Nothing else differs from v1.

## 0. What this is and is not
- **What it is.** A deterministic way to turn many predicted structures of one complex into a few explicitly defined
  groups, each a distinct binding proposal, with:
  - a representative per group;
  - the engine pick always shown;
  - a map of what distinguishes two groups.
- **What it is not:**
  - **Not a selector.** No group or representative is called best, likely, reliable or correct.
  - **Not ordered by size.** Group size is shown but never used to order or recommend a group. The Rank study (closed
    2026-10-14) showed that agreement and consensus did not identify better candidates.
  - **Not tuned.** Every threshold is one of rc3 Report's three predefined settings (0.3, 0.5, 0.7). They are
    sensitivity settings, not calibrated confidence levels. No accuracy outcome is used to choose anything.

## 1. Definitions (rc3 Report's frozen code paths only)
Each eligible structure *s* has:
- a contact set C_s: protein position × RNA position pairs with heavy atoms < 5.0 Å, in construct numbering, from
  Report's frozen `interface_contacts`;
- a protein surface set S_s: the protein positions present in C_s, as Report defines surface agreement.

The quantities:
- **Register agreement** R(s,t) = Jaccard(C_s, C_t), Report's `weighted_jaccard` with unit weights.
- **Surface agreement** U(s,t) = Jaccard(S_s, S_t), the same function.
- **RNA pose difference** P(s,t): Report's `rna_pose_difference`, the minimum RNA C4′ RMSD after protein
  superposition over copy assignments, in Å. It is descriptive only and never used for grouping.
- **[v2] RNA conformation difference Q: UNAVAILABLE.** v1 used Diagnose's `disagreement.axes_between`, which builds
  residue pairs with `score_decomp.prot_pairs` and `f1_b2a_matrix.align_pairs`. That is the `SequenceMatcher` route
  with the known correspondence defect (stop report 2026-10-14). The 2026-10-15 audit verified these mappings correct
  on its three cohorts, but that is evidence about those data, not a correction of the route. Q is not computed,
  shown or used. The output states "RNA conformation difference: unavailable (blocked correspondence route)".
- **No interface.** Structures with no protein–RNA contact (C_s empty) form their own group, which is always shown.
  They are excluded from the clustering itself, so Jaccard(∅, ∅) is never evaluated.
- **[v2] Ineligible structures.** Structures that Report marks ineligible are listed with their state and are never
  grouped.
- **Parity.** R, U and P values must equal rc3 Report's for the same structure pairs. This is a test.

## 2. Grouping rule
**Levels.**
- **Level 1, binding surface:** groups by U over all interface structures.
- **Level 2, contact register:** groups by R within each level-1 group.
- Report order: protein surface → contact register → descriptive RNA pose spread.

**[v2] Algorithm, fully specified.** Agglomerative clustering with average (UPGMA) linkage on d = 1 − agreement:
1. **Start.** Every structure is a singleton cluster.
2. **Merge.** Repeatedly merge the two clusters with the smallest average pairwise distance, while that distance is
   ≤ 1 − t. Merging therefore continues while the mean agreement between them is ≥ t.
3. **Distances.** Computed in exact rational arithmetic, using `fractions.Fraction` of the integer set sizes, so
   ties are exact.
4. **Ties.** Equal distances are broken by the canonical key of the pair: the lexicographically smaller
   (min canonical key of cluster 1, min canonical key of cluster 2), with the pair itself ordered.
5. **Canonical key** of a structure: (sha256 of the structure file used, structure id). It never depends on input
   order.
6. **Thresholds.** The primary cut is t = 0.5. Groupings at t = 0.3 and t = 0.7 are always reported alongside. No
   threshold is chosen per target.
7. **Dendrogram.** The full merge sequence is exported.

**[v2] Order invariance.** For any permutation of the input structures, group membership, representatives and
display order are identical. Only labels derived from canonical keys appear. Structures with identical file content
have equal contact sets and always fall in the same group.

**No discarding.** Singletons and small groups are kept and listed with the same prominence. Every eligible
structure appears in exactly one group at each threshold.

**Display order.**
- The group containing the engine-designated structure comes first, labelled as such.
- **[v2]** The other groups follow by their smallest canonical key, never by size.
- Every group's size is printed with the fixed note: "Group size reflects how often the supplied predictions
  produced this proposal; repeated samples from one model are not independent evidence."

**Multi-engine input.** Groups may mix engines. For each group the report gives:
- its engine composition;
- an engine-weighted size, in which each engine's eligible structures sum to one.

## 3. Representatives
- **Choice.** The register medoid: the member with the highest mean R to the other members.
  - **[v2]** Ties are broken by canonical key.
  - A singleton is its own representative.
- **Engine pick.** The engine-designated structure is always shown, in whatever group it falls. When it is not the
  medoid, it is shown as "engine-designated structure (member of group k)".
- **Naming.** "representative of group k"; never "best", "top" or "most likely".
- **Spread.** Each group gives the spread of P among its members (min, median, max), descriptively. The Diagnose
  finding that placement disagreement cannot be attributed to error is stated.

## 4. Difference map between two groups
For any two groups A and B, a table and a contact-map overlay listing:
- contacts frequent in both;
- contacts frequent in A only;
- contacts frequent in B only.

"Frequent" means present in at least half of the group's members, a presentation cut-point declared in the output.

For each contact the table gives:
- protein position and residue;
- RNA position and nucleotide;
- the fraction of A and of B containing it;
- **[v2]** for each member, whether both positions are resolved in that structure. A position that is not resolved
  is counted as "not observed", never as "no contact". Fractions use only the members in which both positions are
  resolved, and that denominator is printed;
- the fixed caveat column.

The caveat: "A contact distinguishing two predicted groups is a candidate observation for expert review; it does not
establish a biological contact. Mutation effects can reflect RNA structural change as well as loss of a contact. No
mutation is recommended and no effect is predicted."

**Export.** TSV, plus an HTML panel linked to the local Mol* view.

## 5. Descriptive qualification on development pools (definitions frozen here, before computation)
**Pools.**
- **A:** Boltz-2 with 50 samples, 65 targets minus 5MSF, so **64** targets.
- **B:** the 5-pose corpus, 224 listed targets minus 4KR6, 4PMI, 4RDX, 5FN1, 5HSW, 6DCB, 6NY2 and 6XMF, so
  **216** targets.
- **[v2]** Those exclusions are the overlap with the sealed assistant-evaluation targets.
- The reserved 72-target Rank holdout stays closed, and the pool B source folder is never enumerated.

**Properties (reference-free), at each of 0.3, 0.5 and 0.7:**
- groups per target;
- the group-size distribution;
- the singleton fraction;
- the reduction factor (structures ÷ groups);
- the mean R of members to their representative.

**Order invariance.** Five random permutations per target (seed 20261016). The outputs must be identical; any
difference is a defect.

**Subsampling stability.** Adjusted Rand index between the full-pool grouping, restricted to the subset, and the
grouping of random 80% subsets. 20 subsets per target, seed 20261016, pool A only. Pool B's 5 candidates are too few
for this to be meaningful, so it is reported only for completeness.

**[v2] Representative diversity and redundancy at a fixed inspection budget k ∈ {3, 5}** (pool A only):
- **The shown set:** the engine pick, then group representatives in display order until k structures are shown.
- **Diversity:** the mean pairwise 1 − R within the shown set.
- **Redundancy:** the number of shown pairs with R ≥ 0.5.
- **Coverage of alternatives:** the fraction of the target's groups, at t = 0.5, that have a member in the shown set.
- **Compared with three baselines:**
  - k random structures (expected value over 200 draws, seed 20261016);
  - the top-k by engine confidence;
  - the engine pick plus the next k − 1 by confidence.
- Display order is not by size. This measures what a fixed-size inspection set covers; it is not a recommendation.

**Retrospective inspection-set accuracy coverage (secondary, reference-based, descriptive).**
- Computed only after this specification and the grouping code are frozen, from the frozen labels:
  - pool A: `nscale_sample_dockq.tsv`;
  - pool B: `rank_corpus.tsv`.
- Restricted to targets with an acceptable candidate (DockQ ≥ 0.23) in the pool. It gives:
  - the fraction where at least one shown structure is acceptable, at k = 3 and 5 and at "all representatives";
  - the fraction where the best candidate's group representative is within 0.05 DockQ of the best candidate.
- Compared with the same baselines.
- This measures whether a small inspection set retains an accurate proposal. It does not test whether RNPLens can
  tell which one it is, and it is never reported as selection or as improved accuracy. No parameter is changed
  after seeing it.

**Labelling.** Every result is labelled "exploratory, development-pool, descriptive". No manuscript claim is
proposed from it.

## 6. Acceptance tests
- **Determinism and order invariance** under permuted input, including ties.
- **Constructed fixtures:**
  - three distinct registers on one surface → three level-2 groups in one level-1 group;
  - two surfaces → two level-1 groups;
  - a no-contact structure → the "no interface" group;
  - an engine with 50 samples plus another with 1 → equal engine-weighted sizes;
  - **[v2]** a chaining fixture, A–B–C with R(A,B) = R(B,C) = 0.6 and R(A,C) = 0, which must NOT become one group at
    t = 0.5 under average linkage;
  - **[v2]** unresolved positions counted as not observed in the difference map.
- **Parity:** R, U and P equal rc3 Report's for the same pairs.
- **Wording audit,** plus a check that no output contains "best", "most likely", "correct group" or "confidence of
  the group".

## 7. Risks stated in advance
- **Thresholds.** Thresholds inherited from engine-level grouping may split or merge groups differently than an
  expert would. That is why all three cuts and the dendrogram are shown.
- **Small pools.** With 5 candidates, grouping mostly restates pairwise agreement. Its value is expected mainly for
  pools of 20 or more.
- **Misreading.** Users may read the largest group as the answer. The fixed wording, the display order, the
  engine-pick-first rule and the outside-user test are the mitigations.
- **Blocked axis.** Q is unavailable, so groups that differ only in RNA-internal conformation are not separated
  beyond what P and the contact register show.
