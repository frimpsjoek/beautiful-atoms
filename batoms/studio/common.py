"""Helpers shared by the Batoms Studio operators."""

import bpy
import numpy as np

# Final printed widths in mm (same numbers as the nature-/science-figures skills)
JOURNAL_WIDTHS_MM = {
    "NATURE_1": ("Nature single column", 90.0),
    "NATURE_2": ("Nature double column", 180.0),
    "SCIENCE_1": ("Science single column", 90.0),
    "SCIENCE_15": ("Science 1.5 column", 144.0),
    "SCIENCE_2": ("Science double column", 184.0),
    "ACS_1": ("ACS single column", 82.5),
    "ACS_2": ("ACS double column", 178.0),
    "APS_1": ("APS single column", 86.0),
    "APS_2": ("APS double column", 178.0),
    "RSC_1": ("RSC single column", 83.0),
    "RSC_2": ("RSC double column", 171.0),
}

# View directions: the direction the camera looks *from*
VIEWS = {
    "AUTO": ("Auto", "Widest face of the structure, slightly tilted"),
    "TOP": ("Top (+z)", "Look down the z axis"),
    "BOTTOM": ("Bottom (-z)", "Look up the z axis"),
    "FRONT": ("Front (-y)", "Look along +y"),
    "SIDE_X": ("Side (+x)", "Look along -x"),
    "SIDE_TILT": ("Side tilted", "Slab view: side, tilted down onto the surface"),
    "ISO": ("Isometric", "Oblique 3/4 view"),
}
VIEW_VECTORS = {
    "TOP": (0, 0, 1),
    "BOTTOM": (0, 0, -1),
    "FRONT": (0, -1, 0),
    "SIDE_X": (1, 0, 0),
    "SIDE_TILT": (0.15, -1, 0.55),
    "ISO": (1, -1, 0.8),
}


def batoms_root(obj):
    """The structure object for ``obj`` (itself or its batoms parent)."""
    while obj is not None and obj.batoms.type != "BATOMS":
        obj = obj.parent
    return obj


def has_structure(context):
    """Cheap check for poll(): no Batoms object is built (poll may not write data)."""
    if context.active_object is not None and batoms_root(context.active_object) is not None:
        return True
    return any(o.batoms.type == "BATOMS" for o in context.view_layer.objects)


def active_structure(context):
    """Batoms object of the active selection, else the first visible structure."""
    from ..batoms import Batoms

    root = batoms_root(context.active_object) if context.active_object else None
    if root is None:
        root = next(
            (o for o in context.view_layer.objects if o.batoms.type == "BATOMS" and o.visible_get()),
            None,
        )
    return Batoms(root.batoms.label) if root is not None else None


def structure_objects(b):
    """The structure and its visible helper meshes (for bounding the studio)."""
    objs = [b.obj] + [
        o for o in b.obj.children_recursive
        if o.type == "MESH" and o.batoms.type != "INSTANCER" and not o.hide_render
    ]
    return objs


def auto_view(positions):
    """Along the smallest principal axis, slightly tilted (see the skill)."""
    p = np.asarray(positions, dtype=float)
    if len(p) < 3:
        return (0, 0, 1)
    c = p - p.mean(axis=0)
    _, vecs = np.linalg.eigh(c.T @ c)
    v = vecs[:, 0] + 0.15 * vecs[:, 1] + 0.1 * vecs[:, 2]
    return tuple(v / np.linalg.norm(v))


def view_vector(key, b):
    if key == "AUTO":
        return auto_view(b.positions)
    return VIEW_VECTORS[key]


def frame_camera(b, direction, orthographic=True):
    """batoms' own framing (distance, ortho scale, look-at) without rendering."""
    r = b.render
    r.batoms = b
    r.camera.type = "ORTHO" if orthographic else "PERSP"
    r.viewport = direction
    r.set_viewport_distance_center()
    bpy.context.scene.camera = r.camera.obj
    bpy.context.view_layer.update()
    return r.camera.obj


def width_pixels(settings):
    width_mm = settings.width_mm if settings.journal == "CUSTOM" else JOURNAL_WIDTHS_MM[settings.journal][1]
    return int(round(width_mm / 25.4 * settings.dpi)), width_mm
