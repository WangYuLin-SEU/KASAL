# rotational_symmetry Package

This package contains the rotational symmetry analysis and dataset annotation pipeline.

## Main Modules

- `run_dataset.py`: command-line entry for mesh dataset annotation from a flat directory of `.ply` files.
- `pipeline.py`: dataset discovery, chunk selection, multiprocessing, and summary writing.
- `model_preprocess.py`: mesh loading, normalization, surface/point sampling, and optional color extraction.
- `analyzer.py`: geometric rotational symmetry analysis and optional texture-aware refinement.
- `output_schema.py`: conversion from raw analysis results to serializable BOP-style JSON and summary CSV rows.
- `config.py`: analysis thresholds and sampling parameters.

## Data Flow

```text
mesh file
  -> model_preprocess.load_preprocessed_model(...)
  -> analyzer.analyze_rotational_symmetry(...)
  -> output_schema.build_model_output_json(...)
  -> <object>/<mesh_stem>_bop.json
```

The main pipeline does not read GT labels. It generates annotations from the input meshes.

## Output Contract

Top-level JSON fields describe geometric rotational symmetry. When `--tex` is enabled, texture-aware symmetry is
stored separately under `texture_symmetry`; it does not overwrite the geometric result.

See the repository-level `README.md` for install instructions, command examples, input layouts, and the full output
schema.
