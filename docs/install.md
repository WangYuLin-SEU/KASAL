<div align="center">

**English** | [中文](install_zh.md) · [Project home](../README.md)

</div>

# Install KASALv2 from source

The integrated KASALv2 application is currently distributed from this repository, not from the `kasal-6d` PyPI package. Python 3.10 and conda are recommended.

## Choose a profile

| Profile | Use case |
|---------|----------|
| `full-cpu` | Complete desktop application without CUDA |
| `full-gpu` | Complete desktop application with a compatible NVIDIA GPU |
| `headless-cpu` | Command-line KASALv2 processing on CPU |
| `headless-gpu` | Command-line KASALv2 processing on CUDA |

CPU and GPU torch packages are alternatives; do not install both in one environment. The exact profile composition is listed in [requirements/README.md](../requirements/README.md).

## Install and verify

```bash
git clone https://github.com/WangYuLin-SEU/KASAL.git
cd KASAL
conda create -n kasal python=3.10
conda activate kasal
python scripts/install_deps.py full-cpu
python scripts/verify_pytorch3d.py
```

Use `full-gpu` instead of `full-cpu` only when the machine has a compatible NVIDIA/CUDA environment. A successful verification prints the torch version, confirms a PyTorch3D operation, and reports `cpu` or `cuda`.

## Launch the GUI

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
- **You installed `kasal-6d` from PyPI:** that is the separately released classic kasalv1 package; see the [kasalv1 guide](README_kasalv1.md).
