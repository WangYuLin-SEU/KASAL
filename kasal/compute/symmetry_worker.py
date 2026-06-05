# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

# Subprocess entry for GUI symmetry jobs (avoids GIL blocking Polyscope).

from __future__ import annotations

from kasal.compute.symmetry_job import SymmetryJobSpec, run_symmetry_job
from kasal.utils.compute_progress import (
    clear_progress_ipc_queue,
    get_compute_progress,
    set_progress_ipc_queue,
)


def mp_symmetry_worker_entry(job: SymmetryJobSpec, progress_queue, progress_meta: dict) -> None:
    """Target for multiprocessing.Process; must stay top-level for Windows spawn."""

    set_progress_ipc_queue(progress_queue)
    pg = get_compute_progress()
    pg.begin_object(
        progress_meta["mesh_name"],
        object_index=int(progress_meta["progress_index"]),
        object_total=int(progress_meta["progress_total"]),
        engine=progress_meta.get("engine", job.engine),
    )
    try:
        result = run_symmetry_job(job)
        progress_queue.put(("done", (job, result, None)))
    except Exception as exc:
        progress_queue.put(("done", (job, None, exc)))
    finally:
        clear_progress_ipc_queue()
