"""One isolated analysis process. Never writes to source mesh sidecars."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback


def emit(kind: str, **payload) -> None:
    print('@STUDIO ' + json.dumps({'kind': kind, **payload}, ensure_ascii=True), flush=True)


class ProgressSink:
    def put_nowait(self, message):
        if message[0] == 'progress':
            emit('progress', **message[1])


def calculate(request: dict, output: Path) -> None:
    import numpy as np
    from kasal.annotations.io import SymmetryAnnotationState, build_symmetry_type_dict
    from kasal.compute.symmetry_job import SymmetryJobSpec, run_symmetry_job
    from kasal.utils.compute_progress import set_progress_ipc_queue, get_compute_progress
    from kasal.utils.io_json import write_json
    from kasal.utils.io_ply import save_ply_model
    from kasal.utils.mesh_preprocess import load_mesh_for_analysis
    from kasal.viz.symmetry_visual_export import build_symmetry_visualization_model

    request = dict(request)
    os.environ['KASAL_TORCH_DEVICE'] = request.pop('device', 'cpu')
    # Enforce this boundary even if a malformed caller requested legacy exports.
    request['exports'] = []
    job = SymmetryJobSpec(**request)
    output.mkdir(parents=True, exist_ok=True)
    set_progress_ipc_queue(ProgressSink())
    get_compute_progress().begin_object(Path(job.mesh_path).name, engine=job.engine)
    started = time.monotonic()
    result = run_symmetry_job(job)
    if not result.success:
        raise RuntimeError(result.error or 'Analysis failed')
    info = result.current_obj_info
    # The v2 classifier uses an internal alias which the classic UI does not
    # recognize. Keep the analysis payload, but use the schema's spherical label.
    if info.get('has_rot_sym') and info.get('rot_sym_type') == 'spherical':
        result.sym_type = 'C(>>1): Spherical Item'
    if result.sym_type != 'None':
        if result.engine_used == 'kasalv1':
            viz = info
        else:
            bundle = load_mesh_for_analysis(job.mesh_path, need_colors=job.tex, policy=job.policy)
            viz = build_symmetry_visualization_model(bundle.kasalv1_model, info, result.sym_type)
        exported = save_ply_model(viz, str(output / 'visualization.ply'), arrow_ratio=1.0, save_twofold_axis=True)
        if result.engine_used == 'kasalv1':
            info = {**exported, 'has_rot_sym': True, 'rot_sym_type': result.sym_type,
                    'n_fold': result.n_fold,
                    'rot_sym_axis': np.asarray(viz.get('axis', [])).tolist(),
                    'rot_center': np.asarray(viz.get('center_ch', [0, 0, 0])).tolist()}
    state = SymmetryAnnotationState(
        sym_type=result.sym_type, n_fold=result.n_fold, adi_c=job.adi_c,
        axis_xyz=job.axis_xyz, current_obj_info=info, compute_engine=result.engine_used,
        sym_type_source='user' if result.engine_used == 'kasalv1' else 'kasalv2_auto',
        n_fold_source='user' if result.engine_used == 'kasalv1' else 'kasalv2_auto',
        axis_xyz_source='user' if job.axis_xyz != 'None' else 'none',
    )
    write_json(output / 'annotation.json', build_symmetry_type_dict(state))
    emit('done', elapsed=time.monotonic() - started)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        calculate(json.loads(args.request.read_text(encoding='utf-8')), args.output)
        return 0
    except Exception as exc:
        emit('error', message=str(exc))
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
