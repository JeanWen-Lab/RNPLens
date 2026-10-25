"""RNPLens viewer track r2: check the owner package after a fresh unzip, from the render.js results of the frozen
driver run_all.sh (one run inside a network-less namespace, one with request logging and strace).

usage: python zip_check.py UNZIP_ROOT RESULTS_DIR OUT_JSON
UNZIP_ROOT is the unzipped RNPLens_owner_screen_check/ folder; RESULTS_DIR/<short>/result_{offline,netlog}.json and
strace_netlog.txt as written by run_all.sh for page ids equal to the package's short page names.
Checks per page: Z1 loaded (both runs, no page error); Z2 only file: and data: requests, no WebSocket, no CSP
violation, 0 AF_INET/AF_INET6 calls in strace; Z3 snapshot titles = expected_highlights.json labels in order;
Z4 Mol*'s ball-and-stick and cartoon highlight-layer residue sets = expected_highlights.json per structure and chain;
Z5 every file: request lies inside UNZIP_ROOT; Z6 the status label is in viewer.html and index.html."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coverage import molstar_sets  # noqa: E402
from check_pages import strace_summary  # noqa: E402

LABEL = "automatically tested, awaiting manual visual confirmation; not fully visually qualified"


def main(argv):
    root, res, outp = os.path.abspath(argv[0]), argv[1], argv[2]
    exp = json.load(open(os.path.join(root, "expected_highlights.json")))
    out = {"record": "rnplens-owner-package-zip-check-1", "unzip_root": root, "pages": {}}
    index_ok = LABEL in open(os.path.join(root, "index.html"), encoding="utf-8").read()
    for short, e in sorted(exp.items()):
        d = os.path.join(res, short)
        if not all(os.path.isfile(os.path.join(d, "result_%s.json" % t)) for t in ("offline", "netlog")):
            out["pages"][short] = {"checks": {"Z0_results_present": False}, "pass": False, "n_structures": len(e["structures"])}
            continue
        runs = {t: json.load(open(os.path.join(d, "result_%s.json" % t))) for t in ("offline", "netlog")}
        C = {}
        C["Z1_loaded"] = all(r["status"].startswith("LOADED") and not r["page_errors"] for r in runs.values())
        st = strace_summary(os.path.join(d, "strace_netlog.txt"))
        C["Z2_local_only"] = all(set(r["request_schemes"]) <= {"file", "data"} and not r["nonlocal_requests"] and not r["websockets"]
                                 and not r["csp_violations"] for r in runs.values()) and st is not None and st["n_inet_calls"] == 0
        R = runs["offline"]
        C["Z3_titles"] = [s["name"] for s in R["snapshots"]] == [s["label"] for s in e["structures"]]
        z4, bad = True, []
        for s in e["structures"]:
            snap = next((x for x in R["snapshots"] if x["name"] == s["label"]), None)
            if snap is None:
                z4 = False; bad.append({"label": s["label"], "what": "no snapshot"}); continue
            M = molstar_sets(snap)
            pc, rc = s["chains"]["protein"], s["chains"]["rna"]
            got = {"ball_protein": sorted(r for c, r in M["ball"] if c == pc), "ball_rna": sorted(r for c, r in M["ball"] if c == rc),
                   "layer_protein": sorted(r for c, r in M["layer"].get("protein", set()) if c == pc),
                   "layer_rna": sorted(r for c, r in M["layer"].get("nucleic", set()) if c == rc),
                   "other_chains": sorted({c for c, _ in M["ball"]} - {pc, rc})}
            ok = got["ball_protein"] == got["layer_protein"] == s["protein_residues"] and \
                got["ball_rna"] == got["layer_rna"] == s["rna_residues"] and not got["other_chains"]
            if not ok:
                z4 = False; bad.append({"label": s["label"], "got": got, "expected": {"protein": s["protein_residues"], "rna": s["rna_residues"]}})
        C["Z4_molstar_highlights_equal_expected"] = z4
        files = [q["url"] for r in runs.values() for q in r["requests"] if q["url"].startswith("file://")]
        C["Z5_files_inside_package"] = all(u[len("file://"):].startswith(root + os.sep) for u in files)
        C["Z6_status_label"] = index_ok and LABEL in open(os.path.join(root, e["page"]), encoding="utf-8").read()
        out["pages"][short] = {"checks": C, "pass": all(C.values()), "n_structures": len(e["structures"]), "problems": bad,
                               "schemes": {t: r["request_schemes"] for t, r in runs.items()}, "n_requests": {t: len(r["requests"]) for t, r in runs.items()},
                               "strace_inet_calls": st and st["n_inet_calls"], "load_ms": R.get("load_ms"),
                               "renderer": (R.get("gl") or {}).get("unmasked_renderer")}
    out["all_pass"] = all(p["pass"] for p in out["pages"].values())
    with open(outp, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({k: v["pass"] for k, v in out["pages"].items()}), "all_pass", out["all_pass"])


if __name__ == "__main__":
    main(sys.argv[1:])
