# KASAL dependencies

**4 files** — profiles are combinations, not duplicate txt files:

| File | Contents |
|------|----------|
| `base.txt` | Core (trimesh, open3d, fpsample, …) — no torch, no GUI |
| `torch-cpu.txt` | CPU torch + pytorch3d |
| `torch-gpu.txt` | GPU torch + pytorch3d (cu118) |
| `gui.txt` | PyMeshLab + Polyscope **2.6.1** + opencv (add-on; **2.6.1+** for Chinese UI) |

`torch-cpu` and `torch-gpu` are **mutually exclusive** per environment.

## Install (recommended)

```powershell
cd KASAL
conda activate kasal
python scripts/install_deps.py full-cpu
```

## Profiles

| Profile | Layers | Use case |
|---------|--------|----------|
| `base` | base | Legacy only, no kasalv2 |
| `torch-cpu` / `torch-gpu` | torch | Add torch stack only |
| `gui` | gui | Add GUI to existing env |
| `headless-cpu` / `cpu` | base + torch-cpu | Server / batch CPU |
| `headless-gpu` / `gpu` | base + torch-gpu | Server / batch GPU |
| **`full-cpu`** | base + torch-cpu + gui | **Desktop CPU** |
| **`full-gpu`** | base + torch-gpu + gui | **Desktop GPU** |

(`cpu` = `headless-cpu`, `gpu` = `headless-gpu`)

## Plain pip (no script)

```powershell
pip install -r requirements/base.txt -r requirements/torch-cpu.txt -r requirements/gui.txt
```

## Chinese UI (polyscope)

Setup/KASAL **中文** mode needs `polyscope==2.6.1` (pinned in `gui.txt`). Older `2.3.x` cannot build CJK glyphs → labels show as `□` / `????`.

```powershell
python -m pip install -r requirements/gui.txt
# or upgrade only:
python -m pip install --upgrade polyscope==2.6.1
```

Optional: `KASAL_UI_FONT` points to a `.ttf`/`.ttc`. Default search includes Windows fonts, Linux Noto/WQY paths, and `fc-list :lang=zh`.

**Linux GUI** (not installed by pip): system packages for OpenGL/X11, `python3-tk` or `zenity`/`kdialog`, and `fonts-noto-cjk` for Chinese UI. See [../docs/install.md](../docs/install.md#linux-ubuntu-2004-gui-system-packages).

**KASALv2 source install tutorial:** [../docs/install_kasalv2.md](../docs/install_kasalv2.md) (English) · [../docs/install_kasalv2_zh.md](../docs/install_kasalv2_zh.md) (中文)

Full technical reference: [../docs/install.md](../docs/install.md)
