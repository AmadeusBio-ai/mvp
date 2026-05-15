---
name: napari
description: Use when operating a napari image viewer through the napari-mcp MCP server — i.e. anytime the user asks to "load an image", "add a layer", "take a screenshot", "switch to 3D", "segment cells", "navigate the timelapse", "run code in napari", or whenever any `mcp__napari-mcp__*` tool is in scope. Covers standalone mode (Claude owns the viewer) and plugin/bridge mode (Claude controls a running napari session).
---

# napari-mcp

This skill is for driving a napari viewer through the `mcp__napari-mcp__*` tool family. It tells you which tool to reach for, which invariants matter, and which gotchas bite if forgotten.

## 1. Mode check first

Always call `session_information` before assuming a viewer exists. Branch on `session_type`:

- **`napari_mcp_standalone_session`** with `viewer: null` → call `init_viewer` to create one. `init_viewer` and `close_viewer` are available; you own the viewer's lifecycle.
- **`napari_mcp_standalone_session`** with viewer info populated → a viewer already exists; proceed.
- **`napari_bridge_session`** → the user's running napari process owns the viewer. `init_viewer` and `close_viewer` are **NOT registered** in this mode (`bridge_server.py` removes them) — do not call them. Mutations are dispatched onto the Qt main thread.
- Call failed entirely → assume standalone, call `init_viewer`.

See [references/modes.md](references/modes.md) for the full comparison and the subtler proxy-fallthrough behavior in `auto-detect` mode.

## 2. Tool decision table

| Goal | Tool |
|---|---|
| See what's loaded (cheap) | `list_layers` |
| Detailed metadata for one layer, optionally with data/stats | `get_layer` |
| Load image/labels from disk | `add_layer(layer_type="image", path=...)` |
| Add layer from an array already in the exec namespace | `add_layer(layer_type=..., data_var="var")` |
| Add layer from inline data (small coordinates, shapes, etc.) | `add_layer(layer_type=..., data=[[...]])` |
| Tweak one layer's render props | `set_layer_properties` |
| Tweak many layers at once (by type or glob) | `apply_to_layers` |
| Reorder a layer in the stack | `reorder_layer(name, index=…)` / `before=…` / `after=…` |
| Camera, 2D ↔ 3D, slider position, grid | `configure_viewer` |
| Reset camera to fit | `configure_viewer(reset_view=True)` |
| Show user the canvas | `screenshot()` (canvas-only by default; ~150 KB auto-downsized) |
| Sweep an axis and grab frames | `screenshot(axis=, slice_range=)` |
| Run arbitrary Python in the napari namespace | `execute_code` |
| Missing dependency | `install_packages([...])` then `execute_code` |
| Output was truncated / large data deferred | `read_output(output_id)` |
| Persist a layer to disk | `save_layer_data(name, path)` |
| Remove a layer | `remove_layer(name)` |
| Stop the standalone viewer (standalone only) | `close_viewer` |
| Discover state of session/viewer | `session_information` |

Per-tool parameter and return shapes live in [references/tools.md](references/tools.md).

## 3. Non-obvious invariants

These are the parts that bite if forgotten — they are not obvious from the tool signatures alone.

### Persistent execution namespace
`execute_code` shares a **persistent** namespace across calls within one server lifetime. `viewer`, `napari`, and `np` are pre-bound by the server itself — do not re-import unless a previous call errored and corrupted state. Variables you create (`data = ...`, `arr = ...`) survive into the next `execute_code` call and into `add_layer(data_var="...")`.

### `add_layer` data source is XOR
Provide **exactly one** of `path` / `data` / `data_var`. Passing more than one returns an error. `path` only works for `image` and `labels`; for `surface` you must use `data_var` (surfaces are a tuple `(vertices, faces[, values])`, not JSON-friendly).

### Layer type aliases
`layer_type` accepts singular/plural aliases: `images→image`, `label→labels`, `point→points`, `shape→shapes`, `vector→vectors`, `track→tracks`, `surfaces→surface`. Canonical form is fine; "Image" with capital I is not.

### Screenshot byte budgets
- **Single inline `screenshot()`**: auto-downscales the PNG to stay under ~150 KB (≈200 KB base64). If you need exact pixels, pass `save_path=...` and read the file from disk instead.
- **Timelapse `screenshot(axis=, slice_range=)`**: with `interpolate_to_fit=True`, frames are downscaled so total base64 stays under **1,309,246 bytes** (≈1.3 MB). Without it, frames render at full resolution but the loop **stops early** once accumulated base64 would overshoot that cap — so you may get fewer frames than `slice_range` implies. To capture every frame at full resolution, use `save_dir=...`.

### Slice syntax (two different parsers)
- **`screenshot(slice_range=...)`** uses Python-slice syntax for a **single axis**: `"1:5"`, `":6"`, `"::2"`, `"-1"` (last frame), `"5"` (single index). `"1:2:3:4"` is invalid; `"::0"` raises "step cannot be 0".
- **`get_layer(slicing=...)`** uses **comma-separated** multi-axis slicing: `"0, :5, :5"` → `arr[0, :5, :5]`. Only ints, colons, and commas — no arbitrary expressions or steps validation here; same `:` rules per component.

### `output_id` and `read_output`
- `execute_code` default truncates stdout/stderr to **30 lines** and returns an `output_id`. Pass `line_limit=-1` for unbounded output, but only when you actually need it (it returns a warning and consumes tokens).
- `get_layer(include_data=True)` returning a numeric array larger than `max_elements` (default **1,000**, max **1,000,000**) stashes it and returns `output_id` instead of inlining — fetch with `read_output`. Look for the `"_large_data"` pattern: you'll see `"output_id"` and `"message"` instead of the data inline.
- `install_packages` truncates the same way.
- Output storage is FIFO-evicted at 1,000 items (env: `NAPARI_MCP_MAX_OUTPUT_ITEMS`).

### `install_packages` constraints
Package names are validated against a strict regex — **URL/VCS specifiers are rejected** (no `git+https://...`, no local paths). Use standard pip name + version specifiers. Default timeout is **240 s**.

### `configure_viewer` paired params and clamping
- `dims_axis` and `dims_value` **must be provided together** or omitted together.
- `ndisplay` must be `2` or `3`; `zoom` must be `> 0`.
- `dims_value` is silently **clamped** to `[0, nsteps-1]` and a `warning` is added to the response — check the response for `"warning"` after slider changes.

### Bridge vs standalone `execute_code` timeouts
- **Standalone**: runs synchronously on the asyncio thread (which shares with Qt via the event pump). **No timeout.** A hung script blocks subsequent tool calls.
- **Bridge**: dispatched onto the Qt main thread with a hard **600 s timeout**. On timeout, an `output_id` and an error message are returned, but the code may still be running inside napari — break long work into chunks.

### `auto-detect` mode proxy fallthrough
In auto-detect mode, a fixed subset of tools (`list_layers`, `add_layer` for image paths, `screenshot`, `execute_code`, `install_packages`, `session_information`, `init_viewer`) tries to proxy to a running bridge on `localhost:NAPARI_MCP_BRIDGE_PORT` (default `9999`). Other tools (`get_layer`, `set_layer_properties`, `reorder_layer`, `apply_to_layers`, `configure_viewer`, `save_layer_data`, `remove_layer`, `read_output`, `close_viewer`) do **not** proxy — they operate on the local viewer, which may not exist. Either install into the bridged napari directly or stick to the proxied tool list. Details in [references/modes.md](references/modes.md).

## 4. Recipes

End-to-end tool sequences in [references/recipes.md](references/recipes.md):

1. Load image → set colormap → screenshot.
2. Filter a layer via `execute_code` → add the result as a new layer.
3. Switch to 3D and rotate the camera.
4. Sweep a temporal axis and capture every frame.
5. Batch process many files (add → process → save).
6. Persist layer artifacts (image/labels → tiff/png; points/tracks/vectors → csv; anything → npy).

## 5. Helper scripts

Three drop-in helpers — paste their source into `execute_code`, then call the defined function. They assume the standard pre-bound `viewer`, `napari`, `np`.

- [`scripts/dump_session.py`](scripts/dump_session.py) — print every field `list_layers`/`session_information` skips (dtype, world bounds, scale, translate, full camera state). Use when you need detail those tools don't surface.
- [`scripts/apply_filter.py`](scripts/apply_filter.py) — `apply_filter(layer_name, kind, **kwargs)` for `kind ∈ {"gaussian", "median", "threshold_otsu", "label"}`. Adds the result as a new layer (Image for filters, Labels for threshold/label).
- [`scripts/screenshot_grid.py`](scripts/screenshot_grid.py) — `capture_grid(axis, indices, save_dir=None)` to step a dim and screenshot at each index. Bypasses the timelapse ~1.3 MB cap by saving to disk or returning a stitched numpy montage.

## 6. Links

Skill files:
- [references/tools.md](references/tools.md) — per-tool parameter/return reference.
- [references/recipes.md](references/recipes.md) — six end-to-end recipes.
- [references/modes.md](references/modes.md) — standalone vs bridge vs auto-detect.

Code-side references (read these when the skill is ambiguous):
- `src/napari_mcp/server.py` — every tool's authoritative signature and behavior.
- `src/napari_mcp/bridge_server.py` — bridge overrides for `session_information`, `add_layer`, `execute_code`; lifecycle-tool removal.
- `src/napari_mcp/_helpers.py` — `LAYER_TYPE_ALIASES`, `build_layer_detail`, `create_layer_on_viewer`, `run_code`, `build_truncated_response`.
- `src/napari_mcp/state.py` — `StartupMode`, `proxy_to_external`, output storage.
- `docs/examples/direct_mcp_client.py`, `docs/examples/anthropic_integration.py` — concrete call sequences.
- `tests/test_integration.py`, `tests/test_timelapse.py` — known-good multi-tool flows.
