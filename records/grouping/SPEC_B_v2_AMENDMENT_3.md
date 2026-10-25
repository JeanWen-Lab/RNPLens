# Specification B v2, Amendment 3 (16 Oct 2026): operational definitions for the section 5 qualification

**Status.** Written before any development pool was grouped and before any DockQ label file was opened (not even
its header). No parameter of the grouping is added or changed; these fix how the frozen section 5 quantities
are computed where the text admits more than one reading.

## A3.1 Pools and paths
- Pool A: `RNPLens-Rank/derived/poolA_targets.txt` minus 5MSF (64 targets); models
  `jpf/nscale/boltz_out/boltz_results_<T>/predictions/<T>/<T>_model_<i>.pdb`, i = 0..49, paths built from the
  target list and the index range, never by listing a folder. Construct: `jpf/nscale/inputs/<T>.yaml`.
- Pool B: `poolB_targets.txt` minus the 8 sealed-overlap targets (216); models i = 0..4 under
  `fullrun/boltz_out/boltz_results_<T>/predictions/<T>/`; construct `fullrun/inputs_gpu0/<T>.yaml` or
  `fullrun/inputs_gpu1/<T>.yaml`, tested by exact path. The script refuses any target in the contracts' excluded
  list.
- One engine (BOLTZ2), one run per target; structure id = execution = `model_<i>`.

## A3.2 Engine designation for the pools
The designated structure is the engine's `model_0`. Boltz-2 writes models in descending `confidence_score`; the
script reads every `confidence_<T>_model_<i>.json` and reports, per pool, the number of targets in which model_0
has the highest `confidence_score` and in which the model order is non-increasing in it. The designation stays
model_0 regardless (task rule); disagreements, if any, are reported. Engine confidence for the baselines is
`confidence_score`, ties by canonical key.

## A3.3 Reference-free properties
- Structures = Report-eligible structures (no-interface ones included). Groups = level-2 groups including the
  no-interface group (A1.2, A1.4); surface-group counts reported alongside.
- **Singleton fraction** is reported in both readings, labelled: (a) the fraction of a target's groups that have
  one member; (b) the fraction of a target's structures that sit in a one-member group.
- Reduction factor = eligible structures / groups. Mean R to representative per A1.6.
- Aggregates over targets: median, mean, min and max of the per-target values, plus the group-size histogram.

## A3.4 Inspection sets for pool B
Section 5 states diversity/redundancy/coverage for pool A only, but its retrospective part names pool B's label
file, which needs pool B's shown sets. The shown sets and baselines are therefore computed for pool B with the same
rules; pool B's reference-free diversity numbers are reported separately, labelled "for completeness (5 candidates)".

## A3.5 Random draws
Per target and per setting (k = 3, k = 5, all representatives), a fresh `numpy.random.default_rng(20261016)` draws
200 sets of m structures without replacement from the eligible structures in canonical-key order (m = size of the
shown set, A1.9). The retrospective script regenerates the same draws with the same function.

## A3.6 Label files (opened only after records/grouping/CODE_FREEZE.md is committed)
- Column detection (frozen here, before the header is seen): target column = the unique header among
  {target, entry_id, pdb_id, pdb, target_id, T}; model column = the unique header among {model, model_idx,
  model_index, sample, sample_idx, sample_index, model_id, rank}; DockQ column = the unique header equal to `dockq`
  or `DockQ` (case-insensitive). A model value is mapped to its integer index (`model_7`, `7`, `<T>_model_7`).
  If any column is not uniquely identified, or a value cannot be mapped, the script stops without computing, and
  the header (only) is recorded in a further amendment before any change.
- Restricted to targets with an acceptable eligible structure (DockQ ≥ 0.23). Structures without a label are
  reported as missing, never imputed.

## A3.7 Contacts parity with the Rank study
`RNPLens-Rank/derived/pool{A,B}_contacts.json` lists, per target and model index, contacts as `"A<i>|B<j>"`. With
one protein chain A and one RNA chain B numbered from 1 (Boltz output), (i, j) is compared with Report's construct
positions. Agreement is reported as the fraction of structures with identical sets and the pooled Jaccard. It is
a parity check only; it never feeds the grouping.

## A3.8 Execution
karyon, detached processes, `OMP_NUM_THREADS=1` (and MKL/OPENBLAS = 1), at most 32 worker processes, per-target
JSON written atomically, a DONE marker at the end. Order invariance compares all three documents (groups,
dendrogram, pairwise; provenance excluded) over the 5 permutations; any difference is reported as a defect.
