"""Data-access record of one demonstration run under strace (open/openat/openat2/execve, all processes).

Lists every distinct path opened or executed, groups them by location, and FAILS if any path matches a forbidden
pattern: DockQ label files (nscale_sample_dockq.tsv, rank_corpus.tsv), reranker_consensus.tsv, anything under
RNPLens-Rank/, the frozen evaluation (assistant_2026-10-16, eval/sealed), holdout files, or the manuscript.
Also lists every PCfold3D-RNP and dev-task path touched.

With --allow-from TARGET_RULE_JSON (demo 1b), every PCfold3D-RNP path must also start with one of that file's
allowed_pcfold_paths, and paths under pilot/references, pilot/audit, any pilot/*score* folder or exec_A_retry1 are
forbidden.

usage: python access_audit.py STRACE_FILE PACKAGE_ROOT TRACK_CLONE OUT_JSON [--allow-from TARGET_RULE_JSON]
"""
import json
import re
import sys

FORBIDDEN = [r"nscale_sample_dockq\.tsv", r"rank_corpus\.tsv", r"reranker_consensus\.tsv", r"/RNPLens-Rank/",
             r"assistant_2026-10-16", r"/eval/sealed", r"holdout", r"/manuscript/"]
PAT = re.compile(r'(?:open|openat|openat2|execve)\((?:[A-Z_0-9]+, )?"([^"]+)"')


PILOT_FORBIDDEN = [r"/pilot/references", r"/pilot/audit", r"/pilot/[^/]*score", r"exec_A_retry1"]


def main(trace, pkg, clone, out, allow_from=None):
    paths = set()
    for line in open(trace, errors="replace"):
        m = PAT.search(line)
        if m and "ENOENT" not in line:
            paths.add(m.group(1))
    groups = {"package": [], "track_clone": [], "pcfold3d_rnp": [], "dev_tasks": [], "system_or_python": [], "other": []}
    for p in sorted(paths):
        if p.startswith(pkg):
            groups["package"].append(p)
        elif p.startswith(clone):
            groups["track_clone"].append(p)
        elif "/PCfold3D-RNP/" in p:
            groups["pcfold3d_rnp"].append(p)
        elif "/assistant_dev_tasks/" in p:
            groups["dev_tasks"].append(p)
        elif p.startswith(("/usr", "/lib", "/etc", "/proc", "/sys", "/dev", "/bin", "/home/jwen/miniforge3", "/home/jwen/projects/RNPBench/RNPLens_dev_0.3/venv", "/snap")) or "/tmp" in p:
            groups["system_or_python"].append(p)
        else:
            groups["other"].append(p)
    pats = FORBIDDEN + (PILOT_FORBIDDEN if allow_from else [])
    bad = sorted({p for p in paths for f in pats if re.search(f, p)})
    not_allowed = []
    if allow_from:
        allowed = json.load(open(allow_from))["allowed_pcfold_paths"]
        not_allowed = sorted(p for p in groups["pcfold3d_rnp"] if not any(p == a or p.startswith(a) or p + "/" == a for a in allowed))
        bad = sorted(set(bad) | set(not_allowed))
    res = {"trace": trace, "n_paths": len(paths), "forbidden_patterns": pats, "forbidden_paths_opened": bad,
           "allow_list_file": allow_from, "pcfold3d_paths_outside_allow_list": not_allowed,
           "counts": {k: len(v) for k, v in groups.items()}, "pcfold3d_rnp_paths": groups["pcfold3d_rnp"],
           "dev_task_paths": groups["dev_tasks"], "other_paths": groups["other"],
           "verdict": "PASS" if not bad else "FAIL"}
    json.dump(res, open(out, "w"), indent=1)
    pc = sorted({re.sub(r"_model_\d+", "_model_*", p) for p in groups["pcfold3d_rnp"]})
    print("access audit: %s; %d distinct paths opened/executed; forbidden %d; by location %s" % (res["verdict"], len(paths), len(bad), res["counts"]))
    print("  PCfold3D-RNP paths (model numbers collapsed): %s" % pc)
    print("  other paths: %s" % groups["other"][:20])
    return 0 if not bad else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(*a[:4], allow_from=a[a.index("--allow-from") + 1] if "--allow-from" in a else None))
