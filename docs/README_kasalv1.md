<div align="center">

**English** | [中文](README_kasalv1_zh.md) · [KASALv2 home](../README.md)

</div>

# KASAL (kasalv1) user guide

This guide covers the original user-guided KASAL workflow: the user supplies a symmetry type and order, and kasalv1 localizes the corresponding axes and rotation center. The current repository retains this workflow beside the automatic KASALv2 engine.

For automatic analysis, current GUI behavior, and command-line batches, use the [project README](../README.md#usage-essentials).

## Availability

| Distribution | Contents | License |
|--------------|----------|---------|
| Current source repository | Integrated kasalv1 + KASALv2 application | [PolyForm Noncommercial 1.0.0](../LICENSE) |
| [`kasal-6d` on PyPI](https://pypi.org/project/kasal-6d/) | Classic kasalv1 package | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) |

Install the classic package with:

```bash
pip install kasal-6d
```

To run the integrated source application instead, follow [Install KASALv2 from source](install.md).

## Start the integrated GUI

```bash
python demo_shape_meshes.py
```

For textured examples:

```bash
python demo_texture_meshes.py
```

You can also open your own dataset:

```python
from kasal.app.polyscope_app import app

app(r"C:\path\to\mesh_dataset")
```

The integrated GUI discovers PLY and OBJ files recursively. Other explicitly supplied formats supported by KASALv2 are listed in the [workflow overview](../README.md#choose-a-workflow).

<a id="rotational-symmetry-types"></a>

## Rotational symmetry types

KASAL uses eight canonical types: three continuous families and five discrete families.

<p align="center">
  <img src="../kasal/datasets/fig1.png" alt="Eight rotational symmetry types supported by KASAL" width="720">
</p>

| Label | User input |
|-------|------------|
| `C(>>1): Spherical Item` | Type |
| `C(>1): Cylindrical Item` | Type |
| `C(=1): Circular Item` | Type |
| `D(>1): n-fold Prismatic Item` | Type and order *n* |
| `D(=1): n-fold Pyramidal Item` | Type and order *n* |
| `P(4): Tetrahedral Item` | Type |
| `P(8): Octahedral Item` | Type |
| `P(20): Icosahedral Item` | Type |

In the main panel:

1. Select a concrete **Symmetry Type**.
2. Set *n* for an n-fold prismatic or pyramidal object.
3. Choose **kasalv1** for the current-object engine.
4. Click **Cal Current**.

If the object is unlabeled, the integrated application routes it to KASALv2 even when kasalv1 was requested. This prevents a manual pipeline from running without its required type.

<a id="symmetry-axis-localization-results"></a>

## Localization results

KASAL estimates all axes implied by the supplied family and the shared rotation center. The visualization uses arrows for axis direction and vertex colors to distinguish symmetry order.

<p align="center">
  <img src="../kasal/datasets/result-p20-1.png" alt="Symmetry axes and rotation center on a regular dodecahedron" width="720">
</p>

An arrow starts at the rotation center and points along its symmetry axis.

<p align="center">
  <img src="../kasal/datasets/result-p20-2.png" alt="Vertex-color visualization of rotational order" width="720">
</p>

Results are saved as `*_sym_type.json` and, when requested, `*_sym.ply`.

<a id="texture-rotational-symmetry"></a>

## Texture rotational symmetry

Geometry can have a higher rotational order than its appearance. Enable **ADI-C** when texture or color should participate in symmetry evaluation. Use `demo_texture_meshes.py` for the bundled example.

The integrated KASALv2 path stores texture-aware output separately under `texture_symmetry`; it does not replace the geometric result.

<a id="assisted-localization"></a>

## Assisted localization

Approximately symmetric or imperfect meshes can make the primary axis ambiguous. Enable **show xyz** to display the canonical axes, then choose the X, Y, or Z axis closest to the expected primary key axis.

<p align="center">
  <img src="../kasal/datasets/show xyz.png" alt="Canonical XYZ axes used for assisted localization" width="720">
</p>

Selecting an axis override always routes computation to kasalv1. A concrete symmetry type is still required.

<a id="batch-processing"></a>

## Batch processing

In the integrated application, **Cal All (unsaved)** processes only objects without a valid sidecar or objects edited since loading. Successful results are saved as each object completes.

For repeatable non-interactive execution, use `python -m kasal.cli.run_job JOB.json`. It accepts the same manual fields through `defaults.sym_type`, `defaults.n_fold`, and `defaults.axis_xyz`.

The separately distributed PyPI package preserves the classic kasalv1 application described on its [PyPI project page](https://pypi.org/project/kasal-6d/); its interface can differ from the integrated source application.

<a id="datasets"></a>

## Datasets

- [DSRSTO](https://huggingface.co/datasets/SEU-WYL/DSRSTO-dataset)
- [GSO-SAD](https://huggingface.co/datasets/SEU-WYL/GSO-SAD)
- [ShapeNet-SAD](https://huggingface.co/datasets/SEU-WYL/ShapeNet-SAD)

<a id="citation"></a>

## Citation

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

If you use the automatic KASALv2 method, also cite the CVPR 2026 paper listed in the [project README](../README.md#citation).
