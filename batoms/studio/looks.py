"""Shading looks: Studio (physically based), Goodsell, Toon.

Non-destructive: every material keeps its Principled BSDF; a look adds nodes
named "look_*" next to it and re-routes the Material Output. Switching back
to Studio reconnects the Principled BSDF and removes the look nodes.

- Studio:   Principled BSDF lit by the three-point rig (Cycles).
- Goodsell: flat color darkened by ambient occlusion (crevices and contacts
            go dark) + black outlines. Emission-based, so it ignores lights,
            like David Goodsell's illustrations (Cycles).
- Toon:     diffuse lighting quantized into 3 bands x color (cel shading)
            + outlines. Uses Shader-to-RGB, which only EEVEE supports.
Outlines: Freestyle silhouettes; width scales with the render resolution;
the studio backdrop is excluded.
"""

import bpy

LOOKS = (
    ("STUDIO", "Studio", "Physically based shading lit by the three-point rig (Cycles)"),
    ("GOODSELL", "Goodsell", "Flat colors darkened by ambient occlusion, black outlines (Cycles)"),
    ("TOON", "Toon", "Cel shading in three bands with outlines (EEVEE)"),
)


def _materials():
    """Materials of the molecular scene (everything but the studio backdrop)."""
    return [m for m in bpy.data.materials if m.node_tree and m.name != "studio_backdrop"]


def _principled(nt):
    return next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)


def _output(nt):
    return next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None) or next(
        (n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None
    )


def _clear_look_nodes(nt):
    for n in [n for n in nt.nodes if n.name.startswith("look_")]:
        nt.nodes.remove(n)


def _color_source(nt, bsdf):
    """Socket carrying the base color (its link if colored by attribute, else an RGB node)."""
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        return base.links[0].from_socket
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.name = "look_color"
    rgb.outputs[0].default_value = base.default_value
    rgb.location = bsdf.location.x - 300, bsdf.location.y + 250
    return rgb.outputs[0]


def _with_alpha(nt, shader_socket, bsdf, out):
    """Keep the material's transparency (isosurfaces) with a transparent mix."""
    alpha = bsdf.inputs["Alpha"].default_value
    if alpha >= 0.999:
        nt.links.new(shader_socket, out.inputs["Surface"])
        return
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.name = "look_transparent"
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = "look_alpha"
    mix.inputs["Fac"].default_value = alpha
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(shader_socket, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def _goodsell(nt, bsdf, out, settings):
    color = _color_source(nt, bsdf)
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.name = "look_ao"
    ao.samples = 16
    ao.inputs["Distance"].default_value = settings.ao_distance
    # soften: color * (floor + (1 - floor) * AO)
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.name = "look_ao_range"
    ramp.inputs["To Min"].default_value = settings.ao_floor
    mul = nt.nodes.new("ShaderNodeMix")
    mul.name = "look_ao_mul"
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "look_emit"
    nt.links.new(color, ao.inputs["Color"])
    nt.links.new(ao.outputs["AO"], ramp.inputs["Value"])
    nt.links.new(color, mul.inputs["A"])
    nt.links.new(ramp.outputs["Result"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], emit.inputs["Color"])
    _with_alpha(nt, emit.outputs[0], bsdf, out)


def _toon(nt, bsdf, out, settings):
    color = _color_source(nt, bsdf)
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diff.name = "look_diffuse"
    to_rgb = nt.nodes.new("ShaderNodeShaderToRGB")
    to_rgb.name = "look_to_rgb"
    bands = nt.nodes.new("ShaderNodeValToRGB")
    bands.name = "look_bands"
    cr = bands.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.35, 0.35, 0.35, 1)
    cr.elements[1].position, cr.elements[1].color = 0.25, (0.7, 0.7, 0.7, 1)
    top = cr.elements.new(0.6)
    top.color = (1.0, 1.0, 1.0, 1)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.name = "look_band_mul"
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "look_emit"
    nt.links.new(diff.outputs[0], to_rgb.inputs[0])
    nt.links.new(to_rgb.outputs["Color"], bands.inputs["Fac"])
    nt.links.new(color, mul.inputs["A"])
    nt.links.new(bands.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], emit.inputs["Color"])
    _with_alpha(nt, emit.outputs[0], bsdf, out)


def _outlines(settings, enable):
    scene = bpy.context.scene
    scene.render.use_freestyle = enable
    if not enable:
        return
    scene.render.line_thickness_mode = "ABSOLUTE"
    scale = max(scene.render.resolution_x * scene.render.resolution_percentage / 100, 1) / 1000
    scene.render.line_thickness = settings.outline_width * scale
    fs = scene.view_layers[0].freestyle_settings
    ls = fs.linesets.get("batoms_outline") or fs.linesets.new("batoms_outline")
    for other in fs.linesets:
        other.show_render = other.name == "batoms_outline"
    ls.select_by_visibility = True
    ls.select_by_edge_types = True
    ls.select_silhouette = ls.select_border = ls.select_external_contour = True
    ls.select_crease = False
    studio = bpy.data.collections.get("studio")
    ls.select_by_collection = studio is not None
    if studio is not None:
        ls.collection = studio
        ls.collection_negation = "EXCLUSIVE"
    ls.linestyle.color = (0.02, 0.02, 0.02)
    ls.linestyle.thickness = 1.0


def apply_look(settings):
    """Apply ``settings.look`` to every molecular material; set engine/outlines."""
    look = settings.look
    for mat in _materials():
        nt = mat.node_tree
        bsdf, out = _principled(nt), _output(nt)
        if bsdf is None or out is None:
            continue
        _clear_look_nodes(nt)
        if look == "STUDIO":
            nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
        elif look == "GOODSELL":
            _goodsell(nt, bsdf, out, settings)
        else:
            _toon(nt, bsdf, out, settings)
    _outlines(settings, look != "STUDIO" and settings.outlines)
    from .lighting import update_render

    update_render(settings)  # engine follows the look (Toon -> EEVEE)
