"""Reporter/receipt contradictions must never become a green business result."""

import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.automation_outcome import check_automation_outcome  # noqa: E402
from ai_test_framework.cli import main  # noqa: E402


def put(root, name, content):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}


class AutomationOutcomeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runner = put(self.root, "feature/tests/example.spec.ts", "// illustrative UI runner\n")
        self.baseline = put(self.root, "cases/approved.json", json.dumps({
            "baseline_id": "BL-A", "cases": [{"id": "TC-1", "covered_rule_ids": ["A-1"]}]}))
        self.oracle = put(self.root, "feature/oracles/expected.json", '{"expected": 1}\n')
        self.evidence = put(self.root, "runs/RUN-A/screen.txt", "synthetic evidence (no real screenshot)\n")
        self.report = self.make_report("passed")
        self.payload = {
            "schema_version": 1, "run_id": "RUN-A", "mode": "standard",
            "baseline": {**self.baseline, "id": "BL-A", "status": "approved"},
            "runner": self.runner, "playwright_report": self.report,
            "assertions": [{"id": "A-1", "case_id": "TC-1", "fixture_id": "FX-1",
                            "test_title": "TC-1 concrete outcome", "oracle": self.oracle}],
            "results": [{"id": "A-1", "status": "passed", "fixture_verified": True,
                         "oracle_verdict": "passed", "evidence": [{**self.evidence, "content_review": "passed"}]}],
        }

    def tearDown(self):
        self.temp.cleanup()

    def make_report(self, status, title="TC-1 concrete outcome", file="example.spec.ts", retry=0):
        report = {"config": {"rootDir": str(self.root / "feature/tests")},
                  "suites": [{"file": file, "specs": [{"title": title, "tests": [{
            "expectedStatus": "passed", "results": [{"status": status, "retry": retry}],
        }]}]}]}
        return put(self.root, "runs/RUN-A/playwright-results.json", json.dumps(report))

    def check(self, payload=None):
        return check_automation_outcome(self.payload if payload is None else payload, self.root)

    def test_clean_concrete_case_passes_only_as_artifact_gate(self):
        result = self.check()
        self.assertEqual(result["status"], "passed")
        self.assertIn("not product acceptance", result["interpretation"])

    def test_swallowed_failure_cannot_be_reported_as_failed_with_green_playwright(self):
        self.payload["results"][0].update(status="failed", oracle_verdict="failed")
        result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("failed_assertion_swallowed_by_runner", result["error_codes"])

    def test_actual_failed_runner_and_failed_assertion_is_not_product_defect_proof(self):
        self.payload["playwright_report"] = self.make_report("failed")
        self.payload["results"][0].update(status="failed", oracle_verdict="failed")
        result = self.check()
        self.assertEqual(result["status"], "failed")
        self.assertIn("not product acceptance", result["interpretation"])

    def test_playwright_failure_or_skip_never_promoted_to_pass(self):
        for status in ("failed", "skipped", "timedOut", "interrupted"):
            with self.subTest(status=status):
                self.payload["playwright_report"] = self.make_report(status)
                self.assertIn("playwright_not_clean_pass", self.check()["error_codes"])

    def test_flaky_retry_not_clean_pass(self):
        data = json.loads((self.root / self.report["path"]).read_text())
        data["suites"][0]["specs"][0]["tests"][0]["results"].insert(0, {"status": "failed"})
        self.payload["playwright_report"] = put(self.root, self.report["path"], json.dumps(data))
        self.assertIn("playwright_not_clean_pass", self.check()["error_codes"])

    def test_duplicate_title_or_other_file_cannot_borrow_green_test(self):
        self.payload["playwright_report"] = self.make_report("passed", file="other.spec.ts")
        self.assertIn("playwright_test_missing", self.check()["error_codes"])
        data = json.loads((self.root / self.report["path"]).read_text())
        data["suites"][0]["file"] = "example.spec.ts"
        data["suites"].append(copy.deepcopy(data["suites"][0]))
        self.payload["playwright_report"] = put(self.root, self.report["path"], json.dumps(data))
        self.assertIn("playwright_test_not_unique", self.check()["error_codes"])

    def test_unbound_failed_test_in_same_report_blocks_whole_run(self):
        data = json.loads((self.root / self.report["path"]).read_text())
        extra = copy.deepcopy(data["suites"][0]["specs"][0])
        extra["title"] = "TC-OTHER unexpected failure"
        extra["tests"][0]["results"][0]["status"] = "failed"
        data["suites"][0]["specs"].append(extra)
        self.payload["playwright_report"] = put(self.root, self.report["path"], json.dumps(data))
        self.assertIn("unbound_nonpassed_test", self.check()["error_codes"])

    def test_old_run_report_and_evidence_cannot_be_claimed_by_new_run(self):
        self.payload["run_id"] = "RUN-OTHER"
        errors = self.check()["error_codes"]
        self.assertIn("playwright_run_identity_mismatch", errors)
        self.assertIn("evidence_run_identity_mismatch", errors)

    def test_report_from_other_root_cannot_borrow_matching_filename(self):
        data = json.loads((self.root / self.report["path"]).read_text())
        data["config"]["rootDir"] = str(self.root / "another-project")
        self.payload["playwright_report"] = put(self.root, self.report["path"], json.dumps(data))
        self.assertIn("playwright_test_missing", self.check()["error_codes"])

    def test_missing_or_tampered_assertion_or_evidence_blocks(self):
        self.payload["results"] = []
        self.assertIn("assertion_result_set_mismatch", self.check()["error_codes"])
        self.payload["results"] = [{"id": "A-1", "status": "passed", "fixture_verified": True,
                                     "oracle_verdict": "passed", "evidence": [{**self.evidence, "content_review": "passed"}]}]
        (self.root / self.evidence["path"]).write_text("changed")
        self.assertIn("evidence_hash_mismatch", self.check()["error_codes"])
        self.payload["results"][0]["evidence"][0].update(put(self.root, self.evidence["path"], "changed"))
        self.payload["results"][0]["evidence"][0]["content_review"] = "pending"
        self.assertIn("evidence_content_unreviewed", self.check()["error_codes"])

    def test_standard_case_and_assertion_must_come_from_single_baseline(self):
        self.payload["assertions"][0]["case_id"] = "TC-NOT-APPROVED"
        self.assertIn("case_not_in_baseline", self.check()["error_codes"])
        self.payload["assertions"][0]["case_id"] = "TC-1"
        self.payload["assertions"][0]["id"] = "A-NOT-APPROVED"
        self.payload["results"][0]["id"] = "A-NOT-APPROVED"
        self.assertIn("assertion_not_in_baseline_case", self.check()["error_codes"])

    def test_partial_case_cannot_be_claimed_complete(self):
        baseline = {"baseline_id": "BL-A", "cases": [{"id": "TC-1", "covered_rule_ids": ["A-1", "A-2"]}]}
        self.payload["baseline"].update(put(self.root, self.baseline["path"], json.dumps(baseline)))
        self.assertIn("baseline_case_rule_coverage_gap", self.check()["error_codes"])

    def test_baseline_identity_mismatch_blocks(self):
        self.payload["baseline"]["id"] = "BL-OTHER"
        self.assertIn("baseline_id_mismatch", self.check()["error_codes"])

    def test_wrong_oracle_fixture_and_baseline_cannot_pass(self):
        self.payload["assertions"][0]["oracle"]["sha256"] = "0" * 64
        self.payload["results"][0]["fixture_verified"] = False
        self.payload["baseline"]["status"] = "draft"
        errors = self.check()["error_codes"]
        self.assertTrue({"oracle_hash_mismatch", "fixture_unverified", "approved_baseline_missing"} <= set(errors))

    def test_rapid_charter_not_formal_approval(self):
        self.payload["mode"] = "rapid"
        self.payload["baseline"]["status"] = "provisional"
        self.assertEqual(self.check()["status"], "passed")
        self.assertEqual(self.check()["mode"], "rapid")
        self.payload["baseline"]["status"] = "approved"
        self.assertIn("provisional_charter_missing", self.check()["error_codes"])

    def test_blocked_and_unexecuted_need_reason_and_never_pass(self):
        self.payload["results"][0] = {"id": "A-1", "status": "blocked"}
        self.assertIn("nonpass_reason_missing", self.check()["error_codes"])
        self.payload["results"][0]["reason"] = "fixture absent"
        self.assertEqual(self.check()["status"], "blocked")

    def test_cli_nonzero_and_receipt_for_contradiction(self):
        self.payload["playwright_report"] = self.make_report("failed")
        input_path = self.root / "input.json"
        output = self.root / "receipt.json"
        input_path.write_text(json.dumps(self.payload))
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["automation-outcome-check", "--input", str(input_path), "--root", str(self.root),
                         "--output", str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.read_text())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
