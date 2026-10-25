"""Pre-registered distance and correspondence check for contact-explorer pages (PREREG_NT_CONTACTS.md, part P).

Independent of rnplens.contact_explorer and of Biopython: every structure copy of a page is read with gemmi, residues
(waters dropped) are numbered 1..L in file order per chain, and the minimum heavy-atom (element not H/D) distance of
every protein/RNA residue pair is computed with numpy. Per structure:
  P1 page chains == the project manifest's protein/RNA chains (type_by_report) of that structure
  P2 page residue map (construct position -> auth_seq_id, insertion code, residue name) == gemmi file order
  P3 {pairs with gemmi minimum distance <= 5.0 A} == Report's record (report/contacts_by_output.json) for its key
  P4 page contact rows: set of (protein pos, RNA pos) == Report's record; one row per pair (one chain pair)
  P5 every page distance d: |d - gemmi minimum| <= 0.005 A (+1e-9; page rounds to 0.01 A)
  P6 the named closest atoms are at the gemmi minimum (|dist - min| <= 1e-4) and the page coordinates equal gemmi's
     coordinates of those atoms (<= 5e-4 A per axis)
  P7 page distance_check.status == PASS
usage: python parity_check.py OUT_JSON PAGE_DIR,ANALYSIS_DIR,PROJECT_DIR [...]
Computes nothing new about the structures beyond this check; exit 0 when every structure passes P1-P7."""
import json
import os
import sys

import gemmi
import numpy as np

CUT = 5.0


def view_data(page):
    t = open(os.path.join(page, "view_data.js"), encoding="ascii").read()
    return json.loads(t.split("=", 1)[1].strip().rstrip(";"))


def chain_residues(model, ch):
    out = []
    for r in model[ch]:
        if r.is_water():
            continue
        atoms = [(a.name, np.array([a.pos.x, a.pos.y, a.pos.z], dtype=float)) for a in r if a.element.name not in ("H", "D")]
        out.append((r.seqid.num, (r.seqid.icode or " ").strip(), r.name, atoms))
    return out


def mins(P, R):
    out = {}
    for i, (_, _, _, pa) in enumerate(P):
        if not pa:
            continue
        A = np.array([x for _, x in pa])
        for j, (_, _, _, ra) in enumerate(R):
            if not ra:
                continue
            B = np.array([x for _, x in ra])
            d = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
            m = float(d.min())
            if m <= CUT + 1.0:
                out[(i + 1, j + 1)] = m
    return out


def check_page(page, analysis, project):
    V = view_data(page)["explorer"]
    cbo = json.load(open(os.path.join(analysis, "report", "contacts_by_output.json")))
    man = json.load(open(os.path.join(project, "manifest.json")))
    by_id = {s["id"]: s for s in man["structures"]}
    rows = []
    for s in V["structures"]:
        rec = s["rec"]
        res = {"label": s["label"], "copy": s["rel"], "key": rec["key"], "checks": {}}
        ms = by_id[rec["structure_id"]]
        key = "%s|%s" % (ms["engine"], ms.get("execution", ""))
        poly = [c for c in ms["chains"] if c.get("status") != "NONPOLYMER_CHAIN"]
        mc = {"protein": [c["chain"] for c in poly if c.get("type_by_report") == "protein"],
              "rna": [c["chain"] for c in poly if c.get("type_by_report") == "rna"]}
        res["checks"]["P1"] = rec["chains"] == mc and key == rec["key"]
        st = gemmi.read_structure(os.path.join(page, s["rel"]))
        model = st[0]
        pc, rc = mc["protein"][0], mc["rna"][0]
        P, R = chain_residues(model, pc), chain_residues(model, rc)
        want_map = {pc: [[i + 1, x[0], x[1], x[2]] for i, x in enumerate(P)], rc: [[i + 1, x[0], x[1], x[2]] for i, x in enumerate(R)]}
        got_map = {ch: [r[:4] for r in rec["residues"][ch]] for ch in (pc, rc)}
        res["checks"]["P2"] = want_map == got_map
        m = mins(P, R)
        report = {tuple(x) for x in cbo[key]}
        g = {k for k, d in m.items() if d <= CUT}
        res["checks"]["P3"] = g == report
        res["n_report_pairs"], res["n_gemmi_pairs"] = len(report), len(g)
        res["gemmi_only"], res["report_only"] = sorted(g - report)[:20], sorted(report - g)[:20]
        prs = [(c["p"], c["r"]) for c in rec["contacts"]]
        res["checks"]["P4"] = set(prs) == report and len(prs) == len(report) and all(c["pc"] == pc and c["rc"] == rc for c in rec["contacts"])
        worst5, worst6 = 0.0, 0.0
        ok5 = ok6 = True
        for c in rec["contacts"]:
            gm = m.get((c["p"], c["r"]))
            if c["d"] is None or gm is None:
                ok5 = ok6 = False
                continue
            e = abs(c["d"] - gm)
            worst5 = max(worst5, e)
            ok5 &= e <= 0.005 + 1e-9
            pa = dict(P[c["p"] - 1][3]).get(c["pa"])
            ra = dict(R[c["r"] - 1][3]).get(c["ra"])
            if pa is None or ra is None:
                ok6 = False
                continue
            dd = float(np.sqrt(((pa - ra) ** 2).sum()))
            ce = max(float(np.abs(pa - np.array(c["pxyz"])).max()), float(np.abs(ra - np.array(c["rxyz"])).max()))
            worst6 = max(worst6, abs(dd - gm), ce)
            ok6 &= abs(dd - gm) <= 1e-4 and ce <= 5e-4
        res["checks"]["P5"], res["checks"]["P6"] = ok5, ok6
        res["max_abs_distance_difference_A"], res["max_atom_check_deviation_A"] = round(worst5, 6), round(worst6, 6)
        res["checks"]["P7"] = rec["distance_check"]["status"] == "PASS"
        near = [abs(d - CUT) for d in m.values()]
        res["smallest_margin_to_cutoff_A"] = round(min(near), 6) if near else None
        res["pass"] = all(res["checks"].values())
        rows.append(res)
    return rows


def main(argv):
    out, specs = argv[0], argv[1:]
    doc = {"gemmi": gemmi.__version__, "cutoff_A": CUT, "pages": []}
    for spec in specs:
        page, analysis, project = spec.split(",")
        rows = check_page(page, analysis, project)
        doc["pages"].append({"page": page, "n_structures": len(rows), "n_pass": sum(r["pass"] for r in rows),
                             "n_contact_rows": sum(r["n_report_pairs"] for r in rows), "structures": rows})
    doc["pass"] = all(p["n_pass"] == p["n_structures"] for p in doc["pages"])
    with open(out, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    for p in doc["pages"]:
        print("%s: %d/%d structures pass P1-P7 (%d contact rows)" % (p["page"], p["n_pass"], p["n_structures"], p["n_contact_rows"]))
    print("PARITY", "PASS" if doc["pass"] else "FAIL")
    return 0 if doc["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
