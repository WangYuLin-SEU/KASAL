# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import numpy as np
import torch
from numpy.fft import irfft, rfft
from scipy.interpolate import UnivariateSpline
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks, savgol_filter

from .config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig
from .geometry import batched_chamfer_distance, normalize_vector, rodrigues


def estimate_axis_periodicity(
    pts,
    best_axis,
    plane_samples=None,
    center_ch=None,
    *,
    config: SymmetryAnalysisConfig | None = None,
    device: str | None = None,
):
    """Sweep rotations around one axis and estimate the rotational order."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    periodicity_cfg = cfg.periodicity
    plane_samples = periodicity_cfg.plane_samples if plane_samples is None else plane_samples
    device = cfg.axis_search.device if device is None else device

    pts = np.asarray(pts, dtype=np.float32)
    if center_ch is None:
        center_ch = np.zeros(3, dtype=np.float32)
    pts_c = pts - center_ch
    dev = torch.device(device)

    pts_c_t = torch.tensor(pts_c, dtype=torch.float32, device=dev)
    best_axis = np.asarray(best_axis, dtype=np.float32)
    best_axis = best_axis / (np.linalg.norm(best_axis) + 1e-12)
    batch_size = int(plane_samples)

    axes_batch = torch.tensor(np.tile(best_axis, (batch_size, 1)), dtype=torch.float32, device=dev)
    phis = np.linspace(0.0, 2.0 * np.pi, batch_size, endpoint=False)
    theta_t = torch.tensor(phis, dtype=torch.float32, device=dev)

    rotation_batch = rodrigues(axes_batch, theta_t)
    pts_batch = pts_c_t.unsqueeze(0).expand(batch_size, -1, -1)
    pts_rot = torch.bmm(pts_batch, rotation_batch.transpose(1, 2))

    l2_vals = batched_chamfer_distance(pts_batch, pts_rot)
    l2_vals = l2_vals.detach().cpu().numpy()

    diameter_est = float(np.linalg.norm(pts.max(0) - pts.min(0))) + 1e-12
    l2_norm = l2_vals / diameter_est

    n_peaks, n_troughs = estimate_fold_from_waveform(l2_norm, config=cfg)

    X_dc = np.fft.rfft(l2_norm)
    mag_dc = np.abs(X_dc)
    dc_ratio = float((mag_dc[0] ** 2) / (np.sum(mag_dc ** 2) + 1e-12))
    flat_std = float(np.std(l2_norm))

    if n_peaks == 0 and n_troughs == 0 and flat_std > periodicity_cfg.continuous_flat_std_threshold:
        n_est = 0
    elif (
        n_peaks == 0
        and n_troughs == 0
        and flat_std < periodicity_cfg.continuous_flat_std_threshold
        and dc_ratio > periodicity_cfg.continuous_dc_ratio_threshold
    ):
        n_est = periodicity_cfg.continuous_fold_value
    else:
        candidate_folds = set()
        pool = {n_peaks, n_peaks + 1, n_peaks - 1, n_troughs, n_troughs + 1, n_troughs - 1}
        for k in pool:
            if k is not None and k > 1:
                candidate_folds.add(int(k))
        candidate_folds = sorted(candidate_folds)
        if not candidate_folds:
            n_est = 0
        else:
            axis_unit = best_axis / (np.linalg.norm(best_axis) + 1e-12)
            axes_batch = torch.tensor(
                np.tile(axis_unit, (len(candidate_folds), 1)),
                dtype=torch.float32,
                device=dev,
            )
            theta_t = torch.tensor(
                [2.0 * np.pi / float(n) for n in candidate_folds],
                dtype=torch.float32,
                device=dev,
            )
            rotation_batch = rodrigues(axes_batch, theta_t)
            pts_expand = pts_c_t.unsqueeze(0).expand(len(candidate_folds), -1, -1)
            pts_rot = torch.bmm(pts_expand, rotation_batch.transpose(1, 2))
            errs = batched_chamfer_distance(pts_expand, pts_rot)
            best_idx = int(torch.argmin(errs).item())
            n_est = int(candidate_folds[best_idx])

    if np.isinf(n_est):
        n_out = float("inf")
    elif n_est >= 2:
        n_out = int(n_est)
    else:
        n_out = 0

    return {
        "axis": normalize_vector(best_axis),
        "N": n_out,
        "fft": {"plane_samples": int(plane_samples)},
        "L2_vals": l2_vals,
        "L2_norm": l2_norm,
        "dc_ratio": dc_ratio,
        "flat_std": flat_std,
        "phis": phis,
    }


def estimate_fold_from_waveform(L2_vals, *, config: SymmetryAnalysisConfig | None = None):
    """Estimate the fold count from the rotation-error waveform."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    periodicity_cfg = cfg.periodicity

    y_raw = np.asarray(L2_vals, dtype=float)
    x_deg_full = np.linspace(0, 360, len(y_raw), endpoint=False)
    y_raw = y_raw[1:]
    x_deg_full = x_deg_full[1:]

    y = y_raw
    x_deg = x_deg_full

    if is_almost_flat_waveform(y, config=cfg) and float(np.std(y)) < periodicity_cfg.continuous_flat_std_threshold:
        return 0, 0

    y, left_trim, right_trim = trim_waveform_edges(
        y,
        margin=periodicity_cfg.trim_margin,
        ignore_frac=periodicity_cfg.first_trim_ignore_frac,
    )
    x_deg = x_deg[left_trim : len(x_deg) - right_trim]

    baseline = estimate_waveform_baseline(
        y,
        method=periodicity_cfg.baseline_method,
        ma_win=(len(y) // periodicity_cfg.baseline_window_divisor) | 1,
        ma_kind=periodicity_cfg.baseline_window_kind,
        ma_wrap=periodicity_cfg.baseline_wrap,
        use_fft=periodicity_cfg.baseline_use_fft,
    )
    y_detr = y - periodicity_cfg.baseline_alpha * (baseline - baseline.mean())

    if periodicity_cfg.smooth:
        n = len(y_detr)
        win = min(periodicity_cfg.smooth_win, n - (n % 2 == 0))
        if win % 2 == 0:
            win = max(3, win - 1)
        win = max(3, win)
        poly = min(periodicity_cfg.smooth_poly, win - 1)
        y_smooth = savgol_filter(y_detr, window_length=win, polyorder=poly)
    else:
        y_smooth = y_detr.copy()

    y_final, left_trim, right_trim = trim_waveform_edges(
        y_smooth,
        margin=periodicity_cfg.trim_margin,
        ignore_frac=periodicity_cfg.second_trim_ignore_frac,
    )
    x_deg = x_deg[left_trim : len(x_deg) - right_trim]

    def count_global_runs(y_arr, mode="min", tol_ratio=0.1):
        ymin, ymax = float(np.min(y_arr)), float(np.max(y_arr))
        amp = ymax - ymin
        if amp <= 1e-12:
            return 1, [(0, len(y_arr))], [len(y_arr) // 2]
        tol = tol_ratio * amp
        mask = (y_arr <= ymin + tol) if mode == "min" else (y_arr >= ymax - tol)
        mask_int = mask.astype(int)
        starts = np.where(np.diff(mask_int, prepend=0) == 1)[0]
        ends = np.where(np.diff(mask_int, append=0) == -1)[0] + 1
        centers = [(s + e) // 2 for s, e in zip(starts, ends)]
        return len(starts), list(zip(starts, ends)), centers

    n_peaks, _, _ = count_global_runs(y_final, mode="max", tol_ratio=periodicity_cfg.tol_ratio)
    if periodicity_cfg.use_troughs:
        n_troughs, _, _ = count_global_runs(y_final, mode="min", tol_ratio=periodicity_cfg.tol_ratio)
    else:
        n_troughs = 0

    return int(n_peaks), int(n_troughs)


def circular_weighted_moving_average(y, win, kind="hann"):
    """Compute a circular weighted moving average for periodic waveforms."""

    y = np.asarray(y, dtype=float)
    n = len(y)
    if win % 2 == 0:
        win += 1
    win = max(3, min(win, n - (n % 2 == 0)))

    weights = np.hanning(win) if kind == "hann" else np.ones(win)
    weights = weights / weights.sum()

    kernel = np.zeros(n, dtype=float)
    half = win // 2
    kernel[: half + 1] = weights[half:]
    kernel[-half:] = weights[:half]

    return irfft(rfft(y) * rfft(kernel), n=n)


def estimate_waveform_baseline(
    y,
    method="poly",
    *,
    poly_deg=3,
    lp_win=None,
    lp_poly=3,
    ma_win=None,
    ma_kind="hann",
    spline_s=None,
    ma_wrap=True,
    use_fft=True,
):
    """Estimate a smooth baseline for waveform detrending."""

    y = np.asarray(y, dtype=float)
    n = len(y)
    x = np.arange(n, dtype=float)

    if n < 3:
        return y.copy()

    if method == "poly":
        deg = int(poly_deg)
        deg = max(1, min(deg, max(1, n - 1)))
        coeffs = np.polyfit(x, y, deg=deg)
        baseline = np.polyval(coeffs, x)
    elif method == "savgol_lp":
        if lp_win is None:
            lp_win = max(31, (n // 5) | 1)
        if lp_win % 2 == 0:
            lp_win += 1
        lp_win = min(lp_win, n - (n % 2 == 0))
        lp_win = max(5, lp_win)
        lp_poly = int(min(lp_poly, lp_win - 1))
        baseline = savgol_filter(y, window_length=lp_win, polyorder=lp_poly, mode="wrap")
    elif method == "moving":
        if ma_win is None:
            ma_win = max(31, (n // 6) | 1)
        if ma_win % 2 == 0:
            ma_win += 1
        ma_win = max(3, min(ma_win, n - (n % 2 == 0)))

        if ma_wrap:
            if ma_kind == "box" and not use_fft:
                baseline = uniform_filter1d(y, size=ma_win, mode="wrap")
            else:
                baseline = circular_weighted_moving_average(y, win=ma_win, kind=ma_kind)
        else:
            weights = np.hanning(ma_win) if ma_kind == "hann" else np.ones(ma_win)
            weights = weights / weights.sum()
            baseline = np.convolve(y, weights, mode="same")
    elif method == "spline":
        if spline_s is None:
            spline_s = n * np.var(y) * 0.01
        baseline = UnivariateSpline(x, y, s=spline_s)(x)
    else:
        raise ValueError("Unknown baseline method.")

    return baseline


def is_almost_flat_waveform(y, *, config: SymmetryAnalysisConfig | None = None):
    """Detect nearly flat waveforms that imply continuous symmetry."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    periodicity_cfg = cfg.periodicity

    y = np.asarray(y, float)
    n = len(y)
    if n < 7:
        return 0

    base_win = min(periodicity_cfg.smooth_win, n - (n % 2 == 0))
    if base_win % 2 == 0:
        base_win = max(3, base_win - 1)
    base_win = max(3, base_win)
    base_poly = min(periodicity_cfg.smooth_poly, base_win - 1)
    y_smooth = savgol_filter(y, window_length=base_win, polyorder=base_poly)

    win = max(3, int(round(periodicity_cfg.flat_smooth_win_frac * n)))
    if win % 2 == 0:
        win += 1
    win = min(win, n - (n % 2 == 0))
    ys = savgol_filter(y_smooth, window_length=win, polyorder=min(periodicity_cfg.smooth_poly, win - 1))

    amp = float(np.ptp(ys)) + 1e-12
    prom = periodicity_cfg.flat_prom_frac * amp
    dist = max(1, int(round(periodicity_cfg.flat_min_dist_frac * n)))

    peaks, pinfo = find_peaks(ys, prominence=prom, distance=dist)
    troughs, tinfo = find_peaks(-ys, prominence=prom, distance=dist)

    def _count_prominent_groups(indices, info):
        if len(indices) < 1:
            return 0
        prominences = np.sort(info["prominences"])[::-1]
        if len(prominences) == 1:
            return 1
        if prominences[0] >= periodicity_cfg.flat_single_peak_ratio * prominences[1]:
            return 1
        return len(indices)

    k_peaks = _count_prominent_groups(peaks, pinfo)
    k_troughs = _count_prominent_groups(troughs, tinfo)
    return max(k_peaks, k_troughs) < 2 or (k_peaks == 1 and k_troughs == 2)


def trim_waveform_edges(y, margin=0.0, ignore_frac=0.05):
    """Trim low-signal edges from a waveform before peak counting."""

    y = np.asarray(y, dtype=float)
    n = len(y)
    n_ignore = max(1, int(n * ignore_frac))
    main_min = np.min(y[n_ignore : -n_ignore or None])
    thresh = main_min + margin

    left = 0
    while left < n and y[left] < thresh:
        left += 1

    right = n - 1
    while right > left and y[right] < thresh:
        right -= 1

    y_trimmed = y[left : right + 1]
    return y_trimmed, left, n - 1 - right
