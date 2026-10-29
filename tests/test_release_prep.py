"""Release documentation states established facts: MIT licensing of both distributions, the recorded authors, a
consistent NOTICE, complete data provenance, and no approval, qualification or live result that does not exist."""
import csv
import hashlib
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


IP_GATE = re.compile(r"institutional \(ANU\)|institutional IP|IP clearance|intellectual[- ]property|pending ANU|ANU IP|ANU/owner", re.I)


def public_documents():
    files = ["README.md", "NOTICE", "CITATION.cff", "pyproject.toml", os.path.join("assistant", "pyproject.toml"),
             os.path.join("examples", "DATA_PROVENANCE.tsv"), os.path.join("src", "rnpbench_evaluate", "fixtures", "fixture_sources.json")]
    return files + [os.path.join("docs", f) for f in sorted(os.listdir(DOCS)) if f.endswith(".md")]


def test_release_status_states_facts_and_claims_no_unperformed_qualification():
    cond = read("docs", "release_conditions.md")
    assert "| Licence | MIT for the core toolkit and the optional Assistant" in cond
    for c in ("| Live qualification of the Assistant | not performed", "| Sealed evaluation of the Assistant | not performed",
              "| Manual visual checks of the viewer | not performed", "| Diagnose (user-facing) | blocked by design in 0.4",
              "| Evaluate four-axis geometry | blocked by design in 0.4"):
        assert c in cond, c
    model = read("docs", "model_and_privacy.md")
    assert "no live Codex call has been made for RNPLens 0.4" in model
    for f in ("platforms.md", "model_and_privacy.md", "code_availability.md", "release_conditions.md"):
        t = read("docs", f).lower()
        assert not re.search(r"live call passed|live qualification passed|approved by anu|clearance (was )?granted", t), f
        assert all(t[m.start() - 4:m.start()] == "not " for m in re.finditer(r"live(-| )qualified", t)), f


def test_no_institutional_ip_gate_in_public_documents():
    for p in public_documents():
        if os.path.isfile(os.path.join(ROOT, p)):
            m = IP_GATE.search(read(p))
            assert m is None, (p, m and m.group(0))


def test_mit_licensing_configuration():
    lic = read("LICENSE")
    assert lic.startswith("MIT License\n") and "Copyright (c) 2026 The RNPLens authors" in lic
    assert read("assistant", "LICENSE") == lic
    core, asst = read("pyproject.toml"), read("assistant", "pyproject.toml")
    assert re.search(r'^license = "MIT"$', core, re.M) and re.search(r'^license = "MIT"$', asst, re.M)
    assert 'license-files = ["LICENSE", "NOTICE"]' in core and 'license-files = ["LICENSE"]' in asst
    assert re.search(r"^license: MIT$", read("CITATION.cff"), re.M)
    assert "MIT LICENSE at the repository root" in read("NOTICE")


def test_notice_is_consistent_and_its_digests_match_the_files():
    n = read("NOTICE")
    for stale in ("UNRESOLVED", "Release blocker", "PUBLIC RELEASE ADDENDUM", "staging/0.4", "release_prep_2026", "is left to legal"):
        assert stale not in n, stale
    vendor = os.path.join(ROOT, "src", "rnplens", "vendor", "molstar")
    ref = os.path.join(ROOT, "src", "rnpbench_diagnose", "reference")
    for p in [os.path.join(vendor, f) for f in ("molstar.js", "molstar.css", "LICENSE")] + \
             [os.path.join(ref, f) for f in ("cohortP_disagreement.tsv", "cohortE_disagreement.tsv")]:
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() in n, p
    for holder in ("Mol* contributors", "Facebook, Inc. and its affiliates", "Lee Byron", "Equinor",
                   "Institute for Health Metrics and Evaluation", "Tarek Sherif", "Arseny Kapoulkine", "Simon Rodriguez",
                   "Inigo Quilez"):
        assert holder in n, holder


def test_data_provenance_covers_every_bundled_structure_and_confidence_file():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "examples", "DATA_PROVENANCE.tsv"), encoding="utf-8"), delimiter="\t"))
    listed = {r["file"]: r for r in rows}
    assert len(listed) == len(rows)
    for r in rows:
        p = os.path.join(ROOT, r["file"])
        assert os.path.isfile(p), r["file"]
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == r["sha256"], r["file"]
    bundled = []
    for top in ("examples", "src"):
        for dp, _, fns in os.walk(os.path.join(ROOT, top)):
            for f in fns:
                if f.endswith((".pdb", ".cif")) or (f.startswith("confidence_") and f.endswith(".json")):
                    bundled.append(os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/"))
    assert not sorted(set(bundled) - set(listed)), sorted(set(bundled) - set(listed))
    assert sum(os.path.basename(f).startswith("confidence_") for f in listed) == 6


def test_platform_matrix_states_native_single_computer_operation():
    """0.4 native platforms: each supported system runs the assistant on its own; no second computer and no SSH."""
    p = read("docs", "platforms.md")
    assert "**supported natively**" in p and "Seatbelt" in p and "bubblewrap" in p and "no second computer" in p
    assert "macOS → Linux over SSH" not in p and "ssh -t" not in p and "LINUX_HOST" not in p
