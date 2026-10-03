#!/usr/bin/env python3

# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Quick check that torch + pytorch3d (knn_points) work in the current environment."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from kasal.device import resolve_torch_device

    try:
        import torch
        from pytorch3d.ops import knn_points
    except ImportError as exc:
        print("FAIL:", exc, file=sys.stderr)
        print(
            "Install PyTorch3D from MiroPsota — see docs/install.md",
            file=sys.stderr,
        )
        return 1

    device = resolve_torch_device("cuda")
    x = torch.zeros(1, 4, 3, device=device)
    knn_points(x, x, K=1)
    print("OK torch", torch.__version__, "| pytorch3d import | device", device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
