# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import random

import numpy as np

from .axis_search import search_primary_axis, search_secondary_axis_at_angle
from .config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig
from .consistency import geom_pi_axis_consistency_ok
from .contour import classify_circle_vs_polygon, extract_flattened_contour_uv_from_mesh
from .geometry import (
    build_rotation_transform,
    compute_axis_rotation_loss,
    generate_symmetry_transforms,
    get_template_axis_angle,
    normalize_vector,
    refine_axis_center_with_icp,
)
from .periodicity import estimate_axis_periodicity


def is_continuous_fold_marker(n_fold: object) -> bool:
    """Return True when a fold value represents continuous rotational symmetry."""

    try:
        return bool(np.isinf(float(n_fold)))
    except (TypeError, ValueError):
        return False


def normalize_estimated_fold(n_fold: object) -> int | float:
    """Normalize periodicity output while preserving the continuous marker."""

    if is_continuous_fold_marker(n_fold):
        return float("inf")
    try:
        return int(n_fold)
    except (TypeError, ValueError):
        return 0


def seed_everything(seed: int):
    """Seed Python, NumPy and Torch to keep the analysis deterministic."""

    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except Exception:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def estimate_discrete_rotation_angle(n_fold, *, config: SymmetryAnalysisConfig):
    """Convert a fold count to the discrete rotation angle used downstream."""

    if is_continuous_fold_marker(n_fold):
        return float(config.classification.large_fold_angle_window_deg)
    if n_fold <= config.classification.max_discrete_fold_direct:
        return 360.0 / n_fold
    step = 360.0 / n_fold
    return int(config.classification.large_fold_angle_window_deg / step) * step


def build_axis_info(axis, center_ch, rotation_angle_deg):
    """Create the lightweight axis record consumed by ICP refinement."""

    return {
        "axis": axis,
        "axis_mat": [build_rotation_transform(axis, rotation_angle_deg, center_ch)],
    }


def refine_secondary_twofold_axis(model_input, pts, primary_axis, center_ch, *, config: SymmetryAnalysisConfig):
    """Search, refine and validate a 2-fold side axis."""

    diameter = model_input["diameter"]
    axis_info = search_secondary_axis_at_angle(
        config.classification.two_fold_angle_deg,
        pts,
        primary_axis,
        div=2,
        center_ch=center_ch,
        config=config,
    )
    refined_center, refined_axis = refine_axis_center_with_icp(axis_info, model_input, center_ch, config=config)
    loss = compute_axis_rotation_loss(
        pts,
        refined_axis,
        180.0,
        device=config.classification.rotation_loss_device,
    )
    exists = loss < diameter * config.classification.secondary_axis_loss_ratio
    ok_2fold = geom_pi_axis_consistency_ok(
        pts=pts,
        center_ch=refined_center,
        axis=refined_axis,
        diameter=diameter,
        bad_ratio_th=config.consistency.bad_ratio_th,
        q=config.consistency.q,
        gain=config.consistency.gain,
        floor_ratio=config.consistency.floor_ratio,
        ceil_ratio=config.consistency.ceil_ratio,
    )
    return axis_info, refined_center, refined_axis, loss, exists, ok_2fold


def _progress_stage(key: str, label: str, fraction: float) -> None:
    try:
        from kasal.utils.compute_progress import (
            get_compute_progress,
            progress_pulse,
            progress_reporting_enabled,
        )

        pg = get_compute_progress()
        if progress_reporting_enabled():
            pg.set_stage(key, label, fraction=fraction, indeterminate=False)
            progress_pulse()
    except Exception:
        pass


def analyze_rotational_symmetry(model_input, tex=False, config: SymmetryAnalysisConfig | None = None):
    """Run symmetry analysis from a fully prepared model dictionary."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    seed_everything(cfg.seed.value)
    sampled_points = model_input["analysis_points"]
    rotation_center = model_input["rotation_center"]

    _progress_stage("axis_search", "Searching primary symmetry axis", 0.42)
    has_rot_sym, rot_sym_type, main_n_fold, axis_1, axis_2, center_ch, sym_op = classify_rotational_symmetry_family(
        model_input,
        sampled_points,
        rotation_center,
        config=cfg,
    )

    if sym_op == "symmetries_discrete":
        axis_list, matrices_list = generate_symmetry_transforms(main_n_fold, rot_sym_type, axis_1, axis_2, center_ch)
    else:
        axis_list = [axis_1]
        matrices_list = None

    result = {
        "has_rot_sym": has_rot_sym,
        "rot_sym_type": rot_sym_type,
        "rot_sym_axis": axis_list,
        "rot_sym_matrices": matrices_list,
        "rot_center": center_ch,
        "sym_op": sym_op,
    }

    _progress_stage("classify", "Classifying symmetry family", 0.72)
    if has_rot_sym and tex is True:
        from .texture import refine_symmetry_with_texture

        _progress_stage("texture", "Texture / ADI-C refinement", 0.82)
        colors_ = model_input["analysis_colors"]
        tex_result, tex_n_fold = refine_symmetry_with_texture(
            sampled_points,
            colors_,
            rot_sym_type,
            center_ch,
            axis_list,
            main_n_fold,
            config=cfg,
        )
        has_tex_sym = bool(tex_result.get("has_rot_sym_tex", False))
        tex_type = tex_result.get("rot_sym_type")
        tex_axes = tex_result.get("axes_tex") or []
        result["texture_symmetry"] = {
            "enabled": True,
            "evaluated": True,
            "has_rot_sym": bool(has_tex_sym and tex_type and tex_axes),
            "rot_sym_type": tex_type if has_tex_sym else None,
            "n_fold": tex_n_fold if has_tex_sym else 0,
            "sym_op": tex_result.get("sym_op", "none") if has_tex_sym else "none",
            "rot_center": tex_result.get("rot_center", center_ch),
            "rot_sym_axis": tex_axes,
            "rot_sym_matrices": tex_result.get("rot_sym_matrices") or [],
        }
    elif tex is True:
        result["texture_symmetry"] = {
            "enabled": True,
            "evaluated": False,
            "has_rot_sym": False,
            "rot_sym_type": None,
            "n_fold": None,
            "sym_op": "none",
            "rot_center": center_ch,
            "rot_sym_axis": [],
            "rot_sym_matrices": [],
        }

    return result, main_n_fold


def classify_rotational_symmetry_family(
    model_input,
    pts,
    rot_center,
    *,
    config: SymmetryAnalysisConfig | None = None,
):
    """Classify the rotational symmetry family from the dominant axis and waveform."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    labels = cfg.labels
    center_ch = np.asarray(rot_center, dtype=np.float32)
    diameter = model_input["diameter"]

    best_axis = search_primary_axis(
        pts,
        center_ch=center_ch,
        n_fold_candidates=cfg.classification.primary_orders,
        config=cfg,
    )
    best_axis = normalize_vector(best_axis)

    periodicity = estimate_axis_periodicity(
        pts,
        best_axis,
        center_ch=center_ch,
        config=cfg,
    )
    n_fft = normalize_estimated_fold(periodicity.get("N", 0))

    if not is_continuous_fold_marker(n_fft) and n_fft <= cfg.classification.dominant_axis_retry_max_fold:
        best_axis = search_primary_axis(
            pts,
            center_ch=center_ch,
            n_fold_candidates=cfg.classification.fallback_orders,
            config=cfg,
        )

        periodicity = estimate_axis_periodicity(
            pts,
            best_axis,
            center_ch=center_ch,
            config=cfg,
        )
        n_fft = normalize_estimated_fold(periodicity.get("N", 0))

    if n_fft == 0:
        return True, labels.error, 2, best_axis, None, center_ch, None

    discrete_rotation_deg = estimate_discrete_rotation_angle(n_fft, config=cfg)
    axis_info = build_axis_info(best_axis, center_ch, discrete_rotation_deg)
    center_ch, best_axis = refine_axis_center_with_icp(axis_info, model_input, center_ch, config=cfg)

    dominant_axis_loss = compute_axis_rotation_loss(
        pts,
        best_axis,
        discrete_rotation_deg,
        device=cfg.classification.rotation_loss_device,
    )
    secondary_axis_loss_threshold = diameter * cfg.classification.secondary_axis_loss_ratio

    if dominant_axis_loss > diameter * cfg.classification.dominant_axis_loss_ratio:
        return False, labels.non_rotational, 0, None, None, center_ch, None

    if is_continuous_fold_marker(n_fft) or n_fft > cfg.classification.continuous_fold_cutoff:
        n_fft = cfg.periodicity.continuous_fold_value

    if is_continuous_fold_marker(n_fft):
        contour_uv, _ = extract_flattened_contour_uv_from_mesh(
            model_input,
            best_axis,
            grid=cfg.contour.grid,
            margin=cfg.contour.margin,
            pad_px=cfg.contour.pad_px,
            close_radius_px=cfg.contour.close_radius_px,
            fill_holes=cfg.contour.fill_holes,
            keep_largest_cc=cfg.contour.keep_largest_cc,
            min_contour_pts=cfg.contour.min_contour_pts,
        )

        contour_label, contour_metrics = classify_circle_vs_polygon(
            contour_uv,
            M_resample=cfg.contour.resample_points,
            n_theta=cfg.contour.radial_fft_samples,
            circ_th=cfg.contour.circle_threshold,
            energy_th=cfg.contour.energy_threshold,
        )

        if contour_label == "polygon_like":
            radial_peak_k = int(contour_metrics.get("radial_peak_k", 0))
            if radial_peak_k >= 2:
                sym_op = "symmetries_discrete"
                n_fft = radial_peak_k
                _, refined_center, best_axis2, loss, exists, ok_2fold = refine_secondary_twofold_axis(
                    model_input,
                    pts,
                    best_axis,
                    center_ch,
                    config=cfg,
                )
                if exists and ok_2fold:
                    return True, labels.prismatic, n_fft, best_axis, best_axis2, refined_center, sym_op
                return True, labels.pyramidal, n_fft, best_axis, best_axis, refined_center, sym_op

        sym_op = "symmetries_continuous"
        continuous_n_fold = cfg.periodicity.continuous_fold_value
        axis_info = search_secondary_axis_at_angle(
            cfg.classification.continuous_probe_angle_deg,
            pts,
            best_axis,
            div=2,
            center_ch=center_ch,
            config=cfg,
        )
        if axis_info["best_loss"] < secondary_axis_loss_threshold:
            return True, labels.spherical, continuous_n_fold, best_axis, None, center_ch, sym_op

        _, refined_center, best_axis2, loss, exists, ok_2fold = refine_secondary_twofold_axis(
            model_input,
            pts,
            best_axis,
            center_ch,
            config=cfg,
        )
        if exists and ok_2fold:
            return True, labels.cylindrical, continuous_n_fold, best_axis, best_axis2, refined_center, sym_op
        return True, labels.circular, continuous_n_fold, best_axis, None, refined_center, sym_op

    sym_op = "symmetries_discrete"

    if n_fft > 5:
        _, refined_center, best_axis2, loss, exists, ok_2fold = refine_secondary_twofold_axis(
            model_input,
            pts,
            best_axis,
            center_ch,
            config=cfg,
        )
        if exists and ok_2fold:
            return True, labels.prismatic, n_fft, best_axis, best_axis2, refined_center, sym_op
        return True, labels.pyramidal, n_fft, best_axis, best_axis, refined_center, sym_op

    if n_fft == 5:
        poly_label = labels.icosahedral
        poly_angle = get_template_axis_angle(poly_label, None)
        axis_info = search_secondary_axis_at_angle(poly_angle, pts, best_axis, div=5, center_ch=center_ch, config=cfg)
        refined_center, best_axis2 = refine_axis_center_with_icp(axis_info, model_input, center_ch, config=cfg)
        loss = compute_axis_rotation_loss(
            pts,
            best_axis2,
            360 / 5,
            device=cfg.classification.rotation_loss_device,
        )
        if loss < secondary_axis_loss_threshold:
            return True, poly_label, 5, best_axis, best_axis2, refined_center, sym_op

        axis_info = search_secondary_axis_at_angle(
            cfg.classification.two_fold_angle_deg,
            pts,
            best_axis,
            div=2,
            center_ch=center_ch,
            config=cfg,
        )
        refined_center, best_axis2 = refine_axis_center_with_icp(axis_info, model_input, center_ch, config=cfg)
        loss = axis_info["best_loss"]
        exists = loss < secondary_axis_loss_threshold
        ok_2fold = geom_pi_axis_consistency_ok(
            pts=pts,
            center_ch=refined_center,
            axis=best_axis2,
            diameter=diameter,
            bad_ratio_th=cfg.consistency.bad_ratio_th,
            q=cfg.consistency.q,
            gain=cfg.consistency.gain,
            floor_ratio=cfg.consistency.floor_ratio,
            ceil_ratio=cfg.consistency.ceil_ratio,
        )
        if exists and ok_2fold:
            refined_center, best_axis2 = refine_axis_center_with_icp(axis_info, model_input, refined_center, config=cfg)
            return True, labels.prismatic, 5, best_axis, best_axis2, refined_center, sym_op
        return True, labels.pyramidal, 5, best_axis, best_axis, refined_center, sym_op

    if n_fft == 4:
        poly_label = labels.octahedral
        poly_angle = get_template_axis_angle(poly_label, None)
        axis_info = search_secondary_axis_at_angle(poly_angle, pts, best_axis, div=4, center_ch=center_ch, config=cfg)
        refined_center, best_axis2 = refine_axis_center_with_icp(axis_info, model_input, center_ch, config=cfg)
        loss = compute_axis_rotation_loss(
            pts,
            best_axis2,
            360 / 4,
            device=cfg.classification.rotation_loss_device,
        )
        if loss < secondary_axis_loss_threshold:
            return True, poly_label, 4, best_axis, best_axis2, refined_center, sym_op

        _, refined_center, best_axis2, loss, exists, ok_2fold = refine_secondary_twofold_axis(
            model_input,
            pts,
            best_axis,
            center_ch,
            config=cfg,
        )
        if exists and ok_2fold:
            return True, labels.prismatic, 4, best_axis, best_axis2, refined_center, sym_op
        return True, labels.pyramidal, 4, best_axis, best_axis, refined_center, sym_op

    if n_fft == 3:
        poly_label = labels.tetrahedral
        poly_angle = get_template_axis_angle(poly_label, None)
        axis_info = search_secondary_axis_at_angle(poly_angle, pts, best_axis, div=3, center_ch=center_ch, config=cfg)
        refined_center, best_axis2 = refine_axis_center_with_icp(axis_info, model_input, center_ch, config=cfg)
        loss = compute_axis_rotation_loss(
            pts,
            best_axis2,
            360 / 3,
            device=cfg.classification.rotation_loss_device,
        )
        if loss < secondary_axis_loss_threshold:
            return True, poly_label, 3, best_axis, best_axis2, refined_center, sym_op

        _, refined_center, best_axis2, loss, exists, ok_2fold = refine_secondary_twofold_axis(
            model_input,
            pts,
            best_axis,
            center_ch,
            config=cfg,
        )
        if exists and ok_2fold:
            return True, labels.prismatic, 3, best_axis, best_axis2, refined_center, sym_op
        return True, labels.pyramidal, 3, best_axis, best_axis, refined_center, sym_op

    if n_fft == 2:
        _, refined_center, best_axis2, loss, exists, ok_2fold = refine_secondary_twofold_axis(
            model_input,
            pts,
            best_axis,
            center_ch,
            config=cfg,
        )
        if exists and ok_2fold:
            return True, labels.prismatic, 2, best_axis, best_axis2, refined_center, sym_op
        return True, labels.pyramidal, 2, best_axis, best_axis, refined_center, sym_op

    return True, labels.error, n_fft, best_axis, None, center_ch, sym_op

