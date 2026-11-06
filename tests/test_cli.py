"""Public CLI workflows; v1 is real, only the batch v2 search is substituted."""
import json
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from kasal.bop_toolkit_lib import inout
from kasal.cli import run_job
from kasal.rotational_symmetry import run_dataset


def test_job_computes_exports_and_skips_saved_models(tmp_path, capsys):
    mesh = trimesh.creation.box(extents=[2., 2., 1.]).subdivide().subdivide()
    mesh.export(tmp_path / 'box.ply')
    job = tmp_path / 'job.json'
    job.write_text(json.dumps({'mesh_dir': '.', 'defaults': {
        'engine': 'kasalv1', 'sym_type': 'D(=1): n-fold Pyramidal Item', 'n_fold': 4,
    }}), encoding='utf-8')
    assert run_job.main([str(job)]) == 0
    annotation, visualization = tmp_path / 'box_sym_type.json', tmp_path / 'box_sym.ply'
    saved = json.loads(annotation.read_text(encoding='utf-8'))
    assert saved['kasal_v2']['compute_engine'] == 'kasalv1' and saved['n-fold'] == 4
    transforms = np.asarray(saved['current_obj_info']['symmetries_discrete']).reshape(-1, 4, 4)
    assert len(transforms) == 3
    tree = cKDTree(mesh.vertices)
    for transform in transforms:
        transformed = mesh.vertices @ transform[:3, :3].T + transform[:3, 3]
        assert tree.query(transformed)[0].max() < .05
    exported = inout.load_ply(visualization)
    assert len(exported['pts']) > len(mesh.vertices) and np.isfinite(exported['pts']).all()

    before = annotation.read_bytes(), visualization.read_bytes()
    capsys.readouterr()
    assert run_job.main([str(job)]) == 0
    assert 'Done: 0 ok, 0 failed' in capsys.readouterr().out
    assert (annotation.read_bytes(), visualization.read_bytes()) == before
    # A damaged existing label must be reported rather than overwritten on a rerun.
    annotation.write_text('{', encoding='utf-8')
    assert run_job.main([str(job)]) == 1
    assert annotation.read_bytes() == b'{' and visualization.read_bytes() == before[1]


def test_dataset_exports_successes_and_reports_failures(colored_mesh, v2_analysis, tmp_path, monkeypatch):
    (tmp_path / 'bad.ply').write_text('invalid mesh', encoding='utf-8')
    output = tmp_path / 'output'
    monkeypatch.setattr(sys, 'argv', [
        'run_dataset', '--input-dir', str(tmp_path), '--output-dir', str(output),
        '--workers', '1', '--tex',
    ])
    assert run_dataset.main() == 1
    summary = json.loads((output / 'batch_summary.json').read_text(encoding='utf-8'))
    results = {item['object']: item for item in summary}
    assert results['part.v1']['success']
    assert not results['bad']['success'] and results['bad']['error']
    assert results['bad']['output'] is None and not (output / 'bad').exists()
    bop = json.loads((output / 'part.v1/part.v1_bop.json').read_text(encoding='utf-8'))
    assert bop['n_fold'] == 2 and bop['diameter'] > 0 and bop['rot_sym_axis']
    assert 'bad' in (output / 'batch_summary.csv').read_text(encoding='utf-8-sig')
