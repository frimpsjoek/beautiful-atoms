import glob
import os

import bpy
import numpy as np
import pytest

PDEP = os.path.expanduser("~/Documents/PDEP-project/datasets/silane-structures/runs/combined_cubes")


def _import(paths, **kw):
    d = os.path.dirname(paths[0])
    return bpy.ops.batoms.import_series(
        directory=d, files=[{"name": os.path.basename(p)} for p in paths], **kw
    )


def _cleanup():
    for label in [c.name for c in bpy.data.collections if c.batoms.type == "BATOMS"]:
        bpy.ops.batoms.delete(label=label)


def _perturbed(atoms, k):
    a = atoms.copy()
    a.positions += 0.05 * k
    return a


@pytest.mark.parametrize("fmt, ext", [("extxyz", "xyz"), ("cif", "cif"), ("vasp", "vasp"), ("espresso-in", "in")])
def test_series_formats_natural_order(tmp_path, fmt, ext):
    from ase.build import bulk, molecule
    from ase.io import write
    from batoms import Batoms

    base = molecule("H2O") if fmt == "extxyz" else bulk("Si", cubic=True)
    kw = {"pseudopotentials": {"Si": "Si.upf"}} if fmt == "espresso-in" else {}
    for k in (1, 2, 3, 10):
        write(tmp_path / f"f_{k}.{ext}", _perturbed(base, k), format=fmt, **kw)
    paths = sorted(glob.glob(str(tmp_path / f"*.{ext}")))  # lexical: 1, 10, 2, 3
    assert _import(paths, label="ser", build_isosurfaces=False) == {"FINISHED"}
    b = Batoms("ser")
    traj = b.get_trajectory()["positions"]
    assert len(traj) == 4
    # natural order: frame 3 is f_10 (largest shift)
    shifts = [float(np.mean(t - traj[0])) for t in traj]
    assert np.allclose(np.diff(shifts) > 0, True) and np.isclose(shifts[3], 0.05 * 9, atol=1e-3)
    _cleanup()


def test_series_different_atoms_copy_style(tmp_path):
    from ase.build import molecule
    from ase.io import write
    from batoms import Batoms

    for i, m in enumerate(("H2O", "CH4", "NH3")):
        write(tmp_path / f"m_{i}.xyz", molecule(m))
    _import(sorted(glob.glob(str(tmp_path / "*.xyz"))), label="mix", build_isosurfaces=False)
    first = Batoms("mix_000")
    first["H"].color = [1, 0, 0, 1]
    first.model_style = 1
    from batoms.studio.series import copy_style

    second = Batoms("mix_001")
    copy_style(first, second)
    assert np.allclose(second["H"].color, [1, 0, 0, 1]) and second.model_style == 1
    scene = bpy.context.scene
    scene.frame_set(1)
    assert second.obj.hide_render is False and first.obj.hide_render is True
    _cleanup()


def test_series_append(tmp_path):
    from ase.build import molecule
    from ase.io import write
    from batoms import Batoms

    h2o = molecule("H2O")
    b = Batoms("app", from_ase=h2o)
    for k in (1, 2, 3):
        write(tmp_path / f"a_{k}.xyz", _perturbed(h2o, k))
    bpy.context.view_layer.objects.active = b.obj
    assert _import(sorted(glob.glob(str(tmp_path / "*.xyz"))), target="APPEND", build_isosurfaces=False) == {"FINISHED"}
    assert len(Batoms("app").get_trajectory()["positions"]) == 4
    _cleanup()


@pytest.mark.skipif(not os.path.isdir(PDEP), reason="PDEP data not available")
def test_cube_series_animation_build_update():
    from batoms import Batoms

    files = [os.path.join(PDEP, "eigQ000001I000001_Silane.cube")] + [
        os.path.join(PDEP, f"eigQ000001I000001_perturbed_{k}.cube") for k in (1, 2, 3)
    ]
    s = bpy.context.scene.batoms_studio
    s.level, s.substeps, s.method, s.upsample_to, s.smooth = 0.0, 2, "linear", 0, 0
    assert _import(files, label="pdep", build_isosurfaces=True) == {"FINISHED"}
    assert "verified" in s.anim_report, s.anim_report
    b = Batoms("pdep")
    coll = bpy.data.collections["pdep_isosurfaces"]
    frames = sorted({o["iso_frame"] for o in coll.objects})
    assert frames == list(range(7))  # 4 keys, 2 substeps -> 7 frames
    obj0 = next(o for o in coll.objects if o["iso_frame"] == 0 and o["iso_sign"] == "positive")
    n_before = len(obj0.data.vertices)
    s.level = 60.0
    assert bpy.ops.batoms.volume_anim_update() == {"FINISHED"}
    assert len(obj0.data.vertices) > n_before  # lower isovalue -> larger lobe
    assert bpy.ops.batoms.volume_anim_verify() == {"FINISHED"}
    assert s.anim_report == "All frames OK"
    _cleanup()


def test_make_vacancy_si():
    from ase.build import bulk
    from batoms import Batoms

    si = Batoms("si", from_ase=bulk("Si", cubic=True).repeat((2, 2, 2)))
    n0 = len(si)
    for v in si.obj.data.vertices:
        v.select = v.index == 20
    bpy.context.view_layer.objects.active = si.obj
    assert bpy.ops.batoms.make_vacancy() == {"FINISHED"}
    si = Batoms("si")
    assert len(si) == n0 - 1
    assert "Si_1" in si.species.keys()
    assert int(np.sum(np.array(si.arrays["species"]) == "Si_1")) == 4  # tetrahedral neighbours
    assert any(o.get("vacancy") for o in bpy.data.objects)
    _cleanup()
