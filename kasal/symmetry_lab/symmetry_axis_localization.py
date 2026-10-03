# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""KASALv1 localization of user-selected symmetry templates."""

import fpsample
import numpy as np
import trimesh
from scipy import spatial

from kasal.symmetry_lab.symmetry_axis_template import clear_symmetry_fields
from kasal.config.algorithms import DEFAULT_KASALV1_CONFIG, KasalV1Config
from kasal.geometry.o3d_icp import refine_axis_center
from kasal.keyaxis.search import search_primary_key_axis, search_secondary_key_axis
from kasal.geometry.transforms import rotation_about_axis
from kasal.viz.symmetry_visual_export import apply_symmetry_orbit_colors


def _apply_model_bounds(model: dict) -> None:

    vertices = model["vertices"]
    model["min_x"] = np.min(vertices[:, 0])
    model["min_y"] = np.min(vertices[:, 1])
    model["min_z"] = np.min(vertices[:, 2])
    model["size_x"] = np.max(vertices[:, 0]) - np.min(vertices[:, 0])
    model["size_y"] = np.max(vertices[:, 1]) - np.min(vertices[:, 1])
    model["size_z"] = np.max(vertices[:, 2]) - np.min(vertices[:, 2])

def _transform_axis_template(axis_template, rotation, center):
    """Expand template axes and rotations in the localized frame."""

    rotation_transforms = []
    localized_axis_vectors = []
    for template_entry in axis_template:
        for template_axis in template_entry['axis_l']:
            axis_order = template_entry['num']+1
            rotation_step_deg = 360 / axis_order
            for rotation_index in range(axis_order - 1):
                rotation_angle_deg = (rotation_index+1) * rotation_step_deg
                rotation_transform = rotation_about_axis(np.dot(rotation, np.array(template_axis)), rotation_angle_deg, center)
                rotation_transforms.append(rotation_transform)
            localized_axis_vectors.append(np.dot(rotation, np.array(template_axis)))
    return localized_axis_vectors, rotation_transforms


def localize_symmetry_axes(
    model,
    template_or_step_path=None,
    symmetry_operation=None,
    color_symmetry_orbits=False,
    score_mode='pts',
    config: KasalV1Config = DEFAULT_KASALV1_CONFIG,
    refine_with_icp=True,
    axis_constraint=None,
):
    """Locate a specified symmetry template and update the mesh model in place.

    The template may also come from a closed, planar-face STEP model.
    Orbit coloring affects visualization only; score_mode selects the metric."""

    axis_template = []
    if isinstance(template_or_step_path, str):
        from kasal.utils.io_step import load_step_faces, infer_step_symmetry_axes

        step_faces = load_step_faces(template_or_step_path)
        step_axes, step_rotation_counts = infer_step_symmetry_axes(step_faces)
        for (step_axis, rotation_count) in zip(step_axes, step_rotation_counts):
            axis_template.append({'axis_l' : [step_axis.tolist()], 'num' : int(rotation_count)})
    elif isinstance(template_or_step_path, list):
        axis_template = template_or_step_path
    elif template_or_step_path is not None:
        raise ValueError('Expected an axis-template list, a STEP path, or None.')
    np.random.seed(config.seed)
    sample_indices = fpsample.bucket_fps_kdline_sampling(
        model["vertices"],
        min(config.fps_sample_count, model["vertices"].shape[0]),
        h=config.fps_h,
    )
    sampled_points = model['vertices'][sample_indices,:]
    sampled_colors = model['colors'][sample_indices,:]
    diameter = model['diameter']
    clear_symmetry_fields(model)
    if symmetry_operation in (
        "symmetries_continuous", "symmetries_continuous_2",
        "symmetries_continuous_3", "symmetries_discrete",
    ):
        mesh_mass = trimesh.Trimesh(
            vertices=model["vertices"].astype(np.float32),
            faces=model["faces"].astype(np.uint32),
        )
        center = mesh_mass.convex_hull.mass_properties["center_mass"]
        print("center_ch: ", center)
    if symmetry_operation == 'symmetries_continuous' or symmetry_operation == 'symmetries_continuous_2' or symmetry_operation == 'symmetries_continuous_3':
        primary_axis_info = search_primary_key_axis(
            sampled_points,
            sampled_colors,
            diameter,
            order=3,
            sample_count=config.primary_sample_count,
            center=center,
            score_mode=score_mode,
            axis_constraint=axis_constraint,
            axis_constraint_radius=config.axis_constraint_radius,
        )
        primary_axis = primary_axis_info['axis']
        if refine_with_icp:
            center, primary_axis = refine_axis_center(
                primary_axis_info,
                model["vertices"],
                diameter,
                center,
                config=config.refinement,
            )
        if symmetry_operation == 'symmetries_continuous_2' or symmetry_operation == 'symmetries_continuous_3':
            secondary_axis_info = search_secondary_key_axis(
                90,
                sampled_points,
                sampled_colors,
                primary_axis,
                diameter,
                order=2,
                sample_count=config.secondary_sample_count,
                center=center,
                score_mode=score_mode,
            )
            secondary_axis = secondary_axis_info['axis']
            if refine_with_icp:
                center, secondary_axis = refine_axis_center(
                    secondary_axis_info,
                    model["vertices"],
                    diameter,
                    center,
                    config=config.refinement,
                )
        _apply_model_bounds(model)
        if symmetry_operation == 'symmetries_continuous_2':
            rotation_transform = rotation_about_axis(secondary_axis, 180, center)
            model['symmetries_continuous'] = [{"axis": primary_axis.reshape((3)).tolist(), "offset": center.reshape((3)).tolist()}]
            model['symmetries_discrete'] = [rotation_transform.reshape((16)).tolist()]
        elif symmetry_operation == 'symmetries_continuous':
            model['symmetries_continuous'] = [{"axis": primary_axis.reshape((3)).tolist(), "offset": center.reshape((3)).tolist()}]
        elif symmetry_operation == 'symmetries_continuous_3':
            model['symmetries_continuous'] = [{"axis" : [], "offset": center.reshape((3)).tolist()}]

    elif symmetry_operation == 'symmetries_discrete':
        rotation_counts = []
        for template_entry in axis_template:
            rotation_counts.append(template_entry['num'])
        axis_order_indices = np.argsort( - np.array(rotation_counts))
        localized_axes = {}
        if rotation_counts:
            primary_template_index = axis_order_indices[0]
            primary_rotation_count = axis_template[primary_template_index]['num']
            primary_axis_info = search_primary_key_axis(
                sampled_points, sampled_colors, diameter,
                order=primary_rotation_count+1,
                sample_count=config.primary_sample_count,
                center=center,
                score_mode=score_mode,
                axis_constraint=axis_constraint if len(rotation_counts) == 1 else None,
                axis_constraint_radius=config.axis_constraint_radius,
            )
            primary_axis = primary_axis_info['axis']
            if refine_with_icp:
                center, primary_axis = refine_axis_center(
                    primary_axis_info, model["vertices"], diameter, center,
                    config=config.refinement,
                )
        if len(rotation_counts) == 1:
            localized_axes['axis'] = [primary_axis]
            model['axis'] = localized_axes['axis']
            model['center_ch'] = center
            localized_axes['axis_mat'] = []
            for rotation_index in range(primary_rotation_count):
                rotation_transform = rotation_about_axis(primary_axis, (rotation_index+1) * 360 / (primary_rotation_count+1), center)
                localized_axes['axis_mat'].append(rotation_transform)

        if len(rotation_counts) >= 2:
            secondary_template_index = axis_order_indices[1]
            secondary_rotation_count = axis_template[secondary_template_index]['num']
            primary_template_axis = axis_template[primary_template_index]['axis_l'][0]
            primary_template_axis = np.array(primary_template_axis) / np.linalg.norm(primary_template_axis)
            secondary_template_axis = axis_template[secondary_template_index]['axis_l'][0]
            secondary_template_axis = np.array(secondary_template_axis) / np.linalg.norm(secondary_template_axis)
            axis_dot_product = np.dot(primary_template_axis, secondary_template_axis)
            template_angle_rad = np.arccos(axis_dot_product)
            template_angle_deg = np.degrees(template_angle_rad)
            inter_axis_angle_deg = template_angle_deg
            secondary_axis_info = search_secondary_key_axis(
                inter_axis_angle_deg,
                sampled_points,
                sampled_colors,
                primary_axis,
                diameter,
                order=secondary_rotation_count+1,
                sample_count=config.secondary_sample_count,
                center=center,
                score_mode=score_mode,
            )
            secondary_axis = secondary_axis_info['axis']
            if refine_with_icp:
                center, secondary_axis = refine_axis_center(
                    secondary_axis_info,
                    model["vertices"],
                    diameter,
                    center,
                    config=config.refinement,
                )

            template_basis = np.array([primary_template_axis, secondary_template_axis, np.cross(primary_template_axis, secondary_template_axis)/np.linalg.norm(np.cross(primary_template_axis, secondary_template_axis))])
            localized_basis = np.array([primary_axis, secondary_axis, np.cross(primary_axis, secondary_axis)/np.linalg.norm(np.cross(primary_axis, secondary_axis))])
            rotation = np.dot(localized_basis.T, np.linalg.inv(template_basis.T))
            localized_axis_vectors, rotation_transforms = _transform_axis_template(
                axis_template, rotation, center,
            )
            localized_axes['axis'] = localized_axis_vectors
            model['axis'] = localized_axes['axis']
            model['center_ch'] = center
            localized_axes['axis_mat'] = rotation_transforms
        symmetries_discrete = []
        orbit_transforms = []
        orbit_transforms.append(np.eye(4))
        for transform in localized_axes['axis_mat']:
            symmetries_discrete.append(transform.reshape((16)))
            orbit_transforms.append(transform)
        symmetries_discrete = np.array(symmetries_discrete)
        distinct_orbit_found = 0
        for i in range(config.orbit_probe_attempts):
            reference_point = np.random.uniform(0,1,3)
            orbit_points = []
            for transform in orbit_transforms:
                transformed_reference = np.dot(transform[:3, :3], reference_point) + transform[:3, 3]
                orbit_points.append(transformed_reference)
            orbit_points = np.array(orbit_points)
            distances = spatial.distance.cdist(orbit_points, orbit_points, metric='euclidean').reshape((-1))
            zero_distances = distances[distances == 0]
            if zero_distances.shape[0] == orbit_points.shape[0]:
                distinct_orbit_found = 1
                break
        if distinct_orbit_found == 0:
            raise ValueError("Could not find distinct points for the symmetry orbit.")
        if color_symmetry_orbits:
            orbit_colors = np.random.randint(0, 255, (len(orbit_transforms), 3)).astype('int')
            apply_symmetry_orbit_colors(
                model,
                orbit_transforms,
                reference_point=reference_point,
                orbit_colors=orbit_colors,
            )
        _apply_model_bounds(model)
        model[symmetry_operation] = symmetries_discrete.tolist()

    return model
