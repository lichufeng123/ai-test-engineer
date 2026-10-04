"""Offline report-gate controls; fake media and review declarations are NOT QA evidence."""
import contextlib
import copy
import hashlib
import io
import json
import unittest
from unittest.mock import patch

import test_guarded_run as guard_fixture
from ai_test_framework.cli import main
from ai_test_framework.guarded_run import execute_guarded_playwright
from ai_test_framework.report_promotion import check_report_promotion


class ReportPromotionTests(unittest.TestCase):
    def setUp(self):
        guard_fixture.GuardedRunTests.setUp(self)
        self.run = self.root / "runs/RUN-EXAMPLE"
        (self.run / "guarded-bundle.json").write_text(json.dumps(self.bundle))
        self.video = self.web / "runs/RUN-EXAMPLE/artifacts/video.webm"
        def fake_run(*args, **kwargs):
            result = guard_fixture.GuardedRunTests._launch(self, *args, **kwargs)
            self.video.parent.mkdir(parents=True, exist_ok=True)
            self.video.write_bytes(b"fictional video in isolated unit fixture")
            path = self.web / "runs/RUN-EXAMPLE/playwright-results.json"
            payload = json.loads(path.read_text())
            attachments = payload["suites"][0]["specs"][0]["tests"][0]["results"][0]["attachments"]
            attachments.append({"name": "video", "contentType": "video/webm", "path": str(self.video)})
            path.write_text(json.dumps(payload))
            return result
        with patch("ai_test_framework.guarded_run._start_process", side_effect=fake_run):
            synthetic = execute_guarded_playwright(self.bundle, self.root)
        self.assertEqual(synthetic["status"], "review_required", synthetic)
        self.run = self.root / "runs/RUN-EXAMPLE"
        def ref(path):
            target = self.root / path
            return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        self.ref = ref
        report = "automation/web/runs/RUN-EXAMPLE/playwright-results.json"
        video = self.video.relative_to(self.root).as_posix()
        items = []
        for name in (report, video):
            file = ref(name)
            items.append({**file, "human_review": {"status": "passed", "reviewer": "UNIT-TEST-DECLARATION",
                                                     "reviewed_sha256": file["sha256"]}})
        manifest = {"schema_version": 1, "items": items}
        (self.run / "privacy-review.json").write_text(json.dumps(manifest))
        self.request = {"schema_version": 1, "mode": "synthetic", "run_id": "RUN-EXAMPLE",
                        "guarded_receipt": ref("runs/RUN-EXAMPLE/guarded-run-receipt.json"),
                        "privacy_manifest": ref("runs/RUN-EXAMPLE/privacy-review.json")}

    def test_complete_local_material_still_never_promotes_product(self):
        result = check_report_promotion(self.request, self.root)
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["technical_checks"], "passed")
        self.assertEqual(result["product_verdict"], "not_evaluated")
        self.assertEqual(result["human_review_identity"], "declaration_only_not_authenticated")

    def test_cli_returns_nonzero_even_when_local_material_is_consistent(self):
        request_path = self.run / "report-promotion-request.json"
        request_path.write_text(json.dumps(self.request))
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["report-promotion-check", "--root", str(self.root), "--input", str(request_path)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["product_verdict"], "not_evaluated")

    def test_business_mode_cannot_self_claim_current_or_authorization(self):
        request = {**self.request, "mode": "standard", "current_verified": True}
        result = check_report_promotion(request, self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("trusted_business_promotion_adapter_missing", result["error_codes"])

    def test_missing_review_or_video_blocks(self):
        manifest = json.loads((self.run / "privacy-review.json").read_text())
        del manifest["items"][1]["human_review"]
        (self.run / "privacy-review.json").write_text(json.dumps(manifest))
        request = {**self.request, "privacy_manifest": self.ref("runs/RUN-EXAMPLE/privacy-review.json")}
        self.assertIn("semantic_privacy_review_missing", check_report_promotion(request, self.root)["error_codes"])
        self.video.unlink()
        self.assertEqual(check_report_promotion(request, self.root)["status"], "blocked")

    def test_tamper_report_marker_or_history_blocks(self):
        reporter = self.web / "runs/RUN-EXAMPLE/playwright-results.json"
        reporter.write_text("{}")
        self.assertIn("playwright_report_hash_mismatch", check_report_promotion(self.request, self.root)["error_codes"])
        marker = self.root / ".ai-test/guarded-runs/RUN-EXAMPLE.json"
        marker.write_text("{}")
        self.assertIn("guarded_marker_mismatch", check_report_promotion(self.request, self.root)["error_codes"])
        history = self.root / ".ai-test/execution_history.json"
        state = json.loads(history.read_text())
        state["automations"][0]["runs"][0]["status"] = "passed"
        history.write_text(json.dumps(state))
        self.assertIn("run_history_not_closed_for_source", check_report_promotion(self.request, self.root)["error_codes"])

    def test_direct_playwright_only_or_extra_privacy_file_blocks(self):
        other = copy.deepcopy(self.request)
        other["guarded_receipt"]["sha256"] = "0" * 64
        self.assertIn("guarded_receipt_hash_mismatch", check_report_promotion(other, self.root)["error_codes"])
        manifest = json.loads((self.run / "privacy-review.json").read_text())
        manifest["items"].append(manifest["items"][0])
        (self.run / "privacy-review.json").write_text(json.dumps(manifest))
        other = {**self.request, "privacy_manifest": self.ref("runs/RUN-EXAMPLE/privacy-review.json")}
        self.assertIn("privacy_review_coverage_or_hash_mismatch", check_report_promotion(other, self.root)["error_codes"])


if __name__ == "__main__":
    unittest.main()
