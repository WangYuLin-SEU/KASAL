"""Two maintenance workflows: automatic analysis and manual point-cloud labeling."""
import json
from pathlib import Path
import shutil

import numpy as np
import trimesh
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QMessageBox
from scipy.spatial.transform import Rotation
from vtkmodules.util.numpy_support import vtk_to_numpy

from kasal.annotations.io import SymmetryAnnotationState, build_symmetry_type_dict
from kasal.bop_toolkit_lib import inout
from kasal.utils.io_json import write_json


def test_analyze_batch_cancel_export_and_clear(desktop, tmp_path):
    ui = desktop
    root = Path(__file__).resolve().parents[2]
    models = tmp_path / '模型库'
    shutil.copytree(root / 'kasal/datasets/shape_meshes', models)
    sources = sorted(p for p in models.glob('*.ply') if not p.stem.endswith('_sym'))
    original = {p: p.read_bytes() for p in sources}
    first = sources[0]
    legacy = first.with_name(first.stem + '_sym_type.json')
    write_json(legacy, build_symmetry_type_dict(SymmetryAnnotationState()))
    old_label = legacy.read_bytes()
    w = ui.open(models)
    w.analyze_button.click()
    ui.wait(lambda: not w.runner.busy)
    assert w.runner.successes == 1, w.current.error
    assert w.current.baseline.compute_engine == 'kasalv2'
    assert w.view.symmetry_actors and w.view.result_meshes
    generation = w.store.current_dir(first)
    w.display_source.setCurrentIndex(w.display_source.findData('result'))
    assert w.view.result_meshes[0][0].GetVisibility()
    # The display removes baked arrow geometry; the exported result remains intact.
    actor = w.view.result_meshes[0][0]
    actor.GetMapper().Update()
    source_mesh = trimesh.load(first, process=False)
    assert actor.GetMapper().GetInput().GetNumberOfCells() == len(source_mesh.faces)
    # The icosahedron has 59 stored rotations plus identity: all 60 regions exist.
    saved_colors = inout.load_ply(generation / (first.stem + '_sym.ply'))['colors'][:len(source_mesh.vertices)]
    shown_colors = vtk_to_numpy(actor.GetMapper().GetInput().GetPointData().GetScalars())
    assert len(np.unique(saved_colors, axis=0)) == len(np.unique(shown_colors, axis=0)) == 60
    w.show_axes.setChecked(False)
    assert all(not a.GetVisibility() for a in w.view.symmetry_actors + w.view.symmetry_outlines)
    w.show_axes.setChecked(True)
    assert all(a.GetVisibility() for a in w.view.symmetry_actors + w.view.symmetry_outlines)
    ui.export(tmp_path / 'exports')
    for name in (first.stem + '_sym_type.json', first.stem + '_sym.ply'):
        assert (tmp_path / 'exports' / name).read_bytes() == (generation / name).read_bytes()

    w.analyze_current()
    assert w.runner.busy
    w.cancel_jobs()
    ui.wait(lambda: not w.runner.busy)
    assert w.store.current_dir(first) == generation
    w.analyze_batch()
    ui.wait(lambda: not w.runner.busy)
    assert w.runner.total == len(sources) - 1 and w.runner.failures == 0

    def confirm(dialog):
        dialog.button(QMessageBox.StandardButton.Yes).click()
    ui.modal(w.clear_results, confirm)
    assert all(w.store.current_dir(p) is None for p in sources)
    assert list((w.store.directory / '.trash').glob('*/current.json'))
    assert legacy.read_bytes() == old_label
    assert all(p.read_bytes() == data for p, data in original.items())

    # Repair old PLY colors in the view, including the highest supported order.
    high_order = tmp_path / 'prism.ply'
    cylinder = trimesh.creation.cylinder(radius=1, height=2, sections=360)
    cylinder.export(high_order)
    old_ply = tmp_path / 'prism_sym.ply'
    cylinder.export(old_ply)
    old_bytes = old_ply.read_bytes()
    rotations = Rotation.create_group('D90').as_matrix()
    rotations = rotations[~np.all(np.isclose(rotations, np.eye(3)), axis=(1, 2))]
    transforms = np.tile(np.eye(4), (len(rotations), 1, 1))
    transforms[:, :3, :3] = rotations
    write_json(tmp_path / 'prism_sym_type.json', build_symmetry_type_dict(SymmetryAnnotationState(
        sym_type='D(>1): n-fold Prismatic Item', n_fold=90, current_obj_info={
            'rot_sym_axis': [[0, 0, 1]], 'rot_center': [0, 0, 0],
            'symmetries_discrete': transforms.reshape(-1, 16).tolist(),
        })))
    colors = []
    for _ in range(2):
        np.random.random(7)  # Reopening must not depend on the global RNG state.
        w.open_path(high_order)
        w.display_source.setCurrentIndex(w.display_source.findData('result'))
        mapper = w.view.result_meshes[0][0].GetMapper()
        mapper.Update()
        colors.append(vtk_to_numpy(mapper.GetInput().GetPointData().GetScalars()).copy())
    assert len(np.unique(colors[0], axis=0)) == 180
    assert np.array_equal(*colors) and old_ply.read_bytes() == old_bytes

    textured = tmp_path / 'texture'
    shutil.copytree(root / 'kasal/datasets/texture_meshes', textured)
    w.open_path(textured)
    assert any(texture is not None for _, texture in w.view.meshes)
    w.texture.setChecked(True)
    w.analyze_current()
    ui.wait(lambda: not w.runner.busy)
    assert w.runner.successes == 1, w.current.error
    assert 'texture_symmetry' in w.current.baseline.current_obj_info


def test_view_edit_reopen_and_export_point_cloud(desktop, tmp_path):
    ui = desktop
    points = trimesh.creation.icosphere(subdivisions=1).vertices
    cloud = tmp_path / 'cloud.ply'
    cloud.write_text(
        f'ply\nformat ascii 1.0\nelement vertex {len(points)}\n'
        'property float x\nproperty float y\nproperty float z\nproperty float intensity\nend_header\n'
        + ''.join(f'{x} {y} {z} {z}\n' for x, y, z in points), encoding='ascii')
    original = cloud.read_bytes()
    w = ui.open(cloud)
    assert w.view.parts[0].point_cloud and not w.analyze_button.isEnabled()
    w.open_display_controls()
    w.display_panel.scalar.setCurrentIndex(w.display_panel.scalar.findData('point:intensity'))
    assert w.view.scalar_range() == (-1., 1.) and w.view.scalar_bar.GetVisibility()

    # Exercise the actual mouse event path once; avoid maintaining a navigation matrix.
    before = ui.camera()
    a = QPointF(w.view.width() * .5, w.view.height() * .5)
    b = a + QPointF(65, 35)
    for kind, pos, button, held in (
        (QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseMove, b, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseButtonRelease, b, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton),
    ):
        ui.app.sendEvent(w.view, QMouseEvent(kind, pos, pos, button, held, Qt.KeyboardModifier.NoModifier))
    assert not np.allclose(ui.camera()[:3], before[:3])
    w.sym_type.setCurrentIndex(w.sym_type.findData('D(=1): n-fold Pyramidal Item'))
    w.fold.setValue(7)
    before = ui.camera()
    w.language_combo.setCurrentIndex(w.language_combo.findData('en'))
    assert w.analyze_button.text() == 'Analyze model' and ui.camera() == before
    assert w.view.scalar_key == ('point', 'intensity') and w.current.draft_saved

    ui.close()
    w = ui.open(cloud)
    assert w.language == 'en' and w.current.state.n_fold == 7 and w.current.edited
    w.save_label_button.click()
    assert w.current.result_kind == 'manual_annotation' and not w.current.dirty
    assert w.runner.process is None
    ui.export(tmp_path / 'labels')
    annotation = json.loads((tmp_path / 'labels/cloud_sym_type.json').read_text(encoding='utf-8'))
    assert annotation['n-fold'] == 7 and annotation['current_obj_info'] == {}
    assert len(list((tmp_path / 'labels').iterdir())) == 1
    w.open_path(cloud)
    assert not w.current.edited and w.current.result_kind == 'manual_annotation'
    assert cloud.read_bytes() == original
