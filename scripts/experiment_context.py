"""Shared time and paths; the legacy algorithms keep their own parameters."""

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_START_TIME = "201609281600"


def parse_start_time(value):
    if len(value) != 12 or not value.isascii() or not value.isdigit():
        raise argparse.ArgumentTypeError("start time must be YYYYMMDDHHMM (UTC)")
    try:
        date = datetime.strptime(value, "%Y%m%d%H%M")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if date.minute % 5:
        raise argparse.ArgumentTypeError("FMI start time must be on a 5-minute boundary")
    return date


@dataclass(frozen=True)
class ExperimentContext:
    date: datetime
    project_root: Path = PROJECT_ROOT
    case_mode: bool = False

    @property
    def start_time(self):
        return self.date.strftime("%Y%m%d%H%M")

    @property
    def case_id(self):
        return self.date.strftime("fmi_%Y%m%dT%H%M00Z")

    @property
    def data_root(self):
        return self.project_root / "data/sample/pysteps-data/radar/fmi/pgm"

    @property
    def output_root(self):
        root = self.project_root / "outputs"
        return root / "cases" / self.case_id if self.case_mode else root

    def legacy_path(self, path):
        """Preserve original cwd-relative strings for scripts run without arguments."""
        if not self.case_mode:
            return path
        return self.output_root / Path(path).relative_to("outputs")


def get_context(argv=None):
    parser = argparse.ArgumentParser(description="Legacy experiment task")
    parser.add_argument("--start-time", type=parse_start_time)
    parser.add_argument("--case-run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.case_run != (args.start_time is not None):
        parser.error("use run_case.py for a configurable case; task flags are internal")
    return ExperimentContext(
        args.start_time or parse_start_time(DEFAULT_START_TIME),
        case_mode=args.case_run,
    )


def check_radar_inputs(context, previous, following):
    """Check filenames only, with the same current rcparams as the algorithms."""
    from pysteps import io, rcparams

    source = rcparams.data_sources["fmi"]
    files, timestamps = io.archive.find_by_date(
        context.date, str(context.data_root), source["path_fmt"],
        source["fn_pattern"], source["fn_ext"], source["timestep"],
        num_prev_files=previous, num_next_files=following,
    )
    missing = [str(time) for path, time in zip(files, timestamps)
               if path is None or not Path(path).is_file()]
    if len(files) != previous + following + 1 or missing:
        raise FileNotFoundError("Missing FMI frames: " + ", ".join(missing))
    return len(files)
