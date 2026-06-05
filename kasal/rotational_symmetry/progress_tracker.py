# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Write machine-readable progress for long GSO / dataset runs.

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def _progress_path(output_root: Path) -> Path:
    return output_root / "run_progress.json"


def init_progress(
    output_root: Path,
    *,
    total: int,
    workers: int,
    input_dir: str,
) -> None:
    """Create or reset progress file at batch start."""

    output_root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    payload = {
        "phase": "running",
        "total": int(total),
        "done": 0,
        "ok": 0,
        "failed": 0,
        "workers": int(workers),
        "input_dir": str(input_dir),
        "output_dir": str(output_root),
        "started_at": now,
        "updated_at": now,
        "last_object": None,
        "last_status": None,
        "eta_sec": None,
        "recent": [],
    }
    _write(payload, output_root)


def update_progress(
    output_root: Path,
    *,
    item: dict[str, Any],
    index: int,
    total: int,
) -> None:
    """Append one finished object and refresh ETA."""

    path = _progress_path(output_root)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"started_at": time.time(), "recent": []}

    now = time.time()
    started = float(payload.get("started_at", now))
    done = int(payload.get("done", 0)) + 1
    ok = int(payload.get("ok", 0)) + (1 if item.get("success") else 0)
    failed = int(payload.get("failed", 0)) + (0 if item.get("success") else 1)

    elapsed = max(now - started, 1e-6)
    rate = done / elapsed
    remaining = max(int(total) - done, 0)
    eta_sec = (remaining / rate) if rate > 0 else None

    recent = list(payload.get("recent", []))
    recent.append(
        {
            "object": item.get("object"),
            "status": "ok" if item.get("success") else "error",
            "sym_type": item.get("sym_type"),
            "n_fold": item.get("n_fold"),
            "total_sec": item.get("total_sec"),
        }
    )
    recent = recent[-8:]

    payload.update(
        {
            "phase": "running",
            "total": int(total),
            "done": done,
            "ok": ok,
            "failed": failed,
            "updated_at": now,
            "last_object": item.get("object"),
            "last_status": "ok" if item.get("success") else "error",
            "eta_sec": round(eta_sec, 1) if eta_sec is not None else None,
            "recent": recent,
        }
    )
    _write(payload, output_root)

    pct = 100.0 * done / max(int(total), 1)
    eta_txt = _format_eta(eta_sec)
    line = (
        f"[DATASET] progress {done}/{total} ({pct:.1f}%) | "
        f"ok={ok} fail={failed} | last={item.get('object')} ({payload['last_status']}) | "
        f"elapsed={_format_eta(elapsed)} eta={eta_txt}"
    )
    print(line, flush=True)


def finish_progress(output_root: Path, *, success_count: int, total: int) -> None:
    """Mark batch complete."""

    path = _progress_path(output_root)
    payload = {}
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(
        {
            "phase": "done",
            "total": int(total),
            "done": int(total),
            "ok": int(success_count),
            "failed": int(total) - int(success_count),
            "updated_at": time.time(),
            "eta_sec": 0,
        }
    )
    _write(payload, output_root)
    print(
        f"[DATASET] COMPLETE {success_count}/{total} succeeded | progress file: {path}",
        flush=True,
    )


def _write(payload: dict, output_root: Path) -> None:
    path = _progress_path(output_root)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _format_eta(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    sec = int(max(seconds, 0))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"
