"""Artifact registry and state reconciliation for requirement work items."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .project import STAGES


ARTIFACT_STATUSES = (
    "generated",
    "validated",
    "review_pending",
    "review_exported",
    "review_validated",
    "approved",
    "synced",
    "not_applicable",
    "superseded",
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_SAFE_TYPE = re.compile(r"^[a-z][a-z0-9._-]{1,127}$")
_DISCOVERABLE_SUFFIXES = {".json", ".html", ".md"}
_DEFAULT_GATE_REQUIREMENTS = {
    "CASE_DESIGN": [
        {
            "artifact_type": "automation_readiness_plan",
            "acceptable_statuses": ["validated", "approved"],
        },
        {
            "artifact_type": "rule_review_receipt",
            "acceptable_statuses": ["review_validated", "approved"],
        },
        {
            "artifact_type": "rule_current_sync_disposition",
            "acceptable_statuses": ["synced", "not_applicable"],
        },
    ]
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _registry_path(root: Path, requirement_id: str) -> Path:
    return root / ".ai-test/work-items" / requirement_id / "artifacts.json"


def _item_root(root: Path, requirement_id: str) -> Path:
    return root / ".ai-test/work-items" / requirement_id


def _validate_identifier(value: str, field: str, pattern: re.Pattern) -> str:
    value = value.strip()
    if not pattern.fullmatch(value):
        raise ValueError(f"{field} 格式无效")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_artifact_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _stage_index(stage: str) -> int:
    try:
        return STAGES.index(stage)
    except ValueError:
        return -1


def _merge_default_gates(registry: Dict[str, Any]) -> bool:
    changed = False
    gates = registry.setdefault("gate_requirements", {})
    for gate_name, default_requirements in _DEFAULT_GATE_REQUIREMENTS.items():
        existing = gates.setdefault(gate_name, [])
        by_type = {item.get("artifact_type"): item for item in existing}
        for requirement in default_requirements:
            artifact_type = requirement["artifact_type"]
            if by_type.get(artifact_type) != requirement:
                existing[:] = [
                    item for item in existing if item.get("artifact_type") != artifact_type
                ]
                existing.append(requirement)
                changed = True
    return changed


def initialize_artifact_registry(root: Path, requirement_id: str) -> Dict[str, Any]:
    root = Path(root)
    registry_path = _registry_path(root, requirement_id)
    if registry_path.exists():
        registry = _read_json(registry_path)
        if _merge_default_gates(registry):
            registry["updated_at"] = _now()
            _write_json(registry_path, registry)
        return registry
    if not (_item_root(root, requirement_id) / "manifest.json").exists():
        raise FileNotFoundError(f"未找到需求 {requirement_id}")
    created_at = _now()
    registry = {
        "schema_version": 1,
        "requirement_id": requirement_id,
        "gate_requirements": _DEFAULT_GATE_REQUIREMENTS,
        "artifacts": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
    _write_json(registry_path, registry)
    return registry


def summarize_work_item_artifacts(root: Path, requirement_id: str) -> Dict[str, Any]:
    registry_path = _registry_path(Path(root), requirement_id)
    if not registry_path.exists():
        return {
            "registry_status": "missing",
            "total": 0,
            "by_type": {},
            "by_status": {},
            "review_pending": 0,
        }
    registry = _read_json(registry_path)
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for artifact in registry.get("artifacts", []):
        artifact_type = artifact.get("artifact_type", "unknown")
        status = artifact.get("status", "unknown")
        by_type[artifact_type] = by_type.get(artifact_type, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "registry_status": "ready",
        "total": len(registry.get("artifacts", [])),
        "by_type": by_type,
        "by_status": by_status,
        "review_pending": by_status.get("review_pending", 0),
        "updated_at": registry.get("updated_at"),
    }


def register_work_item_artifact(
    root: Path,
    *,
    requirement_id: str,
    artifact_id: str,
    artifact_type: str,
    path: str,
    status: str,
    stage: str,
    baseline_id: Optional[str] = None,
    run_id: Optional[str] = None,
    parent_artifact_id: Optional[str] = None,
) -> Dict[str, Any]:
    root = Path(root)
    artifact_id = _validate_identifier(artifact_id, "artifact_id", _SAFE_ID)
    artifact_type = _validate_identifier(artifact_type, "artifact_type", _SAFE_TYPE)
    if status not in ARTIFACT_STATUSES:
        raise ValueError(f"未知产物状态 {status}")
    if stage not in STAGES:
        raise ValueError(f"未知阶段 {stage}")
    if parent_artifact_id is not None:
        parent_artifact_id = _validate_identifier(parent_artifact_id, "parent_artifact_id", _SAFE_ID)
    artifact_path = _resolve_artifact_path(root, path)
    if not artifact_path.is_file():
        raise FileNotFoundError(f"产物不存在或不是文件：{artifact_path}")

    registry = initialize_artifact_registry(root, requirement_id)
    if artifact_type == "automation_script":
        acceptable = {"validated", "approved"}
        reuse_receipt = next(
            (
                item
                for item in registry.get("artifacts", [])
                if item.get("artifact_type") == "automation_asset_reuse_receipt"
                and item.get("status") in acceptable
                and (run_id is None or item.get("run_id") == run_id)
                and _resolve_artifact_path(root, item["path"]).is_file()
                and _sha256(_resolve_artifact_path(root, item["path"])) == item.get("sha256")
            ),
            None,
        )
        if reuse_receipt is None:
            raise ValueError(
                "automation_asset_reuse_receipt_required:新增或更新自动化脚本前必须登记同一运行的已校验资产复用回执"
            )
    now = _now()
    previous = next(
        (item for item in registry.get("artifacts", []) if item.get("artifact_id") == artifact_id),
        None,
    )
    artifact = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "path": path,
        "sha256": _sha256(artifact_path),
        "status": status,
        "stage": stage,
        "baseline_id": baseline_id,
        "run_id": run_id,
        "parent_artifact_id": parent_artifact_id,
        "registered_at": previous.get("registered_at", now) if previous else now,
        "updated_at": now,
    }
    registry["artifacts"] = [
        item for item in registry.get("artifacts", []) if item.get("artifact_id") != artifact_id
    ] + [artifact]
    registry["updated_at"] = now
    _write_json(_registry_path(root, requirement_id), registry)

    state_path = _item_root(root, requirement_id) / "workflow-state.json"
    current_stage = _read_json(state_path).get("stage", "INTAKE")
    if _stage_index(stage) > _stage_index(current_stage):
        from .work_items import update_work_item

        update_work_item(root, requirement_id=requirement_id, stage=stage)
        current_stage = stage

    return {
        "status": "registered",
        "requirement_id": requirement_id,
        "current_stage": current_stage,
        "artifact": artifact,
    }


def _evaluate_gate(
    registry: Dict[str, Any],
    gate_name: str,
    valid_artifact_ids: Iterable[str],
) -> Dict[str, Any]:
    valid_ids = set(valid_artifact_ids)
    requirements = registry.get("gate_requirements", {}).get(gate_name, [])
    missing: List[Dict[str, Any]] = []
    satisfied: List[Dict[str, Any]] = []
    for requirement in requirements:
        artifact_type = requirement["artifact_type"]
        acceptable = set(requirement.get("acceptable_statuses", []))
        match = next(
            (
                artifact
                for artifact in registry.get("artifacts", [])
                if artifact.get("artifact_id") in valid_ids
                and artifact.get("artifact_type") == artifact_type
                and artifact.get("status") in acceptable
            ),
            None,
        )
        if match:
            satisfied.append({"artifact_type": artifact_type, "artifact_id": match["artifact_id"]})
        else:
            missing.append(
                {
                    "artifact_type": artifact_type,
                    "acceptable_statuses": sorted(acceptable),
                }
            )
    return {
        "status": "passed" if not missing else "blocked",
        "satisfied": satisfied,
        "missing": missing,
    }


def evaluate_stage_entry_gate(root: Path, requirement_id: str, stage: str) -> Dict[str, Any]:
    """Validate registered, unchanged artifacts required before entering a gated stage."""
    root = Path(root)
    registry = initialize_artifact_registry(root, requirement_id)
    valid_artifact_ids: List[str] = []
    invalid_artifacts: List[Dict[str, Any]] = []
    for artifact in registry.get("artifacts", []):
        artifact_path = _resolve_artifact_path(root, artifact["path"])
        if not artifact_path.is_file():
            invalid_artifacts.append(
                {"artifact_id": artifact["artifact_id"], "reason": "missing"}
            )
            continue
        if _sha256(artifact_path) != artifact.get("sha256"):
            invalid_artifacts.append(
                {"artifact_id": artifact["artifact_id"], "reason": "hash_mismatch"}
            )
            continue
        valid_artifact_ids.append(artifact["artifact_id"])
    gate = _evaluate_gate(registry, stage, valid_artifact_ids)
    gate["invalid_artifacts"] = invalid_artifacts
    return gate


def _discover_unregistered(
    root: Path,
    manifest: Dict[str, Any],
    registry: Dict[str, Any],
    discover_roots: Iterable[Path],
) -> List[Dict[str, Any]]:
    registered = {
        str(_resolve_artifact_path(root, artifact["path"]))
        for artifact in registry.get("artifacts", [])
        if artifact.get("path")
    }
    needles = [
        value
        for value in (
            manifest.get("requirement_id"),
            manifest.get("title"),
            manifest.get("feature"),
        )
        if value
    ]
    found: List[Dict[str, Any]] = []
    inspected = 0
    for discover_root in discover_roots:
        discover_root = Path(discover_root).expanduser().resolve()
        if not discover_root.exists():
            continue
        candidates = [discover_root] if discover_root.is_file() else discover_root.rglob("*")
        for candidate in candidates:
            if inspected >= 5000:
                return found
            if not candidate.is_file() or candidate.suffix.lower() not in _DISCOVERABLE_SUFFIXES:
                continue
            if ".git" in candidate.parts or str(candidate.resolve()) in registered:
                continue
            inspected += 1
            try:
                if candidate.stat().st_size > 10 * 1024 * 1024:
                    continue
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            matches = [needle for needle in needles if needle in text]
            if matches:
                found.append(
                    {
                        "code": "UNREGISTERED_ARTIFACT",
                        "message": "发现包含当前需求身份但未登记的产物",
                        "path": str(candidate),
                        "matched_identity": matches[0],
                    }
                )
    return found


def reconcile_work_item(
    root: Path,
    requirement_id: str,
    *,
    discover_roots: Optional[Iterable[Path]] = None,
    apply: bool = False,
) -> Dict[str, Any]:
    root = Path(root)
    item_root = _item_root(root, requirement_id)
    manifest_path = item_root / "manifest.json"
    state_path = item_root / "workflow-state.json"
    if not manifest_path.exists() or not state_path.exists():
        raise FileNotFoundError(f"未找到需求 {requirement_id}")
    manifest = _read_json(manifest_path)
    state = _read_json(state_path)
    registry = initialize_artifact_registry(root, requirement_id)
    issues: List[Dict[str, Any]] = []
    valid_artifact_ids: List[str] = []
    stage_candidates: List[str] = []

    for artifact in registry.get("artifacts", []):
        artifact_path = _resolve_artifact_path(root, artifact["path"])
        if not artifact_path.is_file():
            issues.append(
                {
                    "code": "ARTIFACT_MISSING",
                    "message": "已登记产物不存在",
                    "artifact_id": artifact["artifact_id"],
                    "path": str(artifact_path),
                }
            )
            continue
        actual_sha256 = _sha256(artifact_path)
        if actual_sha256 != artifact.get("sha256"):
            issues.append(
                {
                    "code": "ARTIFACT_HASH_MISMATCH",
                    "message": "已登记产物内容已变化，必须重新登记或保留新版本",
                    "artifact_id": artifact["artifact_id"],
                    "path": str(artifact_path),
                    "registered_sha256": artifact.get("sha256"),
                    "actual_sha256": actual_sha256,
                }
            )
            continue
        valid_artifact_ids.append(artifact["artifact_id"])
        if artifact.get("status") != "superseded" and artifact.get("stage") in STAGES:
            stage_candidates.append(artifact["stage"])

    if discover_roots:
        issues.extend(_discover_unregistered(root, manifest, registry, discover_roots))

    derived_stage = max(stage_candidates, key=_stage_index) if stage_candidates else None
    if derived_stage and _stage_index(state["stage"]) < _stage_index(derived_stage):
        issues.append(
            {
                "code": "STATE_BEHIND_ARTIFACTS",
                "message": "工作项阶段落后于已登记且校验通过的产物",
                "current_stage": state["stage"],
                "derived_stage": derived_stage,
            }
        )

    case_design_gate = _evaluate_gate(registry, "CASE_DESIGN", valid_artifact_ids)
    if _stage_index(state["stage"]) >= _stage_index("CASE_DESIGN") and case_design_gate["status"] != "passed":
        issues.append(
            {
                "code": "CASE_DESIGN_GATE_BYPASSED",
                "message": "工作项已进入用例设计，但缺少准备度计划或规则审核回执",
                "missing": case_design_gate["missing"],
            }
        )

    applied_stage = None
    if apply and derived_stage and _stage_index(state["stage"]) < _stage_index(derived_stage):
        from .work_items import update_work_item

        update_work_item(root, requirement_id=requirement_id, stage=derived_stage)
        applied_stage = derived_stage
        issues = [item for item in issues if item.get("code") != "STATE_BEHIND_ARTIFACTS"]

    receipt = {
        "schema_version": 1,
        "requirement_id": requirement_id,
        "generated_at": _now(),
        "consistency_status": "consistent" if not issues else "inconsistent",
        "current_stage": applied_stage or state["stage"],
        "artifact_derived_stage": derived_stage,
        "applied_stage": applied_stage,
        "artifact_summary": summarize_work_item_artifacts(root, requirement_id),
        "case_design_gate": case_design_gate,
        "issues": issues,
    }
    receipt["status"] = "ready" if not issues else "inconsistent"
    _write_json(item_root / "reconciliation-receipt.json", receipt)
    return receipt
