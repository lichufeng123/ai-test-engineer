"""Read-only bridge to an authorized local knowledge registry.

The registry decides required_reads; this adapter rechecks their paths and
hashes. It cannot attest that an agent understood the files, or that a local
mirror is the latest approved product Current.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

STAGES = {"intake", "requirement", "assertion", "case_design", "readiness", "execution", "triage", "retrospective"}
PLATFORMS = {"web", "app", "h5", "miniapp", "api", "device"}


def _invoke(root: Path, command: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        process = subprocess.run(
            [sys.executable, str(root / "scripts/knowledge_registry.py"), *command],
            cwd=root, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "registry_unavailable"
    if process.returncode != 0:
        return None, "registry_command_failed"
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        return None, "registry_output_invalid"
    return (payload, None) if isinstance(payload, dict) else (None, "registry_output_invalid")


def audit_local_knowledge(
    root: Path, *, feature: str, stage: str, platform: str | None = None, role: str | None = None,
    module_id: str | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    errors: list[str] = []
    if not isinstance(feature, str) or not feature.strip() or not isinstance(stage, str) or stage not in STAGES or (platform is not None and (not isinstance(platform, str) or platform not in PLATFORMS)) or (role is not None and not isinstance(role, str)):
        return {"status": "blocked", "error_codes": ["request_invalid"], "scope": "local_registry_only"}
    script = (root / "scripts/knowledge_registry.py").resolve()
    if not script.is_relative_to(root) or not script.is_file():
        return {"status": "blocked", "error_codes": ["registry_script_missing_or_unsafe"], "scope": "local_registry_only"}
    valid, issue = _invoke(root, ["validate"])
    if issue or not isinstance(valid, dict) or valid.get("status") != "passed" or valid.get("mode") != "local_only":
        return {"status": "blocked", "error_codes": [issue or "registry_validation_failed"], "scope": "local_registry_only"}
    args = ["load", "--feature", feature, "--stage", stage]
    if platform:
        args.extend(["--platform", platform])
    if role:
        args.extend(["--role", role])
    loaded, issue = _invoke(root, args)
    if issue or not isinstance(loaded, dict) or loaded.get("status") != "passed" or loaded.get("mode") != "local_only":
        return {"status": "blocked", "error_codes": [issue or "registry_load_failed"], "scope": "local_registry_only"}
    requested = loaded.get("request")
    if (not isinstance(requested, dict) or requested.get("feature") != feature
            or requested.get("stage") != stage or requested.get("platform") != platform
            or requested.get("role") != role or requested.get("include_candidates") is not False):
        errors.append("load_request_mismatch")
    reads = loaded.get("required_reads")
    if not isinstance(reads, list) or not reads or loaded.get("required_read_count") != len(reads):
        errors.append("required_reads_invalid")
        reads = []
    ids: set[str] = set()
    verified: list[dict[str, str]] = []
    for item in reads:
        if not isinstance(item, dict) or not isinstance(item.get("entry_id"), str) or not item["entry_id"].strip():
            errors.append("required_read_identity_invalid")
            continue
        entry_id = item["entry_id"]
        if entry_id in ids:
            errors.append("required_read_duplicate")
        ids.add(entry_id)
        if item.get("status") not in {"reviewed", "approved_test_method"}:
            errors.append("unapproved_required_read")
            continue
        raw = item.get("path")
        if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or ".." in Path(raw).parts:
            errors.append("required_read_path_unsafe")
            continue
        file = (root / raw).resolve()
        if (not file.is_relative_to(root) or not file.is_file()
                or item.get("absolute_path") != str(file)):
            errors.append("required_read_path_mismatch")
            continue
        try:
            hasher = hashlib.sha256()
            with file.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
        except OSError:
            errors.append("required_read_unreadable")
            continue
        if hasher.hexdigest() != item.get("sha256"):
            errors.append("required_read_hash_mismatch")
            continue
        verified.append({"entry_id": entry_id, "sha256": hasher.hexdigest(), "status": item["status"]})
    if len(verified) != len(reads):
        errors.append("required_reads_incomplete")
    module_entry_count: int | None = None
    if module_id is not None:
        if not isinstance(module_id, str) or not module_id.strip():
            errors.append("module_id_invalid")
        else:
            try:
                manifest = json.loads((root / "knowledge/manifest.json").read_text(encoding="utf-8"))
                entries = manifest.get("entries") if isinstance(manifest, dict) else None
                if not isinstance(entries, list):
                    raise ValueError("manifest_entries_invalid")
                matched_ids = {entry["entry_id"] for entry in entries if isinstance(entry, dict)
                               and isinstance(entry.get("entry_id"), str)
                               and isinstance(entry.get("modules"), list)
                               and module_id in entry["modules"]}
                module_entry_count = len(matched_ids & {item["entry_id"] for item in verified})
                if module_entry_count == 0:
                    errors.append("feature_module_not_indexed")
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                errors.append("module_manifest_unavailable")
    return {"schema_version": 1, "status": "blocked" if errors else "passed",
            "scope": "local_registry_hashes_only", "feature": feature, "stage": stage,
            "verified_entries": verified, "module_entry_count": module_entry_count,
            "error_codes": sorted(set(errors)),
            "content_interpreted": False, "authoritative_current_verified": False,
            "notice": "The caller must actually read each required file; local mirror is not official Current."}


SAFE_REQUIREMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")


def audit_local_baseline(root: Path, requirement_id: str) -> dict[str, Any]:
    """Check a work-item baseline's local identity/hash; never certify Feishu Current."""
    if not isinstance(requirement_id, str) or not SAFE_REQUIREMENT_ID.fullmatch(requirement_id):
        return {"status": "blocked", "error_codes": ["requirement_id_invalid"]}
    root = Path(root).resolve()
    manifest = root / ".ai-test/work-items" / requirement_id / "manifest.json"
    if not manifest.is_file():
        return {"status": "blocked", "error_codes": ["work_item_manifest_missing"]}
    try:
        item = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "error_codes": ["work_item_manifest_invalid"]}
    if not isinstance(item, dict) or item.get("requirement_id") != requirement_id:
        return {"status": "blocked", "error_codes": ["work_item_identity_mismatch"]}
    baseline = item.get("official_baseline")
    if not isinstance(baseline, dict) or not all(isinstance(baseline.get(k), str) and baseline[k].strip() for k in ("id", "path", "sha256")):
        return {"status": "blocked", "error_codes": ["local_baseline_reference_missing"],
                "requirement_id": requirement_id, "official_current_verified": False}
    raw = Path(baseline["path"])
    if raw.is_absolute() or ".." in raw.parts:
        return {"status": "blocked", "error_codes": ["local_baseline_outside_authorized_repo"],
                "requirement_id": requirement_id, "official_current_verified": False}
    target = (root / raw).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return {"status": "blocked", "error_codes": ["local_baseline_missing"],
                "requirement_id": requirement_id, "official_current_verified": False}
    try:
        hasher = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        content = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "error_codes": ["local_baseline_unreadable"],
                "requirement_id": requirement_id, "official_current_verified": False}
    errors = []
    if hasher.hexdigest() != baseline["sha256"]:
        errors.append("local_baseline_hash_mismatch")
    if not isinstance(content, dict) or content.get("baseline_id") != baseline["id"]:
        errors.append("local_baseline_identity_mismatch")
    return {"schema_version": 1, "status": "blocked" if errors else "passed",
            "scope": "local_baseline_file_only", "requirement_id": requirement_id,
            "baseline_id": baseline["id"], "sha256": hasher.hexdigest(),
            "test_mode": item.get("test_mode", "unclassified"),
            "error_codes": sorted(errors), "official_current_verified": False,
            "notice": "Local hash match is not a validated remote Current or a permission to execute."}
