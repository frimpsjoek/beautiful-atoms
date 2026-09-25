"""Batoms Studio: publication output, studio lighting, series import,
volume animation and defect tools (sidebar tab "Batoms Studio").

Everything here is also usable from Python through the same functions,
so the interface and scripts share one implementation.
"""

import bpy
from bpy.props import PointerProperty

from . import ops_studio, panels, props


def _classes():
    return [props.BatomsStudioSettings] + ops_studio.classes + panels.classes


def register_class():
    for cls in _classes():
        bpy.utils.register_class(cls)
    bpy.types.Scene.batoms_studio = PointerProperty(type=props.BatomsStudioSettings)


def unregister_class():
    del bpy.types.Scene.batoms_studio
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)
