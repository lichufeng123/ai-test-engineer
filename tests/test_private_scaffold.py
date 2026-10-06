"""The shipped private-repository starter must satisfy the framework's own gate."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_test_framework.cli import build_parser
from ai_test_framework.knowledge_adapter import audit_local_knowledge
from ai_test_framework.private_repo import scaffold_private_repository


class PrivateScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private-assets"

    def _scaffold(self, **overrides):
        options = dict(name="Example Products", system_id="example-products",
                       environments=["sit"], platforms=["web"])
        options.update(overrides)
        return scaffold_private_repository(self.root, **options)

    def test_scaffold_creates_a_validating_registry(self):
        result = self._scaffold()
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["project_profile"], "created")
        self.assertEqual(result["entry_count"], 4)
        for relative in ("ai-test.json", ".gitignore", "docs/PRIVATE_REPOSITORY.md",
                         "knowledge/INDEX.md", "knowledge/manifest.json",
                         "scripts/knowledge_registry.py"):
            self.assertTrue((self.root / relative).is_file(), relative)

        manifest = json.loads((self.root / "knowledge/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mode"], "local_only")
        self.assertFalse(manifest["remote_sync"]["enabled"])
        self.assertTrue(all(len(entry["sha256"]) == 64 for entry in manifest["entries"]))

        process = subprocess.run([sys.executable, "scripts/knowledge_registry.py", "validate"],
                                 cwd=self.root, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "passed")

    def test_framework_knowledge_audit_accepts_the_starter(self):
        self.assertEqual(self._scaffold()["status"], "created")
        result = audit_local_knowledge(self.root, feature="example-module", stage="execution")
        self.assertEqual(result["status"], "passed", result.get("error_codes"))
        self.assertEqual(result["scope"], "local_registry_hashes_only")
        self.assertFalse(result["content_interpreted"])
        self.assertFalse(result["authoritative_current_verified"])
        self.assertEqual(sorted(item["entry_id"] for item in result["verified_entries"]),
                         ["KNOWLEDGE-INDEX", "MODULE-TOPOLOGY", "OMISSION-RISKS", "SYSTEM-ECOSYSTEM"])

    def test_module_id_routing_uses_the_manifest(self):
        self._scaffold()
        matched = audit_local_knowledge(self.root, feature="example-module", stage="execution",
                                        module_id="example-module")
        self.assertGreaterEqual(matched["module_entry_count"], 1)
        missing = audit_local_knowledge(self.root, feature="example-module", stage="execution",
                                        module_id="unregistered-module")
        self.assertIn("feature_module_not_indexed", missing["error_codes"])

    def test_hash_drift_is_blocked_until_refresh(self):
        self._scaffold()
        target = self.root / "knowledge/INDEX.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n额外内容\n", encoding="utf-8")
        blocked = audit_local_knowledge(self.root, feature="example-module", stage="execution")
        self.assertEqual(blocked["status"], "blocked")
        # The registry's own validate rejects the drift before load can return it,
        # so the gate reports the upstream failure rather than a stale hash.
        self.assertEqual(blocked["error_codes"], ["registry_command_failed"])

        subprocess.run([sys.executable, "scripts/knowledge_registry.py", "refresh"],
                       cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(
            audit_local_knowledge(self.root, feature="example-module", stage="execution")["status"],
            "passed")

    def test_existing_files_are_never_overwritten(self):
        self.assertEqual(self._scaffold()["status"], "created")
        sentinel = self.root / "knowledge/INDEX.md"
        sentinel.write_text("手工内容\n", encoding="utf-8")
        again = self._scaffold()
        self.assertEqual(again["status"], "blocked")
        self.assertEqual(again["reason"], "private_repo_target_exists")
        self.assertIn("knowledge/INDEX.md", again["existing_files"])
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "手工内容\n")

    def test_profile_required_when_ai_test_json_is_absent(self):
        result = scaffold_private_repository(self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "project_profile_required")

    def test_existing_profile_is_reused(self):
        self._scaffold()
        self.root.joinpath("ai-test.json").write_text("{}", encoding="utf-8")
        # Remove only the knowledge layer so the scaffold can run again.
        for relative in ("knowledge", "scripts", "docs"):
            shutil.rmtree(self.root / relative)
        (self.root / ".gitignore").unlink()
        result = scaffold_private_repository(self.root)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["project_profile"], "existing")

    def test_registry_id_must_be_safe(self):
        result = scaffold_private_repository(self.root, name="X", system_id="example",
                                             registry_id="../escape")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "registry_id_invalid")
        self.assertFalse((self.root / "knowledge").exists())

    def test_cli_exposes_private_scaffold(self):
        args = build_parser().parse_args(["private-scaffold", "--root", "x",
                                          "--name", "N", "--system-id", "s"])
        self.assertEqual(args.command, "private-scaffold")
        self.assertEqual(args.root, "x")


if __name__ == "__main__":
    unittest.main()
