# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Rigid transforms shared by the v1 and v2 symmetry pipelines."""

import numpy as np

def rotation_about_axis(axis, angle_deg, center):
    """Return a 4x4 rotation about a fixed center; angle_deg is in degrees.

    A NumPy axis array is normalized in place."""

    angle_rad = np.deg2rad(angle_deg)
    axis = np.asarray(axis)
    axis /= np.linalg.norm(axis)
    skew_matrix = np.array([[0, -axis[2], axis[1]],
                [axis[2], 0, -axis[0]],
                [-axis[1], axis[0], 0]])
    rotation = np.eye(3) + np.sin(angle_rad) * skew_matrix + (1 - np.cos(angle_rad)) * np.dot(skew_matrix, skew_matrix)
    transform = np.eye(4)
    transform[:3, :3] = rotation
    rotated_center = np.dot(rotation, center.reshape((3)), )
    center_offset = center - rotated_center
    transform[:3, 3] = center_offset
    return transform

