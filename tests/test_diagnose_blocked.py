"""0.4 r2: Diagnose is BLOCKED in the public interface until it is re-qualified (owner decision, 17 Oct 2026).

The public commands refuse with DIAGNOSE_BLOCKED and exit 5; `rnplens analyse` never runs Diagnose and records the
status; the frozen rc3 component is unchanged (its pinned sources still verify) and its internal contract checks still
run in the self-test; `rnplens import` does not use the Diagnose workflow.
"""
import json
import os
import subprocess
import sys

import pytest

from rnplens import analyse, capabilities, importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
pytestmark = pytest.mark.skipif(not os.path.isdir(RF), reason="examples/ not present")


def rn(*args):
    return subprocess.run([sys.executable, "-m", "rnplens", *args], capture_output=True, text=True,
                          env=dict(os.environ, MPLBACKEND="Agg"))


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    t = tmp_path_factory.mktemp("blocked")
    PS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_protein.fasta"))
    RS = importer.read_sequence_arg(os.path.join(EX, "reference_based", "7K9D_rna.fasta"))
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], PS, RS, str(t / "p"), "7K9D_example", "BOLTZ2") == 0
    return t


def test_constants_and_registry_entry():
    assert capabilities.DIAGNOSE_BLOCKED_EXIT == 5 and capabilities.DIAGNOSE_BLOCKED_STATUS == "DIAGNOSE_BLOCKED"
    b = capabilities.BLOCKED[0]                    # position 0 is cited by the follow-up as capabilities.py#/BLOCKED/0
    assert b["id"] == "diagnose_interpretation" and b["status"] == "UNAVAILABLE"
    assert "Diagnose" in b["label"] and "exit 5" in b["reason"]
    offered, missing = capabilities.available()
    assert "diagnose_interpretation" in {m["id"] for m in missing}
    assert not any("diagnos" in c["id"] for c in offered)
    from rnplens import trace
    assert trace.wording_audit(capabilities.DIAGNOSE_BLOCKED_MESSAGE) == []


def test_analyse_default_never_runs_diagnose_and_records_blocked(project):
    out = project / "a_default"
    assert analyse.run(str(project / "p"), str(out)) == 0
    S = json.load(open(out / "summary.json"))
    assert S["diagnose"] == [] and S["steps"]["diagnose_skipped"] is True
    assert S["steps"]["diagnose_blocked"]["status"] == "DIAGNOSE_BLOCKED"
    assert S["steps"]["diagnose_blocked"]["exit_code_if_requested"] == 5
    assert not any(n.startswith("diagnose") for n in os.listdir(out))
    assert any("DIAGNOSE_BLOCKED" in x for x in S["limits"])
    assert "DIAGNOSE_BLOCKED" in open(out / "summary.html").read()
    from rnplens import evidence_query as EQ
    txt = EQ.render_text(EQ.build([str(out)], query="unavailable"))
    assert "DIAGNOSE_BLOCKED" in txt


def test_analyse_with_diagnose_is_refused_and_writes_nothing(project):
    out = project / "a_with"
    r = rn("analyse", str(project / "p"), "--out", str(out), "--with-diagnose")
    assert r.returncode == 5 and "DIAGNOSE_BLOCKED" in r.stderr and not out.exists()
    assert analyse.run(str(project / "p"), str(out), diagnose=True) == 5 and not out.exists()


def test_analyse_without_diagnose_is_still_accepted(project):
    # the pinned assistant (rnplens_assistant.tools) passes --without-diagnose; it stays a valid no-op
    out = project / "a_without"
    r = rn("analyse", str(project / "p"), "--out", str(out), "--without-diagnose")
    assert r.returncode == 0, r.stderr
    assert json.load(open(out / "summary.json"))["steps"]["diagnose_blocked"]["status"] == "DIAGNOSE_BLOCKED"


def test_update_with_diagnose_is_refused(tmp_path):
    r = rn("update", str(tmp_path / "mp"), "--with-diagnose")
    assert r.returncode == 5 and "DIAGNOSE_BLOCKED" in r.stderr and not (tmp_path / "mp").exists()


def test_help_states_the_block():
    top = rn("--help").stdout
    assert "BLOCKED (run, preflight, validity exit 5)" in top and "Diagnose BLOCKED in 0.4" in top
    assert "DIAGNOSE_BLOCKED" in rn("analyse", "--help").stdout or "BLOCKED" in rn("analyse", "--help").stdout
    assert "refused in 0.4" in rn("update", "--help").stdout


def test_frozen_component_sources_still_verify():
    from rnpbench_core import frozen_loader
    man = frozen_loader.verify_sources()               # raises FrozenIntegrityError on any change
    assert man["files"]


def test_import_does_not_load_the_diagnose_component():
    code = ("import sys, rnplens.importer, rnplens.analyse; "
            "print(any(m == 'rnpbench_diagnose' or m.startswith('rnpbench_diagnose.') for m in sys.modules))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "False", r.stderr
