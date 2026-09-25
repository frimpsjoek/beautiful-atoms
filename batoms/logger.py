"""
Logger
"""
import bpy
import sys
from tempfile import NamedTemporaryFile
from pathlib import Path
import logging
import os

batoms_dir = os.path.dirname(Path(__file__).parent)


# logger = logging.getLogger('batoms')
logger = logging.getLogger(__name__)
root_logger = logging.getLogger("batoms")


def set_logger(version):
    # formatter = ('%(levelname)-8s '
    #                             '[%(funcName)-20s]: %(message)s')
    formatter = "%(levelname)s " "[%(name)-10s %(funcName)-10s]: %(message)s"
    logging.basicConfig(stream=sys.stdout, format=formatter, level=logging.INFO)
    # add logger file
    logfile = NamedTemporaryFile(mode = "wt", suffix=".log", prefix="beautiful_atoms_", delete=False)
    root_logger.info("Log file: " + str(logfile.name))
    file_handler = logging.StreamHandler(logfile)
    file_handler.setFormatter(logging.Formatter(formatter))
    root_logger.addHandler(file_handler)
    root_logger.info("Blender version: {} ".format(bpy.app.version_string))
    root_logger.info("Python version: {} ".format(sys.version))
    root_logger.info("Beautiful Atoms version: {} ".format(version))
    root_logger.info("Beautiful Atoms directory: {} ".format(batoms_dir))


def update_logging_level():
    # Legacy add-on key is "batoms"; as an extension it is "bl_ext.<repo>.batoms"
    keys = [key for key in bpy.context.preferences.addons.keys() if "batoms" in key]
    if not keys:
        return
    prefs = bpy.context.preferences.addons[keys[0]].preferences
    root_logger.setLevel(prefs.logging_level)


def print_time(key, value):
    return "{}: {}".format(key, value)
