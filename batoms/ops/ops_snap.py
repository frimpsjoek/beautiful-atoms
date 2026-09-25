"""Snap a molecule onto a surface (sidebar: Batoms > Snap)."""

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty


def _batoms_root(obj):
    """The structure object for obj (the object itself or its batoms parent)."""
    while obj is not None and obj.batoms.type != "BATOMS":
        obj = obj.parent
    return obj


def _world_atoms(b):
    """Batoms -> clean ase.Atoms with positions/cell in world coordinates.

    Built from symbols/positions/cell/pbc only: as_ase() also exports
    batoms' mesh attributes (including a copy of the positions), which
    Batoms(from_ase=...) would write back over the snapped coordinates.
    """
    from ase import Atoms

    src = b.as_ase(with_attribute=False)
    src = src[0] if isinstance(src, list) else src
    mw = np.array(b.obj.matrix_world)
    return Atoms(
        numbers=src.numbers,
        positions=src.positions @ mw[:3, :3].T + mw[:3, 3],
        cell=np.asarray(src.cell) @ mw[:3, :3].T,
        pbc=src.pbc,
    )


class BATOMS_OT_snap(bpy.types.Operator):
    """Move the active molecule onto the other selected structure until the
    closest atom pair reaches its covalent (bond) or van der Waals contact
    distance; optionally merge both so batoms draws the new bonds"""

    bl_idname = "batoms.snap"
    bl_label = "Snap to surface"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name="Contact",
        items=(
            ("covalent", "Bond (covalent radii)", "Chemisorption: contact at R_i + R_j (covalent)"),
            ("vdw", "van der Waals", "Physisorption: contact at R_i + R_j (vdW, Alvarez)"),
        ),
        default="covalent",
    )
    scale: FloatProperty(
        name="Distance scale", default=1.0, min=0.5, max=2.0,
        description="Multiplies the contact distance (1.1 = 10% longer)",
    )
    merge: BoolProperty(
        name="Merge into one structure", default=True,
        description="Combine both into a new structure so bonds between them are drawn; "
        "the originals are hidden, not deleted",
    )

    @classmethod
    def poll(cls, context):
        roots = {_batoms_root(o) for o in context.selected_objects} - {None}
        return len(roots) == 2 and _batoms_root(context.active_object) in roots

    def execute(self, context):
        from ..batoms import Batoms
        from ..utils.butils import object_mode, world_translate
        from ..utils.snap import snap

        object_mode()
        mol_obj = _batoms_root(context.active_object)
        surf_obj = next(r for r in {_batoms_root(o) for o in context.selected_objects} if r and r != mol_obj)
        mol, surf = Batoms(mol_obj.batoms.label), Batoms(surf_obj.batoms.label)
        try:
            result, info = snap(
                _world_atoms(surf), _world_atoms(mol),
                mode=self.mode, scale=self.scale, merge=self.merge,
            )
        except RuntimeError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        pair = "{}–{}".format(*info["pair_symbols"])
        msg = "{} contact {:.3f} Å (target {:.3f} Å, {})".format(
            pair, info["contact_distance"], info["target"], self.mode
        )
        if not self.merge:
            world_translate(mol_obj, np.array(info["direction"]) * info["travel"])
            self.report({"INFO"}, "Snapped: " + msg)
            return {"FINISHED"}
        label = "{}_{}".format(surf.label, mol.label)
        i = 1
        while label in bpy.data.collections:
            label = "{}_{}_{}".format(surf.label, mol.label, i)
            i += 1
        model_style = surf.model_style
        merged = Batoms(label, from_ase=result)
        merged.model_style = model_style
        for o in (mol_obj, surf_obj):
            for part in [o] + list(o.children_recursive):
                part.hide_set(True)
                part.hide_render = True
        self.report({"INFO"}, "Merged into '{}': {}".format(label, msg))
        return {"FINISHED"}


class BATOMS_PT_snap(bpy.types.Panel):
    bl_label = "Snap"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Batoms"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select surface, then molecule (active)")
        row = layout.row(align=True)
        op = row.operator(BATOMS_OT_snap.bl_idname, text="Snap (bond)")
        op.mode = "covalent"
        op = row.operator(BATOMS_OT_snap.bl_idname, text="Snap (vdW)")
        op.mode = "vdw"
        layout.label(text="Scale / merge: F9 after snapping")
