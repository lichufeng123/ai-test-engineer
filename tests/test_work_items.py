import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.cli import main
from ai_test_framework.project import initialize_project
from ai_test_framework.work_item_artifacts import (
    reconcile_work_item,
    register_work_item_artifact,
)
from ai_test_framework.work_items import create_work_item, show_work_item, update_work_item


class WorkItemTest(unittest.TestCase):
    def test_project_init_creates_empty_work_item_index_instead_of_shared_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_project(
                root,
                name="演示项目",
                system_id="demo",
                environments=["sit", "pre"],
                platforms=["web"],
            )

            index = json.loads(
                (root / ".ai-test/work-items/index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["items"], [])
            self.assertFalse((root / ".ai-test/workflow_state.json").exists())
            self.assertIn("暂无测试需求", (root / "TEST_WORK_ITEMS.md").read_text(encoding="utf-8"))

    def test_create_work_item_writes_complete_isolated_context_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = create_work_item(
                root,
                requirement_id="REQ-SBA-012",
                title="智能工牌权限回归",
                feature="智能工牌后台管理",
                environments=["sit", "zone99"],
                platforms=["web"],
                scope="后台权限矩阵与数据范围",
            )

            item_root = root / ".ai-test/work-items/REQ-SBA-012"
            self.assertEqual(result["status"], "created")
            for name in (
                "manifest.json",
                "workflow-state.json",
                "handoff.json",
                "decisions.md",
                "asset-links.json",
                "artifacts.json",
            ):
                self.assertTrue((item_root / name).exists(), name)
            state = json.loads((item_root / "workflow-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "INTAKE")
            self.assertEqual(state["requirement_id"], "REQ-SBA-012")
            overview = (root / "TEST_WORK_ITEMS.md").read_text(encoding="utf-8")
            self.assertIn("REQ-SBA-012", overview)
            self.assertIn("智能工牌权限回归", overview)

    def test_work_item_updates_are_isolated_and_refresh_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for requirement_id in ("REQ-A", "REQ-B"):
                create_work_item(
                    root,
                    requirement_id=requirement_id,
                    title=requirement_id,
                    feature="功能",
                    environments=["sit"],
                    platforms=["web"],
                    scope="范围",
                )

            update_work_item(
                root,
                requirement_id="REQ-A",
                stage="ASSERTION_DESIGN",
                status="active",
                summary="规则正在生成与校验",
                completed=["需求审核"],
                blockers=["等待门店账号"],
                next_steps=["补齐账号后执行权限用例"],
                owner="conversation-a",
            )

            state_a = json.loads(
                (root / ".ai-test/work-items/REQ-A/workflow-state.json").read_text(encoding="utf-8")
            )
            state_b = json.loads(
                (root / ".ai-test/work-items/REQ-B/workflow-state.json").read_text(encoding="utf-8")
            )
            handoff = json.loads(
                (root / ".ai-test/work-items/REQ-A/handoff.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state_a["stage"], "ASSERTION_DESIGN")
            self.assertEqual(state_b["stage"], "INTAKE")
            self.assertEqual(handoff["summary"], "规则正在生成与校验")
            self.assertEqual(handoff["next_steps"], ["补齐账号后执行权限用例"])
            self.assertEqual(handoff["owner"], "conversation-a")

    def test_update_can_expand_platform_environment_and_scope_without_recreating_item(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-MOBILE-EXPAND",
                title="设备App联动",
                feature="设备App",
                environments=["sit"],
                platforms=["web"],
                scope="Web后台",
            )

            result = update_work_item(
                root,
                requirement_id="REQ-MOBILE-EXPAND",
                add_environments=["sit", "pre"],
                add_platforms=["app", "web"],
                scope="Web、App、服务端与实体设备联动",
            )

            manifest = json.loads(
                (root / ".ai-test/work-items/REQ-MOBILE-EXPAND/manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            handoff = json.loads(
                (root / ".ai-test/work-items/REQ-MOBILE-EXPAND/handoff.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["platforms"], ["web", "app"])
            self.assertEqual(manifest["environments"], ["sit", "pre"])
            self.assertEqual(manifest["scope"], "Web、App、服务端与实体设备联动")
            self.assertEqual(handoff["platforms"], ["web", "app"])
            self.assertEqual(handoff["scope"], "Web、App、服务端与实体设备联动")

    def test_registering_review_page_creates_registry_and_advances_to_review_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-AUTO-TAG",
                title="智能耳机自动标签",
                feature="智能耳机自动标签",
                environments=["sit"],
                platforms=["web"],
                scope="自动标签",
            )
            review_page = root / "outputs/business_assertions_review.html"
            review_page.parent.mkdir(parents=True)
            review_page.write_text("<html>智能耳机自动标签</html>", encoding="utf-8")

            registered = register_work_item_artifact(
                root,
                requirement_id="REQ-AUTO-TAG",
                artifact_id="ART-AUTO-TAG-RULE-REVIEW",
                artifact_type="business_assertion_review_page",
                path=str(review_page.relative_to(root)),
                status="review_pending",
                stage="BUSINESS_ASSERTION_REVIEW",
                baseline_id="BL-AUTO-TAG-001",
            )

            registry = json.loads(
                (root / ".ai-test/work-items/REQ-AUTO-TAG/artifacts.json").read_text(
                    encoding="utf-8"
                )
            )
            shown = show_work_item(root, "REQ-AUTO-TAG")
            self.assertEqual(registered["artifact"]["sha256"], registry["artifacts"][0]["sha256"])
            self.assertEqual(shown["current_stage"], "BUSINESS_ASSERTION_REVIEW")
            self.assertEqual(shown["artifact_summary"]["review_pending"], 1)
            self.assertIn(
                ".ai-test/work-items/REQ-AUTO-TAG/artifacts.json",
                shown["read_first"],
            )

    def test_reconcile_detects_and_repairs_state_behind_registered_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-RECONCILE",
                title="规则对账",
                feature="规则对账",
                environments=["sit"],
                platforms=["web"],
                scope="规则",
            )
            artifact = root / "rules.html"
            artifact.write_text("规则审核页", encoding="utf-8")
            register_work_item_artifact(
                root,
                requirement_id="REQ-RECONCILE",
                artifact_id="ART-RULE-PAGE",
                artifact_type="business_assertion_review_page",
                path="rules.html",
                status="review_pending",
                stage="BUSINESS_ASSERTION_REVIEW",
            )
            state_path = root / ".ai-test/work-items/REQ-RECONCILE/workflow-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stage"] = "REQUIREMENT_FREEZE"
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            receipt = reconcile_work_item(root, "REQ-RECONCILE")
            self.assertEqual(receipt["consistency_status"], "inconsistent")
            self.assertIn("STATE_BEHIND_ARTIFACTS", [item["code"] for item in receipt["issues"]])

            repaired = reconcile_work_item(root, "REQ-RECONCILE", apply=True)
            self.assertEqual(repaired["applied_stage"], "BUSINESS_ASSERTION_REVIEW")
            shown = show_work_item(root, "REQ-RECONCILE")
            self.assertEqual(shown["current_stage"], "BUSINESS_ASSERTION_REVIEW")
            self.assertEqual(shown["reconciliation"]["consistency_status"], "consistent")
            self.assertEqual(shown["reconciliation"]["case_design_gate"]["status"], "blocked")

    def test_reconcile_detects_missing_changed_and_unregistered_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-ARTIFACT-CHECK",
                title="产物检查",
                feature="产物检查",
                environments=["sit"],
                platforms=["web"],
                scope="规则",
            )
            tracked = root / "tracked.json"
            tracked.write_text('{"title":"产物检查"}', encoding="utf-8")
            register_work_item_artifact(
                root,
                requirement_id="REQ-ARTIFACT-CHECK",
                artifact_id="ART-TRACKED",
                artifact_type="business_topology",
                path="tracked.json",
                status="validated",
                stage="BUSINESS_TOPOLOGY_ANALYSIS",
            )
            tracked.write_text('{"title":"已被修改"}', encoding="utf-8")
            orphan_root = root / "legacy"
            orphan_root.mkdir()
            (orphan_root / "assertions.json").write_text(
                '{"title":"产物检查｜业务流程规则与原子断言"}', encoding="utf-8"
            )

            receipt = reconcile_work_item(
                root,
                "REQ-ARTIFACT-CHECK",
                discover_roots=[orphan_root],
            )
            codes = [item["code"] for item in receipt["issues"]]
            self.assertIn("ARTIFACT_HASH_MISMATCH", codes)
            self.assertIn("UNREGISTERED_ARTIFACT", codes)

            tracked.unlink()
            missing = reconcile_work_item(root, "REQ-ARTIFACT-CHECK")
            self.assertIn("ARTIFACT_MISSING", [item["code"] for item in missing["issues"]])

    def test_case_design_gate_requires_readiness_and_rule_review_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-CASE-GATE",
                title="用例门禁",
                feature="用例门禁",
                environments=["sit"],
                platforms=["web"],
                scope="正式用例",
            )
            with self.assertRaisesRegex(ValueError, "CASE_DESIGN门禁未通过"):
                update_work_item(root, requirement_id="REQ-CASE-GATE", stage="CASE_DESIGN")

            blocked = reconcile_work_item(root, "REQ-CASE-GATE")
            self.assertEqual(blocked["case_design_gate"]["status"], "blocked")
            self.assertNotIn("CASE_DESIGN_GATE_BYPASSED", [item["code"] for item in blocked["issues"]])

            readiness = root / "automation_readiness_plan.json"
            readiness.write_text('{"plan_sha256":"placeholder"}', encoding="utf-8")
            review_receipt = root / "rule_review_receipt.json"
            review_receipt.write_text('{"gate_status":"passed"}', encoding="utf-8")
            sync_disposition = root / "rule_current_sync_disposition.json"
            sync_disposition.write_text(
                '{"status":"not_applicable","reason":"标准生成不写外部Current"}',
                encoding="utf-8",
            )
            register_work_item_artifact(
                root,
                requirement_id="REQ-CASE-GATE",
                artifact_id="ART-READINESS",
                artifact_type="automation_readiness_plan",
                path="automation_readiness_plan.json",
                status="validated",
                stage="AUTOMATION_READINESS_PLANNING",
            )
            register_work_item_artifact(
                root,
                requirement_id="REQ-CASE-GATE",
                artifact_id="ART-RULE-REVIEW",
                artifact_type="rule_review_receipt",
                path="rule_review_receipt.json",
                status="review_validated",
                stage="RULE_CURRENT_SYNC",
            )
            register_work_item_artifact(
                root,
                requirement_id="REQ-CASE-GATE",
                artifact_id="ART-RULE-CURRENT-DISPOSITION",
                artifact_type="rule_current_sync_disposition",
                path="rule_current_sync_disposition.json",
                status="not_applicable",
                stage="RULE_CURRENT_SYNC",
            )

            updated = update_work_item(root, requirement_id="REQ-CASE-GATE", stage="CASE_DESIGN")
            self.assertEqual(updated["current_stage"], "CASE_DESIGN")
            passed = reconcile_work_item(root, "REQ-CASE-GATE")
            self.assertEqual(passed["case_design_gate"]["status"], "passed")
            self.assertNotIn("CASE_DESIGN_GATE_BYPASSED", [item["code"] for item in passed["issues"]])

    def test_show_returns_a_short_takeover_instruction_so_users_need_not_memorize_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-LOGIN-001",
                title="登录改造",
                feature="登录",
                environments=["sit"],
                platforms=["web", "h5"],
                scope="登录与跨端回读",
            )

            result = show_work_item(root, "REQ-LOGIN-001")

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["current_stage"], "INTAKE")
            self.assertTrue(any(path.endswith("/manifest.json") for path in result["read_first"]))
            self.assertTrue(any(path.endswith("/handoff.json") for path in result["read_first"]))
            self.assertIn("REQ-LOGIN-001", result["takeover_prompt"])
            self.assertLess(len(result["takeover_prompt"]), 120)

    def test_recreating_same_item_is_idempotent_but_conflicting_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = dict(
                requirement_id="REQ-IDEMPOTENT",
                title="稳定任务",
                feature="功能",
                environments=["sit"],
                platforms=["web"],
                scope="范围",
            )
            create_work_item(root, **kwargs)
            repeated = create_work_item(root, **kwargs)
            self.assertEqual(repeated["status"], "exists")
            with self.assertRaisesRegex(ValueError, "已存在"):
                create_work_item(root, **{**kwargs, "title": "冲突标题"})

    def test_cli_artifact_register_and_reconcile_expose_review_pending_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_work_item(
                root,
                requirement_id="REQ-CLI-ARTIFACT",
                title="CLI产物",
                feature="CLI产物",
                environments=["sit"],
                platforms=["web"],
                scope="业务规则",
            )
            page = root / "business_assertions_review.html"
            page.write_text("<html>CLI产物</html>", encoding="utf-8")

            with redirect_stdout(StringIO()):
                code = main([
                    "work-item-artifact-register", "--root", directory,
                    "--requirement-id", "REQ-CLI-ARTIFACT",
                    "--artifact-id", "ART-CLI-RULE-PAGE",
                    "--artifact-type", "business_assertion_review_page",
                    "--path", "business_assertions_review.html",
                    "--status", "review_pending",
                    "--stage", "BUSINESS_ASSERTION_REVIEW",
                ])
            self.assertEqual(code, 0)

            reconcile_out = StringIO()
            with redirect_stdout(reconcile_out):
                code = main([
                    "work-item-reconcile", "--root", directory,
                    "--requirement-id", "REQ-CLI-ARTIFACT",
                ])
            self.assertEqual(code, 0)
            receipt = json.loads(reconcile_out.getvalue())
            self.assertEqual(receipt["consistency_status"], "consistent")
            self.assertEqual(receipt["artifact_derived_stage"], "BUSINESS_ASSERTION_REVIEW")
            self.assertEqual(receipt["case_design_gate"]["status"], "blocked")

    def test_cli_create_update_and_show_support_new_conversation_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            create_out = StringIO()
            with redirect_stdout(create_out):
                code = main([
                    "work-item-create", "--root", directory,
                    "--requirement-id", "REQ-CLI-001",
                    "--title", "CLI需求", "--feature", "CLI功能",
                    "--environment", "sit", "--platform", "web",
                    "--scope", "核心范围",
                ])
            self.assertEqual(code, 0)

            with redirect_stdout(StringIO()):
                code = main([
                    "work-item-update", "--root", directory,
                    "--requirement-id", "REQ-CLI-001",
                    "--stage", "FEATURE_DISCOVERY", "--status", "active",
                    "--summary", "入口已确认", "--completed", "系统入口校验",
                    "--next-step", "继续功能探索",
                    "--add-environment", "pre", "--add-platform", "app",
                    "--scope", "Web与App增量探索",
                ])
            self.assertEqual(code, 0)

            show_out = StringIO()
            with redirect_stdout(show_out):
                code = main([
                    "work-item-show", "--root", directory,
                    "--requirement-id", "REQ-CLI-001",
                ])
            self.assertEqual(code, 0)
            shown = json.loads(show_out.getvalue())
            self.assertEqual(shown["current_stage"], "FEATURE_DISCOVERY")
            self.assertEqual(shown["next_steps"], ["继续功能探索"])
            self.assertEqual(shown["environments"], ["sit", "pre"])
            self.assertEqual(shown["platforms"], ["web", "app"])
            self.assertEqual(shown["scope"], "Web与App增量探索")


if __name__ == "__main__":
    unittest.main()
