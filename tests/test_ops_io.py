import os

import bpy

path = os.path.dirname(os.path.abspath(__file__))


def test_import_from_edit_mode():
    """Import must work while another object is in Edit Mode.

    Regression: building species instancers called
    ``bpy.ops.object.shade_smooth`` / ``primitive_uv_sphere_add``, which fail
    or edit the wrong mesh outside Object Mode.
    """
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    bpy.ops.object.mode_set(mode="EDIT")
    getattr(bpy.ops.batoms, "import")(
        filepath=os.path.join(path, "datas/tio2.cif"), label="tio2_io"
    )
    assert "tio2_io" in bpy.data.objects
    # the cube mesh must not have received the instancer sphere geometry
    assert len(cube.data.vertices) == 8
    for obj in bpy.data.objects:
        if obj.batoms.type == "INSTANCER" and obj.type == "MESH":
            assert all(p.use_smooth for p in obj.data.polygons)
    bpy.ops.batoms.delete(label="tio2_io")
    bpy.data.objects.remove(cube)
