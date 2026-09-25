import bpy
import numpy as np
import os

path = os.path.dirname(os.path.abspath(__file__))

try:
    from _common_helpers import use_cycles, set_cycles_res

    use_cycles = not use_cycles()
except ImportError:
    use_cycles = False

extras = dict(engine="cycles") if use_cycles else {}


def test_settings(h2o_homo):
    """key search"""
    h2o = h2o_homo
    h2o.isosurface.settings["1"] = {"level": -0.001}
    h2o.isosurface.settings["2"] = {"level": 0.001, "color": [0, 0, 0.8, 0.5]}
    assert len(h2o.isosurface.settings) == 2
    assert h2o.isosurface.settings.find("1") is not None
    assert h2o.isosurface.settings.find(1) is not None
    h2o.isosurface.settings.remove("1")
    assert h2o.isosurface.settings.find("1") is None


# def test_slice():
#     bpy.ops.batoms.delete()
#     h2o = read(os.path.join(path, "datas/h2o-homo.cube"))
#     h2o.isosurface.settings["1"] = {"level": -0.001}
#     h2o.isosurface.settings["2"] = {"level": 0.001, "color": [0, 0, 0.8, 0.5]}
#     h2o.isosurface.draw()
#     h2o.lattice_plane.settings[(1, 0, 0)] = {"distance": 6, "slicing": True}
#     h2o.lattice_plane.draw()
#     if use_cycles:
#         set_cycles_res(h2o)
#     h2o.get_image([0, 0, 1], **extras)


def test_color_by(h2o_homo):
    from ase.io.cube import read_cube_data

    h2o = h2o_homo
    bpy.context.view_layer.objects.active = h2o.obj
    hartree, _atoms = read_cube_data(os.path.join(path, "datas/h2o-hartree.cube"))
    h2o.volumetric_data["hartree"] = -hartree
    bpy.ops.surface.isosurface_add(name="positive")
    h2o.isosurface.settings["positive"].level = 0.001
    h2o.isosurface.settings["positive"].color_by = "hartree"
    bpy.ops.surface.isosurface_draw()


def test_diff(h2o_homo):
    h2o = h2o_homo
    volume = h2o.volumetric_data["h2o_homo"]
    h2o.volumetric_data["h2o_homo"] = volume + 0.1
    assert np.allclose(h2o.volumetric_data["h2o_homo"], volume + 0.1)
    h2o.isosurface.settings["positive"] = {"level": 0.008, "color": [1, 1, 0, 0.8]}
    h2o.isosurface.settings["negative"] = {"level": -0.008, "color": [0, 0, 1, 0.8]}
    h2o.model_style = 1
    h2o.isosurface.draw()
    if use_cycles:
        set_cycles_res(h2o)
    else:
        h2o.render.resolution = [200, 200]
    h2o.get_image([0, 0, 1], output="h2o-homo-diff-top.png", **extras)
    h2o.get_image([1, 0, 0], output="h2o-homo-diff-side.png", **extras)


def test_isosurface_ops(h2o_homo):
    h2o = h2o_homo
    bpy.context.view_layer.objects.active = h2o.obj
    bpy.ops.surface.isosurface_draw()
    assert len(h2o.isosurface.settings) == 0
    bpy.ops.surface.isosurface_add(name="positive")
    assert len(h2o.isosurface.settings) == 1
    bpy.ops.surface.isosurface_draw()


def test_isosurface_uilist(h2o_homo):
    """isosurface panel"""
    h2o = h2o_homo
    bpy.context.view_layer.objects.active = h2o.obj
    h2o.obj.select_set(True)
    assert h2o.coll.Bisosurface.ui_list_index == 0
    bpy.ops.surface.isosurface_add(name="positive")
    assert h2o.coll.Bisosurface.ui_list_index == 0
    bpy.ops.surface.isosurface_add(name="negative")
    assert h2o.coll.Bisosurface.ui_list_index == 1


def test_draw_single(h2o_homo):
    """draw() with a setting name draws only that isosurface (used to crash on name.name)"""
    h2o = h2o_homo
    h2o.isosurface.settings["1"] = {"level": -0.001}
    h2o.isosurface.settings["2"] = {"level": 0.001, "color": [0, 0, 0.8, 0.5]}
    h2o.isosurface.draw("2")
    names = [o.name for o in bpy.data.objects if o.batoms.type == "ISOSURFACE"]
    assert names == [f"{h2o.label}_isosurface_2"]


def _iso_objects(label):
    return {o.name: o for o in bpy.data.objects if o.batoms.type == "ISOSURFACE" and o.batoms.label == label}


def test_quality_and_auto_level(h2o_homo):
    """Upsampling, detail step, persistent smoothing, automatic +/- level."""
    from batoms.plugins.isosurface.isosurface import enclosing_level

    h2o = h2o_homo
    q = h2o.coll.Bisosurface
    h2o.isosurface.settings["1"] = {"level": 0.05}
    q.upsample_to, q.smooth, q.step_size = 0, 0, 1
    h2o.isosurface.draw()
    raw = len(next(iter(_iso_objects(h2o.label).values())).data.vertices)
    q.upsample_to = 60
    h2o.isosurface.draw()
    fine = len(next(iter(_iso_objects(h2o.label).values())).data.vertices)
    assert fine > raw
    q.step_size = 2
    h2o.isosurface.draw()
    coarse = len(next(iter(_iso_objects(h2o.label).values())).data.vertices)
    assert coarse < fine
    q.step_size, q.smooth = 1, 6
    h2o.isosurface.draw()
    h2o.isosurface.draw()  # smoothing must survive a redraw
    obj = next(iter(_iso_objects(h2o.label).values()))
    assert obj.modifiers["iso_smooth"].iterations == 6
    # auto level: signed orbital -> +/- rows at the enclosing level
    bpy.context.view_layer.objects.active = h2o.obj
    assert bpy.ops.surface.isosurface_auto_level() == {"FINISHED"}
    vol = h2o.volumetric_data[list(h2o.volumetric_data.keys())[0]]
    level, signed = enclosing_level(vol, q.enclose)
    assert signed
    levels = sorted(r.level for r in q.settings)
    assert np.allclose(levels, [-level, level])
    assert len(_iso_objects(h2o.label)) == 2
