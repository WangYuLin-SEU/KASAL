# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Engine routing rules (no torch / GUI dependencies).

from __future__ import annotations

import kasal.config.config as config
from kasal.version_names import KASALV2_ENGINE, is_kasalv1_engine, normalize_engine


def kasalv1_user_labels_specified(
    sym_type: str,
    sym_type_source: str | None,
    n_fold_source: str | None,
) -> bool:
    """kasalv1 may run when the UI has a concrete symmetry type."""

    if sym_type in ("None", ""):
        return False
    return True


def kasalv1_skip_reason(
    sym_type: str,
    sym_type_source: str | None,
    n_fold_source: str | None,
) -> str | None:
    """Human-readable reason when kasalv1 cannot run; None when labels are ready."""

    if kasalv1_user_labels_specified(sym_type, sym_type_source, n_fold_source):
        return None
    if sym_type in ("None", ""):
        return (
            "kasalv1 requires symmetry type and n-fold set in the UI "
            "(object is unlabeled)."
        )
    return "kasalv1 requires a concrete symmetry type before it can compute."


def engine_speed_hint(*, cuda_available: bool) -> str:
    """Short UI note: which engine is usually faster on this hardware build."""

    if cuda_available:
        return "GPU build: kasalv2 is typically faster than kasalv1."
    return "CPU build: kasalv1 is typically faster than kasalv2."


def kasalv1_usage_hint() -> str:
    return (
        "kasalv1 computes when a concrete symmetry type is available in the UI; "
        "unlabeled objects use kasalv2 first."
    )


def engine_routing_note(requested_engine: str, resolved_engine: str) -> str | None:
    """Explain when the UI engine choice is overridden (e.g. unlabeled → kasalv2)."""

    if (
        is_kasalv1_engine(requested_engine)
        and normalize_engine(resolved_engine) == KASALV2_ENGINE
    ):
        return (
            "Unlabeled object: compute will use kasalv2 "
            "(kasalv1 requires user-set symmetry type and n-fold)."
        )
    return None


def should_use_kasalv1_engine(axis_xyz: str | None, engine_mode: str) -> bool:
    """Return True when the kasalv1 (original KASAL) engine must be used."""

    if axis_xyz is not None and axis_xyz != "None":
        return True
    if is_kasalv1_engine(engine_mode):
        return True
    if getattr(config, "sym_type_source", "kasalv2_auto") == "user":
        return True
    if getattr(config, "n_fold_source", "kasalv2_auto") == "user":
        return True
    return False


# Backward-compatible alias (deprecated name).
should_use_legacy_engine = should_use_kasalv1_engine
