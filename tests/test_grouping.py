"""Function 6 acceptance tests: binding-hypothesis grouping and difference maps (Spec B v2 section 6, with
Amendments 1-2 in records/grouping/)."""
import builtins
import copy
import hashlib
import itertools
import json
import os
import random
import sys
from fractions import Fraction

import pytest

from rnplens import capabilities, cli, grouping as G, trace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fixtures_v04", "grouping"))
import synth  # noqa: E402

EX = os.path.join(os.path.dirname(HERE), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")


def H(i):
    return hashlib.sha256(("structure-%s" % i).encode()).hexdigest()


def S(i, contacts, engine="BOLTZ2", designated=False, state="ELIGIBLE", sha=None):
    return {"id": "x%03d" % i, "engine": engine, "execution": "run#%03d" % i, "sha256": sha or H(i),
            "designated": designated, "state": state,
            "contacts": [tuple(c) for c in contacts] if state == "ELIGIBLE" else None}


def regs(prot, rna):
    return list(zip(prot, rna))


def groups_at(doc, t="0.5"):
    return [g["members"] for g in doc["thresholds"][t]["groups"]]


def canon(doc):
    d = copy.deepcopy(doc)
    d.pop("provenance", None)
    return json.dumps(d, sort_keys=True)


# ------------------------------------------------------------------------------------------- constructed fixtures
def test_three_registers_on_one_surface_give_three_register_groups_in_one_surface_group():
    X, Y, Z = regs([1, 2, 3], [1, 2, 3]), regs([1, 2, 3], [4, 5, 6]), regs([1, 2, 3], [7, 8, 9])
    st = [S(1, X), S(2, X), S(3, Y), S(4, Y), S(5, Z), S(6, Z)]
    doc, dend, _ = G.compute(st, pose=False)
    for t in G.THRESHOLDS:
        T = doc["thresholds"][t]
        assert T["n_surface_groups"] == 1 and T["n_groups"] == 3
        assert {g["surface_group"] for g in T["groups"]} == {1}
        assert sorted(sorted(g) for g in groups_at(doc, t)) == [["x001", "x002"], ["x003", "x004"], ["x005", "x006"]]


def test_two_surfaces_give_two_surface_groups():
    st = [S(1, regs([1, 2, 3], [1, 2, 3])), S(2, regs([1, 2, 3], [1, 2, 3])), S(3, regs([6, 7, 8], [1, 2, 3]))]
    doc, _, _ = G.compute(st, pose=False)
    T = doc["thresholds"]["0.5"]
    assert T["n_surface_groups"] == 2 and T["n_groups"] == 2
    assert [s["members"] for s in T["surface_groups"]] in ([["x001", "x002"], ["x003"]], [["x003"], ["x001", "x002"]])


def test_no_contact_structure_forms_the_no_interface_group_and_is_never_clustered():
    st = [S(1, regs([1, 2], [1, 2])), S(2, []), S(3, [])]
    doc, dend, _ = G.compute(st, pose=False)
    for t in G.THRESHOLDS:
        ni = [g for g in doc["thresholds"][t]["groups"] if g["no_interface"]]
        assert len(ni) == 1 and sorted(ni[0]["members"]) == ["x002", "x003"]
        assert ni[0]["representative"]["rule"].startswith("no contacts")
        assert ni[0]["mean_R_members_to_representative"] is None
        assert any(s["label"] == "no interface" for s in doc["thresholds"][t]["surface_groups"])
    assert dend["level1"]["members"] == ["x001"]          # Jaccard(empty, empty) never evaluated


def test_fifty_plus_one_engine_weighting_gives_equal_engine_weighted_sizes():
    A = regs([1, 2, 3], [1, 2, 3])
    B = regs([6, 7, 8], [4, 5, 6])
    st = [S(i, A, engine="BOLTZ2", designated=(i == 1)) for i in range(1, 51)] + [S(51, B, engine="OTHER", designated=True)]
    doc, _, _ = G.compute(st, pose=False)
    gs = doc["thresholds"]["0.5"]["groups"]
    assert sorted(g["size"] for g in gs) == [1, 50]
    assert [g["engine_weighted_size"]["fraction"] for g in gs] == ["1/1", "1/1"]
    assert {tuple(g["engine_composition"].items()) for g in gs} == {(("BOLTZ2", 50),), (("OTHER", 1),)}


def test_chaining_core_matrix_exactly_as_specified_is_not_one_group():
    """Amendment 1 (A1.1, part 1): the agreement matrix of Spec B v2 section 6 on the clustering core."""
    A, B, C = ("a", "A"), ("b", "B"), ("c", "C")
    M = {frozenset((A, B)): Fraction(3, 5), frozenset((B, C)): Fraction(3, 5), frozenset((A, C)): Fraction(0)}
    merges = G.upgma([A, B, C], lambda x, y: M[frozenset((x, y))])
    part = G.cut([A, B, C], merges, "0.5")
    assert len(part) == 2 and max(len(p) for p in part) == 2
    assert merges[1]["distance"] == Fraction(7, 10)     # mean d of C to {A,B} = (1 + 0.4)/2


def test_chaining_realisable_contact_sets_are_not_one_group():
    """Amendment 1 (A1.1, part 2): R = 3/5, 3/5, 1/5 (minimum realisable R(A,C)), all on one protein surface."""
    A = [(1, r) for r in (1, 2, 3)]
    B = [(1, r) for r in (1, 2, 3, 4, 5)]
    C = [(1, r) for r in (1, 4, 5)]
    st = [S(1, A), S(2, B), S(3, C)]
    doc, dend, pw = G.compute(st, pose=False)
    R = {frozenset((p["a"], p["b"])): p["R_exact"] for p in pw["pairs"]}
    assert R[frozenset(("x001", "x002"))] == "3/5" and R[frozenset(("x002", "x003"))] == "3/5"
    assert R[frozenset(("x001", "x003"))] == "1/5"
    assert doc["thresholds"]["0.5"]["n_surface_groups"] == 1
    assert doc["thresholds"]["0.5"]["n_groups"] == 2
    assert doc["thresholds"]["0.3"]["n_groups"] == 1      # mean agreement 0.4 >= 0.3


def test_average_linkage_matches_scipy_without_ties():
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    rng = random.Random(7)
    n = 12
    keys = [(H(i), "k%02d" % i) for i in range(n)]
    M = {}
    for i, j in itertools.combinations(range(n), 2):
        M[frozenset((keys[i], keys[j]))] = Fraction(rng.randrange(1, 10 ** 6), 10 ** 6)
    merges = G.upgma(keys, lambda a, b: M[frozenset((a, b))])
    import numpy as np
    D = np.zeros((n, n))
    for i, j in itertools.combinations(range(n), 2):
        D[i, j] = D[j, i] = float(1 - M[frozenset((keys[i], keys[j]))])
    Z = linkage(squareform(D), method="average")
    for t in ("0.3", "0.5", "0.7"):
        lab = fcluster(Z, 1 - float(t), criterion="distance")
        ref = sorted(tuple(sorted(keys[i] for i in range(n) if lab[i] == c)) for c in set(lab))
        assert G.cut(keys, merges, t) == ref
    assert [float(m["distance"]) for m in merges] == pytest.approx(sorted(Z[:, 2]))


def test_merge_on_equality_at_the_threshold():
    """d <= 1 - t merges: agreement exactly 0.5 merges at t = 0.5 (exact arithmetic, no float edge)."""
    st = [S(1, [(1, 1), (1, 2)]), S(2, [(1, 2), (1, 3)]), S(3, [(1, 3), (1, 4), (1, 5), (1, 6)])]
    doc, _, pw = G.compute(st, pose=False)
    assert {p["R_exact"] for p in pw["pairs"] if {p["a"], p["b"]} == {"x001", "x002"}} == {"1/3"}
    st = [S(1, [(1, 1), (1, 2), (1, 3)]), S(2, [(1, 2), (1, 3), (1, 4)])]   # R = 2/4
    doc, _, _ = G.compute(st, pose=False)
    assert doc["thresholds"]["0.5"]["n_groups"] == 1 and doc["thresholds"]["0.7"]["n_groups"] == 2


# ------------------------------------------------------------------------------------------- order and display
def _tie_pool():
    X, Y = regs([1, 2, 3], [1, 2, 3]), regs([1, 2, 3], [1, 2, 4])
    Z, W = regs([7, 8], [1, 2]), regs([7, 8], [3, 4])
    st = [S(i, X) for i in range(1, 5)] + [S(i, Y) for i in range(5, 8)] + [S(8, Z), S(9, W), S(10, []), S(11, [])]
    st += [S(12, X, sha=H(1)) | {"id": "x012", "execution": "run#012"}]       # identical file content to x001
    st[3]["designated"] = True
    return st


def test_permutation_invariance_with_ties():
    st = _tie_pool()
    ref = [canon(x) for x in G.compute(st, pose=False)]
    rng = random.Random(20261016)
    for _ in range(25):
        p = st[:]
        rng.shuffle(p)
        assert [canon(x) for x in G.compute(p, pose=False)] == ref


def test_identical_file_content_always_in_the_same_group():
    doc, _, _ = G.compute(_tie_pool(), pose=False)
    for t in G.THRESHOLDS:
        assert any({"x001", "x012"} <= set(g) for g in groups_at(doc, t))


def test_display_order_designated_first_then_smallest_key_never_by_size():
    small, big = regs([1, 2], [1, 2]), regs([6, 7], [3, 4])
    # the 5-member group has the larger canonical keys; the singleton has the smallest key
    st = [S(1, small, sha="0" * 64)] + [S(i, big, sha="%x" % (i + 1) * 64) for i in range(2, 7)]
    doc, _, _ = G.compute(st, pose=False)
    assert [g["size"] for g in doc["thresholds"]["0.5"]["groups"]] == [1, 5]
    st[3]["designated"] = True
    doc, _, _ = G.compute(st, pose=False)
    gs = doc["thresholds"]["0.5"]["groups"]
    assert gs[0]["contains_designated"] and gs[0]["size"] == 5 and gs[1]["size"] == 1
    assert doc["thresholds"]["0.5"]["designated"][0]["text"] in (
        "engine-designated structure (member of group 1)", "engine-designated structure; representative of group 1")


def test_representative_is_register_medoid_with_canonical_tie_break():
    a, b, c = [(1, 1), (1, 2), (1, 3)], [(1, 1), (1, 2), (1, 3), (1, 4)], [(1, 1), (1, 2), (1, 3), (1, 5)]
    doc, _, _ = G.compute([S(1, b), S(2, c), S(3, a)], pose=False)
    g = doc["thresholds"]["0.3"]["groups"][0]
    assert g["representative"]["id"] == "x003"            # a: mean R 3/4 to b and c, highest
    doc, _, _ = G.compute([S(1, a, sha="f" * 64), S(2, a, sha="1" * 64)], pose=False)
    assert doc["thresholds"]["0.5"]["groups"][0]["representative"]["id"] == "x002"   # tie -> smaller key


def test_designated_not_medoid_is_shown_as_member_of_group():
    a, b, c = [(1, 1), (1, 2), (1, 3)], [(1, 1), (1, 2), (1, 3), (1, 4)], [(1, 1), (1, 2), (1, 3), (1, 5)]
    doc, _, _ = G.compute([S(1, b, designated=True), S(2, c), S(3, a)], pose=False)
    d = doc["thresholds"]["0.3"]["designated"]
    assert d == [{"id": "x001", "engine": "BOLTZ2", "group": 1, "text": "engine-designated structure (member of group 1)"}]


def test_every_eligible_structure_in_exactly_one_group_and_ineligible_listed():
    st = _tie_pool() + [S(20, None, state="INDEXING_UNVERIFIED", designated=True)]
    doc, _, _ = G.compute(st, pose=False)
    elig = {s["id"] for s in st if s["state"] == "ELIGIBLE"}
    for t in G.THRESHOLDS:
        allm = [m for g in groups_at(doc, t) for m in g]
        assert sorted(allm) == sorted(elig)
        assert any(d["id"] == "x020" and "ineligible" in d["text"] for d in doc["thresholds"][t]["designated"])
    assert [r["id"] for r in doc["ineligible"]] == ["x020"]


def test_dendrogram_exports_full_merge_sequences():
    doc, dend, _ = G.compute(_tie_pool(), pose=False)
    assert len(dend["level1"]["merges"]) == doc["n_interface"] - 1
    for t in G.THRESHOLDS:
        for d in dend["level2"][t]:
            assert len(d["merges"]) == len(d["members"]) - 1


# ------------------------------------------------------------------------------------------- pipeline + parity
@pytest.fixture(scope="module")
def k7(tmp_path_factory):
    from rnplens import analyse, importer
    t = tmp_path_factory.mktemp("k7")
    PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
    RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"),
                        "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(str(t / "p"), str(t / "r")) == 0
    assert cli.main(["group", str(t / "p"), "--analysis", str(t / "r")]) == 0
    return t


def test_parity_R_U_P_with_rc3_report_7K9D(k7):
    rep = json.load(open(k7 / "r" / "report" / "result.json"))["summary"]["repeat_agreement"]["BOLTZ2"]
    pw = json.load(open(k7 / "r" / "groups" / "pairwise.json"))["pairs"]
    assert len(pw) == 1
    p = pw[0]
    assert p["register_agreement_R"] == rep["register_agreement"]
    assert p["surface_agreement_U"] == rep["surface_agreement"]
    assert p["rna_pose_difference_P_A"] == rep["rna_pose_difference_A"]
    assert p["P_copy_permutation_capped"] == rep["rna_pose_copy_permutation_capped"]


def test_worked_example_7K9D_outputs_and_wording(k7):
    g = k7 / "r" / "groups"
    for f in ("groups.json", "groups.html", "groups.tsv", "dendrogram.json", "pairwise.json"):
        assert (g / f).is_file()
    doc = json.load(open(g / "groups.json"))
    assert doc["provenance"]["kind"] == "hypothesis_grouping" and doc["provenance"]["config_sha256"]
    assert all("evidence_id" in x for t in G.THRESHOLDS for x in doc["thresholds"][t]["groups"])
    assert all("evidence_id" in x for x in doc["structures"])
    page = (g / "groups.html").read_text()
    assert G.SIZE_NOTE in page and G.Q_STATEMENT in page and trace.wording_audit(page) == []
    assert all(t in page for t in ("t = 0.5", "t = 0.3", "t = 0.7"))
    for f in os.listdir(g):
        if os.path.isfile(g / f):
            text = (g / f).read_text().lower()
            for w in ("best", "most likely", "correct group", "confidence of the group"):
                assert w not in text, (f, w)


def test_parity_pairs_against_report_repeat_agreement_on_synthetic_pool(tmp_path):
    """Every pair: R, U and P equal Report's own repeat-agreement output for a 2-structure contract."""
    from rnpbench_report import agreement, contract
    specs = [{"engine": "BOLTZ2", "run": "r", "sample": "m%d" % i, "assign": a, "jitter": 0.3 * i}
             for i, a in enumerate([[1, 2, 3, None], [1, 2, 4, None], [None, 5, 6, 7], [1, None, 3, 3]])]
    p = synth.make_project(str(tmp_path), 8, 4, specs)
    a = synth.make_analysis(p, str(tmp_path))
    assert G.main([p, "--analysis", a]) == 0
    pw = json.load(open(os.path.join(a, "groups", "pairwise.json")))["pairs"]
    man = {s["id"]: s for s in json.load(open(os.path.join(p, "manifest.json")))["structures"]}
    con = json.load(open(os.path.join(p, "report_contract.json")))
    for row in pw:
        sub = dict(con, outputs=[o for o in con["outputs"] if o["execution"] in (man[row["a"]]["execution"],
                                                                               man[row["b"]]["execution"])])
        rep = agreement.run(contract.validate(sub))["summary"]["repeat_agreement"]["BOLTZ2"]
        assert row["register_agreement_R"] == rep["register_agreement"]
        assert row["surface_agreement_U"] == rep["surface_agreement"]
        assert row["rna_pose_difference_P_A"] == rep["rna_pose_difference_A"]


def test_analysis_mode_equals_raw_mode(tmp_path):
    specs = [{"engine": "BOLTZ2", "run": "r1", "sample": "m%d" % i, "assign": a, "designated": i == 0}
             for i, a in enumerate([[1, 2, 3, None], [1, 2, 3, None], [None, None, 6, 7], [None] * 4])]
    p = synth.make_project(str(tmp_path), 8, 4, specs)
    a = synth.make_analysis(p, str(tmp_path))
    d1 = G.run(p, analysis=a, quiet=True)["doc"]
    d2 = G.run(p, out=str(tmp_path / "raw"), quiet=True)["doc"]
    strip = lambda d: canon({k: v for k, v in d.items() if k != "source"})  # noqa: E731
    assert strip(d1) == strip(d2)


def test_multi_engine_pool_end_to_end(tmp_path):
    X = [1, 2, 3, None, None, None]
    Y = [None, None, None, 6, 7, 8]
    specs = [{"engine": "BOLTZ2", "run": "r1", "sample": "m%d" % i, "assign": X, "designated": i == 0} for i in range(5)]
    specs += [{"engine": "OTHER", "run": "o1", "sample": "m0", "assign": Y, "designated": True},
              {"engine": "OTHER", "run": "o1", "sample": "m1", "assign": [None] * 6},
              {"engine": "OTHER", "run": "o1", "sample": "m2", "assign": X, "broken": True}]
    p = synth.make_project(str(tmp_path), 8, 6, specs)
    a = synth.make_analysis(p, str(tmp_path))
    doc = G.run(p, analysis=a, quiet=True)["doc"]
    gs = doc["thresholds"]["0.5"]["groups"]
    assert [g["contains_designated"] for g in gs][:2] == [True, True]
    assert {g["engine_weighted_size"]["fraction"] for g in gs} == {"1/1", "1/2"}
    assert [r["state"] for r in doc["ineligible"]] == ["INDEXING_UNVERIFIED"]


# ------------------------------------------------------------------------------------------- difference map
def test_difference_map_unresolved_positions_are_not_observed(tmp_path):
    X = [1, 2, 3, None]
    Y = [1, None, None, 7]
    specs = [{"engine": "BOLTZ2", "run": "r", "sample": "a0", "assign": X, "designated": True},
             {"engine": "BOLTZ2", "run": "r", "sample": "a1", "assign": X},
             {"engine": "BOLTZ2", "run": "r", "sample": "a2", "assign": [1, 2, None, None], "unresolved": (3,)},
             {"engine": "BOLTZ2", "run": "r", "sample": "b0", "assign": [None, None, None, 7]},
             {"engine": "BOLTZ2", "run": "r", "sample": "b1", "assign": Y}]
    p = synth.make_project(str(tmp_path), 8, 4, specs)
    a = synth.make_analysis(p, str(tmp_path))
    doc = G.run(p, analysis=a, quiet=True)["doc"]
    gs = doc["thresholds"]["0.5"]["groups"]
    ga = [g for g in gs if "s001" in g["members"]][0]
    gb = [g for g in gs if "s004" in g["members"]][0]
    assert sorted(ga["members"]) == ["s001", "s002", "s003"] and sorted(gb["members"]) == ["s004", "s005"]
    assert G.main_diff([a, str(ga["group"]), str(gb["group"])]) == 0
    sub = os.path.join(a, "groups", G.diff_dirname(ga["group"], gb["group"]))
    d = json.load(open(os.path.join(sub, "diff.json")))
    row = {(x["protein_position"], x["rna_position"]): x for x in d["rows"]}
    r33 = row[(3, 3)]["A"]                    # s003 has protein 3 unresolved: not observed, not "no contact"
    assert r33["denominator_resolved_members"] == 2 and r33["members_containing"] == 2 and r33["fraction"] == "2/2"
    assert r33["not_observed"] == ["s003"]
    assert row[(1, 1)]["category"] == "frequent in both"       # A 3/3, B 1/2 (>= 1/2)
    assert row[(7, 4)]["category"] == "frequent in group %d only" % gb["group"]
    assert row[(3, 3)]["category"] == "frequent in group %d only" % ga["group"]
    assert all(x["caveat"] == G.DIFF_CAVEAT for x in d["rows"])
    assert d["frequent_cut_point"] == "1/2" and d["provenance"]["kind"] == "group_difference_map"
    tsv = open(os.path.join(sub, "diff.tsv")).read()
    assert tsv.splitlines()[0].count("denominator_group") == 2 and G.DIFF_CAVEAT in tsv
    page = open(os.path.join(sub, "diff.html")).read()
    assert trace.wording_audit(page) == [] and "<svg" in page and G.DIFF_CAVEAT in page


def test_difference_map_with_explicit_resolution_and_zero_denominator():
    st = [S(1, [(1, 1), (2, 2)], designated=True), S(2, [(1, 1), (2, 2)]), S(3, [(6, 3), (7, 4)])]
    doc, _, _ = G.compute(st, pose=False)
    gs = doc["thresholds"]["0.5"]["groups"]
    res = {"x001": ({1, 2, 6, 7}, {1, 2, 3, 4}), "x002": ({1, 6, 7}, {1, 2, 3, 4}), "x003": ({1, 2}, {1, 2})}
    d = G.difference(doc, 1, 2, resolved=res)
    row = {(x["protein_position"], x["rna_position"]): x for x in d["rows"]}
    assert row[(2, 2)]["A"]["denominator_resolved_members"] == 1
    assert (6, 3) not in row      # group 2's only member does not resolve protein 6: not observed, not frequent
    assert d["counts"]["contacts frequent in neither group (not listed)"] == 2


def test_difference_map_bad_groups_refused(k7):
    assert cli.main(["group-diff", str(k7 / "r"), "1", "9"]) == 2
    assert cli.main(["group-diff", str(k7 / "r"), "1", "1"]) == 2
    assert not any(n.startswith("diff_") for n in os.listdir(k7 / "r" / "groups"))


# ------------------------------------------------------------------------------------------- malformed / missing
def test_malformed_inputs_are_refused():
    with pytest.raises(G.GroupingInputError):
        G.compute([S(1, [(1, 1)]), S(1, [(1, 2)])])                          # duplicate id
    bad = S(2, [(1, 1)]); bad["sha256"] = "xyz"
    with pytest.raises(G.GroupingInputError):
        G.compute([bad])
    bad = S(3, [(1, 1)]); bad["contacts"] = [(0, 1)]
    with pytest.raises(G.GroupingInputError):
        G.compute([bad])
    bad = S(4, [(1, 1)]); bad["contacts"] = None
    with pytest.raises(G.GroupingInputError):
        G.compute([bad])
    with pytest.raises(G.GroupingInputError):
        G.compute([{"id": "a"}])


def test_inconsistent_analysis_is_refused_and_nothing_written(tmp_path):
    specs = [{"engine": "BOLTZ2", "run": "r", "sample": "m%d" % i, "assign": [1, 2, None]} for i in range(2)]
    p = synth.make_project(str(tmp_path), 6, 3, specs)
    a = synth.make_analysis(p, str(tmp_path))
    cbo = os.path.join(a, "report", "contacts_by_output.json")
    good = open(cbo).read()
    d = json.loads(good); d["BOLTZ2|r#m9"] = [[1, 1]]; open(cbo, "w").write(json.dumps(d))
    assert G.main([p, "--analysis", a]) == 2
    d = json.loads(good); d.pop("BOLTZ2|r#m0"); open(cbo, "w").write(json.dumps(d))
    assert G.main([p, "--analysis", a]) == 2
    open(cbo, "w").write(good)
    m = json.load(open(os.path.join(p, "manifest.json"))); m["structures"][0]["used_sha256"] = "0" * 64
    json.dump(m, open(os.path.join(p, "manifest.json"), "w"))
    assert G.main([p, "--analysis", a]) == 2
    assert G.main([p]) == 2                                   # neither --analysis nor --out
    assert not os.path.exists(os.path.join(a, "groups"))


def test_missing_structure_file_makes_P_unavailable_not_zero(tmp_path):
    specs = [{"engine": "BOLTZ2", "run": "r", "sample": "m%d" % i, "assign": [1, 2, None]} for i in range(3)]
    p = synth.make_project(str(tmp_path), 6, 3, specs)
    a = synth.make_analysis(p, str(tmp_path))
    os.remove(json.load(open(os.path.join(p, "manifest.json")))["structures"][2]["used_path"])
    doc = G.run(p, analysis=a, quiet=True)["doc"]
    pw = json.load(open(os.path.join(a, "groups", "pairwise.json")))["pairs"]
    assert any("P unavailable" in n for n in doc["notes"])
    assert sum(r["rna_pose_difference_P_A"] is None for r in pw) == 2
    sp = doc["thresholds"]["0.5"]["groups"][0]["rna_pose_difference_spread_A"]
    assert sp["n_pairs"] == 1 and sp["n_pairs_unavailable"] == 2


def test_zero_eligible_structures_still_writes_a_listing(tmp_path):
    st = [S(1, None, state="INELIGIBLE_POLYMER_ABSENT", designated=True)]
    doc, _, _ = G.compute(st)
    assert doc["thresholds"]["0.5"]["n_groups"] == 0 and len(doc["ineligible"]) == 1


# ------------------------------------------------------------------------------------------- determinism / access
def test_determinism_two_runs_identical_outputs(tmp_path):
    specs = [{"engine": "BOLTZ2", "run": "r", "sample": "m%d" % i, "assign": a}
             for i, a in enumerate([[1, 2, 3], [1, 2, 3], [4, 5, None], [None] * 3])]
    p = synth.make_project(str(tmp_path), 6, 3, specs)
    a = synth.make_analysis(p, str(tmp_path))
    G.run(p, analysis=a, quiet=True)
    first = {f: open(os.path.join(a, "groups", f)).read() for f in ("groups.tsv", "groups.html")}
    j1 = json.load(open(os.path.join(a, "groups", "groups.json")))
    G.run(p, analysis=a, quiet=True)
    assert first == {f: open(os.path.join(a, "groups", f)).read() for f in first}
    assert canon(j1) == canon(json.load(open(os.path.join(a, "groups", "groups.json"))))


def test_reads_only_declared_inputs(tmp_path, monkeypatch):
    specs = [{"engine": "BOLTZ2", "run": "r", "sample": "m%d" % i, "assign": a}
             for i, a in enumerate([[1, 2, 3], [1, 2, None]])]
    p = synth.make_project(str(tmp_path), 6, 3, specs)
    a = synth.make_analysis(p, str(tmp_path))
    man = json.load(open(os.path.join(p, "manifest.json")))
    allowed = {os.path.abspath(x) for x in [os.path.join(p, "manifest.json"), os.path.join(a, "report", "result.json"),
                                             os.path.join(a, "report", "contacts_by_output.json")]
               + [s["used_path"] for s in man["structures"]]}
    seen = []
    real = builtins.open

    def spy(f, mode="r", *k, **kw):
        if isinstance(f, (str, os.PathLike)) and "r" in mode and "+" not in mode:
            seen.append(os.path.abspath(f))
        return real(f, mode, *k, **kw)
    monkeypatch.setattr(builtins, "open", spy)
    G.run(p, analysis=a, quiet=True)
    monkeypatch.setattr(builtins, "open", real)
    outside = {x for x in seen if x not in allowed and not x.startswith(os.path.dirname(os.path.abspath(G.__file__)))
               and "site-packages" not in x and not x.startswith(sys.prefix)}
    assert outside == set(), outside


# ------------------------------------------------------------------------------------------- wording / registry
def test_wording_audit_and_forbidden_phrases_refuse_output():
    for bad in ("the best group", "the most likely proposal", "the correct group", "confidence of the group is 0.8"):
        assert G.audit("<p>%s</p>" % bad) != []
    assert G.audit("<p>%s %s %s</p>" % (G.SIZE_NOTE, G.DIFF_CAVEAT, G.Q_STATEMENT)) == []
    assert G.audit("<p>file /data/best/model.pdb</p>", ["/data/best/model.pdb"]) == []
    for text in G.LIMITS + [G.DEFINITION, G.NOT_RANKED, G.PLACEMENT_NOTE, G.FREQUENT_TEXT]:
        assert G.audit(text) == [], text


def test_capabilities_registered_in_menu_E_as_descriptive():
    offered, missing = capabilities.available()
    mine = {c["id"]: c for c in offered if c["module"] == "grouping"}
    assert mine["hypothesis_grouping"]["menu"] == "E" and mine["hypothesis_grouping"]["status"] == "DESCRIPTIVE"
    assert mine["group_difference"]["status"] == "DESCRIPTIVE"
    for c in mine.values():
        assert callable(capabilities.resolve(c["call"])) and G.audit(c["label"] + " " + c["limits"]) == []
    assert "rna_conformation_difference" in {m["id"] for m in missing}


def test_capability_call_returns_outputs(k7):
    r = G.run_capability(str(k7 / "p"), analysis=str(k7 / "r"))
    assert r["outputs"] and all(os.path.isfile(x) for x in r["outputs"])


def test_ari_helper():
    assert G.adjusted_rand_index([0, 0, 1, 1], [5, 5, 7, 7]) == 1.0
    assert G.adjusted_rand_index([0, 0, 0], [1, 1, 1]) == 1.0
    assert G.adjusted_rand_index([0, 0, 1, 1], [0, 1, 0, 1]) == pytest.approx(-0.5)
