#!/usr/bin/env python3
"""Ensure PyMOL is running and listening on the MCP socket port.

Checks whether something is accepting TCP connections on localhost:9876.
If yes: prints "ready" and exits 0.
If no: spawns `pymol -d "mcp_start"` detached from this process, then polls
the port up to --wait seconds. Exits 0 once the port is up, 1 if it never
comes up, 2 if the `pymol` binary cannot be found.

Stdlib only. Safe to call before every PyMOL task — it is a no-op when
PyMOL is already listening.

Usage:
  python pymol_launch.py                # check + launch if needed, wait 30s
  python pymol_launch.py --wait 60      # give PyMOL longer to start
  python pymol_launch.py --check-only   # report status, never launch
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import time

HOST = "localhost"
PORT = 9876


def port_is_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to (host, port) succeeds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def launch_pymol() -> subprocess.Popen:
    """Spawn PyMOL with the MCP plugin auto-started, detached from this process."""
    pymol_bin = shutil.which("pymol")
    if pymol_bin is None:
        sys.stderr.write(
            "ERROR: 'pymol' binary not found in PATH. "
            "Install PyMOL and ensure `pymol` is on your PATH, then retry.\n"
        )
        sys.exit(2)

    # Detach so PyMOL outlives this helper. Discard PyMOL's stdout/stderr —
    # we only care whether the socket comes up, and the plugin captures
    # command output via the socket protocol anyway.
    devnull = open(os.devnull, "wb")
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        creationflags = 0x00000008 | 0x00000200
        proc = subprocess.Popen(
            [pymol_bin, "-d", "mcp_start"],
            stdout=devnull,
            stderr=devnull,
            stdin=devnull,
            creationflags=creationflags,
            close_fds=True,
        )
    else:
        proc = subprocess.Popen(
            [pymol_bin, "-d", "mcp_start"],
            stdout=devnull,
            stderr=devnull,
            stdin=devnull,
            start_new_session=True,
            close_fds=True,
        )
    return proc


def wait_for_port(host: str, port: int, deadline: float) -> bool:
    """Poll the port until it opens or the deadline passes. Return True on success."""
    while time.monotonic() < deadline:
        if port_is_open(host, port):
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default=HOST, help="Hostname (default: localhost)")
    p.add_argument("--port", type=int, default=PORT, help="Port (default: 9876)")
    p.add_argument(
        "--wait",
        type=float,
        default=30.0,
        help="Seconds to wait for the port to come up after launch (default: 30)",
    )
    p.add_argument(
        "--check-only",
        action="store_true",
        help="Report status only; never launch PyMOL",
    )
    args = p.parse_args()

    if port_is_open(args.host, args.port):
        print("ready")
        sys.exit(0)

    if args.check_only:
        print("not_running")
        sys.exit(1)

    sys.stderr.write(
        f"PyMOL not detected on {args.host}:{args.port}. "
        f'Launching `pymol -d "mcp_start"` ...\n'
    )
    launch_pymol()

    deadline = time.monotonic() + args.wait
    if wait_for_port(args.host, args.port, deadline):
        print("ready")
        sys.exit(0)

    sys.stderr.write(
        f"PyMOL did not start listening within {args.wait:.0f}s. "
        "Open PyMOL manually and confirm the MCP Socket Plugin is set to autostart "
        '(or run `pymol -d "mcp_start"` in a terminal).\n'
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
