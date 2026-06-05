# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

start_id_json_file = ''
# Path to KASAL.json  

is_true2 = False
# ADI-C activation status  

is_true3 = False
# Display status of the XYZ axes  

ui_int = 2
# Value of n in n-fold symmetry  

ui_options = [
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
# Options for the 8 types of rotational symmetry.  
# 'C' represents continuous rotational symmetry,  
# while 'D' represents discrete rotational symmetry.  

ui_options_selected = ui_options[0]
# The rotational symmetry type of the object is set to None by default.  

ui_xyz_options = [
    "None",
    "axis X (red)",
    "axis Y (green)",
    "axis Z (blue)",
]
# Options for x, y, and z axes.  
# For a few objects, KASAL may fail to accurately locate the symmetry axis.  
# For these objects, you can simply set one of the x, y, or z axes,  
# and KASAL will locate a symmetry axis close to the specified axis.  

ui_xyz_options_selected = ui_xyz_options[0]

files_name_list = None
# Paths to all object models in the folder.  

current_file_id = 0
# ID of the current object.  

psm_list = []
# List of objects displayed in polyscope.  

uv_texture_size = 500
# Texture image size of the object.  

ui_int_upper = 90
# Maximum value of n in the set of n-fold symmetry axes.  

sample_num = 5250 * 1 + 1
# Number of Fibonacci sphere sampling points.  

current_obj_info = {}
# Information of the current object.  

arrow_ratio = 1.0
# Scaling factor of the saved symmetry axes.  

save_2_fold_a = True

close_ADI_c = False
# Disable ADI-C.  

compute_engine = "kasalv2"
# Engine for Cal Current Obj: kasalv1 | kasalv2

batch_compute_engine = "kasalv2"
# Engine for Cal All (dirty objects only)

mesh_preprocess_policy = "kasalv2_adaptive"
# kasalv2_adaptive | kasalv2_strict | kasalv1

mesh_preprocess_backend = ""
mesh_preprocess_fallback_reason = ""
mesh_enrich_applied = []
mesh_topology = ""
format_route = ""

sym_type_source = "kasalv2_auto"
n_fold_source = "kasalv2_auto"
axis_xyz_source = "none"
kasalv2_snapshot = None

annotation_dirty = {}
saved_fingerprints = {}

models_dir = ""
# Root folder currently loaded in the GUI (dataset of PLY/OBJ meshes).
# 当前 GUI 加载的数据集根目录（PLY/OBJ 网格）。

ui_language = "en"
# Setup / KASAL panel language: ``en`` | ``zh``; persisted in KASAL.json.
# Setup / KASAL 面板语言：``en`` | ``zh``；写入 KASAL.json。

ui_font_scale = 1.2
# Global ImGui ``FontScaleMain`` (English + Chinese panels); persisted in KASAL.json.
# 全局 ImGui ``FontScaleMain``（中英文界面通用）；写入 KASAL.json。

preprocess_modal_confirmed = False
preprocess_modal_dismiss = False

open_folder_picker_pending = False
# Set by preprocess UI; native folder dialog runs on the next frame.

dataset_folder_error = ""
# Last in-app folder switch error (shown on preprocess panel).

torch_device_id = ""
# Active kasalv2 device: ``cpu`` or ``cuda:N``; mirrored to KASAL_TORCH_DEVICE.

torch_device_options = []
# Cached list[TorchDeviceOption] from list_torch_device_options().

ui_batch_status = ""
# Last Cal All / mark-unsaved / restore action message for the GUI panel.

cal_all_run_pending = False
# Set by confirm modal; executed at end of next UI frame (outside popup handler).

cal_current_run_pending = False
# Set by Cal Current button; worker starts on next UI frame.

compute_worker_process = None
compute_worker_queue = None
compute_worker_done = False
compute_worker_result = None
# (SymmetryJobSpec, SymmetryJobResult|None, Exception|None) from worker subprocess.

compute_worker_thread = None
# Deprecated alias; GUI uses compute_worker_process (multiprocessing).

compute_worker_meta = {}
# refresh_status, progress_index, progress_total for main-thread apply.

cal_all_batch = None
# dict with dirty_ids, next_idx, restore_file_id, engine, total while Cal All runs.

compute_worker_discard = False
# True after user confirms stop; completed worker result is thrown away.

compute_aborted = False
# True while UI is unlocked after stop until the background thread exits.

progress_modal_needs_center = False
# Set when a new compute job starts; center progress window on first frame.

engine_options = ["kasalv1", "kasalv2"]
mesh_preprocess_policy_options = [
    "kasalv2_adaptive",
    "kasalv2_strict",
    "kasalv1",
]
