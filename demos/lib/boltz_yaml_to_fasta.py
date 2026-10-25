"""Write protein.fasta and rna.fasta from a Boltz input YAML with one protein and one rna entry (no YAML library
needed): python boltz_yaml_to_fasta.py INPUT.yaml OUTDIR"""
import os
import sys

kind, seqs = None, {}
for line in open(sys.argv[1]):
    s = line.strip()
    if s.startswith("- protein:"):
        kind = "protein"
    elif s.startswith("- rna:"):
        kind = "rna"
    elif s.startswith("sequence:") and kind:
        if kind in seqs:
            raise SystemExit("more than one %s entry" % kind)
        seqs[kind] = s.split(":", 1)[1].strip()
if set(seqs) != {"protein", "rna"}:
    raise SystemExit("expected one protein and one rna sequence, found %s" % sorted(seqs))
for k, v in seqs.items():
    open(os.path.join(sys.argv[2], k + ".fasta"), "w").write(">%s\n%s\n" % (k, v))
print("protein %d aa, rna %d nt" % (len(seqs["protein"]), len(seqs["rna"])))
