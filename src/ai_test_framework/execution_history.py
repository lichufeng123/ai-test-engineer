"""Persistent, human-readable history for automation test executions."""

import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import fcntl


STATE_PATH = Path(".ai-test/execution_history.json")
MARKDOWN_PATH = Path("AUTOMATION_EXECUTION_HISTORY.md")
FINAL_STATUSES = {"passed", "partial", "failed", "blocked", "interrupted"}


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed


def _required(value: str, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "automations": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("automations"), list):
        raise ValueError("unsupported execution history format")
    return value


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def _locked(root: Path):
    lock_path = root / ".ai-test/execution_history.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _escape(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")


def _duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分")
    parts.append(f"{seconds}秒")
    return "".join(parts)


def _refresh_summary(automation: Dict[str, Any]) -> None:
    runs = automation["runs"]
    starts = sorted(run["started_at"] for run in runs)
    automation["first_executed_at"] = starts[0]
    automation["last_executed_at"] = starts[-1]
    automation["execution_count"] = len(runs)


def _render(value: Dict[str, Any]) -> str:
    lines = [
        "# 自动化测试执行历史",
        "",
        "> 由 `ai-test execution-log-start` 与 `ai-test execution-log-finish` 维护。",
        "> 禁止记录账号、密码、Cookie、Token 或客户隐私数据。",
        "",
        "## 自动化资产概览",
        "",
        "| 自动化 ID | 功能 | 首次执行时间 | 最近执行时间 | 执行次数 |",
        "| --- | --- | --- | --- | ---: |",
    ]
    automations = sorted(value["automations"], key=lambda item: item["automation_id"])
    if not automations:
        lines.append("| — | — | — | — | 0 |")
    for automation in automations:
        lines.append(
            "| {automation_id} | {feature} | {first} | {last} | {count} |".format(
                automation_id=_escape(automation["automation_id"]),
                feature=_escape(automation["feature"]),
                first=_escape(automation["first_executed_at"]),
                last=_escape(automation["last_executed_at"]),
                count=automation["execution_count"],
            )
        )

    lines.extend(["", "## 历次执行", ""])
    all_runs = []
    for automation in automations:
        for run in automation["runs"]:
            all_runs.append((automation, run))
    for automation, run in sorted(all_runs, key=lambda item: item[1]["started_at"], reverse=True):
        lines.extend(
            [
                f"### {_escape(run['run_id'])} · {_escape(automation['feature'])}",
                "",
                f"- 自动化 ID：`{_escape(automation['automation_id'])}`",
                f"- 状态：`{_escape(run['status'])}`",
                f"- 环境：`{_escape(run['environment'])}`",
                f"- 平台：{_escape('、'.join(run['platforms']))}",
                f"- 开始时间：{_escape(run['started_at'])}",
                f"- 结束时间：{_escape(run.get('finished_at'))}",
                f"- 执行耗时：{_duration(run.get('duration_seconds'))}",
                f"- 执行作用：{_escape(run['purpose'])}",
                f"- 执行目的：{_escape(run['objective'])}",
                f"- 执行范围：{_escape(run['scope'])}",
                f"- 用例基线：{_escape(run.get('baseline'))}",
                f"- 结果摘要：{_escape(run.get('summary'))}",
                f"- 测试报告：{_escape(run.get('report'))}",
                f"- 证据清单：{_escape(run.get('evidence'))}",
                f"- 资产变化：{_escape('；'.join(run.get('asset_changes', [])))}",
                "",
            ]
        )
    if not all_runs:
        lines.extend(["暂无执行记录。", ""])
    return "\n".join(lines)


def _save(root: Path, value: Dict[str, Any]) -> None:
    _write_json(root / STATE_PATH, value)
    markdown = root / MARKDOWN_PATH
    temporary = markdown.with_suffix(markdown.suffix + ".tmp")
    temporary.write_text(_render(value), encoding="utf-8")
    os.replace(temporary, markdown)


def initialize_execution_history(root: Path) -> None:
    root = Path(root)
    with _locked(root):
        state = _load(root / STATE_PATH)
        _save(root, state)


def start_execution(
    root: Path,
    *,
    automation_id: str,
    run_id: str,
    feature: str,
    environment: str,
    platforms: Iterable[str],
    purpose: str,
    objective: str,
    scope: str,
    started_at: str,
    baseline: Optional[str] = None,
) -> Dict[str, Any]:
    root = Path(root)
    normalized_platforms = list(dict.fromkeys(_required(item, "platform") for item in platforms))
    if not normalized_platforms:
        raise ValueError("at least one platform is required")
    started_at = _required(started_at, "started_at")
    _parse_time(started_at, "started_at")
    automation_id = _required(automation_id, "automation_id")
    run_id = _required(run_id, "run_id")
    feature = _required(feature, "feature")
    environment = _required(environment, "environment")
    purpose = _required(purpose, "purpose")
    objective = _required(objective, "objective")
    scope = _required(scope, "scope")

    with _locked(root):
        value = _load(root / STATE_PATH)
        existing_owner = next(
            (
                automation
                for automation in value["automations"]
                if any(run["run_id"] == run_id for run in automation["runs"])
            ),
            None,
        )
        if existing_owner and existing_owner["automation_id"] != automation_id:
            raise ValueError("run_id is already used by another automation")

        automation = next(
            (item for item in value["automations"] if item["automation_id"] == automation_id), None
        )
        if automation is None:
            automation = {"automation_id": automation_id, "feature": feature, "runs": []}
            value["automations"].append(automation)
        elif automation["feature"] != feature:
            raise ValueError("feature does not match the existing automation_id")

        existing = next((run for run in automation["runs"] if run["run_id"] == run_id), None)
        if existing is not None:
            _refresh_summary(automation)
            _save(root, value)
            return {
                "status": existing["status"],
                "run_id": run_id,
                "first_executed_at": automation["first_executed_at"],
                "execution_count": automation["execution_count"],
                "idempotent": True,
                "history": str(root / MARKDOWN_PATH),
            }

        automation["runs"].append(
            {
                "run_id": run_id,
                "status": "started",
                "environment": environment,
                "platforms": normalized_platforms,
                "started_at": started_at,
                "purpose": purpose,
                "objective": objective,
                "scope": scope,
                "baseline": baseline,
                "summary": None,
                "report": None,
                "evidence": None,
                "asset_changes": [],
            }
        )
        _refresh_summary(automation)
        _save(root, value)
        return {
            "status": "started",
            "run_id": run_id,
            "first_executed_at": automation["first_executed_at"],
            "execution_count": automation["execution_count"],
            "idempotent": False,
            "history": str(root / MARKDOWN_PATH),
        }


def finish_execution(
    root: Path,
    *,
    run_id: str,
    result_status: str,
    summary: str,
    finished_at: str,
    report: Optional[str] = None,
    evidence: Optional[str] = None,
    asset_changes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    root = Path(root)
    run_id = _required(run_id, "run_id")
    if result_status not in FINAL_STATUSES:
        raise ValueError(f"result_status must be one of {sorted(FINAL_STATUSES)}")
    summary = _required(summary, "summary")
    finished_at = _required(finished_at, "finished_at")
    finished = _parse_time(finished_at, "finished_at")

    with _locked(root):
        value = _load(root / STATE_PATH)
        match = None
        for automation in value["automations"]:
            for run in automation["runs"]:
                if run["run_id"] == run_id:
                    match = run
                    break
            if match:
                break
        if match is None:
            raise ValueError("run_id was not started")
        started = _parse_time(match["started_at"], "started_at")
        duration = int((finished - started).total_seconds())
        if duration < 0:
            raise ValueError("finished_at cannot be earlier than started_at")
        match.update(
            {
                "status": result_status,
                "finished_at": finished_at,
                "duration_seconds": duration,
                "summary": summary,
                "report": report,
                "evidence": evidence,
                "asset_changes": [str(item).strip() for item in (asset_changes or []) if str(item).strip()],
            }
        )
        _save(root, value)
        return {
            "status": result_status,
            "run_id": run_id,
            "duration_seconds": duration,
            "history": str(root / MARKDOWN_PATH),
        }
