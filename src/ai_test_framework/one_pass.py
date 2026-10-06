"""Structural gate for an unreviewed, end-to-end one-pass test run.

This never executes product actions, approves business expectations, or promotes
provisional cases to the formal baseline. It checks a frozen display plan and
its one-to-one step results so a one-pass report cannot silently omit cases.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

STATUSES = {"passed", "failed", "blocked", "not_executed"}


def _required(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _list(value: Any, field: str) -> list:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a nonempty list")
    return value


def _file(root: Path, raw: str, field: str) -> Path:
    path = (root / _required(raw, field)).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"{field} is missing or outside the project root")
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_plan(plan: dict, root: Path) -> tuple[dict[str, dict], list[str]]:
    if plan.get("schema_version") != 1 or plan.get("mode") != "one_pass" or plan.get("result_authority") != "provisional":
        raise ValueError("plan must be one_pass with provisional result authority")
    for key in ("run_id", "requirement_id", "feature", "environment", "platform"):
        _required(plan.get(key), key)
    scope = plan.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope is required")
    for key in ("included", "excluded"):
        values = scope.get(key)
        if not isinstance(values, list) or (key == "included" and not values):
            raise ValueError(f"scope.{key} must be a list")
        for value in values:
            _required(value, f"scope.{key}")
    kinds = set()
    read_sources = set()
    for item in _list(plan.get("knowledge_context"), "knowledge_context"):
        if not isinstance(item, dict):
            raise ValueError("knowledge_context entries must be objects")
        kind = _required(item.get("kind"), "knowledge.kind")
        kinds.add(kind)
        if item.get("read_status") == "read":
            path = _file(root, item.get("path"), "knowledge.path")
            if item.get("sha256") != _hash(path):
                raise ValueError(f"knowledge hash mismatch: {kind}")
            read_sources.add(item["path"])
        elif item.get("read_status") == "unavailable":
            _required(item.get("reason"), "knowledge.unavailable.reason")
        else:
            raise ValueError("knowledge must be read or explicitly unavailable")
    if "omission_risk" not in kinds:
        raise ValueError("omission-risk rules must be loaded or explicitly unavailable")
    cases: dict[str, dict] = {}
    ready: list[str] = []
    for case in _list(plan.get("cases"), "cases"):
        if not isinstance(case, dict):
            raise ValueError("case must be an object")
        case_id = _required(case.get("case_id"), "case_id")
        if case_id in cases or not case_id.startswith("OP-"):
            raise ValueError("temporary case IDs must be unique OP-* IDs")
        cases[case_id] = case
        for key in ("title", "source_ref", "role", "write_boundary"):
            _required(case.get(key), f"{case_id}.{key}")
        readiness = case.get("readiness", "ready")
        expectation_status = case.get("expectation_status")
        if expectation_status not in {"confirmed", "unknown"}:
            raise ValueError(f"{case_id}: expectation_status must be confirmed or unknown")
        if readiness == "ready" and (expectation_status != "confirmed" or
                                      not any(case["source_ref"].startswith(ref + "#") or case["source_ref"] == ref
                                              for ref in read_sources)):
            raise ValueError(f"{case_id}: ready expectation must cite a read knowledge source")
        fixture = case.get("fixture")
        if not isinstance(fixture, dict):
            raise ValueError(f"{case_id}.fixture is required")
        for key in ("id", "unique_locator", "scope"):
            _required(fixture.get(key), f"{case_id}.fixture.{key}")
        for item in _list(case.get("preconditions"), f"{case_id}.preconditions"):
            _required(item, f"{case_id}.precondition")
        for item in _list(case.get("stop_conditions"), f"{case_id}.stop_conditions"):
            _required(item, f"{case_id}.stop_condition")
        ids = set()
        for step in _list(case.get("steps"), f"{case_id}.steps"):
            if not isinstance(step, dict):
                raise ValueError(f"{case_id}: step must be an object")
            step_id = _required(step.get("step_id"), f"{case_id}.step_id")
            if step_id in ids:
                raise ValueError(f"{case_id}: duplicate step ID")
            ids.add(step_id)
            for key in ("action", "expected"):
                _required(step.get(key), f"{case_id}/{step_id}.{key}")
            oracle = step.get("oracle")
            if not isinstance(oracle, dict) or oracle.get("independent") is not True:
                raise ValueError(f"{case_id}/{step_id}: independent Oracle is required")
            _required(oracle.get("source_ref"), f"{case_id}/{step_id}.oracle.source_ref")
            for item in _list(step.get("evidence_plan"), f"{case_id}/{step_id}.evidence_plan"):
                _required(item, f"{case_id}/{step_id}.evidence")
        if readiness == "blocked":
            _required(case.get("blocker"), f"{case_id}.blocker")
        elif readiness == "ready":
            ready.append(case_id)
        else:
            raise ValueError(f"{case_id}: unknown readiness")
    return cases, ready


def _check_results(plan: dict, results: dict, root: Path, plan_path: Path, cases: dict[str, dict]) -> dict[str, str]:
    if (results.get("schema_version") != 1 or results.get("run_id") != plan["run_id"]
            or results.get("plan_sha256") != _hash(_file(root, str(plan_path), "plan_path"))):
        raise ValueError("result must bind to the same run and frozen plan SHA-256")
    entries = _list(results.get("cases"), "results.cases")
    ids = [entry.get("case_id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(entries) or len(set(ids)) != len(ids) or set(ids) != set(cases):
        raise ValueError("every planned case needs exactly one result")
    statuses = {}
    run_dir = (root / "runs" / plan["run_id"]).resolve()
    for entry in entries:
        case_id = entry["case_id"]
        status = entry.get("status")
        if status not in STATUSES:
            raise ValueError(f"{case_id}: invalid result status")
        if cases[case_id].get("readiness") == "blocked" and status not in {"blocked", "not_executed"}:
            raise ValueError(f"{case_id}: blocked case cannot be promoted to passed or failed")
        if status in {"failed", "blocked", "not_executed"}:
            _required(entry.get("reason"), f"{case_id}.reason")
        planned_steps = {step["step_id"] for step in cases[case_id]["steps"]}
        steps = _list(entry.get("steps"), f"{case_id}.result.steps")
        actual_ids = [step.get("step_id") for step in steps if isinstance(step, dict)]
        if len(actual_ids) != len(steps) or len(set(actual_ids)) != len(actual_ids) or set(actual_ids) != planned_steps:
            raise ValueError(f"{case_id}: all steps require a result")
        step_statuses = []
        for step in steps:
            step_id = step["step_id"]
            state = step.get("status")
            if state not in STATUSES:
                raise ValueError(f"{case_id}/{step_id}: invalid step status")
            step_statuses.append(state)
            if state in {"passed", "failed"}:
                _required(step.get("actual"), f"{case_id}/{step_id}.actual")
                for evidence in _list(step.get("evidence_refs"), f"{case_id}/{step_id}.evidence_refs"):
                    path = _file(root, evidence, f"{case_id}/{step_id}.evidence")
                    if not path.is_relative_to(run_dir):
                        raise ValueError(f"{case_id}/{step_id}: historical or unrelated evidence")
            else:
                for evidence in step.get("evidence_refs", []):
                    _file(root, evidence, f"{case_id}/{step_id}.evidence")
        if status == "passed" and any(value != "passed" for value in step_statuses):
            raise ValueError(f"{case_id}: a passed case contains incomplete steps")
        if status == "failed" and "failed" not in step_statuses:
            raise ValueError(f"{case_id}: failed case has no failed step")
        if status == "blocked" and ("failed" in step_statuses or all(value == "passed" for value in step_statuses)):
            raise ValueError(f"{case_id}: blocked case must have an incomplete step")
        if status == "not_executed" and any(value != "not_executed" for value in step_statuses):
            raise ValueError(f"{case_id}: not_executed case contains executed steps")
        statuses[case_id] = status
    return statuses


def check_one_pass(plan: dict, root: Path, *, results: Optional[dict] = None,
                   plan_path: Optional[Path] = None) -> Dict[str, Any]:
    """Check structure and local hashes; do not execute or approve a product result."""
    root = Path(root).resolve()
    try:
        cases, ready = _check_plan(plan, root)
        if results is not None:
            if plan_path is None:
                raise ValueError("closure requires the frozen plan file")
            statuses = _check_results(plan, results, root, Path(plan_path), cases)
            details = {}
            by_id = {entry["case_id"]: entry for entry in results["cases"]}
            for case_id, case in cases.items():
                entry = by_id[case_id]
                observed_steps = {step["step_id"]: step for step in entry["steps"]}
                details[case_id] = {
                    "title": case["title"], "role": case["role"], "fixture_id": case["fixture"]["id"],
                    "status": entry["status"], "reason": entry.get("reason"),
                    "steps": [{"action": step["action"], "expected": step["expected"],
                               "status": observed_steps[step["step_id"]]["status"],
                               "actual": observed_steps[step["step_id"]].get("actual"),
                               "evidence_refs": observed_steps[step["step_id"]].get("evidence_refs", [])}
                              for step in case["steps"]],
                }
            return {"status": "checked", "phase": "closure", "run_id": plan["run_id"],
                    "case_count": len(cases), "case_results": statuses, "case_details": details,
                    "result_authority": "provisional", "semantic_evidence_review": "not_performed",
                    "notice": "Consistency and file existence only; not business acceptance or release approval."}
        if not ready:
            raise ValueError("all cases blocked; only independent context work can proceed")
        preview = [{"case_id": case_id, "title": case["title"], "role": case["role"],
                    "fixture_id": case["fixture"]["id"], "readiness": case.get("readiness", "ready"),
                    "blocker": case.get("blocker"), "steps": [
                        {"action": step["action"], "expected": step["expected"]} for step in case["steps"]]}
                   for case_id, case in cases.items()]
        return {"status": "ready", "phase": "preflight", "run_id": plan["run_id"],
                "case_count": len(cases), "case_preview": preview, "ready_case_ids": ready,
                "blocked_case_ids": sorted(set(cases) - set(ready)),
                "result_authority": "provisional",
                "notice": "A checked plan is not authorization, current product knowledge or an approved baseline."}
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {"status": "blocked", "error_codes": ["one_pass_contract_invalid"], "reason": str(error),
                "result_authority": "provisional"}
