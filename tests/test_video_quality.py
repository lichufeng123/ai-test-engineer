import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

import sys

sys.path.insert(0, str(SRC))

from ai_test_framework.cli import main
from ai_test_framework.video_quality import check_videos


def video_spec(**overrides):
    item = {
        "evidence_id": "VE-DEMO-001",
        "case_id": "TC-DEMO-001",
        "path": "evidence/TC-DEMO-001.mp4",
        "expected_duration_seconds": {"minimum": 30, "maximum": 120},
    }
    item.update(overrides)
    return {"schema_version": 1, "run_id": "RUN-DEMO", "videos": [item]}


class FakeRunner:
    def __init__(self, *, duration=60.0, black_output="", static_output=""):
        self.duration = duration
        self.black_output = black_output
        self.static_output = static_output
        self.commands = []

    def __call__(self, command, **_kwargs):
        self.commands.append(command)
        if command[0] == "ffprobe":
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({
                    "streams": [{"width": 1920, "height": 1080}],
                    "format": {"duration": str(self.duration)},
                }),
                stderr="",
            )
        if "blackdetect" in " ".join(command):
            output = "\n".join(part for part in (self.black_output, self.static_output) if part)
            return SimpleNamespace(returncode=0, stdout="", stderr=output)
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")


class VideoQualityTest(unittest.TestCase):
    def _check(self, runner, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "evidence/TC-DEMO-001.mp4"
            video.parent.mkdir()
            video.write_bytes(b"sanitized-placeholder")
            return check_videos(video_spec(**overrides), root=root, runner=runner)

    def test_normal_video_passes_all_technical_checks(self):
        runner = FakeRunner(duration=60)
        result = self._check(runner)
        self.assertEqual(result["status"], "passed")
        item = result["items"][0]
        self.assertEqual(item["disposition"], "passed")
        self.assertEqual(item["probe"]["width"], 1920)
        self.assertRegex(item["probe"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(item["checks"]["black_frames"]["ratio"], 0.0)
        self.assertEqual(result["scope"]["semantic_content_check"], "not_performed")
        self.assertEqual(len(runner.commands), 2, "ffprobe and one combined ffmpeg pass expected")

    def test_black_video_requires_rerecording_and_reports_segment(self):
        output = "[blackdetect] black_start:0 black_end:60 black_duration:60\n"
        result = self._check(FakeRunner(duration=60, black_output=output))
        item = result["items"][0]
        self.assertEqual(result["status"], "repair_required")
        self.assertEqual(item["disposition"], "rerecord_required")
        self.assertEqual(item["checks"]["black_frames"]["ratio"], 1.0)
        self.assertEqual(item["checks"]["black_frames"]["segments"][0]["start_seconds"], 0.0)
        self.assertIn("black_ratio_exceeded", [issue["code"] for issue in item["issues"]])

    def test_long_static_wait_requires_rerecording(self):
        output = "\n".join([
            "[freezedetect] lavfi.freezedetect.freeze_start: 5",
            "[freezedetect] lavfi.freezedetect.freeze_duration: 50",
            "[freezedetect] lavfi.freezedetect.freeze_end: 55",
        ])
        result = self._check(FakeRunner(duration=60, static_output=output))
        item = result["items"][0]
        self.assertEqual(item["disposition"], "rerecord_required")
        self.assertAlmostEqual(item["checks"]["static_frames"]["ratio"], 50 / 60, places=4)
        self.assertIn("static_ratio_exceeded", [issue["code"] for issue in item["issues"]])

    def test_overlong_video_is_marked_for_trimming(self):
        result = self._check(FakeRunner(duration=260))
        item = result["items"][0]
        self.assertEqual(item["disposition"], "trim_required")
        self.assertIn("duration_above_maximum", [issue["code"] for issue in item["issues"]])

    def test_short_video_requires_rerecording(self):
        result = self._check(FakeRunner(duration=10))
        item = result["items"][0]
        self.assertEqual(item["disposition"], "rerecord_required")
        self.assertIn("duration_below_minimum", [issue["code"] for issue in item["issues"]])

    def test_missing_ffmpeg_blocks_instead_of_silently_passing(self):
        probe_runner = FakeRunner(duration=60)

        def runner(command, **kwargs):
            if command[0] == "ffmpeg":
                raise FileNotFoundError("ffmpeg")
            return probe_runner(command, **kwargs)

        result = self._check(runner)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["items"][0]["issues"][0]["code"], "ffmpeg_unavailable")
        self.assertEqual(result["items"][0]["probe"]["duration_seconds"], 60.0)

    def test_invalid_duration_contract_is_blocked_without_invoking_tools(self):
        runner = FakeRunner()
        result = self._check(
            runner,
            expected_duration_seconds={"minimum": 120, "maximum": 30},
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["items"][0]["issues"][0]["code"], "invalid_video_item")
        self.assertEqual(runner.commands, [])

    def test_missing_video_is_blocked_without_invoking_tools(self):
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as directory:
            result = check_videos(video_spec(), root=Path(directory), runner=runner)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["items"][0]["disposition"], "blocked")
        self.assertEqual(runner.commands, [])

    def test_path_cannot_escape_evidence_root(self):
        result = self._check(FakeRunner(), path="../private.mp4")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["items"][0]["issues"][0]["code"], "path_outside_root")

    def test_cli_writes_machine_readable_receipt(self):
        receipt = {
            "schema_version": 1,
            "receipt_type": "video_quality",
            "run_id": "RUN-DEMO",
            "input_sha256": "1" * 64,
            "status": "passed",
            "scope": {"technical_checks": ["duration", "black_frames", "static_frames"],
                      "semantic_content_check": "not_performed"},
            "summary": {"total": 1, "passed": 1, "trim_required": 0,
                        "rerecord_required": 0, "blocked": 0},
            "items": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            output_path = root / "receipt.json"
            input_path.write_text(json.dumps(video_spec()), encoding="utf-8")
            stdout = io.StringIO()
            with patch("ai_test_framework.cli.check_videos", return_value=receipt):
                with contextlib.redirect_stdout(stdout):
                    exit_code = main([
                        "video-check", "--input", str(input_path), "--root", str(root),
                        "--output", str(output_path),
                    ])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue()), receipt)
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), receipt)

    def test_repository_contains_input_and_receipt_schemas_and_sanitized_examples(self):
        input_schema = json.loads(
            (ROOT / "schemas/video-check-input.schema.json").read_text(encoding="utf-8")
        )
        receipt_schema = json.loads(
            (ROOT / "schemas/video-quality-receipt.schema.json").read_text(encoding="utf-8")
        )
        example = (ROOT / "templates/video-check-input.example.json").read_text(encoding="utf-8")
        self.assertIn("videos", input_schema["required"])
        self.assertEqual(receipt_schema["properties"]["receipt_type"]["const"], "video_quality")
        for forbidden in ("/users/", "http://", "https://", "token", "password"):
            self.assertNotIn(forbidden, example.lower())


if __name__ == "__main__":
    unittest.main()
