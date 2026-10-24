"""The exploration-to-automation contract must fail closed, including rapid repeats."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.exploration_handoff import check_exploration_handoff  # noqa: E402
from ai_test_framework.cli import main  # noqa: E402


def put(root: Path, path: str, text: str) -> dict[str, str]:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


class ExplorationHandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runner = put(self.root, "feature/tests/import.spec.ts", "test('one safe read', () => {});\n")
        self.oracle = put(self.root, "feature/scripts/oracle.py", "# independent exported workbook oracle\n")
        validation = {
            "status": "passed", "feature": "import-export", "runner_sha256": self.runner["sha256"],
            "tests_passed": 2, "test_scope": "read_only_export",
        }
        self.validation = put(self.root, "runs/test-receipt.json", json.dumps(validation))
        self.backup = put(self.root, "runs/remote-backup.json", json.dumps({
            "status": "passed", "runner_sha256": self.runner["sha256"], "revision": "r10",
        }))
        self.payload = {
            "schema_version": 1, "feature": "import-export", "run_id": "RUN-SECOND",
            "phase": "preflight", "purpose": "repeat_execution", "mode": "rapid",
            "questions": [{
                "id": "EXP-01", "unknown": "identity and stable locator", "status": "implemented",
                "asset": self.oracle,
            }],
            "runner": {**self.runner, "validation_receipt": self.validation,
                       "remote_backup_receipt": self.backup},
            "oracle": self.oracle,
            "evidence_plan": {
                "video": "continuous_on", "error_capture": "on_visible_notice",
                "assertion_ids": ["A-01"],
            },
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_validated_executable_with_closed_questions_and_capture_plan_can_start(self):
        self.assertEqual(check_exploration_handoff(self.payload, self.root)["status"], "passed")

    def test_method_only_json_or_missing_runner_blocks_repeat_even_in_rapid_mode(self):
        value = dict(self.payload)
        value["runner"] = {**put(self.root, "feature/method.json", "{}"),
                           "validation_receipt": self.validation, "remote_backup_receipt": self.backup}
        result = check_exploration_handoff(value, self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("runner_not_executable", result["error_codes"])
        value["runner"] = None
        self.assertIn("runner_missing", check_exploration_handoff(value, self.root)["error_codes"])

    def test_open_question_and_stale_oracle_and_missing_video_block(self):
        value = json.loads(json.dumps(self.payload))
        value["questions"][0]["status"] = "unknown"
        value["oracle"]["sha256"] = "0" * 64
        value["evidence_plan"]["video"] = "retain_on_failure"
        errors = check_exploration_handoff(value, self.root)["error_codes"]
        self.assertIn("exploration_question_open", errors)
        self.assertIn("oracle_hash_mismatch", errors)
        self.assertIn("continuous_video_not_planned", errors)

    def test_missing_backup_or_test_proof_blocks_but_exploration_can_continue_without_pass(self):
        value = json.loads(json.dumps(self.payload))
        value["runner"].pop("remote_backup_receipt")
        self.assertIn("remote_backup_missing", check_exploration_handoff(value, self.root)["error_codes"])
        value["purpose"] = "first_exploration"
        result = check_exploration_handoff(value, self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("exploration_handoff_incomplete", result["error_codes"])

    def test_closure_requires_video_and_assertion_bound_visible_error_screenshot(self):
        value = json.loads(json.dumps(self.payload))
        value["phase"] = "closure"
        result = check_exploration_handoff(value, self.root)
        self.assertIn("video_evidence_missing", result["error_codes"])
        self.assertIn("assertion_screenshot_missing", result["error_codes"])
        video = put(self.root, "runs/core.webm", "synthetic video fixture")
        shot = put(self.root, "runs/error.png", "synthetic screenshot fixture")
        value["evidence"] = {
            "videos": [{**video, "quality": "passed", "semantic_review": "passed"}],
            "screenshots": [{**shot, "assertion_id": "A-01", "kind": "error_notice",
                             "content_review": "failed", "prompt_visible": False}],
        }
        errors = check_exploration_handoff(value, self.root)["error_codes"]
        self.assertIn("error_prompt_not_visible", errors)
        value["evidence"]["screenshots"][0].update(content_review="passed", prompt_visible=True)
        self.assertEqual(check_exploration_handoff(value, self.root)["status"], "passed")

    def test_cli_writes_blocked_receipt_and_returns_nonzero(self):
        value = json.loads(json.dumps(self.payload))
        value["runner"] = None
        source = self.root / "preflight.json"
        receipt = self.root / "gate.json"
        source.write_text(json.dumps(value), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["exploration-handoff-check", "--input", str(source),
                         "--root", str(self.root), "--output", str(receipt)])
        self.assertEqual(1, code)
        self.assertEqual("blocked", json.loads(receipt.read_text())["status"])

    def test_wrong_runner_validation_identity_or_tampered_receipt_blocks(self):
        value = json.loads(json.dumps(self.payload))
        proof = json.loads((self.root / self.validation["path"]).read_text())
        proof["tests_passed"] = 0
        (self.root / self.validation["path"]).write_text(json.dumps(proof))
        errors = check_exploration_handoff(value, self.root)["error_codes"]
        self.assertIn("runner_validation_receipt_hash_mismatch", errors)
        value["runner"]["validation_receipt"] = put(self.root, self.validation["path"], json.dumps(proof))
        errors = check_exploration_handoff(value, self.root)["error_codes"]
        self.assertIn("runner_validation_not_passed", errors)


if __name__ == "__main__":
    unittest.main()
