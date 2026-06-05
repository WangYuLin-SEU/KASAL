# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

try:
    import win32gui, win32con, win32api

    _WIN32_ICON_AVAILABLE = True
except ImportError:
    _WIN32_ICON_AVAILABLE = False
import math
import os, sys, cv2
import multiprocessing as mp
import queue
from datetime import datetime
import numpy as np
import kasal.config.config as config
# from config.config import is_true2, is_true3, ui_int, ui_options, ui_options_selected, \
#     ui_xyz_options, ui_xyz_options_selected, files_name_list, current_file_id, \
#         psm_list, uv_texture_size, ui_int_upper, targetfacenum, sample_num, current_obj_info, \
#             arrow_ratio, save_2_fold_a, close_ADI_c, start_id_json_file
from kasal.utils.io_json import load_json2dict, save_symmetry_type, load_symmetry_type, get_all_ply_obj
from kasal.utils.load_obj import OBJ
from kasal.utils.io_ply import save_ply_model
from kasal.utils.annotation_state import (
    clear_all_dataset_annotations,
    count_annotation_artifacts,
    dirty_object_ids,
    saved_object_ids,
    initialize_dataset_dirty_state,
    mark_all_dirty,
    mark_object_dirty,
    sync_dirty_for_current_object,
)
from kasal.utils.io_ply_meshlab import is_pymeshlab_available
from kasal.utils.folder_picker import pick_dataset_folder
from kasal.utils.linux_x11 import maximize_window_by_title, set_window_icon_by_title
from kasal.utils.ui_font import find_cjk_ui_font_path
from kasal.device import (
    TorchDeviceOption,
    apply_torch_device_choice,
    device_option_label,
    list_hardware_device_rows,
    list_torch_device_options,
    normalize_device_id,
    resolve_torch_device,
    torch_cuda_runtime_available,
)
from kasal.compute.symmetry_job import (
    SymmetryJobSpec,
    apply_job_result_to_config,
)
from kasal.engine_routing import engine_speed_hint, kasalv1_usage_hint
from kasal.app.ui_strings import (
    UI_LANG_EN,
    UI_LANG_ZH,
    batch_status_progress_text,
    batch_status_skip_text,
    batch_status_text,
    cleared_labels_status_text,
    cpu_only_build_hint_text,
    cuda_available_hint_text,
    dataset_folder_error_text,
    engine_speed_hint_text,
    gpu_install_hint_text,
    hardware_status_label,
    hardware_table_header,
    kasalv1_block_reason_text,
    kasalv1_usage_hint_text,
    preprocess_policy_label_text,
    preprocess_policy_option_text,
    sym_type_option_label,
    symmetry_routing_note_text,
    tr,
)
from kasal.compute.symmetry_worker import mp_symmetry_worker_entry
from kasal.utils.compute_progress import PROGRESS_POPUP_ID, apply_remote_progress, get_compute_progress
from kasal.utils.console_io import configure_stdio_utf8
from kasal.version_names import normalize_preprocess_policy
from kasal.datasets.datasets_path import arrow_xyz_path, icon_path, icon_png_path

ICON_SHOW = _WIN32_ICON_AVAILABLE or sys.platform.startswith("linux")
_ICON_STANDARD_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

import pymeshlab as ml
import polyscope
import polyscope.imgui as psim

polyscope.set_verbosity(0)
polyscope.set_max_fps(33)
polyscope.set_program_name("Key-Axis-based Symmetry Axis Localization")
mesh = ml.MeshSet()
_imgui_ui_font = None
_imgui_polyscope_default_font = None

_UI_FONT_BASE_PT = 15.0
_UI_FONT_SCALE_DEFAULT = 1.2
_UI_FONT_SCALE_MIN = 0.8
_UI_FONT_SCALE_MAX = 1.5
_UI_FONT_SCALE_STEP = 0.05

def _find_ui_font_path():
    return find_cjk_ui_font_path()


def _collect_ui_cjk_probe_text() -> str:
    """Unique non-ASCII codepoints from localized UI strings (imgui 1.92 glyph warm-up)."""

    from kasal.app.ui_strings import _STRINGS, _SYM_TYPE_LABELS

    chars: set[str] = set()
    for table in (_STRINGS, _SYM_TYPE_LABELS):
        for entry in table.values():
            for text in entry.values():
                for ch in str(text):
                    if ord(ch) > 127:
                        chars.add(ch)
    return "".join(sorted(chars))


def _prewarm_cjk_font_glyphs() -> None:
    if _imgui_ui_font is None or not hasattr(psim, "CalcTextSize"):
        return
    probe = _collect_ui_cjk_probe_text()
    if not probe:
        return
    try:
        io = psim.GetIO()
        prev_default = io.FontDefault
        io.FontDefault = _imgui_ui_font
        psim.CalcTextSize(probe)
        io.FontDefault = prev_default
    except Exception:
        pass


def _load_imgui_ui_font():
    """Load a CJK-capable font and keep Polyscope's original default for English mode."""

    global _imgui_ui_font, _imgui_polyscope_default_font
    if not hasattr(psim.ImFontAtlas, "Build"):
        print(
            "[KASAL WARNING] Polyscope is too old to load CJK UI glyphs; "
            "Chinese labels will show as squares. Fix: "
            "python -m pip install --upgrade polyscope==2.6.1 "
            "(or: python scripts/install_deps.py gui from KASAL/)"
        )
        return
    font_path = _find_ui_font_path()
    if not font_path:
        print("[KASAL WARNING] No CJK UI font found; Chinese UI may render as question marks.")
        return
    try:
        io = psim.GetIO()
        _imgui_polyscope_default_font = io.FontDefault or psim.GetFont()
        font = io.Fonts.AddFontFromFileTTF(font_path, _UI_FONT_BASE_PT)
        if font is not None:
            if hasattr(io.Fonts, "Build"):
                io.Fonts.Build()
            _imgui_ui_font = font
            _prewarm_cjk_font_glyphs()
            print("[KASAL] Loaded UI font: %s" % font_path)
    except Exception as exc:
        _imgui_ui_font = None
        print("[KASAL WARNING] Failed to load UI font %s: %s" % (font_path, exc))


def _clamp_ui_font_scale(scale: float) -> float:
    return max(_UI_FONT_SCALE_MIN, min(_UI_FONT_SCALE_MAX, float(scale)))


def _apply_ui_font_scale() -> None:
    """Apply persisted UI scale to ImGui (Polyscope 2.6 defaults FontScaleMain to ~1.5)."""

    psim.GetStyle().FontScaleMain = _clamp_ui_font_scale(
        getattr(config, "ui_font_scale", _UI_FONT_SCALE_DEFAULT)
    )


def _apply_ui_font_for_language() -> None:
    """Switch ImGui default font so every widget uses CJK glyphs in Chinese mode."""

    io = psim.GetIO()
    if config.ui_language == UI_LANG_ZH and _imgui_ui_font is not None:
        io.FontDefault = _imgui_ui_font
        return
    if _imgui_polyscope_default_font is not None:
        io.FontDefault = _imgui_polyscope_default_font
    else:
        io.FontDefault = psim.GetFont()


def _render_ui_font_scale_slider() -> None:
    """Setup control for global interface text scale."""

    scale = _clamp_ui_font_scale(getattr(config, "ui_font_scale", _UI_FONT_SCALE_DEFAULT))
    psim.TextUnformatted(tr("setup.font_size"))
    avail = psim.GetContentRegionAvail()
    row_w = max(float(avail[0]), 200.0)
    dec_clicked = _imgui_button("-##font_scale_dec", min_width=30.0)
    psim.SameLine()
    psim.PushItemWidth(max(row_w - 70.0, 130.0))
    changed, scale = psim.DragFloat(
        "##ui_font_scale",
        scale,
        0.01,
        _UI_FONT_SCALE_MIN,
        _UI_FONT_SCALE_MAX,
        "%.2f",
        psim.ImGuiSliderFlags_AlwaysClamp,
    )
    psim.PopItemWidth()
    psim.SameLine()
    inc_clicked = _imgui_button("+##font_scale_inc", min_width=30.0)
    if dec_clicked:
        scale = _clamp_ui_font_scale(scale - _UI_FONT_SCALE_STEP)
        changed = True
    if inc_clicked:
        scale = _clamp_ui_font_scale(scale + _UI_FONT_SCALE_STEP)
        changed = True
    if changed:
        config.ui_font_scale = _clamp_ui_font_scale(scale)
        _apply_ui_font_scale()
    psim.TextWrapped(tr("setup.font_size_hint"))


def _imgui_bool(result):
    return bool(result[0] if isinstance(result, tuple) else result)


def _imgui_begin(name: str, p_open: bool, flags: int = 0) -> bool:
    return _imgui_bool(psim.Begin(name, p_open, flags))


def _imgui_begin_popup_modal(name: str, p_open: bool, flags: int = 0) -> bool:
    return _imgui_bool(psim.BeginPopupModal(name, p_open, flags))


def _imgui_selectable_selected(label: str, selected: bool = False) -> bool:
    result = psim.Selectable(label, selected)
    if isinstance(result, tuple):
        return bool(result[1])
    return bool(result)


def _imgui_font_scale_main() -> float:
    try:
        return float(psim.GetStyle().FontScaleMain)
    except Exception:
        return 1.0


def _imgui_button_size(label: str, min_width: float = 0.0) -> tuple[float, float]:
    """Compute button size from label text so width tracks ui_font_scale / CJK labels."""

    style = psim.GetStyle()
    font_scale = _imgui_font_scale_main()
    pad_x = float(style.FramePadding[0]) * 2.0
    pad_y = float(style.FramePadding[1]) * 2.0
    try:
        text_w, text_h = psim.CalcTextSize(label)
    except Exception:
        text_w, text_h = (0.0, 0.0)
    text_w *= font_scale
    text_h *= font_scale
    width = max(min_width * font_scale, text_w + pad_x * font_scale + 6.0)
    height = text_h + pad_y * font_scale
    return (width, height)


def _imgui_button(label: str, min_width: float = 0.0) -> bool:
    return psim.Button(label, _imgui_button_size(label, min_width=min_width))


def _try_maximize_glfw_window() -> bool:
    try:
        import glfw
    except ImportError:
        return False
    window = glfw.get_current_context()
    if not window:
        return False
    try:
        glfw.maximize_window(window)
        return True
    except Exception:
        return False


def _try_maximize_polyscope_window() -> None:
    """Maximize the main Polyscope window once (platform-specific; screen-size fallback)."""

    global _MAIN_WINDOW_MAXIMIZE_PENDING
    if not _MAIN_WINDOW_MAXIMIZE_PENDING:
        return
    if _WIN32_ICON_AVAILABLE:
        hwnd = win32gui.FindWindow(None, _MAIN_WINDOW_TITLE)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            _MAIN_WINDOW_MAXIMIZE_PENDING = False
            return
    if sys.platform.startswith("linux"):
        if _try_maximize_glfw_window():
            _MAIN_WINDOW_MAXIMIZE_PENDING = False
            return
        if maximize_window_by_title(_MAIN_WINDOW_TITLE):
            _MAIN_WINDOW_MAXIMIZE_PENDING = False
            return
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        polyscope.set_window_size(root.winfo_screenwidth(), root.winfo_screenheight())
        root.destroy()
        _MAIN_WINDOW_MAXIMIZE_PENDING = False
    except Exception:
        pass


def _resolve_icon_png_path() -> str:
    for candidate in (icon_png_path, icon_path.replace(".ico", ".png")):
        if candidate and os.path.isfile(candidate):
            return candidate
    return ""


def _load_icon_source_rgba() -> np.ndarray | None:
    """Load the application icon as an RGBA image (HxWx4 uint8)."""

    png_path = _resolve_icon_png_path()
    if png_path:
        try:
            from PIL import Image

            image = np.asarray(Image.open(png_path).convert("RGBA"), dtype=np.uint8)
            if image.ndim == 3 and image.shape[2] == 4:
                return image
        except Exception:
            image = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
            if image is not None:
                if image.ndim == 2:
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
                elif image.shape[2] == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
                return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)

    if os.path.isfile(icon_path):
        try:
            from PIL import Image

            image = np.asarray(Image.open(icon_path).convert("RGBA"), dtype=np.uint8)
            if image.ndim == 3 and image.shape[2] == 4:
                return image
        except Exception:
            pass

    print(
        "[KASAL WARNING] Icon image not found or unreadable (expected %s or %s)"
        % (icon_png_path, icon_path)
    )
    return None


def _icon_square_canvas(source: np.ndarray) -> np.ndarray:
    height, width = source.shape[:2]
    side = max(width, height)
    canvas = np.zeros((side, side, 4), dtype=np.uint8)
    offset_x = (side - width) // 2
    offset_y = (side - height) // 2
    canvas[offset_y : offset_y + height, offset_x : offset_x + width] = source
    return canvas


def _icon_rgba_scaled(source: np.ndarray, size: int) -> np.ndarray:
    canvas = _icon_square_canvas(source)
    return cv2.resize(canvas, (size, size), interpolation=cv2.INTER_LANCZOS4)


def _icon_rgba_at_standard_sizes() -> list[np.ndarray]:
    """Return square RGBA icons at common taskbar/title-bar sizes."""

    source = _load_icon_source_rgba()
    if source is None:
        return []

    return [_icon_rgba_scaled(source, size) for size in _ICON_STANDARD_SIZES]


def _windows_icon_load_sizes() -> list[tuple[int, int]]:
    sizes = {
        (
            win32api.GetSystemMetrics(win32con.SM_CXSMICON),
            win32api.GetSystemMetrics(win32con.SM_CYSMICON),
        ),
        (
            win32api.GetSystemMetrics(win32con.SM_CXICON),
            win32api.GetSystemMetrics(win32con.SM_CYICON),
        ),
    }
    for side in _ICON_STANDARD_SIZES:
        sizes.add((side, side))
    return sorted(sizes)


def _write_temp_ico_path(source: np.ndarray) -> str | None:
    try:
        from PIL import Image
        import tempfile
    except ImportError:
        return None

    pil = Image.fromarray(_icon_square_canvas(source), "RGBA")
    handle = tempfile.NamedTemporaryFile(suffix=".ico", delete=False)
    try:
        pil.save(handle.name, format="ICO", sizes=_windows_icon_load_sizes())
    except Exception:
        handle.close()
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        return None
    handle.close()
    return handle.name


def _rgba_to_glfw_image(rgba: np.ndarray) -> tuple[int, int, list]:
    height, width = rgba.shape[:2]
    pixels = [
        [[int(rgba[y, x, channel]) for channel in range(4)] for x in range(width)]
        for y in range(height)
    ]
    return (width, height, pixels)


def _set_window_icon_glfw(icon_images: list[np.ndarray]) -> bool:
    """Best-effort GLFW icon path (works when GLFW context is externally visible)."""

    if not icon_images:
        return False
    try:
        import glfw
    except ImportError:
        return False

    window = glfw.get_current_context()
    if not window:
        return False
    try:
        glfw.set_window_icon(
            window,
            [_rgba_to_glfw_image(image) for image in icon_images],
        )
        return True
    except Exception:
        return False


def _set_window_icon_windows() -> bool:
    """Apply the KASAL icon to the main window on Windows (title bar + taskbar)."""

    hwnd = win32gui.FindWindow(None, _MAIN_WINDOW_TITLE)
    if not hwnd:
        return False

    cx_sm = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
    cy_sm = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
    cx_lg = win32api.GetSystemMetrics(win32con.SM_CXICON)
    cy_lg = win32api.GetSystemMetrics(win32con.SM_CYICON)
    load_flags = win32con.LR_LOADFROMFILE

    source_rgba = _load_icon_source_rgba()
    temp_ico_path = _write_temp_ico_path(source_rgba) if source_rgba is not None else None
    ico_load_path = temp_ico_path if temp_ico_path else icon_path
    if not os.path.isfile(ico_load_path):
        print("[KASAL WARNING] Icon file not found: %s" % icon_path)
        return False

    try:
        small_icon = win32gui.LoadImage(
            0, ico_load_path, win32con.IMAGE_ICON, cx_sm, cy_sm, load_flags
        )
        big_icon = win32gui.LoadImage(
            0, ico_load_path, win32con.IMAGE_ICON, cx_lg, cy_lg, load_flags
        )
        if not small_icon and not big_icon:
            fallback = win32gui.LoadImage(
                0,
                ico_load_path,
                win32con.IMAGE_ICON,
                0,
                0,
                load_flags | win32con.LR_DEFAULTSIZE,
            )
            small_icon = big_icon = fallback

        if not small_icon and not big_icon:
            print("[KASAL WARNING] Failed to load icon: %s" % ico_load_path)
            return False

        if small_icon:
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, small_icon)
        if big_icon:
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, big_icon)
        return True
    finally:
        if temp_ico_path:
            try:
                os.unlink(temp_ico_path)
            except OSError:
                pass


def _set_window_icon_linux(icon_images: list[np.ndarray]) -> bool:
    if _set_window_icon_glfw(icon_images):
        return True
    return set_window_icon_by_title(_MAIN_WINDOW_TITLE, icon_images)


def set_window_icon() -> bool:
    """Apply the KASAL icon to the main Polyscope window."""

    if sys.platform == "win32" and _WIN32_ICON_AVAILABLE:
        return _set_window_icon_windows()
    if sys.platform.startswith("linux"):
        return _set_window_icon_linux(_icon_rgba_at_standard_sizes())
    return False


def _try_apply_window_icon() -> None:
    """Apply the window icon once the Polyscope HWND exists (after maximize)."""

    global _MAIN_WINDOW_ICON_PENDING
    if not _MAIN_WINDOW_ICON_PENDING or not ICON_SHOW:
        return
    if _MAIN_WINDOW_MAXIMIZE_PENDING:
        return
    if set_window_icon():
        _MAIN_WINDOW_ICON_PENDING = False

def build_psm(m, mesh_id, input_file, transparency):
    ''' Convert a pymeshlab variable to a polyscope variable.  
    Parameters:  
        m: The object model variable in pymeshlab.  
        mesh_id: The object ID in polyscope (each object in polyscope must have a unique ID).  
        input_file: The path to the object model.  
        transparency: The transparency of the object in polyscope.  
    Returns:  
        psm: The object model variable in polyscope.  
    '''
    
    is_enabled = m.is_visible()
    if m.is_point_cloud():
        psm = polyscope.register_point_cloud(str(mesh_id), m.transformed_vertex_matrix(), enabled=is_enabled, transparency=transparency)
    else:
        psm = polyscope.register_surface_mesh(str(mesh_id), m.transformed_vertex_matrix(), m.face_matrix(), enabled=is_enabled, transparency=transparency)
    if m.has_wedge_tex_coord():
        key_ = list(m.textures().keys())
        polyscope.remove_all_structures()
        obj_ = OBJ(input_file)
        info_ = obj_.faces_material
        ver_uv_face_list = []
        image_list = []
        transparency_list = []
        for info_key_ in info_:
            ver_uv_face = info_[info_key_]
            uv_path_ = os.path.join(os.path.dirname(input_file), info_key_)
            if os.path.exists(uv_path_):
                try:
                    image_ = cv2.cvtColor(cv2.imread(uv_path_), cv2.COLOR_RGB2BGR)
                    transparency_list.append(1)
                except:
                    image_ = np.ones((16,16,3),dtype=np.uint8) * 255
                    image_[:, :, :] = 255
                    transparency_list.append(1.0)
            else:
                image_ = np.ones((16,16,3),dtype=np.uint8) * 255
                image_[:, :, :] = 255 
                transparency_list.append(1.0)
            ver_uv_face_list.append(ver_uv_face)
            image_list.append(image_)
        psm = polyscope.create_group(str(mesh_id))
        psm_i_list = []
        for i_ in range(len(image_list)):
            new_image = image_list[i_]
            ver_uv_face = ver_uv_face_list[i_]
            uv_i_ = np.array(ver_uv_face['uv'])
            uv_i_min = np.min(uv_i_, axis=0)
            uv_i_max = np.max(uv_i_, axis=0)
            uv_i_min_0 = np.array(uv_i_min).astype(np.int64) - 1
            uv_i_max_0 = np.array(uv_i_max).astype(np.int64) + 1
            d_x_ = uv_i_max_0[0] - uv_i_min_0[0]
            d_y_ = uv_i_max_0[1] - uv_i_min_0[1]
            uv_i_[:, 0] = (uv_i_[:, 0] - uv_i_min_0[0]) / d_x_
            uv_i_[:, 1] = (uv_i_[:, 1] - uv_i_min_0[1]) / d_y_
            static_size = 256 * 256
            h_new_image, w_new_image,  = new_image.shape[:2]
            new_image_size = w_new_image * h_new_image
            resize_ratio_ = np.sqrt(static_size / (new_image_size * d_x_ * d_y_))
            if resize_ratio_ > 1: resize_ratio_ = 1
            w_new_image = int(w_new_image*resize_ratio_)
            if w_new_image == 0: 
                w_new_image = 1
                h_new_image = 1
            h_new_image = int(h_new_image*resize_ratio_)
            if h_new_image == 0: 
                w_new_image = 1
                h_new_image = 1
            new_image = cv2.resize(new_image, (w_new_image, h_new_image))
            hh_, ww_ = new_image.shape[0], new_image.shape[1]
            if np.max([hh_, ww_]) == 1:
                uv_i_min = np.min(uv_i_, axis=0)
                uv_i_max = np.max(uv_i_, axis=0)
                uv_i_min_0 = np.array(uv_i_min).astype(np.int64) - 1
                uv_i_max_0 = np.array(uv_i_max).astype(np.int64) + 1
                d_x_ = uv_i_max_0[0] - uv_i_min_0[0]
                d_y_ = uv_i_max_0[1] - uv_i_min_0[1]
                uv_i_[:, 0] = (uv_i_[:, 0] - uv_i_min_0[0]) / d_x_
                uv_i_[:, 1] = (uv_i_[:, 1] - uv_i_min_0[1]) / d_y_
                new_image_big = new_image
            else:
                x_img_l = []
                for jj_ in range(d_x_):
                    x_img_l.append(new_image)
                x_img_l = np.hstack(x_img_l)
                y_img_l = []
                for ii_ in range(d_y_):
                    y_img_l.append(x_img_l)
                new_image_big = np.vstack(y_img_l)
            psm_i = polyscope.register_surface_mesh(str(mesh_id)+'_'+str(i_), 
                                                    m.transformed_vertex_matrix(),
                                                    np.array(ver_uv_face['faces'], dtype=np.int64), 
                                                    enabled=is_enabled, transparency=transparency)
            psm_i.add_parameterization_quantity("vertex_uv_coords", np.array(uv_i_), coords_type='unit',
                                    defined_on='corners', enabled=True)
            new_image_big = np.array(new_image_big, dtype=np.float32) / 255
            psm_i.add_color_quantity("vertex_texture", new_image_big, 
                        defined_on='texture', param_name="vertex_uv_coords", enabled=True)
            psm_i.add_to_group(psm)
            psm_i_list.append(psm_i)
        psm.set_enabled(True)
        psm.set_hide_descendants_from_structure_lists(True)
        psm.set_show_child_details(False)
    elif m.has_vertex_tex_coord():
        v_uv = m.vertex_tex_coord_matrix()
        psm.add_parameterization_quantity("vertex_uv_coords", v_uv, defined_on='vertices', enabled=True)
        key_ = list(m.textures().keys())
        if len(key_) > 1:
            raise ValueError(' The number of textures is not equal to 1! ')
        v_tex = cv2.cvtColor(cv2.imread(os.path.join(os.path.dirname(input_file), key_[0])), cv2.COLOR_RGB2BGR)
        v_tex = cv2.resize(v_tex, (config.uv_texture_size, config.uv_texture_size))
        v_tex = np.array(v_tex, dtype=np.float32) / 255
        psm.add_color_quantity("vertex_texture", v_tex, defined_on='texture', param_name="vertex_uv_coords", enabled=True)
    elif m.has_vertex_scalar():
        psm.add_scalar_quantity('vertex_scalar', m.vertex_scalar_array(),enabled=True)
    elif m.has_vertex_color():
        vc = m.vertex_color_matrix()
        vc = np.delete(vc, 3, 1)
        psm.add_color_quantity('vertex_color', vc, enabled=True)
    elif not m.is_point_cloud() and m.has_face_color() and not m.has_wedge_tex_coord():
        fc = m.face_color_matrix()
        fc = np.delete(fc, 3, 1)
        psm.add_color_quantity('face_color', fc, defined_on='faces',enabled=True)
    elif not m.is_point_cloud() and m.has_face_scalar():
        psm.add_scalar_quantity('face_scalar', m.face_scalar_array(), defined_on='faces',enabled=True)
    return psm   

def last_object_func():
    ''' Load the previous object. '''
    
    mesh.clear()
    save_symmetry_type()
    if config.current_file_id - 1 >= 0:
        config.current_file_id = config.current_file_id - 1
        input_file = config.files_name_list[config.current_file_id]
        mesh.load_new_mesh(input_file)
        mesh_id = mesh.current_mesh_id()
        mesh_id_list = [mesh_id]
        transparency_list = [1.0]
        if config.is_true3:
            mesh_c = mesh.current_mesh()
            bbox = mesh_c.bounding_box()
            center_ = bbox.center()
            dim_0 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()]) * 1.5
            mesh.load_new_mesh(arrow_xyz_path)
            mesh_c = mesh.current_mesh()
            bbox = mesh_c.bounding_box()
            dim_1 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()])
            mesh.compute_matrix_from_translation_rotation_scale(scalex = dim_0 / dim_1,
                                                                scaley = dim_0 / dim_1,
                                                                scalez = dim_0 / dim_1,
                                                                )
            mesh.compute_matrix_from_translation_rotation_scale(translationx = center_[0],
                                                                translationy = center_[1],
                                                                translationz = center_[2],
                                                                )
            mesh_id = mesh.current_mesh_id()
            mesh_id_list.append(mesh_id)
            transparency_list.append(0.3)
        input_sym_file = os.path.join(os.path.dirname(input_file), os.path.basename(input_file).split('.')[0]+'_sym.ply')
        if os.path.exists(input_sym_file):
            mesh.load_new_mesh(input_sym_file)
            mesh_id = mesh.current_mesh_id()
            mesh_id_list.append(mesh_id)
            transparency_list.append(1.0)
        polyscope.remove_all_groups()
        polyscope.remove_all_structures()
        config.psm_list = []
        for (m, mesh_id, transparency) in zip(mesh, mesh_id_list, transparency_list):
            psm = build_psm(m, mesh_id, input_file, transparency)
            config.psm_list.append(psm)
    config.ui_options_selected = config.ui_options[0]    
    config.ui_xyz_options_selected = config.ui_xyz_options[0]   
    config.is_true2 = False
    load_symmetry_type()

def next_object_func():
    ''' Load the next object. '''
    
    mesh.clear()
    save_symmetry_type()
    obj_number = len(config.files_name_list)
    if config.current_file_id + 1 < obj_number:
        config.current_file_id = config.current_file_id + 1
        input_file = config.files_name_list[config.current_file_id]
        mesh.load_new_mesh(input_file)
        mesh_id = mesh.current_mesh_id()
        mesh_id_list = [mesh_id]
        transparency_list = [1.0]
        if config.is_true3:
            mesh_c = mesh.current_mesh()
            bbox = mesh_c.bounding_box()
            center_ = bbox.center()
            dim_0 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()]) * 1.5
            mesh.load_new_mesh(arrow_xyz_path)
            mesh_c = mesh.current_mesh()
            bbox = mesh_c.bounding_box()
            dim_1 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()])
            mesh.compute_matrix_from_translation_rotation_scale(scalex = dim_0 / dim_1,
                                                                scaley = dim_0 / dim_1,
                                                                scalez = dim_0 / dim_1,
                                                                )
            mesh.compute_matrix_from_translation_rotation_scale(translationx = center_[0],
                                                                translationy = center_[1],
                                                                translationz = center_[2],
                                                                )
            mesh_id = mesh.current_mesh_id()
            mesh_id_list.append(mesh_id)
            transparency_list.append(0.3)
        input_sym_file = os.path.join(os.path.dirname(input_file), os.path.basename(input_file).split('.')[0]+'_sym.ply')
        if os.path.exists(input_sym_file):
            mesh.load_new_mesh(input_sym_file)
            mesh_id = mesh.current_mesh_id()
            mesh_id_list.append(mesh_id)
            transparency_list.append(1.0)
        polyscope.remove_all_groups()
        polyscope.remove_all_structures()
        config.psm_list = []
        for (m, mesh_id, transparency) in zip(mesh, mesh_id_list, transparency_list):
            psm = build_psm(m, mesh_id, input_file, transparency)
            config.psm_list.append(psm)
    config.ui_options_selected = config.ui_options[0]
    config.ui_xyz_options_selected = config.ui_xyz_options[0]   
    config.is_true2 = False
    load_symmetry_type()

def reload_object_func():
    ''' Reload the object. When the object's symmetry axis information changes  
        or the XYZ axis display is enabled, the object displayed in polyscope  
        will be updated accordingly.  
    '''
    
    mesh.clear()
    load_symmetry_type()
    input_file = config.files_name_list[config.current_file_id]
    mesh.load_new_mesh(input_file)
    mesh_id = mesh.current_mesh_id()
    mesh_id_list = [mesh_id]
    transparency_list = [1.0]
    if config.is_true3:
        mesh_c = mesh.current_mesh()
        bbox = mesh_c.bounding_box()
        center_ = bbox.center()
        dim_0 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()]) * 1.5
        mesh.load_new_mesh(arrow_xyz_path)
        mesh_c = mesh.current_mesh()
        bbox = mesh_c.bounding_box()
        dim_1 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()])
        mesh.compute_matrix_from_translation_rotation_scale(scalex = dim_0 / dim_1,
                                                            scaley = dim_0 / dim_1,
                                                            scalez = dim_0 / dim_1,
                                                            )
        mesh.compute_matrix_from_translation_rotation_scale(translationx = center_[0],
                                                            translationy = center_[1],
                                                            translationz = center_[2],
                                                            )
        mesh_id = mesh.current_mesh_id()
        mesh_id_list.append(mesh_id)
        transparency_list.append(0.3)
    input_sym_file = os.path.join(os.path.dirname(input_file), os.path.basename(input_file).split('.')[0]+'_sym.ply')
    if os.path.exists(input_sym_file):
        mesh.load_new_mesh(input_sym_file)
        mesh_id = mesh.current_mesh_id()
        mesh_id_list.append(mesh_id)
        transparency_list.append(1.0)
    polyscope.remove_all_groups()
    polyscope.remove_all_structures()
    config.psm_list = []
    for (m, mesh_id, transparency) in zip(mesh, mesh_id_list, transparency_list):
        psm = build_psm(m, mesh_id, input_file, transparency)
        config.psm_list.append(psm)

_MAIN_WINDOW_TITLE = "Key-Axis-based Symmetry Axis Localization"
_MAIN_WINDOW_MAXIMIZE_PENDING = True
_MAIN_WINDOW_ICON_PENDING = True
_PROGRESS_MODAL_WIDTH = 380.0
_PROGRESS_BAR_SIZE = (320.0, 18.0)
_PROGRESS_MODAL_FLAGS = (
    psim.ImGuiWindowFlags_AlwaysAutoResize
    | psim.ImGuiWindowFlags_NoCollapse
    | psim.ImGuiWindowFlags_Modal
)
COMPUTE_CANCEL_CONFIRM_POPUP = "Confirm stop compute##kasal"
_kasal_side_panel_mode: str | None = None


def _sync_kasal_side_panel_mode(mode: str) -> None:
    '''Track Setup vs main; Structure panel stays visible in both layouts.
    跟踪设置页与主面板；两页均保留左侧 Structure 面板。'''

    global _kasal_side_panel_mode
    if _kasal_side_panel_mode == mode:
        return
    _kasal_side_panel_mode = mode
    polyscope.set_build_default_gui_panels(True)


def _return_to_setup_panel() -> None:
    '''Leave KASAL main panel and reopen the Setup (pre-confirm) page.
    离开 KASAL 主面板，重新打开设置（Confirm 前）页面。'''

    global _kasal_side_panel_mode
    if _symmetry_compute_busy():
        config.ui_batch_status = tr("batch.setup_blocked")
        return
    config.preprocess_modal_confirmed = False
    config.preprocess_modal_dismiss = False
    _kasal_side_panel_mode = None
    config.ui_batch_status = tr("batch.returned_setup")
    _kasal_log(config.ui_batch_status)


def _push_warning_button_style() -> None:
    """Medium-risk confirm buttons (amber / yellow)."""

    psim.PushStyleColor(psim.ImGuiCol_Button, (0.82, 0.68, 0.12, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonHovered, (0.90, 0.76, 0.22, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonActive, (0.72, 0.58, 0.08, 1.0))


def _pop_warning_button_style() -> None:
    psim.PopStyleColor(3)


_KASAL_PANEL_CHROME_COLOR_PUSH_COUNT = 8


def _push_kasal_panel_chrome_style() -> None:
    """Brighter separators, borders, and scrollbar grip in the user panel."""

    psim.PushStyleColor(psim.ImGuiCol_Separator, (0.52, 0.60, 0.76, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_SeparatorHovered, (0.38, 0.56, 0.92, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_SeparatorActive, (0.28, 0.46, 0.98, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_Border, (0.48, 0.56, 0.72, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ScrollbarBg, (0.18, 0.20, 0.26, 0.92))
    psim.PushStyleColor(psim.ImGuiCol_ScrollbarGrab, (0.50, 0.58, 0.74, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ScrollbarGrabHovered, (0.36, 0.52, 0.88, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ScrollbarGrabActive, (0.28, 0.44, 0.96, 1.0))
    psim.PushStyleVar(psim.ImGuiStyleVar_ScrollbarSize, 18.0)


def _pop_kasal_panel_chrome_style() -> None:
    psim.PopStyleVar(1)
    psim.PopStyleColor(_KASAL_PANEL_CHROME_COLOR_PUSH_COUNT)


def _imgui_draw_list():
    """Polyscope 2.3.x exposes draw APIs on psim; newer versions use GetWindowDrawList()."""

    if hasattr(psim, "GetWindowDrawList"):
        return psim.GetWindowDrawList()
    return psim


def _render_user_panel_resize_grip() -> None:
    """Visible grip band at the top of the user panel (near the structure/user splitter)."""

    avail = psim.GetContentRegionAvail()
    width = max(float(avail[0]), 220.0)
    height = 10.0
    pos = psim.GetCursorScreenPos()
    x0, y0 = pos
    p_max = (x0 + width, y0 + height)
    mouse_x, mouse_y = psim.GetMousePos()
    hovered = x0 <= mouse_x <= p_max[0] and y0 <= mouse_y <= p_max[1]
    if hovered:
        fill = psim.GetColorU32((0.34, 0.50, 0.88, 1.0))
        edge = psim.GetColorU32((0.22, 0.38, 0.78, 1.0))
    else:
        fill = psim.GetColorU32((0.46, 0.54, 0.70, 1.0))
        edge = psim.GetColorU32((0.30, 0.40, 0.62, 1.0))
    draw_list = _imgui_draw_list()
    draw_list.AddRectFilled(pos, p_max, fill, 3.0)
    draw_list.AddRect(pos, p_max, edge, 3.0, 0, 1.2)
    mid_y = y0 + height * 0.5
    dot_col = psim.GetColorU32((0.94, 0.96, 1.0, 0.98))
    cx = x0 + width * 0.5
    for dx in (-16.0, 0.0, 16.0):
        draw_list.AddCircleFilled((cx + dx, mid_y), 2.0, dot_col)
    psim.Dummy((width, height + 4.0))


def _draw_flowing_progress_bar(fraction: float, size: tuple[float, float]) -> None:
    """Draw a progress bar with animated flowing highlight stripes."""

    frac = max(0.0, min(1.0, float(fraction)))
    width, height = size
    pos = psim.GetCursorScreenPos()
    x0, y0 = pos
    p_max = (x0 + width, y0 + height)
    rounding = min(4.0, height * 0.35)

    bg_col = psim.GetColorU32(psim.ImGuiCol_FrameBg)
    fill_col = psim.GetColorU32(psim.ImGuiCol_PlotHistogram)
    border_col = psim.GetColorU32(psim.ImGuiCol_Border)
    draw_list = _imgui_draw_list()

    draw_list.AddRectFilled(pos, p_max, bg_col, rounding)

    fill_w = frac * width
    if fill_w > 0.5:
        fill_max = (x0 + fill_w, p_max[1])
        draw_list.AddRectFilled(pos, fill_max, fill_col, rounding)

        psim.PushClipRect(pos, fill_max, True)
        t = psim.GetTime()
        stripe_period = 22.0
        stripe_w = 9.0
        offset = (t * 42.0) % stripe_period
        shine = psim.GetColorU32((1.0, 1.0, 1.0, 0.30))
        sx = x0 - stripe_period + offset
        y_pad = 2.0
        while sx < x0 + fill_w + stripe_period:
            p1 = (sx, y0 - y_pad)
            p2 = (sx + stripe_w, y0 - y_pad)
            p3 = (sx + stripe_w + height, y0 + height + y_pad)
            p4 = (sx + height, y0 + height + y_pad)
            draw_list.AddQuadFilled(p1, p2, p3, p4, shine)
            sx += stripe_period
        psim.PopClipRect()

    draw_list.AddRect(pos, p_max, border_col, rounding, 0, 1.0)
    psim.Dummy(size)


def _center_modal_on_appear() -> None:
    """Center the next popup/modal on the Polyscope main window."""

    try:
        win_w, win_h = polyscope.get_window_size()
        psim.SetNextWindowPos(
            (win_w * 0.5, win_h * 0.5),
            psim.ImGuiCond_Appearing,
            (0.5, 0.5),
        )
    except Exception:
        pass


def _center_progress_modal_on_appear() -> None:
    if not config.progress_modal_needs_center:
        return
    _center_modal_on_appear()
    config.progress_modal_needs_center = False


def compute_cancel_confirm_modal() -> None:
    """High-risk confirmation before abandoning an in-flight symmetry job."""

    pg = get_compute_progress()
    batch = config.cal_all_batch
    if not _imgui_begin_popup_modal(
        COMPUTE_CANCEL_CONFIRM_POPUP,
        True,
        psim.ImGuiWindowFlags_AlwaysAutoResize,
    ):
        return
    psim.TextUnformatted("DANGER: stop in-progress computation")
    psim.Separator()
    psim.TextWrapped(
        "The running symmetry job will be abandoned immediately. "
        "Partial results will NOT be saved to disk."
    )
    psim.TextWrapped(
        "The background process may keep running briefly until it finishes; "
        "its output will be discarded."
    )
    if batch is not None:
        psim.TextWrapped(
            "Cal All batch will be aborted. Remaining objects in the queue will NOT be processed."
        )
    psim.TextUnformatted("Current object: %s" % pg.mesh_name)
    if pg.object_total > 1:
        psim.TextUnformatted("Queue position: %d / %d" % (pg.object_index, pg.object_total))
    psim.Separator()
    psim.PushStyleColor(psim.ImGuiCol_Button, (0.75, 0.15, 0.15, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonHovered, (0.85, 0.25, 0.25, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonActive, (0.65, 0.1, 0.1, 1.0))
    if _imgui_button("Confirm stop", min_width=120.0):
        psim.CloseCurrentPopup()
        _abort_compute_worker()
    psim.PopStyleColor(3)
    psim.SameLine()
    if _imgui_button("Continue computing", min_width=150.0):
        psim.CloseCurrentPopup()
    psim.EndPopup()


def _render_compute_progress_modal() -> None:
    """Centered, draggable modal with optional mid-flight stop."""

    pg = get_compute_progress()
    if not pg.active:
        return

    _center_progress_modal_on_appear()
    psim.SetNextWindowSize((_PROGRESS_MODAL_WIDTH, 0.0), psim.ImGuiCond_Always)
    if not _imgui_begin(PROGRESS_POPUP_ID, True, _PROGRESS_MODAL_FLAGS):
        return

    pct = pg.display_percent()
    frac = pct / 100.0
    psim.TextUnformatted("Computing — please wait")
    psim.Separator()
    if config.cal_all_batch is not None:
        obj_total = max(1, int(pg.object_total))
        obj_index = max(1, min(int(pg.object_index), obj_total))
        obj_frac = obj_index / float(obj_total)
        obj_pct = int(round(obj_frac * 100.0))
        psim.TextUnformatted("Objects %d / %d" % (obj_index, obj_total))
        psim.TextUnformatted("%d%%" % obj_pct)
        _draw_flowing_progress_bar(obj_frac, _PROGRESS_BAR_SIZE)
        psim.Separator()
    psim.TextUnformatted(pg.mesh_name)
    psim.TextUnformatted("Engine: %s" % pg.engine)
    psim.Separator()
    psim.TextWrapped(pg.stage_label)
    if pg.detail and pg.detail != pg.stage_label:
        psim.TextWrapped(pg.detail)
    psim.TextUnformatted("%d%%" % pct)
    _draw_flowing_progress_bar(frac, _PROGRESS_BAR_SIZE)
    psim.Separator()
    psim.PushStyleColor(psim.ImGuiCol_Button, (0.75, 0.15, 0.15, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonHovered, (0.85, 0.25, 0.25, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonActive, (0.65, 0.1, 0.1, 1.0))
    if _imgui_button("Stop computation"):
        psim.OpenPopup(COMPUTE_CANCEL_CONFIRM_POPUP)
    psim.PopStyleColor(3)
    compute_cancel_confirm_modal()
    psim.End()


def _compute_worker_busy() -> bool:
    proc = config.compute_worker_process
    return proc is not None and proc.is_alive()


def _cleanup_compute_worker_process() -> None:
    proc = config.compute_worker_process
    if proc is not None:
        try:
            proc.join(timeout=0.05)
        except Exception:
            pass
    config.compute_worker_process = None
    config.compute_worker_thread = None
    config.compute_worker_queue = None


def _drain_compute_worker_queue() -> None:
    q = config.compute_worker_queue
    if q is None:
        return
    while True:
        try:
            msg = q.get_nowait()
        except queue.Empty:
            break
        kind = msg[0]
        if kind == "progress":
            apply_remote_progress(msg[1])
        elif kind == "done":
            config.compute_worker_result = msg[1]
            config.compute_worker_done = True


def _symmetry_compute_busy() -> bool:
    if config.compute_aborted:
        return _compute_worker_busy()
    return (
        _compute_worker_busy()
        or get_compute_progress().active
        or config.cal_all_batch is not None
    )


def _ui_panel_locked() -> bool:
    """Grey out the side panel while compute runs or a job is queued."""
    if config.compute_aborted:
        return False
    return (
        _symmetry_compute_busy()
        or config.cal_current_run_pending
        or config.cal_all_run_pending
    )


def _build_symmetry_job(mesh_path: str, engine: str) -> SymmetryJobSpec:
    tex = config.is_true2 and not config.close_ADI_c
    return SymmetryJobSpec(
        mesh_path=mesh_path,
        engine=engine,
        sym_type=config.ui_options_selected,
        n_fold=config.ui_int,
        adi_c=tex,
        axis_xyz=config.ui_xyz_options_selected,
        tex=tex,
        policy=config.mesh_preprocess_policy,
        sym_type_source=config.sym_type_source,
        n_fold_source=config.n_fold_source,
    )


def _start_compute_worker(
    job: SymmetryJobSpec,
    *,
    progress_index: int,
    progress_total: int,
    refresh_status: bool = True,
) -> bool:
    """Run symmetry job in a subprocess; main thread polls queue and applies."""

    if _compute_worker_busy():
        return False

    _cleanup_compute_worker_process()

    config.compute_worker_done = False
    config.compute_worker_result = None
    config.compute_worker_discard = False
    config.compute_aborted = False
    config.progress_modal_needs_center = True
    config.compute_worker_meta = {
        "refresh_status": refresh_status,
        "progress_index": progress_index,
        "progress_total": progress_total,
    }
    mesh_name = os.path.basename(job.mesh_path)

    pg = get_compute_progress()
    pg.begin_object(
        mesh_name,
        object_index=progress_index,
        object_total=progress_total,
        engine=job.engine,
    )

    ctx = mp.get_context("spawn")
    progress_queue = ctx.Queue()
    progress_meta = {
        "mesh_name": mesh_name,
        "progress_index": progress_index,
        "progress_total": progress_total,
        "engine": job.engine,
    }
    proc = ctx.Process(
        target=mp_symmetry_worker_entry,
        args=(job, progress_queue, progress_meta),
        name="kasal-sym-compute",
        daemon=True,
    )
    config.compute_worker_queue = progress_queue
    config.compute_worker_process = proc
    config.compute_worker_thread = proc
    proc.start()
    return True


def _discard_compute_worker_result() -> None:
    config.compute_worker_done = False
    config.compute_worker_result = None
    _cleanup_compute_worker_process()
    config.compute_worker_discard = False
    config.compute_aborted = False
    _kasal_log("Discarded background result after user stop")


def _abort_compute_worker() -> None:
    """User confirmed stop: close UI, abort batch, discard worker output."""

    batch = config.cal_all_batch
    restore_id = int(config.current_file_id)
    if batch is not None:
        restore_id = int(batch.get("restore_file_id", restore_id))

    config.compute_worker_discard = True
    config.compute_aborted = True
    config.cal_all_batch = None
    config.cal_current_run_pending = False
    config.cal_all_run_pending = False

    pg = get_compute_progress()
    if pg.active:
        pg.end_object(success=False)

    if batch is not None:
        run_polyscope(config.files_name_list, start_id=restore_id)

    proc = config.compute_worker_process
    if proc is not None and proc.is_alive():
        try:
            proc.terminate()
            proc.join(timeout=3.0)
        except Exception:
            pass

    if config.compute_worker_done:
        _discard_compute_worker_result()
    else:
        _cleanup_compute_worker_process()

    _refresh_batch_status("stopped")
    _kasal_log("Compute stopped by user (partial results not saved)")


def _apply_compute_worker_result() -> None:
    if not config.compute_worker_done or config.compute_worker_result is None:
        return

    if config.compute_worker_discard:
        _discard_compute_worker_result()
        return

    job, result, exc = config.compute_worker_result
    config.compute_worker_done = False
    config.compute_worker_result = None
    _drain_compute_worker_queue()
    _cleanup_compute_worker_process()

    pg = get_compute_progress()
    meta = config.compute_worker_meta or {}
    refresh_status = bool(meta.get("refresh_status", True))
    try:
        if exc is not None:
            pg.end_object(success=False)
            _kasal_log("compute error: %s" % exc)
        elif result is None or not result.success:
            pg.end_object(success=False)
            _kasal_log((result.error if result else None) or "compute failed")
        else:
            apply_job_result_to_config(job, result)
            pg.set_stage("save", "Saving annotation files", fraction=0.96, indeterminate=False)
            save_symmetry_type()
            reload_object_func()
            if config.cal_all_batch is None:
                pg.end_object(success=True)
            else:
                pg.set_stage(
                    "batch_next",
                    "Object saved — starting next in queue",
                    fraction=0.98,
                    indeterminate=False,
                )
    except Exception as apply_exc:
        pg.end_object(success=False)
        _kasal_log("apply error: %s" % apply_exc)

    if refresh_status:
        _refresh_batch_status("cal_current_done")
    if config.cal_all_batch is not None:
        _cal_all_batch_continue()


def _poll_compute_worker() -> None:
    _drain_compute_worker_queue()
    if config.compute_worker_done:
        _apply_compute_worker_result()


def _queue_cal_current_async() -> None:
    files = config.files_name_list or []
    if not files:
        return
    mesh_path = files[config.current_file_id]
    job = _build_symmetry_job(mesh_path, config.compute_engine)
    block = kasalv1_block_reason_text(job)
    if block:
        config.ui_batch_status = block
        _kasal_log(block)
        return
    route_note = symmetry_routing_note_text(job)
    if route_note:
        _kasal_log(route_note)
    _start_compute_worker(
        job,
        progress_index=1,
        progress_total=1,
        refresh_status=True,
    )


def cal_all_obj_sym_start() -> None:
    """Begin async Cal All: one background job per dirty object."""

    dirty_ids = dirty_object_ids()
    _kasal_log("Cal All start: dirty_ids=%s" % dirty_ids)
    if not dirty_ids:
        _refresh_batch_status("cal_all_skipped")
        return
    config.cal_all_batch = {
        "dirty_ids": dirty_ids,
        "next_idx": 0,
        "restore_file_id": int(config.current_file_id),
        "engine": config.batch_compute_engine,
        "total": len(dirty_ids),
    }
    _cal_all_batch_start_next()


def _cal_all_batch_start_next() -> None:
    batch = config.cal_all_batch
    if batch is None or _compute_worker_busy():
        return

    idx = int(batch["next_idx"])
    dirty_ids = batch["dirty_ids"]
    if idx >= len(dirty_ids):
        run_polyscope(config.files_name_list, start_id=batch["restore_file_id"])
        engine = batch["engine"]
        config.cal_all_batch = None
        pg = get_compute_progress()
        if pg.active:
            pg.end_object(success=True)
        _refresh_batch_status("cal_all_done", engine=engine)
        return

    start_id = dirty_ids[idx]
    mesh_path = config.files_name_list[start_id]
    config.ui_batch_status = batch_status_progress_text(
        idx + 1,
        batch["total"],
        os.path.basename(mesh_path),
        batch["engine"],
    )
    _kasal_log(config.ui_batch_status)
    run_polyscope(config.files_name_list, start_id=start_id)
    job = _build_symmetry_job(mesh_path, batch["engine"])
    block = kasalv1_block_reason_text(job)
    if block:
        skip_msg = batch_status_skip_text(os.path.basename(mesh_path), block)
        config.ui_batch_status = skip_msg
        _kasal_log(skip_msg)
        batch["next_idx"] = idx + 1
        _cal_all_batch_start_next()
        return
    route_note = symmetry_routing_note_text(job)
    if route_note:
        _kasal_log(route_note)
    _start_compute_worker(
        job,
        progress_index=idx + 1,
        progress_total=batch["total"],
        refresh_status=False,
    )


def _cal_all_batch_continue() -> None:
    batch = config.cal_all_batch
    if batch is None:
        return
    batch["next_idx"] = int(batch["next_idx"]) + 1
    _cal_all_batch_start_next()


def _kasal_log(msg: str) -> None:
    """Log to console, stderr, and dataset KASAL_batch.log (Windows GUI may hide stdout)."""

    configure_stdio_utf8()
    get_compute_progress().clear_terminal()
    line = "[KASAL] " + msg
    print(line, flush=True)
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass
    try:
        base = os.path.dirname(config.start_id_json_file) if config.start_id_json_file else os.getcwd()
        log_path = os.path.join(base, "KASAL_batch.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _refresh_batch_status(status_key: str, **extra) -> None:
    '''Update the localized batch-status line on the KASAL panel.
    更新 KASAL 面板上的双语批量状态行。'''

    dirty_n = len(dirty_object_ids())
    saved_n = len(saved_object_ids())
    total_n = len(config.files_name_list or [])
    config.ui_batch_status = batch_status_text(
        status_key,
        saved=saved_n,
        total=total_n,
        unsaved=dirty_n,
        **extra,
    )
    _kasal_log(config.ui_batch_status)


CAL_ALL_CONFIRM_POPUP = "Confirm Cal All##kasal"
CLEAR_ALL_LABELS_POPUP = "Clear all labels##kasal"
PREPROCESS_CONFIRM_POPUP = "Confirm preprocess setup##kasal"
# Setup Confirm modal: 420×300 base → width ×1.8 (756), height ×1.32 (396); centered on open.
# 设置 Confirm 弹窗：420×300 基准 → 宽 ×1.8（756）、高 ×1.32（396）；打开时居中。
_PREPROCESS_CONFIRM_MODAL_WIDTH_SCALE = 1.5 * 1.2
_PREPROCESS_CONFIRM_MODAL_HEIGHT_SCALE = 1.1 * 1.2
PREPROCESS_CONFIRM_MODAL_SIZE = (
    420.0 * _PREPROCESS_CONFIRM_MODAL_WIDTH_SCALE,
    300.0 * _PREPROCESS_CONFIRM_MODAL_HEIGHT_SCALE,
)
BACK_TO_SETUP_CONFIRM_POPUP = "Confirm back to Setup##kasal"
# Back-to-Setup modal: 420×260 base → width ×1.5 (630), height ×0.9504 (247); centered on open.
# 返回设置弹窗：420×260 基准 → 宽 ×1.5（630）、高 ×0.9504（247）；打开时居中。
_BACK_TO_SETUP_CONFIRM_MODAL_WIDTH_SCALE = 1.5
_BACK_TO_SETUP_CONFIRM_MODAL_HEIGHT_SCALE = 1.1 * 0.8 * 0.9 * 1.2
BACK_TO_SETUP_CONFIRM_MODAL_SIZE = (
    420.0 * _BACK_TO_SETUP_CONFIRM_MODAL_WIDTH_SCALE,
    260.0 * _BACK_TO_SETUP_CONFIRM_MODAL_HEIGHT_SCALE,
)

_hw_device_rows_cache_key: str | None = None
_hw_device_rows_cache: list = []


def _reset_current_object_ui_defaults() -> None:
    config.ui_options_selected = config.ui_options[0]
    config.ui_xyz_options_selected = config.ui_xyz_options[0]
    config.ui_int = 2
    config.is_true2 = False
    config.sym_type_source = "kasalv2_auto"
    config.n_fold_source = "kasalv2_auto"
    config.axis_xyz_source = "none"
    config.current_obj_info = {}
    config.kasalv2_snapshot = None


def clear_all_labels_action() -> None:
    """Delete all *_sym_type.json / *_sym.ply and reset to unlabeled state."""

    files = config.files_name_list or []
    stats = clear_all_dataset_annotations(files)
    _reset_current_object_ui_defaults()
    reload_object_func()
    config.ui_batch_status = cleared_labels_status_text(
        stats["json_removed"],
        stats["ply_removed"],
        stats["objects"],
        len(files),
    )
    _kasal_log(config.ui_batch_status)


def clear_all_labels_confirm_modal() -> None:
    """High-risk confirmation before wiping all annotation sidecars."""

    files = config.files_name_list or []
    total_n = len(files)
    json_n, ply_n = count_annotation_artifacts(files)
    if not _imgui_begin_popup_modal(
        CLEAR_ALL_LABELS_POPUP,
        True,
        psim.ImGuiWindowFlags_AlwaysAutoResize,
    ):
        return
    psim.TextUnformatted("DANGER: irreversible wipe")
    psim.Separator()
    psim.TextWrapped(
        "This will permanently delete ALL *_sym_type.json and *_sym.ply files "
        "for every object in the current dataset folder."
    )
    psim.TextWrapped(
        "Symmetry type, n-fold, axis, and computed sym meshes will be removed. "
        "Legacy manual labels cannot be recovered unless you have a backup."
    )
    psim.TextUnformatted(
        "On disk now: %d sym_type.json, %d sym.ply (%d objects)"
        % (json_n, ply_n, total_n)
    )
    if json_n == 0 and ply_n == 0:
        psim.TextWrapped("No annotation sidecars found; confirm will still reset UI to unlabeled.")
    psim.Separator()
    if _imgui_button("Confirm wipe", min_width=120.0):
        psim.CloseCurrentPopup()
        clear_all_labels_action()
    psim.SameLine()
    if _imgui_button("Cancel", min_width=100.0):
        psim.CloseCurrentPopup()
    psim.EndPopup()


def cal_all_confirm_modal() -> None:
    """Risk confirmation before batch Cal All."""

    dirty_n = len(dirty_object_ids())
    total_n = len(config.files_name_list or [])
    if not _imgui_begin_popup_modal(
        CAL_ALL_CONFIRM_POPUP,
        True,
        psim.ImGuiWindowFlags_AlwaysAutoResize,
    ):
        return
    psim.TextUnformatted("Warning: risky batch operation")
    psim.Separator()
    psim.TextWrapped(
        "Cal All will recompute every unsaved object using engine "
        "'%s' and may overwrite *_sym_type.json and *_sym.ply on disk."
        % config.batch_compute_engine
    )
    psim.TextWrapped(engine_speed_hint(cuda_available=torch_cuda_runtime_available()))
    psim.TextWrapped(kasalv1_usage_hint())
    psim.TextWrapped(
        "Saved kasalv1 manual labels are skipped by default. "
        "Use 'Mark all as unsaved' only if you intend to re-run the full dataset."
    )
    psim.TextUnformatted("Unsaved queue: %d / %d" % (dirty_n, total_n))
    if dirty_n == 0:
        psim.TextWrapped(
            "The queue is empty. Cal All will not change any object unless you "
            "mark items unsaved first (e.g. 'Mark all as unsaved')."
        )
    psim.Separator()
    if dirty_n == 0:
        psim.BeginDisabled(True)
    _push_warning_button_style()
    if _imgui_button("Confirm Cal All", min_width=140.0):
        psim.CloseCurrentPopup()
        config.cal_all_run_pending = True
        config.ui_batch_status = "Cal All confirmed; starting..."
        _kasal_log("Cal All confirmed (queue %d/%d)" % (dirty_n, total_n))
    _pop_warning_button_style()
    if dirty_n == 0:
        psim.EndDisabled()
    psim.SameLine()
    if _imgui_button("Cancel", min_width=100.0):
        psim.CloseCurrentPopup()
    psim.EndPopup()


def _resolve_dataset_start_id(models_dir: str, start_id: int) -> int:
    if start_id != -1:
        return int(start_id)
    kasal_json_path = os.path.join(models_dir, "KASAL.json")
    if os.path.exists(kasal_json_path):
        try:
            return int(load_json2dict(kasal_json_path)["start_id"])
        except Exception:
            pass
    return 0


def _ensure_torch_device_options(*, refresh: bool = False) -> list[TorchDeviceOption]:
    if refresh or not config.torch_device_options:
        config.torch_device_options = list_torch_device_options()
    return config.torch_device_options


def _cached_hardware_device_rows(selected_device_id: str | None = None):
    global _hw_device_rows_cache_key, _hw_device_rows_cache
    cache_key = selected_device_id or ""
    if _hw_device_rows_cache_key != cache_key:
        _hw_device_rows_cache_key = cache_key
        _hw_device_rows_cache = list_hardware_device_rows(selected_device_id)
    return _hw_device_rows_cache


def _selected_device_label() -> str:
    if config.torch_device_options:
        return device_option_label(config.torch_device_id, config.torch_device_options)
    return config.torch_device_id or "(none)"


def _init_torch_device_selection() -> None:
    _ensure_torch_device_options(refresh=True)
    if config.torch_device_id:
        apply_torch_device_choice(config.torch_device_id)
        return
    env = os.environ.get("KASAL_TORCH_DEVICE", "").strip()
    if env:
        config.torch_device_id = apply_torch_device_choice(env)
        return
    config.torch_device_id = apply_torch_device_choice(resolve_torch_device("cuda"))


def _load_kasal_json_gui_settings(models_dir: str) -> bool:
    """Load preprocess policy (+ optional torch device) from KASAL.json."""

    kasal_json_path = os.path.join(models_dir, "KASAL.json")
    if not os.path.exists(kasal_json_path):
        return False
    try:
        kasal_json = load_json2dict(kasal_json_path)
    except Exception:
        return False

    has_policy = "mesh_preprocess_policy" in kasal_json
    if has_policy:
        config.mesh_preprocess_policy = normalize_preprocess_policy(
            kasal_json["mesh_preprocess_policy"]
        )
    if "torch_device" in kasal_json:
        apply_torch_device_choice(kasal_json["torch_device"])
    elif not config.torch_device_id:
        _init_torch_device_selection()
    if kasal_json.get("ui_language") in (UI_LANG_EN, UI_LANG_ZH):
        config.ui_language = kasal_json["ui_language"]
    if "ui_font_scale" in kasal_json:
        try:
            config.ui_font_scale = _clamp_ui_font_scale(kasal_json["ui_font_scale"])
        except (TypeError, ValueError):
            pass
    return has_policy


def _load_preprocess_policy_from_disk(models_dir: str) -> bool:
    return _load_kasal_json_gui_settings(models_dir)


def _render_torch_device_combo(combo_id: str) -> None:
    options = _ensure_torch_device_options()
    if not config.torch_device_id:
        _init_torch_device_selection()
    if not torch_cuda_runtime_available() and config.torch_device_id.startswith("cuda"):
        config.torch_device_id = "cpu"
    current_label = device_option_label(config.torch_device_id, options)
    changed = psim.BeginCombo(combo_id, current_label)
    if changed:
        for opt in options:
            selected = _imgui_selectable_selected(opt.label, config.torch_device_id == opt.device_id)
            if selected:
                config.torch_device_id = opt.device_id
        psim.EndCombo()


def _hw_table_cell(text: str, *, muted: bool = False, wrap: bool = False) -> None:
    if muted:
        psim.TextDisabled(text)
    elif wrap:
        psim.TextWrapped(text)
    else:
        psim.TextUnformatted(text)


def _render_hardware_device_table(selected_device_id: str | None = None) -> None:
    """Detected CPU/GPU as a bordered three-column table."""

    rows = _cached_hardware_device_rows(selected_device_id)
    psim.Columns(3, "##hardware_device_table", True)
    psim.SetColumnWidth(0, 58)
    psim.SetColumnWidth(1, 220)

    _hw_table_cell(hardware_table_header("type"))
    psim.NextColumn()
    _hw_table_cell(hardware_table_header("model"))
    psim.NextColumn()
    _hw_table_cell(hardware_table_header("status"))
    psim.NextColumn()
    psim.Separator()

    for row in rows:
        _hw_table_cell(row.device_type, muted=row.muted)
        psim.NextColumn()
        _hw_table_cell(row.model_name, muted=row.muted, wrap=True)
        psim.NextColumn()
        _hw_table_cell(hardware_status_label(row.status), muted=row.muted, wrap=True)
        psim.NextColumn()

    psim.Columns(1)


def _render_torch_device_panel(combo_id: str) -> None:
    """Device combo plus CPU-only / hardware-GPU notices."""

    _render_torch_device_combo(combo_id)
    psim.TextUnformatted(tr("setup.detected_hardware"))
    _render_hardware_device_table(config.torch_device_id)
    hint = gpu_install_hint_text()
    if hint:
        psim.TextWrapped(hint)
    elif torch_cuda_runtime_available():
        psim.TextWrapped(cuda_available_hint_text())
        psim.TextWrapped(engine_speed_hint_text(cuda_available=True))
    else:
        psim.TextWrapped(cpu_only_build_hint_text())
        psim.TextWrapped(engine_speed_hint_text(cuda_available=False))


def _apply_dataset_folder(models_dir: str, start_id: int = -1) -> bool:
    """Switch the open dataset in-place (no process restart)."""

    models_dir = os.path.abspath(models_dir)
    if not os.path.isdir(models_dir):
        config.dataset_folder_error = dataset_folder_error_text("not_folder", models_dir)
        return False

    files = get_all_ply_obj(models_dir)
    if not files:
        config.dataset_folder_error = dataset_folder_error_text("no_meshes", models_dir)
        return False

    if _symmetry_compute_busy():
        config.dataset_folder_error = dataset_folder_error_text("compute_busy")
        return False

    start_id = _resolve_dataset_start_id(models_dir, start_id)
    if start_id >= len(files):
        start_id = 0

    global _kasal_side_panel_mode
    _load_preprocess_policy_from_disk(models_dir)
    config.preprocess_modal_confirmed = False
    config.preprocess_modal_dismiss = False
    _kasal_side_panel_mode = None

    config.models_dir = models_dir
    config.start_id_json_file = os.path.join(models_dir, "KASAL.json")
    config.files_name_list = files
    config.dataset_folder_error = ""
    config.cal_all_batch = None
    config.cal_current_run_pending = False
    config.cal_all_run_pending = False
    config.ui_batch_status = tr(
        "batch.loaded_folder",
        name=os.path.basename(models_dir) or models_dir,
        count=len(files),
    )
    initialize_dataset_dirty_state(files)
    print(files[start_id])
    print("id:", start_id)
    run_polyscope(files, start_id=start_id)
    _kasal_log("Switched dataset folder: %s (%d objects)" % (models_dir, len(files)))
    return True


def _request_dataset_folder_picker() -> None:
    config.open_folder_picker_pending = True


def _run_pending_dataset_folder_picker() -> None:
    if not config.open_folder_picker_pending:
        return
    config.open_folder_picker_pending = False
    initial = config.models_dir if config.models_dir else None
    folder = pick_dataset_folder(initial_dir=initial)
    if not folder:
        return
    _apply_dataset_folder(folder)


def preprocess_confirm_action() -> None:
    """Apply preprocess + device choices and persist to KASAL.json."""

    config.preprocess_modal_confirmed = True
    apply_torch_device_choice(config.torch_device_id)
    try:
        kasal_json = load_json2dict(config.start_id_json_file)
    except Exception:
        kasal_json = {}
    kasal_json["mesh_preprocess_policy"] = config.mesh_preprocess_policy
    kasal_json["torch_device"] = config.torch_device_id
    kasal_json["ui_language"] = config.ui_language
    kasal_json["ui_font_scale"] = _clamp_ui_font_scale(
        getattr(config, "ui_font_scale", _UI_FONT_SCALE_DEFAULT)
    )
    from kasal.utils.io_json import write_dict2json

    write_dict2json(config.start_id_json_file, kasal_json)
    _kasal_log(
        "Preprocess confirmed: policy=%s device=%s folder=%s"
        % (config.mesh_preprocess_policy, config.torch_device_id, config.models_dir)
    )


def back_to_setup_confirm_modal() -> None:
    '''Confirm leaving KASAL main panel to change folder / preprocess / device.
    确认离开 KASAL 主面板并返回设置页。'''

    if not _imgui_begin_popup_modal(
        BACK_TO_SETUP_CONFIRM_POPUP,
        True,
        psim.ImGuiWindowFlags_NoResize,
    ):
        return
    psim.TextUnformatted(tr("confirm_back_setup.title"))
    psim.Separator()
    psim.TextWrapped(tr("confirm_back_setup.body1"))
    psim.TextWrapped(tr("confirm_back_setup.body2"))
    psim.Separator()
    _push_warning_button_style()
    if _imgui_button(tr("confirm_back_setup.confirm_btn"), min_width=160.0):
        psim.CloseCurrentPopup()
        _return_to_setup_panel()
    _pop_warning_button_style()
    psim.SameLine()
    if _imgui_button(tr("confirm_back_setup.cancel_btn"), min_width=100.0):
        psim.CloseCurrentPopup()
    psim.EndPopup()


def preprocess_confirm_modal() -> None:
    '''Medium-risk confirmation before locking preprocess + device for this dataset.
    锁定预处理与设备前的中等风险确认弹窗。'''

    if not _imgui_begin_popup_modal(
        PREPROCESS_CONFIRM_POPUP,
        True,
        psim.ImGuiWindowFlags_NoResize,
    ):
        return
    psim.TextUnformatted(tr("confirm_preprocess.title"))
    psim.Separator()
    psim.TextWrapped(tr("confirm_preprocess.body1"))
    psim.TextWrapped(tr("confirm_preprocess.body2"))
    psim.Separator()
    psim.TextUnformatted(tr("confirm_preprocess.dataset"))
    psim.TextWrapped(config.models_dir or tr("setup.none"))
    psim.TextUnformatted(
        tr("confirm_preprocess.preprocess", preprocess_policy_label_text(config.mesh_preprocess_policy))
    )
    psim.TextUnformatted(tr("confirm_preprocess.device", _selected_device_label()))
    if config.preprocess_modal_dismiss:
        psim.TextWrapped(tr("confirm_preprocess.dismiss_note"))
    psim.Separator()
    _push_warning_button_style()
    if _imgui_button(tr("confirm_preprocess.confirm_btn"), min_width=140.0):
        psim.CloseCurrentPopup()
        preprocess_confirm_action()
    _pop_warning_button_style()
    psim.SameLine()
    if _imgui_button(tr("confirm_preprocess.cancel_btn"), min_width=100.0):
        psim.CloseCurrentPopup()
    psim.EndPopup()


def preprocess_setup_callback():
    '''First-page Setup panel only (folder / preprocess / device / language).
    设置页：文件夹、预处理、设备与界面语言（Confirm 前）。'''

    if config.preprocess_modal_confirmed:
        return

    _sync_kasal_side_panel_mode("setup")
    _push_kasal_panel_chrome_style()
    _render_user_panel_resize_grip()
    _run_pending_dataset_folder_picker()

    psim.TextUnformatted(tr("setup.title"))
    psim.Separator()
    psim.TextUnformatted(tr("setup.language"))
    for lang_id, lang_label_key in (
        (UI_LANG_EN, "setup.lang_en"),
        (UI_LANG_ZH, "setup.lang_zh"),
    ):
        selected = _imgui_selectable_selected(
            tr(lang_label_key), config.ui_language == lang_id
        )
        if selected:
            config.ui_language = lang_id
            _apply_ui_font_for_language()
    _render_ui_font_scale_slider()
    psim.Separator()
    psim.TextUnformatted(tr("setup.dataset_folder"))
    folder_label = config.models_dir or tr("setup.none")
    psim.TextWrapped(folder_label)
    if config.dataset_folder_error:
        psim.TextWrapped(config.dataset_folder_error)
    if _imgui_button(tr("setup.open_folder")):
        _request_dataset_folder_picker()
    psim.Separator()
    psim.TextUnformatted(tr("setup.preprocess_mode"))
    psim.Separator()
    pymeshlab_ok = is_pymeshlab_available()
    if not pymeshlab_ok:
        psim.TextUnformatted(tr("setup.pymeshlab_warning"))
    policies = list(config.mesh_preprocess_policy_options)
    for pol in policies:
        disabled = (not pymeshlab_ok) and pol in ("kasalv1", "kasalv2_adaptive")
        label = preprocess_policy_option_text(pol)
        if disabled:
            psim.TextDisabled(label)
        else:
            selected = _imgui_selectable_selected(label, config.mesh_preprocess_policy == pol)
            if selected:
                config.mesh_preprocess_policy = pol
    psim.Separator()
    psim.TextUnformatted(tr("setup.compute_device"))
    _render_torch_device_panel("##preprocess_torch_device")
    psim.Separator()
    _, config.preprocess_modal_dismiss = psim.Checkbox(tr("setup.dismiss_checkbox"), False)
    _push_warning_button_style()
    if _imgui_button(tr("setup.confirm"), min_width=120.0):
        psim.SetNextWindowSize(
            PREPROCESS_CONFIRM_MODAL_SIZE,
            psim.ImGuiCond_Appearing,
        )
        _center_modal_on_appear()
        psim.OpenPopup(PREPROCESS_CONFIRM_POPUP)
    _pop_warning_button_style()
    preprocess_confirm_modal()
    _pop_kasal_panel_chrome_style()

def _main_toolkit_callback() -> None:
    '''Post-confirm KASAL labeling panel (separate from Setup).
    Confirm 后的 KASAL 对称标注主面板。'''

    _sync_kasal_side_panel_mode("main")
    _push_kasal_panel_chrome_style()
    _render_user_panel_resize_grip()
    _poll_compute_worker()
    ui_locked = _ui_panel_locked()
    if ui_locked:
        psim.BeginDisabled(True)

    psim.PushItemWidth(200)
    psim.TextUnformatted(tr("kasal.title"))
    psim.Separator()
    psim.TextUnformatted(tr("kasal.subtitle"))
    folder_label = config.models_dir or tr("setup.none")
    psim.TextWrapped(
        tr("kasal.dataset", os.path.basename(folder_label) or folder_label)
    )
    if _imgui_button(tr("setup.open_folder")):
        _request_dataset_folder_picker()
    _run_pending_dataset_folder_picker()
    psim.Separator()
    psim.TextWrapped(engine_speed_hint_text(cuda_available=torch_cuda_runtime_available()))
    psim.TextWrapped(kasalv1_usage_hint_text())
    psim.Separator()
    psim.TextUnformatted(tr("kasal.cal_current"))
    changed_eng = psim.BeginCombo("##cal_current_eng", config.compute_engine)
    if changed_eng:
        for val in config.engine_options:
            selected = _imgui_selectable_selected(val, config.compute_engine == val)
            if selected:
                config.compute_engine = val
        psim.EndCombo()
    psim.TextUnformatted(tr("kasal.cal_all"))
    changed_batch = psim.BeginCombo("##cal_all_eng", config.batch_compute_engine)
    if changed_batch:
        for val in config.engine_options:
            selected = _imgui_selectable_selected(val, config.batch_compute_engine == val)
            if selected:
                config.batch_compute_engine = val
        psim.EndCombo()
    files = config.files_name_list or []
    if files:
        cal_job = _build_symmetry_job(files[config.current_file_id], config.compute_engine)
        cal_block = kasalv1_block_reason_text(cal_job)
        if cal_block:
            psim.TextWrapped(cal_block)
        else:
            route_note = symmetry_routing_note_text(cal_job)
            if route_note:
                psim.TextWrapped(route_note)
    dirty_n = len(dirty_object_ids())
    saved_n = len(saved_object_ids())
    total_n = len(config.files_name_list or [])
    psim.TextUnformatted(
        tr("kasal.sources", config.sym_type_source, config.n_fold_source)
    )
    psim.TextUnformatted(
        tr("kasal.saved_unsaved", saved_n, total_n, dirty_n, total_n)
    )
    psim.Separator()
    psim.PushItemWidth(200)
    psim.TextUnformatted(tr("kasal.symmetry_type"))
    psim.SameLine() 
    changed = psim.BeginCombo(" "*1, sym_type_option_label(config.ui_options_selected))
    if changed:
        for val in config.ui_options:
            selected = _imgui_selectable_selected(
                sym_type_option_label(val),
                config.ui_options_selected == val,
            )
            if selected:
                config.ui_options_selected = val
                config.sym_type_source = "user"
                config.n_fold_source = "user"
                mark_object_dirty(config.current_file_id)
        psim.EndCombo()
    psim.PopItemWidth()
    psim.Separator()
    psim.TextUnformatted(tr("kasal.d_setting"))
    psim.TextUnformatted(tr("kasal.n_note"))
    psim.Separator()
    psim.TextUnformatted(tr("kasal.n_fold"))
    psim.SameLine() 
    changed, config.ui_int = psim.InputInt(" "*2, config.ui_int, step=1, step_fast=10)
    if changed:
        config.n_fold_source = "user"
        mark_object_dirty(config.current_file_id)
    psim.SameLine() 
    psim.TextUnformatted(tr("kasal.adi_c"))
    psim.SameLine() 
    changed, config.is_true2 = psim.Checkbox(" "*3, config.is_true2)
    if changed:
        mark_object_dirty(config.current_file_id)
    psim.Separator()
    psim.TextUnformatted(tr("kasal.axis_xyz"))
    psim.SameLine() 
    changed = psim.BeginCombo(" "*4, config.ui_xyz_options_selected)
    if changed:
        for val in config.ui_xyz_options:
            selected_2 = _imgui_selectable_selected(val, config.ui_xyz_options_selected==val)
            if selected_2:
                config.ui_xyz_options_selected = val
                config.axis_xyz_source = "user"
                mark_object_dirty(config.current_file_id)
        psim.EndCombo()
    psim.PopItemWidth()
    psim.SameLine() 
    psim.TextUnformatted(tr("kasal.show_xyz"))
    psim.SameLine() 
    changed, config.is_true3 = psim.Checkbox(" "*5, config.is_true3)
    if(changed): 
        reload_object_func()
        pass 
    psim.Separator()
    if _imgui_button(tr("kasal.last_object")):
        last_object_func()
    psim.SameLine() 
    if _imgui_button(tr("kasal.next_object")):
        next_object_func()
    psim.Separator()
    cal_current_blocked = bool(files and kasalv1_block_reason_text(
        _build_symmetry_job(files[config.current_file_id], config.compute_engine)
    ))
    if cal_current_blocked:
        psim.BeginDisabled(True)
    if _imgui_button(tr("kasal.cal_current_btn")):
        config.cal_current_run_pending = True
        print("Cal Current Obj")
    if cal_current_blocked:
        psim.EndDisabled()
    psim.SameLine()
    if _imgui_button(tr("kasal.cal_all_btn")):
        psim.OpenPopup(CAL_ALL_CONFIRM_POPUP)
    cal_all_confirm_modal()
    psim.Separator()
    psim.TextWrapped(tr("kasal.mark_all_hint"))
    psim.TextWrapped(tr("kasal.restore_hint"))
    psim.Separator()
    if _imgui_button(tr("kasal.mark_all_btn")):
        mark_all_dirty()
        _refresh_batch_status("queued_all")
    psim.SameLine() 
    if _imgui_button(tr("kasal.restore_btn")):
        initialize_dataset_dirty_state(config.files_name_list)
        load_symmetry_type()
        _refresh_batch_status("restored")
    psim.Separator()
    psim.TextWrapped(tr("kasal.clear_hint"))
    psim.PushStyleColor(psim.ImGuiCol_Button, (0.75, 0.15, 0.15, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonHovered, (0.85, 0.25, 0.25, 1.0))
    psim.PushStyleColor(psim.ImGuiCol_ButtonActive, (0.65, 0.1, 0.1, 1.0))
    if _imgui_button(tr("kasal.clear_btn")):
        psim.OpenPopup(CLEAR_ALL_LABELS_POPUP)
    psim.PopStyleColor(3)
    clear_all_labels_confirm_modal()
    if ui_locked:
        psim.EndDisabled()

    _render_compute_progress_modal()
    _drain_compute_worker_queue()
    psim.Separator()
    if config.ui_batch_status:
        psim.TextUnformatted(config.ui_batch_status)

    if not _compute_worker_busy():
        if config.cal_all_run_pending:
            config.cal_all_run_pending = False
            cal_all_obj_sym_start()
        elif config.cal_current_run_pending:
            config.cal_current_run_pending = False
            _queue_cal_current_async()

    psim.Separator()
    if ui_locked:
        psim.BeginDisabled(True)
    _push_warning_button_style()
    if _imgui_button(tr("kasal.back_to_setup")):
        psim.SetNextWindowSize(
            BACK_TO_SETUP_CONFIRM_MODAL_SIZE,
            psim.ImGuiCond_Appearing,
        )
        _center_modal_on_appear()
        psim.OpenPopup(BACK_TO_SETUP_CONFIRM_POPUP)
    _pop_warning_button_style()
    if ui_locked:
        psim.EndDisabled()
    back_to_setup_confirm_modal()

    _pop_kasal_panel_chrome_style()


def callback():
    '''GUI callback: Setup page before confirm, KASAL main panel after.
    GUI 回调：Confirm 前为设置页，Confirm 后为 KASAL 主面板。'''

    _try_maximize_polyscope_window()
    _try_apply_window_icon()
    _apply_ui_font_scale()
    _apply_ui_font_for_language()
    if not config.preprocess_modal_confirmed:
        preprocess_setup_callback()
        return
    _main_toolkit_callback()


def run_polyscope(files_name_list, start_id = 0):
    ''' Use polyscope to display objects from pymeshlab.  
    Parameters:  
        files_name_list: A list of paths to all object models in the folder.  
        start_id: The index of the object to start loading.  
    '''
    
    mesh.clear()
    polyscope.remove_all_groups()
    polyscope.remove_all_structures()
    input_file = files_name_list[start_id]
    config.current_file_id = start_id
    load_symmetry_type()
    mesh.load_new_mesh(input_file)
    mesh_id = mesh.current_mesh_id()
    mesh_id_list = [mesh_id]
    transparency_list = [1.0]
    if config.is_true3:
        mesh_c = mesh.current_mesh()
        bbox = mesh_c.bounding_box()
        center_ = bbox.center()
        dim_0 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()]) * 1.5
        mesh.load_new_mesh(arrow_xyz_path)
        mesh_c = mesh.current_mesh()
        bbox = mesh_c.bounding_box()
        dim_1 = np.max([bbox.dim_x(), bbox.dim_y(), bbox.dim_z()])
        mesh.compute_matrix_from_translation_rotation_scale(scalex = dim_0 / dim_1,
                                                            scaley = dim_0 / dim_1,
                                                            scalez = dim_0 / dim_1,
                                                            )
        mesh.compute_matrix_from_translation_rotation_scale(translationx = center_[0],
                                                            translationy = center_[1],
                                                            translationz = center_[2],
                                                            )
        mesh_id = mesh.current_mesh_id()
        mesh_id_list.append(mesh_id)
        transparency_list.append(0.3)
    
    input_sym_file = os.path.join(os.path.dirname(input_file), os.path.basename(input_file).split('.')[0]+'_sym.ply')
    if os.path.exists(input_sym_file):
        mesh.load_new_mesh(input_sym_file)
        mesh_id = mesh.current_mesh_id()
        mesh_id_list.append(mesh_id)
        transparency_list.append(1.0)
    
    for (m, mesh_id, transparency_) in zip(mesh, mesh_id_list, transparency_list):
        psm = build_psm(m, mesh_id, input_file, transparency_)
        config.psm_list.append(psm)

def app(models_dir, start_id = -1):
    '''Application of symmetry axis localization.

    Parameters:
        models_dir: Folder of object models (.ply / .obj under subdirs).
        start_id: Object index to open (-1 = read KASAL.json, else 0).

    ------------------------------------------------------

    对称轴定位 GUI 入口。

    参数：
        models_dir: 物体模型文件夹（递归扫描 .ply / .obj）。
        start_id: 起始物体索引（-1 表示读 KASAL.json，否则默认 0）。
    '''
    
    global _MAIN_WINDOW_MAXIMIZE_PENDING, _MAIN_WINDOW_ICON_PENDING
    configure_stdio_utf8()
    _MAIN_WINDOW_MAXIMIZE_PENDING = True
    _MAIN_WINDOW_ICON_PENDING = True
    polyscope.init()
    _load_imgui_ui_font()
    polyscope.set_build_default_gui_panels(True)
    polyscope.set_user_callback(callback)
    config.preprocess_modal_confirmed = False
    config.preprocess_modal_dismiss = False
    _ensure_torch_device_options(refresh=True)
    _init_torch_device_selection()
    if not _apply_dataset_folder(models_dir, start_id=start_id):
        raise FileNotFoundError(
            "No loadable meshes in dataset folder: %s" % os.path.abspath(models_dir)
        )
    _apply_ui_font_scale()
    _apply_ui_font_for_language()
    polyscope.show()
