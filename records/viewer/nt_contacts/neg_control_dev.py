# Negative control of check_nt.py on the 7K9D development run (PREREG_NT_CONTACTS.md). Run from feature/nt-contacts/tmp with devout3/ present.

import json, copy, subprocess, sys
base = json.load(open("devout3/result_dev3.json"))
def run(name, f):
    d = copy.deepcopy(base); f(d); json.dump(d, open("devout3/neg.json","w"))
    p = subprocess.run([sys.executable, "/home/jwen/projects/RNPBench/RNPLens_dev_0.4/feature/nt-contacts/RNPLens/records/viewer/nt_contacts/check_nt.py", "dev3_plan.json", "devout3/neg.json", "/home/jwen/projects/RNPBench/RNPLens_dev_0.4/feature/nt-contacts/tmp/dev7k9d/a/viewer_15-30", "/home/jwen/projects/RNPBench/RNPLens_dev_0.4/feature/nt-contacts/tmp/dev7k9d/p", "/home/jwen/projects/RNPBench/RNPLens_dev_0.4/feature/nt-contacts/tmp/dev7k9d/a", "devout3/negc.json"], capture_output=True, text=True)
    print(name, "rc=%d" % p.returncode, p.stdout.strip().splitlines()[-1][:150])
st = lambda d, i: d["steps"][i]
run("drop_panel_row", lambda d: st(d,1)["panel"]["rows"].pop())
run("extra_bs_residue", lambda d: st(d,1)["components"][3]["residues"].append("A:99"))
run("wrong_colour", lambda d: st(d,1)["components"][2]["reprs"][0].__setitem__("uniform", "#E69F00"))
run("distance_off", lambda d: st(d,1)["panel"]["rows"][0].__setitem__("d", st(d,1)["panel"]["rows"][0]["d"] + 0.02))
run("stale_structure", lambda d: st(d,10)["fingerprint"][0].__setitem__("xyz", st(d,1)["fingerprint"][0]["xyz"]) if st(d,10)["fingerprint"][0]["xyz"] != st(d,1)["fingerprint"][0]["xyz"] else None)
run("line_moved", lambda d: st(d,1)["lines"][0].__setitem__("molstar_p", [0,0,0]))
run("mouse_fallback", lambda d: st(d,1)["click"].__setitem__("how", "api_fallback"))
run("network_request", lambda d: d["requests"].append({"url": "https://example.org/x"}))
run("focus_cell", lambda d: st(d,1).__setitem__("focus_cells", ["Non-covalent Interactions"]))
run("ensemble_text", lambda d: st(d,1)["panel"].__setitem__("text", st(d,1)["panel"]["text"].replace("2 of 2", "1 of 2")))
