"""Contact explorer of the offline viewer (rnplens view; feature/nt-contact-explorer).

The explorer's contacts are Report's per-structure record; distances are recomputed and shown only when the
recomputed contact set equals that record. These tests use the bundled 7K9D example (development target) and
fixtures derived from its structure copy: a modified nucleotide, author numbering with an insertion code, a missing
residue, a second RNA chain, and a deliberately altered record (distance check must fail and hide distances)."""
import json
import os
import re

import numpy as np
import pytest
from Bio.PDB import PDBIO, PDBParser

from rnplens import analyse, contact_explorer as CE, importer, trace, viewer
from rnpbench_report import geometry as G

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))
URL = re.compile(r"(?i)\b(?:https?|ftp|wss?):|//[a-z0-9.-]+\.[a-z]{2,}")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    t = tmp_path_factory.mktemp("ntc")
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(str(t / "p"), str(t / "a")) == 0
    st = viewer.project_structures(str(t / "p"))
    cbo = json.load(open(t / "a" / "report" / "contacts_by_output.json"))
    return t, st, cbo


def brute(path, pc, rc):
    """Independent minimum heavy-atom distance per residue pair (plain loops over Biopython atoms)."""
    m = PDBParser(QUIET=True).get_structure("x", path)[0]
    P = [x for x in m[pc] if x.id[0] != "W"]
    R = [x for x in m[rc] if x.id[0] != "W"]
    ra = [(j + 1, np.asarray(a.coord, dtype=float)) for j, x in enumerate(R) for a in x if a.element != "H"]
    out = {}
    for i, x in enumerate(P):
        for a in x:
            if a.element == "H":
                continue
            c = np.asarray(a.coord, dtype=float)
            for j, b in ra:
                d = float(np.sqrt(((c - b) ** 2).sum()))
                if d < out.get((i + 1, j), 1e9):
                    out[(i + 1, j)] = d
    return out


def test_record_reproduces_reports_contacts_and_distances(proj):
    t, st, cbo = proj
    for s in st:
        rec = CE.structure_record(s["path"], s["chains"], cbo[s["key"]], s["key"], s["id"], "BOLTZ2", (len(PS), len(RS)))
        assert rec["available"] and rec["distance_check"]["status"] == "PASS"
        assert {(c["p"], c["r"]) for c in rec["contacts"]} == {tuple(x) for x in cbo[s["key"]]}
        assert len(rec["contacts"]) == len(cbo[s["key"]])                       # one chain pair: one row per Report pair
        assert [r[0] for r in rec["residues"]["B"]] == list(range(1, len(RS) + 1))
        assert [r[0] for r in rec["residues"]["A"]] == list(range(1, len(PS) + 1))
        b = brute(s["path"], "A", "B")
        assert {k for k, d in b.items() if d <= G.CONTACT_CUTOFF_A} == {tuple(x) for x in cbo[s["key"]]}
        for c in rec["contacts"]:
            assert c["d"] <= G.CONTACT_CUTOFF_A and abs(c["d"] - b[(c["p"], c["r"])]) <= 0.005 + 1e-9
            assert c["pa"] and c["ra"] and len(c["pxyz"]) == 3 and len(c["rxyz"]) == 3
            assert abs(float(np.linalg.norm(np.subtract(c["pxyz"], c["rxyz"]))) - c["d"]) <= 0.01
            assert c["eid"].startswith("report/contacts_by_output.json#/")


def test_per_nucleotide_counts_and_empty_nucleotides(proj):
    t, st, cbo = proj
    s = st[0]
    rec = CE.structure_record(s["path"], s["chains"], cbo[s["key"]], s["key"], s["id"], "BOLTZ2", (len(PS), len(RS)))
    for r in range(1, len(RS) + 1):
        want = sorted({p for p, q in cbo[s["key"]] if q == r})
        got = sorted({c["p"] for c in rec["contacts"] if c["r"] == r and c["rc"] == "B"})
        assert got == want
    assert not [c for c in rec["contacts"] if c["r"] == 5]                     # nucleotide 5: no qualifying contact


def _rewrite(src, dst, edit):
    s = PDBParser(QUIET=True).get_structure("x", src)
    edit(s[0])
    io = PDBIO(); io.set_structure(s); io.save(str(dst))
    return str(dst)


def test_modified_nucleotide_and_author_numbering_with_insertion_code(tmp_path, proj):
    t, st, cbo = proj
    s = st[0]

    def edit(m):
        ch = m["B"]
        res = list(ch)
        for x in res:
            ch.detach_child(x.id)
        for i, x in enumerate(res):
            num = 100 + i if i < 10 else 99 + i          # construct 10 -> 109, 11 -> 109A (same number), 18 -> 116 (PSU)
            x.id = (("H_PSU" if i == 17 else " "), num, "A" if i == 10 else " ")
            if i == 17:
                x.resname = "PSU"
            ch.add(x)
    f = _rewrite(s["path"], tmp_path / "mod.pdb", edit)
    prot, rna, _ = G.split_chains(G.parse_model(f))
    pairs = G.interface_contacts(prot, rna)[0]                                   # Report's own function, read-only
    assert {tuple(x) for x in pairs} == {tuple(x) for x in cbo[s["key"]]}       # same atoms, so same index pairs
    rec = CE.structure_record(f, s["chains"], [list(x) for x in pairs], "fixture", "fx", "BOLTZ2", (len(PS), len(RS)))
    assert rec["available"] and rec["distance_check"]["status"] == "PASS"
    b = {r[0]: r for r in rec["residues"]["B"]}
    assert b[18][1:4] == [116, "", "PSU"] and b[18][4] is True                # construct 18 = structure B 116, PSU, HETATM
    assert b[10][1:3] == [109, ""] and b[11][1:3] == [109, "A"] and b[12][1:3] == [110, ""]
    assert b[1][1] == 100
    out = viewer.structure_page(str(tmp_path / "page"), [{"path": f, "label": "fixture", "chains": s["chains"], "explorer": rec}],
                                explorer={"seq": {"protein": PS, "rna": RS}, "ensemble": None})
    V = json.loads(open(tmp_path / "page" / "view_data.js").read().split("=", 1)[1].rstrip().rstrip(";"))
    assert V["explorer"]["structures"][0]["rec"]["residues"]["B"][17][3] == "PSU"
    assert os.path.isfile(tmp_path / "page" / "assets" / "contact_explorer.js")
    assert "assets/contact_explorer.js" in json.load(open(out["manifest"]))["files"]


def test_missing_residue_gives_no_correspondence(tmp_path, proj):
    t, st, cbo = proj
    s = st[0]
    f = _rewrite(s["path"], tmp_path / "gap.pdb", lambda m: m["B"].detach_child(list(m["B"])[9].id))
    rec = CE.structure_record(f, s["chains"], cbo[s["key"]], s["key"], "fx", "BOLTZ2", (len(PS), len(RS)))
    assert not rec["available"] and "construct positions cannot be assigned" in rec["reason"]
    assert rec["residues"] == {} and rec["contacts"] == []
    rec2 = CE.structure_record(s["path"], s["chains"], None, s["key"], "fx", "BOLTZ2", (len(PS), len(RS)))
    assert not rec2["available"] and "no contact record" in rec2["reason"] and rec2["residues"]


def test_second_rna_chain_rows_carry_their_chain(tmp_path, proj):
    t, st, cbo = proj
    s = st[0]

    def edit(m):
        c = m["B"].copy(); c.id = "C"; m.add(c)
    f = _rewrite(s["path"], tmp_path / "two.pdb", edit)
    prot, rna, _ = G.split_chains(G.parse_model(f))
    pairs = G.interface_contacts(prot, rna)[0]
    rec = CE.structure_record(f, {"protein": "A", "rna": ["B", "C"]}, [list(x) for x in pairs], "fx", "fx", "BOLTZ2", (len(PS), len(RS)))
    assert rec["distance_check"]["status"] == "PASS"
    assert {c["rc"] for c in rec["contacts"]} == {"B", "C"}
    assert len(rec["contacts"]) == 2 * len(pairs)
    with pytest.raises(viewer.ViewerError, match="2 protein and 1 RNA|1 protein and 2 RNA"):   # the project route still refuses
        man = json.load(open(t / "p" / "manifest.json"))
        man["structures"][0]["chains"].append(dict([c for c in man["structures"][0]["chains"] if c.get("type_by_report") == "rna"][0], chain="C"))
        q = tmp_path / "pq"; q.mkdir(); (q / "manifest.json").write_text(json.dumps(man))
        viewer.project_structures(str(q))


def test_altered_record_fails_the_distance_check_and_hides_distances(proj):
    t, st, cbo = proj
    s = st[0]
    alt = [list(x) for x in cbo[s["key"]][1:]] + [[1, 1]]
    rec = CE.structure_record(s["path"], s["chains"], alt, s["key"], s["id"], "BOLTZ2", (len(PS), len(RS)))
    dc = rec["distance_check"]
    assert dc["status"] == "FAIL" and dc["only_in_report"] == [[1, 1]] and dc["only_recomputed"] == [list(cbo[s["key"]][0])]
    assert all(c["d"] is None and c["pxyz"] is None for c in rec["contacts"])
    assert {(c["p"], c["r"]) for c in rec["contacts"]} == {tuple(x) for x in alt}   # Report's record is shown as it is
    assert "distances are not shown" in rec["reason_distances"]


def test_ensemble_keeps_engines_apart():
    cbo = {"BOLTZ2|r#a": [[1, 2], [3, 4]], "BOLTZ2|r#b": [[1, 2]], "AF3|r#c": [[1, 2]]}
    e = CE.ensemble(cbo, {"BOLTZ2|r#a": "s1", "BOLTZ2|r#b": "s2", "AF3|r#c": "s3"})
    assert e["BOLTZ2"]["n"] == 2 and e["AF3"]["n"] == 1
    assert [e["BOLTZ2"]["ids"][k] for k in e["BOLTZ2"]["pair"]["1-2"]] == ["s1", "s2"]
    assert e["AF3"]["pair"]["1-2"] == [0] and "3-4" not in e["AF3"]["pair"]
    assert len(e["BOLTZ2"]["rna"]["4"]) == 1 and len(e["BOLTZ2"]["protein"]["1"]) == 2


def test_view_command_page_carries_explorer_and_passes_audits(proj, tmp_path):
    t, st, cbo = proj
    assert viewer.main([str(t / "p"), "--analysis", str(t / "a"), "--rna", "15-30", "--out", str(tmp_path / "v")]) == 0
    html = open(tmp_path / "v" / "viewer.html", encoding="utf-8").read()
    js = open(tmp_path / "v" / "assets" / "contact_explorer.js", encoding="utf-8").read()
    assert trace.wording_audit(html) == [] and trace.wording_audit(js) == []
    assert not URL.search(js) and not URL.search(html)
    for needed in ('id="rx-clear"', 'value="focus"', 'value="all"', 'id="rx-structure"', 'id="rnplens-explorer"',
                   "Clear selection", "Show all contacts", "Focus on selected nucleotide", viewer.STATUS.split(";")[0]):
        assert needed in html
    V = json.loads(open(tmp_path / "v" / "view_data.js").read().split("=", 1)[1].rstrip().rstrip(";"))
    X = V["explorer"]
    assert [s["rec"]["key"] for s in X["structures"]] == [s["key"] for s in st]
    assert X["ensemble"]["BOLTZ2"]["n"] == len(cbo) and X["cutoff"] == G.CONTACT_CUTOFF_A
    for s in X["structures"]:
        assert s["rec"]["chains"] == {"protein": ["A"], "rna": ["B"]}           # chain identity from the manifest
        assert {(c["p"], c["r"]) for c in s["rec"]["contacts"]} == {tuple(x) for x in cbo[s["rec"]["key"]]}
        assert all(15 <= x["residue"] <= 30 for x in s["overview"]["rna"])
    man = json.load(open(tmp_path / "v" / "viewer_manifest.json"))
    assert [x["distance_check"]["status"] for x in man["contact_explorer"]["structures"]] == ["PASS", "PASS"]


def test_explorer_record_is_validated(tmp_path, proj):
    t, st, cbo = proj
    with pytest.raises(viewer.ViewerError, match="explorer must be a record"):
        viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": "a", "explorer": {"x": 1}}])
