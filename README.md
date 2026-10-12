# Radar Nowcasting

Long-term research workspace for radar-based precipitation nowcasting.

## Current progress (2026-10-12)

Four baselines (Persistence, Optical Flow, S-PROG and STEPS), deterministic
verification and STEPS probabilistic verification are implemented. Both FMI cases
(`201609281600` and `201705091300`, UTC) completed all 14 workflow tasks on
2026-10-05 according to local run manifests. Per-case BSS relative to Persistence
and cross-case RMSE, categorical, BSS and CRPS summaries are also available locally.
Data and generated outputs are excluded from Git.

The project is at the two-case validation stage. Broader independent weather-case
evaluation and cross-case interpretation remain to be done; two cases do not
establish general performance. See [the progress record](docs/progress.md).

## Layout

- data/: sample, raw, and processed datasets
- baselines/: persistence, rainymotion, and pysteps baselines
- experiments/: experiment definitions and runs
- outputs/: figures, metrics, and forecast products
- scripts/: reusable command-line workflows
- notebooks/: exploratory analysis
- configs/: experiment and model configuration
- docs/: project documentation
- logs/: runtime logs
- environment/: reproducible environment specifications

## Case experiments

Run from the project root in the `radar-nowcasting` Conda environment:

```bash
python scripts/run_case.py --start-time 201609281600 --dry-run
python scripts/run_case.py --start-time 201609281600
python scripts/run_cases.py --cases configs/cases.json --dry-run
```

Times are UTC. The new entrypoints write to `outputs/cases/<case_id>/` and refuse
existing cases unless `--overwrite` is explicit. Numbered scripts without arguments
retain their original date, paths and behavior. The framework uses current PySTEPS
FMI rcparams and project-relative data paths; `configs/pystepsrc` is not required.

See [the experiment framework guide](docs/experiment_framework.md) for task
selection, dependencies, failure handling, tests and batch configuration.
