"""QA agent-security regression (fix #8): the privacy page must state the Codex jail's real network policy (shared
host network namespace: internet, loopback services, abstract Unix sockets; Codex network-capable tools disabled).
Before the fix the documentation described only the jail's filesystem view."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_jail_network_policy_documented_and_true_to_the_jail():
    doc = open(os.path.join(ROOT, "docs", "setup_and_privacy.md"), encoding="utf-8").read()
    sec = doc.split("## Network inside the Codex jail (0.4)", 1)[1].split("\n## ", 1)[0]
    for phrase in ("--share-net", "the internet", "loopback", "abstract Unix sockets", "web search", "not implemented in 0.4"):
        assert phrase in sec, phrase
    jail = open(os.path.join(ROOT, "assistant", "rnplens_assistant", "codex_adapter", "codex_jail.sh"), encoding="utf-8").read()
    assert "--share-net" in jail                     # the documented policy is the shipped one
    from rnplens_assistant import codex_llm
    for f in ("shell_tool", "unified_exec", "browser_use", "computer_use", "apps", "plugins"):
        assert f in codex_llm.HARDENING
    assert 'web_search="disabled"' in codex_llm.HARDENING
