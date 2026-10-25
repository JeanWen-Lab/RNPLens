"""Pre-registered check of a browser run (PREREG_NT_CONTACTS.md, part B) against Report's records.
usage: python check_nt.py PLAN_JSON RESULT_JSON PAGE_DIR PROJECT_DIR ANALYSIS_DIR OUT_JSON

Expected values come from: the plan's actions (simulated: selection, toggle-off, clear, structure index, mode); the
page's viewer_manifest.json (structure order -> structure file) and the project manifest (file -> Report key, chain
types); Report's report/contacts_by_output.json (contacts); gemmi on the page's structure copies (construct position
<-> author residue number, atom coordinates, minimum heavy-atom distances). The page's own explorer data are not used.

Per step (criteria, all must hold):
  B0  no driver error; explorer READY
  B1  structure: state index/key, selector value and panel label are the expected structure; Mol*'s first-atom
      coordinates of every chain equal that structure file's (<= 1e-3 A)
  B2  selection (molecule, chain, construct position) in state and panel == simulated expectation
  B3  panel rows {(protein chain, protein pos, RNA chain, RNA pos)} == Report's pairs of the selected residue in the
      structure on screen; count == number of partner residues; zero partners -> "No qualifying contact"
  B4  Mol* ball-and-stick components: focus mode -> union == {selected} + partners, one component == {selected}
      coloured #CC00CC, one == partners coloured #E69F00 (RNA selected) / #0072B2 (protein selected), cartoons at
      opacity 0.3 (protein) / 0.6 (RNA); show-all mode -> union == page highlights + selected + partners, cartoons
      opaque; no selection -> union == page highlights (Report pairs in the page's RNA range), nothing magenta
  B5  contact lines: one per panel row; endpoints == Mol*'s coordinates of the named atoms (<= 1e-3 A); length ==
      row distance (<= 0.006 A); no lines without a selection
  B6  panel distances == gemmi minimum heavy-atom distance (<= 0.005 A); none missing
  B7  no Mol*-generated focus / interaction components
  B8  ensemble sentence "k of n BOLTZ2" == count over Report's BOLTZ2 records
  B9  steps marked require_mouse were done by a real mouse click on the residue
Run-level: status LOADED; no request other than file:/data:/blob:/about:; no websocket; no failed load; no page error."""
import json
import os
import re
import sys

import gemmi
import numpy as np

MAG, ORANGE, BLUE = "#CC00CC", "#E69F00", "#0072B2"


def load_structure(path):
    m = gemmi.read_structure(path)[0]
    chains = {}
    for ch in m:
        res = [r for r in ch if not r.is_water()]
        chains[ch.name] = [(r.seqid.num, (r.seqid.icode or " ").strip(), r.name,
                            {a.name: np.array([a.pos.x, a.pos.y, a.pos.z]) for a in r},
                            np.array([[a.pos.x, a.pos.y, a.pos.z] for a in r if a.element.name not in ("H", "D")]))
                           for r in res]
    return chains


def main(plan_p, res_p, page, project, analysis, out):
    plan, run = json.load(open(plan_p)), json.load(open(res_p))
    vm = json.load(open(os.path.join(page, "viewer_manifest.json")))
    man = json.load(open(os.path.join(project, "manifest.json")))
    cbo = json.load(open(os.path.join(analysis, "report", "contacts_by_output.json")))
    by_used = {os.path.realpath(s["used_path"]): s for s in man["structures"] if s.get("used_path")}
    S = []
    for s in vm["structures"]:
        ms = by_used[os.path.realpath(s["source"])]
        poly = [c for c in ms["chains"] if c.get("status") != "NONPOLYMER_CHAIN"]
        S.append({"id": ms["id"], "label": s["label"], "key": "%s|%s" % (ms["engine"], ms.get("execution", "")),
                  "copy": os.path.join(page, s["copy"]), "pc": [c["chain"] for c in poly if c.get("type_by_report") == "protein"][0],
                  "rc": [c["chain"] for c in poly if c.get("type_by_report") == "rna"][0]})
    cache = {}

    def struct(k):
        if k not in cache:
            cache[k] = load_structure(S[k]["copy"])
        return cache[k]

    def auth(k, ch, pos):
        r = struct(k)[ch][pos - 1]
        return "%s:%d%s" % (ch, r[0], r[1])

    def mind(k, p, r):
        s = S[k]
        A, B = struct(k)[s["pc"]][p - 1][4], struct(k)[s["rc"]][r - 1][4]
        return float(np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)).min())

    rng = plan.get("rna_range")

    def overview(k):
        pairs = [(p, r) for p, r in cbo[S[k]["key"]] if not rng or rng[0] <= r <= rng[1]]
        return {auth(k, S[k]["pc"], p) for p, _ in pairs} | {auth(k, S[k]["rc"], r) for _, r in pairs}

    boltz = [k for k in cbo if k.split("|")[0] == "BOLTZ2"]
    st = {"k": 0, "sel": None, "mode": "focus"}
    n = len(S)
    rows, nfail = [], 0
    for step in run["steps"]:
        a = step["args"]
        do = a["do"]
        if do in ("click", "api_residue"):
            k = st["k"]; s = S[k]
            mol = "rna" if a["chain"] == s["rc"] else "protein" if a["chain"] == s["pc"] else None
            idx = [i + 1 for i, r in enumerate(struct(k)[a["chain"]]) if r[0] == a["auth"] and r[1] == (a.get("ins") or "")]
            tgt = (mol, a["chain"], idx[0])
            st["sel"] = None if st["sel"] == tgt else tgt
        elif do == "api_select":
            tgt = (a["molecule"], a["chain"], a["pos"])
            st["sel"] = None if st["sel"] == tgt else tgt
        elif do == "clear":
            st["sel"] = None
        elif do in ("show", "next", "prev"):
            st["k"] = a["k"] if do == "show" else max(0, min(n - 1, st["k"] + (1 if do == "next" else -1)))
            if st["sel"]:
                s = S[st["k"]]
                mol, ch, pos = st["sel"]
                if ch not in (s["pc"], s["rc"]) or pos > len(struct(st["k"])[ch]):
                    st["sel"] = None
        elif do == "mode":
            st["mode"] = a["m"]
        k, s, sel = st["k"], S[st["k"]], st["sel"]
        c = {}
        x = step.get("state") or {}
        pn = step.get("panel") or {}
        c["B0"] = not step.get("error") and pn.get("state") == "READY"
        fp_ok = bool(step.get("fingerprint"))
        for f in step.get("fingerprint") or []:
            rr = [r for r in struct(k).get(f["chain"], []) if r[0] == f["seq"] and r[1] == f["ins"]]
            fp_ok &= bool(rr) and f["atom"] in rr[0][3] and float(np.abs(rr[0][3][f["atom"]] - np.array(f["xyz"])).max()) <= 1e-3
        c["B1"] = x.get("k") == k and x.get("key") == s["key"] and pn.get("select_value") == str(k) and s["label"] in (pn.get("structure_text") or "") and fp_ok
        psel = pn.get("selection")
        c["B2"] = ((x.get("sel") is None and psel is None) if sel is None else
                   (x.get("sel") == {"molecule": sel[0], "chain": sel[1], "pos": sel[2]} and psel is not None
                    and (psel["molecule"], psel["chain"], psel["pos"]) == sel))
        exp_rows, partners = set(), set()
        if sel:
            mol, ch, pos = sel
            for p, r in cbo[s["key"]]:
                if (mol == "rna" and r == pos) or (mol == "protein" and p == pos):
                    exp_rows.add((s["pc"], p, s["rc"], r))
                    partners.add(auth(k, s["pc"], p) if mol == "rna" else auth(k, s["rc"], r))
            got_rows = {(r["pc"], r["p"], r["rc"], r["r"]) for r in pn.get("rows", [])}
            c["B3"] = (got_rows == exp_rows and len(pn.get("rows", [])) == len(exp_rows) and pn.get("count") == len(partners)
                       and (len(partners) > 0 or "No qualifying contact" in (pn.get("text") or "")))
        else:
            c["B3"] = not pn.get("rows") and pn.get("count") is None
        bs = [cm for cm in step.get("components", []) if any(r["type"] == "ball-and-stick" for r in cm["reprs"])]
        union = set().union(*[set(cm["residues"]) for cm in bs]) if bs else set()
        colour = lambda cm: [r["uniform"] for r in cm["reprs"] if r["type"] == "ball-and-stick"][0]
        cart = {cm["label"]: [r["alpha"] for r in cm["reprs"] if r["type"] == "cartoon"] for cm in step.get("components", []) if cm["label"] in ("Protein", "Nucleic")}
        if sel:
            me = auth(k, sel[1], sel[2])
            has_me = any(set(cm["residues"]) == {me} and colour(cm) == MAG for cm in bs)
            pcol = ORANGE if sel[0] == "rna" else BLUE
            has_p = (not partners) or any(set(cm["residues"]) == partners and colour(cm) == pcol for cm in bs)
            if st["mode"] == "focus":
                c["B4"] = union == {me} | partners and has_me and has_p and cart == {"Protein": [0.3], "Nucleic": [0.6]}
            else:
                c["B4"] = union == overview(k) | {me} | partners and has_me and has_p and cart == {"Protein": [1], "Nucleic": [1]}
        else:
            c["B4"] = union == overview(k) and not any(colour(cm) == MAG for cm in bs) and cart == {"Protein": [1], "Nucleic": [1]}
        lines = step.get("lines") or []
        lok = len(lines) == len(pn.get("rows", [])) if sel else (not lines and step.get("primitive_cells", 0) == 0)
        dist = {(r["pc"], r["p"], r["rc"], r["r"]): r["d"] for r in pn.get("rows", [])}
        for l in lines:
            kk = (l["pc"], l["p"], l["rc"], l["r"])
            lok &= kk in exp_rows and l["molstar_p"] is not None and l["molstar_r"] is not None
            if not lok:
                break
            lok &= float(np.abs(np.array(l["molstar_p"]) - l["start"]).max()) <= 1e-3 and float(np.abs(np.array(l["molstar_r"]) - l["end"]).max()) <= 1e-3
            lok &= dist.get(kk) is not None and abs(float(np.linalg.norm(np.subtract(l["start"], l["end"]))) - dist[kk]) <= 0.006
        c["B5"] = bool(lok)
        dok, worst = True, 0.0
        for r in pn.get("rows", []):
            if r["d"] is None:
                dok = False
                continue
            e = abs(r["d"] - mind(k, r["p"], r["r"]))
            worst = max(worst, e)
            dok &= e <= 0.005 + 1e-9
        c["B6"] = dok
        c["B7"] = not step.get("focus_cells")
        if sel:
            mol, ch, pos = sel
            kk = sum(1 for key in boltz if any((r if mol == "rna" else p) == pos for p, r in cbo[key]))
            m = re.search(r"has at least one Report contact in (\d+) of (\d+) BOLTZ2", pn.get("text") or "")
            c["B8"] = bool(m) and (int(m.group(1)), int(m.group(2))) == (kk, len(boltz))
        else:
            c["B8"] = True
        c["B9"] = (step.get("click") or {}).get("how") == "mouse" if a.get("require_mouse") else True
        ok = all(c.values())
        nfail += not ok
        rows.append({"id": step["id"], "do": do, "structure": s["id"], "mode": st["mode"],
                     "selected": None if not sel else "%s %s:%d" % sel, "click": step.get("click", {}).get("how") if step.get("click") else None,
                     "click_atom": (step.get("click") or {}).get("atom"),
                     "expected_partners": sorted(partners, key=lambda q: (q.split(":")[0], int(re.sub(r"\D", "", q.split(":")[1])))),
                     "observed_panel_rows": sorted([[r["pc"], r["p"], r["rc"], r["r"], r["d"]] for r in pn.get("rows", [])]),
                     "observed_count": pn.get("count"), "observed_bs_union": sorted(union), "n_lines": len(lines),
                     "max_distance_error_A": round(worst, 6), "screenshot": step.get("screenshot"), "criteria": c, "pass": ok,
                     "ensemble_text": (re.search(r"has at least one Report contact in \d+ of \d+ BOLTZ2", pn.get("text") or "") or [None])[0]})
    nonlocal_ = [r["url"] for r in run["requests"] if not re.match(r"^(file|data|blob|about):", r["url"])]
    glob = {"status_loaded": run.get("status", "").startswith("LOADED"), "nonlocal_requests": len(nonlocal_),
            "websockets": len(run["websockets"]), "failed_loads": len(run["failed"]), "page_errors": len(run["page_errors"])}
    gok = glob["status_loaded"] and not nonlocal_ and not run["websockets"] and not run["failed"] and not run["page_errors"]
    doc = {"plan": plan["tag"], "page": page, "browser": run.get("browser_version"), "gl": run.get("gl"), "n_steps": len(rows),
           "n_pass": len(rows) - nfail, "run_level": glob, "run_level_pass": gok, "pass": gok and nfail == 0, "steps": rows,
           "n_requests": len(run["requests"])}
    with open(out, "w") as fh:
        json.dump(doc, fh, indent=1)
    print("%s: %d/%d steps pass; run-level %s; requests %d (non-local %d)" % (plan["tag"], doc["n_pass"], len(rows), "PASS" if gok else "FAIL",
                                                                           len(run["requests"]), len(nonlocal_)))
    for r in rows:
        if not r["pass"]:
            print("  FAIL", r["id"], {k: v for k, v in r["criteria"].items() if not v})
    return 0 if doc["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:7]))
