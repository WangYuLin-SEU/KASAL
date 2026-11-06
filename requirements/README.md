# KASAL dependency profiles

[Installation guide](../docs/install.md) · [中文安装指南](../docs/install_zh.md) · [Project home](../README.md)

`scripts/install_deps.py` combines the dependency layers below into named profiles.
The root `requirements.txt` is the plain-pip entry point for `full-cpu`.

| File | Contents |
|------|----------|
| `base.txt` | Core mesh, geometry, sampling, and image dependencies; no torch or GUI |
| `torch-cpu.txt` | CPU PyTorch, torchvision, PyTorch3D, iopath, and fvcore |
| `torch-gpu.txt` | CUDA 11.8 builds of the same torch stack |
| `torch-common.txt` | Shared PyTorch3D index and dependency bounds; included by both torch profiles |
| `gui.txt` | PyMeshLab, Polyscope 2.6.1, OpenCV, and platform GUI helpers |
| `studio.txt` | Optional KASAL Studio window: PySide6 and VTK |
| `test.txt` | Pytest for contributors and CI; install a runtime profile first |

`torch-cpu.txt` and `torch-gpu.txt` are mutually exclusive.

## Profiles

| Profile | Files | Intended use |
|---------|-------|--------------|
| `base` | base | Core/legacy dependencies only |
| `torch-cpu` | torch-cpu | Add only the CPU torch stack |
| `torch-gpu` | torch-gpu | Add only the CUDA torch stack |
| `gui` | gui | Add only desktop dependencies |
| `test` | test | Add only the test runner |
| `headless-cpu`, `cpu` | base + torch-cpu | CPU command-line processing |
| `headless-gpu`, `gpu` | base + torch-gpu | CUDA command-line processing |
| `full-cpu` | base + torch-cpu + gui | Complete CPU desktop application |
| `full-gpu` | base + torch-gpu + gui | Complete CUDA desktop application |

## Install a profile

```bash
python scripts/install_deps.py full-cpu
```

Use `full-gpu` only for a compatible NVIDIA/CUDA environment. A dry run prints the pip command without installing:

```bash
python scripts/install_deps.py full-cpu --dry-run
```

The equivalent plain-pip command is:

```bash
python -m pip install -r requirements.txt
```

After installing a CPU or GPU profile, verify the actual PyTorch3D operator:

```bash
python scripts/verify_pytorch3d.py
```

The regression suite needs only `base.txt` and `test.txt`, matching CI:

```bash
python -m pip install -r requirements/base.txt -r requirements/test.txt
python -m pytest tests -q
```

If a runtime profile is already installed, add only the runner with
`python scripts/install_deps.py test`.

The maintenance suite keeps six headless tests: two public CLI workflows,
STEP-to-axis inference, and three data-loss guards for JSON writes, Studio commits
and exports. The job CLI runs real CPU kasalv1; the dataset test substitutes only
the expensive v2 search and retains real mesh loading and export.

With the algorithm runtime and `requirements/studio.txt` installed, include the
two native desktop workflows (eight tests total; a graphical desktop is required):

```bash
python -m pytest tests --desktop -q
```

These workflows cover real v2/texture workers, batch/cancel/export/clear, and
point-cloud viewing, scalars, orbit, language/draft persistence and manual labeling.
Run only these workflows with `python -m pytest tests/desktop --desktop -q`.
Missing desktop dependencies fail collection when explicitly requested; the
default base-only CI does not import them. Temporary meshes and preferences use
pytest's temporary directories. An optional report can be written with
`--junitxml=.local/studio/test-results.xml`.

Extend these workflows when maintaining the project. Avoid separate unit checks
for behavior they already exercise; keep fault injection only for data-loss risks.
One-off reproductions, exhaustive input variations, legacy GUI substitutes and
detailed rendering checks are intentionally outside the permanent suite.

These tests do not establish classification accuracy across all symmetry families
or exercise every CUDA kernel. Keep `scripts/verify_pytorch3d.py` for installation
diagnosis and the independent CPU/GPU operator smoke check.

## Notes

- KASALv2 requires one torch layer; `base` alone cannot run the automatic engine.
- The desktop GUI requires `gui.txt`.
- Headless profiles omit PyMeshLab, so use `kasalv2_strict` preprocessing.
- Chinese UI requires the pinned `polyscope==2.6.1` and a CJK font. Set `KASAL_UI_FONT` only when automatic font discovery is insufficient.
- Exact pinned torch and PyTorch3D versions are documented in the [installation guide](../docs/install.md#pytorch3d-packages).
