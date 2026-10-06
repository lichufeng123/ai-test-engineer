#!/usr/bin/env python3
"""Reference local knowledge registry for an AI Test Engineer private repository.

Place this file at ``<private-repo>/scripts/knowledge_registry.py`` and keep the
registry manifest at ``<private-repo>/knowledge/manifest.json``.

The framework reads the repository through ``ai-test knowledge-audit``, which runs
``validate`` and then ``load`` and independently re-checks every returned path and
hash. This script is deliberately local-only:

* it never contacts a network service;
* it never promotes a learning candidate into a product rule;
* it only routes and hash-binds local knowledge. It cannot prove that an agent
  read or understood a file, and it cannot certify a remote "Current" baseline.

Commands
--------
validate  Check the manifest, entry fields, path safety and file hashes.
load      Return the ordered list of required reads for a feature and stage.
refresh   Recompute hashes after a reviewed local edit.

Only the Python standard library is used, so the script runs on any clone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "knowledge"
MANIFEST_PATH = KNOWLEDGE_ROOT / "manifest.json"

STAGES = ["intake", "requirement", "assertion", "case_design", "readiness", "execution", "triage", "retrospective"]
KINDS = ["guide", "system_map", "business_topology", "rule_set", "test_method", "learning_inbox", "asset_register", "environment"]
ALLOWED_STATUSES = {"reviewed", "approved_test_method", "pending_review", "conflict_open", "deprecated"}
READABLE_STATUSES = {"reviewed", "approved_test_method"}
SAFE_ENTRY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_registered_path(raw: Any) -> Path:
    """Resolve a manifest path, refusing absolute paths and '..' traversal."""
    if not isinstance(raw, str) or not raw:
        raise ValueError("注册路径必须是非空字符串")
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"注册路径必须位于仓库内且不含 ..：{raw}")
    resolved = (ROOT / candidate).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"注册路径越出仓库根目录：{raw}")
    return resolved


def validate_registry() -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.exists():
        return [f"Manifest不存在：{MANIFEST_PATH}"]
    try:
        manifest = read_json(MANIFEST_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"Manifest读取失败：{error}"]
    if not isinstance(manifest, dict):
        return ["Manifest必须是JSON对象"]

    if manifest.get("schema_version") != 1:
        errors.append("manifest.schema_version 必须为 1")
    if manifest.get("mode") != "local_only":
        errors.append("manifest.mode 必须为 local_only")
    remote_sync = manifest.get("remote_sync") or {}
    if remote_sync.get("enabled") is not False:
        errors.append("本地阶段 remote_sync.enabled 必须为 false")

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("manifest.entries 必须是非空数组")
        return errors

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, entry in enumerate(entries):
        prefix = f"manifest.entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        entry_id = entry.get("entry_id")
        raw_path = entry.get("path")
        if not isinstance(entry_id, str) or not SAFE_ENTRY_ID.fullmatch(entry_id):
            errors.append(f"{prefix} entry_id 非法")
        elif entry_id in seen_ids:
            errors.append(f"{prefix} entry_id 重复：{entry_id}")
        else:
            seen_ids.add(entry_id)
        if entry.get("kind") not in KINDS:
            errors.append(f"{prefix} 不支持的 kind：{entry.get('kind')}")
        if entry.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{prefix} 不支持的状态：{entry.get('status')}")
        if not isinstance(entry.get("modules"), list) or not entry["modules"]:
            errors.append(f"{prefix} modules 必须是非空数组")
        if not raw_path:
            errors.append(f"{prefix} 缺少 path")
            continue
        if raw_path in seen_paths:
            errors.append(f"{prefix} path 重复：{raw_path}")
        seen_paths.add(raw_path)
        try:
            path = resolve_registered_path(raw_path)
        except ValueError as error:
            errors.append(str(error))
            continue
        if not path.is_file():
            errors.append(f"{prefix} 文件不存在：{raw_path}")
            continue
        expected_hash = entry.get("sha256")
        actual_hash = sha256_file(path)
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            errors.append(f"{prefix} 缺少合法 sha256；先执行 refresh")
        elif expected_hash != actual_hash:
            errors.append(f"{prefix} SHA-256 不一致：{raw_path}；先审核修改再执行 refresh")
    return errors


def refresh_manifest() -> dict[str, Any]:
    manifest = read_json(MANIFEST_PATH)
    for entry in manifest.get("entries", []):
        path = resolve_registered_path(entry["path"])
        if not path.is_file():
            raise FileNotFoundError(f"无法刷新不存在的文件：{entry['path']}")
        entry["sha256"] = sha256_file(path)
        entry["size_bytes"] = path.stat().st_size
    manifest["updated_at"] = now_iso()
    write_json(MANIFEST_PATH, manifest)
    return manifest


def normalize(value: str) -> str:
    return re.sub(r"[\s_\-/]+", "", str(value).casefold())


def feature_matches(entry: dict[str, Any], feature: str | None) -> bool:
    if entry.get("always_load"):
        return True
    modules = [str(value) for value in entry.get("modules", [])]
    if "global" in modules:
        return True
    if not feature:
        return False
    target = normalize(feature)
    candidates = modules + [str(value) for value in entry.get("keywords", [])]
    return any(target in normalize(value) or normalize(value) in target for value in candidates)


def stage_matches(entry: dict[str, Any], stage: str | None) -> bool:
    stages = entry.get("load_when") or ["all"]
    return not stage or "all" in stages or stage in stages


def platform_matches(entry: dict[str, Any], platform: str | None) -> bool:
    declared = entry.get("platforms") or []
    return not declared or platform in declared


def role_matches(entry: dict[str, Any], role: str | None) -> bool:
    declared = entry.get("roles") or []
    return not declared or role in declared


def load_context(args: argparse.Namespace) -> int:
    errors = validate_registry()
    if errors:
        print(json.dumps({"status": "failed", "error_count": len(errors), "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    manifest = read_json(MANIFEST_PATH)
    entries = manifest["entries"]
    priorities = {entry["entry_id"]: entry.get("priority", 100) for entry in entries}

    selected: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("kind") == "learning_inbox" and not args.include_candidates:
            continue
        if entry.get("status") not in READABLE_STATUSES:
            continue
        if not feature_matches(entry, args.feature) or not stage_matches(entry, args.stage):
            continue
        if not platform_matches(entry, args.platform) or not role_matches(entry, args.role):
            continue
        selected.append(
            {
                "entry_id": entry["entry_id"],
                "kind": entry["kind"],
                "path": entry["path"],
                "absolute_path": str(resolve_registered_path(entry["path"])),
                "status": entry["status"],
                "sha256": entry["sha256"],
                "reason": entry.get("reason", "registered knowledge"),
            }
        )
    selected.sort(key=lambda item: priorities[item["entry_id"]])
    result = {
        "status": "passed",
        "mode": "local_only",
        "request": {
            "feature": args.feature,
            "stage": args.stage,
            "platform": args.platform,
            "role": args.role,
            "include_candidates": args.include_candidates,
        },
        "required_read_count": len(selected),
        "required_reads": selected,
        "notice": "必须实际读取 required_reads；本回执只证明本地路径与哈希，不替代规则理解，也不代表远端 Current。",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_validate(_: argparse.Namespace) -> int:
    errors = validate_registry()
    if errors:
        print(json.dumps({"status": "failed", "error_count": len(errors), "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    manifest = read_json(MANIFEST_PATH)
    print(json.dumps({"status": "passed", "entry_count": len(manifest["entries"]), "mode": manifest["mode"],
                      "updated_at": manifest.get("updated_at")}, ensure_ascii=False, indent=2))
    return 0


def command_refresh(_: argparse.Namespace) -> int:
    manifest = refresh_manifest()
    print(json.dumps({"status": "refreshed", "entry_count": len(manifest["entries"]),
                      "updated_at": manifest["updated_at"]}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地测试知识注册中心（local_only）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="校验 manifest、字段、路径安全与文件哈希")
    validate_parser.set_defaults(func=command_validate)

    refresh_parser = subparsers.add_parser("refresh", help="审核本地修改后刷新受控文件哈希")
    refresh_parser.set_defaults(func=command_refresh)

    load_parser = subparsers.add_parser("load", help="按功能与阶段返回必须读取的本地知识")
    load_parser.add_argument("--feature", help="功能名或别名")
    load_parser.add_argument("--stage", choices=STAGES)
    load_parser.add_argument("--platform", choices=["web", "app", "h5", "miniapp", "api", "device"])
    load_parser.add_argument("--role")
    load_parser.add_argument("--include-candidates", action="store_true",
                             help="仅用于人工审查候选；框架门禁要求该值为 false")
    load_parser.set_defaults(func=load_context)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
