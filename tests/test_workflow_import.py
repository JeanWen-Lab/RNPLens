"""0.3 workflow: rnplens import (layouts, chain correspondence, confirmation, derived copies, originals untouched)."""
import json
import os
import shutil

import gemmi
import pytest

from rnplens import importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PRED = os.path.join(EX, "reference_based", "7K9D_prediction.pdb")
PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))


def _imp(paths, out, **kw):
    return importer.run([str(p) for p in paths], PS, RS, str(out), **kw)


def _man(out):
    return json.load(open(os.path.join(out, "manifest.json")))


def _write(st, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    st.write_pdb(str(path))


def _boltz_layout(tmp, n=3):
    d = tmp / "run1" / "boltz_results_X" / "predictions" / "X"
    d.mkdir(parents=True)
    for k in range(n):
        shutil.copy(PRED, d / ("X_model_%d.pdb" % k))
        with open(d / ("X_model_%d.pdb" % k), "a") as fh:
            fh.write("REMARK distinct copy %d\n" % k)
        json.dump({"confidence_score": 0.9 - 0.1 * k, "iptm": 0.8}, open(d / ("confidence_X_model_%d.json" % k), "w"))
    return tmp / "run1"


def _sha_tree(p):
    return {f: importer.sha256(os.path.join(dp, f)) for dp, _, fs in os.walk(p) for f in fs}


def test_boltz_layout_designated_and_originals_untouched(tmp_path):
    src = _boltz_layout(tmp_path)
    before = _sha_tree(src)
    os.chmod(src, 0o755)
    assert _imp([src], tmp_path / "p") == 0
    m = _man(tmp_path / "p")
    assert m["counts"]["included"] == 3
    assert [s["designated"] for s in m["structures"]] == [True, False, False]
    assert all(s["used_path"] == s["path"] and s["derived"] is None for s in m["structures"])
    assert _sha_tree(src) == before
    c = json.load(open(tmp_path / "p" / "report_contract.json"))
    assert [o["sha256"] for o in c["outputs"]] == [importer.sha256(o["structure_path"]) for o in c["outputs"]]
    assert all(o["structure_path"].startswith(str(src)) for o in c["outputs"])   # originals, not copies


def test_refuses_existing_output(tmp_path):
    (tmp_path / "p").mkdir()
    assert _imp([_boltz_layout(tmp_path)], tmp_path / "p") == importer.EXIT_REFUSED


def test_unrecognised_layout_is_listed_not_guessed(tmp_path):
    shutil.copy(PRED, tmp_path / "loose.pdb")
    # nothing includable: refused with a non-zero exit and nothing written (0.3 first-use test, M1/m9)
    assert _imp([tmp_path / "loose.pdb"], tmp_path / "p") == importer.EXIT_REFUSED
    assert not (tmp_path / "p").exists()
    assert _imp([tmp_path / "loose.pdb"], tmp_path / "q", engine="BOLTZ2") == 0
    assert _man(tmp_path / "q")["counts"]["included"] == 1


def test_af3_style_layout_asks_for_the_engine(tmp_path):
    root = tmp_path / "out" / "T"
    for k in range(2):
        d = root / ("seed-1_sample-%d" % k); d.mkdir(parents=True)
        st = gemmi.read_structure(PRED); st.setup_entities()
        for m in st:
            for ch in m:
                for r in ch:
                    for a in r:
                        a.pos = gemmi.Position(a.pos.x + k, a.pos.y, a.pos.z)
        st.make_mmcif_document().write_file(str(d / ("T_seed-1_sample-%d_model.cif" % k)))
        json.dump({"ranking_score": 0.5 + k}, open(d / ("T_seed-1_sample-%d_summary_confidences.json" % k), "w"))
    shutil.copy(root / "seed-1_sample-1" / "T_seed-1_sample-1_model.cif", root / "T_model.cif")
    assert _imp([tmp_path / "out"], tmp_path / "p") == importer.EXIT_NEEDS_CONFIRMATION
    q = json.load(open(tmp_path / "p" / "QUESTIONS.json"))
    key = [k for k in q["answers"] if k.startswith("engine:")][0]
    assert _imp([tmp_path / "out"], tmp_path / "p2", answers={key: "RF3"}) == 0
    m = _man(tmp_path / "p2")
    assert m["counts"]["included"] == 2 and {s["engine"] for s in m["structures"]} == {"RF3"}
    assert [s["designated"] for s in m["structures"]] == [False, True]
    assert m["decisions"][0]["verified"] is True       # top-level copy equals the designated sample


def test_offset_needs_acceptance_and_derived_copy_verifies(tmp_path):
    st = gemmi.read_structure(PRED)
    for r in st[0]["A"]:
        r.seqid = gemmi.SeqId(r.seqid.num + 10, " ")
    _write(st, tmp_path / "in" / "shifted.pdb")
    orig = importer.sha256(tmp_path / "in" / "shifted.pdb")
    assert _imp([tmp_path / "in"], tmp_path / "p", engine="OTHER") == importer.EXIT_NEEDS_CONFIRMATION
    assert _imp([tmp_path / "in"], tmp_path / "p2", engine="OTHER", accept_derived=True) == 0
    s = _man(tmp_path / "p2")["structures"][0]
    assert s["verdict"] == "INCLUDED" and s["derived"]["from_sha256"] == orig
    assert [c["status"] for c in s["chains"]] == ["RENUMBER", "EXACT"] and s["chains"][0]["offset"] == 10
    assert importer.sha256(tmp_path / "in" / "shifted.pdb") == orig
    post = importer.examine_chains(s["used_path"], PS, RS)
    assert [c["status"] for c in post] == ["EXACT", "EXACT"]


def test_point_substitution_is_reported_never_corrected(tmp_path):
    st = gemmi.read_structure(PRED)
    r = st[0]["A"][5]; r.name = "TRP" if r.name != "TRP" else "ALA"
    _write(st, tmp_path / "in" / "mut.pdb")
    shutil.copy(PRED, tmp_path / "in" / "zz_ok.pdb")       # one includable file: an all-excluded import is refused
    assert _imp([tmp_path / "in"], tmp_path / "p", engine="OTHER", accept_derived=True) == 0
    s = [x for x in _man(tmp_path / "p")["structures"] if x["path"].endswith("mut.pdb")][0]
    assert s["verdict"] == "INCOMPATIBLE"
    al = [c for c in s["chains"] if c["chain"] == "A"][0]["alignment"]
    assert al["substitutions"] == 1 and al["identity_over_construct"] < 1


def test_extra_ligand_chain_is_listed_and_removed_only_in_a_derived_copy(tmp_path):
    st = gemmi.read_structure(PRED)
    ch = gemmi.Chain("Z"); res = gemmi.Residue(); res.name = "ZN"; res.seqid = gemmi.SeqId(1, " "); res.het_flag = "H"
    at = gemmi.Atom(); at.name = "ZN"; at.element = gemmi.Element("Zn"); at.pos = gemmi.Position(0, 0, 0); res.add_atom(at)
    ch.add_residue(res); st[0].add_chain(ch)
    _write(st, tmp_path / "in" / "lig.pdb")
    assert _imp([tmp_path / "in"], tmp_path / "p", engine="OTHER", accept_derived=True) == 0
    s = _man(tmp_path / "p")["structures"][0]
    assert any(c["status"] == "NONPOLYMER_CHAIN" for c in s["chains"]) and s["derived"] and s["verdict"] == "INCLUDED"


def test_uncertain_chain_type_stops_with_a_question(tmp_path):
    st = gemmi.read_structure(PRED)
    for i, r in enumerate(st[0]["A"]):
        if i % 3 == 0:
            r.name = "A"
    _write(st, tmp_path / "in" / "mixed.pdb")
    shutil.copy(PRED, tmp_path / "in" / "zz_ok.pdb")       # one includable file: an all-excluded import is refused
    assert _imp([tmp_path / "in"], tmp_path / "p", engine="OTHER") == importer.EXIT_NEEDS_CONFIRMATION
    q = json.load(open(tmp_path / "p" / "QUESTIONS.json"))
    key = [k for k in q["answers"] if k.startswith("chains:")][0]
    assert _imp([tmp_path / "in"], tmp_path / "p2", engine="OTHER", answers={key: "exclude_file"}) == 0
    assert [x for x in _man(tmp_path / "p2")["structures"] if x["path"].endswith("mixed.pdb")][0]["verdict"] == "EXCLUDED_BY_USER"
    # excluding the only file leaves nothing to import: refused, nothing written
    os.remove(tmp_path / "in" / "zz_ok.pdb")
    assert _imp([tmp_path / "in"], tmp_path / "p3", engine="OTHER", answers={key: "exclude_file"}) == importer.EXIT_REFUSED
    assert not (tmp_path / "p3").exists()


def test_duplicate_file_counted_once(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    shutil.copy(PRED, tmp_path / "a" / "m.pdb"); shutil.copy(PRED, tmp_path / "b" / "m.pdb")
    assert _imp([tmp_path / "a", tmp_path / "b"], tmp_path / "p", engine="OTHER") == 0
    v = [s["verdict"] for s in _man(tmp_path / "p")["structures"]]
    assert sorted(v) == ["DUPLICATE", "INCLUDED"]
