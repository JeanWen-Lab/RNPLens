"""The general-agent tool server speaks minimal MCP over a Unix socket and enforces the same budget and allowlist."""
import json
import os
import socket
import tempfile

from rnplens_assistant import evidence as EV, mcp_server, tools as T

from test_assistant_core import _task


def _rpc(f, mid, method, params=None):
    f.write((json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n").encode()); f.flush()
    return json.loads(f.readline())


def test_mcp_roundtrip_and_budget(tmp_path):
    t = _task(tmp_path)
    ws, store = T.Workspace(str(t), str(tmp_path / "run")), EV.Store()
    sp = os.path.join(os.path.relpath(tempfile.mkdtemp(dir=".")), "t.sock")
    try:
        srv = mcp_server.Server(sp, ws, store, max_calls=2)
    except PermissionError:
        import pytest; pytest.skip("this platform forbids Unix-socket binding (sandboxed test host)")
    s = socket.socket(socket.AF_UNIX); s.connect(sp); f = s.makefile("rwb")
    assert _rpc(f, 1, "initialize", {"protocolVersion": "2025-06-18"})["result"]["capabilities"] == {"tools": {}}
    f.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'); f.flush()
    tools = _rpc(f, 2, "tools/list")["result"]["tools"]
    assert {x["name"] for x in tools} == set(T.SCHEMAS)
    r = _rpc(f, 3, "tools/call", {"name": "import_predictions", "arguments": {"project_id": "p", "folders": ["runA", "runB"], "protein_fasta": "protein.fasta",
                                                                           "rna_fasta": "rna.fasta", "engine": None, "accept_offsets": False, "resolve": None}})
    assert r["result"]["isError"] is False and json.loads(r["result"]["content"][0]["text"])["result"]["status"] == "IMPORTED"
    r = _rpc(f, 4, "tools/call", {"name": "evaluate_against_reference", "arguments": {"project_id": "p", "reference": "/etc/passwd"}})
    assert r["result"]["isError"] is True and "outside the task inputs" in r["result"]["content"][0]["text"]
    r = _rpc(f, 5, "tools/call", {"name": "analyse_predictions", "arguments": {"project_id": "p"}})
    assert "budget exhausted" in r["result"]["content"][0]["text"]
    assert [x["status"] for x in srv.log] == ["IMPORTED", "ACCESS_REFUSED", "BUDGET_EXHAUSTED"]
    srv.close()
