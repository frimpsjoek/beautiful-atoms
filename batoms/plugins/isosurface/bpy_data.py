import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    FloatVectorProperty,
    CollectionProperty,
)

from ...internal_data import Base


class IsosurfaceSetting(Base):
    """ """

    flag: BoolProperty(name="flag", default=False)
    name: StringProperty(name="name")
    label: StringProperty(name="label", default="")
    level: FloatProperty(name="level", default=0.10)
    color: FloatVectorProperty(
        name="color",
        size=4,
        subtype="COLOR",
        min=0,
        max=1,
        default=[1, 1, 0, 0.5],
    )
    color1: FloatVectorProperty(
        name="color1", size=4, subtype="COLOR", min=0, max=1, default=[1, 0, 0, 1.0]
    )
    color2: FloatVectorProperty(
        name="color2", size=4, subtype="COLOR", min=0, max=1, default=[0, 0, 1, 1.0]
    )

    def get_volumetric_data(self, context):
        keys = bpy.data.collections[self.label].batoms.settings_volumetric_data.keys()
        # items = [("0", "None", "None")]
        items = []
        i = 1
        for key in keys:
            items.append((key, key, key))
            i += 1
        return items

    volumetric_data: EnumProperty(
        items=get_volumetric_data,
        name="volumetric_data",
        description="choose a volumetric_data",
        default=None,
        update=None,
    )

    def get_color_by(self, context):
        keys = bpy.data.collections[self.label].batoms.settings_volumetric_data.keys()
        items = [("None", "None", "None")]
        i = 1
        for key in keys:
            items.append((key, key, key))
            i += 1
        return items

    color_by: EnumProperty(
        items=get_color_by,
        name="color_by",
        description="color by",
        default=None,
        update=None,
    )

    def as_dict(self) -> dict:
        setdict = {
            "flag": self.flag,
            "label": self.label,
            "name": self.name,
            "volumetric_data": self.volumetric_data,
            "color_by": self.color_by,
            "material_style": self.material_style,
            "color": self.color[:],
            "level": self.level,
        }
        return setdict

    def __repr__(self) -> str:
        s = "-" * 60 + "\n"
        s = "Name    volumetric_data    level        color            \n"
        s += "{0:10s}   {1:10s}  {2:1.6f}  [{3:1.2f}  {4:1.2f}  {5:1.2f}   {6:1.2f}] \n".format(
            self.name,
            self.volumetric_data,
            self.level,
            self.color[0],
            self.color[1],
            self.color[2],
            self.color[3],
        )
        s += "-" * 60 + "\n"
        return s


class Isosurface(bpy.types.PropertyGroup):
    """This module defines the Isosurface properties to extend
    Blender’s internal data.

    """

    active: BoolProperty(name="active", default=False)
    settings: CollectionProperty(name="IsosurfaceSetting", type=IsosurfaceSetting)
    upsample_to: IntProperty(
        name="Grid", default=0, min=0, soft_max=256,
        description="Interpolate the grid to this many points on its shortest axis before "
        "contouring (0 = raw grid). Smooths the surface, adds no detail",
    )
    smooth: IntProperty(name="Smooth", default=8, min=0, max=50,
                        description="Smooth modifier iterations (kept on every redraw)")
    step_size: IntProperty(name="Detail step", default=1, min=1, max=6,
                           description="Marching-cubes step: 1 = full detail, larger = coarser")
    enclose: FloatProperty(
        name="Enclose", default=0.85, min=0.05, max=0.999,
        description="Auto level: surface encloses this fraction of |psi|^2 (signed data) "
        "or of the density",
    )

    ui_list_index: IntProperty(name="ui_list_index", default=0)

    def as_dict(self) -> dict:
        setdict = {}
        return setdict
