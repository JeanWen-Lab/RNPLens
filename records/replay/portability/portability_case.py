"""PORTABILITY_TEST_v1 scenario driver (frozen with records/replay/PORTABILITY_TEST_v1.md). Records, never judges.

usage: python portability_case.py ROOT T R1
  ROOT  retest root; T case id; R1 the case root of a completed base workflow (retest_case_v2.sh)
Writes ROOT/T/portability_run.json (every command: argv, cwd, exit code, stdout/stderr tails; tree snapshots) and
ROOT/T/plogs/<scenario>/<command>.{out,err}. The judgement is check_portability.py.
env: RNPLENS_PY (python importing the RNPLens checkout under test, with PYTHONPATH set by the caller).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

PY = os.environ.get("RNPLENS_PY", sys.executable)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snapshot(d):
    out = {}
    for dp, dn, fn in os.walk(d):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if os.path.isfile(p) and not os.path.islink(p):
                out[os.path.relpath(p, d)] = sha(p)
    return out


def head_dirs(case_root):
    """(import dir, analysis dir) of the head state, relative to the case root."""
    proj = os.path.join(case_root, "project")
    vid = json.load(open(os.path.join(proj, ".rnplens", "HEAD")))["version"]
    st = json.load(open(os.path.join(proj, ".rnplens", "state", vid + ".json")))
    a = st["analyses"]["main"]
    rel = lambda p: os.path.normpath(os.path.join("project", p))
    return rel(a["import_dir"]), rel(a["dir"])


class Driver:
    def __init__(self, root, T, r1):
        self.root, self.T, self.r1 = os.path.abspath(root), T, os.path.abspath(r1)
        self.base = os.path.join(self.root, T)
        self.rec = {"case": T, "r1": self.r1, "scenarios": {}}
        rule = json.load(open(os.path.join(self.r1, "region_rule.json")))["region"]
        self.rna = "%d-%d" % (rule["start"], rule["end"])
        self.imp, self.an = head_dirs(self.r1)
        self.rec.update(rna=self.rna, import_dir=self.imp, analysis_dir=self.an)

    def run(self, scen, name, argv, cwd):
        d = os.path.join(self.base, "plogs", scen)
        os.makedirs(d, exist_ok=True)
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))
        open(os.path.join(d, name + ".out"), "w").write(p.stdout)
        open(os.path.join(d, name + ".err"), "w").write(p.stderr)
        r = {"argv": argv, "cwd": cwd, "exit": p.returncode, "stdout_tail": p.stdout[-3000:], "stderr_tail": p.stderr[-3000:]}
        self.rec["scenarios"].setdefault(scen, {}).setdefault("commands", {})[name] = r
        return r

    def commands(self, scen, case_root, analyse_out):
        rn, ra = [PY, "-m", "rnplens"], [PY, "-m", "rnplens_assistant"]
        imp, an = self.imp, self.an
        S = self.rec["scenarios"].setdefault(scen, {})
        S["case_root"] = case_root
        S["before"] = snapshot(os.path.join(case_root, "project"))
        self.run(scen, "c_update", rn + ["update", "project"], case_root)
        self.run(scen, "c_region", rn + ["region", imp, an, "--rna", self.rna], case_root)
        self.run(scen, "c_view", rn + ["view", imp, "--analysis", an, "--rna", self.rna], case_root)
        self.run(scen, "c_explain", rn + ["explain", "structures", "--analysis", an, "--project", imp], case_root)
        self.run(scen, "c_methods", rn + ["export-methods", an, "--project", imp], case_root)
        self.run(scen, "c_group", rn + ["group", imp, "--analysis", an], case_root)
        for fu in ("fu_0001", "fu_0002"):
            plan = os.path.join(an, "followup", fu, "followup_plan.json")
            self.run(scen, "c_replay_" + fu, ra + ["replay-followup", plan, "--project", imp, "--analysis", an], case_root)
        self.run(scen, "c_analyse", rn + ["analyse", imp, "--out", analyse_out], case_root)
        S["after"] = snapshot(os.path.join(case_root, "project"))

    def go(self):
        cp = os.path.join(self.base, "copies")
        os.makedirs(cp)
        C = {"S1": os.path.join(cp, "case_copy")}
        shutil.copytree(self.r1, C["S1"], symlinks=True)
        for s in ("S2", "S3", "S4", "S5"):
            C[s] = os.path.join(cp, "project_only_" + s)
            os.makedirs(C[s])
            shutil.copytree(os.path.join(self.r1, "project"), os.path.join(C[s], "project"), symlinks=True)
        self.rec["copies"] = C
        man = json.load(open(os.path.join(self.r1, self.imp, "manifest.json")))
        inc = [s for s in man["structures"] if s["verdict"] == "INCLUDED"]
        self.rec["included"] = [{"id": s["id"], "path": s["path"], "used_path": s["used_path"], "derived": bool(s.get("derived")),
                                 "original_sha256": s["original_sha256"], "used_sha256": s["used_sha256"]} for s in inc]
        out = lambda s: os.path.join(self.base, "analyse_out_" + s)
        # S0: the original, in place
        self.commands("S0", self.r1, out("S0"))
        # S3: project-only copy, original present
        self.commands("S3", C["S3"], out("S3"))
        # S4: project-only copy, original present, one required original file's bytes changed (restored afterwards)
        target = inc[0]["path"]
        bk = os.path.join(self.base, "s4_backup.bin")
        shutil.copy2(target, bk)
        with open(target, "ab") as fh:
            fh.write(b"REMARK 999 PORTABILITY TEST: BYTES CHANGED\n")
        self.rec["s4_changed_file"] = {"path": target, "recorded_sha256": inc[0]["original_sha256"], "now_sha256": sha(target)}
        self.commands("S4", C["S4"], out("S4"))
        shutil.copy2(bk, target)
        self.rec["s4_restored"] = sha(target) == inc[0]["original_sha256"]
        # the original made unavailable
        away = self.r1 + ".away"
        os.rename(self.r1, away)
        self.rec["original_moved_to"] = away
        # S1: whole-case copy
        self.commands("S1", C["S1"], out("S1"))
        # S2: project-only copy: refusal, then relink by search in the moved originals, then the commands again
        self.commands("S2", C["S2"], out("S2"))
        self.run("S2_relink", "relink", [PY, "-m", "rnplens", "relink", "project", "--search", os.path.join(away, "in")], C["S2"])
        rj = os.path.join(C["S2"], "project", ".rnplens", "relink.json")
        self.rec["s2_relink_json"] = json.load(open(rj)) if os.path.exists(rj) else None
        self.commands("S2b", C["S2"], out("S2b"))
        # S5: a different file with the same name at the original path (all other originals still away)
        other = next(s for s in inc[1:] if s["original_sha256"] != inc[0]["original_sha256"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(away + other["path"][len(self.r1):], target)
        self.rec["s5_fake"] = {"path": target, "recorded_sha256": inc[0]["original_sha256"], "now_sha256": sha(target),
                               "bytes_from": other["id"]}
        self.commands("S5", C["S5"], out("S5"))
        self.run("S5_relink", "relink", [PY, "-m", "rnplens", "relink", "project", "--search", os.path.join(self.r1, "in")], C["S5"])
        rj = os.path.join(C["S5"], "project", ".rnplens", "relink.json")
        self.rec["s5_relink_json"] = json.load(open(rj)) if os.path.exists(rj) else None
        # clean up: remove the fake original tree (scratch only) and put the original back
        shutil.rmtree(self.r1)
        os.rename(away, self.r1)
        self.rec["original_restored"] = os.path.isdir(self.r1)
        json.dump(self.rec, open(os.path.join(self.base, "portability_run.json"), "w"), indent=1, sort_keys=True)
        return 0


if __name__ == "__main__":
    D = Driver(*sys.argv[1:4])
    try:
        rc = D.go()
    except Exception as ex:              # an infrastructure stop: record it and put the original back
        D.rec["driver_error"] = "%s: %s" % (type(ex).__name__, ex)
        bk = os.path.join(D.base, "s4_backup.bin")
        if "s4_changed_file" in D.rec and "s4_restored" not in D.rec and os.path.exists(bk):
            shutil.copy2(bk, D.rec["s4_changed_file"]["path"])
        away = D.r1 + ".away"
        if os.path.isdir(away):
            if os.path.isdir(D.r1):
                shutil.rmtree(D.r1)
            os.rename(away, D.r1)
        json.dump(D.rec, open(os.path.join(D.base, "portability_run.json"), "w"), indent=1, sort_keys=True, default=str)
        raise
    sys.exit(rc)
