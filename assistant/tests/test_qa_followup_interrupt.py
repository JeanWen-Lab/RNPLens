"""QA agent-security regression (fix #2): a Codex follow-up interrupted during its model call (SIGINT/SIGTERM) must
still count as the one planning round for that question. Before the fix followup_record.json was written only at the
end of followup.run(), so _round_used() did not see the interrupted round and the same question got new model calls."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_followup_common import clone, make_project  # noqa: E402

from rnplens_assistant import consent, followup as F, llm  # noqa: E402

Q = "Which contacts in RNA 13-23 are found in only one run, and which structures list them? (interrupt)"


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    b = tmp_path_factory.mktemp("fu_int")
    make_project(str(b / "x"))
    return str(b / "x")


class Interrupted:
    """A scripted client whose model call is interrupted (Ctrl-C) after the payload was handed over."""
    config, calls = {"model": "scripted"}, []

    def structured(self, *a, **k):
        self.calls.append(1)
        raise KeyboardInterrupt


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit])
def test_interrupted_round_is_counted(base, tmp_path, exc):
    P, A = clone(base, str(tmp_path / "w"))
    consent.opt_in(P, "--yes")
    cl = Interrupted()
    cl.structured = lambda *a, **k: (_ for _ in ()).throw(exc())
    with pytest.raises(exc):
        F.run(P, A, Q, mode="codex", yes=True, out=lambda *x: None, client_factory=lambda: cl, agent_status=lambda: (True, []))
    recs = [os.path.join(A, "followup", d, "followup_record.json") for d in sorted(os.listdir(os.path.join(A, "followup")))]
    assert os.path.isfile(recs[-1]), "no record of the interrupted round"
    r = json.load(open(recs[-1]))
    assert r["state"] == "MODEL_CALL_IN_PROGRESS" and r["model_calls_made"] == 1 and r["payloads"]
    made = []
    rec = F.run(P, A, Q, mode="codex", yes=True, out=lambda *x: None, agent_status=lambda: (True, []),
                client_factory=lambda: made.append(1) or llm.Stub([{"follow_up": "none", "args": F._blank(), "rationale": "x"}]))
    assert rec["stop"]["kind"] == "ROUND_USED" and "MODEL_CALL_IN_PROGRESS" in rec["stop"]["message"]
    assert made == [], "a model client was created for a question whose round was interrupted"


def test_completed_round_record_is_marked_complete(base, tmp_path):
    P, A = clone(base, str(tmp_path / "w"))
    consent.opt_in(P, "--yes")
    rec = F.run(P, A, Q + " (complete)", mode="codex", yes=True, out=lambda *x: None, agent_status=lambda: (True, []),
                client_factory=lambda: llm.Stub([{"follow_up": "none", "args": F._blank(), "rationale": "x"}]))
    assert rec["stop"] is None and rec["state"] == "COMPLETE"
    assert json.load(open(os.path.join(A, rec["dir"], "followup_record.json")))["state"] == "COMPLETE"
