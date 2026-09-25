import bpy
import numpy as np
import pytest


def _setup():
    from batoms import Batoms
    from ase.build import fcc111, molecule

    slab = Batoms("pt", from_ase=fcc111("Pt", (3, 3, 3), vacuum=8.0))
    slab.model_style = 1
    co = molecule("CO")
    co.translate(slab.positions[-1] + np.array([0.0, 0.0, 8.0]))
    mol = Batoms("co", from_ase=co)
    mol.obj.location = (0.4, -0.3, 1.5)  # "dragged" by hand in the viewport
    bpy.ops.object.select_all(action="DESELECT")
    slab.obj.select_set(True)
    mol.obj.select_set(True)
    bpy.context.view_layer.objects.active = mol.obj
    return slab, mol


def _cross_bonds(label, n_surface):
    from batoms import Batoms

    arr = Batoms(label).bond.arrays
    i, j = arr["atoms_index0"], arr["atoms_index1"]
    return int(np.sum((i < n_surface) != (j < n_surface)))


@pytest.mark.parametrize("mode, expect_bonds", [("covalent", True), ("vdw", False)])
def test_snap_merge(mode, expect_bonds):
    from ase.data import covalent_radii
    from ase.data.vdw_alvarez import vdw_radii

    slab, mol = _setup()
    n_surface = len(slab)
    assert bpy.ops.batoms.snap(mode=mode) == {"FINISHED"}
    assert "pt_co" in bpy.data.collections
    from batoms import Batoms

    merged = Batoms("pt_co")
    assert len(merged) == n_surface + 2
    pos = merged.positions
    d = np.linalg.norm(pos[n_surface:, None] - pos[None, :n_surface], axis=2)
    radii = covalent_radii if mode == "covalent" else vdw_radii
    target = radii[merged.arrays["numbers"][n_surface:]][:, None] + radii[78]
    # contact reached, nothing closer than contact (periodic images aside)
    assert np.isclose((d - target).min(), 0.0, atol=2e-3)
    assert (_cross_bonds("pt_co", n_surface) > 0) == expect_bonds
    # originals hidden, not deleted
    assert slab.obj.hide_get() and mol.obj.hide_get()
    for label in ("pt_co", "co", "pt"):
        bpy.ops.batoms.delete(label=label)
