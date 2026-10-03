# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Torch device enumeration and resolution for kasalv2 engine.

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TorchDeviceOption:
    """One selectable compute device (CPU or CUDA GPU)."""

    device_id: str
    label: str


@dataclass(frozen=True)
class HardwareDeviceRow:
    """One row for the detected-hardware table in the GUI."""

    device_type: str
    model_name: str
    status: str
    muted: bool = False


GPU_INSTALL_CMD = "python scripts/install_deps.py full-gpu"
GPU_INSTALL_DOC = "https://github.com/WangYuLin-SEU/KASAL/blob/kasalv2/docs/install.md"


def _short_model_name(name: str, *, max_len: int = 56) -> str:
    text = " ".join((name or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _cpu_model_name() -> str:
    """Best-effort CPU marketing name on Windows / Linux / macOS."""

    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            if name and str(name).strip():
                return _short_model_name(str(name).strip())
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "name"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            lines = [
                ln.strip()
                for ln in out.splitlines()
                if ln.strip() and ln.strip().lower() != "name"
            ]
            if lines:
                return _short_model_name(lines[0])
        except Exception:
            pass

    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
            )
            if out.strip():
                return _short_model_name(out.strip())
        except Exception:
            pass

    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return _short_model_name(line.split(":", 1)[1].strip())
    except Exception:
        pass

    proc = platform.processor()
    if proc and proc.strip():
        return _short_model_name(proc.strip())
    return platform.machine() or "Unknown CPU"


def torch_cuda_runtime_available() -> bool:
    """True when the installed PyTorch build can use CUDA at runtime."""

    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def detect_hardware_nvidia_gpus() -> List[str]:
    """NVIDIA GPU model names visible to the OS (independent of PyTorch build)."""

    names: List[str] = []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "-L"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in out.splitlines():
            text = line.strip()
            if not text.startswith("GPU "):
                continue
            # "GPU 0: NVIDIA GeForce ... (UUID: ...)"
            if ":" in text:
                part = text.split(":", 1)[1].strip()
                if "(" in part:
                    part = part.split("(", 1)[0].strip()
                if part:
                    names.append(_short_model_name(part))
    except Exception:
        pass

    if names:
        return names

    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in out.splitlines():
                text = line.strip()
                if not text or text.lower() == "name":
                    continue
                if "nvidia" in text.lower():
                    names.append(_short_model_name(text))
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            out = subprocess.check_output(
                ["lspci", "-nn"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
            )
            for line in out.splitlines():
                text = line.strip()
                lower = text.lower()
                if "nvidia" not in lower and "10de:" not in lower:
                    continue
                if ":" not in text:
                    continue
                part = text.split(":", 2)[-1].strip()
                if "[" in part:
                    part = part.split("[", 1)[0].strip()
                if part:
                    names.append(_short_model_name(part))
        except Exception:
            pass
    return names


def _gpu_model_names() -> List[str]:
    """CUDA GPU names via PyTorch; only when the runtime build supports CUDA."""

    if not torch_cuda_runtime_available():
        return []
    names: List[str] = []
    try:
        import torch

        count = int(torch.cuda.device_count())
        for index in range(count):
            try:
                names.append(_short_model_name(torch.cuda.get_device_name(index)))
            except Exception:
                names.append("CUDA device %d" % index)
    except Exception:
        pass
    return names


def list_hardware_device_rows(
    selected_device_id: str | None = None,
) -> List[HardwareDeviceRow]:
    """Rows for the detected CPU/GPU table (Type | Model | Status)."""

    selected = normalize_device_id(selected_device_id) if selected_device_id else None
    rows: List[HardwareDeviceRow] = []

    cpu_status = "Selected" if selected == "cpu" else "Available"
    rows.append(
        HardwareDeviceRow("CPU", _cpu_model_name(), cpu_status, muted=False)
    )

    if torch_cuda_runtime_available():
        gpu_models = _gpu_model_names()
        if not gpu_models:
            rows.append(
                HardwareDeviceRow(
                    "GPU",
                    "(none detected by PyTorch CUDA)",
                    "—",
                    muted=True,
                )
            )
        else:
            for index, model in enumerate(gpu_models):
                device_id = "cuda:%d" % index
                status = "Selected" if selected == device_id else "Available"
                rows.append(
                    HardwareDeviceRow(
                        "GPU %d" % index,
                        model,
                        status,
                        muted=False,
                    )
                )
    else:
        hardware = detect_hardware_nvidia_gpus()
        if not hardware:
            rows.append(
                HardwareDeviceRow("GPU", "(none detected)", "—", muted=True)
            )
        else:
            for index, model in enumerate(hardware):
                rows.append(
                    HardwareDeviceRow(
                        "GPU %d" % index,
                        model,
                        "Not selectable (CPU-only PyTorch)",
                        muted=True,
                    )
                )
    return rows


def list_torch_device_options() -> List[TorchDeviceOption]:
    """Scan this machine for CPU and CUDA GPUs with model names."""

    cpu_model = _cpu_model_name()
    options: List[TorchDeviceOption] = [
        TorchDeviceOption("cpu", "CPU: %s" % cpu_model)
    ]
    for index, model in enumerate(_gpu_model_names()):
        options.append(
            TorchDeviceOption(
                "cuda:%d" % index,
                "GPU %d: %s" % (index, model),
            )
        )
    return options


def _cuda_index_available(index: int) -> bool:
    try:
        import torch

        return torch.cuda.is_available() and index < int(torch.cuda.device_count())
    except Exception:
        return False


def normalize_device_id(raw: str | None, *, default: str = "cpu", strict: bool = False) -> str:
    """Return a usable device id, optionally rejecting an unavailable explicit choice."""

    if raw is not None and not isinstance(raw, str):
        if strict:
            raise ValueError(f"Invalid torch device id: {raw!r}")
        return "cpu"
    text = (raw or "").strip().lower()
    if not text:
        text = default.strip().lower()
    if text == "cpu":
        return "cpu"
    if text == "cuda":
        index = 0
    elif text.startswith("cuda:"):
        try:
            index = int(text.split(":", 1)[1])
        except (TypeError, ValueError):
            if strict:
                raise ValueError(f"Invalid torch device id: {raw!r}")
            return "cpu"
        if index < 0:
            if strict:
                raise ValueError(f"Invalid torch device id: {raw!r}")
            return "cpu"
    else:
        if strict:
            raise ValueError(f"Invalid torch device id: {raw!r}")
        return "cpu"

    canonical = f"cuda:{index}"
    if _cuda_index_available(index):
        return canonical
    if strict:
        raise ValueError(f"Requested torch device is unavailable: {canonical}")
    return "cpu"


def device_option_label(device_id: str, options: List[TorchDeviceOption] | None = None) -> str:
    """Human-readable label for a device id."""

    for opt in options or list_torch_device_options():
        if opt.device_id == device_id:
            return opt.label
    return device_id or "CPU"


def apply_torch_device_choice(device_id: str, *, strict: bool = True) -> str:
    """Persist GUI choice to config and ``KASAL_TORCH_DEVICE`` env (for subprocess workers)."""

    canonical = normalize_device_id(device_id, strict=strict)
    try:
        import kasal.config.runtime as config

        config.torch_device_id = canonical
    except ImportError:
        pass
    os.environ["KASAL_TORCH_DEVICE"] = canonical
    return canonical


def resolve_torch_device(prefer: str = "cuda") -> str:
    """Resolve torch device from env, GUI config, or preference."""

    env = os.environ.get("KASAL_TORCH_DEVICE", "").strip()
    if env:
        return normalize_device_id(env, default=prefer, strict=True)

    try:
        import kasal.config.runtime as config

        gui = getattr(config, "torch_device_id", "") or ""
        if gui:
            return normalize_device_id(gui, default=prefer, strict=True)
    except ImportError:
        pass

    prefer_norm = normalize_device_id(prefer, default="cpu")
    return prefer_norm
