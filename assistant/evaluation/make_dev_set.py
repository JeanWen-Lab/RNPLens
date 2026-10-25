"""Package the development pilot tasks and development keys in the sealed-set layout, so the runner and aggregator
can be exercised end to end without touching the sealed set. Usage: make_dev_set.py DEV_TASKS DEV_KEYS OUT"""
import hashlib
import json
import os
import shutil
import sys

src, keys, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
assert not os.path.exists(out)
os.makedirs(out + "/keys")
shutil.copytree(src, out + "/tasks")
for t, k in keys.items():
    k = dict(k, task_id=t, cluster=t, counted=True)
    json.dump(k, open(out + "/keys/%s.json" % t, "w"), indent=1, sort_keys=True)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
files = {}
for root in ("tasks", "keys"):
    for dp, dn, fn in os.walk(os.path.join(out, root)):
        for f in fn:
            files[os.path.relpath(os.path.join(dp, f), out)] = sha(os.path.join(dp, f))
json.dump({"development_set": True, "files": files}, open(out + "/SEALED_MANIFEST.json", "w"), indent=1, sort_keys=True)
open(out + "/SEALED_MANIFEST.sha256", "w").write(sha(out + "/SEALED_MANIFEST.json") + "  SEALED_MANIFEST.json\n")
print("dev set:", len(os.listdir(out + "/tasks")), "tasks", len(files), "files")
