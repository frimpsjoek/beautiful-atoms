"""Vacancy from selected atoms: marker sphere + recolored neighbours."""

import bmesh
import bpy
import numpy as np

from .lighting import srgb_to_linear


def selected_atoms(b):
    """Indices of atoms selected in Edit Mode (or vertex selection flags)."""
    obj = b.obj
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        return [v.index for v in bm.verts if v.select]
    return [v.index for v in obj.data.vertices if v.select]


def neighbours(atoms, removed_positions, removed_numbers, scale):
    """Indices (in ``atoms``) within scale*(R_i + R_removed), minimum image."""
    from ase.data import covalent_radii
    from ase.geometry import get_distances

    found = set()
    for pos, num in zip(removed_positions, removed_numbers):
        _, d = get_distances([pos], atoms.positions, cell=atoms.cell, pbc=atoms.pbc)
        cut = scale * (covalent_radii[num] + covalent_radii[atoms.numbers])
        found |= set(np.where(d[0] <= cut)[0].tolist())
    return sorted(found)


def _marker(b, position, radius, color, i):
    from ..utils.butils import attach_child

    me = bpy.data.meshes.new(f"{b.label}_vacancy_{i}")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=radius)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    mat = bpy.data.materials.get("vacancy_marker") or bpy.data.materials.new("vacancy_marker")
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = srgb_to_linear(color) + [1.0]
    bsdf.inputs["Alpha"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.3
    me.materials.append(mat)
    obj = bpy.data.objects.new(me.name, me)
    b.coll.objects.link(obj)
    obj.location = position
    attach_child(obj, b.obj)
    obj.matrix_parent_inverse.identity()
    obj.location = position  # local coordinates of the structure
    obj["vacancy"] = True
    return obj


def make_vacancies(b, indices, settings):
    """Remove ``indices`` from ``b``; add markers; recolor neighbours."""
    from ..utils.butils import object_mode

    object_mode()
    atoms = b.as_ase(with_attribute=False)
    atoms = atoms[0] if isinstance(atoms, list) else atoms
    removed_pos = atoms.positions[indices].copy()
    removed_num = atoms.numbers[indices].copy()
    keep = np.setdiff1d(np.arange(len(atoms)), indices)
    remaining = atoms[keep]
    nbrs = neighbours(remaining, removed_pos, removed_num, settings.neighbour_scale)
    b.delete(list(indices))
    markers = [
        _marker(b, pos, settings.vacancy_radius, settings.vacancy_color, i)
        for i, pos in enumerate(removed_pos)
    ]
    symbols = np.array(remaining.get_chemical_symbols())
    for el in sorted(set(symbols[nbrs])):
        idx = [i for i in nbrs if symbols[i] == el]
        b.replace(idx, f"{el}_1")
        b.species[f"{el}_1"].color = srgb_to_linear(settings.neighbour_color) + [1.0]
    return {"removed": len(indices), "neighbours": nbrs, "markers": [m.name for m in markers]}
