"""Serial FMI cases; never expand a case list or fill in missing dependencies."""

import argparse
import json
from pathlib import Path
import sys

from experiment_context import ExperimentContext, parse_start_time
from run_case import add_run_options, run_case


def load_cases(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"start_times"}:
        raise ValueError("Case JSON must contain only start_times")
    values = config["start_times"]
    if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
        raise ValueError("start_times must be a nonempty list of UTC YYYYMMDDHHMM strings")
    if len(values) != len(set(values)):
        raise ValueError("Duplicate start times are not allowed")
    return [parse_start_time(value) for value in values]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    add_run_options(parser)
    args = parser.parse_args(argv)
    try:
        dates = load_cases(args.cases)
    except (OSError, ValueError, argparse.ArgumentTypeError) as exc:
        parser.error(str(exc))
    results = []
    for date in dates:
        result = run_case(ExperimentContext(date, case_mode=True), args.tasks, args.overwrite, args.dry_run)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if result["status"] == "interrupted":
            break
    failed = sum(r["status"] not in ("success", "checked") for r in results)
    print(json.dumps({"total": len(dates), "completed": len(results), "failed": failed,
                      "results": results}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
