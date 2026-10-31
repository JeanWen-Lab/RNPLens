"""Amendment 4: the packaged guide is byte-identical to the toolkit's docs/ copy, and the prompt the arms receive is
exactly the one evaluated before the packaging change."""
import hashlib
import os

from rnplens_assistant import ask, guide, tools

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# LIVE_QUALIFICATION_v1 Amendment 6 (P3): the guide states that the four-axis geometry route is blocked. The previous
# values (d1a45b57..., a79637fd...) are those of the guide before that change; the sealed evaluation uses its own
# frozen snapshot and is not affected by this 0.4 copy.
EVALUATED_GUIDE = "9b302bc7db6232ba6a463f3b60f8f3388ecb12017ad7a13cc678953862c9283f"
EVALUATED_DOC_TEXT = "b52f6ada689c003e3146050087d72c4b5c2fb5e8ad09cfcb619e57cb8fa1544a"


def test_packaged_guide_is_the_evaluated_version():
    # The packaged guide is the Assistant's evaluated reference text and stays byte-identical to it (it is also pinned
    # by LIVE_QUALIFICATION_v1). Since 0.4.1 the toolkit's user guide, docs/which_analysis_should_i_use.md, is
    # maintained separately: it no longer offers Diagnose, which is not available in RNPLens 0.4.
    a = open(guide.GUIDE, "rb").read()
    assert hashlib.sha256(a).hexdigest() == EVALUATED_GUIDE


def test_user_guide_offers_only_available_analyses():
    t = open(os.path.join(ROOT, "docs", "which_analysis_should_i_use.md"), encoding="utf-8").read()
    start = t.split("## Start here", 1)[1].split("## Three rules", 1)[0]
    assert "| **Evaluate** |" in start and "| **Report** |" in start and "| **Diagnose** |" not in start
    assert "not available in RNPLens 0.4" in start


def test_prompt_context_unchanged():
    assert hashlib.sha256(ask.doc_text().encode()).hexdigest() == EVALUATED_DOC_TEXT


def test_explain_metric_reads_packaged_guide():
    tools.METRIC_DOC = None
    r, recs = tools.explain_metric(None, "fnat")
    assert r["status"] == "EXPLAINED" and recs


def test_missing_guide_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(guide, "GUIDE", str(tmp_path / "absent.md"))
    import pytest
    with pytest.raises(RuntimeError):
        ask._doc()
