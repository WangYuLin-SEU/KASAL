# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

from typing import Any

import numpy as np


TEXTURE_SYMMETRY_KEY = "texture_symmetry"

SUMMARY_CSV_FIELDS = [
    "object",
    "success",
    "pred_sym_type",
    "pred_n_fold",
    "tex_has_rot_sym",
    "tex_sym_type",
    "tex_n_fold",
    "tex_sym_op",
    "preprocess_sec",
    "analysis_sec",
    "postprocess_sec",
    "total_sec",
    "model",
    "model_relpath",
    "output",
    "error",
]


def normalize_n_fold_for_output(n_fold: Any) -> int | str | None:
    if n_fold is None:
        return None
    try:
        fold_value = float(n_fold)
    except (TypeError, ValueError):
        return str(n_fold)
    if np.isinf(fold_value):
        return "inf"
    return int(fold_value)


def normalize_xyz_for_output(value: Any, default: list[float] | None = None) -> list[float]:
    fallback = [0.0, 0.0, 0.0] if default is None else default
    try:
        return np.asarray(value, dtype=np.float32).reshape(-1)[:3].tolist()
    except (TypeError, ValueError):
        return fallback


def normalize_axes_for_output(values: Any) -> list[list[float]]:
    if values is None:
        return []
    return [
        np.asarray(axis, dtype=np.float32).reshape(-1)[:3].tolist()
        for axis in values
    ]


def normalize_matrices_for_output(values: Any) -> list[list[list[float]]]:
    if values is None:
        return []
    return [
        np.asarray(matrix, dtype=np.float32).tolist()
        for matrix in values
    ]


def normalize_symmetry_layer_for_output(raw_layer: dict[str, Any]) -> dict[str, Any]:
    sym_op = raw_layer.get("sym_op", "none")
    n_fold = raw_layer.get("n_fold")
    n_fold_out = "inf" if sym_op == "symmetries_continuous" else normalize_n_fold_for_output(n_fold)
    axes = raw_layer.get("rot_sym_axis", raw_layer.get("axes_tex"))

    result = {
        "has_rot_sym": bool(raw_layer.get("has_rot_sym", raw_layer.get("has_rot_sym_tex", False))),
        "sym_type": raw_layer.get("sym_type", raw_layer.get("rot_sym_type")),
        "n_fold": n_fold_out,
        "sym_op": sym_op,
        "rot_center": normalize_xyz_for_output(raw_layer.get("rot_center", np.zeros(3))),
        "rot_sym_axis": normalize_axes_for_output(axes),
        "rot_sym_matrices": normalize_matrices_for_output(raw_layer.get("rot_sym_matrices")),
    }
    if "enabled" in raw_layer:
        result["enabled"] = bool(raw_layer.get("enabled"))
    if "evaluated" in raw_layer:
        result["evaluated"] = bool(raw_layer.get("evaluated"))
    return result


def build_analysis_result(raw_result: dict[str, Any], n_fold: Any) -> dict[str, Any]:
    sym_op = raw_result.get("sym_op", "none")
    n_fold_out = "inf" if sym_op == "symmetries_continuous" else normalize_n_fold_for_output(n_fold)
    analysis = {
        "has_rot_sym": bool(raw_result.get("has_rot_sym", False)),
        "sym_type": raw_result.get("rot_sym_type"),
        "n_fold": n_fold_out,
        "sym_op": sym_op,
        "rot_center": normalize_xyz_for_output(raw_result.get("rot_center", np.zeros(3))),
        "rot_sym_axis": normalize_axes_for_output(raw_result.get("rot_sym_axis")),
        "rot_sym_matrices": normalize_matrices_for_output(raw_result.get("rot_sym_matrices")),
    }
    texture_symmetry = raw_result.get(TEXTURE_SYMMETRY_KEY)
    if isinstance(texture_symmetry, dict):
        analysis[TEXTURE_SYMMETRY_KEY] = normalize_symmetry_layer_for_output(texture_symmetry)
    return analysis


def add_bop_symmetry_payload(target: dict[str, Any], analysis: dict[str, Any]) -> None:
    if analysis.get("sym_op") == "symmetries_discrete":
        target["symmetries_discrete"] = [
            np.asarray(matrix, dtype=np.float32).reshape(4, 4).flatten().tolist()
            for matrix in analysis.get("rot_sym_matrices", [])
        ]
    elif analysis.get("sym_op") == "symmetries_continuous":
        target["symmetries_continuous"] = [
            {
                "axis": axis,
                "offset": analysis.get("rot_center", [0.0, 0.0, 0.0]),
            }
            for axis in analysis.get("rot_sym_axis", [])
        ]


def build_symmetry_output_layer(analysis: dict[str, Any]) -> dict[str, Any]:
    result = {
        "has_rot_sym": analysis.get("has_rot_sym", False),
        "rot_sym_type": analysis.get("sym_type"),
        "n_fold": analysis.get("n_fold"),
        "sym_op": analysis.get("sym_op"),
        "rot_center": analysis.get("rot_center", [0.0, 0.0, 0.0]),
        "rot_sym_axis": analysis.get("rot_sym_axis", []),
    }
    if "enabled" in analysis:
        result["enabled"] = analysis.get("enabled")
    if "evaluated" in analysis:
        result["evaluated"] = analysis.get("evaluated")
    add_bop_symmetry_payload(result, analysis)
    return result


def build_model_output_json(analysis: dict[str, Any], bbox_info: dict[str, Any]) -> dict[str, Any]:
    result = dict(bbox_info)
    result.update(
        {
            "has_rot_sym": analysis.get("has_rot_sym", False),
            "rot_sym_type": analysis.get("sym_type"),
            "n_fold": analysis.get("n_fold"),
            "sym_op": analysis.get("sym_op"),
            "rot_center": analysis.get("rot_center", [0.0, 0.0, 0.0]),
            "rot_sym_axis": analysis.get("rot_sym_axis", []),
        }
    )
    add_bop_symmetry_payload(result, analysis)

    if TEXTURE_SYMMETRY_KEY in analysis:
        result[TEXTURE_SYMMETRY_KEY] = build_symmetry_output_layer(analysis[TEXTURE_SYMMETRY_KEY])

    return result


def build_summary_csv_row(item: dict[str, Any]) -> list[Any]:
    return [
        item["object"],
        item["success"],
        item["sym_type"],
        item["n_fold"],
        item.get("tex_has_rot_sym"),
        item.get("tex_sym_type"),
        item.get("tex_n_fold"),
        item.get("tex_sym_op"),
        item["preprocess_sec"],
        item["analysis_sec"],
        item["postprocess_sec"],
        item["total_sec"],
        item["model"],
        item["model_relpath"],
        item["output"],
        item["error"],
    ]
