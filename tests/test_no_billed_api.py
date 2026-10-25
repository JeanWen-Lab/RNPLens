"""Owner programme 2026-10-18, section 7: the optional AI mode never invokes a separately billed API.

Every language-model route builds codex_llm.CodexClient (Codex CLI, ChatGPT sign-in, inside the jail); no shipped module
constructs the OpenAI API client rnplens_assistant.llm.Client; no package declares openai; the jail starts from a
cleared environment and removes the API-key variables; the doctor strips them from its probes and refuses an API-key
sign-in."""
import inspect
import os
import re

import pytest

import rnplens
from rnplens import assist, doctor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ra = pytest.importorskip("rnplens_assistant")
ADIR = os.path.dirname(ra.__file__)
SDIR = os.path.dirname(rnplens.__file__)


def _py_files(d):
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in ("__pycache__", "tests")]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def test_no_shipped_module_uses_the_api_client():
    for p in list(_py_files(SDIR)) + list(_py_files(ADIR)):
        src = open(p, encoding="utf-8").read()
        rel = os.path.relpath(p, os.path.dirname(ADIR) if p.startswith(ADIR) else os.path.dirname(SDIR))
        if rel != os.path.join("rnplens_assistant", "llm.py"):
            assert not re.search(r"^\s*(import|from)\s+openai\b", src, flags=re.M), rel
        assert not re.search(r"\bllm\.Client\s*\(|\bfrom\s+(\.|rnplens_assistant\.)llm\s+import\s+Client\b", src), rel


def test_every_language_model_route_builds_the_codex_client():
    assert "codex_llm.CodexClient(" in inspect.getsource(assist._make_client)
    assert "codex_llm.CodexClient(" in inspect.getsource(assist._make_followup_client)
    main = open(os.path.join(ADIR, "__main__.py"), encoding="utf-8").read()
    assert "codex_llm.CodexClient(" in main and "llm.Client" not in main


def test_jail_and_doctor_remove_api_keys():
    jail = open(os.path.join(ADIR, "codex_adapter", "codex_jail.sh"), encoding="utf-8").read()
    assert "--clearenv" in jail and "env -u OPENAI_API_KEY -u CODEX_API_KEY bwrap" in jail
    assert set(doctor.SECRET_ENV) == {"OPENAI_API_KEY", "CODEX_API_KEY"}
    assert "if k not in SECRET_ENV" in inspect.getsource(doctor)
    assert '"api key" in low' in inspect.getsource(doctor.check_login)


def test_no_package_declares_openai():
    for p in (os.path.join(ROOT, "pyproject.toml"), os.path.join(ROOT, "assistant", "pyproject.toml")):
        if not os.path.isfile(p):
            pytest.skip("repository pyproject files not available (installed mode)")
        assert "openai" not in open(p, encoding="utf-8").read().lower(), p
