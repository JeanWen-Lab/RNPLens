"""Follow-up worked examples on the karyon development tasks d2 (1VTM, 5+5 samples) and d4 (24BR, with a reference file
that must never be read or sent). Local mode and scripted Codex proposals only; skipped where the tasks are absent."""
import contextlib
import io
import json
import os
import shutil

import pytest

from rnplens import assist, cli
from rnplens_assistant import consent, followup as F, llm

TASKS = "/home/jwen/projects/RNPBench/scratch_agent/assistant_dev_tasks"
pytestmark = [pytest.mark.karyon, pytest.mark.skipif(not os.path.isdir(TASKS), reason="karyon development tasks not available")]


def _setup(task, tmp):
    t = os.path.join(tmp, "task")
    shutil.copytree(os.path.join(TASKS, task), t, ignore=shutil.ignore_patterns("reference*"))
    P, A = os.path.join(tmp, "p"), os.path.join(tmp, "a")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["import", os.path.join(t, "run_A"), os.path.join(t, "run_B"), "--protein-seq", os.path.join(t, "protein.fasta"),
                         "--rna-seq", os.path.join(t, "rna.fasta"), "--out", P, "--case-id", task[:12], "--engine", "BOLTZ2"]) == 0
        assert assist.main(["--project", P, "--analysis", A, "--item", "A", "--json"], out=lambda *x: None) == 0
    return P, A


@pytest.mark.parametrize("task", ["d2_1VTM_agreement", "d4_24BR_compare"])
def test_dev_task_local_and_scripted_codex_follow_up(task, tmp_path):
    P, A = _setup(task, str(tmp_path))
    S = F.build_summary(P, A, "Where on the RNA do the runs differ?")
    txt = F.summary_text(S)
    assert F.privacy_check(txt, P) == [] and "reference.cif" not in txt and S["reference_derived"]["included"] is False
    assert not any(k in txt.lower() for k in ('"dockq', '"fnat', '"irmsd', '"lrmsd'))
    pos = sorted(S["rna_positions_in_contact"]["value"])
    consent.opt_in(P, "--yes")
    prop = {"follow_up": "compare_runs_in_region", "rationale": "x",
            "args": dict(F._blank(), rna_start=pos[0], rna_end=min(pos[-1], pos[0] + 20), runs=["run_A", "run_B"])}
    c = llm.Stub([prop])
    rec = F.run(P, A, "Which RNA positions do the two runs contact differently?", mode="codex", yes=True, out=lambda *x: None,
                client_factory=lambda: c, agent_status=lambda: (True, []))
    assert rec["stop"] is None and rec["tool_log"][0]["status"] == "OK" and rec["traceability_violations"] == []
    assert not any("reference.cif" in p["text"] for p in rec["payloads"])
    assert F.replay_plan(os.path.join(A, rec["dir"], "followup_plan.json"), P, A)[0] == rec["evidence_sha256"]
    # the same region again is refused as a repeat (F5); the local follow-up then offers the existing comparison (L4)
    assert F.policy_check(prop, F.build_summary(P, A), "Which RNA positions differ?", {})["rule"] == "F5"
    q = "Where on the RNA do the runs differ?"
    sugg = F.suggest_local(F.build_summary(P, A, q), q)
    rec = F.run(P, A, q, mode="local", yes=True, out=lambda *x: None)
    assert rec["traceability_violations"] == [] and rec["wording_audit"] == []
    if rec["tool_log"]:
        assert F.replay_plan(os.path.join(A, rec["dir"], "followup_plan.json"), P, A)[0] == rec["evidence_sha256"]
    json.dump({"task": task, "local_rules": [s["rule"] for s in sugg], "agreement": S["agreement"]},
              open(os.path.join(str(tmp_path), "summary_digest.json"), "w"))
