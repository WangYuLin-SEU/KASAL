# rotational_symmetry package

This package contains the KASALv2 rotational-symmetry analysis and dataset annotation pipeline.

## Main modules

- `run_dataset.py`: command-line entry for annotation of a flat mesh directory.
- `pipeline.py`: file selection, multiprocessing, failure capture, and summary writing.
- `model_preprocess.py`: mesh loading, sampling, normalization, and optional color extraction.
- `analyzer.py`: geometric rotational-symmetry analysis and optional texture refinement.
- `output_schema.py`: conversion from analysis results to serializable BOP-style JSON and summary rows.
- `../config/algorithms.py`: shared algorithm thresholds, sampling, mesh simplification, and ICP parameters.
  `build_analysis_config(device=..., fps_sample_count=...)` applies explicit runtime choices to the defaults.

## Data flow

```text
mesh file
  -> model_preprocess.load_preprocessed_model(...)
  -> analyzer.analyze_rotational_symmetry(...)
  -> output_schema.build_model_output_json(...)
  -> <output>/<mesh_stem>/<mesh_stem>_bop.json
```

The pipeline generates annotations from input meshes and does not read ground-truth labels. For installation and public usage, see the repository [README](../../README.md) and [installation guide](../../docs/install.md).
