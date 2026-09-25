"""Import a series of structure files onto the timeline.

Same atoms in every frame (MD, relaxation, NEB, perturbations) -> one
structure with a trajectory (Blender frame k = file k), so colors and
formatting are shared by construction. "Append" extends a structure that
is already in the scene. Different atoms per frame -> one structure per
frame, each visible only on its own frame, with the style (colors, radii,
model style, bond cutoffs) copied from the first.

Cube files also carry volumes; they are saved as key frames for the
Volume animation panel (<blend>_<label>_volumes.npz next to the .blend).
"""

import os
import re

import bpy
import numpy as np

FORMATS = (
    ("AUTO", "Auto (by extension)", "cube, xyz, cif, POSCAR/CONTCAR/.vasp, QE .in/.pwi, .out/.pwo, traj ..."),
    ("cube", "Gaussian cube", ""),
    ("extxyz", "XYZ / extended XYZ", ""),
    ("cif", "CIF", ""),
    ("vasp", "VASP POSCAR/CONTCAR", ""),
    ("vasp-out", "VASP OUTCAR", ""),
    ("espresso-in", "Quantum ESPRESSO input", ""),
    ("espresso-out", "Quantum ESPRESSO output", ""),
    ("traj", "ASE trajectory", ""),
)

_EXT = {
    ".cube": "cube", ".cub": "cube", ".xyz": "extxyz", ".extxyz": "extxyz", ".cif": "cif",
    ".vasp": "vasp", ".poscar": "vasp", ".in": "espresso-in", ".pwi": "espresso-in",
    ".out": "espresso-out", ".pwo": "espresso-out", ".traj": "traj",
}


def natural_key(path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", os.path.basename(str(path)))]


def guess_format(path):
    name = os.path.basename(path).upper()
    if name.startswith(("POSCAR", "CONTCAR")):
        return "vasp"
    if name.startswith("OUTCAR"):
        return "vasp-out"
    return _EXT.get(os.path.splitext(path)[1].lower())  # None -> let ASE guess


def read_series(paths, fmt="AUTO"):
    """Read files in the given order -> (frames, volumes or None, sources).

    Multi-frame files (xyz, QE .out, traj, OUTCAR) contribute all frames.
    ``volumes`` is a list only when every file is a cube.
    """
    from ase.io import read
    from ase.io.cube import read_cube_data

    frames, volumes, sources = [], [], []
    all_cubes = True
    for path in paths:
        f = guess_format(path) if fmt == "AUTO" else fmt
        if f == "cube":
            vol, atoms = read_cube_data(path)
            frames.append(atoms)
            volumes.append(np.asarray(vol, dtype=np.float32))
            sources.append(os.path.basename(path))
            continue
        all_cubes = False
        images = read(path, index=":", format=f)
        images = images if isinstance(images, list) else [images]
        frames += images
        sources += [os.path.basename(path)] * len(images)
    return frames, (volumes if all_cubes and volumes else None), sources


def same_topology(frames):
    ref = frames[0].numbers
    return all(len(a) == len(ref) and np.array_equal(a.numbers, ref) for a in frames)


def copy_style(src, dst):
    """Copy what the user formatted on ``src`` onto ``dst`` (another Batoms).

    Structures of other frames are hidden on the current frame; batoms can
    only edit visible objects, so they are shown during the copy.
    """
    parts = [dst.obj] + list(dst.obj.children_recursive)
    hidden = [(o, o.hide_viewport, o.hide_get()) for o in parts]
    for o in parts:
        o.hide_viewport = False
        o.hide_set(False)
    try:
        _copy_style(src, dst)
    finally:
        for o, hv, h in hidden:
            o.hide_viewport = hv
            o.hide_set(h)


def _copy_style(src, dst):
    dst.model_style = src.model_style
    for sp in dst.species.keys():
        if sp in src.species.keys():
            dst.species[sp].color = list(src.species[sp].color)
    for pair, data in src.bond.settings.items():
        if pair in dst.bond.settings.keys():
            dst.bond.settings[pair] = {"max": data["max"], "min": data["min"]}
    dst.cell.hide = src.cell.hide


def _keyframe_only_on(objs, frame, last):
    for obj in objs:
        for hide, f in ((True, frame - 1), (False, frame), (True, frame + 1)):
            if 0 <= f <= last:
                obj.hide_viewport = obj.hide_render = hide
                obj.keyframe_insert("hide_viewport", frame=f)
                obj.keyframe_insert("hide_render", frame=f)


def volumes_file(label):
    """Where key-frame volumes of ``label`` are stored (next to the .blend)."""
    base = bpy.data.filepath
    folder = os.path.dirname(base) if base else bpy.app.tempdir
    stem = os.path.splitext(os.path.basename(base))[0] if base else "unsaved"
    return os.path.join(folder, f"{stem}_{label}_volumes.npz")


def import_series(paths, label=None, fmt="AUTO", append_to=None):
    """Create/extend structures from ``paths``. Returns a report dict."""
    from ..batoms import Batoms

    frames, volumes, sources = read_series(paths, fmt)
    if not frames:
        raise ValueError("no structures read")
    scene = bpy.context.scene
    report = {"files": len(paths), "frames": len(frames)}

    if append_to is not None:
        b = append_to
        existing = b.get_trajectory()["positions"]
        if len(existing) == 0:
            existing = [b.positions]
        ref = b.as_ase(with_attribute=False)
        ref = ref[0] if isinstance(ref, list) else ref
        if not same_topology([ref] + frames):
            raise ValueError(
                "cannot append: the files have different atoms than '{}' "
                "(use a new structure instead)".format(b.label)
            )
        inv = np.linalg.inv(np.array(b.obj.matrix_world))
        new = [a.positions @ inv[:3, :3].T + inv[:3, 3] for a in frames]
        from .common import replace_trajectory

        replace_trajectory(b, np.array(list(existing) + new))
        n = len(existing) + len(new)
        report.update(mode="appended", label=b.label, total_frames=n)
        start_index = len(existing)
    elif same_topology(frames):
        label = label or os.path.splitext(os.path.basename(paths[0]))[0]
        b = Batoms(label, from_ase=frames, load_trajectory=len(frames) > 1)
        n = len(frames)
        report.update(mode="trajectory", label=b.label, total_frames=n)
        start_index = 0
    else:
        label = label or os.path.splitext(os.path.basename(paths[0]))[0]
        first = None
        n = len(frames)
        for k, atoms in enumerate(frames):
            bk = Batoms(f"{label}_{k:03d}", from_ase=atoms)
            if first is None:
                first = bk
            else:
                copy_style(first, bk)
            _keyframe_only_on([bk.obj] + list(bk.obj.children_recursive), k, n - 1)
        b = first
        report.update(mode="separate", label=first.label, total_frames=n,
                      note="different atoms per frame: one structure per frame, style copied from the first")
        start_index = 0

    scene.frame_start, scene.frame_end = 0, n - 1
    scene.frame_set(start_index)
    if volumes is not None:
        path = volumes_file(b.label)
        old = []
        if append_to is not None and os.path.exists(path):
            old = list(np.load(path)["vols"])
        np.savez_compressed(path, vols=np.array(old + volumes, dtype=np.float32))
        s = scene.batoms_studio
        s.volumes_path, s.anim_label = path, b.label
        report["volumes"] = path
    report["sources"] = sources
    return b, report
