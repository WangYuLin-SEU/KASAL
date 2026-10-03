# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Mutable GUI state and display defaults, local to each process."""

# Dataset settings and current selection.

settings_path = ''

adi_color_enabled = False

show_coordinate_axes = False

selected_n_fold = 2

# Canonical labels are also used in saved annotations.

symmetry_type_options = [
    "None",
    "C(>>1): Spherical Item",
    "C(>1): Cylindrical Item",
    "C(=1): Circular Item",
    "D(>1): n-fold Prismatic Item",
    "D(=1): n-fold Pyramidal Item",
    "P(4): Tetrahedral Item",
    "P(8): Octahedral Item",
    "P(20): Icosahedral Item",
]

selected_symmetry_type = symmetry_type_options[0]

# Optional coordinate-axis constraint for the primary search.

axis_constraint_options = [
    "None",
    "axis X (red)",
    "axis Y (green)",
    "axis Z (blue)",
]

selected_axis_constraint = axis_constraint_options[0]

# Dataset navigation and registered Polyscope structures.

mesh_paths = None

current_mesh_index = 0

displayed_meshes = []

# Display texture resolution in pixels.

uv_texture_size = 500

max_n_fold = 90

current_obj_info = {}

# Arrow scale relative to the mesh diameter.

arrow_ratio = 1.0

save_twofold_axis = True

disable_color_analysis = False

# Engine and preprocessing choices for interactive jobs.

compute_engine = "kasalv2"

batch_compute_engine = "kasalv2"

mesh_preprocess_policy = "kasalv2_adaptive"

# Provenance distinguishes manual labels from automatic results.

sym_type_source = "kasalv2_auto"

n_fold_source = "kasalv2_auto"

axis_xyz_source = "none"

# Invalid sidecars remain protected until explicitly marked dirty.

annotation_dirty = {}

annotation_load_errors = {}

# GUI settings; language and font scale are persisted in KASAL.json.

models_dir = ""

ui_language = "en"

ui_font_scale = 1.2

ui_font_base_pt = 15.0

ui_font_scale_min = 0.8

ui_font_scale_max = 1.5

ui_font_scale_step = 0.05

ui_max_fps = 33

# Setup and folder-picker state.

preprocess_modal_confirmed = False

preprocess_modal_dismiss = False

open_folder_picker_pending = False

dataset_folder_error = ""

settings_load_warning = ""

device_selection_warning = ""

# Device choice is mirrored to KASAL_TORCH_DEVICE for worker processes.

torch_device_id = ""

torch_device_options = []

ui_batch_status = ""

# Pending actions start outside the popup callback.

cal_all_run_pending = False

cal_current_run_pending = False

# Active worker and its queued result.

compute_worker_process = None

compute_worker_queue = None

compute_worker_job = None

compute_worker_done = False

compute_worker_result = None

compute_worker_refresh_status = True

# Batch cursor and the mesh index to restore afterward.

cal_all_batch = None

# Discard a canceled worker result while keeping the UI responsive.

compute_worker_discard = False

compute_aborted = False

progress_modal_needs_center = False

engine_options = ["kasalv1", "kasalv2"]

mesh_preprocess_policy_options = [
    "kasalv2_adaptive",
    "kasalv2_strict",
    "kasalv1",
]
