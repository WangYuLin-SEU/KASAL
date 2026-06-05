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
import torch.nn.functional as F

from .config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig
from .geometry import (
    axis_from_phi_torch,
    batched_chamfer_distance,
    build_rotation_transform,
    euler_matrix,
    fibonacci_sampling,
    rodrigues,
)


def search_secondary_axis_at_angle(
    inter_axis_angle_deg,
    pts,
    primary_axis,
    div=2,
    center_ch=None,
    *,
    config: SymmetryAnalysisConfig | None = None,
    steps: int | None = None,
    lambda_pen: float | None = None,
    device: str | None = None,
):
    """Refine a secondary axis under a known inter-axis angle constraint."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    device = cfg.axis_search.device if device is None else device
    steps = cfg.axis_search.secondary_steps if steps is None else steps
    lambda_pen = cfg.axis_search.secondary_lambda_pen if lambda_pen is None else lambda_pen

    dis_ang = 360.0 / div
    topk = div * cfg.axis_search.secondary_topk_factor
    sample_num = topk * cfg.axis_search.secondary_sample_factor

    if center_ch is None:
        center_ch = np.zeros(3, dtype=np.float32)
    pts_c = pts - center_ch

    theta = float(np.deg2rad(inter_axis_angle_deg))
    primary_axis = primary_axis / np.linalg.norm(primary_axis)

    primary_axis_t = torch.tensor(primary_axis, dtype=torch.float32, device=device)
    helper = (
        torch.tensor([1.0, 0.0, 0.0], device=device)
        if abs(primary_axis[0]) < 0.9
        else torch.tensor([0.0, 1.0, 0.0], device=device)
    )
    tangent_0 = torch.linalg.cross(primary_axis_t, helper)
    tangent_0 = tangent_0 / tangent_0.norm()
    tangent_1 = torch.linalg.cross(primary_axis_t, tangent_0)

    phis_full = torch.linspace(0, 2 * torch.pi, sample_num * 2 + 1, device=device, dtype=torch.float32)[:-1]
    phis = phis_full[:sample_num]

    cos_theta = torch.cos(torch.tensor(theta, device=device))
    sin_theta = torch.sin(torch.tensor(theta, device=device))

    primary_axis_t = primary_axis_t.view(1, 3)
    tangent_0 = tangent_0.view(1, 3)
    tangent_1 = tangent_1.view(1, 3)
    phis = phis.view(-1)

    coarse_axes_t = (
        cos_theta * primary_axis_t
        + sin_theta
        * (
            torch.cos(phis).view(-1, 1) * tangent_0
            + torch.sin(phis).view(-1, 1) * tangent_1
        )
    )
    coarse_axes_t = coarse_axes_t / coarse_axes_t.norm(dim=1, keepdim=True)

    theta_rot = torch.tensor(np.deg2rad(dis_ang), dtype=torch.float32, device=device)
    rotation_batch = rodrigues(coarse_axes_t, theta_rot.expand(sample_num))
    pts_c_t = torch.tensor(pts_c, dtype=torch.float32, device=device)
    pts_expand = pts_c_t.unsqueeze(0).expand(sample_num, -1, -1)
    pts_rot = torch.bmm(pts_expand, rotation_batch.transpose(1, 2))
    errs = batched_chamfer_distance(pts_expand, pts_rot)

    top_ids = torch.topk(-errs, topk).indices
    cand_phis_t = phis[top_ids]

    n_opt_pts = min(cfg.sampling.optimization_sample_count, len(pts_c))
    idxs = np.random.choice(len(pts_c), n_opt_pts, replace=False)
    pts_t = torch.tensor(pts_c[idxs], dtype=torch.float32, device=device)
    band_t = torch.tensor(theta, dtype=torch.float32, device=device)
    theta_rot = torch.tensor(np.deg2rad(dis_ang), dtype=torch.float32, device=device)

    phis_t = cand_phis_t.clone().detach().requires_grad_(True)
    optimizer = torch.optim.Adam([phis_t], lr=cfg.axis_search.secondary_lr)

    batch_size = phis_t.shape[0]
    primary_axis_batch = primary_axis_t.expand(batch_size, 3)
    band_batch = band_t.expand(batch_size)
    pts_expand = pts_t.unsqueeze(0).expand(batch_size, -1, -1)
    theta_rot_batch = theta_rot.expand(batch_size)

    min_delta = cfg.axis_search.secondary_early_stop_delta
    patience = cfg.axis_search.secondary_early_stop_patience
    prev_losses = []

    for _ in range(steps):
        optimizer.zero_grad()
        axes = axis_from_phi_torch(primary_axis_batch, phis_t, band_batch)
        rotation_batch = rodrigues(axes, theta_rot_batch)
        pts_rot = torch.bmm(pts_expand, rotation_batch.transpose(1, 2))
        batch_losses = batched_chamfer_distance(pts_expand, pts_rot)
        penalty = lambda_pen * torch.mean(torch.abs(torch.sum(axes * primary_axis_t, dim=1) - torch.cos(band_t)))
        loss = batch_losses.mean() + penalty
        loss.backward()
        optimizer.step()
        prev_losses.append(loss.item())
        if len(prev_losses) > patience:
            prev_losses.pop(0)
            if max(prev_losses) - min(prev_losses) < min_delta:
                break

    with torch.no_grad():
        final_axes = axis_from_phi_torch(primary_axis_batch, phis_t, band_batch)
        rotation_batch = rodrigues(final_axes, theta_rot_batch)
        pts_rot = torch.bmm(pts_expand, rotation_batch.transpose(1, 2))
        batch_losses = batched_chamfer_distance(pts_expand, pts_rot)
        best_idx = batch_losses.argmin().item()
        best_axis = final_axes[best_idx].cpu().numpy()
        best_loss = batch_losses[best_idx].item()
        best_axis /= np.linalg.norm(best_axis)

    axis_matrices = [
        build_rotation_transform(best_axis, k * 360.0 / div, center_ch)
        for k in range(1, div)
    ]
    axis_matrices = np.stack(axis_matrices, axis=0)

    return {
        "axis": best_axis,
        "axis_mat": axis_matrices,
        "xyz_axis": coarse_axes_t.cpu().numpy(),
        "best_loss": best_loss,
    }


def score_candidate_axes(axes_t, pts_c_t, n_fold_candidates):
    """Score candidate axes across a set of rotational orders."""

    device = axes_t.device
    dtype = axes_t.dtype
    axes_t = F.normalize(axes_t, dim=1)
    batch_size = axes_t.shape[0]
    num_points = pts_c_t.shape[0]

    theta_list = []
    n_list = []
    n_repeat = []
    for n_fold in n_fold_candidates:
        if n_fold < 2:
            n_repeat.append(0)
            continue
        k = torch.arange(1, n_fold, device=device, dtype=dtype)
        theta_each = (2.0 * torch.pi / float(n_fold)) * k
        theta_list.append(theta_each)
        n_list.append(torch.full((n_fold - 1,), n_fold, device=device, dtype=torch.long))
        n_repeat.append(n_fold - 1)

    if sum(n_repeat) == 0:
        zero = torch.zeros(batch_size, device=device, dtype=dtype)
        return zero, {n: zero for n in n_fold_candidates}

    theta_flat = torch.cat(theta_list, dim=0)
    n_flat = torch.cat(n_list, dim=0)
    total_rotations = theta_flat.shape[0]

    axes_flat = axes_t.unsqueeze(1).expand(batch_size, total_rotations, 3).reshape(batch_size * total_rotations, 3)
    theta_flat_exp = theta_flat.view(1, total_rotations).expand(batch_size, total_rotations).reshape(batch_size * total_rotations)
    rotation_batch = rodrigues(axes_flat, theta_flat_exp)

    pts_rep = pts_c_t.unsqueeze(0).expand(batch_size, num_points, 3).unsqueeze(1)
    pts_rep = pts_rep.expand(batch_size, total_rotations, num_points, 3).contiguous().reshape(batch_size * total_rotations, num_points, 3)
    pts_rot = torch.bmm(pts_rep, rotation_batch.transpose(1, 2))

    losses_flat = batched_chamfer_distance(pts_rep, pts_rot).view(batch_size, total_rotations)

    uniq_n, inv = torch.unique(n_flat, sorted=True, return_inverse=True)
    per_n_tensor = torch.zeros(batch_size, uniq_n.numel(), device=device, dtype=losses_flat.dtype)
    per_n_tensor.scatter_add_(dim=1, index=inv.view(1, -1).expand(batch_size, -1), src=losses_flat)

    per_n = {}
    idx = 0
    for n_fold in n_fold_candidates:
        if n_fold < 2:
            per_n[n_fold] = torch.zeros(batch_size, device=device, dtype=losses_flat.dtype)
        else:
            per_n[n_fold] = per_n_tensor[:, idx]
            idx += 1

    mixed_loss = per_n_tensor.sum(dim=1)
    return mixed_loss, per_n


def search_primary_axis(
    pts,
    center_ch=None,
    n_fold_candidates=None,
    *,
    config: SymmetryAnalysisConfig | None = None,
    steps: int | None = None,
    device: str | None = None,
    max_angle_deg: float | None = None,
    lr: float | None = None,
    lambda_z: float | None = None,
):
    """Locate the dominant rotational axis."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    device = cfg.axis_search.device if device is None else device
    steps = cfg.axis_search.primary_steps if steps is None else steps
    max_angle_deg = cfg.axis_search.primary_max_angle_deg if max_angle_deg is None else max_angle_deg
    lr = cfg.axis_search.primary_lr if lr is None else lr
    lambda_z = cfg.axis_search.primary_lambda_z if lambda_z is None else lambda_z

    pts = np.asarray(pts, dtype=np.float32)
    if center_ch is None:
        center_ch = np.zeros(3, dtype=np.float32)
    pts_c = pts - center_ch
    dev = torch.device(device)

    n_opt_pts = min(cfg.sampling.optimization_sample_count, pts_c.shape[0])
    idxs = np.random.choice(pts_c.shape[0], n_opt_pts, replace=False)
    pts_c = pts_c[idxs]
    pts_t = torch.tensor(pts_c, dtype=torch.float32, device=dev)

    coarse_num = cfg.axis_search.primary_coarse_num
    topk = cfg.axis_search.primary_topk
    fine_num = cfg.axis_search.primary_fine_num
    topk_adam = cfg.axis_search.primary_topk_adam

    xyz = torch.tensor(fibonacci_sampling(coarse_num * 2 + 1, 1), dtype=torch.float32, device=dev)
    ai, aj, ak = (4 * np.pi) * (np.random.rand(3) - 0.5)
    global_rotation = torch.tensor(euler_matrix(ai, aj, ak)[:3, :3], dtype=torch.float32, device=dev)
    xyz = (global_rotation @ xyz.T).T
    xyz = xyz[xyz[:, 2] >= 0]

    coarse_loss, _ = score_candidate_axes(xyz, pts_t, n_fold_candidates)
    top_ids = torch.topk(-coarse_loss, k=min(topk, xyz.shape[0])).indices
    coarse_axes = xyz[top_ids]

    topk_c = coarse_axes.shape[0]
    phi = 2 * torch.pi * torch.rand(topk_c, fine_num, device=dev)
    u = torch.rand(topk_c, fine_num, device=dev)
    theta = torch.arccos(1 - u * (1 - torch.cos(torch.deg2rad(torch.tensor(max_angle_deg, device=dev)))))

    coarse_batch = coarse_axes.unsqueeze(1).expand(-1, fine_num, -1).reshape(-1, 3)
    phi = phi.reshape(-1)
    theta = theta.reshape(-1)
    candidate_axes = axis_from_phi_torch(coarse_batch, phi, theta)
    candidate_axes = candidate_axes / candidate_axes.norm(dim=1, keepdim=True)

    fine_loss, _ = score_candidate_axes(candidate_axes, pts_t, n_fold_candidates)
    top_ids2 = torch.topk(-fine_loss, k=min(topk_adam, candidate_axes.shape[0])).indices
    candidate_axes = candidate_axes[top_ids2]

    ab = torch.zeros(topk_adam, 2, device=dev, requires_grad=True)
    axis_seed = candidate_axes.clone().detach()

    helper = torch.tensor([1.0, 0.0, 0.0], device=dev).expand(topk_adam, 3)
    mask = torch.abs(axis_seed[:, 0]) > 0.9
    helper = helper.clone()
    helper[mask] = torch.tensor([0.0, 1.0, 0.0], device=dev)
    tangent_0 = torch.linalg.cross(axis_seed, helper, dim=1)
    tangent_0 = tangent_0 / tangent_0.norm(dim=1, keepdim=True)
    tangent_1 = torch.linalg.cross(axis_seed, tangent_0, dim=1)

    optimizer = torch.optim.Adam([ab], lr)
    min_delta = cfg.axis_search.primary_early_stop_delta
    patience = cfg.axis_search.primary_early_stop_patience
    prev_losses = []

    for _ in range(steps):
        optimizer.zero_grad()
        axis_t = axis_seed + ab[:, 0:1] * tangent_0 + ab[:, 1:2] * tangent_1
        axis_t = axis_t / axis_t.norm(dim=1, keepdim=True)

        mixed_loss, _ = score_candidate_axes(axis_t, pts_t, n_fold_candidates)
        if lambda_z > 0:
            mixed_loss = mixed_loss + lambda_z * axis_t[:, 2].abs()
        loss = mixed_loss.mean()
        loss.backward()
        optimizer.step()
        prev_losses.append(loss.item())
        if len(prev_losses) > patience:
            prev_losses.pop(0)
        if len(prev_losses) == patience and max(prev_losses) - min(prev_losses) < min_delta:
            break

    with torch.no_grad():
        axis_t = axis_seed + ab[:, 0:1] * tangent_0 + ab[:, 1:2] * tangent_1
        axis_t = axis_t / axis_t.norm(dim=1, keepdim=True)
        mixed_loss, _ = score_candidate_axes(axis_t, pts_t, n_fold_candidates)
        best_idx = torch.argmin(mixed_loss).item()
        best_axis = axis_t[best_idx].cpu().numpy()

    return best_axis
