"""Three data-loss guards that normal end-to-end workflows cannot induce."""
import shutil

import pytest

from kasal.annotations.io import SymmetryAnnotationState, build_symmetry_type_dict
from kasal.studio.model import ModelRecord, ResultStore
from kasal.utils import io_json


def test_interrupted_json_write_preserves_previous_file(tmp_path, monkeypatch):
    target = tmp_path / 'annotation.json'
    io_json.write_json(target, {'n-fold': 4})
    before = target.read_bytes()

    def fail(value, stream, **kwargs):
        stream.write('{')
        raise OSError('disk full')

    monkeypatch.setattr(io_json.json, 'dump', fail)
    with pytest.raises(OSError, match='disk full'):
        io_json.write_json(target, {'n-fold': 6})
    assert target.read_bytes() == before
    assert list(tmp_path.iterdir()) == [target]


@pytest.fixture
def saved_result(colored_mesh, tmp_path):
    mesh, _, _ = colored_mesh
    store, record = ResultStore(tmp_path), ModelRecord(mesh, mesh.name)
    stage = tmp_path / 'stage'
    stage.mkdir()
    state = SymmetryAnnotationState(sym_type='D(=1): n-fold Pyramidal Item', n_fold=4)
    io_json.write_json(stage / 'annotation.json', build_symmetry_type_dict(state))
    shutil.copyfile(mesh, stage / 'visualization.ply')
    store.commit(record, stage)
    return store, record, stage


def test_interrupted_commit_keeps_previous_generation(saved_result, monkeypatch):
    import kasal.studio.model as model
    store, record, stage = saved_result
    previous = store.current_dir(record.path)
    before = {p.name: p.read_bytes() for p in previous.iterdir()}
    copy = model.shutil.copyfile

    def fail(source, target):
        if source.suffix == '.ply':
            raise OSError('disk full')
        return copy(source, target)

    monkeypatch.setattr(model.shutil, 'copyfile', fail)
    with pytest.raises(OSError, match='disk full'):
        store.commit(record, stage)
    assert store.current_dir(record.path) == previous
    assert {p.name: p.read_bytes() for p in previous.iterdir()} == before
    store.load(record)
    assert record.state.n_fold == 4 and not record.error


def test_export_failure_and_retry_preserve_user_files(saved_result, tmp_path, monkeypatch):
    import kasal.studio.model as model
    store, record, _ = saved_result
    destination = tmp_path / 'exports'
    destination.mkdir()
    keep = destination / 'keep.txt'
    keep.write_bytes(b'user data')

    def fail(source, target, **kwargs):
        target.write(b'partial')
        raise OSError('disk full')

    with monkeypatch.context() as patch:
        patch.setattr(model.shutil, 'copyfileobj', fail)
        with pytest.raises(OSError, match='disk full'):
            store.export(record, destination)
    assert list(destination.iterdir()) == [keep] and keep.read_bytes() == b'user data'
    store.export(record, destination)
    before = {p.name: p.read_bytes() for p in destination.iterdir()}
    with pytest.raises(FileExistsError):
        store.export(record, destination)
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == before
