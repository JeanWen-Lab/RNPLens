"""P3 (QA outside-user-viewer, fix round): the 0.4 guide (the user guide and the Assistant's packaged copy) states that Evaluate's four-axis
geometry route is BLOCKED (residue-correspondence defect, 2026-10-14) and that DockQ, DockQ class, fnat, iRMSD and
LRMSD remain available under their own definitions and are not replacements for the four-axis decomposition. Nothing
in the guide may describe the geometry values as computed."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COPIES = [os.path.join(ROOT, "docs", "which_analysis_should_i_use.md"),
          os.path.join(ROOT, "assistant", "rnplens_assistant", "docs", "which_analysis_should_i_use.md")]


def _text(path):
    # Since 0.4.1 the user guide (docs/) and the Assistant's packaged, evaluated copy are maintained separately;
    # both must state the geometry block.
    lines = [re.sub(r"^> ?", "", l) for l in open(path, encoding="utf-8").read().splitlines()]     # blockquote markers
    return " ".join(" ".join(lines).split())


@pytest.mark.parametrize("path", COPIES)
def test_guide_states_the_geometry_route_is_blocked(path):
    t = _text(path)
    assert "**Four-axis geometry is blocked.**" in t
    assert "residue-correspondence defect found on 2026-10-14" in t
    assert "values are not computed and must not be reported" in t
    assert "DockQ, DockQ class, fnat, iRMSD and LRMSD remain available under their own definitions" in t
    assert "They are not replacements for the four-axis decomposition" in t
    assert "`BLOCKED` (geometry)" in t and "The geometry values are blocked in this version and are not computed." in t


@pytest.mark.parametrize("path", COPIES)
def test_no_geometry_row_reads_as_a_computed_value(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    for name in ("RNA internal C4′ RMSD", "RNA placement C4′ RMSD", "protein internal Cα RMSD"):
        row = [l for l in lines if l.startswith("| %s |" % name)]
        assert len(row) == 1 and "**blocked, not computed** (four-axis geometry route; correspondence defect, 2026-10-14)" in row[0], name
    start = [l for l in lines if l.startswith("| a prediction **and** an experimental structure")][0]
    assert re.search(r"RNA shape, RNA placement and protein geometry \(the four-axis geometry route\) are blocked", start)
    assert "LRMSD), RNA shape" not in start                  # the old wording listed geometry among Evaluate's results
