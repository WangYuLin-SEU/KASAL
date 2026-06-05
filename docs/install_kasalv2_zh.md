<div align="center">

[English](./install_kasalv2.md) | **中文**

</div>

# KASALv2 — 从源码安装

本文介绍如何从 **GitHub 源码** 安装 **KASALv2** 并启动集成桌面 GUI。集成版 **KASALv2** PyPI 包尚未发布，请暂时使用本流程。

> **kasalv1（经典版）：** 同一 GUI 仍支持原版手动标注流程。仅安装 PyPI 版 kasalv1 及经典用法见 [README_kasalv1_zh.md](README_kasalv1_zh.md)。本文仅聚焦 **KASALv2 源码安装**。

### 环境要求

| 项目 | 说明 |
|------|------|
| **Python** | 3.10（推荐 conda） |
| **代码** | 克隆 [KASAL](https://github.com/WangYuLin-SEU/KASAL)，在 `KASAL/` 目录下操作 |
| **安装剖面** | 桌面 GUI + kasalv2 请用 **`full-cpu`** 或 **`full-gpu`** |

### 依赖文件（4 个）

依赖位于 `KASAL/requirements/`，通过 `scripts/install_deps.py` 按剖面组合安装：

| 文件 | 内容 |
|------|------|
| [`base.txt`](../requirements/base.txt) | 核心网格/几何库（trimesh、open3d、fpsample 等），无 PyTorch、无 GUI |
| [`torch-cpu.txt`](../requirements/torch-cpu.txt) | CPU 版 PyTorch + **PyTorch3D**（kasalv2 必需） |
| [`torch-gpu.txt`](../requirements/torch-gpu.txt) | CUDA PyTorch + PyTorch3D（cu118） |
| [`gui.txt`](../requirements/gui.txt) | Polyscope **2.6.1**、PyMeshLab、OpenCV — 桌面 GUI |

`torch-cpu` 与 `torch-gpu` **二选一**，不可同环境混装。

| 剖面 | 组合 | 适用 |
|------|------|------|
| **`full-cpu`** | base + torch-cpu + gui | **无 NVIDIA GPU 的桌面** |
| **`full-gpu`** | base + torch-gpu + gui | **有 NVIDIA GPU 的桌面**（推荐） |
| `headless-cpu` / `headless-gpu` | base + torch | 无 GUI 的批处理/服务器 |

完整剖面表：[requirements/README.md](../requirements/README.md)。

### 步骤 1 — 创建环境并安装

```bash
conda create -n kasal python=3.10
conda activate kasal
cd KASAL
python scripts/install_deps.py full-cpu    # 或：full-gpu
```

等价 pip（完整 CPU 桌面版）：

```bash
pip install -r requirements/base.txt -r requirements/torch-cpu.txt -r requirements/gui.txt
```

**Windows 上 PyTorch3D：** 请勿单独从 PyPI `pip install pytorch3d`，请使用 `torch-cpu.txt` / `torch-gpu.txt` 中的固定版本（MiroPsota 源）。详见 [install.md — PyTorch3D](install.md#pytorch3d-required-for-kasalv2)。

### 步骤 2 — 验证 kasalv2 环境

```bash
python scripts/verify_pytorch3d.py
```

正常应输出：`OK torch … | pytorch3d import | device cpu`（或 `cuda`）。

### 步骤 3 — 启动 GUI（demo）

**几何网格**（自带示例数据集）：

```bash
python demo_shape_meshes.py
```

**纹理网格**（ADI-C / 纹理旋转对称）：

```bash
python demo_texture_meshes.py
```

两个 demo 打开同一套 **Setup → KASAL** 界面，仅默认样本目录不同（`shape_meshes` / `texture_meshes`）。

### 步骤 4 — 首次使用流程

1. **Setup（设置）** — 选择 **界面语言**、**数据集文件夹**、**网格预处理**（推荐 `kasalv2_adaptive`）、**计算设备**。
2. 点击黄色 **确认** → 写入 `KASAL.json` → 进入 **KASAL** 主面板。
3. 在列表中选物体；**当前计算** 引擎选 **`kasalv2`** 即可自动分析对称。
4. **当前计算** 处理单个物体；**批量计算（仅未保存）** 批处理 — 输出 `{stem}_sym_type.json`、`{stem}_sym.ply`。

界面截图与功能说明：[README_zh.md](../README_zh.md)。

### 仅 CPU 机器

已装 `full-cpu` 或无 CUDA 时：

```bash
# Linux / macOS
export KASAL_TORCH_DEVICE=cpu

# Windows（cmd）
set KASAL_TORCH_DEVICE=cpu

python demo_shape_meshes.py
```

### 中文界面

**中文** 界面需要 `polyscope==2.6.1`（`gui.txt` 已包含）。Linux 请安装 `fonts-noto-cjk` 或设置 `KASAL_UI_FONT`。详见 [install.md — 中文界面](install.md#chinese-ui-polyscope-261)。

### Linux GUI 系统依赖

Polyscope/GLFW 需要 OpenGL + X11；选文件夹需要 `zenity`/`kdialog` 或 `python3-tk`：

```bash
sudo apt install -y libgl1 libglu1-mesa libx11-6 libxi6 libxrandr2 \
  libxxf86vm1 libxinerama1 libxcursor1 libxkbcommon0 \
  python3-tk zenity fonts-noto-cjk pciutils
```

完整说明：[install.md — Linux](install.md#linux-ubuntu-2004-gui-system-packages)。

### 可选环境变量

| 变量 | 用途 |
|------|------|
| `KASAL_TORCH_DEVICE` | `cpu` \| `cuda` — 强制设备 |
| `KASAL_UI_FONT` | 中文界面字体路径（`.ttf`/`.ttc`） |
| `KASAL_SEED` | 可选，固定随机种子 |

### 故障排查

- 安装细节、无头任务、版本矩阵 → [install.md](install.md)
- 经典 kasalv1 手动标注、`pip install kasal-6d` → [README_kasalv1_zh.md](README_kasalv1_zh.md)
