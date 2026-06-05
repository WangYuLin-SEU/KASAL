<div align="center">

[English](./README_kasalv1.md) | **中文**

</div>

# KASAL（kasalv1）用户手册

本文介绍 **经典 kasalv1** 交互流程（用户指定对称类型、PyMeshLab 预处理）。集成 GUI 在 **KASALv2** 之外仍完整保留这些功能。

**KASALv2（新功能）** → [Main README](../README.md) | [主 README（中文）](../README_zh.md)

---

# <img src="../kasal/datasets/K8.ico" width="36"> KASAL（kasalv1）：基于主轴的对称轴定位

KASAL 用于确定旋转对称物体的对称轴朝向与旋转中心。使用 KASAL 时，用户需指定八种预定义旋转对称类型之一；据此在物体模型上定位全部对称轴。完成后自动以 [BOP 格式](https://bop.felk.cvut.cz/) 保存旋转对称信息，便于与支持 BOP 的 6D 位姿估计方法集成，也可用于三维重建、物体识别等任务。

> **↩ 返回 KASALv2** — 您从 KASALv2 文档跳转至此。
> **回到：** [KASALv2 导航表](../README_zh.md#zh-ret-nav-full) · [kasalv1 与 kasalv2 对比](../README_zh.md#zh-ret-compare-kasalv1)

<a name="news"></a>

### <img src="../kasal/datasets/K16.png" width="28"> 动态

统一时间轴见 [主 README — 项目时间轴](../README_zh.md#timeline)。

- **2025 年 9 月**：官方支持 **Windows** 与 **Ubuntu (Linux)**。
- **2025 年 3 月**：GitHub 与 PyPI 全面开源。
- **2024 年 12 月**：TIP 2024 论文 — [DOI: 10.1109/TIP.2024.3515801](https://doi.org/10.1109/TIP.2024.3515801)。

<a name="datasets"></a>

### <img src="../kasal/datasets/K17.png" width="28"> 数据集

> **↩ 返回 KASALv2**
> **回到：** [数据集（v2 概览）](../README_zh.md#zh-ret-nav-datasets)

可通过 DSRSTO 数据集识别哪些物体具有旋转对称性。我们亦使用 KASAL 标注 Google Scanned Objects (GSO) 与 ShapeNet 数据集中的物体。

* DSRSTO: https://huggingface.co/datasets/SEU-WYL/DSRSTO-dataset
* GSO: https://huggingface.co/datasets/SEU-WYL/GSO-SAD
* ShapeNet: https://huggingface.co/datasets/SEU-WYL/ShapeNet-SAD

<a name="installation"></a>

### <img src="../kasal/datasets/K9.png" width="28"> 安装

> **↩ 返回 KASALv2**
> **回到：** [快速开始（v2）](../README_zh.md#zh-ret-nav-install) · [KASALv2 导航表](../README_zh.md#zh-ret-nav-full)

* **平台**：支持 **Windows** 与 **Ubuntu (Linux)**

>| 平台 | 测试版本 |
>|------|----------|
>| Windows | Windows 10 |
>| Ubuntu | 20.04+（glibc ≥ 2.31）|

* **依赖**：Anaconda 3、MeshLab

* **PyPI 安装（kasalv1 包）**

```
pip install kasal-6d
```

（当前 PyPI 仍为 **kasalv1** 构建；集成 KASALv2 的 PyPI 包即将上线。）

**许可：** 本 **KASALv2** 仓库适用 **[PolyForm Noncommercial 1.0.0](../LICENSE)**；独立 **kasalv1** PyPI 包（`pip install kasal-6d`）适用 **[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)**。

* **KASALv2 源码安装**：见 [install_kasalv2_zh.md](install_kasalv2_zh.md)。技术细节：[install.md](install.md)。摘要：[主 README 快速开始](../README_zh.md#quick-start)。

* **快速体验（经典 GUI）**

```
python demo_texture_meshes.py
# 或
python demo_shape_meshes.py
```

<a name="rotational-symmetry-types"></a>

### <img src="../kasal/datasets/K10.png" width="28"> 旋转对称类型

> **↩ 返回 KASALv2**
> **回到：** [对称类型 — v2 导航](../README_zh.md#zh-ret-nav-symmetry-types) · [对称类型 — v2 功能说明](../README_zh.md#zh-ret-detail-sym-types)

KASAL 支持八类旋转对称（三类连续、五类离散）。

<div style="text-align: center;">
  <img src="../kasal/datasets/fig1.png" alt="">
</div>

在 **「Symmetry Type / 对称类型」** 下拉中选择类型，点击 **「Cal Current Obj / 计算当前物体」** 即可定位对称轴。对 **n 折棱柱** 与 **n 折棱锥** 类型，须指定阶数 *n*。

<a name="symmetry-axis-localization-results"></a>

### <img src="../kasal/datasets/K11.png" width="28"> 对称轴定位结果

> **↩ 返回 KASALv2**
> **回到：** [可视化 — v2 导航](../README_zh.md#zh-ret-nav-visualization)

以**正十二面体**为例，给定对称类型后，KASAL 可准确求出全部对称轴朝向与旋转中心，并以箭头与顶点着色等方式可视化方向、阶数与旋转中心。

<div style="text-align: center;">
  <img src="../kasal/datasets/result-p20-1.png" alt="">
</div>

箭头起点在旋转中心，方向沿对称轴；阶数可视化通过对顶点施加满足对称性的变换矩阵并重新着色实现。

<div style="text-align: center;">
  <img src="../kasal/datasets/result-p20-2.png" alt="">
</div>

<a name="batch-processing"></a>

### <img src="../kasal/datasets/K12.png" width="28"> 批量处理

> **↩ 返回 KASALv2**
> **回到：** [批量处理 — v2 导航](../README_zh.md#zh-ret-nav-batch) · [Cal All（仅未保存）— v2 功能说明](../README_zh.md#zh-ret-detail-cal-all)

> **说明（集成版 GUI）**：**KASALv2** 桌面应用中 **「批量计算」** 仅处理 **未保存（unsaved）** 物体。下文描述 **经典 kasalv1** 批量流程。

给定目录后，KASAL 加载其中全部模型；用户须为每件指定对称类型、阶数（如适用）及是否纹理旋转对称。完成后点击 **「Cal All Objs / 批量计算」** 批量定位。

切换物体时会自动保存；**目录中最后一件**须切回前一件以确保落盘。仅有一件物体时，**计算当前** 或 **批量计算** 即可完成并保存。

KASALv2 **Cal All（仅未保存）** 语义见 [主 README](../README_zh.md#zh-ret-detail-cal-all)。

```
from kasal.app.polyscope_app import app

mesh_path = '您的三维模型数据集目录'

app(mesh_path)
```

<a name="texture-rotational-symmetry"></a>

### <img src="../kasal/datasets/K13.png" width="28"> 纹理旋转对称

> **↩ 返回 KASALv2**
> **回到：** [纹理 ADI-C — v2 导航](../README_zh.md#zh-ret-nav-texture) · [纹理 / ADI-C — v2 功能说明](../README_zh.md#zh-ret-detail-texture)

多数物体为几何旋转对称；少数为纹理旋转对称。默认按几何模式定位；纹理对称须手动开启 **「ADI-C」**。

<a name="assisted-localization"></a>

### <img src="../kasal/datasets/K14.png" width="28"> 辅助定位

> **↩ 返回 KASALv2**
> **回到：** [show xyz — v2 导航](../README_zh.md#zh-ret-nav-assisted) · [轴 xyz（kasalv1）— v2 功能说明](../README_zh.md#zh-ret-detail-assisted)

对近似对称或不完美物体，可开启 **「show xyz」**，手动选择最接近 **主轴（最高阶对称轴）** 的 x / y / z 轴。

<div style="text-align: center;">
  <img src="../kasal/datasets/show xyz.png" alt="">
</div>

<a name="citation"></a>

### <img src="../kasal/datasets/K15.png" width="28"> 引用

使用 **kasalv1** 请引用 TIP 2024；使用 **KASALv2** 请优先引用 CVPR 2026 — 见 [主 README — 引用](../README_zh.md#citation)。

```bibtex
@ARTICLE{KASAL,
  author = {Wang, Yulin and Luo, Chen},
  title  = {Key-Axis-Based Localization of Symmetry Axes in 3D Objects Utilizing Geometry and Texture},
  journal= {IEEE Transactions on Image Processing},
  year   = {2024},
  volume = {33},
  pages  = {6720-6733},
  doi    = {10.1109/TIP.2024.3515801}
}
```
