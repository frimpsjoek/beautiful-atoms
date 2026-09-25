"""Snap a molecule onto a surface at a covalent or van der Waals contact.

Pure numpy/ASE (no bpy), so it runs both inside Blender (the Snap button)
and in plain Python (the batoms skill).

The molecule moves along ``direction`` (default: toward the surface along
its normal) until the first atom pair reaches its contact distance:

    d_ij = scale * (R_i + R_j)

with covalent radii (``mode="covalent"``: bonding distance, batoms will draw
the bond) or van der Waals radii (``mode="vdw"``: non-bonded contact,
Alvarez 2013 set, which covers metals). Periodic images of the surface in
its periodic in-plane directions are included, so a molecule near the cell
edge sees the neighbouring cell.
"""

import numpy as np


def contact_radii(numbers, mode):
    """Radii (Å) used for contact distances."""
    from ase.data import covalent_radii

    numbers = np.asarray(numbers)
    if mode == "covalent":
        return covalent_radii[numbers]
    if mode == "vdw":
        from ase.data.vdw_alvarez import vdw_radii

        r = vdw_radii[numbers]
        # a few heavy elements have no Alvarez value: covalent + 1.0 Å
        missing = ~np.isfinite(r)
        r[missing] = covalent_radii[numbers[missing]] + 1.0
        return r
    raise ValueError("mode must be 'covalent' or 'vdw'")


def surface_normal(surface):
    """Unit normal of a slab: the c axis if it has a cell, else +z."""
    c = np.asarray(surface.cell[2], dtype=float)
    if np.linalg.norm(c) < 1e-8:
        return np.array([0.0, 0.0, 1.0])
    return c / np.linalg.norm(c)


def _images(surface):
    """Surface positions plus in-plane periodic images (3x3 in a, b)."""
    pos = surface.positions
    shifts = [np.zeros(3)]
    if surface.pbc[0] or surface.pbc[1]:
        a, b = surface.cell[0], surface.cell[1]
        ra = (-1, 0, 1) if surface.pbc[0] else (0,)
        rb = (-1, 0, 1) if surface.pbc[1] else (0,)
        shifts = [i * a + j * b for i in ra for j in rb]
    return np.concatenate([pos + s for s in shifts]), np.tile(surface.numbers, len(shifts))


def _clearance(mol_pos, r_mol, surf_pos, r_surf, scale):
    """min_ij (|r_i - r_j| - scale (R_i + R_j)) and the argmin pair."""
    d = np.linalg.norm(mol_pos[:, None, :] - surf_pos[None, :, :], axis=2)
    gap = d - scale * (r_mol[:, None] + r_surf[None, :])
    k = np.unravel_index(np.argmin(gap), gap.shape)
    return gap[k], k, d[k]


def snap(
    surface,
    molecule,
    mode="covalent",
    scale=1.0,
    direction=None,
    site=None,
    anchor=None,
    merge=True,
    max_travel=30.0,
    tol=1e-4,
):
    """Place ``molecule`` in contact with ``surface``.

    surface, molecule: ase.Atoms (not modified).
    mode:      "covalent" (bond forms) or "vdw" (physisorption contact).
    scale:     multiplies the contact distance (e.g. 1.1 for a longer bond).
    direction: unit vector the molecule travels along; default is minus
               the surface normal (molecule starts above and moves down).
    site:      lateral target: a surface atom index or an xyz point. The
               ``anchor`` atom (default: the molecule atom that leads along
               ``direction``) is first moved laterally above it.
    merge:     return surface + molecule as one Atoms (molecule tagged 0,
               surface tagged >= 1), so batoms treats it as one structure
               and draws the new bonds. Otherwise return the moved molecule.

    Returns (atoms, info) with info = {"travel", "contact_distance",
    "pair": (molecule_index, surface_index), "target", "mode", ...}.
    """
    n = -surface_normal(surface) if direction is None else np.asarray(direction, float)
    n = n / np.linalg.norm(n)
    mol = molecule.copy()
    lead = int(np.argmax(mol.positions @ n)) if anchor is None else int(anchor)

    if site is not None:
        target = surface.positions[site] if np.isscalar(site) else np.asarray(site, float)
        lateral = (target - mol.positions[lead])
        lateral -= (lateral @ n) * n  # move only perpendicular to the approach
        mol.positions += lateral

    surf_pos, surf_num = _images(surface)
    r_mol = contact_radii(mol.numbers, mode)
    r_surf = contact_radii(surf_num, mode)

    def gap(t):
        return _clearance(mol.positions + t * n, r_mol, surf_pos, r_surf, scale)[0]

    # start clear of the surface (step back if overlapping), then walk forward
    t0 = 0.0
    while gap(t0) <= 0:
        t0 -= 1.0
        if t0 < -max_travel:
            raise RuntimeError("could not separate molecule from surface")
    step, t = 0.1, t0
    while gap(t + step) > 0:
        t += step
        if t - t0 > 2 * max_travel:
            raise RuntimeError("molecule never reaches the surface along this direction")
    lo, hi = t, t + step  # gap(lo) > 0 >= gap(hi)
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if gap(mid) > 0 else (lo, mid)
    mol.positions += hi * n

    g, (i, j), dist = _clearance(mol.positions, r_mol, surf_pos, r_surf, scale)
    info = {
        "mode": mode,
        "scale": scale,
        "travel": float(hi),
        "direction": n.tolist(),
        "pair": (i, int(j % len(surface))),
        "pair_symbols": (mol[i].symbol, surface[int(j % len(surface))].symbol),
        "contact_distance": float(dist),
        "target": float(scale * (r_mol[i] + r_surf[j])),
    }
    if not merge:
        return mol, info
    surf = surface.copy()
    tags = surf.get_tags()
    if not np.any(tags > 0):
        surf.set_tags(np.ones(len(surf), dtype=int))
    mol.set_tags(np.zeros(len(mol), dtype=int))
    combined = surf + mol
    combined.info["snap"] = info
    return combined, info
