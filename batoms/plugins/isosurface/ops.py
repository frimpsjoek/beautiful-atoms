import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty, StringProperty
from ...batoms import Batoms
from ...ops.base import OperatorBatoms


class IsosurfaceAdd(OperatorBatoms):
    bl_idname = "surface.isosurface_add"
    bl_label = "Add Isosurface"
    bl_description = "Add Isosurface to a Batoms"

    name: StringProperty(
        name="name", default="2", description="Name of Isosurface to be added"
    )

    def execute(self, context):
        obj = context.object
        batoms = Batoms(label=context.object.batoms.label)
        batoms.isosurface.settings.add(self.name)
        context.view_layer.objects.active = obj
        return {"FINISHED"}


class IsosurfaceRemove(OperatorBatoms):
    bl_idname = "surface.isosurface_remove"
    bl_label = "Remove Isosurface"
    bl_description = "Remove Isosurface to a Batoms"

    name: StringProperty(
        name="name", default="1-1-1", description="Name of Isosurface to be removed"
    )

    all: BoolProperty(name="all", default=False, description="Remove all Isosurfaces")

    def execute(self, context):
        obj = context.object
        batoms = Batoms(label=obj.batoms.label)
        batoms.isosurface.settings.remove((self.name))
        context.view_layer.objects.active = obj
        return {"FINISHED"}


class IsosurfaceDraw(OperatorBatoms):
    bl_idname = "surface.isosurface_draw"
    bl_label = "Draw Isosurface"
    bl_description = "Draw Isosurface to a Batoms"

    name: StringProperty(
        name="name", default="ALL", description="Name of Isosurface to be drawed"
    )

    def execute(self, context):
        obj = context.object
        batoms = Batoms(label=obj.batoms.label)
        batoms.isosurface.draw(self.name)
        context.view_layer.objects.active = batoms.obj
        return {"FINISHED"}


class IsosurfaceAutoLevel(OperatorBatoms):
    bl_idname = "surface.isosurface_auto_level"
    bl_label = "Auto level"
    bl_description = (
        "Set the isovalue so the surface encloses the Enclose fraction of the weight "
        "(|psi|^2 for orbitals, density otherwise). For signed data positive and "
        "negative rows get +/-level (a negative row is added if missing). Then draws"
    )

    def execute(self, context):
        from .isosurface import enclosing_level

        batoms = Batoms(label=context.object.batoms.label)
        iso = batoms.coll.Bisosurface
        names = list(batoms.volumetric_data.keys()) if hasattr(batoms.volumetric_data, "keys") else []
        if not names:
            self.report({"ERROR"}, "No volumetric data on this structure")
            return {"CANCELLED"}
        rows = iso.settings
        vol_name = (rows[iso.ui_list_index].volumetric_data if len(rows) else "") or names[0]
        level, signed = enclosing_level(batoms.volumetric_data[vol_name], iso.enclose)
        if len(rows) == 0:
            batoms.isosurface.settings["positive"] = {"level": level, "volumetric_data": vol_name}
        if signed and not any(r.level < 0 for r in rows):
            batoms.isosurface.settings["negative"] = {
                "level": -level, "color": [0.0, 0.52, 0.69, 0.5], "volumetric_data": vol_name,
            }
        for r in batoms.coll.Bisosurface.settings:
            r.level = -level if r.level < 0 else level
        batoms.isosurface.draw()
        self.report(
            {"INFO"},
            "Isovalue {}{:.4g} (encloses {:.0%} of {})".format(
                "+/-" if signed else "", level, iso.enclose, "|psi|^2" if signed else "the density"
            ),
        )
        return {"FINISHED"}


class IsosurfaceModify(Operator):
    bl_idname = "surface.isosurface_modify"
    bl_label = "Modify Isosurface"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Modify Isosurface"

    key: StringProperty(
        name="key", default="style", description="Replaced by this species"
    )

    slice: BoolProperty(
        name="slice",
        default=False,
    )
    boundary: BoolProperty(
        name="boundary",
        default=False,
    )
    distance: FloatProperty(
        name="distance", description="Distance from origin", default=1
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj:
            return obj.batoms.type == "MS" and obj.mode == "EDIT"
        else:
            return False

    def execute(self, context):
        obj = context.object
        data = obj.data
        bm = bmesh.from_edit_mesh(data)
        v = [s.index for s in bm.select_history if isinstance(s, bmesh.types.BMVert)]
        batoms = Batoms(label=obj.batoms.label)
        for i in v:
            setattr(batoms.bonds[i], self.key, getattr(self, self.key))
        # batoms.draw()
        return {"FINISHED"}
