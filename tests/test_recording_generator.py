"""Contract tests for the project-scoped synthetic recording Skill."""

import importlib.util
import json
import platform
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/test-recording-generate/scripts/generate_recordings.py"


def load_generator():
    module_spec = importlib.util.spec_from_file_location("recording_generator", SCRIPT)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class RecordingGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.generator = load_generator()
        self.spec = {
            "feature_id": "synthetic-label-demo",
            "environment": "sit",
            "voice": "Tingting",
            "format": "wav",
            "fixtures": [{
                "fixture_id": "REC-001",
                "kind": "speech",
                "purpose": "合成语音正例",
                "text": "您好，这是合成测试录音。",
                "expectation_status": "pending",
            }],
        }

    def test_rejects_invalid_inputs_before_making_output(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = [
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "fixture_id": "../escape"}]},
                {**self.spec, "fixtures": [self.spec["fixtures"][0]] * 2},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "text": " "}]},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "text": "12345678901" * 500}]},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "expectation_status": "approved"}]},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "expected_tags": ["测试"]}]},
                {**self.spec, "format": "exe"},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "background_noise_db": -10}]},
                {**self.spec, "unrecognized_setting": True},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "min_duration_seconds": 90,
                                          "max_duration_seconds": 30}]},
                {**self.spec, "fixtures": [{"fixture_id": "REC-003", "kind": "dialogue",
                                            "purpose": "对话", "expectation_status": "pending", "turns": []}]},
                {**self.spec, "fixtures": [{"fixture_id": "REC-003", "kind": "dialogue",
                                            "purpose": "对话", "expectation_status": "pending",
                                            "turns": [{"speaker": "员工", "text": " "}]}]},
                {**self.spec, "fixtures": [{"fixture_id": "REC-003", "kind": "dialogue",
                                            "purpose": "对话", "expectation_status": "pending",
                                            "turns": [{"speaker": "员工", "text": "您好", "volume": 9}]}]},
                {**self.spec, "fixtures": [{"fixture_id": "REC-003", "kind": "dialogue",
                                            "purpose": "对话", "expectation_status": "pending", "pause_seconds": 5,
                                            "turns": [{"speaker": "员工", "text": "您好"}]}]},
                {**self.spec, "fixtures": [{**self.spec["fixtures"][0], "kind": "silence", "duration_seconds": 0}]},
            ]
            for index, case in enumerate(cases):
                output = Path(directory) / str(index)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    self.generator.generate_recordings(case, output)
                self.assertFalse(output.exists())

    def test_rejects_existing_output_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.generator.generate_recordings(self.spec, output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "ffmpeg/ffprobe required")
    def test_silent_synthesis_is_rejected_as_unusable(self):
        with tempfile.TemporaryDirectory() as directory:
            quiet = Path(directory) / "quiet.wav"
            self.generator._silence_wav(1, quiet)
            with self.assertRaises(RuntimeError):
                self.generator._audible_db(quiet)
            output = Path(directory) / "run"
            spec = {**self.spec, "fixtures": [
                self.spec["fixtures"][0],
                {"fixture_id": "REC-002", "kind": "silence", "purpose": "静音边界",
                 "duration_seconds": 1, "expectation_status": "pending"}]}
            with patch.object(self.generator, "_say", side_effect=lambda text, voice, rate, target:
                              self.generator._silence_wav(1, target)):
                with self.assertRaises(RuntimeError):
                    self.generator.generate_recordings(spec, output)
            self.assertFalse(output.exists())

    def test_failure_leaves_no_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            silence = {**self.spec, "fixtures": [{"fixture_id": "REC-002", "kind": "silence",
                         "purpose": "静音", "duration_seconds": 1, "expectation_status": "pending"}]}
            with patch.object(self.generator, "_run", side_effect=RuntimeError("tool failed")):
                with self.assertRaises(RuntimeError):
                    self.generator.generate_recordings(silence, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipUnless(platform.system() == "Darwin" and shutil.which("say")
                         and shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "macOS say and ffmpeg/ffprobe required")
    def test_generates_playable_speech_and_silence_with_probe_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "recordings"
            spec = {**self.spec, "fixtures": [
                self.spec["fixtures"][0],
                {"fixture_id": "REC-002", "kind": "silence", "purpose": "静音边界",
                 "duration_seconds": 1, "expectation_status": "pending"},
            ]}
            manifest = self.generator.generate_recordings(spec, output)
            self.assertEqual(manifest["status"], "generated")
            self.assertEqual(len(manifest["fixtures"]), 2)
            self.assertEqual(manifest, json.loads((output / "recording_manifest.json").read_text(encoding="utf-8")))
            for item in manifest["fixtures"]:
                audio = output / item["path"]
                self.assertTrue(audio.is_file())
                self.assertEqual(item["sha256"], self.generator.sha256(audio))
                self.assertEqual(item["probe"]["codec"], "pcm_s16le")
                self.assertEqual(item["probe"]["sample_rate"], 16000)
                self.assertEqual(item["probe"]["channels"], 1)
                self.assertGreater(item["probe"]["duration_seconds"], 0)
                self.assertEqual(item["expectation_status"], "pending")
            self.assertGreater(manifest["fixtures"][0]["mean_volume_db"], -60)
            self.assertNotIn("mean_volume_db", manifest["fixtures"][1])
            self.assertEqual(manifest["fixtures"][1]["probe"]["duration_seconds"], 1.0)
            self.assertNotIn("expected_tags", json.dumps(manifest, ensure_ascii=False))
            self.assertTranscriptDocument(manifest, output)

    def assertTranscriptDocument(self, manifest, output):
        """Every run must ship one document holding the spoken text of each recording."""
        document = output / "recording_transcripts.md"
        self.assertTrue(document.is_file())
        text = document.read_text(encoding="utf-8")
        self.assertIn(manifest["spec_sha256"], text)
        for item in manifest["fixtures"]:
            self.assertIn(item["fixture_id"], text)
            self.assertIn(item["path"], text)
            if item["kind"] == "speech":
                self.assertIn(item["text"], text)
            elif item["kind"] == "dialogue":
                for turn in item["turns"]:
                    self.assertIn(turn["text"], text)
                    self.assertIn(turn["speaker"], text)
            else:
                self.assertIn("无台词", text)
            self.assertFalse(manifest["expectations_verified"])

    @unittest.skipUnless(platform.system() == "Darwin" and shutil.which("say")
                         and shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "macOS say and ffmpeg/ffprobe required")
    def test_dialogue_keeps_speaker_turns_and_enforces_minimum_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dialogue"
            spec = {**self.spec, "fixtures": [{
                "fixture_id": "MEM-01", "kind": "dialogue", "purpose": "双人接待对话",
                "expectation_status": "pending", "min_duration_seconds": 6, "pause_seconds": 0.4,
                "turns": [
                    {"speaker": "员工", "text": "您好，今天想先了解哪方面的护理？"},
                    {"speaker": "顾客", "text": "我之前在你们这家店做过基础护理，服务人员解释得很清楚。"},
                    {"speaker": "顾客", "voice": "Sandy (中文（中国大陆）)", "text": "所以这次我先听听你们的建议。"},
                ]}]}
            manifest = self.generator.generate_recordings(spec, output)
            item = manifest["fixtures"][0]
            self.assertEqual(manifest["format"], "wav")
            self.assertEqual(item["speakers"], ["员工", "顾客"])
            self.assertEqual(item["turn_count"], 3)
            self.assertEqual(len(item["turns"]), 3)
            self.assertEqual(item["turns"][2]["voice"], "Sandy (中文（中国大陆）)")
            self.assertEqual(item["turns"][0]["voice"], "Tingting")
            self.assertGreaterEqual(item["probe"]["duration_seconds"], 6)
            self.assertEqual(item["enforced_min_duration_seconds"], 6)
            self.assertNotIn("enforced_max_duration_seconds", item)
            self.assertEqual(item["probe"]["codec"], "pcm_s16le")
            self.assertFalse(manifest["expectations_verified"])
            self.assertTranscriptDocument(manifest, output)

    @unittest.skipUnless(platform.system() == "Darwin" and shutil.which("say")
                         and shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "macOS say and ffmpeg/ffprobe required")
    def test_short_dialogue_below_minimum_duration_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "too-short"
            spec = {**self.spec, "fixtures": [{
                "fixture_id": "MEM-SHORT", "kind": "dialogue", "purpose": "过短对话",
                "expectation_status": "pending", "min_duration_seconds": 120,
                "turns": [{"speaker": "员工", "text": "您好。"}]}]}
            with self.assertRaises(RuntimeError):
                self.generator.generate_recordings(spec, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipUnless(platform.system() == "Darwin" and shutil.which("say")
                         and shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "macOS say and ffmpeg/ffprobe required")
    def test_approved_expectation_is_declared_but_not_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = {**self.spec["fixtures"][0], "expectation_status": "approved",
                       "oracle_reference": "reviewed-rule-A-001@sha256:demo",
                       "expected_tags": ["演示标签"]}
            manifest = self.generator.generate_recordings(
                {**self.spec, "fixtures": [fixture]}, Path(directory) / "run")
            self.assertFalse(manifest["expectations_verified"])
            self.assertEqual(manifest["fixtures"][0]["expected_tags"], ["演示标签"])
            self.assertEqual(manifest["fixtures"][0]["audio_content_review"], "not_performed")
            self.assertTranscriptDocument(manifest, Path(directory) / "run")


if __name__ == "__main__":
    unittest.main()
