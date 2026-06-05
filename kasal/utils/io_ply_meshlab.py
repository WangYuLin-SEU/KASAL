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
        import pymeshlab  # noqa: F401

        return True
    except Exception:
        return False


def simplify_3DModel_v2(input_file="", targetfacenum=20000, color_op=True):
    """Simplify the object model via PyMeshLab.

    Parameters
    ----------
    input_file : str
        Path to the mesh file.
    targetfacenum : int
        Target face count after decimation.
    color_op : bool
        Whether to retain vertex colors when possible.

    Returns
    -------
    tuple
        vertices, vertex_colors, faces, normals as numpy arrays.
    """

    import pymeshlab as ml

    mesh = ml.MeshSet()
    mesh.load_new_mesh(input_file)
    mesh_c = mesh.current_mesh()
    print(mesh.current_mesh_id())
    n1_ = mesh_c.face_number()
    print("Number of Vertices：", mesh_c.vertex_number())
    print("Number of Faces：", mesh_c.face_number())
    k0_ = int(np.log(targetfacenum / max(n1_, 1)) / np.log(4))
    if k0_ < 0:
        k0_ = 0

    key_ = list(mesh_c.textures().keys())
    if mesh_c.has_vertex_tex_coord() and len(key_) == 1:
        mesh.compute_texcoord_transfer_vertex_to_wedge()

    for _ in range(1):
        mesh.meshing_remove_duplicate_vertices()
        mesh.meshing_remove_duplicate_faces()
        mesh.meshing_repair_non_manifold_edges(method="Remove Faces")
        mesh.meshing_surface_subdivision_midpoint(iterations=4)
        mesh_c = mesh.current_mesh()
        print("Number of Vertices：", mesh_c.vertex_number())
        print("Number of Faces：", mesh_c.face_number())
        if mesh_c.has_wedge_tex_coord() and len(key_) == 1 and color_op:
            mesh.meshing_decimation_quadric_edge_collapse_with_texture(targetfacenum=targetfacenum)
        else:
            mesh.meshing_decimation_quadric_edge_collapse(
                targetfacenum=targetfacenum,
                preservenormal=True,
                preserveboundary=True,
                preservetopology=True,
                autoclean=True,
                planarquadric=True,
            )
        mesh_c = mesh.current_mesh()
        print("Number of Vertices：", mesh_c.vertex_number())
        print("Number of Faces：", mesh_c.face_number())

    mesh.compute_normal_for_point_clouds()
    mesh_c = mesh.current_mesh()
    vertex_matrix = mesh_c.vertex_matrix().copy()
    if color_op:
        if mesh_c.has_wedge_tex_coord():
            mesh.transfer_texture_to_color_per_vertex()
        vertex_color_matrix = mesh_c.vertex_color_matrix().copy()
    else:
        vertex_color_matrix = np.ones((vertex_matrix.shape[0], 4), dtype=np.uint8) * 255
    face_matrix = mesh_c.face_matrix().copy()
    vertex_normal_matrix = mesh_c.vertex_normal_matrix().copy()
    mesh.clear()
    return (
        vertex_matrix.astype(np.float32),
        vertex_color_matrix.astype(np.float32),
        face_matrix.astype(np.uint32),
        vertex_normal_matrix.astype(np.uint32),
    )
