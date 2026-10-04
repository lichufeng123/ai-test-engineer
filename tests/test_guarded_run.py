"""Synthetic-only coordinator tests: no browser, product URL or credentials."""
import base64
import copy
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import test_execution_contract as contract_fixture
from ai_test_framework.execution_contract import digest
from ai_test_framework.execution_readiness import evaluate_execution_readiness, plan_sha256
from ai_test_framework.guarded_run import execute_guarded_playwright


class GuardedRunTests(unittest.TestCase):
    def setUp(self):
        contract_fixture.ExecutionContractTests.setUp(self)
        self.web = self.root / "automation/web"
        scaffold = Path(__file__).resolve().parents[1] / "src/ai_test_framework/starter_playwright"
        shutil.copytree(scaffold, self.web)
        (self.web / "node_modules/.bin").mkdir(parents=True)
        (self.web / "node_modules/playwright").mkdir(parents=True)
        (self.web / "node_modules/@playwright/test").mkdir(parents=True)
        (self.web / "node_modules/playwright/cli.js").write_text("fake local binary")
        (self.web / "node_modules/.bin/playwright").symlink_to("../playwright/cli.js")
        (self.web / "node_modules/playwright/package.json").write_text('{"version":"1.63.0"}')
        (self.web / "node_modules/@playwright/test/package.json").write_text('{"version":"1.63.0"}')
        def ref(relative):
            return {"path": relative, "sha256": hashlib.sha256((self.root / relative).read_bytes()).hexdigest()}
        self.config_ref = ref("automation/web/playwright.config.ts")
        self.package_ref = ref("automation/web/package.json")
        self.runner_ref = ref("automation/web/tests/counter.spec.ts")
        self.probe["mode"] = "rapid"
        charter = contract_fixture.artifact(self.root, "runs/RUN-EXAMPLE/charter.json", {"charter_id": "BL-EXAMPLE"})
        self.probe["baseline"] = {**charter, "id": "BL-EXAMPLE", "status": "provisional"}
        self.title = "TC-EXAMPLE-001 counter increments once"
        self.probe["case_id"] = "TC-EXAMPLE-001"
        self.probe["assertion_ids"] = ["A-EXAMPLE-001"]
        self.probe["fixture"]["id"] = "FX-EXAMPLE-001"
        plan = copy.deepcopy(self.plan)
        plan["automation_scope"]["case_ids"] = ["TC-EXAMPLE-001"]
        plan["case_requirements"][0]["case_id"] = "TC-EXAMPLE-001"
        plan["case_requirements"][0]["required_fixture_ids"] = ["FX-EXAMPLE-001"]
        plan["plan_sha256"] = plan_sha256(plan)
        self.probe["plan"] = contract_fixture.artifact(self.root, self.plan_ref["path"], plan)
        self.probe["plan_sha256"] = plan["plan_sha256"]
        ready = evaluate_execution_readiness(plan, {"schema_version": 1, "plan_id": plan["plan_id"],
            "plan_sha256": plan["plan_sha256"], "target_environment": "local",
            "scope_confirmed": True, "environment_confirmed": True,
            "account_roles_confirmed": True, "data_plan_confirmed": True,
            "available_role_ids": ["ROLE-EXAMPLE"], "ready_fixture_ids": ["FX-EXAMPLE-001"],
            "excluded_case_ids": []})
        self.assertEqual(ready["status"], "passed")
        self.probe["readiness_receipt"] = contract_fixture.artifact(self.root, self.ready_ref["path"], ready)
        self.test_plan_ref = contract_fixture.artifact(self.root, "runs/RUN-EXAMPLE/test-plan.v1.md", {"scope": "local"})
        self.bundle = {"schema_version": 1, "probe": self.probe, "test_plan": self.test_plan_ref,
                       "runner": self.runner_ref,
                       "config": self.config_ref, "package": self.package_ref,
                       "web_root": "automation/web", "test_title": self.title, "browser_channel": "msedge"}

    def _launch(self, args, *, cwd, env, timeout, attach=True, mutate=False, exit_code=0):
        self.assertEqual(timeout, 120)
        self.assertEqual(args[1], "test")
        self.assertEqual(args[2], "tests/counter.spec.ts")
        self.assertEqual(args[4], "TC\\-EXAMPLE\\-001\\ counter\\ increments\\ once$")
        self.assertEqual(env["AI_TEST_RUN_ID"], "RUN-EXAMPLE")
        self.assertNotIn("password", env)
        receipt = {"run_id": "RUN-EXAMPLE", "case_id": "TC-EXAMPLE-001", "assertion_id": "A-EXAMPLE-001",
                   "fixture_id": "FX-EXAMPLE-001", "probe_sha256": digest(self.probe),
                   "oracle_sha256": self.oracle_ref["sha256"], "status": "passed"}
        attachments = [{"name": "ai-test-assertion-A-EXAMPLE-001",
                        "contentType": "application/vnd.ai-test.assertion+json",
                        "body": base64.b64encode(json.dumps(receipt).encode()).decode()}] if attach else []
        report = {"config": {"rootDir": str(self.web / "tests")},
                  "suites": [{"file": "counter.spec.ts", "specs": [{"title": self.title,
                              "tests": [{"expectedStatus": "passed", "results": [
                                  {"status": "passed", "attachments": attachments}]}]}]}]}
        contract_fixture.artifact(self.root, "automation/web/runs/RUN-EXAMPLE/playwright-results.json", report)
        if mutate:
            (self.root / self.runner_ref["path"]).write_text("// changed mid-run")
        return exit_code

    def _run(self, bundle, launcher=None):
        with patch("ai_test_framework.guarded_run._start_process", side_effect=launcher or self._launch):
            return execute_guarded_playwright(bundle, self.root)

    def test_single_bound_reporter_requires_semantic_review_and_cannot_replay(self):
        outcome = self._run(self.bundle)
        self.assertEqual(outcome["status"], "review_required", outcome)
        self.assertEqual(outcome["reporter_status"], "passed")
        self.assertEqual(outcome["product_verdict"], "not_evaluated")
        history = json.loads((self.root / ".ai-test/execution_history.json").read_text())
        self.assertEqual(history["automations"][0]["runs"][0]["status"], "partial")
        self.assertEqual(self._run(self.bundle)["status"], "blocked")

    def test_missing_attachment_blocks_and_closes_history(self):
        outcome = self._run(self.bundle, lambda *a, **k: self._launch(*a, **k, attach=False))
        self.assertIn("assertion_attachment_not_unique", outcome["error_codes"])
        self.assertEqual(outcome["status"], "blocked")
        history = json.loads((self.root / ".ai-test/execution_history.json").read_text())
        self.assertEqual(history["automations"][0]["runs"][0]["status"], "blocked")

    def test_exit_failure_and_source_mutation_block_even_with_green_reporter(self):
        outcome = self._run(self.bundle, lambda *a, **k: self._launch(*a, **k, exit_code=1, mutate=True))
        self.assertIn("playwright_exit_nonzero", outcome["error_codes"])
        self.assertIn("runner_changed_during_run", outcome["error_codes"])
        self.assertEqual(outcome["status"], "blocked")

    def test_timeout_sticks_and_cannot_replay(self):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        result = self._run(self.bundle, timeout)
        self.assertIn("playwright_timeout_unknown_state_no_retry", result["error_codes"])
        self.assertIn("fresh_playwright_report_missing", result["error_codes"])
        self.assertEqual(self._run(self.bundle)["status"], "blocked")
        history = json.loads((self.root / ".ai-test/execution_history.json").read_text())
        self.assertEqual(history["automations"][0]["runs"][0]["status"], "blocked")

    def test_extra_green_spec_is_not_silent_success(self):
        def two_tests(*args, **kwargs):
            result = self._launch(*args, **kwargs)
            p = self.web / "runs/RUN-EXAMPLE/playwright-results.json"
            payload = json.loads(p.read_text())
            payload["suites"][0]["specs"].append({"title": "other green test", "tests": [
                {"expectedStatus": "passed", "results": [{"status": "passed", "attachments": []}]}]})
            p.write_text(json.dumps(payload))
            return result
        result = self._run(self.bundle, two_tests)
        self.assertIn("playwright_test_count_not_one", result["error_codes"])

    def test_unfrozen_plan_and_unrecognized_bundle_field_block_before_launch(self):
        extra = {**self.bundle, "command": "unreviewed"}
        self.assertIn("bundle_fields_invalid", self._run(
            extra, lambda *a, **k: self.fail("launched"))["error_codes"])
        (self.root / self.test_plan_ref["path"]).write_text("scope drift")
        outcome = self._run(self.bundle, lambda *a, **k: self.fail("launched"))
        self.assertIn("test_plan_hash_mismatch", outcome["error_codes"])
        self.assertFalse((self.root / ".ai-test/guarded-runs").exists())
        (self.web / "flows/counterFlow.ts").write_text("// unreviewed extra request")
        outcome = self._run(self.bundle, lambda *a, **k: self.fail("launched"))
        self.assertIn("synthetic_starter_source_drift", outcome["error_codes"])

    def test_symlink_report_directory_blocks_before_launch(self):
        (self.web / "runs").symlink_to(self.root / "runs", target_is_directory=True)
        outcome = self._run(self.bundle, lambda *a, **k: self.fail("launched"))
        self.assertIn("report_directory_unsafe", outcome["error_codes"])
        self.assertFalse((self.root / ".ai-test/guarded-runs").exists())

    def test_nonlocal_or_hash_drift_never_launches(self):
        altered = copy.deepcopy(self.bundle)
        altered["runner"]["sha256"] = "0" * 64
        outcome = self._run(altered, lambda *a, **k: self.fail("launched"))
        self.assertIn("runner_hash_mismatch", outcome["error_codes"])
        self.assertFalse((self.root / ".ai-test/guarded-runs").exists())
        profile = json.loads((self.root / self.profile_ref["path"]).read_text())
        profile["stage"] = "sit"
        contract_fixture.artifact(self.root, self.profile_ref["path"], profile)
        outcome = self._run(self.bundle, lambda *a, **k: self.fail("launched"))
        self.assertIn("business_environment_not_supported", outcome["error_codes"])
