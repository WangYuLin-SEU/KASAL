# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Shared symmetry computation kernel for GUI and headless CLI.

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import kasal.config.config as config
from kasal.engine_routing import (
    engine_routing_note,
    kasalv1_skip_reason,
    should_use_kasalv1_engine,
)
from kasal.kasalv2_bridge import (
    bop_to_current_obj_info,
    kasalv2_result_to_ui,
    run_kasalv2_on_mesh,
)
from kasal.symmetry_lab.symmetry_axis_localization import cal_model_sym
from kasal.symmetry_lab.symmetry_axis_template import get_sym_axis_temp
from kasal.utils.io_json import build_symmetry_type_dict
from kasal.utils.io_ply import save_ply_model
from kasal.utils.compute_progress import get_compute_progress, progress_pulse, progress_reporting_enabled
from kasal.utils.mesh_preprocess import load_mesh_for_analysis
from kasal.viz.symmetry_visual_export import build_model_i_for_save_ply
from kasal.version_names import (
    KASALV1_ENGINE,
    KASALV2_ENGINE,
    is_kasalv1_engine,
    normalize_engine,
)


@dataclass
class SymmetryJobSpec:
    mesh_path: str
    engine: str = KASALV2_ENGINE
    sym_type: str = "None"
    n_fold: int = 2
    adi_c: bool = False
    axis_xyz: str = "None"
    tex: bool | None = None
    policy: str | None = None
    sym_type_source: str | None = None
    n_fold_source: str | None = None
    exports: list[str] = field(default_factory=lambda: ["sym_type_json", "sym_ply"])


@dataclass
class SymmetryJobResult:
    success: bool
    current_obj_info: dict = field(default_factory=dict)
    sym_type: str = "None"
    n_fold: int = 2
    error: str | None = None
    engine_used: str = ""


def _kasalv1_sym_op(sym_type: str) -> str | None:
    if sym_type == "C(>1): Cylindrical Item":
        return "symmetries_continuous_2"
    if sym_type == "C(=1): Circular Item":
        return "symmetries_continuous"
    if sym_type in [
        "D(>1): n-fold Prismatic Item",
        "D(=1): n-fold Pyramidal Item",
        "P(4): Tetrahedral Item",
        "P(8): Octahedral Item",
        "P(20): Icosahedral Item",
    ]:
        return "symmetries_discrete"
    if sym_type == "C(>>1): Spherical Item":
        return "symmetries_continuous_3"
    return None


def resolve_symmetry_job_engine(job: SymmetryJobSpec) -> str:
    """Pick kasalv1 vs kasalv2 from job fields (shared by GUI and CLI)."""

    unlabeled_auto = (
        job.sym_type in ("None", "")
        and job.sym_type_source not in ("user",)
        and job.n_fold_source not in ("user",)
    )
    if unlabeled_auto:
        return KASALV2_ENGINE
    if is_kasalv1_engine(job.engine):
        return KASALV1_ENGINE
    if job.sym_type_source == "user" or job.n_fold_source == "user":
        return KASALV1_ENGINE
    return normalize_engine(job.engine)


_resolve_job_engine = resolve_symmetry_job_engine


def kasalv1_job_blocked_reason(job: SymmetryJobSpec) -> str | None:
    """Return a block reason when kasalv1 was selected but labels are not user-set."""

    engine = resolve_symmetry_job_engine(job)
    if not should_use_kasalv1_engine(job.axis_xyz, engine):
        return None
    return kasalv1_skip_reason(job.sym_type, job.sym_type_source, job.n_fold_source)


def symmetry_job_routing_note(job: SymmetryJobSpec) -> str | None:
    return engine_routing_note(job.engine, resolve_symmetry_job_engine(job))


def run_symmetry_job(job: SymmetryJobSpec) -> SymmetryJobResult:
    """Run one symmetry job (preprocess → engine → export dict)."""

    tex = job.tex if job.tex is not None else job.adi_c
    engine = _resolve_job_engine(job)
    if should_use_kasalv1_engine(job.axis_xyz, engine):
        return _run_kasalv1_job(job, tex=tex)
    return _run_kasalv2_job(job, tex=tex)


def _run_kasalv2_job(job: SymmetryJobSpec, *, tex: bool) -> SymmetryJobResult:
    try:
        bop = run_kasalv2_on_mesh(job.mesh_path, tex=tex, policy=job.policy)
        sym_type, n_fold = kasalv2_result_to_ui(bop)
        current_obj_info = bop_to_current_obj_info(bop)
        bundle = load_mesh_for_analysis(job.mesh_path, need_colors=tex, policy=job.policy)
        model_viz = build_model_i_for_save_ply(bundle.kasalv1_model, current_obj_info, sym_type)
        stem = os.path.basename(job.mesh_path).split(".")[0]
        out_dir = os.path.dirname(job.mesh_path)
        if "sym_ply" in job.exports and sym_type != "None":
            save_ply_model(model_viz, os.path.join(out_dir, stem + "_sym.ply"))
        state = _job_state(
            job,
            sym_type,
            n_fold,
            current_obj_info,
            engine=KASALV2_ENGINE,
            sources=("kasalv2_auto", "kasalv2_auto"),
        )
        if "sym_type_json" in job.exports:
            from kasal.utils.io_json import write_dict2json

            write_dict2json(os.path.join(out_dir, stem + "_sym_type.json"), build_symmetry_type_dict(state))
        return SymmetryJobResult(
            success=True,
            current_obj_info=current_obj_info,
            sym_type=sym_type,
            n_fold=n_fold,
            engine_used=KASALV2_ENGINE,
        )
    except Exception as exc:
        return SymmetryJobResult(success=False, error=str(exc), engine_used=KASALV2_ENGINE)


def _run_kasalv1_job(job: SymmetryJobSpec, *, tex: bool) -> SymmetryJobResult:
    try:
        skip = kasalv1_skip_reason(job.sym_type, job.sym_type_source, job.n_fold_source)
        if skip:
            return SymmetryJobResult(success=False, error=skip, engine_used=KASALV1_ENGINE)
        sym_type = job.sym_type
        sym_info_ = get_sym_axis_temp(sym_type, job.n_fold)
        sym_op = _kasalv1_sym_op(sym_type)
        adi_op = "colors" if tex else "pts"
        pg = get_compute_progress()
        if progress_reporting_enabled():
            pg.set_stage("preprocess", "Loading mesh for kasalv1", fraction=0.15, indeterminate=False)
            progress_pulse()
        bundle = load_mesh_for_analysis(job.mesh_path, need_colors=tex, policy=job.policy)
        model_i_ = dict(bundle.kasalv1_model)
        if progress_reporting_enabled():
            pg.set_stage(
                "cal_sym",
                "kasalv1 axis localization (ICP)",
                fraction=0.45,
                indeterminate=False,
            )
            progress_pulse()
        model_i_ = cal_model_sym(
            model_i_,
            step_path=sym_info_,
            sym_op=sym_op,
            sym_aware=True,
            op=adi_op,
            sample_num=config.sample_num,
            icp_op=True,
            xyz_op=job.axis_xyz,
        )
        stem = os.path.basename(job.mesh_path).split(".")[0]
        out_dir = os.path.dirname(job.mesh_path)
        model_info_i = dict(model_i_)
        if progress_reporting_enabled():
            pg.set_stage("export", "Saving sym.ply / JSON", fraction=0.9, indeterminate=False)
            progress_pulse()
        if "sym_ply" in job.exports and sym_type != "None":
            model_info_i = save_ply_model(model_i_, os.path.join(out_dir, stem + "_sym.ply"))
        state = _job_state(
            job,
            sym_type,
            job.n_fold,
            model_info_i,
            engine=KASALV1_ENGINE,
            sources=(job.sym_type_source or "user", job.n_fold_source or "user"),
        )
        if "sym_type_json" in job.exports:
            from kasal.utils.io_json import write_dict2json

            write_dict2json(os.path.join(out_dir, stem + "_sym_type.json"), build_symmetry_type_dict(state))
        return SymmetryJobResult(
            success=True,
            current_obj_info=model_info_i,
            sym_type=sym_type,
            n_fold=job.n_fold,
            engine_used=KASALV1_ENGINE,
        )
    except Exception as exc:
        return SymmetryJobResult(success=False, error=str(exc), engine_used=KASALV1_ENGINE)


def _job_state(job, sym_type, n_fold, current_obj_info, *, engine, sources):
    from kasal.utils.io_json import SymmetryAnnotationState

    return SymmetryAnnotationState(
        sym_type=sym_type,
        n_fold=n_fold,
        adi_c=job.adi_c,
        axis_xyz=job.axis_xyz,
        current_obj_info=current_obj_info,
        sym_type_source=sources[0],
        n_fold_source=sources[1],
        axis_xyz_source="user" if job.axis_xyz != "None" else "none",
        compute_engine=engine,
        kasalv2_snapshot=current_obj_info if engine == KASALV2_ENGINE else None,
    )


def apply_job_result_to_config(job: SymmetryJobSpec, result: SymmetryJobResult) -> None:
    """Mirror successful job output into global config."""

    if not result.success:
        return
    config.ui_options_selected = result.sym_type
    config.ui_int = result.n_fold
    config.current_obj_info = result.current_obj_info
    if result.engine_used == KASALV2_ENGINE:
        config.sym_type_source = "kasalv2_auto"
        config.n_fold_source = "kasalv2_auto"
        config.kasalv2_snapshot = result.current_obj_info
    else:
        config.sym_type_source = job.sym_type_source or "user"
        config.n_fold_source = job.n_fold_source or "user"
    config.compute_engine = normalize_engine(result.engine_used)


# Backward-compatible aliases (deprecated).
_run_legacy_job = _run_kasalv1_job
_legacy_sym_op = _kasalv1_sym_op
