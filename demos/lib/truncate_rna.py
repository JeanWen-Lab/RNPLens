"""Build an ambiguous input folder: copy SRC to DST and remove the last N nucleotides of the RNA chain from every
.pdb file (ATOM/HETATM lines of those residues). Other files are copied unchanged. The RNA chain is the chain whose
residues are all A, C, G or U. Writes DST/TRUNCATION.json describing what was removed.

usage: python truncate_rna.py SRC DST N
"""
import json
import os
import shutil
import sys

NT = {"A", "C", "G", "U"}


def main(src, dst, n):
    n = int(n)
    os.makedirs(dst)
    rec = {"source": os.path.basename(os.path.normpath(src)), "nucleotides_removed_from_3_end": n, "files": []}
    for f in sorted(os.listdir(src)):
        s, d = os.path.join(src, f), os.path.join(dst, f)
        if not f.endswith(".pdb"):
            shutil.copyfile(s, d)
            continue
        lines = open(s).read().splitlines(True)
        res = {}
        for l in lines:
            if l.startswith(("ATOM", "HETATM")):
                res.setdefault(l[21], []).append((int(l[22:26]), l[17:20].strip()))
        rna = [c for c, r in res.items() if r and all(name in NT for _, name in r)]
        if len(rna) != 1:
            raise SystemExit("%s: expected exactly one RNA chain, found %s" % (f, rna))
        c = rna[0]
        nums = sorted({x for x, _ in res[c]})
        drop = set(nums[-n:])
        out = [l for l in lines if not (l.startswith(("ATOM", "HETATM", "ANISOU")) and l[21] == c and int(l[22:26]) in drop)]
        open(d, "w").write("".join(out))
        rec["files"].append({"file": f, "rna_chain": c, "residues_before": len(nums), "removed_residue_numbers": sorted(drop)})
    json.dump(rec, open(os.path.join(dst, "TRUNCATION.json"), "w"), indent=1)
    print("%d structure file(s) truncated by %d nt" % (len(rec["files"]), n))


if __name__ == "__main__":
    main(*sys.argv[1:4])
