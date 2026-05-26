"""Exhaustive session/layer dump for napari-mcp.

Send this whole file to the napari-mcp socket via ``napari_client.py``:

    python skills/napari/scripts/napari_client.py --file skills/napari/scripts/dump_session.py

The trailing ``dump_session()`` call at the bottom of this file leaves the dict
as the last expression — but the socket protocol returns ``output``, not
``result_repr``, so the file ends by **printing JSON** to capture the payload.
Use when a quick one-liner over ``viewer.layers`` won't surface the field you
need (world bounds, scale, translate, full camera state, dtype, etc.).

Assumes the standard pre-bound names: ``viewer``, ``napari``, ``np``.
"""

from __future__ import annotations


def dump_session() -> dict:
    """Return a dict describing every layer and the viewer state.

    Fields per layer: name, type, dtype, shape, ndim, scale, translate,
    world_bounds, visible, opacity, blending, plus type-specific:
    colormap/contrast_limits/gamma (Image), n_labels (Labels),
    n_points (Points), nshapes/shape_type (Shapes), n_vectors (Vectors),
    n_tracks (Tracks), n_vertices/n_faces (Surface).
    """
    out = {
        "viewer": {
            "title": viewer.title,
            "ndisplay": viewer.dims.ndisplay,
            "ndim": viewer.dims.ndim,
            "current_step": list(viewer.dims.current_step),
            "nsteps": list(viewer.dims.nsteps),
            "order": list(viewer.dims.order),
            "axis_labels": list(viewer.dims.axis_labels),
            "camera_center": list(viewer.camera.center),
            "camera_zoom": float(viewer.camera.zoom),
            "camera_angles": list(viewer.camera.angles),
            "camera_perspective": float(viewer.camera.perspective),
            "grid_enabled": viewer.grid.enabled,
            "grid_shape": list(viewer.grid.shape) if viewer.grid.enabled else None,
        },
        "layers": [],
    }

    for lyr in viewer.layers:
        ltype = lyr.__class__.__name__
        info = {
            "name": lyr.name,
            "type": ltype,
            "ndim": int(getattr(lyr, "ndim", 0)),
            "visible": bool(lyr.visible),
            "opacity": float(lyr.opacity),
            "blending": str(getattr(lyr, "blending", "")),
            "scale": [float(s) for s in lyr.scale],
            "translate": [float(t) for t in lyr.translate],
        }
        try:
            info["world_extent"] = [
                [float(lo), float(hi)]
                for lo, hi in zip(*lyr.extent.world, strict=False)
            ]
        except Exception:
            pass

        data = getattr(lyr, "data", None)
        if data is not None:
            shape = getattr(data, "shape", None)
            dtype = getattr(data, "dtype", None)
            if shape is not None:
                info["shape"] = list(shape)
            if dtype is not None:
                info["dtype"] = str(dtype)

        if ltype == "Image":
            info["colormap"] = getattr(lyr.colormap, "name", str(lyr.colormap))
            try:
                info["contrast_limits"] = [
                    float(lyr.contrast_limits[0]),
                    float(lyr.contrast_limits[1]),
                ]
                info["contrast_limits_range"] = [
                    float(lyr.contrast_limits_range[0]),
                    float(lyr.contrast_limits_range[1]),
                ]
            except Exception:
                pass
            info["gamma"] = float(lyr.gamma)
            info["interpolation2d"] = str(getattr(lyr, "interpolation2d", ""))
        elif ltype == "Labels":
            try:
                info["n_labels"] = int(
                    len(np.unique(np.asarray(data))) - (1 if 0 in data else 0)
                )
            except Exception:
                pass
        elif ltype == "Points":
            info["n_points"] = int(np.shape(data)[0]) if data is not None else 0
            try:
                info["mean_size"] = float(np.mean(lyr.size))
                info["symbol"] = str(lyr.symbol)
            except Exception:
                pass
        elif ltype == "Shapes":
            info["nshapes"] = int(lyr.nshapes)
            info["shape_types"] = list(lyr.shape_type)
        elif ltype == "Vectors":
            info["n_vectors"] = int(np.shape(data)[0]) if data is not None else 0
            info["edge_width"] = float(getattr(lyr, "edge_width", 1.0))
        elif ltype == "Tracks":
            try:
                info["n_tracks"] = int(len(np.unique(np.asarray(data)[:, 0])))
            except Exception:
                pass
        elif ltype == "Surface" and data is not None:
            try:
                info["n_vertices"] = int(np.shape(data[0])[0])
                info["n_faces"] = int(np.shape(data[1])[0])
            except Exception:
                pass

        out["layers"].append(info)

    return out


# Print JSON so the socket response carries the structured dump in
# result.output, which the client can json.loads on the other side.
import json as _json
print(_json.dumps(dump_session(), default=str))
