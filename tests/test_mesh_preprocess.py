from pathlib import Path

import numpy as np

from kasal.utils.mesh_preprocess import (
    enrich_kasalv1_from_kasalv2,
    enrich_kasalv2_from_kasalv1,
    load_mesh_for_analysis,
)


def test_colored_mesh_roundtrip_preserves_geometry_and_color_domains(colored_mesh):
    path, vertices, colors = colored_mesh
    bundle = load_mesh_for_analysis(str(path), need_colors=True, policy="kasalv2_strict")
    analysis, legacy = bundle.model_input, bundle.kasalv1_model
    np.testing.assert_array_equal(legacy["vertices"], vertices)
    np.testing.assert_allclose(analysis["vertex_colors"], colors / 255.)
    np.testing.assert_allclose(legacy["colors"][:, :3], colors / 255.)
    np.testing.assert_array_equal(legacy["colors"][:, 3], 1.)
    assert legacy["diameter"] == analysis["diameter"] == np.sqrt(8.)
    assert len(analysis["analysis_points"]) > len(vertices)
    assert analysis["analysis_colors"].shape == analysis["analysis_points"].shape

    restored = enrich_kasalv2_from_kasalv1({}, legacy, need_colors=True)
    np.testing.assert_array_equal(restored["vertices"], analysis["vertices"])
    np.testing.assert_array_equal(restored["faces"], analysis["faces"])
    np.testing.assert_allclose(restored["vertex_colors"], analysis["vertex_colors"])
    assert restored["analysis_colors"].std() > 0

    # Surface samples have no positional correspondence to mesh vertices.
    sampled_only = dict(analysis)
    sampled_only.pop("vertex_colors")
    sampled_only["diameter"] = 7.5
    uncolored = enrich_kasalv1_from_kasalv2({}, sampled_only, need_colors=True)
    np.testing.assert_array_equal(uncolored["colors"], np.full((len(vertices), 4), 255.))
    assert uncolored["diameter"] == 7.5
    assert list(path.parent.iterdir()) == [path]


def test_texture_file_reaches_analysis_and_compatibility_models():
    path = Path(__file__).parents[1] / "kasal/datasets/texture_meshes/obj_000001_t.obj"
    bundle = load_mesh_for_analysis(str(path), need_colors=True, policy="kasalv2_strict")
    analysis, legacy = bundle.model_input, bundle.kasalv1_model
    assert analysis["analysis_colors"].shape == analysis["analysis_points"].shape
    assert legacy["colors"].shape == (len(analysis["vertices"]), 4)
    assert analysis["analysis_colors"].std() > 0
    assert legacy["colors"][:, :3].std() > 0
