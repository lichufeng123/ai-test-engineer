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
                stage="CASE_DESIGN",
                status="active",
                summary="规则已审核，正在生成用例",
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
            self.assertEqual(state_a["stage"], "CASE_DESIGN")
            self.assertEqual(state_b["stage"], "INTAKE")
            self.assertEqual(handoff["summary"], "规则已审核，正在生成用例")
            self.assertEqual(handoff["next_steps"], ["补齐账号后执行权限用例"])
            self.assertEqual(handoff["owner"], "conversation-a")

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


if __name__ == "__main__":
    unittest.main()
