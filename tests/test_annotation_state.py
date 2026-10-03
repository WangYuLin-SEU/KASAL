import json
from pathlib import Path

import pytest

import kasal.config.runtime as config
from kasal.annotations.state import (
    dirty_object_ids, initialize_dataset_dirty_state, load_symmetry_type,
    saved_object_ids, save_symmetry_type,
)
from kasal.utils import io_json


@pytest.mark.parametrize("invalid_json", [
    "{", "[]",
    *[json.dumps(document) for document in (
        {"schema_version": 99},
        {"sym_type": "mystery"},
        {"n-fold": "4"},
        {"ADI-C": "yes"},
        {"current_obj_info": []},
        {"schema_version": 2, "kasal_v2": {"compute_engine": "mystery"}},
    )],
])
def test_invalid_annotation_is_isolated_without_overwriting(tmp_path, invalid_json):
    config.mesh_paths = [str(tmp_path / "bad.ply"), str(tmp_path / "new.ply")]
    config.current_mesh_index = 0
    bad_sidecar = tmp_path / "bad_sym_type.json"
    bad_sidecar.write_text(invalid_json, encoding="utf-8")

    errors = initialize_dataset_dirty_state(config.mesh_paths)
    assert 0 in errors and str(bad_sidecar) in errors[0]
    assert config.annotation_dirty[0]
    assert dirty_object_ids() == [1] and saved_object_ids() == []
    load_symmetry_type()
    assert 0 in config.annotation_load_errors
    assert config.selected_symmetry_type == "None"
    assert bad_sidecar.read_text(encoding="utf-8") == invalid_json


def test_annotation_write_failure_preserves_previous_file(monkeypatch, tmp_path):
    config.mesh_paths = [str(tmp_path / "mesh.ply")]
    config.current_mesh_index = 0
    config.selected_symmetry_type = "D(=1): n-fold Pyramidal Item"
    config.annotation_dirty = {0: True}
    target = tmp_path / "mesh_sym_type.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def fail_after_partial_write(value, stream, *, indent, ensure_ascii):
        stream.write("{")
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(io_json.json, "dump", fail_after_partial_write)
    with pytest.raises(RuntimeError, match="simulated write failure"):
        save_symmetry_type()
    assert target.read_text(encoding="utf-8") == '{"old": true}'
    assert config.annotation_dirty[0]
    assert sorted(path.name for path in tmp_path.iterdir()) == [target.name]


def test_sidecar_delete_failure_is_not_reported_as_saved(monkeypatch, tmp_path):
    stale_ply = tmp_path / "mesh_sym.ply"
    stale_ply.write_text("stale", encoding="utf-8")
    config.mesh_paths = [str(tmp_path / "mesh.ply")]
    config.current_mesh_index = 0
    config.annotation_dirty = {0: True}
    config.selected_symmetry_type = "None"
    config.current_obj_info = {"has_rot_sym": False}
    config.sym_type_source = config.n_fold_source = "kasalv2_auto"
    original_unlink = Path.unlink

    def reject_stale_ply(path, missing_ok=False):
        if path == stale_ply:
            raise PermissionError("sidecar is locked")
        return original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", reject_stale_ply)
    with pytest.raises(PermissionError, match="sidecar is locked"):
        save_symmetry_type()
    assert config.annotation_dirty[0]
    assert stale_ply.exists()
    assert not (tmp_path / "mesh_sym_type.json").exists()
