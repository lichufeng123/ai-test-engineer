"""Build an explicit, local preview kit. Never publish or overwrite artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT_FILES = (
    "AGENTS.md", "CONTRIBUTING.md", "LICENSE", "README.md", "README.zh-CN.md", "SECURITY.md",
    "framework-manifest.json", "pyproject.toml", "setup.cfg", "setup.py", "uv.lock",
    ".gitignore", ".github/workflows/ci.yml", "scripts/build_team_preview.py",
)
PUBLIC_DIRS = (
    ".agents/skills", "adapters", "bin", "docs", "playbooks", "plugin", "schemas", "src/ai_test_framework",
    "templates", "tests", "examples/synthetic_adapter_projects",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "node_modules", "dist", "build", "benchmarks"}
ALLOWED_SUFFIXES = {".md", ".json", ".py", ".ts", ".js", ".mjs", ".toml", ".cfg", ".yml", ".yaml", ".txt", ".ad", ".lock", ".gitignore"}
FORBIDDEN_TEXT = ("/Users/" + "chenhao", "yizhitech." + "feishu.cn", "yizhi-" + "test-assets")


def build(root: Path, wheel: Path, output: Path) -> dict:
    root, wheel, output = root.resolve(), wheel.resolve(), output.resolve()
    manifest = json.loads((root / "framework-manifest.json").read_text(encoding="utf-8"))
    version = manifest["framework_version"]
    if version not in wheel.name or not wheel.is_file() or not wheel.name.endswith(".whl"):
        raise ValueError("wheel_name_or_version_mismatch")
    if output.exists():
        raise FileExistsError("preview_kit_already_exists")
    files = [root / part for part in ROOT_FILES]
    for part in PUBLIC_DIRS:
        files.extend(path for path in (root / part).rglob("*") if path.is_file())
    items = {}
    for path in sorted(set(files)):
        rel = path.relative_to(root)
        if path.is_symlink() or any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.suffix not in ALLOWED_SUFFIXES and path.name not in {"LICENSE", "ai-test", ".gitignore"}:
            continue
        if path.stat().st_size > 1_000_000:
            raise ValueError("unexpected_large_source_file")
        raw = path.read_bytes()
        if any(pattern.encode() in raw for pattern in FORBIDDEN_TEXT) or b"-----BEGIN PRIVATE KEY-----\n" in raw:
            raise ValueError(f"nonpublic_text_detected:{rel.as_posix()}")
        items[f"framework/{rel.as_posix()}"] = raw
    required = ("framework/AGENTS.md", "framework/docs/TEST_CONTEXT_INDEX.md",
                "framework/.agents/skills/ai-test-workflow/SKILL.md", "framework/docs/TEAM_PREVIEW_INSTALL.md",
                "framework/src/ai_test_framework/synthetic_adapter_runner.py")
    if any(name not in items for name in required):
        raise ValueError("kit_missing_required_file")
    items[f"wheel/{wheel.name}"] = wheel.read_bytes()
    hashes = {path: hashlib.sha256(body).hexdigest() for path, body in sorted(items.items())}
    items["SHA256SUMS.json"] = (json.dumps({"version": version, "files": hashes}, ensure_ascii=False, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never replace a previously shared archive.
    with output.open("xb") as handle:
        with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(items.items()):
                archive.writestr(name, raw)
    return {"version": version, "entries": len(items), "kit_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "path": str(output), "status": "built_local_not_published"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.wheel, args.output), ensure_ascii=False, indent=2))
