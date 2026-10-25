"""rnplens doctor: every check with a mocked system; no credential content is ever output; nothing is changed."""
import builtins
import json
import os
import subprocess

import pytest

from rnplens import doctor as D, provenance as pv, viewer

SECRETS = ["sk-proj-abcdefghijklmnop1234567890", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJl",
           "someone@example.org", "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"]


class FakeEnv(D.Env):
    """A Linux x86_64 machine on which everything is ready, unless a test changes an attribute."""

    def __init__(self, tmp, **kw):
        self.sysname, self.mach, self.py = "Linux", "x86_64", (3, 11, 9)
        self.dists = dict(D.REQUIRED, matplotlib="3.9.2")
        jail = tmp / "codex_jail.sh"; jail.write_text("#!/bin/bash\n")
        self.environ = {"HOME": str(tmp / "home")}
        self.fake_jail = str(jail)          # the approved jail of this fake installation (None: the real packaged jail)
        self.paths = {"codex": "/opt/codex/bin/codex", "bwrap": "/usr/bin/bwrap"}
        # the jail runs Codex's standalone install (QA fix #7: the doctor checks that binary, not `codex` on PATH)
        self.files = {"/opt/codex/bin/codex", os.path.join(str(tmp / "home"), ".codex", "packages", "standalone", "current", "bin", "codex")}
        self.responses = {
            ("codex", "--version"): (0, "codex-cli 0.159.3\n", ""),
            ("codex", "login", "status"): (0, "", "Logged in using ChatGPT\n"),
            ("codex", "debug", "models"): (0, "gpt-6.1-sol\ngpt-6.1-mini\n", ""),
            ("bwrap", "--ro-bind", "/", "/", "true"): (0, "", ""),
        }
        self.calls = []
        self.__dict__.update(kw)

    def system(self):
        return self.sysname

    def machine(self):
        return self.mach

    def python_version(self):
        return self.py

    def which(self, name):
        return self.paths.get(name)

    def isfile(self, p):
        return p in self.files or os.path.isfile(p)

    def approved_jail(self):
        return self.fake_jail or D.Env.approved_jail(self)

    def dist_version(self, name):
        return self.dists.get(name)

    def run(self, argv, timeout=20):
        self.calls.append(list(argv))
        if os.path.basename(argv[0]) == "env" and "RNPLENS_JAIL_PROBE=1" in argv:          # the jail's no-model self-probe
            return getattr(self, "jail_probe", (0, "JAIL_OK\n", ""))
        key = (os.path.basename(argv[0]),) + tuple(argv[1:])
        r = self.responses[key]
        if isinstance(r, BaseException):
            raise r
        return r


def by_id(rec):
    return {c["id"]: c for c in rec["checks"]}


@pytest.fixture
def env(tmp_path):
    return FakeEnv(tmp_path)


def test_everything_ready_on_linux_with_the_tested_codex(env):
    rec = D.run_checks(agent=True, env=env)
    c = by_id(rec)
    for k in ("python", "rnplens", "components", "platform_toolkit", "viewer", "platform_assistant", "codex_cli",
              "codex_login", "codex_model", "bwrap", "codex_jail", "assistant_pkg", "llm_mode"):
        assert c[k]["status"] == D.READY, (k, c[k])
    assert "enabled" in c["llm_mode"]["detail"]
    assert D.agent_status(env) == (True, [])
    # only these four commands were run, all read-only
    probes = [c for c in env.calls if os.path.basename(c[0]) == "env"]
    # the probe runs with the environment of a real call: env -i, HOME (+ CODEX_HOME, RNPLENS_CODEX_BIN), PATH=/usr/bin:/bin
    assert probes and all(c[:2] == ["/usr/bin/env", "-i"] and "PATH=/usr/bin:/bin" in c and "RNPLENS_JAIL_PROBE=1" in c
                          and any(a.startswith("RNPLENS_JAIL_PROBE_HIDDEN=") for a in c) and "/bin/bash" in c for c in probes)
    jx = D.codex_path(env)                       # QA fix #7: the binary the jail runs (standalone), never `codex` on PATH
    assert jx.endswith("/.codex/packages/standalone/current/bin/codex")
    assert set(map(tuple, [c for c in env.calls if os.path.basename(c[0]) != "env"])) == set([            # no other command is ever run
        (jx, "--version"), (jx, "login", "status"),
        (jx, "debug", "models"), ("/usr/bin/bwrap", "--ro-bind", "/", "/", "true")])


def test_every_check_has_a_status_and_a_remedy_when_not_ready(env):
    env.sysname, env.paths, env.dists = "Linux", {}, {}
    env.files = set()
    rec = D.run_checks(agent=True, project="/nonexistent/p", out="/nonexistent/o", env=env)
    for c in rec["checks"]:
        assert c["status"] in (D.READY, D.ACTION, D.UNSUPPORTED)
        if c["status"] != D.READY:
            assert c["remedy"] and "\n" not in c["remedy"], c


def _mac(env):
    env.sysname, env.mach = "Darwin", "arm64"
    env.files.add(D.SANDBOX_EXEC)
    env.responses[("sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true")] = (0, "", "")
    return env


def test_macos_assistant_ready_with_seatbelt(env):
    """0.4 native platforms: the assistant runs natively on macOS, confined by Seatbelt; no bubblewrap probe."""
    _mac(env)
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["platform_toolkit"]["status"] == D.READY and c["platform_assistant"]["status"] == D.READY
    assert c["seatbelt"]["status"] == D.READY and "bwrap" not in c
    assert c["codex_jail"]["status"] == D.READY and c["llm_mode"]["status"] == D.READY
    assert not any("bwrap" in a[0] for a in env.calls)
    assert [a for a in env.calls if a[0] == D.SANDBOX_EXEC] == [[D.SANDBOX_EXEC, "-p", "(version 1)(allow default)", "/usr/bin/true"]]
    assert D.agent_status(env) == (True, [])


def test_macos_packaged_jail_is_the_seatbelt_jail(env):
    _mac(env); env.fake_jail = None
    c = by_id(D.run_checks(agent=True, env=env))["codex_jail"]
    assert c["status"] == D.READY and c["detail"].split(";")[0].endswith("codex_seatbelt.sh")
    probe = [a for a in env.calls if os.path.basename(a[0]) == "env"][0]
    i = probe.index("/bin/bash")
    assert probe[1] == "-i" and probe[i + 1].endswith("codex_seatbelt.sh")


def test_macos_refuses_when_seatbelt_cannot_be_applied(env):
    _mac(env)
    env.responses[("sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true")] = (71, "", "sandbox-exec: sandbox_apply: Operation not permitted")
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["seatbelt"]["status"] == D.ACTION and "ordinary Terminal" in c["seatbelt"]["remedy"]
    assert c["llm_mode"]["status"] != D.READY and D.agent_status(env)[0] is False
    env.files.discard(D.SANDBOX_EXEC)
    env.isfile = lambda p: p in env.files                         # this machine's real sandbox-exec must not count
    env.responses.pop(("sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"))
    assert by_id(D.run_checks(agent=True, env=env))["seatbelt"]["status"] == D.ACTION
    env.jail_probe = (1, "", "denied")
    assert by_id(D.run_checks(agent=True, env=env))["codex_jail"]["status"] == D.ACTION


def test_unqualified_architecture_and_other_systems(env):
    env.sysname, env.mach = "Linux", "arm64"
    assert by_id(D.run_checks(env=env))["platform_toolkit"]["status"] == D.ACTION
    env.sysname, env.mach = "Darwin", "x86_64"
    assert by_id(D.run_checks(env=env))["platform_toolkit"]["status"] == D.ACTION
    env.sysname, env.mach = "Windows", "x86_64"
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["platform_toolkit"]["status"] == D.UNSUPPORTED and c["platform_assistant"]["status"] == D.UNSUPPORTED


@pytest.mark.parametrize("v,status", [((3, 9, 18), D.UNSUPPORTED), ((3, 10, 0), D.READY), ((3, 12, 4), D.READY), ((3, 13, 0), D.UNSUPPORTED)])
def test_python_version(env, v, status):
    env.py = v
    assert by_id(D.run_checks(env=env))["python"]["status"] == status


def test_required_and_optional_dependencies(env):
    env.dists = dict(D.REQUIRED, scipy="1.17.1")
    env.dists.pop("gemmi")
    c = by_id(D.run_checks(env=env))
    assert c["dep_scipy"]["status"] == D.ACTION and "qualified with 1.13.1" in c["dep_scipy"]["detail"]
    assert c["dep_gemmi"]["status"] == D.ACTION and "gemmi==0.6.5" in c["dep_gemmi"]["remedy"]
    assert c["dep_matplotlib"]["status"] == D.ACTION and "optional" in c["dep_matplotlib"]["detail"]
    assert c["dep_DockQ"]["status"] == D.READY


def test_untested_codex_version_and_missing_cli(env, tmp_path):
    env.responses[("codex", "--version")] = (0, "codex-cli 0.160.0", "")
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["codex_cli"]["status"] == D.ACTION and "untested version" in c["codex_cli"]["detail"]
    assert c["llm_mode"]["status"] != D.READY
    env2 = FakeEnv(tmp_path)
    env2.paths, env2.files = {"bwrap": "/usr/bin/bwrap"}, set()
    c = by_id(D.run_checks(agent=True, env=env2))
    assert c["codex_cli"]["status"] == D.ACTION and c["codex_cli"]["detail"].startswith("not found")
    assert "not verified" in c["codex_login"]["detail"] and "not verified" in c["codex_model"]["detail"]
    assert not any("codex" in a[0] for a in env2.calls)


def test_forced_codex_binary_has_no_fallback(env):
    env.environ["RNPLENS_CODEX_BIN"] = "/does/not/exist/codex"
    assert D.codex_path(env) is None
    env.environ["RNPLENS_CODEX_BIN"] = "/opt/codex/bin/codex"
    assert D.codex_path(env) == "/opt/codex/bin/codex"


@pytest.mark.parametrize("line,status", [("Logged in using ChatGPT", D.READY), ("Logged in using an API key - sk-xxxxxxxxxxxxxxxx", D.ACTION),
                                         ("Not logged in", D.ACTION), ("", D.ACTION)])
def test_login_status_line_only(env, line, status):
    env.responses[("codex", "login", "status")] = (0 if "Logged" in line else 1, line + "\n", "")
    c = by_id(D.run_checks(agent=True, env=env))["codex_login"]
    assert c["status"] == status
    assert "sk-xxxx" not in json.dumps(c)


def test_no_credential_content_is_ever_output(env, monkeypatch, capsys):
    env.responses[("codex", "login", "status")] = (0, "Logged in using ChatGPT %s %s\naccess_token: %s\nrefresh %s\n" % tuple(SECRETS), "")
    env.responses[("codex", "debug", "models")] = (0, "gpt-6.1-sol token=%s\n" % SECRETS[0], "")
    env.responses[("codex", "--version")] = (1, "", "error: bad key %s" % SECRETS[1])
    real_open = builtins.open

    def guarded_open(f, *a, **k):
        assert "auth.json" not in str(f), "the doctor must never open Codex's login file"
        return real_open(f, *a, **k)
    monkeypatch.setattr(builtins, "open", guarded_open)
    rec = D.run_checks(agent=True, env=env)
    text = D.render(rec) + json.dumps(rec)
    for s in SECRETS:
        assert s not in text
    env.responses[("codex", "--version")] = (0, "codex-cli 0.159.3", "")
    rec = D.run_checks(agent=True, env=env)
    text = D.render(rec) + json.dumps(rec)
    for s in SECRETS:
        assert s not in text
    assert by_id(rec)["codex_login"]["detail"].startswith("Logged in using ChatGPT")


def test_child_processes_get_no_api_keys(monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(argv, 0, "codex-cli 0.159.3", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-pass")
    monkeypatch.setenv("CODEX_API_KEY", "x")
    D.Env().run(["codex", "--version"])
    assert "OPENAI_API_KEY" not in seen["env"] and "CODEX_API_KEY" not in seen["env"]
    assert seen["stdin"] is subprocess.DEVNULL


def test_model_offered_absent_or_unknown(env):
    env.responses[("codex", "debug", "models")] = (0, json.dumps({"models": [{"slug": "gpt-6.1-mini"}]}), "")
    assert by_id(D.run_checks(agent=True, env=env))["codex_model"]["status"] == D.ACTION
    env.responses[("codex", "debug", "models")] = (0, json.dumps({"models": [{"slug": "gpt-6.1-sol"}]}), "")
    assert by_id(D.run_checks(agent=True, env=env))["codex_model"]["status"] == D.READY
    env.responses[("codex", "debug", "models")] = (2, "", "unknown command")
    c = by_id(D.run_checks(agent=True, env=env))["codex_model"]
    assert c["status"] == D.ACTION and "not verified" in c["detail"]


@pytest.mark.parametrize("resp,word", [
    ((1, "", "bwrap: setting up uid map: Permission denied"), "not usable"),
    ((1, "", "bwrap: No permissions to creating new namespace"), "not usable"),
    (OSError(1, "Operation not permitted by the sandbox"), "not verified"),
    (subprocess.TimeoutExpired("bwrap", 10), "not verified"),
    ((125, "", "something else"), "not verified")])
def test_bwrap_probe_failures_are_never_ready(env, resp, word):
    env.responses[("bwrap", "--ro-bind", "/", "/", "true")] = resp
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["bwrap"]["status"] == D.ACTION and word in c["bwrap"]["detail"]
    assert c["llm_mode"]["status"] != D.READY and D.agent_status(env)[0] is False


def test_bwrap_missing(env):
    env.paths.pop("bwrap")
    c = by_id(D.run_checks(agent=True, env=env))["bwrap"]
    assert c["status"] == D.ACTION and "bubblewrap" in c["remedy"]


def test_jail_and_switch_off(env, tmp_path):
    env.fake_jail = None                      # falls back to the packaged jail of this installation
    c = by_id(D.run_checks(agent=True, env=env))["codex_jail"]
    assert c["status"] == D.READY and "rnplens_assistant" in c["detail"] and "self-probe passed" in c["detail"]
    env.jail_probe = (1, "", "bwrap: setting up uid map: Permission denied")
    c = by_id(D.run_checks(agent=True, env=env))["codex_jail"]
    assert c["status"] == D.ACTION and D.NOT_VERIFIED in c["detail"]          # a failed probe is never READY
    env.jail_probe = (0, "", "")                                              # exit 0 without JAIL_OK is not enough
    assert by_id(D.run_checks(agent=True, env=env))["codex_jail"]["status"] == D.ACTION
    env2 = FakeEnv(tmp_path)
    env2.environ["RNPLENS_LLM"] = "off"
    c = by_id(D.run_checks(agent=True, env=env2))["llm_mode"]
    assert c["status"] == D.ACTION and "RNPLENS_LLM" in c["detail"]


def test_assistant_package_missing(env, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "rnplens_assistant", None)
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["assistant_pkg"]["status"] == D.ACTION and c["llm_mode"]["status"] != D.READY


def test_project_and_output_permissions(tmp_path, env):
    p = tmp_path / "proj"; p.mkdir()
    c = by_id(D.run_checks(project=str(p), out=str(tmp_path / "new" / "out"), env=env))
    assert c["project"]["status"] == D.ACTION and "manifest.json" in c["project"]["detail"]
    assert c["out"]["status"] == D.READY and not (tmp_path / "new").exists()
    (p / "manifest.json").write_text("{}")
    assert by_id(D.run_checks(project=str(p), env=env))["project"]["status"] == D.READY
    f = tmp_path / "file"; f.write_text("x")
    assert by_id(D.run_checks(out=str(f), env=env))["out"]["status"] == D.ACTION

    class NoWrite(FakeEnv):
        def access(self, path, mode):
            return not (mode & os.W_OK)
    nw = NoWrite(tmp_path)
    assert by_id(D.run_checks(out=str(tmp_path), env=nw))["out"]["status"] == D.ACTION
    assert by_id(D.run_checks(out=str(tmp_path / "x" / "y"), env=nw))["out"]["status"] == D.ACTION


def test_viewer_assets_are_hash_checked(tmp_path, monkeypatch, env):
    import shutil
    v = tmp_path / "molstar"; shutil.copytree(viewer.VENDOR, v)
    monkeypatch.setattr(viewer, "VENDOR", str(v))
    assert by_id(D.run_checks(env=env))["viewer"]["status"] == D.READY
    with open(v / "molstar.css", "a") as fh:
        fh.write("/* changed */")
    c = by_id(D.run_checks(env=env))["viewer"]
    assert c["status"] == D.ACTION and "molstar.css" in c["detail"]
    os.remove(v / "molstar.js")
    assert "molstar.js missing" in by_id(D.run_checks(env=env))["viewer"]["detail"]


def test_components_integrity_failure_is_reported(env, monkeypatch):
    from rnpbench_core import frozen_loader

    def bad():
        raise frozen_loader.FrozenIntegrityError("frozen source(s) differ")
    monkeypatch.setattr(frozen_loader, "verify_sources", bad)
    c = by_id(D.run_checks(env=env))["components"]
    assert c["status"] == D.ACTION and "differ" in c["detail"]


def test_notice_is_stated_exactly(env):
    rec = D.run_checks(agent=True, env=env)
    assert rec["notice"] == D.NOTICE and D.NOTICE in D.render(rec)
    assert D.NOTICE == ("Codex mode uses your own ChatGPT account and its usage allowance; RNPLens cannot guarantee that "
                        "supplemental credits will not be used once the included allowance is exhausted; no API key is "
                        "required or used.")
    assert D.NOTICE in D.render(D.run_checks(agent=False, env=env))


def test_cli_writes_nothing_without_save_and_only_doctor_json_with_save(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RNPLENS_CODEX_BIN", str(tmp_path / "no-codex"))
    before = sorted(os.listdir(tmp_path))
    writes = []
    real = pv._atomic
    monkeypatch.setattr(pv, "_atomic", lambda path, data, mode: (writes.append(path), real(path, data, mode)))
    rc = D.main(["--out", str(tmp_path / "o"), "--json"])
    rec = json.loads(capsys.readouterr().out)
    assert rc in (0, 1) and rec["record"] == "rnplens-doctor-1" and writes == [] and sorted(os.listdir(tmp_path)) == before
    rc = D.main(["--out", str(tmp_path / "o"), "--save"])
    assert writes == [str(tmp_path / "o" / "doctor.json")] and os.listdir(tmp_path / "o") == ["doctor.json"]
    saved = json.load(open(tmp_path / "o" / "doctor.json"))
    assert saved["provenance"]["kind"] == "doctor" and saved["notice"] == D.NOTICE
    assert D.main(["--save"]) == 2


def test_cli_exit_code_and_agent_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RNPLENS_CODEX_BIN", str(tmp_path / "no-codex"))
    rc = D.main(["--agent"])
    out = capsys.readouterr().out
    assert rc == 1 and "Codex CLI" in out and "not found" in out and D.NOTICE in out


def test_registry_entry_and_wording():
    from rnplens import trace
    assert D.CAPABILITIES[0]["id"] == "setup_check" and D.CAPABILITIES[0]["menu"] is None
    assert trace.wording_audit(D.render(D.run_checks(env=D.Env()))) == []


def test_redact_keeps_status_words():
    assert D.redact("Logged in using ChatGPT") == "Logged in using ChatGPT"
    out = D.redact(" ".join(SECRETS))
    assert all(s not in out for s in SECRETS)


def test_optional_matplotlib_missing_is_not_a_failure(env, monkeypatch, capsys):
    """QA O1 (proposed policy): a missing optional dependency is shown (ACTION REQUIRED, with remedy) but does not make
    the exit status non-zero; every required check still does."""
    real = D.run_checks
    env.dists = dict(D.REQUIRED)                                         # matplotlib absent
    rec = real(env=env)
    c = by_id(rec)["dep_matplotlib"]
    assert c["status"] == D.ACTION and c["optional"] is True and rec["summary"]["optional_not_ready"] == 1
    assert [x["id"] for x in rec["checks"] if x["status"] != D.READY] == ["dep_matplotlib"]   # the only gap is optional
    monkeypatch.setattr(D, "run_checks", lambda **kw: rec)
    assert D.main([]) == 0
    assert "(1 of them optional; exit status 0)" in capsys.readouterr().out
    env.dists.pop("gemmi")
    rec2 = real(env=env)
    monkeypatch.setattr(D, "run_checks", lambda **kw: rec2)
    assert D.main([]) == 1


def test_jail_override_is_refused_and_never_probed(env, tmp_path):
    """Launch boundary (0.4): RNPLENS_CODEX_JAIL naming any other script is ACTION REQUIRED and is never run."""
    other = tmp_path / "other_jail.sh"; other.write_text("#!/bin/bash\necho JAIL_OK\n")
    env.environ["RNPLENS_CODEX_JAIL"] = str(other)
    c = by_id(D.run_checks(agent=True, env=env))
    assert c["codex_jail"]["status"] == D.ACTION and "unset RNPLENS_CODEX_JAIL" in c["codex_jail"]["remedy"]
    assert c["llm_mode"]["status"] != D.READY and D.agent_status(env)[0] is False
    assert not any(str(other) in a for call in env.calls for a in call)
    env.environ["RNPLENS_CODEX_JAIL"] = env.fake_jail                    # naming the approved jail itself is accepted
    assert by_id(D.run_checks(agent=True, env=env))["codex_jail"]["status"] == D.READY


def test_jail_probe_environment_drops_caller_variables(env):
    env.environ.update({"BASH_ENV": "/tmp/x.sh", "BASH_FUNC_realpath%%": "() { :; }", "LD_PRELOAD": "/tmp/x.so",
                        "RNPLENS_JAIL_TEST": "1", "OPENAI_API_KEY": "sk-x", "PATH": "/tmp/planted:/usr/bin"})
    D.run_checks(agent=True, env=env)
    probe = [a for a in env.calls if os.path.basename(a[0]) == "env"][0]
    assigned = [a.split("=", 1)[0] for a in probe[2:probe.index("/bin/bash")]]
    assert sorted(assigned) == ["HOME", "PATH", "RNPLENS_JAIL_PROBE", "RNPLENS_JAIL_PROBE_HIDDEN"]
    assert "PATH=/usr/bin:/bin" in probe
