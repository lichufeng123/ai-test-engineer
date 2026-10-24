"""Reconcile a declared assertion outcome with an actual Playwright JSON report.

This is an artifact consistency gate, not proof that product expectations, a
reviewer's semantic judgment, or a Playwright report are authentic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _file(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, dict) or not value.get("path") or not value.get("sha256"):
        errors.append(f"{label}_missing")
        return None
    raw = Path(str(value["path"]))
    if raw.is_absolute() or ".." in raw.parts:
        errors.append(f"{label}_unsafe_path")
        return None
    target = (root / raw).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        errors.append(f"{label}_missing")
        return None
    hasher = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    if hasher.hexdigest() != value["sha256"]:
        errors.append(f"{label}_hash_mismatch")
        return None
    return target


def _report_tests(report: Any) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []

    def visit(suite: dict[str, Any], inherited_file: str | None = None) -> None:
        file = suite.get("file") or inherited_file
        for spec in suite.get("specs", []) if isinstance(suite.get("specs", []), list) else []:
            if not isinstance(spec, dict):
                continue
            for item in spec.get("tests", []) if isinstance(spec.get("tests", []), list) else []:
                if isinstance(item, dict):
                    tests.append({"title": spec.get("title"), "file": file,
                                  "expected": item.get("expectedStatus"),
                                  "results": item.get("results")})
        for child in suite.get("suites", []) if isinstance(suite.get("suites", []), list) else []:
            if isinstance(child, dict):
                visit(child, file)

    if isinstance(report, dict):
        for suite in report.get("suites", []) if isinstance(report.get("suites", []), list) else []:
            if isinstance(suite, dict):
                visit(suite)
    return tests


def check_automation_outcome(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    """Fail closed on missing, contradictory, or unbound assertion outcomes.

    A claimed product failure needs independent triage; this gate only checks
    declared assertions against recorded Playwright runs and evidence identity.
    """
    root = Path(root).resolve()
    errors: list[str] = []
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {"schema_version": 1, "status": "blocked", "error_codes": ["invalid_contract"]}
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        errors.append("run_id_missing")
    mode = payload.get("mode")
    if mode not in {"standard", "rapid"}:
        errors.append("invalid_mode")
    baseline = payload.get("baseline")
    if mode == "standard" and (not isinstance(baseline, dict) or baseline.get("status") != "approved"):
        errors.append("approved_baseline_missing")
    if mode == "rapid" and (not isinstance(baseline, dict) or baseline.get("status") != "provisional"):
        errors.append("provisional_charter_missing")
    if not isinstance(baseline, dict) or not isinstance(baseline.get("id"), str) or not baseline["id"].strip():
        errors.append("baseline_identity_missing")
    baseline_file = _file(root, baseline, "baseline", errors)
    baseline_cases: dict[str, dict[str, Any]] = {}
    if mode == "standard" and baseline_file:
        try:
            content = json.loads(baseline_file.read_text(encoding="utf-8"))
            cases = content.get("cases") if isinstance(content, dict) else None
            if not isinstance(cases, list) or not cases or any(not isinstance(case, dict) for case in cases):
                errors.append("baseline_cases_missing")
            else:
                for case in cases:
                    case_id = case.get("id")
                    if not isinstance(case_id, str) or not case_id.strip() or case_id in baseline_cases:
                        errors.append("baseline_case_identity_invalid")
                    else:
                        baseline_cases[case_id] = case
                if isinstance(baseline, dict) and content.get("baseline_id") != baseline.get("id"):
                    errors.append("baseline_id_mismatch")
        except (UnicodeError, json.JSONDecodeError):
            errors.append("baseline_invalid")
    runner = _file(root, payload.get("runner"), "runner", errors)
    if runner and runner.suffix not in {".ts", ".js", ".mjs"}:
        errors.append("runner_not_playwright_source")
    report_ref = payload.get("playwright_report")
    report_file = _file(root, report_ref, "playwright_report", errors)
    if (report_file and isinstance(run_id, str)
            and run_id not in Path(str(report_ref["path"])).parts):
        errors.append("playwright_run_identity_mismatch")
    report: Any = None
    if report_file:
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            errors.append("playwright_report_invalid")
    tests = _report_tests(report)
    if not isinstance(report, dict) or not isinstance(report.get("suites"), list):
        errors.append("playwright_suites_missing")
    declarations = payload.get("assertions")
    outcomes = payload.get("results")
    if not isinstance(declarations, list) or not declarations:
        errors.append("assertions_missing")
        declarations = []
    if not isinstance(outcomes, list):
        errors.append("results_missing")
        outcomes = []
    ids = [item.get("id") for item in declarations if isinstance(item, dict)]
    result_ids = [item.get("id") for item in outcomes if isinstance(item, dict)]
    valid_ids = [i for i in ids if isinstance(i, str) and i.strip()]
    valid_result_ids = [i for i in result_ids if isinstance(i, str) and i.strip()]
    if len(valid_ids) != len(declarations) or len(set(valid_ids)) != len(valid_ids):
        errors.append("assertion_identity_invalid")
    if len(valid_result_ids) != len(outcomes) or len(set(valid_result_ids)) != len(valid_result_ids):
        errors.append("result_identity_invalid")
    if set(valid_ids) != set(valid_result_ids):
        errors.append("assertion_result_set_mismatch")
    by_id = {item.get("id"): item for item in outcomes if isinstance(item, dict) and isinstance(item.get("id"), str)}
    assertion_receipts = []
    linked_tests: set[tuple[str, str]] = set()
    for declaration in declarations:
        if not isinstance(declaration, dict):
            continue
        key = declaration.get("id")
        if not isinstance(key, str) or not key.strip():
            continue
        problems: list[str] = []
        case_id = declaration.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            problems.append("case_id_missing")
        elif mode == "standard":
            case = baseline_cases.get(case_id)
            if not case:
                problems.append("case_not_in_baseline")
            elif not isinstance(case.get("covered_rule_ids"), list) or key not in case["covered_rule_ids"]:
                problems.append("assertion_not_in_baseline_case")
        if not isinstance(declaration.get("fixture_id"), str) or not declaration["fixture_id"].strip():
            problems.append("fixture_id_missing")
        _file(root, declaration.get("oracle"), "oracle", problems)
        title = declaration.get("test_title")
        if not isinstance(title, str) or not title.strip():
            problems.append("test_title_missing")
        source = runner
        report_root = report.get("config", {}).get("rootDir") if isinstance(report, dict) and isinstance(report.get("config"), dict) else None
        if not isinstance(report_root, str) or not Path(report_root).is_absolute():
            problems.append("playwright_root_dir_missing")
        matching = [item for item in tests if item["title"] == title and source is not None
                    and isinstance(report_root, str) and Path(report_root).is_absolute()
                    and isinstance(item["file"], str)
                    and (Path(report_root) / item["file"]).resolve() == source]
        runner_status = "missing"
        if len(matching) != 1:
            problems.append("playwright_test_not_unique" if matching else "playwright_test_missing")
        else:
            test = matching[0]
            linked_tests.add((str(test["file"]), str(test["title"])))
            attempts = test["results"]
            if not isinstance(attempts, list) or not attempts or not all(isinstance(a, dict) for a in attempts):
                problems.append("playwright_attempt_missing")
            elif test["expected"] != "passed" or len(attempts) != 1:
                runner_status = "not_clean"
            else:
                runner_status = attempts[0].get("status")
        result = by_id.get(key)
        status = result.get("status") if isinstance(result, dict) else None
        if status not in {"passed", "failed", "blocked", "not_executed"}:
            problems.append("result_status_invalid")
        if status == "passed" and runner_status != "passed":
            problems.append("playwright_not_clean_pass")
        if status == "failed" and runner_status != "failed":
            problems.append("failed_assertion_swallowed_by_runner" if runner_status == "passed" else "failed_runner_not_confirmed")
        if status in {"passed", "failed"}:
            if result.get("fixture_verified") is not True:
                problems.append("fixture_unverified")
            expected_verdict = "passed" if status == "passed" else "failed"
            if result.get("oracle_verdict") != expected_verdict:
                problems.append("oracle_verdict_mismatch")
            evidence = result.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                problems.append("evidence_missing")
            else:
                for artifact in evidence:
                    found = _file(root, artifact, "evidence", problems)
                    if found and isinstance(run_id, str) and run_id not in Path(str(artifact["path"])).parts:
                        problems.append("evidence_run_identity_mismatch")
                    if not isinstance(artifact, dict) or artifact.get("content_review") != "passed":
                        problems.append("evidence_content_unreviewed")
        if status in {"blocked", "not_executed"} and isinstance(result, dict) and not str(result.get("reason") or "").strip():
            problems.append("nonpass_reason_missing")
        assertion_receipts.append({"id": key, "case_id": declaration.get("case_id"),
                                   "declared_status": status, "error_codes": sorted(set(problems)),
                                   "status": status if not problems else "blocked"})
    if not assertion_receipts:
        errors.append("no_valid_assertions")
    if mode == "standard":
        for case_id in {item.get("case_id") for item in assertion_receipts if isinstance(item.get("case_id"), str)}:
            case = baseline_cases.get(case_id)
            if not case:
                continue
            declared = {item.get("id") for item in assertion_receipts if item.get("case_id") == case_id}
            required = case.get("covered_rule_ids")
            if not isinstance(required, list) or not required or any(not isinstance(x, str) for x in required):
                errors.append("baseline_case_rules_missing")
            elif not set(required).issubset(declared):
                errors.append("baseline_case_rule_coverage_gap")
    for item in tests:
        if (str(item["file"]), str(item["title"])) in linked_tests:
            continue
        attempts = item["results"]
        if (item["expected"] != "passed" or not isinstance(attempts, list)
                or len(attempts) != 1 or not isinstance(attempts[0], dict)
                or attempts[0].get("status") != "passed"):
            errors.append("unbound_nonpassed_test")
    if any(item["error_codes"] for item in assertion_receipts) or errors:
        final = "blocked"
    elif any(item["status"] in {"blocked", "not_executed"} for item in assertion_receipts):
        final = "blocked"
    elif any(item["status"] == "failed" for item in assertion_receipts):
        final = "failed"
    else:
        final = "passed"
    return {"schema_version": 1, "status": final, "run_id": run_id, "mode": mode,
            "baseline_id": baseline.get("id") if isinstance(baseline, dict) else None,
            "error_codes": sorted(set(errors + [code for item in assertion_receipts for code in item["error_codes"]])),
            "assertions": assertion_receipts,
            "interpretation": "artifact/reporter consistency only; not product acceptance or independent semantic proof"}
