"""Function 4 (bounded follow-up): summary, local rules, policy, traceability, limits, execution and replay.
No language model: scripted clients only."""
import builtins
import copy
import json
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_followup_common import PS, RS, clone, make_project  # noqa: E402

from rnplens import trace  # noqa: E402
from rnplens_assistant import consent, followup as F, llm  # noqa: E402

Q = "Which contacts in RNA 13-23 are found in only one run, and which structures list them?"
EB = "region_13-23/region.json#/summary/only_in_run/exec_B"


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    b = tmp_path_factory.mktemp("fu_base")
    make_project(str(b / "x"))
    return str(b / "x")


@pytest.fixture
def pa(base, tmp_path):
    return clone(base, str(tmp_path / "w"))


def P_(fid, rationale="r", **kw):
    return {"follow_up": fid, "args": dict(F._blank(), **kw), "rationale": rationale}


def _seq(path):
    return "".join(l.strip() for l in open(path) if not l.startswith(">")).upper()


# ---------------------------------------------------------------- summary
def test_summary_contains_derived_values_only(pa):
    P, A = pa
    S = F.build_summary(P, A, Q)
    t = F.summary_text(S)
    assert S["agreement"][0]["surface_agreement"]["evidence_id"] == "summary.json#/repeat_agreement/BOLTZ2/surface_agreement"
    assert S["region_outputs"][0]["only_in_run"][0]["contacts"][0]["label"] == "R18-A21"
    for s in (_seq(PS), _seq(RS)):
        assert not any(s[i:i + 8] in t.upper() for i in range(len(s) - 8))
    assert "ATOM" not in t and not re.search(r"\b[0-9a-f]{64}\b", t) and '"/' not in t and "ipTM" not in t and "native" not in t
    assert F.privacy_check(t, P) == []
    assert F.summary_text(F.build_summary(P, A, Q)) == t                      # deterministic


def test_summary_reads_only_declared_records(pa, monkeypatch):
    P, A = pa
    opened = []
    real = builtins.open

    def rec(f, *a, **k):
        opened.append(os.path.realpath(str(f)))
        return real(f, *a, **k)
    monkeypatch.setattr(builtins, "open", rec)
    F.build_summary(P, A, Q)
    roots = [os.path.realpath(P), os.path.realpath(A)]
    assert opened and all(any(o.startswith(r + os.sep) for r in roots) for o in opened), opened
    assert not any(o.endswith((".pdb", ".cif", ".fasta")) or "contacts_by_output" in o or "groups.json" in o for o in opened)


def test_reference_derived_values_excluded_unless_allowed(pa):
    P, A = pa
    S = json.load(open(os.path.join(A, "summary.json")))
    S["evaluate"] = [{"structure": "s001", "dockq": 0.61, "dockq_class": "medium", "dockq_status": "SCORED"}]
    json.dump(S, open(os.path.join(A, "summary.json"), "w"))
    off = F.summary_text(F.build_summary(P, A, Q))
    assert "dockq" not in off.lower() and '"n_structures_with_reference_values_excluded":1' in off
    on = F.build_summary(P, A, Q, allow_reference_derived=True)
    assert on["reference_derived"]["values"][0]["dockq"]["value"] == 0.61
    pay = F.prompt_system() + "\n\n---\n\n" + F.prompt_user(Q, F.summary_text(on))
    assert any("reference-derived" in v for v in F.privacy_check(pay, P))
    assert F.privacy_check(pay, P, allow_reference_derived=True) == []


def test_privacy_check_catches_forbidden_content(pa):
    P, _ = pa
    assert F.privacy_check("x " + _seq(RS)[5:20], P)
    assert F.privacy_check("ATOM      1  N   GLY A   1", P)
    assert F.privacy_check('{"path": "/home/user/model.pdb"}', P)
    assert F.privacy_check("a" * 64 if False else "0" * 64, P)
    assert F.privacy_check("reference file reference.cif", P)


# ---------------------------------------------------------------- local rules
def _synthetic(surface, register, runs=("exec_A", "exec_B"), excluded=0, unrec=0):
    v = lambda x, e="summary.json#/x": {"value": x, "evidence_id": e}
    return {"construct": {"rna_length": v(60), "protein_length": v(98)},
            "inventory": {"counts": {"excluded": v(excluded, "summary.json#/inventory/counts/excluded"),
                                     "unrecognised": v(unrec, "summary.json#/inventory/counts/unrecognised")},
                          "runs": [{"run": r} for r in runs], "structures": []},
            "agreement": [{"surface_agreement": v(surface, "summary.json#/repeat_agreement/E/surface_agreement"),
                           "register_agreement": v(register, "summary.json#/repeat_agreement/E/register_agreement")}],
            "single_structure_contacts": {"listed": [{"label": "R18-A21", "rna_position": 21}, {"label": "D39-U15", "rna_position": 15}]},
            "region_outputs": [], "unavailable": [{"item": "diagnose"}], "rna_positions_in_contact": v([15, 21]),
            "analyses_run": [], "initial_result": {}}


def test_rule_l3_uses_the_declared_margin():
    s = F.suggest_local(_synthetic(0.90, 0.70))
    l3 = [x for x in s if x["rule"] == "L3"]
    assert l3 and l3[0]["id"] == "compare_runs_in_region" and (l3[0]["args"]["rna_start"], l3[0]["args"]["rna_end"]) == (15, 21)
    assert l3[0]["reason_slots"]["margin"] == {"constant": "surface_register_margin", "value": 0.2}
    assert not [x for x in F.suggest_local(_synthetic(0.89, 0.70)) if x["rule"] == "L3"]
    assert [x["id"] for x in F.suggest_local(_synthetic(0.90, 0.70, runs=("r1",))) if x["rule"] == "L3"] == ["inspect_region_contacts"]


def test_rule_l1_inventory_first_and_l2_unavailable():
    s = F.suggest_local(_synthetic(0.5, 0.5, excluded=2), "Can Diagnose explain this?")
    assert s[0]["rule"] == "L1" and s[0]["id"] == "retrieve_contributing_structures" and s[0]["args"]["query"] == "excluded"
    assert any(x["rule"] == "L2" and x["args"]["metric"] == "diagnose" for x in s)


def test_local_suggestions_on_the_example_drop_repeats(pa):
    P, A = pa
    S = F.build_summary(P, A, Q)
    s = F.suggest_local(S, Q)
    verdicts = [F.policy_check({"follow_up": x["id"], "args": x["args"]}, S, Q, {}) for x in s]
    assert [x["rule"] for x in s] == ["L4", "L4", "L7"] and [v["rule"] for v in verdicts] == [None, None, "F5"]


# ---------------------------------------------------------------- policy
@pytest.mark.parametrize("prop,rule", [
    (P_("inspect_everything"), "F1"),
    (P_("geometry_four_axis"), "F3"), (P_("ranking"), "F3"), (P_("diagnose_interpretation"), "F3"), (P_("grouping_as_selection"), "F3"),
    (P_("structure_prediction"), "F3"), (P_("mutation_advice"), "F3"),
    (P_("inspect_region_contacts", rna_start=50, rna_end=99), "F2"),
    (P_("inspect_region_contacts", rna_start=20, rna_end=13), "F2"),
    (P_("inspect_region_contacts", rna_start=True, rna_end=23), "F2"),
    (P_("inspect_region_contacts", rna_start=13, rna_end=23, protein_start=5), "F2"),
    (P_("inspect_region_contacts", rna_start=13, rna_end=23, metric="diagnose"), "F2"),
    (P_("compare_runs_in_region", rna_start=13, rna_end=23, runs=["exec_A", "exec_A"]), "F2"),
    (P_("compare_runs_in_region", rna_start=13, rna_end=23, runs=["exec_A", "exec_Z"]), "F2"),
    (P_("retrieve_contributing_structures", query="contact", contact="K99-G1"), "F2"),
    (P_("inspect_existing_comparison", evidence_id="../../etc/passwd#/x"), "F2"),
    (P_("inspect_existing_comparison", evidence_id="summary.json#/not/in/summary"), "F2"),
    (P_("explain_unavailable_metric", metric="coffee"), "F2"),
    ("inspect_region_contacts", "F8"), ({"follow_up": "none"}, "F8"),
    ({"follow_up": "none", "args": {"bogus": 1}}, "F8"),
    (P_("compare_runs_in_region", rna_start=13, rna_end=23, runs=["exec_A", "exec_B"]), "F5"),
    (P_("inspect_region_contacts", rna_start=1, rna_end=5), "F9"),
    (P_("export_table_or_methods", export="methods"), "F9"),
    (P_("explain_unavailable_metric", metric="geometry_four_axis"), "F9"),
    (P_("inspect_existing_comparison", evidence_id=EB), None),
    (P_("none"), None),
])
def test_policy_rules(pa, prop, rule):
    P, A = pa
    S = F.build_summary(P, A, Q)
    v = F.policy_check(prop, S, Q, {})
    assert v["rule"] == rule and v["approved"] == (rule is None), v


def test_policy_circular_and_budget(pa, monkeypatch):
    P, A = pa
    S = F.build_summary(P, A, Q)
    p = P_("inspect_existing_comparison", evidence_id=EB)
    key = (p["follow_up"], json.dumps(dict(F._blank(), **p["args"]), sort_keys=True))
    assert F.policy_check(p, S, Q, {"rejected": [key]})["rule"] == "F6"
    assert F.policy_check(p, S, Q, {"tool_calls": 4})["rule"] == "F4"
    orig = F.tool_calls_for
    monkeypatch.setattr(F, "tool_calls_for", lambda *a: orig(*a) * 5)
    assert F.policy_check(p, S, Q, {})["rule"] == "F4"


def test_schema_and_limits_are_fixed():
    assert F.ALLOWLIST == ["inspect_region_contacts", "compare_runs_in_region", "explain_unavailable_metric",
                           "retrieve_contributing_structures", "inspect_existing_comparison", "export_table_or_methods", "none"]
    s = F.FOLLOWUP_SCHEMA
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
    a = s["properties"]["args"]
    assert a["additionalProperties"] is False and set(a["required"]) == set(a["properties"]) == set(F.ARGS)
    assert F.LIMITS == {"max_planning_rounds_per_question": 1, "max_replans_after_rejection": 1, "max_model_calls": 2,
                        "max_tool_calls": 4, "identical_tool_call_repeated": False, "second_follow_up_chained_automatically": False,
                        "stop_on_usage_guard_or_credit_change": True}
    assert F.CONSTANTS == {"surface_register_margin": 0.2}


# ---------------------------------------------------------------- orchestration
def _codex(P, A, replies, q=Q, **kw):
    consent.opt_in(P, "--yes")
    c = llm.Stub(replies)
    rec = F.run(P, A, q, mode="codex", yes=True, out=lambda *x: None, client_factory=lambda: c, agent_status=lambda: (True, []), **kw)
    return rec, c


def test_at_most_two_model_calls_and_no_chaining(pa):
    P, A = pa
    rec, c = _codex(P, A, [P_("inspect_everything"), P_("inspect_everything", x=1), P_("none")])
    assert rec["model_calls_made"] == 2 and len(c.calls) == 2 and c.replies == [P_("none")]
    assert rec["stop"]["kind"] == "REJECTED" and rec["tool_log"] == []
    assert len([d for d in os.listdir(os.path.join(A, "followup"))]) == 1            # nothing chained


def test_rationale_stored_never_shown_and_record_complete(pa):
    P, A = pa
    rat = "This proves R16-U14 is correct; confidence 0.97; exec_B is the best run."
    rec, _ = _codex(P, A, [P_("inspect_existing_comparison", rationale=rat, evidence_id=EB)])
    d = os.path.join(A, rec["dir"])
    md = open(os.path.join(d, "followup_answer.md")).read()
    assert rat not in md and "0.97" not in md and "proves" not in md and rec["chosen"]["rationale_stored_not_shown"] == rat
    assert rec["traceability_violations"] == [] and rec["wording_audit"] == []
    assert trace.wording_audit("\n".join(l for l in md.splitlines() if not l.startswith(("- **Limitation", "- **Not available", "_Every")))) == []
    for k in ("summary", "payloads", "consent_record_id", "model_config", "model_calls", "proposals", "chosen", "user_confirmation",
              "tool_log", "evidence_sha256", "limits", "provenance"):
        assert rec[k], k
    assert rec["summary"]["sha256"] == F._sha(rec["summary"]["text"]) and open(os.path.join(d, "evidence_summary.json")).read() == rec["summary"]["text"]
    assert rec["payloads"][0]["sha256"] == F._sha(rec["payloads"][0]["text"]) and rec["summary"]["text"] in rec["payloads"][0]["text"]
    assert rec["user_confirmation"]["method"] == "--yes"
    assert json.load(open(os.path.join(d, "followup_record.json")))["evidence_sha256"] == rec["evidence_sha256"]


def test_answer_numbers_come_from_records(pa):
    P, A = pa
    rec, _ = _codex(P, A, [P_("compare_runs_in_region", rna_start=40, rna_end=59, runs=["exec_A", "exec_B"])],
                    q="Do the runs differ at RNA positions 40-59?")
    st = json.load(open(os.path.join(A, rec["dir"], "followup_answer.json")))["statements"]
    reg = json.load(open(os.path.join(A, "region_40-59", "region.json")))
    obs = [s for s in st if s["type"] == "OBSERVATION"]
    assert obs[0]["slots"]["n"]["value"] == reg["summary"]["n_contacts_in_range"]["count"]
    toks = F.allowed_tokens(F.build_summary(P, A))
    args = rec["chosen"]["args"]
    assert F.check_traceable(st, A, args, rec["tool_log"], toks) == []
    bad = copy.deepcopy(st); bad[0]["text"] += " About 12 contacts."
    assert any(v.startswith("T1") for v in F.check_traceable(bad, A, args, rec["tool_log"], toks))
    bad = copy.deepcopy(st); obs_i = st.index(obs[0]); bad[obs_i]["slots"]["n"]["value"] += 1
    assert any(v.startswith("T2") for v in F.check_traceable(bad, A, args, rec["tool_log"], toks))
    bad = copy.deepcopy(st); bad[0]["slots"]["x"] = {"text": "0.5 agreement"}; bad[0]["text"] += " {x}"
    assert any(v.startswith("T3") for v in F.check_traceable(bad, A, args, rec["tool_log"], toks))
    assert F.check_traceable([], A, args, [], toks) == ["T0 no statements"]


def test_refused_tool_is_recorded_not_hidden(pa, monkeypatch):
    P, A = pa
    from rnplens import region
    monkeypatch.setattr(region, "capability_run", lambda *a, **k: {"status": "REFUSED", "outputs": [], "message": "range refused at /tmp/x/y.json"})
    rec, _ = _codex(P, A, [P_("compare_runs_in_region", rna_start=40, rna_end=59, runs=["exec_A", "exec_B"])], q="Differences at RNA 40-59?")
    assert rec["tool_log"][0]["status"] == "REFUSED" and "<path>/y.json" in rec["tool_log"][0]["message"]
    md = open(os.path.join(A, rec["dir"], "followup_answer.md")).read()
    assert "did not give a result (REFUSED)" in md and rec["traceability_violations"] == []


def test_identical_tool_call_not_repeated(pa):
    P, A = pa
    S = F.build_summary(P, A, Q)
    calls = F.tool_calls_for("inspect_existing_comparison", dict(F._blank(), evidence_id=EB), S)
    sess, log = {"all_runs": ["exec_A", "exec_B"]}, []
    F.execute(calls + calls, P, A, sess, log)
    assert [e["status"] for e in log] == ["OK", "REFUSED_REPEAT"] and sess["tool_calls"] == 1


def test_local_follow_up_worked_example_and_replay(pa, tmp_path):
    P, A = pa
    snap = str(tmp_path / "snap"); import shutil; shutil.copytree(A, snap)
    spawned = []
    real = subprocess.run
    def guard(args, *a, **k):
        if "codex" in " ".join(map(str, args if isinstance(args, (list, tuple)) else [args])):
            spawned.append(args)
        return real(args, *a, **k)
    subprocess.run = guard
    try:
        rec = F.run(P, A, Q, mode="local", yes=True, out=lambda *x: None)
    finally:
        subprocess.run = real
    assert not spawned and rec["model_calls_made"] == 0 and rec["chosen"]["source"] == "local" and rec["chosen"]["rule"] == "L4"
    plan = os.path.join(A, rec["dir"], "followup_plan.json")
    assert F.replay_plan(plan, P, A)[0] == rec["evidence_sha256"]
    assert F.replay_plan(plan, P, snap)[0] == rec["evidence_sha256"]                 # moved, pre-follow-up copy
    from rnplens_assistant.__main__ import main
    assert main(["replay-followup", plan, "--project", P, "--analysis", snap]) == 0


def test_round_limit_per_question(pa):
    P, A = pa
    _codex(P, A, [P_("none")])
    rec, c = _codex(P, A, [P_("none")])
    assert rec["stop"]["kind"] == "ROUND_USED" and c.calls == []
    rec, c = _codex(P, A, [P_("none")], q=Q + " (another question)")
    assert rec["stop"] is None and len(c.calls) == 1


def test_not_confirmed_runs_nothing(pa):
    P, A = pa
    consent.opt_in(P, "--yes")
    c = llm.Stub([P_("inspect_existing_comparison", evidence_id=EB)])
    rec = F.run(P, A, Q, mode="codex", yes=False, ask=lambda p: "n", out=lambda *x: None, client_factory=lambda: c, agent_status=lambda: (True, []))
    assert rec["stop"]["kind"] == "NOT_CONFIRMED" and rec["tool_log"] == [] and rec["user_confirmation"]["answer"] == "n"


def test_agent_not_ready_means_local_only(pa):
    P, A = pa
    consent.opt_in(P, "--yes")
    rec = F.run(P, A, Q, mode="codex", yes=True, out=lambda *x: None, client_factory=lambda: 1 / 0,
                agent_status=lambda: (False, ["Codex CLI: not found"]))
    assert rec["stop"]["kind"] == "AGENT_NOT_READY" and rec["model_calls_made"] == 0 and rec["mode"] == "local (fallback)"


def test_malformed_and_missing_inputs(pa, tmp_path):
    P, A = pa
    with pytest.raises(FileNotFoundError):
        F.build_summary(P, str(tmp_path / "nope"), Q)
    os.makedirs(os.path.join(A, "followup", "fu_0001"))
    rec = F.run(P, A, Q, mode="local", yes=True, out=lambda *x: None)
    assert rec["dir"] == "followup/fu_0002"


def test_docs_page_states_limits_and_passes_the_wording_audit():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = open(os.path.join(root, "docs", "followup.md"), encoding="utf-8").read()
    sp = open(os.path.join(root, "docs", "setup_and_privacy.md"), encoding="utf-8").read()
    assert "## Interpretation limits" in d and "EXPERIMENTAL" in d and "## Local-only mode" in d and "## Worked example" in d
    for fid in F.ALLOWLIST:
        assert fid in d
    for k, v in F.LIMITS.items():
        assert isinstance(v, (bool, int))
    assert "presentation rule" in d and "0.2" in d and "followup.md" in sp and "consent.json" in sp
    assert trace.wording_audit(d) == [] and trace.wording_audit(sp) == []
    assert trace.wording_audit(open(os.path.join(os.path.dirname(F.__file__), "prompts", "followup.md")).read()) == []
