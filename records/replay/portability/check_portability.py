"""PORTABILITY_TEST_v1 pass rule (frozen with records/replay/PORTABILITY_TEST_v1.md, section 5) for ONE case.

usage: python check_portability.py ROOT/T/portability_run.json OUT_JSON      exit 0 = PASS, 1 = FAIL
Every expectation is a named check; the case PASSES iff every check holds.
"""
import json
import os
import sys

REFUSED, WARN, EXTERNAL, RELINK = "PORTABILITY REFUSED", "PORTABILITY WARNING", "NOT SELF-CONTAINED", "rnplens relink"
REJECTED = "rejected (same name, different SHA-256)"
READERS = ("c_region", "c_view", "c_methods", "c_group")
REPLAYS = ("c_replay_fu_0001", "c_replay_fu_0002")
ALL = ("c_update",) + READERS + ("c_explain",) + REPLAYS + ("c_analyse",)


def text(r):
    return (r or {}).get("stdout_tail", "") + "\n" + (r or {}).get("stderr_tail", "")


def main(run_json, out):
    R = json.load(open(run_json))
    checks = []

    def chk(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    S = R.get("scenarios", {})
    cmd = lambda s, c: (S.get(s, {}).get("commands") or {}).get(c)
    ex = lambda s, c: (cmd(s, c) or {}).get("exit")
    has = lambda s, c, t: t in text(cmd(s, c))
    r1 = R["r1"]
    inc = R["included"]
    base0 = os.path.basename(inc[0]["path"])
    an = R["analysis_dir"]
    region_tsv = os.path.join(an, "region_%s" % R["rna"], "region_contacts.tsv")

    def tree_change(s):
        b, a = S[s]["before"], S[s]["after"]
        return sorted(set(f for f in set(a) | set(b) if a.get(f) != b.get(f)))

    def only_allowed(s, extra=()):
        an_rel = os.path.relpath(os.path.join(S[s]["case_root"], an), os.path.join(S[s]["case_root"], "project"))
        allowed = lambda f: (f.startswith(an_rel + "/explain/") or f == ".rnplens/run/projection_index.json" or f in extra)
        bad = [f for f in tree_change(s) if not allowed(f)]
        return not bad, bad[:20]

    def same_region(s):
        a = os.path.join(r1, region_tsv)
        b = os.path.join(S[s]["case_root"], region_tsv)
        return os.path.isfile(a) and os.path.isfile(b) and open(a, "rb").read() == open(b, "rb").read()

    def resolved_region(s):
        p = os.path.join(S[s]["case_root"], an, "region_%s" % R["rna"], "region.json")
        t = open(p).read() if os.path.isfile(p) else ""
        return bool(t) and "used structure file not found" not in t and "changed since import" not in t

    chk("infra: no driver error, original restored, S4 file restored",
        "driver_error" not in R and R.get("original_restored") and R.get("s4_restored"), R.get("driver_error", ""))
    # S0 control
    for c in ALL:
        chk("S0 %s exit 0, no portability text" % c, ex("S0", c) == 0 and not has("S0", c, "PORTABILITY") and not has("S0", c, EXTERNAL),
            "exit %s" % ex("S0", c))
    for c in REPLAYS:
        chk("S0 %s matches" % c, has("S0", c, '"matches": true'))
    # B1: follow-ups recorded under evidence-hash definition 2
    for fu in ("fu_0001", "fu_0002"):
        for f in ("followup_record.json", "followup_plan.json"):
            p = os.path.join(r1, an, "followup", fu, f)
            v = json.load(open(p)).get("evidence_hash_version") if os.path.isfile(p) else None
            chk("B1 %s/%s evidence_hash_version = rnplens.followup.evidence.2" % (fu, f), v == "rnplens.followup.evidence.2", str(v))
    # S1 whole-case copy, original unavailable
    for c in ("c_update",) + READERS + ("c_explain",):
        chk("S1 %s exit 0, self-contained (no notice)" % c, ex("S1", c) == 0 and not has("S1", c, EXTERNAL) and not has("S1", c, REFUSED),
            "exit %s" % ex("S1", c))
    for c in REPLAYS:
        chk("S1 %s exit 0 and matches" % c, ex("S1", c) == 0 and has("S1", c, '"matches": true'), "exit %s" % ex("S1", c))
    chk("S1 c_analyse refused (exit 6) with relink/update advice", ex("S1", "c_analyse") == 6 and has("S1", "c_analyse", REFUSED),
        "exit %s" % ex("S1", "c_analyse"))
    chk("S1 region_contacts.tsv byte-identical to the original's", same_region("S1"))
    chk("S1 region.json: every structure file resolved", resolved_region("S1"))
    # S2 project-only copy, original unavailable: refusal
    chk("S2 c_update refused (exit 6)", ex("S2", "c_update") == 6 and has("S2", "c_update", REFUSED) and has("S2", "c_update", RELINK),
        "exit %s" % ex("S2", "c_update"))
    for c in READERS + ("c_analyse",):
        chk("S2 %s refused (exit 6), lists %s, says how to relink" % (c, base0),
            ex("S2", c) == 6 and has("S2", c, REFUSED) and has("S2", c, RELINK) and has("S2", c, base0), "exit %s" % ex("S2", c))
    chk("S2 c_explain exit 0 with a portability warning", ex("S2", "c_explain") == 0 and has("S2", "c_explain", WARN))
    for c in REPLAYS:
        chk("S2 %s does not verify (exit != 0)" % c, ex("S2", c) not in (0, None), "exit %s" % ex("S2", c))
    ok, bad = only_allowed("S2")
    chk("S2 nothing written except explain outputs and the projection index", ok, bad)
    # S2 relink by search, then the commands
    rl = cmd("S2_relink", "relink")
    rj = R.get("s2_relink_json") or {}
    chk("S2 relink exit 0 and relink.json records file mappings", (rl or {}).get("exit") == 0 and len(rj.get("files") or []) >= 1,
        "exit %s" % (rl or {}).get("exit"))
    chk("S2b c_update exit 0", ex("S2b", "c_update") == 0, "exit %s" % ex("S2b", "c_update"))
    for c in READERS:
        chk("S2b %s exit 0 and says the project is not self-contained" % c, ex("S2b", c) == 0 and has("S2b", c, EXTERNAL),
            "exit %s" % ex("S2b", c))
    chk("S2b c_explain exit 0", ex("S2b", "c_explain") == 0)
    for c in REPLAYS:
        chk("S2b %s exit 0 and matches" % c, ex("S2b", c) == 0 and has("S2b", c, '"matches": true'), "exit %s" % ex("S2b", c))
    chk("S2b c_analyse refused (exit 6)", ex("S2b", "c_analyse") == 6 and has("S2b", "c_analyse", REFUSED))
    chk("S2b region_contacts.tsv byte-identical to the original's", same_region("S2b"))
    # S3 project-only copy, original present
    chk("S3 c_update refused (exit 6), names the original location", ex("S3", "c_update") == 6 and has("S3", "c_update", REFUSED)
        and has("S3", "c_update", r1) and has("S3", "c_update", RELINK), "exit %s" % ex("S3", "c_update"))
    for c in READERS + ("c_explain",):
        chk("S3 %s exit 0 and says NOT SELF-CONTAINED naming the original location" % c,
            ex("S3", c) == 0 and has("S3", c, EXTERNAL) and has("S3", c, r1), "exit %s" % ex("S3", c))
    for c in REPLAYS:
        chk("S3 %s exit 0 and matches" % c, ex("S3", c) == 0 and has("S3", c, '"matches": true'), "exit %s" % ex("S3", c))
    at_recorded = all(not x["derived"] and x["used_path"] == x["path"] for x in inc)
    if at_recorded:
        chk("S3 c_analyse exit 0 with NOT SELF-CONTAINED (every file at its recorded original path)",
            ex("S3", "c_analyse") == 0 and has("S3", "c_analyse", EXTERNAL), "exit %s" % ex("S3", "c_analyse"))
    else:
        chk("S3 c_analyse refused (exit 6): a derived copy is recorded at the original project's path",
            ex("S3", "c_analyse") == 6 and has("S3", "c_analyse", REFUSED), "exit %s" % ex("S3", "c_analyse"))
    chk("S3 region_contacts.tsv byte-identical to the original's", same_region("S3"))
    # S4 project-only copy, original present but changed
    b4 = os.path.basename(R["s4_changed_file"]["path"])
    chk("S4 the changed file really differs", R["s4_changed_file"]["now_sha256"] != R["s4_changed_file"]["recorded_sha256"])
    chk("S4 c_update refused (exit 6)", ex("S4", "c_update") == 6 and has("S4", "c_update", REFUSED))
    for c in READERS + ("c_analyse",):
        chk("S4 %s refused (exit 6), MISMATCH for %s" % (c, b4),
            ex("S4", c) == 6 and has("S4", c, REFUSED) and has("S4", c, "MISMATCH") and has("S4", c, b4), "exit %s" % ex("S4", c))
    chk("S4 c_explain exit 0 with a portability warning", ex("S4", "c_explain") == 0 and has("S4", "c_explain", WARN))
    for c in REPLAYS:
        chk("S4 %s does not verify (exit != 0)" % c, ex("S4", c) not in (0, None))
    ok, bad = only_allowed("S4")
    chk("S4 nothing written except explain outputs and the projection index", ok, bad)
    # S5 a different file with the same name at the original path
    f5 = R["s5_fake"]
    b5 = os.path.basename(f5["path"])
    chk("S5 the planted file has the same name and a different SHA-256", f5["now_sha256"] != f5["recorded_sha256"])
    for c in READERS + ("c_analyse",):
        chk("S5 %s refused (exit 6), MISMATCH for %s" % (c, b5),
            ex("S5", c) == 6 and has("S5", c, REFUSED) and has("S5", c, "MISMATCH") and has("S5", c, b5), "exit %s" % ex("S5", c))
    for c in REPLAYS:
        chk("S5 %s does not verify (exit != 0)" % c, ex("S5", c) not in (0, None))
    r5 = cmd("S5_relink", "relink")
    chk("S5 relink refuses (exit 6) and reports the same-name file as rejected",
        (r5 or {}).get("exit") == 6 and REJECTED in text(r5) and b5 in text(r5), "exit %s" % (r5 or {}).get("exit"))
    rj5 = R.get("s5_relink_json") or {}
    chk("S5 relink.json does not record the planted file", all(e.get("path") != f5["path"] for e in rj5.get("files") or []))
    ok, bad = only_allowed("S5", extra=(".rnplens/relink.json",))
    chk("S5 nothing written except explain outputs, the projection index and relink.json", ok, bad)
    # measured, not gating: files written or changed in the S1 copy that name the original location
    names = []
    for f in tree_change("S1"):
        p = os.path.join(S["S1"]["case_root"], "project", f)
        if os.path.isfile(p) and (r1.encode() in open(p, "rb").read()):
            names.append(f)
    res = {"case": R["case"], "checks": checks, "n_checks": len(checks), "n_failed": sum(not c["ok"] for c in checks),
           "measured_S1_written_files_naming_original_location": names}
    res["verdict"] = "PASS" if res["n_failed"] == 0 else "FAIL"
    json.dump(res, open(out, "w"), indent=1, sort_keys=True)
    print("%s %s: %d checks, %d failed%s" % (R["case"], res["verdict"], len(checks), res["n_failed"],
                                             "".join("\n  FAIL " + c["check"] + " " + str(c["detail"]) for c in checks if not c["ok"])))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
