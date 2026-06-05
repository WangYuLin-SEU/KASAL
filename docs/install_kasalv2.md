<div align="center">

**English** | [中文](./install_kasalv2_zh.md)

</div>

# KASALv2 — Install from Source

This guide covers **installing KASALv2 from the GitHub source tree** and **launching the integrated desktop GUI**. PyPI packages for the integrated **KASALv2** release are not yet available — use this workflow for now.

> **kasalv1 (classic):** The same GUI also supports the original manual-labeling pipeline. For PyPI-only kasalv1 install and classic usage, see [README_kasalv1.md](README_kasalv1.md). This document focuses on **KASALv2 source install**.

### What you need

| Item | Notes |
|------|--------|
| **Python** | 3.10 (conda recommended) |
| **Repo** | Clone [KASAL](https://github.com/WangYuLin-SEU/KASAL); work inside the `KASAL/` folder |
| **Profile** | **`full-cpu`** or **`full-gpu`** for the desktop GUI + kasalv2 |

### Requirements (4 files)

Dependencies live in `KASAL/requirements/`. Profiles are **combinations** of these files (installed via `scripts/install_deps.py`):

| File | Contents |
|------|----------|
| [`base.txt`](../requirements/base.txt) | Core mesh/geometry stack (trimesh, open3d, fpsample, …) — no PyTorch, no GUI |
| [`torch-cpu.txt`](../requirements/torch-cpu.txt) | CPU PyTorch + **PyTorch3D** (required for kasalv2) |
| [`torch-gpu.txt`](../requirements/torch-gpu.txt) | CUDA PyTorch + PyTorch3D (cu118) |
| [`gui.txt`](../requirements/gui.txt) | Polyscope **2.6.1**, PyMeshLab, OpenCV — desktop GUI |

`torch-cpu` and `torch-gpu` are **mutually exclusive** — pick one per environment.

| Profile | Layers | Use case |
|---------|--------|----------|
| **`full-cpu`** | base + torch-cpu + gui | **Desktop, no NVIDIA GPU** |
| **`full-gpu`** | base + torch-gpu + gui | **Desktop with NVIDIA GPU** (recommended if available) |
| `headless-cpu` / `headless-gpu` | base + torch only | Batch/server without GUI |

Full profile reference: [requirements/README.md](../requirements/README.md).

### Step 1 — Create environment & install

```bash
conda create -n kasal python=3.10
conda activate kasal
cd KASAL
python scripts/install_deps.py full-cpu    # or: full-gpu
```

Plain pip equivalent (full CPU):

```bash
pip install -r requirements/base.txt -r requirements/torch-cpu.txt -r requirements/gui.txt
```

**PyTorch3D on Windows:** do not `pip install pytorch3d` from PyPI alone — use the pinned wheels in `torch-cpu.txt` / `torch-gpu.txt` (MiroPsota index). Details: [install.md — PyTorch3D](install.md#pytorch3d-required-for-kasalv2).

### Step 2 — Verify kasalv2 stack

```bash
python scripts/verify_pytorch3d.py
```

Expected output: `OK torch … | pytorch3d import | device cpu` (or `cuda`).

### Step 3 — Launch the GUI (demo)

**Shape meshes** (bundled sample dataset):

```bash
python demo_shape_meshes.py
```

**Texture meshes** (ADI-C / textured symmetry):

```bash
python demo_texture_meshes.py
```

Both demos open the same **Setup → KASAL** GUI. The only difference is the default sample folder (`kasal/datasets/shape_meshes` vs `texture_meshes`).

### Step 4 — First-run workflow

1. **Setup** page — pick **Interface language**, **dataset folder**, **mesh preprocess** (`kasalv2_adaptive` recommended), and **compute device**.
2. Click yellow **Confirm** → settings saved to `KASAL.json` → enter **KASAL** main panel.
3. Select object(s) in the list; set **Cal Current** engine to **`kasalv2`** for automatic symmetry.
4. Use **Cal Current** for one object or **Cal All (unsaved)** for batch — outputs: `{stem}_sym_type.json`, `{stem}_sym.ply`.

Screenshots and feature details: [README.md](../README.md).

### CPU-only machines

If you installed `full-cpu` or have no CUDA:

```bash
# Linux / macOS
export KASAL_TORCH_DEVICE=cpu

# Windows (cmd)
set KASAL_TORCH_DEVICE=cpu

python demo_shape_meshes.py
```

### Chinese UI

**中文** interface needs `polyscope==2.6.1` (included in `gui.txt`). On Linux, install CJK fonts (`fonts-noto-cjk`) or set `KASAL_UI_FONT`. See [install.md — Chinese UI](install.md#chinese-ui-polyscope-261).

### Linux GUI system packages

Polyscope/GLFW needs OpenGL + X11; folder picker needs `zenity`/`kdialog` or `python3-tk`:

```bash
sudo apt install -y libgl1 libglu1-mesa libx11-6 libxi6 libxrandr2 \
  libxxf86vm1 libxinerama1 libxcursor1 libxkbcommon0 \
  python3-tk zenity fonts-noto-cjk pciutils
```

Full list: [install.md — Linux](install.md#linux-ubuntu-2004-gui-system-packages).

### Optional environment variables

| Variable | Purpose |
|----------|---------|
| `KASAL_TORCH_DEVICE` | `cpu` \| `cuda` — force device |
| `KASAL_UI_FONT` | Path to `.ttf`/`.ttc` for Chinese UI |
| `KASAL_SEED` | Optional reproducibility |

### Troubleshooting

- Install issues, headless jobs, verified version matrix → [install.md](install.md)
- Classic kasalv1 manual labeling, PyPI `pip install kasal-6d` → [README_kasalv1.md](README_kasalv1.md)
