"""Results section of demonstration 2, built from its logs and records only: python interactive_summary.py OUT_MD"""
import glob
import json
import os
import sys


def log(name, n=40):
    p = "logs/%s.log" % name
    if not os.path.exists(p):
        return "(missing: %s)" % p
    L = open(p, encoding="utf-8", errors="replace").read().splitlines()
    return "\n".join(L[:n]) + ("\n... (%d more lines in %s)" % (len(L) - n, p) if len(L) > n else "")


def block(title, name, n=40):
    return "**%s** (`logs/%s.log`)\n\n```\n%s\n```\n" % (title, name, log(name, n))


def main(out):
    md = json.load(open("managed_dirs.json"))
    A = md["analysis"]
    rr = json.load(open("region_rule.json"))["region"]
    rdir = "region_%d-%d" % (rr["start"], rr["end"])
    R = json.load(open(os.path.join(A, rdir, "region.json")))["summary"]
    S = []
    S.append("## Results of this run (excerpts of the logs and records of this package)\n")
    S.append(block("1. First update: the typed clarification request", "01_update_init", 12))
    S.append(block("2. The request as listed", "02_clarify_list", 20))
    S.append(block("3. The researcher's answer, recorded, and resumption", "04_clarify_answer", 12))
    S.append(block("4. A contradicting answer to the same question is refused", "05_clarify_contradiction", 6))
    S.append(block("5. No change: reused, nothing asked again", "07b_update_no_change", 8))
    S.append("**6. Region RNA %d-%d** (`%s/%s/region.json`): %d contacts in range; %d shared by both runs; found only in "
             "run_A %d, only in run_B %d; present in some runs %d; not determined %d.\n"
             % (rr["start"], rr["end"], A, rdir, R["n_contacts_in_range"]["count"], R["shared_by_all_runs"]["count"],
                R["only_in_run"].get("run_A", {}).get("count", 0), R["only_in_run"].get("run_B", {}).get("count", 0),
                R["present_in_some_runs"]["count"], R["not_determined"]["count"]))
    S.append(block("7. Methods export", "10_export_methods", 14))
    S.append(block("8. One reported value explained", "11_explain_value", 24))
    S.append(block("9. Menu item C with the local follow-up (no model)", "12_menu_C_followup_local", 60))
    sc = json.load(open("followup_scripted.json"))
    S.append("**10. SCRIPTED Codex-path demonstration (no model, no Codex process)** (`followup_scripted.json`, `%s/%s/`)\n" % (A, sc["dir"]))
    for i, p in enumerate(sc["proposals_raw"] or []):
        v = p.get("verdict") or {}
        S.append("- scripted proposal %d: `%s` -> %s%s" % (i + 1, (p.get("proposal") or {}).get("follow_up"),
                 "approved" if v.get("approved") else "refused", "" if v.get("approved") else " (%s: %s)" % (v.get("rule"), v.get("reason"))))
    S.append("- model calls made (all to the scripted stand-in): %s; stop: %s; traceability violations: %s; "
             "stored rationale shown in the answer: %s\n" % (sc["model_calls_made"], sc["stop"], sc["traceability_violations"], sc["rationale_shown_in_answer"]))
    for p in sorted(glob.glob("logs/14_replay_fu_*.log")):
        n = os.path.basename(p)[:-4]
        S.append(block("11. Replay without any language model: %s" % n[10:], n, 8))
    u = json.load(open("update_after_outputs.json"))
    S.append(block("12. Final update with no input change, after outputs were written into the analysis folder", "15_update_after_outputs", 8))
    S.append("Analysis folder before `%s`, after `%s`: %s. %s\n" % (u["analysis_before"], u["analysis_after"],
             "reused" if u["reused"] else "**recomputed**",
             "" if u["reused"] else "This is defect D1 (DEMOS_REPORT.md): the cache entry is matched against the whole folder "
             "tree, so the region, Methods, explain and follow-up outputs written into the analysis folder invalidate it. "
             "The result is the same (same key); the earlier outputs stay in the earlier version's folder."))
    S.append(block("13. Version history", "16_versions", 20))
    open(out, "w").write("\n".join(S) + "\n")
    print("results section written: %s" % out)


if __name__ == "__main__":
    main(sys.argv[1])
