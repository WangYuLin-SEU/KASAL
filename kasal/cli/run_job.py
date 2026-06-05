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
import os
import sys

import kasal.config.config as config
from kasal.compute.symmetry_job import SymmetryJobSpec, run_symmetry_job
from kasal.utils.annotation_state import initialize_dataset_dirty_state, is_object_dirty
from kasal.utils.io_json import get_all_ply_obj
from kasal.utils.io_ply_meshlab import is_pymeshlab_available
from kasal.utils.mesh_preprocess import resolve_preprocess_policy


HEADLESS_WARNING = """[KASAL WARNING] PyMeshLab is not installed. Headless mode will use kasalv2 mesh loading ONLY.
  - Legacy simplify (simplify_3DModel_v2) is disabled.
  - If loading fails, see error message: install requirements-full-* OR fix mesh geometry.
  - Installing pymeshlab on this machine enables kasalv1 / adaptive fallback in CLI too.
"""


def _validate_headless_policy(policy: str) -> None:
    if is_pymeshlab_available():
        return
    if policy in ("kasalv1", "kasal_legacy", "kasalv2_adaptive"):
        print(
            f"[KASAL ERROR] policy={policy} requires PyMeshLab. Use kasalv2_strict or install requirements-full-*.",
            file=sys.stderr,
        )
        sys.exit(2)


def _run_job_file(job_path: str) -> int:
    with open(job_path, "r", encoding="utf-8") as f:
        job_doc = json.load(f)

    defaults = job_doc.get("defaults", {})
    policy = defaults.get("mesh_preprocess", {}).get("policy", "kasalv2_strict")
    if not is_pymeshlab_available():
        print(HEADLESS_WARNING, file=sys.stderr)
        policy = "kasalv2_strict"
    _validate_headless_policy(policy)

    mesh_dir = job_doc.get("mesh_dir") or job_doc.get("input_dir")
    if not mesh_dir:
        print("job JSON requires mesh_dir or input_dir", file=sys.stderr)
        return 1

    files = job_doc.get("meshes") or get_all_ply_obj(mesh_dir)
    config.files_name_list = files
    only_dirty = defaults.get("only_dirty", True)
    if only_dirty:
        initialize_dataset_dirty_state(files)

    engine = defaults.get("engine", "kasalv2")
    tex = defaults.get("tex", False)
    exports = defaults.get("exports", ["sym_type_json", "sym_ply"])
    ok = 0
    fail = 0

    for i, mesh_path in enumerate(files):
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
