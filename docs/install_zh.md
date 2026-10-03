<div align="center">

[English](install.md) | **中文** · [项目主页](../README_zh.md)

</div>

# 从源码安装 KASALv2

集成版 KASALv2 目前通过本仓库源码发布，并不包含在 `kasal-6d` PyPI 包中。推荐使用 Python 3.10 与 conda。

## 选择安装剖面

| 剖面 | 用途 |
|------|------|
| `full-cpu` | 无 CUDA 的完整桌面应用 |
| `full-gpu` | 兼容 NVIDIA GPU 的完整桌面应用 |
| `headless-cpu` | CPU 上的 KASALv2 命令行处理 |
| `headless-gpu` | CUDA 上的 KASALv2 命令行处理 |

CPU 与 GPU torch 包二选一，不要在同一环境混装。各剖面的准确组成见 [requirements/README.md](../requirements/README.md)。

## 安装与验证

```bash
git clone https://github.com/WangYuLin-SEU/KASAL.git
cd KASAL
conda create -n kasal python=3.10
conda activate kasal
python scripts/install_deps.py full-cpu
python scripts/verify_pytorch3d.py
```

仅在机器具备兼容 NVIDIA/CUDA 环境时把 `full-cpu` 换成 `full-gpu`。验证成功时会打印 torch 版本、PyTorch3D 运算结果以及 `cpu` 或 `cuda`。

## 启动 GUI

```bash
python demo_shape_meshes.py
```

自带纹理示例：

```bash
python demo_texture_meshes.py
```

两条命令打开相同的 **Setup → KASAL** 界面，只是初始数据目录不同。常用流程见[项目 README](../README_zh.md#使用要点)。

## 首次启动

1. 在 **Setup（设置）**页选择界面语言、数据集文件夹、预处理策略与计算设备。
2. 点击**确认**。KASAL 会把这些数据集级设置写入所选文件夹中的 `KASAL.json`，然后进入主面板。
3. 自动分析时保持当前对象引擎为 `kasalv2`；单个对象使用**当前计算**。
4. **批量计算（仅未保存）**只处理尚无保存结果或加载后被编辑的对象。完成后写入 `{stem}_sym_type.json`，适用时还会写入 `{stem}_sym.ply`。

返回设置页只修改配置，不会删除已有标注 sidecar。

## 无头运行

安装 `headless-cpu` 或 `headless-gpu` 后运行：

```bash
python -m kasal.cli.run_job kasal/jobs/example_job.json
```

无头剖面不包含 Polyscope 和 PyMeshLab，应使用 `kasalv2_strict` 预处理，它可以为两套计算引擎准备网格。桌面界面以及 PyMeshLab 预处理（`kasalv1` 策略或自适应回退）需要完整剖面。

## PyTorch3D 包

仓库依赖文件固定了相互匹配的 torch 2.4.1、torchvision 0.19.1 与 PyTorch3D 0.7.8 CPU 或 CUDA 11.8 构建。PyTorch3D 来自 [MiroPsota 包索引](https://miropsota.github.io/torch_packages_builder/)，因为 PyPI 没有项目所需的 Windows wheel。

请优先使用仓库内的安装剖面，不要单独安装 `pytorch3d`。验证失败时，新建干净的 Python 3.10 环境，并只安装一套完整 CPU 或 GPU 剖面。

## Linux 桌面系统包

Ubuntu 20.04+ 需要 OpenGL/X11 库、文件夹选择器，以及中文界面所需的 CJK 字体：

```bash
sudo apt update
sudo apt install -y \
  libgl1 libglu1-mesa libx11-6 libxi6 libxrandr2 libxxf86vm1 \
  libxinerama1 libxcursor1 libxkbcommon0 \
  python3-tk zenity fonts-noto-cjk pciutils
```

KDE 用户可以安装 `kdialog` 代替 `zenity`。

## 中文界面

中文界面需要 `polyscope==2.6.1`（GUI 剖面已固定）和 CJK 字体。如果自动字体搜索失败，可在启动应用前将 `KASAL_UI_FONT` 指向本地 `.ttf` 或 `.ttc`。

Windows PowerShell 示例：

```powershell
$env:KASAL_UI_FONT = "C:\Windows\Fonts\msyh.ttc"
```

## 覆盖计算设备

通常直接在 Setup 页面选择设备。仅覆盖当前 shell 时：

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

环境变量覆盖值优先于已保存的 GUI 选择。显式选择的设备无效或不可用时会报错；只有自动选择设备时才允许回退到 CPU。

## 常见问题

- **检测到 GPU 但无法选择：** 当前 PyTorch 是 CPU 构建；请在干净环境安装 `full-gpu`。
- **中文显示为方框：** 检查 `polyscope==2.6.1`，并安装或指定 CJK 字体。
- **网格预处理失败：** 完整安装可尝试 `kasalv2_adaptive`，并检查网格几何是否有效。
- **GUI 打开目录后没有对象：** 当前会自动发现 `.ply`、`.obj`（扩展名不区分大小写），并排除生成的 `*_sym.ply`。
- **从 PyPI 安装了 `kasal-6d`：** 这是独立发布的经典 kasalv1，见 [kasalv1 手册](README_kasalv1_zh.md)。
