from copy import deepcopy

import pytest

import kasal.config.runtime as config


def pytest_addoption(parser):
    parser.addoption('--desktop', action='store_true',
                     help='Include real Qt/VTK windows and v2 worker workflows.')


def pytest_ignore_collect(collection_path, config):
    # Keep the base-only CI runnable without importing optional desktop libraries.
    if collection_path.name == 'desktop' and not config.getoption('--desktop'):
        return True
    return None


@pytest.fixture(autouse=True)
def runtime_state(monkeypatch):
    """Keep workflows independent of runtime globals and the host's GPU selection."""
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
    """Keep base-only batch CI fast; desktop tests use the real v2 worker."""
    import sys
    from types import ModuleType

    def analyze(model_input, tex, config):
        return {
            'has_rot_sym': True,
            'rot_sym_type': 'D(=1): n-fold Pyramidal Item',
            'sym_op': 'symmetries_discrete',
            'rot_sym_axis': [[0, 0, 1]],
            'symmetries_discrete': [
                [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            ],
        }, 2

    module = ModuleType("kasal.rotational_symmetry.analyzer")
    module.analyze_rotational_symmetry = analyze
    monkeypatch.setitem(sys.modules, module.__name__, module)
