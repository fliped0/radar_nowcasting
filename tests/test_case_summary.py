"""Synthetic CSV tests; no radar data or forecasts are read or executed."""

import csv
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "case_summary", Path(__file__).resolve().parents[1] / "scripts" / "17_case_summary.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.times = ["201609281600", "201705091300"]
        self.dirs = []
        for case_id, value in zip(summary.case_ids(self.times), (1.0, 3.0)):
            metrics = self.root / "outputs" / "cases" / case_id / "metrics"
            self.dirs.append(metrics)
            for filename in summary.METHOD_FILES.values():
                write_csv(metrics / filename, ["lead_time_min", "rmse"],
                          [{"lead_time_min": time, "rmse": value} for time in (5, 10)])
            write_csv(metrics / "unified_metrics_all_thresholds.csv",
                      ["method", "lead_time_min", "threshold", "csi", "pod", "far"],
                      [{"method": method, "lead_time_min": time, "threshold": thr,
                        "csi": value / 10, "pod": value / 10, "far": value / 10}
                       for method in summary.METHOD_FILES for time in (5, 10) for thr in summary.THRESHOLDS])
            write_csv(metrics / "steps_brier_skill_score.csv", ["lead_time_min", "threshold", "bss"],
                      [{"lead_time_min": time, "threshold": thr, "bss": value / 10}
                       for time in (5, 10) for thr in summary.THRESHOLDS])
            write_csv(metrics / "steps_crps.csv", ["lead_time_min", "crps"],
                      [{"lead_time_min": time, "crps": value} for time in (5, 10)])

    def test_two_cases_and_csv_outputs(self):
        tables = summary.summarize(self.times, self.root)
        self.assertEqual([len(rows) for rows in tables.values()], [8, 72, 6, 2])
        for name in ("rmse_summary.csv", "crps_summary.csv"):
            for row in tables[name]:
                self.assertEqual(row["mean"], 2.0)
                self.assertAlmostEqual(row["std"], math.sqrt(2))
                self.assertEqual(row["case_count"], 2)
        self.assertEqual({r["threshold"] for r in tables["bss_summary.csv"]}, {0.1, 1.0, 5.0})
        self.assertEqual({r["metric"] for r in tables["categorical_summary.csv"]}, {"csi", "pod", "far"})
        self.assertAlmostEqual(tables["bss_summary.csv"][0]["mean"], 0.2)
        before = {path: path.read_bytes() for directory in self.dirs for path in directory.iterdir()}
        directory = summary.write_summaries(tables, self.root)
        self.assertEqual({path.name for path in directory.iterdir()}, set(summary.FIELDS))
        self.assertTrue(all(path.read_bytes() == value for path, value in before.items()))

    def test_missing_file_is_error(self):
        path = self.dirs[1] / "steps_crps.csv"
        path.unlink()
        with self.assertRaisesRegex(FileNotFoundError, "steps_crps.csv"):
            summary.summarize(self.times, self.root)
        self.assertFalse((self.root / "outputs/summary").exists())

    def test_empty_list_is_error(self):
        with self.assertRaisesRegex(ValueError, "nonempty"):
            summary.summarize([], self.root)

    def test_duplicate_cases_are_error(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summary.summarize(self.times * 2, self.root)

    def test_incomplete_threshold_is_error(self):
        write_csv(self.dirs[1] / "steps_brier_skill_score.csv", ["lead_time_min", "threshold", "bss"],
                  [{"lead_time_min": 5, "threshold": 0.1, "bss": 0.2}])
        with self.assertRaisesRegex(ValueError, "Incomplete BSS"):
            summary.summarize(self.times, self.root)

    def test_nan_is_explicit_and_counted(self):
        write_csv(self.dirs[1] / "steps_crps.csv", ["lead_time_min", "crps"],
                  [{"lead_time_min": time, "crps": "nan"} for time in (5, 10)])
        with self.assertWarnsRegex(UserWarning, "case_count=1/2"):
            rows = summary.summarize(self.times, self.root)["crps_summary.csv"]
        self.assertEqual(rows[0]["case_count"], 1)
        self.assertEqual(rows[0]["mean"], 1)
        self.assertTrue(math.isnan(rows[0]["std"]))


if __name__ == "__main__":
    unittest.main()
