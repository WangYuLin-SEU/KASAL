# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# Best-effort X11 helpers for Polyscope/GLFW windows on Linux (icon, maximize).

from __future__ import annotations

import array
import ctypes
import ctypes.util
import sys
from typing import Callable

import numpy as np

_X11 = None
_Display = ctypes.c_void_p
_Window = ctypes.c_ulong


def _x11_lib():
    global _X11
    if _X11 is not None:
        return _X11
    if not sys.platform.startswith("linux"):
        return None
    lib_path = ctypes.util.find_library("X11")
    if not lib_path:
        return None
    x11 = ctypes.CDLL(lib_path)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = _Display
    x11.XCloseDisplay.argtypes = [_Display]
    x11.XDefaultRootWindow.argtypes = [_Display]
    x11.XDefaultRootWindow.restype = _Window
    x11.XInternAtom.argtypes = [_Display, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XFetchName.argtypes = [_Display, _Window, ctypes.POINTER(ctypes.c_char_p)]
    x11.XFetchName.restype = ctypes.c_int
    x11.XFree.argtypes = [ctypes.c_void_p]
    x11.XQueryTree.argtypes = [
        _Display,
        _Window,
        ctypes.POINTER(_Window),
        ctypes.POINTER(_Window),
        ctypes.POINTER(ctypes.POINTER(_Window)),
        ctypes.POINTER(ctypes.c_uint),
    ]
    x11.XQueryTree.restype = ctypes.c_int
    x11.XGetWindowProperty.argtypes = [
        _Display,
        _Window,
        ctypes.c_ulong,
        ctypes.c_long,
        ctypes.c_long,
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    x11.XGetWindowProperty.restype = ctypes.c_int
    x11.XChangeProperty.argtypes = [
        _Display,
        _Window,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    x11.XChangeProperty.restype = ctypes.c_int
    x11.XSendEvent.argtypes = [
        _Display,
        _Window,
        ctypes.c_int,
        ctypes.c_long,
        ctypes.c_void_p,
    ]
    x11.XSendEvent.restype = ctypes.c_int
    x11.XFlush.argtypes = [_Display]
    _X11 = x11
    return x11


def _window_titles(display, window_id: int, x11) -> list[str]:
    titles: list[str] = []
    name_ptr = ctypes.c_char_p()
    if x11.XFetchName(display, window_id, ctypes.byref(name_ptr)) and name_ptr.value:
        titles.append(name_ptr.value.decode("utf-8", errors="replace"))
        x11.XFree(name_ptr)

    atom_net_wm_name = x11.XInternAtom(display, b"_NET_WM_NAME", True)
    atom_utf8_string = x11.XInternAtom(display, b"UTF8_STRING", True)
    if atom_net_wm_name and atom_utf8_string:
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop_ptr = ctypes.c_void_p()
        if (
            x11.XGetWindowProperty(
                display,
                window_id,
                atom_net_wm_name,
                0,
                1_048_576,
                False,
                atom_utf8_string,
                ctypes.byref(actual_type),
                ctypes.byref(actual_format),
                ctypes.byref(nitems),
                ctypes.byref(bytes_after),
                ctypes.byref(prop_ptr),
            )
            == 0
            and prop_ptr.value
            and nitems.value
        ):
            raw = ctypes.string_at(prop_ptr.value, nitems.value)
            titles.append(raw.decode("utf-8", errors="replace").rstrip("\0"))
            x11.XFree(prop_ptr)
    return titles


def _visit_window_tree(display, window_id: int, x11, visit: Callable[[int], None]) -> None:
    visit(window_id)
    root_return = _Window()
    parent_return = _Window()
    children = ctypes.POINTER(_Window)()
    child_count = ctypes.c_uint()
    if not x11.XQueryTree(
        display,
        window_id,
        ctypes.byref(root_return),
        ctypes.byref(parent_return),
        ctypes.byref(children),
        ctypes.byref(child_count),
    ):
        return
    try:
        for index in range(child_count.value):
            _visit_window_tree(display, children[index], x11, visit)
    finally:
        if children:
            x11.XFree(children)


def find_window_by_title(title: str) -> int:
    x11 = _x11_lib()
    if not x11 or not title:
        return 0

    display = x11.XOpenDisplay(None)
    if not display:
        return 0

    matched = 0

    def visit(window_id: int) -> None:
        nonlocal matched
        if matched:
            return
        for window_title in _window_titles(display, window_id, x11):
            if window_title == title:
                matched = window_id
                return

    try:
        root_window = x11.XDefaultRootWindow(display)
        _visit_window_tree(display, root_window, x11, visit)
        return matched
    finally:
        x11.XCloseDisplay(display)


def _with_window_by_title(title: str, action: Callable[[object, int, object], bool]) -> bool:
    x11 = _x11_lib()
    if not x11 or not title:
        return False

    display = x11.XOpenDisplay(None)
    if not display:
        return False

    matched = 0

    def visit(window_id: int) -> None:
        nonlocal matched
        if matched:
            return
        for window_title in _window_titles(display, window_id, x11):
            if window_title == title:
                matched = window_id
                return

    try:
        root_window = x11.XDefaultRootWindow(display)
        _visit_window_tree(display, root_window, x11, visit)
        if not matched:
            return False
        ok = action(display, matched, x11)
        if ok:
            x11.XFlush(display)
        return ok
    except Exception:
        return False
    finally:
        x11.XCloseDisplay(display)


def _build_net_wm_icon_property(icon_images: list[np.ndarray]) -> array.array:
    data = array.array("I")
    for rgba in icon_images:
        height, width = rgba.shape[:2]
        data.append(width)
        data.append(height)
        flat = rgba.reshape(-1, 4)
        for red, green, blue, alpha in flat:
            data.append(
                (int(alpha) << 24)
                | (int(red) << 16)
                | (int(green) << 8)
                | int(blue)
            )
    return data


def set_window_icon_by_title(title: str, icon_images: list[np.ndarray]) -> bool:
    if not icon_images:
        return False

    def apply(display, window_id: int, x11) -> bool:
        atom_wm_icon = x11.XInternAtom(display, b"_NET_WM_ICON", False)
        atom_cardinal = x11.XInternAtom(display, b"CARDINAL", False)
        icon_property = _build_net_wm_icon_property(icon_images)
        icon_buffer = (ctypes.c_uint32 * len(icon_property))(*icon_property)
        return (
            x11.XChangeProperty(
                display,
                window_id,
                atom_wm_icon,
                atom_cardinal,
                32,
                0,
                ctypes.cast(icon_buffer, ctypes.c_void_p),
                len(icon_property),
            )
            == 0
        )

    return _with_window_by_title(title, apply)


def maximize_window_by_title(title: str) -> bool:
    """Request EWMH maximize on the Polyscope window (X11 / XWayland)."""

    class _XClientMessageEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_int),
            ("serial", ctypes.c_ulong),
            ("send_event", ctypes.c_int),
            ("display", _Display),
            ("window", _Window),
            ("message_type", ctypes.c_ulong),
            ("format", ctypes.c_int),
            ("data", ctypes.c_long * 5),
        ]

    def apply(display, window_id: int, x11) -> bool:
        atom_wm_state = x11.XInternAtom(display, b"_NET_WM_STATE", False)
        atom_wm_state_add = x11.XInternAtom(display, b"_NET_WM_STATE_ADD", False)
        atom_max_horz = x11.XInternAtom(display, b"_NET_WM_STATE_MAXIMIZED_HORZ", False)
        atom_max_vert = x11.XInternAtom(display, b"_NET_WM_STATE_MAXIMIZED_VERT", False)
        if not atom_wm_state or not atom_wm_state_add:
            return False

        event = _XClientMessageEvent()
        event.type = 33  # ClientMessage
        event.send_event = 1
        event.display = display
        event.window = window_id
        event.message_type = atom_wm_state
        event.format = 32
        event.data[0] = atom_wm_state_add
        event.data[1] = atom_max_horz
        event.data[2] = atom_max_vert
        event.data[3] = 0
        event.data[4] = 0

        root_window = x11.XDefaultRootWindow(display)
        mask = (1 << 0) | (1 << 19)  # SubstructureRedirectMask | SubstructureNotifyMask
        return bool(
            x11.XSendEvent(
                display,
                root_window,
                False,
                mask,
                ctypes.byref(event),
            )
        )

    return _with_window_by_title(title, apply)
