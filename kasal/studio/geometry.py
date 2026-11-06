"""Read scalar attributes without changing vertex order or source geometry."""
from __future__ import annotations
import numpy as np


_GEOMETRY_PROPERTIES = {
    'x', 'y', 'z', 'nx', 'ny', 'nz', 'red', 'green', 'blue', 'alpha',
    'r', 'g', 'b', 'a', 's', 't', 'u', 'v', 'texture_u', 'texture_v',
    'vertex_index', 'vertex_indices', 'texcoord',
}


def scalar_fields(geometry) -> dict[tuple[str, str], np.ndarray]:
    """PLY numeric vertex/face properties, plus explicit Trimesh attributes.

    Reject arrays whose topology no longer matches (e.g. triangulated polygons
    or UV seam duplication). Guessing their correspondence would miscolor data.
    """
    fields = {}
    raw = geometry.metadata.get('_ply_raw', {})
    for domain, element, count, attribute in [
        ('point', 'vertex', len(geometry.vertices), 'vertex_attributes'),
        ('cell', 'face', len(getattr(geometry, 'faces', [])), 'face_attributes'),
    ]:
        if not count:
            continue
        data = raw.get(element, {}).get('data', {})
        names = data.keys() if isinstance(data, dict) else (getattr(data.dtype, 'names', None) or [])
        candidates = {str(name): data[name] for name in names if str(name).lower() not in _GEOMETRY_PROPERTIES}
        candidates.update(getattr(geometry, attribute, {}))
        for name, values in candidates.items():
            array = np.asarray(values)
            if array.dtype.kind not in 'iuf' or array.ndim == 0 or array.size != count or array.shape[0] != count:
                continue
            array = array.reshape(-1).astype(np.float64)
            if not np.isfinite(array).any():
                continue
            array[~np.isfinite(array)] = np.nan
            fields[(domain, str(name))] = array
    return fields


def finite_range(arrays) -> tuple[float, float] | None:
    ranges = []
    for values in arrays:
        finite = np.asarray(values)[np.isfinite(values)]
        if len(finite):
            ranges.append((float(finite.min()), float(finite.max())))
    if not ranges:
        return None
    return min(r[0] for r in ranges), max(r[1] for r in ranges)


def symmetry_lines(info: dict, fallback_center) -> list[tuple[np.ndarray, np.ndarray]]:
    """Resolve axis directions and offsets from current and classic annotations."""
    def vector(value, name):
        array = np.array(value, dtype=float, copy=True).reshape(-1)
        if array.size != 3 or not np.isfinite(array).all():
            raise ValueError(f'{name} must contain three finite coordinates.')
        return array

    def direction(value):
        axis = vector(value, 'Symmetry axis')
        length = np.linalg.norm(axis)
        if not np.isfinite(length) or length < 1e-12:
            raise ValueError('Symmetry axis must be nonzero and finite.')
        return axis / length

    center = vector(info.get('rot_center', info.get('center_ch', fallback_center)), 'Rotation center')
    axes = info.get('rot_sym_axis', info.get('axis', []))
    continuous = info.get('symmetries_continuous', [])
    discrete = info.get('symmetries_discrete', [])
    if any(not isinstance(value, (list, tuple, np.ndarray)) for value in (axes, continuous, discrete)):
        raise ValueError('Symmetry axes and transforms must be arrays.')
    candidates = []
    if len(axes):
        candidates = [(direction(raw), center.copy()) for raw in axes]
    elif len(continuous):
        for item in continuous:
            if not isinstance(item, dict):
                raise ValueError('Continuous symmetry entries must be objects.')
            raw = item.get('axis', [])
            if len(raw):
                candidates.append((direction(raw), vector(item.get('offset', center), 'Axis offset')))
    else:
        for transform in discrete:
            matrix = np.asarray(transform, dtype=float).reshape(4, 4)
            if not np.isfinite(matrix).all():
                raise ValueError('Symmetry transforms must be finite.')
            rotation = matrix[:3, :3]
            if np.allclose(rotation, np.eye(3)):
                continue
            if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(rotation), 1):
                raise ValueError('Symmetry transform must contain a proper rotation.')
            values, vectors = np.linalg.eig(rotation)
            axis = direction(np.real(vectors[:, np.argmin(np.abs(values - 1))]))
            # (I - R)c = t describes the fixed rotation axis, including translated meshes.
            offset = np.linalg.pinv(np.eye(3) - rotation) @ matrix[:3, 3]
            offset += axis * np.dot(center - offset, axis)
            candidates.append((axis, offset))
    lines = []
    for axis, offset in candidates:
        if not any(abs(np.dot(axis, old_axis)) > 1 - 1e-6 and
                   np.linalg.norm(np.cross(offset - old_offset, axis)) < 1e-6
                   for old_axis, old_offset in lines):
            lines.append((axis, offset))
    return lines
