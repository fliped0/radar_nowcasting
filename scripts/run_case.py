"""Run existing tasks serially in one isolated FMI case directory."""

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys

from experiment_context import ExperimentContext, check_radar_inputs, parse_start_time


# Each task retains its calculation, figures, filenames and experiment constants.
SCRIPTS = {
    "01": "01_persistence.py", "02": "02_optical_flow.py",
    "04": "04_sprog.py", "05": "05_steps.py", "06": "06_steps_eval.py",
    "03": "03_compare_rmse.py", "07": "07_unified_evaluation.py",
    "08": "08_plot_threshold_metrics.py", "09": "09_steps_probabilistic_eval.py",
    "10": "10_plot_brier_score.py", "11": "11_steps_crps.py",
    "12": "12_plot_crps.py", "13": "13_steps_reliability.py",
    "14": "14_steps_spread_skill.py",
}
DEPENDENCIES = {
    "06": ("05",), "03": ("01", "02", "04", "06"),
    "07": ("01", "02", "04", "06"), "08": ("07",),
    "09": ("05",), "10": ("09",), "11": ("05",),
    "12": ("11",), "13": ("05",), "14": ("05",),
}
PRODUCTS = {
    "01": ("forecasts/persistence.npy", "metrics/persistence_rmse.csv",
           "persistence/persistence_vs_obs_60min.png", "persistence/persistence_rmse.png"),
    "02": ("forecasts/optical_flow.npy", "metrics/optical_flow_rmse.csv",
           "optical_flow/motion_field.png", "optical_flow/oflow_vs_obs_60min.png"),
    "04": ("forecasts/sprog.npy", "metrics/sprog_rmse.csv", "sprog/sprog_vs_obs_60min.png"),
    "05": ("steps/steps_forecast.npy",),
    "06": ("forecasts/steps_mean.npy", "metrics/steps_rmse.csv", "steps/steps_members_60min.png"),
    "03": ("evaluation/rmse_method_comparison.png",),
    "07": ("metrics/unified_metrics_threshold_1.0.csv", "metrics/unified_metrics_all_thresholds.csv"),
    "08": tuple(f"evaluation/{metric}_threshold_{threshold}.png"
                for metric in ("csi", "pod", "far") for threshold in (0.1, 1.0, 5.0)),
    "09": ("metrics/steps_brier_score.csv",),
    "10": ("evaluation/steps_brier_score.png",),
    "11": ("metrics/steps_crps.csv",),
    "12": ("evaluation/steps_crps.png",),
    "13": ("metrics/steps_reliability.csv",) + tuple(
        f"evaluation/steps_reliability_threshold_{threshold}.png" for threshold in (0.1, 1.0, 5.0)),
    "14": ("metrics/steps_spread_skill.csv", "evaluation/steps_spread_skill.png",
           "evaluation/steps_spread_skill_ratio.png"),
}
# Exact files consumed by each script; plotting does not require radar data.
INPUTS = {
    "06": ("steps/steps_forecast.npy",),
    "03": tuple(f"metrics/{name}_rmse.csv" for name in ("persistence", "optical_flow", "sprog", "steps")),
    "07": tuple(f"forecasts/{name}.npy" for name in ("persistence", "optical_flow", "sprog", "steps_mean")),
    "08": ("metrics/unified_metrics_all_thresholds.csv",),
    "09": ("steps/steps_forecast.npy",), "10": ("metrics/steps_brier_score.csv",),
    "11": ("steps/steps_forecast.npy",), "12": ("metrics/steps_crps.csv",),
    "13": ("steps/steps_forecast.npy",), "14": ("steps/steps_forecast.npy",),
}
RADAR_WINDOWS = {
    "01": (0, 12), "02": (2, 12), "04": (2, 12), "05": (2, 0),
    **{task: (0, 12) for task in ("06", "07", "09", "11", "13", "14")},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_tasks(value):
    selected = value.split(",")
    if len(set(selected)) != len(selected) or any(task not in SCRIPTS for task in selected):
        raise argparse.ArgumentTypeError("tasks must be unique comma-separated IDs 01 through 14")
    return tuple(task for task in SCRIPTS if task in selected)


def add_run_options(parser):
    parser.add_argument("--tasks", type=parse_tasks, default=tuple(SCRIPTS))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def load_existing(context, overwrite):
    root = context.output_root
    if not root.exists():
        return {}
    if not overwrite:
        raise FileExistsError(f"Case already exists: {root}; use --overwrite explicitly")
    path = root / "run_manifest.json"
    if not path.is_file():
        raise ValueError(f"Refusing an existing case without a run_manifest.json: {root}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("case_id") != context.case_id or manifest.get("start_time") != context.start_time:
        raise ValueError("Existing manifest does not match the requested UTC start time")
    return manifest


def check_dependencies(context, tasks, manifest):
    planned = set()
    produced = set()
    for task in tasks:
        for dependency in DEPENDENCIES.get(task, ()):
            if dependency not in planned:
                state = manifest.get("tasks", {}).get(dependency, {}).get("status")
                if state != "success":
                    raise ValueError(f"Task {task} requires successful task {dependency}; select it explicitly")
        for relative in INPUTS.get(task, ()):
            path = context.output_root / relative
            if relative not in produced and (not path.is_file() or path.stat().st_size == 0):
                raise FileNotFoundError(f"Task {task} requires {path}")
        planned.add(task)
        produced.update(PRODUCTS[task])


def preflight(context, tasks, manifest):
    check_dependencies(context, tasks, manifest)
    for task in tasks:
        if not (context.project_root / "scripts" / SCRIPTS[task]).is_file():
            raise FileNotFoundError(SCRIPTS[task])
    windows = [RADAR_WINDOWS[task] for task in tasks if task in RADAR_WINDOWS]
    if windows:
        check_radar_inputs(context, max(w[0] for w in windows), max(w[1] for w in windows))


def save_manifest(context, manifest):
    path = context.output_root / "run_manifest.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_case(context, tasks, overwrite=False, dry_run=False):
    """Return a compact result; fail a case without starting its remaining tasks."""
    result = {"case_id": context.case_id, "start_time": context.start_time,
              "status": "failed", "started_at": now()}
    writable = False
    manifest = None
    try:
        existing = load_existing(context, overwrite)
        if dry_run:
            preflight(context, tasks, existing)
            result["status"] = "checked"
            result["tasks"] = list(tasks)
            return result
        context.output_root.mkdir(parents=True, exist_ok=overwrite)
        writable = True
        manifest = {**result, "status": "running", "tasks": dict(existing.get("tasks", {}))}
        preflight(context, tasks, existing)
        for task in tasks:
            manifest["tasks"][task] = {"status": "pending"}
        save_manifest(context, manifest)
        log_dir = context.output_root / "logs"
        log_dir.mkdir(exist_ok=True)
        for task in tasks:
            record = manifest["tasks"][task]
            record.update(status="running", started_at=now())
            save_manifest(context, manifest)
            print(f"{context.case_id}: task {task} {SCRIPTS[task]}", flush=True)
            try:
                with (log_dir / f"{task}.log").open("w", encoding="utf-8") as log:
                    subprocess.run(
                        [sys.executable, str(context.project_root / "scripts" / SCRIPTS[task]),
                         "--start-time", context.start_time, "--case-run"],
                        cwd=context.project_root, stdout=log, stderr=subprocess.STDOUT, check=True,
                    )
                for relative in PRODUCTS[task]:
                    path = context.output_root / relative
                    if not path.is_file() or path.stat().st_size == 0:
                        raise FileNotFoundError(f"Task {task} did not produce {relative}")
            except (Exception, KeyboardInterrupt) as exc:
                record.update(status="failed", error=str(exc) or type(exc).__name__, finished_at=now())
                raise
            record.update(status="success", finished_at=now())
            save_manifest(context, manifest)
        manifest["status"] = result["status"] = "success"
    except (Exception, KeyboardInterrupt) as exc:
        result["error"] = str(exc) or type(exc).__name__
        result["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        if writable and manifest is not None:
            manifest.update(status=result["status"], error=result["error"])
    finally:
        result["finished_at"] = now()
        if writable and manifest is not None:
            manifest["finished_at"] = result["finished_at"]
            save_manifest(context, manifest)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-time", required=True, type=parse_start_time)
    add_run_options(parser)
    args = parser.parse_args(argv)
    context = ExperimentContext(args.start_time, case_mode=True)
    result = run_case(context, args.tasks, args.overwrite, args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("success", "checked") else 1


if __name__ == "__main__":
    sys.exit(main())
