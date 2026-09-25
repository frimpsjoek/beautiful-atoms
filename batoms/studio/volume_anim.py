"""Animated isosurfaces for a structure with a trajectory + key-frame volumes.

batoms animates atoms (trajectory shape keys) but not isosurfaces, so this
module builds one +/- mesh pair per output frame with keyframed visibility.

Build:
  1. key volumes from settings.volumes_path (saved by Series import);
  2. signs aligned to the reference frame (eigenvector/orbital signs are
     arbitrary; unaligned frames flicker);
  3. one isovalue for all frames (absolute, or enclosing a fraction of the
     reference frame's weight);
  4. optional sub-frames: atoms (minimum-image unwrapped) and volumes are
     interpolated with the same method (interp.py); the key positions are
     kept in the volumes file so the interpolation can be changed later;
  5. contour with the same marching-cubes call batoms uses; shared
     materials iso_positive / iso_negative (recolor once, every frame
     follows); isosurfaces are locked children of the structure;
  6. verification: every frame shows exactly its own pair and the atoms
     match the (interpolated) key positions.
"""

import os
import time

import bpy
import numpy as np

from . import interp
from .lighting import srgb_to_linear


def _load(settings):
    path = bpy.path.abspath(settings.volumes_path)
    if not path or not os.path.exists(path):
        raise ValueError("No key-frame volumes: import a series of cube files first "
                         "(Series import), or set the Volumes file")
    data = np.load(path)
    return path, {k: data[k] for k in data.files}


def _save(path, data):
    np.savez_compressed(path, **data)


def iso_collection(label, create=True):
    name = f"{label}_isosurfaces"
    coll = bpy.data.collections.get(name)
    if coll is None and create:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def clear_isosurfaces(label):
    coll = iso_collection(label, create=False)
    if coll is None:
        return
    for obj in list(coll.objects):
        me = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)


def _material(name, color, alpha):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = srgb_to_linear(color) + [1.0]
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Roughness"].default_value = 0.35
    return mat


def _contour(vol, level, cell, step):
    from skimage import measure

    v, f, _, _ = measure.marching_cubes(
        vol, level=level, spacing=tuple(1.0 / np.array(vol.shape)),
        gradient_direction="descent", allow_degenerate=False, step_size=step,
    )
    return v @ cell, f


def _prepared_volume(keys, f, substeps, method, upsample_to):
    vol = interp.interpolate(keys, f, substeps, method)
    if upsample_to and min(vol.shape) < upsample_to:
        from ..plugins.isosurface.isosurface import upsample_volume

        vol = upsample_volume(vol, upsample_to)
    return vol


def _fill_mesh(me, vol, level, cell, step, draw):
    me.clear_geometry()
    if draw:
        try:
            v, f = _contour(vol, level, cell, step)
            me.from_pydata(v.tolist(), [], f.tolist())
            me.shade_smooth()
        except (ValueError, RuntimeError):
            pass  # level outside this frame's data range: empty mesh
    me.update()


def build(b, settings, progress=None):
    """Build the animation for structure ``b``. Returns a report dict."""
    from ..utils.butils import attach_child

    t0 = time.time()
    path, data = _load(settings)
    keys = data["vols"].astype(np.float32)
    n_keys = len(keys)
    # key positions: stored on first build, else the structure's trajectory
    if "key_positions" in data:
        key_pos = list(data["key_positions"])
    else:
        traj = b.get_trajectory()["positions"]
        key_pos = list(traj) if len(traj) else [b.positions]
        data["key_positions"] = np.array(key_pos)
    if len(key_pos) != n_keys:
        raise ValueError(f"'{b.label}' has {len(key_pos)} frames but there are {n_keys} volumes")
    # signs
    ref_i = min(settings.reference, n_keys - 1)
    ref = keys[ref_i].ravel().astype(float)
    ref /= np.linalg.norm(ref)
    signed = bool(keys[ref_i].min() < -0.05 * np.abs(keys[ref_i]).max())
    flipped, overlaps = [], []
    for k in range(n_keys):
        v = keys[k].ravel().astype(float)
        o = float(np.einsum("i,i", v, ref) / np.sqrt(np.einsum("i,i", v, v)))
        if settings.align_signs and signed and o < 0:
            keys[k] = -keys[k]
            o = -o
            flipped.append(k)
        overlaps.append(o)
    # isovalue
    if settings.level > 0:
        level = settings.level
    else:
        from ..plugins.isosurface.isosurface import enclosing_level

        level, _ = enclosing_level(keys[ref_i], settings.enclose)
    # atoms: interpolated trajectory
    S, method = settings.substeps, settings.method
    cell = np.asarray(b.cell.array if hasattr(b.cell, "array") else b.cell[:], dtype=float)
    pbc = np.linalg.det(cell) > 1e-8
    unwrapped = interp.unwrap_positions(key_pos, cell, [pbc] * 3)
    n = interp.n_output_frames(n_keys, S)
    positions = np.array([interp.interpolate(unwrapped, f, S, method) for f in range(n)])
    from .common import replace_trajectory

    replace_trajectory(b, positions)
    # isosurfaces
    clear_isosurfaces(b.label)
    coll = iso_collection(b.label)
    mats = {
        "positive": _material("iso_positive", settings.positive_color, settings.iso_alpha),
        "negative": _material("iso_negative", settings.negative_color, settings.iso_alpha),
    }
    for f in range(n):
        vol = _prepared_volume(keys, f, S, method, settings.upsample_to)
        for tag, lev in (("positive", level), ("negative", -level)):
            me = bpy.data.meshes.new(f"{b.label}_iso_{tag}_{f:04d}")
            _fill_mesh(me, vol, lev, cell, settings.step_size, tag == "positive" or signed)
            me.materials.append(mats[tag])
            obj = bpy.data.objects.new(me.name, me)
            coll.objects.link(obj)
            attach_child(obj, b.obj)
            obj["iso_frame"], obj["iso_sign"] = f, tag
            if settings.smooth:
                mod = obj.modifiers.new("iso_smooth", "SMOOTH")
                mod.factor, mod.iterations = 0.5, settings.smooth
            for hide, fr in ((True, f - 1), (False, f), (True, f + 1)):
                if 0 <= fr < n:
                    obj.hide_viewport = obj.hide_render = hide
                    obj.keyframe_insert("hide_viewport", frame=fr)
                    obj.keyframe_insert("hide_render", frame=fr)
        if progress:
            progress(f / n)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 0, n - 1
    scene.frame_set(0)
    data["vols_aligned"] = keys
    _save(path, data)
    settings.anim_label = b.label
    report = verify(b, settings, positions)
    report.update(level=level, signed=signed, flipped=flipped, frames=n, keys=n_keys,
                  min_overlap=round(min(overlaps), 3), seconds=round(time.time() - t0, 1))
    settings.anim_report = _summary(report)
    return report


def update(b, settings, progress=None):
    """Re-contour every frame with the current isovalue/colors/quality (atoms untouched)."""
    path, data = _load(settings)
    keys = data.get("vols_aligned", data["vols"]).astype(np.float32)
    if settings.level > 0:
        level = settings.level
    else:
        from ..plugins.isosurface.isosurface import enclosing_level

        level, _ = enclosing_level(keys[min(settings.reference, len(keys) - 1)], settings.enclose)
    signed = bool(keys.min() < -0.05 * np.abs(keys).max())
    _material("iso_positive", settings.positive_color, settings.iso_alpha)
    _material("iso_negative", settings.negative_color, settings.iso_alpha)
    cell = np.asarray(b.cell.array if hasattr(b.cell, "array") else b.cell[:], dtype=float)
    coll = iso_collection(b.label, create=False)
    if coll is None:
        raise ValueError("No animation built yet: press Build first")
    objs = {(o["iso_frame"], o["iso_sign"]): o for o in coll.objects}
    n = max(f for f, _ in objs) + 1
    S = (n - 1) // max(len(keys) - 1, 1) if len(keys) > 1 else 1
    for f in range(n):
        vol = _prepared_volume(keys, f, S, settings.method, settings.upsample_to)
        for tag, lev in (("positive", level), ("negative", -level)):
            obj = objs.get((f, tag))
            if obj is None:
                continue
            _fill_mesh(obj.data, vol, lev, cell, settings.step_size, tag == "positive" or signed)
            mod = obj.modifiers.get("iso_smooth") or obj.modifiers.new("iso_smooth", "SMOOTH")
            mod.factor, mod.iterations = 0.5, max(settings.smooth, 0)
            mod.show_viewport = mod.show_render = settings.smooth > 0
        if progress:
            progress(f / n)
    settings.anim_report = f"Updated {n} frames at ±{level:.4g}"
    return {"frames": n, "level": level}


def verify(b, settings, positions=None):
    """Every frame: exactly its own +/- pair visible; atoms at the expected positions."""
    scene = bpy.context.scene
    coll = iso_collection(b.label, create=False)
    objs = list(coll.objects) if coll else []
    n = scene.frame_end + 1
    bad_vis, err = [], 0.0
    current = scene.frame_current
    for f in range(n):
        scene.frame_set(f)
        vis = sorted(o["iso_frame"] for o in objs if not o.hide_render)
        if vis != [f, f]:
            bad_vis.append(f)
        if positions is not None:
            ev = b.obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            p = np.array([v.co[:] for v in ev.vertices])
            err = max(err, float(np.abs(p - positions[f]).max()))
    scene.frame_set(current)
    return {"bad_visibility": bad_vis, "max_position_error": err, "verified": not bad_vis and err < 1e-3}


def _summary(r):
    ok = "verified" if r.get("verified") else "CHECK FAILED"
    return (f"{r['frames']} frames ({r['keys']} keys), ±{r['level']:.4g}, "
            f"{len(r['flipped'])} sign flips, min overlap {r['min_overlap']}, {ok}")
