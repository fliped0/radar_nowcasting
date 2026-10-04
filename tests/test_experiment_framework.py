"""Framework tests use temporary directories and fake tasks, never nowcasts."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from experiment_context import ExperimentContext, get_context, parse_start_time
import run_case as runner
import run_cases as batch


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = ExperimentContext(datetime(2016, 9, 28, 16), self.root, True)
        (self.root / "scripts").mkdir()
        for name in runner.SCRIPTS.values():
            (self.root / "scripts" / name).touch()

    def existing(self, tasks=None):
        self.context.output_root.mkdir(parents=True, exist_ok=True)
        manifest = {"case_id": self.context.case_id, "start_time": self.context.start_time,
                    "status": "success", "tasks": tasks or {}}
        runner.save_manifest(self.context, manifest)
        return manifest

    def produce(self, task):
        for name in runner.PRODUCTS[task]:
            path = self.context.output_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test artifact")

    def test_legacy_paths_and_time(self):
        context = get_context([])
        self.assertEqual(context.start_time, "201609281600")
        self.assertEqual(context.output_root, context.project_root / "outputs")
        self.assertEqual(context.legacy_path("outputs/sprog/test.png"), "outputs/sprog/test.png")

    def test_case_paths(self):
        self.assertEqual(self.context.case_id, "fmi_20160928T160000Z")
        self.assertEqual(self.context.legacy_path("outputs/sprog/test.png"),
                         self.context.output_root / "sprog/test.png")
        self.assertEqual(self.context.data_root, self.root / "data/sample/pysteps-data/radar/fmi/pgm")

    def test_invalid_dates(self):
        for value in ("20160928160", "201602301600", "201609281602", "２０１６０９２８１６００"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                parse_start_time(value)

    def test_task_order_and_duplicates(self):
        self.assertEqual(runner.parse_tasks("03,06,05"), ("05", "06", "03"))
        for value in ("01,01", "15", "", "1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                runner.parse_tasks(value)

    def test_full_preflight_window(self):
        with patch.object(runner, "check_radar_inputs") as check:
            runner.preflight(self.context, tuple(runner.SCRIPTS), {})
            check.assert_called_once_with(self.context, 2, 12)

    def test_prediction_only_window(self):
        with patch.object(runner, "check_radar_inputs") as check:
            runner.preflight(self.context, ("05",), {})
            check.assert_called_once_with(self.context, 2, 0)

    def test_missing_dependencies_never_run(self):
        with patch.object(runner.subprocess, "run") as execute:
            result = runner.run_case(self.context, ("10",))
            self.assertEqual(result["status"], "failed")
            self.assertIn("09", result["error"])
            execute.assert_not_called()

    def test_dry_run_creates_nothing(self):
        with patch.object(runner, "check_radar_inputs"), patch.object(runner.subprocess, "run") as execute:
            result = runner.run_case(self.context, tuple(runner.SCRIPTS), dry_run=True)
        self.assertEqual(result["status"], "checked")
        self.assertFalse(self.context.output_root.exists())
        execute.assert_not_called()

    def test_output_collision_preserves_manifest(self):
        self.existing()
        path = self.context.output_root / "run_manifest.json"
        before = path.read_bytes()
        result = runner.run_case(self.context, ("01",))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(before, path.read_bytes())

    def test_wrong_case_manifest_rejected(self):
        manifest = self.existing()
        manifest["start_time"] = "201609281605"
        runner.save_manifest(self.context, manifest)
        with self.assertRaises(ValueError):
            runner.load_existing(self.context, True)

    def test_missing_frames_never_run(self):
        with patch.object(runner, "check_radar_inputs", side_effect=FileNotFoundError("Missing FMI frames")), \
                patch.object(runner.subprocess, "run") as execute:
            result = runner.run_case(self.context, ("01",))
            execute.assert_not_called()
        self.assertEqual(result["status"], "failed")

    def test_selected_plot_uses_existing_csv_without_radar(self):
        self.existing({"09": {"status": "success"}})
        self.produce("09")
        with patch.object(runner, "check_radar_inputs") as radar, \
                patch.object(runner.subprocess, "run", side_effect=lambda *a, **k: self.produce("10")) as execute:
            result = runner.run_case(self.context, ("10",), overwrite=True)
        self.assertEqual(result["status"], "success")
        radar.assert_not_called()
        self.assertEqual(execute.call_args.args[0][0], sys.executable)
        self.assertEqual(execute.call_args.kwargs["cwd"], self.root)

    def test_existing_failed_dependency_not_reused(self):
        self.existing({"09": {"status": "failed"}})
        self.produce("09")
        result = runner.run_case(self.context, ("10",), overwrite=True)
        self.assertEqual(result["status"], "failed")

    def test_failure_stops_remaining_tasks(self):
        with patch.object(runner, "check_radar_inputs"), \
                patch.object(runner.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "fake")) as execute:
            result = runner.run_case(self.context, ("01", "02"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(execute.call_count, 1)
        manifest = json.loads((self.context.output_root / "run_manifest.json").read_text())
        self.assertEqual(manifest["tasks"]["01"]["status"], "failed")
        self.assertEqual(manifest["tasks"]["02"]["status"], "pending")

    def test_missing_product_fails_task(self):
        with patch.object(runner, "check_radar_inputs"), patch.object(runner.subprocess, "run"):
            result = runner.run_case(self.context, ("01",))
        self.assertEqual(result["status"], "failed")
        self.assertIn("did not produce", result["error"])

    def test_batch_continues_after_failed_fake_case(self):
        dates = [datetime(2016, 9, 28, 16), datetime(2016, 9, 28, 16, 5)]
        with patch.object(batch, "load_cases", return_value=dates), \
                patch.object(batch, "run_case", side_effect=[{"status": "failed"}, {"status": "success"}]) as run:
            code = batch.main(["--cases", "unused.json"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(code, 1)

    def test_batch_rejects_invalid_lists(self):
        path = self.root / "cases.json"
        for value in ([], {"start_times": []}, {"start_times": [1]},
                      {"start_times": ["201609281600"] * 2}):
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                batch.load_cases(path)


if __name__ == "__main__":
    unittest.main()
