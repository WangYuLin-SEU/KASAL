# Author: Tomas Hodan (hodantom@cmp.felk.cvut.cz)
# Center for Machine Perception, Czech Technical University in Prague

"""PLY I/O helpers used by KASAL.

This is the project-used subset of the bundled BOP I/O module. The original
license remains in ``LICENSE.txt`` in this package.
"""

import struct

import numpy as np


PLY_SCALAR_FORMATS = {
    "float": ("f", 4),
    "double": ("d", 8),
    "int": ("i", 4),
    "uchar": ("B", 1),
}


PLY_POINT_PROPERTIES = {
    "x",
    "y",
    "z",
    "nx",
    "ny",
    "nz",
    "red",
    "green",
    "blue",
    "texture_u",
    "texture_v",
}


def _read_ply_header(stream):
    """Read element counts, property layouts and the optional texture reference."""

    face_n_corners = 3
    n_points = 0
    n_faces = 0
    point_properties = []
    face_properties = []
    is_binary = False
    header_vertex_section = False
    header_face_section = False
    texture_file = None

    while True:
        line = stream.readline().decode("utf8").rstrip("\n").rstrip("\r")
        if line.startswith("comment TextureFile"):
            texture_file = line.split()[-1]
        elif line.startswith("element vertex"):
            n_points = int(line.split()[-1])
            header_vertex_section = True
            header_face_section = False
        elif line.startswith("element face"):
            n_faces = int(line.split()[-1])
            header_vertex_section = False
            header_face_section = True
        elif line.startswith("element"):
            header_vertex_section = False
            header_face_section = False
        elif line.startswith("property") and header_vertex_section:
            point_properties.append((line.split()[-1], line.split()[-2]))
        elif line.startswith("property list") and header_face_section:
            elements = line.split()
            if elements[-1] in ("vertex_indices", "vertex_index"):
                face_properties.append(("n_corners", elements[2]))
                for index in range(face_n_corners):
                    face_properties.append((f"ind_{index}", elements[3]))
            elif elements[-1] == "texcoord":
                face_properties.append(("texcoord", elements[2]))
                for index in range(face_n_corners * 2):
                    face_properties.append((f"texcoord_ind_{index}", elements[3]))
            else:
                print(f"Warning: Not supported face property: {elements[-1]}")
        elif line.startswith("format"):
            is_binary = "binary" in line
        elif line.startswith("end_header"):
            break
        elif not line:
            raise ValueError("PLY header ended before end_header")
    return n_points, n_faces, point_properties, face_properties, is_binary, texture_file


def _read_ply_vertex(stream, properties, is_binary):
    """Read the supported coordinate, normal, color and UV properties."""

    values = {}
    if is_binary:
        for name, data_type in properties:
            value_format, size = PLY_SCALAR_FORMATS[data_type]
            value = struct.unpack(value_format, stream.read(size))[0]
            if name in PLY_POINT_PROPERTIES:
                values[name] = value
    else:
        elements = stream.readline().decode("utf8").rstrip("\n").rstrip("\r").split()
        for property_id, (name, _) in enumerate(properties):
            if name in PLY_POINT_PROPERTIES:
                values[name] = elements[property_id]
    return values


def _read_ply_face(stream, properties, is_binary):
    """Read one face, checking list lengths before consuming their entries."""

    elements = None if is_binary else stream.readline().decode("utf8").split()
    values = {}
    for property_id, (name, data_type) in enumerate(properties):
        if is_binary:
            value_format, size = PLY_SCALAR_FORMATS[data_type]
            value = struct.unpack(value_format, stream.read(size))[0]
        else:
            value = elements[property_id]
        if name in ("n_corners", "texcoord"):
            count = value if is_binary else int(value)
            if name == "n_corners" and count != 3:
                raise ValueError("Only triangular faces are supported.")
            if name == "texcoord" and count != 6:
                raise ValueError("Wrong number of UV face coordinates.")
            continue
        values[name] = value
    return values


def load_ply(path):
    """Load a triangular PLY mesh into the dictionary format used by KASAL."""

    face_n_corners = 3
    with open(path, "rb") as stream:
        n_points, n_faces, point_properties, face_properties, is_binary, texture_file = _read_ply_header(stream)

        model = {}
        if texture_file is not None:
            model["texture_file"] = texture_file
        model["pts"] = np.zeros((n_points, 3), np.float64)
        if n_faces > 0:
            model["faces"] = np.zeros((n_faces, face_n_corners), np.float64)

        point_property_names = [prop[0] for prop in point_properties]
        face_property_names = [prop[0] for prop in face_properties]
        has_normals = {"nx", "ny", "nz"}.issubset(point_property_names)
        has_colors = {"red", "green", "blue"}.issubset(point_property_names)
        has_point_texture = {"texture_u", "texture_v"}.issubset(point_property_names)
        has_face_texture = "texcoord" in face_property_names

        if has_normals:
            model["normals"] = np.zeros((n_points, 3), np.float64)
        if has_colors:
            model["colors"] = np.zeros((n_points, 3), np.float64)
        if has_point_texture:
            model["texture_uv"] = np.zeros((n_points, 2), np.float64)
        if has_face_texture:
            model["texture_uv_face"] = np.zeros((n_faces, 6), np.float64)

        for point_id in range(n_points):
            values = _read_ply_vertex(stream, point_properties, is_binary)

            model["pts"][point_id] = [
                float(values["x"]),
                float(values["y"]),
                float(values["z"]),
            ]
            if has_normals:
                model["normals"][point_id] = [
                    float(values["nx"]),
                    float(values["ny"]),
                    float(values["nz"]),
                ]
            if has_colors:
                model["colors"][point_id] = [
                    float(values["red"]),
                    float(values["green"]),
                    float(values["blue"]),
                ]
            if has_point_texture:
                model["texture_uv"][point_id] = [
                    float(values["texture_u"]),
                    float(values["texture_v"]),
                ]

        for face_id in range(n_faces):
            values = _read_ply_face(stream, face_properties, is_binary)

            model["faces"][face_id] = [
                int(values["ind_0"]),
                int(values["ind_1"]),
                int(values["ind_2"]),
            ]
            if has_face_texture:
                model["texture_uv_face"][face_id] = [
                    float(values[f"texcoord_ind_{index}"]) for index in range(6)
                ]

    return model


def save_ply(path, model, extra_header_comments=None):
    """Save a KASAL model dictionary as an ASCII PLY file."""

    save_ply2(
        path,
        model["pts"],
        model.get("colors"),
        model.get("normals"),
        model.get("faces"),
        model.get("texture_uv"),
        model.get("texture_uv_face"),
        model.get("texture_file"),
        extra_header_comments,
    )


def save_ply2(
    path,
    pts,
    pts_colors=None,
    pts_normals=None,
    faces=None,
    texture_uv=None,
    texture_uv_face=None,
    texture_file=None,
    extra_header_comments=None,
):
    """Save PLY arrays in the format used by the bundled BOP loader."""

    if pts_colors is not None:
        pts_colors = np.asarray(pts_colors)
        assert len(pts) == len(pts_colors)

    valid_points = [not np.isnan(np.sum(point)) for point in pts]
    with open(path, "w") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        if texture_file is not None:
            stream.write(f"comment TextureFile {texture_file}\n")
        if extra_header_comments is not None:
            for comment in extra_header_comments:
                stream.write(f"comment {comment}\n")

        stream.write(
            f"element vertex {sum(valid_points)}\n"
            "property float x\n"
            "property float y\n"
            "property float z\n"
        )
        if pts_normals is not None:
            stream.write("property float nx\nproperty float ny\nproperty float nz\n")
        if pts_colors is not None:
            stream.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        if texture_uv is not None:
            stream.write("property float texture_u\nproperty float texture_v\n")
        if faces is not None:
            stream.write(
                f"element face {len(faces)}\n"
                "property list uchar int vertex_indices\n"
            )
        if texture_uv_face is not None:
            stream.write("property list uchar float texcoord\n")
        stream.write("end_header\n")

        for point_id, point_is_valid in enumerate(valid_points):
            if not point_is_valid:
                continue
            fields = ["{:.4f}".format(value) for value in pts[point_id].astype(float)]
            if pts_normals is not None:
                fields.extend("{:.4f}".format(value) for value in pts_normals[point_id].astype(float))
            if pts_colors is not None:
                fields.extend("{:d}".format(value) for value in pts_colors[point_id, :3].astype(int))
            if texture_uv is not None:
                fields.extend("{:.4f}".format(value) for value in texture_uv[point_id].astype(float))
            stream.write(" ".join(fields) + "\n")

        if faces is not None:
            for face_id, face in enumerate(faces):
                values = [len(face), *face.squeeze()]
                line = " ".join(map(str, map(int, values)))
                if texture_uv_face is not None:
                    uv = texture_uv_face[face_id]
                    line += " " + " ".join(map(str, [len(uv), *map(float, uv.squeeze())]))
                stream.write(line + "\n")
