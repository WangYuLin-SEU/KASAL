import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from kasal.rotational_symmetry.output_schema import build_analysis_result, build_model_output_json
from kasal.utils.io_json import write_json


def test_non_rotational_analysis_exports_empty_axes(monkeypatch, tmp_path):
    # The classifier is replaced below; its unused search dependencies need no runtime.
    def unused_search(*args, **kwargs):
        raise AssertionError("Non-rotational result assembly must not run axis search")

    for name, functions in {
        "axis_search": ["search_primary_axis", "search_secondary_axis_at_angle"],
        "consistency": ["geom_pi_axis_consistency_ok"],
        "geometry": ["compute_axis_rotation_loss", "generate_symmetry_transforms",
                     "get_template_axis_angle", "normalize_vector"],
        "periodicity": ["estimate_axis_periodicity"],
    }.items():
        module = ModuleType(f"kasal.rotational_symmetry.{name}")
        for function in functions:
            setattr(module, function, unused_search)
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setitem(sys.modules, "torch", None)

    # Load the real analyzer separately so temporary dependency stubs cannot leak.
    source = Path(__file__).resolve().parents[1] / "kasal/rotational_symmetry/analyzer.py"
    spec = importlib.util.spec_from_file_location("kasal.rotational_symmetry._test_analyzer", source)
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)

    center = [1.0, 2.0, 3.0]
    monkeypatch.setattr(
        analyzer, "classify_rotational_symmetry_family",
        lambda *args, **kwargs: (False, "non_rotational", 0, None, None, center, None),
    )
    raw, fold = analyzer.analyze_rotational_symmetry(
        {"analysis_points": [], "rotation_center": center}, tex=True,
    )
    analysis = build_analysis_result(raw, fold)
    target = tmp_path / "asymmetric_bop.json"
    write_json(target, build_model_output_json(analysis, {"diameter": 5.0}))

    def reject_constant(value):
        raise ValueError(value)

    result = json.loads(target.read_text(encoding="utf-8"), parse_constant=reject_constant)
    assert result["has_rot_sym"] is False
    assert result["rot_sym_type"] == "non_rotational"
    assert result["n_fold"] == 0
    assert result["rot_sym_axis"] == []
    assert result["rot_center"] == center
    assert result["texture_symmetry"]["rot_sym_axis"] == []
    assert "symmetries_discrete" not in result
    assert "symmetries_continuous" not in result


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_json_rejects_nonfinite_values_without_overwriting(value, tmp_path):
    target = tmp_path / "result.json"
    write_json(target, {"n_fold": "inf", "rot_sym_axis": [[0, 0, 1]]})
    before = target.read_bytes()

    with pytest.raises(ValueError):
        write_json(target, {"rot_sym_axis": [[value, 0, 1]]})

    assert target.read_bytes() == before
    assert list(tmp_path.iterdir()) == [target]
