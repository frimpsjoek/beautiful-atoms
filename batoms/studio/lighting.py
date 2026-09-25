"""Procedural studio: seamless sweep backdrop, three-point lighting, ambient.

Everything is computed from the structure's bounding sphere and the scene
camera, so any view (top, side, oblique) gets a consistent look. Studio
objects live in the "studio" collection and carry custom properties:
``studio_role`` (backdrop/key/fill/rim) and, for lights, ``studio_base``
(power at exposure 1, weight 1), so the panel sliders can re-scale them
live without rebuilding.
"""

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROLES = ("key", "fill", "rim")


def srgb_to_linear(c):
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c[:3]]


def bounding_sphere(objs):
    """Center and radius (Å) of the evaluated geometry of ``objs``."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for obj in objs:
        ev = obj.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        mw = obj.matrix_world
        pts += [mw @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    pts = np.array(pts) if pts else np.zeros((1, 3))
    center = pts.mean(axis=0)
    radius = float(np.linalg.norm(pts - center, axis=1).max()) + 1.5  # atom radius margin
    return Vector(center), max(radius, 2.0)


def camera_frame(camera):
    """(right, up, toward_camera) unit vectors of the camera in world space."""
    m = camera.matrix_world.to_3x3()
    return (
        (m @ Vector((1, 0, 0))).normalized(),
        (m @ Vector((0, 1, 0))).normalized(),
        (m @ Vector((0, 0, 1))).normalized(),
    )


def studio_collection(create=True):
    coll = bpy.data.collections.get("studio")
    if coll is None and create:
        coll = bpy.data.collections.new("studio")
        bpy.context.scene.collection.children.link(coll)
    return coll


def clear_studio():
    coll = studio_collection(create=False)
    if coll:
        for obj in list(coll.objects):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Light):
                    bpy.data.lights.remove(data)
    for obj in bpy.data.objects:  # re-enable lights muted by a previous build
        if obj.type == "LIGHT" and obj.get("muted_by_studio"):
            obj.hide_render = obj.hide_viewport = False
            del obj["muted_by_studio"]


def build_backdrop(center, radius, right, up, toward, settings):
    """Sweep mesh in a camera-aligned frame: x=right, y=away from camera, z=up."""
    floor_z = -1.15 * radius
    wall_y = 1.6 * radius
    cove = 1.2 * radius
    width = 8.0 * radius
    front = -6.0 * radius
    height = 6.0 * radius
    profile = [(front, floor_z), (wall_y - cove, floor_z)]
    for t in np.linspace(-np.pi / 2, 0, 24)[1:]:
        profile.append((wall_y - cove + cove * np.cos(t), floor_z + cove + cove * np.sin(t)))
    profile.append((wall_y, floor_z + height))
    bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for y, z in profile] for x in (-width / 2, width / 2)]
    for i in range(len(profile) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    me = bpy.data.meshes.new("studio_backdrop")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    obj = bpy.data.objects.new("studio_backdrop", me)
    basis = Matrix((right, -toward, up)).transposed()
    obj.matrix_world = Matrix.Translation(center) @ basis.to_4x4()
    mat = bpy.data.materials.get("studio_backdrop") or bpy.data.materials.new("studio_backdrop")
    me.materials.append(mat)
    obj["studio_role"] = "backdrop"
    obj.hide_select = True  # clicks go to the structure
    obj.hide_render = obj.hide_viewport = not settings.backdrop
    studio_collection().objects.link(obj)
    update_backdrop_material(settings)
    return obj


def build_lights(center, radius, right, up, toward, settings):
    """Key / fill / rim disk area lights aimed at the structure.

    Power ~ distance^2 keeps the irradiance independent of structure size;
    7 W * d^2 (d in Å) makes a key-lit sphere's mid-tone match its palette
    color at exposure 1 with the default ambient (measured with Jmol Cu).
    """
    d = 3.0 * radius
    rigs = {
        "key": ((toward + 0.9 * right + 0.8 * up).normalized(), d),
        "fill": ((toward - 1.0 * right + 0.15 * up).normalized(), d),
        "rim": ((-toward + 0.35 * right + 1.1 * up).normalized(), 1.4 * radius),
    }
    for role, (direction, dist) in rigs.items():
        data = bpy.data.lights.new(f"studio_{role}", "AREA")
        data.shape = "DISK"
        obj = bpy.data.objects.new(f"studio_{role}", data)
        obj.location = center + direction * dist
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
        obj["studio_role"] = role
        obj["studio_base"] = 7.0 * dist * dist
        obj["studio_radius"] = radius
        studio_collection().objects.link(obj)
    update_lights(settings)


# ---------------------------------------------------------------- live updates
def studio_objects():
    coll = studio_collection(create=False)
    return list(coll.objects) if coll else []


def update_lights(settings):
    weights = {"key": settings.key, "fill": settings.fill, "rim": settings.rim}
    for obj in studio_objects():
        role = obj.get("studio_role")
        if role in weights:
            obj.data.energy = obj["studio_base"] * weights[role] * settings.exposure
            obj.data.size = settings.light_size * obj["studio_radius"]


def update_backdrop_material(settings):
    mat = bpy.data.materials.get("studio_backdrop")
    if mat is None:
        return
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb_to_linear(settings.backdrop_color) + [1.0]
    bsdf.inputs["Roughness"].default_value = 0.9


def update_backdrop_visibility(settings):
    for obj in studio_objects():
        if obj.get("studio_role") == "backdrop":
            obj.hide_render = obj.hide_viewport = not settings.backdrop
    bpy.context.scene.render.film_transparent = not settings.backdrop


def update_world(settings):
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    nodes = world.node_tree.nodes
    bg = next((n for n in nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        bg = nodes.new("ShaderNodeBackground")
        out = next(n for n in nodes if n.type == "OUTPUT_WORLD")
        world.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs["Color"].default_value = srgb_to_linear(settings.ambient_color) + [1.0]
    bg.inputs["Strength"].default_value = settings.ambient


def update_render(settings):
    scene = bpy.context.scene
    if getattr(settings, "look", "STUDIO") == "TOON":
        # Shader-to-RGB (toon bands) only works in EEVEE
        scene.render.engine = "BLENDER_EEVEE_NEXT" if (4, 2, 0) <= bpy.app.version < (5, 0, 0) else "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = min(settings.samples, 128)
    else:
        scene.render.engine = "CYCLES"
    scene.cycles.samples = settings.samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.cycles.device = "CPU"
    if settings.device == "GPU":
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for dev in prefs.devices:
                dev.use = True
            scene.cycles.device = "GPU"
        except Exception:
            pass


def mute_other_lights():
    """batoms adds its own lights; the three-point rig replaces them."""
    for obj in bpy.data.objects:
        if obj.type == "LIGHT" and "studio_role" not in obj.keys() and not obj.hide_render:
            obj.hide_render = obj.hide_viewport = True
            obj["muted_by_studio"] = True


def build_studio(structure_objs, camera, settings):
    """(Re)build backdrop + lights around ``structure_objs`` for ``camera``."""
    clear_studio()
    center, radius = bounding_sphere(structure_objs)
    right, up, toward = camera_frame(camera)
    build_backdrop(center, radius, right, up, toward, settings)
    build_lights(center, radius, right, up, toward, settings)
    update_world(settings)
    update_render(settings)
    update_backdrop_visibility(settings)
    mute_other_lights()
    camera.data.clip_end = max(
        camera.data.clip_end, (camera.matrix_world.translation - center).length + 20 * radius
    )
    return {"center": list(center), "radius": radius}
