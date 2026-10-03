# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def atomic_output_path(path: str | os.PathLike[str]) -> Iterator[Path]:
    """Yield a sibling temporary path and replace the target on success."""

    target = Path(path)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        yield temporary
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
