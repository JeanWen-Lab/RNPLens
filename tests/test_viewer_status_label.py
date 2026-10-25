"""The viewer is labelled, on the page, in its manifest and in the command output, as automatically tested, with basic
display and interaction confirmed manually on macOS and the remaining manual checks named (owner decisions, 17 and
18 Oct 2026: not fully visually qualified). The page's limits text says where the contacts come from and that
distances are recomputed (parity-gated) when the page is written."""
import json
import os

from rnplens import analyse, importer, trace, viewer

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
RF = os.path.join(EX, "reference_free", "report_7K9D")
LABEL = ("automatically tested; basic on-screen display and interaction confirmed manually by the owner on macOS "
         "(2026-10-18, 2JEA page); switching between binding-hypothesis representatives and offline operation not yet "
         "confirmed manually; not fully visually qualified")
SHORT = "automatically tested; basic display and interaction confirmed manually by the owner on macOS (2026-10-18); switching between binding-hypothesis representatives and offline operation not yet confirmed manually; not fully visually qualified"


def test_status_label_on_page_manifest_and_command(tmp_path, capsys):
    ps = os.path.join(EX, "reference_based", "7K9D_protein.fasta")
    rs = os.path.join(EX, "reference_based", "7K9D_rna.fasta")
    assert importer.run([os.path.join(RF, "exec_A"), os.path.join(RF, "exec_B")], importer.read_sequence_arg(ps),
                        importer.read_sequence_arg(rs), str(tmp_path / "p"), "7K9D_example", "BOLTZ2") == 0
    assert analyse.run(str(tmp_path / "p"), str(tmp_path / "a")) == 0
    capsys.readouterr()
    assert viewer.main([str(tmp_path / "p"), "--analysis", str(tmp_path / "a"), "--rna", "15-30"]) == 0
    out = capsys.readouterr().out
    assert LABEL in out
    page = tmp_path / "a" / "viewer_15-30" / "viewer.html"
    html = page.read_text(encoding="utf-8")
    assert 'id="rnplens-viewer-status"' in html and LABEL in html
    man = json.load(open(tmp_path / "a" / "viewer_15-30" / "viewer_manifest.json"))
    assert LABEL in man["viewer_status"]
    assert LABEL in viewer.STATUS and trace.wording_audit(viewer.STATUS) == []
    assert "It computes no contacts" not in html and "computes no contacts" not in viewer.LIMITS
    assert "taken from Report's record" in viewer.LIMITS and "recomputes the contacts" in viewer.LIMITS
    assert viewer.LIMITS.replace("'", "&#x27;") in html and trace.wording_audit(viewer.LIMITS) == []
    assert man["limits"] == viewer.LIMITS


def test_status_label_in_command_help():
    from rnplens import cli
    assert SHORT in cli.INTERACTIVE["view"][1] and "awaiting manual visual confirmation" not in cli.INTERACTIVE["view"][1]
