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
import open3d as o3d

from kasal.config.algorithms import RefinementConfig


def refine_axis_center(
    axis_info,
    vertices,
    diameter: float,
    center,
    *,
    config: RefinementConfig,
):
    """Refine a rotation center and axis from symmetry transforms using ICP."""

    voxel_size = diameter / config.voxel_size_divisor
    downsample_size = voxel_size / config.downsample_divisor
    vertices = np.asarray(vertices)

    target = o3d.geometry.PointCloud()
    target.points = o3d.utility.Vector3dVector(vertices.astype(np.float32))
    target = target.voxel_down_sample(downsample_size)
    if config.estimate_normals:
        target.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=voxel_size,
                max_nn=config.normal_max_neighbors,
            )
        )

    transforms = [np.eye(4)]
    for axis_transform in axis_info["axis_mat"]:
        source = o3d.geometry.PointCloud()
        transformed_points = (
            np.dot(axis_transform[:3, :3], vertices.T).T.astype(np.float32)
            + axis_transform[:3, 3]
        )
        source.points = o3d.utility.Vector3dVector(transformed_points)
        source = source.voxel_down_sample(downsample_size)
        if config.estimate_normals:
            source.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(
                    radius=voxel_size,
                    max_nn=config.normal_max_neighbors,
                )
            )
        result = o3d.pipelines.registration.registration_icp(
            source,
            target,
            voxel_size * config.icp_distance_factor,
            np.identity(4),
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(
                relative_fitness=config.icp_relative_fitness,
                relative_rmse=config.icp_relative_rmse,
                max_iteration=config.icp_max_iteration,
            ),
        )
        transforms.append(result.transformation)

    centers = []
    axes = []
    for transform in transforms:
        rotation = transform[:3, :3]
        centers.append(np.dot(rotation, center) + transform[:3, 3])
        axes.append(np.dot(rotation, center + axis_info["axis"]) - np.dot(rotation, center))

    refined_center = np.mean(np.asarray(centers), axis=0)
    refined_axis = np.mean(np.asarray(axes), axis=0)
    refined_axis /= np.linalg.norm(refined_axis)
    return refined_center, refined_axis
