"""Project initialization and shared workflow state."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Dict, Any


STAGES = [
    "INTAKE",
    "SYSTEM_DISCOVERY",
    "FEATURE_DISCOVERY",
    "REQUIREMENT_FREEZE",
    "CURRENT_VALIDATION",
    "ASSERTION_DESIGN",
    "CASE_DESIGN",
    "DATA_BUILD",
    "AUTOMATION_HANDOFF",
    "ASSET_VALIDATION",
    "EXECUTION_GATE",
    "TEST_EXECUTION",
    "ISSUE_TRIAGE",
    "RESULT_WRITEBACK",
    "REPORT_REPAIR",
    "ASSET_FEEDBACK",
    "COMPLETE",
]


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def initialize_project(
    root: Path,
    *,
    name: str,
    system_id: str,
    environments: Iterable[str],
    platforms: Iterable[str],
) -> Dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for directory in (
        ".ai-test/locks",
        ".ai-test/receipts",
        "assets/system",
        "assets/features",
        "fixtures",
        "runs",
        "reports",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)

    config = {
        "schema_version": 1,
        "name": name,
        "system_id": system_id,
        "environments": list(dict.fromkeys(environments)),
        "platforms": list(dict.fromkeys(platforms)),
        "case_generation": {
            "adapter": "approved-test-case-baseline",
            "single_official_baseline": True,
        },
        "secrets": {"policy": "runtime-reference-only"},
    }
    state = {
        "schema_version": 1,
        "stage": "INTAKE",
        "allowed_stages": STAGES,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "blockers": [],
        "active_run": None,
    }
    _write_json(root / "ai-test.json", config)
    _write_json(root / ".ai-test/workflow_state.json", state)
    return {"status": "created", "root": str(root), "config": config, "state": state}
