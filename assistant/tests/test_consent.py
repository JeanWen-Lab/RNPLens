"""Privacy contract for the Codex follow-up (consent.py): explicit opt-in, opt-out revokes, no consent -> no call."""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_followup_common import make_project  # noqa: E402

from rnplens import trace  # noqa: E402
from rnplens_assistant import consent as C, followup as F  # noqa: E402

Q = "Which contacts in RNA 13-23 are found in only one run?"


@pytest.fixture(scope="module")
def pa(tmp_path_factory):
    return make_project(str(tmp_path_factory.mktemp("consent") / "x"))


@pytest.fixture(autouse=True)
def clean(pa):
    p = C.path(pa[0])
    if os.path.exists(p):
        os.unlink(p)
    yield


def test_screen_lists_exact_categories_and_never_sent():
    t = C.screen_text()
    for _, txt in C.CATEGORIES:
        assert txt in t
    for txt in C.NEVER_SENT:
        assert txt in t
    assert "coordinates" in t and "sequences" in t and "reference" in t and C.CATEGORIES_VERSION in t
    assert C.REFERENCE_CATEGORY[1] not in t and C.REFERENCE_CATEGORY[1] in C.screen_text(True)
    assert trace.wording_audit(t) == []
    assert [k for k, _ in C.CATEGORIES] == ["question_text", "derived_agreement_values", "contact_labels_positions", "counts", "identifiers"]


def test_opt_in_out_and_status(pa):
    P = pa[0]
    assert C.status(P)[0] is False
    r = C.opt_in(P, "--yes")
    ok, cur, why = C.status(P)
    assert ok and cur["id"] == r["id"] and cur["scope"] == "project" and cur["categories_version"] == C.CATEGORIES_VERSION
    assert cur["allow_reference_derived"] is False and cur["timestamp_utc"] and cur["method"] == "--yes"
    C.opt_out(P, "--yes")
    assert C.status(P)[0] is False and "opted out" in C.status(P)[2]
    doc = json.load(open(C.path(P)))
    assert [x["action"] for x in doc["records"]] == ["opt_in", "opt_out"] and "provenance" in doc


def test_version_or_project_change_requires_new_opt_in(pa, tmp_path):
    P = pa[0]
    C.opt_in(P, "--yes")
    doc = json.load(open(C.path(P)))
    doc["records"][-1]["categories_version"] = "followup-categories-0"
    json.dump(doc, open(C.path(P), "w"))
    assert C.status(P)[0] is False
    C.opt_in(P, "--yes")
    doc = json.load(open(C.path(P))); doc["records"][-1]["project"] = str(tmp_path)
    json.dump(doc, open(C.path(P), "w"))
    assert C.status(P)[0] is False and "another project" in C.status(P)[2]


def test_interactive_opt_in_needs_yes(pa):
    P = pa[0]
    out = []
    assert C.interactive_opt_in(P, lambda p: "y", out=out.append) is None and not os.path.exists(C.path(P))
    assert C.interactive_opt_in(P, lambda p: "yes", out=out.append)["method"] == "interactive"
    assert C.screen_text() in out[0]
    with pytest.raises(ValueError):
        C.opt_in(P, "auto")


def _guarded(monkeypatch):
    spawned = []
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(args, *a, **k):
        flat = " ".join(map(str, args if isinstance(args, (list, tuple)) else [args]))
        if "codex" in flat or "jail" in flat:
            spawned.append(flat)
            raise AssertionError("codex subprocess started")
        return real_run(args, *a, **k)

    class Popen(real_popen):
        def __init__(self, args, *a, **k):
            if "codex" in " ".join(map(str, args if isinstance(args, (list, tuple)) else [args])):
                spawned.append(args); raise AssertionError("codex subprocess started")
            super().__init__(args, *a, **k)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", Popen)
    return spawned


@pytest.mark.parametrize("state", ["none", "opted_out", "old_version"])
def test_without_consent_no_client_and_no_codex_subprocess(pa, monkeypatch, state):
    P, A = pa
    if state == "opted_out":
        C.opt_in(P, "--yes"); C.opt_out(P, "--yes")
    if state == "old_version":
        C.opt_in(P, "--yes"); monkeypatch.setattr(C, "CATEGORIES_VERSION", "followup-categories-3")
    spawned = _guarded(monkeypatch)
    from rnplens_assistant import codex_llm
    made = []
    rec = F.run(P, A, Q, mode="codex", yes=True, out=lambda *x: None,
                client_factory=lambda: made.append(1) or codex_llm.CodexClient("t"), agent_status=lambda: (True, []))
    assert rec["stop"]["kind"] == "NO_CONSENT" and made == [] and spawned == [] and rec["payloads"] == [] and rec["model_calls_made"] == 0
    md = open(os.path.join(A, rec["dir"], "followup_answer.md")).read()
    assert "nothing was sent" in md and "Local suggestion (not run)" in md


def test_consent_cli(pa, capsys):
    from rnplens_assistant.__main__ import main
    P = pa[0]
    assert main(["consent", "show", "--project", P]) == 0 and "never contains" in capsys.readouterr().out
    assert main(["consent", "opt-in", "--project", P, "--yes"]) == 0 and C.status(P)[0]
    assert main(["consent", "opt-out", "--project", P, "--yes"]) == 0 and not C.status(P)[0]
