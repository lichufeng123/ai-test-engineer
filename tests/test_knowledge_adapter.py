"""Read-only knowledge/working-baseline adapter with synthetic private registry."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_test_framework.knowledge_adapter import audit_local_baseline, audit_local_knowledge


class KnowledgeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        guide = self.root / "knowledge/INDEX.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("fictional-reviewed-guide", encoding="utf-8")
        entry = {"entry_id": "IDX", "path": "knowledge/INDEX.md", "absolute_path": str(guide.resolve()),
                 "status": "reviewed", "sha256": hashlib.sha256(guide.read_bytes()).hexdigest()}
        self.receipt = {"status": "passed", "mode": "local_only",
                        "request": {"feature": "example", "stage": "readiness", "platform": None,
                                    "role": None, "include_candidates": False},
                        "required_read_count": 1, "required_reads": [entry]}
        manifest = guide.parent / "manifest.json"
        manifest.write_text(json.dumps({"entries": [{"entry_id": "IDX", "modules": ["example-module"]}]}), encoding="utf-8")
        payload = self.root / "load.json"
        payload.write_text(json.dumps(self.receipt), encoding="utf-8")
        script = self.root / "scripts/knowledge_registry.py"
        script.parent.mkdir(parents=True)
        script.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "if sys.argv[1] == 'validate': print(json.dumps({'status':'passed','mode':'local_only'}))\n"
            "elif sys.argv[1] == 'load': print(Path('load.json').read_text())\n",
            encoding="utf-8")

    def test_reads_route_hashes_without_claiming_official_current(self):
        result = audit_local_knowledge(self.root, feature="example", stage="readiness")
        self.assertEqual(result["status"], "passed")
        self.assertEqual([x["entry_id"] for x in result["verified_entries"]], ["IDX"])
        self.assertFalse(result["content_interpreted"])
        self.assertFalse(result["authoritative_current_verified"])
        self.assertEqual(audit_local_knowledge(self.root, feature="example", stage="readiness",
                                                module_id="example-module")["module_entry_count"], 1)
        self.assertIn("feature_module_not_indexed", audit_local_knowledge(
            self.root, feature="example", stage="readiness", module_id="missing-module")["error_codes"])
        (self.root / "knowledge/INDEX.md").write_text("changed", encoding="utf-8")
        self.assertIn("required_read_hash_mismatch", audit_local_knowledge(
            self.root, feature="example", stage="readiness")["error_codes"])

    def test_candidate_and_request_drift_or_unsafe_path_block(self):
        self.receipt["required_reads"][0]["status"] = "pending_review"
        (self.root / "load.json").write_text(json.dumps(self.receipt), encoding="utf-8")
        result = audit_local_knowledge(self.root, feature="example", stage="readiness")
        self.assertIn("unapproved_required_read", result["error_codes"])
        self.receipt["required_reads"][0].update(status="reviewed", path="../outside")
        (self.root / "load.json").write_text(json.dumps(self.receipt), encoding="utf-8")
        self.assertIn("required_read_path_unsafe", audit_local_knowledge(
            self.root, feature="example", stage="readiness")["error_codes"])
        self.receipt["required_reads"][0]["path"] = "knowledge/INDEX.md"
        self.receipt["request"]["include_candidates"] = True
        (self.root / "load.json").write_text(json.dumps(self.receipt), encoding="utf-8")
        self.assertIn("load_request_mismatch", audit_local_knowledge(
            self.root, feature="example", stage="readiness")["error_codes"])

    def test_local_baseline_hash_and_scope_not_remote_approval(self):
        requirement = "REQ-EXAMPLE"
        base = self.root / ".ai-test/work-items" / requirement
        base.mkdir(parents=True)
        file = base / "cases.json"
        file.write_text(json.dumps({"baseline_id": "BL-EXAMPLE", "cases": []}), encoding="utf-8")
        manifest = base / "manifest.json"
        local_path = str(file.relative_to(self.root))
        value = {"requirement_id": requirement, "test_mode": "rapid",
                 "official_baseline": {"id": "BL-EXAMPLE", "path": local_path,
                                       "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}}
        manifest.write_text(json.dumps(value), encoding="utf-8")
        result = audit_local_baseline(self.root, requirement)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["official_current_verified"])
        file.write_text('{"baseline_id":"BL-OTHER"}', encoding="utf-8")
        self.assertIn("local_baseline_hash_mismatch", audit_local_baseline(
            self.root, requirement)["error_codes"])
        value["official_baseline"]["path"] = "../archived/cases.json"
        manifest.write_text(json.dumps(value), encoding="utf-8")
        self.assertIn("local_baseline_outside_authorized_repo", audit_local_baseline(
            self.root, requirement)["error_codes"])
        self.assertEqual(audit_local_baseline(self.root, "../../etc")["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
