"""Regression for the viewer-track finding (records/viewer/MOLSTAR_VISUAL_VERIFICATION.md): a highlighted residue's
ribbon is coloured inside its molecule's single cartoon by a MolViewSpec colour node with a selector, and no second
cartoon is drawn over it (a second, coincident cartoon rendered in the molecule colour in Mol* 5.13.1)."""
import json
import os

import pytest

from rnplens import analyse, importer, viewer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    t = tmp_path_factory.mktemp("viewer_colour")
    ps = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
    rs = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], ps, rs, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(str(t / "p"), str(t / "a")) == 0
    st = viewer.project_structures(str(t / "p"))
    for s in st:
        s["highlights"] = viewer.contact_highlights(str(t / "a"), s["key"], ps, rs, rna_range=(15, 30))
    res = viewer.structure_page(str(t / "a" / "v"), [{k: s[k] for k in ("path", "label", "chains", "highlights")} for s in st])
    mvs = json.load(open(os.path.join(os.path.dirname(res["page"]), "view.mvsj")))
    return t, st, mvs


def _components(root):
    out = []

    def walk(n):
        if n.get("kind") == "component":
            out.append(n)
        for c in n.get("children", []):
            walk(c)
    walk(root)
    return out


def _reps(comp, kind):
    return [c for c in comp.get("children", []) if c.get("kind") == "representation" and c["params"]["type"] == kind]


def test_highlight_colour_is_a_selector_layer_of_the_single_cartoon(page):
    t, st, mvs = page
    rec = json.load(open(t / "a" / "report" / "contacts_by_output.json"))
    for s, snap in zip(st, mvs["snapshots"]):
        pairs = [(p, r) for p, r in rec[s["key"]] if 15 <= r <= 30]
        want = {"protein": sorted({p for p, _ in pairs}), "nucleic": sorted({r for _, r in pairs})}
        chains = {"protein": s["chains"]["protein"], "nucleic": s["chains"]["rna"]}
        comps = _components(snap["root"])
        cartoons = [(c, r) for c in comps for r in _reps(c, "cartoon")]
        assert [c["params"]["selector"] for c, _ in cartoons] == ["protein", "nucleic"]     # one cartoon per molecule
        for (c, rep), base, hl in zip(cartoons, ("#BBBBBB", "#DDCC77"), ("#E69F00", "#0072B2")):
            mol = c["params"]["selector"]
            colours = [k["params"] for k in rep["children"] if k["kind"] == "color"]
            assert colours[0] == {"color": base}
            assert len(colours) == 2 and colours[1]["color"] == hl
            assert [x["auth_seq_id"] for x in colours[1]["selector"]] == want[mol]
            assert {x["auth_asym_id"] for x in colours[1]["selector"]} == {chains[mol]}
        # highlight components draw ball-and-stick only
        for c in comps:
            if isinstance(c["params"]["selector"], list):
                assert _reps(c, "cartoon") == [] and len(_reps(c, "ball_and_stick")) == 1


def test_no_highlights_leaves_one_plain_colour(page, tmp_path):
    t, st, mvs = page
    viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": "only"}])
    m = json.load(open(tmp_path / "o" / "view.mvsj"))
    for c in _components(m["root"]):
        for r in _reps(c, "cartoon"):
            assert [k["params"] for k in r["children"] if k["kind"] == "color"] in ([{"color": "#BBBBBB"}], [{"color": "#DDCC77"}])


def test_only_protein_highlights_colour_only_the_protein_cartoon(page, tmp_path):
    t, st, mvs = page
    viewer.structure_page(str(tmp_path / "o"), [{"path": st[0]["path"], "label": "p", "chains": st[0]["chains"],
                                                 "highlights": {"protein": [{"residue": 14}, {"residue": 40}]}}])
    m = json.load(open(tmp_path / "o" / "view.mvsj"))
    cart = {c["params"]["selector"]: r for c in _components(m["root"]) for r in _reps(c, "cartoon")}
    assert [k["params"]["color"] for k in cart["protein"]["children"]] == ["#BBBBBB", "#E69F00"]
    assert [k["params"]["color"] for k in cart["nucleic"]["children"]] == ["#DDCC77"]
