"""Output order of the 0.4 commands does not depend on path lengths (integrator decision after the 5b15730 v2
retest failure: logs/10_explain_evidence.log of 2QQP had its stderr 'written:' lines before the stdout body in one
tree and after it in the other, because a redirected stdout is block-buffered (8192 bytes) and the body length
depends on the absolute root). The step runners write `cmd >> log 2>&1`; these tests do the same."""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

from rnplens import state as S

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("determinism_v1_tests_o", os.path.join(HERE, "test_determinism.py"))
D1 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(D1)
BUF = 8192                                     # CPython's default block buffer of a redirected text stream
_HEX = re.compile(rb"[0-9a-f]{64}")
ENV = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))


def _case(root):
    D1._case(root)
    st = S.Project(os.path.join(root, "project")).head()["analyses"]["main"]
    imp, an = os.path.join("project", st["import_dir"]), os.path.join("project", st["dir"])
    r = subprocess.run([sys.executable, "-m", "rnplens", "region", imp, an, "--rna", "14-23"], cwd=root, env=ENV,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return imp, an


def _combined(root, argv, log):
    """Run like the step runner: stdout and stderr appended to one file."""
    with open(log, "wb") as fh:
        rc = subprocess.call([sys.executable] + argv, stdout=fh, stderr=subprocess.STDOUT, cwd=root, env=ENV)
    return rc, open(log, "rb").read()


def _explain(root, imp, an, log):
    return _combined(root, ["-m", "rnplens", "explain", "evidence", "--id", "region_14-23/region.json#/contacts/0",
                            "--analysis", an, "--project", imp], log)


def _body(b):
    return len(b"\n".join(x for x in b.split(b"\n") if not x.startswith(b"  written:")))


def _masked(b, root):
    return _HEX.sub(b"<sha256>", b.replace(os.path.realpath(root).encode(), b"<root>").replace(root.encode(), b"<root>"))


@pytest.fixture(scope="module")
def roots():
    base = tempfile.mkdtemp(prefix="rnpo_", dir="/tmp")          # short absolute root
    try:
        short = os.path.join(base, "s")
        imp, an = _case(short)
        rc, b = _explain(short, imp, an, os.path.join(base, "probe.log"))
        assert rc == 0, b[-2000:]
        n, size = b.count(os.path.realpath(short).encode()) or b.count(short.encode()), _body(b)
        if size > BUF - 200 or n == 0:
            pytest.skip("explain body (%d bytes, %d root occurrences) cannot straddle %d here" % (size, n, BUF))
        pad = (BUF + 300 - size) // n + 1                           # long root: body just above the buffer size
        parts, left = [], pad
        while left > 0:                                             # path components of at most 200 characters
            k = min(200, left); parts.append("p" * k); left -= k + 1
        long_ = os.path.join(base, *parts)
        _case(long_)
        yield {"base": base, "short": short, "long": long_, "rel": (imp, an)}
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_explain_evidence_log_is_identical_across_the_8192_byte_boundary(roots):
    imp, an = roots["rel"]
    out = {}
    for k in ("short", "long"):
        rc, b = _explain(roots[k], imp, an, os.path.join(roots["base"], k + ".log"))
        assert rc == 0, b[-2000:]
        out[k] = b
    sizes = {k: _body(b) for k, b in out.items()}
    assert sizes["short"] <= BUF < sizes["long"], sizes                 # the case reproduces the boundary
    assert b"  written:" in out["short"] and b"  written:" in out["long"]
    assert _masked(out["short"], roots["short"]) == _masked(out["long"], roots["long"])


def test_stdout_is_flushed_before_every_stderr_write_in_program_order(tmp_path):
    """The helper used by both entry points: a long stdout body, then a stderr line, then stdout again."""
    prog = ("import sys\nfrom rnplens import ordered_output\nordered_output.install()\n"
            "for i in range(400): print('o' * 40)\nprint('E1', file=sys.stderr)\nprint('tail')\n"
            "sys.stderr.write('E2 partial'); sys.stderr.write(' line\\n')\nprint('end')\n")
    rc, b = _combined(str(tmp_path), ["-c", prog], str(tmp_path / "x.log"))
    assert rc == 0
    L = b.decode().splitlines()
    assert L[400:] == ["E1", "tail", "E2 partial line", "end"], L[398:]


@pytest.mark.parametrize("argv", [["-m", "rnplens", "--version"], ["-m", "rnplens_assistant", "--help"]])
def test_entry_points_install_the_ordered_output(tmp_path, argv):
    """python -m rnplens (the step runners' entry, and the console script's main) and python -m rnplens_assistant."""
    probe = ("import runpy, sys, atexit\nfrom rnplens import ordered_output\n"
             "atexit.register(lambda: sys.__stdout__.write('INSTALLED=' + str(ordered_output.installed()) + chr(10)))\n"
             "sys.argv = " + repr([argv[1]] + argv[2:]) + "\nrunpy.run_module(" + repr(argv[1]) + ", run_name='__main__')\n")
    r = subprocess.run([sys.executable, "-c", probe], cwd=str(tmp_path), env=ENV, capture_output=True, text=True)
    assert "INSTALLED=True" in r.stdout, (r.stdout[-500:], r.stderr[-500:])
