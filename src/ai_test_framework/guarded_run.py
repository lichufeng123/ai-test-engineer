"""A single synthetic Playwright run wired from frozen probe to reporter closure.

The coordinator is intentionally local/synthetic-only. Real-product execution
needs a reviewed adapter that enforces action-time identity and authorization.
No general command execution, URL, credentials, or automatic retry is accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .automation_outcome import _report_tests
from .execution_contract import _artifact, check_execution_probe, digest
from .execution_history import finish_execution
from .playwright_receipts import collect_playwright_receipts

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,99}$")
_ALLOWED_ENV = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")
_STARTER_FILES = ("tests/counter.spec.ts", "pages/CounterPage.ts", "flows/counterFlow.ts",
                  "oracles/counter.ts", "evidence/assertionReceipt.ts",
                  "evidence/phaseTiming.ts", "playwright.config.ts", "package.json", "package-lock.json")


def _starter_drift(web_root: Path) -> list[str]:
    web_root = web_root.resolve()
    starter = Path(__file__).parent / "starter_playwright"
    mismatches = []
    for relative in _STARTER_FILES:
        deployed = (web_root / relative).resolve()
        if (not deployed.is_relative_to(web_root) or not deployed.is_file() or not (starter / relative).is_file()
                or _hash_file(deployed) != _hash_file(starter / relative)):
            mismatches.append(relative)
    return mismatches


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _start_process(args: list[str], *, cwd: str, env: dict[str, str], timeout: int) -> int:
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return process.returncode


def execute_guarded_playwright(
    bundle: Any, root: Path, *, timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run precisely one synthetic Case once; return non-green until semantic review.

    A directly invoked Playwright process can still bypass this coordinator;
    only reports bound to this run receipt are eligible for later promotion.
    """
    root = Path(root).resolve()
    errors: list[str] = []
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        return {"status": "blocked", "error_codes": ["bundle_invalid"]}
    if set(bundle) != {"schema_version", "probe", "test_plan", "runner", "config", "package", "web_root", "test_title", "browser_channel"}:
        return {"status": "blocked", "error_codes": ["bundle_fields_invalid"]}
    probe = bundle.get("probe")
    if not isinstance(probe, dict):
        return {"status": "blocked", "error_codes": ["probe_missing"]}
    run_id, case_id = probe.get("run_id"), probe.get("case_id")
    if not isinstance(run_id, str) or not _SAFE_ID.fullmatch(run_id):
        return {"status": "blocked", "error_codes": ["run_id_unsafe"]}
    if not isinstance(case_id, str) or not case_id.strip():
        return {"status": "blocked", "error_codes": ["case_id_missing"]}
    if os.name != "posix":
        return {"status": "blocked", "error_codes": ["process_isolation_unsupported"]}
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 120:
        return {"status": "blocked", "error_codes": ["timeout_out_of_bounds"]}
    frozen = check_execution_probe(probe, root)
    if frozen["status"] != "passed":
        errors.extend(frozen["error_codes"])
    profile = _artifact(root, probe.get("profile"), "profile", errors)
    try:
        profile_data = json.loads(profile.read_text(encoding="utf-8")) if profile else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        profile_data = {}
    if (profile_data.get("stage"), profile_data.get("zone")) != ("local", "synthetic"):
        errors.append("business_environment_not_supported")
    if probe.get("mode") != "rapid":
        errors.append("synthetic_rapid_charter_only")
    test_plan = _artifact(root, bundle.get("test_plan"), "test_plan", errors)
    if not test_plan or not test_plan.is_relative_to(root / "runs" / run_id):
        errors.append("test_plan_not_in_run_directory")
    runner = _artifact(root, bundle.get("runner"), "runner", errors)
    config = _artifact(root, bundle.get("config"), "config", errors)
    package = _artifact(root, bundle.get("package"), "package", errors)
    raw_web_root = bundle.get("web_root")
    if raw_web_root != "automation/web":
        errors.append("web_root_unsafe")
    web_root = (root / "automation/web").resolve()
    if not web_root.is_relative_to(root):
        return {"status": "blocked", "error_codes": ["web_root_unsafe"]}
    if config != (web_root / "playwright.config.ts") or package != (web_root / "package.json"):
        errors.append("web_project_reference_mismatch")
    try:
        package_data = json.loads(package.read_text(encoding="utf-8")) if package else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        package_data = {}
    pinned_version = package_data.get("devDependencies", {}).get("@playwright/test") if isinstance(package_data.get("devDependencies"), dict) else None
    if not isinstance(pinned_version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", pinned_version):
        errors.append("playwright_dependency_not_pinned")
    if runner != web_root / "tests/counter.spec.ts" or _starter_drift(web_root):
        errors.append("synthetic_starter_source_drift")
    fixture = probe.get("fixture") if isinstance(probe.get("fixture"), dict) else {}
    if (case_id != "TC-EXAMPLE-001" or probe.get("assertion_ids") != ["A-EXAMPLE-001"]
            or fixture.get("id") != "FX-EXAMPLE-001"):
        errors.append("synthetic_probe_identity_mismatch")
    title = bundle.get("test_title")
    if title != "TC-EXAMPLE-001 counter increments once":
        errors.append("test_title_not_bound")
    channel = bundle.get("browser_channel")
    if channel not in {"msedge", "chromium"}:
        errors.append("browser_channel_not_pinned")
    executable = (web_root / "node_modules/.bin/playwright").resolve()
    allowed_entrypoints = {web_root / "node_modules/playwright/cli.js",
                           web_root / "node_modules/@playwright/test/cli.js"}
    if executable not in allowed_entrypoints or not executable.is_file():
        errors.append("playwright_binary_missing_or_untrusted_layout")
    for dependency in ("playwright", "@playwright/test"):
        try:
            installed = json.loads((web_root / "node_modules" / dependency / "package.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            installed = {}
        if installed.get("version") != pinned_version:
            errors.append("installed_playwright_version_drift")
    report = web_root / "runs" / run_id / "playwright-results.json"
    report_dir = web_root / "runs" / run_id
    if not report_dir.resolve().is_relative_to(root) or (web_root / "runs").is_symlink():
        errors.append("report_directory_unsafe")
    if report.exists() or report.is_symlink() or report_dir.exists() or report_dir.is_symlink():
        errors.append("run_artifact_path_already_exists")
    if not (root / "runs" / run_id).resolve().is_relative_to(root) or (root / "runs" / run_id / "guarded-run-receipt.json").exists():
        errors.append("run_receipt_path_unsafe_or_already_exists")
    if errors:
        return {"schema_version": 1, "status": "blocked", "error_codes": sorted(set(errors)),
                "scope": "synthetic_only"}
    assert runner is not None and isinstance(title, str)
    marker_dir = root / ".ai-test/guarded-runs"
    if not marker_dir.resolve().is_relative_to(root):
        return {"status": "blocked", "error_codes": ["run_receipt_store_unsafe"]}
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / (run_id + ".json")
    starting = {"schema_version": 1, "status": "started", "scope": "synthetic_only",
                "run_id": run_id, "case_id": case_id, "probe_sha256": digest(probe),
                "runner_sha256": bundle["runner"]["sha256"],
                "config_sha256": bundle["config"]["sha256"],
                "package_sha256": bundle["package"]["sha256"],
                "test_plan_sha256": bundle["test_plan"]["sha256"],
                "playwright_binary_sha256": _hash_file(executable),
                "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {"status": "blocked", "error_codes": ["guarded_run_already_started_no_retry"]}
    except OSError:
        return {"status": "blocked", "error_codes": ["run_receipt_store_unavailable"]}
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(starting, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    env = {name: os.environ[name] for name in _ALLOWED_ENV if name in os.environ}
    env.update({"AI_TEST_RUN_ID": run_id, "AI_TEST_PROBE_SHA256": digest(probe),
                "AI_TEST_ORACLE_SHA256": probe["oracle"]["sha256"],
                "AI_TEST_BROWSER_CHANNEL": channel})
    args = [str(executable), "test", runner.relative_to(web_root).as_posix(),
            "--grep", re.escape(title) + "$", "--workers=1", "--retries=0"]
    process_errors: list[str] = []
    exit_code: int | None = None
    try:
        exit_code = _start_process(args, cwd=str(web_root), env=env, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process_errors.append("playwright_timeout_unknown_state_no_retry")
    except OSError:
        process_errors.append("playwright_launch_failed")
    if exit_code is not None and exit_code != 0:
        process_errors.append("playwright_exit_nonzero")
    for name, label in (("test_plan", "test_plan_changed_during_run"),
                        ("runner", "runner_changed_during_run"),
                        ("config", "config_changed_during_run"),
                        ("package", "package_changed_during_run")):
        if _artifact(root, bundle[name], name + "_after", process_errors) is None:
            process_errors.append(label)
    if _starter_drift(web_root):
        process_errors.append("synthetic_starter_changed_during_run")
    if _hash_file(executable) != starting["playwright_binary_sha256"]:
        process_errors.append("playwright_binary_changed_during_run")
    post_probe = check_execution_probe(probe, root, allow_finished=True)
    if post_probe["status"] != "passed":
        process_errors.append("probe_artifact_changed_during_run")
    reporter_receipt: dict[str, Any] | None = None
    report_ref: dict[str, str] | None = None
    if report.is_file() and not report.is_symlink() and report.resolve().is_relative_to(root):
        report_ref = {"path": report.relative_to(root).as_posix(), "sha256": _hash_file(report)}
        binding = {"schema_version": 1, "probe": probe, "runner": bundle["runner"],
                   "playwright_report": report_ref, "test_title": title}
        reporter_receipt = collect_playwright_receipts(binding, root)
        try:
            total_tests = len(_report_tests(json.loads(report.read_text(encoding="utf-8"))))
        except (OSError, UnicodeError, json.JSONDecodeError):
            total_tests = 0
        if total_tests != 1:
            process_errors.append("playwright_test_count_not_one")
        if reporter_receipt["status"] != "passed":
            process_errors.extend(reporter_receipt["error_codes"] or ["reporter_inconsistent"])
    else:
        process_errors.append("fresh_playwright_report_missing")
    status = "blocked" if process_errors else "review_required"
    result = {"schema_version": 1, "status": status, "scope": "synthetic_execution_only",
              "run_id": run_id, "case_id": case_id, "probe_sha256": digest(probe),
              "runner_sha256": bundle["runner"]["sha256"],
              "config_sha256": bundle["config"]["sha256"],
              "package_sha256": bundle["package"]["sha256"],
              "test_plan_sha256": bundle["test_plan"]["sha256"],
              "playwright_binary_sha256": starting["playwright_binary_sha256"],
              "playwright_exit_code": exit_code,
              "playwright_report": report_ref, "reporter_status": reporter_receipt["status"] if reporter_receipt else "missing",
              "error_codes": sorted(set(process_errors)), "product_verdict": "not_evaluated",
              "semantic_review": "pending"}
    run_dir = root / "runs" / run_id
    _write_json(run_dir / "guarded-run-receipt.json", result)
    _write_json(run_dir / "asset-feedback.json", {"schema_version": 1,
                "status": "pending_review", "run_id": run_id, "asset_changes": [],
                "note": "Synthetic run only; no reusable business knowledge or assets are promoted."})
    (run_dir / "report.md").write_text(
        f"# {run_id} · synthetic guarded run\n\n"
        f"- 执行状态：{'阻塞' if process_errors else '部分完成（待语义复核）'}\n"
        f"- Reporter 对账：{result['reporter_status']}；独立业务结论：未评价\n"
        f"- 错误代码：{', '.join(result['error_codes']) if process_errors else '无'}\n"
        f"- 证据：{report_ref['path'] if report_ref else '未生成'}\n"
        "- 资产反馈：pending_review，未晋升业务资产\n",
        encoding="utf-8")
    _write_json(marker, result)
    finish_execution(root, run_id=run_id, result_status="blocked" if process_errors else "partial",
                     summary="Synthetic guarded runner; reporter " + result["reporter_status"] + "; semantic review pending",
                     finished_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                     report=("runs/" + run_id + "/report.md"),
                     evidence=report_ref["path"] if report_ref else None)
    return result
