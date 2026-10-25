"""Runs INSIDE the Codex jail (stdlib only). Codex starts it as an MCP stdio server; it forwards newline-delimited
JSON-RPC between Codex and the RNPLens tool server listening on /work/tools.sock outside the jail."""
import socket
import sys
import threading

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect("/work/tools.sock")


def up():
    for line in sys.stdin.buffer:
        s.sendall(line)
    try:
        s.shutdown(socket.SHUT_WR)
    except OSError:
        pass


threading.Thread(target=up, daemon=True).start()
for line in s.makefile("rb"):
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()
