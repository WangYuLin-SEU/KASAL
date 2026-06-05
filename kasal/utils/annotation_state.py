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

import kasal.config.config as config
from kasal.utils.io_json import (
    SymmetryAnnotationState,
    fingerprint_from_state,
    fingerprint_from_ui,
    load_json2dict,
    parse_symmetry_type_dict,
    sidecar_sym_ply_path,
    sidecar_sym_type_path,
)


def has_persisted_rotational_label(state: SymmetryAnnotationState) -> bool:
    """True when a saved sidecar records a rotational-symmetry type (not None)."""

    return state.sym_type not in ("None", "")


def is_object_dirty(file_id: int) -> bool:
    return bool(config.annotation_dirty.get(file_id, True))


def mark_object_dirty(file_id: int, dirty: bool = True) -> None:
    config.annotation_dirty[file_id] = dirty


def mark_object_clean(file_id: int) -> None:
    config.annotation_dirty[file_id] = False
    config.saved_fingerprints[file_id] = fingerprint_from_ui()


def _apply_saved_state(file_id: int, state: SymmetryAnnotationState) -> None:
    """Sidecar on disk means processed/saved (including sym_type=None after auto-run)."""

    config.saved_fingerprints[file_id] = fingerprint_from_state(state)
    config.annotation_dirty[file_id] = False


def _mark_unlabeled(file_id: int) -> None:
    config.saved_fingerprints[file_id] = None
    config.annotation_dirty[file_id] = True


def sync_dirty_for_current_object() -> None:
    fid = config.current_file_id
    fp = fingerprint_from_ui()
    saved = config.saved_fingerprints.get(fid)
    if saved is None:
        config.annotation_dirty[fid] = True
    else:
        config.annotation_dirty[fid] = fp != saved


def initialize_dataset_dirty_state(files_name_list: list[str]) -> None:
    """Scan sidecars and set unsaved flags.

    Saved (not in Cal All queue):
      - Legacy v1 or v2 sidecar with a rotational sym_type (manual or prior run).

    Unsaved (Cal All will process):
      - No *_sym_type.json sidecar (never processed / cleared).
    """

    config.annotation_dirty = {}
    config.saved_fingerprints = {}
    for i, path in enumerate(files_name_list):
        sym_path = sidecar_sym_type_path(path)
        if not os.path.exists(sym_path):
            _mark_unlabeled(i)
            continue
        raw = load_json2dict(sym_path)
        state = parse_symmetry_type_dict(raw)
        _apply_saved_state(i, state)


def apply_loaded_annotation_state(file_id: int, state: SymmetryAnnotationState) -> None:
    """Sync unsaved flag after loading a sidecar into the UI."""

    _apply_saved_state(file_id, state)


def apply_unlabeled_object_state(file_id: int) -> None:
    """Mark object as unlabeled when no sidecar exists."""

    _mark_unlabeled(file_id)


def dirty_object_ids() -> list[int]:
    return [i for i in range(len(config.files_name_list or [])) if is_object_dirty(i)]


def saved_object_ids() -> list[int]:
    return [i for i in range(len(config.files_name_list or [])) if not is_object_dirty(i)]


def mark_all_dirty() -> None:
    for i in range(len(config.files_name_list or [])):
        config.annotation_dirty[i] = True


def count_annotation_artifacts(files_name_list: list[str]) -> tuple[int, int]:
    """Return (sym_type_json_count, sym_ply_count) present on disk."""

    json_n = 0
    ply_n = 0
    for path in files_name_list:
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


def clear_all_dataset_annotations(files_name_list: list[str]) -> dict[str, int]:
    """Remove all annotation sidecars; mark every object unlabeled."""

    json_removed = 0
    ply_removed = 0
    for path in files_name_list:
        j, p = clear_mesh_annotation_artifacts(path)
        json_removed += int(j)
        ply_removed += int(p)
    initialize_dataset_dirty_state(files_name_list)
    return {
        "objects": len(files_name_list),
        "json_removed": json_removed,
        "ply_removed": ply_removed,
    }
