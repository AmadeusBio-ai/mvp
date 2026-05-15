# napari-mcp recipes

End-to-end tool sequences. Each recipe lists the tool calls in order and the expected response shape. Adapt names, paths, and parameters to your task.

---

## 1. Load → set colormap → screenshot

```text
session_information               → confirm session_type
init_viewer                       → only if standalone and no viewer
add_layer(layer_type="image", path="/path/to/img.tif")
                                  → {"status":"ok","name":"img","shape":[...]}
set_layer_properties(name="img", colormap="viridis",
                     contrast_limits=[0, 4096])
                                  → {"status":"ok","name":"img"}
configure_viewer(reset_view=True) → fit camera to data
screenshot()                      → ImageContent (PNG, ≤150 KB)
```

(Same shape as `docs/examples/direct_mcp_client.py`, but using `add_layer` for path loading instead of `execute_code`.)

---

## 2. Filter via `execute_code` → add as new Labels layer

The `execute_code` namespace persists, so you can compute an array, then reference it from `add_layer(data_var=...)`. (Mirrors the multi-step pattern in `tests/test_integration.py::test_execute_code_adds_layer_visible_via_tools`.)

```text
add_layer(layer_type="image", path="/path/to/cells.tif")
                                  → name="cells"
execute_code("""
from skimage.filters import threshold_otsu
from skimage.measure import label
img = viewer.layers['cells'].data
mask = img > threshold_otsu(img)
seg = label(mask)
""")                              → {"status":"ok",...}
add_layer(layer_type="labels", data_var="seg", name="cells_seg")
                                  → {"status":"ok","name":"cells_seg",...}
```

If `skimage` is missing → `install_packages(["scikit-image"])` first.

For a more structured version, paste `scripts/apply_filter.py` and call `apply_filter("cells", "threshold_otsu")`.

---

## 3. Switch to 3D and rotate the camera

```text
configure_viewer(ndisplay=3)              → {"status":"ok","ndisplay":3,...}
configure_viewer(angles=[30, 45, 0],
                 zoom=1.5)                → camera oriented
screenshot()                              → 3D view PNG
```

`angles` is `[azimuth, elevation, roll]` in degrees. `reset_view=True` is useful before rotating to recenter.

---

## 4. Sweep a temporal axis and capture every frame

A `(T, Y, X)` image lays out time on `axis=0`. (Mirrors `tests/test_timelapse.py::test_timelapse_screenshot_basic`.)

```text
add_layer(layer_type="image", data_var="movie")
                                  → name="movie", shape=[T, Y, X]
screenshot(axis=0, slice_range=":")
                                  → list[ImageContent], one per frame
```

Variants:
- Sub-range: `slice_range="0:10"`, `slice_range="::2"`, `slice_range="-5:"`.
- Single frame: `slice_range="-1"` (last) or `"5"`.
- **Many frames at full resolution:** `screenshot(axis=0, slice_range=":", save_dir="/tmp/frames")` → no inline images, no 1.3 MB cap; returns `{"paths": [...], "n_frames": N}`.
- **Many frames inline (downscaled to fit):** `screenshot(axis=0, slice_range=":", interpolate_to_fit=True)` → all frames at lower resolution, total base64 ≤ 1.3 MB.
- **Default inline (full resolution, may truncate):** the loop stops early once base64 would overshoot 1.3 MB. Don't trust frame count = slice length.

For grids and arbitrary index lists, paste `scripts/screenshot_grid.py`.

---

## 5. Batch process many files

```text
for path in paths:
    add_layer(layer_type="image", path=path)   → name = filename stem
    execute_code(f"""
from skimage.filters import gaussian
img = viewer.layers[{name!r}].data
viewer.add_image(gaussian(img, sigma=2),
                 name={name!r} + '_smooth')
""")
    save_layer_data(name + "_smooth",
                    f"/out/{name}_smooth.tif")
    remove_layer(name)
    remove_layer(name + "_smooth")
```

Why mix `add_layer` (tool) and `viewer.add_image` (in `execute_code`)? Because `add_layer(data_var=...)` requires the array to already exist in the namespace; doing it in one `execute_code` block is shorter when the array is computed there anyway.

If you want the layers to stay around, skip `remove_layer` — but watch the layer count, both tools and screenshots get slow with hundreds of layers.

---

## 6. Persist layer artifacts

`save_layer_data` infers format from extension. Choose the right extension for the layer type — see [tools.md](tools.md#save_layer_dataname-path-format) for the compatibility matrix.

```text
# Image / Labels → tiff (lossless), png (lossless 2D), jpg (lossy)
save_layer_data("nuclei_seg", "/out/nuclei_seg.tif")

# Points / Tracks / Vectors → csv (table) or npy (raw)
save_layer_data("centroids", "/out/centroids.csv")    # CSV with axis-N header
save_layer_data("tracks", "/out/tracks.csv")          # CSV with track_id,axis-N
save_layer_data("flow", "/out/flow.npy")              # raw vectors

# Anything → npy (numpy raw, no metadata)
save_layer_data("any_layer", "/out/dump.npy")
```

`csv` on an Image/Labels layer (or `tif` on a Points layer) returns a structured error — the tool refuses incompatible combinations rather than silently producing garbage.
