"""Prepare a fresh, documented local synthetic counter run without copy/paste scripts.

This is an onboarding smoke-test helper, not a business Current or authorization
adapter. The caller must first save a run-specific test plan in the run dir.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .environment_profile import resolve_environment
from .execution_contract import check_execution_probe, digest
from .execution_history import start_execution
from .execution_readiness import build_readiness_plan, evaluate_execution_readiness
from .guarded_run import _SAFE_ID, _hash_file, _starter_drift


def prepare_synthetic_guarded_run(root: Path, run_id: str, *, channel: str = "msedge") -> dict[str, Any]:
    root = Path(root).resolve()
    if not isinstance(run_id, str) or not _SAFE_ID.fullmatch(run_id):
        return {"status": "blocked", "error_codes": ["run_id_unsafe"]}
    if channel not in {"msedge", "chromium"}:
        return {"status": "blocked", "error_codes": ["browser_channel_not_pinned"]}
    run_dir = root / "runs" / run_id
    plan = run_dir / "test-plan.v1.md"
    web_root = (root / "automation/web").resolve()
    errors: list[str] = []
    if not run_dir.resolve().is_relative_to(root) or run_dir.is_symlink():
        errors.append("run_directory_unsafe")
    if not plan.is_file() or plan.is_symlink() or not plan.resolve().is_relative_to(root):
        errors.append("saved_test_plan_missing")
    else:
        try:
            contents = plan.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            contents = ""
        if not all(part in contents for part in ("local/synthetic", "TC-EXAMPLE-001", "A-EXAMPLE-001")):
            errors.append("synthetic_test_plan_scope_missing")
    if run_dir.is_dir() and any(path.name != "test-plan.v1.md" for path in run_dir.iterdir()):
        errors.append("run_preparation_already_exists")
    if not web_root.is_relative_to(root) or _starter_drift(web_root):
        errors.append("synthetic_starter_missing_or_modified")
    if (web_root / "runs" / run_id).exists() or (web_root / "runs" / run_id).is_symlink() or (web_root / "runs").is_symlink():
        errors.append("report_run_already_exists_or_unsafe")
    try:
        package = json.loads((web_root / "package.json").read_text(encoding="utf-8"))
        declared = package["devDependencies"]["@playwright/test"]
        installed = [json.loads((web_root / "node_modules" / name / "package.json").read_text(encoding="utf-8"))["version"]
                     for name in ("playwright", "@playwright/test")]
        binary = (web_root / "node_modules/.bin/playwright").resolve()
        if (declared not in installed or installed != [declared, declared]
                or binary not in {web_root / "node_modules/playwright/cli.js", web_root / "node_modules/@playwright/test/cli.js"}
                or not binary.is_file()):
            errors.append("local_playwright_dependency_not_ready")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors.append("local_playwright_dependency_not_ready")
    history = root / ".ai-test/execution_history.json"
    try:
        state = json.loads(history.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("schema_version") != 1 or not isinstance(state.get("automations"), list):
            errors.append("execution_history_unavailable")
        elif any(isinstance(run, dict) and run.get("run_id") == run_id
                 for automation in state["automations"] if isinstance(automation, dict)
                 for run in automation.get("runs", []) if isinstance(automation.get("runs"), list)):
            errors.append("run_id_already_recorded")
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        errors.append("execution_history_unavailable")
    if errors:
        return {"status": "blocked", "error_codes": sorted(set(errors)), "scope": "synthetic_only"}
    now = datetime.now(timezone.utc)
    iso = lambda dt: dt.isoformat(timespec="seconds")
    identity = {"stage": "local", "zone": "synthetic", "platform": "web",
                "organization_view_id": "ORG-EXAMPLE", "role_id": "ROLE-EXAMPLE", "build_id": "BUILD-EXAMPLE-001"}
    profile = {"schema_version": 1, "profile_id": "ENV-" + run_id, "status": "reviewed", **identity,
               "capabilities": ["synthetic_ui"], "reviewed_at": iso(now - timedelta(days=1)),
               "expires_at": iso(now + timedelta(days=1))}
    observation = {"schema_version": 1, **identity, "capabilities": ["synthetic_ui"], "observed_at": iso(now)}
    request = {"schema_version": 1, **identity, "required_capabilities": ["synthetic_ui"], "operation": "write"}
    environment = resolve_environment(profile, observation, request, now=now)
    if environment["status"] != "passed" or environment["write_authorized"]:
        return {"status": "blocked", "error_codes": ["synthetic_environment_not_resolved"]}
    def store(path: str, payload: dict[str, Any]) -> dict[str, str]:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return {"path": path, "sha256": _hash_file(target)}
    plan_ref = {"path": plan.relative_to(root).as_posix(), "sha256": _hash_file(plan)}
    profile_ref = store(f"runs/{run_id}/profile.json", profile)
    environment_ref = store(f"runs/{run_id}/environment.json", environment)
    case_id, assertion_id, fixture_id = "TC-EXAMPLE-001", "A-EXAMPLE-001", "FX-EXAMPLE-001"
    charter_id = "CHARTER-" + run_id
    baseline_ref = store(f"runs/{run_id}/charter.json", {
        "schema_version": 1, "charter_id": charter_id, "status": "provisional",
        "case_id": case_id, "assertion_ids": [assertion_id], "scope": "local synthetic counter only",
        "test_plan": plan_ref})
    source = {"schema_version": 1, "plan_id": "ARP-" + run_id,
              "requirement_baseline_id": charter_id, "feature": "synthetic-counter",
              "automation_scope": {"case_ids": [case_id]},
              "case_requirements": [{"case_id": case_id, "required_role_ids": [identity["role_id"]],
                                     "required_fixture_ids": [fixture_id], "required_environment_ids": ["local"]}],
              "account_requirements": [], "fixture_requirements": [], "evidence_plan": {"video": ["local counter"]}}
    readiness_plan = build_readiness_plan(source)
    readiness_plan_ref = store(f"runs/{run_id}/readiness-plan.json", readiness_plan)
    confirmation = {"schema_version": 1, "plan_id": readiness_plan["plan_id"],
                    "plan_sha256": readiness_plan["plan_sha256"], "target_environment": "local",
                    "scope_confirmed": True, "environment_confirmed": True,
                    "account_roles_confirmed": True, "data_plan_confirmed": True,
                    "available_role_ids": [identity["role_id"]], "ready_fixture_ids": [fixture_id],
                    "excluded_case_ids": []}
    readiness = evaluate_execution_readiness(readiness_plan, confirmation)
    if readiness["status"] != "passed":
        return {"status": "blocked", "error_codes": ["synthetic_readiness_not_passed"]}
    readiness_ref = store(f"runs/{run_id}/readiness.json", readiness)
    def file_ref(path: str) -> dict[str, str]:
        return {"path": path, "sha256": _hash_file(root / path)}
    probe = {"schema_version": 1, "run_id": run_id, "case_id": case_id, "mode": "rapid",
             "baseline": {**baseline_ref, "id": charter_id, "status": "provisional"},
             "plan": readiness_plan_ref, "plan_sha256": readiness_plan["plan_sha256"],
             "readiness_receipt": readiness_ref, "profile": profile_ref,
             "profile_sha256": environment["profile_sha256"], "environment_receipt": environment_ref,
             "oracle": file_ref("automation/web/oracles/counter.ts"), "assertion_ids": [assertion_id],
             "fixture": {"id": fixture_id, "business_key": "local-counter-1",
                         "pre_state_sha256": hashlib.sha256(b'{"counter":2}').hexdigest(), "match_count": 1},
             "action": {"id": "CLICK-INCREASE-ONCE", "kind": "write",
                        "input_sha256": hashlib.sha256(b'{"click":"Increase"}').hexdigest()}}
    store(f"runs/{run_id}/execution-probe.json", probe)
    bundle = {"schema_version": 1, "probe": probe, "test_plan": plan_ref,
              "runner": file_ref("automation/web/tests/counter.spec.ts"),
              "config": file_ref("automation/web/playwright.config.ts"),
              "package": file_ref("automation/web/package.json"),
              "web_root": "automation/web", "test_title": "TC-EXAMPLE-001 counter increments once",
              "browser_channel": channel}
    bundle_ref = store(f"runs/{run_id}/guarded-bundle.json", bundle)
    start_execution(root, automation_id="AUTO-FRAMEWORK-SYNTHETIC", run_id=run_id,
                    feature="synthetic-counter", environment="local", platforms=["web"],
                    purpose="clone onboarding synthetic smoke", objective="verify one reporter-bound local Case",
                    scope="local synthetic only", started_at=iso(now), baseline=charter_id)
    check = check_execution_probe(probe, root)
    return {"schema_version": 1, "status": "prepared" if check["status"] == "passed" else "blocked",
            "scope": "synthetic_only", "run_id": run_id, "bundle": bundle_ref,
            "probe_sha256": digest(probe), "plan_sha256": plan_ref["sha256"],
            "error_codes": check["error_codes"], "business_write_authorized": False}
