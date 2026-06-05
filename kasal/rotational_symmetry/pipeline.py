# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import csv
import json
import multiprocessing as mp
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import DEFAULT_ANALYSIS_CONFIG, SymmetryAnalysisConfig
from .device import apply_device_to_config
from .progress_tracker import finish_progress, init_progress, update_progress
from .output_schema import (
    SUMMARY_CSV_FIELDS,
    build_analysis_result,
    build_model_output_json,
    build_summary_csv_row,
)


def object_name_from_mesh(input_model: Path) -> str:
    return input_model.stem


def discover_dataset_meshes(
    input_dir: Path,
    *,
    pattern: str,
) -> list[Path]:
    return sorted(input_dir.glob(pattern))


def select_chunk(
    meshes: list[Path],
    *,
    start: int,
    count: int | None,
    chunk_index: int | None,
    chunk_size: int | None,
) -> tuple[list[Path], int, int | None]:
    if chunk_size is not None and int(chunk_size) > 0:
        chunk_idx = max(int(chunk_index or 0), 0)
        resolved_start = chunk_idx * int(chunk_size)
        resolved_count = int(chunk_size)
    else:
        resolved_start = max(int(start), 0)
        resolved_count = int(count) if count is not None and int(count) > 0 else None

    end = None if resolved_count is None else resolved_start + resolved_count
    return meshes[resolved_start:end], resolved_start, resolved_count


def build_analysis_config(fps_sample_count: int | None) -> SymmetryAnalysisConfig:
    if fps_sample_count is None:
        base = DEFAULT_ANALYSIS_CONFIG
    else:
        base = replace(
            DEFAULT_ANALYSIS_CONFIG,
            sampling=replace(DEFAULT_ANALYSIS_CONFIG.sampling, fps_sample_count=int(fps_sample_count)),
        )
    return apply_device_to_config(base)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _format_texture_status(item: dict[str, Any]) -> str:
    if item.get("tex_has_rot_sym") is None and item.get("tex_sym_type") is None:
        return ""
    return f" | tex_type={item.get('tex_sym_type')} | tex_fold={item.get('tex_n_fold')}"


def process_one_dataset_model(
    input_model: str,
    input_root: str,
    output_root: str,
    tex: bool,
    fps_sample_count: int | None,
) -> dict[str, Any]:
    from rotational_symmetry.analyzer import analyze_rotational_symmetry
    from rotational_symmetry.model_preprocess import load_preprocessed_model

    input_path = Path(input_model)
    input_root_path = Path(input_root)
    output_root_path = Path(output_root)
    object_name = object_name_from_mesh(input_path)
    object_output_dir = output_root_path / object_name
    object_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        analysis_config = build_analysis_config(fps_sample_count)
        preprocess_started_at = time.time()
        model_input, bbox_info = load_preprocessed_model(
            input_path=input_path,
            need_colors=tex,
            config=analysis_config,
        )
        preprocess_elapsed_sec = time.time() - preprocess_started_at

        analysis_started_at = time.time()
        raw_result, n_fold = analyze_rotational_symmetry(model_input, tex=tex, config=analysis_config)
        analysis_elapsed_sec = time.time() - analysis_started_at

        analysis = build_analysis_result(raw_result, n_fold)
        texture_symmetry = analysis.get("texture_symmetry") or {}
        postprocess_started_at = time.time()
        result = build_model_output_json(analysis, bbox_info)
        output_json = object_output_dir / f"{input_path.stem}_bop.json"
        output_json.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        postprocess_elapsed_sec = time.time() - postprocess_started_at

        return {
            "object": object_name,
            "model": input_path.name,
            "model_relpath": _relative_path(input_path, input_root_path),
            "output": _relative_path(output_json, output_root_path),
            "has_rot_sym": analysis["has_rot_sym"],
            "sym_type": analysis["sym_type"],
            "n_fold": analysis["n_fold"],
            "sym_op": analysis["sym_op"],
            "tex_has_rot_sym": texture_symmetry.get("has_rot_sym"),
            "tex_sym_type": texture_symmetry.get("sym_type"),
            "tex_n_fold": texture_symmetry.get("n_fold"),
            "tex_sym_op": texture_symmetry.get("sym_op"),
            "preprocess_sec": round(preprocess_elapsed_sec, 4),
            "analysis_sec": round(analysis_elapsed_sec, 4),
            "postprocess_sec": round(postprocess_elapsed_sec, 4),
            "total_sec": round(preprocess_elapsed_sec + analysis_elapsed_sec + postprocess_elapsed_sec, 4),
            "success": True,
            "error": None,
        }
    except Exception:
        return {
            "object": object_name,
            "model": input_path.name,
            "model_relpath": _relative_path(input_path, input_root_path),
            "output": None,
            "has_rot_sym": False,
            "sym_type": None,
            "n_fold": None,
            "sym_op": "error",
            "tex_has_rot_sym": None,
            "tex_sym_type": None,
            "tex_n_fold": None,
            "tex_sym_op": None,
            "preprocess_sec": None,
            "analysis_sec": None,
            "postprocess_sec": None,
            "total_sec": None,
            "success": False,
            "error": traceback.format_exc(),
        }


def run_dataset_batch(
    input_models: list[Path],
    *,
    input_root: Path,
    output_root: Path,
    tex: bool,
    workers: int,
    fps_sample_count: int | None,
) -> list[dict[str, Any]]:
    tasks = [
        (
            str(input_model),
            str(input_root),
            str(output_root),
            tex,
            fps_sample_count,
        )
        for input_model in input_models
    ]

    total = len(tasks)
    init_progress(
        output_root,
        total=total,
        workers=workers,
        input_dir=str(input_root),
    )
    print(
        f"[DATASET] START total={total} workers={workers} output={output_root}",
        flush=True,
    )

    if workers <= 1:
        summary = []
        for index, task in enumerate(tasks, start=1):
            object_name = object_name_from_mesh(Path(task[0]))
            print(f"[DATASET] processing: {object_name}", flush=True)
            item = process_one_dataset_model(*task)
            update_progress(output_root, item=item, index=index, total=total)
            summary.append(item)
        finish_progress(output_root, success_count=sum(1 for x in summary if x["success"]), total=total)
        return sorted(summary, key=lambda item: item["object"])

    summary = []
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
        future_to_object = {
            executor.submit(process_one_dataset_model, *task): object_name_from_mesh(Path(task[0]))
            for task in tasks
        }
        for index, future in enumerate(as_completed(future_to_object), start=1):
            object_name = future_to_object[future]
            try:
                item = future.result()
            except Exception:
                item = {
                    "object": object_name,
                    "model": None,
                    "model_relpath": None,
                    "output": None,
                    "has_rot_sym": False,
                    "sym_type": None,
                    "n_fold": None,
                    "sym_op": "error",
                    "tex_has_rot_sym": None,
                    "tex_sym_type": None,
                    "tex_n_fold": None,
                    "tex_sym_op": None,
                    "preprocess_sec": None,
                    "analysis_sec": None,
                    "postprocess_sec": None,
                    "total_sec": None,
                    "success": False,
                    "error": traceback.format_exc(),
                }
            update_progress(output_root, item=item, index=index, total=total)
            summary.append(item)

    finish_progress(
        output_root,
        success_count=sum(1 for x in summary if x["success"]),
        total=total,
    )
    return sorted(summary, key=lambda item: item["object"])


def write_dataset_summary(output_dir: Path, summary: list[dict[str, Any]]) -> tuple[Path, Path]:
    summary_json = output_dir / "batch_summary.json"
    summary_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary_csv = output_dir / "batch_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(SUMMARY_CSV_FIELDS)
        for item in summary:
            writer.writerow(build_summary_csv_row(item))

    return summary_json, summary_csv
