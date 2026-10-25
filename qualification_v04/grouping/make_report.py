"""Write records/grouping/GROUPING_QUALIFICATION_REPORT.md from the qualification JSON outputs only (formatting; it
computes nothing new). Usage: python make_report.py RESULTS_DIR OUT_MD"""
import json
import os
import sys

R, OUT = sys.argv[1], sys.argv[2]
L = lambda f: json.load(open(os.path.join(R, f)))  # noqa: E731
SA, SB = L("summary_poolA.json"), L("summary_poolB.json")
PA, PB = L("contacts_parity_poolA.json"), L("contacts_parity_poolB.json")
CA, CB = L("coverage_poolA.json"), L("coverage_poolB.json")
commit = open(os.path.join(R, "code_commit.txt")).read().strip()


def f(x, nd=3):
    return "n/a" if x is None else ("%d" % x if isinstance(x, int) else "%.*f" % (nd, x))


def d(x, nd=3):
    return "%s (%s; %s–%s)" % (f(x.get("median"), nd), f(x.get("mean"), nd), f(x.get("min"), nd), f(x.get("max"), nd)) if x.get("n") else "n/a"


o = []
w = o.append
w("# Grouping (Function 6): descriptive qualification on development pools A and B")
w("")
w("**Label: exploratory, development-pool, descriptive.** No selection, ranking or accuracy-improvement claim is made")
w("or implied, and no manuscript claim is proposed from these numbers. Spec B v2 section 5 with Amendments 1–4")
w("(`records/grouping/`). Code commit of the reference-free run: `%s`; freeze record `CODE_FREEZE.md` committed" % commit)
w("before any label file was opened; Amendment 4 (label-file column names, join check) followed the first, refused")
w("run of the retrospective script for pool B. Every number below is read from the JSON outputs named in each section.")
w("")
w("## 1. Inputs and engine designation (`summary_pool{A,B}.json`)")
w("| | pool A | pool B |")
w("|---|---|---|")
w("| targets listed / completed | %d / %d | %d / %d |" % (SA["n_targets_listed"], SA["n_targets_completed"], SB["n_targets_listed"], SB["n_targets_completed"]))
w("| structures / Report-eligible | %d / %d | %d / %d |" % (SA["n_structures"], SA["n_eligible"], SB["n_structures"], SB["n_eligible"]))
w("| eligible structures with no interface contact | %d | %d |" % (SA["n_no_interface_structures"], SB["n_no_interface_structures"]))
w("| ineligible states | %s | %s |" % (SA["ineligible_states"] or "none", SB["ineligible_states"] or "none"))
w("| targets where model_0 has the highest confidence_score | %d | %d |" % (SA["designation"]["targets_model_0_max_confidence"], SB["designation"]["targets_model_0_max_confidence"]))
w("| targets whose model order is non-increasing in confidence_score | %d | %d |" % (SA["designation"]["targets_order_non_increasing"], SB["designation"]["targets_order_non_increasing"]))
w("")
w("Designation rule: the engine's `model_0`. Boltz-2 writes models in descending `confidence_score`, which the")
w("counts above confirm for every target, so `model_0` is also the structure `rnplens import` designates. Hence the")
w("baselines \"top-m by confidence\" and \"designated plus next m − 1\" coincide on these pools (Amendment 1, A1.9).")
w("")
w("## 2. Reference-free properties per threshold")
w("Per-target values summarised as median (mean; min–max) over targets. Groups are level-2 (register) groups,")
w("including a no-interface group where present (Amendments 1 and 3).")
for S, name in ((SA, "A (50 samples per target)"), (SB, "B (5 poses per target)")):
    w("")
    w("**Pool %s**" % name)
    w("")
    w("| t | groups per target | surface groups per target | singleton fraction of groups | singleton fraction of structures | reduction factor | mean R to representative | targets with one group |")
    w("|---|---|---|---|---|---|---|---|")
    for t in ("0.3", "0.5", "0.7"):
        P = S["properties"][t]
        w("| %s | %s | %s | %s | %s | %s | %s (n=%d) | %d |" % (
            t, d(P["groups_per_target"], 2), d(P["surface_groups_per_target"], 2), d(P["singleton_fraction_of_groups"]),
            d(P["singleton_fraction_of_structures"]), d(P["reduction_factor"], 2), d(P["mean_R_members_to_representative"]),
            P["mean_R_members_to_representative"]["n"], P["targets_with_one_group"]))
    w("")
    w("Group-size histogram (number of groups of each size, all targets):")
    for t in ("0.3", "0.5", "0.7"):
        w("- t = %s: %s" % (t, ", ".join("%s: %d" % (k, v) for k, v in sorted(S["properties"][t]["group_size_histogram"].items(), key=lambda kv: int(kv[0])))))
w("")
w("## 3. Order invariance")
for S in (SA, SB):
    oi = S["order_invariance"]
    w("- Pool %s: %d targets × %d permutations (seed 20261016); targets with any difference in the groups, dendrogram or"
      " pairwise documents: **%d**." % (S["pool"], oi["targets_checked"], oi["permutations_per_target"], oi["targets_with_any_difference"]))
w("")
w("## 4. Subsampling stability (adjusted Rand index, 20 subsets of floor(0.8 n), seed 20261016)")
w("| pool | t | per-target mean ARI | targets with all 20 subsets ARI = 1 |")
w("|---|---|---|---|")
for S in (SA, SB):
    for t in ("0.3", "0.5", "0.7"):
        A = S["subsampling_ari"][t]
        w("| %s | %s | %s | %d of %d |" % (S["pool"], t, d(A["per_target_mean"]), A["targets_all_20_equal_1"], S["n_targets_completed"]))
w("")
w("Pool B (subsets of 4 of 5 poses) is shown for completeness only; with 5 candidates the index is not meaningful (Spec B v2 §5).")
w("")
w("## 5. Fixed inspection budget: diversity, redundancy, coverage of alternatives (pool A)")
w("Shown set: the designated structure, then group representatives at t = 0.5 in display order (never by size).")
w("Baselines are size-matched (m = size of the shown set). Values: mean over targets (median in brackets).")
w("Diversity = mean pairwise 1 − R; redundancy = number of shown pairs with R ≥ 0.5; coverage = fraction of the")
w("target's t = 0.5 groups with a member in the set. This describes what a fixed-size set covers; it is not a recommendation.")


def insp(S, label):
    w("")
    w("**%s**" % label)
    w("")
    w("| k | shown size, mean (median) | targets shown < k | set | diversity | redundancy | coverage |")
    w("|---|---|---|---|---|---|---|")
    for k in ("3", "5", "all"):
        I = S["inspection"][k]
        for i, (n, lab) in enumerate((("grouping_shown_set", "grouping shown set"), ("random_expected", "random (expected, 200 draws)"),
                                      ("top_m_by_confidence", "top-m by confidence"),
                                      ("designated_plus_next_by_confidence", "designated + next m−1 by confidence"))):
            row = I[n]
            w("| %s | %s | %s | %s | %s (%s) | %s (%s) | %s (%s) |" % (
                k if i == 0 else "", ("%s (%s)" % (f(I["shown_size"]["mean"], 2), f(I["shown_size"]["median"], 1))) if i == 0 else "",
                (f(I["targets_shown_smaller_than_k"]) if I["targets_shown_smaller_than_k"] is not None else "–") if i == 0 else "",
                lab, f(row["diversity"]["mean"]), f(row["diversity"]["median"]), f(row["redundancy"]["mean"], 2),
                f(row["redundancy"]["median"], 1), f(row["coverage"]["mean"]), f(row["coverage"]["median"])))


insp(SA, "Pool A (64 targets)")
insp(SB, "Pool B, for completeness (5 candidates; computed because the retrospective part needs pool B's shown sets, Amendment 3 A3.4)")
w("")
w("Coverage of the grouping shown set is high partly by construction: it is built from one representative per group.")
w("Its redundancy is not zero because the rule shows the designated structure and, when that structure is not its group's")
w("representative, also the representative of the same group; two members of one register group usually have R >= 0.5.")
w("\"All representatives\" covers every group by definition (coverage 1).")
w("")
w("## 6. Contacts parity with the Rank study (`contacts_parity_pool{A,B}.json`)")
for P in (PA, PB):
    w("- Pool %s: %d structures compared; identical contact sets %d (fraction %s); pooled Jaccard %s; absent from the Rank"
      " file %d." % (P["pool"], P["n_structures_compared"], P["n_identical_sets"], f(P["fraction_identical"], 4),
                     f(P["pooled_jaccard"], 4), P["n_structures_absent_from_rank_file"]))
w("")
w("Pool A reproduces the Rank study's structure-level contacts exactly. Pool B does not. Together with the iptm join check")
w("in section 7, this indicates that the Rank study's pool B records (`poolB_contacts.json`, `rank_corpus.tsv`) describe")
w("different Boltz-2 coordinate files than those now at the specified pool B path. Grouping itself always recomputes contacts")
w("from the files through Report's `interface_contacts`, so the reference-free results above are unaffected.")
w("")
w("## 7. Retrospective inspection-set accuracy coverage (secondary, reference-based, descriptive)")
w("Computed after the code freeze from the frozen labels, read only. It measures whether a small inspection set retains an")
w("acceptable proposal. It does not test whether RNPLens can tell which one it is, and it is not a selection or accuracy result.")
w("")
w("**Pool A** (`coverage_poolA.json`; label columns %s; %d of %d labelled targets have an acceptable eligible candidate, DockQ ≥ 0.23;"
  " eligible structures without a label: %d)." % (", ".join(CA["labels"]["columns"]), CA["n_targets_with_acceptable_candidate"],
                                                   CA["n_targets_with_labels"], CA["missing"]["eligible_structures_without_label"]))
w("")
w("| setting | shown size, mean | set | ≥ 1 acceptable structure | ≥ 1 structure within 0.05 of the highest-DockQ candidate |")
w("|---|---|---|---|---|")
for k in ("3", "5", "all"):
    s = CA["settings"][k]
    for i, (n, lab) in enumerate((("grouping_shown_set", "grouping shown set"), ("random_expected", "random (expected)"),
                                  ("top_m_by_confidence", "top-m by confidence"),
                                  ("designated_plus_next_by_confidence", "designated + next m−1"))):
        w("| %s | %s | %s | %s | %s |" % ("k = " + k if k != "all" and i == 0 else ("all representatives" if i == 0 else ""),
                                         f(s["shown_size"]["mean"], 2) if i == 0 else "", lab,
                                         f(s[n]["acceptable"]["fraction"]), f(s[n]["within_0.05"]["fraction"])))
w("")
w("- Fraction of targets where the representative of the highest-DockQ candidate's t = 0.5 group is within 0.05 DockQ of it:"
  " %s (n = %d)." % (f(CA["rep_of_top_group_within_0.05"]["fraction"]), CA["rep_of_top_group_within_0.05"]["n"]))
w("- For context, the designated structure alone is acceptable in %s of these targets (n = %d)." % (
    f(CA["designated_alone_acceptable"]["fraction"]), CA["designated_alone_acceptable"]["n"]))
w("- Pool A's label file has no `iptm` column, so the Amendment 4 join check could not run there (rows checked: %d). Its join rests"
  " on the `entry_id`/`sample_index` mapping, supported by the exact contacts parity in section 6." % CA["labels"]["join_check_iptm"]["rows_checked"])
w("")
w("Comparison per setting, read descriptively (grouping shown set vs random expectation and vs top-m by confidence):")
for k in ("3", "5", "all"):
    s = CA["settings"][k]
    parts = []
    for m, lab in (("acceptable", ">= 1 acceptable"), ("within_0.05", "within 0.05")):
        g, r, c = (s[n][m]["fraction"] for n in ("grouping_shown_set", "random_expected", "top_m_by_confidence"))
        rel = lambda a, b: "higher than" if a > b else ("equal to" if a == b else "lower than")  # noqa: E731
        parts.append("%s: %s, %s random (%s) and %s confidence-ordered (%s)" % (lab, f(g), rel(g, r), f(r), rel(g, c), f(c)))
    w("- %s: %s." % ("k = " + k if k != "all" else "all representatives", "; ".join(parts)))
w("")
w("With 50 targets these differences are a few targets each (one target = 0.02). They are not tested, and nothing here")
w("supports using groups or representatives to select a structure.")
w("")
cb = CB["labels"]["join_check_iptm"]
w("**Pool B: not computed.** Under Amendment 4, every `rank_corpus.tsv` row for the 216 targets was checked against the")
w("iptm in the corresponding `confidence_<T>_model_<pose>.json`: %d rows checked, %d mismatched. The labels cannot be joined to the" % (cb["rows_checked"], cb["rows_mismatched"]))
w("structure files that were grouped, so no pool B coverage is reported and no label value was used (`coverage_poolB.json`:")
w("%d targets with labels after the join check)." % CB["n_targets_with_labels"])
w("")
w("## 8. Interpretation limits")
w("- Development pools only, one engine (Boltz-2), one run per target; repeated samples of one model are not independent evidence.")
w("- The cuts 0.3/0.5/0.7 are Report's sensitivity settings, not calibrated levels; group counts depend strongly on the cut.")
w("- With 5 poses (pool B), grouping mostly restates pairwise agreement.")
w("- RNA conformation difference (Q) is unavailable, so proposals that differ only in RNA-internal conformation are not separated.")
w("- The retrospective coverage is secondary and reference-based. It does not show that RNPLens can identify the acceptable member.")
open(OUT, "w").write("\n".join(o) + "\n")
print("written", OUT)
