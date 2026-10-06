"""Scaffold a private, controlled test asset repository the framework can audit.

The public framework deliberately ships no business knowledge. Teams keep real
accounts, internal domains, business rules and evidence in a separate private
repository. This module installs a non-destructive reference skeleton so that
repository can be created from the framework instead of being hand-copied.

The scaffold writes real SHA-256 hashes into ``knowledge/manifest.json`` so the
repository validates immediately. It never overwrites an existing file, never
reads credentials, and never contacts a network service.
"""

from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

# Package-relative source path -> destination path inside the private repository.
STARTER_FILES: tuple[tuple[str, str], ...] = (
    ("PRIVATE_REPOSITORY.md", "docs/PRIVATE_REPOSITORY.md"),
    (".gitignore", ".gitignore"),
    ("knowledge/INDEX.md", "knowledge/INDEX.md"),
    ("knowledge/system/ecosystem-map.md", "knowledge/system/ecosystem-map.md"),
    ("knowledge/modules/example-module/business-topology.md",
     "knowledge/modules/example-module/business-topology.md"),
    ("knowledge/test-risks/omission-risk-rules.json",
     "knowledge/test-risks/omission-risk-rules.json"),
    ("scripts/knowledge_registry.py", "scripts/knowledge_registry.py"),
)

MANIFEST_RELATIVE = "knowledge/manifest.json"

# entry_id, path, kind, status, modules, always_load, priority, load_when, reason
MANIFEST_ENTRIES: tuple[tuple[str, str, str, str, list[str], bool, int, list[str], str], ...] = (
    ("KNOWLEDGE-INDEX", "knowledge/INDEX.md", "guide", "reviewed", ["global"], True, 1, ["all"],
     "定义知识边界、状态与强制加载流程"),
    ("SYSTEM-ECOSYSTEM", "knowledge/system/ecosystem-map.md", "system_map", "reviewed",
     ["global"], True, 10,
     ["intake", "requirement", "assertion", "case_design", "readiness", "execution"],
     "恢复系统层级、平台边界与数据闭环"),
    ("MODULE-TOPOLOGY", "knowledge/modules/example-module/business-topology.md",
     "business_topology", "reviewed", ["example-module"], False, 30,
     ["requirement", "assertion", "case_design", "readiness", "execution", "triage"],
     "恢复目标模块的参与者、状态与上下游"),
    ("OMISSION-RISKS", "knowledge/test-risks/omission-risk-rules.json", "rule_set",
     "approved_test_method", ["global"], False, 50,
     ["assertion", "case_design", "readiness", "execution", "triage", "retrospective"],
     "把历史缺陷、用户纠正与误报转成后续测试设计检查"),
)

SAFE_REGISTRY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _default_registry_id(system_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", system_id).strip("-").upper()
    return f"{slug or 'PROJECT'}-LOCAL-KNOWLEDGE-001"


def _build_manifest(root: Path, *, registry_id: str, title: str) -> dict[str, Any]:
    entries = []
    for entry_id, relative, kind, status, modules, always_load, priority, load_when, reason in MANIFEST_ENTRIES:
        target = root / relative
        entries.append({
            "entry_id": entry_id,
            "path": relative,
            "kind": kind,
            "status": status,
            "modules": modules,
            "keywords": [],
            "load_when": load_when,
            "always_load": always_load,
            "priority": priority,
            "reason": reason,
            "sha256": _sha256(target),
            "size_bytes": target.stat().st_size,
        })
    from datetime import datetime, timezone

    return {
        "schema_version": 1,
        "registry_id": registry_id,
        "title": title,
        "mode": "local_only",
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "authoritative_policy": "产品经理最新明确决定与已审核正式基线定义业务预期；本地文件只提供受控镜像、测试方法和执行学习入口。",
        "remote_sync": {
            "enabled": False,
            "status": "not_configured",
            "note": "本地阶段不连接或写入任何外部知识库。",
        },
        "entries": entries,
    }


def scaffold_private_repository(
    root: Path,
    *,
    name: str | None = None,
    system_id: str | None = None,
    environments: Iterable[str] = (),
    platforms: Iterable[str] = (),
    registry_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Install the private-repository skeleton without overwriting existing files."""
    root = Path(root).resolve()
    profile = root / "ai-test.json"
    targets = {destination: root / destination for _, destination in STARTER_FILES}
    targets[MANIFEST_RELATIVE] = root / MANIFEST_RELATIVE

    existing = sorted(relative for relative, path in targets.items() if path.exists())
    if existing:
        return {
            "status": "blocked",
            "reason": "private_repo_target_exists",
            "root": str(root),
            "existing_files": existing,
            "notice": "Scaffold never overwrites existing files; move or remove them first.",
        }

    resolved_registry_id = registry_id or _default_registry_id(system_id or root.name)
    if not SAFE_REGISTRY_ID.fullmatch(resolved_registry_id):
        return {
            "status": "blocked",
            "reason": "registry_id_invalid",
            "root": str(root),
            "notice": "registry_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$",
        }

    profile_created = False
    if profile.exists():
        profile_note = "existing"
    else:
        if not name or not system_id:
            return {
                "status": "blocked",
                "reason": "project_profile_required",
                "root": str(root),
                "notice": "ai-test.json is absent; pass --name and --system-id to create it.",
            }
        from .project import initialize_project

        initialize_project(root, name=name, system_id=system_id,
                           environments=environments, platforms=platforms)
        profile_created = True
        profile_note = "created"

    source = resources.files("ai_test_framework.starter_private_repo")
    written = []
    for package_path, destination in STARTER_FILES:
        target = root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.joinpath(*Path(package_path).parts).read_bytes())
        written.append(destination)

    manifest = _build_manifest(root, registry_id=resolved_registry_id,
                               title=title or f"{name or root.name} 本地测试知识注册中心")
    _write_json(root / MANIFEST_RELATIVE, manifest)
    written.append(MANIFEST_RELATIVE)

    return {
        "schema_version": 1,
        "status": "created",
        "root": str(root),
        "project_profile": profile_note,
        "registry_id": resolved_registry_id,
        "files": sorted(written),
        "entry_count": len(manifest["entries"]),
        "next_actions": [
            "python3 scripts/knowledge_registry.py validate",
            "ai-test knowledge-audit --private-root <private-repo> --feature example-module --stage execution",
        ],
        "notice": ("Skeleton only: replace the placeholder knowledge, then run refresh and validate. "
                   "No credentials were read and no business expectation is defined."),
    }
