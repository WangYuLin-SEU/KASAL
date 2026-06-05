# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rotational_symmetry.pipeline import (
    discover_dataset_meshes,
    run_dataset_batch,
    select_chunk,
    write_dataset_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run rotational symmetry annotation on a flat directory of PLY meshes and write BOP-style JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        default=argparse.SUPPRESS,
        help="Directory containing PLY mesh files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs") / "rotational_symmetry",
        help="Output directory for per-object BOP json files and batch summaries.",
    )
    parser.add_argument(
        "--pattern",
        default="*.ply",
        help="Glob pattern for mesh files directly under --input-dir.",
    )
    parser.add_argument(
        "--tex",
        action="store_true",
        help="Add a texture_symmetry layer. Requires vertex colors or texture data in the input PLY.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="Worker process count. Use 1 for single-process execution.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="0-based start index in the sorted mesh list.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of models to process from --start.",
    )
    parser.add_argument(
        "--chunk-index",
        type=int,
        default=None,
        help="0-based chunk index. Used with --chunk-size and overrides --start.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Chunk size. When set, selected range is chunk-index * chunk-size.",
    )
    parser.add_argument(
        "--fps-sample-count",
        type=int,
        default=None,
        help="Override the number of FPS analysis points sampled during preprocessing.",
    )
    return parser.parse_args()


def print_timing(summary: list[dict[str, object]]) -> None:
    successful_items = [item for item in summary if item["success"]]
    if not successful_items:
        return
    preprocess_sum = sum(float(item["preprocess_sec"]) for item in successful_items)
    analysis_sum = sum(float(item["analysis_sec"]) for item in successful_items)
    postprocess_sum = sum(float(item["postprocess_sec"]) for item in successful_items)
    total_sum = sum(float(item["total_sec"]) for item in successful_items)
    print(
        "[DATASET] timing share: "
        f"preprocess={preprocess_sum:.4f}s ({(preprocess_sum / total_sum) * 100:.1f}%) | "
        f"analysis={analysis_sum:.4f}s ({(analysis_sum / total_sum) * 100:.1f}%) | "
        f"postprocess={postprocess_sum:.4f}s ({(postprocess_sum / total_sum) * 100:.1f}%)"
    )


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    all_meshes = discover_dataset_meshes(
        input_dir,
        pattern=args.pattern,
    )
    if not all_meshes:
        raise FileNotFoundError(f"No meshes found in: {input_dir}")

    selected_meshes, selected_start, selected_count = select_chunk(
        all_meshes,
        start=args.start,
        count=args.count,
        chunk_index=args.chunk_index,
        chunk_size=args.chunk_size,
    )
    if not selected_meshes:
        raise FileNotFoundError(
            f"No selected meshes: start={selected_start}, count={selected_count}, total={len(all_meshes)}"
        )

    started_at = time.time()
    summary = run_dataset_batch(
        selected_meshes,
        input_root=input_dir,
        output_root=output_dir,
        tex=bool(args.tex),
        workers=max(args.workers, 1),
        fps_sample_count=args.fps_sample_count,
    )
    total_sec = time.time() - started_at
    summary_json, summary_csv = write_dataset_summary(output_dir, summary)

    success_count = sum(1 for item in summary if item["success"])

    print_timing(summary)
    print(
        f"[DATASET] selected: start={selected_start} | count={len(selected_meshes)} "
        f"| total_available={len(all_meshes)}"
    )
    print(f"[DATASET] processed models: {len(selected_meshes)}")
    print(f"[DATASET] success: {success_count} | failed: {len(selected_meshes) - success_count}")
    print(
        f"[DATASET] tex: {bool(args.tex)} | workers: {max(args.workers, 1)} | total_sec: {total_sec:.4f}"
    )
    print(f"[DATASET] summary json: {summary_json}")
    print(f"[DATASET] summary csv: {summary_csv}")

    return 0 if success_count == len(selected_meshes) else 1


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
