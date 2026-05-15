# Standalone vs bridge vs auto-detect

`napari-mcp` runs in three configurations. The tool surface is mostly the same, but a few tools are removed, overridden, or behave differently. Always identify the mode from `session_information` before assuming any tool is available.

---

## Detection

Call `session_information` and read `session_type`:

| `session_type` | Mode |
|---|---|
| `napari_mcp_standalone_session` | Standalone — server owns the viewer. |
| `napari_bridge_session` | Bridge — the napari plugin hosts the server inside a running napari process. |

Auto-detect mode is a flavor of **standalone** that has been told to look for a bridge on `localhost:9999` (configurable via `NAPARI_MCP_BRIDGE_PORT` or `--port`). When no bridge is running, it behaves identically to standalone.

---

## Standalone mode

- Started by: `napari-mcp` (or `python -m napari_mcp.server`).
- Lifecycle: the server creates the napari `Viewer` on first `init_viewer` (or on first tool that calls `ensure_viewer`).
- Tool surface: **all 16 tools** including `init_viewer` and `close_viewer`.
- `execute_code`: synchronous on the asyncio thread (which shares with Qt via the event pump). **No timeout** — a hung script blocks subsequent tool calls.
- `session_information` shape: full — includes `system`, `session`, per-layer `layer_id`, plus `viewer.current_step`.
- Use when: Claude is the only operator, no human has napari open, scripts and notebooks.

---

## Bridge mode

- Started from inside napari: Plugins → "napari-mcp: MCP Server Control" widget → Start Server.
- Lifecycle: the napari user owns the viewer; the bridge exposes it over MCP on `127.0.0.1:9999` (no auth — anything on the box can call).
- **`init_viewer` and `close_viewer` are not registered.** The bridge explicitly removes them. Calling them is an error.
- The 3 tools that are bridge-overridden:
  - `session_information` — leaner shape (no `system`/`session`, no `layer_id`); adds `bridge_port`.
  - `add_layer` — same parameters; runs on the Qt main thread via `QtBridge.run_in_main_thread`.
  - `execute_code` — same parameters; **600 s hard timeout**. On timeout you get an `output_id` and an error message, but the code may still be executing inside napari.
- All other tools route through `state.gui_execute`, which the bridge has wired to `QtBridge.run_in_main_thread` as well — so they're thread-safe even though they're not separately overridden.
- Use when: a human has napari open and you need to drive it without interrupting their session.

---

## Auto-detect mode (standalone variant)

- Started by: `napari-mcp run --auto-detect [--port 9999]`.
- Lifecycle: standalone — but **only seven tools** try to forward to a running bridge first (`proxy_to_external`):
  - `init_viewer`, `session_information` (forwarded via `external_session_information`).
  - `list_layers`, `add_layer` (only when `path` is set and `layer_type=image`), `screenshot`, `execute_code`, `install_packages`.
- Tools that **do NOT proxy** (they always operate on the local viewer): `get_layer`, `set_layer_properties`, `remove_layer`, `reorder_layer`, `apply_to_layers`, `configure_viewer`, `save_layer_data`, `read_output`, `close_viewer`. If you call one of these expecting it to hit the bridge, it will instead create or use a separate local viewer — almost certainly not what you want.
- The proxy is **best-effort**: if the bridge isn't reachable, `proxy_to_external` returns `None` and the call falls through to local execution.

**Practical implication:** auto-detect is fine for read-mostly workflows (`session_information`, `list_layers`, `screenshot`) and for setting up data via `add_layer`/`execute_code`. For property tweaks (`set_layer_properties`, `configure_viewer`) you should run the server **inside** napari (bridge mode) to avoid the local-fallthrough trap.

---

## Choosing tools that work in all modes

The tools in this list behave identically (or proxied) across all three modes — prefer them when you're not sure which mode you're in:

- `session_information`, `list_layers`, `screenshot`, `add_layer`, `execute_code`, `install_packages`, `read_output`.

Tools to **avoid until you've confirmed standalone or bridge mode**:

- `init_viewer`, `close_viewer` — error in bridge mode.
- `get_layer`, `set_layer_properties`, `remove_layer`, `reorder_layer`, `apply_to_layers`, `configure_viewer`, `save_layer_data` — silently hit the wrong viewer in auto-detect mode if the bridge is up.
