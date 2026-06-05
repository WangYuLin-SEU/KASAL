# KASAL + kasalv2 Installation

> **KASALv2 quick path:** Step-by-step source install + demo launch → **[install_kasalv2.md](install_kasalv2.md)** (English) · **[install_kasalv2_zh.md](install_kasalv2_zh.md)** (中文). This file is the full technical reference.

Integrated package layout: **kasalv1** (original KASAL: PyMeshLab + Polyscope) + **kasalv2** rotational symmetry (`kasal/rotational_symmetry/`), which **requires PyTorch3D**.

Dependencies: **4 files** in `requirements/` (`base`, `torch-cpu`, `torch-gpu`, `gui`). Run from **`KASAL/`**.

## Profiles

| Profile | Install | Use case |
|---------|---------|----------|
| Legacy only | `python scripts/install_deps.py base` | No kasalv2 / no torch |
| Headless CPU | `python scripts/install_deps.py headless-cpu` | Server batch |
| Headless GPU | `python scripts/install_deps.py headless-gpu` | GPU batch |
| Full CPU | `python scripts/install_deps.py full-cpu` | Desktop + PyMeshLab |
| Full GPU | `python scripts/install_deps.py full-gpu` | Recommended with NVIDIA GPU |

`torch-cpu` and `torch-gpu` are **mutually exclusive** (pick one per environment).

Equivalent plain pip (full CPU):

```bash
pip install -r requirements/base.txt -r requirements/torch-cpu.txt -r requirements/gui.txt
```

See **`requirements/README.md`** for all profile names.

## Recommended setup (conda)

```bash
conda create -n kasal python=3.10
conda activate kasal
cd KASAL
python scripts/install_deps.py full-cpu    # or full-gpu
```

On machines **without NVIDIA GPU**, use `full-cpu` and set `KASAL_TORCH_DEVICE=cpu`.

### Linux (Ubuntu 20.04+) GUI system packages

Polyscope/GLFW needs OpenGL + X11 (or XWayland). For the desktop GUI also install a folder picker backend and CJK fonts:

```bash
sudo apt update
sudo apt install -y \
  libgl1 libglu1-mesa libx11-6 libxi6 libxrandr2 libxxf86vm1 \
  libxinerama1 libxcursor1 libxkbcommon0 \
  python3-tk zenity fonts-noto-cjk pciutils
```

- **Folder picker**: `zenity` (GNOME) or `kdialog` (KDE) or `python3-tk`
- **Chinese UI**: `fonts-noto-cjk` (or set `KASAL_UI_FONT` to a local `.ttf`/`.ttc`)
- **GPU hint table**: `pciutils` provides `lspci` when `nvidia-smi` is missing

**SSH / no physical display** (optional virtual framebuffer):

```bash
sudo apt install -y xvfb
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
python demo_shape_meshes.py
```

**Wayland note**: taskbar/window icons use GLFW or X11 `_NET_WM_ICON`. On pure Wayland sessions without XWayland, the custom icon may not appear (app still runs).

## PyTorch3D (required for kasalv2)

Official [PyPI](https://pypi.org/project/pytorch3d/) has **no Windows wheels**. Use prebuilt packages from [MiroPsota torch_packages_builder](https://miropsota.github.io/torch_packages_builder):

| Platform | torch | Install pytorch3d tag (Python 3.10) |
|----------|-------|-------------------------------------|
| Windows / Linux CPU | 2.4.1+cpu | `pytorch3d==0.7.8+pt2.4.1cpu` |
| Windows / Linux GPU cu118 | 2.4.1+cu118 | `pytorch3d==0.7.8+pt2.4.1cu118` |

Pinned in `requirements/torch-cpu.txt` and `requirements/torch-gpu.txt`.

Manual install (if you already have matching torch):

```bash
pip install iopath fvcore
pip install --extra-index-url https://miropsota.github.io/torch_packages_builder pytorch3d==0.7.8+pt2.4.1cpu
```

**Do not** `pip install pytorch3d` from PyPI alone on Windows — it will fail or mismatch torch.

### Verify PyTorch3D

```bash
python -c "import torch; from pytorch3d.ops import knn_points; print('torch', torch.__version__, 'ok')"
```

## Full vs Headless

- **Headless** (`headless-cpu` / `headless-gpu`): kasalv2 mesh loading only (`kasalv2_strict`). No Polyscope/PyMeshLab.
- **Full** (`full-cpu` / `full-gpu`): adds `gui.txt` for `kasalv2_adaptive` fallback and `kasalv1` preprocess.

## Chinese UI (polyscope 2.6.1)

The Setup/KASAL **中文** interface loads a CJK font at runtime. Search order: `KASAL_UI_FONT` env → OS font paths → Linux `fc-list :lang=zh`. This requires **`polyscope==2.6.1`** (pinned in `requirements/gui.txt`). If your env still has `polyscope 2.3.x`, Chinese labels render as **square boxes** (`□`) or `????`.

```bash
cd KASAL
conda activate kasal
python -m pip install --upgrade polyscope==2.6.1
# or reinstall the full GUI stack:
python scripts/install_deps.py gui
```

Override the font path:

```bash
# Windows (cmd)
set KASAL_UI_FONT=C:\Windows\Fonts\msyh.ttc

# Linux / macOS (bash)
export KASAL_UI_FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
```

After upgrade, restart the demo (`demo_shape_meshes.py` / `demo_texture_meshes.py`). Console should print `[KASAL] Loaded UI font: ...` when a CJK font is found.

## Environment variables

| Variable | Values | Purpose |
|----------|--------|---------|
| `KASAL_TORCH_DEVICE` | `cpu` \| `cuda` | Force device when CUDA is missing or for CPU-only machines |
| `KASAL_UI_FONT` | path to `.ttf`/`.ttc` | Override CJK UI font (Chinese mode only) |
| `KASAL_SEED` | integer | Optional reproducibility (batch scripts) |

## Verified matrix (fill in locally)

| Python | torch | pytorch3d | CUDA | OS |
|--------|-------|-----------|------|-----|
| 3.10 | 2.4.1+cpu | 0.7.8+pt2.4.1cpu | — | Windows 10 (conda kasal) |
| 3.10 | 2.4.1+cpu | 0.7.8+pt2.4.1cpu | — | Ubuntu 20.04+ (conda kasal) |
| 3.10 | 2.4.1+cu118 | 0.7.8+pt2.4.1cu118 | cu118 | (your GPU machine) |

## Headless job

```bash
cd KASAL
export KASAL_TORCH_DEVICE=cpu   # Windows cmd: set KASAL_TORCH_DEVICE=cpu
python -m kasal.cli.run_job kasal/jobs/example_job.json
```

## GSO regression (kasalv2 standalone scripts)

From repo root `kasalv2/`:

```bash
conda activate kasal
export KASAL_TORCH_DEVICE=cpu   # Windows cmd: set KASAL_TORCH_DEVICE=cpu
python scripts/verify_gso_regression.py --workers 4
python scripts/monitor_gso_progress.py --watch
```

See `revise_kasal.md` for progress monitoring.
