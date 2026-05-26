"""Apply a common image filter and add the result as a new layer.

Use as a function library inside a code blob sent via ``napari_client.py``.
The simplest pattern is to append a call to the end of the file and send the
whole thing with ``--file``:

    # at the bottom of the snippet you actually send:
    import json
    print(json.dumps(apply_filter("cells", "threshold_otsu")))

then:

    python skills/napari/scripts/napari_client.py --file my_snippet.py

Assumes the standard pre-bound names: ``viewer``, ``napari``, ``np``.
Requires ``scipy`` and ``scikit-image`` — there is no in-band installer in the
new plugin, so install them into napari's env from a terminal
(``pip install scipy scikit-image``) and restart napari if they're missing.
"""

from __future__ import annotations


def apply_filter(layer_name: str, kind: str, **kwargs) -> dict:
    """Apply ``kind`` to ``viewer.layers[layer_name].data`` and add the result.

    Parameters
    ----------
    layer_name : str
        Name of an existing Image (or Labels, for "label") layer.
    kind : {"gaussian", "median", "threshold_otsu", "label"}
        - ``gaussian`` / ``median`` → new Image layer (kwargs forwarded).
        - ``threshold_otsu`` → new Labels layer (binary mask, threshold returned
          in result dict).
        - ``label`` → new Labels layer (connected components on a binary input).
    **kwargs
        Forwarded to the underlying filter.

    Returns
    -------
    dict
        ``{"new_layer": str, "kind": str, ...}`` with extra fields per filter
        (e.g. ``threshold`` for Otsu, ``n_labels`` for label).
    """
    if layer_name not in viewer.layers:
        raise KeyError(f"Layer {layer_name!r} not found")
    src = viewer.layers[layer_name]
    data = np.asarray(src.data)

    if kind == "gaussian":
        from scipy.ndimage import gaussian_filter

        sigma = kwargs.pop("sigma", 1.0)
        out = gaussian_filter(data, sigma=sigma, **kwargs)
        new_name = f"{layer_name}_gaussian"
        viewer.add_image(out, name=new_name)
        return {"new_layer": new_name, "kind": kind, "sigma": sigma}

    if kind == "median":
        from scipy.ndimage import median_filter

        size = kwargs.pop("size", 3)
        out = median_filter(data, size=size, **kwargs)
        new_name = f"{layer_name}_median"
        viewer.add_image(out, name=new_name)
        return {"new_layer": new_name, "kind": kind, "size": size}

    if kind == "threshold_otsu":
        from skimage.filters import threshold_otsu

        thr = float(threshold_otsu(data))
        mask = (data > thr).astype(np.uint8)
        new_name = f"{layer_name}_otsu"
        viewer.add_labels(mask, name=new_name)
        return {"new_layer": new_name, "kind": kind, "threshold": thr}

    if kind == "label":
        from skimage.measure import label

        labeled = label(data > 0).astype(np.int32)
        n = int(labeled.max())
        new_name = f"{layer_name}_labels"
        viewer.add_labels(labeled, name=new_name)
        return {"new_layer": new_name, "kind": kind, "n_labels": n}

    raise ValueError(
        f"Unknown kind {kind!r}. Use one of: gaussian, median, threshold_otsu, label"
    )
