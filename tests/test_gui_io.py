import importlib
import json
import queue
import sys
from unittest.mock import MagicMock

import pytest

import kasal.config.runtime as config
from kasal.compute.symmetry_job import SymmetryJobSpec, run_symmetry_job


@pytest.fixture
def gui(monkeypatch, tmp_path):
    polyscope, imgui = MagicMock(), MagicMock()
    polyscope.imgui = imgui
    for name, module in {
        "cv2": MagicMock(), "pymeshlab": MagicMock(),
        "polyscope": polyscope, "polyscope.imgui": imgui,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    app = importlib.import_module("kasal.app.polyscope_app")
    from kasal.utils import compute_progress
    monkeypatch.setattr(compute_progress, "_progress", compute_progress.ComputeProgress())
    for name in (
        "ui_language", "ui_font_scale", "displayed_meshes", "settings_load_warning",
        "device_selection_warning", "dataset_folder_error", "ui_batch_status",
    ):
        monkeypatch.setattr(config, name, getattr(config, name))
    for name in ("compute_worker_done", "compute_worker_discard", "compute_worker_refresh_status"):
        monkeypatch.setattr(config, name, False)
    for name in ("compute_worker_process", "compute_worker_queue", "compute_worker_job",
                 "compute_worker_result", "cal_all_batch"):
        monkeypatch.setattr(config, name, None)
    monkeypatch.setattr(config, "show_coordinate_axes", False)
    config.mesh_paths = [str(tmp_path / "first.ply"), str(tmp_path / "second.ply")]
    config.current_mesh_index = 0
    config.settings_path = str(tmp_path / "KASAL.json")
    config.annotation_dirty = {0: False, 1: True}
    config.annotation_load_errors = {}
    config.torch_device_id = "cpu"
    yield app
    # Discard only the GUI module holding native-app substitutes, not all imports.
    sys.modules.pop("kasal.app.polyscope_app", None)


def test_compute_reload_edit_save_and_navigation(gui, colored_mesh, v2_analysis, tmp_path):
    mesh_path, _, _ = colored_mesh
    config.mesh_paths[0] = str(mesh_path)
    settings = {
        "start_id": 0, "mesh_preprocess_policy": "kasalv2_strict", "torch_device": "cpu",
        "ui_language": "zh", "ui_font_scale": 1.1, "note": "retain existing fields",
    }
    settings_path = tmp_path / "KASAL.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    assert gui._load_kasal_json_gui_settings(str(tmp_path), -1) == 0
    job = SymmetryJobSpec(str(mesh_path), adi_c=True, policy="kasalv2_strict")
    result = run_symmetry_job(job)
    assert result.success, result.error
    annotation_path = tmp_path / "part.v1_sym_type.json"
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    annotation["exporter_field"] = "preserve this output"
    annotation_path.write_text(json.dumps(annotation), encoding="utf-8")
    original_settings, original_annotation = settings_path.read_bytes(), annotation_path.read_bytes()

    config.annotation_dirty[0] = True
    config.selected_axis_constraint = "axis Z (blue)"
    config.compute_worker_queue = queue.Queue()
    config.compute_worker_queue.put(("done", (job, result, None)))
    gui._poll_compute_worker()
    assert annotation_path.read_bytes() == original_annotation
    assert config.selected_n_fold == 4 and config.current_obj_info == result.current_obj_info
    assert config.adi_color_enabled and config.selected_axis_constraint == job.axis_xyz
    assert not config.annotation_dirty[0]
    assert gui.get_compute_progress().stage_label == "Complete"

    gui._reload_current_object()
    assert settings_path.read_bytes() == original_settings
    gui._navigate_object(-1)
    assert config.current_mesh_index == 0
    assert settings_path.read_bytes() == original_settings
    assert annotation_path.read_bytes() == original_annotation
    config.selected_n_fold = 6
    gui.mark_object_dirty(0)
    assert gui.dirty_object_ids() == [0, 1]
    gui._navigate_object(1)
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved == dict(settings, start_id=1)
    assert gui._load_kasal_json_gui_settings(str(tmp_path), -1) == 1
    assert config.current_obj_info == {} and config.selected_symmetry_type == "None"
    assert json.loads(annotation_path.read_text(encoding="utf-8"))["n-fold"] == 6
    assert gui.dirty_object_ids() == [1]
    gui._navigate_object(-1)
    assert config.selected_n_fold == 6
    assert not (tmp_path / "second_sym_type.json").exists()


def test_dead_worker_reports_failure_without_saving(gui, tmp_path, capsys):
    class DeadProcess:
        exitcode = -9

        @staticmethod
        def is_alive():
            return False

        @staticmethod
        def join(timeout=None):
            return None

    job = SymmetryJobSpec(config.mesh_paths[0])
    config.compute_worker_process = DeadProcess()
    config.compute_worker_queue = queue.Queue()
    config.compute_worker_job = job
    config.compute_worker_done = False
    config.compute_worker_result = None
    config.annotation_dirty[0] = True

    gui._poll_compute_worker()

    assert config.compute_worker_process is None
    assert config.annotation_dirty[0]
    assert gui.get_compute_progress().stage_label == "Failed"
    assert "exit code -9" in capsys.readouterr().err
    assert not (tmp_path / "first_sym_type.json").exists()


@pytest.mark.parametrize("invalid_json", ["{", "[]"])
def test_invalid_kasal_settings_are_repaired_on_save(gui, tmp_path, invalid_json):
    settings_path = tmp_path / "KASAL.json"
    settings_path.write_text(invalid_json, encoding="utf-8")

    assert gui._load_kasal_json_gui_settings(str(tmp_path), -1) == 0
    gui._save_kasal_json_gui_settings()

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["start_id"] == config.current_mesh_index
    assert saved["torch_device"] == "cpu"
    assert "Invalid KASAL.json" in config.settings_load_warning


def test_invalid_saved_policy_and_device_are_repaired_with_visible_warning(gui, tmp_path, monkeypatch):
    settings_path = tmp_path / "KASAL.json"
    settings_path.write_text(
        json.dumps(
            {
                "mesh_preprocess_policy": "mystery",
                "torch_device": "cdua:0",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gui, "is_pymeshlab_available", lambda: False)

    assert gui._load_kasal_json_gui_settings(str(tmp_path), -1) == 0

    assert config.mesh_preprocess_policy == "kasalv2_strict"
    assert config.torch_device_id == "cpu"
    assert "Invalid mesh_preprocess_policy" in config.settings_load_warning
    assert "Invalid saved torch_device" in config.settings_load_warning
