"""A released clone must not carry a lockfile for a different framework version."""

import configparser
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _version_field(path, section):
    text = (ROOT / path).read_text(encoding="utf-8")
    block = re.search(rf"(?ms)^\[{re.escape(section)}\]\n(.*?)(?=^\[|\Z)", text)
    assert block, f"missing [{section}] in {path}"
    value = re.search(r'(?m)^version\s*=\s*"([^"]+)"', block.group(1))
    assert value, f"missing version in {path}"
    return value.group(1)


class ReleaseVersionConsistencyTest(unittest.TestCase):
    def test_installed_sources_and_lockfile_share_one_version(self):
        project = _version_field("pyproject.toml", "project")
        config = configparser.ConfigParser()
        config.read(ROOT / "setup.cfg", encoding="utf-8")
        uv = (ROOT / "uv.lock").read_text(encoding="utf-8")
        package = re.search(r'(?ms)^\[\[package\]\]\nname = "ai-test-engineer"\nversion = "([^"]+)"', uv)
        self.assertIsNotNone(package)
        init = re.search(r'__version__\s*=\s*"([^"]+)"',
                         (ROOT / "src/ai_test_framework/__init__.py").read_text(encoding="utf-8"))
        self.assertIsNotNone(init)
        self.assertEqual({
            project,
            config["metadata"]["version"],
            package.group(1),
            init.group(1),
            json.loads((ROOT / "framework-manifest.json").read_text(encoding="utf-8"))["framework_version"],
            json.loads((ROOT / "plugin/plugin.json").read_text(encoding="utf-8"))["version"],
        }, {project})


if __name__ == "__main__":
    unittest.main()
