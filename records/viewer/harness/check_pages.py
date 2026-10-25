"""RNPLens viewer track: check what Mol* loaded, selected, showed and requested against the authoritative records.

usage: python check_pages.py PAGES_JSON RESULTS_DIR OUT_JSON

PAGES_JSON lists pages: {"page_id", "package" (demo package root), "viewer_dir" (relative to package),
"representatives_threshold" (null, or "0.3"/"0.5"/"0.7" for a grouping-representatives page), "expected_range"
("region_rule_log": the RNA range is the last line of logs/03_region_rule.log; "all": every Report contact)}.
RESULTS_DIR/<page_id>/ holds result_offline.json, result_netlog.json, strace_netlog.txt and the screenshots
written by render.js. Expected values are computed here from the records only (project manifest.json run/sample
fields, construct FASTA files, analysis/report/contacts_by_output.json, logs/03_region_rule.log,
analysis/groups/groups.json); nothing from rnplens.viewer is imported. Checks and thresholds are those frozen in
records/viewer/VERIFICATION_PLAN.md."""
import hashlib
import json
import os
import re
import sys

import numpy as np
from PIL import Image

AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
       "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
       "TYR": "Y", "VAL": "V"}
NT = {"A": "A", "C": "C", "G": "G", "U": "U"}
COLOURS = {"protein": 0xBBBBBB, "rna": 0xDDCC77, "protein_highlight": 0xE69F00, "rna_highlight": 0x0072B2}
BOX = (40, 215, 1230, 745)          # 3D canvas area of a 1600 x 840 #app screenshot, below the snapshot caption
MIN_PX = 100


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fasta(p):
    return "".join(l.strip() for l in open(p) if not l.startswith(">"))


def pix(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(float) / 255
    x0, y0, x1, y1 = BOX
    a = a[y0:y1, x0:x1]
    mx, mn = a.max(2), a.min(2)
    v, s = mx, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    d = mx - mn + 1e-9
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return {"rna_highlight": int(((h >= 185) & (h <= 215) & (s > 0.6) & (v > 0.15)).sum()),
            "protein_highlight": int(((h >= 30) & (h < 44) & (s > 0.75) & (v > 0.3)).sum()),
            "rna": int(((h >= 44) & (h <= 62) & (s > 0.25) & (s < 0.7) & (v > 0.3)).sum()),
            "protein": int(((s < 0.06) & (v > 0.25) & (v < 0.9)).sum())}


def colour_layers(rep):
    """[(colour, selection)] of a representation: selection None means all; else a set of (chain, residue) parsed
    strictly from the MolScript expression MolViewSpec writes for a residue-list selector (Amendment 1)."""
    if not rep["color_params"]:
        return None
    cp = json.loads(rep["color_params"])
    if rep["color"] == "uniform":
        return [(cp["value"], None)]
    if rep["color"] != "mvs-multilayer":
        return None
    out = []
    for L in cp["layers"]:
        if L["theme"]["name"] != "uniform":
            return None
        sel = L["selection"]
        if sel["name"] == "static" and sel["params"] == "all":
            out.append((L["theme"]["params"]["value"], None))
            continue
        e = sel["params"]
        if sel["name"] != "expression" or e["head"]["name"] != "structure-query.combinator.merge":
            return None
        got = set()
        for u in e["args"]:
            if u["head"]["name"] != "structure-query.modifier.union" or len(u["args"]) != 1:
                return None
            g = u["args"][0]
            if g["head"]["name"] != "structure-query.generator.atom-groups" or set(g["args"]) != {"chain-test", "residue-test"}:
                return None
            ct, rt = g["args"]["chain-test"], g["args"]["residue-test"]
            if ct["head"]["name"] != "core.rel.eq" or rt["head"]["name"] != "core.rel.eq":
                return None
            if ct["args"][0]["head"]["name"] != "structure-query.atom-property.macromolecular.auth_asym_id" or \
                    rt["args"][0]["head"]["name"] != "structure-query.atom-property.macromolecular.auth_seq_id":
                return None
            got.add((ct["args"][1], rt["args"][1]))
        out.append((L["theme"]["params"]["value"], got))
    return out


def parse_seq_panel(text):
    """'1    GPSPEIGQIV11   KIV...' -> (letters, [(number, offset_in_letters)])"""
    letters, marks = "", []
    for num, block in re.findall(r"(\d+)[\s\xa0]+([A-Za-z]+)", text or ""):
        marks.append((int(num), len(letters)))
        letters += block
    return letters, marks


def strace_summary(p):
    if not os.path.isfile(p):
        return None
    inet, unix, other = [], set(), 0
    for line in open(p, errors="replace"):
        if "connect(" not in line and "sendto(" not in line:
            continue
        if "AF_INET" in line:                       # AF_INET or AF_INET6
            inet.append(line.strip()[:200])
        elif "AF_UNIX" in line:
            m = re.search(r'sun_path=(@?"[^"]*")', line)
            unix.add(m.group(1) if m else "AF_UNIX(?)")
        else:
            other += 1
    return {"inet_calls": inet, "n_inet_calls": len(inet), "unix_paths": sorted(unix), "n_other": other}


def expected_for(pkg, vdir, thr, mode="region_rule_log"):
    proj, ana = os.path.join(pkg, "project"), os.path.join(pkg, "analysis")
    man = json.load(open(os.path.join(proj, "manifest.json")))
    cbo = json.load(open(os.path.join(ana, "report", "contacts_by_output.json")))
    ps, rs = fasta(os.path.join(proj, "construct_protein.fasta")), fasta(os.path.join(proj, "construct_rna.fasta"))
    rng = None
    if thr is None and mode == "all":
        ids = None
    elif thr is None:
        log = os.path.join(pkg, "logs", "03_region_rule.log")
        last = [l.strip() for l in open(log) if l.strip()][-1]
        a, b = (int(x) for x in last.split("-"))
        rng = (a, b)
        ids = None
    else:
        g = json.load(open(os.path.join(ana, "groups", "groups.json")))
        groups = g["thresholds"][thr]["groups"]
        ids = {x["representative"]["id"]: x["group"] for x in groups}
    out = []
    for s in man["structures"]:
        if s.get("verdict") != "INCLUDED" or (ids is not None and s["id"] not in ids):
            continue
        ch = {c["type_by_report"]: c["chain"] for c in s["chains"] if c.get("status") != "NONPOLYMER_CHAIN"}
        key = "%s|%s#%s" % (s["engine"], s["run"], s["sample"])
        pairs = cbo[key]
        if rng:
            pairs = [(p, r) for p, r in pairs if rng[0] <= r <= rng[1]]
        out.append({"id": s["id"], "label": "%s %s#%s" % (s["id"], s["run"], s["sample"]), "key": key,
                    "used_sha256": s["used_sha256"], "chains": ch, "group": ids[s["id"]] if ids else None,
                    "protein": sorted({p for p, _ in pairs}), "rna": sorted({r for _, r in pairs})})
    return {"range": rng, "structures": out, "protein_seq": ps, "rna_seq": rs,
            "representatives": ids, "n_groups": len(ids) if ids is not None else None}


def check_page(pg, rdir):
    pkg, vdir = pg["package"], os.path.join(pg["package"], pg["viewer_dir"])
    E = expected_for(pkg, vdir, pg.get("representatives_threshold"), pg.get("expected_range", "region_rule_log"))
    vman = json.load(open(os.path.join(vdir, "viewer_manifest.json")))
    runs = {t: json.load(open(os.path.join(rdir, "result_%s.json" % t))) for t in ("offline", "netlog")}
    R = runs["offline"]
    page = {"page_id": pg["page_id"], "expected_range": E["range"], "representatives_threshold": pg.get("representatives_threshold"),
            "n_expected_structures": len(E["structures"]), "checks": {}, "snapshots": []}
    C = page["checks"]

    def put(d, name, ok, detail=None):
        d[name] = {"result": ("PASS" if ok else "FAIL") if ok is not None else "NOT_EVALUATED", "detail": detail}

    # ---- page level: loading, renderer, network ----
    for t, r in runs.items():
        put(C, "V1_loaded_%s" % t, r.get("status", "").startswith("LOADED") and not r["page_errors"],
            {"status": r.get("status"), "page_errors": r["page_errors"], "load_ms": r.get("load_ms")})
        put(C, "V10_no_nonlocal_request_%s" % t, not r["nonlocal_requests"] and not r["websockets"] and not r["csp_violations"],
            {"schemes": r["request_schemes"], "nonlocal": r["nonlocal_requests"], "websockets": r["websockets"],
             "csp_violations": r["csp_violations"], "n_requests": len(r["requests"]), "targets": r["targets"]})
    gl = R.get("gl") or {}
    put(C, "V0_webgl_context", bool(gl.get("unmasked_renderer")), gl)
    st = strace_summary(os.path.join(rdir, "strace_netlog.txt"))
    put(C, "V10_no_inet_socket_netlog_strace", (st["n_inet_calls"] == 0) if st else None, st)
    put(C, "V1_snapshot_count", len(R["snapshots"]) == len(E["structures"]),
        {"snapshots": len(R["snapshots"]), "expected": len(E["structures"])})
    put(C, "V1_snapshot_titles_in_order", [s["name"] for s in R["snapshots"]] == [e["label"] for e in E["structures"]],
        {"page": [s["name"] for s in R["snapshots"]], "expected": [e["label"] for e in E["structures"]]})
    if E["representatives"] is not None:
        got = sorted(s["name"].split()[0] for s in R["snapshots"])
        put(C, "V12_representatives_equal_groups_json", got == sorted(E["representatives"]) and len(got) == E["n_groups"],
            {"page_ids": got, "groups_json_representatives": E["representatives"]})
    par = all(a["structures"][0]["residues"] == b["structures"][0]["residues"] and
              [c["residues"] for c in a["structures"][0]["components"]] == [c["residues"] for c in b["structures"][0]["components"]]
              for a, b in zip(runs["offline"]["snapshots"], runs["netlog"]["snapshots"])) and \
        len(runs["offline"]["snapshots"]) == len(runs["netlog"]["snapshots"])
    put(C, "V10_offline_equals_netlog_model_and_selection", par)

    # ---- per snapshot ----
    for i, e in enumerate(E["structures"]):
        snap = R["snapshots"][i] if i < len(R["snapshots"]) else None
        res = {"index": i + 1, "id": e["id"], "label": e["label"], "group": e["group"], "checks": {}}
        page["snapshots"].append(res)
        K = res["checks"]
        if snap is None:
            put(K, "V1_present", False)
            continue
        S = snap["structures"][0] if len(snap["structures"]) == 1 else None
        put(K, "V1_one_structure_loaded", S is not None, len(snap["structures"]))
        if S is None:
            continue
        # V2 identity of the loaded file
        copy = next((x for x in vman["structures"] if x["label"] == e["label"]), None)
        data_labels = [c["label"] for c in snap["cells"] if c["type"] == "String Data"]
        put(K, "V2_loaded_file_is_the_structure_copy",
            copy is not None and len(data_labels) == 1 and data_labels[0].endswith(os.path.basename(copy["copy"]))
            and vman["files"][copy["copy"]] == e["used_sha256"] == sha(os.path.join(vdir, copy["copy"])),
            {"data_cell": data_labels, "copy": copy and copy["copy"], "copy_sha256": copy and vman["files"][copy["copy"]],
             "project_used_sha256": e["used_sha256"]})
        # V3 chains and sequence positions (model residues vs construct)
        pc, rc = e["chains"]["protein"], e["chains"]["rna"]
        bych = {}
        for chn, num, comp, _ in S["residues"]:
            bych.setdefault(chn, []).append((num, comp))
        okp = pc in bych and [n for n, _ in bych[pc]] == list(range(1, len(E["protein_seq"]) + 1)) and \
            "".join(AA3.get(c, "X") for _, c in bych[pc]) == E["protein_seq"]
        okr = rc in bych and [n for n, _ in bych[rc]] == list(range(1, len(E["rna_seq"]) + 1)) and \
            "".join(NT.get(c, "X") for _, c in bych[rc]) == E["rna_seq"]
        put(K, "V3_chains_and_sequence_positions", okp and okr and set(bych) == {pc, rc},
            {"chains_in_model": {c: len(v) for c, v in bych.items()}, "expected": {pc: len(E["protein_seq"]), rc: len(E["rna_seq"])},
             "protein_seq_match": okp, "rna_seq_match": okr})
        comps = S["components"]
        def col(c):
            return [json.loads(r["color_params"])["value"] if r["color_params"] else None for r in c["representations"]]
        prot = [c for c in comps if c["label"] == "Protein"]
        nuc = [c for c in comps if c["label"] == "Nucleic"]

        def layers_ok(c, mol, chain, wanted):
            if len(c["representations"]) != 1:
                return False, None
            L = colour_layers(c["representations"][0])
            exp = [(COLOURS[mol], None)] + ([(COLOURS[mol + "_highlight"], {(chain, n) for n in wanted})] if wanted else [])
            if pg.get("cartoon_layers", False):            # Amendment 1: pages written after the F1 fix
                return L == exp, L and [(hex(v), sorted(x[1] for x in sl) if sl else "all") for v, sl in L]
            return L == [(COLOURS[mol], None)], L and [(hex(v), "all" if sl is None else len(sl)) for v, sl in L]
        okp4, dp4 = layers_ok(prot[0], "protein", pc, e["protein"]) if len(prot) == 1 else (False, None)
        okr4, dr4 = layers_ok(nuc[0], "rna", rc, e["rna"]) if len(nuc) == 1 else (False, None)
        put(K, "V4_base_components",
            len(prot) == 1 and len(nuc) == 1 and sorted(map(tuple, prot[0]["residues"])) == [(pc, n) for n in range(1, len(E["protein_seq"]) + 1)]
            and sorted(map(tuple, nuc[0]["residues"])) == [(rc, n) for n in range(1, len(E["rna_seq"]) + 1)] and okp4 and okr4,
            {"protein_colour_layers": dp4, "nucleic_colour_layers": dr4})
        hl = [c for c in comps if any(r["type"] == "ball-and-stick" for r in c["representations"])]
        want = {"protein": [[pc, n] for n in e["protein"]], "rna": [[rc, n] for n in e["rna"]]}
        got = {}
        for c in hl:
            chs = {x[0] for x in c["residues"]}
            mol = "protein" if chs == {pc} else "rna" if chs == {rc} else "mixed"
            got.setdefault(mol, []).append({"residues": sorted(c["residues"], key=lambda x: x[1]), "colours": sorted(set(col(c)))})
        okh = set(got) <= {"protein", "rna"} and all(len(v) == 1 for v in got.values())
        for mol in ("protein", "rna"):
            if want[mol]:
                okh = okh and mol in got and got[mol][0]["residues"] == want[mol] and got[mol][0]["colours"] == [COLOURS[mol + "_highlight"]]
            else:
                okh = okh and mol not in got
        put(K, "V5_highlight_selection_equals_contact_record", okh,
            {"expected": {m: [x[1] for x in v] for m, v in want.items()},
             "molstar": {m: [[x[1] for x in g["residues"]] for g in v] for m, v in got.items()}})
        # V6 side table
        rows = [r for r in R["side_table"] if r[0] == e["label"]]
        exp_rows = [[e["label"], "protein", pc, str(n), "%s%d" % (E["protein_seq"][n - 1], n)] for n in e["protein"]] + \
                   [[e["label"], "rna", rc, str(n), "%s%d" % (E["rna_seq"][n - 1], n)] for n in e["rna"]]
        okt = [r[:5] for r in rows] == exp_rows and all(r[5].startswith("report/contacts_by_output.json#/" + e["key"].replace("~", "~0").replace("/", "~1") + "/") for r in rows)
        put(K, "V6_side_table_rows_and_evidence_ids", okt, {"n_rows": len(rows), "n_expected": len(exp_rows)})
        # V7 sequence panel
        sp = (snap.get("sequence_panel") or {}).get("chains")
        if not sp:
            put(K, "V7_sequence_panel_positions", None, "sequence panel text not extracted")
        else:
            seqs = []
            for o in sp:
                letters, marks = parse_seq_panel(o["text"])
                seqs.append({"option": o["option"][:40], "letters": letters, "marks_ok": all(n == 1 + off for n, off in marks) and bool(marks)})
            okq = sorted(x["letters"] for x in seqs) == sorted([E["protein_seq"], E["rna_seq"]]) and all(x["marks_ok"] for x in seqs)
            put(K, "V7_sequence_panel_positions", okq, [{"option": x["option"], "n": len(x["letters"]), "marks_ok": x["marks_ok"]} for x in seqs])
        # V8 label layer present when residue labels are expected (<= 40 per molecule and at least one)
        lab = [c for c in snap["cells"] if c["label"] == "MVS Custom Label"]
        need = any(0 < len(e[m]) <= 40 for m in ("protein", "rna"))
        put(K, "V8_label_layer", (len(lab) >= 1) == need, {"label_cells": len(lab), "labels_expected": need})
        # V9 pixels: each expected colour class visible in at least one of the three views
        shots = {}
        for v in [x for x in snap["shots"] if x in ("loaded", "overview", "rnafocus")]:
            p = os.path.join(rdir, "offline_%02d_%s_%s.png" % (i + 1, snap["key"], v))
            shots[v] = pix(p) if os.path.isfile(p) else None
        need_cls = {"protein": len(e["protein"]) < len(E["protein_seq"]), "rna": len(e["rna"]) < len(E["rna_seq"]),
                    "protein_highlight": bool(e["protein"]), "rna_highlight": bool(e["rna"])}
        best = {c: max((s[c] for s in shots.values() if s), default=0) for c in need_cls}
        okpx = all((best[c] >= MIN_PX) for c, n in need_cls.items() if n)
        put(K, "V9_expected_colours_rendered", okpx, {"max_px_over_views": best, "required": need_cls, "per_view": shots})
        # V13 (Amendment 1): with ball-and-stick hidden, the ribbon of highlighted residues shows the highlight colours
        rib = {}
        for v in [x for x in snap["shots"] if x in ("ribbon", "ribbonrna")]:
            p = os.path.join(rdir, "offline_%02d_%s_%s.png" % (i + 1, snap["key"], v))
            rib[v] = pix(p) if os.path.isfile(p) else None
        if not rib:
            put(K, "V13_highlight_ribbon_colour", None, "no ribbon view (harness before Amendment 1)")
        else:
            n_hl = len([c for c in comps if any(r["type"] == "ball-and-stick" for r in c["representations"])])
            bestr = {c: max((x[c] for x in rib.values() if x), default=0) for c in ("protein_highlight", "rna_highlight")}
            okr = snap.get("ball_and_stick_hidden") == n_hl and all(bestr[c] >= MIN_PX for c, n in
                      (("protein_highlight", bool(e["protein"])), ("rna_highlight", bool(e["rna"]))) if n)
            put(K, "V13_highlight_ribbon_colour", okr, {"max_px_ribbon_views": bestr, "ball_and_stick_hidden": snap.get("ball_and_stick_hidden"),
                                                        "highlight_components": n_hl, "per_view": rib})
    allc = [x["result"] for x in C.values()] + [x["result"] for s in page["snapshots"] for x in s["checks"].values()]
    page["summary"] = {k: allc.count(k) for k in ("PASS", "FAIL", "NOT_EVALUATED")}
    return page


def main(argv):
    pages = json.load(open(argv[0]))
    out = {"record": "rnplens-viewer-check-1", "pages": [check_page(p, os.path.join(argv[1], p["page_id"])) for p in pages]}
    out["summary"] = {k: sum(p["summary"][k] for p in out["pages"]) for k in ("PASS", "FAIL", "NOT_EVALUATED")}
    with open(argv[2], "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({p["page_id"]: p["summary"] for p in out["pages"]}), json.dumps(out["summary"]))


if __name__ == "__main__":
    main(sys.argv[1:])
