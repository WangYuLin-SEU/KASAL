# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Unified mesh loading for kasalv2 and kasalv1 (original KASAL) pipelines.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

import kasal.config.runtime as config
from kasal.bop_toolkit_lib import misc
from kasal.geometry.bounds import bounding_box_info
from kasal.version_names import KASALV1_PREPROCESS, KASALV2_ENGINE, validate_preprocess_policy
from kasal.geometry.mesh_simplification import is_pymeshlab_available, simplify_mesh
from kasal.config.algorithms import DEFAULT_MESH_PREPROCESS_CONFIG, MeshPreprocessConfig
from kasal.rotational_symmetry.model_preprocess import load_preprocessed_model, preprocess_mesh_geometry


MESH_PREPROCESS_ERROR_TEMPLATE = """[KASAL] Mesh preprocessing failed.

Primary path (kasalv2) failed: {kasalv2_reason}
Fallback path (PyMeshLab simplify_mesh) is not available: {pymeshlab_reason}

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


class MeshPreprocessError(RuntimeError):
    """Raised when both kasalv2 and PyMeshLab preprocessing fail."""

    def __init__(
        self,
        *,
        kasalv2_reason: str,
        pymeshlab_reason: str | None,
        mesh_path: str,
        error_code: str = "KASAL_MESH_BOTH_FAILED",
    ):
        self.kasalv2_reason = kasalv2_reason
        self.pymeshlab_reason = pymeshlab_reason or "not installed"
        self.mesh_path = mesh_path
        self.error_code = error_code
        self.remediation = MESH_PREPROCESS_ERROR_TEMPLATE.format(
            kasalv2_reason=kasalv2_reason,
            pymeshlab_reason=self.pymeshlab_reason,
            mesh_path=mesh_path,
        )
        super().__init__(self.remediation)


@dataclass
class MeshPreprocessResult:
    backend: str
    model_input: dict[str, Any]
    kasalv1_model: dict[str, Any]
    bbox_info: dict[str, float]
    preprocess_meta: dict[str, Any] = field(default_factory=dict)


def resolve_preprocess_policy(
    policy: str | None = None,
    *,
    pymeshlab_available: bool | None = None,
) -> tuple[bool, bool]:
    """Map policy id to (prefer_kasalv2, adaptive_fallback)."""

    if pymeshlab_available is None:
        pymeshlab_available = is_pymeshlab_available()

    pol = validate_preprocess_policy(
        policy or config.mesh_preprocess_policy
    )
    if pol == "kasalv2_strict":
        return True, False
    if pol == KASALV1_PREPROCESS:
        return False, False
    if pol == "kasalv2_adaptive":
        return True, bool(pymeshlab_available)
    raise AssertionError(f"Unhandled mesh preprocessing policy: {pol}")


def load_mesh_for_analysis(
    input_path: str,
    *,
    need_colors: bool = False,
    policy: str | None = None,
    preprocess_config: MeshPreprocessConfig = DEFAULT_MESH_PREPROCESS_CONFIG,
) -> MeshPreprocessResult:
    """Load mesh for kasalv2 and/or kasalv1 analysis."""

    prefer_kasalv2, adaptive_fallback = resolve_preprocess_policy(policy)
    path = str(Path(input_path).expanduser().resolve())
    meta: dict[str, Any] = {"mesh_path": path, "policy": policy or config.mesh_preprocess_policy}

    if prefer_kasalv2:
        try:
            model_input, bbox_info = load_preprocessed_model(path, need_colors=need_colors)
            if len(model_input.get("analysis_points", [])) < preprocess_config.min_analysis_points:
                raise ValueError(f"Too few analysis points (< {preprocess_config.min_analysis_points})")
            diameter = float(model_input.get("diameter", 0.0))
            if not np.isfinite(diameter) or diameter <= 0:
                raise ValueError(f"Invalid diameter: {diameter}")
            kasalv1_model: dict[str, Any] = {}
            result = MeshPreprocessResult(
                backend=KASALV2_ENGINE,
                model_input=model_input,
                kasalv1_model=kasalv1_model,
                bbox_info=bbox_info,
                preprocess_meta={**meta, "format_route": "kasalv2_native"},
            )
            return enrich_mesh_bundle(result, need_colors=need_colors)
        except Exception as exc:
            meta["fallback_reason"] = str(exc)
            if not adaptive_fallback:
                raise MeshPreprocessError(
                    kasalv2_reason=str(exc),
                    pymeshlab_reason=None,
                    mesh_path=path,
                    error_code="KASAL_MESH_KASALV2_FAILED",
                ) from exc
            return _attempt_kasalv1_fallback(
                path, need_colors=need_colors, meta=meta,
                kasalv2_reason=str(exc), preprocess_config=preprocess_config,
            )

    return _attempt_kasalv1_fallback(
        path, need_colors=need_colors, meta=meta,
        kasalv2_reason="kasalv1 policy", preprocess_config=preprocess_config,
    )


def _attempt_kasalv1_fallback(
    path: str,
    *,
    need_colors: bool,
    meta: dict[str, Any],
    kasalv2_reason: str,
    preprocess_config: MeshPreprocessConfig,
) -> MeshPreprocessResult:
    if not is_pymeshlab_available():
        raise MeshPreprocessError(
            kasalv2_reason=kasalv2_reason,
            pymeshlab_reason="ImportError: pymeshlab not installed",
            mesh_path=path,
            error_code="KASAL_MESH_PYMESHLAB_UNAVAILABLE",
        )
    try:
        vertices, colors, faces, normals = simplify_mesh(
            input_file=path,
            target_face_count=preprocess_config.target_face_count,
            subdivision_iterations=preprocess_config.subdivision_iterations,
            need_colors=need_colors,
        )
        kasalv1_model = {
            "vertices": vertices,
            "colors": colors,
            "faces": faces,
            "normals": normals,
            "diameter": misc.calc_pts_diameter(vertices),
        }
    except Exception as exc:
        raise MeshPreprocessError(
            kasalv2_reason=kasalv2_reason,
            pymeshlab_reason=str(exc),
            mesh_path=path,
            error_code="KASAL_MESH_BOTH_FAILED",
        ) from exc

    result = MeshPreprocessResult(
        backend="kasalv1",
        model_input={},
        kasalv1_model=kasalv1_model,
        bbox_info=bounding_box_info(vertices, kasalv1_model["diameter"]),
        preprocess_meta={
            **meta,
            "backend": "kasalv1",
            "fallback_reason": kasalv2_reason,
            "format_route": f"{Path(path).suffix.lower()}_via_kasalv1_fallback",
        },
    )
    return enrich_mesh_bundle(result, need_colors=need_colors)


def enrich_mesh_bundle(result: MeshPreprocessResult, *, need_colors: bool = False) -> MeshPreprocessResult:
    """Bidirectionally fill model_input and kasalv1_model."""

    applied: list[str] = []
    model_input = dict(result.model_input)
    kasalv1_model = dict(result.kasalv1_model)

    if result.backend == "kasalv1":
        model_input = enrich_kasalv2_from_kasalv1(model_input, kasalv1_model, need_colors=need_colors)
        applied.append("kasalv2_from_kasalv1")
        if not result.model_input:
            result.preprocess_meta["mesh_topology"] = "kasalv1_simplified"
    elif result.backend == "kasalv2":
        kasalv1_model = enrich_kasalv1_from_kasalv2(kasalv1_model, model_input, need_colors=need_colors)
        applied.append("kasalv1_from_kasalv2")
        if not result.kasalv1_model:
            result.preprocess_meta.setdefault("mesh_topology", "kasalv2_raw")

    result.model_input = model_input
    result.kasalv1_model = kasalv1_model
    if applied:
        result.preprocess_meta["mesh_enrich_applied"] = applied
    return result


def enrich_kasalv2_from_kasalv1(
    model_input: dict,
    kasalv1_model: dict,
    *,
    need_colors: bool,
) -> dict:
    """Fill kasalv2 model_input from kasalv1 simplified mesh."""

    out = dict(model_input)
    verts = kasalv1_model.get("vertices")
    faces = kasalv1_model.get("faces")
    if verts is None or faces is None:
        return out

    color_sources = None
    colors = kasalv1_model.get("colors") if need_colors else None
    if colors is not None:
        colors = np.asarray(colors, dtype=np.float32)
        if colors.ndim == 2 and len(colors) == len(verts) and colors.shape[1] >= 3:
            color_sources = {"vertex_colors": colors[:, :3], "texture_available": True}

    model_input_new, _ = preprocess_mesh_geometry(
        np.asarray(verts, dtype=np.float32),
        np.asarray(faces, dtype=np.uint32),
        need_colors=need_colors,
        color_sources=color_sources,
    )
    out.update(model_input_new)
    out["diameter"] = kasalv1_model.get("diameter", out.get("diameter"))
    return out


def enrich_kasalv1_from_kasalv2(
    kasalv1_model: dict,
    model_input: dict,
    *,
    need_colors: bool,
) -> dict:
    """Fill kasalv1_model from kasalv2 model_input."""

    out = dict(kasalv1_model)
    verts = model_input.get("vertices")
    faces = model_input.get("faces")
    if verts is None or faces is None:
        return out

    out["vertices"] = np.asarray(verts, dtype=np.float32)
    out["faces"] = np.asarray(faces, dtype=np.uint32)
    diameter = model_input.get("diameter")
    if diameter is None:
        diameter = misc.calc_pts_diameter(out["vertices"])
    out["diameter"] = float(diameter)

    mesh = trimesh.Trimesh(vertices=out["vertices"], faces=out["faces"].astype(np.int64), process=False)
    try:
        out["normals"] = np.asarray(mesh.vertex_normals, dtype=np.float32)
    except Exception:
        out["normals"] = np.zeros((len(out["vertices"]), 3), dtype=np.float32)

    n = len(out["vertices"])
    colors = model_input.get("vertex_colors") if need_colors else None
    if colors is not None:
        colors = np.asarray(colors, dtype=np.float32)
        if colors.ndim == 2 and len(colors) == n and colors.shape[1] >= 3:
            rgb = colors[:, :3]
            alpha_value = 255.0 if rgb.size and float(np.max(rgb)) > 1.5 else 1.0
            alpha = np.full((n, 1), alpha_value, dtype=np.float32)
            out["colors"] = np.concatenate((rgb, alpha), axis=1)
        else:
            out["colors"] = np.ones((n, 4), dtype=np.float32) * 255.0
    else:
        # analysis_colors belong to sampled surface points and cannot be mapped
        # positionally onto raw mesh vertices.
        out["colors"] = np.ones((n, 4), dtype=np.float32) * 255.0
    return out
