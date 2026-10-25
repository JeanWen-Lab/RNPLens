# Specification B v2, Amendment 4 (16 Oct 2026): pool B label-file columns

**Status.** Written after CODE_FREEZE.md (commit 7e031e1) and after the frozen retrospective script ran. The
script completed pool A, and for pool B it stopped without computing anything, as Amendment 3 (A3.6) requires.
At this point no pool B label value had been read into any result; the only pool B information seen is the
header line that the script printed in its refusal message. Pool A's result file was written but had not been
looked at beyond its one-line count ("50 targets with an acceptable candidate of 64 labelled").

- **Measurement (header only).** `rank_corpus.tsv` columns: `entry, pose, dockq, fnat, irms, Lrms, iptm, ptm,
  ligand_iptm, protein_iptm, complex_plddt, complex_iplddt, complex_pde, complex_ipde, pair_iptm_AB, mean_pae,
  ens_disagree, rna_len, prot_len`. The frozen detection sets contain neither `entry` nor `pose`.
- **Change (column names only).** `entry` is added to the target-column names and `pose` to the model-column names.
  Detection stays "unique match or stop".
- **Added join check.** It uses no label, and it guards the new mapping and the old one alike. When the label file
  has an `iptm` column, every row used must have iptm equal (|difference| ≤ 1e-6) to the `iptm` in that pool's
  `confidence_<T>_model_<index>.json`. Otherwise the row is not used and is counted as a join mismatch. This
  confirms that `pose` means the model-file index. Pool A is recomputed with the same check; without a mismatch
  its numbers cannot change.
- **Unchanged.** Every threshold, set definition, baseline, seed and rule. No parameter is chosen from labels.
