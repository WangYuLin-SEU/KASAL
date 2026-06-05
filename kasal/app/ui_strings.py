# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

'''
Localized UI strings for the Setup and KASAL main panels.

English and Chinese text live in ``_STRINGS``; ``tr()`` reads ``config.ui_language``.
Symmetry-type combo values remain English canonical values on disk.

------------------------------------------------------

Setup 与 KASAL 主面板的界面双语文案。

中英文条目存放在 ``_STRINGS``；``tr()`` 根据 ``config.ui_language`` 取值。
对称类型下拉的写盘值仍为英文 canonical 字符串。
'''

from __future__ import annotations

import kasal.config.config as config
from kasal.compute.symmetry_job import SymmetryJobSpec, kasalv1_job_blocked_reason, symmetry_job_routing_note
from kasal.device import GPU_INSTALL_CMD, GPU_INSTALL_DOC, gpu_install_hint_message

UI_LANG_EN = "en"
UI_LANG_ZH = "zh"

# Supported GUI languages for Setup / KASAL panels.
# Setup / KASAL 面板支持的语言代码。
UI_LANGUAGES = (UI_LANG_EN, UI_LANG_ZH)


def _lang() -> str:
    lang = getattr(config, "ui_language", UI_LANG_EN) or UI_LANG_EN
    if lang not in UI_LANGUAGES:
        return UI_LANG_EN
    return lang


def tr(key: str, *args, **fmt) -> str:
    '''Return localized UI text for the active ``config.ui_language``.'''

    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_lang()) or entry.get(UI_LANG_EN) or key
    if args and not fmt:
        try:
            return text % args if len(args) > 1 else text % args[0]
        except TypeError:
            return text
    if fmt:
        try:
            return text % fmt
        except (KeyError, TypeError):
            return text
    return text


# --- Symmetry type display labels (canonical value -> localized label) ---
# --- 对称类型显示名（canonical 值 -> 界面标签）---

_SYM_TYPE_LABELS: dict[str, dict[str, str]] = {
    "None": {"en": "None", "zh": "无（None）"},
    "C(>>1): Spherical Item": {"en": "C(>>1): Spherical Item", "zh": "C(>>1)：球体"},
    "C(>1): Cylindrical Item": {"en": "C(>1): Cylindrical Item", "zh": "C(>1)：圆柱体"},
    "C(=1): Circular Item": {"en": "C(=1): Circular Item", "zh": "C(=1)：圆片"},
    "D(>1): n-fold Prismatic Item": {
        "en": "D(>1): n-fold Prismatic Item",
        "zh": "D(>1)：n 折棱柱",
    },
    "D(=1): n-fold Pyramidal Item": {
        "en": "D(=1): n-fold Pyramidal Item",
        "zh": "D(=1)：n 折棱锥",
    },
    "P(4): Tetrahedral Item": {"en": "P(4): Tetrahedral Item", "zh": "P(4)：四面体"},
    "P(8): Octahedral Item": {"en": "P(8): Octahedral Item", "zh": "P(8)：八面体"},
    "P(20): Icosahedral Item": {"en": "P(20): Icosahedral Item", "zh": "P(20)：二十面体"},
}


def sym_type_option_label(canonical_val: str) -> str:
    '''Localized combo label; disk still uses ``canonical_val``.'''

    entry = _SYM_TYPE_LABELS.get(canonical_val)
    if entry is None:
        return canonical_val
    return entry.get(_lang()) or entry.get(UI_LANG_EN) or canonical_val


def preprocess_policy_label_text(policy_id: str) -> str:
    '''Localized short label for a preprocess policy id.'''

    key = "policy.%s" % policy_id
    if key in _STRINGS:
        return tr(key)
    return policy_id


def preprocess_policy_option_text(policy_id: str) -> str:
    '''Localized long label for preprocess policy selectable rows.'''

    key = "policy_option.%s" % policy_id
    if key in _STRINGS:
        return tr(key)
    return policy_id


def hardware_table_header(column: str) -> str:
    '''Column title for the detected-hardware table.'''

    return tr("hw.col_%s" % column)


def hardware_status_label(status: str) -> str:
    '''Map English status from device.py to localized table text.'''

    mapping = {
        "Selected": "hw.status_selected",
        "Available": "hw.status_available",
        "—": "hw.status_na",
        "Not selectable (CPU-only PyTorch)": "hw.status_not_selectable",
        "(none detected)": "hw.status_none_detected",
        "(none detected by PyTorch CUDA)": "hw.status_none_cuda",
    }
    key = mapping.get(status)
    if key:
        return tr(key)
    return status


def engine_speed_hint_text(*, cuda_available: bool) -> str:
    '''Localized engine speed note for the active UI language.'''

    if cuda_available:
        return tr("hint.engine_speed_gpu")
    return tr("hint.engine_speed_cpu")


def kasalv1_usage_hint_text() -> str:
    return tr("hint.kasalv1_usage")


def kasalv1_block_reason_text(job: SymmetryJobSpec) -> str | None:
    reason = kasalv1_job_blocked_reason(job)
    if reason is None:
        return None
    if _lang() == UI_LANG_EN:
        return reason
    sym_type = job.sym_type
    if sym_type in ("None", ""):
        return tr("hint.kasalv1_block_unlabeled")
    return tr("hint.kasalv1_block_auto")


def symmetry_routing_note_text(job: SymmetryJobSpec) -> str | None:
    note = symmetry_job_routing_note(job)
    if note is None:
        return None
    if _lang() == UI_LANG_EN:
        return note
    return tr("hint.routing_unlabeled_kasalv2")


def gpu_install_hint_text() -> str | None:
    hint = gpu_install_hint_message()
    if hint is None:
        return None
    if _lang() == UI_LANG_EN:
        return hint
    from kasal.device import detect_hardware_nvidia_gpus

    hardware = detect_hardware_nvidia_gpus()
    if not hardware:
        return None
    joined = "; ".join(hardware)
    return tr(
        "hint.gpu_install",
        gpus=joined,
        cmd=GPU_INSTALL_CMD,
        doc=GPU_INSTALL_DOC,
    )


def cuda_available_hint_text() -> str:
    return tr("hint.cuda_available")


def cpu_only_build_hint_text() -> str:
    return tr("hint.cpu_only_build")


def dataset_folder_error_text(error_key: str, **fmt) -> str:
    return tr("folder_error.%s" % error_key, **fmt)


def batch_status_text(status_key: str, **fmt) -> str:
    '''Build a localized batch-status line shown on the KASAL panel.'''

    saved_n = int(fmt.pop("saved", 0))
    total_n = int(fmt.pop("total", 0))
    unsaved_n = int(fmt.pop("unsaved", 0))
    engine = fmt.pop("engine", None)
    if engine is not None:
        prefix = tr("batch.%s" % status_key, engine)
    elif fmt:
        prefix = tr("batch.%s" % status_key, **fmt)
    else:
        prefix = tr("batch.%s" % status_key)
    suffix = tr(
        "batch.status_suffix",
        saved=saved_n,
        total=total_n,
        unsaved=unsaved_n,
    )
    return "%s%s" % (prefix, suffix)


def batch_status_progress_text(
    index: int,
    total: int,
    mesh_name: str,
    engine: str,
) -> str:
    return tr(
        "batch.cal_all_progress",
        index=index,
        total=total,
        mesh=mesh_name,
        engine=engine,
    )


def batch_status_skip_text(mesh_name: str, block_reason: str) -> str:
    return tr("batch.cal_all_skip", mesh=mesh_name, reason=block_reason)


def cleared_labels_status_text(
    json_removed: int,
    ply_removed: int,
    objects: int,
    total: int,
) -> str:
    return tr(
        "batch.cleared_all",
        json_removed,
        ply_removed,
        objects,
        total,
        total,
        total,
    )


_STRINGS: dict[str, dict[str, str]] = {
    # Setup page
    "setup.title": {"en": "Setup", "zh": "设置（Setup）"},
    "setup.language": {"en": "Interface language", "zh": "界面语言"},
    "setup.lang_en": {"en": "English", "zh": "English"},
    "setup.lang_zh": {"en": "Chinese", "zh": "中文"},
    "setup.font_size": {
        "en": "Interface text size",
        "zh": "界面文字大小",
    },
    "setup.font_size_hint": {
        "en": "Scales all side-panel text (English and Chinese). Range 0.8–1.5; default 1.2.",
        "zh": "缩放侧栏全部文字（中英文通用）。范围 0.8–1.5，默认 1.2。",
    },
    "setup.dataset_folder": {"en": "Current dataset folder", "zh": "当前数据集文件夹"},
    "setup.open_folder": {"en": "Open another folder...", "zh": "打开其他文件夹…"},
    "setup.preprocess_mode": {"en": "Mesh preprocessing mode", "zh": "网格预处理模式"},
    "setup.pymeshlab_warning": {
        "en": "[Warning] PyMeshLab not detected. Legacy / adaptive fallback disabled.",
        "zh": "[警告] 未检测到 PyMeshLab，legacy / adaptive 回退已禁用。",
    },
    "setup.compute_device": {
        "en": "Compute device (kasalv2 / GPU stages)",
        "zh": "计算设备（kasalv2 / GPU 阶段）",
    },
    "setup.detected_hardware": {"en": "Detected on this PC:", "zh": "本机检测到的硬件："},
    "setup.dismiss_checkbox": {
        "en": "Do not show again this session",
        "zh": "本次会话不再显示",
    },
    "setup.confirm": {"en": "Confirm", "zh": "确认"},
    "setup.none": {"en": "(none)", "zh": "（无）"},
    # Preprocess policy labels
    "policy.kasalv2_adaptive": {
        "en": "kasalv2 + adaptive fallback (recommended)",
        "zh": "kasalv2 + 自适应回退（推荐）",
    },
    "policy.kasalv2_strict": {
        "en": "kasalv2 only (no PyMeshLab fallback)",
        "zh": "仅 kasalv2（无 PyMeshLab 回退）",
    },
    "policy.kasalv1": {
        "en": "kasalv1 PyMeshLab simplify (~40k faces)",
        "zh": "kasalv1 PyMeshLab 简化（约 4 万面）",
    },
    "policy_option.kasalv2_adaptive": {
        "en": "Recommended: kasalv2 + adaptive fallback",
        "zh": "推荐：kasalv2 + 自适应回退",
    },
    "policy_option.kasalv2_strict": {
        "en": "kasalv2 only (no PyMeshLab fallback)",
        "zh": "仅 kasalv2（无 PyMeshLab 回退）",
    },
    "policy_option.kasalv1": {
        "en": "kasalv1 simplify (~40k faces, PyMeshLab)",
        "zh": "kasalv1 简化（约 4 万面，PyMeshLab）",
    },
    # Preprocess confirm modal
    "confirm_preprocess.title": {
        "en": "Warning: confirm session settings",
        "zh": "警告：确认会话设置",
    },
    "confirm_preprocess.body1": {
        "en": "These choices affect how every mesh is loaded and how kasalv2 runs. "
        "They are written to KASAL.json in the dataset folder.",
        "zh": "这些选项会影响每个网格的加载方式以及 kasalv2 的运行方式，"
        "并会写入数据集文件夹中的 KASAL.json。",
    },
    "confirm_preprocess.body2": {
        "en": "Switching preprocess policy later can change symmetry classification on the same file. "
        "Pick kasalv1 only if you need legacy PyMeshLab simplification.",
        "zh": "之后更换预处理策略可能会改变同一文件的对称分类结果。"
        "仅在需要 legacy PyMeshLab 简化时选择 kasalv1。",
    },
    "confirm_preprocess.dataset": {"en": "Dataset:", "zh": "数据集："},
    "confirm_preprocess.preprocess": {"en": "Preprocess: %s", "zh": "预处理：%s"},
    "confirm_preprocess.device": {"en": "Device: %s", "zh": "设备：%s"},
    "confirm_preprocess.dismiss_note": {
        "en": "This session will hide the setup panel until you restart the app.",
        "zh": "本次会话将隐藏设置面板，直至重启应用。",
    },
    "confirm_preprocess.confirm_btn": {"en": "Confirm settings", "zh": "确认设置"},
    "confirm_preprocess.cancel_btn": {"en": "Cancel", "zh": "取消"},
    # Back to Setup modal
    "confirm_back_setup.title": {
        "en": "Warning: return to Setup",
        "zh": "警告：返回设置页",
    },
    "confirm_back_setup.body1": {
        "en": "You will leave the KASAL labeling panel and reopen Setup. "
        "Folder, preprocess policy, and compute device can be changed there.",
        "zh": "你将离开 KASAL 标注面板并重新打开设置页，"
        "可在那里修改文件夹、预处理策略和计算设备。",
    },
    "confirm_back_setup.body2": {
        "en": "Current symmetry labels on disk are not deleted, but you must Confirm "
        "Setup again to return to this panel.",
        "zh": "磁盘上的对称标注不会被删除，但需要再次确认设置后才能返回本面板。",
    },
    "confirm_back_setup.confirm_btn": {
        "en": "Confirm back to Setup",
        "zh": "确认返回设置",
    },
    "confirm_back_setup.cancel_btn": {"en": "Cancel", "zh": "取消"},
    # KASAL main panel
    "kasal.title": {"en": "KASAL", "zh": "KASAL"},
    "kasal.subtitle": {
        "en": "Toolkit for Symmetry Axis Localization",
        "zh": "对称轴定位工具包",
    },
    "kasal.dataset": {"en": "Dataset: %s", "zh": "数据集：%s"},
    "kasal.cal_current": {"en": "Cal Current:", "zh": "当前计算："},
    "kasal.cal_all": {"en": "Cal All (unsaved):", "zh": "批量计算（未保存）："},
    "kasal.sources": {
        "en": "sym_type: %s | n_fold: %s",
        "zh": "sym_type：%s | n_fold：%s",
    },
    "kasal.saved_unsaved": {
        "en": "saved: %d/%d | unsaved: %d/%d",
        "zh": "已保存：%d/%d | 未保存：%d/%d",
    },
    "kasal.symmetry_type": {"en": "Symmetry Type:", "zh": "对称类型："},
    "kasal.d_setting": {"en": "Setting of D(>1) and D(=1)", "zh": "D(>1) 与 D(=1) 设置"},
    "kasal.n_note": {
        "en": "Note: if n < 2, n = 2; if n > 90, n = 90 !",
        "zh": "说明：若 n < 2 则 n = 2；若 n > 90 则 n = 90！",
    },
    "kasal.n_fold": {"en": "N (n-fold):", "zh": "N（n 折）："},
    "kasal.adi_c": {"en": "ADI-C:", "zh": "ADI-C："},
    "kasal.axis_xyz": {"en": "axis xyz: ", "zh": "axis xyz："},
    "kasal.show_xyz": {"en": "show xyz: ", "zh": "显示 xyz："},
    "kasal.last_object": {"en": "Last Object", "zh": "上一个物体"},
    "kasal.next_object": {"en": "Next Object", "zh": "下一个物体"},
    "kasal.cal_current_btn": {"en": "Cal Current Obj", "zh": "计算当前物体"},
    "kasal.cal_all_btn": {"en": "Cal All Objs", "zh": "批量计算"},
    "kasal.mark_all_hint": {
        "en": "Mark all: force every object into the Cal All queue.",
        "zh": "全部标记：将所有物体加入批量计算队列。",
    },
    "kasal.restore_hint": {
        "en": "Restore: re-read *_sym_type.json (kasalv1 labels stay saved).",
        "zh": "恢复：重新读取 *_sym_type.json（kasalv1 手工标注仍视为已保存）。",
    },
    "kasal.mark_all_btn": {"en": "Mark all as unsaved", "zh": "全部标为未保存"},
    "kasal.restore_btn": {"en": "Restore saved state", "zh": "恢复已保存状态"},
    "kasal.clear_hint": {
        "en": "Clear all labels: permanently delete every *_sym_type.json and *_sym.ply.",
        "zh": "清除全部标注：永久删除所有 *_sym_type.json 与 *_sym.ply。",
    },
    "kasal.clear_btn": {"en": "Clear all labels (DANGER)", "zh": "清除全部标注（危险）"},
    "kasal.back_to_setup": {
        "en": "Back to Setup (folder / preprocess / device)",
        "zh": "返回设置（文件夹 / 预处理 / 设备）",
    },
    # Hardware table
    "hw.col_type": {"en": "Type", "zh": "类型"},
    "hw.col_model": {"en": "Model", "zh": "型号"},
    "hw.col_status": {"en": "Status", "zh": "状态"},
    "hw.status_selected": {"en": "Selected", "zh": "已选"},
    "hw.status_available": {"en": "Available", "zh": "可用"},
    "hw.status_na": {"en": "—", "zh": "—"},
    "hw.status_not_selectable": {
        "en": "Not selectable (CPU-only PyTorch)",
        "zh": "不可选（CPU-only PyTorch）",
    },
    "hw.status_none_detected": {"en": "(none detected)", "zh": "（未检测到）"},
    "hw.status_none_cuda": {
        "en": "(none detected by PyTorch CUDA)",
        "zh": "（PyTorch CUDA 未检测到）",
    },
    # Dynamic hints
    "hint.engine_speed_gpu": {
        "en": "GPU build: kasalv2 is typically faster than kasalv1.",
        "zh": "GPU 版：kasalv2 通常快于 kasalv1。",
    },
    "hint.engine_speed_cpu": {
        "en": "CPU build: kasalv1 is typically faster than kasalv2.",
        "zh": "CPU 版：kasalv1 通常快于 kasalv2。",
    },
    "hint.kasalv1_usage": {
        "en": "kasalv1 computes when a concrete symmetry type is available in the UI; "
        "unlabeled objects use kasalv2 first.",
        "zh": "只要界面中已有具体对称类型，kasalv1 就可以计算；"
        "未标注物体会先使用 kasalv2。",
    },
    "hint.kasalv1_block_unlabeled": {
        "en": "kasalv1 requires symmetry type and n-fold set in the UI (object is unlabeled).",
        "zh": "kasalv1 需要在界面中指定对称类型与 n 折（当前物体未标注）。",
    },
    "hint.kasalv1_block_auto": {
        "en": "kasalv1 requires a concrete symmetry type before it can compute.",
        "zh": "kasalv1 需要已有具体对称类型后才能计算。",
    },
    "hint.routing_unlabeled_kasalv2": {
        "en": "Unlabeled object: compute will use kasalv2 "
        "(kasalv1 requires user-set symmetry type and n-fold).",
        "zh": "未标注物体：将使用 kasalv2 计算"
        "（kasalv1 需要用户指定的对称类型与 n 折）。",
    },
    "hint.gpu_install": {
        "en": "NVIDIA GPU(s) detected on this PC (%(gpus)s), but the current conda env has "
        "CPU-only PyTorch. GPU cannot be used until you reinstall the GPU build: "
        "%(cmd)s (run inside KASAL/). See %(doc)s.",
        "zh": "本机检测到 NVIDIA GPU（%(gpus)s），但当前 conda 环境为 CPU-only PyTorch。"
        "需重装 GPU 版后方可使用 GPU：%(cmd)s（在 KASAL/ 目录内运行）。详见 %(doc)s。",
    },
    "hint.cuda_available": {
        "en": "CUDA is available. Select CPU or a listed GPU for kasalv2.",
        "zh": "CUDA 可用。请为 kasalv2 选择 CPU 或列表中的 GPU。",
    },
    "hint.cpu_only_build": {
        "en": "Only CPU is available in this PyTorch build.",
        "zh": "当前 PyTorch 构建仅支持 CPU。",
    },
    # Folder errors
    "folder_error.not_folder": {
        "en": "Not a folder: %s",
        "zh": "不是文件夹：%s",
    },
    "folder_error.no_meshes": {
        "en": "No .ply/.obj meshes found under:\n%s",
        "zh": "以下路径未找到 .ply/.obj 网格：\n%s",
    },
    "folder_error.compute_busy": {
        "en": "Cannot switch folder while a symmetry job is running.",
        "zh": "对称计算进行中，无法切换文件夹。",
    },
    # Batch / status messages (KASAL panel)
    "batch.stopped": {"en": "Compute stopped by user", "zh": "用户已停止计算"},
    "batch.cal_current_done": {"en": "Cal Current finished", "zh": "当前物体计算完成"},
    "batch.cal_all_skipped": {"en": "Cal All skipped", "zh": "批量计算已跳过"},
    "batch.cal_all_done": {"en": "Cal All finished (%s)", "zh": "批量计算完成（%s）"},
    "batch.queued_all": {"en": "Queued all for Cal All", "zh": "已全部加入批量计算队列"},
    "batch.restored": {"en": "Restored from disk", "zh": "已从磁盘恢复"},
    "batch.returned_setup": {
        "en": "Returned to Setup (folder / preprocess / device).",
        "zh": "已返回设置页（文件夹 / 预处理 / 设备）。",
    },
    "batch.setup_blocked": {
        "en": "Cannot open Setup while a symmetry job is running.",
        "zh": "对称计算进行中，无法打开设置页。",
    },
    "batch.loaded_folder": {
        "en": "Loaded folder: %(name)s (%(count)d objects)",
        "zh": "已加载文件夹：%(name)s（%(count)d 个物体）",
    },
    "batch.status_suffix": {
        "en": ": saved %(saved)d/%(total)d, unsaved %(unsaved)d/%(total)d.",
        "zh": "：已保存 %(saved)d/%(total)d，未保存 %(unsaved)d/%(total)d。",
    },
    "batch.cal_all_progress": {
        "en": "Cal All %(index)d/%(total)d: %(mesh)s (engine=%(engine)s) ...",
        "zh": "批量计算 %(index)d/%(total)d：%(mesh)s（引擎=%(engine)s）…",
    },
    "batch.cal_all_skip": {
        "en": "Cal All skip %(mesh)s: %(reason)s",
        "zh": "批量计算跳过 %(mesh)s：%(reason)s",
    },
    "batch.cleared_all": {
        "en": "Cleared all labels: removed %d json, %d sym.ply across %d object(s). "
        "saved 0/%d, unsaved %d/%d.",
        "zh": "已清除全部标注：删除 %d 个 json、%d 个 sym.ply（共 %d 个物体）。"
        "已保存 0/%d，未保存 %d/%d。",
    },
}
