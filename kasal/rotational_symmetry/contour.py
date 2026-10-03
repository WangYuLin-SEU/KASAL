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


def extract_flattened_contour_uv_from_mesh(
    modeli: dict,
    axis,
    center=None,
    grid: int = 1024,
    margin: float = 0.06,
    pad_px: int = 24,
    close_radius_px: int = 2,
    fill_holes: bool = True,
    keep_largest_cc: bool = True,
    min_contour_pts: int = 50,
    return_debug: bool = False,
):
    """Project a mesh to a local UV plane and extract the outer contour."""

    try:
        from skimage.draw import polygon
        from skimage.measure import find_contours, label
        from skimage.morphology import binary_closing, disk
    except Exception as e:
        raise ImportError("scikit-image is required for contour extraction.") from e

    try:
        from scipy.ndimage import binary_fill_holes
    except Exception as e:
        raise ImportError("scipy.ndimage.binary_fill_holes is required.") from e

    vertices = np.asarray(modeli["vertices"], dtype=float)
    faces = np.asarray(modeli["faces"], dtype=np.int64)

    if center is None:
        center = vertices.mean(axis=0)
    center = np.asarray(center, dtype=float).reshape(3)

    axis = np.asarray(axis, dtype=float).reshape(3)
    axis = axis / (np.linalg.norm(axis) + 1e-12)

    helper = np.array([1.0, 0.0, 0.0], dtype=float)
    if abs(axis[0]) >= 0.9:
        helper = np.array([0.0, 1.0, 0.0], dtype=float)

    e1 = helper - np.dot(helper, axis) * axis
    e1 = e1 / (np.linalg.norm(e1) + 1e-12)
    e2 = np.cross(axis, e1)
    e2 = e2 / (np.linalg.norm(e2) + 1e-12)

    centered_vertices = vertices - center[None, :]
    u = centered_vertices @ e1
    v = centered_vertices @ e2
    uv_vertices = np.stack([u, v], axis=1)

    umin, vmin = uv_vertices.min(axis=0)
    umax, vmax = uv_vertices.max(axis=0)
    du, dv = umax - umin, vmax - vmin
    span = float(max(du, dv, 1e-12))

    pad_uv = float(margin * span)
    u0 = float(umin - pad_uv)
    v0 = float(vmin - pad_uv)
    span2 = float(span + 2.0 * pad_uv)

    scale = float(grid / span2)
    width = int(np.ceil((umax - u0) * scale)) + 1
    height = int(np.ceil((vmax - v0) * scale)) + 1
    width = max(width, 32)
    height = max(height, 32)

    x_pix = (uv_vertices[:, 0] - u0) * scale
    y_pix = (uv_vertices[:, 1] - v0) * scale

    mask = np.zeros((height, width), dtype=bool)
    for i, j, k in faces:
        xs = np.array([x_pix[i], x_pix[j], x_pix[k]], dtype=float)
        ys = np.array([y_pix[i], y_pix[j], y_pix[k]], dtype=float)
        rr, cc = polygon(ys, xs, shape=mask.shape)
        mask[rr, cc] = True

    if pad_px > 0:
        mask = np.pad(mask, ((pad_px, pad_px), (pad_px, pad_px)), mode="constant", constant_values=False)

    if close_radius_px > 0:
        mask = binary_closing(mask, footprint=disk(int(close_radius_px)))

    if fill_holes:
        mask = binary_fill_holes(mask)

    if keep_largest_cc:
        labels = label(mask.astype(np.uint8), connectivity=2)
        if labels.max() > 0:
            areas = np.bincount(labels.ravel())
            areas[0] = 0
            keep_id = int(np.argmax(areas))
            mask = labels == keep_id

    contours = find_contours(mask.astype(float), level=0.5)
    if not contours:
        out = (None, {"reason": "no_contours"})
        return (*out, {"mask": mask}) if return_debug else out

    contour = max(contours, key=lambda c: c.shape[0])
    if contour.shape[0] < min_contour_pts:
        out = (None, {"reason": "contour_too_short", "n": int(contour.shape[0])})
        return (*out, {"mask": mask}) if return_debug else out

    rows = contour[:, 0]
    cols = contour[:, 1]
    if pad_px > 0:
        cols = cols - pad_px
        rows = rows - pad_px

    contour_u = cols / scale + u0
    contour_v = rows / scale + v0
    contour_uv = np.stack([contour_u, contour_v], axis=1)

    info = {
        "u0": u0,
        "v0": v0,
        "scale": scale,
        "axis": axis,
        "center": center,
        "e1": e1,
        "e2": e2,
        "grid_shape": (int(mask.shape[0]), int(mask.shape[1])),
        "pad_px": int(pad_px),
        "n_contour": int(len(contour_uv)),
    }

    if return_debug:
        return contour_uv, info, {"mask": mask}
    return contour_uv, info


def _close_and_resample_contour(points: np.ndarray, M: int = 2048) -> np.ndarray:
    """Close and uniformly resample a contour by arc length."""

    points = np.asarray(points, dtype=float)
    if len(points) < 3:
        return points

    if np.linalg.norm(points[0] - points[-1]) > 1e-12:
        points = np.vstack([points, points[0]])

    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total_length = float(s[-1] + 1e-12)

    t = np.linspace(0.0, total_length, M, endpoint=False)
    x = np.interp(t, s, points[:, 0])
    y = np.interp(t, s, points[:, 1])
    return np.stack([x, y], axis=1)


def _polygon_area_and_perimeter(points: np.ndarray) -> tuple[float, float]:
    """Compute polygon area and perimeter from a contour."""

    points = np.asarray(points, dtype=float)
    if len(points) < 3:
        return 0.0, 0.0

    if np.linalg.norm(points[0] - points[-1]) > 1e-12:
        points = np.vstack([points, points[0]])

    x = points[:, 0]
    y = points[:, 1]
    area = 0.5 * abs(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    perimeter = float(np.sum(seg))
    return float(area), perimeter


def _radial_fft_energy(points: np.ndarray, n_theta: int = 720) -> dict:
    """Measure non-circular radial energy and dominant harmonic index."""

    points = np.asarray(points, dtype=float)
    if len(points) < 10:
        return {"energy_ratio": 1e9, "peak_k": -1, "peak_ratio": 1e9}

    center = points.mean(axis=0)
    X = points[:, 0] - center[0]
    Y = points[:, 1] - center[1]

    theta = np.arctan2(Y, X)
    radius = np.sqrt(X * X + Y * Y + 1e-12)

    order = np.argsort(theta)
    theta_sorted = np.unwrap(theta[order])
    radius_sorted = radius[order]

    theta_grid = np.linspace(theta_sorted[0], theta_sorted[-1], n_theta, endpoint=False)
    radius_grid = np.interp(theta_grid, theta_sorted, radius_sorted)

    fft_values = np.fft.rfft(radius_grid)
    mag2 = fft_values.real * fft_values.real + fft_values.imag * fft_values.imag

    dc = float(mag2[0] + 1e-12)
    ac = float(np.sum(mag2[1:]) + 1e-12)
    energy_ratio = float(ac / dc)

    if len(mag2) > 2:
        peak_k = int(np.argmax(mag2[1:]) + 1)
        peak_ratio = float(np.sqrt(mag2[peak_k]) / (np.sqrt(mag2[0]) + 1e-12))
    else:
        peak_k, peak_ratio = -1, 0.0

    return {"energy_ratio": energy_ratio, "peak_k": peak_k, "peak_ratio": peak_ratio}


def classify_circle_vs_polygon(
    contour_uv: np.ndarray,
    M_resample: int = 2048,
    n_theta: int = 720,
    circ_th: float = 0.95,
    energy_th: float = 1e-3,
    return_metrics: bool = True,
):
    """Classify a projected contour as circle-like or polygon-like."""

    contour_uv = np.asarray(contour_uv, dtype=float)
    if len(contour_uv) < 30:
        label = "unknown"
        return (label, {"reason": "too_few_points"}) if return_metrics else label

    resampled = _close_and_resample_contour(contour_uv, M=M_resample)
    area, perimeter = _polygon_area_and_perimeter(resampled)
    circularity = float(4.0 * np.pi * area / (perimeter * perimeter + 1e-12))
    radial_metrics = _radial_fft_energy(resampled, n_theta=n_theta)
    energy_ratio = float(radial_metrics["energy_ratio"])

    if (circularity >= circ_th) and (energy_ratio <= energy_th):
        label = "circle_like"
    else:
        label = "polygon_like"

    metrics = {
        "n_in": int(len(contour_uv)),
        "n_resample": int(len(resampled)),
        "area": float(area),
        "perimeter": float(perimeter),
        "circularity": float(circularity),
        "circ_th": float(circ_th),
        "radial_energy_ratio": float(energy_ratio),
        "energy_th": float(energy_th),
        "radial_peak_k": int(radial_metrics["peak_k"]),
        "radial_peak_ratio": float(radial_metrics["peak_ratio"]),
    }
    return (label, metrics) if return_metrics else label
