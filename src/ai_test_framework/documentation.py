"""Guard README and the full framework manual against documentation drift."""

import json
import re
from pathlib import Path
from typing import Dict, Any


VERSION_RE = re.compile(r"<!--\s*FRAMEWORK_VERSION:\s*([^\s]+)\s*-->")


def check_documentation_sync(root: Path) -> Dict[str, Any]:
    root = Path(root)
    manifest_path = root / "framework-manifest.json"
    required = [root / "README.md", root / "README.zh-CN.md", root / "docs/FRAMEWORK.md"]
    missing = [str(path.relative_to(root)) for path in [manifest_path, *required] if not path.exists()]
    if missing:
        return {"status": "failed", "missing_documents": missing, "outdated_documents": []}

    version = json.loads(manifest_path.read_text(encoding="utf-8"))["framework_version"]
    outdated = []
    for path in required:
        match = VERSION_RE.search(path.read_text(encoding="utf-8"))
        if not match or match.group(1) != version:
            outdated.append(str(path.relative_to(root)))
    return {
        "status": "passed" if not outdated else "failed",
        "framework_version": version,
        "missing_documents": [],
        "outdated_documents": outdated,
    }
