"""Validate and install the repository's portable Agent Skills."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r"^(?P<key>[a-zA-Z0-9_-]+):\s*[\"']?(?P<value>.*?)[\"']?\s*$")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CLIENT_PATHS = {
    "universal": Path(".agents/skills"),
    "codex": Path(".codex/skills"),
}
PRIVATE_MARKERS = (
    "/Users/",
    "http://",
    "https://",
)


def _parse_frontmatter(text: str) -> Dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    values: Dict[str, str] = {}
    for line in match.group("body").splitlines():
        field = FIELD_RE.match(line)
        if field:
            values[field.group("key")] = field.group("value")
    return values


def validate_portable_skills(root: Path) -> Dict[str, Any]:
    """Validate layout, frontmatter, privacy, and plugin source reuse."""

    root = Path(root).resolve()
    skill_root = root / ".agents" / "skills"
    errors: List[Dict[str, str]] = []
    skills: List[str] = []

    if not skill_root.is_dir():
        errors.append({"code": "missing_skill_root", "path": ".agents/skills"})
    else:
        for skill_dir in sorted(path for path in skill_root.iterdir() if path.is_dir()):
            name = skill_dir.name
            skills.append(name)
            entrypoint = skill_dir / "SKILL.md"
            if not entrypoint.is_file():
                errors.append({"code": "missing_skill_entrypoint", "path": str(entrypoint.relative_to(root))})
                continue
            text = entrypoint.read_text(encoding="utf-8")
            metadata = _parse_frontmatter(text)
            if not NAME_RE.fullmatch(name):
                errors.append({"code": "invalid_skill_directory_name", "path": str(skill_dir.relative_to(root))})
            if metadata.get("name") != name:
                errors.append({"code": "skill_name_mismatch", "path": str(entrypoint.relative_to(root))})
            description = metadata.get("description", "")
            if not description.startswith("Use when"):
                errors.append({"code": "non_discoverable_description", "path": str(entrypoint.relative_to(root))})
            if len(description) > 1024:
                errors.append({"code": "description_too_long", "path": str(entrypoint.relative_to(root))})
            if len(text.splitlines()) > 500:
                errors.append({"code": "skill_entrypoint_too_long", "path": str(entrypoint.relative_to(root))})

        for path in sorted(skill_root.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in PRIVATE_MARKERS:
                if marker in text:
                    errors.append({
                        "code": "private_runtime_detail",
                        "path": str(path.relative_to(root)),
                        "marker": marker,
                    })

    plugin_path = root / "plugin" / "plugin.json"
    if not plugin_path.is_file():
        errors.append({"code": "missing_plugin_manifest_template", "path": "plugin/plugin.json"})
    else:
        try:
            plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append({"code": "invalid_plugin_manifest", "path": "plugin/plugin.json"})
        else:
            if plugin.get("skills") != "./skills/":
                errors.append({"code": "invalid_built_plugin_skill_path", "path": "plugin/plugin.json"})
            manifest_path = root / "framework-manifest.json"
            if manifest_path.is_file():
                framework_version = json.loads(manifest_path.read_text(encoding="utf-8"))["framework_version"]
                if plugin.get("version") != framework_version:
                    errors.append({"code": "plugin_version_mismatch", "path": "plugin/plugin.json"})

    return {
        "status": "passed" if not errors else "failed",
        "canonical_root": str(skill_root),
        "skills": skills,
        "errors": errors,
    }


def build_portable_plugin(root: Path, output: Path) -> Dict[str, Any]:
    """Build a Codex plugin artifact from the canonical cross-client skills."""

    root = Path(root).resolve()
    output = Path(output).resolve()
    validation = validate_portable_skills(root)
    if validation["status"] != "passed":
        return {"status": "failed", "errors": validation["errors"]}
    canonical_root = root / ".agents" / "skills"
    if output == root or output == canonical_root or canonical_root in output.parents:
        return {
            "status": "failed",
            "errors": [{"code": "plugin_output_conflicts_with_source", "output": str(output)}],
        }
    if _exists(output):
        return {
            "status": "blocked",
            "reason": "plugin_output_exists",
            "output": str(output),
        }

    (output / ".codex-plugin").mkdir(parents=True)
    shutil.copy2(root / "plugin" / "plugin.json", output / ".codex-plugin" / "plugin.json")
    shutil.copytree(root / ".agents" / "skills", output / "skills")
    return {
        "status": "built",
        "output": str(output),
        "manifest": str(output / ".codex-plugin" / "plugin.json"),
        "skills": validation["skills"],
        "source": str(root / ".agents" / "skills"),
    }


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _same_symlink(destination: Path, source: Path) -> bool:
    return destination.is_symlink() and destination.resolve() == source.resolve()


def install_portable_skills(
    root: Path,
    *,
    home: Path | None = None,
    clients: Iterable[str] = ("universal",),
    mode: str = "symlink",
    replace: bool = False,
) -> Dict[str, Any]:
    """Install canonical skills into user discovery paths without silent overwrite."""

    root = Path(root).resolve()
    home = Path(home or Path.home()).resolve()
    clients = list(dict.fromkeys(clients))
    unknown = sorted(set(clients) - set(CLIENT_PATHS))
    if unknown:
        return {"status": "failed", "errors": [{"code": "unknown_client", "clients": unknown}]}
    if mode not in {"symlink", "copy"}:
        return {"status": "failed", "errors": [{"code": "unsupported_install_mode", "mode": mode}]}

    validation = validate_portable_skills(root)
    if validation["status"] != "passed":
        return {"status": "failed", "errors": validation["errors"]}

    sources = [root / ".agents" / "skills" / name for name in validation["skills"]]
    collisions: List[str] = []
    unchanged: List[str] = []
    operations = []
    for client in clients:
        base = home / CLIENT_PATHS[client]
        for source in sources:
            destination = base / source.name
            if _same_symlink(destination, source):
                unchanged.append(str(destination))
                continue
            if _exists(destination) and not replace:
                collisions.append(str(destination))
            else:
                operations.append((client, source, destination))

    if collisions:
        return {
            "status": "blocked",
            "reason": "existing_skills_require_replace",
            "collisions": sorted(collisions),
            "unchanged": sorted(unchanged),
        }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = home / ".agents" / "backups" / "ai-test-engineer" / stamp
    installed: List[str] = []
    backed_up: List[str] = []
    for _client, source, destination in operations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if _exists(destination):
            relative = destination.relative_to(home)
            backup = backup_root / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(backup))
            backed_up.append(str(backup))
        if mode == "symlink":
            destination.symlink_to(source, target_is_directory=True)
        else:
            shutil.copytree(source, destination)
        installed.append(str(destination))

    return {
        "status": "installed",
        "mode": mode,
        "clients": clients,
        "installed": sorted(installed),
        "unchanged": sorted(unchanged),
        "backed_up": sorted(backed_up),
        "backup_root": str(backup_root) if backed_up else None,
    }
