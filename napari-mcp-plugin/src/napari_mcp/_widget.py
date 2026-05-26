"""Qt dock widget for napari-mcp.

Mirrors the layout of pymol_mcp_plugin.ui: a header label, a port spinbox,
a status label, a toggle-listening button, and a close button. The widget
auto-starts the socket server on creation, so launching with

    napari -w napari-mcp 'MCP Server'

drops the user straight into a listening state, matching the PyMOL plugin's
`mcp_start` workflow.

npe2 widget contract: the callable for a widget contribution receives the
active napari.Viewer as its single positional argument. The class itself
serves as that callable here (instantiation == widget construction).
"""

from __future__ import annotations

from typing import Optional

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ._executor import GuiThreadExecutor
from ._socket_server import SocketServer


DEFAULT_PORT = 9877


class MCPServerWidget(QWidget):
    """Dock widget that owns the socket server and shows its status."""

    def __init__(self, napari_viewer=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._viewer = napari_viewer
        self._server: Optional[SocketServer] = None
        self._executor: Optional[GuiThreadExecutor] = None
        self._listening = False

        self._build_ui()
        # Auto-start on creation. This is the napari analogue of PyMOL's
        # `mcp_start` command: opening the widget == starting the server.
        # The launch incantation `napari -w napari-mcp 'MCP Server'` therefore
        # produces a listening server with no further interaction.
        self._start_server()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle("napari MCP Plugin")

        root = QVBoxLayout(self)

        header = QLabel("napari MCP Plugin\nSocket Server for MCP Integration")
        header.setAlignment(Qt.AlignCenter)
        header.setWordWrap(True)
        header.setStyleSheet("background-color: #000; color: white; padding: 20px")
        header.setMinimumSize(280, 60)
        root.addWidget(header)

        grid = QGridLayout()
        grid.addWidget(QLabel("Port"), 0, 0)
        self.input_port = QSpinBox()
        self.input_port.setRange(1024, 65535)
        self.input_port.setValue(DEFAULT_PORT)
        grid.addWidget(self.input_port, 0, 1)

        grid.addWidget(QLabel("Status:"), 1, 0)
        self.label_status = QLabel("Not listening")
        self.label_status.setStyleSheet("color: red;")
        grid.addWidget(self.label_status, 1, 1)
        root.addLayout(grid)

        button_row = QHBoxLayout()
        self.button_toggle = QPushButton("Start Listening")
        self.button_toggle.clicked.connect(self._toggle_listening)
        button_row.addWidget(self.button_toggle)
        root.addLayout(button_row)

        close_row = QHBoxLayout()
        self.button_close = QPushButton("Close")
        self.button_close.clicked.connect(self._close_widget)
        close_row.addWidget(self.button_close)
        root.addLayout(close_row)

        root.addStretch(1)

    # ------------------------------------------------------------------
    # server lifecycle
    # ------------------------------------------------------------------
    def _start_server(self) -> None:
        if self._listening:
            return
        port = int(self.input_port.value())

        # Build the executor here (on the GUI thread) so its signal slot has
        # the right thread affinity.
        self._executor = GuiThreadExecutor(self._viewer, parent=self)

        self._server = SocketServer(port=port)
        ok = self._server.start(command_callback=self._executor.execute)
        if ok:
            self._listening = True
            self._set_status(f"Listening on port {port}", listening=True)
            self.button_toggle.setText("Stop Listening")
            self.input_port.setEnabled(False)
            print(f"[napari-mcp] Started on port {port}")
        else:
            self._set_status("Failed to start", listening=False)

    def _stop_server(self) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None
        self._executor = None
        self._listening = False
        self._set_status("Not listening", listening=False)
        self.button_toggle.setText("Start Listening")
        self.input_port.setEnabled(True)
        print("[napari-mcp] Stopped")

    def _toggle_listening(self) -> None:
        if self._listening:
            self._stop_server()
        else:
            self._start_server()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _set_status(self, text: str, *, listening: bool) -> None:
        self.label_status.setText(text)
        self.label_status.setStyleSheet(
            "color: green;" if listening else "color: red;"
        )

    def _close_widget(self) -> None:
        # The widget is docked inside napari; "Close" here means stop the
        # server and hide the dock. Users who want to keep listening but
        # hide the panel should just close the dock from napari's UI.
        self._stop_server()
        self.hide()

    # Make sure we release the port if napari tears the widget down.
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._stop_server()
        super().closeEvent(event)
