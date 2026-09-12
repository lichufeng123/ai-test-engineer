import json
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.business_flows import (  # noqa: E402
    check_business_flows,
    check_flow_case_coverage,
)
from ai_test_framework.cli import main  # noqa: E402


def valid_payload():
    return {
        "business_flow_contract_version": 1,
        "business_topology": {
            "classification": "linked_confirmed",
            "confirmed_module_ids": ["ORDER", "FULFILLMENT"],
            "confirmed_platforms": ["web", "app"],
            "candidate_links": [],
            "excluded_links": [],
            "basis": [{
                "type": "requirement",
                "reference": "REQ-ORDER-001",
                "status": "confirmed",
            }],
        },
        "assertions": [
            {"id": "A-ORDER-001"},
            {"id": "A-FULFILLMENT-001"},
        ],
        "business_flows": [{
            "id": "BF-ORDER-001",
            "name": "Order submission to fulfillment",
            "priority": "P0",
            "status": "confirmed",
            "trigger": "A customer submits an order",
            "actors": ["customer", "system"],
            "platforms": ["web", "app"],
            "preconditions": ["The cart contains an available item"],
            "start_state": "cart_ready",
            "end_state": "fulfillment_pending",
            "steps": [{
                "sequence": 1,
                "actor": "system",
                "event": "Create the order and enqueue fulfillment",
                "owner_module_id": "ORDER",
                "related_module_ids": ["FULFILLMENT"],
                "from_state": "cart_ready",
                "to_state": "fulfillment_pending",
                "observable_output": "The app displays the pending fulfillment",
                "covered_assertion_ids": ["A-ORDER-001", "A-FULFILLMENT-001"],
            }],
            "failure_branches": [],
            "source_refs": ["REQ-ORDER-001"],
        }],
    }


class BusinessFlowContractTest(unittest.TestCase):
    def test_linked_topology_requires_a_confirmed_flow(self):
        payload = valid_payload()
        payload["business_flows"] = []
        result = check_business_flows(payload)
        self.assertEqual(result["status"], "failed")
        self.assertIn("linked_confirmed_requires_confirmed_flow", result["error_codes"])

    def test_isolated_topology_still_requires_a_local_flow(self):
        payload = valid_payload()
        payload["business_topology"]["classification"] = "isolated"
        payload["business_flows"] = []
        result = check_business_flows(payload)
        self.assertIn("isolated_requires_local_flow", result["error_codes"])

    def test_flow_step_rejects_an_unknown_atomic_assertion(self):
        payload = valid_payload()
        payload["business_flows"][0]["steps"][0]["covered_assertion_ids"] = [
            "A-ORDER-999"
        ]
        result = check_business_flows(payload)
        self.assertIn("unknown_assertion_reference", result["error_codes"])

    def test_valid_flow_returns_a_deterministic_assertion_matrix(self):
        result = check_business_flows(valid_payload())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["flow_assertion_matrix"], [{
            "flow_id": "BF-ORDER-001",
            "status": "confirmed",
            "step_count": 1,
            "assertion_ids": ["A-FULFILLMENT-001", "A-ORDER-001"],
        }])

    def test_confirmed_flow_requires_a_complete_end_to_end_case(self):
        payload = valid_payload()
        cases = [{
            "id": "TC-ORDER-001",
            "covered_flow_ids": [],
            "covered_rule_ids": ["A-ORDER-001", "A-FULFILLMENT-001"],
        }]
        result = check_flow_case_coverage(payload["business_flows"], cases)
        self.assertEqual(result["status"], "failed")
        self.assertIn("confirmed_flow_without_case", result["error_codes"])

        cases[0]["covered_flow_ids"] = ["BF-ORDER-001"]
        result = check_flow_case_coverage(payload["business_flows"], cases)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["flows"][0]["case_ids"], ["TC-ORDER-001"])

    def test_case_cannot_claim_a_flow_without_all_step_assertions(self):
        payload = valid_payload()
        cases = [{
            "id": "TC-ORDER-001",
            "covered_flow_ids": ["BF-ORDER-001"],
            "covered_rule_ids": ["A-ORDER-001"],
        }]
        result = check_flow_case_coverage(payload["business_flows"], cases)
        self.assertIn("incomplete_flow_case", result["error_codes"])

    def test_repository_contains_chinese_readme_and_machine_schema(self):
        self.assertTrue((ROOT / "README.zh-CN.md").is_file())
        schema = json.loads(
            (ROOT / "schemas/business-flow.schema.json").read_text(encoding="utf-8")
        )
        self.assertIn("business_topology", schema["required"])
        self.assertIn("business_flows", schema["required"])

    def test_cli_writes_flow_coverage_matrix(self):
        flow_path = ROOT / "templates/business-flow.example.json"
        case_path = ROOT / "templates/test-case-baseline.business-flow.example.json"
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "flow-coverage.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    "flow-check",
                    "--input", str(flow_path),
                    "--cases", str(case_path),
                    "--matrix-output", str(matrix_path),
                ])
            self.assertEqual(exit_code, 0, stdout.getvalue())
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["status"], "passed")
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            self.assertEqual(matrix["flow_case_coverage"][0]["case_ids"], ["TC-ORDER-001"])


if __name__ == "__main__":
    unittest.main()
