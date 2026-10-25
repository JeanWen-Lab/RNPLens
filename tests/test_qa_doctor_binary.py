"""QA agent-security regression (fix #7): `rnplens doctor --agent` must check the Codex binary that the jail runs.
Before the fix codex_path() preferred `codex` on PATH; on karyon that is a snap build 0.114.0 (untested, 'Not logged
in') while codex_jail.sh runs the standalone 0.159.3, so the doctor and the jail checked/ran different binaries."""
import os

from rnplens import doctor as D
from test_doctor import FakeEnv


class TwoCodexEnv(FakeEnv):
    def __init__(self, tmp):
        super().__init__(tmp)
        self.standalone = os.path.join(str(tmp / "home"), ".codex", "packages", "standalone", "current", "bin", "codex")
        self.paths = {"codex": "/snap/bin/codex", "bwrap": "/usr/bin/bwrap"}
        self.files = {"/snap/bin/codex", self.standalone}

    def run(self, argv, timeout=20):
        if argv and argv[0] == "/snap/bin/codex":
            self.calls.append(list(argv))
            return {"--version": (0, "codex-cli 0.114.0\n", ""), "login": (1, "Not logged in\n", "")}.get(argv[1], (1, "", "unsupported"))
        return super().run(argv, timeout)


def test_doctor_checks_the_jails_binary(tmp_path):
    env = TwoCodexEnv(tmp_path)
    assert D.codex_path(env) == env.standalone
    c = {x["id"]: x for x in D.run_checks(agent=True, env=env)["checks"]}
    assert c["codex_cli"]["status"] == D.READY and env.standalone in c["codex_cli"]["detail"]
    assert "/snap/bin/codex" in c["codex_cli"]["detail"] and "not the binary the jail runs" in c["codex_cli"]["detail"]
    assert c["codex_login"]["status"] == D.READY
    assert not any(a[0] == "/snap/bin/codex" for a in env.calls), "the PATH binary must not be run"


def test_codex_home_and_forced_binary(tmp_path):
    env = TwoCodexEnv(tmp_path)
    ch = str(tmp_path / "ch"); alt = os.path.join(ch, "packages", "standalone", "current", "bin", "codex")
    env.environ["CODEX_HOME"] = ch; env.files.add(alt)
    assert D.codex_path(env) == alt
    env.environ["RNPLENS_CODEX_BIN"] = "/snap/bin/codex"
    assert D.codex_path(env) == "/snap/bin/codex"


def test_path_only_is_not_found(tmp_path):
    env = TwoCodexEnv(tmp_path); env.files = {"/snap/bin/codex"}
    c = {x["id"]: x for x in D.run_checks(agent=True, env=env)["checks"]}
    assert c["codex_cli"]["status"] == D.ACTION and c["codex_cli"]["detail"].startswith("not found where the jail looks")
    assert "/snap/bin/codex" in c["codex_cli"]["detail"]
