import bpy
from batoms.cell import Bcell
import numpy as np


def test_cell(au):
    """ """
    cell = au.cell
    assert isinstance(cell, Bcell)


def test_cell_transform(au):
    au.cell = [2, 2, 2]
    au.cell[2, 2] += 5
    assert au.cell[2, 2] == 7
    au.cell.translate([0, 0, 2])
    assert au.cell[2, 2] == 7
    assert au.cell.global_positions[3, 2] == 9
    # au.cell.rotate(np.pi/4, 'Z')
    # assert au.cell[2, 2] == 7
    # assert au.cell.positions[3, 2] == 9


def test_repeat(au):
    au.cell = [2, 2, 2]
    # au.cell.rotate(np.pi/4, 'Z')
    au.cell.repeat([2, 2, 2])
    assert np.allclose(au.cell.array, np.array([[4, 0, 0], [0, 4, 0], [0, 0, 4]]))


def test_translate_repeat(au):
    au.cell = [2, 2, 2]
    au.cell.translate([0, 0, 2])
    au.cell.repeat([2, 2, 2])
    assert np.allclose(au.cell.array, np.array([[4, 0, 0], [0, 4, 0], [0, 0, 4]]))


def test_copy(au):
    au.cell = [2, 2, 2]
    cell2 = au.cell.copy("au-2")
    assert isinstance(cell2, Bcell)
    reciprocal = au.cell.reciprocal
    assert np.isclose(reciprocal[0, 0], 3.14159)


def test_draw(au):
    au.cell = [2, 2, 2]
    au.cell.width = 0.1
    au.cell.color = [1, 0, 0, 1]


def test_bond_reload(au):
    """save to blend file and reload"""
    import os
    from batoms import Batoms

    au.cell.width = 0.01
    au.cell.color = [1, 0, 0, 0.5]
    cwd = os.getcwd()
    filepath = os.path.join(cwd, "test.blend")
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    bpy.ops.batoms.delete()
    bpy.ops.wm.open_mainfile(filepath=filepath)
    au = Batoms("au")
    assert np.isclose(au.cell.width, 0.01)
    assert np.isclose(au.cell.color, np.array([1, 0, 0, 0.5])).all()


def test_helpers_locked_to_structure(tio2):
    """Cell, boundary, bonds, polyhedra must move only with the structure.

    Regression: grabbing the cell (G) moved it away from the atoms and the
    periodic images, which stayed behind.
    """
    tio2.boundary = [0.01, 0.01, 0.01]
    tio2.model_style = 2
    children = [o for o in tio2.obj.children_recursive if o.batoms.type != "INSTANCER"]
    assert {o.batoms.type for o in children} >= {"CELL", "BOUNDARY", "BOND", "POLYHEDRA"}
    for o in children:
        assert all(o.lock_location) and all(o.lock_rotation) and all(o.lock_scale), o.name
    # what "G" does: translate the selected cell with the transform operator
    cell = tio2.cell.obj
    bpy.ops.object.select_all(action="DESELECT")
    cell.select_set(True)
    bpy.context.view_layer.objects.active = cell
    before = cell.matrix_world.translation.copy()
    with bpy.context.temp_override(selected_editable_objects=[cell], selected_objects=[cell], active_object=cell, object=cell):
        bpy.ops.transform.translate(value=(2.0, 0.0, 0.0))
    assert (cell.matrix_world.translation - before).length < 1e-6
