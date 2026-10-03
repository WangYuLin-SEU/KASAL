import json

import numpy as np
import pytest

import kasal.config.runtime as config
from kasal.bop_toolkit_lib import inout
from kasal.annotations.state import dirty_object_ids, load_symmetry_type, mark_object_dirty, saved_object_ids

from kasal.cli import run_job


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"mesh_dir": "meshes", "defaults": {"mesh_preprocess": {"policy": "mystery"}}}, "Unknown mesh preprocessing policy"),
        ([], "job document must be a JSON object"),
        ({"mesh_dir": "meshes", "defaults": []}, "defaults must be a JSON object"),
        (
            {"mesh_dir": "meshes", "meshes": "mesh.ply"},
            "meshes must be a JSON array",
        ),
        (
            {"mesh_dir": "meshes", "defaults": {"engine": "mystery"}},
            "unknown symmetry engine",
        ),
    ],
)
def test_invalid_job_shapes_are_reported(tmp_path, capsys, document, message):
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(document), encoding="utf-8")

    assert run_job.main([str(job_path)]) == 2
    assert message in capsys.readouterr().err


def test_missing_pymeshlab_does_not_override_requested_policy(tmp_path, capsys, monkeypatch):
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "mesh_dir": str(tmp_path),
                "defaults": {"mesh_preprocess": {"policy": "kasalv2_adaptive"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_job, "is_pymeshlab_available", lambda: False)

    assert run_job.main([str(job_path)]) == 2
    stderr = capsys.readouterr().err
    assert "policy=kasalv2_adaptive requires PyMeshLab" in stderr


def test_job_file_to_exports_reload_and_incremental_run(colored_mesh, v2_analysis, tmp_path):
    mesh_path, vertices, _ = colored_mesh
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    job_path = jobs / "job.json"
    document = {"mesh_dir": "..", "defaults": {"engine": "kasalv1", "tex": True}}
    job_path.write_text(json.dumps(document), encoding="utf-8-sig")
    # Unlabeled jobs must ignore GUI labels and select v2 even when v1 is requested.
    config.sym_type_source = config.n_fold_source = "user"
    assert run_job.main([str(job_path)]) == 0
    annotation = tmp_path / "part.v1_sym_type.json"
    visualization = tmp_path / "part.v1_sym.ply"
    saved = json.loads(annotation.read_text(encoding="utf-8"))
    assert saved["n-fold"] == 4 and saved["ADI-C"]
    assert saved["kasal_v2"]["compute_engine"] == "kasalv2"
    assert saved["current_obj_info"]["diameter"] == pytest.approx(np.sqrt(8.))
    exported = inout.load_ply(visualization)
    np.testing.assert_array_equal(exported["pts"][:len(vertices)], vertices)
    assert len(exported["pts"]) > len(vertices)
    assert np.isfinite(exported["pts"]).all()
    assert exported["faces"].max() < len(exported["pts"])
    config.current_mesh_index = 0
    load_symmetry_type()
    assert config.selected_n_fold == 4 and saved_object_ids() == [0]
    config.selected_n_fold = 6
    mark_object_dirty(0)
    assert dirty_object_ids() == [0]
    load_symmetry_type()
    assert config.selected_n_fold == 4 and dirty_object_ids() == []

    before = annotation.read_bytes(), visualization.read_bytes()
    nested = tmp_path / "nested"
    nested.mkdir()
    for name in ("b.ply", "A.PLY"):
        (nested / name).write_bytes(mesh_path.read_bytes())
        (nested / (name[:-4] + "_sym_type.json")).write_bytes(before[0])
    (nested / "skip_sym.PLY").touch()
    v2_analysis.error = AssertionError("saved objects must not be recomputed")
    assert run_job.main([str(job_path)]) == 0
    assert config.mesh_paths == [str(nested / "A.PLY"), str(nested / "b.ply"), str(mesh_path)]
    assert (annotation.read_bytes(), visualization.read_bytes()) == before

    # Explicit empty input overrides even a nonempty discovery directory.
    document["meshes"] = []
    job_path.write_text(json.dumps(document), encoding="utf-8")
    assert run_job.main([str(job_path)]) == 0
    assert config.mesh_paths == []

    document["meshes"] = ["../part.v1.ply"]
    document["defaults"]["only_dirty"] = False
    job_path.write_text(json.dumps(document), encoding="utf-8")
    v2_analysis.error = None
    v2_analysis.raw = {"has_rot_sym": False, "rot_sym_type": "non_rotational", "sym_op": "none"}
    assert run_job.main([str(job_path)]) == 0
    assert not visualization.exists()
    saved = json.loads(annotation.read_text(encoding="utf-8"))
    assert saved["sym_type"] == "None" and not saved["current_obj_info"]["has_rot_sym"]
    load_symmetry_type()
    assert config.selected_symmetry_type == "None" and saved_object_ids() == [0]

    v2_analysis.error = ValueError("analysis failed")
    before = annotation.read_bytes()
    assert run_job.main([str(job_path)]) == 1
    assert annotation.read_bytes() == before


@pytest.mark.parametrize("collision", [False, True])
def test_invalid_dataset_stops_before_computation(tmp_path, capsys, collision):
    directory = tmp_path / "meshes"
    if collision:
        directory.mkdir()
        (directory / "part.ply").touch()
        (directory / "part.obj").touch()
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps({"mesh_dir": "meshes"}), encoding="utf-8")
    assert run_job.main([str(job_path)]) == 1
    assert ("same stem" if collision else "does not exist") in capsys.readouterr().err


def test_axis_override_without_labels_fails_at_cli(tmp_path, capsys):
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps({
        "meshes": ["missing.ply"], "defaults": {"axis_xyz": "axis Z (blue)"},
    }), encoding="utf-8")
    assert run_job.main([str(job_path)]) == 1
    assert "requires symmetry type" in capsys.readouterr().err
    assert not (tmp_path / "missing_sym_type.json").exists()


def test_manual_job_selects_v1_computes_fourfold_symmetry_and_exports(tmp_path):
    import trimesh
    from scipy.spatial import cKDTree
    from kasal.compute.symmetry_job import SymmetryJobSpec, run_symmetry_job

    mesh = trimesh.creation.box(extents=[2., 2., 1.]).subdivide().subdivide()
    mesh_path = tmp_path / "box.ply"
    mesh.export(mesh_path)
    result = run_symmetry_job(SymmetryJobSpec(
        str(mesh_path), engine="kasalv2", sym_type="D(=1): n-fold Pyramidal Item",
        n_fold=4, sym_type_source="user", policy="kasalv2_strict",
    ))
    assert result.success, result.error
    assert result.engine_used == "kasalv1"
    saved = json.loads((tmp_path / "box_sym_type.json").read_text(encoding="utf-8"))
    assert saved["kasal_v2"]["compute_engine"] == "kasalv1" and saved["n-fold"] == 4
    transforms = np.asarray(saved["current_obj_info"]["symmetries_discrete"]).reshape(-1, 4, 4)
    assert len(transforms) == 3
    tree = cKDTree(mesh.vertices)
    for transform in transforms:
        rotation = transform[:3, :3]
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-6)
        assert np.linalg.det(rotation) == pytest.approx(1.)
        transformed = mesh.vertices @ rotation.T + transform[:3, 3]
        assert tree.query(transformed)[0].max() < 0.05
    exported = inout.load_ply(tmp_path / "box_sym.ply")
    assert len(exported["pts"]) > len(mesh.vertices)
    assert np.isfinite(exported["pts"]).all()
