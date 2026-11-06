<p align="center">
  <img src="kasal/datasets/kasal_icon.png" alt="KASAL" width="75%">
</p>

<p align="center">
  <a href="https://pypi.org/project/kasal-6d/"><img src="https://img.shields.io/pypi/v/kasal-6d" alt="PyPI 版本"></a>
  <a href="https://pepy.tech/projects/kasal-6d"><img src="https://api.pepy.tech/badge/kasal-6d" alt="PyPI 下载量"></a>
  <a href="https://github.com/WangYuLin-SEU/KASAL/releases/"><img src="https://img.shields.io/github/downloads/WangYuLin-SEU/KASAL/total?color=green" alt="GitHub Releases 下载量"></a>
</p>

<div align="center">

[English](README.md) | **中文** · [安装](docs/install_zh.md)

# KASAL：三维旋转对称分类与对称轴定位

KASAL 系列结合三维几何与纹理分析旋转对称。**kasalv1** 在已知对称类型和阶数时自动计算完整轴系；**KASALv2** 则自动推断类型、阶数与对称轴。两套流程集成在同一桌面应用中。

**论文：** [kasalv1 · TIP 2024](https://doi.org/10.1109/TIP.2024.3515801) · [KASALv2 · CVPR 2026 Open Access](https://openaccess.thecvf.com/content/CVPR2026/html/Zhang_KASALv2_Fully_Automatic_3D_Rotational_Symmetry_Classification_and_Axis_Localization_CVPR_2026_paper.html) · [PDF](https://openaccess.thecvf.com/content/CVPR2026/papers/Zhang_KASALv2_Fully_Automatic_3D_Rotational_Symmetry_Classification_and_Axis_Localization_CVPR_2026_paper.pdf)

[快速开始](#快速开始) · [使用方式](#选择使用方式) · [界面](#界面) · [指南](#指南) · [引用](#引用)

</div>

> **PyPI 包名：** KASALv2 **2.0.0** 已正式发布为 [`kasal-6d`](https://pypi.org/project/kasal-6d/2.0.0/)，承接经典 0.1.x 包版本线，提供集成 kasalv1 + KASALv2 的桌面应用。KASALv2 后续版本沿用 `kasal-6d` 包名，当前源码版本为 **2.0.1rc3**。Objaverse-SAD 目前正在整理中，后续将正式发布。

## 主要特点

- 自动覆盖八类典型三维旋转对称的分类与完整轴定位
- 以几何分析为主，并可增加独立的纹理感知细化层
- 同一 GUI 集成自动 **kasalv2** 与用户引导 **kasalv1** 两套引擎
- 提供桌面/无头、CPU/CUDA 安装组合
- 支持仅处理未保存对象的增量批处理，以及独立的数据集批处理
- 输出兼容 BOP 对称字段，可用于下游 6D 位姿估计流程

## 快速开始

KASALv2 2.0.0 支持 Python 3.10，默认包含桌面依赖。先安装匹配的 PyTorch/PyTorch3D 运行环境，再从 PyPI 安装 KASALv2。CPU 示例：

```bash
conda create -n kasalv2 python=3.10
conda activate kasalv2
python -m pip install -r https://raw.githubusercontent.com/WangYuLin-SEU/KASAL/3dba824747530bc6296b84b1d5ba6fa172610a18/requirements/torch-cpu.txt
python -m pip install kasal-6d==2.0.0
kasalv2 --help
kasalv2 "PATH_TO_YOUR_MESH_DIRECTORY"
```

CUDA 环境请在新环境中使用匹配的 `torch-gpu.txt`，详见[安装说明](docs/install_zh.md#pypi-正式版本)。如果在同一环境中从独立的 `kasalv2` 包迁移，请先卸载它再安装 `kasal-6d`，因为两者使用相同的 `kasal` 导入目录。

从源码运行：

推荐使用 Python 3.10 与 conda。仅在具备兼容 NVIDIA/CUDA 环境时选择 `full-gpu`。

```bash
git clone https://github.com/WangYuLin-SEU/KASAL.git
cd KASAL
conda create -n kasal python=3.10
conda activate kasal
python scripts/install_deps.py full-cpu
python scripts/verify_pytorch3d.py
python demo_shape_meshes.py
```

纹理示例运行 `python demo_texture_meshes.py`。GPU、Linux、无头环境与故障排查见[安装指南](docs/install_zh.md)。

## 选择使用方式

| 目标 | 入口 | 输出 |
|------|------|------|
| 在 GUI 中浏览或标注网格 | `python demo_shape_meshes.py` | Sidecar `*_sym_type.json` 与可视化 `*_sym.ply` |
| 在 GUI 中分析纹理示例 | `python demo_texture_meshes.py` | 相同 sidecar 文件；在界面中启用纹理感知分析 |
| 不启动 Polyscope，执行与 GUI 相同的任务 | `python -m kasal.cli.run_job kasal/jobs/example_job.json` | 写在源网格旁的 sidecar 文件 |
| 将平铺数据集处理到独立输出目录 | `python -m kasal.rotational_symmetry.run_dataset --input-dir INPUT --output-dir OUTPUT` | 逐对象 BOP 风格 JSON，以及批量 JSON/CSV 汇总 |
| 使用经典 kasalv1 用户引导流程 | 在集成 GUI 中选择类型/阶数；原版应用使用 `kasal-6d==0.1.4` | 根据给定的类型/阶数自动计算对称轴 |

GUI 会递归发现目录内的 `.ply` 和 `.obj`，并忽略生成的 `*_sym.ply`。如果通过任务列表或数据集运行器的匹配模式显式传入文件，KASALv2 加载器还支持 `.glb`、`.gltf`、`.stl` 和 `.off`。

## 使用要点

在 **Setup（设置）**页选择数据集目录、预处理策略和计算设备，然后点击**确认**。处理新数据集时通常保持使用 **kasalv2**。

- 未标注且类型/阶数未经编辑的对象，无论引擎下拉框选项为何，都使用 kasalv2 自动分析。
- 修改对称类型或阶数，或指定 X/Y/Z 拟合时，计算转由 kasalv1 执行。指定 X/Y/Z 拟合还需要明确的对称类型。
- 命令行任务若提供了已知对称类型，需显式将引擎设为 `kasalv1`。两套引擎都会自动计算对称轴。
- 桌面环境推荐 `kasalv2_adaptive`；没有 PyMeshLab 的无头环境使用 `kasalv2_strict`。
- **批量计算（仅未保存）**只处理尚无保存结果或加载后被编辑的对象。
- 每个完成对象会在源网格旁写入 `{stem}_sym_type.json`，适用时还会写入 `{stem}_sym.ply`。

独立数据集运行器写入单独输出目录，为每个对象生成一份 BOP 风格 JSON，并生成 JSON/CSV 批量汇总。命令行选项可通过以下命令查看：

```bash
python -m kasal.rotational_symmetry.run_dataset --help
```

## 方法概览

```text
网格
  -> 加载、归一化与几何采样
  -> 搜索主高阶轴
  -> 估计旋转周期与阶数
  -> 恢复次轴并分类对称族
  -> 可选：使用外观信息细化
  -> 导出兼容 BOP 的对称数据
```

KASALv2 用 **几何退化层次结构（GDH）** 描述八类典型对称及其相互关系。它首先定位主高阶轴，通过自洽分析推断旋转阶数，再依据这一层次结构确定对称类型并恢复完整轴系。纹理分析以独立层保存，外观造成的阶数变化不会覆盖几何结果。

论文在 438 个 GSO 对称物体上报告了 **94.75% 的类型与阶数联合准确率**。将其对称先验用于 FoundationPose 后，五个 BOP 数据集中最大的平均提升为 **IC-BIN 上的 0.9 个百分点**。这些位姿估计结果取同一次训练的五个检查点的均值。

## kasalv1 与 KASALv2

已知对称类型和阶数时，kasalv1 用少量关键轴确定完整轴系。其轴定位研究涵盖七类非球对称，几何定位使用 **ADI**，结合纹理时使用 **ADI-C**。KASALv2 在此基础上进一步自动推断类型和阶数。

| | kasalv1 | KASALv2 |
|---|---|---|
| 输入 | 用户选择对称类型，必要时指定阶数 | 无需预定义类型或阶数 |
| 主要用途 | 已知类型/阶数时的轴定位、复核、修正与强制 X/Y/Z 轴拟合 | 自动标注新网格和数据集 |
| 核心实现 | PyMeshLab 预处理、关键轴模板、ADI 与 ADI-C | PyTorch3D、GDH 引导的轴搜索、周期性与一致性分析 |
| 发布方式 | 经典 [`kasal-6d` 0.1.x](https://pypi.org/project/kasal-6d/0.1.4/)；集成应用也保留该流程 | 集成版 [`kasal-6d` 2.0.0](https://pypi.org/project/kasal-6d/2.0.0/) 及本仓库源码 |
| 手册 | [经典 kasalv1 手册](docs/README_kasalv1_zh.md) | 本 README |

## 界面

**Setup（设置）**页用于选择数据集目录、界面语言、预处理策略与计算设备。

<p align="center">
  <img src="kasal/datasets/v2-1-ch.png" alt="KASALv2 设置页" width="720">
</p>

确认后进入 **KASAL** 主页面，可切换对象、修改标注、选择引擎、计算当前对象或增量批处理。

<p align="center">
  <img src="kasal/datasets/v2-2-ch.png" alt="KASALv2 主页面" width="720">
</p>

## 指南

| 文档 | 内容 |
|------|------|
| [安装指南](docs/install_zh.md) | 依赖组合、CPU/GPU、Linux 系统包与故障排查 |
| [经典 kasalv1 手册](docs/README_kasalv1_zh.md) | 为现有用户保留的已知对称类型流程 |
| [网站源码](docs/site/) | KASAL 系列、方法、结果与软件的双语介绍 |

## 源码结构

| 目录 | 职责 |
|------|------|
| `kasal/app/`、`kasal/cli/` | GUI 和无头任务入口 |
| `kasal/compute/` | 共用任务执行、引擎路由及后台进程 |
| `kasal/config/` | `algorithms.py` 管理 v1/v2 和网格预处理参数；`runtime.py` 管理 GUI 设置与运行状态 |
| `kasal/annotations/` | 标注格式、sidecar 路径及保存状态；`io.py` 处理格式，`state.py` 管理应用状态 |
| `kasal/keyaxis/`、`kasal/symmetry_lab/` | kasalv1 关键轴搜索、对称模板与轴定位 |
| `kasal/rotational_symmetry/` | KASALv2 自动分析与独立数据集运行器 |
| `kasal/geometry/`、`kasal/viz/` | 共用几何处理与可视化导出 |
| `kasal/utils/`、`kasal/datasets/` | 通用工具、示例模型和资源路径 |
| `docs/site/` | 包含 `index.html` 和本地资源的双语静态网站 |

代码结构将应用入口、运行状态、标注读写、几何工具以及 KASALv1/KASALv2 算法模块分离。算法参数集中在 `kasal/config/algorithms.py`，可变的 GUI 与运行时状态集中在 `kasal/config/runtime.py`。

## 数据集

- [DSRSTO](https://huggingface.co/datasets/SEU-WYL/DSRSTO-dataset)
- [GSO-SAD](https://huggingface.co/datasets/SEU-WYL/GSO-SAD)
- [ShapeNet-SAD](https://huggingface.co/datasets/SEU-WYL/ShapeNet-SAD)
- **Objaverse-SAD（约 3.5 万件）：** 正在整理中，计划后续正式发布

## 许可

本仓库及其中的集成 KASALv2 源码版本采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，该许可不允许商业使用。商业许可问题请联系王宇林（[yulinwang@seu.edu.cn](mailto:yulinwang@seu.edu.cn)）。

历史经典 `kasal-6d` 0.1.x 版本继续采用 [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)。集成版 2.0.0 使用当前仓库许可证；内置第三方代码保留各自的许可声明。

## 引用

使用 KASALv2 请引用 CVPR 2026 论文：

```bibtex
@InProceedings{Zhang_2026_CVPR,
  author    = {Zhang, Mengxin and Wang, Yulin and Luo, Chen and Li, Yongzhe and Zhou, Yijun},
  title     = {KASALv2: Fully Automatic 3D Rotational Symmetry Classification and Axis Localization},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  month     = {June},
  year      = {2026},
  pages     = {13866--13875}
}
```

使用原版 kasalv1 方法时还请引用：

```bibtex
@ARTICLE{KASAL,
  author  = {Wang, Yulin and Luo, Chen},
  title   = {Key-Axis-Based Localization of Symmetry Axes in 3D Objects Utilizing Geometry and Texture},
  journal = {IEEE Transactions on Image Processing},
  year    = {2024},
  volume  = {33},
  pages   = {6720--6733},
  doi     = {10.1109/TIP.2024.3515801}
}
```
