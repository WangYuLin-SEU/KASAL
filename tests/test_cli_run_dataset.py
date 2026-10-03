import sys

import pytest

from kasal.rotational_symmetry import run_dataset


@pytest.mark.parametrize('case', ['empty', 'missing', 'file', 'nonmatching', 'directory_match', 'empty_selection'])
def test_invalid_input_reports_error_without_computation(tmp_path, monkeypatch, capsys, case):
    input_dir = tmp_path / 'meshes'
    output_dir = tmp_path / 'outputs'
    extra_args = []
    if case == 'file':
        input_dir.touch()
    elif case != 'missing':
        input_dir.mkdir()
        if case == 'nonmatching':
            (input_dir / 'notes.txt').touch()
        elif case == 'directory_match':
            (input_dir / 'subfolder.ply').mkdir()
        elif case == 'empty_selection':
            (input_dir / 'mesh.ply').touch()
            extra_args = ['--start', '1']

    def unexpected_batch(*args, **kwargs):
        pytest.fail('Invalid input must stop before computation')

    monkeypatch.setattr(run_dataset, 'run_dataset_batch', unexpected_batch)
    monkeypatch.setattr(sys, 'argv', ['run_dataset', '--input-dir', str(input_dir),
                                    '--output-dir', str(output_dir), *extra_args])
    assert run_dataset.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert '[DATASET] error:' in captured.err
    assert 'Traceback' not in captured.err
    expected = ('does not exist or is not a directory' if case in ('file', 'missing')
                else 'No selected meshes' if case == 'empty_selection' else 'No meshes found')
    assert expected in captured.err
    assert not output_dir.exists()
