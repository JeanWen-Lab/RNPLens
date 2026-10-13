"""Frozen regression (v0.1.1).

Profile is chosen by RNPBENCH_PROFILE (default "portable"; the reference platform runs "reference",
which requires every value bit-identical). Internal fixtures are included when
RNPBENCH_INTERNAL_FIXTURES points at them; otherwise the internal test is skipped (not passed).
"""
import os
import pytest
from rnpbench_evaluate import selftest

PROFILE = os.environ.get("RNPBENCH_PROFILE", "portable")
INTERNAL = os.environ.get("RNPBENCH_INTERNAL_FIXTURES")
_REC = {}


def _run():
    if "r" not in _REC:
        _REC["r"] = selftest.run(verbose=False, profile_name=PROFILE, internal_fixtures=INTERNAL)
    return _REC["r"]


def test_profile_is_the_frozen_one():
    rec, _ = _run()
    assert rec["profile_sha256"] == selftest.PROFILE_SHA256_AT_FREEZE


@pytest.mark.parametrize("fixture", list(selftest.PUBLIC_ORDER) + ["control_rna_removed", "control_renumbered_plus_1000",
                                                                   "control_protein_residues_all_ALA", "control_chain_labels_swapped"])
def test_public_fixture(fixture):
    rec, _ = _run()
    bad = [c for c in rec["checks"] if c["fixture"] == fixture and not c["ok"]]
    assert [c for c in rec["checks"] if c["fixture"] == fixture], "no checks ran"
    assert not bad, bad


@pytest.mark.skipif(not INTERNAL, reason="internal fixtures not available (set RNPBENCH_INTERNAL_FIXTURES)")
@pytest.mark.parametrize("fixture", selftest.INTERNAL_ORDER)
def test_internal_fixture(fixture):
    rec, _ = _run()
    cs = [c for c in rec["checks"] if c["fixture"] == fixture]
    assert cs, "no checks ran"
    assert not [c for c in cs if not c["ok"]]


def test_exact_categories_are_exact_under_any_profile():
    rec, _ = _run()
    bad = [c for c in rec["checks"] if c["tolerance_applied"] is None and not c["bit_exact"]]
    assert not bad, bad[:5]


def test_no_value_is_never_zero():
    _, res = _run()
    for k in ["control_rna_removed", "control_renumbered_plus_1000", "control_protein_residues_all_ALA"] + (["no_value_rf3_6NY2"] if INTERNAL else []):
        assert res[k]["dockq"]["status"] == "NO_VALUE" and res[k]["dockq"]["dockq"] is None
        assert "not DockQ = 0" in res[k]["dockq"]["no_value_note"]
