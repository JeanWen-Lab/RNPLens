"""``rnplens analyse``: run the applicable rc3 tools on an imported project and build one summary.

NOTHING NEW IS COMPUTED ABOUT THE STRUCTURES. Report and (with --reference) Evaluate run unchanged, each through
the ``rnplens`` command and into its own subdirectory with its own run record. The summary is then built only from
those output files:
  * Report result.json and contacts_by_output.json (the per-structure contact lists Report itself writes),
  * Evaluate result.json per structure.
Diagnose is BLOCKED in 0.4 (until it is re-qualified): it is never run, the summary records DIAGNOSE_BLOCKED under
steps.diagnose_blocked (steps.diagnose_skipped stays true for existing readers), and asking for it
(``--with-diagnose`` or ``run(..., diagnose=True)``) is refused with exit 5 before anything is written.
The only arithmetic added is counting: how many of an engine's structures list a given contact or position.
Every count states its numerator, denominator and contributing structures, and trace.verify() re-derives every
displayed number from the module files before the summary is accepted.

Contact frequency is an observation about the supplied predictions. It is not a probability that the contact is
real: predictions from one model can agree on the same error.
"""
import datetime
import json
import os
import subprocess
import sys

SUMMARY_SCHEMA = "rnplens-analysis-summary-1"
FIXED_LIMITS = [
    "Contact and position frequencies count how often the supplied predictions contain a feature. They are not "
    "probabilities that the feature exists in the real complex.",
    "Predictions from the same model are not independent evidence; several of them can share the same error.",
    "No part of this summary estimates which structure is closest to the experimental complex, the binding "
    "affinity, or whether the protein and RNA interact at all.",
    "Diagnose is BLOCKED in this version (DIAGNOSE_BLOCKED) until it is re-qualified; no Diagnose statement is part "
    "of this summary.",
]
REPEAT_NOT_COMPUTED = "Pairwise repeat-agreement summary not computed for this candidate configuration."
REFERENCE_LIMIT = ("Section 5 measures each structure against the experimental reference you supplied; nothing else in "
                   "this summary estimates which structure is closest to the experimental complex. No part estimates "
                   "the binding affinity or whether the protein and RNA interact at all.")
GEOMETRY_WITHHELD = ("Evaluate's four-axis geometry values (protein-internal, RNA-internal and RNA placement RMSD) are "
                     "withheld in this development version: their residue correspondence has a known defect (difflib "
                     "autojunk, stop report 2026-10-14) and the corrected construct-position implementation is not yet "
                     "qualified in this toolkit.")


def run_pairs(inc):
    """Engines whose included structures come from exactly two runs, each with an engine-designated structure, and
    which do not already have exactly two structures (Report's own repeat agreement covers that case).
    -> {engine: [designated structure of run 1, designated structure of run 2]}  (6DCB first-use test, finding M4)"""
    out = {}
    for e in sorted({s["engine"] for s in inc}):
        ss = [s for s in inc if s["engine"] == e]
        runs = sorted({s["run"] for s in ss})
        if len(runs) != 2 or len(ss) == 2:
            continue
        des = [next((s for s in ss if s["run"] == r and s.get("designated")), None) for r in runs]
        out[e] = des
    return out


def _rn(args, log):
    """Run one rnplens command; return (exit code, stdout+stderr tail)."""
    cmd = [sys.executable, "-m", "rnplens"] + args
    p = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))
    with open(log, "a", encoding="utf-8") as fh:
        fh.write("$ %s\nexit %d\n%s\n%s\n" % (" ".join(cmd[2:]), p.returncode, p.stdout[-4000:], p.stderr[-4000:]))
    return p.returncode, (p.stdout + p.stderr)[-1500:]


EXIT_FAILED = 1     # documented: 1 = a run failed


def report_failures(steps):
    """The Report runs of this analysis that did not produce a result: the run on every included structure, and the run
    on the engine-designated structures of two runs. Any one of them makes the analysis a failed run (exit 1), so that
    a managed update records the group FAILED and never caches it as complete."""
    out = []
    if steps["report"]["exit"] != 0:
        out.append("Report exited %d" % steps["report"]["exit"])
    out += ["Report on the engine-designated structures of the %s runs exited %s" % (r["engine"], r.get("exit"))
            for r in steps.get("run_repeat", []) if r.get("status") == "FAILED"]
    return out


def run(project, out, reference=None, nproc=1, diagnose=False):
    from .capabilities import DIAGNOSE_BLOCKED_EXIT, DIAGNOSE_BLOCKED_MESSAGE, DIAGNOSE_BLOCKED_STATUS, diagnose_blocked_text
    if diagnose:
        print(diagnose_blocked_text("analyse --with-diagnose"), file=sys.stderr)
        return DIAGNOSE_BLOCKED_EXIT
    if os.path.exists(out):
        print("rnplens analyse: refused: %s exists (nothing is overwritten)" % out, file=sys.stderr)
        return 2
    man = json.load(open(os.path.join(project, "manifest.json"), encoding="utf-8"))
    from . import portability as PT     # Report reads the recorded paths: refuse unless they are the files to use
    PT.check_manifest(project, man, "recorded", "analyse")
    contract_path = os.path.abspath(os.path.join(project, "report_contract.json"))
    inc = [s for s in man["structures"] if s["verdict"] == "INCLUDED"]
    if not inc:
        print("rnplens analyse: refused: the project has no included structure", file=sys.stderr)
        return 2
    os.makedirs(out)
    log = os.path.join(out, "commands.log")
    steps = {}

    # Report: all included structures
    code, tail = _rn(["report", "run", contract_path, "--out", os.path.join(out, "report"), "--nproc", str(nproc)], log)
    steps["report"] = {"exit": code, "dir": "report", "message": None if code == 0 else tail}

    # Report again on the two runs' designated structures: Report's own two-output repeat agreement (no new statistic)
    steps["run_repeat"] = []
    contract = json.load(open(contract_path, encoding="utf-8"))
    for e, des in run_pairs(inc).items():
        if any(d is None for d in des):
            steps["run_repeat"].append({"engine": e, "status": "NOT_COMPUTED", "reason": "the engine-designated "
                                        "structure of each run is needed and is not determinable for every run"})
            continue
        sub = dict(contract, outputs=[o for o in contract["outputs"] if o["engine"] == e and
                                      o["execution"] in (des[0]["execution"], des[1]["execution"])])
        os.makedirs(os.path.join(out, "run_repeat_inputs"), exist_ok=True)
        cp = os.path.join(out, "run_repeat_inputs", "report_contract_%s.json" % e)
        json.dump(sub, open(cp, "x"), indent=1)
        d = os.path.join(out, "report_runs_%s" % e)
        code, tail = _rn(["report", "run", cp, "--out", d, "--nproc", "1"], log)
        steps["run_repeat"].append({"engine": e, "structures": [des[0]["id"], des[1]["id"]],
                                    "runs": [des[0]["run"], des[1]["run"]], "dir": os.path.basename(d),
                                    "status": "RAN" if code == 0 else "FAILED", "exit": code,
                                    "message": None if code == 0 else tail})

    # Diagnose: BLOCKED in 0.4 (never run; recorded)
    steps["diagnose"] = []
    steps["diagnose_skipped"] = True
    steps["diagnose_blocked"] = {"status": DIAGNOSE_BLOCKED_STATUS, "reason": DIAGNOSE_BLOCKED_MESSAGE,
                                 "exit_code_if_requested": DIAGNOSE_BLOCKED_EXIT}

    # Evaluate: every included structure, only with an experimental reference
    steps["evaluate"] = []
    if reference:
        pf, rf = os.path.join(project, "construct_protein.fasta"), os.path.join(project, "construct_rna.fasta")
        for s in inc:
            d = os.path.join(out, "evaluate", s["id"])
            os.makedirs(os.path.dirname(d), exist_ok=True)
            code, tail = _rn(["evaluate", "run", "--prediction", s["used_path"], "--reference", os.path.abspath(reference),
                              "--protein-seq", pf, "--rna-seq", rf, "--target-id", man["case_id"], "--engine", s["engine"],
                              "--out", d], log)
            steps["evaluate"].append({"structure": s["id"], "dir": os.path.relpath(d, out), "exit": code,
                                      "message": None if code == 0 else tail})

    from . import summary as summ, trace
    S = summ.build(man, out, steps, reference)
    json.dump(S, open(os.path.join(out, "summary.json"), "x"), indent=1)
    problems = trace.verify(S, man, out)
    if problems:
        open(os.path.join(out, "TRACE_FAILED.txt"), "x").write("\n".join(problems) + "\n")
        print("rnplens analyse: summary NOT accepted: %d value(s) could not be traced to a module output; see "
              "TRACE_FAILED.txt" % len(problems), file=sys.stderr)
        return 1
    html = summ.render_html(S, man, out)
    bad = trace.wording_audit(html)
    if bad:
        open(os.path.join(out, "WORDING_AUDIT_FAILED.txt"), "x").write("\n".join(bad) + "\n")
        print("rnplens analyse: summary NOT accepted: wording audit failed; see WORDING_AUDIT_FAILED.txt", file=sys.stderr)
        return 1
    open(os.path.join(out, "summary.html"), "x", encoding="utf-8").write(html)
    print("rnplens analyse: %d structure(s); Report exit %d; Diagnose %s; Evaluate %s" % (
        len(inc), steps["report"]["exit"], DIAGNOSE_BLOCKED_STATUS,
        ("%d run" % len(steps["evaluate"])) if reference else "not run (no --reference)"))
    print("  summary: %s" % os.path.join(os.path.abspath(out), "summary.html"))
    failed = report_failures(steps)
    if failed:
        print("rnplens analyse: FAILED: %s; summary.json records the failed step (steps.report) and the summary is "
              "written for inspection only" % "; ".join(failed), file=sys.stderr)
        return EXIT_FAILED
    return 0


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens analyse", description="Run Report and (with --reference) Evaluate on "
                                 "a project made by 'rnplens import', unchanged, and build one summary from their "
                                 "outputs. Diagnose is BLOCKED in 0.4 (the summary records DIAGNOSE_BLOCKED). "
                                 "Nothing is overwritten.")
    ap.add_argument("project", help="project directory written by 'rnplens import'")
    ap.add_argument("--out", required=True, help="results directory to create (must not exist)")
    ap.add_argument("--reference", help="experimental reference structure (mmCIF); enables Evaluate per structure")
    ap.add_argument("--nproc", type=int, default=1, help="processes for Report")
    ap.add_argument("--without-diagnose", action="store_true", help="accepted for compatibility; Diagnose is never run "
                    "in 0.4")
    ap.add_argument("--with-diagnose", action="store_true", help="refused in 0.4: Diagnose is BLOCKED (exit 5)")
    a = ap.parse_args(argv)
    return run(a.project, a.out, a.reference, a.nproc, diagnose=bool(a.with_diagnose))
