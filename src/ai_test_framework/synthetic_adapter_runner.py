"""In-process SDK runner for local/synthetic, read-only adapters only.

This is not a sandbox: callable adapters are trusted caller code and can have
arbitrary Python side effects. Never use it for a real product environment.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Any, Protocol

from .adapter_trace import check_adapter_trace
from .execution_contract import _artifact, _json, check_execution_probe, digest
from .execution_readiness import _assert_no_sensitive_fields


class SyntheticReadAdapter(Protocol):
    adapter_id: str
    platform: str
    source: dict[str, str]

    def observe(self, probe: dict[str, Any]) -> dict[str, Any]: ...
    def read(self, probe: dict[str, Any]) -> dict[str, Any]: ...
    def readback(self, probe: dict[str, Any]) -> dict[str, Any]: ...
    def evaluate(self, probe: dict[str, Any], observed: dict[str, Any], oracle: Any) -> list[dict[str, Any]]: ...


def run_synthetic_readonly_adapter(probe: dict[str, Any], adapter: SyntheticReadAdapter, root: Path) -> dict[str, Any]:
    """Call the adapter once on a local synthetic fixture; never retry on uncertainty.

    The caller supplies a reviewed adapter object; no dynamic imports or shell
    commands. Snapshot/trace outputs are created exclusively, not overwritten.
    """
    root = Path(root).resolve()
    checked = check_execution_probe(probe, root)
    if checked["status"] != "passed":
        return {"status": "blocked", "error_codes": checked["error_codes"]}
    if probe["action"]["kind"] != "read":
        return {"status": "blocked", "error_codes": ["write_adapter_not_available"]}
    errors: list[str] = []
    profile = _json(_artifact(root, probe.get("profile"), "profile", errors), "profile", errors)
    if not isinstance(profile, dict) or profile.get("stage") != "local" or profile.get("zone") != "synthetic":
        errors.append("only_local_synthetic_adapters_available")
    adapter_meta = {"id": getattr(adapter, "adapter_id", None), "platform": getattr(adapter, "platform", None),
                    "source": getattr(adapter, "source", None)}
    source_path = _artifact(root, adapter_meta["source"], "adapter_source", errors)
    try:
        implementation_path = Path(inspect.getfile(type(adapter))).resolve()
    except (TypeError, OSError):
        implementation_path = None
    if (not isinstance(adapter_meta["id"], str) or adapter_meta["platform"] not in {"web", "api", "app", "h5", "miniapp", "device"}
            or source_path is None or source_path.suffix != ".py" or implementation_path != source_path):
        errors.append("adapter_source_or_identity_invalid")
    run_id = probe["run_id"]
    run_dir = root / "runs" / run_id
    if (not run_id or Path(run_id).name != run_id or not run_dir.is_dir()
            or (run_dir / "adapter-trace.json").exists() or (run_dir / "adapter-read-result.json").exists()):
        errors.append("run_output_missing_or_already_used")
    if errors:
        return {"status": "blocked", "error_codes": sorted(set(errors))}
    fixture, action = probe["fixture"], probe["action"]
    try:
        observed = adapter.observe(probe)
        if not isinstance(observed, dict) or any(observed.get(k) != fixture.get(k) for k in ("id", "business_key", "pre_state_sha256", "match_count")) or observed.get("match_count") != 1:
            return {"status": "blocked", "error_codes": ["observed_fixture_not_unique_or_drifted"]}
        if check_execution_probe(probe, root)["status"] != "passed":
            return {"status": "blocked", "error_codes": ["probe_stale_before_action"]}
        # Trust boundary: read() is a supplied Python callback, not a sandboxed IO primitive.
        result = adapter.read(probe)
        if not isinstance(result, dict):
            raise ValueError("adapter result must be an object")
        _assert_no_sensitive_fields(result)
        snapshot = adapter.readback(probe)
        if not isinstance(snapshot, dict) or any(snapshot.get(k) != fixture.get(fk) for k, fk in (("fixture_id", "id"), ("business_key", "business_key"))) or snapshot.get("match_count") != 1:
            return {"status": "blocked", "error_codes": ["readback_identity_or_state_invalid"]}
        state_sha = snapshot.get("state_sha256")
        if not isinstance(state_sha, str) or len(state_sha) != 64 or any(c not in "0123456789abcdef" for c in state_sha):
            return {"status": "blocked", "error_codes": ["readback_identity_or_state_invalid"]}
        oracle = _json(_artifact(root, probe["oracle"], "oracle", errors), "oracle", errors)
        if errors:
            return {"status": "blocked", "error_codes": sorted(set(errors))}
        assertions = adapter.evaluate(probe, result, oracle)
        if not isinstance(assertions, list) or len(assertions) != len(probe["assertion_ids"]):
            return {"status": "blocked", "error_codes": ["assertion_set_mismatch"]}
        if any(not isinstance(item, dict) or item.get("id") not in probe["assertion_ids"] or item.get("status") not in {"passed", "failed", "blocked", "not_executed"} for item in assertions):
            return {"status": "blocked", "error_codes": ["assertion_invalid"]}
        # Store only synthetic observations. A snapshot is created once, even if later review blocks.
        body = json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")
        snapshot_path = run_dir / "adapter-read-result.json"
        fd = os.open(snapshot_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        evidence = {"path": snapshot_path.relative_to(root).as_posix(), "sha256": hashlib.sha256(body).hexdigest()}
        verdict = []
        for item in assertions:
            entry = {"id": item["id"], "status": item["status"]}
            if entry["status"] in {"passed", "failed"}:
                entry.update({"oracle": probe["oracle"], "evidence": [evidence]})
            else:
                entry["reason"] = item.get("reason", "not evaluated by adapter")
            verdict.append(entry)
        evidence_list = [evidence] if any(x["status"] in {"passed", "failed"} for x in verdict) else []
        payloads = [observed, {**action, "profile_sha256": probe["profile_sha256"]},
                    {"action_id": action["id"], "attempt_count": 1, "result": "observed"}, snapshot,
                    {"assertions": verdict}, {"evidence": evidence_list, "review_status": "pending"}]
        phases = ("OBSERVED", "ACTION_GUARDED", "EXECUTED_ONCE", "READBACK", "VERDICT", "EVIDENCE_REPORT")
        previous = digest({"run_id": run_id, "case_id": probe["case_id"], "probe_sha256": digest(probe),
                           "adapter_sha256": adapter_meta["source"]["sha256"]})
        steps = []
        for phase, payload in zip(phases, payloads):
            step = {"phase": phase, "run_id": run_id, "case_id": probe["case_id"],
                    "fixture_id": fixture["id"], "probe_sha256": digest(probe),
                    "adapter_sha256": adapter_meta["source"]["sha256"],
                    "previous_sha256": previous, "payload": payload}
            steps.append(step)
            previous = digest(step)
        trace = {"schema_version": 1, "probe": probe, "adapter": adapter_meta, "steps": steps}
        checked_trace = check_adapter_trace(trace, root)
        if checked_trace["status"] != "review_required":
            return checked_trace
        trace_path = run_dir / "adapter-trace.json"
        fd = os.open(trace_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(trace, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        return {**checked_trace, "trace_path": trace_path.relative_to(root).as_posix()}
    except Exception as exc:
        # Intentionally no second attempt: the callback may have had side effects.
        return {"status": "blocked", "error_codes": ["adapter_outcome_unknown_no_retry"],
                "phase_error_type": type(exc).__name__, "product_verdict": "not_evaluated"}
