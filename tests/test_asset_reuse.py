import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_test_framework.asset_reuse import check_automation_asset_reuse  # noqa: E402
from ai_test_framework.cli import main  # noqa: E402


def review():
    return {
        "schema_version": 1,
        "feature": "员工表现一致性",
        "searches": [
            {
                "root": "features/earphone",
                "file_globs": ["tests/*consistency*.spec.ts", "pages/*.ts"],
                "purpose": "查找正式回归和共享页面资产",
            }
        ],
        "candidate_assets": [
            {
                "path": "features/earphone/tests/earphone.consistency.spec.ts",
                "covered_capabilities": ["员工详情", "六维"],
                "decision": "extend",
                "reason": "既有主干可覆盖 Web 采集",
            },
            {
                "path": "features/earphone/pages/Recorder.ts",
                "covered_capabilities": ["证据记录"],
                "decision": "reuse",
                "reason": "现有证据封装可直接使用",
            },
        ],
        "proposed_changes": [
            {
                "path": "features/earphone/tests/earphone.consistency.spec.ts",
                "change_type": "extend_existing",
                "gap": "缺少跨端快照输出",
                "based_on": [
                    "features/earphone/tests/earphone.consistency.spec.ts",
                    "features/earphone/pages/Recorder.ts",
                ],
            }
        ],
        "review_confirmed": True,
    }


def prepare(root: Path):
    for relative in (
        "features/earphone/tests/earphone.consistency.spec.ts",
        "features/earphone/pages/Recorder.ts",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// reusable asset\n", encoding="utf-8")


class AutomationAssetReuseTest(unittest.TestCase):
    def test_existing_assets_and_incremental_change_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root)
            result = check_automation_asset_reuse(review(), root)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["error_codes"], [])
            self.assertEqual(len(result["discovered_asset_paths"]), 2)

    def test_discovered_asset_without_disposition_blocks_new_script(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root)
            extra = root / "features/earphone/pages/EmployeePerformance.ts"
            extra.write_text("// existing page asset\n", encoding="utf-8")
            result = check_automation_asset_reuse(review(), root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("discovered_assets_without_disposition", result["error_codes"])
            self.assertIn(
                "features/earphone/pages/EmployeePerformance.ts",
                result["undispositioned_asset_paths"],
            )

    def test_new_asset_without_reuse_basis_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root)
            value = review()
            value["proposed_changes"] = [
                {
                    "path": "features/earphone/tests/new.spec.ts",
                    "change_type": "new_asset",
                    "gap": "新增对账",
                    "based_on": [],
                }
            ]
            result = check_automation_asset_reuse(value, root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("invalid_proposed_change", result["error_codes"])
            self.assertIn(
                "features/earphone/tests/new.spec.ts:reuse_basis_missing",
                result["invalid_changes"],
            )

    def test_cli_writes_receipt_and_returns_nonzero_when_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root)
            value = review()
            value["review_confirmed"] = False
            source = root / "review.json"
            receipt = root / "receipt.json"
            source.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([
                    "automation-asset-reuse-check",
                    "--input", str(source),
                    "--root", str(root),
                    "--output", str(receipt),
                ])
            self.assertEqual(code, 1)
            self.assertEqual(
                json.loads(receipt.read_text(encoding="utf-8"))["status"],
                "blocked",
            )


if __name__ == "__main__":
    unittest.main()
