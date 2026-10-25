"""0.3 workflow: rnplens compare (like-for-like separated from correspondence, evaluability and construct changes)."""
import csv
import json
import os

import gemmi
import numpy as np
import pytest

from rnplens import compare, importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "reference_based")
PRED, REF = os.path.join(EX, "7K9D_prediction.pdb"), os.path.join(EX, "7K9D_reference.cif")
PS = importer.read_sequence_arg(os.path.join(EX, "7K9D_protein.fasta"))
RS = importer.read_sequence_arg(os.path.join(EX, "7K9D_rna.fasta"))


def _tsv(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t"); w.writerow(["target_id", "prediction", "protein_sequence", "rna_sequence"]); w.writerows(rows)


def _variant(tmp, name, fn):
    st = gemmi.read_structure(PRED); fn(st); p = str(tmp / (name + ".pdb")); st.write_pdb(p); return p


def _shift_rna(st):
    for r in st[0]["B"]:
        for a in r:
            a.pos = gemmi.Position(a.pos.x + 6.0, a.pos.y, a.pos.z)


def _truncate_protein(st):
    ch = st[0]["A"]
    for i in range(4, -1, -1):
        del ch[i]


def _relabel(st):
    st[0]["A"].name = "P"; st[0]["B"].name = "R"


def _drop_rna(st):
    st[0].remove_chain("B")


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    t = tmp_path_factory.mktemp("c")
    shifted, trunc, norna = _variant(t, "shifted", _shift_rna), _variant(t, "trunc", _truncate_protein), _variant(t, "norna", _drop_rna)
    relab = _variant(t, "relab", _relabel)
    _tsv(t / "before.tsv", [["same", PRED, PS, RS], ["worse", PRED, PS, RS], ["corr", PRED, PS, RS], ["relabel", PRED, PS, RS], ["lost", PRED, PS, RS],
                            ["gained", norna, PS, RS], ["construct", PRED, PS, RS], ["only_b", PRED, PS, RS]])
    _tsv(t / "after.tsv", [["same", PRED, PS, RS], ["worse", shifted, PS, RS], ["corr", trunc, PS, RS], ["relabel", relab, PS, RS], ["lost", norna, PS, RS],
                           ["gained", PRED, PS, RS], ["construct", PRED, PS[:-1] + ("A" if PS[-1] != "A" else "G"), RS]])
    with open(t / "refs.tsv", "w") as fh:
        fh.write("target_id\treference\n" + "".join("%s\t%s\n" % (x, REF) for x in ("same", "worse", "corr", "relabel", "lost", "gained", "construct", "only_b")))
    assert compare.run(str(t / "before.tsv"), str(t / "after.tsv"), str(t / "refs.tsv"), str(t / "out"), jobs=4) == 0
    rows = list(csv.DictReader(open(t / "out" / "comparison.tsv"), delimiter="\t"))
    return t, {(r["target_id"], r["metric"]): r for r in rows}, json.load(open(t / "out" / "comparison_summary.json"))


def test_identical_predictions_unchanged(result):
    _, r, _ = result
    assert {r[("same", m)]["class"] for m, *_ in compare.METRICS} == {"UNCHANGED"}


def test_worsened_on_the_right_axis(result):
    _, r, _ = result
    assert r[("worse", "lrmsd")]["class"] == "WORSENED"
    assert r[("worse", "dockq")]["class"] == "WORSENED"
    assert not any(k[1] in compare.WITHHELD["metrics"] for k in r)      # geometry route withheld


def test_changed_correspondence_is_never_like_for_like(result):
    _, r, s = result
    # five protein residues removed: the DockQ route cannot use construct positions for a chain shorter than the
    # construct, so it has no value after
    assert r[("corr", "dockq")]["class"] == "NEWLY_UNEVALUABLE"
    # same coordinates under new chain names: a different chain mapping, so not pooled even if the values agree
    assert r[("relabel", "dockq")]["class"] == "CORRESPONDENCE_CHANGED"
    assert r[("relabel", "dockq")]["before"] == r[("relabel", "dockq")]["after"]
    assert "relabel" in s["metrics"]["dockq"]["targets_by_class"]["CORRESPONDENCE_CHANGED"]


def test_evaluability_and_construct_changes_separate(result):
    _, r, s = result
    assert r[("lost", "dockq")]["class"] == "NEWLY_UNEVALUABLE"
    assert r[("gained", "dockq")]["class"] == "NEWLY_EVALUABLE"
    assert r[("construct", "dockq")]["class"] == "CONSTRUCT_CHANGED"
    assert s["unmatched"]["only_before"] == ["only_b"]
    dq = s["metrics"]["dockq"]
    assert dq["like_for_like_n"] == 2          # same and worse only
    assert dq["counts"]["UNCHANGED"] == 1 and dq["counts"]["WORSENED"] == 1


def test_refuses_existing_output(result):
    t, _, _ = result
    assert compare.run(str(t / "before.tsv"), str(t / "after.tsv"), str(t / "refs.tsv"), str(t / "out")) == 2
