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


def bounding_box_info(vertices: np.ndarray, diameter: float) -> dict[str, float]:
    """Return the axis-aligned bounds fields shared by both pipelines."""

    vertex_min = vertices.min(axis=0)
    size = vertices.max(axis=0) - vertex_min
    return {
        "diameter": float(diameter),
        "min_x": float(vertex_min[0]),
        "min_y": float(vertex_min[1]),
        "min_z": float(vertex_min[2]),
        "size_x": float(size[0]),
        "size_y": float(size[1]),
        "size_z": float(size[2]),
    }
