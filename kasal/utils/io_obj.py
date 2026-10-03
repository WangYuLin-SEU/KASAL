# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import locale
import os
import shlex

import numpy as np


_DEFAULT_MATERIAL = "__default__"
_MAP_OPTION_ARITY = {
    "-blendu": 1,
    "-blendv": 1,
    "-boost": 1,
    "-bm": 1,
    "-cc": 1,
    "-clamp": 1,
    "-imfchan": 1,
    "-mm": 2,
    "-texres": 1,
    "-type": 1,
}


def _split_tokens(value: str) -> list[str]:
    return [token.strip('"') for token in shlex.split(value, posix=False)]


def _read_lines(filename: str) -> list[str]:
    # Single-byte locale codecs can silently misdecode GB18030 material names.
    encodings = ("utf-8-sig", "gb18030", locale.getpreferredencoding(False))
    for encoding in dict.fromkeys(encodings):
        try:
            with open(filename, "r", encoding=encoding) as stream:
                return stream.readlines()
        except UnicodeDecodeError:
            continue
    with open(filename, "r", encoding="utf-8", errors="replace") as stream:
        return stream.readlines()


def _normalize_reference_path(value: str) -> str:
    return value.replace("\\", os.sep).replace("/", os.sep)


def _parse_map_path(value: str) -> str:
    """Return the filename portion of a map_Kd statement."""

    tokens = _split_tokens(value)
    index = 0
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index].lower()
        index += 1
        if option in ("-o", "-s", "-t"):
            consumed = 0
            while index < len(tokens) and consumed < 3:
                try:
                    float(tokens[index])
                except ValueError:
                    break
                index += 1
                consumed += 1
            continue
        index += _MAP_OPTION_ARITY.get(option, 1)
    path = " ".join(tokens[index:]).strip()
    if not path:
        raise ValueError("map_Kd statement does not contain a texture path")
    return path


def _resolve_index(value: str, count: int, kind: str) -> int | None:
    if not value:
        return None
    raw = int(value)
    if raw == 0:
        raise ValueError(f"OBJ {kind} indices cannot be zero")
    resolved = raw - 1 if raw > 0 else count + raw
    if resolved < 0 or resolved >= count:
        raise ValueError(f"OBJ {kind} index {raw} is out of range")
    return resolved


class ObjModel:
    """Load the OBJ/MTL information needed by the Polyscope texture view."""

    @staticmethod
    def load_materials(filename):
        contents = {}
        material = None
        for raw_line in _read_lines(filename):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            keyword = parts[0]
            value = parts[1].strip() if len(parts) == 2 else ""
            if keyword == "newmtl":
                if not value:
                    raise ValueError(f"Missing material name in {filename}")
                material = contents.setdefault(value, {})
            elif material is None:
                continue
            elif keyword == "map_Kd":
                material[keyword] = _normalize_reference_path(_parse_map_path(value))
            elif keyword == "map_d":
                continue
            else:
                tokens = value.split()
                try:
                    material[keyword] = [float(token) for token in tokens]
                except ValueError:
                    material[keyword] = value
        return contents

    def __init__(self, filename, swap_yz=False):
        self.vertices = []
        self.normals = []
        self.texcoords = []
        self.faces = []
        self.faces_material = {}
        self.mtl = {}
        self.gl_list = 0
        dirname = os.path.dirname(filename)
        material = _DEFAULT_MATERIAL

        for raw_line in _read_lines(filename):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            keyword = parts[0]
            value = parts[1].strip() if len(parts) == 2 else ""
            if keyword == "v":
                vertex = list(map(float, value.split()[:3]))
                if swap_yz:
                    vertex = [vertex[0], vertex[2], vertex[1]]
                self.vertices.append(vertex)
            elif keyword == "vn":
                normal = list(map(float, value.split()[:3]))
                if swap_yz:
                    normal = [normal[0], normal[2], normal[1]]
                self.normals.append(normal)
            elif keyword == "vt":
                self.texcoords.append(list(map(float, value.split()[:2])))
            elif keyword in ("usemtl", "usemat"):
                material = value or _DEFAULT_MATERIAL
            elif keyword == "mtllib":
                self._load_material_references(dirname, value)
            elif keyword == "f":
                self._append_face(value, material)

        self.vertices = np.asarray(self.vertices, dtype=np.float64).reshape(-1, 3)
        self.texcoords = np.asarray(self.texcoords, dtype=np.float64).reshape(-1, 2)

    def _load_material_references(self, dirname: str, value: str) -> None:
        exact_reference = _normalize_reference_path(value.strip('"'))
        exact_path = os.path.join(dirname, exact_reference)
        references = [exact_reference] if os.path.isfile(exact_path) else [
            _normalize_reference_path(reference) for reference in _split_tokens(value)
        ]
        for reference in references:
            material_path = os.path.join(dirname, reference)
            try:
                self.mtl.update(self.load_materials(material_path))
            except OSError:
                # A missing material file should not prevent geometry display;
                # the caller will use a white texture for this material.
                continue

    def _append_face(self, value: str, material: str) -> None:
        references = value.split()
        if len(references) < 3:
            raise ValueError("OBJ faces must contain at least three vertices")

        vertices = []
        texcoords = []
        normals = []
        for reference in references:
            fields = reference.split("/")
            vertex = _resolve_index(fields[0], len(self.vertices), "vertex")
            if vertex is None:
                raise ValueError("OBJ face is missing a vertex index")
            vertices.append(vertex)
            texcoords.append(
                _resolve_index(fields[1], len(self.texcoords), "texture") if len(fields) >= 2 else None
            )
            normals.append(
                _resolve_index(fields[2], len(self.normals), "normal") if len(fields) >= 3 else None
            )

        for offset in range(1, len(vertices) - 1):
            triangle = [0, offset, offset + 1]
            face_vertices = [vertices[index] for index in triangle]
            face_texcoords = [texcoords[index] for index in triangle]
            face_normals = [normals[index] for index in triangle]
            self.faces.append((face_vertices, face_normals, face_texcoords, material))
            self._append_material_face(material, face_vertices, face_texcoords)

    def _append_material_face(self, material: str, vertices: list[int], texcoords: list[int | None]) -> None:
        material_info = self.mtl.get(material, {})
        texture_path = material_info.get("map_Kd")
        group_name = str(texture_path) if texture_path else material
        group = self.faces_material.setdefault(group_name, {"uv": [], "faces": []})
        if texture_path is None:
            group["mtl_0"] = material_info

        for texcoord in texcoords:
            if texcoord is None:
                group["uv"].append(np.zeros(2, dtype=np.float64))
            else:
                group["uv"].append(np.asarray(self.texcoords[texcoord], dtype=np.float64))
        group["faces"].append(np.asarray(vertices, dtype=np.int64))
