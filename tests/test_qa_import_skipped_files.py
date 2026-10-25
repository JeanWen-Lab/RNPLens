"""QA install-science fix round O3: a folder import must not ignore any file silently. Every file under an input folder
that is not a candidate structure file (compressed or other-format structure files such as .pdb.gz and .ent, engine
sidecars, anything else) and every hidden folder that is not searched is listed under manifest.json skipped_files with a
reason and counted; on a refusal the structure-like ones are named."""
import gzip
import json
import os
import shutil

from rnplens import importer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PF = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
RF = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
RUN_A = os.path.join(EX, "reference_free", "report_7K9D", "exec_A")


def _folder(tmp_path):
    d = tmp_path / "in" / "exec_A"
    shutil.copytree(RUN_A, d)
    pdb = next(f for f in os.listdir(d) if f.endswith(".pdb"))
    with open(d / pdb, "rb") as fi, gzip.open(d / "copy_model_9.pdb.gz", "wb") as fo:
        fo.write(fi.read())
    shutil.copy(d / pdb, d / "copy_model_8.ent")
    (d / "pae_x.npz").write_bytes(b"\0")
    (d / ".hidden").mkdir()
    shutil.copy(d / pdb, d / ".hidden" / "x_model_0.pdb")
    return d


def test_every_non_imported_file_is_listed_with_a_reason(tmp_path, capsys):
    d = _folder(tmp_path)
    rc = importer.main([str(d), "--protein-seq", PF, "--rna-seq", RF, "--engine", "BOLTZ2", "--out", str(tmp_path / "p")])
    out = capsys.readouterr().out
    assert rc == 0
    m = json.load(open(tmp_path / "p" / "manifest.json"))
    sk = {os.path.relpath(x["path"], str(d)): x for x in m["skipped_files"]}
    assert set(sk) == {"copy_model_9.pdb.gz", "copy_model_8.ent", "pae_x.npz", ".hidden",
                       [f for f in os.listdir(d) if f.startswith("confidence_")][0]}
    assert all(x["reason"] for x in sk.values())
    assert sk["copy_model_9.pdb.gz"]["structure_like"] and sk["copy_model_8.ent"]["structure_like"]
    assert not sk["pae_x.npz"]["structure_like"] and sk[".hidden"]["kind"] == "folder"
    assert m["counts"]["skipped_files"] == 5 and m["counts"]["skipped_structure_like"] == 2
    # every file under the folder is accounted for: imported/excluded/unrecognised structures + skipped
    n_files = sum(len(fs) for r, ds, fs in os.walk(d) if ".hidden" not in r)
    assert m["counts"]["found"] + m["counts"]["skipped_files"] - 1 == n_files       # -1: the hidden folder entry
    assert "copy_model_9.pdb.gz" in out and "copy_model_8.ent" in out and "skipped_files" in out


def test_refusal_names_structure_like_files(tmp_path, capsys):
    d = tmp_path / "only_gz"
    d.mkdir()
    pdb = os.path.join(RUN_A, next(f for f in os.listdir(RUN_A) if f.endswith(".pdb")))
    with open(pdb, "rb") as fi, gzip.open(d / "m_model_0.pdb.gz", "wb") as fo:
        fo.write(fi.read())
    rc = importer.main([str(d), "--protein-seq", PF, "--rna-seq", RF, "--out", str(tmp_path / "p")])
    err = capsys.readouterr().err
    assert rc == 2 and not (tmp_path / "p").exists()
    assert "m_model_0.pdb.gz" in err and "compressed" in err
