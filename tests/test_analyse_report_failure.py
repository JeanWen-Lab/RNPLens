"""When Report fails, `rnplens analyse` must exit with the failure code (1) and a managed `update` must record the group
FAILED, not COMPLETE, and must not cache the failed analysis (QA track outside-user-viewer, defect S2, 2026-10-18).

Before the fix analyse returned 0 after Report exited 2 (it printed "Report exit 2"), so `update` marked the project
COMPLETE and cached an analysis without Report results.
"""
import json
import os

from rnplens import analyse, cli, importer
from rnplens import incremental as I
from rnplens import state as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
PF = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RFA = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
PS, RS = importer.read_sequence_arg(PF), importer.read_sequence_arg(RFA)
INPUTS = [os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")]


def _project(tmp_path):
    p = str(tmp_path / "p")
    assert cli.main(["import"] + INPUTS + ["--protein-seq", PF, "--rna-seq", RFA, "--out", p, "--case-id", "x",
                                           "--engine", "BOLTZ2"]) == 0
    return p


def test_analyse_exits_1_when_report_refuses_its_contract(tmp_path, capsys):
    p = _project(tmp_path)
    cp = os.path.join(p, "report_contract.json")
    c = json.load(open(cp))
    c["outputs"].append(dict(c["outputs"][0]))          # a contract Report refuses (duplicate engine/execution)
    json.dump(c, open(cp, "w"), indent=1)
    a = str(tmp_path / "a")
    assert analyse.run(p, a) == 1
    S_ = json.load(open(os.path.join(a, "summary.json")))
    assert S_["steps"]["report"]["exit"] == 2 and S_["report"]["status"] == "NOT_AVAILABLE"
    assert os.path.isfile(os.path.join(a, "summary.html"))       # written for inspection, with the failed step
    assert "FAILED" in capsys.readouterr().err


def test_analyse_normal_project_still_exits_0(tmp_path):
    assert analyse.run(_project(tmp_path), str(tmp_path / "a")) == 0


def test_update_records_failed_and_does_not_cache_when_report_fails(tmp_path, monkeypatch):
    real = analyse._rn
    def failing(args, log):
        if args[:2] == ["report", "run"]:
            open(log, "a").write("$ simulated Report failure\nexit 2\n")
            return 2, "CONTRACT ERROR: simulated Report failure"
        return real(args, log)
    monkeypatch.setattr(analyse, "_rn", failing)
    root = str(tmp_path / "m")
    code, vid = I.init_project(root, INPUTS, PS, RS, "BOLTZ2", "x")
    P = S.Project(root)
    head = P.head()
    assert code != 0 and head["status"] == "FAILED", (code, head["status"])
    a = head["analyses"]["main"]
    assert a["status"] == "FAILED" and a["exit"] == 1 and P.cache_lookup(a["key"]) is None
    # once Report works again, the same inputs are analysed afresh (nothing failed was reused) and complete
    monkeypatch.setattr(analyse, "_rn", real)
    code2, vid2 = I.run_pipeline(P, "update")
    h2 = P.head()
    assert code2 == 0 and h2["status"] == "COMPLETE" and h2["analyses"]["main"]["reused"] is False
