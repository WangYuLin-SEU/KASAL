# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Bridge preprocess bundles into PyMeshLab for Polyscope display.

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from kasal.utils.mesh_preprocess import MeshPreprocessResult


def mesh_bundle_to_pymeshlab_meshset(
    bundle: MeshPreprocessResult,
    *,
    ml_meshset,
) -> int:
    """Write bundle display mesh into an existing MeshSet; return mesh_id."""

    display = bundle.kasalv1_model if bundle.kasalv1_model.get("vertices") is not None else bundle.model_input
    verts = np.asarray(display["vertices"], dtype=np.float64)
    faces = np.asarray(display["faces"], dtype=np.int32)
    colors = display.get("colors")
    if colors is not None:
        colors = np.asarray(colors, dtype=np.float32)
        if colors.max() > 1.5:
            colors = colors / 255.0
    ml_meshset.add_mesh(verts, faces, v_color_matrix=colors)
    return ml_meshset.current_mesh_id()


def write_display_ply(bundle: MeshPreprocessResult, path: Path) -> Path:
    """Write a temporary display PLY from bundle geometry."""

    import trimesh

    display = bundle.kasalv1_model if bundle.kasalv1_model.get("vertices") is not None else bundle.model_input
    mesh = trimesh.Trimesh(
        vertices=np.asarray(display["vertices"]),
        faces=np.asarray(display["faces"]),
        process=False,
    )
    path = Path(path)
    mesh.export(str(path))
    return path
