"""Interpolation between key frames (pure numpy; used in and outside Blender).

Output frame f of a sequence with K key frames and ``substeps`` S has
key index k = f // S and fraction w = (f % S) / S; the last output frame is
key frame K-1. Methods:

- "step":       hold key frame k (no blending)
- "linear":     (1 - w) X_k + w X_{k+1}
- "smoothstep": linear blend with eased weight 3w^2 - 2w^3 (slows at keys)
- "cubic":      Catmull-Rom spline through the keys (C1-smooth, may
                overshoot slightly between keys)

The same function interpolates atom positions and volumetric grids.
"""

import numpy as np

METHODS = ("step", "linear", "smoothstep", "cubic")


def n_output_frames(n_keys, substeps):
    return (n_keys - 1) * substeps + 1


def segment(f, n_keys, substeps):
    """(k, w) for output frame f."""
    if f >= (n_keys - 1) * substeps:
        return n_keys - 2, 1.0
    return f // substeps, (f % substeps) / substeps


def interpolate(keys, f, substeps, method="linear"):
    """Value at output frame f from key frames ``keys`` (sequence of arrays)."""
    n = len(keys)
    if n == 1 or substeps == 1:
        return np.asarray(keys[min(f, n - 1)], dtype=float)
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    k, w = segment(f, n, substeps)
    a, b = np.asarray(keys[k], dtype=float), np.asarray(keys[k + 1], dtype=float)
    if method == "step":
        return a if w < 1.0 else b
    if method == "linear":
        return (1 - w) * a + w * b
    if method == "smoothstep":
        s = w * w * (3 - 2 * w)
        return (1 - s) * a + s * b
    # Catmull-Rom with clamped end tangents
    p0 = np.asarray(keys[max(k - 1, 0)], dtype=float)
    p3 = np.asarray(keys[min(k + 2, n - 1)], dtype=float)
    w2, w3 = w * w, w * w * w
    return 0.5 * (
        2 * a
        + (-p0 + b) * w
        + (2 * p0 - 5 * a + 4 * b - p3) * w2
        + (-p0 + 3 * a - 3 * b + p3) * w3
    )


def unwrap_positions(frames_positions, cell, pbc):
    """Remove jumps across periodic boundaries between consecutive frames.

    Each frame is shifted atom-by-atom by lattice vectors so every
    displacement from the previous frame is a minimum-image displacement.
    Without this, an atom crossing the cell edge would be interpolated
    through the whole cell.
    """
    cell = np.asarray(cell, dtype=float)
    out = [np.asarray(frames_positions[0], dtype=float)]
    if not np.any(pbc) or abs(np.linalg.det(cell)) < 1e-8:
        return [np.asarray(p, dtype=float) for p in frames_positions]
    inv = np.linalg.inv(cell)
    for p in frames_positions[1:]:
        d = np.asarray(p, dtype=float) - out[-1]
        frac = d @ inv
        frac[:, np.asarray(pbc, bool)] -= np.round(frac[:, np.asarray(pbc, bool)])
        out.append(out[-1] + frac @ cell)
    return out
