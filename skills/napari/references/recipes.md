# napari recipes

Each recipe is a self-contained `code` blob to send via `napari_client.py`. The exec namespace is fresh per call (see [protocol.md](protocol.md)), so each recipe collapses what used to be multi-tool sequences into a single Python block. Adapt names, paths, and parameters to your task.

Run any of these by writing the blob to a file (or via heredoc) and sending it with:

```bash
python skills/napari/scripts/napari_client.py --file recipe.py
```

---

## 1. Load image → set colormap → screenshot

```python
viewer.open("/path/to/img.tif")
l = viewer.layers[-1]                       # the layer just added
l.colormap = "viridis"
l.contrast_limits = [0, 4096]
viewer.reset_view()
viewer.screenshot(path="/tmp/img_view.png", canvas_only=True)
_result = {"layer": l.name, "shape": tuple(l.data.shape), "screenshot": "/tmp/img_view.png"}
```

Read the PNG on the Claude side: `Read /tmp/img_view.png`.

---

## 2. Filter via scipy/skimage → add as new Labels layer

```python
from skimage.filters import threshold_otsu
from skimage.measure import label

img = np.asarray(viewer.layers["cells"].data)
thr = float(threshold_otsu(img))
mask = (img > thr).astype(np.uint8)
viewer.add_labels(mask, name="cells_otsu")
labels = label(mask).astype(np.int32)
viewer.add_labels(labels, name="cells_components")
_result = {"threshold": thr, "n_components": int(labels.max())}
```

If `skimage` is missing, the call returns `executed: false` with an `ImportError`. Install into napari's env (`pip install scikit-image`) and retry — there is no in-band package installer in this plugin.

For more structure, paste `scripts/apply_filter.py` and end with `_result = apply_filter("cells", "threshold_otsu")`.

---

## 3. Switch to 3D and rotate the camera

```python
viewer.dims.ndisplay = 3
viewer.reset_view()
viewer.camera.angles = (30, 45, 0)          # (azimuth, elevation, roll) in degrees
viewer.camera.zoom = 1.5
viewer.screenshot(path="/tmp/view_3d.png", canvas_only=True)
_result = {"angles": list(viewer.camera.angles), "zoom": float(viewer.camera.zoom),
           "screenshot": "/tmp/view_3d.png"}
```

---

## 4. Sweep a temporal axis and save every frame to disk

For `(T, Y, X)` data, time is axis 0. This recipe writes one PNG per timepoint and returns the list of paths — there is no inline image transport, so disk is the only mode for many-frame captures.

```python
from pathlib import Path

outdir = Path("/tmp/sweep")
outdir.mkdir(parents=True, exist_ok=True)

axis = 0
nsteps = int(viewer.dims.nsteps[axis])
paths = []
for i in range(nsteps):
    viewer.dims.set_current_step(axis, i)
    p = outdir / f"frame_{i:04d}.png"
    viewer.screenshot(path=str(p), canvas_only=True)
    paths.append(str(p))

_result = {"n_frames": len(paths), "outdir": str(outdir), "first": paths[0], "last": paths[-1]}
```

For arbitrary index sets or a stitched montage, paste `scripts/screenshot_grid.py` and call `capture_grid(axis=0, indices=[0, 5, 10, 15], save_dir="/tmp/grid")`.

---

## 5. Batch process many files (load → filter → save → unload)

```python
from pathlib import Path
from scipy.ndimage import gaussian_filter
import tifffile

inputs = sorted(Path("/data/in").glob("*.tif"))
outdir = Path("/data/out")
outdir.mkdir(parents=True, exist_ok=True)

results = []
for p in inputs:
    viewer.open(str(p))
    l = viewer.layers[-1]
    blurred = gaussian_filter(np.asarray(l.data), sigma=2.0)
    out_path = outdir / f"{p.stem}_smooth.tif"
    tifffile.imwrite(str(out_path), blurred)
    results.append({"in": str(p), "out": str(out_path), "shape": tuple(blurred.shape)})
    # Free the viewer — many layers get slow.
    viewer.layers.remove(l)

_result = {"n": len(results), "results": results}
```

Send via `napari_client.py --file batch.py`. Heavy batches may approach the 300 s Qt-thread timeout; in that case chunk the file list and send a separate call per chunk (intermediate progress is fine to print, but it'll lose the `_result` payload — stdout wins).

---

## 6. Persist layer artifacts

The plugin doesn't ship a generic layer-saver — pick the right writer for the data type.

```python
import tifffile
import numpy as np

# Image / Labels → tiff (lossless, ND-friendly)
tifffile.imwrite("/out/nuclei_seg.tif",
                 np.asarray(viewer.layers["nuclei_seg"].data))

# Points / Tracks / Vectors → csv (table form)
points = np.asarray(viewer.layers["centroids"].data)
header = ",".join(f"axis-{i}" for i in range(points.shape[1]))
np.savetxt("/out/centroids.csv", points, delimiter=",", header=header, comments="")

# Anything → npy (raw, no metadata)
np.save("/out/raw_dump.npy", np.asarray(viewer.layers["raw"].data))

_result = {"saved": ["/out/nuclei_seg.tif", "/out/centroids.csv", "/out/raw_dump.npy"]}
```

For PNG/JPG of a single 2D slice, use `PIL`:

```python
from PIL import Image as _PIL
arr = np.asarray(viewer.layers["raw"].data).astype(np.uint8)
_PIL.fromarray(arr).save("/out/raw.png")
```
