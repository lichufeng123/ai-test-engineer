import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.cli import main  # noqa: E402
from ai_test_framework.execution_readiness import (  # noqa: E402
    build_readiness_plan,
    evaluate_execution_readiness,
    plan_sha256,
)
from ai_test_framework.project import STAGES  # noqa: E402


def readiness_source():
    return {
        "schema_version": 1,
        "plan_id": "ARP-BADGE-001",
        "requirement_baseline_id": "REQ-BADGE-001",
        "feature": "智能工牌后台管理",
        "automation_scope": {
            "platforms": ["web"],
            "environments": ["sit"],
            "business_flow_ids": ["BF-BADGE-001"],
            "case_ids": ["TC-001", "TC-002"],
        },
        "case_requirements": [
            {
                "case_id": "TC-001",
                "required_role_ids": ["store_admin"],
                "required_fixture_ids": [],
                "required_environment_ids": ["sit"],
            },
            {
                "case_id": "TC-002",
                "required_role_ids": ["store_admin"],
                "required_fixture_ids": ["unassigned_recording"],
                "required_environment_ids": ["sit"],
            },
        ],
        "account_requirements": [
            {"role_id": "store_admin", "purpose": "门店后台浏览", "status": "needed"}
        ],
        "fixture_requirements": [
            {
                "fixture_id": "unassigned_recording",
                "purpose": "验证关联顾客",
                "case_ids": ["TC-002"],
                "status": "needed",
            }
        ],
        "evidence_plan": {
            "screenshots": ["列表初始态", "关联结果"],
            "videos": ["核心浏览流程"],
        },
        "manual_only_case_ids": [],
        "open_questions": [],
    }


def confirmation(plan, **overrides):
    value = {
        "schema_version": 1,
        "plan_id": plan["plan_id"],
        "plan_sha256": plan_sha256(plan),
        "target_environment": "sit",
        "scope_confirmed": True,
        "environment_confirmed": True,
        "account_roles_confirmed": True,
        "data_plan_confirmed": True,
        "available_role_ids": ["store_admin"],
        "ready_fixture_ids": [],
        "excluded_case_ids": [],
        "confirmed_at": "2026-09-14T10:00:00+08:00",
    }
    value.update(overrides)
    return value


class ExecutionReadinessTest(unittest.TestCase):
    def test_requirement_stage_plan_preserves_scope_accounts_data_and_evidence(self):
        plan = build_readiness_plan(readiness_source())
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["automation_scope"]["case_ids"], ["TC-001", "TC-002"])
        self.assertEqual(plan["account_requirements"][0]["role_id"], "store_admin")
        self.assertEqual(plan["fixture_requirements"][0]["fixture_id"], "unassigned_recording")
        self.assertEqual(plan["evidence_plan"]["videos"], ["核心浏览流程"])
        self.assertRegex(plan["plan_sha256"], r"^[0-9a-f]{64}$")

    def test_pre_execution_confirmation_continues_ready_cases_and_blocks_only_missing_data(self):
        plan = build_readiness_plan(readiness_source())
        result = evaluate_execution_readiness(plan, confirmation(plan))
        self.assertEqual(result["status"], "passed_with_case_blocks")
        self.assertEqual(result["ready_case_ids"], ["TC-001"])
        self.assertEqual(result["blocked_cases"][0]["case_id"], "TC-002")
        self.assertEqual(result["blocked_cases"][0]["missing_fixture_ids"], ["unassigned_recording"])
        self.assertEqual(result["blocked_cases"][0]["execution_action"], "skip_without_retry")
        self.assertFalse(result["missing_prerequisites"][0]["retry_allowed"])

    def test_same_missing_prerequisite_is_not_retried_or_duplicated(self):
        plan = build_readiness_plan(readiness_source())
        first = evaluate_execution_readiness(plan, confirmation(plan))
        second = evaluate_execution_readiness(
            plan,
            confirmation(plan),
            previous_missing=first["missing_prerequisites"],
        )
        self.assertEqual(second["missing_prerequisites"], first["missing_prerequisites"])
        self.assertEqual(second["blocked_cases"][0]["execution_action"], "skip_without_retry")

    def test_plan_hash_or_unconfirmed_scope_blocks_all_execution(self):
        plan = build_readiness_plan(readiness_source())
        result = evaluate_execution_readiness(
            plan,
            confirmation(plan, plan_sha256="0" * 64, scope_confirmed=False),
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["ready_case_ids"], [])
        self.assertIn("plan_hash_mismatch", result["error_codes"])
        self.assertIn("scope_not_confirmed", result["error_codes"])

    def test_credentials_are_rejected_from_readiness_artifacts(self):
        source = readiness_source()
        source["account_requirements"][0]["password"] = "secret"
        with self.assertRaisesRegex(ValueError, "sensitive_field"):
            build_readiness_plan(source)

    def test_cli_writes_plan_and_confirmation_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            plan_path = root / "plan.json"
            confirmation_path = root / "confirmation.json"
            receipt_path = root / "receipt.json"
            source_path.write_text(json.dumps(readiness_source(), ensure_ascii=False), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([
                    "readiness-plan", "--input", str(source_path), "--output", str(plan_path)
                ])
            self.assertEqual(code, 0, stdout.getvalue())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            confirmation_path.write_text(
                json.dumps(confirmation(plan), ensure_ascii=False), encoding="utf-8"
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([
                    "readiness-check",
                    "--plan", str(plan_path),
                    "--confirmation", str(confirmation_path),
                    "--output", str(receipt_path),
                ])
            self.assertEqual(code, 0, stdout.getvalue())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "passed_with_case_blocks")

    def test_workflow_places_planning_after_requirement_and_confirmation_before_gate(self):
        self.assertLess(
            STAGES.index("REQUIREMENT_FREEZE"),
            STAGES.index("AUTOMATION_READINESS_PLANNING"),
        )
        self.assertLess(
            STAGES.index("PRE_EXECUTION_CONFIRMATION"),
            STAGES.index("EXECUTION_GATE"),
        )

    def test_blocked_cli_gate_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = build_readiness_plan(readiness_source())
            plan_path = root / "plan.json"
            confirmation_path = root / "confirmation.json"
            receipt_path = root / "receipt.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            confirmation_path.write_text(
                json.dumps(confirmation(plan, scope_confirmed=False), ensure_ascii=False),
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([
                    "readiness-check",
                    "--plan", str(plan_path),
                    "--confirmation", str(confirmation_path),
                    "--output", str(receipt_path),
                ])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
