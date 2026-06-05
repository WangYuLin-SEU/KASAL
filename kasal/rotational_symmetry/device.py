# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Torch device resolution for standalone kasalv2 runs.

from __future__ import annotations

import os
from dataclasses import replace

from .config import SymmetryAnalysisConfig


def resolve_torch_device(prefer: str = "cuda") -> str:
    """Resolve device; honor KASAL_TORCH_DEVICE=cpu|cuda."""

    env = os.environ.get("KASAL_TORCH_DEVICE", "").strip().lower()
    if env in ("cpu", "cuda"):
        if env == "cuda":
            try:
                import torch

                if not torch.cuda.is_available():
                    return "cpu"
            except Exception:
                return "cpu"
        return env

    if prefer == "cuda":
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
    return "cpu"


def apply_device_to_config(config: SymmetryAnalysisConfig) -> SymmetryAnalysisConfig:
    """Inject resolved device into axis_search / texture / classification."""

    device = resolve_torch_device("cuda")
    classification = config.classification
    rot_dev = classification.rotation_loss_device
    if rot_dev is None:
        rot_dev = device
    return replace(
        config,
        axis_search=replace(config.axis_search, device=device),
        texture=replace(config.texture, device=device),
        classification=replace(classification, rotation_loss_device=rot_dev),
    )
