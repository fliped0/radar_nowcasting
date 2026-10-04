# Radar Nowcasting

Long-term research workspace for radar-based precipitation nowcasting.

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
