"""Scene settings behind the Batoms Studio panels (saved in the .blend).

Sliders with ``update=`` change the scene live: light power, ambient,
backdrop, samples and output size need no rebuild.
"""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)

from . import lighting, looks
from .common import JOURNAL_WIDTHS_MM, VIEWS


def _lights(self, context):
    lighting.update_lights(self)


def _world(self, context):
    lighting.update_world(self)


def _backdrop(self, context):
    lighting.update_backdrop_visibility(self)


def _backdrop_color(self, context):
    lighting.update_backdrop_material(self)


def _render(self, context):
    lighting.update_render(self)


def _look(self, context):
    looks.apply_look(self)


def _output(self, context):
    from .common import width_pixels

    r = context.scene.render
    ratio = r.resolution_y / max(r.resolution_x, 1)
    px, _ = width_pixels(self)
    r.resolution_x = px
    r.resolution_y = max(int(round(px * ratio)), 1)
    r.resolution_percentage = 100


def _transparent(self, context):
    context.scene.render.film_transparent = self.transparent
    if self.transparent and self.backdrop:
        self.backdrop = False  # a visible backdrop would fill the background


INTERP_ITEMS = (
    ("step", "Step", "Hold each frame (no blending)"),
    ("linear", "Linear", "Straight blend at constant speed"),
    ("smoothstep", "Smooth (ease in/out)", "Blend that slows into and out of each key frame"),
    ("cubic", "Cubic (Catmull-Rom)", "Smooth curve through the key frames; can overshoot slightly"),
)


class BatomsStudioSettings(bpy.types.PropertyGroup):
    # ---- studio
    backdrop: BoolProperty(name="Backdrop", default=True, update=_backdrop,
                           description="Seamless sweep behind and under the structure")
    backdrop_color: FloatVectorProperty(name="Backdrop color", subtype="COLOR_GAMMA", size=3,
                                        min=0, max=1, default=(0.92, 0.92, 0.92), update=_backdrop_color)
    ambient: FloatProperty(name="Ambient", default=0.35, min=0, soft_max=2, update=_world,
                           description="World light strength (uniform fill)")
    ambient_color: FloatVectorProperty(name="Ambient color", subtype="COLOR_GAMMA", size=3,
                                       min=0, max=1, default=(1, 1, 1), update=_world)
    exposure: FloatProperty(name="Exposure", default=1.0, min=0, soft_max=4, update=_lights,
                            description="Scales key, fill and rim together (1 = palette-true colors)")
    key: FloatProperty(name="Key", default=1.0, min=0, soft_max=3, update=_lights)
    fill: FloatProperty(name="Fill", default=0.35, min=0, soft_max=2, update=_lights)
    rim: FloatProperty(name="Rim", default=0.8, min=0, soft_max=3, update=_lights)
    light_size: FloatProperty(name="Softness", default=1.0, min=0.05, soft_max=4, update=_lights,
                              description="Light size relative to the structure; larger = softer shadows")
    samples: IntProperty(name="Samples", default=256, min=1, soft_max=2048, update=_render)
    look: EnumProperty(name="Look", items=looks.LOOKS, default="STUDIO", update=_look)
    outlines: BoolProperty(name="Outlines", default=True, update=_look,
                           description="Black silhouettes (Goodsell / Toon)")
    outline_width: FloatProperty(name="Outline width", default=2.0, min=0.1, soft_max=8, update=_look,
                                 description="Line width per 1000 px of image width")
    ao_distance: FloatProperty(name="AO distance", default=2.5, min=0.1, soft_max=10, unit="LENGTH",
                               update=_look, description="Goodsell: how far occlusion reaches (Å)")
    ao_floor: FloatProperty(name="AO darkest", default=0.35, min=0, max=1, update=_look,
                            description="Goodsell: brightness of fully occluded regions")
    device: EnumProperty(name="Device", items=(("GPU", "GPU (Metal)", ""), ("CPU", "CPU", "")),
                         default="GPU", update=_render)
    # ---- publication output
    journal: EnumProperty(
        name="Width",
        items=[(k, v[0], f"{v[1]} mm") for k, v in JOURNAL_WIDTHS_MM.items()]
        + [("CUSTOM", "Custom (mm)", "Set the width in mm")],
        default="NATURE_1", update=_output,
    )
    width_mm: FloatProperty(name="Width (mm)", default=90.0, min=10, max=600, update=_output)
    dpi: IntProperty(name="DPI", default=600, min=72, max=2400, update=_output)
    transparent: BoolProperty(name="Transparent background", default=False, update=_transparent)
    view: EnumProperty(name="View", items=[(k, v[0], v[1]) for k, v in VIEWS.items()], default="AUTO")
    orthographic: BoolProperty(name="Orthographic", default=True)
    export_path: StringProperty(name="Export", subtype="FILE_PATH", default="//figure.png")
    # ---- isosurface / volume animation
    level: FloatProperty(name="Isovalue", default=0.0, min=0, precision=4,
                         description="Absolute isovalue (+/-). 0 = automatic from Enclose")
    enclose: FloatProperty(name="Enclose", default=0.85, min=0.05, max=0.999,
                           description="Automatic isovalue: surface encloses this fraction of the "
                           "weight (|psi|^2 for orbitals, rho for densities) of the reference frame")
    positive_color: FloatVectorProperty(name="+", subtype="COLOR_GAMMA", size=3, min=0, max=1,
                                        default=(1.0, 0.85, 0.0))
    negative_color: FloatVectorProperty(name="-", subtype="COLOR_GAMMA", size=3, min=0, max=1,
                                        default=(0.0, 0.75, 0.85))
    iso_alpha: FloatProperty(name="Opacity", default=0.5, min=0.05, max=1)
    upsample_to: IntProperty(name="Grid", default=120, min=0, soft_max=256,
                             description="Interpolate grids to this many points on the shortest "
                             "axis before contouring (0 = raw grid). Smooths, adds no detail")
    smooth: IntProperty(name="Smooth", default=8, min=0, max=50,
                        description="Smooth modifier iterations on isosurfaces")
    step_size: IntProperty(name="Detail step", default=1, min=1, max=6,
                           description="Marching-cubes step: 1 = full detail, larger = coarser/faster")
    reference: IntProperty(name="Reference frame", default=0, min=0,
                           description="Frame used for sign alignment and the automatic isovalue")
    align_signs: BoolProperty(name="Align signs", default=True,
                              description="Flip each frame to a positive overlap with the reference "
                              "(eigenvector/orbital signs are arbitrary)")
    method: EnumProperty(name="Interpolation", items=INTERP_ITEMS, default="linear")
    substeps: IntProperty(name="Sub-frames", default=1, min=1, max=24,
                          description="Frames per key-frame step (1 = no in-between frames)")
    volumes_path: StringProperty(name="Volumes", subtype="FILE_PATH",
                                 description="Key-frame volumes (.npz) of the active series")
    anim_label: StringProperty(name="Structure", description="Structure the animation belongs to")
    anim_report: StringProperty(name="Report", default="")
    # ---- defect
    vacancy_radius: FloatProperty(name="Marker radius", default=0.9, min=0.1, max=3, unit="LENGTH")
    vacancy_color: FloatVectorProperty(name="Marker", subtype="COLOR_GAMMA", size=3, min=0, max=1,
                                       default=(0.55, 0.75, 0.95))
    neighbour_color: FloatVectorProperty(name="Neighbours", subtype="COLOR_GAMMA", size=3, min=0,
                                         max=1, default=(0.95, 0.55, 0.1))
    neighbour_scale: FloatProperty(name="Cutoff scale", default=1.2, min=0.8, max=2.0,
                                   description="Neighbours within scale x (sum of covalent radii)")
