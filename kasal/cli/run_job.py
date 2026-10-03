# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Headless symmetry batch runner.

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

import kasal.config.runtime as config
from kasal.compute.symmetry_job import SymmetryJobSpec, run_symmetry_job
from kasal.annotations.state import initialize_dataset_dirty_state, is_object_dirty
from kasal.annotations.io import discover_annotation_meshes
from kasal.geometry.mesh_simplification import is_pymeshlab_available
from kasal.version_names import (
    KASALV1_PREPROCESS,
    KASALV2_ADAPTIVE,
    KASALV2_ENGINE,
    KASALV2_STRICT,
    validate_engine,
    validate_preprocess_policy,
)


HEADLESS_WARNING = """[KASAL WARNING] PyMeshLab is not installed. Headless mode will use kasalv2 mesh loading ONLY.
  - Legacy simplify (simplify_mesh) is disabled.
  - If loading fails, install a full profile with scripts/install_deps.py OR fix mesh geometry.
  - Installing pymeshlab on this machine enables kasalv1 / adaptive fallback in CLI too.
"""


def _validate_headless_policy(policy: str) -> None:
    if is_pymeshlab_available():
        return
    if policy in (KASALV1_PREPROCESS, KASALV2_ADAPTIVE):
        raise ValueError(
            f"policy={policy} requires PyMeshLab; use {KASALV2_STRICT} or install "
            "a full-cpu/full-gpu profile"
        )


def _require_mapping(value, field_name: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _validate_job_document(job_doc) -> tuple[Mapping, str, str | None, list[str] | None]:
    job = _require_mapping(job_doc, "job document")
    job_version = job.get("job_version", 1)
    if isinstance(job_version, bool) or not isinstance(job_version, int) or job_version != 1:
        raise ValueError(f"unsupported job_version: {job_version!r}; expected 1")

    defaults = _require_mapping(job.get("defaults", {}), "defaults")
    preprocess = _require_mapping(defaults.get("mesh_preprocess", {}), "defaults.mesh_preprocess")
    raw_policy = preprocess.get("policy", KASALV2_STRICT)
    if not isinstance(raw_policy, str):
        raise ValueError("defaults.mesh_preprocess.policy must be a string")
    policy = validate_preprocess_policy(raw_policy)

    mesh_dir = job.get("mesh_dir") or job.get("input_dir")
    if mesh_dir is not None and (not isinstance(mesh_dir, str) or not mesh_dir.strip()):
        raise ValueError("mesh_dir or input_dir must be a non-empty string")

    raw_meshes = job.get("meshes")
    meshes = None
    if raw_meshes is not None:
        if not isinstance(raw_meshes, list) or any(
            not isinstance(path, str) or not path.strip() for path in raw_meshes
        ):
            raise ValueError("meshes must be a JSON array of non-empty path strings")
        meshes = list(raw_meshes)
    if mesh_dir is None and meshes is None:
        raise ValueError("job JSON requires mesh_dir/input_dir or an explicit meshes array")

    raw_engine = defaults.get("engine", KASALV2_ENGINE)
    if not isinstance(raw_engine, str):
        raise ValueError("defaults.engine must be a string")
    validate_engine(raw_engine)

    for field_name in ("tex", "only_dirty"):
        if field_name in defaults and not isinstance(defaults[field_name], bool):
            raise ValueError(f"defaults.{field_name} must be a boolean")
    for field_name in ("sym_type", "axis_xyz"):
        if field_name in defaults and not isinstance(defaults[field_name], str):
            raise ValueError(f"defaults.{field_name} must be a string")

    exports = defaults.get("exports", ["sym_type_json", "sym_ply"])
    if not isinstance(exports, list) or any(not isinstance(item, str) for item in exports):
        raise ValueError("defaults.exports must be a JSON array of strings")
    unknown_exports = sorted(set(exports) - {"sym_type_json", "sym_ply"})
    if unknown_exports:
        raise ValueError(f"unknown export type(s): {', '.join(unknown_exports)}")

    if "n_fold" in defaults:
        n_fold = defaults["n_fold"]
        if isinstance(n_fold, bool) or not isinstance(n_fold, int) or not 2 <= n_fold <= config.max_n_fold:
            raise ValueError(f"defaults.n_fold must be an integer from 2 to {config.max_n_fold}")

    return defaults, policy, mesh_dir, meshes


def _resolve_job_path(value: str, job_directory: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = job_directory / path
    return path.resolve()


def _run_job_file(job_path: str) -> int:
    job_file = Path(job_path).expanduser().resolve()
    job_directory = job_file.parent
    try:
        with job_file.open("r", encoding="utf-8-sig") as f:
            job_doc = json.load(f)
        defaults, policy, mesh_dir, explicit_meshes = _validate_job_document(job_doc)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid job file {job_path}: {exc}", file=sys.stderr)
        return 2

    if not is_pymeshlab_available():
        print(HEADLESS_WARNING, file=sys.stderr)
    try:
        _validate_headless_policy(policy)
    except ValueError as exc:
        print(f"[KASAL ERROR] {exc}", file=sys.stderr)
        return 2

    try:
        if explicit_meshes is not None:
            files = [str(_resolve_job_path(path, job_directory)) for path in explicit_meshes]
        else:
            mesh_directory = _resolve_job_path(mesh_dir, job_directory)
            if not mesh_directory.is_dir():
                raise ValueError(f"mesh directory does not exist or is not a directory: {mesh_dir}")
            files = discover_annotation_meshes(str(mesh_directory))
    except (OSError, ValueError) as exc:
        print(f"Invalid mesh dataset: {exc}", file=sys.stderr)
        return 1
    config.mesh_paths = files
    only_dirty = defaults.get("only_dirty", True)
    annotation_errors = {}
    if only_dirty:
        try:
            annotation_errors = initialize_dataset_dirty_state(files)
        except ValueError as exc:
            print(f"Invalid mesh dataset: {exc}", file=sys.stderr)
            return 1

    engine = defaults.get("engine", "kasalv2")
    tex = defaults.get("tex", False)
    exports = defaults.get("exports", ["sym_type_json", "sym_ply"])
    ok = 0
    fail = 0

    for i, mesh_path in enumerate(files):
        if i in annotation_errors:
            fail += 1
            print(f"FAIL {mesh_path}: invalid annotation: {annotation_errors[i]}", file=sys.stderr)
            continue
        if only_dirty and not is_object_dirty(i):
            continue
        spec = SymmetryJobSpec(
            mesh_path=mesh_path,
            engine=engine,
            sym_type=defaults.get("sym_type", "None"),
            n_fold=defaults.get("n_fold", 2),
            adi_c=tex,
            axis_xyz=defaults.get("axis_xyz", "None"),
            tex=tex,
            policy=policy,
            exports=exports,
        )
        result = run_symmetry_job(spec)
        if result.success:
            ok += 1
            print(f"OK {mesh_path} engine={result.engine_used}")
        else:
            fail += 1
            print(f"FAIL {mesh_path}: {result.error}", file=sys.stderr)

    print(f"Done: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="KASAL headless symmetry job runner")
    parser.add_argument("job_json", help="Path to job JSON file")
    args = parser.parse_args(argv)
    return _run_job_file(args.job_json)


if __name__ == "__main__":
    raise SystemExit(main())
