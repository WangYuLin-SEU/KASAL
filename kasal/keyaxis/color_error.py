# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Nearest-neighbor scores used by KASALv1 candidate-axis search."""

import numpy as np
from scipy import spatial

def rotation_alignment_errors(points, colors, transform,):
    """Return mean geometry and color errors using nearest-neighbor matches.

    Keep the v1 row-vector rotation convention for score consistency."""
    transformed_points = np.dot(points, transform[:3,:3])+transform[:3,3]
    point_tree = spatial.cKDTree(points)
    distances, nearest_indices = point_tree.query(transformed_points, k=1)
    color_differences = colors - colors[nearest_indices, :]
    color_distances = np.linalg.norm(color_differences, axis=1)
    color_error = np.mean(color_distances)
    distance_error = np.mean(distances)
    return distance_error, color_error
