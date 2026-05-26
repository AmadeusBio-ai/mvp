"""Launch napari with the napari-mcp plugin widget, idempotently.

Probes ``localhost:9877`` first. If something is already accepting connections,
exits 0 ("already running"). Otherwise spawns

    napari -w napari-mcp 'MCP Server'

detached from this process (so the napari window survives after the script
returns), then polls the port until it responds or until 30 s pass.

Usage:

    python skills/napari/scripts/launch_napari.py
    python skills/napari/scripts/launch_napari.py --port 9877 --timeout 30

Exit codes:
    0  napari is listening on the port
    1  timed out waiting for the port
    2  ``napari`` binary not found on PATH
"""

from __future__ import annotations

import argparse
import platform
import shutil
import socket
import subprocess
import sys
import time

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9877
DEFAULT_TIMEOUT = 30.0
LAUNCH_CMD = ["napari", "-w", "napari-mcp", "MCP Server"]


def port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def spawn_napari() -> subprocess.Popen:
    """Spawn napari fully detached from this process.

    POSIX: ``start_new_session=True`` puts napari in its own session, so
    closing this Python process does not propagate SIGHUP. Windows: combine
    ``DETACHED_PROCESS`` with ``CREATE_NEW_PROCESS_GROUP`` so the GUI is not
    tied to this script's console.
    """
    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if platform.system() == "Windows":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(LAUNCH_CMD, **kwargs)


def wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_open(host, port, timeout=0.5):
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    if port_open(args.host, args.port):
        print(f"napari already listening on {args.host}:{args.port}")
        return 0

    if shutil.which("napari") is None:
        print(
            "napari binary not found on PATH. Install napari and the "
            "napari-mcp plugin into the same env, then retry.",
            file=sys.stderr,
        )
        return 2

    print(f"launching: {' '.join(LAUNCH_CMD)}")
    spawn_napari()

    if wait_for_port(args.host, args.port, args.timeout):
        print(f"napari listening on {args.host}:{args.port}")
        return 0

    print(
        f"timed out after {args.timeout:.0f}s waiting for {args.host}:{args.port}. "
        "Check that the napari-mcp plugin is installed in the same env as napari "
        "(`pip install -e /home/yangyi/Code/napari-mcp-plugin`) and that "
        "`napari --info` lists it under Plugins.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
