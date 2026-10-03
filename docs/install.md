<div align="center">

**English** | [中文](install_zh.md) · [Project home](../README.md)

</div>

# Install KASALv2

The integrated application is packaged as `kasal-6d` 2.0.0, continuing the classic 0.1.x releases. It supports Python 3.10 and includes desktop dependencies by default. CPU or CUDA PyTorch/PyTorch3D packages are installed separately. The Python import remains `kasal`, and the command-line entry points remain `kasalv2`, `kasalv2-job`, and `kasalv2-dataset`.

## PyPI release

The integrated **2.0.0** release targets the existing [`kasal-6d` PyPI project](https://pypi.org/project/kasal-6d/). Once published, create a clean Python 3.10 environment, install the matched CPU runtime, and then install the release:

```bash
conda create -n kasalv2 python=3.10
conda activate kasalv2
python -m pip install -r https://raw.githubusercontent.com/WangYuLin-SEU/KASAL/fa5f567a0aa7be862d00d5578f4a55a10449a6b1/requirements/torch-cpu.txt
python -m pip install --index-url https://pypi.org/simple/ kasal-6d==2.0.0
python -m pip check
python -c "import torch; from pytorch3d.ops import knn_points; x = torch.zeros(1, 4, 3); knn_points(x, x, K=1); print('OK torch', torch.__version__, '| PyTorch3D CPU operation')"
kasalv2 --help
```

For a compatible NVIDIA/CUDA machine, replace `torch-cpu.txt` with `torch-gpu.txt` in a fresh environment. Do not replace PyTorch3D or mix CPU and CUDA builds. Windows CPU installation has been validated. CUDA and Linux users should use the matching profiles below and report environment-specific issues through the project issue tracker.

The earlier standalone `kasalv2` 2.0.0 PyPI release and its `2.0.0rc1` TestPyPI build remain historical releases. Future updates use `kasal-6d`.

### Upgrade an existing installation

For classic `kasal-6d` 0.1.x users, first prepare a Python 3.10 environment with the matched PyTorch/PyTorch3D runtime above, then upgrade after publication:

```bash
python -m pip install --upgrade "kasal-6d==2.0.0"
```

If the same environment contains the standalone `kasalv2` package, remove it before installing `kasal-6d`, because both distributions own the `kasal` import directory:

```bash
python -m pip uninstall kasalv2
python -m pip install --upgrade "kasal-6d==2.0.0"
```

The old `kasal-6d[recommended]` extra remains accepted; its desktop dependencies are included by default in 2.0.0. The historical 0.1.x releases use Apache-2.0; the integrated 2.0.0 release uses the repository's [PolyForm Noncommercial license](../LICENSE) and retains third-party license notices. To keep the original classic application, pin `kasal-6d==0.1.4` in a separate environment.

Open a writable folder containing your meshes:

```bash
kasalv2 "PATH_TO_YOUR_MESH_DIRECTORY"
```

To try bundled geometry examples, copy them into a new working folder first so that annotations are written outside the installed package:

```bash
python -c "import shutil; from kasal.datasets.paths import shape_mesh_path; shutil.copytree(shape_mesh_path, 'kasalv2-demo')"
kasalv2 kasalv2-demo
```

For texture examples, use `texture_mesh_path` instead of `shape_mesh_path` and a new destination folder. Installed command-line entry points are also available:

```bash
kasalv2-job path/to/job.json
kasalv2-dataset --input-dir INPUT --output-dir OUTPUT
```

The job file uses the same format as [the source example](../kasal/jobs/example_job.json); mesh paths are relative to the job file. The package includes GUI dependencies even when using these command-line tools. To omit GUI dependencies, use a source headless profile below.

## Install from source

Future PyPI releases will provide wheels only. To obtain the source code, clone the GitHub repository using the command below.

Python 3.10 and conda are recommended. The following profiles install dependencies for running directly from the checkout.

### Choose a profile

| Profile | Use case |
|---------|----------|
| `full-cpu` | Complete desktop application without CUDA |
| `full-gpu` | Complete desktop application with a compatible NVIDIA GPU |
| `headless-cpu` | Command-line KASALv2 processing on CPU |
| `headless-gpu` | Command-line KASALv2 processing on CUDA |

CPU and GPU torch packages are alternatives; do not install both in one environment. The exact profile composition is listed in [requirements/README.md](../requirements/README.md).

### Install and verify

```bash
git clone https://github.com/WangYuLin-SEU/KASAL.git
cd KASAL
conda create -n kasal python=3.10
conda activate kasal
python scripts/install_deps.py full-cpu
python scripts/verify_pytorch3d.py
```

Use `full-gpu` instead of `full-cpu` only when the machine has a compatible NVIDIA/CUDA environment. A successful verification prints the torch version, confirms a PyTorch3D operation, and reports `cpu` or `cuda`.

### Launch the GUI from source

```bash
python demo_shape_meshes.py
```

For the bundled textured example:

```bash
python demo_texture_meshes.py
```

Both commands open the same **Setup → KASAL** interface with different initial data folders. The [project README](../README.md#usage-essentials) summarizes the normal workflow.

## First run

1. On **Setup**, choose the interface language, dataset folder, preprocessing policy, and compute device.
2. Click **Confirm**. KASAL saves these dataset-level settings to `KASAL.json` in the selected folder, then opens the main panel.
3. Keep the current-object engine on `kasalv2` for automatic analysis. Use **Cal Current** for one object.
4. **Cal All (unsaved)** processes only objects without a saved result or objects edited since loading. Completed objects write `{stem}_sym_type.json` and, when applicable, `{stem}_sym.ply`.

Returning to Setup changes configuration without deleting existing annotation sidecars.

## Headless use

Install `headless-cpu` or `headless-gpu`, then run:

```bash
python -m kasal.cli.run_job kasal/jobs/example_job.json
```

Headless profiles omit Polyscope and PyMeshLab. Use the `kasalv2_strict` preprocessing policy, which can prepare meshes for either engine. The desktop interface and PyMeshLab preprocessing (`kasalv1` or adaptive fallback) require a full profile.

## PyTorch3D packages

The checked-in requirements pin matching torch 2.4.1, torchvision 0.19.1, and PyTorch3D 0.7.8 builds for CPU or CUDA 11.8. PyTorch3D is installed from the [MiroPsota package index](https://miropsota.github.io/torch_packages_builder/), because PyPI does not provide the required Windows wheel.

Prefer the repository profiles over installing `pytorch3d` independently. If verification fails, create a clean Python 3.10 environment and install one complete CPU or GPU profile.

## Linux desktop packages

Ubuntu 20.04+ needs OpenGL/X11 libraries, a folder picker, and a CJK font for Chinese UI:

```bash
sudo apt update
sudo apt install -y \
  libgl1 libglu1-mesa libx11-6 libxi6 libxrandr2 libxxf86vm1 \
  libxinerama1 libxcursor1 libxkbcommon0 \
  python3-tk zenity fonts-noto-cjk pciutils
```

KDE users may install `kdialog` instead of `zenity`.

## Chinese interface

The Chinese UI requires `polyscope==2.6.1`, already pinned in the GUI profile, and a CJK font. If automatic font discovery is insufficient, set `KASAL_UI_FONT` to a local `.ttf` or `.ttc` file before launching the application.

Example for Windows PowerShell:

```powershell
$env:KASAL_UI_FONT = "C:\Windows\Fonts\msyh.ttc"
```

## Device override

Normally, select the device on the Setup page. For a shell-only override:

```powershell
# Windows PowerShell
$env:KASAL_TORCH_DEVICE = "cpu"
```

```bat
:: Windows cmd
set KASAL_TORCH_DEVICE=cpu
```

```bash
# Linux
export KASAL_TORCH_DEVICE=cpu
```

The environment override takes precedence over the saved GUI choice. An invalid or unavailable explicitly selected device raises an error; only automatic device selection can fall back to CPU.

## Common problems

- **GPU is detected but cannot be selected:** the active PyTorch build is CPU-only; install `full-gpu` in a clean environment.
- **Chinese labels appear as boxes:** verify `polyscope==2.6.1` and install or select a CJK font.
- **Mesh preprocessing fails:** try `kasalv2_adaptive` in a full installation, or check that the mesh has valid geometry.
- **A GUI folder appears empty:** folder discovery includes `.ply` and `.obj` files case-insensitively and excludes generated `*_sym.ply` files.
- **Only the classic application is available:** check `python -m pip show kasal-6d`. Versions 0.1.x contain the original kasalv1 application; 2.0.0 integrates kasalv1 and KASALv2. See the [kasalv1 guide](README_kasalv1.md) for the manual workflow.
