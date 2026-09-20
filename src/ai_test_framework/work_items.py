"""Per-requirement state and handoff packages for multi-conversation testing."""

import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .project import STAGES


WORK_ITEM_STATUSES = ("planned", "active", "blocked", "complete", "cancelled")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def _index_lock(root: Path):
    lock_path = root / ".ai-test/work-items/index.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            import fcntl
        except ImportError:
            yield
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _validate_id(requirement_id: str) -> None:
    if not _SAFE_ID.fullmatch(requirement_id):
        raise ValueError("requirement_id 只能包含字母、数字、点、下划线和连字符，长度为 2-128")


def initialize_work_item_index(root: Path) -> Dict[str, Any]:
    root = Path(root)
    index_path = root / ".ai-test/work-items/index.json"
    if index_path.exists():
        index = _read_json(index_path)
    else:
        index = {"schema_version": 1, "updated_at": _now(), "items": []}
        _write_json(index_path, index)
    _render_overview(root, index)
    return index


def _render_overview(root: Path, index: Dict[str, Any]) -> None:
    lines = [
        "# 测试需求工作台",
        "",
        "> 该文件由 `ai-test work-item-*` 自动生成。每个需求使用独立任务和独立状态目录。",
        "",
        "## 当前需求",
        "",
    ]
    items = sorted(index.get("items", []), key=lambda item: item.get("updated_at", ""), reverse=True)
    if not items:
        lines.append("暂无测试需求。使用 `ai-test work-item-create` 创建第一项。")
    else:
        lines.extend([
            "| 需求ID | 标题 | 功能 | 状态 | 阶段 | 环境 | 平台 | 最近更新 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for item in items:
            lines.append(
                "| {requirement_id} | {title} | {feature} | {status} | {stage} | {environments} | {platforms} | {updated_at} |".format(
                    requirement_id=item["requirement_id"],
                    title=item["title"].replace("|", "／"),
                    feature=item["feature"].replace("|", "／"),
                    status=item["status"],
                    stage=item["stage"],
                    environments="、".join(item.get("environments", [])),
                    platforms="、".join(item.get("platforms", [])),
                    updated_at=item.get("updated_at", ""),
                )
            )
    lines.extend([
        "",
        "## 新任务怎么接手",
        "",
        "在新的 Codex、WorkBuddy 或其他 Agent 任务中只需说：`接手需求 REQ-XXX`。",
        "Agent 必须先运行 `ai-test work-item-show --root . --requirement-id REQ-XXX`，再按返回的文件顺序恢复上下文。",
        "",
    ])
    (root / "TEST_WORK_ITEMS.md").write_text("\n".join(lines), encoding="utf-8")


def _index_entry(manifest: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "requirement_id": manifest["requirement_id"],
        "title": manifest["title"],
        "feature": manifest["feature"],
        "status": state["status"],
        "stage": state["stage"],
        "environments": manifest["environments"],
        "platforms": manifest["platforms"],
        "updated_at": state["updated_at"],
        "path": f".ai-test/work-items/{manifest['requirement_id']}",
    }


def _upsert_index(root: Path, manifest: Dict[str, Any], state: Dict[str, Any]) -> None:
    with _index_lock(root):
        index = initialize_work_item_index(root)
        entry = _index_entry(manifest, state)
        items = [
            item for item in index.get("items", [])
            if item.get("requirement_id") != manifest["requirement_id"]
        ]
        items.append(entry)
        index["items"] = items
        index["updated_at"] = _now()
        _write_json(root / ".ai-test/work-items/index.json", index)
        _render_overview(root, index)


def create_work_item(
    root: Path,
    *,
    requirement_id: str,
    title: str,
    feature: str,
    environments: Iterable[str],
    platforms: Iterable[str],
    scope: str,
) -> Dict[str, Any]:
    root = Path(root)
    _validate_id(requirement_id)
    environments = _unique(environments)
    platforms = _unique(platforms)
    if not title.strip() or not feature.strip() or not scope.strip():
        raise ValueError("title、feature 和 scope 不能为空")
    if not environments or not platforms:
        raise ValueError("至少需要一个环境和一个平台")
    item_root = root / ".ai-test/work-items" / requirement_id
    manifest_path = item_root / "manifest.json"
    expected_identity = {
        "requirement_id": requirement_id,
        "title": title.strip(),
        "feature": feature.strip(),
        "environments": environments,
        "platforms": platforms,
        "scope": scope.strip(),
    }
    if manifest_path.exists():
        existing = _read_json(manifest_path)
        if any(existing.get(key) != value for key, value in expected_identity.items()):
            raise ValueError(f"需求 {requirement_id} 已存在且元数据不同，请使用 work-item-update")
        return {**show_work_item(root, requirement_id), "status": "exists", "idempotent": True}

    created_at = _now()
    manifest = {
        "schema_version": 1,
        **expected_identity,
        "created_at": created_at,
        "updated_at": created_at,
        "official_baseline": {"id": None, "path": None, "sha256": None},
    }
    state = {
        "schema_version": 1,
        "requirement_id": requirement_id,
        "status": "planned",
        "stage": "INTAKE",
        "allowed_stages": STAGES,
        "summary": "需求已登记，等待完成来源与范围确认。",
        "completed": [],
        "blockers": [],
        "next_steps": ["确认需求来源、目标功能、环境、平台和候选测试范围"],
        "active_run": None,
        "owner": "unassigned",
        "updated_at": created_at,
    }
    handoff = _build_handoff(manifest, state)
    asset_links = {
        "schema_version": 1,
        "requirement_id": requirement_id,
        "system_assets": [],
        "feature_assets": [],
        "automation_assets": [],
        "reports": [],
        "evidence": [],
        "updated_at": created_at,
    }
    _write_json(manifest_path, manifest)
    _write_json(item_root / "workflow-state.json", state)
    _write_json(item_root / "handoff.json", handoff)
    _write_json(item_root / "asset-links.json", asset_links)
    (item_root / "decisions.md").write_text(
        f"# {requirement_id} 决策记录\n\n"
        "只记录已经确认且会影响后续测试的业务口径。不得记录账号、密码、Cookie、Token或客户隐私数据。\n\n"
        "| 日期 | 决策 | 来源 | 影响 |\n"
        "| --- | --- | --- | --- |\n",
        encoding="utf-8",
    )
    _upsert_index(root, manifest, state)
    return {**show_work_item(root, requirement_id), "status": "created"}


def _build_handoff(manifest: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "requirement_id": manifest["requirement_id"],
        "title": manifest["title"],
        "feature": manifest["feature"],
        "current_stage": state["stage"],
        "status": state["status"],
        "summary": state["summary"],
        "completed": state["completed"],
        "blockers": state["blockers"],
        "next_steps": state["next_steps"],
        "owner": state["owner"],
        "official_baseline": manifest["official_baseline"],
        "asset_links_path": "asset-links.json",
        "decisions_path": "decisions.md",
        "updated_at": state["updated_at"],
    }


def update_work_item(
    root: Path,
    *,
    requirement_id: str,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    summary: Optional[str] = None,
    completed: Optional[Iterable[str]] = None,
    blockers: Optional[Iterable[str]] = None,
    next_steps: Optional[Iterable[str]] = None,
    owner: Optional[str] = None,
    baseline_id: Optional[str] = None,
    baseline_path: Optional[str] = None,
    baseline_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    root = Path(root)
    _validate_id(requirement_id)
    item_root = root / ".ai-test/work-items" / requirement_id
    manifest_path = item_root / "manifest.json"
    state_path = item_root / "workflow-state.json"
    if not manifest_path.exists() or not state_path.exists():
        raise FileNotFoundError(f"未找到需求 {requirement_id}，请先运行 work-item-create")
    manifest = _read_json(manifest_path)
    state = _read_json(state_path)
    if stage is not None:
        if stage not in STAGES:
            raise ValueError(f"未知阶段 {stage}")
        state["stage"] = stage
    if status is not None:
        if status not in WORK_ITEM_STATUSES:
            raise ValueError(f"未知状态 {status}")
        state["status"] = status
    if summary is not None:
        state["summary"] = summary.strip()
    if completed is not None:
        state["completed"] = _unique(completed)
    if blockers is not None:
        state["blockers"] = _unique(blockers)
    if next_steps is not None:
        state["next_steps"] = _unique(next_steps)
    if owner is not None:
        state["owner"] = owner.strip() or "unassigned"
    if any(value is not None for value in (baseline_id, baseline_path, baseline_sha256)):
        baseline = manifest["official_baseline"]
        if baseline_id is not None:
            baseline["id"] = baseline_id
        if baseline_path is not None:
            baseline["path"] = baseline_path
        if baseline_sha256 is not None:
            baseline["sha256"] = baseline_sha256
    updated_at = _now()
    state["updated_at"] = updated_at
    manifest["updated_at"] = updated_at
    _write_json(manifest_path, manifest)
    _write_json(state_path, state)
    _write_json(item_root / "handoff.json", _build_handoff(manifest, state))
    _upsert_index(root, manifest, state)
    return {**show_work_item(root, requirement_id), "status": "updated"}


def show_work_item(root: Path, requirement_id: str) -> Dict[str, Any]:
    root = Path(root)
    _validate_id(requirement_id)
    item_root = root / ".ai-test/work-items" / requirement_id
    manifest_path = item_root / "manifest.json"
    state_path = item_root / "workflow-state.json"
    if not manifest_path.exists() or not state_path.exists():
        raise FileNotFoundError(f"未找到需求 {requirement_id}")
    manifest = _read_json(manifest_path)
    state = _read_json(state_path)
    relative_root = f".ai-test/work-items/{requirement_id}"
    return {
        "status": "ready",
        "requirement_id": requirement_id,
        "title": manifest["title"],
        "feature": manifest["feature"],
        "current_status": state["status"],
        "current_stage": state["stage"],
        "summary": state["summary"],
        "completed": state["completed"],
        "blockers": state["blockers"],
        "next_steps": state["next_steps"],
        "owner": state["owner"],
        "official_baseline": manifest["official_baseline"],
        "read_first": [
            f"{relative_root}/manifest.json",
            f"{relative_root}/workflow-state.json",
            f"{relative_root}/handoff.json",
            f"{relative_root}/decisions.md",
            f"{relative_root}/asset-links.json",
        ],
        "takeover_prompt": f"接手需求 {requirement_id}，按工作项状态继续，不重复已完成步骤。",
    }


def list_work_items(root: Path) -> Dict[str, Any]:
    index = initialize_work_item_index(Path(root))
    return {"status": "ready", "items": index.get("items", []), "count": len(index.get("items", []))}
