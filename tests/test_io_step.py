import numpy as np
import pytest

from kasal.utils.io_step import infer_step_symmetry_axes, load_step_faces


def test_step_file_to_tetrahedron_axes_and_invalid_coordinates(tmp_path):
    vertices = [[1., 1., 1.], [-1., -1., 1.], [-1., 1., -1.], [1., -1., -1.]]
    entities = []

    def entity(text):
        entities.append(f"#{len(entities) + 1} = {text};")
        return f"#{len(entities)}"

    points = [entity(f"CARTESIAN_POINT('',({x},{y},{z}))") for x, y, z in vertices]
    refs = [entity(f"VERTEX_POINT('',{point})") for point in points]
    curve = entity(f"LINE('',{points[0]})")
    expected_faces = []
    for a, b, c in [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]:
        edges = []
        for start, end in [(a, b), (b, c), (c, a)]:
            edge = entity(f"EDGE_CURVE('',{refs[start]},{refs[end]},{curve},.T.)")
            edges.append(entity(f"ORIENTED_EDGE('',*,*,{edge},.T.)"))
        entity(f"EDGE_LOOP('',({','.join(edges)}))")
        expected_faces.append([[vertices[a], vertices[b]], [vertices[b], vertices[c]], [vertices[c], vertices[a]]])
    source = "ISO-10303-21;\nDATA;\n" + "\n".join(entities) + "\nENDSEC;\nEND-ISO-10303-21;\n"
    path = tmp_path / "tetrahedron.step"
    path.write_text(source, encoding="ascii")

    faces = load_step_faces(path)
    assert faces == expected_faces
    axes, counts = infer_step_symmetry_axes(faces)
    assert axes.shape == (7, 3)
    np.testing.assert_allclose(np.linalg.norm(axes, axis=1), 1.)
    np.testing.assert_array_equal(np.sort(counts), [1, 1, 1, 2, 2, 2, 2])

    path.write_text(source.replace("(1.0,1.0,1.0)", "(invalid,1.0,1.0)", 1), encoding="ascii")
    with pytest.raises(ValueError):
        load_step_faces(path)
