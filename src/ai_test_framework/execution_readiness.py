"""Deterministic planning and pre-execution readiness gates."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional


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

CONFIRMATION_FIELDS = {
    "scope_confirmed": "scope_not_confirmed",
    "environment_confirmed": "environment_not_confirmed",
    "account_roles_confirmed": "account_roles_not_confirmed",
    "data_plan_confirmed": "data_plan_not_confirmed",
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


def _without_derived_hash(plan: Dict[str, Any]) -> Dict[str, Any]:
    value = copy.deepcopy(plan)
    value.pop("plan_sha256", None)
    return value


def plan_sha256(plan: Dict[str, Any]) -> str:
    """Hash the plan without its derived hash field."""

    return hashlib.sha256(_canonical_json(_without_derived_hash(plan))).hexdigest()


def _require_keys(value: Dict[str, Any], keys: Iterable[str]) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise ValueError("missing_fields:" + ",".join(missing))


def _case_ids(plan: Dict[str, Any]) -> List[str]:
    return list(plan.get("automation_scope", {}).get("case_ids", []))


def build_readiness_plan(source: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and freeze a requirement-stage automation readiness plan."""

    _assert_no_sensitive_fields(source)
    _require_keys(
        source,
        [
            "schema_version",
            "plan_id",
            "requirement_baseline_id",
            "feature",
            "automation_scope",
            "case_requirements",
            "account_requirements",
            "fixture_requirements",
            "evidence_plan",
        ],
    )
    if source["schema_version"] != 1:
        raise ValueError("unsupported_schema_version")

    plan = copy.deepcopy(source)
    plan.setdefault("manual_only_case_ids", [])
    plan.setdefault("open_questions", [])
    plan.setdefault("execution_target_requirements", [])
    plan.setdefault("hardware_fixture_requirements", [])
    plan["status"] = "planned"

    case_ids = _case_ids(plan)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate_case_id")
    requirements = {item.get("case_id"): item for item in plan["case_requirements"]}
    if set(case_ids) != set(requirements):
        raise ValueError("case_requirements_must_match_scope")

    manual_only = set(plan["manual_only_case_ids"])
    unknown_manual = manual_only - set(case_ids)
    if unknown_manual:
        raise ValueError("unknown_manual_only_case_id:" + ",".join(sorted(unknown_manual)))

    target_ids = [item.get("target_id") for item in plan["execution_target_requirements"]]
    if any(not target_id for target_id in target_ids):
        raise ValueError("missing_execution_target_id")
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("duplicate_execution_target_id")
    hardware_ids = [
        item.get("hardware_fixture_id") for item in plan["hardware_fixture_requirements"]
    ]
    if any(not fixture_id for fixture_id in hardware_ids):
        raise ValueError("missing_hardware_fixture_id")
    if len(hardware_ids) != len(set(hardware_ids)):
        raise ValueError("duplicate_hardware_fixture_id")

    known_targets = set(target_ids)
    known_hardware = set(hardware_ids)
    known_cases = set(case_ids)
    for target in plan["execution_target_requirements"]:
        unknown_cases = set(target.get("case_ids", [])) - known_cases
        if unknown_cases:
            raise ValueError("unknown_execution_target_case_id:" + ",".join(sorted(unknown_cases)))
    for fixture in plan["hardware_fixture_requirements"]:
        unknown_cases = set(fixture.get("case_ids", [])) - known_cases
        if unknown_cases:
            raise ValueError("unknown_hardware_fixture_case_id:" + ",".join(sorted(unknown_cases)))
    for requirement in plan["case_requirements"]:
        unknown_targets = set(requirement.get("required_execution_target_ids", [])) - known_targets
        if unknown_targets:
            raise ValueError("unknown_execution_target_id:" + ",".join(sorted(unknown_targets)))
        unknown_hardware = set(requirement.get("required_hardware_fixture_ids", [])) - known_hardware
        if unknown_hardware:
            raise ValueError("unknown_hardware_fixture_id:" + ",".join(sorted(unknown_hardware)))

    plan["plan_sha256"] = plan_sha256(plan)
    return plan


def _prerequisite_fingerprint(
    case_id: str,
    missing_roles: List[str],
    missing_fixtures: List[str],
    missing_environments: List[str],
    missing_execution_targets: List[str],
    missing_hardware_fixtures: List[str],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "case_id": case_id,
                "missing_role_ids": missing_roles,
                "missing_fixture_ids": missing_fixtures,
                "missing_environment_ids": missing_environments,
                "missing_execution_target_ids": missing_execution_targets,
                "missing_hardware_fixture_ids": missing_hardware_fixtures,
            }
        )
    ).hexdigest()


def evaluate_execution_readiness(
    plan: Dict[str, Any],
    confirmation: Dict[str, Any],
    previous_missing: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Reconfirm scope/environment/accounts/data and split ready from blocked cases."""

    _assert_no_sensitive_fields(plan)
    _assert_no_sensitive_fields(confirmation)
    _require_keys(
        confirmation,
        [
            "schema_version",
            "plan_id",
            "plan_sha256",
            "target_environment",
            "scope_confirmed",
            "environment_confirmed",
            "account_roles_confirmed",
            "data_plan_confirmed",
            "available_role_ids",
            "ready_fixture_ids",
            "excluded_case_ids",
        ],
    )

    error_codes: List[str] = []
    expected_hash = plan_sha256(plan)
    if confirmation["plan_sha256"] != expected_hash:
        error_codes.append("plan_hash_mismatch")
    if confirmation["plan_id"] != plan.get("plan_id"):
        error_codes.append("plan_id_mismatch")
    for field, code in CONFIRMATION_FIELDS.items():
        if confirmation.get(field) is not True:
            error_codes.append(code)
    if plan.get("execution_target_requirements") and confirmation.get(
        "execution_targets_confirmed"
    ) is not True:
        error_codes.append("execution_targets_not_confirmed")
    if plan.get("hardware_fixture_requirements") and confirmation.get(
        "hardware_fixtures_confirmed"
    ) is not True:
        error_codes.append("hardware_fixtures_not_confirmed")

    gate_blocked = bool(error_codes)
    if gate_blocked:
        return {
            "schema_version": 1,
            "status": "blocked",
            "plan_id": plan.get("plan_id"),
            "plan_sha256": expected_hash,
            "target_environment": confirmation.get("target_environment"),
            "ready_case_ids": [],
            "blocked_cases": [],
            "excluded_case_ids": sorted(set(confirmation.get("excluded_case_ids", []))),
            "missing_prerequisites": list(previous_missing or []),
            "error_codes": sorted(set(error_codes)),
        }

    available_roles = set(confirmation["available_role_ids"])
    ready_fixtures = set(confirmation["ready_fixture_ids"])
    available_execution_targets = set(confirmation.get("available_execution_target_ids", []))
    ready_hardware_fixtures = set(confirmation.get("ready_hardware_fixture_ids", []))
    target_environment = confirmation["target_environment"]
    excluded = set(confirmation["excluded_case_ids"]) | set(plan.get("manual_only_case_ids", []))
    previous_by_fingerprint = {
        item.get("prerequisite_fingerprint"): copy.deepcopy(item)
        for item in (previous_missing or [])
        if item.get("prerequisite_fingerprint")
    }

    ready: List[str] = []
    blocked: List[Dict[str, Any]] = []
    missing_ledger: List[Dict[str, Any]] = []
    for requirement in plan.get("case_requirements", []):
        case_id = requirement["case_id"]
        if case_id in excluded:
            continue
        missing_roles = sorted(set(requirement.get("required_role_ids", [])) - available_roles)
        missing_fixtures = sorted(set(requirement.get("required_fixture_ids", [])) - ready_fixtures)
        required_environments = set(requirement.get("required_environment_ids", []))
        missing_environments = [] if target_environment in required_environments else sorted(required_environments)
        missing_execution_targets = sorted(
            set(requirement.get("required_execution_target_ids", []))
            - available_execution_targets
        )
        missing_hardware_fixtures = sorted(
            set(requirement.get("required_hardware_fixture_ids", []))
            - ready_hardware_fixtures
        )
        if not (
            missing_roles
            or missing_fixtures
            or missing_environments
            or missing_execution_targets
            or missing_hardware_fixtures
        ):
            ready.append(case_id)
            continue

        fingerprint = _prerequisite_fingerprint(
            case_id,
            missing_roles,
            missing_fixtures,
            missing_environments,
            missing_execution_targets,
            missing_hardware_fixtures,
        )
        blocked.append(
            {
                "case_id": case_id,
                "missing_role_ids": missing_roles,
                "missing_fixture_ids": missing_fixtures,
                "missing_environment_ids": missing_environments,
                "missing_execution_target_ids": missing_execution_targets,
                "missing_hardware_fixture_ids": missing_hardware_fixtures,
                "execution_action": "skip_without_retry",
                "resume_condition": "prerequisite_fingerprint_changed",
            }
        )
        ledger_item = previous_by_fingerprint.get(fingerprint)
        if ledger_item is None:
            ledger_item = {
                "case_id": case_id,
                "prerequisite_fingerprint": fingerprint,
                "missing_role_ids": missing_roles,
                "missing_fixture_ids": missing_fixtures,
                "missing_environment_ids": missing_environments,
                "missing_execution_target_ids": missing_execution_targets,
                "missing_hardware_fixture_ids": missing_hardware_fixtures,
                "first_detected_at": confirmation.get("confirmed_at"),
                "retry_count": 0,
                "retry_allowed": False,
                "next_action": "await_prerequisite",
            }
        missing_ledger.append(ledger_item)

    if ready and blocked:
        status = "passed_with_case_blocks"
    elif ready:
        status = "passed"
    else:
        status = "blocked"

    return {
        "schema_version": 1,
        "status": status,
        "plan_id": plan["plan_id"],
        "plan_sha256": expected_hash,
        "target_environment": target_environment,
        "ready_case_ids": ready,
        "blocked_cases": blocked,
        "excluded_case_ids": sorted(excluded),
        "missing_prerequisites": missing_ledger,
        "error_codes": [],
    }
