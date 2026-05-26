"""Send one ``execute`` command to the napari-mcp plugin and print its response.

Wire protocol (raw TCP + UTF-8 JSON, default port 9877):

    request  {"type": "execute", "code": "<python>"}
    success  {"status": "success", "result": {"executed": true,  "output": "..."}}
    user err {"status": "success", "result": {"executed": false, "error":  "..."}}
    srv err  {"status": "error",   "message": "..."}

The framing has no length prefix; the server (and this client) parse
incrementally until ``json.loads`` succeeds. Lifted from
``napari-mcp-plugin/test_client.py`` so we stay in sync with upstream.

Usage:

    python skills/napari/scripts/napari_client.py "_result = 'pong'"
    python skills/napari/scripts/napari_client.py --file path/to/snippet.py
    cat snippet.py | python skills/napari/scripts/napari_client.py --stdin

Exit codes:
    0  status=success and executed=true
    3  status=success but executed=false (user code raised)
    4  status=error (server-level error: bad request, no callback, etc.)
    5  connection refused (napari not listening — run launch_napari.py first)
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import Any

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9877
DEFAULT_SOCKET_TIMEOUT = 10.0


def send_command(
    code: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_SOCKET_TIMEOUT,
) -> dict[str, Any]:
    """Send one execute command and read one JSON response.

    Mirrors the framing loop from napari-mcp-plugin/test_client.py: the
    server does not close the connection after responding, so we cannot
    read until EOF — we accumulate bytes and retry ``json.loads`` until it
    succeeds.
    """
    payload = json.dumps({"type": "execute", "code": code}).encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as s:
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


def _read_code(args: argparse.Namespace) -> str:
    if args.stdin:
        return sys.stdin.read()
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.code is not None:
        return args.code
    sys.exit("error: provide a code string, --file PATH, or --stdin")


def _classify(response: dict[str, Any]) -> int:
    status = response.get("status")
    if status == "success":
        result = response.get("result")
        if isinstance(result, dict) and result.get("executed") is False:
            return 3
        return 0
    if status == "error":
        return 4
    return 4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("code", nargs="?", help="Python code to execute")
    parser.add_argument("--file", help="Read code from this file instead of argv")
    parser.add_argument("--stdin", action="store_true", help="Read code from stdin")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_SOCKET_TIMEOUT,
        help="Socket I/O timeout in seconds (separate from server's 300s exec timeout)",
    )
    args = parser.parse_args()

    code = _read_code(args)

    try:
        response = send_command(code, args.host, args.port, args.timeout)
    except ConnectionRefusedError:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": (
                        f"connection refused on {args.host}:{args.port} — napari is "
                        "not listening. Run skills/napari/scripts/launch_napari.py "
                        "first."
                    ),
                }
            )
        )
        return 5
    except OSError as e:
        print(json.dumps({"status": "error", "message": f"socket error: {e}"}))
        return 5

    print(json.dumps(response, indent=2, default=str))
    return _classify(response)


if __name__ == "__main__":
    sys.exit(main())
