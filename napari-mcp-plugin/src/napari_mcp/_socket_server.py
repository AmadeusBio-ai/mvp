"""Threaded TCP socket server that accepts JSON commands.

Direct port of the PyMOL plugin's SocketServer with the same wire protocol:

    request  (JSON, UTF-8):  {"type": "...", "code": "<python>"}
    response (JSON, UTF-8):  {"status": "success", "result": <obj>}
                          or {"status": "error",   "message": "..."}

The server runs in a daemon thread. The command callback is invoked from
that worker thread; callers that need to touch GUI objects must marshal
back to the GUI thread themselves (see _widget.MCPServerWidget).
"""

from __future__ import annotations

import json
import socket
import threading
import traceback
from typing import Any, Callable, Optional


CommandCallback = Callable[[str], Any]


class SocketServer:
    def __init__(self, host: str = "localhost", port: int = 9876) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.client: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.command_callback: Optional[CommandCallback] = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self, command_callback: Optional[CommandCallback] = None) -> bool:
        if self.running:
            return False

        self.command_callback = command_callback
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(2.0)
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None
        self.client = None
        self.thread = None

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _run_server(self) -> None:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.socket.settimeout(1.0)

            print(f"[napari-mcp] Socket server listening on {self.host}:{self.port}")

            while self.running:
                try:
                    self.client, address = self.socket.accept()
                    print(f"[napari-mcp] Connected to client: {address}")
                    self.client.settimeout(1.0)
                    self._serve_client(self.client)
                    if self.client:
                        try:
                            self.client.close()
                        except Exception:
                            pass
                        self.client = None
                except socket.timeout:
                    continue
                except OSError:
                    # Socket was closed from another thread (during stop())
                    break
                except Exception as e:  # pragma: no cover - defensive
                    print(f"[napari-mcp] Error accepting connection: {e}")
        except Exception as e:  # pragma: no cover - defensive
            print(f"[napari-mcp] Socket server error: {e}")
            traceback.print_exc()
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
            self.running = False
            print("[napari-mcp] Socket server stopped")

    def _serve_client(self, client: socket.socket) -> None:
        buffer = b""
        while self.running:
            try:
                data = client.recv(4096)
                if not data:
                    break
                buffer += data

                # Try to parse what we have so far. If it isn't complete JSON
                # yet, keep reading. This matches the PyMOL plugin's behaviour.
                try:
                    command = json.loads(buffer.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                buffer = b""
                response = self._handle_command(command)
                client.sendall(json.dumps(response).encode("utf-8"))
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[napari-mcp] Error receiving data: {e}")
                break

    def _handle_command(self, command: dict) -> dict:
        if not command:
            return {"status": "error", "message": "empty command"}

        code = command.get("code", "")
        if not code:
            return {"status": "error", "message": "no code in request"}

        if self.command_callback is None:
            return {"status": "error", "message": "no command callback registered"}

        try:
            result = self.command_callback(code)
            return {
                "status": "success",
                "result": result if result is not None else "Command executed",
            }
        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "message": str(e)}
