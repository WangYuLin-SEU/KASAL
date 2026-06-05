#!/usr/bin/env python3

# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Install KASAL dependency profile via pip."""

import argparse
import subprocess
import sys
from pathlib import Path

KASAL_ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = KASAL_ROOT / "requirements"

# Only 4 requirement files; profiles combine them.
PROFILES = {
    "base": ["base.txt"],
    "torch-cpu": ["torch-cpu.txt"],
    "torch-gpu": ["torch-gpu.txt"],
    "gui": ["gui.txt"],
    "headless-cpu": ["base.txt", "torch-cpu.txt"],
    "headless-gpu": ["base.txt", "torch-gpu.txt"],
    "cpu": ["base.txt", "torch-cpu.txt"],
    "gpu": ["base.txt", "torch-gpu.txt"],
    "full-cpu": ["base.txt", "torch-cpu.txt", "gui.txt"],
    "full-gpu": ["base.txt", "torch-gpu.txt", "gui.txt"],
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install a KASAL requirements profile (see requirements/README.md)"
    )
    parser.add_argument(
        "profile",
        choices=sorted(PROFILES),
        help="Install profile name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pip command only",
    )
    args = parser.parse_args()

    req_files = []
    for name in PROFILES[args.profile]:
        path = REQ_DIR / name
        if not path.is_file():
            print(f"[ERR] missing {path}", file=sys.stderr)
            return 1
        req_files.append(str(path))

    cmd = [sys.executable, "-m", "pip", "install"]
    for req in req_files:
        cmd.extend(["-r", req])
    print(" ".join(cmd), flush=True)
    if args.dry_run:
        return 0
    return subprocess.call(cmd, cwd=str(KASAL_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
