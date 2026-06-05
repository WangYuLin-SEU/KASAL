# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

import fpsample
import numpy as np
import trimesh

from .config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
EXACT_DIAMETER_VERTEX_LIMIT = 25_000


SUPPORTED_MESH_SUFFIXES = (".ply", ".obj", ".glb", ".gltf", ".stl", ".off")


def load_preprocessed_model(
    input_path,
    need_colors: bool = False,
    config: SymmetryAnalysisConfig | None = None,
) -> tuple[Dict[str, Any], Dict[str, float]]:
    """Load one mesh file and build the analysis input dictionary."""

    cfg = DEFAULT_ANALYSIS_CONFIG if config is None else config
    path = Path(input_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_MESH_SUFFIXES:
        raise ValueError(
            f"Unsupported model format: {suffix}. Supported: {', '.join(SUPPORTED_MESH_SUFFIXES)}"
        )

    return _load_surface_candidate_model(path, need_colors=need_colors, config=cfg)


def _load_mesh_geometry_and_color_sources(
    path: Path,
    *,
    need_colors: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if path.suffix.lower() == ".ply":
        return _load_ply_geometry_and_color_sources(path, need_colors=need_colors)
    return _load_generic_mesh_geometry_and_color_sources(path, need_colors=need_colors)


def _load_generic_mesh_geometry_and_color_sources(
    path: Path,
    *,
    need_colors: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    loaded = trimesh.load(path, process=False)
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise ValueError(f"Empty scene: {path}")
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"No triangle meshes in scene: {path}")
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    else:
        mesh = loaded

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32).reshape(-1, 3)
    color_sources: dict[str, Any] = {"texture_available": False}
    if need_colors and _mesh_has_explicit_vertex_colors(mesh):
        colors = _ensure_rgb(np.asarray(mesh.visual.vertex_colors, dtype=np.float32))
        if colors.ndim == 2 and len(colors) == len(vertices) and colors.shape[1] >= 3:
            color_sources["vertex_colors"] = colors[:, :3].astype(np.float32, copy=False)
            color_sources["texture_available"] = True
    texture_path = _infer_texture_path(path)
    if texture_path is not None:
        color_sources["texture_path"] = texture_path
    return vertices, faces, color_sources


def _load_surface_candidate_model(
    path: Path,
    *,
    need_colors: bool,
    config: SymmetryAnalysisConfig,
) -> tuple[Dict[str, Any], Dict[str, float]]:
    vertices, faces, color_sources = _load_mesh_geometry_and_color_sources(path, need_colors=need_colors)
    if faces.shape[0] == 0:
        raise ValueError(f"Surface candidate preprocessing requires triangle faces: {path}")

    sample_count = max(int(config.sampling.fps_sample_count), 1)
    candidate_multiplier = max(int(config.sampling.mesh_surface_candidate_multiplier), 1)
    candidate_count = max(sample_count, sample_count * candidate_multiplier)
    candidate_points, candidate_colors = _sample_mesh_surface_candidates(
        vertices,
        faces,
        candidate_count,
        seed=int(config.seed.value),
        fps_h=int(config.sampling.fps_h),
        fps_start_idx=getattr(config.sampling, "fps_start_idx", None),
        color_sources=color_sources if need_colors else None,
    )
    if len(candidate_points) <= sample_count:
        analysis_points = candidate_points.astype(np.float32, copy=False)
        analysis_colors = None if candidate_colors is None else candidate_colors.astype(np.float32, copy=False)
    else:
        sample_idx = fpsample.bucket_fps_kdline_sampling(
            candidate_points,
            sample_count,
            h=int(config.sampling.fps_h),
            start_idx=_fps_start_arg(getattr(config.sampling, "fps_start_idx", None)),
        )
        analysis_points = candidate_points[sample_idx, :].astype(np.float32, copy=False)
        analysis_colors = None if candidate_colors is None else candidate_colors[sample_idx, :].astype(
            np.float32,
            copy=False,
        )

    diameter = _estimate_analysis_diameter(vertices, analysis_points)

    model_input = {
        "vertices": vertices,
        "faces": faces,
        "diameter": diameter,
        "analysis_points": analysis_points,
        "rotation_center": _estimate_rotation_center(vertices, faces),
    }
    if need_colors:
        if analysis_colors is None:
            analysis_colors = np.ones((len(analysis_points), 3), dtype=np.float32)
        model_input["analysis_colors"] = analysis_colors.astype(np.float32, copy=False)

    bbox_info = _bounding_box_info(vertices, diameter)
    texture_path = color_sources.get("texture_path")
    if texture_path is not None:
        bbox_info["texture_path"] = str(texture_path)
    return model_input, bbox_info


def _load_ply_geometry_and_color_sources(
    path: Path,
    *,
    need_colors: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    mesh = trimesh.load(path, process=False, force="mesh")
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32).reshape(-1, 3)
    color_sources: dict[str, Any] = {"texture_available": False}
    if not need_colors:
        return vertices, faces, color_sources

    if _mesh_has_explicit_vertex_colors(mesh):
        colors = _ensure_rgb(np.asarray(mesh.visual.vertex_colors, dtype=np.float32))
        if colors.ndim == 2 and len(colors) == len(vertices) and colors.shape[1] >= 3:
            color_sources["vertex_colors"] = colors[:, :3].astype(np.float32, copy=False)
            color_sources["texture_available"] = True

    texture_image = getattr(getattr(mesh.visual, "material", None), "image", None)
    texture_path = _infer_texture_path(path)
    if texture_image is not None:
        color_sources["texture_image"] = texture_image
    if texture_path is not None:
        color_sources["texture_path"] = texture_path

    if (texture_image is not None or texture_path is not None) and getattr(mesh.visual, "uv", None) is not None:
        texture_uv = np.asarray(mesh.visual.uv, dtype=np.float32)
        if texture_uv.ndim == 2 and len(texture_uv) == len(vertices) and texture_uv.shape[1] >= 2:
            color_sources["texture_uv"] = texture_uv[:, :2].astype(np.float32, copy=False)
            color_sources["texture_available"] = True

    texture_uv_face = _load_face_texture_uv(mesh)
    if (texture_image is not None or texture_path is not None) and texture_uv_face is not None:
        if texture_uv_face.ndim == 2 and len(texture_uv_face) == len(faces) and texture_uv_face.shape[1] >= 6:
            color_sources["texture_uv_face"] = texture_uv_face[:, :6].reshape(-1, 3, 2).astype(
                np.float32,
                copy=False,
            )
            color_sources["texture_available"] = True

    return vertices, faces, color_sources


def _mesh_has_explicit_vertex_colors(mesh: trimesh.Trimesh) -> bool:
    raw = mesh.metadata.get("_ply_raw", {})
    vertex_raw = raw.get("vertex", {}) if isinstance(raw, dict) else {}
    properties = vertex_raw.get("properties", {})
    prop_names = set(properties.keys()) if hasattr(properties, "keys") else set()
    color_names = {"red", "green", "blue"}
    return color_names.issubset(prop_names) and hasattr(mesh.visual, "vertex_colors")


def _infer_texture_path(path: Path) -> Path | None:
    for suffix in [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]:
        candidate = path.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def _load_face_texture_uv(mesh: trimesh.Trimesh) -> np.ndarray | None:
    raw = mesh.metadata.get("_ply_raw", {})
    face_raw = raw.get("face", {}) if isinstance(raw, dict) else {}
    face_data = face_raw.get("data", {})
    texcoord = face_data.get("texcoord") if hasattr(face_data, "get") else None
    if texcoord is None:
        return None
    arr = np.asarray(texcoord, dtype=np.float32)
    if arr.ndim == 2 and arr.shape[1] >= 6:
        return arr[:, :6]
    return None


def _fps_start_arg(start_idx: int | None):
    if start_idx is None or int(start_idx) < 0:
        return None
    return int(start_idx)


def _sample_vertex_colors(indices: np.ndarray, color_sources: dict[str, Any]) -> np.ndarray | None:
    vertex_colors = color_sources.get("vertex_colors")
    if vertex_colors is not None:
        return np.asarray(vertex_colors, dtype=np.float32)[indices, :3].astype(np.float32, copy=False)

    texture_uv = color_sources.get("texture_uv")
    texture_source = _texture_source(color_sources)
    if texture_uv is not None and texture_source is not None:
        return _sample_texture_colors(np.asarray(texture_uv, dtype=np.float32)[indices, :2], texture_source)
    return None


def _sample_face_colors(
    valid_faces: np.ndarray,
    valid_mask: np.ndarray,
    face_choice: np.ndarray,
    barycentric: np.ndarray,
    color_sources: dict[str, Any],
) -> np.ndarray | None:
    vertex_colors = color_sources.get("vertex_colors")
    if vertex_colors is not None:
        face_colors = np.asarray(vertex_colors, dtype=np.float32)[valid_faces][face_choice]
        return np.sum(face_colors * barycentric[:, :, None], axis=1, dtype=np.float32)

    texture_source = _texture_source(color_sources)
    if texture_source is None:
        return None

    texture_uv_face = color_sources.get("texture_uv_face")
    if texture_uv_face is not None:
        valid_face_uv = np.asarray(texture_uv_face, dtype=np.float32)[valid_mask]
        face_uv = valid_face_uv[face_choice]
        sampled_uv = np.sum(face_uv * barycentric[:, :, None], axis=1, dtype=np.float32)
        return _sample_texture_colors(sampled_uv.astype(np.float32, copy=False), texture_source)

    texture_uv = color_sources.get("texture_uv")
    if texture_uv is not None:
        face_uv = np.asarray(texture_uv, dtype=np.float32)[valid_faces][face_choice]
        sampled_uv = np.sum(face_uv * barycentric[:, :, None], axis=1, dtype=np.float32)
        return _sample_texture_colors(sampled_uv.astype(np.float32, copy=False), texture_source)
    return None


def _sample_mesh_surface_candidates(
    vertices: np.ndarray,
    faces: np.ndarray,
    sample_count: int,
    *,
    seed: int,
    fps_h: int,
    fps_start_idx: int | None,
    color_sources: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    verts = np.asarray(vertices, dtype=np.float32).reshape(-1, 3)
    faces_arr = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    if sample_count <= 0:
        return np.empty((0, 3), dtype=np.float32), None
    if faces_arr.size == 0:
        sample_idx = fpsample.bucket_fps_kdline_sampling(
            verts,
            min(sample_count, len(verts)),
            h=fps_h,
            start_idx=_fps_start_arg(fps_start_idx),
        )
        sampled_points = verts[sample_idx, :].astype(np.float32, copy=False)
        sampled_colors = None if color_sources is None else _sample_vertex_colors(sample_idx, color_sources)
        return sampled_points, sampled_colors

    triangles = verts[faces_arr]
    cross_prod = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    face_areas = 0.5 * np.linalg.norm(cross_prod, axis=1)
    valid_mask = np.isfinite(face_areas) & (face_areas > 1e-12)
    if not np.any(valid_mask):
        sample_idx = fpsample.bucket_fps_kdline_sampling(
            verts,
            min(sample_count, len(verts)),
            h=fps_h,
            start_idx=_fps_start_arg(fps_start_idx),
        )
        sampled_points = verts[sample_idx, :].astype(np.float32, copy=False)
        sampled_colors = None if color_sources is None else _sample_vertex_colors(sample_idx, color_sources)
        return sampled_points, sampled_colors

    valid_faces = faces_arr[valid_mask]
    valid_triangles = triangles[valid_mask]
    area_weights = face_areas[valid_mask].astype(np.float64)
    area_weights = area_weights / area_weights.sum()

    rng = np.random.default_rng(seed)
    face_choice = rng.choice(len(valid_triangles), size=sample_count, replace=True, p=area_weights)
    selected_triangles = valid_triangles[face_choice]

    r1 = np.sqrt(rng.random(sample_count, dtype=np.float32))
    r2 = rng.random(sample_count, dtype=np.float32)
    barycentric = np.stack(
        [
            1.0 - r1,
            r1 * (1.0 - r2),
            r1 * r2,
        ],
        axis=1,
    ).astype(np.float32, copy=False)
    sampled_points = np.sum(selected_triangles * barycentric[:, :, None], axis=1, dtype=np.float32)
    sampled_colors = None
    if color_sources is not None:
        sampled_colors = _sample_face_colors(valid_faces, valid_mask, face_choice, barycentric, color_sources)
        if sampled_colors is None and bool(color_sources.get("texture_available", False)):
            sampled_colors = np.ones((len(sampled_points), 3), dtype=np.float32)
    return sampled_points.astype(np.float32, copy=False), sampled_colors


def _estimate_analysis_diameter(vertices: np.ndarray, analysis_points: np.ndarray) -> float:
    verts = np.asarray(vertices, dtype=np.float32).reshape(-1, 3)
    if len(verts) <= EXACT_DIAMETER_VERTEX_LIMIT:
        return _calc_exact_diameter(verts)

    extreme_points = np.asarray(
        [
            verts[int(np.argmin(verts[:, 0]))],
            verts[int(np.argmax(verts[:, 0]))],
            verts[int(np.argmin(verts[:, 1]))],
            verts[int(np.argmax(verts[:, 1]))],
            verts[int(np.argmin(verts[:, 2]))],
            verts[int(np.argmax(verts[:, 2]))],
        ],
        dtype=np.float32,
    )
    subset = np.vstack([np.asarray(analysis_points, dtype=np.float32).reshape(-1, 3), extreme_points])
    return _calc_exact_diameter(subset)


def _texture_source(color_sources: dict[str, Any]) -> Any:
    return color_sources.get("texture_image") or color_sources.get("texture_path")


def _sample_texture_colors(texture_uv: np.ndarray, texture_source: Any) -> np.ndarray:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Texture color sampling requires Pillow to be installed.") from exc

    uv_image = Image.open(texture_source) if isinstance(texture_source, (str, Path)) else texture_source
    uv_image = uv_image.resize((uv_image.size[0] * 2, uv_image.size[1] * 2))
    colors = trimesh.visual.color.uv_to_interpolated_color(texture_uv, uv_image)
    return np.asarray(colors, dtype=np.float32) / 255.0


def _calc_exact_diameter(vertices: np.ndarray) -> float:
    """Compute the exact point-set diameter using convex hull vertices first."""

    pts = np.asarray(vertices, dtype=np.float64)
    if pts.shape[0] < 2:
        return 0.0

    diameter_pts = pts
    try:
        from scipy.spatial import ConvexHull

        hull = ConvexHull(pts)
        if len(hull.vertices) >= 2:
            diameter_pts = pts[hull.vertices]
    except Exception:
        diameter_pts = pts

    return math.sqrt(_max_pairwise_squared_distance(diameter_pts))


def _max_pairwise_squared_distance(points: np.ndarray, *, chunk_size: int = 256) -> float:
    pts = np.asarray(points, dtype=np.float64)
    max_sq = 0.0
    for start in range(0, pts.shape[0], chunk_size):
        chunk = pts[start : start + chunk_size]
        diff = chunk[:, None, :] - pts[None, :, :]
        sq_dist = np.einsum("ijk,ijk->ij", diff, diff, optimize=True)
        max_sq = max(max_sq, float(np.max(sq_dist)))
    return max_sq


def _estimate_rotation_center(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    if faces.shape[0] == 0:
        return vertices.mean(axis=0).astype(np.float32)
    mesh = trimesh.Trimesh(vertices=vertices.astype(np.float32), faces=faces.astype(np.int64), process=False)
    return np.asarray(mesh.convex_hull.mass_properties["center_mass"], dtype=np.float32)


def _bounding_box_info(vertices: np.ndarray, diameter: float) -> Dict[str, float]:
    vertex_min = vertices.min(axis=0)
    vertex_max = vertices.max(axis=0)
    size = vertex_max - vertex_min
    return {
        "diameter": float(diameter),
        "min_x": float(vertex_min[0]),
        "min_y": float(vertex_min[1]),
        "min_z": float(vertex_min[2]),
        "size_x": float(size[0]),
        "size_y": float(size[1]),
        "size_z": float(size[2]),
    }


def _ensure_rgb(colors: np.ndarray) -> np.ndarray:
    arr = np.asarray(colors, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] == 0:
        return arr
    if arr.shape[1] >= 3:
        arr = arr[:, :3]
    if arr.max() > 1.5:
        arr = arr / 255.0
    return arr.astype(np.float32)
