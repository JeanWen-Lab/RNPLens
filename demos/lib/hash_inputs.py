"""Write the SHA-256 of every file under a folder (sorted relative paths): python hash_inputs.py DIR OUT_TSV"""
import hashlib, os, sys
root, out = sys.argv[1], sys.argv[2]
rows = []
for d, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(d, f)
        rows.append((os.path.relpath(p, root), hashlib.sha256(open(p, "rb").read()).hexdigest(), os.path.getsize(p)))
with open(out, "w") as fh:
    fh.write("file\tsha256\tbytes\n")
    for r in sorted(rows):
        fh.write("%s\t%s\t%d\n" % r)
print("%d files hashed" % len(rows))
