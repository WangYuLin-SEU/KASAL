# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# UTF-8 console helpers for terminal progress / logs (Windows + Linux).

from __future__ import annotations

import sys
import unicodedata

_STDIO_UTF8_CONFIGURED = False


def configure_stdio_utf8() -> None:
    """Best-effort UTF-8 for stdout/stderr (fixes Chinese mojibake on Windows)."""

    global _STDIO_UTF8_CONFIGURED
    if _STDIO_UTF8_CONFIGURED:
        return
    _STDIO_UTF8_CONFIGURED = True

    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def terminal_display_width(text: str) -> int:
    """Return terminal column width (CJK counts as 2)."""

    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        east = unicodedata.east_asian_width(char)
        if east in ("F", "W"):
            width += 2
        elif east == "A" and ord(char) > 127:
            width += 2
        else:
            width += 1
    return width


def write_terminal_carriage_line(
    stream,
    line: str,
    *,
    last_width: int = 0,
) -> int:
    """Overwrite the current terminal line in-place; return new display width."""

    configure_stdio_utf8()
    pad = max(last_width - terminal_display_width(line), 0)
    payload = "\r" + line + (" " * pad)
    try:
        stream.write(payload)
        stream.flush()
    except Exception:
        return last_width
    return terminal_display_width(line)


def clear_terminal_carriage_line(stream, *, last_width: int) -> None:
    if last_width <= 0:
        return
    try:
        stream.write("\r" + (" " * last_width) + "\r")
        stream.flush()
    except Exception:
        pass
