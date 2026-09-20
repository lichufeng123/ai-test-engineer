"""Project initialization and shared workflow state."""

import json
from pathlib import Path
from typing import Iterable, Dict, Any

from .execution_history import initialize_execution_history


STAGES = [
    "INTAKE",
    "SYSTEM_DISCOVERY",
    "FEATURE_DISCOVERY",
    "REQUIREMENT_FREEZE",
    "AUTOMATION_READINESS_PLANNING",
    "CURRENT_VALIDATION",
    "ASSERTION_DESIGN",
    "CASE_DESIGN",
    "DATA_BUILD",
    "AUTOMATION_HANDOFF",
    "ASSET_VALIDATION",
    "PRE_EXECUTION_CONFIRMATION",
    "EXECUTION_GATE",
    "EXECUTION_LOG_START",
    "TEST_EXECUTION",
    "ISSUE_TRIAGE",
    "RESULT_WRITEBACK",
    "REPORT_REPAIR",
    "ASSET_FEEDBACK",
    "EXECUTION_LOG_FINISH",
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
    _write_json(root / "ai-test.json", config)
    from .work_items import initialize_work_item_index

    index = initialize_work_item_index(root)
    initialize_execution_history(root)
    return {"status": "created", "root": str(root), "config": config, "work_items": index}
