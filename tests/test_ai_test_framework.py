import json
import re
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

sys.path.insert(0, str(SRC))

from ai_test_framework.data_factory import generate_fixtures
from ai_test_framework.discovery import plan_discovery
from ai_test_framework.documentation import check_documentation_sync
from ai_test_framework.evidence import check_evidence
from ai_test_framework.project import initialize_project


def write_fake_png(path: Path, width: int, height: int) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
    )


class DiscoveryPlanningTest(unittest.TestCase):
    def test_first_user_without_assets_is_reminded_to_explore_globally(self):
        result = plan_discovery(
            project={"system_id": "demo", "environments": ["sit"], "platforms": ["web"]},
            asset_register=None,
            requested_environment="sit",
            requested_platforms=["web"],
            product_version="1.0",
        )
        self.assertEqual(result["decision"], "system_global_required")
        self.assertIn("首次没有系统探索资产", result["reasons"])

    def test_verified_assets_skip_repeated_global_exploration(self):
        result = plan_discovery(
            project={"system_id": "demo", "environments": ["sit"], "platforms": ["web"]},
            asset_register={
                "system_id": "demo",
                "status": "verified",
                "product_version": "1.0",
                "environments": ["sit"],
                "platforms": ["web"],
            },
            requested_environment="sit",
            requested_platforms=["web"],
            product_version="1.0",
        )
        self.assertEqual(result["decision"], "feature_only")
        self.assertFalse(result["global_exploration_required"])

    def test_manual_request_always_triggers_global_exploration(self):
        result = plan_discovery(
            project={"system_id": "demo"},
            asset_register={"status": "verified", "product_version": "1.0"},
            requested_environment="sit",
            requested_platforms=["web"],
            product_version="1.0",
            manual_global=True,
        )
        self.assertEqual(result["decision"], "system_global_required")
        self.assertIn("用户手动要求全局探索", result["reasons"])

    def test_new_h5_surface_for_app_triggers_scoped_incremental_exploration(self):
        result = plan_discovery(
            project={"system_id": "demo"},
            asset_register={
                "status": "verified",
                "product_version": "1.0",
                "environments": ["sit"],
                "platforms": ["web"],
            },
            requested_environment="pre",
            requested_platforms=["app", "h5"],
            product_version="1.0",
        )
        self.assertEqual(result["decision"], "incremental_required")
        self.assertEqual(result["uncovered_environments"], ["pre"])
        self.assertEqual(result["uncovered_platforms"], ["app", "h5"])
        self.assertTrue(result["app_h5_pair_review_required"])


class ProjectInitializationTest(unittest.TestCase):
    def test_init_creates_shared_state_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = initialize_project(
                root,
                name="演示项目",
                system_id="demo",
                environments=["sit", "pre"],
                platforms=["web", "app", "h5"],
            )
            config = json.loads((root / "ai-test.json").read_text(encoding="utf-8"))
            state = json.loads((root / ".ai-test/workflow_state.json").read_text(encoding="utf-8"))
            self.assertEqual(config["case_generation"]["adapter"], "approved-test-case-baseline")
            self.assertNotIn("password", json.dumps(config).lower())
            self.assertEqual(state["stage"], "INTAKE")
            self.assertTrue((root / "runs").is_dir())
            self.assertEqual(result["status"], "created")


class DocumentationGuardTest(unittest.TestCase):
    def test_repository_readme_and_handbook_are_synced(self):
        result = check_documentation_sync(ROOT)
        self.assertEqual(result["status"], "passed")

    def test_package_versions_match_framework_manifest(self):
        version = json.loads(
            (ROOT / "framework-manifest.json").read_text(encoding="utf-8")
        )["framework_version"]
        for path in (ROOT / "pyproject.toml", ROOT / "setup.cfg"):
            match = re.search(
                r"^version\s*=\s*[\"']?([^\"'\s]+)",
                path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            self.assertIsNotNone(match, path)
            self.assertEqual(match.group(1), version, path)
        init_text = (ROOT / "src/ai_test_framework/__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{version}"', init_text)

    def test_readme_and_handbook_must_match_manifest_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "framework-manifest.json").write_text(
                json.dumps({"framework_version": "0.1.0"}), encoding="utf-8"
            )
            (root / "README.md").write_text("<!-- FRAMEWORK_VERSION: 0.1.0 -->", encoding="utf-8")
            (root / "README.zh-CN.md").write_text("<!-- FRAMEWORK_VERSION: 0.1.0 -->", encoding="utf-8")
            (root / "docs/FRAMEWORK.md").write_text("<!-- FRAMEWORK_VERSION: 0.0.9 -->", encoding="utf-8")
            result = check_documentation_sync(root)
            self.assertEqual(result["status"], "failed")
            self.assertIn("docs/FRAMEWORK.md", result["outdated_documents"])

    def test_chinese_readme_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "framework-manifest.json").write_text(
                json.dumps({"framework_version": "0.3.0"}), encoding="utf-8"
            )
            (root / "README.md").write_text("<!-- FRAMEWORK_VERSION: 0.3.0 -->", encoding="utf-8")
            (root / "docs/FRAMEWORK.md").write_text("<!-- FRAMEWORK_VERSION: 0.3.0 -->", encoding="utf-8")
            result = check_documentation_sync(root)
            self.assertEqual(result["status"], "failed")
            self.assertIn("README.zh-CN.md", result["missing_documents"])


class EvidenceGuardTest(unittest.TestCase):
    def test_small_web_screenshot_and_filename_only_report_get_repair_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "TC-001-result.png"
            write_fake_png(evidence, 1000, 700)
            report = root / "report.md"
            report.write_text("截图：TC-001-result.png", encoding="utf-8")
            manifest = {
                "items": [{
                    "case_id": "TC-001",
                    "kind": "screenshot",
                    "phase": "result",
                    "platform": "web",
                    "path": evidence.name,
                    "required": True,
                }]
            }
            result = check_evidence(manifest, root=root, report_path=report)
            self.assertEqual(result["status"], "repair_required")
            self.assertIn("recapture_normal_viewport", result["repair_actions"])
            self.assertIn("embed_media_block", result["repair_actions"])

    def test_mobile_screenshot_keeps_device_size_and_embedded_image_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "TC-MINI-result.png"
            write_fake_png(evidence, 750, 1334)
            report = root / "report.md"
            report.write_text("![结果](TC-MINI-result.png)", encoding="utf-8")
            manifest = {"items": [{
                "case_id": "TC-MINI",
                "kind": "screenshot",
                "phase": "result",
                "platform": "miniapp",
                "path": evidence.name,
                "required": True,
            }]}
            result = check_evidence(manifest, root=root, report_path=report)
            self.assertEqual(result["status"], "passed")


class DataFactoryTest(unittest.TestCase):
    def test_generates_semantic_xlsx_and_hash_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = {
                "feature_id": "question-import",
                "fixtures": [{
                    "fixture_id": "QBI-VALID-001",
                    "format": "xlsx",
                    "purpose": "合法最小数据",
                    "expected": "success",
                    "cleanup": "retain_for_regression",
                    "headers": ["模块", "题目"],
                    "rows": [["自动化模块", "自动化题目"]],
                }],
            }
            manifest = generate_fixtures(spec, root)
            item = manifest["fixtures"][0]
            generated = root / item["path"]
            self.assertRegex(generated.name, r"QBI-VALID-001_合法最小数据\.xlsx")
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(generated.exists())
            with zipfile.ZipFile(generated) as archive:
                self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
            self.assertEqual(item["cleanup"], "retain_for_regression")


if __name__ == "__main__":
    unittest.main()
