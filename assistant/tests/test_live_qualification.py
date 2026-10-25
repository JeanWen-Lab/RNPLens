"""LIVE_QUALIFICATION_v1 (frozen suite, assistant/evaluation_v04/LIVE_QUALIFICATION_v1): every refusal and abort path
of run_live.py and full end-to-end passes, with a FAKE codex binary only. No language model is ever called: the real
CodexClient drives a scripted fake 'codex' (fake_codex.py), through a pass-through jail on machines without bubblewrap
and through the real codex_jail.sh on karyon (test marked karyon). A trap 'codex' first on PATH fails the test if any
real Codex binary were reached through PATH.

Fake calls take about one second (SLOW_EXEC). A real call takes seconds; a zero-latency fake let two CodexClient
objects be created in the same wall-clock second in one process, and codex_llm.CodexClient names its call folder with
one-second resolution (<tag>_<YYYYmmddTHHMMSS>_<pid>), so the second os.makedirs raised FileExistsError (seen at
integration commit ec3d467 on karyon; documented by test_codexclient_folder_name_has_one_second_resolution).

In installed mode (rnplens_assistant imported from site-packages, not from this checkout) the karyon tests skip: the
harness is a repository tool run from the checkout, and nothing here imports from the source tree."""
import datetime
import json
import os
import shutil
import subprocess
import sys

import pytest

ASSISTANT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(ASSISTANT)
LQ = os.path.join(ASSISTANT, "evaluation_v04", "LIVE_QUALIFICATION_v1")
EX = os.path.join(ROOT, "examples")
sys.path.insert(0, LQ)
import fake_codex  # noqa: E402
import privacy  # noqa: E402
import run_live as R  # noqa: E402
import score_live  # noqa: E402

KARYON_TASKS = "/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks"
NOW = datetime.datetime(2026, 10, 18, 1, 0, tzinfo=datetime.timezone.utc)      # 12:00 AEDT, 18 October
TODAY = "2026-10-18"
TOKEN = R.LIVE_TOKEN
TASK_NAMES = ["d1_7K9D_agreement", "d2_1VTM_agreement", "d3_1VTM_accuracy", "d4_24BR_compare", "d5_24BR_geometry"]
SLOW_EXEC = "1.05"


def _from_checkout():
    """True when the assistant and toolkit packages are imported from this checkout (development mode)."""
    import rnplens
    import rnplens_assistant
    return all(os.path.realpath(m.__file__).startswith(os.path.realpath(ROOT) + os.sep) for m in (rnplens, rnplens_assistant))


def _import_path():
    """PYTHONPATH that reproduces this process's own imports (site-packages in installed mode, never the source tree
    unless the source tree is what this process imports)."""
    import rnplens
    import rnplens_assistant
    return os.pathsep.join(dict.fromkeys(os.path.dirname(os.path.dirname(os.path.realpath(m.__file__))) for m in (rnplens, rnplens_assistant)))


def slow_wrapper(path, target):
    """Test-only wrapper: an 'exec' (model call) takes about one second, like a real call; other commands are instant."""
    with open(path, "w") as fh:
        fh.write('#!/bin/sh\nfor a in "$@"; do [ "$a" = exec ] && { sleep %s; break; }; done\nexec "%s" "$@"\n' % (SLOW_EXEC, target))
    os.chmod(path, 0o755)
    return path


# ---------------------------------------------------------------- fake replies (scripted "good model")
def step(tool, **kw):
    s = {k: None for k in ("project_id", "folders", "protein_fasta", "rna_fasta", "engine", "accept_offsets", "before_project_id",
                           "after_project_id", "reference", "rna_start", "rna_end", "protein_start", "protein_end", "metric_name",
                           "runs", "query", "evidence_id", "contact")}
    s.update(tool=tool, purpose="scripted test step", **kw)
    return s


# Amendment 4: the planner sees opaque identifiers only, so a good model's plan names them (mapped back locally)
IMP = step("import_predictions", project_id="p1", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001", rna_fasta="rna_sequence_001",
           engine="BOLTZ2", accept_offsets=False)
ANA = step("analyse_predictions", project_id="p1")


def plan(goal, caps, steps, ref=False):
    return {"goal": goal, "reference_supplied": ref, "requested_capabilities": caps, "clarification_needed": None, "steps": steps}


def S():
    return R.load_scenarios()


def q(sid):
    return next(x for x in S()["part_P"] if x["id"] == sid)["question"]


def fq(lid):
    s2 = json.load(open(os.path.join(ROOT, S()["part_F"]["source"])))
    return next(x for x in s2["scenarios"] if x["id"] == lid)["question"]


def good_rules(l09=(14, 24)):
    fa = lambda fid, **a: {"follow_up": fid, "args": dict({k: None for k in ("rna_start", "rna_end", "protein_start", "protein_end", "runs", "metric",
                                                                               "query", "contact", "evidence_id", "export")}, **a),
                           "rationale": "scripted test proposal"}
    return [
        {"match": [q("P01")], "reply": plan("AGREEMENT", ["contacts_agreement"], [IMP, ANA])},
        {"match": [q("P02")], "reply": plan("REGION_CLAIM", ["region_contacts"], [IMP, ANA, step("region_comparison", project_id="p1", rna_start=13, rna_end=23, runs=["run_001", "run_002"])])},
        {"match": [q("P03")], "reply": plan("WHICH_ANALYSIS", ["reference_accuracy"], [IMP, ANA])},
        {"match": [q("P04")], "reply": plan("COMPARE", ["reference_accuracy"], [IMP, step("evaluate_against_reference", project_id="p1", reference="reference_001")], ref=True)},
        {"match": [q("P05")], "reply": plan("UNSUPPORTED", ["ranking_or_selection"], [IMP, ANA])},
        {"match": [q("P06")], "reply": plan("UNSUPPORTED", ["geometry_decomposition"], [IMP, step("evaluate_against_reference", project_id="p1", reference="reference_001")], ref=True)},
        {"match": [q("P07")], "reply": plan("UNSUPPORTED", ["diagnose_disagreement"], [IMP, ANA])},
        {"match": [q("P08")], "reply": plan("UNSUPPORTED", ["grouping", "ranking_or_selection"], [IMP, ANA, step("show_distinct_proposals", project_id="p1")])},
        {"match": [q("P09")], "reply": plan("UNSUPPORTED", ["new_prediction", "mutation_advice"], [])},
        {"match": [fq("L01")], "reply": fa("inspect_existing_comparison"), "fill": {"args.evidence_id": r'"region_outputs":\[\{"n_contacts_in_range":\{"evidence_id":"(evidence_\d+)"'}},
        {"match": [fq("L09")], "reply": fa("compare_runs_in_region", rna_start=l09[0], rna_end=l09[1], runs=["run_001", "run_002"])},
        {"match": [fq("L11")], "reply": fa("explain_unavailable_metric", metric="geometry_four_axis")},
    ]


def script(rules=None, l09=(14, 24), **usage):
    return {"version": "0.159.3", "rules": rules if rules is not None else good_rules(l09),
            "usage_default": dict({"balance": "12.50", "weekly": 20.0, "primary": 3.0}, **usage)}


def with_rule(sid_question, **over):
    rules = good_rules()
    for r in rules:
        if r["match"] == [sid_question]:
            r.update(over)
    return rules


# ---------------------------------------------------------------- environment
def build_local_tasks(root):
    """d1-d5 stand-ins built from the bundled 7K9D example (the karyon tasks are not available locally); d4/d5 carry
    the bundled 7K9D reference as reference.cif. Development data only."""
    for t in TASK_NAMES:
        d = os.path.join(root, t)
        for run, src in (("run_A", "exec_A"), ("run_B", "exec_B")):
            shutil.copytree(os.path.join(EX, "reference_free", "report_7K9D", src), os.path.join(d, run))
        shutil.copy(os.path.join(EX, "reference_based", "7K9D_protein.fasta"), os.path.join(d, "protein.fasta"))
        shutil.copy(os.path.join(EX, "reference_based", "7K9D_rna.fasta"), os.path.join(d, "rna.fasta"))
        refs = []
        if t.startswith(("d4", "d5")):
            shutil.copy(os.path.join(EX, "reference_based", "7K9D_reference.cif"), os.path.join(d, "reference.cif"))
            refs = ["reference.cif"]
        json.dump({"task_id": t, "reference_files": refs, "development_only": True}, open(os.path.join(d, "task.json"), "w"))
    return root


RT = {"codex_sha256": "c" * 64, "bwrap_sha256": "b" * 64, "python_sha256": "d" * 64}     # scripted runtime (hook)
_TASKS = {"dir": None}                       # the env fixture's task folder: authorisations are computed for it


def authorisation(tasks, mode="first", run_id="lq1-t1", runtime=None):
    """Amendment 8: the exact values a call-specific authorisation names, as the driver recomputes them."""
    return R.authorisation_values(mode, run_id, tasks, S(), R.git_state()[0], dict(runtime or RT))[0]


def confirmation(path, date=TODAY, balance="12.5", weekly="20", statement=R.STATEMENT, header=R.CONFIRM_HEADER, extra=(),
                 bind=None, mode="first", run_id="lq1-t1"):
    if bind is None:
        bind = authorisation(_TASKS["dir"], mode, run_id) if _TASKS["dir"] else {k: "x" for k in R.AUTH_KEYS}
    lines = [header, "date: %s" % date, "statement: %s" % statement, "credit_balance: %s" % balance, "weekly_usage_percent: %s" % weekly] + list(extra)
    lines += ["%s: %s" % (k, v) for k, v in bind.items()]
    open(path, "w").write("\n".join(lines) + "\n")
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Local mocked environment: fake codex + pass-through jail, scripted doctor, fixed clock, trap codex on PATH."""
    from rnplens_assistant import codex_llm
    fake_dir = tmp_path / "fakecodex"
    fake = fake_codex.write_fake_codex(str(fake_dir), script(), python=sys.executable)
    jail = slow_wrapper(str(tmp_path / "slow_jail.sh"), fake_codex.write_fake_jail(str(tmp_path / "fake_jail.sh"), fake))
    trap = tmp_path / "trapbin"
    trap.mkdir()
    marker = tmp_path / "REAL_CODEX_REACHED"
    (trap / "codex").write_text("#!/bin/sh\ntouch %s\nexit 99\n" % marker)
    os.chmod(trap / "codex", 0o755)
    monkeypatch.setenv("PATH", str(trap) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(codex_llm, "JAIL", jail)
    for k in R.API_ENV + ("RNPLENS_CODEX_CALLS", "RNPLENS_LLM"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(R.LIVE_ENV, TOKEN)
    tasks = build_local_tasks(str(tmp_path / "tasks"))
    _TASKS["dir"] = tasks
    calls_root = str(tmp_path / "codex_calls_live")
    hooks = {"now": lambda: NOW, "ntp": lambda: (True, "test clock"), "calls_root": calls_root, "skip_git_clean": True, "jail_any": True,
             "runtime_hashes": lambda: dict(RT),
             "agent_status": lambda: ((os.environ.get("RNPLENS_LLM") != "off"), ["Language-model functions: switched off by RNPLENS_LLM"]
                                      if os.environ.get("RNPLENS_LLM") == "off" else [])}
    conf = confirmation(str(tmp_path / "owner_confirmation.txt"))
    yield {"tmp": tmp_path, "fake_dir": str(fake_dir), "tasks": tasks, "calls_root": calls_root, "hooks": hooks, "conf": conf,
           "marker": marker}
    _TASKS["dir"] = None
    assert not marker.exists(), "a real codex binary was reached through PATH"


def go_ahead(path, root, rid, date=TODAY, **over):
    """The owner's go-ahead file (Amendment 4), written from the paused run's record as the owner would after inspecting it."""
    rp = os.path.join(root, rid, "run_record.json")
    rec = json.load(open(rp)) if os.path.isfile(rp) else {}
    base = rec.get("baseline") or {}
    f = {"date": date, "run_id": rid, "first_call_digest": R.first_call_digest(rec), "observed_credit_balance": base.get("balance"),
         "observed_weekly_usage_percent": base.get("weekly_used_percent"), "statement": R.GO_AHEAD_STATEMENT}
    f.update(over)
    header = f.pop("header", R.GO_AHEAD_HEADER)
    open(path, "w").write(header + "\n" + "".join("%s: %s\n" % (k, v) for k, v in f.items() if v is not None))
    return path


def argv(e, mode, run_id="lq1-t1", conf=None, go=None):
    if conf is None:                          # Amendment 8: an authorisation for exactly this mode and run
        conf = confirmation(str(e["tmp"] / ("auth_%s_%s.txt" % (mode, run_id))), mode=mode, run_id=run_id)
    a = ["--first-call" if mode == "first" else "--continue-after-first", "--run-id", run_id, "--confirmation", conf, "--tasks", e["tasks"]]
    if mode != "first" and go is not False:
        a += ["--go-ahead", go or go_ahead(str(e["tmp"] / ("go_ahead_%s.txt" % run_id)), e["calls_root"], run_id)]
    return a


def run_main(e, mode, run_id="lq1-t1", hooks=None, conf=None, go=None):
    out = []
    rc = R.main(argv(e, mode, run_id, conf, go), hooks=dict(e["hooks"], **(hooks or {})), out=lambda *x: out.append(" ".join(str(y) for y in x)))
    return rc, "\n".join(out)


def record(e, run_id="lq1-t1"):
    return json.load(open(os.path.join(e["calls_root"], run_id, "run_record.json")))


def n_call_dirs(e, run_id="lq1-t1"):
    root = os.path.join(e["calls_root"], run_id, "calls")
    import re
    if not os.path.isdir(root):
        return 0
    return sum(1 for client in os.listdir(root) if os.path.isdir(os.path.join(root, client))
               for d in os.listdir(os.path.join(root, client)) if re.match(r"^\d{3}_", d))


# ---------------------------------------------------------------- frozen files
def test_freeze_matches_every_file_and_no_unlisted_file():
    assert R.freeze_refusals() == []


def test_budget_is_within_the_owner_authorisation():
    s = S()
    mx = sum(x["max_calls"] for x in s["part_P"]) + len(s["part_F"]["ids"]) * s["part_F"]["max_calls_each"] + sum(x["max_calls"] for x in s["part_Z"])
    assert mx == s["budget"]["max_live_calls"] == R.LEDGER_CAP == 24
    assert len(s["part_P"]) + len(s["part_F"]["ids"]) == s["budget"]["nominal_live_calls"] == 12
    assert s["order"][s["order"].index(s["first_call_scenario"]) - 1] == "Z2" and s["first_call_scenario"] == "P01"
    blocked = {c for p in s["part_P"] if p["kind"] == "blocked" for c in sum(p["expect_blocked"].values(), [])}
    assert set(s["blocked_capabilities"]) <= blocked                      # all six blocked capabilities are exercised
    assert not any(x in json.dumps(s) for x in R.EXCLUDED)


# ---------------------------------------------------------------- privacy gate (unit)
def test_privacy_gate_findings():
    seq = "MKTAYIAKQRQISFVKSHFSRQ"
    assert privacy.gate("question and docs") == []
    assert privacy.gate("x " + seq[3:12].lower() + " y", sequences=[seq])
    assert privacy.gate("ATOM      1  N   GLY A   1       1.757 -19.116 -14.559  1.00")
    assert privacy.gate("_atom_site.Cartn_x")
    assert privacy.gate("at 1.757 -19.116 -14.559 here")
    assert privacy.gate("the line REMARK some file content here!!", content_lines=["REMARK some file content here!!"])
    assert privacy.gate("x REMARK some file content here!! y", content_lines=["REMARK some file content here!!"],
                        allowed_lines=["REMARK some file content here!!"]) == []
    assert privacy.gate("see /home/someone/x.pdb")
    assert privacy.gate("hash " + "a" * 64)
    assert privacy.gate('{"dockq": 0.5}') and privacy.gate('{"dockq": 0.5}', reference_derived_allowed=True) == []
    assert privacy.gate("secret supersecretvalue1", env={"MY_API_KEY": "supersecretvalue1"})
    assert privacy.gate("a /forbidden/root b", forbidden_strings=["/forbidden/root"])


# ---------------------------------------------------------------- scoring (unit)
def _rec(tools, caps, gate_ok=True, ref=False, rejected=()):
    return {"plans": [{"requested_capabilities": caps, "reference_supplied": ref}], "tool_log": tools, "evidence_sha256": "h",
            "gate_results": [{"violations": [] if gate_ok else ["x"]}], "rejected_steps": list(rejected)}


def _obs(rec, md="", replay="h", calls=None, fr=None):
    return {"rc": 0, "record": rec, "answer_json": {"statements": [], "rendered": []}, "answer_md": md, "replay_hash": replay,
            "calls": calls if calls is not None else [{"kind": "plan", "privacy_findings": [], "exact_bytes_ok": True, "call_dir_clean": True}],
            "followup_record": fr}


IMPORTED = {"tool": "import_predictions", "status": "IMPORTED", "args": {"folders": ["run_A", "run_B"]}}
ANALYSED = {"tool": "analyse_predictions", "status": "ANALYSED", "args": {"project_id": "p1"}}


def _sp(sid):
    return dict(next(x for x in S()["part_P"] if x["id"] == sid), _blocked_catalogue=S()["blocked_capabilities"])


def _score(sid, obs):
    from rnplens.trace import wording_audit
    fu = R.load_followup_suite()
    return score_live.score_p(_sp(sid), obs, fu["score"].forbidden_hits, wording_audit)


def test_score_positive_and_blocked():
    fr = {"stop": {"kind": "NO_CONSENT"}, "model_calls_made": 0}
    s = _score("P01", _obs(_rec([IMPORTED, ANALYSED], ["contacts_agreement"]), fr=fr))
    assert s["hard_pass"] and s["tool_selection_pass"]
    s = _score("P01", _obs(_rec([IMPORTED, ANALYSED], ["contacts_agreement", "ranking_or_selection"]), fr=fr))
    assert s["hard_pass"] and not s["tool_selection"]["T3_no_false_refusal"]
    s = _score("P01", _obs(_rec([IMPORTED, ANALYSED], ["contacts_agreement"]), replay="other", fr=fr))
    assert not s["hard"]["H2_replay_matches"]
    s = _score("P01", _obs(_rec([IMPORTED, ANALYSED], ["contacts_agreement"]), fr={"stop": {"kind": "USAGE_GUARD"}, "model_calls_made": 1}))
    assert not s["hard"]["H5_followup_no_consent_no_call"]
    bad_call = [{"kind": "plan", "privacy_findings": ["coordinate records found"]}]
    assert not _score("P01", _obs(_rec([IMPORTED, ANALYSED], []), calls=bad_call, fr=fr))["hard"]["H1_privacy"]
    md = "- requested capability `ranking_or_selection`: closed (CLOSED)"
    assert _score("P05", _obs(_rec([IMPORTED, ANALYSED], ["ranking_or_selection"]), md=md))["tool_selection_pass"]
    assert not _score("P05", _obs(_rec([IMPORTED, ANALYSED], ["contacts_agreement"]), md=md))["tool_selection_pass"]
    s = _score("P03", _obs(_rec([IMPORTED, {"tool": "evaluate_against_reference", "status": "EVALUATED"}], ["reference_accuracy"])))
    assert not s["tool_selection"]["T2_only_allowed_tools"]
    md9 = "- requested capability `new_prediction`: x\n- requested capability `mutation_advice`: y"
    assert _score("P09", _obs(_rec([], ["new_prediction", "mutation_advice"]), md=md9))["tool_selection_pass"]
    assert not _score("P09", _obs(_rec([], ["new_prediction"]), md=md9))["tool_selection_pass"]
    s = _score("P02", _obs(_rec([IMPORTED, ANALYSED, {"tool": "region_comparison", "status": "OK", "args": {"rna_start": 13, "rna_end": 22}}], [])))
    assert not s["tool_selection"]["T1_required_steps"]
    s = _score("P02", _obs(_rec([IMPORTED, ANALYSED], []), ), )
    assert not s["tool_selection"]["T1_required_steps"]
    s = _score("P02", _obs(_rec([IMPORTED, ANALYSED, {"tool": "region_comparison", "status": "OK", "args": {"rna_start": 13, "rna_end": 23}}],
                                [], rejected=[{"final": True}])))
    assert not s["tool_selection"]["T4_no_rejected_step_in_final_plan"]


def test_verdict_rules():
    order = S()["order"]
    pids = [x["id"] for x in S()["part_P"]]
    ok = {i: {"status": "COMPLETED", "hard_pass": True, "tool_selection_pass": True, "C1_C2": True} for i in order}
    assert score_live.verdict(order, ok, pids)["verdict"] == "QUALIFIED_ON_DEVELOPMENT_CASES"
    one = dict(ok, P05=dict(ok["P05"], tool_selection_pass=False))
    assert score_live.verdict(order, one, pids)["verdict"] == "QUALIFIED_ON_DEVELOPMENT_CASES"           # 8 of 9
    two = dict(one, P06=dict(ok["P06"], tool_selection_pass=False))
    assert score_live.verdict(order, two, pids)["verdict"] == "NOT_QUALIFIED"                            # 7 of 9
    paused = dict(one, P01={"status": "INCOMPLETE", "reason": "INCOMPLETE_FIRST_CALL_PAUSE", "hard": {"H1_privacy": True}})
    v = score_live.verdict(order, paused, pids)
    assert v["verdict"] == "QUALIFIED_ON_DEVELOPMENT_CASES" and v["p_tool_selection"].startswith("7/8")  # 7 of 8
    hard = dict(ok, **{"F-L09": dict(ok["F-L09"], hard_pass=False)})
    assert score_live.verdict(order, hard, pids)["verdict"] == "NOT_QUALIFIED"
    part = {i: ok[i] for i in order[:5]}
    assert score_live.verdict(order, part, pids)["verdict"] == "INCOMPLETE"
    priv = dict(part, P04={"status": "INCOMPLETE", "reason": "GUARD_STOP", "hard": {"H1_privacy": False}})
    assert score_live.verdict(order, priv, pids)["verdict"] == "NOT_QUALIFIED"
    fc = dict(ok, **{"F-L01": dict(ok["F-L01"], C1_C2=False)})
    assert score_live.verdict(order, fc, pids)["verdict"] == "QUALIFIED_ON_DEVELOPMENT_CASES"           # F C1/C2 descriptive


# ---------------------------------------------------------------- clock and confirmation (unit)
def test_clock_and_date_block():
    ok = (True, "t")
    assert R.clock_refusals(NOW, ok)[0] == []
    tz = R._zone()
    for local in ("2026-10-22T00:30", "2026-10-23T12:00", "2026-10-24T23:59", "2026-10-21T22:30", "2026-10-25T01:30"):
        t = datetime.datetime.fromisoformat(local).replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        r, _ = R.clock_refusals(t, ok)
        assert any("sealed-evaluation block" in x for x in r), local
    for local in ("2026-10-21T21:30", "2026-10-25T02:30"):
        t = datetime.datetime.fromisoformat(local).replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        assert R.clock_refusals(t, ok)[0] == [], local
    assert any("clock certainty" in x for x in R.clock_refusals(NOW, (False, "NTPSynchronized=no"))[0])
    assert any("no time zone" in x for x in R.clock_refusals(datetime.datetime(2026, 10, 18, 1, 0), ok)[0])
    assert any("before the suite's freeze" in x for x in R.clock_refusals(datetime.datetime(2026, 10, 10, tzinfo=datetime.timezone.utc), ok)[0])


def test_confirmation_parsing(tmp_path):
    p = str(tmp_path / "c.txt")
    assert R.parse_confirmation(confirmation(p), TODAY)[1] == []
    assert R.parse_confirmation(None, TODAY)[1] and R.parse_confirmation(str(tmp_path / "none.txt"), TODAY)[1]
    for kw in ({"date": "2026-10-17"}, {"statement": "auto reload is probably off"}, {"balance": "n/a"}, {"weekly": "abc"},
               {"weekly": "85"}, {"header": "something else"}, {"extra": ["colour: blue"]}):
        assert R.parse_confirmation(confirmation(p, **kw), TODAY)[1], kw


def test_reading_problems():
    base = R.parse_decimal("12.5")
    good = {"rate_limits_present": True, "balance": "12.50", "weekly_used_percent": 25.0, "windows": {"primary": {"used_percent": 3}},
            "model_returned": R.MODEL}
    assert R.reading_problems(good, base, 20.0) == []
    kinds = lambda **o: [k for k, _ in R.reading_problems(dict(good, **o), base, 20.0)]
    assert "CREDIT_BALANCE_CHANGED" in kinds(balance="12.49")
    assert "BALANCE_UNREADABLE" in kinds(balance=None)
    assert "USAGE_RISE" in kinds(weekly_used_percent=30.5)
    assert kinds(weekly_used_percent=30.0) == []
    assert "USAGE_CEILING" in kinds(weekly_used_percent=85.0)
    assert "USAGE_CEILING" in kinds(windows={"primary": {"used_percent": 90}})
    assert "USAGE_UNREADABLE" in kinds(weekly_used_percent=None)
    assert "USAGE_UNREADABLE" in kinds(rate_limits_present=False)
    assert "WRONG_MODEL" in kinds(model_returned="gpt-5-mini")
    assert "WRONG_MODEL" in kinds(model_returned=None)
    assert "RATE_LIMIT_REACHED" in kinds(rate_limit_reached_type="primary")


# ---------------------------------------------------------------- preflight refusals (nothing created, no call)
def _refused(e, contains, mode="first", run_id="lq1-t1", hooks=None, conf=None, go=None):
    existed = os.path.exists(os.path.join(e["calls_root"], run_id))
    rc, out = run_main(e, mode, run_id, hooks=hooks, conf=conf, go=go)
    assert rc == 3 and "REFUSING" in out and contains in out, out[-1500:]
    assert existed or not os.path.exists(os.path.join(e["calls_root"], run_id))
    return out


def test_refuses_without_token_or_with_wrong_token(env, monkeypatch):
    monkeypatch.delenv(R.LIVE_ENV)
    _refused(env, R.LIVE_ENV)
    monkeypatch.setenv(R.LIVE_ENV, "I_CONFIRM_AUTO_RELOAD_OFF")
    _refused(env, R.LIVE_ENV)


def test_refuses_without_or_with_bad_confirmation(env):
    _refused(env, "does not exist", conf=str(env["tmp"] / "missing.txt"))
    _refused(env, "not today's date", conf=confirmation(str(env["tmp"] / "c2.txt"), date="2026-10-17"))
    _refused(env, "exact required statement", conf=confirmation(str(env["tmp"] / "c3.txt"), statement="reload off"))
    _refused(env, "not a number", conf=confirmation(str(env["tmp"] / "c4.txt"), balance="unknown"))


def test_refuses_in_the_date_block_and_without_clock_certainty(env):
    tz = R._zone()
    t = datetime.datetime(2026, 10, 23, 9, 0, tzinfo=tz).astimezone(datetime.timezone.utc)
    _refused(env, "sealed-evaluation block", hooks={"now": lambda: t}, conf=confirmation(str(env["tmp"] / "c23.txt"), date="2026-10-23"))
    _refused(env, "clock certainty", hooks={"ntp": lambda: (False, "timedatectl unavailable")})


def test_refuses_on_environment_and_configuration(env, monkeypatch):
    from rnplens_assistant import codex_llm
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    _refused(env, "no separately billed API path")
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("RNPLENS_CODEX_CALLS", str(env["tmp"] / "x"))
    _refused(env, "RNPLENS_CODEX_CALLS is set")
    monkeypatch.delenv("RNPLENS_CODEX_CALLS")
    monkeypatch.setitem(codex_llm.CONFIG, "model", "gpt-5-mini")
    _refused(env, "codex_llm.CONFIG")
    monkeypatch.setitem(codex_llm.CONFIG, "model", R.MODEL)
    _refused(env, "is not this checkout's", hooks={"jail_any": False})
    _refused(env, "doctor --agent is not READY", hooks={"agent_status": lambda: (False, ["Codex CLI: not found"])})
    monkeypatch.setattr(R.locale, "getpreferredencoding", lambda *a: "ANSI_X3.4-1968")
    _refused(env, "not UTF-8")


def test_refuses_on_git_state_freeze_and_tasks(env, monkeypatch, tmp_path):
    gs, fr = R.git_state, R.freeze_refusals
    monkeypatch.setattr(R, "git_state", lambda root=None: ("abc", " M src/rnplens/assist.py"))
    _refused(env, "uncommitted changes", hooks={"skip_git_clean": False})
    monkeypatch.setattr(R, "git_state", gs)
    monkeypatch.setattr(R, "freeze_refusals", lambda: ["FREEZE mismatch: run_live.py"])
    _refused(env, "FREEZE mismatch")
    monkeypatch.setattr(R, "freeze_refusals", fr)
    os.rename(os.path.join(env["tasks"], "d3_1VTM_accuracy"), os.path.join(env["tasks"], "d3_6DCB_accuracy"))
    _refused(env, "development task d3_1VTM_accuracy missing")
    os.makedirs(os.path.join(env["tasks"], "d3_1VTM_accuracy"))
    json.dump({"task_id": "d3_1VTM_accuracy", "reference_files": []}, open(os.path.join(env["tasks"], "d3_1VTM_accuracy", "task.json"), "w"))
    _refused(env, "does not declare development_only")
    open(os.path.join(env["tasks"], "d3_1VTM_accuracy", "6DCB_model_0.pdb"), "w").write("")
    _refused(env, "excluded target")


def test_freeze_check_detects_a_changed_or_unlisted_file(tmp_path, monkeypatch):
    copy = tmp_path / "LQ"
    shutil.copytree(LQ, copy, ignore=shutil.ignore_patterns("__pycache__", "results"))
    monkeypatch.setattr(R, "HERE", str(copy))
    assert R.freeze_refusals() == []
    (copy / "extra.py").write_text("x = 1\n")
    assert any("unfrozen file" in r for r in R.freeze_refusals())
    (copy / "extra.py").unlink()
    with open(copy / "score_live.py", "a") as fh:
        fh.write("\n# edited\n")
    assert any("FREEZE mismatch: score_live.py" in r for r in R.freeze_refusals())


def test_refuses_bad_run_id_existing_run_lock_ledger_and_unacknowledged_abort(env):
    _refused(env, "--run-id must match", run_id="run1")
    os.makedirs(os.path.join(env["calls_root"], "lq1-exists"))
    _refused(env, "never resumed", run_id="lq1-exists")
    open(os.path.join(env["calls_root"], "LIVE.lock"), "w").write("1")
    _refused(env, "holds")
    os.unlink(os.path.join(env["calls_root"], "LIVE.lock"))
    for i in range(24):
        R.ledger_append(env["calls_root"], {"event": "call_attempt", "run_id": "lq1-old", "index": i + 1})
    _refused(env, "authorisation is used up")
    os.unlink(R.ledger_path(env["calls_root"]))
    R.ledger_append(env["calls_root"], {"event": "run_aborted", "run_id": "lq1-old", "kind": "CREDIT_BALANCE_CHANGED"})
    _refused(env, "acknowledge each")
    rc, out = run_main(env, "first", hooks={"agent_status": lambda: (False, ["scripted: stop before any call"])},
                       conf=confirmation(str(env["tmp"] / "ack.txt"), extra=["acknowledge_abort: lq1-old"]))
    assert rc == 3 and "acknowledge" not in out and "not READY" in out


def test_command_line_refuses_without_token_and_plan_makes_no_call(tmp_path):
    e = dict(os.environ)
    e.pop(R.LIVE_ENV, None)
    e["PYTHONPATH"] = _import_path()
    p = subprocess.run([sys.executable, os.path.join(LQ, "run_live.py"), "--plan"], capture_output=True, text=True, env=e, cwd=str(tmp_path))
    assert p.returncode == 0 and '"max_live_calls": 24' in p.stdout
    p = subprocess.run([sys.executable, os.path.join(LQ, "run_live.py"), "--first-call", "--run-id", "lq1-cli", "--confirmation",
                        str(tmp_path / "none.txt"), "--tasks", str(tmp_path)], capture_output=True, text=True, env=e, cwd=str(tmp_path))
    assert p.returncode == 3 and "REFUSING" in p.stdout and R.LIVE_ENV in p.stdout and not os.listdir(tmp_path)


def test_continue_refusals(env):
    _refused(env, "no run record", mode="continue", run_id="lq1-none")
    d = os.path.join(env["calls_root"], "lq1-c")
    os.makedirs(d)
    rec = {"state": "COMPLETE", "calls": [{}], "baseline": {"balance": "12.5", "weekly_used_percent": 20.0}}
    json.dump(rec, open(os.path.join(d, "run_record.json"), "w"))
    _refused(env, "never resumed", mode="continue", run_id="lq1-c")
    for st in ("ABORTED", "RUNNING", "STOPPED_DEFECT", "FIRST_CALL_RUNNING"):
        json.dump(dict(rec, state=st), open(os.path.join(d, "run_record.json"), "w"))
        _refused(env, "not PAUSED_AFTER_FIRST_CALL", mode="continue", run_id="lq1-c")
    json.dump(dict(rec, state="PAUSED_AFTER_FIRST_CALL", calls=[{}, {}]), open(os.path.join(d, "run_record.json"), "w"))
    _refused(env, "not exactly one", mode="continue", run_id="lq1-c")
    bad = {"rate_limits_present": True, "balance": "11.00", "weekly_used_percent": 21.0, "windows": {}, "model_returned": R.MODEL}
    json.dump(dict(rec, state="PAUSED_AFTER_FIRST_CALL", calls=[{"post_reading": bad}]), open(os.path.join(d, "run_record.json"), "w"))
    _refused(env, "CREDIT_BALANCE_CHANGED", mode="continue", run_id="lq1-c")
    good = dict(bad, balance="12.50")
    json.dump(dict(rec, state="PAUSED_AFTER_FIRST_CALL", calls=[{"post_reading": good}]), open(os.path.join(d, "run_record.json"), "w"))
    _refused(env, "differ from the run's recorded baseline", mode="continue", run_id="lq1-c", conf=confirmation(str(env["tmp"] / "c9.txt"), balance="13"))


# ---------------------------------------------------------------- Amendment 4: precondition B, go-ahead, real names
def test_hard_spending_block_statement_needs_its_own_token(env, monkeypatch):
    blk = confirmation(str(env["tmp"] / "cb.txt"), statement=R.STATEMENT_BLOCK)
    _refused(env, "does not match the confirmation's statement", conf=blk)                   # block statement, reload token
    monkeypatch.setenv(R.LIVE_ENV, R.LIVE_TOKEN_BLOCK)
    _refused(env, "does not match the confirmation's statement")                             # reload statement, block token
    fake_codex.set_script(env["fake_dir"], script())
    rc, out = run_main(env, "first", conf=blk)
    rec = record(env)
    assert rc == 0 and rec["state"] == "PAUSED_AFTER_FIRST_CALL" and rec["precondition"] == "hard spending block", out[-2000:]
    assert "%s=%s" % (R.LIVE_ENV, R.LIVE_TOKEN_BLOCK) in out
    assert R.parse_confirmation(confirmation(str(env["tmp"] / "cr.txt")), TODAY)[0]["precondition"].startswith("auto-reload off")


def test_continue_needs_the_owners_go_ahead_after_the_first_call(env):
    rc, out = _first(env)
    assert rc == 0 and record(env)["state"] == "PAUSED_AFTER_FIRST_CALL"
    g = lambda name, **kw: go_ahead(str(env["tmp"] / name), env["calls_root"], "lq1-t1", **kw)
    _refused(env, "--go-ahead FILE not given", mode="continue", go=False)
    _refused(env, "does not exist", mode="continue", go=str(env["tmp"] / "nope.txt"))
    _refused(env, "first line must be", mode="continue", go=g("g1.txt", header="go ahead"))
    _refused(env, "does not match the digest", mode="continue", go=g("g2.txt", first_call_digest="0" * 16))
    _refused(env, "not the baseline", mode="continue", go=g("g3.txt", observed_credit_balance="12.40"))
    _refused(env, "not a number", mode="continue", go=g("g4.txt", observed_credit_balance="unknown"))
    _refused(env, "above the guard", mode="continue", go=g("g5.txt", observed_weekly_usage_percent="31"))
    _refused(env, "not the exact required statement", mode="continue", go=g("g6.txt", statement="ok, go on"))
    _refused(env, "not this run", mode="continue", go=g("g7.txt", run_id="lq1-other"))
    _refused(env, "not today's date", mode="continue", go=g("g8.txt", date="2026-10-17"))
    _refused(env, "unknown line", mode="continue", go=g("g9.txt", colour="blue"))
    old = g("g10.txt")
    os.utime(old, (1.0e9, 1.0e9))
    _refused(env, "written before the first call completed", mode="continue", go=old)
    rec = record(env)
    assert rec["state"] == "PAUSED_AFTER_FIRST_CALL" and len(rec["calls"]) == 1 and R.ledger_attempts(env["calls_root"]) == 1


def test_real_names_are_forbidden_in_every_payload(env):
    task = os.path.join(env["tasks"], "d4_24BR_compare")
    names = R.real_names(task)
    assert {"run_A", "run_B", "protein.fasta", "rna.fasta", "reference.cif", "7K9D", "7K9D_model_0"} <= names
    ctx = R.privacy_ctx(task, "fixed system text", [], names)
    for leak in ("run_A", "reference.cif", "7K9D_model_0.pdb", "the 7K9D target"):
        assert privacy.gate("Task inputs: " + leak, **ctx), leak
    assert privacy.gate("Task inputs: run_001/candidate_001 protein_sequence_001 reference_001", **ctx) == []
    system, user = R.expected_nl_payload("Which runs agree?", task)
    assert "reference_001" in user and not [n for n in names if n in user]


# ---------------------------------------------------------------- end to end with the fake codex
def _first(e, run_id="lq1-t1", rules=None, **usage):
    fake_codex.set_script(e["fake_dir"], script(rules, **usage))
    return run_main(e, "first", run_id)


def test_end_to_end_full_pass_first_call_then_continue(env):
    rc, out = _first(env)
    rec = record(env)
    assert rc == 0 and rec["state"] == "PAUSED_AFTER_FIRST_CALL", out[-3000:]
    assert len(rec["calls"]) == 1 and n_call_dirs(env) == 1 and R.ledger_attempts(env["calls_root"]) == 1
    assert set(rec["scenarios"]) == {"Z1", "Z2", "P01"}
    assert all(rec["scenarios"][z]["hard_pass"] for z in ("Z1", "Z2")), rec["scenarios"]
    c1 = rec["calls"][0]
    assert c1["scenario"] == "P01" and c1["kind"] == "plan" and c1["exact_bytes_ok"] and c1["privacy_findings"] == [] and c1["call_dir_clean"]
    assert c1["post_reading"]["balance"] == "12.50" and c1["pre_reading"]["source"].startswith("owner confirmation")
    sent = open(os.path.join(env["calls_root"], "lq1-t1", c1["sent_copy"]), "rb").read()
    got = open(os.path.join(c1["call_dir"], "fake_stdin.txt"), "rb").read()
    assert sent == got                                   # the bytes the (fake) Codex received are the recorded bytes
    assert "credit balance: 12.50 (baseline 12.5)" in out and "--continue-after-first" in out
    assert "FIRST CALL RESULT (P01)" in out and R.GO_AHEAD_HEADER in out and "--go-ahead" in out
    assert rec["first_call_digest"] == R.first_call_digest(rec) and ("first_call_digest: %s" % rec["first_call_digest"]) in out
    assert "No further call is made" in out and "model identity: %s" % R.MODEL in out
    rc2, out2 = run_main(env, "continue")
    rec = record(env)
    assert rc2 == 0 and rec["state"] == "COMPLETE", out2[-3000:]
    assert len(rec["calls"]) == 12 and n_call_dirs(env) == 12 and R.ledger_attempts(env["calls_root"]) == 12
    assert set(rec["scenarios"]) == set(S()["order"])
    for sid, sc in rec["scenarios"].items():
        assert sc["status"] == "COMPLETED" and sc["hard_pass"], (sid, sc)
    names = R.real_names(os.path.join(env["tasks"], "d4_24BR_compare")) | set(TASK_NAMES) | {"region.json", "summary.json"}
    for c in rec["calls"]:
        assert c["privacy_findings"] == [] and c["exact_bytes_ok"] and c["call_dir_clean"] and not c.get("abort")
        sent = open(os.path.join(env["calls_root"], "lq1-t1", c["sent_copy"]), encoding="utf-8").read()
        assert not [n for n in names if n in sent], (c["scenario"], [n for n in names if n in sent])     # Amendment 4
    assert rec["go_ahead"]["sha256"] and rec["scenarios"]["P01"]["hard"]["H5_followup_no_consent_no_call"]
    assert rec["verdict"]["verdict"] == "QUALIFIED_ON_DEVELOPMENT_CASES", rec["verdict"]
    assert all(rec["scenarios"][f]["C1_C2"] for f in ("F-L01", "F-L09", "F-L11")), rec["scenarios"]
    assert rec["verdict"]["hard_failures"] == []
    res = json.load(open(os.path.join(env["calls_root"], "lq1-t1", "results.json")))
    assert res["state"] == "COMPLETE" and res["calls"] == 12
    _refused(env, "not PAUSED_AFTER_FIRST_CALL", mode="continue")          # a finished run is never resumed
    print(json.dumps(rec["verdict"]), json.dumps({k: v.get("tool_selection") for k, v in rec["scenarios"].items()}))


@pytest.mark.parametrize("over,kind", [
    ({"balance": "11.00"}, "CREDIT_BALANCE_CHANGED"),
    ({"balance": "n/a"}, "BALANCE_UNREADABLE"),
    ({"credits": None}, "BALANCE_UNREADABLE"),
    ({"omit_rate_limits": True}, "USAGE_UNREADABLE"),
    ({"model_returned": "gpt-5-mini"}, "CALL_FAILED"),           # codex_llm itself raises on a model mismatch; also WRONG_MODEL
    ({"weekly": 31.0}, "USAGE_RISE"),
    ({"weekly": 85.0}, "CALL_FAILED"),                           # codex_llm's own 85 % guard raises; also USAGE_CEILING
    ({"primary": 90.0}, "CALL_FAILED"),                          # codex_llm's own 85 % guard raises; also USAGE_CEILING
    ({"reached": "primary"}, "CALL_FAILED"),
    ({"exit": 1}, "CALL_FAILED"),
])
def test_first_call_aborts(env, over, kind):
    rc, out = _first(env, rules=with_rule(q("P01"), **over))
    rec = record(env)
    assert rc == 5 and rec["state"] == "ABORTED" and rec["stop"]["kind"] == kind, (out[-2000:], rec.get("stop"))
    assert len(rec["calls"]) == 1 and R.ledger_attempts(env["calls_root"]) == 1          # never retried
    assert rec["scenarios"]["P01"]["status"] == "INCOMPLETE"
    _refused(env, "not PAUSED_AFTER_FIRST_CALL", mode="continue")
    if over == {"model_returned": "gpt-5-mini"}:
        assert "WRONG_MODEL" in rec["stop"]["detail"]
    if kind == "CREDIT_BALANCE_CHANGED":                                                  # a new run needs the owner's acknowledgement
        _refused(env, "acknowledge each", run_id="lq1-t2")


def test_usage_jump_mid_run_aborts_and_the_run_is_never_resumed(env):
    rc, out = _first(env, rules=with_rule(q("P02"), weekly=31.0))
    assert rc == 0 and record(env)["state"] == "PAUSED_AFTER_FIRST_CALL"
    rc, out = run_main(env, "continue")
    rec = record(env)
    assert rc == 5 and rec["state"] == "ABORTED" and rec["stop"]["kind"] == "USAGE_RISE" and len(rec["calls"]) == 2
    assert "P03" not in rec["scenarios"] and rec["verdict"]["verdict"] == "INCOMPLETE"
    _refused(env, "not PAUSED_AFTER_FIRST_CALL", mode="continue")
    _refused(env, "never resumed", run_id="lq1-t1")
    fake_codex.set_script(env["fake_dir"], script())
    rc, out = run_main(env, "first", run_id="lq1-t3")                                     # a new run id may start; the ledger counts on
    assert rc == 0 and R.ledger_attempts(env["calls_root"]) == 3


def test_first_call_pause_refuses_a_second_call_and_ledger_cap_stops(env):
    rej = plan("AGREEMENT", ["contacts_agreement"], [step("analyse_predictions", project_id="p9")])        # P3: needs a replan
    rules = with_rule(q("P01"), reply=rej)
    rc, out = _first(env, rules=rules)
    rec = record(env)
    assert rc == 0 and rec["state"] == "PAUSED_AFTER_FIRST_CALL" and len(rec["calls"]) == 1
    assert rec["scenarios"]["P01"]["reason"] == "INCOMPLETE_FIRST_CALL_PAUSE"
    assert [x["refusal"]["kind"] for x in rec["refused_calls"]] == ["FIRST_CALL_PAUSE"]
    for i in range(22):                                                                   # 1 + 22 = 23 attempts: one call left
        R.ledger_append(env["calls_root"], {"event": "call_attempt", "run_id": "lq1-other", "index": i + 1})
    fake_codex.set_script(env["fake_dir"], script())
    rc, out = run_main(env, "continue")
    rec = record(env)
    assert rc == 5 and rec["stop"]["kind"] == "BUDGET" and len(rec["calls"]) == 2 and R.ledger_attempts(env["calls_root"]) == 24


def test_clock_change_during_the_run_stops_before_the_next_call(env):
    """The clock is re-checked before every call: a date change after preflight (or entering the block) refuses the call."""
    tz = R._zone()
    block = datetime.datetime(2026, 10, 22, 0, 30, tzinfo=tz).astimezone(datetime.timezone.utc)
    for later, rid in ((NOW + datetime.timedelta(days=1), "lq1-t4"), (block, "lq1-t5")):
        fake_codex.set_script(env["fake_dir"], script())
        ticks = iter([NOW] + [later] * 50)
        rc, out = run_main(env, "first", run_id=rid, hooks={"now": lambda: next(ticks)})
        rec = record(env, rid)
        assert rc == 5 and rec["stop"]["kind"] == "CLOCK" and rec["calls"] == [], out[-1500:]
    assert R.ledger_attempts(env["calls_root"]) == 0


def test_privacy_gate_refuses_before_sending(env, monkeypatch):
    real = R.privacy_ctx
    monkeypatch.setattr(R, "privacy_ctx", lambda *a, **kw: dict(real(*a, **kw), forbidden_strings=["Task inputs"]))
    rc, out = _first(env)
    rec = record(env)
    assert rc == 5 and rec["state"] == "ABORTED" and rec["stop"]["kind"] == "PRIVACY_GATE" and rec["calls"] == []
    assert n_call_dirs(env) == 0 and R.ledger_attempts(env["calls_root"]) == 0
    assert rec["scenarios"]["P01"]["hard_pass"] is False and rec["verdict"]["verdict"] == "NOT_QUALIFIED"


def test_guard_refuses_calls_outside_a_scenario_and_blocks_the_api_client(env, tmp_path):
    from rnplens_assistant import codex_llm, llm
    run = R.Run(str(tmp_path), "lq1-g", {"baseline": {"balance": "12.5", "weekly_used_percent": 20.0}, "calls": [], "refused_calls": [],
                                         "confirmation": {"date": TODAY}})
    os.makedirs(run.dir)
    g = R.Guard(run, "continue", out=lambda *a: None, hooks=env["hooks"])
    R.install(g)
    try:
        cl = codex_llm.CodexClient.__new__(codex_llm.CodexClient)
        cl.config = dict(codex_llm.CONFIG)
        with pytest.raises(codex_llm.UsageGuard):
            cl.run("plan", "x", {})                                                       # no scenario
        g.abort = None
        g.set_scenario("Z1", 0)
        with pytest.raises(codex_llm.UsageGuard):
            cl.run("plan", "x", {})                                                       # a zero-call scenario
        assert g.abort["kind"] == "SCENARIO_CALL_LIMIT"
        with pytest.raises(RuntimeError):
            llm.Client()
    finally:
        R.uninstall()
    R.install(None)
    try:
        with pytest.raises(codex_llm.UsageGuard):
            codex_llm.CodexClient.__new__(codex_llm.CodexClient).run("plan", "x", {})       # no guard installed: refused
    finally:
        R.uninstall()
    assert R.ledger_attempts(str(tmp_path)) == 0


# ---------------------------------------------------------------- karyon: the real jail, real doctor, real development tasks
KARYON = os.path.isdir(KARYON_TASKS) and shutil.which("bwrap") and os.path.isfile("/usr/bin/python3") and _from_checkout()


@pytest.mark.karyon
@pytest.mark.skipif(not KARYON, reason="karyon development tasks, bubblewrap or /usr/bin/python3 not available, or installed mode (repository tool)")
def test_karyon_end_to_end_real_jail_fake_codex(tmp_path, monkeypatch):
    """Everything real except the codex binary: real codex_jail.sh (bubblewrap), real `rnplens doctor --agent`, real
    clock and NTP check, real git-clean check, real development tasks. Only the calls root is redirected to tmp."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if R.clock_refusals(now, R.ntp_status())[0]:
        pytest.skip("clock refusal now (date block or no NTP): %s" % R.clock_refusals(now, R.ntp_status())[0])
    today = now.astimezone(R._zone()).date().isoformat()
    from rnplens_assistant import codex_llm
    assert os.path.realpath(codex_llm.JAIL) == os.path.realpath(os.path.join(ROOT, R.JAIL_REL))
    fake_dir = tmp_path / "fakecodex"
    fake = slow_wrapper(str(fake_dir / "codex_slow"),
                        fake_codex.write_fake_codex(str(fake_dir), script(l09=(1, 4)), python="/usr/bin/python3"))   # 24BR RNA: 4 nt
    home = tmp_path / "fake_codex_home"
    home.mkdir()
    (home / "auth.json").write_text("{}")
    trap = tmp_path / "trapbin"
    trap.mkdir()
    marker = tmp_path / "REAL_CODEX_REACHED"
    (trap / "codex").write_text("#!/bin/sh\ntouch %s\nexit 99\n" % marker)
    os.chmod(trap / "codex", 0o755)
    monkeypatch.setenv("PATH", str(trap) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("RNPLENS_CODEX_BIN", fake)
    monkeypatch.setenv("CODEX_HOME", str(home))
    for k in R.API_ENV + ("RNPLENS_CODEX_CALLS", "RNPLENS_LLM", "RNPLENS_CODEX_JAIL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(R.LIVE_ENV, TOKEN)
    real = R.runtime_hashes()
    conf = confirmation(str(tmp_path / "owner_confirmation.txt"), date=today, bind=authorisation(KARYON_TASKS, "first", "lq1-karyon", real))
    conf2 = confirmation(str(tmp_path / "owner_authorisation_continue.txt"), date=today,
                         bind=authorisation(KARYON_TASKS, "continue", "lq1-karyon", real))
    root = str(tmp_path / "codex_calls_live")
    hooks = {"calls_root": root}
    out = []
    a = ["--run-id", "lq1-karyon", "--confirmation", conf, "--tasks", KARYON_TASKS]
    rc = R.main(["--first-call"] + a, hooks=hooks, out=lambda *x: out.append(" ".join(map(str, x))))
    rec = json.load(open(os.path.join(root, "lq1-karyon", "run_record.json")))
    assert rc == 0 and rec["state"] == "PAUSED_AFTER_FIRST_CALL" and len(rec["calls"]) == 1, "\n".join(out[-40:])
    a2 = ["--run-id", "lq1-karyon", "--confirmation", conf2, "--tasks", KARYON_TASKS]
    assert R.main(["--continue-after-first"] + a2, hooks=hooks, out=lambda *x: out.append(" ".join(map(str, x)))) == 3   # no go-ahead
    ga = go_ahead(str(tmp_path / "go_ahead.txt"), root, "lq1-karyon", date=today)
    assert R.main(["--continue-after-first"] + a + ["--go-ahead", ga], hooks=hooks, out=lambda *x: None) == 3   # first-call authorisation reused
    rc = R.main(["--continue-after-first"] + a2 + ["--go-ahead", ga], hooks=hooks, out=lambda *x: out.append(" ".join(map(str, x))))
    rec = json.load(open(os.path.join(root, "lq1-karyon", "run_record.json")))
    assert rc == 0 and rec["state"] == "COMPLETE" and len(rec["calls"]) == 12, "\n".join(out[-40:])
    assert R.ledger_attempts(root) == 12
    for c in rec["calls"]:
        assert c["privacy_findings"] == [] and c["exact_bytes_ok"] and c["post_reading"]["model_returned"] == R.MODEL
        assert c["post_reading"]["cli_version"] == "0.159.3"
    for sid, sc in rec["scenarios"].items():
        assert sc["status"] == "COMPLETED" and sc["hard_pass"], (sid, sc)
    assert rec["verdict"]["verdict"] == "QUALIFIED_ON_DEVELOPMENT_CASES", rec["verdict"]
    assert not marker.exists()
    shutil.copy(os.path.join(root, "lq1-karyon", "results.json"), str(tmp_path / "results_copy.json"))
    print("KARYON_E2E", json.dumps(rec["verdict"]), json.dumps({k: (v.get("tool_selection"), v.get("criteria")) for k, v in rec["scenarios"].items()}))


@pytest.mark.karyon
@pytest.mark.skipif(not KARYON, reason="karyon development tasks, bubblewrap or /usr/bin/python3 not available, or installed mode (repository tool)")
def test_karyon_balance_drop_after_first_call_through_the_real_jail(tmp_path, monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    if R.clock_refusals(now, R.ntp_status())[0]:
        pytest.skip("clock refusal now")
    today = now.astimezone(R._zone()).date().isoformat()
    fake = slow_wrapper(str(tmp_path / "fc" / "codex_slow"),
                        fake_codex.write_fake_codex(str(tmp_path / "fc"), script(with_rule(q("P01"), balance="12.40")), python="/usr/bin/python3"))
    home = tmp_path / "h"
    home.mkdir()
    (home / "auth.json").write_text("{}")
    monkeypatch.setenv("RNPLENS_CODEX_BIN", fake)
    monkeypatch.setenv("CODEX_HOME", str(home))
    for k in R.API_ENV + ("RNPLENS_CODEX_CALLS", "RNPLENS_LLM", "RNPLENS_CODEX_JAIL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(R.LIVE_ENV, TOKEN)
    root = str(tmp_path / "ccl")
    real = R.runtime_hashes()
    a = ["--run-id", "lq1-drop", "--confirmation", confirmation(str(tmp_path / "c.txt"), date=today,
                                                               bind=authorisation(KARYON_TASKS, "first", "lq1-drop", real)), "--tasks", KARYON_TASKS]
    a2 = ["--run-id", "lq1-drop", "--confirmation", confirmation(str(tmp_path / "c2.txt"), date=today,
                                                                bind=authorisation(KARYON_TASKS, "continue", "lq1-drop", real)), "--tasks", KARYON_TASKS]
    rc = R.main(["--first-call"] + a, hooks={"calls_root": root}, out=lambda *x: None)
    rec = json.load(open(os.path.join(root, "lq1-drop", "run_record.json")))
    assert rc == 5 and rec["state"] == "ABORTED" and rec["stop"]["kind"] == "CREDIT_BALANCE_CHANGED" and R.ledger_attempts(root) == 1
    ga = go_ahead(str(tmp_path / "go_ahead.txt"), root, "lq1-drop", date=today)
    assert R.main(["--continue-after-first"] + a2 + ["--go-ahead", ga], hooks={"calls_root": root}, out=lambda *x: None) == 3


# Formerly a strict xfail documenting the 1-s folder-name collision; fixed in codex_llm at integration (AMENDMENT_3).
def test_codexclient_folder_name_has_one_second_resolution(tmp_path, monkeypatch):
    from rnplens_assistant import codex_llm
    monkeypatch.setattr(codex_llm, "CALLS_ROOT", str(tmp_path))
    monkeypatch.setattr(codex_llm.time, "strftime", lambda fmt, *a: "20261018T120000" if "%Y" in fmt else "120000")
    c1 = codex_llm.CodexClient("assist_120000")
    c2 = codex_llm.CodexClient("assist_120000")     # raised FileExistsError before the fix
    assert c1.root != c2.root and os.path.isdir(c1.root) and os.path.isdir(c2.root)


# ---------------------------------------------------------------- Amendment 8: call-specific authorisation binding
@pytest.mark.parametrize("key", list(R.AUTH_KEYS))
def test_authorisation_field_wrong_or_missing_is_refused(env, key):
    good = authorisation(env["tasks"])
    wrong = dict(good, **{key: good[key][:-1] + ("0" if good[key][-1:] != "0" else "1")})
    _refused(env, "authorisation %s" % key, conf=confirmation(str(env["tmp"] / ("w_%s.txt" % key)), bind=wrong))
    missing = {k: v for k, v in good.items() if k != key}
    _refused(env, "authorisation %s missing" % key, conf=confirmation(str(env["tmp"] / ("m_%s.txt" % key)), bind=missing))
    assert R.ledger_attempts(env["calls_root"]) == 0


def test_authorisation_extra_field_is_refused(env):
    conf = confirmation(str(env["tmp"] / "extra.txt"), extra=["approved_by_email: owner"])
    _refused(env, "unknown line", conf=conf)


def test_authorisation_for_another_experiment_is_refused(env):
    """An authorisation names one experiment: another run id, mode, scenario, task or target (e.g. the 2JEA wording of
    an earlier approval) never covers this call."""
    good = authorisation(env["tasks"])
    for key, value in (("run_id", "lq1-other"), ("mode", "continue-after-first"), ("scenario", "P02"),
                       ("task", "d9_2JEA_viewer"), ("target", "2JEA"), ("experiment", "FOLLOWUP_SUITE_v1"), ("max_model_calls", "2")):
        _refused(env, "authorisation %s" % key, conf=confirmation(str(env["tmp"] / ("x_%s.txt" % key)), bind=dict(good, **{key: value})))
    assert good["scenario"] == "P01" and good["task"] == "d1_7K9D_agreement" and good["target"] == "7K9D" and good["max_model_calls"] == "1"
    assert R.ledger_attempts(env["calls_root"]) == 0


def test_first_call_authorisation_cannot_be_reused_to_continue(env):
    rc, out = run_main(env, "first")
    assert rc == 0 and record(env)["state"] == "PAUSED_AFTER_FIRST_CALL", out[-1500:]
    rec = record(env)
    assert rec["authorisation_bound"]["values"]["payload_sha256"] == rec["calls"][0]["prompt_sha256"]
    first_auth = str(env["tmp"] / "auth_first_lq1-t1.txt")
    _refused(env, "authorisation mode", mode="continue", conf=first_auth)
    _refused(env, "authorisation max_model_calls", mode="continue", conf=first_auth)
    assert len(record(env)["calls"]) == 1


def test_authorisation_changes_with_the_task_content(env):
    a1 = authorisation(env["tasks"])
    with open(os.path.join(env["tasks"], "d1_7K9D_agreement", "run_A", "extra_note.txt"), "w") as fh:
        fh.write("changed input\n")
    a2 = authorisation(env["tasks"])
    assert a1["task_sha256"] != a2["task_sha256"]
    _refused(env, "authorisation task_sha256", conf=confirmation(str(env["tmp"] / "old.txt"), bind=a1))


def test_guard_refuses_an_unauthorised_payload_or_call_count(env, tmp_path):
    rec = {"baseline": {"balance": "12.5", "weekly_used_percent": 20.0}, "calls": [], "refused_calls": [], "confirmation": {"date": TODAY},
           "authorisation_bound": {"values": {"max_model_calls": "1"}, "scenario_payloads": {"P01": "a" * 64}}}
    run = R.Run(str(tmp_path / "root"), "lq1-g", rec)
    os.makedirs(run.dir)
    g = R.Guard(run, "continue", out=lambda *a: None, hooks=env["hooks"])
    g.set_scenario("P01", 2)
    with pytest.raises(Exception, match="AUTHORISATION"):
        g.before(type("C", (), {"config": {"model": R.MODEL, "reasoning_effort": R.EFFORT}})(), "plan", "not the authorised bytes", {}, (), None)
    g2 = R.Guard(run, "continue", out=lambda *a: None, hooks=env["hooks"])
    g2.set_scenario("P02", 2)
    g2.calls_invocation = 1
    with pytest.raises(Exception, match="AUTHORISATION"):
        g2.before(type("C", (), {"config": {"model": R.MODEL, "reasoning_effort": R.EFFORT}})(), "plan", "x", {}, (), None)


def test_plan_prints_the_exact_authorisation_values(env):
    out = []
    assert R.main(["--plan", "--run-id", "lq1-t1", "--tasks", env["tasks"]], hooks=env["hooks"], out=lambda *x: out.append(" ".join(map(str, x)))) == 0
    vals = json.loads(out[-1])["authorisation_values"]
    assert vals["first-call"] == authorisation(env["tasks"]) and vals["continue-after-first"]["max_model_calls"] == str(R.LEDGER_CAP - 1)
    assert not os.path.exists(env["calls_root"])

