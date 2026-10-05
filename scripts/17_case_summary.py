"""Aggregate existing FMI case CSVs without importing or running forecast code."""

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import sys
import warnings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METHOD_FILES = {
    "Persistence": "persistence_rmse.csv",
    "Optical Flow": "optical_flow_rmse.csv",
    "S-PROG": "sprog_rmse.csv",
    "STEPS Mean": "steps_rmse.csv",
}
THRESHOLDS = (0.1, 1.0, 5.0)
FIELDS = {
    "rmse_summary.csv": ("method", "lead_time_min", "mean", "std", "case_count"),
    "categorical_summary.csv": ("method", "lead_time_min", "threshold", "metric", "mean", "std", "case_count"),
    "bss_summary.csv": ("method", "reference_method", "lead_time_min", "threshold", "mean", "std", "case_count"),
    "crps_summary.csv": ("method", "lead_time_min", "mean", "std", "case_count"),
}


def case_ids(start_times):
    if not isinstance(start_times, list) or not start_times:
        raise ValueError("Case list must be a nonempty list of UTC start times")
    result = []
    for value in start_times:
        if not isinstance(value, str) or len(value) != 12 or not value.isascii() or not value.isdigit():
            raise ValueError(f"Invalid UTC start time: {value!r}; expected YYYYMMDDHHMM")
        date = datetime.strptime(value, "%Y%m%d%H%M")
        if date.minute % 5:
            raise ValueError(f"Start time must be on a 5-minute boundary: {value}")
        result.append(date.strftime("fmi_%Y%m%dT%H%M%SZ"))
    if len(result) != len(set(result)):
        raise ValueError("Duplicate cases are not allowed")
    return result


def read_rows(path, columns):
    if not path.is_file():
        raise FileNotFoundError(f"Missing required case CSV: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(columns).issubset(reader.fieldnames):
            raise ValueError(f"Invalid CSV columns in {path}; required: {', '.join(columns)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"Empty case CSV: {path}")
    return rows


def number(row, field, path):
    try:
        value = float(row[field])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"Invalid {field} in {path}: {row}") from exc
    if math.isinf(value):
        raise ValueError(f"Infinite {field} in {path}")
    return value


def lead(row, path):
    value = number(row, "lead_time_min", path)
    if not math.isfinite(value) or value <= 0 or not value.is_integer():
        raise ValueError(f"Invalid lead_time_min in {path}: {row}")
    return int(value)


def threshold(row, path):
    value = number(row, "threshold", path)
    if value not in THRESHOLDS:
        raise ValueError(f"Unexpected threshold {value} in {path}")
    return value


def insert(table, key, value, path):
    if key in table:
        raise ValueError(f"Duplicate metric row {key} in {path}")
    table[key] = value


def read_case(root, case_id):
    metrics = root / "outputs" / "cases" / case_id / "metrics"
    rmse, categorical, bss, crps = {}, {}, {}, {}
    for method, filename in METHOD_FILES.items():
        path = metrics / filename
        for row in read_rows(path, ("lead_time_min", "rmse")):
            insert(rmse, (method, lead(row, path)), number(row, "rmse", path), path)
    leads = {key[1] for key in rmse if key[0] == "Persistence"}
    expected_rmse = {(method, time) for method in METHOD_FILES for time in leads}
    if set(rmse) != expected_rmse:
        raise ValueError(f"Inconsistent RMSE lead times in {metrics}")

    path = metrics / "unified_metrics_all_thresholds.csv"
    for row in read_rows(path, ("method", "lead_time_min", "threshold", "csi", "pod", "far")):
        method, time, thr = row["method"], lead(row, path), threshold(row, path)
        for metric in ("csi", "pod", "far"):
            insert(categorical, (method, time, thr, metric), number(row, metric, path), path)
    expected = {(method, time, thr, metric) for method in METHOD_FILES
                for time in leads for thr in THRESHOLDS for metric in ("csi", "pod", "far")}
    if set(categorical) != expected:
        raise ValueError(f"Incomplete or unexpected categorical rows in {path}")

    path = metrics / "steps_brier_skill_score.csv"
    for row in read_rows(path, ("lead_time_min", "threshold", "bss")):
        insert(bss, ("STEPS", "Persistence", lead(row, path), threshold(row, path)),
               number(row, "bss", path), path)
    expected_bss = {("STEPS", "Persistence", time, thr) for time in leads for thr in THRESHOLDS}
    if set(bss) != expected_bss:
        raise ValueError(f"Incomplete BSS rows in {path}")

    path = metrics / "steps_crps.csv"
    for row in read_rows(path, ("lead_time_min", "crps")):
        insert(crps, ("STEPS", lead(row, path)), number(row, "crps", path), path)
    if set(crps) != {("STEPS", time) for time in leads}:
        raise ValueError(f"Incomplete CRPS rows in {path}")
    return (rmse, categorical, bss, crps)


def summarize(start_times, project_root=PROJECT_ROOT):
    ids = case_ids(start_times)
    cases = [read_case(Path(project_root), case_id) for case_id in ids]
    output = {}
    keys_by_file = (
        ("method", "lead_time_min"),
        ("method", "lead_time_min", "threshold", "metric"),
        ("method", "reference_method", "lead_time_min", "threshold"),
        ("method", "lead_time_min"),
    )
    for index, (filename, keys) in enumerate(zip(FIELDS, keys_by_file)):
        baseline = set(cases[0][index])
        for case_id, tables in zip(ids[1:], cases[1:]):
            if set(tables[index]) != baseline:
                raise ValueError(f"Metric rows differ between cases for {filename}: {case_id}")
        rows = []
        for key in sorted(baseline):
            values = [tables[index][key] for tables in cases]
            valid = [value for value in values if math.isfinite(value)]
            if len(valid) != len(values):
                undefined = [case_id for case_id, value in zip(ids, values) if not math.isfinite(value)]
                warnings.warn(f"Undefined metric in {filename} {key}: {undefined}; "
                              f"case_count={len(valid)}/{len(values)}", stacklevel=2)
            rows.append({**dict(zip(keys, key)),
                         "mean": statistics.mean(valid) if valid else math.nan,
                         "std": statistics.stdev(valid) if len(valid) > 1 else math.nan,
                         "case_count": len(valid)})
        output[filename] = rows
    return output


def write_summaries(tables, project_root=PROJECT_ROOT):
    directory = Path(project_root) / "outputs" / "summary"
    directory.mkdir(parents=True, exist_ok=True)
    for filename, fields in FIELDS.items():
        path = directory / filename
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(tables[filename])
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start-times", nargs="+", help="UTC YYYYMMDDHHMM times")
    group.add_argument("--cases", type=Path, help="JSON with start_times; default configs/cases.json")
    args = parser.parse_args(argv)
    try:
        if args.start_times is not None:
            times = args.start_times
        else:
            path = args.cases or PROJECT_ROOT / "configs" / "cases.json"
            config = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(config, dict) or "start_times" not in config:
                raise ValueError(f"Missing start_times in {path}")
            times = config["start_times"]
        tables = summarize(times)
        directory = write_summaries(tables)
    except (OSError, ValueError) as exc:
        print(f"Case summary failed: {exc}", file=sys.stderr)
        return 1
    print(f"Cases: {', '.join(case_ids(times))}")
    for filename, rows in tables.items():
        print(f"{directory / filename}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
