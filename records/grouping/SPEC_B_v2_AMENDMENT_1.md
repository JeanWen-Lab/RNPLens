# Specification B v2, Amendment 1 (16 Oct 2026): interpretation decisions made before implementation

**Status.** Written before any grouping code was written, before any test was run against grouping code, and
before any development pool was grouped. No DockQ or other accuracy record had been opened. Spec B v2
(sha256 `1c304fc154aecf3c5cd03c92ed6b59787213d0414ee9f08bf634de10d25fb38d`) is unchanged; this file records
(a) one requirement that is impossible as stated, with the measurement that shows it, and (b) points where
the specification admits more than one reading, with the reading adopted. No threshold, cut-point or
parameter is added or changed.

## A1.1 Chaining fixture (section 6): impossible as stated with real contact sets
- **Requirement.** "A–B–C with R(A,B) = R(B,C) = 0.6 and R(A,C) = 0".
- **Measurement.** Jaccard distance 1 − J is a metric, so 1 − R(A,C) ≤ (1 − R(A,B)) + (1 − R(B,C)) = 0.8, i.e.
  R(A,C) ≥ 0.2 whenever R(A,B) = R(B,C) = 0.6. An exhaustive search over all non-empty subsets of a
  7-element universe (127 sets, every triple with R(A,B) = R(B,C) = 3/5) found minimum R(A,C) = 1/5, attained by
  A = {0,1,2}, B = {0,1,2,3,4}, C = {0,3,4}. No contact-set triple with R(A,C) = 0 exists.
- **Resolution.** The fixture is tested twice, and both must hold:
  1. on the clustering core with the agreement matrix exactly as specified (3/5, 3/5, 0);
  2. through the full pipeline with realisable contact sets on one protein surface, R = 3/5, 3/5, 1/5.
  Under average linkage at t = 0.5 neither may form one group (mean distance of C to {A,B} = 0.7 resp. 0.6 > 0.5).

## A1.2 Thresholds at the two levels
At each t ∈ {0.3, 0.5, 0.7} the same t is applied at level 1 (U) and level 2 (R). A **group** (sections 2–5)
is a level-2 (contact-register) group inside its level-1 (surface) group. Level-1 counts are reported alongside.

## A1.3 Display order with nested levels and several designated structures
- The manifest marks one designated structure per run (`designated`), so a project with several runs or engines
  has several. The rule "designated group first, then by smallest canonical key, never by size" is applied at
  both levels: level-1 groups containing ≥1 designated structure come first, then the others; within a level-1
  group, level-2 groups containing ≥1 designated structure come first, then the others; ties within each class
  by smallest canonical key of the group. Group numbers k = 1, 2, … follow this nested order.
- Every designated structure is shown, with "engine-designated structure (member of group k)" when it is not
  the representative of its group.

## A1.4 The "no interface" group
- It is a group in its own right (counted in groups per target, coverage and ARI), placed in the display order by
  the same rule as a level-1 group (first if it holds a designated structure, otherwise by smallest canonical key).
- It has no register medoid, because R among empty sets is never evaluated. Its representative is its member with
  the smallest canonical key, labelled as chosen by canonical key. Its members are excluded from the mean R to the
  representative. P spread is still reported (P does not use contacts).

## A1.5 Agreement involving an empty contact set outside clustering
Outside clustering (inspection-set diversity and redundancy), R(s, ∅) is Report's value (0.0 when s is non-empty);
R(∅, ∅) is undefined (Report returns None). Such pairs are excluded from the diversity mean and the redundancy
count, and their number is reported.

## A1.6 Mean R of members to their representative
Per group: mean of R(member, representative) over the non-representative members. Per target: the
member-weighted mean over all non-representative members of interface groups with ≥ 2 members; null if none.

## A1.7 P spread
Over all unordered member pairs of a group: min, median (Report's median convention, numpy median of the sorted
values) and max of P. Pairs for which Report returns None are excluded and counted. Singletons: null.

## A1.8 Difference map
- Contacts considered: the union of the member contacts of the two groups. Each is listed in exactly one of
  "frequent in both", "frequent in A only", "frequent in B only"; a contact frequent in neither is not listed
  (the specification names only these three categories) but the number of such contacts is reported.
- **Resolved.** A position is resolved in a structure when its residue (construct numbering) has at least one
  non-hydrogen atom in at least one copy of that polymer, the atoms Report's `interface_contacts` uses.
- Fraction = (members containing the contact) / (members with both positions resolved), exact; "frequent" means
  fraction ≥ 1/2. With denominator 0 the fraction is null ("not observed") and the contact is not frequent.
- Group labels follow A1.3 at the chosen threshold (default 0.5). Output folder `A/groups/diff_<g>_<h>/` for
  t = 0.5 and `A/groups/diff_<g>_<h>_t<t>/` for t = 0.3 or 0.7.

## A1.9 Inspection set (section 5)
- Shown set: the designated structure, then group representatives at t = 0.5 in display order, skipping any
  structure already shown, until k are shown or representatives run out (the set may be smaller than k; the
  number of such targets is reported). "All representatives" = designated structure plus every representative.
- Baselines are size-matched per target (m = size of the shown set): m random structures (expected value over
  200 draws, seed 20261016), the top-m by engine confidence, and the designated structure plus the next m − 1 by
  confidence. For single-run Boltz pools the designated structure is the top-confidence one, so the last two
  baselines coincide; this is stated, not hidden.
- Engine confidence for the pools: Boltz-2 `confidence_score` from `confidence_<stem>.json` (the score the
  importer uses to designate). Ties by canonical key.

## A1.10 Subsampling ARI
At each threshold, labels are the level-2 groups (the no-interface group is one label). Subset size
floor(0.8 n) of the n eligible structures; 20 subsets drawn from the canonical-key-sorted list with
`numpy.random.default_rng(20261016)` created afresh per target. ARI by the pair-counting formula, with the
convention that two identical partitions give 1.0 (scikit-learn's convention).

## A1.11 Order invariance
Five permutations per target from `numpy.random.default_rng(20261016)` created afresh per target. Compared: the
complete grouping output (membership, levels, representatives, designated placement, display order, dendrograms,
P spread) serialised with sorted keys, excluding only provenance timestamps.

## A1.12 Retrospective accuracy coverage (definitions only; the label files stay closed until CODE_FREEZE.md)
- Highest-DockQ candidate per target: maximum DockQ among eligible structures, ties by canonical key.
- "Within 0.05 DockQ": DockQ(x) ≥ DockQ(top) − 0.05.
- Reported for the grouping: (a) fraction of targets where the shown set holds an acceptable structure (k = 3, 5,
  all representatives); (b) fraction where the representative of the top candidate's t = 0.5 group is within 0.05.
  For a size-matched comparison of (b) with the baselines, the fraction where a set holds a structure within
  0.05 is reported for the grouping shown set and for each baseline.

## A1.13 Contacts without an analysis directory
When a project has no analysis directory (and for the qualification pools), each structure is passed through
rc3 Report's own per-output routine `rnpbench_report.agreement.analyse_output` (Report's eligibility states,
`interface_contacts`, `backbone_tracks`), so eligibility and contacts come from the same frozen code path.
For the pools, the declared construct is the protein and RNA sequence of the target's Boltz input YAML (every
pool A and pool B target has one protein and one RNA entity, checked before this amendment).
