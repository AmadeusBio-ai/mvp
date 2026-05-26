"""Execute Python code received over the socket against a napari Viewer.

Unlike PyMOL, napari's Qt objects are not safe to manipulate from a worker
thread; `viewer.add_image(...)` from a non-GUI thread can crash the app or
silently corrupt state. We therefore route every execution through a Qt
signal so it runs on the main (GUI) thread, and block the worker thread on
a threading.Event until the result is ready.
"""

from __future__ import annotations

import io
import threading
import traceback
from contextlib import redirect_stdout
from typing import Any, Dict

import numpy as np
from qtpy.QtCore import QObject, Signal, Qt


def _exec_code_in_namespace(code: str, viewer) -> Dict[str, Any]:
    """Run `code` synchronously on whatever thread we're currently on.

    Exposed names inside the user code:
        viewer  -- the live napari.Viewer
        napari  -- the napari module
        np      -- numpy
    """
    import napari  # imported lazily so module import stays cheap

    print(f"[napari-mcp] Executing command:\n{code}")
    exec_globals: Dict[str, Any] = {
        "viewer": viewer,
        "napari": napari,
        "np": np,
        "__builtins__": __builtins__,
    }
    output_buffer = io.StringIO()
    try:
        with redirect_stdout(output_buffer):
            exec(code, exec_globals)
    except Exception as e:
        error_msg = f"Error executing napari command: {e}"
        print(error_msg)
        traceback.print_exc()
        return {"executed": False, "error": error_msg}

    output = output_buffer.getvalue()
    if output:
        print(f"[napari-mcp] Command output: {output}")
        return {"executed": True, "output": output}
    if "_result" in exec_globals:
        result = str(exec_globals["_result"])
        print(f"[napari-mcp] Command result: {result}")
        return {"executed": True, "output": result}
    return {"executed": True, "output": "Command executed successfully (no output)"}


class GuiThreadExecutor(QObject):
    """Marshals exec() calls from the socket worker thread to the GUI thread.

    Created and `moveToThread`-ed onto the GUI thread (it's typically created
    *on* the GUI thread, which has the same effect). The socket thread calls
    `execute(code)`; under the hood we emit a Qt signal with a
    BlockingQueuedConnection-like pattern: signal -> slot runs on GUI thread,
    a threading.Event unblocks the worker once the result is stored.
    """

    _run_requested = Signal(str, object, object)  # code, result_container, event

    def __init__(self, viewer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._viewer = viewer
        # QueuedConnection forces the slot to be invoked on the receiver's
        # thread affinity (the GUI thread, since we live there). We don't use
        # BlockingQueuedConnection because we manage blocking ourselves via
        # an Event, which works even when emitter and receiver are on the same
        # thread (which would dead-lock with BlockingQueuedConnection).
        self._run_requested.connect(self._on_run_requested, Qt.QueuedConnection)

    def execute(self, code: str) -> Dict[str, Any]:
        """Called from the socket worker thread. Blocks until done."""
        result_container: Dict[str, Any] = {}
        done = threading.Event()
        self._run_requested.emit(code, result_container, done)
        # Wait for the GUI thread to finish. Generous timeout so a long-running
        # `viewer.add_image` on a big array doesn't spuriously fail.
        finished = done.wait(timeout=300.0)
        if not finished:
            return {"executed": False, "error": "GUI thread execution timed out"}
        return result_container.get(
            "result", {"executed": False, "error": "no result produced"}
        )

    def _on_run_requested(self, code: str, result_container: dict, done) -> None:
        # Runs on the GUI thread.
        try:
            result_container["result"] = _exec_code_in_namespace(code, self._viewer)
        except Exception as e:  # pragma: no cover - defensive
            result_container["result"] = {"executed": False, "error": str(e)}
        finally:
            done.set()
