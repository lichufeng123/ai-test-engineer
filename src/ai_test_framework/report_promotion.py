"""Local report-delivery gate: no self-declared business Current or product pass.

The only supported path is a synthetic, reporter-bound run awaiting human report
approval. Real business promotion needs a separate trusted Current/authorization
adapter and CI policy; local files and human-review declarations can be forged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .automation_outcome import _report_tests
from .evidence_privacy import check_evidence_privacy
from .execution_contract import _artifact, check_execution_probe, digest
from .guarded_run import _SAFE_ID, _hash_file, _starter_drift
from .playwright_receipts import collect_playwright_receipts


def _read_json(path: Path | None, label: str, errors: list[str]) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(label + "_invalid_json")
        return {}
    if not isinstance(payload, dict):
        errors.append(label + "_invalid_json")
        return {}
    return payload


def check_report_promotion(request: Any, root: Path) -> dict[str, Any]:
    """Never produce product approval from local receipts or caller-supplied flags."""
    root = Path(root).resolve()
    if not isinstance(request, dict) or request.get("schema_version") != 1:
        return {"status": "blocked", "error_codes": ["promotion_request_invalid"]}
    if request.get("mode") != "synthetic":
        return {"status": "blocked", "error_codes": ["trusted_business_promotion_adapter_missing"],
                "product_verdict": "not_evaluated"}
    if set(request) != {"schema_version", "mode", "run_id", "guarded_receipt", "privacy_manifest"}:
        return {"status": "blocked", "error_codes": ["promotion_request_fields_invalid"]}
    run_id = request.get("run_id")
    if not isinstance(run_id, str) or not _SAFE_ID.fullmatch(run_id):
        return {"status": "blocked", "error_codes": ["run_id_unsafe"]}
    errors: list[str] = []
    run_dir = root / "runs" / run_id
    receipt_path = _artifact(root, request.get("guarded_receipt"), "guarded_receipt", errors)
    if receipt_path != run_dir / "guarded-run-receipt.json":
        errors.append("guarded_receipt_not_in_run")
    receipt = _read_json(receipt_path, "guarded_receipt", errors)
    if (receipt.get("status") != "review_required" or receipt.get("scope") != "synthetic_execution_only"
            or receipt.get("run_id") != run_id or receipt.get("case_id") != "TC-EXAMPLE-001"
            or receipt.get("playwright_exit_code") != 0 or receipt.get("reporter_status") != "passed"
            or receipt.get("product_verdict") != "not_evaluated" or receipt.get("semantic_review") != "pending"
            or receipt.get("error_codes") != []):
        errors.append("guarded_run_not_clean_or_identity_mismatch")
    marker = _read_json(root / ".ai-test/guarded-runs" / (run_id + ".json"), "guarded_marker", errors)
    if marker != receipt or not marker:
        errors.append("guarded_marker_mismatch")
    bundle = _read_json(run_dir / "guarded-bundle.json", "bundle", errors)
    probe = bundle.get("probe")
    if not isinstance(probe, dict) or probe.get("run_id") != run_id or probe.get("case_id") != receipt.get("case_id"):
        errors.append("probe_identity_mismatch")
        probe = {}
    else:
        frozen = check_execution_probe(probe, root, allow_finished=True)
        if frozen["status"] != "passed" or receipt.get("probe_sha256") != digest(probe):
            errors.append("probe_not_frozen_or_changed")
    for name in ("runner", "config", "package", "test_plan"):
        ref = bundle.get(name)
        path = _artifact(root, ref, name, errors)
        if path is None or not isinstance(ref, dict) or receipt.get(name + "_sha256") != ref.get("sha256"):
            errors.append(name + "_not_bound_to_run")
    if bundle.get("web_root") != "automation/web" or bundle.get("test_title") != "TC-EXAMPLE-001 counter increments once":
        errors.append("synthetic_bundle_identity_mismatch")
    if _starter_drift(root / "automation/web"):
        errors.append("synthetic_source_changed_after_run")
    report_ref = receipt.get("playwright_report")
    report_path = _artifact(root, report_ref, "playwright_report", errors)
    if report_path != root / "automation/web/runs" / run_id / "playwright-results.json":
        errors.append("report_identity_or_path_mismatch")
    report = _read_json(report_path, "playwright_report", errors)
    if report_path and isinstance(probe, dict) and probe:
        binding = {"schema_version": 1, "probe": probe, "runner": bundle.get("runner"),
                   "playwright_report": report_ref, "test_title": bundle.get("test_title")}
        reporter = collect_playwright_receipts(binding, root)
        if reporter["status"] != "passed":
            errors.extend(reporter["error_codes"] or ["reporter_inconsistent"])
    tests = _report_tests(report)
    if len(tests) != 1:
        errors.append("playwright_test_count_not_one")
    external: dict[str, str] = {}
    videos = 0
    for test in tests:
        attempts = test.get("results")
        if not isinstance(attempts, list) or len(attempts) != 1 or not isinstance(attempts[0], dict):
            errors.append("attempts_not_unique")
            continue
        attachments = attempts[0].get("attachments")
        if not isinstance(attachments, list):
            errors.append("attachments_invalid")
            continue
        for item in attachments:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            raw = Path(str(item["path"]))
            attachment = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
            if (not attachment.is_relative_to(root / "automation/web/runs" / run_id)
                    or not attachment.is_file() or attachment.is_symlink()):
                errors.append("attachment_outside_run_or_missing")
                continue
            relative = attachment.relative_to(root).as_posix()
            external[relative] = _hash_file(attachment)
            if item.get("name") == "video" and attachment.suffix.lower() in {".webm", ".mp4"}:
                videos += 1
    if videos != 1:
        errors.append("single_run_video_missing")
    try:
        history = json.loads((root / ".ai-test/execution_history.json").read_text(encoding="utf-8"))
        runs = [run for automation in history["automations"] if isinstance(automation, dict)
                for run in automation.get("runs", []) if isinstance(run, dict) and run.get("run_id") == run_id]
    except (OSError, UnicodeError, TypeError, KeyError, json.JSONDecodeError):
        runs = []
    baseline = probe.get("baseline") if isinstance(probe.get("baseline"), dict) else {}
    if (len(runs) != 1 or runs[0].get("status") != "partial"
            or runs[0].get("baseline") != baseline.get("id")
            or runs[0].get("report") != f"runs/{run_id}/report.md"
            or runs[0].get("evidence") != (report_ref.get("path") if isinstance(report_ref, dict) else None)):
        errors.append("run_history_not_closed_for_source")
    feedback = _read_json(run_dir / "asset-feedback.json", "asset_feedback", errors)
    if feedback.get("run_id") != run_id or feedback.get("status") != "pending_review":
        errors.append("asset_feedback_missing_or_unbound")
    if not (run_dir / "report.md").is_file():
        errors.append("technical_report_missing")
    manifest_path = _artifact(root, request.get("privacy_manifest"), "privacy_manifest", errors)
    if manifest_path != run_dir / "privacy-review.json":
        errors.append("privacy_manifest_not_in_run")
    manifest = _read_json(manifest_path, "privacy_manifest", errors)
    items = manifest.get("items")
    required = dict(external)
    if report_path and isinstance(report_ref, dict):
        required[report_ref["path"]] = report_ref["sha256"]
    if (not isinstance(items, list) or any(not isinstance(item, dict)
            or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str) for item in items)):
        errors.append("privacy_manifest_invalid")
    else:
        actual = {item["path"]: item["sha256"] for item in items}
        if len(items) != len(actual) or actual != required:
            errors.append("privacy_review_coverage_or_hash_mismatch")
        else:
            privacy = check_evidence_privacy(manifest, root)
            if privacy["status"] != "passed":
                errors.extend(privacy["error_codes"] or ["privacy_review_incomplete"])
    if errors:
        return {"schema_version": 1, "status": "blocked", "scope": "local_synthetic_delivery_only",
                "run_id": run_id, "error_codes": sorted(set(errors)), "product_verdict": "not_evaluated"}
    return {"schema_version": 1, "status": "review_required", "scope": "local_synthetic_delivery_only",
            "run_id": run_id, "technical_checks": "passed", "error_codes": [],
            "product_verdict": "not_evaluated", "human_review_identity": "declaration_only_not_authenticated",
            "notice": "Local evidence is consistent; formal product-report promotion remains unavailable."}
