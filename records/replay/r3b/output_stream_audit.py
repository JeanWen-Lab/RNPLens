"""Audit (integrator decision after the 5b15730 v2 failure): which commands used by the retest step runners write to
BOTH stdout and stderr (the pattern whose combined-log order depended on output length before
rnplens.ordered_output), and does each run through an entry point that installs the ordered output.

usage: python output_stream_audit.py OUT_JSON

Static part: per module, the number of print/write calls to stderr and to stdout (a heuristic count).
Dynamic part: every runner command on the tests/test_determinism.py fixture (7K9D-based; built in a temp dir),
run with separate pipes; bytes on each stream, and whether the entry installed rnplens.ordered_output. On this
fixture `view` refuses (exit 2: a structure with two protein chains needs explicit chains); it still runs through
the entry point, which is what the audit checks.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODULES = {"update/status/versions": "src/rnplens/incremental.py", "clarify": "src/rnplens/clarify.py",
           "region": "src/rnplens/region.py", "export-methods": "src/rnplens/methods_export.py",
           "explain": "src/rnplens/evidence_query.py", "view": "src/rnplens/viewer.py",
           "group/group-diff": "src/rnplens/grouping.py", "relink": "src/rnplens/portability.py",
           "assist (pinned)": "src/rnplens/assist.py", "replay-followup entry": "assistant/rnplens_assistant/__main__.py",
           "follow-up (pinned)": "assistant/rnplens_assistant/followup.py",
           "replay (pinned)": "assistant/rnplens_assistant/replay.py", "cli": "src/rnplens/cli.py",
           "scripted follow-up (frozen v2 harness)": "demos/lib/followup_scripted.py"}
ERR = re.compile(r"file\s*=\s*sys\.stderr|sys\.stderr\.write|out\s*=\s*sys\.stderr")
OUT = re.compile(r"\bprint\((?![^\n]*file\s*=)|sys\.stdout\.write|out\s*=\s*print")


def static():
    rows = {}
    for k, rel in MODULES.items():
        s = open(os.path.join(REPO, rel), encoding="utf-8").read()
        rows[k] = {"file": rel, "stderr_writes": len(ERR.findall(s)), "stdout_writes": len(OUT.findall(s))}
    return rows


def dynamic():
    sys.path.insert(0, os.path.join(REPO, "tests"))
    sp = importlib.util.spec_from_file_location("d1audit", os.path.join(REPO, "tests", "test_determinism.py"))
    D1 = importlib.util.module_from_spec(sp); sp.loader.exec_module(D1)
    from rnplens import state as S
    base = tempfile.mkdtemp(prefix="rnpaudit_")
    root = os.path.join(base, "case")
    D1._case(root)
    st = S.Project(os.path.join(root, "project")).head()["analyses"]["main"]
    imp, an = os.path.join("project", st["import_dir"]), os.path.join("project", st["dir"])
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    probe = ("import runpy, sys, atexit\nfrom rnplens import ordered_output\n"
             "atexit.register(lambda: open(%r, 'a').write(str(ordered_output.installed()) + chr(10)))\n"
             "sys.argv = sys.argv[1:]\nrunpy.run_module(sys.argv[0], run_name='__main__')\n")
    fu = None
    cmds = [("update", ["rnplens", "update", "project"]),
            ("clarify --json", ["rnplens", "clarify", "project", "--json"]),
            ("region", ["rnplens", "region", imp, an, "--rna", "14-23"]),
            ("export-methods", ["rnplens", "export-methods", an, "--project", imp]),
            ("explain structures", ["rnplens", "explain", "structures", "--analysis", an, "--project", imp]),
            ("explain evidence", ["rnplens", "explain", "evidence", "--id", "region_14-23/region.json#/contacts/0",
                                  "--analysis", an, "--project", imp]),
            ("explain region_mapping", ["rnplens", "explain", "region_mapping", "--region", "14-23", "--analysis", an,
                                        "--project", imp]),
            ("view", ["rnplens", "view", imp, "--analysis", an, "--rna", "14-23"]),
            ("group", ["rnplens", "group", imp, "--analysis", an]),
            ("assist menu C (local follow-up)", ["rnplens", "assist", "--project", imp, "--analysis", an, "--item", "C",
                                                "--rna", "14-23", "--runs", "run_A,run_B", "--followup", "local",
                                                "--question", "Which contacts in RNA 14-23 are found in only one run?"]),
            ("replay-followup", None),
            ("relink --dry-run", ["rnplens", "relink", "project", "--search", "in", "--dry-run"]),
            ("update --report", "REPORT"),
            ("update --versions", ["rnplens", "update", "project", "--versions"]),
            ("update --status", ["rnplens", "update", "project", "--status"])]
    rows = []
    for name, argv in cmds:
        if argv == "REPORT":                      # first and head state versions, as continue_case_v2.sh c6
            vs = [v["version"] for v in S.Project(os.path.join(root, "project")).versions()]
            argv = ["rnplens", "update", "project", "--report", vs[0], vs[-1]]
        if argv is None:
            fu = os.path.join(root, an, "followup", "fu_0001", "followup_plan.json")
            argv = ["rnplens_assistant", "replay-followup", fu, "--project", imp, "--analysis", an]
        flag = os.path.join(base, "flag.txt")
        if os.path.exists(flag):
            os.remove(flag)
        r = subprocess.run([sys.executable, "-c", probe % flag] + argv, cwd=root, env=env, capture_output=True)
        rows.append({"command": name, "argv": " ".join(argv), "exit": r.returncode, "stdout_bytes": len(r.stdout),
                     "stderr_bytes": len(r.stderr), "both_streams": bool(r.stdout) and bool(r.stderr),
                     "ordered_output_installed": open(flag).read().strip() == "True" if os.path.exists(flag) else None})
    shutil.rmtree(base, ignore_errors=True)
    return rows


def main(out):
    d = {"static": static(), "dynamic": dynamic()}
    json.dump(d, open(out, "w"), indent=1, sort_keys=True); open(out, "a").write("\n")
    for r in d["dynamic"]:
        print("%-34s exit %-3s out %6d err %6d both %-5s installed %s" % (r["command"], r["exit"], r["stdout_bytes"],
              r["stderr_bytes"], r["both_streams"], r["ordered_output_installed"]))
    for k, v in d["static"].items():
        print("%-40s stderr %3d stdout %3d" % (k, v["stderr_writes"], v["stdout_writes"]))
    return 0 if all(r["ordered_output_installed"] for r in d["dynamic"]) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
