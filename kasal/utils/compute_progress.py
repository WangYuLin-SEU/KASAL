# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Progress state for GUI modal + terminal during long symmetry jobs.

from __future__ import annotations

import sys
import threading

import kasal.config.config as config
from kasal.utils.console_io import (
    clear_terminal_carriage_line,
    configure_stdio_utf8,
    write_terminal_carriage_line,
)

PROGRESS_POPUP_ID = "KASAL Computing##progress"

_TERMINAL_STAGE_LABELS = {
    "init": "Starting",
    "done": "Complete",
    "preprocess": "Preprocess",
    "cal_sym": "Axis localization",
    "analyze": "Symmetry analysis",
    "axis_search": "Axis search",
    "classify": "Classify",
    "texture": "Texture refine",
    "export": "Export",
    "save": "Save",
}


class ComputeProgress:
    """Tracks per-object compute stage for UI and terminal feedback."""

    def __init__(self) -> None:
        self.active = False
        self.object_index = 0
        self.object_total = 1
        self.mesh_name = ""
        self.engine = ""
        self.stage_key = ""
        self.stage_label = ""
        self.detail = ""
        self.fraction = 0.0
        self.indeterminate = False
        self._display_percent = 0
        self._last_terminal_len = 0
        self._lock = threading.Lock()

    def begin_object(
        self,
        mesh_name: str,
        *,
        object_index: int = 1,
        object_total: int = 1,
        engine: str = "kasalv2",
    ) -> None:
        self.active = True
        self.object_index = int(object_index)
        self.object_total = int(object_total)
        self.mesh_name = mesh_name
        self.engine = engine
        with self._lock:
            self.fraction = 0.0
            self._display_percent = 0
        self.set_stage("init", "Starting...", fraction=0.05, indeterminate=False)
        self.pulse()

    def end_object(self, *, success: bool = True) -> None:
        label = "Complete" if success else "Failed"
        self.set_stage("done", label, fraction=1.0, indeterminate=False)
        self.detail = label
        self.pulse()
        self.active = False
        self.pulse()
        self._clear_terminal_line()

    def set_stage(
        self,
        key: str,
        label: str,
        *,
        fraction: float | None = None,
        detail: str = "",
        indeterminate: bool = False,
    ) -> None:
        with self._lock:
            self.stage_key = key
            self.stage_label = label
            if detail:
                self.detail = detail
            if fraction is not None:
                self.fraction = max(self.fraction, max(0.0, min(1.0, float(fraction))))
                pct = int(round(self.fraction * 100.0))
                self._display_percent = max(self._display_percent, pct)
            self.indeterminate = indeterminate
        _emit_ipc_progress(self)

    def display_fraction(self) -> float:
        with self._lock:
            return self.fraction

    def display_percent(self) -> int:
        """Integer percent for UI; never decreases within one compute job."""
        with self._lock:
            pct = int(round(self.fraction * 100.0))
            self._display_percent = max(self._display_percent, pct)
            return self._display_percent

    def pulse(self) -> None:
        self._write_terminal()
        # UI reads pg.active each frame on the main thread; no frame_tick from workers.

    def _terminal_stage_label(self) -> str:
        key = (self.stage_key or "").strip()
        if key == "done" and self.stage_label == "Failed":
            return "Failed"
        label = _TERMINAL_STAGE_LABELS.get(key)
        if label:
            return label
        ascii_label = self.stage_label.encode("ascii", "replace").decode("ascii").strip()
        return ascii_label or key or "Working"

    def _terminal_mesh_name(self) -> str:
        name = self.mesh_name or ""
        if name.isascii():
            return name
        return name.encode("ascii", "replace").decode("ascii")

    def _write_terminal(self) -> None:
        if not self.active:
            return
        configure_stdio_utf8()
        pct = self.display_percent()
        frac = pct / 100.0
        width = 36
        filled = int(width * frac)
        head = min(filled, width - 1)
        tail = width - head - 1
        bar = ("=" * head) + (">" if head < width else "") + (" " * max(tail, 0))
        obj = ""
        if self.object_total > 1:
            obj = " obj %d/%d" % (self.object_index, self.object_total)
        line = "[KASAL]%s [%s] %3.0f%% | %s | %s" % (
            obj,
            bar,
            float(pct),
            self._terminal_stage_label(),
            self._terminal_mesh_name(),
        )
        self._last_terminal_len = write_terminal_carriage_line(
            sys.stderr,
            line,
            last_width=self._last_terminal_len,
        )

    def clear_terminal(self) -> None:
        """Clear the in-place stderr progress line before normal log output."""

        self._clear_terminal_line()

    def _clear_terminal_line(self) -> None:
        clear_terminal_carriage_line(sys.stderr, last_width=self._last_terminal_len)
        self._last_terminal_len = 0


_progress = ComputeProgress()
_ipc_queue = None


def get_compute_progress() -> ComputeProgress:
    return _progress


def progress_reporting_enabled() -> bool:
    """True in GUI (active modal) or worker subprocess (IPC queue attached)."""

    return _progress.active or _ipc_queue is not None


def set_progress_ipc_queue(queue) -> None:
    """Worker subprocess: forward stage updates to the GUI process."""

    global _ipc_queue
    _ipc_queue = queue


def clear_progress_ipc_queue() -> None:
    global _ipc_queue
    _ipc_queue = None


def _emit_ipc_progress(state: ComputeProgress) -> None:
    if _ipc_queue is None:
        return
    try:
        _ipc_queue.put_nowait(
            (
                "progress",
                {
                    "key": state.stage_key,
                    "label": state.stage_label,
                    "detail": state.detail,
                    "fraction": state.fraction,
                    "mesh_name": state.mesh_name,
                    "object_index": state.object_index,
                    "object_total": state.object_total,
                    "engine": state.engine,
                },
            )
        )
    except Exception:
        pass


def apply_remote_progress(data: dict) -> None:
    """GUI process: apply a progress snapshot from the worker queue."""

    pg = _progress
    if data.get("mesh_name"):
        pg.mesh_name = data["mesh_name"]
    if data.get("engine"):
        pg.engine = data["engine"]
    if data.get("object_index") is not None:
        pg.object_index = int(data["object_index"])
    if data.get("object_total") is not None:
        pg.object_total = int(data["object_total"])
    pg.set_stage(
        data.get("key", ""),
        data.get("label", ""),
        fraction=data.get("fraction"),
        detail=data.get("detail", ""),
    )


def progress_pulse() -> None:
    _progress.pulse()
