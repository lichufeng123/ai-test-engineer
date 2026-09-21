"""Command-line entry point for the AI test engineering framework."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from .data_factory import generate_fixtures
from .business_flows import check_business_flows, check_flow_case_coverage
from .case_quality import check_case_granularity
from .permission_quality import check_permission_coverage
from .discovery import plan_discovery
from .documentation import check_documentation_sync
from .evidence import check_evidence
from .execution_readiness import build_readiness_plan, evaluate_execution_readiness
from .execution_history import finish_execution, start_execution
from .project import STAGES, initialize_project
from .skills import build_portable_plugin, install_portable_skills, validate_portable_skills
from .video_quality import check_videos
from .web_execution_routing import check_web_execution_routing
from .work_item_artifacts import (
    ARTIFACT_STATUSES,
    reconcile_work_item,
    register_work_item_artifact,
)
from .work_items import create_work_item, list_work_items, show_work_item, update_work_item


def _read(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value.get("status") not in {"failed", "repair_required", "blocked", "inconsistent"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-test", description="可移植的 AI 测试工程框架")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化共享测试项目")
    init.add_argument("path")
    init.add_argument("--name", required=True)
    init.add_argument("--system-id", required=True)
    init.add_argument("--environment", action="append", default=[])
    init.add_argument("--platform", action="append", choices=["web", "app", "h5", "miniapp"], default=[])

    work_create = commands.add_parser("work-item-create", help="为一个测试需求创建独立状态与接手包")
    work_create.add_argument("--root", default=".")
    work_create.add_argument("--requirement-id", required=True)
    work_create.add_argument("--title", required=True)
    work_create.add_argument("--feature", required=True)
    work_create.add_argument("--environment", action="append", required=True, dest="environments")
    work_create.add_argument(
        "--platform", action="append", required=True, choices=["web", "app", "h5", "miniapp"], dest="platforms"
    )
    work_create.add_argument("--scope", required=True)

    work_show = commands.add_parser("work-item-show", help="读取一个需求并给出新任务接手上下文")
    work_show.add_argument("--root", default=".")
    work_show.add_argument("--requirement-id", required=True)

    work_list = commands.add_parser("work-item-list", help="列出全部测试需求及当前阶段")
    work_list.add_argument("--root", default=".")

    work_update = commands.add_parser("work-item-update", help="更新需求阶段、进展、阻塞和下一步")
    work_update.add_argument("--root", default=".")
    work_update.add_argument("--requirement-id", required=True)
    work_update.add_argument("--stage", choices=STAGES)
    work_update.add_argument("--status", choices=["planned", "active", "blocked", "complete", "cancelled"])
    work_update.add_argument("--summary")
    work_update.add_argument("--completed", action="append")
    work_update.add_argument("--blocker", action="append", dest="blockers")
    work_update.add_argument("--next-step", action="append", dest="next_steps")
    work_update.add_argument("--owner")
    work_update.add_argument("--add-environment", action="append", dest="add_environments")
    work_update.add_argument(
        "--add-platform",
        action="append",
        choices=["web", "app", "h5", "miniapp"],
        dest="add_platforms",
    )
    work_update.add_argument("--scope")
    work_update.add_argument("--baseline-id")
    work_update.add_argument("--baseline-path")
    work_update.add_argument("--baseline-sha256")

    artifact_register = commands.add_parser(
        "work-item-artifact-register",
        help="登记需求产物、内容哈希、审核状态和对应阶段",
    )
    artifact_register.add_argument("--root", default=".")
    artifact_register.add_argument("--requirement-id", required=True)
    artifact_register.add_argument("--artifact-id", required=True)
    artifact_register.add_argument("--artifact-type", required=True)
    artifact_register.add_argument("--path", required=True)
    artifact_register.add_argument("--status", required=True, choices=ARTIFACT_STATUSES)
    artifact_register.add_argument("--stage", required=True, choices=STAGES)
    artifact_register.add_argument("--baseline-id")
    artifact_register.add_argument("--run-id")
    artifact_register.add_argument("--parent-artifact-id")

    reconcile = commands.add_parser(
        "work-item-reconcile",
        help="对账工作项阶段、已登记产物、用例生成门禁和孤立产物",
    )
    reconcile.add_argument("--root", default=".")
    reconcile.add_argument("--requirement-id", required=True)
    reconcile.add_argument("--discover-root", action="append", dest="discover_roots")
    reconcile.add_argument("--apply", action="store_true", help="阶段落后时推进到已验证产物对应阶段")

    discovery = commands.add_parser("discovery-plan", help="判断是否需要全局或增量探索")
    discovery.add_argument("--project", required=True)
    discovery.add_argument("--assets")
    discovery.add_argument("--environment", required=True)
    discovery.add_argument("--platform", action="append", required=True, choices=["web", "app", "h5", "miniapp"])
    discovery.add_argument("--product-version", required=True)
    discovery.add_argument("--global", dest="manual_global", action="store_true")

    docs = commands.add_parser("docs-check", help="校验 README 与完整手册同步")
    docs.add_argument("--root", default=".")

    evidence = commands.add_parser("evidence-check", help="校验证据和报告中的媒体块")
    evidence.add_argument("--manifest", required=True)
    evidence.add_argument("--root", required=True)
    evidence.add_argument("--report")

    video = commands.add_parser("video-check", help="检查视频证据的时长、黑帧和静止区间")
    video.add_argument("--input", required=True, help="符合 video-check 输入 Schema 的 JSON")
    video.add_argument("--root", required=True, help="视频相对路径的受限根目录")
    video.add_argument("--output", required=True, help="写出机器可读的视频质量回执")
    video.add_argument("--ffprobe", default="ffprobe", help="ffprobe 可执行文件")
    video.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件")

    data = commands.add_parser("data-generate", help="按声明生成可复用测试数据")
    data.add_argument("--spec", required=True)
    data.add_argument("--output", required=True)

    flows = commands.add_parser("flow-check", help="校验业务流程规则和端到端用例覆盖")
    flows.add_argument("--input", required=True, help="包含业务拓扑、流程和原子断言的 JSON")
    flows.add_argument("--cases", help="可选：包含 cases 数组的测试用例基线 JSON")
    flows.add_argument("--matrix-output", help="可选：写出流程到断言和流程到用例矩阵")

    granularity = commands.add_parser("case-granularity-check", help="检查规则是否只被大体量端到端用例间接覆盖")
    granularity.add_argument("--cases", required=True, help="包含 cases 数组的测试用例基线 JSON")
    granularity.add_argument("--max-e2e-only-ratio", type=float, default=0.35)

    permission = commands.add_parser("permission-check", help="检查已声明权限矩阵的用例设计覆盖")
    permission.add_argument("--matrix", required=True)
    permission.add_argument("--cases", required=True)
    permission.add_argument("--output", required=True)

    web_executor = commands.add_parser(
        "web-executor-check",
        help="校验Playwright MCP、Chrome DevTools MCP、Ego Lite、Stagehand与正式回归的受控分工",
    )
    web_executor.add_argument("--input", required=True)
    web_executor.add_argument("--output", required=True)

    skills_check = commands.add_parser("skills-check", help="校验跨客户端 Skill 与插件清单")
    skills_check.add_argument("--root", default=".")

    skills_install = commands.add_parser("skills-install", help="安装跨客户端用户级 Skill")
    skills_install.add_argument("--root", default=".")
    skills_install.add_argument(
        "--client",
        action="append",
        choices=["universal", "codex"],
        dest="clients",
        help="安装目标；可重复指定。默认 universal",
    )
    skills_install.add_argument("--mode", choices=["symlink", "copy"], default="symlink")
    skills_install.add_argument("--replace", action="store_true", help="备份后替换已有同名 Skill")

    plugin_build = commands.add_parser("plugin-build", help="从跨客户端 Skill 构建 Codex 插件包")
    plugin_build.add_argument("--root", default=".")
    plugin_build.add_argument("--output", required=True)

    readiness_plan = commands.add_parser(
        "readiness-plan", help="冻结需求审核后的自动化范围、账号角色、数据和证据计划"
    )
    readiness_plan.add_argument("--input", required=True)
    readiness_plan.add_argument("--output", required=True)

    readiness_check = commands.add_parser(
        "readiness-check", help="执行前复核范围、环境、账号角色和测试数据"
    )
    readiness_check.add_argument("--plan", required=True)
    readiness_check.add_argument("--confirmation", required=True)
    readiness_check.add_argument("--previous-missing")
    readiness_check.add_argument("--output", required=True)

    execution_start = commands.add_parser(
        "execution-log-start", help="自动化开始前登记执行时间、作用、目的和范围"
    )
    execution_start.add_argument("--root", default=".")
    execution_start.add_argument("--automation-id", required=True)
    execution_start.add_argument("--run-id", required=True)
    execution_start.add_argument("--feature", required=True)
    execution_start.add_argument("--environment", required=True)
    execution_start.add_argument("--platform", action="append", required=True, dest="platforms")
    execution_start.add_argument("--purpose", required=True, help="本次执行的作用，如发布门禁或缺陷复测")
    execution_start.add_argument("--objective", required=True, help="本次执行要证明的目标")
    execution_start.add_argument("--scope", required=True, help="本次纳入和排除的测试范围")
    execution_start.add_argument("--baseline", help="已审核用例基线及内容哈希")
    execution_start.add_argument("--started-at", help="带时区的 ISO-8601 时间；默认当前本地时间")

    execution_finish = commands.add_parser(
        "execution-log-finish", help="自动化结束后登记耗时、结果、报告、证据和资产变化"
    )
    execution_finish.add_argument("--root", default=".")
    execution_finish.add_argument("--run-id", required=True)
    execution_finish.add_argument(
        "--status",
        required=True,
        choices=["passed", "partial", "failed", "blocked", "interrupted"],
    )
    execution_finish.add_argument("--summary", required=True)
    execution_finish.add_argument("--finished-at", help="带时区的 ISO-8601 时间；默认当前本地时间")
    execution_finish.add_argument("--report")
    execution_finish.add_argument("--evidence")
    execution_finish.add_argument("--asset-change", action="append", default=[], dest="asset_changes")

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return _emit(initialize_project(Path(args.path), name=args.name, system_id=args.system_id,
                                        environments=args.environment, platforms=args.platform))
    if args.command == "work-item-create":
        return _emit(create_work_item(
            Path(args.root), requirement_id=args.requirement_id, title=args.title,
            feature=args.feature, environments=args.environments, platforms=args.platforms,
            scope=args.scope,
        ))
    if args.command == "work-item-show":
        return _emit(show_work_item(Path(args.root), args.requirement_id))
    if args.command == "work-item-list":
        return _emit(list_work_items(Path(args.root)))
    if args.command == "work-item-update":
        return _emit(update_work_item(
            Path(args.root), requirement_id=args.requirement_id, stage=args.stage,
            status=args.status, summary=args.summary, completed=args.completed,
            blockers=args.blockers, next_steps=args.next_steps, owner=args.owner,
            add_environments=args.add_environments, add_platforms=args.add_platforms,
            scope=args.scope, baseline_id=args.baseline_id, baseline_path=args.baseline_path,
            baseline_sha256=args.baseline_sha256,
        ))
    if args.command == "work-item-artifact-register":
        return _emit(register_work_item_artifact(
            Path(args.root), requirement_id=args.requirement_id,
            artifact_id=args.artifact_id, artifact_type=args.artifact_type,
            path=args.path, status=args.status, stage=args.stage,
            baseline_id=args.baseline_id, run_id=args.run_id,
            parent_artifact_id=args.parent_artifact_id,
        ))
    if args.command == "work-item-reconcile":
        return _emit(reconcile_work_item(
            Path(args.root), args.requirement_id,
            discover_roots=[Path(value) for value in (args.discover_roots or [])],
            apply=args.apply,
        ))
    if args.command == "discovery-plan":
        value = plan_discovery(project=_read(args.project),
                               asset_register=_read(args.assets) if args.assets else None,
                               requested_environment=args.environment,
                               requested_platforms=args.platform,
                               product_version=args.product_version,
                               manual_global=args.manual_global)
        value["status"] = "planned"
        return _emit(value)
    if args.command == "docs-check":
        return _emit(check_documentation_sync(Path(args.root)))
    if args.command == "evidence-check":
        return _emit(check_evidence(_read(args.manifest), root=Path(args.root),
                                    report_path=Path(args.report) if args.report else None))
    if args.command == "video-check":
        value = check_videos(
            _read(args.input),
            root=Path(args.root),
            ffprobe=args.ffprobe,
            ffmpeg=args.ffmpeg,
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "data-generate":
        value = generate_fixtures(_read(args.spec), Path(args.output))
        value["status"] = "generated"
        return _emit(value)
    if args.command == "flow-check":
        payload = _read(args.input)
        value = check_business_flows(payload)
        if args.cases and value["status"] == "passed":
            case_payload = _read(args.cases)
            cases = case_payload.get("cases", []) if isinstance(case_payload, dict) else []
            coverage = check_flow_case_coverage(payload.get("business_flows", []), cases)
            value["flow_case_coverage"] = coverage.get("flows", [])
            if coverage["status"] == "failed":
                value["status"] = "failed"
                value["errors"].extend(coverage["errors"])
                value["error_codes"] = sorted(set(value["error_codes"] + coverage["error_codes"]))
        if args.matrix_output:
            matrix_path = Path(args.matrix_output)
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "flow_assertion_matrix": value.get("flow_assertion_matrix", []),
                    "flow_case_coverage": value.get("flow_case_coverage", []),
                }, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return _emit(value)
    if args.command == "case-granularity-check":
        payload = _read(args.cases)
        cases = payload.get("cases", []) if isinstance(payload, dict) else []
        return _emit(check_case_granularity(cases, args.max_e2e_only_ratio))
    if args.command == "permission-check":
        payload = _read(args.cases)
        cases = payload.get("cases", []) if isinstance(payload, dict) else payload
        value = check_permission_coverage(_read(args.matrix), cases)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "web-executor-check":
        value = check_web_execution_routing(_read(args.input))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "skills-check":
        return _emit(validate_portable_skills(Path(args.root)))
    if args.command == "skills-install":
        return _emit(
            install_portable_skills(
                Path(args.root),
                clients=args.clients or ["universal"],
                mode=args.mode,
                replace=args.replace,
            )
        )
    if args.command == "plugin-build":
        return _emit(build_portable_plugin(Path(args.root), Path(args.output)))
    if args.command == "readiness-plan":
        value = build_readiness_plan(_read(args.input))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "readiness-check":
        value = evaluate_execution_readiness(
            _read(args.plan),
            _read(args.confirmation),
            previous_missing=_read(args.previous_missing) if args.previous_missing else None,
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "execution-log-start":
        return _emit(
            start_execution(
                Path(args.root),
                automation_id=args.automation_id,
                run_id=args.run_id,
                feature=args.feature,
                environment=args.environment,
                platforms=args.platforms,
                purpose=args.purpose,
                objective=args.objective,
                scope=args.scope,
                baseline=args.baseline,
                started_at=args.started_at or datetime.now().astimezone().isoformat(timespec="seconds"),
            )
        )
    if args.command == "execution-log-finish":
        return _emit(
            finish_execution(
                Path(args.root),
                run_id=args.run_id,
                result_status=args.status,
                summary=args.summary,
                finished_at=args.finished_at
                or datetime.now().astimezone().isoformat(timespec="seconds"),
                report=args.report,
                evidence=args.evidence,
                asset_changes=args.asset_changes,
            )
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
