# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Build model_i_ dict for save_ply_model from BOP / kasalv2 output.

from __future__ import annotations

import copy

import numpy as np
from scipy import spatial


def build_model_i_for_save_ply(
    legacy_model: dict,
    current_obj_info: dict,
    sym_type: str,
    *,
    sym_aware: bool = True,
) -> dict:
    """Merge mesh geometry and symmetry visualization fields for save_ply_model."""

    model_i_ = copy.deepcopy(legacy_model)
    info_ = current_obj_info

    for key in ("min_x", "min_y", "min_z", "size_x", "size_y", "size_z", "diameter"):
        if key in info_:
            model_i_[key] = info_[key]

    if sym_type == "None" or not info_.get("has_rot_sym", True):
        return model_i_

    sym_op = info_.get("sym_op")
    rot_center = np.asarray(info_.get("rot_center", [0, 0, 0]), dtype=np.float32).reshape(3)
    model_i_["center_ch"] = rot_center

    if sym_op == "symmetries_discrete" and "symmetries_discrete" in info_:
        mats = info_["symmetries_discrete"]
        sym_draw_list = [np.asarray(m, dtype=np.float32).reshape(4, 4) for m in mats]
        model_i_["symmetries_discrete"] = mats
        axes = info_.get("rot_sym_axis", [])
        if axes:
            model_i_["axis"] = [np.asarray(a, dtype=np.float32).reshape(3) for a in axes]
        if sym_aware and sym_draw_list:
            _apply_sym_colors(model_i_, sym_draw_list)
    elif sym_op == "symmetries_continuous" or sym_type.startswith("C("):
        cont = info_.get("symmetries_continuous")
        if cont is None and info_.get("rot_sym_axis"):
            cont = [
                {"axis": axis, "offset": rot_center.tolist()}
                for axis in info_.get("rot_sym_axis", [])
            ]
        if cont:
            model_i_["symmetries_continuous"] = cont
            axes = [np.asarray(c.get("axis", []), dtype=np.float32).reshape(-1)[:3] for c in cont if c.get("axis")]
            if axes:
                model_i_["axis"] = axes
            else:
                model_i_["axis"] = []

    return model_i_


def _apply_sym_colors(model_i_: dict, sym_draw_list: list) -> None:
    """Color vertices by discrete symmetry orbits (simplified from cal_model_sym)."""

    r_axis = np.random.uniform(0, 1, 3)
    vertices_ = model_i_["vertices"]
    vertices_sym = []
    for mat_1 in sym_draw_list:
        vertices_sym.append(np.dot(mat_1[:3, :3], vertices_.T).T + mat_1[:3, 3] - r_axis)
    vertices_sym = np.array(vertices_sym)
    vertices_sym = np.linalg.norm(vertices_sym, axis=2)
    vertices_sym = np.argmin(vertices_sym, axis=0)
    rand_color = np.random.randint(0, 255, (len(sym_draw_list), 3)).astype(int)
    colors_ = np.zeros((model_i_["colors"].shape[0], 4))
    for i, rand_color_i in enumerate(rand_color):
        colors_[vertices_sym == i, :3] = rand_color_i
    colors_[:, 3] = 255
    model_i_["sym_colors"] = colors_.astype(np.float32) / 255
