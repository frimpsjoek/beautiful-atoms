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
        col.label(text=f"{r.resolution_x} x {r.resolution_y} px", icon="IMAGE_DATA")
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


classes = [BATOMS_PT_studio_figure, BATOMS_PT_studio_lights]
