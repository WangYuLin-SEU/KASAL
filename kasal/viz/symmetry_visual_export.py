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
    rotation_center = np.asarray(symmetry_info.get("rot_center", [0, 0, 0]), dtype=np.float32).reshape(3)
    visualization_model["center_ch"] = rotation_center

    if sym_op == "symmetries_discrete" and "symmetries_discrete" in symmetry_info:
        transforms = symmetry_info["symmetries_discrete"]
        orbit_transforms = [np.asarray(m, dtype=np.float32).reshape(4, 4) for m in transforms]
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
    """Write normalized RGBA orbit colors into the model.

    Missing reference points and RGB colors use the current NumPy RNG state."""

    if reference_point is None:
        reference_point = np.random.uniform(0, 1, 3)
    vertices = visualization_model["vertices"]
    transformed_offsets = []
    for transform in orbit_transforms:
        transformed_offsets.append(
            np.dot(transform[:3, :3], vertices.T).T
            + transform[:3, 3]
            - reference_point
        )
    transformed_offsets = np.array(transformed_offsets)
    orbit_distances = np.linalg.norm(transformed_offsets, axis=2)
    nearest_orbit = np.argmin(orbit_distances, axis=0)
    if orbit_colors is None:
        orbit_colors = np.random.randint(0, 255, (len(orbit_transforms), 3)).astype(int)
    vertex_colors = np.zeros((visualization_model["colors"].shape[0], 4))
    for i, orbit_color in enumerate(orbit_colors):
        vertex_colors[nearest_orbit == i, :3] = orbit_color
    vertex_colors[:, 3] = 255
    visualization_model["sym_colors"] = vertex_colors.astype(np.float32) / 255
