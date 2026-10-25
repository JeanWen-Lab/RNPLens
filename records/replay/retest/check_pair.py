"""Frozen pass rule of the replay requalification (DETERMINISM_CONTRACT_v1.md, section 6) for ONE case.

usage: python check_pair.py FIRST_CASE_ROOT SECOND_CASE_ROOT OUT_JSON
PASS iff (0) both runs completed (logs/RESULT == COMPLETE, every step at its expected exit code),
         (i)  the canonical file sets (canonical_artifacts_v1.json) are equal, non-empty, and every canonical file
              is byte-identical, and
         (ii) the scientific comparison is equal: records/replay/trace_replay_diffs.py over the two case roots reports
              no file with verdict CONTENT, UNRESOLVED or DEMO_TOOLING, no unpaired file, and every recorded
              follow-up evidence hash equals its recomputation.
Anything else is FAIL. Exit 0 on PASS, 1 on FAIL.
"""
import fnmatch
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import trace_replay_diffs as TR  # noqa: E402

SPEC = json.load(open(os.path.join(HERE, "canonical_artifacts_v1.json")))


def canonical_files(case_root):
    proj = os.path.join(case_root, SPEC["project_dir"])
    out = {}
    for rel, p in TR.walk(proj).items():
        segs = rel.split("/")
        for pat in SPEC["patterns_relative_to_project_dir"]:
            ps = pat.split("/")
            if len(ps) == len(segs) and all(fnmatch.fnmatchcase(s, q) for s, q in zip(segs, ps)):
                out[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
                break
    return out


def completed(case_root):
    try:
        res = open(os.path.join(case_root, "logs", "RESULT")).read().strip()
        rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(case_root, "logs", "steps.tsv"))][1:]
    except OSError as ex:
        return False, "missing run record: %s" % ex
    bad = [r[0] for r in rows if r[1] != r[2]]
    return res == "COMPLETE" and not bad, "RESULT=%s, steps=%d, unexpected exits=%s" % (res, len(rows), bad)


def main(first, second, out):
    first, second = os.path.realpath(first), os.path.realpath(second)
    c1, c2 = completed(first), completed(second)
    res = {"first": first, "second": second, "completed": {"first": c1[1], "second": c2[1]}, "criteria": {}}
    if not (c1[0] and c2[0]):
        res["criteria"]["0_completed"] = False
        res["verdict"] = "FAIL"
        json.dump(res, open(out, "w"), indent=1, sort_keys=True); print("FAIL (run incomplete)", res["completed"]); return 1
    res["criteria"]["0_completed"] = True
    A, B = canonical_files(first), canonical_files(second)
    rows = []
    for f in sorted(set(A) | set(B)):
        rows.append({"file": f, "first_sha256": A.get(f), "second_sha256": B.get(f),
                     "result": "BYTE_IDENTICAL" if A.get(f) and A.get(f) == B.get(f) else
                               ("MISSING_IN_SECOND" if f not in B else "MISSING_IN_FIRST" if f not in A else "DIFFERENT")})
    res["canonical_files"] = rows
    res["n_canonical"] = {"first": len(A), "second": len(B)}
    res["criteria"]["i_canonical_byte_identical"] = bool(rows) and all(r["result"] == "BYTE_IDENTICAL" for r in rows)
    T = TR.Tracer(first, second)
    both, pairs, (only_a, only_b) = T.pair_files()
    T.pairmap = dict(pairs)
    diffs = [T.file_diff(f, f) for f in both] + [T.file_diff(f, g) for f, g in pairs]
    diffs = [d for d in diffs if d["result"] != "BYTE_IDENTICAL"]
    bad = [{"file": d["file"], "verdict": d["verdict"], "classes": d["class_counts"]} for d in diffs
           if d["verdict"] in ("CONTENT", "UNRESOLVED", "DEMO_TOOLING")]
    ev = {}
    for side, tree in (("first", T.A), ("second", T.B)):
        for k, v in (getattr(tree, "derived_check", {}) or {}).items():
            ev["%s:%s" % (side, k)] = v["equal"]
    res["scientific"] = {"n_files_first": len(T.A.files), "n_files_second": len(T.B.files),
                         "n_byte_identical": sum(1 for f in both if T.A.bytes[f] == T.B.bytes[f]),
                         "differing_files": [{"file": d["file"], "verdict": d["verdict"], "classes": d["class_counts"]} for d in diffs],
                         "not_volatile": bad, "unpaired_first": only_a, "unpaired_second": only_b,
                         "evidence_hash_recomputation_equal": ev, "derive_error": T.A.derive_error}
    res["criteria"]["ii_scientific_equal"] = not bad and not only_a and not only_b and all(ev.values())
    res["verdict"] = "PASS" if all(res["criteria"].values()) else "FAIL"
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)
    open(out, "a").write("\n")
    print("%s: canonical %d/%d files, %d byte-identical; scientific: %d differing files, %d not volatile, unpaired %d/%d"
          % (res["verdict"], len(A), len(B), sum(r["result"] == "BYTE_IDENTICAL" for r in rows), len(diffs), len(bad),
             len(only_a), len(only_b)))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
