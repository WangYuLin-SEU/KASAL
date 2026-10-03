# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# OS-native folder picker (Polyscope/ImGui has no directory dialog API).

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _normalize_dir(path: str | None) -> str | None:
    if path and os.path.isdir(path):
        return os.path.abspath(path)
    return None


def _pick_via_tkinter(*, title: str, initial_dir: str | None) -> str | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    opts: dict = {"title": title, "mustexist": True}
    if initial_dir:
        opts["initialdir"] = initial_dir
    path = filedialog.askdirectory(**opts)
    root.update()
    root.destroy()
    return os.path.abspath(path) if path else None


def _pick_via_zenity(*, title: str, initial_dir: str | None) -> str | None:
    if not shutil.which("zenity"):
        return None
    cmd = ["zenity", "--file-selection", "--directory", "--title", title]
    if initial_dir:
        cmd.extend(["--filename", initial_dir + os.sep])
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=600)
    except Exception:
        return None
    path = out.strip()
    return os.path.abspath(path) if path and os.path.isdir(path) else None


def _pick_via_kdialog(*, title: str, initial_dir: str | None) -> str | None:
    if not shutil.which("kdialog"):
        return None
    start_dir = initial_dir or os.path.expanduser("~")
    cmd = ["kdialog", "--getexistingdirectory", start_dir, "--title", title]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=600)
    except Exception:
        return None
    path = out.strip()
    return os.path.abspath(path) if path and os.path.isdir(path) else None


def pick_dataset_folder(
    *,
    title: str = "Select dataset folder (PLY/OBJ)",
    initial_dir: str | None = None,
) -> str | None:
    """Return an absolute folder path, or None if the user cancelled."""

    initial = _normalize_dir(initial_dir)
    backends: list[tuple[str, object]] = []

    if sys.platform.startswith("linux"):
        backends.extend(
            [
                ("zenity", _pick_via_zenity),
                ("kdialog", _pick_via_kdialog),
                ("tkinter", _pick_via_tkinter),
            ]
        )
    else:
        backends.append(("tkinter", _pick_via_tkinter))

    errors: list[str] = []
    for name, picker in backends:
        if name in ("zenity", "kdialog") and not shutil.which(name):
            continue
        try:
            return picker(title=title, initial_dir=initial)
        except Exception as exc:
            errors.append("%s: %s" % (name, exc))

    if errors:
        print(
            "[KASAL WARNING] Folder picker unavailable (%s)."
            % "; ".join(errors),
            file=sys.stderr,
        )
        if sys.platform.startswith("linux"):
            print(
                "[KASAL WARNING] On Linux install one of: python3-tk, zenity, kdialog.",
                file=sys.stderr,
            )
    return None
