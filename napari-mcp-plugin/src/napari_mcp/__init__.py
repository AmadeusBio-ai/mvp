"""napari-mcp

A napari plugin that listens on a TCP socket and executes Python code
received from external clients (e.g. an MCP server) against the running
napari viewer.

Mirrors the design of the reference PyMOL MCP plugin: a JSON line-protocol
on a configurable port, with a small Qt widget for status & control.
"""

from __future__ import annotations

__all__ = ["MCPServerWidget"]
__version__ = "0.1.0"


def __getattr__(name):
    # Lazy import so the package can be imported in environments without Qt
    # (e.g. when only the socket server is being used or tested).
    if name == "MCPServerWidget":
        from ._widget import MCPServerWidget
        return MCPServerWidget
    raise AttributeError(f"module 'napari_mcp' has no attribute {name!r}")
