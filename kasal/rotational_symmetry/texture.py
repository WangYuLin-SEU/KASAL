# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from pytorch3d.ops import knn_points

from .config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig
from .geometry import build_rotation_transform, rodrigues


Number = int | float


@dataclass
class AxisRecord:
    """Describe one symmetry axis at the geometry and texture levels."""

    axis: np.ndarray
    n_geo: Number | None = None
    n_tex: Number | None = None
    role: str | None = None


def to_tensor_on_device(arr, dev, dtype=torch.float32):
    """Convert an input array to a tensor on the target device."""

    if isinstance(arr, torch.Tensor):
        return arr.to(device=dev, dtype=dtype)
    if isinstance(arr, np.ndarray):
        return torch.from_numpy(arr).to(device=dev, dtype=dtype)
    return torch.tensor(arr, device=dev, dtype=dtype)


def prepare_colors(color, dev, normalize_if_255=True):
    """Prepare color features as a batched tensor."""

    cx = to_tensor_on_device(color, dev, dtype=torch.float32)
    if cx.dim() == 2:
        cx = cx.unsqueeze(0)
    if normalize_if_255:
        with torch.no_grad():
            if cx.numel() > 0 and cx.max().item() > 1.5:
                cx = cx / 255.0
    return cx


def build_axis_records(axis_list: Any, rot_sym_type: str, n_geo_max: int | None = None) -> list[AxisRecord]:
    """Attach geometric roles and orders to a raw axis list."""

    if axis_list is None:
        return []
    arr = axis_list.detach().cpu().numpy() if torch.is_tensor(axis_list) else np.asarray(axis_list)
    arr = arr.astype(np.float32, copy=False)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape[1] < 3:
        return []

    count = arr.shape[0]
    n_geos: list[float | None] = [None] * count
    roles: list[str | None] = [None] * count

    if rot_sym_type == "D(=1): n-fold Pyramidal Item":
        if count >= 1:
            n_geos[0], roles[0] = float(n_geo_max), "main"
    elif rot_sym_type == "C(=1): Circular Item":
        if count >= 1:
            n_geos[0], roles[0] = np.inf, "main"
    elif rot_sym_type == "D(>1): n-fold Prismatic Item":
        if count >= 1:
            n_geos[0], roles[0] = float(n_geo_max), "main"
        for i in range(1, count):
            n_geos[i], roles[i] = 2.0, "side"
    elif rot_sym_type == "C(>1): Cylindrical Item":
        if count >= 1:
            n_geos[0], roles[0] = np.inf, "main"
        for i in range(1, count):
            n_geos[i], roles[i] = 2.0, "side"
    elif rot_sym_type == "P(4): Tetrahedral Item":
        for i in range(count):
            n_geos[i], roles[i] = (3.0, "C3") if i < 4 else (2.0, "C2")
    elif rot_sym_type == "P(8): Octahedral Item":
        for i in range(count):
            if i < 3:
                n_geos[i], roles[i] = 4.0, "C4"
            elif i < 7:
                n_geos[i], roles[i] = 3.0, "C3"
            else:
                n_geos[i], roles[i] = 2.0, "C2"
    elif rot_sym_type == "P(20): Icosahedral Item":
        for i in range(count):
            if i < 6:
                n_geos[i], roles[i] = 5.0, "C5"
            elif i < 16:
                n_geos[i], roles[i] = 3.0, "C3"
            else:
                n_geos[i], roles[i] = 2.0, "C2"
    else:
        if count >= 1:
            roles[0] = "main"
            n_geos[0] = float(n_geo_max) if n_geo_max is not None else None
        for i in range(1, count):
            n_geos[i], roles[i] = 2.0, "side"

    records: list[AxisRecord] = []
    for i in range(count):
        axis = arr[i, :3].astype(np.float32, copy=False)
        axis = axis / (float(np.linalg.norm(axis)) + 1e-12)
        records.append(AxisRecord(axis=axis, n_geo=n_geos[i], n_tex=None, role=roles[i]))
    return records


def batched_color_chamfer_distance(x: torch.Tensor, y: torch.Tensor, cx: torch.Tensor, cy: torch.Tensor | None = None, p: int = 2):
    """Compute a color-feature Chamfer distance for one or more rotated clouds."""

    squeeze_b = False
    if x.dim() == 2:
        x = x.unsqueeze(0)
        squeeze_b = True
    b, n, dx = x.shape
    if dx != 3:
        raise ValueError(f"x last dimension must be 3, got {dx}")

    if cx.dim() == 2:
        cx = cx.unsqueeze(0)
    cdim = cx.shape[-1]
    if cx.shape[0] == 1 and b > 1:
        cx = cx.expand(b, -1, -1)
    if cx.shape[0] != b or cx.shape[1] != n:
        raise ValueError(f"cx must be (B,N,C) or (1,N,C), got cx={tuple(cx.shape)}, x={tuple(x.shape)}")

    if y.dim() == 3:
        y = y.unsqueeze(0)
    if y.dim() != 4:
        raise ValueError(f"y must be (K,M,3) or (B,K,M,3), got {tuple(y.shape)}")
    by, k, m, dy = y.shape
    if dy != 3:
        raise ValueError(f"y last dimension must be 3, got {dy}")

    if b == 1 and by > 1:
        x = x.expand(by, -1, -1)
        cx = cx.expand(by, -1, -1)
        b = by
    if by != b:
        raise ValueError(f"Batch size mismatch: x batch={b}, y batch={by}")

    if cy is None:
        if m != n:
            raise ValueError(f"cy=None requires M==N, got M={m}, N={n}")
        cy = cx.unsqueeze(1).expand(b, k, n, cdim)
    else:
        if cy.dim() == 3:
            cy = cy.unsqueeze(0)
        if cy.shape != (b, k, m, cdim):
            raise ValueError(f"cy must be (B,K,M,{cdim}), got {tuple(cy.shape)}")

    x_bk = x.unsqueeze(1).expand(b, k, n, 3).reshape(b * k, n, 3)
    cx_bk = cx.unsqueeze(1).expand(b, k, n, cdim).reshape(b * k, n, cdim)
    y_bk = y.reshape(b * k, m, 3)
    cy_bk = cy.reshape(b * k, m, cdim)

    idx_x2y = knn_points(x_bk, y_bk, K=1, return_nn=False).idx[..., 0]
    idx_y2x = knn_points(y_bk, x_bk, K=1, return_nn=False).idx[..., 0]
    cy_nn_for_x = torch.gather(cy_bk, 1, idx_x2y.unsqueeze(-1).expand(b * k, n, cdim))
    cx_nn_for_y = torch.gather(cx_bk, 1, idx_y2x.unsqueeze(-1).expand(b * k, m, cdim))

    d_x2y = (cx_bk - cy_nn_for_x).abs().pow(p).sum(dim=-1).pow(1.0 / p)
    d_y2x = (cy_bk - cx_nn_for_y).abs().pow(p).sum(dim=-1).pow(1.0 / p)
    out = (0.5 * (d_x2y.mean(dim=1) + d_y2x.mean(dim=1))).view(b, k)
    return out[0] if (squeeze_b and out.shape[0] == 1) else out


def estimate_texture_order_for_axis(
    pts_centered,
    colors_,
    axis_rec: AxisRecord,
    n_max_tex: int = 20,
    gain_threshold: float = 0.2,
    device: str = "cuda",
    *,
    config: SymmetryAnalysisConfig | None = None,
) -> Number:
    """Estimate the effective texture order supported by one axis."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    tex_cfg = cfg.texture
    n_max_tex = tex_cfg.n_max_tex if n_max_tex == 20 else n_max_tex
    gain_threshold = tex_cfg.order_gain_threshold if gain_threshold == 0.2 else gain_threshold
    device = tex_cfg.device if device == "cuda" else device

    axis = axis_rec.axis
    n_geo = axis_rec.n_geo
    if n_geo is None:
        return 0

    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    x = to_tensor_on_device(pts_centered, dev, dtype=torch.float32)
    colors_t = to_tensor_on_device(colors_, dev, dtype=torch.float32)
    if colors_t.ndim == 1:
        colors_t = colors_t.view(-1, 1)
    if torch.var(colors_t, dim=0, unbiased=False).mean().item() < tex_cfg.order_col_var_threshold:
        return n_geo

    axis_t = to_tensor_on_device(axis, dev, dtype=torch.float32).view(-1)[:3]
    axis_t = axis_t / (torch.norm(axis_t) + 1e-12)
    cx = prepare_colors(colors_t, dev)

    if not np.isfinite(float(n_geo)):
        m_samp = tex_cfg.continuous_samples
        phis = torch.linspace(0.0, 2.0 * math.pi, m_samp + 1, device=dev)[:-1]
        axis_batch = axis_t.unsqueeze(0).repeat(m_samp, 1)
        y_all = torch.bmm(x.unsqueeze(0).expand(m_samp, -1, -1), rodrigues(axis_batch, phis).transpose(1, 2))
        d_phi = batched_color_chamfer_distance(x=x, y=y_all, cx=cx, cy=None, p=2)
        mu = torch.mean(d_phi)
        sigma = torch.std(d_phi, unbiased=False) + 1e-12
        d_rand = mu
        if d_rand.item() <= 1e-12:
            return np.inf

        good = (
            (d_phi <= torch.roll(d_phi, 1, 0))
            & (d_phi <= torch.roll(d_phi, -1, 0))
            & ((d_phi < torch.roll(d_phi, 1, 0)) | (d_phi < torch.roll(d_phi, -1, 0)))
            & (((d_rand - d_phi) / d_rand) >= gain_threshold)
        )
        idx_good = torch.nonzero(good, as_tuple=False).view(-1).detach().cpu().tolist()
        if len(idx_good) == 0:
            return np.inf if (sigma / (mu + 1e-12)).item() < tex_cfg.continuous_flat_cv_threshold else 0

        idx_good.sort()
        clusters, cur = [], [idx_good[0]]
        for j in range(1, len(idx_good)):
            if idx_good[j] - idx_good[j - 1] <= tex_cfg.continuous_cluster_gap:
                cur.append(idx_good[j])
            else:
                clusters.append(cur)
                cur = [idx_good[j]]
        clusters.append(cur)
        if len(clusters) > 1 and (clusters[0][0] + m_samp - clusters[-1][-1]) <= tex_cfg.continuous_cluster_gap:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()
        if len(clusters) < 2:
            return np.inf if (sigma / (mu + 1e-12)).item() < tex_cfg.continuous_flat_cv_threshold else 0

        phis_cpu = phis.detach().cpu().numpy()
        centers = []
        for cluster in clusters:
            ang = phis_cpu[np.asarray(cluster, dtype=np.int64)]
            center = math.atan2(np.sin(ang).mean(), np.cos(ang).mean())
            centers.append(center + 2.0 * math.pi if center < 0 else center)
        centers.sort()
        gaps = []
        for i in range(len(centers)):
            d = centers[(i + 1) % len(centers)] - centers[i]
            gaps.append(d + 2.0 * math.pi if d < 0 else d)
        gaps = np.asarray(gaps, dtype=np.float64)
        if float(gaps.std()) / (float(gaps.mean()) + 1e-12) > tex_cfg.continuous_gap_cv_threshold:
            return np.inf if (sigma / (mu + 1e-12)).item() < tex_cfg.continuous_flat_cv_threshold else 0
        return int(len(clusters))

    n_max_tex = min(int(round(float(n_geo) * 2.0)), int(n_max_tex))
    n_geo_int = int(round(float(n_geo)))
    if n_geo_int < 2:
        return 0
    finite_candidates = [d for d in range(2, n_geo_int + 1) if (n_geo_int % d == 0) and (d <= n_max_tex)]
    if len(finite_candidates) == 0:
        return 0

    k_count = len(finite_candidates)
    axes_batch = axis_t.unsqueeze(0).repeat(k_count, 1)
    theta_k = torch.as_tensor([2.0 * math.pi / float(k) for k in finite_candidates], dtype=torch.float32, device=dev)
    y_k = torch.bmm(x.unsqueeze(0).expand(k_count, -1, -1), rodrigues(axes_batch, theta_k).transpose(1, 2))
    errs_k = batched_color_chamfer_distance(x=x, y=y_k, cx=cx, cy=None, p=2)

    phis_base = torch.linspace(0.0, 2.0 * math.pi, tex_cfg.finite_baseline_samples + 1, device=dev)[:-1]
    delta = (2.0 * math.pi) / float(tex_cfg.finite_baseline_samples) * 1.5
    mask = torch.ones((tex_cfg.finite_baseline_samples,), dtype=torch.bool, device=dev)
    for th in theta_k:
        d = torch.remainder(phis_base - th + math.pi, 2.0 * math.pi) - math.pi
        mask &= (d.abs() > delta)
    phis_use = phis_base[mask] if mask.any() else phis_base
    y_base = torch.bmm(x.unsqueeze(0).expand(phis_use.numel(), -1, -1), rodrigues(axis_t.unsqueeze(0).repeat(phis_use.numel(), 1), phis_use).transpose(1, 2))
    errs_base = batched_color_chamfer_distance(x=x, y=y_base, cx=cx, cy=None, p=2)

    th = torch.quantile(errs_base, tex_cfg.finite_baseline_quantile)
    d_base = float(errs_base[errs_base >= th].mean().item())
    if d_base <= 1e-12:
        return int(finite_candidates[int(torch.argmin(errs_k).item())])

    best_idx = int(torch.argmin(errs_k).item())
    gain = (float(errs_base.mean().item()) - float(errs_k[best_idx].item())) / (float(errs_base.max().item()) - float(errs_base.min().item()) + 1e-12)
    return int(finite_candidates[best_idx]) if gain >= gain_threshold else 0


def find_texture_2fold_axes_on_ring(
    pts_centered,
    colors_,
    main_axis,
    device: str = "cuda",
    M_dir: int = 180,
    gain_threshold: float = 0.2,
    gap_th: int = 3,
    *,
    config: SymmetryAnalysisConfig | None = None,
) -> list[AxisRecord]:
    """Search texture-supported 2-fold side axes on the ring orthogonal to the main axis."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    tex_cfg = cfg.texture
    device = tex_cfg.device if device == "cuda" else device
    M_dir = tex_cfg.ring_search_dirs if M_dir == 180 else M_dir
    gain_threshold = tex_cfg.ring_gain_threshold if gain_threshold == 0.2 else gain_threshold
    gap_th = tex_cfg.ring_cluster_gap if gap_th == 3 else gap_th

    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    x = to_tensor_on_device(pts_centered, dev, dtype=torch.float32)
    if x.shape[0] < tex_cfg.ring_min_points:
        return []
    col = to_tensor_on_device(colors_, dev, dtype=torch.float32)
    if col.ndim == 1:
        col = col.view(-1, 1)
    if col.shape[0] != x.shape[0] or torch.var(col, dim=0, unbiased=False).mean().item() < tex_cfg.order_col_var_threshold:
        return []

    v = to_tensor_on_device(main_axis, dev, dtype=torch.float32).view(-1)[:3]
    v = v / (torch.norm(v) + 1e-12)
    tmp = torch.tensor([1.0, 0.0, 0.0], device=dev) if torch.abs(v[0]) < 0.9 else torch.tensor([0.0, 1.0, 0.0], device=dev)
    e1 = tmp - torch.dot(tmp, v) * v
    e1 = e1 / (torch.norm(e1) + 1e-12)
    e2 = torch.linalg.cross(v, e1)
    e2 = e2 / (torch.norm(e2) + 1e-12)

    phis = torch.linspace(0.0, math.pi, M_dir + 1, device=dev)[:-1]
    axes_batch = torch.cos(phis)[:, None] * e1[None, :] + torch.sin(phis)[:, None] * e2[None, :]
    axes_batch = axes_batch / (torch.norm(axes_batch, dim=1, keepdim=True) + 1e-12)

    cx = prepare_colors(col, dev)
    theta_pi = torch.full((M_dir,), math.pi, dtype=torch.float32, device=dev)
    y_pi = torch.bmm(x.unsqueeze(0).expand(M_dir, -1, -1), rodrigues(axes_batch, theta_pi).transpose(1, 2))
    d_pi = batched_color_chamfer_distance(x=x, y=y_pi, cx=cx, cy=None, p=2)
    theta_rand = torch.rand(M_dir, device=dev) * (2.0 * math.pi)
    y_rand = torch.bmm(x.unsqueeze(0).expand(M_dir, -1, -1), rodrigues(axes_batch, theta_rand).transpose(1, 2))
    d_rand = float(batched_color_chamfer_distance(x=x, y=y_rand, cx=cx, cy=None, p=2).mean().item())
    if d_rand <= 1e-12 or M_dir < 3:
        return []

    d_mid = d_pi[1:-1]
    good_mid = ((d_mid < d_pi[:-2]) & (d_mid < d_pi[2:])) & (((d_rand - d_mid) / d_rand) >= gain_threshold)
    idx_good = (torch.nonzero(good_mid, as_tuple=False).view(-1) + 1).detach().cpu().tolist()
    if len(idx_good) == 0:
        return []

    idx_good.sort()
    clusters, cur = [], [idx_good[0]]
    for i in range(1, len(idx_good)):
        if idx_good[i] - idx_good[i - 1] <= gap_th:
            cur.append(idx_good[i])
        else:
            clusters.append(cur)
            cur = [idx_good[i]]
    clusters.append(cur)

    best_axis, best_err = None, None
    for cluster in clusters:
        cluster_t = torch.as_tensor(cluster, device=dev, dtype=torch.long)
        axis_mean = axes_batch.index_select(0, cluster_t).mean(dim=0)
        axis_mean = axis_mean / (torch.norm(axis_mean) + 1e-12)
        y_rep = torch.bmm(x.unsqueeze(0), rodrigues(axis_mean.view(1, 3), torch.tensor([math.pi], device=dev, dtype=torch.float32)).transpose(1, 2))
        err_val = float(batched_color_chamfer_distance(x=x, y=y_rep, cx=cx, cy=None, p=2).view(-1)[0].item())
        if best_err is None or err_val < best_err:
            best_axis, best_err = axis_mean, err_val

    if best_axis is None:
        return []
    return [AxisRecord(axis=best_axis.detach().cpu().numpy().astype(np.float32), n_geo=2, n_tex=2, role="side_tex")]


@torch.no_grad()
def texture_bad_ratio_after_rotation(
    x: torch.Tensor,
    y: torch.Tensor,
    col: torch.Tensor,
    bad_ratio_th: float = 0.20,
    color_gain: float = 0.60,
    color_lo: float = 0.05,
    color_hi: float = 0.25,
    *,
    config: SymmetryAnalysisConfig | None = None,
):
    """Measure the color mismatch ratio after rotating one point cloud."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    tex_cfg = cfg.texture
    bad_ratio_th = tex_cfg.color_bad_ratio_threshold if bad_ratio_th == 0.20 else bad_ratio_th
    color_gain = tex_cfg.color_gain if color_gain == 0.60 else color_gain
    color_lo = tex_cfg.color_lo if color_lo == 0.05 else color_lo
    color_hi = tex_cfg.color_hi if color_hi == 0.25 else color_hi

    if x.dim() != 2 or y.dim() != 2 or col.dim() != 2:
        raise ValueError("x, y and col must be 2D tensors.")
    if x.shape[1] != 3 or y.shape[1] != 3:
        raise ValueError("x and y must have last dimension 3.")
    if col.shape[0] != x.shape[0]:
        raise ValueError("col and x must share the same point count.")

    idx = knn_points(y[None, ...], x[None, ...], K=1, return_nn=False).idx[0, :, 0].to(torch.long)
    diff = torch.norm(col - col.index_select(0, idx), dim=-1)
    color_th_t = torch.clamp(torch.std(col, dim=0, unbiased=False).mean() * float(color_gain), float(color_lo), float(color_hi))
    bad_ratio = float((diff > color_th_t).float().mean().item())
    return bool(bad_ratio <= float(bad_ratio_th)), bad_ratio, float(color_th_t.item())


def infer_side_axes_given_k(
    pts_centered,
    colors_,
    main_axis,
    k_main: int,
    device: str = "cuda",
    M_dir: int = 360,
    gain_threshold: float = 0.2,
    *,
    config: SymmetryAnalysisConfig | None = None,
) -> tuple[list[AxisRecord], int]:
    """Infer texture-consistent side axes given the texture order of the main axis."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    tex_cfg = cfg.texture
    device = tex_cfg.device if device == "cuda" else device
    M_dir = tex_cfg.side_axis_dirs if M_dir == 360 else M_dir
    gain_threshold = tex_cfg.ring_gain_threshold if gain_threshold == 0.2 else gain_threshold

    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    x = to_tensor_on_device(pts_centered, dev, dtype=torch.float32)
    col = to_tensor_on_device(colors_, dev, dtype=torch.float32)
    if col.ndim == 1:
        col = col.view(-1, 1)
    if x.shape[0] < tex_cfg.ring_min_points or col.shape[0] != x.shape[0]:
        return [], 0
    if torch.var(col, dim=0, unbiased=False).mean().item() < tex_cfg.order_col_var_threshold:
        return [], 0

    k_main = int(k_main)
    if k_main < 2:
        return [], 0

    v = to_tensor_on_device(main_axis, dev, dtype=torch.float32).view(-1)[:3]
    v = v / (torch.norm(v) + 1e-12)
    tmp = torch.tensor([1.0, 0.0, 0.0], device=dev) if torch.abs(v[0]) < 0.9 else torch.tensor([0.0, 1.0, 0.0], device=dev)
    e1 = tmp - torch.dot(tmp, v) * v
    e1 = e1 / (torch.norm(e1) + 1e-12)
    e2 = torch.cross(v, e1, dim=0)
    e2 = e2 / (torch.norm(e2) + 1e-12)

    phis = torch.linspace(0.0, math.pi, M_dir + 1, device=dev)[:-1]
    axes_ring = torch.cos(phis)[:, None] * e1[None, :] + torch.sin(phis)[:, None] * e2[None, :]
    axes_ring = axes_ring / (torch.norm(axes_ring, dim=1, keepdim=True) + 1e-12)
    cx = prepare_colors(col, dev)
    theta_pi = torch.full((M_dir,), math.pi, dtype=torch.float32, device=dev)
    y_pi = torch.bmm(x.unsqueeze(0).expand(M_dir, -1, -1), rodrigues(axes_ring, theta_pi).transpose(1, 2))
    d_pi = batched_color_chamfer_distance(x=x, y=y_pi, cx=cx, cy=None, p=2)
    d_base = float(d_pi.mean().item())
    if d_base <= 1e-12 or float(((d_base - d_pi.min()) / d_base).item()) < gain_threshold:
        return [], 0

    period = math.pi / float(k_main)
    n0 = max(16, int(round(period / (math.pi / float(M_dir)))))
    phi0_grid = torch.linspace(0.0, period, n0 + 1, device=dev)[:-1]
    sample_phis = phi0_grid[:, None] + torch.arange(k_main, device=dev, dtype=torch.float32)[None, :] * period
    idx = torch.clamp(torch.round(sample_phis / math.pi * float(M_dir)).to(torch.long), 0, M_dir - 1)
    phi0 = float(phi0_grid[int(torch.argmin(d_pi[idx].mean(dim=1)).item())].item())

    phis_k = phi0 + torch.arange(k_main, device=dev, dtype=torch.float32) * period
    axes_k = torch.cos(phis_k)[:, None] * e1[None, :] + torch.sin(phis_k)[:, None] * e2[None, :]
    axes_k = axes_k / (torch.norm(axes_k, dim=1, keepdim=True) + 1e-12)
    r_pi_k = rodrigues(axes_k, torch.full((k_main,), math.pi, dtype=torch.float32, device=dev))

    good_mask = torch.zeros((k_main,), dtype=torch.bool, device=dev)
    for j in range(k_main):
        y_c = x @ r_pi_k[j].T
        good_mask[j] = texture_bad_ratio_after_rotation(
            x=x,
            y=y_c,
            col=col,
            bad_ratio_th=gain_threshold,
            color_gain=tex_cfg.color_gain,
            color_lo=tex_cfg.color_lo,
            color_hi=tex_cfg.color_hi,
            config=cfg,
        )[0]
    good_cnt = int(good_mask.sum().item())
    if good_cnt != k_main:
        return [], 0

    side_axes = []
    for j in torch.nonzero(good_mask, as_tuple=False).view(-1).tolist():
        side_axes.append(AxisRecord(axis=axes_k[j].detach().cpu().numpy().astype(np.float32), n_geo=2, n_tex=2, role="side_tex"))
    return side_axes, good_cnt


def refine_texture_family(
    rot_sym_type: str,
    axes_with_tex: list[AxisRecord],
    pts_centered,
    colors_,
    device: str = "cuda",
    *,
    config: SymmetryAnalysisConfig | None = None,
) -> tuple[str | None, list[AxisRecord]]:
    """Map per-axis texture orders back to a texture-aware symmetry family."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    tex_cfg = cfg.texture
    device = tex_cfg.device if device == "cuda" else device
    active_axes = [rec for rec in axes_with_tex if (rec.n_tex is not None and ((isinstance(rec.n_tex, float) and np.isinf(rec.n_tex)) or rec.n_tex >= 2))]
    if len(active_axes) == 0 and rot_sym_type != "C(>1): Cylindrical Item":
        return None, []
    by_role = lambda name: [rec for rec in active_axes if rec.role == name]
    cnt = len(active_axes)

    if rot_sym_type == "C(>1): Cylindrical Item":
        main = by_role("main")[0] if by_role("main") else None
        if main is None:
            raw_main = [rec for rec in axes_with_tex if rec.role == "main"]
            if len(raw_main) == 0:
                return None, []
            side_axes = find_texture_2fold_axes_on_ring(pts_centered, colors_, raw_main[0].axis, device=device, M_dir=tex_cfg.ring_search_dirs, gain_threshold=tex_cfg.ring_gain_threshold, gap_th=tex_cfg.ring_cluster_gap, config=cfg)
            return ("D(=1): n-fold Pyramidal Item", side_axes) if len(side_axes) else (None, [])
        if isinstance(main.n_tex, float) and np.isinf(main.n_tex):
            return "C(>1): Cylindrical Item", active_axes
        side_axes, good_cnt = infer_side_axes_given_k(pts_centered, colors_, main.axis, int(round(float(main.n_tex))), device=device, M_dir=tex_cfg.side_axis_dirs, gain_threshold=tex_cfg.ring_gain_threshold, config=cfg)
        return ("D(>1): n-fold Prismatic Item", [main] + side_axes) if good_cnt >= 1 else ("D(=1): n-fold Pyramidal Item", [main])

    if rot_sym_type == "C(=1): Circular Item":
        main = by_role("main")[0] if by_role("main") else None
        if main is None:
            return None, []
        return ("C(=1): Circular Item", [main]) if (isinstance(main.n_tex, float) and np.isinf(main.n_tex)) else ("D(=1): n-fold Pyramidal Item", active_axes)
    if rot_sym_type == "D(=1): n-fold Pyramidal Item":
        return "D(=1): n-fold Pyramidal Item", active_axes
    if rot_sym_type == "D(>1): n-fold Prismatic Item":
        main = by_role("main")[0] if by_role("main") else None
        if main is None:
            return "D(=1): n-fold Pyramidal Item", active_axes
        return ("D(>1): n-fold Prismatic Item", active_axes) if len([rec for rec in by_role("side") if rec.n_tex is not None]) >= 1 else ("D(=1): n-fold Pyramidal Item", active_axes)
    if rot_sym_type == "P(20): Icosahedral Item":
        return ("D(=1): n-fold Pyramidal Item", active_axes) if cnt == 1 else ("P(4): Tetrahedral Item", active_axes)
    if rot_sym_type == "P(8): Octahedral Item":
        if cnt == 1:
            return "D(=1): n-fold Pyramidal Item", active_axes
        return ("P(4): Tetrahedral Item", active_axes) if cnt == 7 else ("D(>1): n-fold Prismatic Item", active_axes)
    if rot_sym_type == "P(4): Tetrahedral Item":
        return ("D(=1): n-fold Pyramidal Item", active_axes) if cnt == 1 else ("P(4): Tetrahedral Item", active_axes)
    return "Unknown: Texture-Induced Rotational Item", active_axes


def refine_symmetry_with_texture(
    ply_pts: np.ndarray,
    colors_: np.ndarray,
    rot_sym_type: str,
    center_ch: np.ndarray | None,
    axis_list: Any,
    n_geo_max: int,
    n_max_tex: int = 20,
    device: str = "cuda",
    *,
    config: SymmetryAnalysisConfig | None = None,
) -> tuple[dict[str, Any], Any]:
    """Refine the geometric symmetry result using texture consistency."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    tex_cfg = cfg.texture
    n_max_tex = tex_cfg.n_max_tex if n_max_tex == 20 else n_max_tex
    device = tex_cfg.device if device == "cuda" else device

    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    pts_t = torch.as_tensor(ply_pts, dtype=torch.float32, device=dev)
    center_t = torch.zeros(3, dtype=torch.float32, device=dev) if center_ch is None else torch.as_tensor(center_ch, dtype=torch.float32, device=dev).reshape(-1)[:3]
    if center_t.numel() < 3:
        center_t = torch.zeros(3, dtype=torch.float32, device=dev)
    pts_centered_t = pts_t - center_t
    colors_t = torch.as_tensor(colors_, dtype=torch.float32, device=dev)
    if colors_t.ndim == 1:
        colors_t = colors_t.view(-1, 1)

    center_np = center_t.detach().cpu().numpy().astype(np.float32).reshape(3)
    axes_geo = build_axis_records(axis_list, rot_sym_type, n_geo_max)
    axes_with_tex = []
    for rec in axes_geo:
        axes_with_tex.append(
            AxisRecord(
                axis=rec.axis,
                n_geo=rec.n_geo,
                n_tex=estimate_texture_order_for_axis(pts_centered_t, colors_t, rec, n_max_tex=n_max_tex, gain_threshold=tex_cfg.order_gain_threshold, device=device, config=cfg),
                role=rec.role,
            )
        )

    t_tex, axes_tex = refine_texture_family(rot_sym_type, axes_with_tex, pts_centered_t, colors_t, device=device, config=cfg)
    has_rot_sym_tex = (t_tex is not None) and (axes_tex is not None) and (len(axes_tex) > 0)
    sym_op = "symmetries_continuous" if t_tex in ["C(=1): Circular Item", "C(>1): Cylindrical Item"] else "symmetries_discrete"
    axes_sorted = sorted(
        axes_tex,
        key=lambda rec: (1e9 if (rec.n_tex is not None and isinstance(rec.n_tex, float) and np.isinf(rec.n_tex)) else float(rec.n_tex) if rec.n_tex is not None else -1.0),
        reverse=True,
    )

    sym_mats_tex = []
    for rec in axes_sorted:
        if rec.n_tex is None or float(rec.n_tex) == 0.0:
            theta_deg = 0.0
        else:
            nf = float(rec.n_tex)
            theta_deg = 1.0 if np.isinf(nf) else 360.0 / nf
        sym_mats_tex.append(build_rotation_transform(np.asarray(rec.axis, dtype=np.float32).reshape(-1)[:3], theta_deg, center_np))

    axes_out = [np.asarray(rec.axis, dtype=np.float32).reshape(-1)[:3].tolist() for rec in axes_sorted]
    if len(axes_sorted) == 0 or axes_sorted[0].n_tex is None:
        main_fold = 0
    else:
        n0f = float(axes_sorted[0].n_tex)
        main_fold = np.inf if np.isinf(n0f) else int(round(n0f))

    result = {
        "has_rot_sym_tex": has_rot_sym_tex,
        "sym_op": sym_op,
        "rot_sym_type": t_tex,
        "axes_tex": axes_out,
        "rot_sym_matrices": sym_mats_tex,
        "rot_center": center_np.tolist(),
    }
    return result, main_fold
