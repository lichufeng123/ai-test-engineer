"""Synthetic end-to-end negative controls for environment and write intent gates."""

import base64
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_test_framework.environment_profile import resolve_environment
from ai_test_framework.execution_contract import check_execution_probe, digest, reserve_write_intent
from ai_test_framework.execution_history import finish_execution, start_execution
from ai_test_framework.execution_readiness import build_readiness_plan, evaluate_execution_readiness
from ai_test_framework.project import initialize_project
from ai_test_framework.playwright_receipts import collect_playwright_receipts


def artifact(root, name, payload):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class ExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize_project(self.root, name="synthetic", system_id="SYNTHETIC", environments=["local"], platforms=["web"])
        self.now = datetime.now(timezone.utc)
        iso = lambda dt: dt.isoformat(timespec="seconds")
        identity = {"stage": "local", "zone": "synthetic", "platform": "web",
                    "organization_view_id": "ORG-EXAMPLE", "role_id": "ROLE-EXAMPLE", "build_id": "BUILD-1"}
        self.profile = {"schema_version": 1, "profile_id": "ENV-1", "status": "reviewed", **identity,
                        "capabilities": ["synthetic_ui"],
                        "reviewed_at": iso(self.now - timedelta(days=1)),
                        "expires_at": iso(self.now + timedelta(days=1))}
        self.observation = {"schema_version": 1, **identity, "capabilities": ["synthetic_ui"],
                            "observed_at": iso(self.now)}
        self.request = {"schema_version": 1, **identity, "required_capabilities": ["synthetic_ui"],
                        "operation": "write"}
        self.env = resolve_environment(self.profile, self.observation, self.request, now=self.now)
        self.assertEqual(self.env["status"], "passed")
        self.baseline = artifact(self.root, "cases/approved.json", {
            "baseline_id": "BL-EXAMPLE", "cases": [{"id": "TC-EXAMPLE", "covered_rule_ids": ["A-EXAMPLE"]}]})
        source = {"schema_version": 1, "plan_id": "PLAN-EXAMPLE", "requirement_baseline_id": "REQ-EXAMPLE",
                  "feature": "synthetic", "automation_scope": {"case_ids": ["TC-EXAMPLE"]},
                  "case_requirements": [{"case_id": "TC-EXAMPLE", "required_role_ids": ["ROLE-EXAMPLE"],
                                         "required_fixture_ids": ["FX-EXAMPLE"], "required_environment_ids": ["local"]}],
                  "account_requirements": [], "fixture_requirements": [], "evidence_plan": {}}
        self.plan = build_readiness_plan(source)
        self.plan_ref = artifact(self.root, "plans/readiness.json", self.plan)
        self.readiness = evaluate_execution_readiness(self.plan, {
            "schema_version": 1, "plan_id": self.plan["plan_id"], "plan_sha256": self.plan["plan_sha256"],
            "target_environment": "local", "scope_confirmed": True, "environment_confirmed": True,
            "account_roles_confirmed": True, "data_plan_confirmed": True,
            "available_role_ids": ["ROLE-EXAMPLE"], "ready_fixture_ids": ["FX-EXAMPLE"],
            "excluded_case_ids": []})
        self.assertEqual(self.readiness["status"], "passed")
        self.ready_ref = artifact(self.root, "runs/RUN-EXAMPLE/readiness.json", self.readiness)
        self.env_ref = artifact(self.root, "runs/RUN-EXAMPLE/environment.json", self.env)
        self.profile_ref = artifact(self.root, "profiles/synthetic.json", self.profile)
        self.oracle_ref = artifact(self.root, "oracles/synthetic.json", {"expected": 3})
        start_execution(self.root, automation_id="AUTO-EXAMPLE", run_id="RUN-EXAMPLE",
                        feature="synthetic", environment="local", platforms=["web"],
                        purpose="contract negative control", objective="no business write",
                        scope="single synthetic case", started_at=iso(self.now), baseline="BL-EXAMPLE")
        self.probe = {"schema_version": 1, "run_id": "RUN-EXAMPLE", "case_id": "TC-EXAMPLE",
                      "mode": "standard", "baseline": {**self.baseline, "id": "BL-EXAMPLE", "status": "approved"},
                      "plan": self.plan_ref, "plan_sha256": self.plan["plan_sha256"],
                      "readiness_receipt": self.ready_ref,
                      "profile": self.profile_ref, "profile_sha256": self.env["profile_sha256"],
                      "environment_receipt": self.env_ref, "oracle": self.oracle_ref,
                      "assertion_ids": ["A-EXAMPLE"],
                      "fixture": {"id": "FX-EXAMPLE", "business_key": "synthetic-key-1",
                                  "pre_state_sha256": "a" * 64, "match_count": 1},
                      "action": {"id": "INCREMENT", "kind": "write", "input_sha256": "b" * 64}}
        self.current = {"run_id": "RUN-EXAMPLE", "case_id": "TC-EXAMPLE",
                        **self.probe["fixture"], **identity, "observed_at": iso(self.now),
                        "profile_sha256": self.env["profile_sha256"]}
        self.approval = {"run_id": "RUN-EXAMPLE", "case_id": "TC-EXAMPLE", "status": "approved",
                         "approved_at": iso(self.now), "expires_at": iso(self.now + timedelta(minutes=2)),
                         "approved_by": "SYNTHETIC-REVIEWER", "action_id": "INCREMENT",
                         "business_key": "synthetic-key-1", "input_sha256": "b" * 64,
                         "probe_sha256": digest(self.probe)}

    def test_environment_exact_match_and_drift(self):
        self.assertFalse(self.env["write_authorized"])
        changed = copy.deepcopy(self.observation)
        changed["zone"] = "different"
        self.assertIn("zone_mismatch", resolve_environment(
            self.profile, changed, self.request, now=self.now)["error_codes"])
        changed = copy.deepcopy(self.observation)
        changed["observed_at"] = (self.now - timedelta(minutes=3)).isoformat()
        self.assertIn("observation_stale", resolve_environment(
            self.profile, changed, self.request, now=self.now)["error_codes"])
        changed = copy.deepcopy(self.observation)
        changed["capabilities"] = []
        self.assertIn("observed_capability_missing", resolve_environment(
            self.profile, changed, self.request, now=self.now)["error_codes"])
        legacy = {**self.profile, "production_writes_authorized": True}
        self.assertIn("profile_unknown_fields", resolve_environment(
            legacy, self.observation, self.request, now=self.now)["error_codes"])
        self.profile["expires_at"] = (self.now - timedelta(seconds=1)).isoformat()
        self.assertIn("profile_expired_or_unreviewed", resolve_environment(
            self.profile, self.observation, self.request, now=self.now)["error_codes"])

    def test_probe_checks_existing_case_and_all_hashes(self):
        self.assertEqual(check_execution_probe(self.probe, self.root)["status"], "passed")
        changed = copy.deepcopy(self.probe)
        changed["assertion_ids"] = ["A-OTHER"]
        self.assertIn("assertion_ids_differ_from_baseline", check_execution_probe(changed, self.root)["error_codes"])
        changed = copy.deepcopy(self.probe)
        changed["fixture"]["match_count"] = 0
        self.assertIn("fixture_not_unique_or_unfrozen", check_execution_probe(changed, self.root)["error_codes"])
        changed = copy.deepcopy(self.probe)
        changed["plan_sha256"] = "0" * 64
        self.assertIn("plan_hash_mismatch", check_execution_probe(changed, self.root)["error_codes"])
        changed = copy.deepcopy(self.probe)
        changed["baseline"] = "bad"
        self.assertEqual(check_execution_probe(changed, self.root)["status"], "blocked")
        (self.root / self.oracle_ref["path"]).write_text('{"expected": 4}', encoding="utf-8")
        self.assertIn("oracle_hash_mismatch", check_execution_probe(self.probe, self.root)["error_codes"])

    def test_write_intent_is_exclusive_across_concurrent_attempts(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda unused: reserve_write_intent(
                self.probe, self.current, self.approval, self.root), range(4)))
        self.assertEqual([r["status"] for r in receipts].count("reserved"), 1)
        self.assertEqual([r["status"] for r in receipts].count("blocked"), 3)
        self.assertEqual(len(list((self.root / ".ai-test/write-intents").glob("*.json"))), 1)
        self.assertIn("target_already_reserved_manual_reconcile", reserve_write_intent(
            self.probe, self.current, self.approval, self.root)["error_codes"])

    def test_nonlocal_business_write_stays_blocked_even_with_declared_approval(self):
        profile = copy.deepcopy(self.profile)
        profile["stage"] = "sit"
        observation = copy.deepcopy(self.observation)
        observation["stage"] = "sit"
        request = copy.deepcopy(self.request)
        request["stage"] = "sit"
        env = resolve_environment(profile, observation, request, now=self.now)
        self.assertEqual(env["status"], "passed")
        probe = copy.deepcopy(self.probe)
        probe["profile"] = artifact(self.root, self.profile_ref["path"], profile)
        probe["profile_sha256"] = env["profile_sha256"]
        probe["environment_receipt"] = artifact(self.root, self.env_ref["path"], env)
        self.assertEqual(check_execution_probe(probe, self.root)["status"], "passed")
        observed = {**self.current, "stage": "sit", "profile_sha256": env["profile_sha256"]}
        approved = {**self.approval, "probe_sha256": digest(probe)}
        result = reserve_write_intent(probe, observed, approved, self.root)
        self.assertIn("business_authorization_adapter_missing", result["error_codes"])
        self.assertFalse((self.root / ".ai-test/write-intents").exists())

    def test_bad_identity_or_approval_never_reserves(self):
        changed = copy.deepcopy(self.current)
        changed["business_key"] = "different"
        self.assertIn("fixture_identity_or_prestate_drift", reserve_write_intent(
            self.probe, changed, self.approval, self.root)["error_codes"])
        changed = copy.deepcopy(self.approval)
        changed["probe_sha256"] = "old-plan"
        self.assertIn("write_approval_unbound", reserve_write_intent(
            self.probe, self.current, changed, self.root)["error_codes"])
        self.assertFalse((self.root / ".ai-test/write-intents").exists())

    def test_reporter_receipts_derive_verdict_without_manual_results(self):
        runner = artifact(self.root, "feature/tests/synthetic.spec.ts", {"synthetic": True})
        receipt = {"run_id": "RUN-EXAMPLE", "case_id": "TC-EXAMPLE", "assertion_id": "A-EXAMPLE",
                   "fixture_id": "FX-EXAMPLE", "probe_sha256": digest(self.probe),
                   "oracle_sha256": self.oracle_ref["sha256"], "status": "passed"}
        attempt = {"status": "passed", "attachments": [{
            "name": "ai-test-assertion-A-EXAMPLE", "contentType": "application/vnd.ai-test.assertion+json",
            "body": base64.b64encode(json.dumps(receipt).encode()).decode()}]}
        report = {"config": {"rootDir": str(self.root / "feature/tests")},
                  "suites": [{"file": "synthetic.spec.ts", "specs": [{"title": "TC-EXAMPLE sample",
                              "tests": [{"expectedStatus": "passed", "results": [attempt]}]}]}]}
        report_ref = artifact(self.root, "runs/RUN-EXAMPLE/playwright-results.json", report)
        binding = {"schema_version": 1, "probe": self.probe, "runner": runner,
                   "playwright_report": report_ref, "test_title": "TC-EXAMPLE sample"}
        result = collect_playwright_receipts(binding, self.root)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["assertions"], [{"assertion_id": "A-EXAMPLE", "status": "passed"}])
        self.assertTrue(result["manual_review_required"])
        finish_execution(self.root, run_id="RUN-EXAMPLE", result_status="partial", summary="synthetic",
                         finished_at=(self.now + timedelta(seconds=1)).isoformat(timespec="seconds"))
        self.assertEqual(check_execution_probe(self.probe, self.root)["status"], "blocked")
        self.assertEqual(collect_playwright_receipts(binding, self.root)["status"], "passed")
        report["suites"][0]["specs"][0]["tests"][0]["results"][0]["attachments"] = []
        binding["playwright_report"] = artifact(self.root, report_ref["path"], report)
        self.assertIn("assertion_attachment_not_unique", collect_playwright_receipts(binding, self.root)["error_codes"])
        receipt["status"] = "failed"
        attempt["attachments"] = [{"name": "ai-test-assertion-A-EXAMPLE",
                                   "contentType": "application/vnd.ai-test.assertion+json",
                                   "body": base64.b64encode(json.dumps(receipt).encode()).decode()}]
        binding["playwright_report"] = artifact(self.root, report_ref["path"], report)
        self.assertIn("assertion_not_passed", collect_playwright_receipts(binding, self.root)["error_codes"])
        receipt["status"] = "passed"
        receipt["case_id"] = "TC-OTHER"
        attempt["attachments"][0]["body"] = base64.b64encode(json.dumps(receipt).encode()).decode()
        binding["playwright_report"] = artifact(self.root, report_ref["path"], report)
        self.assertIn("assertion_attachment_identity_mismatch", collect_playwright_receipts(binding, self.root)["error_codes"])
        receipt["case_id"] = "TC-EXAMPLE"
        attempt["attachments"][0]["body"] = base64.b64encode(json.dumps(receipt).encode()).decode()
        attempt["status"] = "failed"
        binding["playwright_report"] = artifact(self.root, report_ref["path"], report)
        self.assertIn("playwright_did_not_pass", collect_playwright_receipts(binding, self.root)["error_codes"])

    def test_malformed_or_sensitive_input_blocks_not_crashes(self):
        probe = copy.deepcopy(self.probe)
        probe["token"] = "must-never-be-echoed"
        self.assertEqual(check_execution_probe(probe, self.root)["error_codes"], ["probe_contains_sensitive_field"])
        profile = copy.deepcopy(self.profile)
        profile["password"] = "must-never-be-echoed"
        result = resolve_environment(profile, self.observation, self.request, now=self.now)
        self.assertIn("profile_contains_sensitive_field", result["error_codes"])
        self.assertNotIn("must-never-be-echoed", json.dumps(result))
        self.assertEqual(check_execution_probe({"schema_version": 1, "baseline": "oops"}, self.root)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
