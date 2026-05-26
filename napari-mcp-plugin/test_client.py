"""Minimal test client for napari-mcp.

Run napari with the MCP Server widget open, then run this script. It sends
a few commands to add layers to the viewer over the socket.

    python tools/test_client.py
"""

from __future__ import annotations

import json
import socket
import sys


def send_command(code: str, host: str = "localhost", port: int = 9876) -> dict:
    """Send one command and read one JSON response.

    The server doesn't close the connection after responding (it loops back
    to read more commands), so we can't read-until-EOF. We accumulate bytes
    and try json.loads() incrementally until it succeeds, which matches the
    server's own framing rule.
    """
    payload = json.dumps({"type": "execute", "code": code}).encode("utf-8")

    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(payload)
        buffer = b""
        while True:
            data = s.recv(4096)
            if not data:
                break
            buffer += data
            try:
                return json.loads(buffer.decode("utf-8"))
            except json.JSONDecodeError:
                continue
    raise RuntimeError("connection closed before a complete response was received")


def main() -> int:
    examples = [
        # 1. Add a random image
        "import numpy as np\nviewer.add_image(np.random.rand(256, 256), name='random')",
        # 2. Add some points
        "viewer.add_points([[50, 50], [100, 100], [150, 150]], name='dots', size=10)",
        # 3. Read back layer names
        "_result = [layer.name for layer in viewer.layers]",
    ]

    for i, code in enumerate(examples, start=1):
        print(f"\n--- request {i} ---")
        print(code)
        try:
            resp = send_command(code)
        except Exception as e:
            print(f"  request failed: {e}")
            return 1
        print(f"response: {resp}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
