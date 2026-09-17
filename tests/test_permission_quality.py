import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai_test_framework.cli import main
from ai_test_framework.permission_quality import check_permission_coverage


def fixture(edit=True):
    context = {
        "id": "PC-ROLE-STORE", "role": "ordinary_chain", "surface": "store_web",
        "grant_layer": "role", "source_ref": "A-DEMO-001",
        "activation": "relogin", "supports_edit": edit,
        "edit_only_policy": "reject_configuration", "upstream_gate": True,
        "scope_required": True, "surface_switch_required": True, "filters_required": True,
    }
    scenarios = {
        "granted": ["menu", "page", "navigation", "read_api"],
        "denied": ["menu", "page", "navigation", "read_api"],
        "revoked": ["page", "navigation", "read_api"],
        "upstream_disabled": ["page", "read_api"],
        "scope_granted": ["scope", "read_api"],
        "scope_denied": ["scope", "read_api"],
        "scope_denied_no_permission": ["scope", "read_api"],
        "switch_context": ["menu", "page", "scope"],
        "filter_preservation": ["menu", "page"],
    }
    if edit:
        scenarios.update({
            "browse_only": ["edit_control", "write_api_no_change"],
            "edit_only": ["dependency_contract"],
            "browse_edit": ["edit_control", "save_readback"],
            "revoke_edit": ["edit_control", "write_api_no_change"],
            "stale_form": ["write_api_no_change"],
            "revoke_browse": ["dependency_contract"],
            "filter_readonly": ["edit_control", "write_api_no_change"],
        })
        for scenario in ["denied", "revoked", "upstream_disabled", "scope_denied", "scope_denied_no_permission"]:
            scenarios[scenario].append("write_api_no_change")
        scenarios["filter_preservation"].append("edit_control")
    cases = [{
        "id": f"TC-DEMO-{index:03d}", "steps": ["保存权限后退出并重新登录", "执行目标功能验证"],
        "permission_test": {"context_id": context["id"], "scenario": scenario,
                            "activation_performed": "relogin", "checks": checks},
    } for index, (scenario, checks) in enumerate(scenarios.items(), 1)]
    return {"contexts": [context]}, cases


class PermissionCoverageTest(unittest.TestCase):
    def test_complete_edit_matrix_passes(self):
        matrix, cases = fixture()
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "passed")

    def test_browse_only_feature_does_not_require_edit_scenarios(self):
        matrix, cases = fixture(False)
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "passed")

    def test_missing_browse_edit_combination_fails(self):
        matrix, cases = fixture()
        cases = [case for case in cases if case["permission_test"]["scenario"] != "edit_only"]
        result = check_permission_coverage(matrix, cases)
        self.assertEqual(result["status"], "failed")
        self.assertIn("edit_only", str(result["gaps"]))

    def test_ui_hiding_cannot_replace_server_denial(self):
        matrix, cases = fixture()
        for case in cases:
            if case["permission_test"]["scenario"] == "browse_only":
                case["permission_test"]["checks"] = ["edit_control"]
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "failed")

    def test_relogin_metadata_alone_is_not_enough(self):
        matrix, cases = fixture()
        cases[0]["steps"] = ["刷新页面", "执行验证"]
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "failed")

    def test_unknown_dependency_policy_blocks_formal_acceptance(self):
        matrix, cases = fixture()
        matrix["contexts"][0]["edit_only_policy"] = "pending"
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "blocked")

    def test_invalid_context_and_duplicate_case_ids_fail(self):
        matrix, cases = fixture()
        cases.append(copy.deepcopy(cases[0]))
        cases[0]["permission_test"]["context_id"] = "unknown"
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "failed")

    def test_empty_matrix_does_not_claim_coverage(self):
        self.assertEqual(check_permission_coverage({"contexts": []}, [])["status"], "failed")

    def test_independent_operations_require_positive_and_negative_cases(self):
        matrix, cases = fixture()
        matrix["contexts"][0]["independent_operations"] = ["add"]
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "failed")
        for scenario, checks in [("operation_add_granted", ["edit_control", "save_readback"]),
                                 ("operation_add_denied", ["edit_control", "write_api_no_change"])]:
            case = copy.deepcopy(cases[0])
            case["id"] = scenario
            case["permission_test"].update(scenario=scenario, checks=checks)
            cases.append(case)
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "passed")

    def test_invalid_operation_definition_fails(self):
        matrix, cases = fixture()
        matrix["contexts"][0]["independent_operations"] = [{}]
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "failed")

    def test_unhashable_input_reports_errors_instead_of_crashing(self):
        matrix, cases = fixture()
        matrix["contexts"][0]["activation"] = []
        matrix["contexts"][0]["edit_only_policy"] = {}
        cases[0]["permission_test"]["scenario"] = []
        self.assertEqual(check_permission_coverage(matrix, cases)["status"], "failed")

    def test_cli_writes_receipt_and_returns_nonzero_for_blocked(self):
        matrix, cases = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix_path, cases_path, output = root / "matrix.json", root / "cases.json", root / "receipt.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            cases_path.write_text(json.dumps(cases), encoding="utf-8")
            arguments = ["permission-check", "--matrix", str(matrix_path), "--cases", str(cases_path), "--output", str(output)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(arguments), 0)
                self.assertEqual(json.loads(output.read_text())["status"], "passed")
                matrix["contexts"][0]["edit_only_policy"] = "pending"
                matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
                self.assertEqual(main(arguments), 1)
                self.assertEqual(json.loads(output.read_text())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
