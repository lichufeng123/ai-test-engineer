import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.execution_history import finish_execution, start_execution
from ai_test_framework.cli import main
from ai_test_framework.project import initialize_project


class ExecutionHistoryTest(unittest.TestCase):
    def test_workflow_and_handbook_require_start_and_finish_logging(self):
        workflow = (
            ROOT / ".agents/skills/ai-test-workflow/SKILL.md"
        ).read_text(encoding="utf-8")
        execution_skill = (
            ROOT
            / ".agents/skills/requirement-grounded-functional-testing/SKILL.md"
        ).read_text(encoding="utf-8")
        handbook = (ROOT / "docs/FRAMEWORK.md").read_text(encoding="utf-8")
        chinese_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for content in (workflow, execution_skill, handbook, chinese_readme):
            self.assertIn("execution-log-start", content)
            self.assertIn("execution-log-finish", content)
            self.assertIn("AUTOMATION_EXECUTION_HISTORY.md", content)

    def test_project_initialization_creates_fixed_markdown_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_project(
                root,
                name="演示项目",
                system_id="demo",
                environments=["sit"],
                platforms=["web"],
            )
            markdown = root / "AUTOMATION_EXECUTION_HISTORY.md"
            self.assertTrue(markdown.exists())
            self.assertIn("暂无执行记录", markdown.read_text(encoding="utf-8"))
            index = json.loads(
                (root / ".ai-test/work-items/index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["items"], [])

    def test_start_records_first_time_purpose_objective_and_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = start_execution(
                root,
                automation_id="smart-earphone-web",
                run_id="RUN-001",
                feature="智能耳机 Web",
                environment="sit",
                platforms=["web"],
                purpose="发布前回归门禁",
                objective="确认核心流程可以进入下一环境",
                scope="连锁与门店的搜索、筛选、分页和页面跳转",
                baseline="approved-cases@sha256:abc",
                started_at="2026-09-20T09:30:00+08:00",
            )

            self.assertEqual(result["status"], "started")
            self.assertEqual(result["first_executed_at"], "2026-09-20T09:30:00+08:00")
            state = json.loads(
                (root / ".ai-test/execution_history.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["automations"][0]["execution_count"], 1)
            markdown = (root / "AUTOMATION_EXECUTION_HISTORY.md").read_text(encoding="utf-8")
            self.assertIn("发布前回归门禁", markdown)
            self.assertIn("确认核心流程可以进入下一环境", markdown)
            self.assertIn("连锁与门店的搜索、筛选、分页和页面跳转", markdown)

    def test_subsequent_run_preserves_first_time_and_increments_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = {
                "root": root,
                "automation_id": "smart-earphone-web",
                "feature": "智能耳机 Web",
                "environment": "sit",
                "platforms": ["web"],
                "purpose": "日常回归",
                "objective": "确认既有能力稳定",
                "scope": "核心流程",
            }
            start_execution(run_id="RUN-001", started_at="2026-09-20T09:30:00+08:00", **common)
            result = start_execution(
                run_id="RUN-002", started_at="2026-09-21T10:00:00+08:00", **common
            )

            self.assertEqual(result["first_executed_at"], "2026-09-20T09:30:00+08:00")
            self.assertEqual(result["execution_count"], 2)
            markdown = (root / "AUTOMATION_EXECUTION_HISTORY.md").read_text(encoding="utf-8")
            self.assertIn("RUN-001", markdown)
            self.assertIn("RUN-002", markdown)
            self.assertIn("2026-09-20T09:30:00+08:00", markdown)

    def test_repeated_start_is_idempotent_and_finish_records_duration_and_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = {
                "automation_id": "roleplay-miniapp",
                "run_id": "RUN-003",
                "feature": "自定义陪练难度",
                "environment": "prod1",
                "platforms": ["miniapp"],
                "purpose": "缺陷修复回归",
                "objective": "验证三个难度链路",
                "scope": "简单、标准、挑战三条核心流程",
                "started_at": "2026-09-20T10:00:00+08:00",
            }
            start_execution(root, **kwargs)
            repeated = start_execution(root, **kwargs)
            self.assertTrue(repeated["idempotent"])
            self.assertEqual(repeated["execution_count"], 1)

            result = finish_execution(
                root,
                run_id="RUN-003",
                result_status="passed",
                summary="三个难度均完成并产生评分",
                finished_at="2026-09-20T10:08:30+08:00",
                report="reports/roleplay-prod1.md",
                evidence="runs/RUN-003/evidence-manifest.json",
                asset_changes=["更新小程序入口定位", "保留三段核心流程视频"],
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["duration_seconds"], 510)
            markdown = (root / "AUTOMATION_EXECUTION_HISTORY.md").read_text(encoding="utf-8")
            self.assertIn("8分30秒", markdown)
            self.assertIn("三个难度均完成并产生评分", markdown)
            self.assertIn("更新小程序入口定位", markdown)

    def test_simultaneous_synthetic_starts_preserve_all_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def create(index):
                return start_execution(
                    root, automation_id="AUTO-SYNTH", run_id=f"RUN-SYNTH-{index}",
                    feature="synthetic", environment="local", platforms=["api"],
                    purpose="lock smoke", objective="no lost runs", scope="read-only",
                    started_at="2026-10-04T00:00:00+00:00")

            with ThreadPoolExecutor(max_workers=4) as pool:
                receipts = list(pool.map(create, range(4)))
            self.assertEqual([item["status"] for item in receipts], ["started"] * 4)
            data = json.loads((root / ".ai-test/execution_history.json").read_text(encoding="utf-8"))
            self.assertEqual(data["automations"][0]["execution_count"], 4)
            self.assertEqual(len(data["automations"][0]["runs"]), 4)

    def test_same_run_id_cannot_be_reused_for_another_automation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = {
                "root": root,
                "run_id": "RUN-SHARED",
                "feature": "功能",
                "environment": "sit",
                "platforms": ["web"],
                "purpose": "回归",
                "objective": "验证",
                "scope": "核心流程",
                "started_at": "2026-09-20T10:00:00+08:00",
            }
            start_execution(automation_id="asset-a", **base)
            with self.assertRaisesRegex(ValueError, "run_id"):
                start_execution(automation_id="asset-b", **base)

    def test_cli_start_and_finish_update_the_same_fixed_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = StringIO()
            with redirect_stdout(output):
                start_code = main(
                    [
                        "execution-log-start",
                        "--root",
                        directory,
                        "--automation-id",
                        "qbank-import-export",
                        "--run-id",
                        "RUN-CLI-001",
                        "--feature",
                        "题库批量导入导出",
                        "--environment",
                        "zone99",
                        "--platform",
                        "web",
                        "--purpose",
                        "发布回归",
                        "--objective",
                        "确认发布包可用",
                        "--scope",
                        "导入和全部导出",
                        "--started-at",
                        "2026-09-20T11:00:00+08:00",
                    ]
                )
            self.assertEqual(start_code, 0)

            output = StringIO()
            with redirect_stdout(output):
                finish_code = main(
                    [
                        "execution-log-finish",
                        "--root",
                        directory,
                        "--run-id",
                        "RUN-CLI-001",
                        "--status",
                        "partial",
                        "--summary",
                        "导入通过，导出待数据",
                        "--finished-at",
                        "2026-09-20T11:05:00+08:00",
                        "--asset-change",
                        "更新导入定位",
                    ]
                )
            self.assertEqual(finish_code, 0)
            markdown = (Path(directory) / "AUTOMATION_EXECUTION_HISTORY.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("RUN-CLI-001", markdown)
            self.assertIn("partial", markdown)
            self.assertIn("更新导入定位", markdown)


if __name__ == "__main__":
    unittest.main()
