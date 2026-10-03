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
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from kasal.utils.io_json import write_json
from kasal.utils.atomic_file import atomic_output_path

from kasal.config.algorithms import DEFAULT_ANALYSIS_CONFIG, build_analysis_config
from kasal.device import resolve_torch_device
from .output_schema import (
    SUMMARY_CSV_FIELDS,
    build_analysis_result,
    build_model_output_json,
    build_summary_csv_row,
)


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


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def process_one_dataset_model(
    input_model: str,
    input_root: str,
    output_root: str,
    tex: bool,
    fps_sample_count: int | None,
) -> dict[str, Any]:
    input_path = Path(input_model)
    input_root_path = Path(input_root)
    output_root_path = Path(output_root)
    object_name = input_path.stem
    object_output_dir = output_root_path / object_name

    try:
        from .analyzer import analyze_rotational_symmetry
        from .model_preprocess import load_preprocessed_model

        analysis_config = build_analysis_config(
            device=resolve_torch_device(DEFAULT_ANALYSIS_CONFIG.axis_search.device),
            fps_sample_count=fps_sample_count,
        )
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
        object_output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_json, result, ensure_ascii=False)
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
        return _failed_dataset_result(
            object_name,
            traceback.format_exc(),
            model=input_path.name,
            model_relpath=_relative_path(input_path, input_root_path),
        )


def _failed_dataset_result(object_name, error, *, model=None, model_relpath=None) -> dict[str, Any]:
    """Use the same failure record for model errors and worker failures."""

    return {
        "object": object_name,
        "model": model,
        "model_relpath": model_relpath,
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
        "error": error,
    }


def _print_dataset_progress(item, index, total, success_count, started_at) -> None:
    elapsed = max(time.time() - started_at, 1e-6)
    eta = elapsed / index * (total - index)
    status = "ok" if item["success"] else "error"
    print(
        f"[DATASET] progress {index}/{total} ({100.0 * index / total:.1f}%) | "
        f"ok={success_count} fail={index - success_count} | last={item['object']} ({status}) | "
        f"elapsed={elapsed:.1f}s eta={eta:.1f}s",
        flush=True,
    )


def run_dataset_batch(
    input_models: list[Path],
    *,
    input_root: Path,
    output_root: Path,
    tex: bool,
    workers: int,
    fps_sample_count: int | None,
) -> list[dict[str, Any]]:
    total = len(input_models)
    started_at = time.time()
    success_count = 0
    summary = []
    print(
        f"[DATASET] START total={total} workers={workers} output={output_root}",
        flush=True,
    )

    if workers <= 1:
        for index, input_model in enumerate(input_models, start=1):
            object_name = input_model.stem
            print(f"[DATASET] processing: {object_name}", flush=True)
            item = process_one_dataset_model(
                str(input_model), str(input_root), str(output_root), tex, fps_sample_count
            )
            summary.append(item)
            success_count += int(item["success"])
            _print_dataset_progress(item, index, total, success_count, started_at)
    else:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
            future_to_object = {
                executor.submit(
                    process_one_dataset_model,
                    str(input_model), str(input_root), str(output_root), tex, fps_sample_count,
                ): input_model.stem
                for input_model in input_models
            }
            for index, future in enumerate(as_completed(future_to_object), start=1):
                object_name = future_to_object[future]
                try:
                    item = future.result()
                except Exception:
                    item = _failed_dataset_result(object_name, traceback.format_exc())
                summary.append(item)
                success_count += int(item["success"])
                _print_dataset_progress(item, index, total, success_count, started_at)

    print(f"[DATASET] COMPLETE {success_count}/{total} succeeded", flush=True)
    return sorted(summary, key=lambda item: item["object"])


def write_dataset_summary(output_dir: Path, summary: list[dict[str, Any]]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / "batch_summary.json"
    summary_csv = output_dir / "batch_summary.csv"
    with (
        atomic_output_path(summary_csv) as temporary_csv,
        atomic_output_path(summary_json) as temporary_json,
    ):
        with temporary_json.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        with temporary_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(SUMMARY_CSV_FIELDS)
            for item in summary:
                writer.writerow(build_summary_csv_row(item))
            f.flush()
            os.fsync(f.fileno())

    return summary_json, summary_csv
