"""Local release-kit builder must include the project lock and never overwrite."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_team_preview import ROOT_FILES, build  # noqa: E402


class PreviewKitTests(unittest.TestCase):
    def test_lock_is_included_and_existing_archive_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            for name in ROOT_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fictional source", encoding="utf-8")
            (root / "framework-manifest.json").write_text(json.dumps({"framework_version": "0.13.0a1"}))
            for name in ("docs/TEST_CONTEXT_INDEX.md", "docs/TEAM_PREVIEW_INSTALL.md",
                         ".agents/skills/ai-test-workflow/SKILL.md",
                         "src/ai_test_framework/synthetic_adapter_runner.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fictional file", encoding="utf-8")
            (root / "uv.lock").write_text('version = "0.13.0a1"\n', encoding="utf-8")
            wheel = Path(directory) / "ai_test_engineer-0.13.0a1-py3-none-any.whl"
            wheel.write_bytes(b"fictional-wheel")
            output = Path(directory) / "preview.zip"
            result = build(root, wheel, output)
            self.assertEqual(result["status"], "built_local_not_published")
            with ZipFile(output) as archive:
                self.assertEqual(archive.read("framework/uv.lock"), (root / "uv.lock").read_bytes())
            with self.assertRaises(FileExistsError):
                build(root, wheel, output)


if __name__ == "__main__":
    unittest.main()
