# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Unsaved tracking and dataset initialization for Cal All.

from __future__ import annotations

import os
from pathlib import Path

import kasal.config.runtime as config
from kasal.annotations.io import (
    SymmetryAnnotationState,
    build_symmetry_type_dict,
    parse_symmetry_type_dict,
    sidecar_sym_ply_path,
    sidecar_sym_type_path,
    validate_unique_sidecar_targets,
)
from kasal.utils.io_json import load_json, write_json
from kasal.version_names import normalize_engine


def is_object_dirty(file_id: int) -> bool:
    return bool(config.annotation_dirty.get(file_id, True))


def mark_object_dirty(file_id: int, dirty: bool = True) -> None:
    config.annotation_dirty[file_id] = dirty
    config.annotation_load_errors.pop(file_id, None)


def initialize_dataset_dirty_state(mesh_paths: list[str]) -> dict[int, str]:
    """Scan sidecars and set unsaved flags.

    Saved (not in Cal All queue):
      - A readable v1 or v2 sidecar, including sym_type=None after an auto-run.

    Unsaved (Cal All will process):
      - No *_sym_type.json sidecar (never processed / cleared).

    Invalid sidecars are reported and protected from automatic overwrite until
    the user explicitly marks that object unsaved.
    """

    validate_unique_sidecar_targets(mesh_paths)
    config.annotation_dirty = {}
    config.annotation_load_errors = {}
    for i, path in enumerate(mesh_paths):
        sym_path = sidecar_sym_type_path(path)
        if not os.path.exists(sym_path):
            mark_object_dirty(i)
            continue
        try:
            parse_symmetry_type_dict(load_json(sym_path))
        except (OSError, TypeError, ValueError) as exc:
            config.annotation_dirty[i] = True
            config.annotation_load_errors[i] = f"{sym_path}: {exc}"
            continue
        mark_object_dirty(i, False)
    return dict(config.annotation_load_errors)


def dirty_object_ids() -> list[int]:
    return [
        i
        for i in range(len(config.mesh_paths or []))
        if is_object_dirty(i) and i not in config.annotation_load_errors
    ]


def saved_object_ids() -> list[int]:
    return [
        i
        for i in range(len(config.mesh_paths or []))
        if not is_object_dirty(i) and i not in config.annotation_load_errors
    ]


def mark_all_dirty() -> None:
    config.annotation_load_errors = {}
    for i in range(len(config.mesh_paths or [])):
        config.annotation_dirty[i] = True


def count_annotation_artifacts(mesh_paths: list[str]) -> tuple[int, int]:
    """Return (sym_type_json_count, sym_ply_count) present on disk."""

    json_n = 0
    ply_n = 0
    for path in mesh_paths:
        if os.path.exists(sidecar_sym_type_path(path)):
            json_n += 1
        if os.path.exists(sidecar_sym_ply_path(path)):
            ply_n += 1
    return json_n, ply_n


def clear_mesh_annotation_artifacts(mesh_path: str) -> tuple[bool, bool]:
    """Delete *_sym_type.json and *_sym.ply for one mesh if they exist."""

    json_removed = False
    ply_removed = False
    sym_json = sidecar_sym_type_path(mesh_path)
    sym_ply = sidecar_sym_ply_path(mesh_path)
    if os.path.exists(sym_json):
        os.remove(sym_json)
        json_removed = True
    if os.path.exists(sym_ply):
        os.remove(sym_ply)
        ply_removed = True
    return json_removed, ply_removed


def clear_all_dataset_annotations(mesh_paths: list[str]) -> dict[str, int]:
    """Remove all annotation sidecars; mark every object unlabeled."""

    json_removed = 0
    ply_removed = 0
    for path in mesh_paths:
        j, p = clear_mesh_annotation_artifacts(path)
        json_removed += int(j)
        ply_removed += int(p)
    initialize_dataset_dirty_state(mesh_paths)
    return {
        "objects": len(mesh_paths),
        "json_removed": json_removed,
        "ply_removed": ply_removed,
    }


def apply_state_to_config(state: SymmetryAnnotationState) -> None:
    config.selected_symmetry_type = state.sym_type
    config.selected_n_fold = state.n_fold
    config.adi_color_enabled = state.adi_c
    config.selected_axis_constraint = state.axis_xyz
    config.current_obj_info = state.current_obj_info
    config.sym_type_source = state.sym_type_source
    config.n_fold_source = state.n_fold_source
    config.axis_xyz_source = state.axis_xyz_source
    config.compute_engine = state.compute_engine


def reset_current_object_ui() -> None:
    config.selected_symmetry_type = config.symmetry_type_options[0]
    config.selected_axis_constraint = config.axis_constraint_options[0]
    config.selected_n_fold = 2
    config.adi_color_enabled = False
    config.sym_type_source = "kasalv2_auto"
    config.n_fold_source = "kasalv2_auto"
    config.axis_xyz_source = "none"
    config.current_obj_info = {}


def _annotation_should_persist() -> bool:
    if config.selected_symmetry_type != "None":
        return True
    return (
        config.sym_type_source == "kasalv2_auto"
        and config.n_fold_source == "kasalv2_auto"
        and bool(config.current_obj_info)
    )


def save_symmetry_type():
    """Save the rotational symmetry information of the current object."""

    mesh_path = config.mesh_paths[config.current_mesh_index]
    sym_type_file = sidecar_sym_type_path(mesh_path)
    sym_ply_file = sidecar_sym_ply_path(mesh_path)

    if _annotation_should_persist():
        state = SymmetryAnnotationState(
            sym_type=config.selected_symmetry_type,
            n_fold=config.selected_n_fold,
            adi_c=config.adi_color_enabled,
            axis_xyz=config.selected_axis_constraint,
            current_obj_info=config.current_obj_info,
            sym_type_source=config.sym_type_source,
            n_fold_source=config.n_fold_source,
            axis_xyz_source=config.axis_xyz_source,
            compute_engine=normalize_engine(config.compute_engine),
        )
        if config.selected_symmetry_type == "None":
            Path(sym_ply_file).unlink(missing_ok=True)
        write_json(sym_type_file, build_symmetry_type_dict(state))
        mark_object_dirty(config.current_mesh_index, False)
        return

    Path(sym_type_file).unlink(missing_ok=True)
    Path(sym_ply_file).unlink(missing_ok=True)
    mark_object_dirty(config.current_mesh_index)
    return


def load_symmetry_type():
    """Load the rotational symmetry information of the current object."""

    print("id / N : %s / %s" % (str(config.current_mesh_index), str(len(config.mesh_paths))))

    mesh_path = config.mesh_paths[config.current_mesh_index]
    print(mesh_path)
    sym_type_file = sidecar_sym_type_path(mesh_path)
    fid = config.current_mesh_index
    if os.path.exists(sym_type_file):
        try:
            symmetry_type_dict = load_json(sym_type_file)
            state = parse_symmetry_type_dict(symmetry_type_dict)
        except (OSError, TypeError, ValueError) as exc:
            reset_current_object_ui()
            config.annotation_dirty[fid] = True
            config.annotation_load_errors[fid] = f"{sym_type_file}: {exc}"
            config.ui_batch_status = (
                f"Invalid annotation protected from overwrite: {sym_type_file}"
            )
            print(f"[KASAL WARNING] {config.annotation_load_errors[fid]}")
            return
        apply_state_to_config(state)
        mark_object_dirty(fid, False)
    else:
        reset_current_object_ui()
        mark_object_dirty(fid)
    return
