"""Fail-closed handoff from bounded exploration to repeatable automation.

This checks artifact identity and attestations, not the semantic truth of a video,
reviewer's judgment, a product rule or a fabricated execution receipt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _artifact(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, dict) or not value.get("path"):
        errors.append(f"{label}_missing")
        return None
    raw = Path(str(value["path"]))
    if raw.is_absolute() or ".." in raw.parts:
        errors.append(f"{label}_unsafe_path")
        return None
    root = root.resolve()
    path = (root / raw).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        errors.append(f"{label}_missing")
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != value.get("sha256"):
        errors.append(f"{label}_hash_mismatch")
        return None
    return path


def _receipt(root: Path, value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    path = _artifact(root, value, label, errors)
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (UnicodeError, json.JSONDecodeError):
        pass
    errors.append(f"{label}_invalid")
    return {}


def check_exploration_handoff(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    """Check a run-local plan before repeating work or closing claimed evidence.

    Always evaluate a concrete run; a passing receipt is not authorization for a
    business write, review approval or proof of product acceptance.
    """
    errors: list[str] = []
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {"schema_version": 1, "status": "blocked", "error_codes": ["invalid_contract"]}
    feature = str(payload.get("feature") or "").strip()
    if not feature or not str(payload.get("run_id") or "").strip():
        errors.append("run_identity_missing")
    if payload.get("phase") not in {"preflight", "closure"}:
        errors.append("invalid_phase")
    if payload.get("purpose") not in {"first_exploration", "repeat_execution"}:
        errors.append("invalid_purpose")
    if payload.get("mode") not in {"rapid", "standard"}:
        errors.append("invalid_mode")

    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("exploration_questions_missing")
        questions = []
    seen: set[str] = set()
    for item in questions:
        if not isinstance(item, dict):
            errors.append("exploration_question_invalid")
            continue
        key = str(item.get("id") or "").strip()
        if not key or key in seen or not str(item.get("unknown") or "").strip():
            errors.append("exploration_question_invalid")
        seen.add(key)
        state = item.get("status")
        if state == "implemented":
            _artifact(root, item.get("asset"), "exploration_asset", errors)
        elif state == "not_applicable":
            if not str(item.get("reason") or "").strip():
                errors.append("exploration_exclusion_reason_missing")
        elif state == "blocked":
            if not str(item.get("reason") or "").strip():
                errors.append("exploration_block_reason_missing")
            errors.append("exploration_question_open")
        else:
            errors.append("exploration_question_open")

    runner = payload.get("runner")
    if not isinstance(runner, dict):
        errors.append("runner_missing")
        runner = {}
    else:
        runner_path = _artifact(root, runner, "runner", errors)
        if runner_path and runner_path.suffix not in {".ts", ".js", ".mjs", ".py", ".ad"}:
            errors.append("runner_not_executable")
        proof = _receipt(root, runner.get("validation_receipt"), "runner_validation_receipt", errors)
        if (proof.get("status") != "passed" or proof.get("feature") != feature
                or proof.get("runner_sha256") != runner.get("sha256")
                or not isinstance(proof.get("tests_passed"), int)
                or proof.get("tests_passed", 0) <= 0
                or not str(proof.get("test_scope") or "").strip()):
            errors.append("runner_validation_not_passed")
        backup = _receipt(root, runner.get("remote_backup_receipt"), "remote_backup", errors)
        if (backup.get("status") != "passed" or backup.get("runner_sha256") != runner.get("sha256")
                or not str(backup.get("revision") or "").strip()):
            errors.append("remote_backup_not_verified")
    _artifact(root, payload.get("oracle"), "oracle", errors)

    plan = payload.get("evidence_plan")
    if not isinstance(plan, dict):
        plan = {}
    if plan.get("video") != "continuous_on":
        errors.append("continuous_video_not_planned")
    if plan.get("error_capture") != "on_visible_notice":
        errors.append("error_screenshot_not_planned")
    assertions = plan.get("assertion_ids")
    if (not isinstance(assertions, list) or not assertions
            or any(not isinstance(item, str) or not item.strip() for item in assertions)
            or len(assertions) != len(set(assertions))):
        errors.append("assertion_evidence_plan_missing")
        assertions = []

    if payload.get("phase") == "closure":
        evidence = payload.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        videos = evidence.get("videos", [])
        if not isinstance(videos, list) or not videos:
            errors.append("video_evidence_missing")
        else:
            for item in videos:
                _artifact(root, item, "video_evidence", errors)
                if item.get("quality") != "passed" or item.get("semantic_review") != "passed":
                    errors.append("video_content_unverified")
        shots = evidence.get("screenshots", [])
        if not isinstance(shots, list):
            shots = []
        for assertion in assertions:
            matched = [shot for shot in shots if isinstance(shot, dict) and shot.get("assertion_id") == assertion]
            if not matched:
                errors.append("assertion_screenshot_missing")
            for item in matched:
                _artifact(root, item, "assertion_screenshot", errors)
                if item.get("content_review") != "passed":
                    errors.append("screenshot_content_unverified")
                if item.get("kind") == "error_notice" and item.get("prompt_visible") is not True:
                    errors.append("error_prompt_not_visible")
    if payload.get("purpose") == "first_exploration" and errors:
        errors.append("exploration_handoff_incomplete")
    return {
        "schema_version": 1,
        "status": "blocked" if errors else "passed",
        "phase": payload.get("phase"),
        "purpose": payload.get("purpose"),
        "feature": feature,
        "run_id": payload.get("run_id"),
        "error_codes": sorted(set(errors)),
        "interpretation": "artifact/evidence gate only; no business write authorization or formal product verdict",
    }
