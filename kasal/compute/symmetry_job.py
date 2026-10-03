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

from dataclasses import dataclass, field
from pathlib import Path

import kasal.config.runtime as config
from kasal.config.algorithms import (
    DEFAULT_ANALYSIS_CONFIG,
    DEFAULT_KASALV1_CONFIG,
    build_analysis_config,
)
from kasal.device import resolve_torch_device
from kasal.utils.atomic_file import atomic_output_path
from kasal.utils.compute_progress import report_compute_stage
from kasal.annotations.io import (
    SymmetryAnnotationState,
    build_symmetry_type_dict,
    sidecar_sym_ply_path,
    sidecar_sym_type_path,
)
from kasal.utils.io_json import write_json
from kasal.version_names import (
    KASALV1_ENGINE,
    KASALV2_ENGINE,
    is_kasalv1_engine,
    normalize_engine,
)


@dataclass
class SymmetryJobSpec:
    """Inputs for one job; tex optionally overrides the recorded adi_c setting."""

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
    """Job outcome, including the actual engine and any failure message."""

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

    if job.axis_xyz not in (None, "None"):
        return KASALV1_ENGINE
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


def kasalv1_job_blocked_reason(job: SymmetryJobSpec) -> str | None:
    """Return a block reason when kasalv1 has no concrete symmetry type."""

    engine = resolve_symmetry_job_engine(job)
    if engine != KASALV1_ENGINE:
        return None
    if job.sym_type not in ("None", ""):
        return None
    return (
        "kasalv1 requires symmetry type and n-fold set in the UI "
        "(object is unlabeled)."
    )


def symmetry_job_routing_note(job: SymmetryJobSpec) -> str | None:
    if is_kasalv1_engine(job.engine) and resolve_symmetry_job_engine(job) == KASALV2_ENGINE:
        return (
            "Unlabeled object: compute will use kasalv2 "
            "(kasalv1 requires user-set symmetry type and n-fold)."
        )
    return None


def run_symmetry_job(job: SymmetryJobSpec) -> SymmetryJobResult:
    """Resolve the engine, then preprocess, analyze and export a single mesh."""

    tex = job.tex if job.tex is not None else job.adi_c
    engine = resolve_symmetry_job_engine(job)
    if engine == KASALV1_ENGINE:
        return _run_kasalv1_job(job, tex=tex)
    return _run_kasalv2_job(job, tex=tex)


def _save_ply_model_atomically(model: dict, output_path: str) -> dict:
    """Write a visualization beside its target, then replace it as one operation."""

    from kasal.utils.io_ply import save_ply_model

    with atomic_output_path(output_path) as temporary:
        return save_ply_model(
            model, str(temporary),
            arrow_ratio=config.arrow_ratio,
            save_twofold_axis=config.save_twofold_axis,
        )


def _run_kasalv2_job(job: SymmetryJobSpec, *, tex: bool) -> SymmetryJobResult:
    try:
        from kasal.rotational_symmetry.analyzer import analyze_rotational_symmetry
        from kasal.rotational_symmetry.output_schema import build_analysis_result, build_model_output_json
        from kasal.utils.mesh_preprocess import load_mesh_for_analysis

        report_compute_stage("preprocess", "Loading & preprocessing mesh", fraction=0.12)
        bundle = load_mesh_for_analysis(job.mesh_path, need_colors=tex, policy=job.policy)
        analysis_config = build_analysis_config(
            device=resolve_torch_device(DEFAULT_ANALYSIS_CONFIG.axis_search.device)
        )
        report_compute_stage(
            "analyze", "kasalv2 symmetry analysis (CPU may take several minutes)", fraction=0.35
        )
        raw_result, n_fold = analyze_rotational_symmetry(bundle.model_input, tex=tex, config=analysis_config)
        report_compute_stage("export", "Building BOP output", fraction=0.92)
        analysis = build_analysis_result(raw_result, n_fold)
        current_obj_info = build_model_output_json(analysis, bundle.bbox_info)
        sym_type, n_fold = _kasalv2_result_to_ui(current_obj_info)
        if "sym_ply" in job.exports:
            sym_ply_path = sidecar_sym_ply_path(job.mesh_path)
            if sym_type == "None":
                Path(sym_ply_path).unlink(missing_ok=True)
            else:
                from kasal.viz.symmetry_visual_export import build_symmetry_visualization_model

                model_viz = build_symmetry_visualization_model(bundle.kasalv1_model, current_obj_info, sym_type)
                _save_ply_model_atomically(model_viz, sym_ply_path)
        if "sym_type_json" in job.exports:
            state = _job_state(
                job,
                sym_type,
                n_fold,
                current_obj_info,
                engine=KASALV2_ENGINE,
                sym_type_source="kasalv2_auto",
                n_fold_source="kasalv2_auto",
            )
            write_json(sidecar_sym_type_path(job.mesh_path), build_symmetry_type_dict(state))
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
        skip = kasalv1_job_blocked_reason(job)
        if skip:
            return SymmetryJobResult(success=False, error=skip, engine_used=KASALV1_ENGINE)
        from kasal.symmetry_lab.symmetry_axis_localization import localize_symmetry_axes
        from kasal.symmetry_lab.symmetry_axis_template import get_symmetry_axis_template
        from kasal.utils.mesh_preprocess import load_mesh_for_analysis

        sym_type = job.sym_type
        axis_template = get_symmetry_axis_template(sym_type, job.n_fold)
        sym_op = _kasalv1_sym_op(sym_type)
        score_mode = "colors" if tex else "pts"
        report_compute_stage("preprocess", "Loading mesh for kasalv1", fraction=0.15)
        bundle = load_mesh_for_analysis(job.mesh_path, need_colors=tex, policy=job.policy)
        model = dict(bundle.kasalv1_model)
        report_compute_stage("cal_sym", "kasalv1 axis localization (ICP)", fraction=0.45)
        model = localize_symmetry_axes(
            model,
            template_or_step_path=axis_template,
            symmetry_operation=sym_op,
            color_symmetry_orbits=True,
            score_mode=score_mode,
            config=DEFAULT_KASALV1_CONFIG,
            refine_with_icp=True,
            axis_constraint=job.axis_xyz,
        )
        model_info = dict(model)
        report_compute_stage("export", "Saving sym.ply / JSON", fraction=0.9)
        if "sym_ply" in job.exports and sym_type != "None":
            model_info = _save_ply_model_atomically(model, sidecar_sym_ply_path(job.mesh_path))
        if "sym_type_json" in job.exports:
            state = _job_state(
                job,
                sym_type,
                job.n_fold,
                model_info,
                engine=KASALV1_ENGINE,
                sym_type_source=job.sym_type_source or "user",
                n_fold_source=job.n_fold_source or "user",
            )
            write_json(sidecar_sym_type_path(job.mesh_path), build_symmetry_type_dict(state))
        return SymmetryJobResult(
            success=True,
            current_obj_info=model_info,
            sym_type=sym_type,
            n_fold=job.n_fold,
            engine_used=KASALV1_ENGINE,
        )
    except Exception as exc:
        return SymmetryJobResult(success=False, error=str(exc), engine_used=KASALV1_ENGINE)


def _job_state(job, sym_type, n_fold, current_obj_info, *, engine, sym_type_source, n_fold_source):
    return SymmetryAnnotationState(
        sym_type=sym_type,
        n_fold=n_fold,
        adi_c=job.adi_c,
        axis_xyz=job.axis_xyz,
        current_obj_info=current_obj_info,
        sym_type_source=sym_type_source,
        n_fold_source=n_fold_source,
        axis_xyz_source="user" if job.axis_xyz != "None" else "none",
        compute_engine=engine,
    )


def apply_job_result_to_config(job: SymmetryJobSpec, result: SymmetryJobResult) -> None:
    """Mirror successful job output into global config."""

    if not result.success:
        return
    config.selected_symmetry_type = result.sym_type
    config.selected_n_fold = result.n_fold
    config.adi_color_enabled = job.adi_c
    config.selected_axis_constraint = job.axis_xyz
    config.axis_xyz_source = "user" if job.axis_xyz != "None" else "none"
    config.current_obj_info = result.current_obj_info
    if result.engine_used == KASALV2_ENGINE:
        config.sym_type_source = "kasalv2_auto"
        config.n_fold_source = "kasalv2_auto"
    else:
        config.sym_type_source = job.sym_type_source or "user"
        config.n_fold_source = job.n_fold_source or "user"
    config.compute_engine = normalize_engine(result.engine_used)


def _kasalv2_result_to_ui(bop_dict: dict) -> tuple[str, int]:
    """Map kasalv2 BOP output to UI sym_type and n-fold."""

    sym_type = bop_dict.get("rot_sym_type") or "None"
    n_fold = bop_dict.get("n_fold", 2)
    if not bop_dict.get("has_rot_sym", False):
        return "None", 2
    ui_type = sym_type if sym_type in config.symmetry_type_options else config.symmetry_type_options[0]
    try:
        if str(n_fold) == "inf":
            ui_n = config.selected_n_fold
        else:
            ui_n = int(n_fold)
    except (TypeError, ValueError):
        ui_n = 2
    if ui_n < 2:
        ui_n = 2
    if ui_n > config.max_n_fold:
        ui_n = config.max_n_fold
    return ui_type, ui_n
