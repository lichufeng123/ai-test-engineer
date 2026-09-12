"""Validate local evidence before and after report generation."""

import re
import struct
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


def _image_size(path: Path) -> Optional[Tuple[int, int]]:
    raw = path.read_bytes()
    if raw.startswith(b"\x89PNG") and len(raw) >= 24:
        return struct.unpack(">II", raw[16:24])
    if raw.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(raw):
            if raw[index] != 0xFF:
                index += 1
                continue
            marker = raw[index + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", raw[index + 5:index + 9])
                return width, height
            if index + 4 > len(raw):
                break
            length = struct.unpack(">H", raw[index + 2:index + 4])[0]
            index += 2 + length
    return None


def check_evidence(
    manifest: Dict[str, Any],
    *,
    root: Path,
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    root = Path(root)
    report = report_path.read_text(encoding="utf-8") if report_path and report_path.exists() else ""
    issues = []
    repairs = []

    for item in manifest.get("items", []):
        if not item.get("required", True):
            continue
        relative = item.get("path", "")
        path = root / relative
        case_id = item.get("case_id", "UNKNOWN")
        if not path.exists():
            issues.append({"case_id": case_id, "issue": "evidence_missing", "path": relative})
            repairs.append("recapture_or_restore_missing_evidence")
            continue
        if item.get("kind") == "screenshot":
            size = _image_size(path)
            if not size:
                issues.append({"case_id": case_id, "issue": "image_unreadable", "path": relative})
                repairs.append("recapture_or_restore_missing_evidence")
            elif item.get("platform") == "web" and size[0] < 1600:
                issues.append({"case_id": case_id, "issue": "web_viewport_too_small", "size": size})
                repairs.append("recapture_normal_viewport")

        if report_path:
            escaped = re.escape(relative)
            embedded = bool(re.search(r"!\[[^\]]*\]\([^)]*" + escaped + r"[^)]*\)", report))
            if not embedded:
                issues.append({"case_id": case_id, "issue": "media_not_embedded", "path": relative})
                repairs.append("embed_media_block")

    repairs = list(dict.fromkeys(repairs))
    return {
        "status": "passed" if not issues else "repair_required",
        "issues": issues,
        "repair_actions": repairs,
        "checked_items": len(manifest.get("items", [])),
    }
