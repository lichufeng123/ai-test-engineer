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
}


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
