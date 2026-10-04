"""Derive per-assertion outcome from the Playwright JSON reporter, not hand-filled results.

Requires an assertion wrapper which always attaches a receipt AND throws a failed
assertion into Playwright. This is reporter consistency, not proof of business
semantics, authentic browser actions, or the exact source used at run time.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .automation_outcome import _report_tests
from .execution_contract import _artifact, check_execution_probe, digest


def collect_playwright_receipts(binding: Any, root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    errors: list[str] = []
    if not isinstance(binding, dict) or binding.get("schema_version") != 1:
        return {"status": "blocked", "error_codes": ["binding_invalid"]}
    probe = binding.get("probe")
    frozen = check_execution_probe(probe, root, allow_finished=True)
    if frozen["status"] != "passed":
        errors.append("probe_not_frozen")
    runner = _artifact(root, binding.get("runner"), "runner", errors)
    report_path = _artifact(root, binding.get("playwright_report"), "report", errors)
    if runner and runner.suffix not in {".ts", ".js", ".mjs"}:
        errors.append("runner_not_playwright_source")
    if not isinstance(probe, dict) or not isinstance(probe.get("run_id"), str):
        errors.append("run_id_missing")
    elif (report_path and probe["run_id"] not in Path(binding["playwright_report"]["path"]).parts):
        errors.append("report_run_identity_mismatch")
    report: Any = None
    if report_path:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError, OSError):
            errors.append("report_invalid")
    tests = _report_tests(report)
    root_dir = report.get("config", {}).get("rootDir") if isinstance(report, dict) and isinstance(report.get("config"), dict) else None
    if not isinstance(root_dir, str) or not Path(root_dir).is_absolute():
        errors.append("report_root_missing")
    title = binding.get("test_title")
    if not isinstance(title, str) or not title.strip():
        errors.append("test_title_missing")
    matching = [item for item in tests if item["title"] == title and runner
                and isinstance(root_dir, str) and Path(root_dir).is_absolute()
                and isinstance(item["file"], str) and (Path(root_dir) / item["file"]).resolve() == runner]
    if len(matching) != 1:
        errors.append("playwright_test_not_unique" if matching else "playwright_test_missing")
    # _report_tests preserves one item per test and all attempts, but not attachments.
    # Look up that same unique spec in the original report before extracting receipts.
    spec_matches: list[dict[str, Any]] = []
    def visit(suite: Any, parent_file: Any = None) -> None:
        if not isinstance(suite, dict):
            return
        file = suite.get("file") or parent_file
        for spec in suite.get("specs", []) if isinstance(suite.get("specs"), list) else []:
            if isinstance(spec, dict) and spec.get("title") == title and isinstance(root_dir, str) and isinstance(file, str) and runner and (Path(root_dir) / file).resolve() == runner:
                for test in spec.get("tests", []) if isinstance(spec.get("tests"), list) else []:
                    if isinstance(test, dict):
                        spec_matches.append(test)
        for child in suite.get("suites", []) if isinstance(suite.get("suites"), list) else []:
            visit(child, file)
    if isinstance(report, dict):
        for suite in report.get("suites", []) if isinstance(report.get("suites"), list) else []:
            visit(suite)
    if len(spec_matches) != 1 or spec_matches[0].get("expectedStatus") != "passed":
        errors.append("test_identity_or_expected_status_invalid")
    attempts = spec_matches[0].get("results") if len(spec_matches) == 1 else None
    if not isinstance(attempts, list) or len(attempts) != 1 or not isinstance(attempts[0], dict):
        errors.append("playwright_attempt_not_unique")
        attempts = []
    if attempts and attempts[0].get("status") != "passed":
        errors.append("playwright_did_not_pass")
    if isinstance(report, dict):
        errors_at_root = report.get("errors", [])
        if errors_at_root:
            errors.append("playwright_root_errors")
    for item in tests:
        if item in matching:
            continue
        attempts_other = item["results"]
        if (item["expected"] != "passed" or not isinstance(attempts_other, list)
                or len(attempts_other) != 1 or not isinstance(attempts_other[0], dict)
                or attempts_other[0].get("status") != "passed"):
            errors.append("other_test_not_clean")
    attached = attempts[0].get("attachments") if attempts else None
    if not isinstance(attached, list):
        attached = []
    receipts: list[dict[str, Any]] = []
    expected_ids = probe.get("assertion_ids", []) if isinstance(probe, dict) else []
    for assertion_id in expected_ids if isinstance(expected_ids, list) else []:
        items = [a for a in attached if isinstance(a, dict) and a.get("name") == "ai-test-assertion-" + assertion_id]
        if len(items) != 1:
            errors.append("assertion_attachment_not_unique")
            continue
        item = items[0]
        # Refuse paths or sidecar files, which can be swapped independently of the JSON report.
        if item.get("contentType") != "application/vnd.ai-test.assertion+json" or not isinstance(item.get("body"), str) or item.get("path"):
            errors.append("assertion_attachment_invalid")
            continue
        try:
            receipt = json.loads(base64.b64decode(item["body"], validate=True).decode("utf-8"))
        except (ValueError, UnicodeError, json.JSONDecodeError):
            errors.append("assertion_attachment_unreadable")
            continue
        expected = {"run_id": probe["run_id"], "case_id": probe["case_id"],
                    "assertion_id": assertion_id, "fixture_id": probe["fixture"]["id"],
                    "probe_sha256": digest(probe), "oracle_sha256": probe["oracle"]["sha256"]}
        if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected.items()):
            errors.append("assertion_attachment_identity_mismatch")
        elif receipt.get("status") != "passed":
            errors.append("assertion_not_passed")
        else:
            receipts.append({"assertion_id": assertion_id, "status": "passed"})
    return {"schema_version": 1, "status": "blocked" if errors else "passed",
            "scope": "reporter_assertion_consistency_only", "error_codes": sorted(set(errors)),
            "run_id": probe.get("run_id") if isinstance(probe, dict) else None,
            "case_id": probe.get("case_id") if isinstance(probe, dict) else None,
            "assertions": receipts,
            "manual_review_required": True}
