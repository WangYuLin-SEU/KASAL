# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LabelConfig:
    error: str = "Error"
    non_rotational: str = "non_rotational"
    spherical: str = "spherical"
    circular: str = "C(=1): Circular Item"
    cylindrical: str = "C(>1): Cylindrical Item"
    pyramidal: str = "D(=1): n-fold Pyramidal Item"
    prismatic: str = "D(>1): n-fold Prismatic Item"
    tetrahedral: str = "P(4): Tetrahedral Item"
    octahedral: str = "P(8): Octahedral Item"
    icosahedral: str = "P(20): Icosahedral Item"


@dataclass(frozen=True)
class SeedConfig:
    value: int = 0


@dataclass(frozen=True)
class SamplingConfig:
    fps_sample_count: int = 1500
    fps_h: int = 3
    mesh_surface_candidate_multiplier: int = 8
    fps_start_idx: int | None = None
    optimization_sample_count: int = 1024


@dataclass(frozen=True)
class AxisSearchConfig:
    device: str = "cuda"
    primary_steps: int = 5
    primary_max_angle_deg: float = 10.0
    primary_lr: float = 0.04
    primary_lambda_z: float = 0.0
    primary_coarse_num: int = 128
    primary_topk: int = 6
    primary_fine_num: int = 8
    primary_topk_adam: int = 3
    primary_early_stop_delta: float = 1e-4
    primary_early_stop_patience: int = 3
    secondary_steps: int = 5
    secondary_lambda_pen: float = 0.01
    secondary_lr: float = 0.05
    secondary_topk_factor: int = 2
    secondary_sample_factor: int = 8
    secondary_early_stop_delta: float = 1e-4
    secondary_early_stop_patience: int = 4


@dataclass(frozen=True)
class PeriodicityConfig:
    plane_samples: int = 360
    continuous_fold_value: float = float("inf")
    continuous_flat_std_threshold: float = 0.003
    continuous_dc_ratio_threshold: float = 0.98
    smooth: bool = True
    smooth_win: int = 17
    smooth_poly: int = 3
    tol_ratio: float = 0.10
    use_troughs: bool = True
    trim_margin: float = 0.0001
    first_trim_ignore_frac: float = 0.01
    second_trim_ignore_frac: float = 0.001
    baseline_method: str = "moving"
    baseline_alpha: float = 0.9
    baseline_window_divisor: int = 8
    baseline_window_kind: str = "hann"
    baseline_wrap: bool = True
    baseline_use_fft: bool = True
    flat_smooth_win_frac: float = 0.15
    flat_min_dist_frac: float = 0.20
    flat_prom_frac: float = 0.15
    flat_single_peak_ratio: float = 2.0


@dataclass(frozen=True)
class RefinementConfig:
    voxel_size_divisor: float = 50.0
    downsample_divisor: float = 4.0
    icp_distance_factor: float = 10.0
    icp_relative_fitness: float = 1e-6
    icp_relative_rmse: float = 1e-6
    icp_max_iteration: int = 100


@dataclass(frozen=True)
class ConsistencyConfig:
    bad_ratio_th: float = 0.10
    q: float = 0.80
    gain: float = 1.5
    floor_ratio: float = 0.01
    ceil_ratio: float = 0.03


@dataclass(frozen=True)
class ContourConfig:
    grid: int = 1024
    margin: float = 0.06
    pad_px: int = 24
    close_radius_px: int = 2
    fill_holes: bool = True
    keep_largest_cc: bool = True
    min_contour_pts: int = 50
    circle_threshold: float = 0.95
    energy_threshold: float = 1e-3
    resample_points: int = 2048
    radial_fft_samples: int = 720


@dataclass(frozen=True)
class TextureConfig:
    device: str = "cuda"
    n_max_tex: int = 20
    order_gain_threshold: float = 0.20
    order_col_var_threshold: float = 1e-4
    continuous_samples: int = 180
    continuous_flat_cv_threshold: float = 0.05
    continuous_cluster_gap: int = 3
    continuous_gap_cv_threshold: float = 0.25
    finite_baseline_samples: int = 72
    finite_baseline_quantile: float = 0.75
    ring_search_dirs: int = 180
    ring_gain_threshold: float = 0.20
    ring_cluster_gap: int = 3
    ring_min_points: int = 64
    color_bad_ratio_threshold: float = 0.20
    color_gain: float = 0.60
    color_lo: float = 0.05
    color_hi: float = 0.25
    side_axis_dirs: int = 360


@dataclass(frozen=True)
class ClassificationConfig:
    primary_orders: tuple[int, ...] = (3, 4, 5, 6)
    fallback_orders: tuple[int, ...] = (2, 1)
    dominant_axis_retry_max_fold: int = 2
    dominant_axis_loss_ratio: float = 0.05
    secondary_axis_loss_ratio: float = 0.02
    continuous_fold_cutoff: int = 15
    max_discrete_fold_direct: int = 6
    large_fold_angle_window_deg: float = 120.0
    two_fold_angle_deg: float = 90.0
    continuous_probe_angle_deg: float = 45.0
    rotation_loss_device: str | None = None


@dataclass(frozen=True)
class SymmetryAnalysisConfig:
    seed: SeedConfig = field(default_factory=SeedConfig)
    labels: LabelConfig = field(default_factory=LabelConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    axis_search: AxisSearchConfig = field(default_factory=AxisSearchConfig)
    periodicity: PeriodicityConfig = field(default_factory=PeriodicityConfig)
    refinement: RefinementConfig = field(default_factory=RefinementConfig)
    consistency: ConsistencyConfig = field(default_factory=ConsistencyConfig)
    contour: ContourConfig = field(default_factory=ContourConfig)
    texture: TextureConfig = field(default_factory=TextureConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)


DEFAULT_ANALYSIS_CONFIG = SymmetryAnalysisConfig()
