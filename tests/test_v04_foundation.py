"""0.4 foundation: provenance helpers, atomic writes, command table and capability registry."""
import json
import os

import pytest

from rnplens import capabilities, cli, provenance as pv


def test_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    p = tmp_path / "a" / "x.json"
    pv.atomic_write_json(str(p), {"b": 1, "a": 2})
    pv.atomic_write_json(str(p), {"c": 3})
    assert json.load(open(p)) == {"c": 3} and [f for f in os.listdir(p.parent)] == ["x.json"]


def test_atomic_write_failure_keeps_previous(tmp_path):
    p = tmp_path / "x.json"
    pv.atomic_write_json(str(p), {"ok": True})
    with pytest.raises(TypeError):
        pv._atomic(str(p), 123, "w")          # write of a non-string fails mid-way
    assert json.load(open(p)) == {"ok": True} and os.listdir(tmp_path) == ["x.json"]


def test_block_hashes_inputs_and_config(tmp_path):
    f = tmp_path / "in.txt"; f.write_text("abc")
    b = pv.block("k", [str(f)], "definition", {"t": 0.5})
    assert b["inputs"][0]["sha256"] == pv.sha256_file(str(f)) and b["config_sha256"] == pv.sha256_json({"t": 0.5})
    assert pv.sha256_json({"a": 1, "b": 2}) == pv.sha256_json({"b": 2, "a": 1})


def test_evidence_id_format():
    assert pv.evidence_id("region_40-60/region.json", "contacts/3") == "region_40-60/region.json#/contacts/3"


def test_interactive_commands_listed_and_missing_modules_reported(capsys):
    assert all(k in cli.USAGE for k in cli.INTERACTIVE)
    offered, missing = capabilities.available()
    ids = {m["id"] for m in missing}
    assert {"geometry_four_axis", "ranking", "rna_conformation_difference"} <= ids
    assert all(c["status"] != "UNAVAILABLE" for c in offered)
