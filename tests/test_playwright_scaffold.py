"""Team starter must be packaged, layered, private-data-free, and non-destructive."""

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
from ai_test_framework.project import scaffold_playwright  # noqa: E402


class PlaywrightScaffoldTest(unittest.TestCase):
    def test_sample_has_distinct_layers_and_no_external_site(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = scaffold_playwright(root)
            self.assertEqual(result["status"], "created")
            web = root / "automation/web"
            for part in ("pages/CounterPage.ts", "flows/counterFlow.ts", "oracles/counter.ts",
                         "tests/counter.spec.ts", "evidence/phaseTiming.ts", "playwright.config.ts", "package-lock.json"):
                self.assertTrue((web / part).is_file(), part)
            spec = (web / "tests/counter.spec.ts").read_text()
            self.assertIn("assertCounter(actual, expected)", spec)
            self.assertIn(".toThrow('A-EXAMPLE-001')", spec)
            self.assertNotIn("http://", spec)
            self.assertNotIn("https://", spec)
            oracle = (web / "oracles/counter.ts").read_text()
            self.assertNotIn("page.", oracle)

    def test_existing_team_file_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "automation/web/pages/CounterPage.ts"
            target.parent.mkdir(parents=True)
            target.write_text("// team modification\n")
            result = scaffold_playwright(root)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(target.read_text(), "// team modification\n")
            self.assertFalse((root / "automation/web/tests/counter.spec.ts").exists())

    def test_cli_displays_blocked_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["playwright-scaffold", "--root", temp]), 0)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["playwright-scaffold", "--root", temp]), 1)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
