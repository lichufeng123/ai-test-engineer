"""Domain-neutral, read-only execution-adapter receipt chain.

Validates local binding and ordering, not an adapter's authenticity, an Oracle's
business correctness, real execution, or permission to publish a product result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .execution_contract import _artifact, check_execution_probe, digest
from .execution_readiness import _assert_no_sensitive_fields

PHASES = ("OBSERVED", "ACTION_GUARDED", "EXECUTED_ONCE", "READBACK", "VERDICT", "EVIDENCE_REPORT")
PLATFORMS = {"web", "api", "app", "h5", "miniapp", "device"}


def check_adapter_trace(trace: Any, root: Path) -> dict[str, Any]:
    """Accept arbitrary Case IDs and domains, but never promote a product verdict."""
    if not isinstance(trace, dict) or trace.get("schema_version") != 1:
        return {"status": "blocked", "error_codes": ["adapter_trace_invalid"]}
    try:
        if len(json.dumps(trace, ensure_ascii=False)) > 256_000:
            return {"status": "blocked", "error_codes": ["adapter_trace_too_large"]}
        _assert_no_sensitive_fields(trace)
    except (ValueError, TypeError):
        return {"status": "blocked", "error_codes": ["adapter_trace_sensitive_or_invalid"]}
    errors: list[str] = []
    root = Path(root).resolve()
    probe = trace.get("probe")
    frozen = check_execution_probe(probe, root, allow_finished=True)
    if frozen["status"] != "passed":
        errors.append("probe_not_frozen")
    if not isinstance(probe, dict):
        return {"status": "blocked", "error_codes": sorted(set(errors + ["probe_invalid"]))}
    run_id, case_id = probe.get("run_id"), probe.get("case_id")
    fixture = probe.get("fixture") if isinstance(probe.get("fixture"), dict) else {}
    action = probe.get("action") if isinstance(probe.get("action"), dict) else {}
    if action.get("kind") != "read":
        errors.append("write_adapter_not_available")
    adapter = trace.get("adapter")
    adapter = adapter if isinstance(adapter, dict) else {}
    source = _artifact(root, adapter.get("source"), "adapter_source", errors)
    if not isinstance(adapter.get("id"), str) or not adapter["id"].strip() or adapter.get("platform") not in PLATFORMS:
        errors.append("adapter_identity_invalid")
    if source is not None and source.suffix not in {".py", ".ts", ".js", ".mjs"}:
        errors.append("adapter_source_not_code")
    adapter_sha = adapter.get("source", {}).get("sha256") if isinstance(adapter.get("source"), dict) else None
    raw_ids = probe.get("assertion_ids")
    expected_ids = raw_ids if isinstance(raw_ids, list) and all(isinstance(value, str) for value in raw_ids) else []
    if not expected_ids:
        errors.append("expected_assertions_invalid")
    steps = trace.get("steps")
    if not isinstance(steps, list) or len(steps) != len(PHASES):
        return {"schema_version": 1, "status": "blocked", "run_id": run_id, "case_id": case_id,
                "error_codes": sorted(set(errors + ["phase_count_or_order_invalid"])),
                "product_verdict": "not_evaluated"}
    previous = digest({"run_id": run_id, "case_id": case_id,
                       "probe_sha256": digest(probe), "adapter_sha256": adapter_sha})
    evidence_refs: set[tuple[str, str]] = set()
    executed_assertions = 0
    for phase, step in zip(PHASES, steps):
        if not isinstance(step, dict):
            errors.append("step_invalid")
            continue
        if step.get("phase") != phase:
            errors.append("phase_count_or_order_invalid")
        if (step.get("run_id") != run_id or step.get("case_id") != case_id
                or step.get("fixture_id") != fixture.get("id")
                or step.get("probe_sha256") != digest(probe)
                or step.get("adapter_sha256") != adapter_sha):
            errors.append("step_identity_mismatch")
        if step.get("previous_sha256") != previous:
            errors.append("step_chain_broken")
        previous = digest(step)
        payload = step.get("payload")
        if not isinstance(payload, dict):
            errors.append("step_payload_invalid")
            continue
        if phase == "OBSERVED":
            if any(payload.get(key) != fixture.get(key) for key in ("id", "business_key", "pre_state_sha256", "match_count")) or payload.get("match_count") != 1:
                errors.append("observed_fixture_not_unique_or_drifted")
        elif phase == "ACTION_GUARDED":
            if (any(payload.get(key) != action.get(key) for key in ("id", "kind", "input_sha256"))
                    or payload.get("kind") != "read" or payload.get("profile_sha256") != probe.get("profile_sha256")):
                errors.append("action_or_environment_not_frozen")
        elif phase == "EXECUTED_ONCE":
            if payload.get("action_id") != action.get("id") or payload.get("attempt_count") != 1 or payload.get("result") != "observed":
                errors.append("read_action_not_single_or_confirmed")
        elif phase == "READBACK":
            value = payload.get("state_sha256")
            if (payload.get("fixture_id") != fixture.get("id") or payload.get("business_key") != fixture.get("business_key")
                    or payload.get("match_count") != 1 or not isinstance(value, str) or len(value) != 64
                    or any(ch not in "0123456789abcdef" for ch in value)):
                errors.append("readback_identity_or_state_invalid")
        elif phase == "VERDICT":
            results = payload.get("assertions")
            if not isinstance(results, list) or len(results) != len(expected_ids):
                errors.append("assertion_set_mismatch")
                continue
            ids = [item.get("id") for item in results if isinstance(item, dict)]
            if (len(ids) != len(results) or any(not isinstance(value, str) or not value for value in ids)
                    or len(ids) != len(set(ids)) or set(ids) != set(expected_ids)):
                errors.append("assertion_set_mismatch")
            for result in results:
                if not isinstance(result, dict):
                    errors.append("assertion_invalid")
                    continue
                status = result.get("status")
                if status not in {"passed", "failed", "blocked", "not_executed"}:
                    errors.append("assertion_status_invalid")
                    continue
                if status in {"passed", "failed"}:
                    executed_assertions += 1
                    oracle = result.get("oracle")
                    if oracle != probe.get("oracle") or _artifact(root, oracle, "oracle", errors) is None:
                        errors.append("assertion_oracle_not_frozen")
                    refs = result.get("evidence")
                    if not isinstance(refs, list) or not refs:
                        errors.append("assertion_evidence_missing")
                        continue
                    for ref in refs:
                        path = _artifact(root, ref, "evidence", errors)
                        if path and isinstance(ref, dict):
                            if ref == oracle or run_id not in Path(ref["path"]).parts:
                                errors.append("evidence_not_independent_or_run_bound")
                            evidence_refs.add((ref["path"], ref["sha256"]))
                elif not isinstance(result.get("reason"), str) or not result["reason"].strip():
                    errors.append("nonpass_reason_missing")
        elif phase == "EVIDENCE_REPORT":
            refs = payload.get("evidence")
            if not isinstance(refs, list) or payload.get("review_status") != "pending":
                errors.append("evidence_report_invalid")
                continue
            declared = set()
            for ref in refs:
                path = _artifact(root, ref, "evidence_report", errors)
                if path and isinstance(ref, dict):
                    declared.add((ref["path"], ref["sha256"]))
            if declared != evidence_refs or len(refs) != len(declared):
                errors.append("evidence_report_coverage_mismatch")
    if executed_assertions == 0:
        errors.append("no_executed_assertions")
    return {"schema_version": 1, "status": "blocked" if errors else "review_required",
            "scope": "adapter_receipt_consistency_only", "run_id": run_id, "case_id": case_id,
            "adapter_id": adapter.get("id"), "error_codes": sorted(set(errors)),
            "product_verdict": "not_evaluated", "source_attested": False}
