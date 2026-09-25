"""Operators: series import, volume animation, vacancy."""

import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from . import defect, series, volume_anim
from .common import active_structure, has_structure


def _progress(context):
    wm = context.window_manager
    if bpy.app.background:
        return None
    wm.progress_begin(0, 100)
    return lambda x: wm.progress_update(int(100 * x))


class BATOMS_OT_import_series(bpy.types.Operator, ImportHelper):
    """Import many structure files (select several) as frames on the timeline.
    Same atoms in every file -> one structure with a trajectory (shared colors
    and formatting); different atoms -> one structure per frame with the
    style of the first. Cube files also bring their volumes"""

    bl_idname = "batoms.import_series"
    bl_label = "Import series"
    bl_options = {"REGISTER", "UNDO"}

    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: StringProperty(subtype="DIR_PATH")
    filter_glob: StringProperty(
        default="*.cube;*.cub;*.xyz;*.extxyz;*.cif;*.vasp;POSCAR*;CONTCAR*;OUTCAR*;*.in;*.pwi;*.out;*.pwo;*.traj",
        options={"HIDDEN"},
    )
    fmt: EnumProperty(name="Format", items=series.FORMATS, default="AUTO")
    target: EnumProperty(
        name="Into",
        items=(
            ("NEW", "New structure", "Create a new structure from the series"),
            ("APPEND", "Append to active", "Add the series after the frames of the active structure"),
        ),
        default="NEW",
    )
    label: StringProperty(name="Name", default="", description="Name of the new structure (default: first file)")
    natural_sort: BoolProperty(name="Natural order", default=True,
                               description="Sort names as 1, 2, ..., 10 (not 1, 10, 2)")
    build_isosurfaces: BoolProperty(
        name="Animate isosurfaces", default=True,
        description="Cube files: build the isosurface animation right away (Volume animation settings)",
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "fmt")
        col.prop(self, "target")
        if self.target == "NEW":
            col.prop(self, "label")
        col.prop(self, "natural_sort")
        col.prop(self, "build_isosurfaces")

    def execute(self, context):
        paths = [os.path.join(self.directory, f.name) for f in self.files if f.name]
        if not paths and self.filepath:
            paths = [self.filepath]
        if not paths:
            self.report({"ERROR"}, "No files selected")
            return {"CANCELLED"}
        paths = sorted(paths, key=series.natural_key) if self.natural_sort else sorted(paths)
        append_to = active_structure(context) if self.target == "APPEND" else None
        if self.target == "APPEND" and append_to is None:
            self.report({"ERROR"}, "Select the structure to append to")
            return {"CANCELLED"}
        try:
            b, rep = series.import_series(paths, self.label or None, self.fmt, append_to)
        except (ValueError, OSError) as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        msg = f"{rep['files']} files -> {rep['total_frames']} frames ({rep['mode']}) in '{rep['label']}'"
        if "volumes" in rep and self.build_isosurfaces and rep["mode"] != "separate":
            s = context.scene.batoms_studio
            try:
                r = volume_anim.build(b, s, _progress(context))
                msg += "; isosurfaces: " + s.anim_report
            except ValueError as err:
                msg += f"; isosurfaces not built: {err}"
            finally:
                if not bpy.app.background:
                    context.window_manager.progress_end()
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class _AnimBase:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return has_structure(context)

    def _structure(self, context):
        from ..batoms import Batoms

        s = context.scene.batoms_studio
        if s.anim_label and s.anim_label in bpy.data.collections:
            return Batoms(s.anim_label)
        return active_structure(context)


class BATOMS_OT_volume_anim_build(_AnimBase, bpy.types.Operator):
    """Build the isosurface animation: align signs, one isovalue, interpolate
    sub-frames (atoms and volumes), one mesh pair per frame, then verify"""

    bl_idname = "batoms.volume_anim_build"
    bl_label = "Build animation"

    def execute(self, context):
        s = context.scene.batoms_studio
        try:
            volume_anim.build(self._structure(context), s, _progress(context))
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        finally:
            if not bpy.app.background:
                context.window_manager.progress_end()
        self.report({"INFO"}, s.anim_report)
        return {"FINISHED"}


class BATOMS_OT_volume_anim_update(_AnimBase, bpy.types.Operator):
    """Re-contour every frame with the current isovalue, colors and quality
    (atoms and timing unchanged)"""

    bl_idname = "batoms.volume_anim_update"
    bl_label = "Update all frames"

    def execute(self, context):
        s = context.scene.batoms_studio
        try:
            volume_anim.update(self._structure(context), s, _progress(context))
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        finally:
            if not bpy.app.background:
                context.window_manager.progress_end()
        self.report({"INFO"}, s.anim_report)
        return {"FINISHED"}


class BATOMS_OT_volume_anim_verify(_AnimBase, bpy.types.Operator):
    """Check that every frame shows exactly its own isosurface pair"""

    bl_idname = "batoms.volume_anim_verify"
    bl_label = "Verify"

    def execute(self, context):
        s = context.scene.batoms_studio
        r = volume_anim.verify(self._structure(context), s)
        s.anim_report = ("All frames OK" if not r["bad_visibility"]
                         else f"Wrong visibility on frames {r['bad_visibility'][:10]}")
        self.report({"INFO"}, s.anim_report)
        return {"FINISHED"}


class BATOMS_OT_make_vacancy(bpy.types.Operator):
    """Remove the selected atoms (Edit Mode), mark each site with a translucent
    sphere and recolor the neighbouring atoms"""

    bl_idname = "batoms.make_vacancy"
    bl_label = "Make vacancy"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return has_structure(context)

    def execute(self, context):
        b = active_structure(context)
        idx = defect.selected_atoms(b)
        if not idx:
            self.report({"ERROR"}, "Select atoms in Edit Mode (Tab, then click atoms)")
            return {"CANCELLED"}
        r = defect.make_vacancies(b, idx, context.scene.batoms_studio)
        self.report({"INFO"}, f"{r['removed']} vacancy(ies), {len(r['neighbours'])} neighbours highlighted")
        return {"FINISHED"}


classes = [
    BATOMS_OT_import_series,
    BATOMS_OT_volume_anim_build,
    BATOMS_OT_volume_anim_update,
    BATOMS_OT_volume_anim_verify,
    BATOMS_OT_make_vacancy,
]
