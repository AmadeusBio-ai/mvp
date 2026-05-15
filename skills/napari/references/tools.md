# napari-mcp tool reference

One section per tool. Sources of truth: `src/napari_mcp/server.py` (signatures, behavior) and `src/napari_mcp/_helpers.py` (alias map, layer construction, response truncation).

A tool is **bridge-overridden** when `bridge_server.py` registers a different implementation that dispatches onto the Qt main thread. Bridge-overridden tools have minor schema differences noted below; non-overridden tools are identical in both modes.

---

## `session_information()`

Discover the current session and viewer state. **Always call this first** in a new session.

**Returns** (standalone, viewer present):
```
{
  "status": "ok",
  "session_type": "napari_mcp_standalone_session",
  "timestamp": "<ISO>",
  "viewer": { "title", "viewer_id", "n_layers", "layer_names", "selected_layers",
              "current_step", "ndisplay", "camera_center", "camera_zoom",
              "camera_angles", "grid_enabled" },
  "system": { "python_version", "platform", "napari_version", "process_id",
              "working_directory" },
  "session": { "server_type", "viewer_instance", "gui_pump_running",
               "execution_namespace_vars", "qt_app_available" },
  "layers": [ {build_layer_detail + "layer_id"}, ... ]
}
```

**Returns** (standalone, no viewer): same wrapper but `"viewer": null` and a `"message"` telling you to call `init_viewer`.

**Returns** (bridge): leaner shape — `session_type: "napari_bridge_session"`, only `viewer` (no `current_step`), `layers`, and `bridge_port`. No `system`/`session` blocks.

**Per-layer detail** (`build_layer_detail`): `name`, `type` (e.g., `"Image"`, `"Labels"`), `visible`, `opacity`, plus when applicable `data_shape`, `data_dtype`, `colormap`, `blending`, `contrast_limits`, `gamma`. Standalone mode adds `layer_id` (Python `id()` — useful for disambiguating renamed layers).

**Bridge-overridden:** yes (different shape).

---

## `init_viewer(title?, width?, height?, port?, detect_only=False)`

Create or return the napari viewer.

**Parameters:**
- `title`, `width`, `height` — only used when creating a new local viewer.
- `port` — overrides bridge port for auto-detect mode (default from `NAPARI_MCP_BRIDGE_PORT` or `9999`).
- `detect_only=True` — does not create or modify; reports both local and external viewer availability under `viewers.local` / `viewers.external`.

**Returns** (`detect_only=False`): `{ "status": "ok", "viewer_type": "local"|"external", "title", "layers": [...] }`.

**Returns** (`detect_only=True`): `{ "status": "ok", "viewers": {"local": {...}, "external": {...}} }`.

**Bridge-overridden:** the tool is **removed** in bridge mode (the viewer is owned by napari). Do not call.

---

## `close_viewer()`

Close the standalone viewer and clear all layers. **Removed in bridge mode.**

**Returns:** `{"status": "closed"}` or `{"status": "no_viewer"}` or `{"status": "error", ...}`.

Triggers server shutdown after a short delay (lets in-flight responses flush).

---

## `list_layers()`

Cheap layer roster. **Always call before other layer operations** to confirm the layer name spelling.

**Returns:** `list[dict]` — each dict from `build_layer_detail` (see `session_information`).

**Bridge-overridden:** no (proxies through `state.gui_execute`).

---

## `get_layer(name, include_data=False, slicing=None, max_elements=1000)`

Detailed metadata for one layer; optionally returns data and/or stats.

**Parameters:**
- `name` — exact layer name; returns `{"status": "not_found", ...}` on miss.
- `include_data=True` — include statistics (`min`, `max`, `mean`, `std`) and inline data when small.
- `slicing` — numpy-style multi-axis string (`"0, :5, :5"`); implies `include_data=True`. Only ints, colons, and commas are allowed.
- `max_elements` — cap for inline data (default `1000`, max `1_000_000`). Larger arrays are stashed → `output_id`.

**Always-returned metadata:** `name`, `type`, `visible`, `opacity`, `blending`, `ndim`, plus when present `data_shape`, `data_dtype`, `scale`, `translate`. Type-specific: `colormap`/`contrast_limits`/`gamma`/`interpolation2d` (Image); `n_labels`/`selected_label` (Labels); `n_points`/`point_size`/`symbol` (Points); `nshapes`/`shape_type`/`edge_width` (Shapes); `n_vectors`/`edge_width` (Vectors); `n_tracks` (Tracks); `n_vertices`/`n_faces` (Surface).

**Data-mode additions:** `statistics` for numeric arrays; `coordinates` (Points), `shapes` (Shapes), `vertices`+`faces` (Surface), `data` (Vectors/Tracks/Image/Labels), `slice_shape` (when `slicing`).

**Large-data response:** when the array exceeds `max_elements`, the inline data fields are **omitted** and you instead get:
```
{ ..., "output_id": "<id>", "message": "<label> too large for inline response (>N elements). Use read_output('<id>') to retrieve." }
```

**Bridge-overridden:** no.

---

## `add_layer(layer_type, path?, data?, data_var?, name?, ...)`

Add a new layer. **Provide exactly one of `path` / `data` / `data_var`.**

**Required:**
- `layer_type` — one of `image`, `labels`, `points`, `shapes`, `vectors`, `tracks`, `surface`. Aliases (singular/plural) accepted via `LAYER_TYPE_ALIASES`.

**Per layer-type kwargs** (from `create_layer_on_viewer`):

| Type | `path` ok? | Required | Optional kwargs |
|---|---|---|---|
| `image` | yes | data source | `colormap`, `blending`, `channel_axis` |
| `labels` | yes | data source | (none) |
| `points` | no | data source | `size` (default 10) |
| `shapes` | no | data source | `shape_type` (default `"rectangle"`), `edge_color`, `face_color`, `edge_width` |
| `vectors` | no | data source | `edge_color`, `edge_width` |
| `tracks` | no | data source | (none) |
| `surface` | no | **`data_var` only** (data is a `(vertices, faces[, values])` tuple) | (none) |

**Image-specific guards:** rejects empty arrays and complex dtypes with a clear error message ("Convert to real first (e.g., np.abs(data))").

**Returns:** `{"status": "ok", "name": "<resolved name>", "shape": [...]}` for image/labels; `{"status": "ok", "name", "n_points"|"nshapes"|"n_vectors"|"n_tracks"|"n_vertices"+"n_faces"}` for the others. Image with `channel_axis` returns `name` as a list and adds `n_channels`.

**Bridge-overridden:** yes — bridge variant is functionally identical but lives on the Qt thread; same parameter shape.

---

## `remove_layer(name)`

Remove a layer by name.

**Returns:** `{"status": "removed", "name": ...}` or `{"status": "not_found", ...}`.

**Bridge-overridden:** no.

---

## `set_layer_properties(name, visible?, opacity?, colormap?, blending?, contrast_limits?, gamma?, new_name?, active?)`

Set rendering properties on a single layer.

**Validation:** `opacity` must be `[0.0, 1.0]`; `gamma` must be `> 0`; `contrast_limits` must be a 2-element list; invalid `colormap`/`blending` strings return a structured error. `active=True` selects the layer; `active=False` is a no-op (use viewer selection directly to deselect).

**Returns:** `{"status": "ok", "name": "<final name>"}` (the name reflects `new_name` if rename succeeded).

**Bridge-overridden:** no.

---

## `reorder_layer(name, index?, before?, after?)`

Move a layer in the stack. **Provide exactly one** of `index`/`before`/`after`.

- `index` — absolute position; clamped to `[0, len(layers)-1]`.
- `before` / `after` — name of an anchor layer.

**Returns:** `{"status": "ok", "name": ..., "index": <new index>}`.

**Bridge-overridden:** no.

---

## `apply_to_layers(filter_type?, filter_pattern?, properties)`

Bulk property changes across matching layers.

**Filters** (combined with AND):
- `filter_type` — class name match (`"Image"`, `"Labels"`, `"Points"`, `"Shapes"`, `"Vectors"`, `"Tracks"`, `"Surface"`).
- `filter_pattern` — `fnmatch` glob over layer names (e.g., `"seg_*"`).

**Recognized property keys:** `visible`, `opacity`, `colormap`, `blending`, `contrast_limits`, `gamma`. **Renaming is not supported here** — use `set_layer_properties` for that. Unknown keys are ignored and reported in the response.

**Returns:** `{"status": "ok", "matched": [names], "count": N, "unknown_properties": [...]?, "message": ...?}`.

**Bridge-overridden:** no.

---

## `configure_viewer(reset_view=False, center?, zoom?, angles?, ndisplay?, dims_axis?, dims_value?, grid?)`

One-shot viewer configuration: camera, dimensionality, slider, grid.

**Validation:**
- `zoom > 0`.
- `ndisplay ∈ {2, 3}`.
- `dims_axis` and `dims_value` **must be provided together** (XOR is an error).
- `dims_axis` must be in `[0, viewer.dims.ndim)`.
- `dims_value` is silently **clamped** to `[0, nsteps[axis]-1]`; a `"warning"` is added to the response when clamping occurs.

**Returns:** `{"status": "ok", "center": [...], "zoom": ..., "angles": [...], "ndisplay"?, "axis"?, "value"?, "warning"?, "grid"?}`.

**Camera angles** are `[azimuth, elevation, roll]` in degrees.

**Bridge-overridden:** no.

---

## `screenshot(canvas_only=True, save_path?, axis?, slice_range?, interpolate_to_fit=False, save_dir?)`

Single screenshot or sweep over an axis.

### Single mode (no `axis` and no `slice_range`)

- Default returns an `ImageContent` (PNG) inline. Auto-downscaled to keep the encoded PNG under ~150 KB.
- `save_path` set → saves PNG to disk; returns `{"status": "ok", "path", "size": [w, h]}`.
- `canvas_only=False` includes the napari window chrome.

### Timelapse mode (both `axis` and `slice_range` set)

- `slice_range` syntax (Python-slice for one axis): `"1:5"`, `":6"`, `"::2"`, `"-1"`, `"5"`. Step `0` → error; more than three colons → error.
- `interpolate_to_fit=True` — frames are downscaled so total base64 stays under **1,309,246 bytes** (~1.3 MB). All frames are returned but at lower resolution.
- `interpolate_to_fit=False` (default) — frames are full resolution but the loop **stops early** if the next frame would push total base64 over 1.3 MB. Expect fewer frames than requested for large sweeps.
- `save_dir` set → frames are saved as `frame_NNNN.png` in that directory; returns `{"status": "ok", "paths": [...], "n_frames": N}` (no inline images, no byte cap).

### Errors

- Only one of `axis`/`slice_range` set → `{"status": "error", "message": "Both 'axis' and 'slice_range' are required for timelapse."}`.
- Invalid slice → `{"status": "error", "message": "Invalid slice range: ..."}`.

**Bridge-overridden:** no — but in auto-detect mode the call is forwarded to the bridge.

---

## `execute_code(code, line_limit=30)`

Run arbitrary Python in the persistent server namespace.

**Pre-bound names:** `viewer`, `napari`, `np`. The namespace is shared across calls — variables you create persist for subsequent `execute_code` and for `add_layer(data_var=...)`.

**Last-expression handling:** if `code` ends in an expression, its value's `repr()` is captured as `result_repr`. (Same trick napari's console uses.)

**Output:** stdout/stderr always stored fully under `output_id`. Response includes the first `line_limit` lines (default `30`); pass `line_limit=-1` for unlimited (sets a `warning`).

**Returns** (success): `{"status": "ok", "output_id", "result_repr"?, "stdout", "stderr", "truncated"?, "message"?}`.

**Returns** (error): same shape with `"status": "error"`; `stderr` includes the traceback. A `TypeError: ...` summary line is appended if not already visible after truncation.

**Timeouts:**
- **Standalone:** none. A hung script blocks subsequent tool calls.
- **Bridge:** **600 s** hard cap. On timeout you get an error with `output_id`, but the code may still be running on the napari main thread. Break long work into chunks.

**Bridge-overridden:** yes (Qt main-thread dispatch + 600 s timeout).

---

## `install_packages(packages, upgrade=False, no_deps=False, index_url?, extra_index_url?, pre=False, line_limit=30, timeout=240)`

Install packages with pip in the server's environment.

**Validation:** every entry of `packages` is matched against `_PKG_NAME_RE`. **URL/VCS specifiers are rejected** (no `git+https://...`, no local paths). Standard pip name + version markers are fine: `"numpy>=1.20"`, `"torch==2.3.1"`, `"scikit-image[optional]"`.

**Returns:** `{"status": "ok"|"error", "output_id", "stdout", "stderr", "returncode", "command", "truncated"?, "message"?}`.

**Default timeout:** 240 s. On timeout, `stderr` notes the timeout and the process is killed.

**Bridge-overridden:** no — but proxied in auto-detect mode.

---

## `save_layer_data(name, path, format?)`

Save a layer's data to disk.

**Format inference:** from `path` extension unless `format` is set explicitly.

**Supported extensions:** `npy`, `csv`, `tiff`, `tif`, `png`, `jpg`, `jpeg`.

**Type/format compatibility:**
- `csv` → only Points / Tracks / Vectors. Header for Points: `axis-0,axis-1,...`; for Tracks: `track_id,axis-0,...`; for Vectors: `col-0,col-1,...`.
- `tiff` / `tif` / `png` / `jpg` / `jpeg` → only Image / Labels.
- `npy` → any layer type (fallback for non-image when extension is unrecognized).

**Returns:** `{"status": "ok", "path", "format", "size_bytes"}`.

**Bridge-overridden:** no.

---

## `read_output(output_id, start=0, end=-1)`

Read back a stored output (from `execute_code`, `install_packages`, or `get_layer` large-data deferral).

**Combined output:** stdout and stderr are concatenated (with a separator newline if needed). `start`/`end` are line indices into that combined text. `end=-1` means "to the end".

**Returns:** `{"status": "ok", "output_id", "tool_name", "timestamp", "lines": [...], "line_range": {start, end}, "total_lines", "result_repr"?}`.

**Eviction:** outputs are FIFO-evicted when the store exceeds `NAPARI_MCP_MAX_OUTPUT_ITEMS` (default `1000`).

**Bridge-overridden:** no.
