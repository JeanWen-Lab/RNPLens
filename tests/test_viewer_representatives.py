"""rnplens view: --ids keeps the order given, and --representatives T shows each binding-proposal group's
representative in the groups' display order, labelled with its group, plus every engine-designated structure that is
not a representative (QA track outside-user-viewer, finding U1, 2026-10-18). The default page is unchanged."""
import json
import os

import pytest

from rnplens import cli, viewer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    t = tmp_path_factory.mktemp("view_reps")
    P, A = str(t / "p"), str(t / "a")
    assert cli.main(["import", os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B"), "--protein-seq",
                     os.path.join(EX, "reference_based", "7K9D_protein.fasta"), "--rna-seq",
                     os.path.join(EX, "reference_based", "7K9D_rna.fasta"), "--out", P, "--case-id", "v",
                     "--engine", "BOLTZ2"]) == 0
    assert cli.main(["analyse", P, "--out", A]) == 0
    return t, P, A


def _titles(page_dir):
    txt = open(os.path.join(page_dir, "view_data.js"), encoding="utf-8").read()
    V = json.loads(txt.split("=", 1)[1].strip().rstrip(";"))
    return [s["metadata"]["title"] for s in V["mvs"]["snapshots"]]


def test_default_page_lists_structures_in_manifest_order_with_plain_labels(proj):
    t, P, A = proj
    assert viewer.main([P, "--analysis", A, "--out", str(t / "v_default")]) == 0
    ti = _titles(str(t / "v_default"))
    assert [x.split()[0] for x in ti] == ["s001", "s002"] and all("|" not in x for x in ti)


def test_ids_order_is_kept(proj):
    t, P, A = proj
    assert viewer.main([P, "--analysis", A, "--ids", "s002,s001", "--out", str(t / "v_ids")]) == 0
    assert [x.split()[0] for x in _titles(str(t / "v_ids"))] == ["s002", "s001"]


def test_representatives_are_labelled_with_their_group_in_display_order(proj):
    t, P, A = proj
    assert viewer.main([P, "--analysis", A, "--representatives", "0.5"]) == 2      # no groups.json yet: refused
    assert cli.main(["group", P, "--analysis", A]) == 0
    G = json.load(open(os.path.join(A, "groups", "groups.json")))["thresholds"]["0.5"]["groups"]
    want = [(g["representative"]["id"], "%s (t=0.5)" % g["representative"]["label"]) for g in G]
    reps = {i for i, _ in want}
    want += [(d["id"], "%s (t=0.5)" % d["text"]) for g in G for d in g["designated_members"] if d["id"] not in reps]
    assert viewer.main([P, "--analysis", A, "--representatives", "0.5"]) == 0
    ti = _titles(os.path.join(A, "viewer_representatives_t0.5"))
    assert [(x.split()[0], x.split(" | ", 1)[1]) for x in ti] == want
    assert any("representative of group 1" in x for x in ti)
    names = sorted(os.listdir(os.path.join(A, "viewer_representatives_t0.5", "structures")))
    assert names and all(".." not in n and "group" not in n and n.endswith((".pdb", ".pdb.js", ".cif", ".cif.js"))
                         for n in names), names           # file names come from the plain label, never truncated labels
    assert viewer.main([P, "--analysis", A, "--representatives", "0.5", "--ids", "s001"]) == 2
