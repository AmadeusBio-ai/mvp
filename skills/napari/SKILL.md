---
name: napari
description: Use when operating a napari image viewer via the napari-mcp plugin — i.e. whenever the user asks to "load an image", "add a layer", "take a screenshot", "switch to 3D", "segment cells", "navigate the timelapse", "run code in napari", or any task that needs the running napari window. The plugin listens on a TCP socket; this skill teaches how to launch it and what Python to send.
---

# napari

The `napari-mcp` plugin (installed into napari's Python env from `napari-mcp-plugin/` in this repo) gives an external client a single operation: **`execute` arbitrary Python against the live `napari.Viewer`**. Everything else — loading images, sweeping sliders, taking screenshots — is just napari's Python API sent over the socket. This skill tells you how to launch the viewer, how to call the socket, and which Python idioms to reach for.

## 1. Launch & connect

The plugin is auto-started by opening its dock widget. Run this **same command on Linux, macOS, and Windows** — no platform branching:

```bash
napari -w napari-mcp 'MCP Server'
```

Widget name and plugin id are fixed by `napari-mcp-plugin/src/napari_mcp/napari.yaml` (`name: napari-mcp`, `display_name: MCP Server`). The widget calls `_start_server()` on construction, so launching this way drops you straight into a listening state on port **9877** (`_widget.py:36` `DEFAULT_PORT = 9877` — note: the upstream README still says 9876, it's stale; trust the widget).

Use the launcher script — it's idempotent and cross-platform:

```bash
python skills/napari/scripts/launch_napari.py
```

- If port 9877 is already open, exits 0 immediately.
- Otherwise spawns the launch command detached from this process and polls until the port responds (≤30 s).
- Exit 1 if the port never comes up; exit 2 if the `napari` binary isn't on PATH.

If napari fails to start, check `napari --info` and confirm `napari-mcp` appears under Plugins. If it doesn't, the plugin isn't installed into napari's env — follow the env-aware install in the project README (`<napari-env-pip> install -e ./napari-mcp-plugin`) and retry.

## 2. The one operation

Send a single JSON request, get a single JSON response:

```text
request   {"type": "execute", "code": "<python>"}
success   {"status": "success", "result": {"executed": true,  "output": "<str>"}}
user err  {"status": "success", "result": {"executed": false, "error":  "<str>"}}
srv err   {"status": "error",   "message": "<str>"}
```

Call it via the helper (handles framing, exit codes, error reporting):

```bash
python skills/napari/scripts/napari_client.py "viewer.add_image(np.random.rand(256,256), name='r')"
python skills/napari/scripts/napari_client.py --file path/to/snippet.py
cat snippet.py | python skills/napari/scripts/napari_client.py --stdin
```

Exit codes: `0` success+executed, `3` success-but-user-code-raised, `4` server error, `5` connection refused. **Always check the exit code or parse the JSON — `status: success` with `executed: false` is a user-code error, not a success.**

Full protocol reference: [references/protocol.md](references/protocol.md).

## 3. Code-author conventions

Inside the `code` you send, three names are pre-bound (`_executor.py:33-37`):

| Name | What it is |
|---|---|
| `viewer` | the live `napari.Viewer` |
| `napari` | the napari module |
| `np` | numpy |

To return a value back across the socket, either:

- **Print** it (`print(json.dumps(payload))`) — stdout is captured and returned as `output`.
- **Set `_result`** (`_result = expr`) — `str(_result)` is returned as `output`.

**stdout wins** if both are set (`_executor.py:50-56`). For structured data, `print(json.dumps(...))` on the server side + `json.loads(response["result"]["output"])` on the client side is the clean pattern.

## 4. Decision table — goal → Python idiom

| Goal | Code to send |
|---|---|
| List layers | `_result = [l.name for l in viewer.layers]` |
| Load from disk (autodetect) | `viewer.open('/path/to/file')` |
| Add image array | `viewer.add_image(arr, name='x', colormap='viridis')` |
| Add labels | `viewer.add_labels(mask.astype(np.int32), name='seg')` |
| Tweak render props | `l = viewer.layers['x']; l.contrast_limits = [0, 4096]; l.colormap = 'magma'` |
| Remove layer | `del viewer.layers['x']` |
| Reorder | `viewer.layers.move(viewer.layers.index(viewer.layers['x']), 0)` |
| Switch to 3D | `viewer.dims.ndisplay = 3` |
| Reset camera | `viewer.reset_view()` |
| Rotate camera | `viewer.camera.angles = (30, 45, 0); viewer.camera.zoom = 1.5` |
| Step slider | `viewer.dims.set_current_step(0, 10)` |
| Grid mode | `viewer.grid.enabled = True; viewer.grid.shape = (-1, 3)` |
| Screenshot | `viewer.screenshot(path='/tmp/x.png', canvas_only=True)` — then `Read /tmp/x.png` |
| Apply filter | `from scipy.ndimage import gaussian_filter; viewer.add_image(gaussian_filter(np.asarray(viewer.layers['x'].data), 2), name='x_blur')` |
| Save layer | `import tifffile; tifffile.imwrite('/out/seg.tif', np.asarray(viewer.layers['seg'].data))` |
| Inspect everything | paste `scripts/dump_session.py` and end with `_result = dump_session()` |

Full API surface: [references/api.md](references/api.md). End-to-end pipelines: [references/recipes.md](references/recipes.md).

## 5. Invariants (the things that bite)

### Fresh exec namespace per call
`_executor.py:33` builds a new `exec_globals` dict every time. **Variables do NOT persist across calls.** A two-call sequence like

```bash
napari_client.py "arr = np.random.rand(256,256)"
napari_client.py "viewer.add_image(arr)"     # NameError: arr
```

fails on the second call. Pack multi-step pipelines into one `code` blob, or rebuild state by reading from `viewer.layers` at the start of each call (the viewer itself persists — only your local Python state doesn't).

### User-code errors come back as `executed: false`, not `status: error`
`status: error` means the *transport* rejected the request (empty code, no callback). A Python exception in your code returns `{"status": "success", "result": {"executed": false, "error": "..."}}`. Branch on `result.executed`, not just `status`.

### One client at a time
The server accepts a single connection at a time (`_socket_server.py:75`). Don't fan out parallel `napari_client.py` calls — they'll queue at the OS level and you may get connection refusals mid-flight. Issue calls serially.

### 300 s Qt-thread timeout
Long-running code hits a hard 300 s cap (`_executor.py:89`). Break heavy pipelines into chunks; results landing on `viewer.layers` survive across calls.

### No inline screenshot transport
Unlike the old plugin there is no base64 PNG response. Always `viewer.screenshot(path='/tmp/x.png', ...)` and then `Read /tmp/x.png` from the Claude side — Claude is multimodal and renders the PNG inline.

### Imports don't carry over
Because the namespace is fresh, `from scipy.ndimage import gaussian_filter` must appear inside every `code` blob that uses it. Don't write recipes that assume earlier imports survived.

## 6. Recipes

Six end-to-end pipelines in [references/recipes.md](references/recipes.md), each as a single `code` blob to send via `napari_client.py --file`: load → colormap → screenshot; filter via scipy → add as new Labels; switch to 3D + rotate; sweep an axis and save frames to disk; batch process many files; persist layer artifacts.

## 7. Helper scripts

Drop-in modules to paste via `napari_client.py --file`. Each defines a function and ends with `_result = the_function(...)` so its return value comes back as `output`.

- [`scripts/launch_napari.py`](scripts/launch_napari.py) — idempotent launcher (not for `--file`, run directly with `python`).
- [`scripts/napari_client.py`](scripts/napari_client.py) — the client itself (not for `--file`).
- [`scripts/dump_session.py`](scripts/dump_session.py) — exhaustive `dump_session()` covering every layer/viewer field that the one-liner table skips (world bounds, scale, translate, full camera state).
- [`scripts/apply_filter.py`](scripts/apply_filter.py) — `apply_filter(layer_name, kind, **kwargs)` for `kind ∈ {"gaussian", "median", "threshold_otsu", "label"}`. Adds the result as a new layer.
- [`scripts/screenshot_grid.py`](scripts/screenshot_grid.py) — `capture_grid(axis, indices, save_dir=...)` to step a dim and screenshot each index. Disk mode is the recommended default (no inline transport anyway).

## 8. Links

Skill files:
- [references/protocol.md](references/protocol.md) — wire protocol, response shapes, framing rules.
- [references/api.md](references/api.md) — napari Python API cheatsheet.
- [references/recipes.md](references/recipes.md) — six end-to-end pipelines as code blobs.

Plugin source (read-only, for verification):
- `napari-mcp-plugin/src/napari_mcp/_socket_server.py` — TCP server, JSON framing.
- `napari-mcp-plugin/src/napari_mcp/_executor.py` — Qt-thread executor, exec namespace, `_result`/stdout precedence.
- `napari-mcp-plugin/src/napari_mcp/_widget.py` — dock widget, port (`DEFAULT_PORT = 9877`), auto-start.
- `napari-mcp-plugin/test_client.py` — canonical framing-loop reference for any client.

napari documentation: <https://napari.org/dev/api/index.html>.
