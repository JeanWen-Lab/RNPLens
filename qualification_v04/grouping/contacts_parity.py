"""Contacts parity: grouping's recomputed contact sets (rc3 Report's interface_contacts via analyse_output) against
the Rank study's RNPLens-Rank/derived/pool{A,B}_contacts.json (Amendment 3, A3.7). Parity check only.

Usage: python contacts_parity.py --pool A|B --qual DIR --out FILE
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qualify as Q  # noqa: E402

from rnplens import provenance as pv  # noqa: E402


def parse(c):
    m = re.fullmatch(r"A(-?\d+)\|B(-?\d+)", c)
    if not m:
        raise ValueError("unexpected contact token %r" % c)
    return int(m.group(1)), int(m.group(2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, choices=("A", "B"))
    ap.add_argument("--qual", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src = os.path.join(Q.RANK, "pool%s_contacts.json" % a.pool)
    rank = json.load(open(src))
    n = same = 0
    inter = union = 0
    diffs, missing = [], 0
    for t in Q.targets(a.pool):
        p = os.path.join(a.qual, "targets", "%s.json" % t)
        if not os.path.isfile(p):
            continue
        r = json.load(open(p))
        for s in r["structures"]:
            if s["state"] != "ELIGIBLE":
                continue
            i = s["id"].split("_")[1]
            if t not in rank or i not in rank[t]:
                missing += 1
                continue
            mine = {tuple(x) for x in s["contacts"]}
            theirs = {parse(c) for c in rank[t][i]}
            n += 1
            same += mine == theirs
            inter += len(mine & theirs)
            union += len(mine | theirs)
            if mine != theirs and len(diffs) < 20:
                diffs.append({"target": t, "model": int(i), "n_grouping": len(mine), "n_rank": len(theirs),
                              "only_grouping": sorted(mine - theirs)[:5], "only_rank": sorted(theirs - mine)[:5]})
    S = {"pool": a.pool, "label": Q.LABEL, "rank_file": {"path": src, "sha256": pv.sha256_file(src)},
         "n_structures_compared": n, "n_identical_sets": same,
         "fraction_identical": same / n if n else None,
         "pooled_jaccard": inter / union if union else None,
         "n_structures_absent_from_rank_file": missing, "first_differences": diffs,
         "note": "parity check only; grouping always uses Report's own interface_contacts"}
    pv.atomic_write_json(a.out, S)
    print("pool %s: %d/%d identical contact sets" % (a.pool, same, n))


if __name__ == "__main__":
    main()
