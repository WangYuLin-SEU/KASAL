# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any

import kasal.config.config as config
from kasal.version_names import KASALV1_ENGINE, KASALV2_ENGINE, normalize_engine

SYMMETRY_SCHEMA_V1 = 1
SYMMETRY_SCHEMA_V2 = 2


@dataclass
class SymmetryAnnotationState:
    sym_type: str = "None"
    n_fold: int = 2
    adi_c: bool = False
    axis_xyz: str = "None"
    current_obj_info: dict = field(default_factory=dict)
    sym_type_source: str = "user"
    n_fold_source: str = "user"
    axis_xyz_source: str = "none"
    compute_engine: str = KASALV1_ENGINE
    kasalv2_snapshot: dict | None = None
    mesh_preprocess_backend: str = ""
    mesh_preprocess_fallback_reason: str = ""
    mesh_enrich_applied: list = field(default_factory=list)
    mesh_topology: str = ""
    format_route: str = ""


def load_json2dict(path):
    with open(path, "r") as f:
        dict_ = json.load(f)
    return dict_


def write_dict2json(path, dict_):
    with open(path, "w") as f:
        json.dump(dict_, f, indent=4)
    return


def get_all_ply_obj(dir):
    """Load all files with the extensions .ply and .obj, excluding files with the suffix _sym.ply."""

    filelist = []
    for home, dirs, files in os.walk(dir):
        for filename in files:
            if filename.endswith(".ply") or filename.endswith(".obj"):
                if not filename.endswith("_sym.ply"):
                    filelist.append(os.path.join(home, filename))
    return filelist


def sidecar_sym_type_path(mesh_path: str) -> str:
    return os.path.join(
        os.path.dirname(mesh_path),
        os.path.basename(mesh_path).split(".")[0] + "_sym_type.json",
    )


def sidecar_sym_ply_path(mesh_path: str) -> str:
    return os.path.join(
        os.path.dirname(mesh_path),
        os.path.basename(mesh_path).split(".")[0] + "_sym.ply",
    )


def fingerprint_from_ui() -> tuple:
    return (
        config.ui_options_selected,
        config.ui_int,
        config.is_true2,
        config.ui_xyz_options_selected,
    )


def fingerprint_from_state(state: SymmetryAnnotationState) -> tuple:
    return (state.sym_type, state.n_fold, state.adi_c, state.axis_xyz)


def parse_symmetry_type_dict(raw: dict) -> SymmetryAnnotationState:
    """Parse v1 or v2 symmetry JSON into runtime state."""

    schema = raw.get("schema_version", SYMMETRY_SCHEMA_V1)
    v2 = raw.get("kasal_v2", {}) if schema == SYMMETRY_SCHEMA_V2 else {}

    sym_type = raw.get("sym_type", "None")
    n_fold = raw.get("n-fold", 2)
    adi_c = raw.get("ADI-C", False)
    axis_xyz = raw.get("axis_xyz", "None")
    current_obj_info = raw.get("current_obj_info", {})

    if v2:
        return SymmetryAnnotationState(
            sym_type=sym_type,
            n_fold=n_fold,
            adi_c=adi_c,
            axis_xyz=axis_xyz,
            current_obj_info=current_obj_info,
            sym_type_source=v2.get("sym_type_source", "user"),
            n_fold_source=v2.get("n_fold_source", "user"),
            axis_xyz_source=v2.get("axis_xyz_source", "none"),
            compute_engine=normalize_engine(v2.get("compute_engine", KASALV1_ENGINE)),
            kasalv2_snapshot=v2.get("kasalv2_snapshot"),
            mesh_preprocess_backend=v2.get("mesh_preprocess_backend", ""),
            mesh_preprocess_fallback_reason=v2.get("mesh_preprocess_fallback_reason", ""),
            mesh_enrich_applied=v2.get("mesh_enrich_applied", []),
            mesh_topology=v2.get("mesh_topology", ""),
            format_route=v2.get("format_route", ""),
        )

    return SymmetryAnnotationState(
        sym_type=sym_type,
        n_fold=n_fold,
        adi_c=adi_c,
        axis_xyz=axis_xyz,
        current_obj_info=current_obj_info,
        sym_type_source="user",
        n_fold_source="user",
        axis_xyz_source="user" if axis_xyz != "None" else "none",
        compute_engine=KASALV1_ENGINE,
    )


def build_symmetry_type_dict(state: SymmetryAnnotationState) -> dict:
    """Build v2 JSON dict with v1-compatible top-level keys."""

    ui_int_c = state.n_fold
    if ui_int_c > config.ui_int_upper:
        ui_int_c = config.ui_int_upper
    if ui_int_c < 2:
        ui_int_c = 2

    symmetry_type_dict: dict[str, Any] = {
        "schema_version": SYMMETRY_SCHEMA_V2,
        "sym_type": state.sym_type,
        "n-fold": ui_int_c,
        "ADI-C": state.adi_c,
        "current_obj_info": state.current_obj_info,
        "kasal_v2": {
            "sym_type_source": state.sym_type_source,
            "n_fold_source": state.n_fold_source,
            "axis_xyz_source": state.axis_xyz_source,
            "compute_engine": state.compute_engine,
            "kasalv2_snapshot": state.kasalv2_snapshot,
            "mesh_preprocess_backend": state.mesh_preprocess_backend or getattr(config, "mesh_preprocess_backend", ""),
            "mesh_preprocess_fallback_reason": state.mesh_preprocess_fallback_reason
            or getattr(config, "mesh_preprocess_fallback_reason", ""),
            "mesh_enrich_applied": state.mesh_enrich_applied or getattr(config, "mesh_enrich_applied", []),
            "mesh_topology": state.mesh_topology or getattr(config, "mesh_topology", ""),
            "format_route": state.format_route or getattr(config, "format_route", ""),
        },
    }
    if state.axis_xyz != "None":
        symmetry_type_dict["axis_xyz"] = state.axis_xyz
    return symmetry_type_dict


def apply_state_to_config(state: SymmetryAnnotationState) -> None:
    config.ui_options_selected = state.sym_type
    config.ui_int = state.n_fold
    config.is_true2 = state.adi_c
    config.ui_xyz_options_selected = state.axis_xyz
    config.current_obj_info = state.current_obj_info
    config.sym_type_source = state.sym_type_source
    config.n_fold_source = state.n_fold_source
    config.axis_xyz_source = state.axis_xyz_source
    config.compute_engine = state.compute_engine
    config.kasalv2_snapshot = state.kasalv2_snapshot


def _annotation_should_persist() -> bool:
    if config.ui_options_selected != "None":
        return True
    return (
        getattr(config, "sym_type_source", "") == "kasalv2_auto"
        and getattr(config, "n_fold_source", "") == "kasalv2_auto"
    )


def save_symmetry_type():
    """Save the rotational symmetry information of the current object."""

    from kasal.utils.annotation_state import apply_unlabeled_object_state, mark_object_clean

    f_ = config.files_name_list[config.current_file_id]
    sym_type_file = sidecar_sym_type_path(f_)
    sym_ply_file = sidecar_sym_ply_path(f_)

    if _annotation_should_persist():
        state = SymmetryAnnotationState(
            sym_type=config.ui_options_selected,
            n_fold=config.ui_int,
            adi_c=config.is_true2,
            axis_xyz=config.ui_xyz_options_selected,
            current_obj_info=config.current_obj_info,
            sym_type_source=getattr(config, "sym_type_source", "user"),
            n_fold_source=getattr(config, "n_fold_source", "user"),
            axis_xyz_source=getattr(config, "axis_xyz_source", "none"),
            compute_engine=normalize_engine(getattr(config, "compute_engine", KASALV1_ENGINE)),
            kasalv2_snapshot=getattr(config, "kasalv2_snapshot", None),
        )
        write_dict2json(sym_type_file, build_symmetry_type_dict(state))
        mark_object_clean(config.current_file_id)
        if config.ui_options_selected == "None":
            try:
                os.remove(sym_ply_file)
            except Exception:
                pass
        return

    try:
        os.remove(sym_type_file)
    except Exception:
        pass
    try:
        os.remove(sym_ply_file)
    except Exception:
        pass
    apply_unlabeled_object_state(config.current_file_id)
    return


def load_symmetry_type():
    """Load the rotational symmetry information of the current object."""

    from kasal.utils.annotation_state import (
        apply_loaded_annotation_state,
        apply_unlabeled_object_state,
    )

    print("id / N : %s / %s" % (str(config.current_file_id), str(len(config.files_name_list))))

    write_dict2json(
        config.start_id_json_file,
        {"start_id": config.current_file_id},
    )
    f_ = config.files_name_list[config.current_file_id]
    print(f_)
    sym_type_file = sidecar_sym_type_path(f_)
    fid = config.current_file_id
    if os.path.exists(sym_type_file):
        symmetry_type_dict = load_json2dict(sym_type_file)
        state = parse_symmetry_type_dict(symmetry_type_dict)
        apply_state_to_config(state)
        apply_loaded_annotation_state(fid, state)
    else:
        apply_unlabeled_object_state(fid)
    return
