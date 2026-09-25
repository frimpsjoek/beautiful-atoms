import bpy


def test_bondpair(ch4):
    """bondpair panel"""
    bpy.context.view_layer.objects.active = ch4.obj
    ch4.coll.Bbond.ui_list_index = 0
    assert ch4.coll.Bbond.ui_list_index == 0
    bpy.ops.bond.bond_pair_add(species1="H", species2="H")
    assert ch4.coll.Bbond.ui_list_index == 2


def test_edit_bonds(ch4):
    """Edit bonds panel"""
    import numpy as np

    ch4.model_style = 1
    # select only the first vertex; foreach_set needs one value per vertex
    select = np.zeros(len(ch4.bond.obj.data.vertices), dtype=bool)
    select[0] = True
    ch4.bond.obj.data.vertices.foreach_set("select", select)
    ch4.bond[0].order = 2
    # order
    ch4.obj.select_set(False)
    bpy.context.view_layer.objects.active = ch4.bond.obj
    assert np.isclose(bpy.context.scene.Bbond.order, ch4.bond[0].order)
    ch4.bond.obj.data.vertices.foreach_set("select", select)
    bpy.context.scene.Bbond.order = 1
    assert np.isclose(ch4.bond[0].order, bpy.context.scene.Bbond.order)
