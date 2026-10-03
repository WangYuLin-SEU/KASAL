import struct

import numpy as np
import pytest

from kasal.bop_toolkit_lib import inout


@pytest.mark.parametrize("binary, corner_count, uv_count", [
    (False, 3, 6), (True, 3, 6), (False, 4, 6), (True, 3, 4),
])
def test_ply_file_roundtrip_and_invalid_list_lengths(tmp_path, binary, corner_count, uv_count):
    path = tmp_path / "triangle.ply"
    encoding = "binary_little_endian" if binary else "ascii"
    header = (
        f"ply\nformat {encoding} 1.0\ncomment TextureFile texture.png\n"
        "element vertex 3\nproperty float x\nproperty float y\nproperty float z\n"
        "property float intensity\nproperty uchar red\nproperty uchar green\nproperty uchar blue\n"
        "element face 1\nproperty list uchar int vertex_indices\n"
        "property list uchar float texcoord\nend_header\n"
    ).encode("ascii")
    vertices = [(0., 0., 0., 9., 255, 0, 0), (1., 0., 0., 8., 0, 255, 0), (0., 1., 0., 7., 0, 0, 255)]
    face = (corner_count, 0, 1, 2, uv_count, 0., 0., 1., 0., 0., 1.)
    if binary:
        body = b"".join(struct.pack("<ffffBBB", *vertex) for vertex in vertices)
        body += struct.pack("<BiiiBffffff", *face)
    else:
        body = "".join(" ".join(map(str, row)) + "\n" for row in [*vertices, face]).encode("ascii")
    path.write_bytes(header + body)

    if corner_count != 3 or uv_count != 6:
        message = "triangular" if corner_count != 3 else "UV face"
        with pytest.raises(ValueError, match=message):
            inout.load_ply(path)
        return

    model = inout.load_ply(path)
    np.testing.assert_array_equal(model["pts"], np.array(vertices)[:, :3])
    np.testing.assert_array_equal(model["colors"], np.array(vertices)[:, 4:])
    np.testing.assert_array_equal(model["faces"], [[0, 1, 2]])
    np.testing.assert_array_equal(model["texture_uv_face"], [[0., 0., 1., 0., 0., 1.]])
    assert model["texture_file"] == "texture.png"

    # Exporters supply RGBA; the PLY RGB fields must not shift subsequent UVs.
    colors = np.column_stack((model["colors"], [128, 64, 255]))
    uv = np.array([[0., 0.], [1., 0.], [0., 1.]])
    output = tmp_path / "roundtrip.ply"
    inout.save_ply(output, dict(model, colors=colors, texture_uv=uv))
    vertex_rows = output.read_text().split("end_header\n", 1)[1].splitlines()[:len(vertices)]
    assert all(len(row.split()) == 8 for row in vertex_rows)
    loaded = inout.load_ply(output)
    for field in ("pts", "colors", "faces", "texture_uv_face"):
        np.testing.assert_array_equal(loaded[field], model[field])
    np.testing.assert_allclose(loaded["texture_uv"], uv)
    assert loaded["texture_file"] == model["texture_file"]
