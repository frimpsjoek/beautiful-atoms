"""

1) set custom file folder.
2) use default startup of batoms.
3) use default preferences of batoms.
#TODO  batoms_setting_path_update
"""

import bpy
from bpy.types import AddonPreferences
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
)
from .logger import update_logging_level
import logging
from .utils import subprocess_run
from .utils.butils import get_preferences_addon

logger = logging.getLogger(__name__)


# Enum property.
logging_level_items = [
    ("DEBUG", "DEBUG", "", 0),
    ("INFO", "INFO", "", 1),
    ("WARNING", "WARNING", "", 2),
    ("ERROR", "ERROR", "", 3),
    ("CRITICAL", "CRITICAL", "", 4),
]

dependencies = {
    "ase": "ase",
    "scikit-image": "skimage",
    "spglib": "spglib",
    "pymatgen": "pymatgen",
    "openbabel": "openbabel",
}


DEFAULT_GITHUB_ACCOUNT = "beautiful-atoms"
DEFAULT_REPO_NAME = "beautiful-atoms"
DEFAULT_PLUGIN_NAME = "batoms"


def update_plugin(key):
    """Build an update callback that (un)registers plugin ``key``.

    Blender >= 5.0 no longer exposes ``bpy.props`` values through
    dict-style access (``self[key]``), so the value is kept in the
    property's own storage and only the side effect lives here.
    """

    def update(self, context):
        import importlib

        plugin = importlib.import_module(".plugins.{}".format(key), package=__package__)
        if getattr(self, key):
            plugin.register_class()
            logger.info("Enable {} plugin.".format(key))
        else:
            plugin.unregister_class()
            logger.info("Disable {} plugin.".format(key))

    return update


class BatomsDefaultPreference(bpy.types.Operator):
    """Update Batoms"""

    bl_idname = "batoms.use_batoms_preference"
    bl_label = "Use defatul preference of Batoms"
    bl_description = "Use startup file of Batoms"

    def execute(self, context):
        import pathlib
        import os

        batoms_asset_dir = os.path.join(
            pathlib.Path(__file__).parent.resolve(), "asset"
        )
        batoms_asset_dir = os.path.join(batoms_asset_dir, "libraries")

        bpy.context.scene.unit_settings.system = "NONE"
        #
        bpy.context.preferences.view.use_translate_new_dataname = False
        bpy.context.preferences.inputs.use_rotate_around_active = True
        bpy.context.preferences.inputs.use_zoom_to_mouse = True
        # For laptop
        bpy.context.preferences.inputs.use_emulate_numpad = True
        # For laptop without mouse
        bpy.context.preferences.inputs.use_mouse_emulate_3_button = True
        # bpy.context.window.workspace = bpy.data.workspaces['UV Editing']
        # theme
        bpy.context.preferences.themes[
            0
        ].view_3d.space.gradients.background_type = "LINEAR"
        bpy.context.preferences.themes[0].view_3d.space.gradients.high_gradient = (
            0.9,
            0.9,
            0.9,
        )
        bpy.context.preferences.themes[0].view_3d.space.gradients.gradient = (
            0.5,
            0.5,
            0.5,
        )
        bpy.ops.wm.save_userpref()
        # logger
        get_preferences_addon().preferences.logging_level = "WARNING"
        # asset_libraries
        if "Batoms" not in bpy.context.preferences.filepaths.asset_libraries.keys():
            bpy.ops.preferences.asset_library_add(directory=batoms_asset_dir)
            bpy.context.preferences.filepaths.asset_libraries[-1].name = "Batoms"
        self.report({"INFO"}, "Set default preferences successfully!")
        return {"FINISHED"}


class BatomsDefaultStartup(bpy.types.Operator):
    """Update Batoms"""

    bl_idname = "batoms.use_batoms_startup"
    bl_label = "Use startup file of Batoms"
    bl_description = "Use defatul startup of Batoms"

    def execute(self, context):
        import os
        import pathlib

        addon_dir = pathlib.Path(__file__).parent.resolve()
        blend_dir = os.path.join(addon_dir, "data/startup.blend")
        bpy.ops.wm.open_mainfile(filepath=blend_dir, load_ui=True, use_scripts=True)
        ###################################################
        # Add additional settings to the startup file here
        ###################################################
        # viewport overlayrs
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.overlay.show_extras = False
                        space.overlay.show_relationship_lines = False
                        break
        ###################################################
        bpy.ops.wm.save_homefile()
        self.report({"INFO"}, "Load default startup successfully!")
        # todo open preference again.
        # bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        # bpy.ops.preferences.addon_show(module="batoms")
        return {"FINISHED"}


class BatomsAddonPreferences(AddonPreferences):
    bl_idname = __package__

    def logging_level_update(self, context):
        # Set the logging level for all child loggers of "batoms"
        update_logging_level()
        # Note the following logging info might not emit
        # if global level is higher than INFO
        logger.info("Set logging level to: {}".format(self.logging_level))

    def batoms_setting_path_update(self, context):
        import os

        if os.name == "posix":  # Linux
            cmds = ["export", "BATOMS_SETTING_PATH={}".format(self.batoms_setting_path)]
        if os.name == "nt":  # Windows
            cmds = ["setx", "BATOMS_SETTING_PATH {}".format(self.batoms_setting_path)]
        logger.debug(subprocess_run(cmds))

    batoms_setting_path: StringProperty(
        name="Custom Setting Path",
        description="Custom Setting Path",
        default="",
        subtype="FILE_PATH",
        update=batoms_setting_path_update,
    )

    logging_level: EnumProperty(
        name="Logging Level",
        items=logging_level_items,
        update=logging_level_update,
        default="WARNING",
    )

    isosurface: BoolProperty(
        name="isosurface",
        description="Enable isosurface plugin",
        update=update_plugin("isosurface"),
        default=True,
    )

    molecular_surface: BoolProperty(
        name="molecular_surface",
        description="Enable molecular_surface plugin",
        update=update_plugin("molecular_surface"),
        default=True,
    )

    real_interaction: BoolProperty(
        name="real_interaction",
        description="Enable real_interaction plugin",
        update=update_plugin("real_interaction"),
        default=False,
    )

    magres: BoolProperty(
        name="magres",
        description="Enable magres plugin",
        update=update_plugin("magres"),
        default=True,
    )

    highlight: BoolProperty(
        name="highlight",
        description="Enable highlight plugin",
        update=update_plugin("highlight"),
        default=True,
    )

    cavity: BoolProperty(
        name="cavity",
        description="Enable cavity plugin",
        update=update_plugin("cavity"),
        default=True,
    )

    crystal_shape: BoolProperty(
        name="crystal_shape",
        description="Enable crystal_shape plugin",
        update=update_plugin("crystal_shape"),
        default=True,
    )

    lattice_plane: BoolProperty(
        name="lattice_plane",
        description="Enable lattice_plane plugin",
        update=update_plugin("lattice_plane"),
        default=True,
    )

    template: BoolProperty(
        name="template",
        description="Enable template plugin",
        update=update_plugin("template"),
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        layout.label(text="Welcome to Batoms!")
        # Check Blender version
        if bpy.app.version_string < "3.0.0":
            box = layout.box().column()
            box.label(text="Warning: Batoms need Blender version > 3.0.0.")

        layout.label(text="Use default setting.")
        box = layout.box().column()
        row = box.row(align=True)
        row.operator(
            "batoms.use_batoms_startup", text="Use startup", icon="FILE_REFRESH"
        )
        row.operator(
            "batoms.use_batoms_preference", text="Use Preferences", icon="FILE_REFRESH"
        )
        layout.separator()
        #
        layout.separator()
        split = layout.split()
        col = split.column()
        col.label(text="Custom Plugins")
        col.prop(self, "highlight")
        col.prop(self, "isosurface")
        col.prop(self, "molecular_surface")
        col.prop(self, "crystal_shape")
        col.prop(self, "lattice_plane")
        col.prop(self, "cavity")
        col.prop(self, "magres")
        col.prop(self, "real_interaction")
        col.prop(self, "template")
        col = split.column()
        # custom folder
        layout.separator()
        box = layout.box().column()
        box.label(text="Custom Settings")
        box.prop(self, "logging_level")
        box.prop(self, "batoms_setting_path")


classes = [
    BatomsDefaultPreference,
    BatomsDefaultStartup,
    BatomsAddonPreferences,
]


def register_class():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)


def unregister_class():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
