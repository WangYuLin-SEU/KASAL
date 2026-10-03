import locale

import numpy as np

from kasal.utils.io_obj import ObjModel


def test_obj_material_file_to_triangulated_mesh(tmp_path, monkeypatch):
    # cp1252 accepts these GB18030 bytes without reporting a decoding error.
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _do_setlocale=False: "cp1252")
    material_path = tmp_path / "表面 材质.mtl"
    material_path.write_text(
        'newmtl 表面\nmap_Kd -s 1 1 1 "表面 纹理.png"\n',
        encoding="gb18030",
    )
    obj_path = tmp_path / "quad.obj"
    obj_path.write_text(
        "\n".join(
            [
                'mtllib "表面 材质.mtl"',
                "v 0 0 0",
                "v 1 0 0",
                "v 1 1 0",
                "v 0 1 0",
                "vt 0 0",
                "vt 1 0",
                "vt 1 1",
                "vt 0 1",
                "usemtl 表面",
                "f -4/-4 -3/-3 -2/-2 -1/-1",
            ]
        ),
        encoding="gb18030",
    )

    model = ObjModel(str(obj_path))

    assert model.vertices.shape == (4, 3)
    group = model.faces_material["表面 纹理.png"]
    assert np.array_equal(group["faces"], [[0, 1, 2], [0, 2, 3]])
    np.testing.assert_array_equal(group["uv"], [[0, 0], [1, 0], [1, 1], [0, 0], [1, 1], [0, 1]])


def test_obj_loader_allows_missing_materials_and_texture_coordinates(tmp_path):
    obj_path = tmp_path / "plain.obj"
    obj_path.write_text(
        "v\t0 0 0\nv\t1 0 0\nv\t0 1 0\nusemtl plain\nf\t1 2 3\n",
        encoding="utf-8",
    )

    model = ObjModel(str(obj_path))

    group = model.faces_material["plain"]
    assert np.array_equal(group["faces"], [[0, 1, 2]])
    assert np.array_equal(group["uv"], np.zeros((3, 2)))
    assert group["mtl_0"] == {}
