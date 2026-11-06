# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Prepare analysis results and orbit colors for symmetry visualization."""

from __future__ import annotations

import colorsys
import copy

import numpy as np


def build_symmetry_visualization_model(
    mesh_model: dict,
    current_obj_info: dict,
    sym_type: str,
    *,
    color_symmetry_orbits: bool = True,
) -> dict:
    """Copy mesh geometry and add BOP symmetry fields for PLY visualization."""

    visualization_model = copy.deepcopy(mesh_model)
    symmetry_info = current_obj_info

    for key in ("min_x", "min_y", "min_z", "size_x", "size_y", "size_z", "diameter"):
        if key in symmetry_info:
            visualization_model[key] = symmetry_info[key]

    if sym_type == "None" or not symmetry_info.get("has_rot_sym", True):
        return visualization_model

    sym_op = symmetry_info.get("sym_op")
    rotation_center = np.asarray(symmetry_info.get("rot_center", [0, 0, 0]), dtype=np.float64).reshape(3)
    visualization_model["center_ch"] = rotation_center

    if sym_op == "symmetries_discrete" and "symmetries_discrete" in symmetry_info:
        transforms = symmetry_info["symmetries_discrete"]
        orbit_transforms = [np.asarray(m, dtype=np.float64).reshape(4, 4) for m in transforms]
        visualization_model["symmetries_discrete"] = transforms
        axes = symmetry_info.get("rot_sym_axis", [])
        if axes:
            visualization_model["axis"] = [np.asarray(a, dtype=np.float32).reshape(3) for a in axes]
        if color_symmetry_orbits and orbit_transforms:
            apply_symmetry_orbit_colors(visualization_model, orbit_transforms)
    elif sym_op == "symmetries_continuous" or sym_type.startswith("C("):
        continuous_symmetries = symmetry_info.get("symmetries_continuous")
        if continuous_symmetries is None and symmetry_info.get("rot_sym_axis"):
            continuous_symmetries = [
                {"axis": axis, "offset": rotation_center.tolist()}
                for axis in symmetry_info.get("rot_sym_axis", [])
            ]
        if continuous_symmetries:
            visualization_model["symmetries_continuous"] = continuous_symmetries
            axes = [np.asarray(c.get("axis", []), dtype=np.float32).reshape(-1)[:3] for c in continuous_symmetries if c.get("axis")]
            if axes:
                visualization_model["axis"] = axes
            else:
                visualization_model["axis"] = []

    return visualization_model


def apply_symmetry_orbit_colors(
    visualization_model: dict,
    orbit_transforms: list,
    *,
    reference_point=None,
    orbit_colors=None,
) -> None:
    """Color representative regions of the complete finite rotation group.

    Identity is included for coloring only; the stored BOP transforms are unchanged.
    Defaults are deterministic and do not consume NumPy's global random state.
    Explicit colors must include an entry for identity when it is absent in input.
    """
    labels, count = symmetry_region_labels(
        visualization_model['vertices'], orbit_transforms,
        center=visualization_model.get('center_ch'), reference_point=reference_point,
    )
    palette = symmetry_palette(count) if orbit_colors is None else np.asarray(orbit_colors)
    if palette.shape != (count, 3) or not np.isfinite(palette).all() or np.any((palette < 0) | (palette > 255)):
        raise ValueError('Orbit colors must contain one RGB triplet per group element, including identity.')
    rgba = np.full((len(labels), 4), 255, dtype=np.uint8)
    rgba[:, :3] = palette[labels]
    visualization_model['sym_colors'] = rgba.astype(np.float32) / 255


def symmetry_palette(count: int) -> np.ndarray:
    """A deterministic cool palette with distinct *quantized* RGB entries."""
    colors, used = [], set()
    index = 0
    while len(colors) < count:
        rgb = colorsys.hls_to_rgb(.44 + .32 * ((index * .61803398875) % 1),
                                 .62 + .18 * ((index * .569840291) % 1),
                                 .32 + .16 * ((index * .754877666) % 1))
        color = tuple(np.rint(np.asarray(rgb) * 255).astype(int))
        if color not in used:
            colors.append(color)
            used.add(color)
        index += 1
    return np.asarray(colors, dtype=np.uint8).reshape(-1, 3)


def symmetry_region_labels(vertices, transforms, *, center=None, reference_point=None):
    """Return a transform index per vertex and the full group size.

    Each region consists of points whose chosen symmetry transform brings them
    closest to a reference point. This is a representative-region visualization,
    not a confidence map or a claim that equally colored points share one orbit.
    """
    vertices = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    matrices = np.asarray(transforms, dtype=np.float64).reshape(-1, 4, 4)
    if not len(vertices) or not np.isfinite(vertices).all() or not np.isfinite(matrices).all():
        raise ValueError('Symmetry coloring requires finite vertices and transforms.')
    if not any(np.allclose(matrix, np.eye(4), rtol=0, atol=1e-8) for matrix in matrices):
        matrices = np.concatenate((np.eye(4)[None], matrices))
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2 if center is None else np.asarray(center, dtype=float).reshape(3)
    if not np.isfinite(center).all():
        raise ValueError('Symmetry coloring requires a finite rotation center.')
    scale = max(float(np.ptp(vertices, axis=0).max()), 1e-12)
    points = (vertices - center) / scale
    rotations = matrices[:, :3, :3]
    offsets = (np.einsum('nij,j->ni', rotations, center) + matrices[:, :3, 3] - center) / scale
    if reference_point is None:
        # Fixed sphere samples avoid a reference on an axis. Maximize separation
        # of its transformed copies; normalized coordinates preserve scale/shift.
        reference, best_gap = np.array([1., 0., 0.]), -1.
        if len(matrices) > 1:
            for index in range(32):
                z = 1 - 2 * (index + .5) / 32
                angle = index * np.pi * (3 - np.sqrt(5))
                candidate = np.array([np.sqrt(1 - z*z) * np.cos(angle),
                                      np.sqrt(1 - z*z) * np.sin(angle), z])
                orbit = np.einsum('nij,j->ni', rotations, candidate) + offsets
                distances = np.sum((orbit[:, None] - orbit[None, :]) ** 2, axis=2)
                np.fill_diagonal(distances, np.inf)
                gap = float(distances.min())
                if gap > best_gap + 1e-10:
                    reference, best_gap = candidate, gap
    else:
        reference = (np.asarray(reference_point, dtype=float).reshape(3) - center) / scale
        if not np.isfinite(reference).all():
            raise ValueError('The coloring reference point must be finite.')
    # Keep O(vertex_count) memory instead of stacking every transformed mesh.
    labels = np.zeros(len(points), dtype=np.int64)
    nearest = np.full(len(points), np.inf)
    for index, (rotation, offset) in enumerate(zip(rotations, offsets)):
        delta = points @ rotation.T + offset - reference
        distance = np.einsum('ij,ij->i', delta, delta)
        closer = distance < nearest
        labels[closer], nearest[closer] = index, distance[closer]
    return labels, len(matrices)
