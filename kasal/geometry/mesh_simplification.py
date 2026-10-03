# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# PyMeshLab mesh simplification (optional GUI / legacy fallback).

from __future__ import annotations

import numpy as np


def is_pymeshlab_available() -> bool:
    """Return True when pymeshlab can be imported."""

    try:
        import pymeshlab
        return True
    except Exception:
        return False


def simplify_mesh(input_file: str, target_face_count: int, subdivision_iterations: int, need_colors: bool):
    """Simplify the object model via PyMeshLab.

    Parameters
    ----------
    input_file : str
        Path to the mesh file.
    target_face_count : int
        Target face count after decimation.
    subdivision_iterations : int
        Midpoint subdivision passes before decimation.
    need_colors : bool
        Whether to retain vertex colors when possible.

    Returns
    -------
    tuple
        vertices, vertex_colors, faces, normals as numpy arrays.
    """

    import pymeshlab as ml

    mesh_set = ml.MeshSet()
    mesh_set.load_new_mesh(input_file)
    current_mesh = mesh_set.current_mesh()
    print(mesh_set.current_mesh_id())
    print("Number of Vertices：", current_mesh.vertex_number())
    print("Number of Faces：", current_mesh.face_number())

    texture_names = list(current_mesh.textures().keys())
    if current_mesh.has_vertex_tex_coord() and len(texture_names) == 1:
        mesh_set.compute_texcoord_transfer_vertex_to_wedge()

    mesh_set.meshing_remove_duplicate_vertices()
    mesh_set.meshing_remove_duplicate_faces()
    mesh_set.meshing_repair_non_manifold_edges(method="Remove Faces")
    mesh_set.meshing_surface_subdivision_midpoint(iterations=subdivision_iterations)
    current_mesh = mesh_set.current_mesh()
    print("Number of Vertices：", current_mesh.vertex_number())
    print("Number of Faces：", current_mesh.face_number())
    if current_mesh.has_wedge_tex_coord() and len(texture_names) == 1 and need_colors:
        mesh_set.meshing_decimation_quadric_edge_collapse_with_texture(targetfacenum=target_face_count)
    else:
        mesh_set.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target_face_count,
            preservenormal=True,
            preserveboundary=True,
            preservetopology=True,
            autoclean=True,
            planarquadric=True,
        )
    current_mesh = mesh_set.current_mesh()
    print("Number of Vertices：", current_mesh.vertex_number())
    print("Number of Faces：", current_mesh.face_number())

    mesh_set.compute_normal_for_point_clouds()
    current_mesh = mesh_set.current_mesh()
    vertex_matrix = current_mesh.vertex_matrix().copy()
    if need_colors:
        if current_mesh.has_wedge_tex_coord():
            mesh_set.transfer_texture_to_color_per_vertex()
        vertex_color_matrix = current_mesh.vertex_color_matrix().copy()
    else:
        vertex_color_matrix = np.ones((vertex_matrix.shape[0], 4), dtype=np.uint8) * 255
    face_matrix = current_mesh.face_matrix().copy()
    vertex_normal_matrix = current_mesh.vertex_normal_matrix().copy()
    mesh_set.clear()
    return (
        vertex_matrix.astype(np.float32),
        vertex_color_matrix.astype(np.float32),
        face_matrix.astype(np.uint32),
        vertex_normal_matrix.astype(np.uint32),
    )
