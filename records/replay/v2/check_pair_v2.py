"""Frozen pass rule of DETERMINISM_CONTRACT_v2 (section 6) for ONE pair of case roots.

usage: python check_pair_v2.py A B OUT_JSON [--moved]
  A, B     two case roots that ran the same workflow (A = the first run)
  --moved  B is a byte copy of A (taken after A's base workflow) at another absolute path, continued there:
           absolute paths under A's root that B inherited are recognised as B's own when comparing

PASS iff
  (0)   both trees completed: logs/RESULT == COMPLETE, logs/RESULT_CONTINUATION == CONTINUED, every step at its
        expected exit code (a step recorded as "skipped" counts as expected only if it is skipped in both trees);
  (i)   the PROMISED set of the managed project is equal in A and B, non-empty, and every promised file is
        byte-identical. PROMISED(T) = every regular file under T/project except (1) files under
        T/project/.rnplens/run/ (sidecars) and (2) files F for which F.canonical.json or F.canonical.txt exists (the
        projection is promised instead of F);
  (i-b) projection coverage: in A and in B, every file under project/ with a projection extension (.json .md .txt
        .html .tsv .svg .log) that is not under project/.rnplens/, not a v1 canonical file, and not itself a
        projection, has its projection;
  (ii)  scientific equality: the trace (records/replay/trace_replay_diffs.py; with --moved, A's root is also
        recognised in B; a hash of a former version of an overwritten file is resolved when both trees' sidecar
        projection indexes map it to the same projection hash) over the two case roots reports no file with verdict
        CONTENT, UNRESOLVED or DEMO_TOOLING, no unpaired file, and every recorded follow-up evidence hash equals its
        recomputation.
Also MEASURED and reported, not a pass criterion (contract section 6, (iii)): with --moved, the files under
B/project outside the sidecars whose bytes contain A's absolute root, split into promised and non-promised files.
(A promised file containing A's root would already fail (i).) Exit 0 on PASS, 1 on FAIL.
"""
import fnmatch
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import trace_replay_diffs as TR  # noqa: E402

SPEC1 = json.load(open(os.path.join(os.path.dirname(HERE), "retest", "canonical_artifacts_v1.json")))
PROJ_EXT = (".json", ".md", ".txt", ".html", ".tsv", ".svg", ".log")
PROJ_SUFFIX = (".canonical.json", ".canonical.txt")


def v1_canonical(rel):
    segs = rel.split("/")
    for pat in SPEC1["patterns_relative_to_project_dir"]:
        ps = pat.split("/")
        if len(ps) == len(segs) and all(fnmatch.fnmatchcase(s, q) for s, q in zip(segs, ps)):
            return True
    return False


def project_files(root):
    proj = os.path.join(root, "project")
    return {rel: p for rel, p in TR.walk(proj).items()}


def promised(files):
    out = {}
    for rel, p in files.items():
        if rel.startswith(".rnplens/run/"):
            continue
        if any((rel + s) in files for s in PROJ_SUFFIX):
            continue
        out[rel] = p
    return out


def missing_projections(files):
    miss = []
    for rel in files:
        if rel.endswith(PROJ_SUFFIX) or rel.startswith(".rnplens/") or v1_canonical(rel):
            continue
        if rel.endswith(PROJ_EXT):
            want = rel + (".canonical.json" if rel.endswith(".json") else ".canonical.txt")
            if want not in files:
                miss.append(rel)
    return sorted(miss)


def steps(root):
    rows = []
    for f in ("steps.tsv",):
        try:
            rows += [l.rstrip("\n").split("\t") for l in open(os.path.join(root, "logs", f))][1:]
        except OSError:
            pass
    return rows


def completed(root):
    try:
        r1 = open(os.path.join(root, "logs", "RESULT")).read().strip()
        r2 = open(os.path.join(root, "logs", "RESULT_CONTINUATION")).read().strip()
    except OSError as ex:
        return False, "missing run record: %s" % ex, {}
    rows = steps(root)
    bad = [r[0] for r in rows if r[1] != r[2]]
    skipped = {r[0] for r in rows if r[1] == "skipped"}
    return (r1 == "COMPLETE" and r2 == "CONTINUED" and not [b for b in bad if b not in skipped],
            "RESULT=%s, CONTINUATION=%s, steps=%d, unexpected=%s" % (r1, r2, len(rows), bad), skipped)


def projection_index(root):
    p = os.path.join(root, "project", ".rnplens", "run", "projection_index.json")
    try:
        doc = json.load(open(p))
    except (OSError, ValueError):
        return {}
    if isinstance(doc.get("entries"), list):          # Amendment 1: list in write order (latest entry wins)
        return {e.get("raw_sha256"): e.get("projection_sha256") for e in doc["entries"] if isinstance(e, dict)}
    return dict(doc.get("raw_to_projection") or {})


class V2Tracer(TR.Tracer):
    """The step-A tracer plus two v2 rules: (1) with moved=True, A's root is also recognised in B;
    (2) a hash with no common target in the two trees (a former version of an overwritten file) is resolved when both
    trees' projection indexes map it to the same projection hash (contract section 4.2 step 4)."""

    def __init__(self, a, b, moved=False):
        TR.Tracer.__init__(self, a, b)
        self.moved = moved
        self.ix = (projection_index(self.A.root), projection_index(self.B.root))

    def norm_path(self, s, side):
        if side == 1:
            s = s.replace(self.B.root, "<ROOT>")
        return s.replace(self.A.root, "<ROOT>") if (side == 0 or self.moved) else s

    def resolve(self, ha, hb):
        r = TR.Tracer.resolve(self, ha, hb)
        if r.get("verdict") == "UNRESOLVED" and r.get("note") == "no common target found in the two trees":
            pa, pb = self.ix[0].get(ha), self.ix[1].get(hb)
            if pa and pa == pb:
                r = dict(r, verdict="VOLATILE_ONLY", note="resolved through the projection index: projection-sha256:" + pa)
                self.memo[(ha, hb)] = r
        return r


def main(a, b, out, moved=False):
    a, b = os.path.realpath(a), os.path.realpath(b)
    res = {"first": a, "second": b, "moved": moved, "criteria": {}}
    ca, cb = completed(a), completed(b)
    res["completed"] = {"first": ca[1], "second": cb[1], "skipped_first": sorted(ca[2]), "skipped_second": sorted(cb[2])}
    res["criteria"]["0_completed"] = ca[0] and cb[0] and ca[2] == cb[2]
    if not res["criteria"]["0_completed"]:
        res["verdict"] = "FAIL"
        json.dump(res, open(out, "w"), indent=1, sort_keys=True); print("FAIL (incomplete)", res["completed"]); return 1
    fa, fb = project_files(a), project_files(b)
    pa, pb = promised(fa), promised(fb)
    rows = []
    for f in sorted(set(pa) | set(pb)):
        ha = hashlib.sha256(open(pa[f], "rb").read()).hexdigest() if f in pa else None
        hb = hashlib.sha256(open(pb[f], "rb").read()).hexdigest() if f in pb else None
        rows.append({"file": f, "first_sha256": ha, "second_sha256": hb,
                     "result": "BYTE_IDENTICAL" if ha and ha == hb else ("MISSING_IN_SECOND" if hb is None else
                                                                          "MISSING_IN_FIRST" if ha is None else "DIFFERENT")})
    res["promised_files"] = rows
    res["n_promised"] = {"first": len(pa), "second": len(pb),
                         "projections": sum(1 for f in pa if f.endswith(PROJ_SUFFIX))}
    res["criteria"]["i_promised_byte_identical"] = bool(rows) and all(r["result"] == "BYTE_IDENTICAL" for r in rows)
    ma, mb = missing_projections(fa), missing_projections(fb)
    res["missing_projections"] = {"first": ma, "second": mb}
    res["criteria"]["ib_projection_coverage"] = not ma and not mb
    T = V2Tracer(a, b, moved)
    both, pairs, (only_a, only_b) = T.pair_files()
    T.pairmap = dict(pairs)
    diffs = [T.file_diff(f, f) for f in both] + [T.file_diff(f, g) for f, g in pairs]
    diffs = [d for d in diffs if d["result"] != "BYTE_IDENTICAL"]
    bad = [{"file": d["file"], "verdict": d["verdict"], "classes": d["class_counts"]} for d in diffs
           if d["verdict"] in ("CONTENT", "UNRESOLVED", "DEMO_TOOLING")]
    ev = {}
    for side, tree in (("first", T.A), ("second", T.B)):
        for kk, v in (getattr(tree, "derived_check", {}) or {}).items():
            ev["%s:%s" % (side, kk)] = v["equal"]
    res["scientific"] = {"n_files_first": len(T.A.files), "n_files_second": len(T.B.files),
                         "n_byte_identical": sum(1 for f in both if T.A.bytes[f] == T.B.bytes[f]),
                         "differing_files": [{"file": d["file"], "verdict": d["verdict"], "classes": d["class_counts"]} for d in diffs],
                         "not_volatile": bad, "unpaired_first": only_a, "unpaired_second": only_b,
                         "evidence_hash_recomputation_equal": ev}
    res["criteria"]["ii_scientific_equal"] = not bad and not only_a and not only_b and all(ev.values())
    if moved:
        refs_p, refs_n = [], []
        for rel, p in fb.items():
            if rel.startswith(".rnplens/run/"):
                continue
            if a.encode() in open(p, "rb").read():
                (refs_p if rel in pb else refs_n).append(rel)
        res["measured_iii_references_to_original_root"] = {"promised": sorted(refs_p), "non_promised": sorted(refs_n),
                                                           "n_promised": len(refs_p), "n_non_promised": len(refs_n)}
    # raw (non-promised) files that differ in bytes: the status of 'complete managed-project byte reproducibility'
    raw = sorted(set(fa) & set(fb) - set(pa) - {f for f in fa if f.startswith(".rnplens/run/")})
    res["measured_raw_files"] = {"n": len(raw), "n_differing": sum(1 for f in raw if open(fa[f], "rb").read() != open(fb[f], "rb").read())}
    res["verdict"] = "PASS" if all(res["criteria"].values()) else "FAIL"
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)
    open(out, "a").write("\n")
    print("%s: promised %d/%d (%d projections), %d byte-identical; missing projections %d/%d; scientific: %d differing, %d not volatile, unpaired %d/%d%s"
          % (res["verdict"], len(pa), len(pb), res["n_promised"]["projections"], sum(r["result"] == "BYTE_IDENTICAL" for r in rows),
             len(ma), len(mb), len(diffs), len(bad), len(only_a), len(only_b),
             ("; moved: %d promised / %d non-promised files reference the original root" % (
                 res["measured_iii_references_to_original_root"]["n_promised"],
                 res["measured_iii_references_to_original_root"]["n_non_promised"])) if moved else ""))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], "--moved" in sys.argv[4:]))
