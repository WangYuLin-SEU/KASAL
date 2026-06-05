# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Bridge kasalv2 rotational symmetry analysis into KASAL UI/BOP format.

from __future__ import annotations

from dataclasses import replace
from typing import Any

import kasal.config.config as config
from kasal.device import resolve_torch_device
from kasal.rotational_symmetry import analyze_rotational_symmetry, seed_everything
from kasal.rotational_symmetry.config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig
from kasal.rotational_symmetry.output_schema import build_analysis_result, build_model_output_json
from kasal.utils.compute_progress import get_compute_progress, progress_pulse, progress_reporting_enabled
from kasal.utils.mesh_preprocess import MeshPreprocessResult, enrich_mesh_bundle, load_mesh_for_analysis


def _analysis_config_with_device(cfg: SymmetryAnalysisConfig | None = None) -> SymmetryAnalysisConfig:
    base = DEFAULT_ANALYSIS_CONFIG if cfg is None else cfg
    device = resolve_torch_device("cuda")
    return replace(
        base,
        axis_search=replace(base.axis_search, device=device),
        texture=replace(base.texture, device=device),
        classification=replace(
            base.classification,
            rotation_loss_device=device if base.classification.rotation_loss_device is None else base.classification.rotation_loss_device,
        ),
    )


def run_kasalv2_on_mesh(mesh_path: str, tex: bool = False, policy: str | None = None) -> dict[str, Any]:
    """Preprocess mesh, run kasalv2, return BOP-compatible dict."""

    pg = get_compute_progress()
    if progress_reporting_enabled():
        pg.set_stage("preprocess", "Loading & preprocessing mesh", fraction=0.12, indeterminate=False)
        progress_pulse()
    bundle = load_mesh_for_analysis(mesh_path, need_colors=tex, policy=policy)
    return run_kasalv2_on_bundle(bundle, tex=tex)


def run_kasalv2_on_bundle(bundle: MeshPreprocessResult, tex: bool = False) -> dict[str, Any]:
    """Run kasalv2 on an existing preprocess bundle."""

    cfg = _analysis_config_with_device()
    seed_everything(int(cfg.seed.value))
    pg = get_compute_progress()
    if progress_reporting_enabled():
        pg.set_stage(
            "analyze",
            "kasalv2 symmetry analysis (CPU may take several minutes)",
            fraction=0.35,
            indeterminate=False,
        )
        progress_pulse()
    raw_result, n_fold = analyze_rotational_symmetry(bundle.model_input, tex=tex, config=cfg)
    if progress_reporting_enabled():
        pg.set_stage("export", "Building BOP output", fraction=0.92, indeterminate=False)
        progress_pulse()
    analysis = build_analysis_result(raw_result, n_fold)
    bop = build_model_output_json(analysis, bundle.bbox_info)
    bop["_preprocess_meta"] = dict(bundle.preprocess_meta)
    bop["_backend"] = bundle.backend
    return bop


def kasalv2_result_to_ui(bop_dict: dict[str, Any]) -> tuple[str, int]:
    """Map kasalv2 BOP output to UI sym_type and n-fold."""

    sym_type = bop_dict.get("rot_sym_type") or "None"
    n_fold = bop_dict.get("n_fold", 2)
    if not bop_dict.get("has_rot_sym", False):
        return "None", 2
    if sym_type in config.ui_options:
        ui_type = sym_type
    else:
        ui_type = sym_type if sym_type in config.ui_options else config.ui_options[0]
    try:
        if str(n_fold) == "inf":
            ui_n = config.ui_int
        else:
            ui_n = int(n_fold)
    except (TypeError, ValueError):
        ui_n = 2
    if ui_n < 2:
        ui_n = 2
    if ui_n > config.ui_int_upper:
        ui_n = config.ui_int_upper
    return ui_type, ui_n


def bop_to_current_obj_info(bop: dict[str, Any]) -> dict[str, Any]:
    """Strip internal keys for current_obj_info persistence."""

    skip = {"_preprocess_meta", "_backend"}
    return {k: v for k, v in bop.items() if k not in skip}
