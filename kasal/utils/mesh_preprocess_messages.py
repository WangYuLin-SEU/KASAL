# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# User-facing messages for mesh preprocessing failures.

from __future__ import annotations

MESH_PREPROCESS_ERROR_TEMPLATE = """[KASAL] Mesh preprocessing failed.

Primary path (kasalv2) failed: {kasalv2_reason}
Fallback path (PyMeshLab simplify_3DModel_v2) is not available: {pymeshlab_reason}

You can:
  (1) Install the FULL KASAL environment (includes PyMeshLab for legacy mesh simplify):
      python scripts/install_deps.py full-cpu
      or: python scripts/install_deps.py full-gpu
      See docs/install.md section "Full vs Headless".

  (2) Fix / standardize your mesh so kasalv2 can load it WITHOUT PyMeshLab:
      - Use triangle mesh (no quads/ngons); watertight or near-watertight preferred
      - Remove degenerate faces, duplicate vertices, zero-area triangles
      - One connected component; reasonable scale (not near-zero bbox)
      - Prefer .ply with valid face indices; for .obj ensure .mtl/texture paths exist if using ADI-C
      - Re-export from Blender/MeshLab: "Export PLY" binary, merge vertices, recalculate normals

  (3) Headless/server: use engine=kasalv2 in job JSON and fix the mesh; do not request engine=kasal without installing requirements/gui.txt.

Mesh file: {mesh_path}
"""
