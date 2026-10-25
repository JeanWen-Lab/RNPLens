"""``rnplens compare``: matched before/after evaluation of two prediction sets of the same targets.

Each prediction is evaluated by the unchanged Evaluate (both routes) against the same reference. Per target and
metric the change is put in exactly one class, in this order of precedence:
  CONSTRUCT_CHANGED        the declared protein or RNA sequence differs between the two sets
  NOT_EVALUABLE_IN_BOTH    no value before and no value after
  NEWLY_EVALUABLE          no value before, a value after
  NEWLY_UNEVALUABLE        a value before, none after
  CORRESPONDENCE_CHANGED   both have values but the residue correspondence or chain choice differs, so the two
                           numbers do not measure the same thing; reported, never pooled
  IMPROVED / WORSENED / UNCHANGED   like-for-like, at the stated precision. These give the DIRECTION of a
                           change at that precision; no threshold of practical relevance is applied.
A target whose Evaluate run itself failed or was refused is not a scientific class: the comparison stops with a
non-zero exit (RUN_FAILED rows are written so the failure is visible, and never counted as unevaluable).
Only like-for-like targets enter the paired summary. Evaluability and correspondence changes are counted
separately, because the S5 lesson of the benchmark is that a changed mapping can move a score with no change in
the structure.
"""
import csv
import json
import re
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

METRICS = [  # name, route, higher_is_better, precision (decimal places compared)
    ("dockq", "dockq", True, 3), ("fnat", "dockq", True, 3), ("irmsd", "dockq", False, 3), ("lrmsd", "dockq", False, 3)]
# Evaluate's four-axis geometry route is not compared in this development version: its residue correspondence has a
# known defect (difflib autojunk; stop report 2026-10-14) and the corrected construct-position implementation is not
# yet qualified in the toolkit. There is deliberately no option to include it.
WITHHELD = {"metrics": ["prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd"],
            "route": "geometry",
            "reason": "Evaluate's four-axis geometry route is withheld: known residue-correspondence defect (difflib "
                      "autojunk, stop report 2026-10-14); the corrected construct-position implementation is not yet "
                      "qualified in this toolkit. DockQ's iRMSD and LRMSD are DockQ quantities with their own "
                      "definitions and are not substitutes for the RNA conformation/placement decomposition."}
MIN_UNITS_FOR_INTERVAL = 2   # a bootstrap over one resampling unit is degenerate (zero width); none is reported
CHANGE_NOTE = ("IMPROVED and WORSENED give the direction of a change at the stated precision; no threshold of "
               "practical relevance is applied.")
ACCEPTABLE = 0.23
NBOOT, SEED = 5000, 20261014


def _read_tsv(p, need):
    rows = list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))
    miss = [c for c in need if rows and c not in rows[0]]
    if not rows or miss:
        raise ValueError("%s: needs a header with columns %s%s" % (p, ", ".join(need), (" (missing %s)" % ", ".join(miss)) if miss else ""))
    ids = [r["target_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("%s: target_id values must be unique" % p)
    return {r["target_id"]: r for r in rows}


def _resolve(v, base):
    """Every relative path in a TSV is resolved against that TSV's own directory (never the working directory)."""
    return v if os.path.isabs(v) else os.path.normpath(os.path.join(base, v))


def _looks_like_path(v):
    return bool(re.search(r"[/\\.]", v)) or v.lower().endswith((".fa", ".fasta", ".txt"))


def _seq(v, base):
    """A sequence column holds either a sequence (letters only) or a path to a FASTA file, resolved like every
    other path. A value that looks like a path but does not exist is an input error, never read as a sequence."""
    from .importer import read_sequence_arg
    v = (v or "").strip()
    if _looks_like_path(v):
        q = _resolve(v, base)
        if not os.path.isfile(q):
            raise ValueError("sequence file not found: %s (relative paths are resolved against the TSV's directory)" % q)
        return read_sequence_arg(q)
    return read_sequence_arg(v)


def _evaluate(job):
    tag, t, pred, ref, ps, rs, out = job
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wd = out + ".in"
    os.makedirs(wd)
    open(wd + "/protein.fasta", "w").write(">p\n%s\n" % ps); open(wd + "/rna.fasta", "w").write(">r\n%s\n" % rs)
    p = subprocess.run([sys.executable, "-m", "rnplens", "evaluate", "run", "--prediction", pred, "--reference", ref,
                        "--protein-seq", wd + "/protein.fasta", "--rna-seq", wd + "/rna.fasta", "--target-id", t, "--out", out],
                       capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))
    return tag, t, p.returncode, (p.stdout + p.stderr)[-600:]


def _values(res):
    if res is None:
        return None
    dq = res["dockq"]
    first = next(iter(dq["per_interface"].values())) if dq.get("per_interface") else {}
    ok = dq["status"] == "SCORED"
    # fnat, iRMSD and LRMSD are those of the interface DockQ reports (first in DockQ's own order, the frozen convention)
    vals = {"dockq": dq.get("dockq") if ok else None, "fnat": first.get("fnat") if ok else None,
            "irmsd": first.get("iRMSD") if ok else None, "lrmsd": first.get("LRMSD") if ok else None}
    corr = {"dockq": json.dumps([dq.get("selected_mapping"), dq.get("correspondence")], sort_keys=True)}
    return vals, corr, {"dockq": dq["status"]}


def classify(b, a, construct_changed, run_failed=False):
    """b, a: _values() of before/after (or None when Evaluate wrote no result). -> {metric: row}."""
    out = {}
    for m, route, hib, nd in METRICS:
        vb = b[0][m] if b else None
        va = a[0][m] if a else None
        row = {"before": vb, "after": va, "difference_after_minus_before": None}
        if construct_changed:
            cls = "CONSTRUCT_CHANGED"
        elif run_failed:
            cls = "RUN_FAILED"
        elif vb is None and va is None:
            cls = "NOT_EVALUABLE_IN_BOTH"
        elif vb is None:
            cls = "NEWLY_EVALUABLE"
        elif va is None:
            cls = "NEWLY_UNEVALUABLE"
        elif b[1][route] != a[1][route]:
            cls = "CORRESPONDENCE_CHANGED"
        else:
            d = round(va, nd) - round(vb, nd)
            row["difference_after_minus_before"] = round(d, nd)
            cls = "UNCHANGED" if round(d, nd) == 0 else ("IMPROVED" if (d > 0) == hib else "WORSENED")
        row["class"] = cls
        out[m] = row
    return out


def _boot(diffs, units):
    groups = {}
    for t, d in diffs.items():
        groups.setdefault(units.get(t, t), []).append(d)
    keys = sorted(groups)
    rng = random.Random(SEED); means = []
    for _ in range(NBOOT):
        s = [x for k in (rng.choice(keys) for _ in keys) for x in groups[k]]
        means.append(sum(s) / len(s))
    means.sort()
    return [means[int(0.025 * NBOOT)], means[int(0.975 * NBOOT) - 1]], len(keys)


def run(before, after, references, out, jobs=4):
    if os.path.exists(out):
        print("rnplens compare: refused: %s exists (nothing is overwritten)" % out, file=sys.stderr)
        return 2
    try:
        B = _read_tsv(before, ["target_id", "prediction", "protein_sequence", "rna_sequence"])
        A = _read_tsv(after, ["target_id", "prediction", "protein_sequence", "rna_sequence"])
        Rf = _read_tsv(references, ["target_id", "reference"])
    except ValueError as ex:
        print("rnplens compare: refused: %s" % ex, file=sys.stderr)
        return 2
    targets = sorted(set(B) & set(A))
    only = {"only_before": sorted(set(B) - set(A)), "only_after": sorted(set(A) - set(B)),
            "no_reference": sorted(t for t in targets if t not in Rf)}
    targets = [t for t in targets if t in Rf]
    if not targets:
        print("rnplens compare: refused: no target is in both sets and the reference table", file=sys.stderr)
        return 2
    bb, ab, rb = (os.path.dirname(os.path.abspath(x)) for x in (before, after, references))
    # preflight: every input must exist and every sequence must read before anything is written (finding M2)
    seqs, jobs_, errors = {}, [], []
    for t in targets:
        try:
            sb = (_seq(B[t]["protein_sequence"], bb), _seq(B[t]["rna_sequence"], bb))
            sa = (_seq(A[t]["protein_sequence"], ab), _seq(A[t]["rna_sequence"], ab))
        except ValueError as ex:
            errors.append("%s: %s" % (t, ex)); continue
        seqs[t] = (sb, sa)
        ref, pb, pa = _resolve(Rf[t]["reference"], rb), _resolve(B[t]["prediction"], bb), _resolve(A[t]["prediction"], ab)
        for kind, f in (("reference", ref), ("before prediction", pb), ("after prediction", pa)):
            if not os.path.isfile(f):
                errors.append("%s: %s file not found: %s" % (t, kind, f))
        jobs_.append(("before", t, pb, ref, sb[0], sb[1], os.path.join(out, "evaluate", "before", t)))
        jobs_.append(("after", t, pa, ref, sa[0], sa[1], os.path.join(out, "evaluate", "after", t)))
    if errors:
        print("rnplens compare: refused: %d input error(s); nothing was written. Relative paths in each TSV are "
              "resolved against that TSV's own directory." % len(errors), file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 2
    os.makedirs(out)
    log = []
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        for tag, t, code, tail in ex.map(_evaluate, jobs_):
            log.append({"set": tag, "target": t, "exit": code, "message": None if code == 0 else tail})
    json.dump(log, open(os.path.join(out, "evaluate_runs.json"), "x"), indent=1)

    def load(tag, t):
        p = os.path.join(out, "evaluate", tag, t, "result.json")
        return json.load(open(p)) if os.path.exists(p) else None
    units = {t: Rf[t].get("cluster") or t for t in targets}
    failed = sorted({x["target"] for x in log if x["exit"] != 0})
    rows, per = [], {}
    for t in targets:
        cc = seqs[t][0] != seqs[t][1]
        c = classify(_values(load("before", t)), _values(load("after", t)), cc, run_failed=t in failed)
        per[t] = c
        for m, r in c.items():
            rows.append([t, units[t], m, r["class"], r["before"], r["after"], r["difference_after_minus_before"]])
    with open(os.path.join(out, "comparison.tsv"), "x", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["target_id", "resampling_unit", "metric", "class", "before", "after", "difference_after_minus_before"])
        w.writerows([["" if v is None else v for v in r] for r in rows])
    summ = {"comparison": "rnplens-compare-1", "n_targets": len(targets), "unmatched": only,
            "resampling_unit": "cluster column of the reference table" if any(Rf[t].get("cluster") for t in targets) else "target",
            "precision": {m: "%d decimal places" % nd for m, _, _, nd in METRICS},
            "definition_note": "fnat, iRMSD and LRMSD are those of the interface DockQ reports (the first interface in DockQ's own order, the frozen convention)",
            "change_class_note": CHANGE_NOTE, "withheld": WITHHELD, "evaluate_run_failures": failed,
            "metrics": {}}
    for m, route, hib, nd in METRICS:
        cls = {}
        for t in targets:
            cls.setdefault(per[t][m]["class"], []).append(t)
        like = {t: per[t][m]["difference_after_minus_before"] for t in cls.get("IMPROVED", []) + cls.get("WORSENED", []) + cls.get("UNCHANGED", [])}
        row = {"route": route, "direction": "higher is better" if hib else "lower is better",
               "counts": {k: len(v) for k, v in sorted(cls.items())},
               "targets_by_class": {k: sorted(v) for k, v in sorted(cls.items())},
               "like_for_like_n": len(like)}
        if like:
            nu = len({units[t] for t in like})
            row.update({"mean_difference_after_minus_before": sum(like.values()) / len(like), "n_resampling_units": nu})
            if nu >= MIN_UNITS_FOR_INTERVAL:
                row["ci95_bootstrap"] = _boot(like, units)[0]
            else:
                row["ci95_bootstrap"] = None
                row["interval_note"] = "n = %d resampling unit: no interval" % nu
            if m == "dockq":
                bv = [per[t][m]["before"] for t in like]; av = [per[t][m]["after"] for t in like]
                row["acceptable_rate_like_for_like"] = {"threshold": ACCEPTABLE, "before": sum(v >= ACCEPTABLE for v in bv) / len(bv),
                                                        "after": sum(v >= ACCEPTABLE for v in av) / len(av)}
        summ["metrics"][m] = row
    json.dump(summ, open(os.path.join(out, "comparison_summary.json"), "x"), indent=1)
    txt = render_text(summ)
    from .trace import wording_audit
    bad = wording_audit(txt)
    if bad:
        open(os.path.join(out, "WORDING_AUDIT_FAILED.txt"), "x").write("\n".join(bad))
        return 1
    open(os.path.join(out, "comparison_summary.txt"), "x").write(txt)
    print(txt)
    if failed:
        print("rnplens compare: Evaluate refused or failed for %d target(s): %s. See evaluate_runs.json; these are "
              "input or run errors, not unevaluable predictions." % (len(failed), ", ".join(failed)), file=sys.stderr)
        return 1
    return 0


def render_text(s):
    L = ["RNPLens compare: %d matched target(s); resampling unit: %s" % (s["n_targets"], s["resampling_unit"])]
    for k, v in s["unmatched"].items():
        if v:
            L.append("  %s: %s" % (k.replace("_", " "), ", ".join(v)))
    for m, r in s["metrics"].items():
        c = r["counts"]
        L.append("%s (%s, %s): like-for-like %d [improved %d, worsened %d, unchanged %d]; reported separately: "
                 "correspondence changed %d, newly evaluable %d, newly unevaluable %d, not evaluable in both %d, construct changed %d, run failed %d"
                 % (m, r["route"], r["direction"], r["like_for_like_n"], c.get("IMPROVED", 0), c.get("WORSENED", 0), c.get("UNCHANGED", 0),
                    c.get("CORRESPONDENCE_CHANGED", 0), c.get("NEWLY_EVALUABLE", 0), c.get("NEWLY_UNEVALUABLE", 0),
                    c.get("NOT_EVALUABLE_IN_BOTH", 0), c.get("CONSTRUCT_CHANGED", 0), c.get("RUN_FAILED", 0)))
        if "mean_difference_after_minus_before" in r:
            if r.get("ci95_bootstrap"):
                L.append("    mean difference (after - before) on like-for-like targets %+.4f, 95%% bootstrap interval [%+.4f, %+.4f] over %d unit(s)"
                         % (r["mean_difference_after_minus_before"], r["ci95_bootstrap"][0], r["ci95_bootstrap"][1], r["n_resampling_units"]))
            else:
                L.append("    mean difference (after - before) on like-for-like targets %+.4f; %s"
                         % (r["mean_difference_after_minus_before"], r["interval_note"]))
        if "acceptable_rate_like_for_like" in r:
            a = r["acceptable_rate_like_for_like"]
            L.append("    DockQ >= %.2f on the same targets: before %.3f, after %.3f (read with fnat, iRMSD and LRMSD, not alone)" % (a["threshold"], a["before"], a["after"]))
    L.append(s["change_class_note"])
    L.append("Not compared: %s. %s" % (", ".join(s["withheld"]["metrics"]), s["withheld"]["reason"]))
    return "\n".join(L) + "\n"


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="rnplens compare", description="Matched before/after Evaluate of two prediction "
                                 "sets of the same targets. Changes of correspondence or evaluability are reported "
                                 "separately and never pooled with like-for-like changes.")
    ap.add_argument("--before", required=True, help="TSV: target_id, prediction, protein_sequence, rna_sequence (sequence or FASTA path). "
                    "Relative paths in every TSV are resolved against that TSV's own directory")
    ap.add_argument("--after", required=True, help="TSV with the same columns for the second set")
    ap.add_argument("--references", required=True, help="TSV: target_id, reference [, cluster]")
    ap.add_argument("--out", required=True, help="results directory to create (must not exist)")
    ap.add_argument("--jobs", type=int, default=4, help="Evaluate runs in parallel")
    a = ap.parse_args(argv)
    return run(a.before, a.after, a.references, a.out, a.jobs)
