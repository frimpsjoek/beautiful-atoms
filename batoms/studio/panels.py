"""Sidebar panels: 3D viewport > N > Batoms Studio."""

import bpy

CATEGORY = "Batoms Studio"


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY


class BATOMS_PT_studio_figure(_Base, bpy.types.Panel):
    bl_label = "Publication output"
    bl_order = 1

    def draw(self, context):
        s = context.scene.batoms_studio
        r = context.scene.render
        col = self.layout.column()
        col.operator("batoms.studio_setup_figure", icon="SCENE")
        col.separator()
        col.prop(s, "view")
        row = col.row(align=True)
        row.prop(s, "orthographic", toggle=True)
        row.operator("batoms.studio_frame_camera", icon="VIEW_CAMERA")
        col.separator()
        col.prop(s, "journal")
        if s.journal == "CUSTOM":
            col.prop(s, "width_mm")
        col.prop(s, "dpi")
        from .common import width_pixels

        px, mm = width_pixels(s)
        col.label(text=f"Target: {px} px wide = {mm:g} mm at {s.dpi} dpi", icon="IMAGE_DATA")
        if r.resolution_x != px:
            col.label(text=f"Scene now {r.resolution_x} x {r.resolution_y}: press Set up figure", icon="ERROR")
        col.prop(s, "transparent")
        col.prop(s, "export_path", text="")
        col.operator("batoms.studio_render", icon="RENDER_STILL")
        col.label(text="Animation: Ctrl+F12", icon="RENDER_ANIMATION")


class BATOMS_PT_studio_lights(_Base, bpy.types.Panel):
    bl_label = "Studio"
    bl_order = 2

    def draw(self, context):
        s = context.scene.batoms_studio
        col = self.layout.column()
        row = col.row(align=True)
        row.operator("batoms.studio_build", icon="LIGHT_AREA")
        row.operator("batoms.studio_remove", text="", icon="X")
        box = col.box().column(align=True)
        box.label(text="Look")
        box.row(align=True).prop(s, "look", expand=True)
        if s.look != "STUDIO":
            box.prop(s, "outlines")
            sub = box.column(align=True)
            sub.enabled = s.outlines
            sub.prop(s, "outline_width")
        if s.look == "GOODSELL":
            box.prop(s, "ao_distance")
            box.prop(s, "ao_floor", slider=True)
        box.operator("batoms.studio_apply_look", text="Re-apply after color changes", icon="FILE_REFRESH")
        box = col.box().column(align=True)
        box.label(text="Lights (live)")
        box.prop(s, "exposure", slider=True)
        box.prop(s, "key", slider=True)
        box.prop(s, "fill", slider=True)
        box.prop(s, "rim", slider=True)
        box.prop(s, "light_size")
        box = col.box().column(align=True)
        box.label(text="Ambient & backdrop")
        box.prop(s, "ambient", slider=True)
        box.prop(s, "ambient_color", text="")
        box.prop(s, "backdrop")
        sub = box.column()
        sub.enabled = s.backdrop
        sub.prop(s, "backdrop_color", text="")
        box = col.box().column(align=True)
        box.label(text="Cycles")
        box.prop(s, "samples")
        box.prop(s, "device", expand=True)


class BATOMS_PT_studio_series(_Base, bpy.types.Panel):
    bl_label = "Series import"
    bl_order = 0

    def draw(self, context):
        col = self.layout.column()
        col.operator("batoms.import_series", icon="FILE_FOLDER")
        col.label(text="Select many files (shift / box select)", icon="INFO")
        col.label(text="Append: select the structure first")


class BATOMS_PT_studio_volume(_Base, bpy.types.Panel):
    bl_label = "Volume animation"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.batoms_studio
        col = self.layout.column()
        col.prop(s, "volumes_path", text="")
        if s.anim_label:
            col.label(text=f"Structure: {s.anim_label}", icon="OUTLINER_OB_MESH")
        box = col.box().column(align=True)
        box.label(text="Isovalue")
        box.prop(s, "level", text="Level (0 = auto)")
        sub = box.column()
        sub.enabled = s.level == 0
        sub.prop(s, "enclose", slider=True)
        box.prop(s, "reference")
        box.prop(s, "align_signs")
        box = col.box().column(align=True)
        box.label(text="Colors")
        row = box.row(align=True)
        row.prop(s, "positive_color")
        row.prop(s, "negative_color")
        box.prop(s, "iso_alpha", slider=True)
        box = col.box().column(align=True)
        box.label(text="Timing")
        box.prop(s, "method", text="")
        box.prop(s, "substeps")
        box = col.box().column(align=True)
        box.label(text="Quality")
        box.prop(s, "upsample_to")
        box.prop(s, "smooth")
        box.prop(s, "step_size")
        row = col.row(align=True)
        row.operator("batoms.volume_anim_build", icon="RENDER_ANIMATION")
        row.operator("batoms.volume_anim_update", icon="FILE_REFRESH")
        col.operator("batoms.volume_anim_verify", icon="CHECKMARK")
        if s.anim_report:
            col.label(text=s.anim_report)


class BATOMS_PT_studio_defect(_Base, bpy.types.Panel):
    bl_label = "Defect"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.batoms_studio
        col = self.layout.column()
        col.label(text="Tab into Edit Mode, select atoms", icon="INFO")
        col.prop(s, "vacancy_radius")
        row = col.row(align=True)
        row.prop(s, "vacancy_color")
        row.prop(s, "neighbour_color")
        col.prop(s, "neighbour_scale")
        col.operator("batoms.make_vacancy", icon="MESH_UVSPHERE")


classes = [
    BATOMS_PT_studio_series,
    BATOMS_PT_studio_figure,
    BATOMS_PT_studio_lights,
    BATOMS_PT_studio_volume,
    BATOMS_PT_studio_defect,
]
