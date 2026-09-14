"""Quality gates for executable test-case granularity."""

from typing import Any, Dict, List


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _is_e2e(case: Dict[str, Any]) -> bool:
    case_type = str(case.get("case_type") or "").lower()
    return bool(_strings(case.get("covered_flow_ids"))) or "端到端" in case_type or "e2e" in case_type


def check_case_granularity(
    cases: List[Dict[str, Any]], max_e2e_only_ratio: float = 0.35
) -> Dict[str, Any]:
    """Reject suites whose rule coverage exists mainly inside E2E cases."""
    if not 0 <= max_e2e_only_ratio <= 1:
        raise ValueError("max_e2e_only_ratio must be between 0 and 1")

    all_rules = set()
    independently_covered_rules = set()
    e2e_cases = []
    independent_cases = []
    for case in cases:
        rule_ids = set(_strings(case.get("covered_rule_ids")))
        all_rules.update(rule_ids)
        if _is_e2e(case):
            e2e_cases.append(case)
        else:
            independent_cases.append(case)
            independently_covered_rules.update(rule_ids)

    e2e_only_rules = sorted(all_rules - independently_covered_rules)
    ratio = len(e2e_only_rules) / len(all_rules) if all_rules else 0.0
    overloaded_e2e_cases = [
        {
            "case_id": str(case.get("id") or ""),
            "covered_rule_count": len(set(_strings(case.get("covered_rule_ids")))),
            "step_count": len(_strings(case.get("steps"))),
        }
        for case in e2e_cases
        if len(set(_strings(case.get("covered_rule_ids")))) >= 12
    ]

    errors = []
    if len(all_rules) >= 10 and e2e_cases and ratio > max_e2e_only_ratio:
        errors.append(
            f"{len(e2e_only_rules)}/{len(all_rules)} rules ({ratio:.1%}) only have E2E coverage; "
            f"maximum allowed ratio is {max_e2e_only_ratio:.1%}"
        )
    if e2e_cases and not independent_cases:
        errors.append("suite contains E2E cases but no independent execution layer")

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "metrics": {
            "case_count": len(cases),
            "e2e_case_count": len(e2e_cases),
            "independent_case_count": len(independent_cases),
            "covered_rule_count": len(all_rules),
            "independently_covered_rule_count": len(independently_covered_rules),
            "e2e_only_rule_count": len(e2e_only_rules),
            "e2e_only_rule_ratio": round(ratio, 6),
            "max_e2e_only_rule_ratio": max_e2e_only_ratio,
            "overloaded_e2e_cases": overloaded_e2e_cases,
        },
        "e2e_only_rule_ids": e2e_only_rules,
    }
