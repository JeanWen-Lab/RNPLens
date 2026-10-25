# Binding-proposal grouping and difference maps (`rnplens group`, `rnplens group-diff`)

> **Note on the development pools.** "Pool A" (Boltz-2, 50 samples per target) and "pool B" (5 samples per target)
> are development collections of the RNPLens authors. They are not distributed with RNPLens. The pool-B results come
> from full-run Boltz-2 predictions for the pool-B target list, not from the corpus of an earlier study, whose files
> could not be matched. The development qualification report is in the source tree, under
> `records/grouping/GROUPING_QUALIFICATION_REPORT.md`.


**Status: DESCRIPTIVE** (capability `hypothesis_grouping`, menu E; `group_difference`). It implements frozen
Specification B v2 (`docs/dev/specs/SPEC_B_HYPOTHESIS_GROUPING_v2.md`) with Amendments 1–4 (`records/grouping/`).

## What it does, and what it does not do
- **What it does.** It turns many predicted structures of one complex into a few explicitly defined binding
  proposals. Each proposal has a representative, the engine-designated structure is always shown, and a
  difference map lists the contacts that distinguish two proposals.
- **What it does not do.** It does not predict structures. It does not rank groups or representatives, and it
  never orders groups by size. Group size, and recurrence among predictions, are not evidence that a proposal
  matches the real complex. RNPLens Rank (closed 2026-10-14) found that agreement and consensus did not identify
  better candidates.

## Commands
```
rnplens group PROJECT --analysis ANALYSIS     # contacts from ANALYSIS/report (Report's records); writes ANALYSIS/groups/
rnplens group PROJECT --out DIR               # no analysis yet: contacts via Report's own per-output routine; writes DIR/groups/
rnplens group-diff ANALYSIS G H [--threshold 0.5|0.3|0.7]   # writes ANALYSIS/groups/diff_G_H[_t<t>]/
```
Outputs:
- `groups/groups.json`: groups at t = 0.3, 0.5 and 0.7, representatives, designated structures, engine
  composition, P spread, the ineligible listing, provenance and evidence IDs;
- `groups/groups.html` and `groups/groups.tsv`;
- `groups/dendrogram.json`: full merge sequences at both levels;
- `groups/pairwise.json`: R, U and P for every eligible pair;
- `diff_G_H/diff.json`, `diff.tsv`, `diff.html` and `overlay.svg`.

Every file is written atomically. Every text output passes the wording audit and the forbidden-phrase check (the four phrases listed in Spec B v2
section 6); an output that fails is refused, not written.

## Definitions (rc3 Report's frozen code only)
- **Contacts C_s.** Protein × RNA position pairs with heavy atoms < 5.0 Å, in construct numbering, from Report's
  `interface_contacts`, either via `report/contacts_by_output.json` or via Report's `agreement.analyse_output`.
  **Surface S_s** is the set of protein positions in C_s.
- **R** = Jaccard(C_s, C_t) and **U** = Jaccard(S_s, S_t), both by Report's `weighted_jaccard` with unit weights.
  Clustering uses the identical exact fraction, which is checked equal to Report's float for every pair.
- **P** is Report's `rna_pose_difference`: the minimum RNA C4′ RMSD after protein superposition, in Å. It is called
  in Report's own (engine, execution) argument order (Amendment 2). It is descriptive only.
- **Q, RNA conformation difference: unavailable (blocked correspondence route).**
- **No interface.** Structures with an empty C_s form the "no interface" group. They are never clustered.
- **Ineligible.** Structures that Report marks ineligible are listed with their Report state and never grouped.

## Algorithm
1. **Levels.** Level 1 groups interface structures by U. Level 2 groups each level-1 group by R. The same t is used
   at both levels (Amendment 1).
2. **Linkage.** Average linkage (UPGMA) on d = 1 − agreement, in exact `fractions.Fraction` arithmetic. Merging
   continues while the mean agreement between two clusters is ≥ t.
3. **Tie-breaks.** Ties are broken by the canonical key pair, where a structure's canonical key is
   (sha256 of the structure file used, structure id). Results do not depend on input order: the qualification
   checked 5 permutations per target on 280 targets and found 0 differences.
4. **Thresholds.** t = 0.3, 0.5 (primary) and 0.7 are always all reported. No threshold is chosen per target.
5. **Display order.** At each level, groups holding a designated structure come first, then the others by their
   smallest canonical key, never by size. Group numbers follow this order. Every group carries the fixed note:
   "Group size reflects how often the supplied predictions produced this proposal; repeated samples from one model
   are not independent evidence."
6. **Representative.** The representative is the register medoid: the member with the highest mean R to the other
   members, with ties broken by canonical key. A singleton is its own representative. The no-interface group has
   no medoid; its member with the smallest key is shown, labelled as such. A designated structure that is not the
   representative is shown as "engine-designated structure (member of group k)".
7. **Engine weighting.** The engine-weighted size gives each engine's eligible structures a total weight of one.
   For example, 50 samples of engine X in one group and 1 structure of engine Y in another give both groups size 1.

## Difference map
- **Contacts listed.** Contacts frequent in both groups, frequent in group G only, and frequent in group H only.
  "Frequent" means present in at least half of the members in which both positions are resolved: a fraction
  ≥ 1/2, a presentation cut-point.
- **Unresolved positions.** A position with no heavy atom in a member is "not observed", never "no contact". That
  member is left out of the denominator and is listed.
- **Caveat.** Every row carries the fixed caveat: "A contact distinguishing two predicted groups is a candidate
  observation for expert review; it does not establish a biological contact. Mutation effects can reflect RNA
  structural change as well as loss of a contact. No mutation is recommended and no effect is predicted."

## Worked example: 6BJG, pool A (development target, Boltz-2, 50 samples)
The run (on the developers' Linux host) was `rnplens import` (the 50 `6BJG_model_*.pdb` files and the sequences from the Boltz input YAML),
then `rnplens analyse --nproc 8`, then `rnplens group project --analysis analysis`, then
`rnplens group-diff analysis 1 2`. The importer designated s001 (`model_0`, highest Boltz-2 `confidence_score`).
As commands (FASTA files written from the protein and RNA sequences of the Boltz input YAML, one record each):
```
rnplens import boltz_out/boltz_results_6BJG --protein-seq 6BJG_protein.fasta --rna-seq 6BJG_rna.fasta --case-id 6BJG --out project
rnplens analyse project --out analysis --nproc 8
rnplens group project --analysis analysis
rnplens group-diff analysis 1 2
rnplens view project --analysis analysis --representatives 0.5     # optional: offline page of the representatives
```
The run is named after the folder that holds `boltz_results_6BJG` (here `boltz_out`).

| cut | groups | surface groups | group sizes in display order |
|---|---|---|---|
| t = 0.3 | 2 | 1 | 47, 3 |
| t = 0.5 (primary) | 5 | 1 | 26, 19, 2, 1, 2 |
| t = 0.7 | 18 | 5 | 15, 2, 1, 7, 2, 7, 2, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2 |

At t = 0.5, all 50 structures share one protein surface and split into 5 contact registers:

| group | size | engine-weighted size | representative | mean R of members to representative | P spread, Å (min / median / max) |
|---|---|---|---|---|---|
| 1 (holds the designated s001, which is not its medoid) | 26 | 13/25 | s013 | 0.746 | 1.65 / 16.71 / 47.54 |
| 2 | 19 | 19/50 | s033 | 0.718 | 1.65 / 7.93 / 22.48 |
| 3 | 2 | 1/25 | s016 | 0.889 | 1.75 (one pair) |
| 4 | 1 | 1/50 | s039 (singleton) | – | – |
| 5 | 2 | 1/25 | s020 | 0.739 | 1.76 (one pair) |

`group-diff analysis 1 2` gives 14 contacts frequent in both groups, 4 frequent in group 1 only and 4 frequent in
group 2 only; 38 contacts frequent in neither are counted but not listed. Group 1's specific contacts are W39–C18,
E41–U21, N46–U21 and L53–U21. Group 2's are W39–G3, W39–A4, W39–A5 and R43–G3. Every member resolves every
position here (denominators 26 and 19).

How to read this:
- The two large groups contact the same protein surface with the RNA in two different registers. W39 contacts
  C18 in one and G3–A5 in the other.
- Each is a candidate observation for expert review. Neither is supported by being larger.
- The wide P spread inside group 1 (up to 47.5 Å) shows that one contact register can come with very different
  RNA placements of this 21-nt RNA. P is descriptive and does not split groups.

## Interpretation limits
- Groups describe how the supplied predictions distribute over binding proposals. They do not say which proposal,
  if any, matches the real complex. Group size, and recurrence among samples of one model, are not independent
  evidence.
- The cuts 0.3/0.5/0.7 are sensitivity settings inherited from rc3 Report, not calibrated levels. Group counts
  depend strongly on the cut (6BJG: 2, 5 and 18 groups), which is why all three cuts and the dendrogram are shown.
- With few structures (for example 5 poses), grouping mostly restates pairwise agreement.
- Q is unavailable, so proposals that differ only in RNA-internal conformation are separated only as far as P and
  the contact register show.
- The difference map lists candidate observations. It does not establish contacts, recommend mutations or predict
  effects.
- **Development qualification.** `records/grouping/GROUPING_QUALIFICATION_REPORT.md` covers pools A and B. It is
  exploratory, development-pool and descriptive. In a retrospective check on pool A, a fixed inspection set built
  from group representatives did not retain an acceptable structure more often than the same number of structures
  taken by engine confidence: with k = 5, the representatives contained an acceptable structure (DockQ >= 0.23) in
  0.86 of the 50 targets with an acceptable candidate, against 0.94 for confidence order (k = 3: 0.84 against 0.88).
  Grouping is therefore an inspection aid for seeing the alternatives, never an accuracy selector; using it as an
  inspection aid is listed as EXPERIMENTAL in [capabilities.md](capabilities.md).
