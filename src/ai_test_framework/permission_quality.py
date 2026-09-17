"""Check declared permission design coverage, not business truth or execution."""

import re
from typing import Any, Dict, List


def _requirements(context: Dict[str, Any]) -> Dict[str, set]:
    required = {
        "granted": {"menu", "page", "navigation", "read_api"},
        "denied": {"menu", "page", "navigation", "read_api"},
        "revoked": {"page", "navigation", "read_api"},
    }
    if context.get("upstream_gate"):
        required["upstream_disabled"] = {"page", "read_api"}
    if context.get("scope_required"):
        required["scope_granted"] = {"scope", "read_api"}
        required["scope_denied"] = {"scope", "read_api"}
        required["scope_denied_no_permission"] = {"scope", "read_api"}
    if context.get("surface_switch_required"):
        required["switch_context"] = {"menu", "page", "scope"}
    if context.get("filters_required"):
        required["filter_preservation"] = {"menu", "page"}
    if context.get("supports_edit"):
        required.update({
            "browse_only": {"edit_control", "write_api_no_change"},
            "edit_only": {"dependency_contract"},
            "browse_edit": {"edit_control", "save_readback"},
            "revoke_edit": {"edit_control", "write_api_no_change"},
            "stale_form": {"write_api_no_change"},
            "revoke_browse": {"dependency_contract"},
        })
        for scenario in ("denied", "revoked", "upstream_disabled", "scope_denied", "scope_denied_no_permission"):
            if scenario in required:
                required[scenario].add("write_api_no_change")
        if "filter_preservation" in required:
            required["filter_preservation"].add("edit_control")
            required["filter_readonly"] = {"edit_control", "write_api_no_change"}
    operations = context.get("independent_operations", [])
    if isinstance(operations, list):
        for action in operations:
            if isinstance(action, str) and re.fullmatch(r"[a-z][a-z0-9_]*", action):
                required[f"operation_{action}_granted"] = {"edit_control", "save_readback"}
                required[f"operation_{action}_denied"] = {"edit_control", "write_api_no_change"}
    return required


def check_permission_coverage(matrix: Any, cases: Any) -> Dict[str, Any]:
    """Require independent design entries for permission combinations and bypasses."""
    errors, gaps, pending = [], [], []
    contexts = matrix.get("contexts", []) if isinstance(matrix, dict) else []
    if not isinstance(contexts, list) or not contexts:
        errors.append("permission matrix must contain non-empty contexts")
        contexts = []
    if not isinstance(cases, list):
        errors.append("cases must be an array")
        cases = []
    registry = {}
    for context in contexts:
        if not isinstance(context, dict):
            errors.append("context must be an object")
            continue
        context_id = context.get("id")
        if not isinstance(context_id, str) or not context_id.strip():
            errors.append("context requires stable id")
            continue
        if context_id in registry:
            errors.append(f"duplicate context: {context_id}")
        for field in ("role", "surface", "grant_layer", "source_ref"):
            if not isinstance(context.get(field), str) or not context[field].strip():
                errors.append(f"{context_id}: missing {field}")
        for field in ("supports_edit", "upstream_gate", "scope_required",
                      "surface_switch_required", "filters_required"):
            if not isinstance(context.get(field), bool):
                errors.append(f"{context_id}: {field} must be explicitly boolean")
        if not isinstance(context.get("activation"), str) or context["activation"] not in {"relogin", "refresh", "immediate"}:
            errors.append(f"{context_id}: activation policy missing or invalid")
        if context.get("supports_edit"):
            policy = context.get("edit_only_policy")
            if policy == "pending":
                pending.append(f"{context_id}: edit-only dependency policy needs decision")
            elif not isinstance(policy, str) or policy not in {"auto_grant_browse", "reject_configuration", "independent", "deny_access"}:
                errors.append(f"{context_id}: edit_only_policy missing or invalid")
        operations = context.get("independent_operations", [])
        if not isinstance(operations, list) or any(
            not isinstance(action, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", action)
            for action in operations
        ):
            errors.append(f"{context_id}: independent_operations must be an array of operation keys")
        elif len(set(operations)) != len(operations):
            errors.append(f"{context_id}: duplicate independent operation")
        registry[context_id] = context

    coverage, seen = {}, set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append("case must be an object")
            continue
        metadata = case.get("permission_test")
        if metadata is None:
            continue
        if not isinstance(metadata, dict):
            errors.append("permission_test must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            errors.append(f"missing or duplicate permission case id: {case_id}")
        seen.add(str(case_id))
        context_id = metadata.get("context_id")
        context = registry.get(context_id) if isinstance(context_id, str) else None
        if not context:
            errors.append(f"{case_id}: unknown context {context_id}")
            continue
        scenario = metadata.get("scenario")
        if not isinstance(scenario, str) or scenario not in _requirements(context):
            errors.append(f"{case_id}: unknown scenario {scenario}")
            continue
        checks = metadata.get("checks")
        if not isinstance(checks, list) or any(not isinstance(item, str) for item in checks):
            errors.append(f"{case_id}: checks must be a string array")
            continue
        steps = case.get("steps", [])
        if not isinstance(steps, list) or not steps or any(not isinstance(item, str) for item in steps):
            errors.append(f"{case_id}: requires executable text steps")
            continue
        if metadata.get("activation_performed") != context.get("activation"):
            errors.append(f"{case_id}: activation differs from context")
            continue
        if context.get("activation") == "relogin" and not re.search(
            r"重新登录|重登|re[- ]?login|sign out.*sign in", " ".join(steps), re.IGNORECASE
        ):
            errors.append(f"{case_id}: steps omit required re-login")
            continue
        coverage.setdefault((context_id, scenario), set()).update(checks)

    total, covered = 0, 0
    for context_id, context in registry.items():
        for scenario, checks in _requirements(context).items():
            total += len(checks)
            found = checks & coverage.get((context_id, scenario), set())
            covered += len(found)
            missing = sorted(checks - found)
            if missing:
                gaps.append({"context_id": context_id, "scenario": scenario, "missing_checks": missing})
    return {
        "status": "failed" if errors or gaps else ("blocked" if pending else "passed"),
        "scope": "declared_permission_design_only",
        "errors": errors, "gaps": gaps, "pending_decisions": pending,
        "metrics": {"context_count": len(registry), "permission_case_count": len(seen),
                    "required_check_count": total, "covered_check_count": covered,
                    "percentage": round(100 * covered / total, 2) if total else 0},
        "limitations": ["Context completeness, step semantics, business expectations and actual execution require independent review."],
    }
