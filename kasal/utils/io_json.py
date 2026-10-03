# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from kasal.utils.atomic_file import atomic_output_path


def load_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: str | Path, data: Any, *, ensure_ascii: bool = True) -> None:
    """Atomically replace a JSON file without truncating the previous version."""

    with atomic_output_path(path) as temporary:
        with temporary.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=4, ensure_ascii=ensure_ascii, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
