#!/usr/bin/env python3
"""Send PyMOL Python to the MCP Socket Plugin on localhost:9876.

Reads code from --code or stdin, forwards it as
    {"type": "pymol_command", "code": <code>}
and prints PyMOL's captured stdout. Scans the output for known
silent-error patterns (PyMOL sometimes prints errors without raising)
and emits a WARNING line on stderr when one matches.

Exit codes:
  0 — success
  1 — PyMOL/exec error
  2 — connection or transport error

Convenience subcommand:
  --fetch-pdb <ID>    Fetch a PDB ID into PyMOL with async_=0 and apply a
                      sensible default cartoon view. Equivalent to a short
                      cmd.fetch + cmd.show_as + cmd.orient sequence, sent
                      over the same socket. Use --name to set the object
                      name (defaults to the PDB ID, lowercased).

Stdlib only.
"""
import argparse
import json
import re
import socket
import sys

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9876
# Heavy tasks (large PDBs, ray-traces, alignments) need a generous timeout
# on the response side. The connect-side timeout is short (set below) so we
# fail fast when PyMOL isn't listening at all.
DEFAULT_TIMEOUT = 300.0

SILENT_ERROR_PATTERNS = {
    "SYNTAX_ERROR": (r"syntax error", r"invalid syntax", r"unknown command"),
    "SELECTION_ERROR": (
        r"invalid selection",
        r"no atoms selected",
        r"selection not found",
        r"selection \S+ doesn't exist",
    ),
    "OBJECT_NOT_FOUND": (
        r"object \S+ not found",
        r"object \S+ does not exist",
        r"unable to find object named \S+",
    ),
    "ATOM_NOT_FOUND": (r"no atoms matched", r"no atoms in selection", r"atom not found"),
    "FILE_ERROR": (
        r"unable to open file",
        r"no such file",
        r"permission denied",
        r"error reading file",
        r"error writing file",
    ),
    "PARAMETER_ERROR": (
        r"incorrect number of parameters",
        r"invalid parameter",
        r"parameter out of range",
    ),
    "FETCH_ERROR": (
        r"fetch-error",
        r"unable to fetch",
        r"could not download",
    ),
}


def detect_silent_error(output: str):
    if not output:
        return None
    low = output.lower()
    for label, patterns in SILENT_ERROR_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, low):
                return f"{label} (matched /{pat}/)"
    return None


def send(code: str, host: str, port: int, timeout: float) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Short connect-side timeout: fail fast if PyMOL isn't listening.
    sock.settimeout(5.0)
    try:
        sock.connect((host, port))
    except ConnectionRefusedError:
        sys.stderr.write(
            f"Cannot connect to PyMOL at {host}:{port}. "
            "Run pymol_launch.py first, or start PyMOL with "
            '`pymol -d "mcp_start"`.\n'
        )
        sys.exit(2)
    except (socket.timeout, OSError) as e:
        sys.stderr.write(f"Network error connecting to {host}:{port}: {e}\n")
        sys.exit(2)

    # Switch to the longer execution-side timeout for command processing.
    sock.settimeout(timeout)

    try:
        # Newline-framed JSON. The plugin uses newline framing on its receive loop.
        payload = json.dumps({"type": "pymol_command", "code": code}).encode("utf-8") + b"\n"
        sock.sendall(payload)

        # Close the writing half so the plugin's recv() sees EOF and starts
        # executing immediately rather than hanging waiting for more bytes.
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass

        buffer = b""
        while True:
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                sys.stderr.write(
                    f"Timed out waiting for PyMOL response after {timeout} seconds.\n"
                )
                sys.exit(2)

            if not chunk:
                break

            buffer += chunk

            # Opportunistically try to parse — the plugin may flush the full
            # JSON before closing, so we can return early.
            try:
                return json.loads(buffer.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # JSON not yet complete (or split mid-multibyte). Keep reading.
                continue

        if buffer:
            return json.loads(buffer.decode("utf-8"))

        sys.stderr.write("No response from PyMOL plugin.\n")
        sys.exit(2)
    finally:
        sock.close()


def build_fetch_pdb_code(pdb_id: str, obj_name: str) -> str:
    """Build a PyMOL Python snippet that fetches a PDB and applies a default view.

    Uses async_=0 to guarantee the object exists before the next command,
    and assigns a useful summary to _result so the caller sees it.
    """
    pid = pdb_id.strip().lower()
    name = obj_name.strip()
    return f"""
cmd.fetch('{pid}', '{name}', async_=0)
cmd.show_as('cartoon', '{name}')
cmd.orient('{name}')
_result = {{
    'object': '{name}',
    'chains': cmd.get_chains('{name}'),
    'n_atoms': cmd.count_atoms('{name}'),
    'extent': cmd.get_extent('{name}'),
}}
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code", help="PyMOL Python code (default: read stdin)")
    p.add_argument(
        "--fetch-pdb",
        metavar="ID",
        help="Convenience: fetch a PDB ID (cmd.fetch with async_=0) "
        "and apply a default cartoon view. Mutually exclusive with --code/stdin.",
    )
    p.add_argument(
        "--name",
        help="Object name for --fetch-pdb (defaults to the PDB ID, lowercased).",
    )
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = p.parse_args()

    # Resolve which code blob to send.
    if args.fetch_pdb is not None:
        if args.code is not None:
            sys.stderr.write("Use either --fetch-pdb or --code, not both.\n")
            sys.exit(2)
        pdb_id = args.fetch_pdb.strip()
        obj_name = (args.name or pdb_id).strip().lower()
        code = build_fetch_pdb_code(pdb_id, obj_name)
    else:
        code = args.code if args.code is not None else sys.stdin.read()
        if not code.strip():
            sys.stderr.write("No code provided (use --code, --fetch-pdb, or pipe via stdin).\n")
            sys.exit(2)

    # SAFETY CATCH: cmd.reinitialize() hard-crashes the plugin. Block it.
    # Use cmd.delete('all') to clear the workspace instead.
    if "cmd.reinitialize" in code:
        sys.stderr.write(
            "ERROR: cmd.reinitialize() is blocked — it hard-crashes the MCP socket. "
            "Use cmd.delete('all') to clear the workspace instead.\n"
        )
        sys.exit(1)

    response = send(code, args.host, args.port, args.timeout)
    status = response.get("status", "error")
    result = response.get("result")

    if status == "success" and isinstance(result, dict) and result.get("executed"):
        output = result.get("output") or ""
        if output:
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
        warning = detect_silent_error(output)
        if warning:
            sys.stderr.write(f"WARNING: possible silent PyMOL error — {warning}\n")
        sys.exit(0)

    if isinstance(result, dict) and result.get("error"):
        sys.stderr.write(result["error"].rstrip() + "\n")
    elif response.get("message"):
        sys.stderr.write(str(response["message"]).rstrip() + "\n")
    else:
        sys.stderr.write(json.dumps(response) + "\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
