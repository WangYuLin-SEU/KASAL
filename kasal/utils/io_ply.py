# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

import copy
import numpy as np
from kasal.bop_toolkit_lib import inout
from kasal.datasets.paths import arrow_path

def save_ply_model(model, output_ply, *, arrow_ratio: float, save_twofold_axis: bool):
    """Export the mesh and symmetry arrows; return serializable symmetry metadata.

    arrow_ratio scales arrows relative to the diameter. The caller handles
    atomic replacement of the output file."""

    def add_arrow(output_mesh, arrow_mesh, rotation, center, color_variant = 0):
        """Append transformed arrow geometry, normals and a selected color variant."""

        transformed_arrow = copy.deepcopy(arrow_mesh)
        transformed_arrow['pts'] = np.dot(rotation, transformed_arrow['pts'].T).T + center
        transformed_arrow['normals'] = np.dot(rotation, transformed_arrow['normals'].T).T
        output_mesh['faces'] = np.concatenate((output_mesh['faces'], transformed_arrow['faces'] + output_mesh['pts'].shape[0]), axis=0)
        output_mesh['pts'] = np.concatenate((output_mesh['pts'], transformed_arrow['pts']), axis=0)
        output_mesh['normals'] = np.concatenate((output_mesh['normals'], transformed_arrow['normals']), axis=0)
        if color_variant == 0:
            output_mesh['colors'] = np.concatenate((output_mesh['colors'], transformed_arrow['colors']), axis=0)
        elif color_variant == 1:
            arrow_colors = transformed_arrow['colors'].copy()
            arrow_colors[:,0] = transformed_arrow['colors'][:,2]
            arrow_colors[:,2] = transformed_arrow['colors'][:,0]
            output_mesh['colors'] = np.concatenate((output_mesh['colors'], arrow_colors), axis=0)
        elif color_variant == 2:
            arrow_colors = transformed_arrow['colors'].copy()
            arrow_colors[:,0] = transformed_arrow['colors'][:,1]
            arrow_colors[:,1] = transformed_arrow['colors'][:,0]
            output_mesh['colors'] = np.concatenate((output_mesh['colors'], arrow_colors), axis=0)
        return

    def rotation_between_vectors(source_axis, target_axis):
        """Return a 3x3 rotation mapping the source direction onto the target."""

        source = np.array(source_axis, dtype=float, copy=True)
        target = np.array(target_axis, dtype=float, copy=True)
        source_norm = np.linalg.norm(source)
        target_norm = np.linalg.norm(target)
        if source_norm == 0 or target_norm == 0:
            raise ValueError("Symmetry visualization axis must be non-zero.")
        source /= source_norm
        target /= target_norm
        cosine = float(np.clip(np.dot(source, target), -1.0, 1.0))

        if np.isclose(cosine, 1.0):
            return np.eye(3)
        if np.isclose(cosine, -1.0):
            basis = np.array([1.0, 0.0, 0.0])
            if abs(source[0]) > 0.9:
                basis = np.array([0.0, 1.0, 0.0])
            rotation_axis = np.cross(source, basis)
            rotation_axis /= np.linalg.norm(rotation_axis)
            return 2.0 * np.outer(rotation_axis, rotation_axis) - np.eye(3)

        cross = np.cross(source, target)
        skew = np.array(
            [
                [0.0, -cross[2], cross[1]],
                [cross[2], 0.0, -cross[0]],
                [-cross[1], cross[0], 0.0],
            ]
        )
        return np.eye(3) + skew + np.dot(skew, skew) * ((1.0 - cosine) / np.dot(cross, cross))

    model_info = model
    output_mesh = {}
    output_mesh['pts'] = np.array(model_info['vertices'], dtype='float')
    output_mesh['normals'] = np.array(model_info['normals'], dtype='float')
    output_mesh['faces'] = np.array(model_info['faces'], dtype='int')
    colors = np.array(model_info['colors'], dtype=float, copy=True)
    while colors.size and np.max(colors) > 1:
        colors /= 255
    output_mesh['colors'] = np.array(colors * 255, dtype='int')
    if 'sym_colors' in model_info:
        output_mesh['colors'] = np.array(np.asarray(model_info['sym_colors']) * 255, dtype='int')
    arrow_mesh = inout.load_ply(arrow_path)
    arrow_rgba = np.zeros((arrow_mesh['colors'].shape[0], 4), dtype=np.uint8)
    arrow_rgba[:, 3] = 255
    arrow_rgba[:, :3] = arrow_mesh['colors']
    arrow_mesh['colors'] = arrow_rgba
    arrow_x, arrow_y = arrow_mesh['pts'][:,0], arrow_mesh['pts'][:,1]
    arrow_mesh['pts'][:,0] -= (np.min(arrow_x)+np.max(arrow_x))/2
    arrow_mesh['pts'][:,1] -= (np.min(arrow_y)+np.max(arrow_y))/2
    arrow_mesh['pts'] = arrow_mesh['pts'] / 1000 * model_info['diameter'] * arrow_ratio
    if 'sym_colors' in model_info:
        for axis_i in model_info['axis']:
            rotation = rotation_between_vectors(np.array([0,0,1]), axis_i)
            add_arrow(output_mesh, arrow_mesh, rotation, model_info['center_ch'])
        inout.save_ply(output_ply, output_mesh)
    else:
        if 'symmetries_continuous' in model_info:
            if len(model_info['symmetries_continuous'][0]['axis']):
                rotation = rotation_between_vectors(np.array([0,0,1]), np.array(model_info['symmetries_continuous'][0]['axis']))
                add_arrow(output_mesh, arrow_mesh, rotation, np.array(model_info['symmetries_continuous'][0]['offset']))
            else:
                rotation = rotation_between_vectors(np.array([0,0,1]).astype(np.float32), np.array([1,0,0]).astype(np.float32))
                add_arrow(output_mesh, arrow_mesh, rotation, np.array(model_info['symmetries_continuous'][0]['offset']), color_variant = 0)
                rotation = rotation_between_vectors(np.array([0,0,1]).astype(np.float32), np.array([0,1,0]).astype(np.float32))
                add_arrow(output_mesh, arrow_mesh, rotation, np.array(model_info['symmetries_continuous'][0]['offset']), color_variant = 2)
                rotation = np.eye(3)
                add_arrow(output_mesh, arrow_mesh, rotation, np.array(model_info['symmetries_continuous'][0]['offset']), color_variant = 1)
            inout.save_ply(output_ply, output_mesh)
        if (
            'symmetries_discrete' in model_info
            and 'symmetries_continuous' in model_info
            and save_twofold_axis
        ):
            rotation = rotation_between_vectors(np.array([1,0,0]), np.array(model_info['symmetries_continuous'][0]['axis']))
            add_arrow(output_mesh, arrow_mesh, rotation, np.array(model_info['symmetries_continuous'][0]['offset']), color_variant=1)
            inout.save_ply(output_ply, output_mesh)
        elif 'symmetries_discrete' in model_info:
            for axis_i in model_info.get('axis', []):
                rotation = rotation_between_vectors(np.array([0,0,1]), axis_i)
                add_arrow(output_mesh, arrow_mesh, rotation, model_info['center_ch'])
            inout.save_ply(output_ply, output_mesh)
    symmetry_info = {}
    bounds_fields = [
        'diameter', 'min_x', 'min_y', 'min_z', 'size_x', 'size_y', 'size_z'
    ]
    symmetry_fields = [
        'symmetries_discrete', 'symmetries_continuous',
        'symmetries_continuous_2', 'symmetries_continuous_3'
    ]
    for field_name in bounds_fields:
        if field_name in model_info:
            symmetry_info[field_name] = float(model_info[field_name])
    for field_name in symmetry_fields:
        if field_name in model_info:
            symmetry_info[field_name] = np.array(model_info[field_name]).tolist()
    return symmetry_info
