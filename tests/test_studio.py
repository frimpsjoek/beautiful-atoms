import bpy
import numpy as np


def _lights():
    return {o["studio_role"]: o for o in bpy.data.collections["studio"].objects if o.type == "LIGHT"}


def test_setup_figure_and_live_sliders(h2o):
    s = bpy.context.scene.batoms_studio
    bpy.context.view_layer.objects.active = h2o.obj
    s.journal, s.dpi = "ACS_1", 600
    assert bpy.ops.batoms.studio_setup_figure() == {"FINISHED"}
    r = bpy.context.scene.render
    assert r.engine == "CYCLES" and r.resolution_x == round(82.5 / 25.4 * 600)
    roles = {o.get("studio_role") for o in bpy.data.collections["studio"].objects}
    assert roles == {"backdrop", "key", "fill", "rim"}
    key0 = _lights()["key"].data.energy
    s.exposure = 2.0  # live update, no rebuild
    assert np.isclose(_lights()["key"].data.energy, 2 * key0)
    s.fill = 0.0
    assert _lights()["fill"].data.energy == 0
    s.backdrop = False
    back = next(o for o in bpy.data.collections["studio"].objects if o.get("studio_role") == "backdrop")
    assert back.hide_render and r.film_transparent
    s.ambient = 0.8
    bg = next(n for n in bpy.context.scene.world.node_tree.nodes if n.type == "BACKGROUND")
    assert np.isclose(bg.inputs["Strength"].default_value, 0.8)
    s.exposure, s.fill, s.backdrop, s.ambient = 1.0, 0.35, True, 0.35


def test_frame_camera_views(h2o):
    s = bpy.context.scene.batoms_studio
    bpy.context.view_layer.objects.active = h2o.obj
    for view in ("TOP", "SIDE_X", "ISO", "AUTO"):
        s.view = view
        assert bpy.ops.batoms.studio_frame_camera() == {"FINISHED"}
    cam = bpy.context.scene.camera
    assert cam is not None and cam.data.type == "ORTHO"


def test_studio_remove_restores(h2o):
    bpy.context.view_layer.objects.active = h2o.obj
    bpy.ops.batoms.studio_build()
    bpy.ops.batoms.studio_remove()
    coll = bpy.data.collections.get("studio")
    assert coll is None or len(coll.objects) == 0


def test_looks_switch_and_restore(h2o):
    s = bpy.context.scene.batoms_studio
    bpy.context.view_layer.objects.active = h2o.obj
    bpy.ops.batoms.studio_setup_figure()
    mats = [m for m in bpy.data.materials if m.node_tree and m.name != "studio_backdrop"]

    def surface_source(m):
        out = next(n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL")
        return out.inputs["Surface"].links[0].from_node

    for look, engine in (("GOODSELL", "CYCLES"), ("TOON", "BLENDER_EEVEE"), ("STUDIO", "CYCLES")):
        s.look = look
        assert bpy.context.scene.render.engine == engine
        assert bpy.context.scene.render.use_freestyle == (look != "STUDIO")
        for m in mats:
            src = surface_source(m)
            if look == "STUDIO":
                assert src.type == "BSDF_PRINCIPLED"
                assert not [n for n in m.node_tree.nodes if n.name.startswith("look_")]
            else:
                assert src.name.startswith("look_")
