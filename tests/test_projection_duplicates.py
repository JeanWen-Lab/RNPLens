"""DETERMINISM_CONTRACT_v2 coverage (0.4 RC fix): every eligible output of a managed project has its canonical
projection, also when two files hold the same bytes (the Mol* assets of two viewer pages). Found by replay v2 at
78b942f: the second viewer page's LICENSE.molstar.txt and VERSION.molstar.json had no projection."""
import json
import os
import subprocess
import sys

from rnplens import projection as PJ

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")


def rn(*a):
    r = subprocess.run([sys.executable, "-m", "rnplens"] + [str(x) for x in a], capture_output=True, text=True, timeout=900,
                       env=dict(os.environ, MPLBACKEND="Agg"))
    assert r.returncode == 0, (a, r.stderr[-1500:])
    return r


def test_two_viewer_pages_both_fully_projected(tmp_path):
    P = tmp_path / "proj"
    rn("update", P, "--init", RF + "/exec_A", RF + "/exec_B", "--protein-seq", EX + "/reference_based/7K9D_protein.fasta",
       "--rna-seq", EX + "/reference_based/7K9D_rna.fasta", "--engine", "BOLTZ2", "--case-id", "7K9D_proj")
    idx = json.load(open(sorted((P / "analyses").glob("v*/index.json"))[-1]))["groups"]["main"]
    imp, ana = P / idx["import_dir"], P / idx["analysis_dir"]
    rn("view", imp, "--analysis", ana, "--rna", "13-23")
    rn("view", imp, "--analysis", ana, "--rna", "20-30")
    a1, a2 = ana / "viewer_13-23" / "assets", ana / "viewer_20-30" / "assets"
    assert (a1 / "LICENSE.molstar.txt").read_bytes() == (a2 / "LICENSE.molstar.txt").read_bytes()
    missing = []
    for dp, dn, fn in os.walk(P):
        dn[:] = [d for d in dn if not (dp == str(P) and d == ".rnplens")]
        for f in fn:
            p = os.path.join(dp, f)
            if PJ.eligible(str(P), p) and not os.path.exists(PJ.projection_path(p)):
                missing.append(os.path.relpath(p, P))
    assert missing == [], missing
