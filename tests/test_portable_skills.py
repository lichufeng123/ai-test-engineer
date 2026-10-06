import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

import sys

sys.path.insert(0, str(SRC))

from ai_test_framework.skills import (  # noqa: E402
    build_portable_plugin,
    install_portable_skills,
    validate_portable_skills,
)


SKILL_NAMES = {
    "ai-test-workflow",
    "requirement-spec-generate",
    "generate-business-assertions",
    "test-case-generate",
    "requirement-grounded-functional-testing",
    "test-execution-asset-retrospective",
    "test-omission-risk-retrospective",
    "rapid-test",
    "one-pass-test",
    "test-data-and-account-fixture-management",
    "test-recording-generate",
}


class OmissionRiskWorkflowContractTest(unittest.TestCase):
    def test_case_generation_and_retrospective_share_one_risk_contract(self):
        case_skill = (ROOT / ".agents/skills/test-case-generate/SKILL.md").read_text(
            encoding="utf-8"
        )
        workflow_skill = (ROOT / ".agents/skills/ai-test-workflow/SKILL.md").read_text(
            encoding="utf-8"
        )
        execution_skill = (
            ROOT / ".agents/skills/requirement-grounded-functional-testing/SKILL.md"
        ).read_text(encoding="utf-8")
        retrospective = (
            ROOT / ".agents/skills/test-omission-risk-retrospective/SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("omission_risk_audit.json", case_skill)
        self.assertIn("OMISSION_RISK_RETROSPECTIVE", workflow_skill)
        self.assertIn("OMISSION_RISK_RETROSPECTIVE", execution_skill)
        self.assertIn("测试遗漏风险规则库", retrospective)
        self.assertIn("用户纠正", retrospective)
        self.assertIn("测试误判", retrospective)


class PortableSkillLayoutTest(unittest.TestCase):
    def test_cross_client_directory_is_the_canonical_skill_source(self):
        skill_root = ROOT / ".agents" / "skills"
        self.assertTrue(skill_root.is_dir())
        self.assertEqual(
            {path.name for path in skill_root.iterdir() if path.is_dir()},
            SKILL_NAMES,
        )

        result = validate_portable_skills(ROOT)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(set(result["skills"]), SKILL_NAMES)

    def test_plugin_is_built_from_canonical_skills_without_a_second_source_copy(self):
        manifest = json.loads(
            (ROOT / "plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "ai-test-engineer")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertFalse((ROOT / "skills").exists())
        self.assertEqual(
            manifest["version"],
            json.loads((ROOT / "framework-manifest.json").read_text(encoding="utf-8"))[
                "framework_version"
            ],
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ai-test-engineer"
            result = build_portable_plugin(ROOT, output)
            self.assertEqual(result["status"], "built", result)
            built_manifest = json.loads(
                (output / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
            )
            self.assertEqual(built_manifest, manifest)
            for name in SKILL_NAMES:
                self.assertEqual(
                    (output / "skills" / name / "SKILL.md").read_bytes(),
                    (ROOT / ".agents/skills" / name / "SKILL.md").read_bytes(),
                )

    def test_rapid_test_preserves_test_engineer_reasoning_and_provisional_authority(self):
        skill = (ROOT / ".agents/skills/rapid-test/SKILL.md").read_text(encoding="utf-8")
        for required in (
            "独立 Oracle",
            "动作前",
            "临时结论",
            "正式需求说明书",
            "待审核区",
            "零命中",
            "多命中",
        ):
            self.assertIn(required, skill)

        workflow = (ROOT / ".agents/skills/ai-test-workflow/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("rapid-test", workflow)
        self.assertIn("Skills 不是业务知识索引", workflow)

    def test_rapid_charter_template_encodes_context_oracle_and_provisional_result(self):
        schema = json.loads((ROOT / "schemas/rapid-test-charter.schema.json").read_text(encoding="utf-8"))
        template = json.loads((ROOT / "templates/rapid-test-charter.example.json").read_text(encoding="utf-8"))

        self.assertEqual(schema["properties"]["mode"]["const"], "rapid_test")
        self.assertEqual(schema["properties"]["result_authority"]["const"], "provisional")
        self.assertIn("knowledge_context", template)
        self.assertIn("risk_hypotheses", template)
        probe = template["probes"][0]
        self.assertTrue(probe["oracle"]["independent_from_sut"])
        self.assertIn("assertions", probe)
        self.assertIn("fixture", probe)
        self.assertEqual(probe["status"], "draft")

    def test_one_pass_skill_keeps_provisional_authority_and_visible_cases(self):
        skill = (ROOT / ".agents/skills/one-pass-test/SKILL.md").read_text(encoding="utf-8")
        for required in ("one_pass", "case_preview", "独立Oracle", "provisional", "执行", "报告", "不作验收/发布门禁"):
            self.assertIn(required, skill)
        workflow = (ROOT / ".agents/skills/ai-test-workflow/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("one-pass-test", workflow)

    def test_agent_guide_routes_project_knowledge_and_reasoning_before_skills(self):
        agent_guide = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        context_index = (ROOT / "docs/TEST_CONTEXT_INDEX.md").read_text(encoding="utf-8")
        reasoning = (ROOT / "docs/TEST_ENGINEER_REASONING.md").read_text(encoding="utf-8")

        for required in ("knowledge/INDEX.md", "knowledge/manifest.json", "遗漏风险", "独立 Oracle"):
            self.assertIn(required, agent_guide)
        for required in ("系统知识", "已审核业务规则", "测试设计风险", "执行资产", "required_reads"):
            self.assertIn(required, context_index)
        for required in ("测试意图", "风险假设", "Fixture", "Oracle", "假阳性"):
            self.assertIn(required, reasoning)

    def test_public_skills_do_not_embed_private_runtime_details(self):
        forbidden = {
            "/Users/",
            "http://",
            "https://",
        }
        for path in (ROOT / ".agents" / "skills").rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"{marker} leaked through {path}")

    def test_readmes_explain_project_and_user_level_cross_client_discovery(self):
        for filename in ("README.md", "README.zh-CN.md"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(".agents/skills", text)
            self.assertIn(".codex-plugin/plugin.json", text)


class PortableSkillInstallerTest(unittest.TestCase):
    def test_installer_links_the_same_canonical_source_into_client_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            result = install_portable_skills(
                ROOT,
                home=home,
                clients=["universal", "codex"],
                mode="symlink",
            )
            self.assertEqual(result["status"], "installed")
            for base in (home / ".agents/skills", home / ".codex/skills"):
                for name in SKILL_NAMES:
                    target = base / name
                    self.assertTrue(target.is_symlink())
                    self.assertEqual(target.resolve(), (ROOT / ".agents/skills" / name).resolve())

    def test_existing_directory_is_never_overwritten_without_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            existing = home / ".agents/skills/ai-test-workflow"
            existing.mkdir(parents=True)
            (existing / "KEEP.txt").write_text("keep", encoding="utf-8")

            result = install_portable_skills(
                ROOT,
                home=home,
                clients=["universal"],
                mode="symlink",
            )
            self.assertEqual(result["status"], "blocked")
            self.assertTrue((existing / "KEEP.txt").is_file())

    def test_replace_moves_existing_skill_to_a_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            existing = home / ".agents/skills/ai-test-workflow"
            existing.mkdir(parents=True)
            (existing / "KEEP.txt").write_text("keep", encoding="utf-8")

            result = install_portable_skills(
                ROOT,
                home=home,
                clients=["universal"],
                mode="symlink",
                replace=True,
            )
            self.assertEqual(result["status"], "installed")
            backup = Path(result["backup_root"])
            self.assertEqual(
                (backup / ".agents/skills/ai-test-workflow/KEEP.txt").read_text(
                    encoding="utf-8"
                ),
                "keep",
            )


if __name__ == "__main__":
    unittest.main()
