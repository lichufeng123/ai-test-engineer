"""Deterministic gate for reusing existing automation assets before adding scripts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Set


ALLOWED_DECISIONS = {"reuse", "extend", "reject", "supersede"}
ALLOWED_CHANGE_TYPES = {"extend_existing", "new_asset", "archive_only"}
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "credentials",
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _assert_no_sensitive_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS:
                raise ValueError(f"sensitive_field:{path}.{key}")
            _assert_no_sensitive_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_sensitive_fields(child, f"{path}[{index}]")


def _safe_relative(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe_relative_path:{value}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"path_outside_root:{value}") from error
    return resolved


def _discover(root: Path, searches: List[Dict[str, Any]]) -> Set[str]:
    discovered: Set[str] = set()
    for search in searches:
        relative_root = str(search.get("root", "")).strip()
        patterns = search.get("file_globs", [])
        if not relative_root or not patterns:
            continue
        search_root = _safe_relative(root, relative_root)
        if not search_root.is_dir():
            continue
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                continue
            for path in search_root.glob(pattern):
                if path.is_file():
                    discovered.add(path.resolve().relative_to(root.resolve()).as_posix())
    return discovered


def check_automation_asset_reuse(review: Dict[str, Any], root: Path) -> Dict[str, Any]:
    """Require an evidence-backed disposition for every discovered candidate asset."""

    _assert_no_sensitive_fields(review)
    root = Path(root).resolve()
    errors: List[str] = []
    if review.get("schema_version") != 1:
        errors.append("unsupported_schema_version")
    if not str(review.get("feature", "")).strip():
        errors.append("feature_missing")

    searches = review.get("searches")
    if not isinstance(searches, list) or not searches:
        errors.append("asset_search_missing")
        searches = []
    discovered = _discover(root, searches)
    if not discovered:
        errors.append("no_existing_asset_search_results")

    candidates = review.get("candidate_assets")
    if not isinstance(candidates, list):
        candidates = []
        errors.append("candidate_assets_missing")

    candidate_paths: Set[str] = set()
    invalid_candidates: List[str] = []
    missing_candidate_files: List[str] = []
    for index, candidate in enumerate(candidates):
        path = str(candidate.get("path", "")).strip()
        decision = candidate.get("decision")
        reason = str(candidate.get("reason", "")).strip()
        capabilities = candidate.get("covered_capabilities")
        if not path:
            invalid_candidates.append(f"candidate_{index}:path_missing")
            continue
        candidate_paths.add(path)
        if decision not in ALLOWED_DECISIONS:
            invalid_candidates.append(f"{path}:decision_invalid")
        if not reason:
            invalid_candidates.append(f"{path}:reason_missing")
        if not isinstance(capabilities, list) or not capabilities:
            invalid_candidates.append(f"{path}:covered_capabilities_missing")
        try:
            if not _safe_relative(root, path).is_file():
                missing_candidate_files.append(path)
        except ValueError:
            missing_candidate_files.append(path)

    undispositioned = sorted(discovered - candidate_paths)
    if undispositioned:
        errors.append("discovered_assets_without_disposition")
    if invalid_candidates:
        errors.append("invalid_candidate_disposition")
    if missing_candidate_files:
        errors.append("candidate_asset_file_missing")

    proposed = review.get("proposed_changes")
    if not isinstance(proposed, list):
        proposed = []
        errors.append("proposed_changes_missing")
    invalid_changes: List[str] = []
    for index, change in enumerate(proposed):
        path = str(change.get("path", "")).strip()
        change_type = change.get("change_type")
        gap = str(change.get("gap", "")).strip()
        based_on = change.get("based_on", [])
        label = path or f"change_{index}"
        if not path:
            invalid_changes.append(f"{label}:path_missing")
        if change_type not in ALLOWED_CHANGE_TYPES:
            invalid_changes.append(f"{label}:change_type_invalid")
        if not gap:
            invalid_changes.append(f"{label}:gap_missing")
        if change_type in {"extend_existing", "new_asset"}:
            if not isinstance(based_on, list) or not based_on:
                invalid_changes.append(f"{label}:reuse_basis_missing")
            elif set(based_on) - candidate_paths:
                invalid_changes.append(f"{label}:reuse_basis_unknown")
    if invalid_changes:
        errors.append("invalid_proposed_change")

    if review.get("review_confirmed") is not True:
        errors.append("reuse_review_not_confirmed")

    return {
        "schema_version": 1,
        "status": "passed" if not errors else "blocked",
        "feature": review.get("feature"),
        "review_sha256": hashlib.sha256(_canonical_json(review)).hexdigest(),
        "discovered_asset_paths": sorted(discovered),
        "candidate_asset_paths": sorted(candidate_paths),
        "undispositioned_asset_paths": undispositioned,
        "invalid_candidates": invalid_candidates,
        "missing_candidate_files": sorted(set(missing_candidate_files)),
        "invalid_changes": invalid_changes,
        "error_codes": sorted(set(errors)),
    }
