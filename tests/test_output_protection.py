"""RNPBENCH_REPORT_OUTPUT_PROTECTION_V1 (0.2.0.dev1): `run` refuses an existing --outdir and changes nothing.

Every entry point is exercised in a subprocess: the public `rnplens report run` and the internal module.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

from rnpbench_report import selftest as rs


def _which(name):
    p = os.path.join(os.path.dirname(sys.executable), name)
    return p if os.path.exists(p) else shutil.which(name)


ENTRY = {
    "python -m rnpbench_report": lambda: [sys.executable, "-m", "rnpbench_report", "run"],
    "rnplens report run": lambda: [_which("rnplens"), "report", "run"],
}


@pytest.fixture(scope="module")
def contract(tmp_path_factory):
    d = tmp_path_factory.mktemp("example")
    ex = d / "report_7K9D"; shutil.copytree(rs.EXAMPLE, ex)
    return rs.write_example_contract(str(ex), str(d / "contract.json"))


def _snap(d):
    return {os.path.relpath(os.path.join(p, f), d): (hashlib.sha256(open(os.path.join(p, f), "rb").read()).hexdigest(),
                                                       os.stat(os.path.join(p, f)).st_mtime_ns)
            for p, _, fs in os.walk(d) for f in fs}


def _populate(d):
    d.mkdir()
    (d / "result.json").write_text(json.dumps({"sentinel": "pre-existing result; must survive"}))
    (d / "contacts_by_output.json").write_text("{}")
    (d / "report_7K9D_example.html").write_text("<html>pre-existing</html>")
    (d / "notes.txt").write_text("unrelated user file")
    (d / "sub").mkdir(); (d / "sub" / "keep.dat").write_bytes(os.urandom(64))


def _cmd(entry, contract, out):
    base = ENTRY[entry]()
    if base[0] is None:
        pytest.skip("%s is not installed" % entry)
    return base + [contract, "--out" if entry == "rnplens report run" else "--outdir", str(out)]


@pytest.mark.parametrize("entry", sorted(ENTRY))
@pytest.mark.parametrize("state", ["populated", "empty"])
def test_existing_output_directory_is_refused_and_unchanged(entry, state, contract, tmp_path):
    out = tmp_path / "existing out"
    if state == "populated":
        _populate(out)
    else:
        out.mkdir()
    before = _snap(str(out)); listing = sorted(os.listdir(out))
    r = subprocess.run(_cmd(entry, contract, out), capture_output=True, text=True)
    assert r.returncode == 2, (r.returncode, r.stdout[-400:], r.stderr[-400:])
    assert "REFUSED: output directory exists" in r.stderr
    assert _snap(str(out)) == before          # same files, same bytes, same modification times; nothing added
    assert sorted(os.listdir(out)) == listing


@pytest.mark.parametrize("entry", sorted(ENTRY))
def test_existing_file_as_outdir_is_refused(entry, contract, tmp_path):
    f = tmp_path / "a_file"; f.write_text("keep")
    r = subprocess.run(_cmd(entry, contract, f), capture_output=True, text=True)
    assert r.returncode == 2 and f.read_text() == "keep"


def test_new_directory_is_written(contract, tmp_path):
    out = tmp_path / "fresh"
    r = subprocess.run([sys.executable, "-m", "rnpbench_report", "run", contract, "--outdir", str(out), "--no-report"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
    assert {"result.json", "contacts_by_output.json"} <= set(os.listdir(out))
