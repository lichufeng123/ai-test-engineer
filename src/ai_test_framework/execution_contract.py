"""Bind a single Case/rapid probe to existing baseline and runtime receipts.

These are local consistency gates, not attestation of independently reviewed
requirements, real browser observations, or a user's actual consent.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .execution_readiness import _assert_no_sensitive_fields, plan_sha256
from .environment_profile import IDENTITY, _date


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _artifact(root: Path, ref: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(ref, dict) or not isinstance(ref.get("sha256"), str) or len(ref["sha256"]) != 64 or not isinstance(ref.get("path"), str):
        errors.append(label + "_reference_invalid")
        return None
    raw = Path(ref["path"])
    if not ref["path"] or raw.is_absolute() or ".." in raw.parts:
        errors.append(label + "_path_unsafe")
        return None
    target = (root / raw).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        errors.append(label + "_missing")
        return None
    try:
        hasher = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        if hasher.hexdigest() != ref["sha256"]:
            errors.append(label + "_hash_mismatch")
            return None
    except OSError:
        errors.append(label + "_unreadable")
        return None
    return target


def _json(path: Path | None, label: str, errors: list[str]) -> Any:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError, OSError):
        errors.append(label + "_invalid_json")
        return None


def _id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def check_execution_probe(probe: Any, root: Path, *, allow_finished: bool = False) -> dict[str, Any]:
    """Freeze existing baseline/charter; optionally recheck after run closure (read-only)."""
    errors: list[str] = []
    if not isinstance(probe, dict) or probe.get("schema_version") != 1:
        return {"status": "blocked", "error_codes": ["probe_invalid"]}
    try:
        _assert_no_sensitive_fields(probe)
    except ValueError:
        return {"status": "blocked", "error_codes": ["probe_contains_sensitive_field"]}
    root = Path(root).resolve()
    run_id, case_id = probe.get("run_id"), probe.get("case_id")
    if not _id(run_id) or not _id(case_id):
        errors.append("run_or_case_id_missing")
    mode = probe.get("mode")
    if mode not in {"standard", "rapid"}:
        errors.append("mode_invalid")
    baseline = probe.get("baseline")
    baseline_ref = baseline if isinstance(baseline, dict) else {}
    baseline_file = _artifact(root, baseline, "baseline", errors)
    baseline_data = _json(baseline_file, "baseline", errors) if mode == "standard" else None
    if not isinstance(baseline, dict) or not _id(baseline.get("id")) or baseline.get("status") != ("approved" if mode == "standard" else "provisional"):
        errors.append("baseline_status_or_id_invalid")
    if mode == "standard":
        if not isinstance(baseline_data, dict) or baseline_data.get("baseline_id") != baseline_ref.get("id"):
            errors.append("baseline_identity_mismatch")
        else:
            matches = [case for case in baseline_data.get("cases", []) if isinstance(case, dict) and case.get("id") == case_id] if isinstance(baseline_data.get("cases"), list) else []
            if len(matches) != 1:
                errors.append("case_not_unique_in_baseline")
            else:
                required = matches[0].get("covered_rule_ids")
                asserted = probe.get("assertion_ids")
                if (not isinstance(required, list) or not required or not isinstance(asserted, list)
                        or any(not _id(x) for x in required + asserted)
                        or len(asserted) != len(set(asserted)) or set(required) != set(asserted)):
                    errors.append("assertion_ids_differ_from_baseline")
    else:
        asserted = probe.get("assertion_ids")
        if not isinstance(asserted, list) or not asserted or any(not _id(a) for a in asserted) or len(asserted) != len(set(asserted)):
            errors.append("rapid_probe_assertions_invalid")
    readiness = _json(_artifact(root, probe.get("readiness_receipt"), "readiness", errors), "readiness", errors)
    if (not isinstance(readiness, dict) or readiness.get("status") not in {"passed", "passed_with_case_blocks"}
            or not isinstance(readiness.get("ready_case_ids"), list) or case_id not in readiness["ready_case_ids"]):
        errors.append("case_not_ready")
    plan = _json(_artifact(root, probe.get("plan"), "plan", errors), "plan", errors)
    if (not isinstance(readiness, dict) or not isinstance(plan, dict)
            or readiness.get("plan_sha256") != probe.get("plan_sha256")
            or plan_sha256(plan) != probe.get("plan_sha256")
            or readiness.get("plan_id") != plan.get("plan_id")):
        errors.append("plan_hash_mismatch")
    scope = plan.get("automation_scope") if isinstance(plan, dict) else None
    if not isinstance(scope, dict) or not isinstance(scope.get("case_ids"), list) or case_id not in scope["case_ids"]:
        errors.append("case_not_in_plan")
    environment = _json(_artifact(root, probe.get("environment_receipt"), "environment", errors), "environment", errors)
    if not isinstance(environment, dict) or environment.get("status") != "passed" or environment.get("scope") != "identity_and_capability_only":
        errors.append("environment_not_resolved")
    profile = _json(_artifact(root, probe.get("profile"), "profile", errors), "profile", errors)
    if (not isinstance(environment, dict) or not isinstance(profile, dict)
            or environment.get("profile_sha256") != probe.get("profile_sha256")
            or digest(profile) != probe.get("profile_sha256")):
        errors.append("profile_hash_mismatch")
    if not allow_finished:
        now = datetime.now(timezone.utc)
        observed_at = _date(environment.get("observed_at")) if isinstance(environment, dict) else None
        expires_at = _date(profile.get("expires_at")) if isinstance(profile, dict) else None
        if (not observed_at or (now - observed_at).total_seconds() > 120
                or (observed_at - now).total_seconds() > 30 or not expires_at or expires_at <= now):
            errors.append("environment_observation_stale")
    oracle = probe.get("oracle")
    if _artifact(root, oracle, "oracle", errors) is None:
        errors.append("oracle_artifact_missing")
    fixture, action = probe.get("fixture"), probe.get("action")
    if not isinstance(fixture, dict) or not all(_id(fixture.get(key)) for key in ("id", "business_key")) or not _hash(fixture.get("pre_state_sha256")) or fixture.get("match_count") != 1:
        errors.append("fixture_not_unique_or_unfrozen")
    if not isinstance(action, dict) or not _id(action.get("id")) or action.get("kind") not in {"read", "write"} or not _hash(action.get("input_sha256")):
        errors.append("action_not_frozen")
    # The run log must have been opened before the first test action.
    history = _json(root / ".ai-test/execution_history.json", "run_history", errors)
    runs = [run for item in history.get("automations", []) if isinstance(item, dict)
            for run in item.get("runs", []) if isinstance(run, dict) and run.get("run_id") == run_id] if isinstance(history, dict) else []
    accepted_statuses = {"started"} | ({"passed", "partial", "failed", "blocked", "interrupted"} if allow_finished else set())
    if len(runs) != 1 or runs[0].get("status") not in accepted_statuses or runs[0].get("baseline") != baseline_ref.get("id"):
        errors.append("run_not_started_for_baseline")
    return {
        "schema_version": 1, "status": "blocked" if errors else "passed", "error_codes": sorted(set(errors)),
        "scope": "local_probe_consistency_only", "run_id": run_id, "case_id": case_id,
        "probe_sha256": digest(probe),
    }


def reserve_write_intent(probe: Any, observation: Any, approval: Any, root: Path) -> dict[str, Any]:
    """Atomically reserve one target; unknown outcome stays reserved, never retry.

    Must be called directly before the UI write, after a fresh actual readback.
    The local approval is an auditable declaration, not cryptographic consent.
    """
    checked = check_execution_probe(probe, root)
    if checked["status"] != "passed":
        return {"status": "blocked", "error_codes": checked["error_codes"]}
    if not isinstance(probe, dict) or probe["action"]["kind"] != "write":
        return {"status": "blocked", "error_codes": ["not_a_write_action"]}
    if not isinstance(observation, dict) or not isinstance(approval, dict):
        return {"status": "blocked", "error_codes": ["observation_or_approval_missing"]}
    for item in (observation, approval):
        try:
            _assert_no_sensitive_fields(item)
        except ValueError:
            return {"status": "blocked", "error_codes": ["sensitive_field_forbidden"]}
    identity = ("run_id", "case_id")
    fields = ("id", "business_key", "pre_state_sha256")
    target = probe["fixture"]
    action = probe["action"]
    errors = []
    if any(observation.get(k) != probe[k] or approval.get(k) != probe[k] for k in identity):
        errors.append("run_case_drift")
    if any(observation.get(k) != target[k] for k in fields) or observation.get("match_count") != 1:
        errors.append("fixture_identity_or_prestate_drift")
    profile_errors: list[str] = []
    profile = _json(_artifact(Path(root).resolve(), probe.get("profile"), "profile", profile_errors), "profile", profile_errors)
    if (not isinstance(profile, dict) or profile.get("stage") != "local" or profile.get("zone") != "synthetic"):
        errors.append("business_authorization_adapter_missing")
    if observation.get("profile_sha256") != probe["profile_sha256"] or not isinstance(profile, dict) or any(observation.get(key) != profile.get(key) for key in IDENTITY):
        errors.append("environment_drift")
    now = datetime.now(timezone.utc)
    observed_at = _date(observation.get("observed_at"))
    if not observed_at or (now - observed_at).total_seconds() > 120 or (observed_at - now).total_seconds() > 30:
        errors.append("prewrite_observation_stale")
    approved_at, expires_at = _date(approval.get("approved_at")), _date(approval.get("expires_at"))
    if not approved_at or not expires_at or approved_at > now or expires_at <= now or (now - approved_at).total_seconds() > 120:
        errors.append("approval_receipt_stale")
    if (approval.get("status") != "approved" or not _id(approval.get("approved_by"))
            or approval.get("action_id") != action["id"] or approval.get("business_key") != target["business_key"]
            or approval.get("input_sha256") != action["input_sha256"]
            or approval.get("probe_sha256") != checked["probe_sha256"]):
        errors.append("write_approval_unbound")
    if errors:
        return {"status": "blocked", "error_codes": sorted(set(errors))}
    root = Path(root).resolve()
    lock_dir = root / ".ai-test/write-intents"
    lock_dir.mkdir(parents=True, exist_ok=True)
    # Deliberately reserve across runs: no auto-release even if the runner crashes.
    fingerprint = digest({"key": target["business_key"]})
    path = lock_dir / (fingerprint + ".json")
    receipt = {"schema_version": 1, "status": "reserved", "run_id": probe["run_id"],
               "case_id": probe["case_id"], "action_id": action["id"],
               "probe_sha256": checked["probe_sha256"], "target_fingerprint": fingerprint,
               "scope": "single_local_write_intent_only"}
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {"status": "blocked", "error_codes": ["target_already_reserved_manual_reconcile"]}
    except OSError:
        return {"status": "blocked", "error_codes": ["intent_store_unavailable"]}
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        # Preserve the reservation even if writing its body fails; never auto-retry.
        return {"status": "blocked", "error_codes": ["intent_record_incomplete_manual_reconcile"]}
    return receipt
