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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import kasal.config.runtime as config
from kasal.version_names import KASALV1_ENGINE, validate_engine

SYMMETRY_SCHEMA_V1 = 1
SYMMETRY_SCHEMA_V2 = 2
SIDECAR_MESH_SUFFIXES = (".ply", ".obj", ".glb", ".gltf", ".stl", ".off")


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


def discover_annotation_meshes(directory: str | Path) -> list[str]:
    """Find PLY/OBJ inputs recursively, excluding generated symmetry meshes."""

    filelist = []
    for home, _, files in os.walk(directory):
        for filename in files:
            filename_lower = filename.lower()
            if filename_lower.endswith(".ply") or filename_lower.endswith(".obj"):
                if not filename_lower.endswith("_sym.ply"):
                    filelist.append(os.path.join(home, filename))
    filelist = sorted(
        filelist,
        key=lambda path: (
            os.path.relpath(path, directory).replace(os.sep, "/").casefold(),
            os.path.relpath(path, directory).replace(os.sep, "/"),
        ),
    )
    validate_unique_sidecar_targets(filelist)
    return filelist


def validate_unique_sidecar_targets(mesh_paths) -> None:
    """Reject mesh sets whose legacy sidecar names would collide."""

    targets = {}
    for mesh_path in mesh_paths:
        path = Path(mesh_path)
        key = (str(path.parent.resolve()).casefold(), path.stem.casefold())
        previous = targets.get(key)
        if previous is not None and Path(previous).resolve() != path.resolve():
            raise ValueError(
                f"Mesh files with the same stem share annotation sidecars: "
                f"{Path(previous).name}, {path.name}. Rename or separate these files before processing."
            )
        targets[key] = path


def _ensure_unique_sidecar_target(mesh_path: str) -> Path:
    path = Path(mesh_path)
    siblings = [
        path.with_suffix(suffix)
        for suffix in SIDECAR_MESH_SUFFIXES
        if path.with_suffix(suffix).exists()
        and path.with_suffix(suffix).resolve() != path.resolve()
    ]
    if siblings:
        names = ", ".join([path.name, *(sibling.name for sibling in siblings)])
        raise ValueError(
            f"Mesh files with the same stem share annotation sidecars: "
            f"{names}. Rename or separate these files before processing."
        )
    return path


def sidecar_sym_type_path(mesh_path: str) -> str:
    path = _ensure_unique_sidecar_target(mesh_path)
    return str(path.with_name(path.stem + "_sym_type.json"))


def sidecar_sym_ply_path(mesh_path: str) -> str:
    path = _ensure_unique_sidecar_target(mesh_path)
    return str(path.with_name(path.stem + "_sym.ply"))


def parse_symmetry_type_dict(raw: dict) -> SymmetryAnnotationState:
    """Parse v1 or v2 symmetry JSON into runtime state."""

    if not isinstance(raw, dict):
        raise ValueError("Symmetry annotation JSON must contain an object at the top level.")

    schema = raw.get("schema_version", SYMMETRY_SCHEMA_V1)
    if isinstance(schema, bool) or schema not in (SYMMETRY_SCHEMA_V1, SYMMETRY_SCHEMA_V2):
        raise ValueError(f"Unsupported symmetry annotation schema_version: {schema!r}")
    v2 = raw.get("kasal_v2", {}) if schema == SYMMETRY_SCHEMA_V2 else {}
    if not isinstance(v2, dict):
        raise ValueError("kasal_v2 must be a JSON object.")

    sym_type = raw.get("sym_type", "None")
    n_fold = raw.get("n-fold", 2)
    adi_c = raw.get("ADI-C", False)
    axis_xyz = raw.get("axis_xyz", "None")
    current_obj_info = raw.get("current_obj_info", {})

    if not isinstance(sym_type, str) or sym_type not in config.symmetry_type_options:
        raise ValueError(f"Unknown symmetry type: {sym_type!r}")
    if isinstance(n_fold, bool) or not isinstance(n_fold, int) or not 2 <= n_fold <= config.max_n_fold:
        raise ValueError(f"n-fold must be an integer from 2 to {config.max_n_fold}")
    if not isinstance(adi_c, bool):
        raise ValueError("ADI-C must be a boolean")
    if not isinstance(axis_xyz, str) or axis_xyz not in config.axis_constraint_options:
        raise ValueError(f"Unknown axis_xyz value: {axis_xyz!r}")
    if not isinstance(current_obj_info, dict):
        raise ValueError("current_obj_info must be a JSON object")

    if v2:
        compute_engine = validate_engine(v2.get("compute_engine", KASALV1_ENGINE))
        return SymmetryAnnotationState(
            sym_type=sym_type,
            n_fold=n_fold,
            adi_c=adi_c,
            axis_xyz=axis_xyz,
            current_obj_info=current_obj_info,
            sym_type_source=v2.get("sym_type_source", "user"),
            n_fold_source=v2.get("n_fold_source", "user"),
            axis_xyz_source=v2.get("axis_xyz_source", "none"),
            compute_engine=compute_engine,
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

    n_fold = state.n_fold
    if n_fold > config.max_n_fold:
        n_fold = config.max_n_fold
    if n_fold < 2:
        n_fold = 2

    symmetry_type_dict: dict[str, Any] = {
        "schema_version": SYMMETRY_SCHEMA_V2,
        "sym_type": state.sym_type,
        "n-fold": n_fold,
        "ADI-C": state.adi_c,
        "current_obj_info": state.current_obj_info,
        "kasal_v2": {
            "sym_type_source": state.sym_type_source,
            "n_fold_source": state.n_fold_source,
            "axis_xyz_source": state.axis_xyz_source,
            "compute_engine": state.compute_engine,
        },
    }
    if state.axis_xyz != "None":
        symmetry_type_dict["axis_xyz"] = state.axis_xyz
    return symmetry_type_dict
