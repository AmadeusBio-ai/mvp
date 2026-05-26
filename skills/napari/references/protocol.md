# napari-mcp plugin wire protocol

Source of truth: `/home/yangyi/Code/napari-mcp-plugin/src/napari_mcp/_socket_server.py` and `_executor.py`. Read those if anything here is ambiguous.

## Transport

- **Raw TCP** on `localhost:9877` (default). Not HTTP, not WebSocket, not MCP/JSON-RPC.
- **UTF-8 JSON** payloads, **no length prefix**. The server reads bytes and retries `json.loads` until parsing succeeds, then dispatches.
- **One client at a time.** The server `accept()`s a single connection, serves it (multiple commands on the same socket are fine), closes, then loops back to accept the next. Parallel clients queue at the OS level.
- **No auth.** Server binds `localhost` only — don't expose port 9877 to untrusted networks.

## Request

The only valid request shape:

```json
{"type": "execute", "code": "<python>"}
```

Any other shape, or an empty `code`, returns a server error.

## Response

Three possible response shapes:

### Success (user code ran without raising)

```json
{"status": "success", "result": {"executed": true, "output": "<str>"}}
```

`output` is either:
- whatever the code printed to stdout (captured via `redirect_stdout`), **if non-empty**, **or**
- `str(_result)` if the code assigned a `_result` variable, **or**
- `"Command executed successfully (no output)"` otherwise.

**stdout wins.** If your code both prints and sets `_result`, only the stdout reaches you (see `_executor.py:50-56`).

### User-code error (server accepted, exec raised)

```json
{"status": "success", "result": {"executed": false, "error": "<traceback summary>"}}
```

Note this is still `status: "success"` at the transport level — the exec error lives inside `result`. `napari_client.py` exits with code 3 in this case to make it easy to detect from a shell.

### Server error (malformed request or internal failure)

```json
{"status": "error", "message": "<str>"}
```

Examples: empty request, missing `code`, no command callback registered.

## Execution semantics

From `_executor.py:22-57`:

- **Pre-bound names**: `viewer` (live `napari.Viewer`), `napari` (module), `np` (numpy). `__builtins__` is in scope.
- **Fresh exec namespace per call.** Every call constructs a new `exec_globals` dict. Variables you create do **not** persist into the next call. Pack multi-step pipelines into a single `code` string, or rebuild state by reading from `viewer.layers` at the start of each call.
- **Runs on the Qt main thread.** The socket worker thread emits a Qt signal and blocks on a `threading.Event` until the GUI thread finishes. This is what makes calls like `viewer.add_image` safe.
- **300-second timeout.** A call that runs longer returns `{"executed": false, "error": "GUI thread execution timed out"}`. Break long work into smaller chunks; intermediate results live on `viewer.layers` and survive across calls.

## Practical implications for the client

- **Returning data**: print it, or set `_result = <expr>`. `output` is always a string; deserialize on the client if you need structure (e.g., `json.dumps(...)` on the server side, `json.loads(output)` on the client).
- **Errors**: branch on `response["status"] == "success"` first, then on `response["result"]["executed"]`. Don't conflate the two.
- **Large outputs**: there is no `output_id` / `read_output` mechanism. Stdout is returned in full and crosses the socket as a single JSON blob — be reasonable with print volume. For arrays, save to disk via `np.save` / `viewer.screenshot(path=...)` and pass the path back as `_result`.
- **Screenshots**: there is no inline image transport. Always use `viewer.screenshot(path="/tmp/x.png", canvas_only=True)` and read the PNG from disk on the client side.
- **Multi-command sessions**: keeping a single socket open for many commands works (the server loops back after responding), but `napari_client.py` opens a fresh socket per call. The per-call overhead is negligible; one-call-per-connection is simpler and matches the upstream `test_client.py`.
