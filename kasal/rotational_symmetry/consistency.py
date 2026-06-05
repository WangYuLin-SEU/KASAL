# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

import math

import torch
from pytorch3d.ops import knn_points

from .geometry import rodrigues

def _knn1_idx(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    squeeze_b = False
    if x.dim() == 2:
        x = x.unsqueeze(0)
        squeeze_b = True
    if y.dim() == 2:
        y = y.unsqueeze(0)

    result = knn_points(x, y, K=1, return_nn=False)
    idx = result.idx[..., 0].to(torch.long)
    return idx[0] if squeeze_b else idx

@torch.no_grad()
def geom_bad_ratio_after_rotation(
    x: torch.Tensor,
    y: torch.Tensor,
    diameter: float,
    bad_ratio_th: float = 0.15,
    q: float = 0.82,
    gain: float = 1.5,
    floor_ratio: float = 0.01,
    ceil_ratio: float = 0.02,
):
    if x.dim() != 2 or y.dim() != 2 or x.shape[1] != 3 or y.shape[1] != 3:
        raise ValueError(f"x,y must be (N,3); got x={tuple(x.shape)}, y={tuple(y.shape)}")

    idx = _knn1_idx(x, y)
    y_nn = y.index_select(0, idx)
    disp = torch.norm(x - y_nn, dim=-1)

    base = float(max(float(diameter), 1e-6))
    disp_q = torch.quantile(disp, float(q))
    geom_th_t = torch.clamp(
        disp_q * float(gain),
        float(floor_ratio) * base,
        float(ceil_ratio) * base,
    )

    bad_ratio = float((disp > geom_th_t).float().mean().item())
    ok = bad_ratio <= float(bad_ratio_th)
    return bool(ok), bad_ratio, float(geom_th_t.item())

@torch.no_grad()
def geom_pi_axis_consistency_ok(
    pts,
    center_ch,
    axis,
    diameter: float,
    bad_ratio_th: float = 0.15,
    q: float = 0.80,
    gain: float = 1.5,
    floor_ratio: float = 0.01,
    ceil_ratio: float = 0.03,
) -> bool:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    x_t = pts if torch.is_tensor(pts) else torch.as_tensor(pts, dtype=torch.float32)
    c_t = center_ch if torch.is_tensor(center_ch) else torch.as_tensor(center_ch, dtype=torch.float32)
    a_t = axis if torch.is_tensor(axis) else torch.as_tensor(axis, dtype=torch.float32)

    x_t = x_t.to(device=device, dtype=torch.float32)
    c_t = c_t.to(device=device, dtype=torch.float32).view(-1)[:3]
    a_t = a_t.to(device=device, dtype=torch.float32).view(-1)[:3]
    a_t = a_t / (torch.norm(a_t) + 1e-12)

    theta = torch.tensor([math.pi], device=device, dtype=torch.float32)
    rotation = rodrigues(a_t[None, :], theta)[0]

    x_c = x_t - c_t[None, :]
    y_c = x_c @ rotation.T

    ok, _, _ = geom_bad_ratio_after_rotation(
        x=x_c,
        y=y_c,
        diameter=float(diameter),
        bad_ratio_th=float(bad_ratio_th),
        q=float(q),
        gain=float(gain),
        floor_ratio=float(floor_ratio),
        ceil_ratio=float(ceil_ratio),
    )
    return bool(ok)
