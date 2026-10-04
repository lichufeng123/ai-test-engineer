"""Read-only, offline onboarding checks for a cloned team test project.

Passing this check only establishes local installation health. It never grants
business execution, validates product rules, contacts a server, or reads secrets.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def _manifest_health(root: Path) -> list[str]:
    manifest = root / "knowledge/manifest.json"
    if not manifest.is_file():
        return ["knowledge_manifest_missing"]
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return ["knowledge_manifest_invalid"]
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        return ["knowledge_entries_missing"]
    problems: list[str] = []
    ids: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("entry_id"), str) or not item["entry_id"].strip():
            problems.append("knowledge_entry_invalid")
            continue
        if item["entry_id"] in ids:
            problems.append("knowledge_entry_duplicate")
        ids.add(item["entry_id"])
        raw = item.get("path")
        if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or ".." in Path(raw).parts:
            problems.append("knowledge_path_unsafe")
            continue
        target = (root / raw).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            problems.append("knowledge_file_missing")
            continue
        digest = hashlib.sha256()
        try:
            with target.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            problems.append("knowledge_file_unreadable")
            continue
        if digest.hexdigest() != item.get("sha256"):
            problems.append("knowledge_hash_mismatch")
    return sorted(set(problems))


def inspect_team_project(
    project_root: Path, framework_root: Path, *, private_root: Path | None = None,
    require_business: bool = False,
) -> dict[str, Any]:
    """Inspect only local files and command availability; do not execute tools."""
    project_root = Path(project_root).resolve()
    framework_root = Path(framework_root).resolve()
    problems: list[str] = []
    checks: dict[str, Any] = {}
    required_framework_files = (
        "AGENTS.md", "docs/TEST_CONTEXT_INDEX.md", ".agents/skills/ai-test-workflow/SKILL.md",
    )
    checks["framework_clone"] = all((framework_root / name).is_file() for name in required_framework_files)
    if not checks["framework_clone"]:
        problems.append("framework_clone_incomplete")
    config_path = project_root / "ai-test.json"
    config: Any = None
    if not config_path.is_file():
        problems.append("project_not_initialized")
    else:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            problems.append("project_config_invalid")
    if isinstance(config, dict):
        case_generation = config.get("case_generation")
        secrets = config.get("secrets")
        if (config.get("schema_version") != 1 or not str(config.get("system_id") or "").strip()
                or not isinstance(case_generation, dict)
                or case_generation.get("single_official_baseline") is not True
                or not isinstance(secrets, dict)
                or secrets.get("policy") != "runtime-reference-only"):
            problems.append("project_contract_invalid")
        platforms = config.get("platforms", [])
        if not isinstance(platforms, list) or any(not isinstance(item, str) or item not in {"web", "api", "app", "h5", "miniapp"} for item in platforms):
            problems.append("project_platforms_invalid")
            platforms = []
    else:
        if config is not None:
            problems.append("project_config_invalid")
        platforms = []
    checks["python_supported"] = sys.version_info >= (3, 9)
    if not checks["python_supported"]:
        problems.append("python_unsupported")
    web = any(item in {"web", "h5"} for item in platforms)
    if web:
        checks["node_available"] = shutil.which("node") is not None
        checks["npm_available"] = shutil.which("npm") is not None
        starter = project_root / "automation/web"
        checks["web_starter_present"] = (starter / "playwright.config.ts").is_file() and (starter / "package.json").is_file()
        checks["playwright_dependency_present"] = (starter / "node_modules/@playwright/test/package.json").is_file()
        for name, ok in (("node_missing", checks["node_available"]), ("npm_missing", checks["npm_available"]),
                         ("web_starter_missing", checks["web_starter_present"]),
                         ("playwright_dependency_missing", checks["playwright_dependency_present"])):
            if not ok:
                problems.append(name)
    else:
        checks["web_starter_present"] = "not_applicable"
    knowledge_root = Path(private_root).resolve() if private_root else project_root
    if private_root is not None or (knowledge_root / "knowledge/manifest.json").is_file():
        knowledge_problems = _manifest_health(knowledge_root)
        checks["knowledge_manifest_hashes"] = "passed" if not knowledge_problems else "blocked"
        problems.extend(knowledge_problems)
    else:
        checks["knowledge_manifest_hashes"] = "not_configured"
    checks["browser_runtime"] = "not_tested"
    checks["credentials"] = "not_read"
    checks["business_execution"] = "not_validated"
    if require_business:
        problems.append("business_execution_not_integrated")
    return {
        "schema_version": 1,
        "status": "blocked" if problems else "passed",
        "scope": "offline_clone_health_only",
        "project_root": str(project_root), "framework_root": str(framework_root),
        "checks": checks,
        "error_codes": sorted(set(problems)),
        "next_actions": [
            "Install only the missing local prerequisites; do not provide credentials in chat.",
            "Run the synthetic Playwright smoke test before claiming a browser works.",
            "Business execution still requires current knowledge, a reviewed baseline or charter, runtime identity, authorization and per-action guards.",
        ],
    }
