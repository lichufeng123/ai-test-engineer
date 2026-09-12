"""Deterministic contracts for business-flow rules and end-to-end case coverage."""

from __future__ import annotations

import re
from typing import Any


FLOW_ID = re.compile(r"^BF-[A-Z0-9]+-\d{3}$")
TOPOLOGY_TYPES = {"isolated", "linked_confirmed", "linked_candidate", "pending"}
CONFIRMED_STATUSES = {"confirmed", "已确认"}
FLOW_STATUSES = CONFIRMED_STATUSES | {"pending", "risk", "待确认", "带风险"}
PRIORITIES = {"P0", "P1", "P2"}
FLOW_FIELDS = {
    "id", "name", "priority", "status", "trigger", "actors", "platforms",
    "preconditions", "start_state", "end_state", "steps", "failure_branches",
    "source_refs",
}
STEP_FIELDS = {
    "sequence", "actor", "event", "owner_module_id", "related_module_ids",
    "from_state", "to_state", "observable_output", "covered_assertion_ids",
}


def _string_ids(rows: Any, key: str) -> set[str]:
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get(key))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get(key), str) and row.get(key)
    }


def _add(errors: list[dict[str, Any]], code: str, message: str, **details: Any) -> None:
    errors.append({"code": code, "message": message, **details})


def _result(errors: list[dict[str, Any]], **values: Any) -> dict[str, Any]:
    return {
        "status": "failed" if errors else "passed",
        "errors": errors,
        "error_codes": sorted({error["code"] for error in errors}),
        **values,
    }


def check_business_flows(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate topology, flow structure, and flow-to-assertion references."""
    errors: list[dict[str, Any]] = []
    if payload.get("business_flow_contract_version") != 1:
        _add(errors, "unsupported_contract_version", "business_flow_contract_version must be 1")

    topology = payload.get("business_topology")
    if not isinstance(topology, dict):
        _add(errors, "missing_business_topology", "business_topology must be an object")
        topology = {}
    classification = topology.get("classification")
    if classification not in TOPOLOGY_TYPES:
        _add(errors, "invalid_topology_classification", "business topology classification is invalid")
    for field in (
        "confirmed_module_ids", "confirmed_platforms", "candidate_links",
        "excluded_links", "basis",
    ):
        if not isinstance(topology.get(field), list):
            _add(errors, "invalid_topology_field", f"business_topology.{field} must be an array", field=field)

    assertions = _string_ids(payload.get("assertions"), "id")
    flows = payload.get("business_flows")
    if not isinstance(flows, list):
        _add(errors, "invalid_business_flows", "business_flows must be an array")
        flows = []
    confirmed = [
        flow for flow in flows
        if isinstance(flow, dict) and flow.get("status") in CONFIRMED_STATUSES
    ]
    if classification == "linked_confirmed" and not confirmed:
        _add(
            errors,
            "linked_confirmed_requires_confirmed_flow",
            "linked_confirmed topology requires at least one confirmed business flow",
        )
    if classification == "isolated" and not flows:
        _add(
            errors,
            "isolated_requires_local_flow",
            "isolated topology still requires a local business flow",
        )

    seen: set[str] = set()
    matrix: list[dict[str, Any]] = []
    for index, flow in enumerate(flows, 1):
        if not isinstance(flow, dict):
            _add(errors, "invalid_flow", "business flow must be an object", index=index)
            continue
        flow_id = str(flow.get("id") or "")
        if not FLOW_ID.fullmatch(flow_id):
            _add(errors, "invalid_flow_id", "business flow ID is invalid", flow_id=flow_id, index=index)
        elif flow_id in seen:
            _add(errors, "duplicate_flow_id", "business flow ID is duplicated", flow_id=flow_id)
        seen.add(flow_id)
        missing = sorted(FLOW_FIELDS - set(flow))
        if missing:
            _add(errors, "missing_flow_fields", "business flow has missing fields", flow_id=flow_id, fields=missing)
        if flow.get("priority") not in PRIORITIES:
            _add(errors, "invalid_flow_priority", "business flow priority is invalid", flow_id=flow_id)
        if flow.get("status") not in FLOW_STATUSES:
            _add(errors, "invalid_flow_status", "business flow status is invalid", flow_id=flow_id)
        for field in ("actors", "platforms", "preconditions", "failure_branches", "source_refs"):
            if not isinstance(flow.get(field), list):
                _add(errors, "invalid_flow_array", f"{field} must be an array", flow_id=flow_id, field=field)
        if not flow.get("source_refs"):
            _add(errors, "missing_flow_source", "business flow requires source references", flow_id=flow_id)

        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            _add(errors, "missing_flow_steps", "business flow requires at least one step", flow_id=flow_id)
            continue
        covered: set[str] = set()
        for step_index, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                _add(errors, "invalid_flow_step", "business flow step must be an object", flow_id=flow_id, step=step_index)
                continue
            missing_step = sorted(STEP_FIELDS - set(step))
            if missing_step:
                _add(errors, "missing_flow_step_fields", "business flow step has missing fields", flow_id=flow_id, step=step_index, fields=missing_step)
            if step.get("sequence") != step_index:
                _add(errors, "invalid_flow_sequence", "flow step sequence must start at 1 and be continuous", flow_id=flow_id, step=step_index)
            assertion_ids = step.get("covered_assertion_ids")
            if not isinstance(assertion_ids, list) or not assertion_ids:
                _add(errors, "missing_step_assertions", "flow step must reference atomic assertions", flow_id=flow_id, step=step_index)
                continue
            unknown = sorted(set(assertion_ids) - assertions)
            if unknown:
                _add(errors, "unknown_assertion_reference", "flow step references unknown assertions", flow_id=flow_id, step=step_index, assertion_ids=unknown)
            covered.update(str(value) for value in assertion_ids)
        matrix.append({
            "flow_id": flow_id,
            "status": flow.get("status"),
            "step_count": len(steps),
            "assertion_ids": sorted(covered),
        })

    return _result(errors, flow_assertion_matrix=sorted(matrix, key=lambda row: row["flow_id"]))


def check_flow_case_coverage(
    flows: list[dict[str, Any]], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check that cases claiming a flow cover every step assertion."""
    errors: list[dict[str, Any]] = []
    flow_by_id = {
        str(flow.get("id")): flow for flow in flows if isinstance(flow, dict) and flow.get("id")
    }
    coverage: dict[str, list[str]] = {flow_id: [] for flow_id in flow_by_id}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "")
        flow_ids = case.get("covered_flow_ids", [])
        rule_ids = case.get("covered_rule_ids", [])
        if not isinstance(flow_ids, list):
            _add(errors, "invalid_case_flow_ids", "covered_flow_ids must be an array", case_id=case_id)
            continue
        if not isinstance(rule_ids, list):
            _add(errors, "invalid_case_rule_ids", "covered_rule_ids must be an array", case_id=case_id)
            continue
        for flow_id in flow_ids:
            if flow_id not in flow_by_id:
                _add(errors, "unknown_flow_reference", "case references an unknown business flow", case_id=case_id, flow_id=flow_id)
                continue
            required = {
                assertion_id
                for step in flow_by_id[flow_id].get("steps", [])
                if isinstance(step, dict)
                for assertion_id in step.get("covered_assertion_ids", [])
            }
            missing = sorted(required - set(rule_ids))
            if missing:
                _add(errors, "incomplete_flow_case", "case does not cover all flow assertions", case_id=case_id, flow_id=flow_id, assertion_ids=missing)
                continue
            coverage[flow_id].append(case_id)
    for flow_id, flow in flow_by_id.items():
        if flow.get("status") in CONFIRMED_STATUSES and not coverage[flow_id]:
            _add(errors, "confirmed_flow_without_case", "confirmed business flow has no complete end-to-end case", flow_id=flow_id)
    rows = [
        {
            "flow_id": flow_id,
            "status": flow_by_id[flow_id].get("status"),
            "case_ids": sorted(coverage[flow_id]),
        }
        for flow_id in sorted(flow_by_id)
    ]
    return _result(errors, flows=rows)
