import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.cli import main
from ai_test_framework.one_pass import check_one_pass
from ai_test_framework.work_items import create_work_item, show_work_item, update_work_item, list_work_items


class OnePassModeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "source.md").write_text("Reviewed decision: synthetic import updates one row.\n", encoding="utf-8")
        (self.root / "risk.json").write_text("{}", encoding="utf-8")
        (self.root / "runs/ONE-001").mkdir(parents=True)
        (self.root / "runs/ONE-001/result.png").write_bytes(b"synthetic screenshot")
        digest = lambda name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        self.plan = {
            "schema_version": 1,
            "run_id": "ONE-001", "requirement_id": "REQ-ONE-001", "mode": "one_pass",
            "feature": "Synthetic import", "environment": "sit", "platform": "web",
            "scope": {"included": ["one synthetic import"], "excluded": ["production"]},
            "result_authority": "provisional",
            "knowledge_context": [
                {"kind": "decision", "path": "source.md", "sha256": digest("source.md"), "read_status": "read"},
                {"kind": "omission_risk", "path": "risk.json", "sha256": digest("risk.json"), "read_status": "read"},
            ],
            "cases": [
                {"case_id": "OP-001", "title": "Import and readback", "source_ref": "source.md#1",
                 "expectation_status": "confirmed",
                 "role": "test editor", "fixture": {"id": "QA-001", "unique_locator": "fixture-id=QA-001", "scope": "sit store"},
                 "preconditions": ["target uniquely identified"],
                 "steps": [{"step_id": "S1", "action": "upload one file and reload",
                            "expected": "one row updates to 7", "oracle": {"source_ref": "source.md#1", "independent": True},
                            "evidence_plan": ["readback screenshot"]}],
                 "write_boundary": "one isolated SIT fixture", "stop_conditions": ["unknown submit state"]},
                {"case_id": "OP-002", "title": "Unknown permission rule", "source_ref": "pending-decision",
                 "expectation_status": "unknown",
                 "role": "restricted", "fixture": {"id": "QA-002", "unique_locator": "fixture-id=QA-002", "scope": "sit store"},
                 "preconditions": ["reviewed expected behavior available"],
                 "steps": [{"step_id": "S1", "action": "open direct link", "expected": "deny write",
                            "oracle": {"source_ref": "pending-decision", "independent": True},
                            "evidence_plan": ["permission screenshot"]}],
                 "write_boundary": "read-only", "stop_conditions": ["expectation unknown"],
                 "readiness": "blocked", "blocker": "permission behavior not confirmed"},
            ],
        }
        self.plan_file = self.root / "runs/ONE-001/one-pass-plan.json"
        self.plan_file.write_text(json.dumps(self.plan), encoding="utf-8")
        self.results = {"schema_version": 1, "run_id": "ONE-001",
                        "plan_sha256": hashlib.sha256(self.plan_file.read_bytes()).hexdigest(),
                        "cases": [
                            {"case_id": "OP-001", "status": "passed", "steps": [
                                {"step_id": "S1", "status": "passed", "actual": "row is 7 after reload",
                                 "evidence_refs": ["runs/ONE-001/result.png"]}]},
                            {"case_id": "OP-002", "status": "blocked", "reason": "permission behavior not confirmed",
                             "steps": [{"step_id": "S1", "status": "not_executed", "actual": "not opened", "evidence_refs": []}]},
                        ]}

    def tearDown(self):
        self.directory.cleanup()

    def test_work_item_mode_is_distinct_and_does_not_skip_formal_case_gate(self):
        item = create_work_item(self.root, requirement_id="REQ-ONE-001", title="One pass",
                                feature="Synthetic import", environments=["sit"], platforms=["web"],
                                scope="synthetic only", test_mode="one_pass")
        self.assertEqual(item["test_mode"], "one_pass")
        self.assertIsNone(item["official_baseline"]["id"])
        overview = (self.root / "TEST_WORK_ITEMS.md").read_text(encoding="utf-8")
        self.assertIn("当前一站式测试", overview)
        self.assertEqual(list_work_items(self.root)["items"][0]["test_mode"], "one_pass")
        with self.assertRaisesRegex(ValueError, "CASE_DESIGN"):
            update_work_item(self.root, requirement_id="REQ-ONE-001", stage="CASE_DESIGN")
        self.assertEqual(show_work_item(self.root, "REQ-ONE-001")["current_stage"], "INTAKE")

    def test_existing_rapid_item_can_switch_mode_without_replacing_work_item(self):
        create_work_item(self.root, requirement_id="REQ-ONE-001", title="One pass",
                         feature="Synthetic import", environments=["sit"], platforms=["web"],
                         scope="synthetic only", test_mode="rapid")
        item = update_work_item(self.root, requirement_id="REQ-ONE-001", test_mode="one_pass")
        self.assertEqual(item["test_mode"], "one_pass")
        self.assertIn("REQ-ONE-001", (self.root / "TEST_WORK_ITEMS.md").read_text(encoding="utf-8"))

    def test_preflight_and_closure_bind_every_case_and_step(self):
        preflight = check_one_pass(self.plan, self.root)
        self.assertEqual(preflight["status"], "ready")
        self.assertEqual(preflight["case_count"], 2)
        self.assertEqual(preflight["ready_case_ids"], ["OP-001"])
        self.assertEqual(preflight["case_preview"][0]["steps"][0]["expected"], "one row updates to 7")
        closure = check_one_pass(self.plan, self.root, results=self.results, plan_path=self.plan_file)
        self.assertEqual(closure["status"], "checked")
        self.assertEqual(closure["result_authority"], "provisional")
        self.assertEqual(closure["case_results"], {"OP-001": "passed", "OP-002": "blocked"})
        self.assertEqual(closure["case_details"]["OP-001"]["steps"][0]["actual"], "row is 7 after reload")
        self.assertEqual(closure["semantic_evidence_review"], "not_performed")

    def test_missing_or_derived_expectation_cannot_be_ready(self):
        self.plan["cases"][0]["steps"][0]["expected"] = ""
        self.assertEqual(check_one_pass(self.plan, self.root)["status"], "blocked")
        self.plan["cases"][0]["steps"][0]["expected"] = "one row updates to 7"
        self.plan["cases"][0]["steps"][0]["oracle"]["independent"] = False
        self.assertEqual(check_one_pass(self.plan, self.root)["status"], "blocked")
        self.plan["cases"][0]["steps"][0]["oracle"]["independent"] = True
        self.plan["cases"][0]["expectation_status"] = "unknown"
        self.assertEqual(check_one_pass(self.plan, self.root)["status"], "blocked")
        self.plan["cases"][0]["expectation_status"] = "confirmed"
        self.plan["cases"][0]["source_ref"] = "unread-source.md#1"
        self.assertEqual(check_one_pass(self.plan, self.root)["status"], "blocked")

    def test_pass_cannot_hide_missing_evidence_step_or_unknown_business_rule(self):
        self.results["cases"][0]["steps"][0]["evidence_refs"] = []
        self.assertEqual(check_one_pass(self.plan, self.root, results=self.results, plan_path=self.plan_file)["status"], "blocked")
        self.results["cases"][0]["steps"][0]["evidence_refs"] = ["runs/ONE-001/result.png"]
        self.results["cases"][1]["status"] = "passed"
        self.results["cases"][1]["steps"][0] = {"step_id": "S1", "status": "passed", "actual": "looks denied",
                                                  "evidence_refs": ["runs/ONE-001/result.png"]}
        self.assertEqual(check_one_pass(self.plan, self.root, results=self.results, plan_path=self.plan_file)["status"], "blocked")

    def test_stale_hash_missing_case_and_no_omission_risk_read_block(self):
        self.results["plan_sha256"] = "0" * 64
        self.assertEqual(check_one_pass(self.plan, self.root, results=self.results, plan_path=self.plan_file)["status"], "blocked")
        self.results["plan_sha256"] = hashlib.sha256(self.plan_file.read_bytes()).hexdigest()
        self.results["cases"].pop()
        self.assertEqual(check_one_pass(self.plan, self.root, results=self.results, plan_path=self.plan_file)["status"], "blocked")
        self.plan["knowledge_context"].pop()
        self.assertEqual(check_one_pass(self.plan, self.root)["status"], "blocked")

    def test_schema_template_and_cli_expose_explicit_mode(self):
        schema = json.loads((ROOT / "schemas/one-pass-test-plan.schema.json").read_text(encoding="utf-8"))
        template = json.loads((ROOT / "templates/one-pass-test-plan.example.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["mode"]["const"], "one_pass")
        self.assertEqual(template["result_authority"], "provisional")
        self.assertIn("cases", template)
        self.assertEqual(main(["one-pass-check", "--input", str(self.plan_file), "--root", str(self.root)]), 0)


if __name__ == "__main__":
    unittest.main()
