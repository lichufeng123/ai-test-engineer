"""Fail-closed privacy scanning without exposing matched values in receipts."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_test_framework.evidence_privacy import check_evidence_privacy


class EvidencePrivacyTests(unittest.TestCase):
    def test_text_sensitive_and_binary_unreviewed_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "runs/RUN-EXAMPLE/request.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text('{"Authorization":"Bearer fake-private-value"}', encoding="utf-8")
            ref = {"path": str(evidence.relative_to(root)),
                   "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
            payload = {"schema_version": 1, "items": [{**ref, "human_review": {
                "status": "passed", "reviewer": "SYNTHETIC", "reviewed_sha256": ref["sha256"]}}]}
            result = check_evidence_privacy(payload, root)
            self.assertIn("possible_sensitive_content", result["error_codes"])
            self.assertNotIn("fake-private-value", json.dumps(result))
            evidence.write_text('{"state":"ready"}', encoding="utf-8")
            payload["items"][0]["sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
            self.assertIn("semantic_privacy_review_missing", check_evidence_privacy(payload, root)["error_codes"])
            payload["items"][0]["human_review"]["reviewed_sha256"] = payload["items"][0]["sha256"]
            self.assertEqual(check_evidence_privacy(payload, root)["status"], "passed")
            media = root / "runs/RUN-EXAMPLE/view.png"
            media.write_bytes(b"not a valid image: privacy scanner does not check media quality")
            payload["items"] = [{"path": str(media.relative_to(root)),
                                  "sha256": hashlib.sha256(media.read_bytes()).hexdigest()}]
            self.assertIn("semantic_privacy_review_missing", check_evidence_privacy(payload, root)["error_codes"])


if __name__ == "__main__":
    unittest.main()
