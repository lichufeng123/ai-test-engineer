"""Two unrelated fictional read-only adapters; receipts are fabricated unit inputs."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

import test_execution_contract as fixture_factory
from ai_test_framework.adapter_trace import PHASES, check_adapter_trace
from ai_test_framework.cli import main
from ai_test_framework.execution_contract import digest
from ai_test_framework.execution_readiness import evaluate_execution_readiness, plan_sha256
from ai_test_framework.synthetic_adapter_runner import run_synthetic_readonly_adapter


class AdapterTraceTests(unittest.TestCase):
    def setUp(self):
        fixture_factory.ExecutionContractTests.setUp(self)

    def _trace(self, domain):
        assert domain in {"catalog", "tasks"}
        case_id = "TC-CATALOG-READ" if domain == "catalog" else "TC-TASKS-READ"
        assertion_id = "A-CATALOG-COUNT" if domain == "catalog" else "A-TASKS-OPEN"
        fixture_id = "FX-CATALOG" if domain == "catalog" else "FX-TASKS"
        key = "catalog-fixture-unique" if domain == "catalog" else "task-fixture-unique"
        oracle_expected = 3 if domain == "catalog" else 2
        plan = copy.deepcopy(self.plan)
        plan["automation_scope"]["case_ids"] = [case_id]
        plan["case_requirements"][0]["case_id"] = case_id
        plan["case_requirements"][0]["required_fixture_ids"] = [fixture_id]
        plan["plan_sha256"] = plan_sha256(plan)
        plan_ref = fixture_factory.artifact(self.root, self.plan_ref["path"], plan)
        ready = evaluate_execution_readiness(plan, {
            "schema_version": 1, "plan_id": plan["plan_id"], "plan_sha256": plan["plan_sha256"],
            "target_environment": "local", "scope_confirmed": True, "environment_confirmed": True,
            "account_roles_confirmed": True, "data_plan_confirmed": True,
            "available_role_ids": ["ROLE-EXAMPLE"], "ready_fixture_ids": [fixture_id], "excluded_case_ids": []})
        self.assertEqual(ready["status"], "passed")
        ready_ref = fixture_factory.artifact(self.root, self.ready_ref["path"], ready)
        charter_ref = fixture_factory.artifact(self.root, "runs/RUN-EXAMPLE/charter.json", {"scope": "fictional read"})
        oracle = fixture_factory.artifact(self.root, f"oracles/{domain}.json", {"expected": oracle_expected})
        evidence = fixture_factory.artifact(self.root, f"runs/RUN-EXAMPLE/{domain}-observation.json", {"observed": oracle_expected})
        adapter_path = self.root / f"adapters/{domain}.py"
        adapter_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__).resolve().parents[1] / "examples/synthetic_adapter_projects" / domain / "adapter.py", adapter_path)
        source = {"path": adapter_path.relative_to(self.root).as_posix(),
                  "sha256": hashlib.sha256(adapter_path.read_bytes()).hexdigest()}
        probe = copy.deepcopy(self.probe)
        probe.update({"case_id": case_id, "mode": "rapid",
                      "baseline": {**charter_ref, "id": "BL-EXAMPLE", "status": "provisional"},
                      "plan": plan_ref, "plan_sha256": plan["plan_sha256"], "readiness_receipt": ready_ref,
                      "oracle": oracle, "assertion_ids": [assertion_id],
                      "fixture": {"id": fixture_id, "business_key": key,
                                  "pre_state_sha256": hashlib.sha256(key.encode()).hexdigest(), "match_count": 1},
                      "action": {"id": "READ-" + domain.upper(), "kind": "read", "input_sha256": "a" * 64}})
        payloads = [copy.deepcopy(probe["fixture"]),
                    {**probe["action"], "profile_sha256": probe["profile_sha256"]},
                    {"action_id": probe["action"]["id"], "attempt_count": 1, "result": "observed"},
                    {"fixture_id": fixture_id, "business_key": key, "match_count": 1,
                     "state_sha256": hashlib.sha256((domain + "-readback").encode()).hexdigest()},
                    {"assertions": [{"id": assertion_id, "status": "passed", "oracle": oracle, "evidence": [evidence]}]},
                    {"evidence": [evidence], "review_status": "pending"}]
        trace = {"schema_version": 1, "probe": probe,
                 "adapter": {"id": "adapter-" + domain, "platform": "api" if domain == "catalog" else "web",
                             "source": source}, "steps": []}
        previous = digest({"run_id": probe["run_id"], "case_id": case_id,
                           "probe_sha256": digest(probe), "adapter_sha256": source["sha256"]})
        for phase, payload in zip(PHASES, payloads):
            step = {"phase": phase, "run_id": probe["run_id"], "case_id": case_id,
                    "fixture_id": fixture_id, "probe_sha256": digest(probe),
                    "adapter_sha256": source["sha256"], "previous_sha256": previous, "payload": payload}
            trace["steps"].append(step)
            previous = digest(step)
        return trace

    def test_two_unrelated_domains_share_contract_without_preset_case_ids(self):
        for domain in ("catalog", "tasks"):
            with self.subTest(domain=domain):
                result = check_adapter_trace(self._trace(domain), self.root)
                self.assertEqual(result["status"], "review_required", result)
                self.assertEqual(result["product_verdict"], "not_evaluated")
                self.assertFalse(result["source_attested"])

    def test_wrong_fixture_and_skipped_phase_block(self):
        trace = self._trace("catalog")
        trace["steps"][0]["payload"]["business_key"] = "another-key"
        self.assertIn("observed_fixture_not_unique_or_drifted", check_adapter_trace(trace, self.root)["error_codes"])
        trace = self._trace("catalog")
        trace["steps"].pop(1)
        self.assertIn("phase_count_or_order_invalid", check_adapter_trace(trace, self.root)["error_codes"])

    def test_cross_run_evidence_and_changed_oracle_block(self):
        trace = self._trace("tasks")
        evidence = fixture_factory.artifact(self.root, "runs/RUN-OTHER/stolen.json", {"observed": 2})
        trace["steps"][4]["payload"]["assertions"][0]["evidence"] = [evidence]
        trace["steps"][5]["payload"]["evidence"] = [evidence]
        self.assertIn("evidence_not_independent_or_run_bound", check_adapter_trace(trace, self.root)["error_codes"])
        trace = self._trace("tasks")
        trace["steps"][4]["payload"]["assertions"][0]["oracle"] = evidence
        self.assertIn("assertion_oracle_not_frozen", check_adapter_trace(trace, self.root)["error_codes"])

    def test_write_action_and_duplicate_assertion_block(self):
        trace = self._trace("catalog")
        trace["probe"]["action"]["kind"] = "write"
        self.assertIn("write_adapter_not_available", check_adapter_trace(trace, self.root)["error_codes"])
        trace = self._trace("catalog")
        trace["steps"][4]["payload"]["assertions"].append(copy.deepcopy(trace["steps"][4]["payload"]["assertions"][0]))
        self.assertIn("assertion_set_mismatch", check_adapter_trace(trace, self.root)["error_codes"])

    def test_malformed_ids_and_source_drift_fail_closed(self):
        trace = self._trace("catalog")
        trace["probe"]["assertion_ids"] = None
        self.assertEqual(check_adapter_trace(trace, self.root)["status"], "blocked")
        trace = self._trace("catalog")
        trace["steps"][4]["payload"]["assertions"][0]["id"] = []
        self.assertIn("assertion_set_mismatch", check_adapter_trace(trace, self.root)["error_codes"])
        trace = self._trace("catalog")
        trace["adapter"]["source"]["sha256"] = "0" * 64
        self.assertIn("adapter_source_hash_mismatch", check_adapter_trace(trace, self.root)["error_codes"])

    def _run_actual_synthetic_adapter(self, domain):
        trace = self._trace(domain)
        probe = trace["probe"]
        state_path = self.root / "state.json"
        if domain == "catalog":
            state = {"fixtures": [{"id": probe["fixture"]["id"], "business_key": probe["fixture"]["business_key"]}],
                     "items": ["alpha", "beta", "gamma"]}
            class_name = "CatalogAdapter"
        else:
            state = {"boards": [{"id": probe["fixture"]["id"], "business_key": probe["fixture"]["business_key"]}],
                     "tasks": [{"status": "open"}, {"status": "done"}, {"status": "open"}]}
            class_name = "TaskBoardAdapter"
        state_path.write_text(json.dumps(state))
        source_path = self.root / trace["adapter"]["source"]["path"]
        spec = importlib.util.spec_from_file_location("synthetic_" + domain + "_" + str(id(self)), source_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        adapter = getattr(module, class_name)(trace["adapter"]["source"], state_path)
        return probe, adapter, state_path

    def test_catalog_actual_sdk_run(self):
        probe, adapter, _ = self._run_actual_synthetic_adapter("catalog")
        result = run_synthetic_readonly_adapter(probe, adapter, self.root)
        self.assertEqual(result["status"], "review_required", result)
        saved = json.loads((self.root / result["trace_path"]).read_text())
        self.assertEqual(check_adapter_trace(saved, self.root)["status"], "review_required")
        self.assertEqual(run_synthetic_readonly_adapter(probe, adapter, self.root)["status"], "blocked")

    def test_taskboard_actual_sdk_run(self):
        probe, adapter, _ = self._run_actual_synthetic_adapter("tasks")
        result = run_synthetic_readonly_adapter(probe, adapter, self.root)
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(json.loads((self.root / "runs/RUN-EXAMPLE/adapter-read-result.json").read_text()), {"open_tasks": 2})

    def test_duplicate_target_prevents_callback_read(self):
        probe, adapter, state_path = self._run_actual_synthetic_adapter("catalog")
        state = json.loads(state_path.read_text())
        state["fixtures"].append(state["fixtures"][0])
        state_path.write_text(json.dumps(state))
        result = run_synthetic_readonly_adapter(probe, adapter, self.root)
        self.assertIn("observed_fixture_not_unique_or_drifted", result["error_codes"])
        self.assertFalse((self.root / "runs/RUN-EXAMPLE/adapter-read-result.json").exists())

    def test_all_unexecuted_cannot_look_ready_for_review(self):
        trace = self._trace("tasks")
        trace["steps"][4]["payload"]["assertions"] = [{"id": "A-TASKS-OPEN", "status": "not_executed", "reason": "fixture unavailable"}]
        trace["steps"][5]["payload"]["evidence"] = []
        result = check_adapter_trace(trace, self.root)
        self.assertIn("no_executed_assertions", result["error_codes"])
        self.assertEqual(result["status"], "blocked")

    def test_cli_is_nonzero_for_local_consistency_only(self):
        trace = self._trace("catalog")
        path = self.root / "runs/RUN-EXAMPLE/trace.json"
        path.write_text(json.dumps(trace))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = main(["adapter-trace-check", "--input", str(path), "--root", str(self.root)])
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "review_required")


if __name__ == "__main__":
    unittest.main()
