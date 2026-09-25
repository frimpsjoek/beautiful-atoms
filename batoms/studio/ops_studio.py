"""Operators: studio lighting, camera framing, publication output."""

import bpy
from bpy.props import BoolProperty

from . import lighting
from .common import active_structure, frame_camera, has_structure, structure_objects, view_vector, width_pixels


def _visible_structures(context):
    from ..batoms import Batoms

    return [
        Batoms(o.batoms.label) for o in context.view_layer.objects
        if o.batoms.type == "BATOMS" and o.visible_get()
    ]


def _studio_exists():
    coll = lighting.studio_collection(create=False)
    return bool(coll and coll.objects)


def build_studio_for(context, settings):
    objs = []
    for b in _visible_structures(context):
        objs += structure_objects(b)
    # isosurface meshes of animations / series belong to the structure too
    objs += [o for o in context.view_layer.objects if o.get("iso_frame") == context.scene.frame_current]
    return lighting.build_studio(objs, context.scene.camera, settings)


class BATOMS_OT_frame_camera(bpy.types.Operator):
    """Point and fit the camera to the active structure using the View preset"""

    bl_idname = "batoms.studio_frame_camera"
    bl_label = "Frame camera"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return has_structure(context)

    def execute(self, context):
        s = context.scene.batoms_studio
        b = active_structure(context)
        frame_camera(b, view_vector(s.view, b), s.orthographic)
        if _studio_exists():
            build_studio_for(context, s)  # lights and backdrop follow the camera
        self.report({"INFO"}, f"Camera framed on '{b.label}' ({s.view.lower()})")
        return {"FINISHED"}


class BATOMS_OT_studio_build(bpy.types.Operator):
    """Build (or rebuild) the studio: sweep backdrop, key/fill/rim lights, ambient,
    Cycles. Frames the camera first if the scene has none"""

    bl_idname = "batoms.studio_build"
    bl_label = "Build / update studio"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return has_structure(context)

    def execute(self, context):
        s = context.scene.batoms_studio
        if context.scene.camera is None:
            b = active_structure(context)
            frame_camera(b, view_vector(s.view, b), s.orthographic)
        info = build_studio_for(context, s)
        self.report({"INFO"}, "Studio built (radius {:.1f} Å)".format(info["radius"]))
        return {"FINISHED"}


class BATOMS_OT_studio_remove(bpy.types.Operator):
    """Remove the studio backdrop and lights (restores batoms' own lights)"""

    bl_idname = "batoms.studio_remove"
    bl_label = "Remove studio"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lighting.clear_studio()
        return {"FINISHED"}


class BATOMS_OT_setup_figure(bpy.types.Operator):
    """One click: frame the camera, set the journal-size output and build the studio"""

    bl_idname = "batoms.studio_setup_figure"
    bl_label = "Set up figure"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return has_structure(context)

    def execute(self, context):
        s = context.scene.batoms_studio
        b = active_structure(context)
        frame_camera(b, view_vector(s.view, b), s.orthographic)
        apply_output(context, s)
        build_studio_for(context, s)
        px, mm = width_pixels(s)
        self.report({"INFO"}, f"Figure set up: {px} px = {mm:g} mm at {s.dpi} dpi")
        return {"FINISHED"}


def apply_output(context, s):
    r = context.scene.render
    ratio = r.resolution_y / max(r.resolution_x, 1)
    px, _ = width_pixels(s)
    r.resolution_x, r.resolution_y = px, max(int(round(px * ratio)), 1)
    r.resolution_percentage = 100
    r.film_transparent = s.transparent or not s.backdrop
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA" if r.film_transparent else "RGB"
    r.image_settings.color_depth = "16"
    r.filepath = s.export_path
    lighting.update_render(s)


class BATOMS_OT_render_still(bpy.types.Operator):
    """Render with the publication settings (opens the render window; save
    from Image > Save, the path is preset)"""

    bl_idname = "batoms.studio_render"
    bl_label = "Render"

    write: BoolProperty(name="Write file", default=False,
                        description="Also write the image to the export path")

    def execute(self, context):
        apply_output(context, context.scene.batoms_studio)
        if bpy.app.background or self.write:
            bpy.ops.render.render(write_still=True)
        else:
            bpy.ops.render.render("INVOKE_DEFAULT")
        return {"FINISHED"}


class BATOMS_OT_apply_look(bpy.types.Operator):
    """Re-apply the current look (needed after changing species or isosurface colors)"""

    bl_idname = "batoms.studio_apply_look"
    bl_label = "Apply look"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .looks import apply_look

        apply_look(context.scene.batoms_studio)
        return {"FINISHED"}


classes = [
    BATOMS_OT_apply_look,
    BATOMS_OT_frame_camera,
    BATOMS_OT_studio_build,
    BATOMS_OT_studio_remove,
    BATOMS_OT_setup_figure,
    BATOMS_OT_render_still,
]
