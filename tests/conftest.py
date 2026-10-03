from copy import deepcopy

import pytest

import kasal.config.runtime as config


@pytest.fixture(autouse=True)
def runtime_state(monkeypatch):
    """Keep CLI, annotation and GUI workflows independent of test order."""
    for name in (
        "mesh_paths", "current_mesh_index", "settings_path", "annotation_dirty",
        "annotation_load_errors", "selected_symmetry_type", "selected_n_fold",
        "selected_axis_constraint", "adi_color_enabled", "current_obj_info",
        "sym_type_source", "n_fold_source", "axis_xyz_source", "compute_engine",
        "mesh_preprocess_policy", "torch_device_id",
    ):
        monkeypatch.setattr(config, name, deepcopy(getattr(config, name)))
    monkeypatch.setenv("KASAL_TORCH_DEVICE", "cpu")


@pytest.fixture
def colored_mesh(tmp_path):
    """A small closed mesh with distinct vertex colors for file-to-result tests."""
    import numpy as np
    from kasal.bop_toolkit_lib.inout import save_ply2

    vertices = np.array([[1., 1., 1.], [-1., -1., 1.], [-1., 1., -1.], [1., -1., -1.]])
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]])
    path = tmp_path / "part.v1.ply"
    save_ply2(path, vertices, pts_colors=colors, faces=faces)
    return path, vertices, colors


@pytest.fixture
def v2_analysis(monkeypatch):
    """Replace only the expensive v2 search; retain real mesh I/O and export."""
    import sys
    from types import ModuleType, SimpleNamespace

    result = SimpleNamespace(
        raw={
            "has_rot_sym": True,
            "rot_sym_type": "D(=1): n-fold Pyramidal Item",
            "sym_op": "symmetries_discrete",
            "rot_sym_axis": [[0, 0, 1], [0, 0, -1]],
            "symmetries_discrete": [
                [0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            ],
        },
        n_fold=4,
        error=None,
        config=None,
    )

    def analyze(model_input, tex, config):
        if result.error is not None:
            raise result.error
        assert model_input["analysis_points"].shape[1] == 3
        if tex:
            assert model_input["analysis_colors"].shape == model_input["analysis_points"].shape
        result.config = config
        return result.raw, result.n_fold

    module = ModuleType("kasal.rotational_symmetry.analyzer")
    module.analyze_rotational_symmetry = analyze
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return result
