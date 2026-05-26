# napari Python API cheatsheet

Everything you send via `napari_client.py` is plain napari Python. This is a goal-indexed reference for the calls that come up most. For the full surface see <https://napari.org/dev/api/index.html>.

Every snippet assumes the pre-bound names `viewer`, `napari`, `np` (see [protocol.md](protocol.md)). Imports beyond those must be inside the `code` blob because the exec namespace is fresh each call.

## Layer creation

```python
# From a file path — napari sniffs the format and picks the right layer type.
viewer.open("/path/to/img.tif")                 # may add one or many layers

# From a numpy array.
viewer.add_image(arr, name="raw", colormap="viridis", contrast_limits=[0, 4096])
viewer.add_labels(mask.astype(np.int32), name="seg")
viewer.add_points([[10, 10], [50, 50]], name="dots", size=10)
viewer.add_shapes([[0, 0], [100, 100]], shape_type="rectangle")
viewer.add_vectors(vec, edge_width=1.0)         # vec shape: (N, 2, D)
viewer.add_tracks(tracks)                       # tracks shape: (N, D+1) with track_id col
viewer.add_surface((vertices, faces, values))   # tuple, not separate args

# Multi-channel image with channel_axis — returns a list of layers.
viewer.add_image(rgb, channel_axis=-1, name=["R", "G", "B"])
```

## Layer access and inspection

```python
viewer.layers                       # LayerList, iterable + indexable
viewer.layers["name"]               # by name
viewer.layers[0]                    # by index
layer.data                          # underlying array (numpy or dask)
layer.dtype, layer.data.shape, layer.ndim
layer.visible, layer.opacity, layer.blending
layer.scale, layer.translate        # world transform
layer.extent.world                  # ((mins...), (maxs...)) in world coords

# Image-specific
layer.colormap.name                 # current colormap
layer.contrast_limits               # [lo, hi]
layer.contrast_limits_range         # data range
layer.gamma
layer.interpolation2d               # "nearest", "linear", etc.

# Labels-specific
np.unique(np.asarray(layer.data))   # label values present
layer.selected_label
```

A common return idiom:

```python
_result = [{"name": l.name, "type": type(l).__name__, "shape": getattr(l.data, "shape", None)}
           for l in viewer.layers]
```

## Layer mutation

```python
layer = viewer.layers["raw"]
layer.visible = False
layer.opacity = 0.6
layer.colormap = "magma"
layer.contrast_limits = [100, 2000]
layer.gamma = 1.4
layer.name = "raw_renamed"

# Selection (used by some napari operations)
viewer.layers.selection = {viewer.layers["raw"]}

# Bulk: glob over name, filter by class
for l in viewer.layers:
    if isinstance(l, napari.layers.Image) and l.name.startswith("seg_"):
        l.visible = False
```

## Layer removal / reorder

```python
viewer.layers.remove(viewer.layers["raw"])      # by reference
del viewer.layers["raw"]                        # by name
viewer.layers.clear()                           # remove all

# Reorder (LayerList is a typed mutable sequence)
i = viewer.layers.index(viewer.layers["seg"])
viewer.layers.move(i, 0)                        # move to bottom
viewer.layers.move_multiple([i, j], 0)
```

## Viewer configuration

```python
# 2D ↔ 3D
viewer.dims.ndisplay = 3
viewer.dims.ndisplay = 2

# Slider position. set_current_step(axis, value); value is clamped to [0, nsteps[axis]-1].
viewer.dims.set_current_step(0, 10)             # step axis 0 to index 10
viewer.dims.current_step                        # tuple of current indices
viewer.dims.nsteps                              # tuple, slider extents
viewer.dims.axis_labels = ("t", "y", "x")

# Camera
viewer.camera.center = (0, 256, 256)
viewer.camera.zoom = 1.5
viewer.camera.angles = (30, 45, 0)              # (azimuth, elevation, roll) in degrees
viewer.camera.perspective = 0                   # 0 = orthographic
viewer.reset_view()                             # fit to data

# Grid mode
viewer.grid.enabled = True
viewer.grid.shape = (-1, 3)                     # auto rows, 3 cols
```

## Screenshot

There is **no inline image transport** in the new protocol. Always save to disk and read the PNG back on the client side.

```python
viewer.screenshot(path="/tmp/canvas.png", canvas_only=True)
viewer.screenshot(path="/tmp/window.png", canvas_only=False)   # includes chrome
viewer.screenshot(path="/tmp/big.png", canvas_only=True, scale=2.0)
viewer.screenshot(path="/tmp/fixed.png", canvas_only=True, size=(1024, 1024))
```

After the call returns, `Read /tmp/canvas.png` on the Claude side renders the image inline.

## Common image operations

The exec namespace is **fresh per call**, so import what you need inside the `code` blob. Recommended libs (already in most napari envs):

```python
# Gaussian blur on an existing Image layer, add the result as a new layer.
from scipy.ndimage import gaussian_filter
img = np.asarray(viewer.layers["raw"].data)
viewer.add_image(gaussian_filter(img, sigma=2.0), name="raw_blur")

# Otsu threshold → binary Labels.
from skimage.filters import threshold_otsu
img = np.asarray(viewer.layers["raw"].data)
mask = (img > threshold_otsu(img)).astype(np.uint8)
viewer.add_labels(mask, name="raw_otsu")

# Connected components.
from skimage.measure import label
labels = label(np.asarray(viewer.layers["raw_otsu"].data) > 0).astype(np.int32)
viewer.add_labels(labels, name="raw_components")
```

For more involved pipelines, paste one of the helper modules (`scripts/dump_session.py`, `scripts/apply_filter.py`, `scripts/screenshot_grid.py`) via `napari_client.py --file` and end with `_result = some_call(...)`.

## Persisting layer data

napari layers don't have a generic `save` method; use the underlying array + an appropriate writer.

```python
# Image / Labels → tiff
import tifffile
tifffile.imwrite("/out/seg.tif", np.asarray(viewer.layers["seg"].data))

# Image → png (single 2D slice)
from PIL import Image as _PIL
_PIL.fromarray(np.asarray(viewer.layers["raw"].data).astype(np.uint8)).save("/out/raw.png")

# Points / Tracks / Vectors → csv
import numpy as np
np.savetxt("/out/centroids.csv", np.asarray(viewer.layers["dots"].data),
           delimiter=",", header=",".join(f"axis-{i}" for i in range(viewer.layers["dots"].data.shape[1])))

# Anything → npy (raw)
np.save("/out/dump.npy", np.asarray(viewer.layers["raw"].data))
```

## Useful introspection one-liners

```python
# Summary
_result = {"layers": [l.name for l in viewer.layers],
           "ndisplay": viewer.dims.ndisplay,
           "current_step": list(viewer.dims.current_step),
           "camera_zoom": float(viewer.camera.zoom)}

# Full dtype/shape inventory
_result = [(l.name, type(l).__name__, str(getattr(l.data, "dtype", "")),
            tuple(getattr(l.data, "shape", ()))) for l in viewer.layers]
```

For an exhaustive dump including world bounds, scale, translate, and full camera state, paste `scripts/dump_session.py` and end with `_result = dump_session()`.
