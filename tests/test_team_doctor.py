"""Offline team onboarding: no browser, network, secrets or business writes."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_test_framework.cli import main
from ai_test_framework.project import initialize_project, scaffold_playwright
from ai_test_framework.team_doctor import inspect_team_project


class TeamDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.framework = self.base / "framework"
        for name in ("AGENTS.md", "docs/TEST_CONTEXT_INDEX.md", ".agents/skills/ai-test-workflow/SKILL.md"):
            path = self.framework / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("dummy", encoding="utf-8")
        self.project = self.base / "project"
        initialize_project(self.project, name="synthetic", system_id="SYS-EXAMPLE", environments=["LOCAL"], platforms=["web"])
        scaffold_playwright(self.project)

    @patch("ai_test_framework.team_doctor.shutil.which", return_value="/bin/tool")
    def test_installed_synthetic_clone_is_only_statically_healthy(self, unused_which):
        package = self.project / "automation/web/node_modules/@playwright/test/package.json"
        package.parent.mkdir(parents=True)
        package.write_text("{}", encoding="utf-8")
        result = inspect_team_project(self.project, self.framework)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["scope"], "offline_clone_health_only")
        self.assertEqual(result["checks"]["browser_runtime"], "not_tested")
        self.assertEqual(result["checks"]["business_execution"], "not_validated")
        self.assertEqual(inspect_team_project(self.project, self.framework, require_business=True)["status"], "blocked")
        self.assertIn("business_execution_not_integrated", inspect_team_project(
            self.project, self.framework, require_business=True)["error_codes"])

    @patch("ai_test_framework.team_doctor.shutil.which", return_value=None)
    def test_missing_prerequisites_block_without_installation(self, unused_which):
        result = inspect_team_project(self.project, self.framework)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("playwright_dependency_missing", result["error_codes"])
        self.assertIn("node_missing", result["error_codes"])
        self.assertFalse((self.project / "automation/web/node_modules").exists())

    @patch("ai_test_framework.team_doctor.shutil.which", return_value="/bin/tool")
    def test_missing_or_unsafe_private_manifest_blocks_only_when_configured(self, unused_which):
        private = self.base / "private"
        private.mkdir()
        result = inspect_team_project(self.project, self.framework, private_root=private)
        self.assertIn("knowledge_manifest_missing", result["error_codes"])
        index = private / "knowledge/INDEX.md"
        index.parent.mkdir()
        index.write_text("reviewed", encoding="utf-8")
        manifest = private / "knowledge/manifest.json"
        entry = {"entry_id": "IDX", "path": "knowledge/INDEX.md", "sha256": hashlib.sha256(index.read_bytes()).hexdigest()}
        manifest.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
        self.assertNotIn("knowledge_hash_mismatch", inspect_team_project(
            self.project, self.framework, private_root=private)["error_codes"])
        index.write_text("changed", encoding="utf-8")
        self.assertIn("knowledge_hash_mismatch", inspect_team_project(
            self.project, self.framework, private_root=private)["error_codes"])
        entry["path"] = "../outside"
        manifest.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
        self.assertIn("knowledge_path_unsafe", inspect_team_project(
            self.project, self.framework, private_root=private)["error_codes"])

    def test_api_only_project_initializes_without_browser_dependency(self):
        api_root = self.base / "api-project"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", str(api_root), "--name", "fictional-catalog",
                                   "--system-id", "SYNTH-CATALOG", "--platform", "api"]), 0)
        result = inspect_team_project(api_root, self.framework)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(json.loads((api_root / "ai-test.json").read_text())["platforms"], ["api"])
        self.assertEqual(result["checks"]["web_starter_present"], "not_applicable")

    def test_invalid_config_never_crashes_and_cli_exit_is_nonzero(self):
        (self.project / "ai-test.json").write_text('{"secrets": "oops", "case_generation": null}', encoding="utf-8")
        result = inspect_team_project(self.project, self.framework)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("project_contract_invalid", result["error_codes"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["doctor", "--root", str(self.project), "--framework-root", str(self.framework)]), 1)
        self.assertNotIn("oops", output.getvalue())


if __name__ == "__main__":
    unittest.main()
