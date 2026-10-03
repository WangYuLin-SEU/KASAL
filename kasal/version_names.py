# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Canonical engine / preprocess ids (kasalv1 = original KASAL pipeline).

from __future__ import annotations

KASALV1_ENGINE = "kasalv1"
KASALV2_ENGINE = "kasalv2"
ENGINES = (KASALV1_ENGINE, KASALV2_ENGINE)

KASALV1_PREPROCESS = "kasalv1"
KASALV2_ADAPTIVE = "kasalv2_adaptive"
KASALV2_STRICT = "kasalv2_strict"
PREPROCESS_POLICIES = (KASALV1_PREPROCESS, KASALV2_ADAPTIVE, KASALV2_STRICT)

# Backward-compatible aliases for saved JSON / older experiment outputs.
ENGINE_ALIASES = {
    "kasal": KASALV1_ENGINE,
    "legacy": KASALV1_ENGINE,
    "kasal_legacy": KASALV1_ENGINE,
}

PREPROCESS_ALIASES = {
    "kasal_legacy": KASALV1_PREPROCESS,
}


def normalize_engine(engine: str | None) -> str:
    if not engine:
        return KASALV1_ENGINE
    key = str(engine).strip()
    return ENGINE_ALIASES.get(key, key)


def validate_engine(engine: str | None) -> str:
    normalized = normalize_engine(engine)
    if normalized not in ENGINES:
        raise ValueError(f"unknown symmetry engine: {engine!r}")
    return normalized


def validate_preprocess_policy(policy: str | None) -> str:
    if not policy:
        normalized = KASALV2_ADAPTIVE
    else:
        key = str(policy).strip()
        normalized = PREPROCESS_ALIASES.get(key, key)
    if normalized not in PREPROCESS_POLICIES:
        raise ValueError(f"Unknown mesh preprocessing policy: {policy!r}")
    return normalized


def is_kasalv1_engine(engine: str | None) -> bool:
    return normalize_engine(engine) == KASALV1_ENGINE
