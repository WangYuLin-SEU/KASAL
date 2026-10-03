# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# OS-native CJK UI font discovery for Polyscope / ImGui.

from __future__ import annotations

import os
import subprocess
import sys

_UI_FONT_ENV = "KASAL_UI_FONT"

_WINDOWS_CJK_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\Deng.ttf",
)

_LINUX_CJK_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/truetype/arphic/ukai.ttc",
    os.path.expanduser("~/.local/share/fonts/NotoSansCJK-Regular.ttc"),
    os.path.expanduser("~/.fonts/NotoSansCJK-Regular.ttc"),
)

_DARWIN_CJK_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
)

_FC_LIST_PREFERRED_KEYWORDS = (
    "noto sans cjk",
    "noto serif cjk",
    "source han sans",
    "source han serif",
    "wqy microhei",
    "wqy zenhei",
    "wenquanyi",
    "droid sans fallback",
    "ar pl uming",
    "ar pl ukai",
)


def _platform_font_candidates() -> tuple[str, ...]:
    if sys.platform == "win32":
        return _WINDOWS_CJK_FONT_CANDIDATES
    if sys.platform.startswith("linux"):
        return _LINUX_CJK_FONT_CANDIDATES
    if sys.platform == "darwin":
        return _DARWIN_CJK_FONT_CANDIDATES
    return ()


def _find_cjk_font_via_fontconfig() -> str | None:
    """Linux fontconfig lookup for any CJK-capable font file."""

    if not sys.platform.startswith("linux"):
        return None
    try:
        out = subprocess.check_output(
            ["fc-list", ":lang=zh", "file"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4,
        )
    except Exception:
        return None

    parsed: list[str] = []
    for line in out.splitlines():
        text = line.strip()
        if not text:
            continue
        path = text.split(":", 1)[0].strip()
        if path and os.path.isfile(path):
            parsed.append(path)

    lowered = [(path, path.lower()) for path in parsed]
    for keyword in _FC_LIST_PREFERRED_KEYWORDS:
        for path, path_lower in lowered:
            if keyword in path_lower:
                return path
    return parsed[0] if parsed else None


def find_cjk_ui_font_path() -> str | None:
    """Return the first usable CJK font path for Chinese UI mode."""

    env_font = os.environ.get(_UI_FONT_ENV, "").strip()
    if env_font and os.path.isfile(env_font):
        return env_font

    for path in _platform_font_candidates():
        if path and os.path.isfile(path):
            return path

    return _find_cjk_font_via_fontconfig()
