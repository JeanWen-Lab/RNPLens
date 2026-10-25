"""0.4 model-payload redaction (rnplens_assistant.redact): no original file name, run-folder name, sample name,
reference name, target ID taken from the inputs, or filesystem path reaches any model payload (planner first call,
planner replan, drafter, follow-up call, follow-up replan). Arguments are mapped back locally; the identifier map stays
in the local records; local rendering shows the real names; LLM-free replay reproduces the evidence hash.
No language model is used: payloads are captured by scripted clients. The karyon test repeats the payload checks on
the real development tasks d1-d5."""
import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_followup_common import EX, PS, RF, RS, make_project  # noqa: E402

RB = os.path.join(EX, "reference_based")
KARYON_TASKS = "/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks"
TARGET_RX = re.compile(r"(?<![A-Za-z0-9])([0-9][A-Za-z0-9]{3})(?=[_.]|$)")


def real_names(task_dir):
    """Every name and path an input could reveal: relative paths, basenames, name-like stems (with a digit or an
    underscore; a plain stem such as 'protein' of protein.fasta is an ordinary word of the documentation), folder
    names, target IDs."""
    names, targets = set(), set()
    for dp, dn, fn in os.walk(task_dir):
        for x in dn + fn:
            rel = os.path.relpath(os.path.join(dp, x), task_dir)
            stem = x.split(".")[0]
            names.update({rel, x} | ({stem} if re.search(r"[0-9_]", stem) else set()))
            targets.update(TARGET_RX.findall(x.split(".")[0]))
    names.add(os.path.abspath(task_dir))
    names.discard("task")
    return {n for n in names if len(n) >= 3}, targets


def leaks(payload, names, targets, allowed=()):
    hits = [n for n in names if n not in allowed and re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", payload)]
    hits += [t for t in targets if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", payload)]
    return hits


def make_task(base, reference=False, restricted=False, names=("runA", "runB")):
    t = os.path.join(base, "task")
    shutil.copytree(os.path.join(RF, "exec_A"), os.path.join(t, names[0]))
    shutil.copytree(os.path.join(RF, "exec_B"), os.path.join(t, names[1]))
    shutil.copy(PS, os.path.join(t, "7K9D_protein.fasta"))
    shutil.copy(RS, os.path.join(t, "7K9D_rna.fasta"))
    refs = []
    if reference:
        shutil.copy(os.path.join(RB, "7K9D_reference.cif"), os.path.join(t, "7K9D_reference.cif"))
        refs = ["7K9D_reference.cif"]
    if restricted:
        shutil.copy(os.path.join(RB, "7K9D_reference.cif"), os.path.join(t, "lab_secret_7K9D_ref.cif"))
    json.dump({"task_id": "t", "reference_files": refs, "development_only": True}, open(os.path.join(t, "task.json"), "w"))
    return t


def step(tool, **kw):
    s = {k: None for k in ("project_id", "folders", "protein_fasta", "rna_fasta", "engine", "accept_offsets", "before_project_id",
                           "after_project_id", "reference", "rna_start", "rna_end", "protein_start", "protein_end", "metric_name",
                           "runs", "query", "evidence_id", "contact")}
    s.update(tool=tool, purpose="t", **kw)
    return s


def plan(goal, steps, ref=False, caps=()):
    return {"goal": goal, "reference_supplied": ref, "requested_capabilities": list(caps), "clarification_needed": None, "steps": steps}


class Capture:
    """Scripted client that records every payload (system + user, exactly as CodexClient.structured joins them)."""
    def __init__(self, replies):
        self.replies, self.payloads, self.calls = list(replies), [], []
        self.config = {"model": "scripted", "reasoning_effort": None}

    def structured(self, kind, system, user, schema_name, schema):
        self.payloads.append((kind, system + "\n\n---\n\n" + user))
        self.calls.append({"kind": kind})
        r = self.replies.pop(0)
        return r(user) if callable(r) else r


IMP = step("import_predictions", project_id="p", folders=["run_001", "run_002"], protein_fasta="protein_sequence_001",
           rna_fasta="rna_sequence_001", accept_offsets=False)


# ---------------------------------------------------------------- planner
def test_planner_first_call_and_replan_carry_identifiers_only(tmp_path):
    from rnplens_assistant import ask, replay
    t = make_task(str(tmp_path), reference=True, restricted=True)
    names, targets = real_names(t)
    bad = plan("COMPARE", [dict(IMP, folders=["run_001", "runA"]), step("evaluate_against_reference", project_id="p", reference="7K9D_reference.cif")], ref=True)
    good = plan("COMPARE", [IMP, step("analyse_predictions", project_id="p"),
                            step("region_comparison", project_id="p", rna_start=13, rna_end=23, runs=["run_001", "run_002"]),
                            step("evaluate_against_reference", project_id="p", reference="reference_001")], ref=True)
    cl = Capture([bad, good])
    rd = str(tmp_path / "run")
    rec = ask.run(t, "Compare runA with runB, then 7K9D_model_0.pdb against 7K9D_reference.cif", rd, cl)
    assert [k for k, _ in cl.payloads] == ["plan", "replan"]
    for kind, p in cl.payloads:
        assert leaks(p, names, targets) == [], (kind, leaks(p, names, targets))
        assert "lab_secret" not in p and "/" + os.path.basename(str(tmp_path)) not in p
    first = cl.payloads[0][1]
    assert "Task inputs (6 files" in first and "yes (reference_001)" in first and "run_001/candidate_001" in first
    assert "Compare run_001 with run_002" in first
    rules = sorted(r["rule"] for r in rec["rejected_steps"] if r["plan"] == 0)
    assert rules == ["P2", "P9"]                       # unknown identifier, and a real reference name the model was never shown
    # the tools ran on the real paths; local records and the answer carry real names
    tl = {e["tool"]: e for e in rec["tool_log"]}
    assert tl["import_predictions"]["args"]["folders"] == ["runA", "runB"] and tl["import_predictions"]["status"] == "IMPORTED"
    assert tl["evaluate_against_reference"]["args"]["reference"] == "7K9D_reference.cif"
    assert tl["region_comparison"]["args"]["runs"] == ["runA", "runB"]
    pj = json.load(open(os.path.join(rd, "plan.json")))
    assert pj["steps"][0]["args"]["folders"] == ["runA", "runB"]
    m = json.load(open(os.path.join(rd, "redaction_map.json")))
    assert m["never_sent"] and m["identifiers"]["reference_001"] == "7K9D_reference.cif" and m["identifiers"]["run_001"] == "runA"
    assert "lab_secret_7K9D_ref.cif" not in json.dumps(m)                  # undeclared top-level file: not even mapped
    ans = open(os.path.join(rd, "answer.md")).read()
    assert "runA" in ans or "runB" in ans or "7K9D_model_0" in ans
    h, _ = replay.run(os.path.join(rd, "plan.json"), t, str(tmp_path / "replay"))
    assert h == rec["evidence_sha256"]


def test_reference_free_task_never_mentions_any_reference(tmp_path):
    from rnplens_assistant import ask
    t = make_task(str(tmp_path), restricted=True)
    cl = Capture([plan("AGREEMENT", [IMP, step("analyse_predictions", project_id="p")])])
    ask.run(t, "Do the two runs agree?", str(tmp_path / "run"), cl)
    p = cl.payloads[0][1]
    names, targets = real_names(t)
    assert leaks(p, names, targets) == [] and "reference_00" not in p and "lab_secret" not in p
    assert "Experimental reference supplied with this task: none" in p and "Task inputs (6 files" in p


def test_drafter_payload_is_redacted_and_statements_map_back(tmp_path):
    from rnplens_assistant import ask
    t = make_task(str(tmp_path))
    names, targets = real_names(t)
    seen = {}

    def draft(user):
        seen["u"] = user
        return {"statements": [{"type": "LIMITATION", "text": "Agreement between run_001 and run_002 is not correctness.", "evidence_ids": []}]}
    cl = Capture([plan("AGREEMENT", [IMP, step("analyse_predictions", project_id="p")]), draft, draft])
    rec = ask.run(t, "Do runA and runB agree?", str(tmp_path / "run"), cl, answer_mode="draft")
    for kind, p in cl.payloads[1:]:
        assert kind in ("draft", "redraft") and leaks(p, names, targets) == []
    assert "between runA and runB" in rec["drafts"][0]["statements"][0]["text"]     # identifiers mapped back locally


# ---------------------------------------------------------------- follow-up
def _fu(tmp_path, replies, question):
    from rnplens_assistant import consent, followup as F
    P, A = make_project(str(tmp_path / "w"))
    consent.opt_in(P, "--yes")
    cl = Capture(replies)
    rec = F.run(P, A, question, mode="codex", initial={"kind": "menu_item", "capability": "region_run_comparison"}, yes=True,
                ask=None, out=lambda *x: None, client_factory=lambda: cl, agent_status=lambda: (True, []))
    return P, A, rec, cl


def _fu_names(P, A):
    man = json.load(open(os.path.join(P, "manifest.json")))
    names = {r["run"] for r in man["runs"]} | {s["sample"] for s in man["structures"]}
    for s in man["structures"]:
        for k in ("used_path", "path", "original_path"):
            if s.get(k):
                names.update({s[k], os.path.basename(s[k]), os.path.basename(s[k]).split(".")[0]})
    names |= {"summary.json", "region.json", "region_13-23", os.path.abspath(P), os.path.abspath(A)}
    targets = set()
    for n in list(names):
        targets.update(TARGET_RX.findall(os.path.basename(n).split(".")[0]))
    return {n for n in names if n and len(n) >= 3}, targets


def test_followup_payloads_carry_identifiers_and_arguments_map_back(tmp_path):
    from rnplens_assistant import followup as F, replay
    blank = {k: None for k in F.ARGS}
    first = {"follow_up": "compare_runs_in_region", "args": dict(blank, rna_start=13, rna_end=23, runs=["exec_A", "exec_B"]), "rationale": "r"}
    second = {"follow_up": "compare_runs_in_region", "args": dict(blank, rna_start=14, rna_end=22, runs=["run_001", "run_002"]), "rationale": "r"}
    P, A, rec, cl = _fu(tmp_path, [first, second], "Which contacts in RNA 14-22 are found in only one of exec_A and exec_B?")
    names, targets = _fu_names(P, A)
    assert [k for k, _ in cl.payloads] == ["followup", "followup_replan"]
    for kind, p in cl.payloads:
        assert leaks(p, names, targets) == [], (kind, leaks(p, names, targets))
        assert F.privacy_check(p, P) == []
    assert "run_001" in cl.payloads[0][1] and "evidence_001" in cl.payloads[0][1] and "candidate_001" in cl.payloads[0][1]
    assert rec["proposals"][0]["verdict"]["rule"] == "F5"            # the real-name proposal repeats the existing comparison
    assert rec["chosen"]["args"]["runs"] == ["exec_A", "exec_B"] and rec["stop"] is None and rec["tool_log"]
    d = os.path.join(A, rec["dir"])
    sent = open(os.path.join(d, "evidence_summary.json")).read()
    assert sent == rec["summary"]["text"] and leaks(sent, names, targets) == []
    assert "exec_A" in open(os.path.join(d, "evidence_summary_local.json")).read()
    m = json.load(open(os.path.join(d, "redaction_map.json")))
    assert m["identifiers"]["run_001"] == "exec_A" and m["never_sent"]
    assert "exec_A" in open(os.path.join(d, "followup_answer.md")).read()      # local rendering shows real names
    h, _log, ok = replay.run_followup(os.path.join(d, "followup_plan.json"), P, A)
    assert ok and h == rec["evidence_sha256"]


def test_followup_evidence_id_identifier_maps_back(tmp_path):
    from rnplens_assistant import followup as F

    def pick(user):
        m = re.search(r'"evidence_id":"(evidence_\d{3})"', user)
        return {"follow_up": "inspect_existing_comparison", "args": dict({k: None for k in F.ARGS}, evidence_id=m.group(1)), "rationale": "r"}
    P, A, rec, cl = _fu(tmp_path, [pick, pick], "Which contacts in RNA 13-23 are found in only one run, and which structures list them?")
    names, targets = _fu_names(P, A)
    assert leaks(cl.payloads[0][1], names, targets) == []
    sent_id = rec["proposals"][0]["proposal"]["args"]["evidence_id"]
    assert sent_id.startswith("evidence_") and "#/" in rec["proposals"][0]["proposal_local"]["args"]["evidence_id"]


def test_redaction_is_deterministic(tmp_path):
    from rnplens_assistant import ask, redact
    t = make_task(str(tmp_path), reference=True)
    u1, m1 = redact.planner_user("q", t, ask.load_task(t))
    u2, m2 = redact.planner_user("q", t, ask.load_task(t))
    assert u1 == u2 and m1.doc() == m2.doc()


# ---------------------------------------------------------------- karyon: the real development tasks
@pytest.mark.karyon
@pytest.mark.skipif(not os.path.isdir(KARYON_TASKS), reason="karyon development tasks not available")
@pytest.mark.parametrize("task", ["d1_7K9D_agreement", "d2_1VTM_agreement", "d3_1VTM_accuracy", "d4_24BR_compare", "d5_24BR_geometry"])
def test_karyon_planner_payload_has_no_real_name(tmp_path, task):
    from rnplens_assistant import ask, followup as F, redact
    t = str(tmp_path / task)
    shutil.copytree(os.path.join(KARYON_TASKS, task), t)
    names, targets = real_names(t)
    names.add(task)
    tk = ask.load_task(t)
    user, m = redact.planner_user("Do the two runs agree on where the protein contacts the RNA?", t, tk)
    sysp = ask._read("planner.md") + "\n\n# RNPLens documentation (which analysis to use)\n\n" + ask.doc_text()
    payload = sysp + "\n\n---\n\n" + user
    assert leaks(payload, names, targets) == []
    assert F.privacy_check(payload, t) == []                          # the follow-up's reference-name flag is now clear
    assert ("reference_001" in user) == bool(tk["reference_files"])


@pytest.mark.karyon
@pytest.mark.skipif(not os.path.isdir(KARYON_TASKS), reason="karyon development tasks not available")
@pytest.mark.parametrize("task", ["d1_7K9D_agreement", "d4_24BR_compare", "d5_24BR_geometry"])
def test_karyon_followup_payload_has_no_real_name(tmp_path, task):
    import contextlib
    import io
    from rnplens import assist, cli
    from rnplens_assistant import consent, followup as F
    t = str(tmp_path / "task")
    shutil.copytree(os.path.join(KARYON_TASKS, task), t, ignore=shutil.ignore_patterns("reference*"))
    P, A = str(tmp_path / "p"), str(tmp_path / "a")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["import", os.path.join(t, "run_A"), os.path.join(t, "run_B"), "--protein-seq", os.path.join(t, "protein.fasta"),
                         "--rna-seq", os.path.join(t, "rna.fasta"), "--out", P, "--case-id", task[:20], "--engine", "BOLTZ2"]) == 0
        assert assist.main(["--project", P, "--analysis", A, "--item", "A", "--json"], out=lambda *x: None) == 0
    consent.opt_in(P, "--yes")
    cl = Capture([{"follow_up": "none", "args": {k: None for k in F.ARGS}, "rationale": "r"}])
    F.run(P, A, "Do the two runs differ in where they contact the RNA?", mode="codex", initial={"kind": "menu_item", "capability": "interface_overview"},
          yes=True, ask=None, out=lambda *x: None, client_factory=lambda: cl, agent_status=lambda: (True, []))
    names, targets = _fu_names(P, A)
    n2, t2 = real_names(t)
    for _, p in cl.payloads:
        assert leaks(p, names | n2 | {task}, targets | t2) == [] and F.privacy_check(p, P) == []
