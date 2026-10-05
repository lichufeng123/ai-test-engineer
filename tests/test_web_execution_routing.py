import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.cli import main
from ai_test_framework.web_execution_routing import check_web_execution_routing


def valid_plan():
    return {
        "schema_version": 1,
        "formal_executor": "playwright-test",
        "approved_baseline_required": True,
        "tools": [
            {
                "id": "playwright-test",
                "availability": "available",
                "exact_version": "1.63.0",
                "roles": ["formal_regression"],
            },
            {
                "id": "playwright-mcp",
                "availability": "planned",
                "exact_version": None,
                "roles": ["locator_generation", "locator_validation"],
            },
            {
                "id": "chrome-devtools-mcp",
                "availability": "planned",
                "exact_version": None,
                "roles": ["diagnosis", "network", "console", "performance"],
            },
            {
                "id": "ego-lite",
                "availability": "available",
                "exact_version": "1.2.3",
                "roles": ["discovery", "authenticated_exploration", "fallback"],
            },
            {
                "id": "jev-advisor",
                "availability": "available",
                "exact_version": "0.1.0",
                "roles": ["bounded_read_only_advisory"],
            },
            {
                "id": "stagehand",
                "availability": "planned",
                "exact_version": None,
                "roles": ["controlled_self_heal"],
            },
        ],
        "routes": {
            "new_feature_discovery": {
                "primary": "ego-lite",
                "advisor": "jev-advisor",
                "fallbacks": [],
            },
            "playwright_locator_assist": {
                "primary": "playwright-mcp",
                "fallbacks": ["ego-lite"],
            },
            "authenticated_or_visual_fallback": {
                "primary": "ego-lite",
                "fallbacks": [],
            },
            "failure_diagnosis": {
                "primary": "chrome-devtools-mcp",
                "fallbacks": ["ego-lite"],
            },
            "locator_repair": {
                "primary": "stagehand",
                "fallbacks": ["ego-lite", "playwright-mcp"],
                "requires_validation_by": "playwright-test",
            },
            "formal_regression": {
                "primary": "playwright-test",
                "fallbacks": [],
            },
        },
        "policies": {
            "formal_expectations_immutable": True,
            "playwright_mcp_required_for_script_generation": False,
            "credentials_runtime_only": True,
            "high_risk_write_requires_approval": True,
            "agentic_output_requires_playwright_validation": True,
            "jev": {
                "authority": "advisory_only",
                "action_space": "finite_local_candidates",
                "read_only_only": True,
                "may_execute_actions": False,
                "may_select_business_target": False,
                "may_change_expectations": False,
                "provider_failure": "stop_no_retry",
                "require_incomplete_terminal": True,
            },
            "stagehand": {
                "allowed_changes": ["locator", "wait_condition", "known_transient_dialog"],
                "forbidden_changes": [
                    "expected_result",
                    "business_rule",
                    "assertion_removal",
                    "blind_write_retry",
                ],
            },
        },
    }


class WebExecutionRoutingTest(unittest.TestCase):
    def test_selected_four_tool_stack_and_playwright_formal_executor_pass(self):
        result = check_web_execution_routing(valid_plan())
        self.assertEqual(result["status"], "passed_with_pending_tools")
        self.assertEqual(
            result["pending_tools"],
            ["playwright-mcp", "chrome-devtools-mcp", "stagehand"],
        )
        self.assertEqual(result["formal_executor"], "playwright-test")

    def test_ego_lite_is_default_discovery_and_playwright_mcp_is_optional_assistance(self):
        plan = valid_plan()
        result = check_web_execution_routing(plan)
        self.assertEqual(
            plan["routes"]["new_feature_discovery"]["primary"],
            "ego-lite",
        )
        self.assertEqual(
            plan["routes"]["playwright_locator_assist"]["primary"],
            "playwright-mcp",
        )
        self.assertEqual(result["status"], "passed_with_pending_tools")

        plan["policies"]["playwright_mcp_required_for_script_generation"] = True
        blocked = check_web_execution_routing(plan)
        self.assertEqual(blocked["status"], "failed")
        self.assertIn("PLAYWRIGHT_MCP_MUST_BE_OPTIONAL", blocked["error_codes"])

    def test_first_round_uses_jev_as_bounded_advisor_and_ego_lite_as_executor(self):
        plan = valid_plan()
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "passed_with_pending_tools")
        self.assertEqual(plan["routes"]["new_feature_discovery"]["primary"], "ego-lite")
        self.assertEqual(plan["routes"]["new_feature_discovery"]["advisor"], "jev-advisor")

        plan["routes"]["new_feature_discovery"].pop("advisor")
        plan["tools"] = [tool for tool in plan["tools"] if tool["id"] != "jev-advisor"]
        plan["policies"].pop("jev")
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "passed_with_pending_tools")
        self.assertNotIn("jev-advisor", result["pending_tools"])

    def test_declared_advisor_must_exist_and_stay_bounded(self):
        plan = valid_plan()
        plan["tools"] = [tool for tool in plan["tools"] if tool["id"] != "jev-advisor"]
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "failed")
        self.assertIn("ROUTE_REFERENCES_UNKNOWN_TOOL", result["error_codes"])

    def test_jev_must_remain_bounded_advisory_and_read_only(self):
        plan = valid_plan()
        plan["policies"]["jev"]["may_execute_actions"] = True
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "failed")
        self.assertIn("JEV_SAFETY_POLICY_VIOLATION", result["error_codes"])

    def test_formal_regression_cannot_fall_back_to_agentic_executor(self):
        plan = valid_plan()
        plan["routes"]["formal_regression"] = {
            "primary": "stagehand",
            "fallbacks": ["ego-lite"],
        }
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "failed")
        self.assertIn("FORMAL_EXECUTOR_MUST_BE_PLAYWRIGHT", result["error_codes"])
        self.assertIn("FORMAL_REGRESSION_AGENTIC_FALLBACK_FORBIDDEN", result["error_codes"])

    def test_stagehand_must_not_change_expectations_or_skip_playwright_validation(self):
        plan = valid_plan()
        plan["policies"]["stagehand"]["forbidden_changes"].remove("expected_result")
        plan["routes"]["locator_repair"]["requires_validation_by"] = "stagehand"
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "failed")
        self.assertIn("STAGEHAND_FORBIDDEN_CHANGES_INCOMPLETE", result["error_codes"])
        self.assertIn("REPAIR_REQUIRES_PLAYWRIGHT_VALIDATION", result["error_codes"])

    def test_security_and_high_risk_write_policies_are_mandatory(self):
        plan = valid_plan()
        plan["policies"]["credentials_runtime_only"] = False
        plan["policies"]["high_risk_write_requires_approval"] = False
        plan["password"] = "must-not-be-here"
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "failed")
        self.assertIn("CREDENTIALS_MUST_BE_RUNTIME_ONLY", result["error_codes"])
        self.assertIn("HIGH_RISK_APPROVAL_REQUIRED", result["error_codes"])
        self.assertIn("SENSITIVE_FIELD_FORBIDDEN", result["error_codes"])

    def test_available_tools_require_exact_non_latest_versions(self):
        plan = valid_plan()
        for tool in plan["tools"]:
            if tool["id"] == "ego-lite":
                tool["exact_version"] = "latest"
        result = check_web_execution_routing(plan)
        self.assertEqual(result["status"], "failed")
        self.assertIn("AVAILABLE_TOOL_VERSION_NOT_PINNED", result["error_codes"])

    def test_cli_writes_machine_readable_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "routing.json"
            output = root / "receipt.json"
            source.write_text(json.dumps(valid_plan()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([
                    "web-executor-check",
                    "--input", str(source),
                    "--output", str(output),
                ])
            self.assertEqual(code, 0)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "passed_with_pending_tools")
            self.assertEqual(receipt["formal_executor"], "playwright-test")

    def test_repository_contains_selected_adapter_contracts(self):
        for relative_path in (
            "adapters/playwright-mcp/README.md",
            "adapters/chrome-devtools-mcp/README.md",
            "adapters/ego-lite/README.md",
            "adapters/stagehand/README.md",
            "schemas/web-executor-routing.schema.json",
            "templates/web-executor-routing.example.json",
        ):
            self.assertTrue((ROOT / relative_path).exists(), relative_path)


if __name__ == "__main__":
    unittest.main()
