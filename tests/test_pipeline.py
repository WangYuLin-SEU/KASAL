import json
import sys
from types import ModuleType

import pytest

import kasal.config.runtime as config
import kasal.rotational_symmetry.pipeline as pipeline_module
from kasal.device import normalize_device_id, resolve_torch_device
from kasal.rotational_symmetry.pipeline import write_dataset_summary
from kasal.rotational_symmetry import run_dataset


def test_explicit_cpu_preference_is_honored_with_cuda_available(monkeypatch):
    torch = ModuleType("torch")
    torch.cuda = ModuleType("torch.cuda")
    torch.cuda.is_available = lambda: True
    torch.cuda.device_count = lambda: 1
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.delenv("KASAL_TORCH_DEVICE", raising=False)
    monkeypatch.setattr(config, "torch_device_id", "")

    assert resolve_torch_device("cpu") == "cpu"


def test_invalid_explicit_device_is_not_silently_changed_to_cpu(monkeypatch):
    monkeypatch.setenv("KASAL_TORCH_DEVICE", "cdua:0")

    with pytest.raises(ValueError, match="Invalid torch device id"):
        resolve_torch_device("cuda")


def test_invalid_saved_device_is_not_silently_changed_to_cpu(monkeypatch):
    monkeypatch.delenv("KASAL_TORCH_DEVICE", raising=False)
    monkeypatch.setattr(config, "torch_device_id", "cdua:0")

    with pytest.raises(ValueError, match="Invalid torch device id"):
        resolve_torch_device("cuda")


def test_automatic_unavailable_cuda_preference_can_fall_back_to_cpu(monkeypatch):
    torch = ModuleType("torch")
    torch.cuda = ModuleType("torch.cuda")
    torch.cuda.is_available = lambda: False
    monkeypatch.setitem(sys.modules, "torch", torch)

    assert normalize_device_id("cuda") == "cpu"
    with pytest.raises(ValueError, match="unavailable"):
        normalize_device_id("cuda", strict=True)


def test_dataset_cli_writes_results_and_reports_failures(colored_mesh, v2_analysis, monkeypatch, tmp_path):
    torch = ModuleType("torch")
    torch.cuda = ModuleType("torch.cuda")
    torch.cuda.is_available = lambda: True
    torch.cuda.device_count = lambda: 2
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setenv("KASAL_TORCH_DEVICE", "cuda:1")
    mesh_path, _, _ = colored_mesh
    (tmp_path / "bad.ply").write_text("invalid mesh", encoding="utf-8")
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", [
        "run_dataset", "--input-dir", str(tmp_path), "--output-dir", str(output),
        "--workers", "1", "--fps-sample-count", "100", "--tex",
    ])
    assert run_dataset.main() == 1
    cfg = v2_analysis.config
    assert cfg.sampling.fps_sample_count == 100
    assert cfg.axis_search.device == cfg.texture.device == cfg.classification.rotation_loss_device == "cuda:1"
    summary = json.loads((output / "batch_summary.json").read_text(encoding="utf-8"))
    results = {item["object"]: item for item in summary}
    assert results["part.v1"]["success"]
    assert not results["bad"]["success"] and results["bad"]["error"]
    assert results["bad"]["output"] is None and not (output / "bad").exists()
    bop_path = output / "part.v1/part.v1_bop.json"
    bop = json.loads(bop_path.read_text(encoding="utf-8"))
    assert bop["n_fold"] == 4 and bop["diameter"] > 0
    assert "bad" in (output / "batch_summary.csv").read_text(encoding="utf-8-sig")

    # A classifier error must traverse result validation and the batch failure path.
    before = bop_path.read_bytes()
    v2_analysis.raw = {"has_rot_sym": True, "rot_sym_type": "Error", "sym_op": None}
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--pattern", mesh_path.name])
    assert run_dataset.main() == 1
    failure, = json.loads((output / "batch_summary.json").read_text(encoding="utf-8"))
    assert not failure["success"] and failure["output"] is None
    assert "valid family" in failure["error"]
    assert bop_path.read_bytes() == before


def test_csv_summary_preserves_previous_file_on_failure(monkeypatch, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    csv_target = output / "batch_summary.csv"
    json_target = output / "batch_summary.json"
    csv_target.write_text("old summary", encoding="utf-8")
    json_target.write_text('[{"old": true}]', encoding="utf-8")

    class FailingWriter:
        @staticmethod
        def writerow(row):
            raise RuntimeError("simulated CSV write failure")

    monkeypatch.setattr(pipeline_module.csv, "writer", lambda stream: FailingWriter())
    with pytest.raises(RuntimeError, match="simulated CSV write failure"):
        write_dataset_summary(output, [])

    assert csv_target.read_text(encoding="utf-8") == "old summary"
    assert json_target.read_text(encoding="utf-8") == '[{"old": true}]'
    assert not (output / ".batch_summary.csv.tmp").exists()
    assert not (output / ".batch_summary.json.tmp").exists()
