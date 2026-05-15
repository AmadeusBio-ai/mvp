"""Capture screenshots at arbitrary slider positions.

Sidesteps the timelapse-mode 1.3 MB inline cap by either saving frames to disk
or returning a stitched numpy montage.

Paste this file into ``execute_code``, then call:

    capture_grid(axis=0, indices=[0, 5, 10, 15], save_dir="/tmp/grid")
    montage = capture_grid(axis=0, indices=range(0, 20, 2))   # returns ndarray

Assumes the standard pre-bound names: ``viewer``, ``napari``, ``np``.
"""

from __future__ import annotations

import math
from pathlib import Path


def capture_grid(
    axis: int,
    indices,
    save_dir: str | None = None,
    canvas_only: bool = True,
    cols: int | None = None,
) -> dict:
    """Step ``axis`` to each value in ``indices`` and screenshot.

    Parameters
    ----------
    axis : int
        Dims axis index to step.
    indices : iterable of int
        Step values (clamped to ``[0, nsteps[axis]-1]``).
    save_dir : str, optional
        If given, save each frame as ``frame_NNNN.png`` and return the paths.
        If omitted, stitch frames into a single montage ndarray.
    canvas_only : bool, default True
        Passed to ``viewer.screenshot``.
    cols : int, optional
        Montage column count. Defaults to ``ceil(sqrt(n_frames))``. Ignored
        when ``save_dir`` is set.

    Returns
    -------
    dict
        ``{"n_frames": N, "paths": [...], "indices": [...]}`` (save mode)
        or ``{"n_frames": N, "montage_shape": [H, W, C], "indices": [...],
              "montage": ndarray}`` (in-memory mode).
    """
    indices = list(indices)
    if not indices:
        return {"n_frames": 0, "indices": []}

    nsteps = int(viewer.dims.nsteps[axis])
    indices = [max(0, min(int(i), nsteps - 1)) for i in indices]

    if save_dir is not None:
        outdir = Path(save_dir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for idx in indices:
            viewer.dims.set_current_step(axis, idx)
            arr = viewer.screenshot(canvas_only=canvas_only)
            arr = np.asarray(arr).astype(np.uint8, copy=False)
            fp = outdir / f"frame_{idx:04d}.png"
            try:
                from PIL import Image as _PIL

                _PIL.fromarray(arr).save(str(fp))
            except Exception:
                np.save(str(fp.with_suffix(".npy")), arr)
                fp = fp.with_suffix(".npy")
            paths.append(str(fp))
        return {"n_frames": len(paths), "paths": paths, "indices": indices}

    # In-memory montage
    frames: list[np.ndarray] = []
    for idx in indices:
        viewer.dims.set_current_step(axis, idx)
        arr = np.asarray(viewer.screenshot(canvas_only=canvas_only))
        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)
        frames.append(arr)

    h, w = frames[0].shape[:2]
    c = frames[0].shape[2] if frames[0].ndim == 3 else 1
    n = len(frames)
    if cols is None:
        cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))

    if c == 1:
        montage = np.zeros((rows * h, cols * w), dtype=np.uint8)
    else:
        montage = np.zeros((rows * h, cols * w, c), dtype=np.uint8)

    for i, frame in enumerate(frames):
        r, k = divmod(i, cols)
        montage[r * h : (r + 1) * h, k * w : (k + 1) * w] = frame

    return {
        "n_frames": n,
        "montage_shape": list(montage.shape),
        "indices": indices,
        "montage": montage,
    }
