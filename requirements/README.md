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

The suite prioritizes file-to-result workflows: a real CPU kasalv1 job, CLI and
dataset exports, annotation reload/edit/save, and STEP parsing through axis
inference. The v2 workflow tests replace only the expensive symmetry search;
mesh preprocessing and JSON/PLY output use the real implementations. GUI tests
replace native window libraries and worker processes. Format rejection, device
selection and failed writes retain small boundary checks where a successful
workflow cannot establish the contract.

Run individual files for affected areas, for example
`python -m pytest tests/test_cli_run_job.py tests/test_annotation_state.py -q`.
The default suite does not validate full v2 classification accuracy, CUDA kernels,
or interactive window rendering. Use `scripts/verify_pytorch3d.py` in the selected
CPU/GPU environment for the real operator smoke check.

## Notes

- KASALv2 requires one torch layer; `base` alone cannot run the automatic engine.
- The desktop GUI requires `gui.txt`.
- Headless profiles omit PyMeshLab, so use `kasalv2_strict` preprocessing.
- Chinese UI requires the pinned `polyscope==2.6.1` and a CJK font. Set `KASAL_UI_FONT` only when automatic font discovery is insufficient.
- Exact pinned torch and PyTorch3D versions are documented in the [installation guide](../docs/install.md#pytorch3d-packages).
