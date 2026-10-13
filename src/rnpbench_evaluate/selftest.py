"""Regression self-test against frozen RNPBench values (v0.1.1).

Fixture sets
  * public   -- bundled in the package (rnpbench_evaluate/fixtures): five Boltz-2 benchmark fixtures and
                four constructed controls. Distribution status: public candidate, pending clearance.
  * internal -- genuine benchmark fixtures whose redistribution is not cleared (RF3, AlphaFold 3,
                Chai-1, RF2NA). They are NOT in the package; pass --internal-fixtures DIR to include them.

Numerical profiles (frozen in profiles/portable_numerical_profile_v1.json before any v0.1.1 run)
  * reference -- every compared value must be bit-identical (the karyon reference platform).
  * portable  -- exact for everything except the listed floating-point quantities, which must lie within
                 their frozen absolute tolerances. Every deviation is reported, including those within
                 tolerance.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import tempfile

from . import contract, engine

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
PROFILE_PATH = os.path.join(HERE, "profiles", "portable_numerical_profile_v1.json")
PROFILE_SHA256_AT_FREEZE = "91d29c96ab0edee7e6064122231cf125de3c83557d4b9649c53bca24ae7a267e"
GEOM_FLOAT = ("prot_internal_ca_rmsd", "rna_internal_c4_rmsd", "rna_placement_c4_rmsd")
GEOM_INT = ("n_prot_aligned", "n_prot_pose", "n_prot_native", "n_rna_aligned", "n_rna_pose", "n_rna_native")
PER_IF = ("DockQ", "fnat", "fnonnat", "nat_correct", "nat_total", "model_total", "len1", "len2", "iRMSD", "LRMSD")
PUBLIC_ORDER = ("ordinary", "short_rna", "partial_reference", "residue_numbering", "equivalent_copies")
INTERNAL_ORDER = ("no_value_rf3_6NY2", "engine_af3_8QJK", "engine_chai1_9RVP", "engine_rf2na_4RCJ")


def load_profile():
    raw = open(PROFILE_PATH, "rb").read()
    got = hashlib.sha256(raw).hexdigest()
    if got != PROFILE_SHA256_AT_FREEZE:
        raise RuntimeError("portable numerical profile differs from the version frozen before testing (%s != %s)" % (got[:16], PROFILE_SHA256_AT_FREEZE[:16]))
    return json.loads(raw), got


def _tolerance(profile, name):
    """Absolute tolerance for a check name under the portable profile, or None (exact)."""
    for grp in profile["tolerances"].values():
        for pat in grp["quantities"]:
            if fnmatch.fnmatchcase(name, pat):
                return grp["abs"]
    return None


def fixture_input(fixdir, cat, src):
    d = os.path.join(fixdir, cat)
    pred = [f for f in os.listdir(d) if f.startswith("prediction")][0]
    return {"contract": contract.CONTRACT_ID, "target_id": src["target"],
            "prediction": {"path": os.path.join(d, pred), "sha256": src["prediction_sha256"], "engine": src["engine"]},
            "reference": {"path": os.path.join(d, "reference.cif"), "sha256": src["reference_sha256"]},
            "construct": dict(src["construct"]), "options": {"tolerance": int(src["released_row"].get("tolerance") or 0)}}


def _fmt(v, d):
    return "NO VALUE" if v is None else "%.*f" % (d, v)


class Checker:
    def __init__(self, profile_name, profile):
        self.profile_name, self.profile, self.checks = profile_name, profile, []

    def ck(self, fixture, name, exp, got, kind=None):
        exact = (exp == got) and type(exp) is type(got) or (exp is None and got is None)
        is_float = isinstance(exp, float) and isinstance(got, float)
        dev = abs(exp - got) if is_float else None
        tol = _tolerance(self.profile, name) if (is_float and kind != "displayed") else None
        if self.profile_name == "reference":
            ok = exact
        else:
            ok = exact or (tol is not None and dev <= tol)
        self.checks.append({"fixture": fixture, "check": name, "expected": exp, "got": got,
                            "level": kind or ("toleranced_float" if tol is not None else "exact"),
                            "bit_exact": exact, "abs_deviation": dev, "tolerance_applied": tol if self.profile_name == "portable" else None,
                            "ok": ok})


def compare(C, cat, src, res):
    rel, dq, g = src["released_row"], res["dockq"], res["geometry"]
    ck = lambda n, e, x, kind=None: C.ck(cat, n, e, x, kind)
    ck("identity.prediction_sha256", src["prediction_sha256"], res["input"]["prediction"]["sha256"])
    ck("identity.reference_sha256", src["reference_sha256"], res["input"]["reference"]["sha256"])
    ck("dockq.status", rel["status"], dq["status"])
    if rel["status"] == "SCORED":
        ck("dockq.dockq", rel["dockq"], dq["dockq"])
        ck("dockq.dockq_unrounded", rel["dockq_unrounded"], dq["dockq_unrounded"])
        ck("dockq.dockq_class", engine.dockq_class(rel["dockq_unrounded"]), dq["dockq_class"])
        ck("display.dockq", _fmt(rel["dockq"], 3), _fmt(dq["dockq"], 3), "displayed")
        ck("dockq.selected_mapping", rel["selected_mapping"], dq["selected_mapping"])
        ck("dockq.n_admissible_candidates", rel["n_admissible_candidates"], dq["n_admissible_candidates"])
        ck("dockq.n_interfaces", rel["n_interfaces"], dq["n_interfaces"])
        ck("dockq.correspondence", rel["correspondence"], dq["correspondence"])
        tot = rel.get("objective_total_dockq", rel.get("adapter_total_dockq"))
        if tot is not None:
            ck("dockq.adapter_total_dockq", tot, dq["adapter_total_dockq"])
        if rel.get("per_interface"):
            for ik, iv in rel["per_interface"].items():
                gv = (dq["per_interface"] or {}).get(ik) or {}
                for f in PER_IF:
                    if f in iv:
                        ck("dockq.per_interface.%s.%s" % (ik, f), iv[f], gv.get(f))
                for f in ("fnat", "iRMSD", "LRMSD"):
                    if f in iv and list(rel["per_interface"]).index(ik) == 0:
                        ck("display.%s" % f, _fmt(iv[f], 3), _fmt(gv.get(f), 3), "displayed")
    else:
        ck("dockq.dockq_is_null_not_zero", None, dq["dockq"])
        ck("dockq.failure_reason", rel.get("failure_reason"), dq["failure_reason"])
        ck("dockq.failure_stage", rel.get("failure_stage", "candidate_enumeration"), dq["failure_stage"])
        if rel.get("failure_detail") is not None:
            ck("dockq.failure_detail", rel.get("failure_detail"), dq["failure_detail"])
    for fa in src.get("four_axes_rows") or []:
        for f in GEOM_FLOAT:
            e = float(fa[f]) if fa[f] != "" else None
            ck("geometry.%s" % f, e, g.get(f))
            ck("display.geometry.%s" % f, _fmt(e, 2), _fmt(g.get(f), 2), "displayed")
        for f in GEOM_INT:
            ck("geometry.%s" % f, int(fa[f]) if fa[f] != "" else None, g.get(f))
        ck("geometry.exclusion", fa["exclusion"] or None, g.get("exclusion"))
        ck("geometry.status", "NO_VALUE" if fa["exclusion"] else "COMPUTED", g.get("status"))


def _write_controls(tmp):
    import gemmi
    pred = os.path.join(FIX, "ordinary", "prediction.pdb")
    def var(name, fn):
        st = gemmi.read_structure(pred); fn(st); p = os.path.join(tmp, name + ".pdb"); st.write_pdb(p); return p
    def rm_rna(st):
        for ch in list(st[0]):
            if ch.name != "A":
                st[0].remove_chain(ch.name)
    def renum(st):
        for ch in st[0]:
            for r in ch:
                r.seqid.num += 1000
    def ala(st):
        for r in st[0]["A"]:
            r.name = "ALA"
    def swap(st):
        st[0]["A"].name = "Z"; st[0]["B"].name = "A"; st[0]["Z"].name = "B"
    return [("control_rna_removed", var("rna_removed", rm_rna)),
            ("control_renumbered_plus_1000", var("renumbered", renum)),
            ("control_protein_residues_all_ALA", var("protein_all_ala", ala)),
            ("control_chain_labels_swapped", var("chain_labels_swapped", swap))]


def _check_controls(C, name, res, ordinary_src):
    dq = res["dockq"]
    ck = lambda n, e, x: C.ck(name, n, e, x)
    if name == "control_chain_labels_swapped":
        # chain labels must not matter: the frozen mapping enumeration finds the same complex
        rel = ordinary_src["released_row"]
        ck("dockq.status", "SCORED", dq["status"])
        ck("dockq.dockq", rel["dockq"], dq["dockq"])
        ck("dockq.dockq_unrounded", rel["dockq_unrounded"], dq["dockq_unrounded"])
        ck("dockq.correspondence", rel["correspondence"], dq["correspondence"])
        # DockQ formats mappings as "<model chains>:<native chains>" in native-chain order (DockQ.format_mapping_string),
        # so the ordinary fixture's AB:AB becomes BA:AB when the model labels are swapped
        ck("dockq.selected_mapping_is_label_swap", "BA:AB", dq["selected_mapping"])
        return
    ck("dockq.status", "NO_VALUE", dq["status"])
    ck("dockq.dockq_is_null_not_zero", None, dq["dockq"])
    expected = {"control_rna_removed": ("adapter_application", "ADAPTER_NOT_APPLIED_NO_NUMBERS_REPORTED"),
                "control_renumbered_plus_1000": ("candidate_evaluation", "NO_ADMISSIBLE_CANDIDATE_SCORED"),
                "control_protein_residues_all_ALA": ("candidate_enumeration", "METRIC_REFUSED_THE_INPUT_BEFORE_ANY_CANDIDATE")}[name]
    ck("dockq.failure_stage", expected[0], dq["failure_stage"])
    ck("dockq.failure_reason", expected[1], dq["failure_reason"])
    if name == "control_rna_removed":
        ck("geometry.status", "NO_VALUE", res["geometry"]["status"])


def run(verbose=True, allow_unpinned=False, profile_name="reference", internal_fixtures=None):
    if profile_name not in ("reference", "portable"):
        raise ValueError("profile must be 'reference' or 'portable'")
    profile, psha = load_profile()
    C = Checker(profile_name, profile)
    results, sets = {}, [("public", FIX, "fixture_sources.json", PUBLIC_ORDER)]
    if internal_fixtures:
        sets.append(("internal", os.path.abspath(internal_fixtures), "fixture_sources_internal.json", INTERNAL_ORDER))   # 0.2.0.dev1: a relative path was joined to itself
    inputs = {}
    for setname, d, fn, order in sets:
        srcs = json.load(open(os.path.join(d, fn)))
        for cat in order:
            src = srcs[cat]
            inp = contract.load(fixture_input(d, cat, src), base_dir=d)
            res = engine.evaluate(inp, allow_unpinned=allow_unpinned)
            results[cat] = res; n0 = len(C.checks)
            compare(C, cat, src, res)
            inputs[cat] = {"set": setname, "target": src["target"], "engine": src["engine"], "prediction_sha256": res["input"]["prediction"]["sha256"],
                           "reference_sha256": res["input"]["reference"]["sha256"], "distribution": src.get("distribution")}
            if verbose:
                cs = C.checks[n0:]
                print("  %-8s %-20s %-5s %-6s DockQ %-6s geometry %-9s %d/%d checks" % (setname, cat, src["target"], src["engine"], res["dockq"]["dockq"],
                      res["geometry"]["status"], sum(x["ok"] for x in cs), len(cs)), flush=True)
    ordinary = json.load(open(os.path.join(FIX, "fixture_sources.json")))["ordinary"]
    tmp = tempfile.mkdtemp(prefix="rnpbench_controls_")
    try:
        for name, p in _write_controls(tmp):
            inp = fixture_input(FIX, "ordinary", ordinary); inp["prediction"] = {"path": p, "engine": "CONSTRUCTED_CONTROL"}
            res = engine.evaluate(contract.load(inp, base_dir=tmp), allow_unpinned=allow_unpinned)
            results[name] = res; n0 = len(C.checks)
            _check_controls(C, name, res, ordinary)
            inputs[name] = {"set": "public (constructed)", "derived_from": "ordinary fixture prediction", "prediction_sha256": res["input"]["prediction"]["sha256"]}
            if verbose:
                cs = C.checks[n0:]
                print("  %-8s %-32s DockQ %-6s (%s: %s) geometry %s  %d/%d checks" % ("control", name, res["dockq"]["dockq"], res["dockq"]["failure_stage"],
                      res["dockq"]["failure_reason"], res["geometry"]["status"], sum(x["ok"] for x in cs), len(cs)), flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    checks = C.checks
    fl = [x for x in checks if isinstance(x["expected"], float) and isinstance(x["got"], float)]
    devs = [x for x in fl if not x["bit_exact"]]
    n_ok = sum(x["ok"] for x in checks)
    return {"selftest_version": "0.1.1", "profile": profile_name, "profile_id": profile["profile_id"], "profile_sha256": psha,
            "verdict": "PASS" if n_ok == len(checks) else "FAIL", "n_checks": len(checks), "n_passed": n_ok,
            "n_exact_required": sum(1 for x in checks if x["tolerance_applied"] is None), "n_exact_required_equal": sum(1 for x in checks if x["tolerance_applied"] is None and x["bit_exact"]),
            "n_unrounded_floats": len(fl), "n_unrounded_floats_bit_exact": len(fl) - len(devs),
            "all_bit_exact": all(x["bit_exact"] for x in checks),
            "all_deviations": sorted(({"fixture": x["fixture"], "check": x["check"], "abs_deviation": x["abs_deviation"], "tolerance": x["tolerance_applied"], "ok": x["ok"]} for x in devs),
                                     key=lambda d: -d["abs_deviation"]),
            "fixture_sets": [s[0] for s in sets], "inputs": inputs,
            "failures": [x for x in checks if not x["ok"]], "checks": checks, "software_versions": engine.versions()}, results
