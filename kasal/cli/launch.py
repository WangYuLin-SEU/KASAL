"""Launch the installed desktop application on a writable mesh directory."""

from __future__ import annotations

import argparse
import multiprocessing as mp
from pathlib import Path


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Open the KASALv2 desktop application")
    parser.add_argument("mesh_dir", type=Path, help="Directory containing your PLY or OBJ meshes")
    args = parser.parse_args(argv)
    mesh_dir = args.mesh_dir.expanduser().resolve()
    if not mesh_dir.is_dir():
        parser.error(f"mesh directory does not exist or is not a directory: {mesh_dir}")

    # Parse --help before importing native window libraries.
    from kasal.app.polyscope_app import app

    mp.freeze_support()
    app(str(mesh_dir))


if __name__ == "__main__":
    main()
