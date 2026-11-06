"""UI-independent model library and versioned, isolated result storage."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from kasal.annotations.io import SymmetryAnnotationState, parse_symmetry_type_dict, build_symmetry_type_dict
from kasal.utils.io_json import load_json, write_json

SUPPORTED = {'.ply', '.obj', '.stl', '.off', '.glb', '.gltf'}
TYPES = [
    ('None', '无旋转对称', 'No rotational symmetry'),
    ('C(>>1): Spherical Item', '球面对称', 'Spherical'),
    ('C(>1): Cylindrical Item', '圆柱对称', 'Cylindrical'),
    ('C(=1): Circular Item', '圆周对称', 'Circular'),
    ('D(>1): n-fold Prismatic Item', 'n 折棱柱', 'n-fold prismatic'),
    ('D(=1): n-fold Pyramidal Item', 'n 折棱锥', 'n-fold pyramidal'),
    ('P(4): Tetrahedral Item', '四面体对称', 'Tetrahedral'),
    ('P(8): Octahedral Item', '八面体对称', 'Octahedral'),
    ('P(20): Icosahedral Item', '二十面体对称', 'Icosahedral'),
]


def fresh_state() -> SymmetryAnnotationState:
    return SymmetryAnnotationState(compute_engine='kasalv2', sym_type_source='none', n_fold_source='none')


def result_kind(annotation: dict) -> str:
    metadata = annotation.get('studio', {})
    if not isinstance(metadata, dict):
        raise ValueError('Studio annotation metadata must be an object.')
    kind = metadata.get('kind', 'computed')
    if kind not in ('computed', 'manual_annotation'):
        raise ValueError('Unknown Studio annotation kind.')
    return kind


@dataclass
class ModelRecord:
    path: Path
    relative: str
    state: SymmetryAnnotationState = field(default_factory=fresh_state)
    dirty: bool = True
    source: str = 'new'
    error: str = ''
    error_kind: str = ''
    running: bool = False
    elapsed: float | None = None
    edited: bool = False
    draft_saved: bool = False
    result_kind: str = 'computed'
    has_surface: bool | None = None
    baseline: SymmetryAnnotationState | None = None

    @property
    def status(self) -> str:
        if self.running:
            return 'running'
        if self.error:
            return 'error'
        if self.dirty:
            return 'pending'
        return 'saved' if self.source == 'studio' else 'legacy'


class ResultStore:
    """Commit a complete generation by atomically replacing a small pointer.

    Workers only write staging files. A cancelled or failed worker cannot alter
    an existing result. Old sidecars are read-only inputs to Studio.
    """
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.directory = self.root / '.kasal-studio'

    def _inside(self, path: Path) -> Path:
        resolved = path.resolve()
        resolved.relative_to(self.directory.resolve())
        # A symlinked result root must not redirect writes outside the dataset.
        self.directory.resolve().relative_to(self.root)
        return resolved

    def object_dir(self, mesh: Path) -> Path:
        relative = Path(mesh).resolve().relative_to(self.root)
        return self._inside(self.directory / relative)

    def current_dir(self, mesh: Path) -> Path | None:
        directory = self.object_dir(mesh)
        manifest = directory / 'current.json'
        if not manifest.exists():
            return None
        data = load_json(manifest)
        name = data.get('generation') if isinstance(data, dict) else None
        if not isinstance(name, str) or not re.fullmatch(r'result-[0-9a-f]{32}', name):
            raise ValueError('Invalid Studio result generation.')
        target = self._inside(directory / name)
        if not target.is_dir():
            raise ValueError('Studio result generation is missing.')
        return target

    def annotation_path(self, mesh: Path) -> Path | None:
        current = self.current_dir(mesh)
        if current is None:
            return None
        path = current / (mesh.stem + '_sym_type.json')
        if not path.is_file():
            raise ValueError('Studio annotation file is missing from the current result.')
        return path

    def visualization_path(self, mesh: Path) -> Path | None:
        current = self.current_dir(mesh)
        path = (current or mesh.parent) / (mesh.stem + '_sym.ply')
        return path if path.is_file() else None

    def save_draft(self, record: ModelRecord) -> None:
        """Persist edited inputs independently from the last computed geometry."""
        state = deepcopy(record.state)
        state.current_obj_info = {}
        current = self.current_dir(record.path)
        path = self.object_dir(record.path) / 'draft.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, {'base_generation': current.name if current else None,
                          'parameters': build_symmetry_type_dict(state)})
        record.draft_saved = True

    def load(self, record: ModelRecord, *, discard_draft=False) -> None:
        record.error = ''
        record.error_kind = ''
        record.running = False
        record.elapsed = None
        record.edited = False
        record.draft_saved = False
        record.baseline = None
        record.result_kind = 'computed'
        record.state = fresh_state()
        record.source, record.dirty = 'new', True
        try:
            path = self.annotation_path(record.path)
            source = 'studio'
            if path is None:
                # Match the classic app's convention without ever writing there.
                path = record.path.with_name(record.path.stem + '_sym_type.json')
                source = 'legacy'
            if path.exists():
                annotation = load_json(path)
                record.state = parse_symmetry_type_dict(annotation)
                record.result_kind = result_kind(annotation)
                record.baseline = deepcopy(record.state)
                record.source, record.dirty = source, False
            draft_path = self.object_dir(record.path) / 'draft.json'
            if discard_draft:
                draft_path.unlink(missing_ok=True)
            elif draft_path.exists():
                draft = load_json(draft_path)
                current = self.current_dir(record.path)
                # A completed analysis supersedes drafts based on an older generation.
                if draft.get('base_generation') == (current.name if current else None):
                    record.state = parse_symmetry_type_dict(draft['parameters'])
                    record.dirty = record.edited = record.draft_saved = True
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
            record.error = str(exc)
            record.error_kind = 'storage'

    def commit(self, record: ModelRecord, staging: Path) -> None:
        annotation = load_json(staging / 'annotation.json')
        state = parse_symmetry_type_dict(annotation)
        kind = result_kind(annotation)
        ply = staging / 'visualization.ply'
        if kind == 'computed' and state.sym_type != 'None' and not ply.is_file():
            raise ValueError('The computed symmetry visualization is missing.')
        baseline = deepcopy(state)
        directory = self.object_dir(record.path)
        generation = directory / ('result-' + uuid.uuid4().hex)
        generation.mkdir(parents=True)
        # A failed copy leaves an unreferenced generation; the prior pointer survives.
        target = generation / (record.path.stem + '_sym_type.json')
        shutil.copyfile(staging / 'annotation.json', target)
        if kind != 'manual_annotation' and ply.is_file():
            shutil.copyfile(ply, generation / (record.path.stem + '_sym.ply'))
        write_json(directory / 'current.json', {'generation': generation.name})
        record.state = state
        record.baseline = baseline
        record.result_kind = kind
        record.elapsed = None
        record.edited = False
        record.draft_saved = False
        record.source, record.dirty, record.error = 'studio', False, ''
        record.error_kind = ''

    def save_manual(self, record: ModelRecord) -> None:
        """Finish a human annotation without retaining obsolete computed geometry."""
        state = deepcopy(record.state)
        state.compute_engine = 'kasalv1'
        state.sym_type_source = state.n_fold_source = 'user'
        if state.sym_type == 'None':
            state.axis_xyz = 'None'
        state.axis_xyz_source = 'user' if state.axis_xyz != 'None' else 'none'
        state.current_obj_info = {}
        annotation = build_symmetry_type_dict(state)
        # Validate before touching the current result pointer.
        parse_symmetry_type_dict(annotation)
        annotation['studio'] = {'kind': 'manual_annotation'}
        with tempfile.TemporaryDirectory(prefix='studio-label-') as temporary:
            staging = Path(temporary)
            write_json(staging / 'annotation.json', annotation)
            self.commit(record, staging)

    def clear(self, record: ModelRecord) -> None:
        """Move Studio history to its trash, preserving old application files."""
        directory = self.object_dir(record.path)
        if directory.exists():
            trash = self._inside(self.directory / '.trash' / uuid.uuid4().hex)
            trash.parent.mkdir(parents=True, exist_ok=True)
            directory.rename(trash)
        self.load(record)

    def export(self, record: ModelRecord, destination: Path) -> None:
        current = self.current_dir(record.path)
        if current is None:
            raise ValueError('Save a manual annotation or run an analysis before exporting.')
        annotation = current / (record.path.stem + '_sym_type.json')
        if not annotation.is_file():
            raise ValueError('Studio annotation file is missing from the current result.')
        raw = load_json(annotation)
        parse_symmetry_type_dict(raw)
        kind = result_kind(raw)
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        files = [annotation]
        ply = current / (record.path.stem + '_sym.ply')
        if kind != 'manual_annotation' and ply.is_file():
            files.append(ply)
        if any((destination / p.name).exists() for p in files):
            raise FileExistsError('The export folder already contains a result with this name. Choose an empty folder.')
        created = []
        try:
            for path in files:
                target = destination / path.name
                # Exclusive creation also protects files created after preflight.
                with target.open('xb') as output:
                    created.append(target)
                    with path.open('rb') as source:
                        shutil.copyfileobj(source, output)
        except Exception:
            for target in reversed(created):
                target.unlink(missing_ok=True)
            raise


def discover(path: Path) -> tuple[Path, list[ModelRecord]]:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f'Path does not exist: {path}')
    root = path if path.is_dir() else path.parent
    candidates = path.rglob('*') if path.is_dir() else [path]
    paths = sorted((p for p in candidates if p.is_file() and p.suffix.lower() in SUPPORTED
                    and not p.name.lower().endswith('_sym.ply')
                    and not any(part.startswith('.') for part in p.relative_to(root).parts)),
                   key=lambda p: str(p.relative_to(root)).casefold())
    records = [ModelRecord(p, p.relative_to(root).as_posix(), has_surface=ply_surface_hint(p)) for p in paths]
    if not records:
        raise ValueError('No supported meshes found (PLY, OBJ, STL, OFF, GLB, GLTF).')
    store = ResultStore(root)
    for record in records:
        store.load(record)
    return root, records


def job_fields(record: ModelRecord, *, policy: str, device: str, engine: str | None = None) -> dict:
    has_surface = record.has_surface if record.has_surface is not None else ply_surface_hint(record.path)
    if has_surface is False:
        raise ValueError('Point clouds support viewing and manual annotation; analysis requires triangle faces.')
    state = deepcopy(record.state)
    if engine is not None:
        if engine not in ('kasalv1', 'kasalv2'):
            raise ValueError(f'Unknown analysis engine: {engine}')
        state.compute_engine = engine
    manual = state.compute_engine == 'kasalv1'
    if manual and state.sym_type == 'None':
        raise ValueError('Select a concrete symmetry type for known-type analysis.')
    return {
        'mesh_path': str(record.path), 'engine': 'kasalv1' if manual else 'kasalv2',
        'sym_type': state.sym_type if manual else 'None', 'n_fold': state.n_fold,
        'adi_c': state.adi_c, 'tex': state.adi_c,
        'axis_xyz': state.axis_xyz if manual else 'None', 'policy': policy,
        'sym_type_source': 'user' if manual else 'none',
        'n_fold_source': 'user' if manual else 'none', 'exports': [], 'device': device,
    }


def ply_surface_hint(path: Path) -> bool | None:
    """Read only the PLY header to keep unseen point clouds out of mesh jobs."""
    if path.suffix.lower() != '.ply':
        return None
    try:
        with path.open('rb') as stream:
            if stream.readline(128).strip() != b'ply':
                return None
            vertices = faces = 0
            for _ in range(4096):
                line = stream.readline(4096).strip().split()
                if line == [b'end_header']:
                    return faces > 0 if vertices else None
                if len(line) == 3 and line[:2] == [b'element', b'vertex']:
                    vertices = int(line[2])
                if len(line) == 3 and line[:2] == [b'element', b'face']:
                    faces = int(line[2])
    except (OSError, ValueError):
        pass
    return None
