"""Owner programme 2026-10-18, section 10: release-candidate preparation files exist, carry placeholders where the
owner must decide, and state no approval or live result that does not exist."""
import os
import re

import pytest

import rnplens

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
pytestmark = pytest.mark.skipif(not os.path.isfile(os.path.join(ROOT, "CITATION.cff")), reason="repository files not available")


def read(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


def test_citation_records_the_owner_supplied_authors():
    # Before publication this test asserted that the author block still held three
    # "TO BE SUPPLIED BY THE OWNER" placeholders, so that no author could be invented or
    # inferred from git history. The owner has now supplied the author list and affiliations
    # from the authoritative manuscript, so the guard asserts those instead.
    c = read("CITATION.cff")
    assert re.search(r"^version: %s$" % re.escape(rnplens.__version__), c, flags=re.M)
    assert "TO BE SUPPLIED BY THE OWNER" not in c
    assert "doi:" not in c.lower()
    for expected in ('family-names: "Parker"', 'given-names: "Brian J."',
                     'family-names: "Wen"', 'given-names: "Jiayu"',
                     "Brian.Parker@anu.edu.au", "Jiayu.Wen@anu.edu.au"):
        assert expected in c, expected
    assert c.count("family-names:") == 2, "exactly the two manuscript authors"


def test_release_prep_pages_exist_and_are_linked():
    readme = read("README.md")
    for f in ("platforms.md", "model_and_privacy.md", "example_data_provenance.md", "release_conditions.md", "code_availability.md"):
        assert os.path.isfile(os.path.join(DOCS, f)) and ("docs/%s" % f) in readme, f


def test_no_claimed_approval_or_live_result():
    cond = read("docs", "release_conditions.md")
    for c in ("Institutional IP clearance (ANU) | OPEN",
              "Redistribution of bundled data | OPEN", "Live qualification of the Assistant | OPEN",
              "Sealed evaluation of the Assistant | OPEN", "Owner visual checks of the viewer | OPEN"):
        assert c in cond, c
    for c in ("Licence | CLOSED", "Authorship and affiliations | CLOSED"):
        assert c in cond, c
    model = read("docs", "model_and_privacy.md")
    assert "no live Codex call has been made for RNPLens 0.4" in model
    for f in ("platforms.md", "model_and_privacy.md", "code_availability.md", "release_conditions.md"):
        t = read("docs", f).lower()
        assert not re.search(r"live call passed|live qualification passed|approved by anu|clearance (was )?granted", t), f
        assert all(t[m.start() - 4:m.start()] == "not " for m in re.finditer(r"live(-| )qualified", t)), f
    assert "unknown" in read("docs", "example_data_provenance.md").lower()


def test_platform_matrix_states_native_single_computer_operation():
    """0.4 native platforms: each supported system runs the assistant on its own; no second computer and no SSH."""
    p = read("docs", "platforms.md")
    assert "**supported natively**" in p and "Seatbelt" in p and "bubblewrap" in p and "no second computer" in p
    assert "macOS → Linux over SSH" not in p and "ssh -t" not in p and "LINUX_HOST" not in p
