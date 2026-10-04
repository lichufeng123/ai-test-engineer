"""Conservative evidence privacy preflight; never echo matched content or secrets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .execution_contract import _artifact

RISK_KEYS = re.compile(r'(?i)["\'](?:password|passwd|secret|api[_-]?key|token|cookie|set-cookie|authorization|phone|mobile|email|id[_-]?card|openid|customer[_-]?name)["\']\s*:')
RISK_VALUES = re.compile(r'(?i)\bBearer\s+\S+|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----|\b(?:password|token|authorization|cookie)\s*[=:]\s*\S+|\b1[3-9][0-9]{9}\b|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|https?://\S+')
TEXT_SUFFIXES = {".json", ".txt", ".md", ".log", ".har", ".xml", ".html", ".csv"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".zip"}


def check_evidence_privacy(payload: Any, root: Path) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("items"), list) or not payload["items"]:
        return {"status": "blocked", "error_codes": ["privacy_manifest_invalid"]}
    errors: list[str] = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            errors.append("privacy_item_invalid")
            continue
        path = _artifact(Path(root).resolve(), item, "evidence", errors)
        if path is None:
            continue
        review = item.get("human_review")
        if (not isinstance(review, dict) or review.get("status") != "passed"
                or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
                or review.get("reviewed_sha256") != item["sha256"]):
            errors.append("semantic_privacy_review_missing")
        if path.suffix.lower() in TEXT_SUFFIXES:
            if path.stat().st_size > 20 * 1024 * 1024:
                errors.append("evidence_text_too_large_for_scan")
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.append("evidence_text_unreadable")
                continue
            if RISK_KEYS.search(text) or RISK_VALUES.search(text):
                errors.append("possible_sensitive_content")
        elif path.suffix.lower() not in BINARY_SUFFIXES:
            errors.append("evidence_format_unsupported")
    return {"schema_version": 1, "status": "blocked" if errors else "passed",
            "scope": "local_scan_and_review_declaration_only", "error_codes": sorted(set(errors)),
            "manual_review_required": True}
