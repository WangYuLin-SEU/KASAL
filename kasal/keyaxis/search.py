# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""KASALv1 grid searches for primary and secondary symmetry axes."""

import numpy as np
from tqdm import tqdm

from kasal.config.algorithms import DEFAULT_KASALV1_CONFIG
from kasal.geometry.transforms import rotation_about_axis
from kasal.geometry.circular_sampling import circular_sampling
from kasal.keyaxis.color_error import rotation_alignment_errors
from kasal.bop_toolkit_lib.view_sampler import fibonacci_sampling
from kasal.bop_toolkit_lib.transform import euler_matrix


def _score_candidate_axes(
    candidate_axes,
    points,
    colors,
    rotation_angle,
    center,
    order,
    *,
    score_mode,
    label,
    diameter,
    show_progress=False,
):
    """Score candidate axes and return the best axis with non-identity rotations."""

    geometry_scores = []
    color_scores = []
    axes = []
    iterator = tqdm(candidate_axes) if show_progress else candidate_axes
    for candidate in iterator:
        transform = rotation_about_axis(candidate, rotation_angle, center)
        geometry_score, color_score = rotation_alignment_errors(points, colors, transform)
        geometry_scores.append(geometry_score)
        color_scores.append(color_score)
        axes.append(candidate)

    scores = np.asarray(color_scores if score_mode == "colors" else geometry_scores)
    best_ids = np.argsort(scores)[:10]
    best_scores = scores[best_ids]
    best_axes = np.asarray(axes)[best_ids]
    print("%s  %s / %s" % (label, str(np.min(best_scores[0])), str(diameter)))

    axis_transforms = [
        rotation_about_axis(best_axes[0], (index + 1) * rotation_angle, center)
        for index in range(order - 1)
    ]
    return {
        "axis": best_axes[0],
        "axis_mat": axis_transforms,
        "xyz_axis": candidate_axes,
        "dis_list": scores,
    }


def search_primary_key_axis(
    points,
    colors,
    diameter,
    order=2,
    center=None,
    sample_count=DEFAULT_KASALV1_CONFIG.primary_sample_count,
    use_hemisphere=True,
    score_mode='pts',
    axis_constraint=None,
    axis_constraint_radius=DEFAULT_KASALV1_CONFIG.axis_constraint_radius,
):
    """Search a Fibonacci sphere for the primary symmetry axis.

    score_mode selects geometry ("pts") or color ("colors"). The optional
    axis constraint uses distance between unit directions."""

    if center is None:
        center = np.array([0,0,0], dtype=np.float64)
    candidate_axes = fibonacci_sampling(sample_count, 1)
    candidate_axes = np.array(candidate_axes)
    angle_x, angle_y, angle_z = (4*np.pi) * (np.random.random(3) - 0.5)
    grid_rotation = euler_matrix(angle_x, angle_y, angle_z)[:3, :3]
    candidate_axes = np.dot(grid_rotation, candidate_axes.T).T
    if use_hemisphere:
        candidate_axes = candidate_axes[ candidate_axes[:, 2]>=0, :]
    if axis_constraint:
        if 'X' in axis_constraint:
            constraint_distances = candidate_axes.copy()
            constraint_distances[:, 0] = np.abs(constraint_distances[:, 0])
            constraint_distances = np.linalg.norm(constraint_distances - np.array([1, 0, 0]), axis=1)
            candidate_axes = candidate_axes[constraint_distances < axis_constraint_radius, :]
        if 'Y' in axis_constraint:
            constraint_distances = candidate_axes.copy()
            constraint_distances[:, 1] = np.abs(constraint_distances[:, 1])
            constraint_distances = np.linalg.norm(constraint_distances - np.array([0, 1, 0]), axis=1)
            candidate_axes = candidate_axes[constraint_distances < axis_constraint_radius, :]
        if 'Z' in axis_constraint:
            constraint_distances = candidate_axes.copy()
            constraint_distances[:, 2] = np.abs(constraint_distances[:, 2])
            constraint_distances = np.linalg.norm(constraint_distances - np.array([0, 0, 1]), axis=1)
            candidate_axes = candidate_axes[constraint_distances < axis_constraint_radius, :]
    if order <= 6:
        rotation_angle_deg = 360 / order
    if order > 6:
        rotation_angle_deg = int(120 / (360 / order)) * 360 / order
    return _score_candidate_axes(
        candidate_axes,
        points,
        colors,
        rotation_angle_deg,
        center,
        order,
        score_mode=score_mode,
        label="search_primary_key_axis",
        diameter=diameter,
        show_progress=True,
    )

def search_secondary_key_axis(
    angle_deg,
    points,
    colors,
    primary_axis,
    diameter,
    order=4,
    center=None,
    sample_count=DEFAULT_KASALV1_CONFIG.secondary_sample_count,
    score_mode='pts',
):
    """Search a circle at angle_deg degrees from the primary axis."""

    if center is None:
        center = np.array([0,0,0], dtype=np.float64)
    candidate_axes = circular_sampling(primary_axis, angle_deg, num_samples = sample_count)
    rotation_angle_deg = 360 / order
    return _score_candidate_axes(
        candidate_axes,
        points,
        colors,
        rotation_angle_deg,
        center,
        order,
        score_mode=score_mode,
        label="search_secondary_key_axis",
        diameter=diameter,
    )
