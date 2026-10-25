"""POST-HOC supplement to compare_results.py (not the pre-registered check; reported separately).

For every file that compare_results.py classed DIFFERENT, and for every file present on one side only, test whether
the two sides become equal after replacing, in keys and string values of both sides:
  - the package root path by <ROOT>,
  - ISO-8601 timestamps (2026-10-16T13:17:13+00:00, ...Z, with fractions) and compact digit timestamps of 14 or more
    digits (202610161317160000) by <TS>,
  - 64-hex strings (SHA-256 values, cache keys) by <HEX>,
  - consent record ids consent-NNNN-<8 hex> by consent-NNNN-<ID> (the 8 hex are the start of the SHA-256 of the
    record, which includes its timestamp: rnplens_assistant/consent.py, _append),
and dropping keys whose name ends in _utc or starts with timestamp.
Files present on one side only (cache entries are named by their key) are paired by their normalised content.
A file that becomes equal differs only in time stamps, time-derived ids and hashes; anything else is OTHER and is
listed with its pointers.

usage: python classify_replay_diffs.py ORIGINAL REPLAY REPLAY_CHECK_JSON OUT_JSON
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_results import diffs, strip  # noqa: E402

TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?|\b\d{14,}\b")
HEX = re.compile(r"\b[0-9a-f]{64}\b")
CONSENT_ID = re.compile(r"\b(consent-\d{4})-[0-9a-f]{8}\b")


def norm(o, root):
    if isinstance(o, dict):
        return {norm(k, root): norm(v, root) for k, v in o.items() if not (k.endswith("_utc") or k.startswith("timestamp"))}
    if isinstance(o, list):
        return [norm(v, root) for v in o]
    if isinstance(o, str):
        return CONSENT_ID.sub(r"\1-<ID>", HEX.sub("<HEX>", TS.sub("<TS>", o.replace(root, "<ROOT>"))))
    return o


def main(orig, rep, check, out):
    orig, rep = os.path.realpath(orig), os.path.realpath(rep)
    C = json.load(open(check))
    rows = []
    for f in C["files"]:
        if f["result"] != "DIFFERENT":
            continue
        a = norm(strip(json.load(open(os.path.join(orig, f["file"])))), orig)
        b = norm(strip(json.load(open(os.path.join(rep, f["file"])))), rep)
        rows.append({"file": f["file"], "result": "ONLY_TIMESTAMPS_IDS_HASHES" if a == b else "OTHER",
                     "other_pointers": [] if a == b else diffs(a, b)})
    load = lambda root, f: norm(strip(json.load(open(os.path.join(root, f)))), root)
    left = {f: load(orig, f) for f in C["missing_in_replay"]}
    right = {f: load(rep, f) for f in C["missing_in_original"]}
    used = set()
    for f, a in sorted(left.items()):
        m = [g for g, b in sorted(right.items()) if g not in used and b == a and HEX.sub("<HEX>", TS.sub("<TS>", g)) == HEX.sub("<HEX>", TS.sub("<TS>", f))]
        if m:
            used.add(m[0])
            rows.append({"file": f, "replay_file": m[0], "result": "ONLY_TIMESTAMPS_IDS_HASHES", "other_pointers": [],
                         "note": "one-side file paired by normalised content; its name differs only by hash/timestamp"})
    unmatched = sorted(set(left) - {r["file"] for r in rows}) + sorted(set(right) - used)
    res = {"status": "POST-HOC SUPPLEMENT (not the pre-registered replay check)", "pre_registered_verdict": C["verdict"],
           "rows": rows, "unmatched_one_side_files": unmatched,
           "n_only_timestamps_ids_hashes": sum(1 for r in rows if r["result"] == "ONLY_TIMESTAMPS_IDS_HASHES"),
           "n_other": sum(1 for r in rows if r["result"] == "OTHER")}
    res["verdict"] = "NO_OTHER_DIFFERENCE" if res["n_other"] == 0 and not unmatched else "OTHER_DIFFERENCES"
    json.dump(res, open(out, "w"), indent=1, sort_keys=True)
    print("post-hoc classification: %s; %d file(s) differ only in timestamps/ids/hashes, %d OTHER, %d unmatched one-side file(s)"
          % (res["verdict"], res["n_only_timestamps_ids_hashes"], res["n_other"], len(unmatched)))
    for r in rows:
        if r["result"] == "OTHER":
            print("  OTHER %s: %s" % (r["file"], r["other_pointers"][:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
