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

import kasal.config.config as config
from kasal.version_names import KASALV1_PREPROCESS, KASALV2_ENGINE, normalize_preprocess_policy
from kasal.bop_toolkit_lib import misc
from kasal.utils.io_ply_meshlab import is_pymeshlab_available, simplify_3DModel_v2
from kasal.utils.mesh_preprocess_messages import MESH_PREPROCESS_ERROR_TEMPLATE
from kasal.rotational_symmetry.model_preprocess import load_preprocessed_model


MIN_ANALYSIS_POINTS = 100
SUPPORTED_MESH_SUFFIXES = (".ply", ".obj", ".glb", ".gltf", ".stl", ".off")


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

    @property
    def legacy_model(self) -> dict[str, Any]:
        """Deprecated alias for kasalv1_model."""
        return self.kasalv1_model


def resolve_preprocess_policy(
    policy: str | None = None,
    *,
    pymeshlab_available: bool | None = None,
) -> tuple[bool, bool]:
    """Map policy id to (prefer_kasalv2, adaptive_fallback)."""

    if pymeshlab_available is None:
        pymeshlab_available = is_pymeshlab_available()

    pol = normalize_preprocess_policy(policy or getattr(config, "mesh_preprocess_policy", "kasalv2_adaptive"))
    if pol == "kasalv2_strict":
        return True, False
    if pol == KASALV1_PREPROCESS:
        return False, False
    if pol == "kasalv2_adaptive":
        return True, bool(pymeshlab_available)
    return True, bool(pymeshlab_available)


def load_mesh_for_analysis(
    input_path: str,
    *,
    need_colors: bool = False,
    policy: str | None = None,
) -> MeshPreprocessResult:
    """Load mesh for kasalv2 and/or kasalv1 analysis."""

    prefer_kasalv2, adaptive_fallback = resolve_preprocess_policy(policy)
    path = str(Path(input_path).expanduser().resolve())
    meta: dict[str, Any] = {"mesh_path": path, "policy": policy or config.mesh_preprocess_policy}

    if prefer_kasalv2:
        try:
            model_input, bbox_info = load_preprocessed_model(path, need_colors=need_colors)
            if len(model_input.get("analysis_points", [])) < MIN_ANALYSIS_POINTS:
                raise ValueError(f"Too few analysis points (< {MIN_ANALYSIS_POINTS})")
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
            return _attempt_kasalv1_fallback(path, need_colors=need_colors, meta=meta, kasalv2_reason=str(exc))

    return _attempt_kasalv1_fallback(path, need_colors=need_colors, meta=meta, kasalv2_reason="kasalv1 policy")


def _attempt_kasalv1_fallback(
    path: str,
    *,
    need_colors: bool,
    meta: dict[str, Any],
    kasalv2_reason: str,
) -> MeshPreprocessResult:
    if not is_pymeshlab_available():
        raise MeshPreprocessError(
            kasalv2_reason=kasalv2_reason,
            pymeshlab_reason="ImportError: pymeshlab not installed",
            mesh_path=path,
            error_code="KASAL_MESH_PYMESHLAB_UNAVAILABLE",
        )
    try:
        kasalv1_model = _load_kasalv1_model(path, need_colors=need_colors)
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
        bbox_info=_bbox_from_kasalv1(kasalv1_model),
        preprocess_meta={
            **meta,
            "backend": "kasalv1",
            "fallback_reason": kasalv2_reason,
            "format_route": f"{Path(path).suffix.lower()}_via_kasalv1_fallback",
        },
    )
    return enrich_mesh_bundle(result, need_colors=need_colors)


def _load_kasalv1_model(path: str, *, need_colors: bool) -> dict:
    vertices, colors, faces, normals = simplify_3DModel_v2(
        input_file=path,
        targetfacenum=40000,
        color_op=need_colors,
    )
    model_i_ = {
        "vertices": vertices,
        "colors": colors,
        "faces": faces,
        "normals": normals,
        "diameter": misc.calc_pts_diameter(vertices),
    }
    return model_i_


def _bbox_from_kasalv1(kasalv1_model: dict) -> dict[str, float]:
    verts = np.asarray(kasalv1_model["vertices"], dtype=np.float32)
    vertex_min = verts.min(axis=0)
    vertex_max = verts.max(axis=0)
    size = vertex_max - vertex_min
    diameter = float(kasalv1_model.get("diameter", 0.0))
    return {
        "diameter": diameter,
        "min_x": float(vertex_min[0]),
        "min_y": float(vertex_min[1]),
        "min_z": float(vertex_min[2]),
        "size_x": float(size[0]),
        "size_y": float(size[1]),
        "size_z": float(size[2]),
    }


def enrich_mesh_bundle(result: MeshPreprocessResult, *, need_colors: bool = False) -> MeshPreprocessResult:
    """Bidirectionally fill model_input and kasalv1_model."""

    applied: list[str] = []
    model_input = dict(result.model_input)
    kasalv1_model = dict(result.kasalv1_model)

    if result.backend == "kasalv1" and model_input == {}:
        model_input = enrich_kasalv2_from_kasalv1({}, kasalv1_model, need_colors=need_colors)
        applied.append("kasalv2_from_kasalv1")
        result.preprocess_meta["mesh_topology"] = "kasalv1_simplified"
    elif result.backend == "kasalv2" and kasalv1_model == {}:
        kasalv1_model = enrich_kasalv1_from_kasalv2({}, model_input, need_colors=need_colors)
        applied.append("kasalv1_from_kasalv2")
        result.preprocess_meta.setdefault("mesh_topology", "kasalv2_raw")
    elif result.backend == "kasalv2" and kasalv1_model:
        kasalv1_model = enrich_kasalv1_from_kasalv2(kasalv1_model, model_input, need_colors=need_colors)
        applied.append("kasalv1_from_kasalv2")
    elif result.backend == "kasalv1" and model_input:
        model_input = enrich_kasalv2_from_kasalv1(model_input, kasalv1_model, need_colors=need_colors)
        applied.append("kasalv2_from_kasalv1")

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

    import tempfile

    mesh = trimesh.Trimesh(
        vertices=np.asarray(verts, dtype=np.float32),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as tmp:
        tmp_path = tmp.name
        mesh.export(tmp_path)
    model_input_new, _ = load_preprocessed_model(tmp_path, need_colors=need_colors)
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
    out["diameter"] = float(model_input.get("diameter", misc.calc_pts_diameter(out["vertices"])))

    mesh = trimesh.Trimesh(vertices=out["vertices"], faces=out["faces"].astype(np.int64), process=False)
    try:
        out["normals"] = np.asarray(mesh.vertex_normals, dtype=np.float32)
    except Exception:
        out["normals"] = np.zeros((len(out["vertices"]), 3), dtype=np.float32)

    n = len(out["vertices"])
    # kasalv1 expects float32 colors in 0–255 (same as PyMeshLab simplify_3DModel_v2).
    colors = np.ones((n, 4), dtype=np.float32) * 255.0
    if need_colors and "analysis_colors" in model_input:
        ac = np.asarray(model_input["analysis_colors"], dtype=np.float32)
        if ac.ndim == 2 and ac.shape[1] >= 3:
            if ac.max() <= 1.0:
                ac = ac * 255.0
            colors[:, :3] = ac[:n, :3]
    out["colors"] = colors
    return out


# Backward-compatible aliases (deprecated).
enrich_kasalv2_from_legacy = enrich_kasalv2_from_kasalv1
enrich_legacy_from_kasalv2 = enrich_kasalv1_from_kasalv2
