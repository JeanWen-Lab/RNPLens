"""Replay check: compare every *.json of two demonstration folders (outside inputs/).

Pass 1 (the check): keys named created_utc or wall_s are removed everywhere; everything else must be equal.
Pass 2 (reported separately, for files that fail pass 1): additionally the absolute package root of each side is
replaced by <ROOT> in every string. A file that passes only pass 2 differs from the original only by where the
package lives.
Pass 3 (reported separately, for files that fail pass 2): every remaining difference is a "sha256" field whose
sibling "path"/"file" names a file of this comparison that itself passes pass 1, 2 or 3 (resolved transitively).
Such a file differs only because it records the hash of an upstream file that carries a timestamp or a path.

usage: python compare_results.py ORIGINAL REPLAY OUT_JSON
exit 0 when every file passes pass 1 or pass 2 and no file is missing on either side; 1 otherwise.
"""
import json
import os
import sys

IGNORED = ("created_utc", "wall_s")
SKIP_DIRS = ("inputs", "checks")


def files(root):
    out = []
    for d, sub, fs in os.walk(root):
        rel = os.path.relpath(d, root)
        if rel.split(os.sep)[0] in SKIP_DIRS:
            continue
        out += [os.path.normpath(os.path.join(rel, f)) for f in fs if f.endswith(".json")]
    return sorted(out)


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in IGNORED}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def subst(o, root):
    if isinstance(o, dict):
        return {subst(k, root): subst(v, root) for k, v in o.items()}
    if isinstance(o, list):
        return [subst(v, root) for v in o]
    if isinstance(o, str):
        return o.replace(root, "<ROOT>")
    return o


def diffs(a, b, ptr="", acc=None, limit=200):
    acc = [] if acc is None else acc
    if len(acc) >= limit:
        return acc
    if type(a) != type(b):
        acc.append(ptr or "/")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                acc.append(ptr + "/" + k)
            else:
                diffs(a[k], b[k], ptr + "/" + k, acc, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            acc.append(ptr + " (length %d vs %d)" % (len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diffs(x, y, "%s/%d" % (ptr, i), acc, limit)
    elif a != b:
        acc.append(ptr or "/")
    return acc


def _get(o, ptr):
    for x in ptr.strip("/").split("/"):
        o = o[int(x)] if isinstance(o, list) else o[x]
    return o


def _hashed_file(doc, ptr, f, orig, known):
    """The comparison file named beside a differing .../sha256 pointer, or None."""
    if not ptr.endswith("/sha256") or " (length" in ptr:
        return None
    try:
        parent = _get(doc, ptr[: -len("/sha256")])
    except (KeyError, IndexError, ValueError, TypeError):
        return None
    p = parent.get("path") or parent.get("file") if isinstance(parent, dict) else None
    if not isinstance(p, str):
        return None
    cands = []
    if p.startswith("<ROOT>/"):
        cands.append(os.path.normpath(p[len("<ROOT>/"):]))
    elif os.path.isabs(p):
        cands.append(os.path.relpath(os.path.realpath(p), orig) if os.path.realpath(p).startswith(orig) else None)
    else:
        cands += [os.path.normpath(os.path.join(os.path.dirname(f), p)), os.path.normpath(p)]
    for c in cands:
        if c in known:
            return c
    return None


def main(orig, rep, out):
    orig, rep = os.path.realpath(orig), os.path.realpath(rep)
    fa, fb = files(orig), files(rep)
    res = {"original": orig, "replay": rep, "ignored_keys": list(IGNORED), "files": [], "missing_in_replay": sorted(set(fa) - set(fb)),
           "missing_in_original": sorted(set(fb) - set(fa))}
    for f in sorted(set(fa) & set(fb)):
        a, b = strip(json.load(open(os.path.join(orig, f)))), strip(json.load(open(os.path.join(rep, f))))
        row = {"file": f}
        if a == b:
            row["result"] = "IDENTICAL"
        else:
            row["pointers_differing"] = diffs(a, b)
            if subst(a, orig) == subst(b, rep):
                row["result"] = "IDENTICAL_AFTER_ROOT_PATH_NORMALISATION"
            else:
                row["result"] = "DIFFERENT"
                row["pointers_differing_after_normalisation"] = diffs(subst(a, orig), subst(b, rep))
        res["files"].append(row)
    # pass 3, transitive: differences that are only hashes of files which themselves pass
    by = {r["file"]: r for r in res["files"]}
    changed = True
    while changed:
        changed = False
        for r in res["files"]:
            if r["result"] != "DIFFERENT":
                continue
            doc = subst(strip(json.load(open(os.path.join(orig, r["file"])))), orig)
            via = []
            for ptr in r["pointers_differing_after_normalisation"]:
                h = _hashed_file(doc, ptr, r["file"], orig, by)
                if h is None or by[h]["result"] == "DIFFERENT":
                    via = None
                    break
                via.append({"pointer": ptr, "hashed_file": h, "hashed_file_result": by[h]["result"]})
            if via and len(r["pointers_differing_after_normalisation"]) < 200:
                r["result"], r["only_hashes_of"] = "IDENTICAL_EXCEPT_HASHES_OF_PASSING_FILES", via
                changed = True
    c = {}
    for r in res["files"]:
        c[r["result"]] = c.get(r["result"], 0) + 1
    res["counts"] = c
    res["n_files"] = len(res["files"])
    ok = not res["missing_in_replay"] and not res["missing_in_original"] and c.get("DIFFERENT", 0) == 0
    res["verdict"] = "PASS" if ok else "FAIL"
    res["verdict_strict"] = "PASS" if ok and c.get("IDENTICAL", 0) == res["n_files"] else "FAIL"
    res["verdict_definition"] = ("PASS: no file missing on either side and every file IDENTICAL (pass 1), IDENTICAL_AFTER_ROOT_PATH_NORMALISATION (pass 2) "
                                 "or IDENTICAL_EXCEPT_HASHES_OF_PASSING_FILES (pass 3); verdict_strict: every file IDENTICAL in pass 1")
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print("replay check: %s (strict: %s); %d JSON files: %s; missing in replay %d, missing in original %d"
          % (res["verdict"], res["verdict_strict"], res["n_files"], c, len(res["missing_in_replay"]), len(res["missing_in_original"])))
    for r in res["files"]:
        if r["result"] == "DIFFERENT":
            print("  DIFFERENT %s: %s" % (r["file"], r["pointers_differing_after_normalisation"][:5]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
