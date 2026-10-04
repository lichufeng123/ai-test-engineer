"""Self-serve synthetic run preparation never launches a browser or business action."""
import json
import unittest

import test_execution_contract as contract_fixture
from ai_test_framework.execution_contract import check_execution_probe
from ai_test_framework.project import scaffold_playwright
from ai_test_framework.synthetic_prepare import prepare_synthetic_guarded_run


class SyntheticPrepareTests(unittest.TestCase):
    def setUp(self):
        contract_fixture.ExecutionContractTests.setUp(self)
        self.run_id = "RUN-SYNTH-NEW-001"
        self.web = self.root / "automation/web"
        self.assertEqual(scaffold_playwright(self.root)["status"], "created")
        (self.web / "node_modules/.bin").mkdir(parents=True)
        (self.web / "node_modules/playwright").mkdir(parents=True)
        (self.web / "node_modules/@playwright/test").mkdir(parents=True)
        (self.web / "node_modules/playwright/cli.js").write_text("fake local node install")
        (self.web / "node_modules/.bin/playwright").symlink_to("../playwright/cli.js")
        for dependency in ("playwright", "@playwright/test"):
            (self.web / "node_modules" / dependency / "package.json").write_text('{"version":"1.63.0"}')
        self.plan = self.root / "runs" / self.run_id / "test-plan.v1.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("# local/synthetic TC-EXAMPLE-001 A-EXAMPLE-001\nNo business actions.\n")

    def test_prepares_unique_probe_and_bundle_then_refuses_replay(self):
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertEqual(result["status"], "prepared", result)
        self.assertFalse(result["business_write_authorized"])
        probe = json.loads((self.plan.parent / "execution-probe.json").read_text())
        self.assertEqual(check_execution_probe(probe, self.root)["status"], "passed")
        bundle = json.loads((self.plan.parent / "guarded-bundle.json").read_text())
        self.assertEqual(bundle["probe"], probe)
        self.assertEqual(bundle["browser_channel"], "msedge")
        self.assertEqual(prepare_synthetic_guarded_run(self.root, self.run_id)["status"], "blocked")
        history = json.loads((self.root / ".ai-test/execution_history.json").read_text())
        runs = [run for item in history["automations"] for run in item["runs"] if run["run_id"] == self.run_id]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "started")

    def test_missing_or_wrong_plan_blocks_without_history(self):
        self.plan.unlink()
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertIn("saved_test_plan_missing", result["error_codes"])
        self.assertFalse((self.plan.parent / "execution-probe.json").exists())
        self.plan.write_text("not the agreed local/synthetic counter")
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertIn("synthetic_test_plan_scope_missing", result["error_codes"])

    def test_malformed_history_and_lockfile_drift_fail_closed(self):
        history = self.root / ".ai-test/execution_history.json"
        history.write_text("[]")
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertIn("execution_history_unavailable", result["error_codes"])
        self.assertFalse((self.plan.parent / "execution-probe.json").exists())
        history.write_text('{"schema_version":1,"automations":[]}')
        (self.web / "package-lock.json").write_text("{}")
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertIn("synthetic_starter_missing_or_modified", result["error_codes"])

    def test_starter_drift_and_report_collision_block(self):
        (self.web / "oracles/counter.ts").write_text("// not the starter")
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertIn("synthetic_starter_missing_or_modified", result["error_codes"])
        self.assertFalse((self.plan.parent / "execution-probe.json").exists())
        (self.web / "runs" / self.run_id).mkdir(parents=True)
        result = prepare_synthetic_guarded_run(self.root, self.run_id)
        self.assertIn("report_run_already_exists_or_unsafe", result["error_codes"])


if __name__ == "__main__":
    unittest.main()
