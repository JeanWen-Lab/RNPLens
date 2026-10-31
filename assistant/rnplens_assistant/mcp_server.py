"""RNPLens tool server for the general-agent arm, OUTSIDE the jail. Minimal MCP (JSON-RPC 2.0, newline-delimited) over
a Unix socket: initialize, tools/list, tools/call, ping. Tool calls run tools.call() with the same Workspace allowlist
and the same budget as the assistant arm; every call, including refused ones, is logged."""
import json
import os
import socket
import threading

from . import evidence as EV, tools as T


class Server:
    def __init__(self, sock_path, ws, store, max_calls):
        self.path, self.ws, self.store, self.max_calls = sock_path, ws, store, max_calls
        self.log = []
        if os.path.exists(sock_path):
            os.remove(sock_path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if len(sock_path) < 100:
            self.sock.bind(sock_path)
        else:      # AF_UNIX path limit: bind through a short /proc/self/fd handle on the directory (Linux)
            dfd = os.open(os.path.dirname(sock_path), os.O_RDONLY)
            try:
                self.sock.bind("/proc/self/fd/%d/%s" % (dfd, os.path.basename(sock_path)))
            finally:
                os.close(dfd)
        self.sock.listen(4)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _specs(self):
        return [{"name": n, "description": s["description"],
                 "inputSchema": {"type": "object", "additionalProperties": False, "properties": s["properties"], "required": s["required"]}}
                for n, s in T.SCHEMAS.items()]

    def _call(self, name, args):
        if len(self.log) >= self.max_calls:
            self.log.append({"step": len(self.log), "tool": name, "args": args, "status": "BUDGET_EXHAUSTED"})
            return {"error": "tool-call budget exhausted"}, True
        status, res, recs = T.call(self.ws, name, args or {})
        step = len(self.log)
        added = self.store.add(recs, step)
        self.log.append({"step": step, "tool": name, "args": args, "status": status if status != "OK" else res.get("status", "OK"), "result": res})
        view = {"result": res, "evidence": [{"id": r["id"], "what": r["label"], "value": EV.fmt(r), "state": r["state"]} for r in added]}
        return view, status != "OK"

    def _handle(self, conn):
        f = conn.makefile("rwb")
        for line in f:
            try:
                msg = json.loads(line)
            except Exception:
                continue
            mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
            if mid is None:
                continue                      # notification
            if method == "initialize":
                res = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                       "serverInfo": {"name": "rnplens", "version": "0.1.1"}}
            elif method == "tools/list":
                res = {"tools": self._specs()}
            elif method == "tools/call":
                view, is_err = self._call(params.get("name"), params.get("arguments"))
                res = {"content": [{"type": "text", "text": json.dumps(view, ensure_ascii=False)[:60000]}], "isError": is_err}
            elif method == "ping":
                res = {}
            else:
                out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}
                f.write((json.dumps(out) + "\n").encode()); f.flush(); continue
            f.write((json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}) + "\n").encode()); f.flush()

    def close(self):
        try:
            self.sock.close()
        finally:
            if os.path.exists(self.path):
                os.remove(self.path)
