"""RNPLens viewer track r2: complete per-structure set comparison between the contact records and what each viewer
page highlights, and, on region pages, a position-by-position account of every RNA position in the region.

usage: python coverage.py PAGES_JSON OUT_JSON

PAGES_JSON: [{"page_id", "package" (demo package root), "viewer_dir" (relative to package), "range_mode":
"region_rule_log" | "all", "representatives_threshold": null | "0.3" | "0.5" | "0.7", "molstar_result": optional path
of a render.js result JSON for this page}]

Sources compared per structure on the page (all read from files; nothing is imported from rnplens):
  R1  analysis/report/contacts_by_output.json[<engine>|<run>#<sample>]   (Report's authoritative per-structure record),
      restricted to the region's RNA range on region pages
  R2  analysis/region_<a>-<b>/region.json: for each contact, the structures listed with it (per_run.*.structures.
      with_contact, plus the run's designated structure when its observation is PRESENT)   (region pages only)
  V1  the page's view.mvsj: residues of the ball-and-stick (highlight) component and of the highlight colour layer of
      the molecule's cartoon
  V2  the page's viewer_manifest.json "highlighted"
  V3  the page's visible side table (viewer.html)
  V4  Mol* itself (render.js result): residues of the ball-and-stick component and of the cartoon highlight layer
  S   the structure copy on the page (PDB): which chain/residue numbers exist, with residue names
Region pages, every RNA position p in [a, b], per structure, classified exactly once:
  HIGHLIGHTED                    p in R1 and highlighted by V1-V4
  NO_QUALIFYING_CONTACT          p present in S (and in the construct mapping) and not in R1, and not highlighted
  ABSENT_FROM_STRUCTURE_OR_MAPPING  p missing in S, or listed unresolved in the region record, or outside the chain's
                                 recorded numbering
  OMITTED_BY_VIEWER              p in R1 but not highlighted by some viewer source        (a viewer defect)
  HIGHLIGHTED_WITHOUT_RECORD     p highlighted but not in R1                               (a viewer defect)
Independent geometry (descriptive cross-check, NOT Report's qualified route): for each RNA position in the region,
the minimum heavy-atom distance to any protein heavy atom in S, compared with Report's 5.0 A definition."""
import json
import math
import os
import re
import sys
from html.parser import HTMLParser

NUC = {"A", "C", "G", "U"}
CUTOFF = 5.0


def fasta(p):
    return "".join(l.strip() for l in open(p) if not l.startswith(">"))


def pdb_atoms(path):
    """[(chain, resnum, resname, atomname, element, x, y, z)] of ATOM/HETATM records."""
    out = []
    for l in open(path, encoding="latin-1"):
        if l.startswith(("ATOM  ", "HETATM")):
            name = l[12:16].strip()
            el = (l[76:78].strip() or re.sub(r"[^A-Za-z]", "", name)[:1]).upper()
            out.append((l[21], int(l[22:26]), l[17:20].strip(), name, el, float(l[30:38]), float(l[38:46]), float(l[46:54])))
    return out


class Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cur, self.cell, self.intable = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cur = []
        elif tag == "td" and self.cur is not None:
            self.cell = ""

    def handle_endtag(self, tag):
        if tag == "td" and self.cur is not None and self.cell is not None:
            self.cur.append(self.cell.strip())
            self.cell = None
        elif tag == "tr" and self.cur is not None:
            if self.cur:
                self.rows.append(self.cur)
            self.cur = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell += d


def side_table(html_path):
    t = Table()
    t.feed(open(html_path, encoding="utf-8").read())
    return [r for r in t.rows if len(r) == 6]


def mvs_sets(root):
    """{'ball': {(chain,res)}, 'layer': {'protein'|'nucleic': {(chain,res)}}} from one MolViewSpec snapshot root."""
    ball, layer = set(), {}

    def walk(n, comp_sel=None):
        if n.get("kind") == "component":
            comp_sel = n["params"]["selector"]
        if n.get("kind") == "representation" and n["params"]["type"] == "ball_and_stick" and isinstance(comp_sel, list):
            ball.update((x["auth_asym_id"], x["auth_seq_id"]) for x in comp_sel)
        if n.get("kind") == "representation" and n["params"]["type"] == "cartoon" and isinstance(comp_sel, str):
            for c in n.get("children", []):
                if c.get("kind") == "color" and isinstance(c["params"].get("selector"), list):
                    layer.setdefault(comp_sel, set()).update((x["auth_asym_id"], x["auth_seq_id"]) for x in c["params"]["selector"])
        for c in n.get("children", []):
            walk(c, comp_sel)
    walk(root)
    return {"ball": ball, "layer": layer}


def molstar_sets(snap):
    """Same from a render.js snapshot record (Mol*'s own state): ball-and-stick residues; cartoon colour-layer residues."""
    ball, layer, ok = set(), {}, True
    st = snap["structures"][0]
    for c in st["components"]:
        for r in c["representations"]:
            if r["type"] == "ball-and-stick":
                ball.update((x[0], x[1]) for x in c["residues"])
            if r["type"] == "cartoon" and c["label"] in ("Protein", "Nucleic") and r["color"] == "mvs-multilayer":
                for L in json.loads(r["color_params"])["layers"]:
                    sel = L["selection"]
                    if sel["name"] == "static":
                        continue
                    got = set()
                    for u in sel["params"]["args"]:
                        g = u["args"][0]["args"]
                        got.add((g["chain-test"]["args"][1], g["residue-test"]["args"][1]))
                    layer.setdefault("protein" if c["label"] == "Protein" else "nucleic", set()).update(got)
    return {"ball": ball, "layer": layer, "ok": ok}


def check_page(pg):
    pkg = pg["package"]
    vdir = os.path.join(pkg, pg["viewer_dir"])
    proj, ana = os.path.join(pkg, "project"), os.path.join(pkg, "analysis")
    man = json.load(open(os.path.join(proj, "manifest.json")))
    cbo = json.load(open(os.path.join(ana, "report", "contacts_by_output.json")))
    ps, rs = fasta(os.path.join(proj, "construct_protein.fasta")), fasta(os.path.join(proj, "construct_rna.fasta"))
    rng, region = None, None
    if pg["range_mode"] == "region_rule_log":
        last = [l.strip() for l in open(os.path.join(pkg, "logs", "03_region_rule.log")) if l.strip()][-1]
        rng = tuple(int(x) for x in last.split("-"))
        region = json.load(open(os.path.join(ana, "region_%d-%d" % rng, "region.json")))
    ids = None
    if pg.get("representatives_threshold"):
        g = json.load(open(os.path.join(ana, "groups", "groups.json")))
        ids = {x["representative"]["id"]: x["group"] for x in g["thresholds"][pg["representatives_threshold"]]["groups"]}
    vman = json.load(open(os.path.join(vdir, "viewer_manifest.json")))
    mvs = json.load(open(os.path.join(vdir, "view.mvsj")))
    snaps = mvs["snapshots"] if mvs.get("kind") == "multiple" else [{"root": mvs["root"], "metadata": {"title": vman["structures"][0]["label"]}}]
    table = side_table(os.path.join(vdir, "viewer.html"))
    ms = None
    if pg.get("molstar_result"):
        ms = json.load(open(pg["molstar_result"]))
    # R2: per-structure pairs from region.json
    r2 = {}
    region_unresolved = {}
    if region:
        for c in region["contacts"]:
            for run, pr in c["per_run"].items():
                with_ids = [w["id"] for w in pr["structures"]["with_contact"]]
                d = pr.get("designated") or {}
                if d.get("observation") == "PRESENT" and d.get("structure"):
                    with_ids.append(d["structure"])
                for sid in set(with_ids):
                    r2.setdefault(sid, set()).add((c["protein_position"], c["rna_position"]))
        for run in region["runs"]:
            for s in run["structures"]:
                region_unresolved[s["id"]] = set(s["coverage"].get("unresolved_rna_positions") or [])
    out = {"page_id": pg["page_id"], "range": rng, "structures": [], "discrepancies": []}
    shown = [s for s in man["structures"] if s.get("verdict") == "INCLUDED" and (ids is None or s["id"] in ids)]
    page_labels = [sn["metadata"]["title"] for sn in snaps]
    exp_labels = ["%s %s#%s" % (s["id"], s["run"], s["sample"]) for s in shown]
    if page_labels != exp_labels:
        out["discrepancies"].append({"what": "structures on page differ from the expected list", "page": page_labels, "expected": exp_labels})
    for i, s in enumerate(shown):
        label = exp_labels[i]
        key = "%s|%s#%s" % (s["engine"], s["run"], s["sample"])
        ch = {c["type_by_report"]: c for c in s["chains"] if c.get("status") != "NONPOLYMER_CHAIN"}
        pc, rc = ch["protein"]["chain"], ch["rna"]["chain"]
        pairs = {(p, r) for p, r in cbo[key] if rng is None or rng[0] <= r <= rng[1]}
        R1 = {"protein": {p for p, _ in pairs}, "rna": {r for _, r in pairs}}
        rec = {"id": s["id"], "label": label, "key": key, "group": ids[s["id"]] if ids else None,
               "chains": {"protein": pc, "rna": rc}, "n_contact_pairs": len(pairs),
               "expected": {"protein": sorted(R1["protein"]), "rna": sorted(R1["rna"])}, "comparisons": {}}
        cmp = rec["comparisons"]

        def put(name, got_p, got_r):
            eq = got_p == R1["protein"] and got_r == R1["rna"]
            cmp[name] = {"equal": eq}
            if not eq:
                cmp[name].update({"protein_missing": sorted(R1["protein"] - got_p), "protein_extra": sorted(got_p - R1["protein"]),
                                  "rna_missing": sorted(R1["rna"] - got_r), "rna_extra": sorted(got_r - R1["rna"])})
                out["discrepancies"].append({"structure": label, "source": name, **cmp[name]})
        if region:
            got = r2.get(s["id"], set())
            cmp["R2_region_record_pairs"] = {"equal": got == pairs, "n": len(got)}
            if got != pairs:
                cmp["R2_region_record_pairs"].update({"missing": sorted(pairs - got)[:50], "extra": sorted(got - pairs)[:50]})
                out["discrepancies"].append({"structure": label, "source": "R2_region_record_pairs", **cmp["R2_region_record_pairs"]})
        idx = page_labels.index(label) if label in page_labels else None
        V1 = mvs_sets(snaps[idx]["root"]) if idx is not None else {"ball": set(), "layer": {}}
        sel = lambda S_, chn: {r for c, r in S_ if c == chn}
        chain_ok = all(c in (pc, rc) for c, _ in V1["ball"])
        put("V1_mvs_ball_and_stick", sel(V1["ball"], pc), sel(V1["ball"], rc))
        put("V1_mvs_cartoon_highlight_layer", sel(V1["layer"].get("protein", set()), pc), sel(V1["layer"].get("nucleic", set()), rc))
        hv = [h for h in vman["highlighted"] if h["structure_label"] == label]
        put("V2_viewer_manifest", {h["residue"] for h in hv if h["molecule"] == "protein" and h["chain_resolved"] == pc},
            {h["residue"] for h in hv if h["molecule"] == "rna" and h["chain_resolved"] == rc})
        tv = [t for t in table if t[0] == label]
        put("V3_side_table", {int(t[3]) for t in tv if t[1] == "protein" and t[2] == pc}, {int(t[3]) for t in tv if t[1] == "rna" and t[2] == rc})
        if ms is not None:
            snap = next((x for x in ms["snapshots"] if x["name"] == label), None)
            if snap is None:
                out["discrepancies"].append({"structure": label, "source": "V4_molstar", "what": "snapshot not found"})
            else:
                V4 = molstar_sets(snap)
                put("V4_molstar_ball_and_stick", sel(V4["ball"], pc), sel(V4["ball"], rc))
                put("V4_molstar_cartoon_highlight_layer", sel(V4["layer"].get("protein", set()), pc), sel(V4["layer"].get("nucleic", set()), rc))
        if not chain_ok:
            out["discrepancies"].append({"structure": label, "source": "V1", "what": "highlight on a chain other than the declared ones"})
        # structure copy on the page
        copy = next(x["copy"] for x in vman["structures"] if x["label"] == label)
        atoms = pdb_atoms(os.path.join(vdir, copy))
        resn = {}
        for a in atoms:
            resn.setdefault((a[0], a[1]), a[2])
        rec["structure_copy"] = {"file": copy, "chains": sorted({a[0] for a in atoms}),
                                 "n_rna_residues": len([k for k in resn if k[0] == rc]), "n_protein_residues": len([k for k in resn if k[0] == pc])}
        if region:
            prot = [(a[5], a[6], a[7]) for a in atoms if a[0] == pc and a[4] != "H"]
            numbering = ch["rna"].get("numbering") or {}
            srcs = {"V1_ball": {r for c, r in V1["ball"] if c == rc}, "V1_layer": {r for c, r in V1["layer"].get("nucleic", set()) if c == rc},
                    "V2": {h["residue"] for h in hv if h["molecule"] == "rna" and h["chain_resolved"] == rc},
                    "V3": {int(t[3]) for t in tv if t[1] == "rna" and t[2] == rc}}
            if ms is not None and snap is not None:
                srcs.update({"V4_ball": {r for c, r in V4["ball"] if c == rc}, "V4_layer": {r for c, r in V4["layer"].get("nucleic", set()) if c == rc}})
            positions = []
            for p in range(rng[0], rng[1] + 1):
                present = (rc, p) in resn and resn[(rc, p)] in NUC
                in_map = numbering.get("first", 1) <= p <= numbering.get("last", 10 ** 9) and p not in region_unresolved.get(s["id"], set())
                nat = [(a[5], a[6], a[7]) for a in atoms if a[0] == rc and a[1] == p and a[4] != "H"]
                dmin = min((math.dist(x, y) for x in nat for y in prot), default=None)
                in_rec = p in R1["rna"]
                hl_every = all(p in v for v in srcs.values())
                hl_any = any(p in v for v in srcs.values())
                hl = hl_every
                if in_rec:
                    cls = "HIGHLIGHTED" if hl_every else "OMITTED_BY_VIEWER"
                elif hl_any:
                    cls = "HIGHLIGHTED_WITHOUT_RECORD"
                elif not present or not in_map:
                    cls = "ABSENT_FROM_STRUCTURE_OR_MAPPING"
                else:
                    cls = "NO_QUALIFYING_CONTACT"
                geo = None if dmin is None else ("within" if dmin <= CUTOFF else "beyond")
                agree = None if dmin is None else ((geo == "within") == in_rec)
                positions.append({"position": p, "construct_nucleotide": rs[p - 1], "structure_residue": resn.get((rc, p)),
                                  "in_mapping": in_map, "in_record": in_rec, "highlighted": hl, "highlighted_in_sources": sorted(k for k, v in srcs.items() if p in v), "class": cls,
                                  "min_heavy_atom_distance_A": None if dmin is None else round(dmin, 3), "geometry_agrees_with_record": agree})
                if cls in ("OMITTED_BY_VIEWER", "HIGHLIGHTED_WITHOUT_RECORD"):
                    out["discrepancies"].append({"structure": label, "source": "position", "position": p, "class": cls})
                if agree is False:
                    out["discrepancies"].append({"structure": label, "source": "independent_geometry", "position": p,
                                                 "min_distance": round(dmin, 3), "in_record": in_rec})
            rec["region_positions"] = positions
        out["structures"].append(rec)
    out["summary"] = {"n_structures": len(out["structures"]), "n_discrepancies": len(out["discrepancies"]),
                      "all_sets_equal": all(c["equal"] for s in out["structures"] for c in s["comparisons"].values()),
                      "molstar_compared": ms is not None}
    return out


def main(argv):
    pages = json.load(open(argv[0]))
    res = {"record": "rnplens-viewer-highlight-coverage-1", "cutoff_A": CUTOFF, "pages": [check_page(p) for p in pages]}
    with open(argv[1], "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    for p in res["pages"]:
        print(p["page_id"], json.dumps(p["summary"]))


if __name__ == "__main__":
    main(sys.argv[1:])
