"""Pre-registered before/after comparison of Report / Evaluate outputs (PREREG_NT_CONTACTS.md, part R).
usage: python compare_outputs.py OUT_JSON BASE_DIR FEATURE_DIR REL [REL ...]
For each relative path: raw SHA-256 equality. When the raw bytes differ and the file is JSON, every differing leaf
path is listed; such a file still passes only if each differing path names a run-environment field (its path contains
one of: wall, time, environment, host, platform, python, date, elapsed). Non-JSON files must be byte-identical.
A path matching *viewer_manifest.json is compared on its "highlighted" list only (the page's existing highlights)."""
import hashlib
import json
import os
import sys

ENV = ("wall", "time", "environment", "host", "platform", "python", "date", "elapsed")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def leaves(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, path + "/" + str(i))
    else:
        yield path, o


def main(out, base, feat, rels):
    rows = []
    for rel in rels:
        a, b = os.path.join(base, rel), os.path.join(feat, rel)
        r = {"file": rel, "base_exists": os.path.isfile(a), "feature_exists": os.path.isfile(b)}
        if not (r["base_exists"] and r["feature_exists"]):
            r["pass"] = False
            rows.append(r)
            continue
        if rel.endswith("viewer_manifest.json"):
            ha, hb = json.load(open(a))["highlighted"], json.load(open(b))["highlighted"]
            r.update({"compared": "highlighted list", "n": len(ha), "equal": ha == hb, "pass": ha == hb})
            rows.append(r)
            continue
        r["sha256_base"], r["sha256_feature"] = sha(a), sha(b)
        r["byte_identical"] = r["sha256_base"] == r["sha256_feature"]
        if r["byte_identical"]:
            r["pass"] = True
        elif rel.endswith(".json"):
            la, lb = dict(leaves(json.load(open(a)))), dict(leaves(json.load(open(b))))
            diff = sorted(k for k in set(la) | set(lb) if la.get(k, object()) != lb.get(k, object()))
            r["differing_paths"] = diff[:200]
            r["n_differing_paths"] = len(diff)
            r["non_environment_differences"] = [k for k in diff if not any(e in k.lower() for e in ENV)]
            r["pass"] = not r["non_environment_differences"]
        else:
            r["pass"] = False
        rows.append(r)
    doc = {"base": base, "feature": feat, "files": rows, "pass": all(r["pass"] for r in rows)}
    json.dump(doc, open(out, "w"), indent=1)
    for r in rows:
        print("%-60s %s%s" % (r["file"], "PASS" if r["pass"] else "FAIL",
                              "" if r.get("byte_identical", r.get("equal")) else "  (differs: %s)" % r.get("differing_paths", "")))
    print("COMPARE", "PASS" if doc["pass"] else "FAIL")
    return 0 if doc["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
