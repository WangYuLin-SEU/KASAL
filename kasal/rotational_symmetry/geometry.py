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
from pytorch3d.ops import knn_points

from kasal.geometry.transforms import rotation_about_axis
from kasal.symmetry_lab.symmetry_axis_template import get_symmetry_axis_template


def batched_chamfer_distance(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Compute the symmetric Chamfer distance for batched point clouds."""

    if x.dim() == 2:
        x = x.unsqueeze(0)
    if y.dim() == 2:
        y = y.unsqueeze(0)
    r1 = knn_points(x, y, K=1, return_nn=True)
    r2 = knn_points(y, x, K=1, return_nn=True)
    d_x2y = torch.norm(r1.knn[..., 0, :] - x, dim=-1)
    d_y2x = torch.norm(r2.knn[..., 0, :] - y, dim=-1)
    out = 0.5 * (d_x2y.mean(dim=1) + d_y2x.mean(dim=1))
    return out[0] if out.shape[0] == 1 else out


def axis_from_phi_torch(v1: torch.Tensor, phi: torch.Tensor, theta_rad: torch.Tensor) -> torch.Tensor:
    """Construct a new axis from a base axis, azimuth and inter-axis angle."""

    v1 = v1 / v1.norm(dim=-1, keepdim=True)
    helper = torch.tensor([1.0, 0.0, 0.0], device=v1.device).expand_as(v1)
    mask = torch.abs(v1[..., 0]) > 0.9
    helper = helper.clone()
    helper[mask] = torch.tensor([0.0, 1.0, 0.0], device=v1.device)
    t0 = torch.linalg.cross(v1, helper, dim=-1)
    t0 = t0 / t0.norm(dim=-1, keepdim=True)
    t1 = torch.linalg.cross(v1, t0, dim=-1)
    axis = torch.cos(theta_rad)[..., None] * v1 + torch.sin(theta_rad)[..., None] * (
        torch.cos(phi)[..., None] * t0 + torch.sin(phi)[..., None] * t1
    )
    axis = axis / axis.norm(dim=-1, keepdim=True)
    return axis


def rodrigues(axis: torch.Tensor, theta: torch.Tensor) -> torch.Tensor:
    """Compute Rodrigues rotation matrices for a batch of axes and angles."""

    axis = axis / axis.norm(dim=-1, keepdim=True)
    a1, a2, a3 = axis.unbind(-1)
    zeros = torch.zeros_like(a1)

    cross_matrix = torch.stack(
        (
            torch.stack((zeros, -a3, a2), dim=-1),
            torch.stack((a3, zeros, -a1), dim=-1),
            torch.stack((-a2, a1, zeros), dim=-1),
        ),
        dim=-2,
    )

    identity = torch.eye(3, dtype=axis.dtype, device=axis.device)
    identity = identity.expand(axis.shape[:-1] + (3, 3))

    sin_t = torch.sin(theta)[..., None, None]
    cos_t = torch.cos(theta)[..., None, None]
    return identity + sin_t * cross_matrix + (1 - cos_t) * (cross_matrix @ cross_matrix)


def get_template_axis_angle(rot_sym_type, main_n_fold):
    """Measure the angle between the first two template axes of a symmetry family."""

    axis_list = get_symmetry_axis_template(rot_sym_type, main_n_fold)
    if axis_list is None or len(axis_list) < 2:
        raise ValueError("The template must contain at least two axes.")

    axis1 = np.array(axis_list[0]["axis_l"][0])
    axis2 = np.array(axis_list[1]["axis_l"][0])
    axis1 = axis1 / np.linalg.norm(axis1)
    axis2 = axis2 / np.linalg.norm(axis2)
    dot = np.clip(np.dot(axis1, axis2), -1.0, 1.0)
    return float(np.degrees(np.arccos(dot)))


def generate_symmetry_transforms(main_n_fold, sym_type, primary_axis, secondary_axis, center_ch):
    """Generate all symmetry axes and discrete transforms from a template family."""

    template_list = get_symmetry_axis_template(sym_type, main_n_fold)
    if not template_list:
        raise ValueError(f"get_symmetry_axis_template({sym_type}, {main_n_fold}) returned an empty template.")
    if len(template_list) < 1 or any(len(entry["axis_l"]) == 0 for entry in template_list):
        raise ValueError("The symmetry template contains an empty axis list.")

    tpl_axis1 = np.asarray(template_list[0]["axis_l"][0], dtype=np.float64)
    if len(template_list) > 1 and len(template_list[1]["axis_l"]) > 0:
        tpl_axis2 = np.asarray(template_list[1]["axis_l"][0], dtype=np.float64)
    else:
        tpl_axis2 = tpl_axis1

    def _make_basis(a1, a2, eps=1e-12):
        e1 = normalize_vector(a1)
        a2_proj = a2 - np.dot(a2, e1) * e1
        if np.linalg.norm(a2_proj) < eps:
            helper = np.array([1.0, 0.0, 0.0]) if abs(e1[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
            a2_proj = helper - np.dot(helper, e1) * e1
        e2 = normalize_vector(a2_proj)
        e3 = normalize_vector(np.cross(e1, e2))
        return np.column_stack([e1, e2, e3])

    tpl_basis = _make_basis(tpl_axis1, tpl_axis2)
    model_basis = _make_basis(primary_axis, secondary_axis)
    rotation_map = model_basis @ tpl_basis.T

    entries = []
    for entry in template_list:
        div = int(entry.get("num", 0)) + 1
        if div >= 2 and entry.get("axis_l", None):
            entries.append((div, entry))
    entries.sort(key=lambda item: item[0], reverse=True)

    axes_model = []
    matrices_list = []
    for div, entry in entries:
        step_deg = 360.0 / div
        for axis_template in entry["axis_l"]:
            axis_template = np.asarray(axis_template, dtype=np.float64).reshape(3)
            axis_model = normalize_vector(rotation_map @ axis_template)
            axes_model.append(axis_model)
            for k in range(1, div):
                matrices_list.append(rotation_about_axis(axis_model, k * step_deg, center_ch))

    return axes_model, matrices_list


def normalize_vector(v, eps=1e-12):
    """Normalize a 3D vector."""

    v = np.asarray(v, dtype=np.float64).reshape(3)
    norm = np.linalg.norm(v)
    if norm < eps:
        raise ValueError("zero-length vector")
    return v / norm


def compute_axis_rotation_loss(pts, axis, angle_deg, center_ch=None, device=None):
    """Measure Chamfer loss after rotating a point cloud around one axis."""

    if isinstance(pts, np.ndarray):
        pts_t = torch.tensor(pts, dtype=torch.float32)
    else:
        pts_t = pts
    dev = pts_t.device if device is None else torch.device(device)
    pts_t = pts_t.to(dev)
    if center_ch is None:
        center_t = torch.zeros(3, dtype=torch.float32, device=dev)
    else:
        center_t = torch.as_tensor(center_ch, dtype=torch.float32, device=dev).reshape(-1)[:3]
        if center_t.numel() < 3:
            center_t = torch.zeros(3, dtype=torch.float32, device=dev)
    axis = np.asarray(axis, dtype=np.float32)
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    axis_batch = torch.tensor(axis, dtype=torch.float32, device=dev).view(1, 3)
    theta_rad = torch.tensor([np.deg2rad(angle_deg)], dtype=torch.float32, device=dev)
    rotation_batch = rodrigues(axis_batch, theta_rad)
    pts_centered = pts_t - center_t[None, :]
    pts_expand = pts_centered.unsqueeze(0)
    pts_rot = torch.bmm(pts_expand, rotation_batch.transpose(1, 2))

    loss_t = batched_chamfer_distance(pts_expand, pts_rot)
    loss = loss_t.item() if loss_t.dim() == 0 else loss_t[0].item()
    return float(loss)
