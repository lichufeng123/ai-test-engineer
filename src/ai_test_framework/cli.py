"""Command-line entry point for the AI test engineering framework."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from .adapter_trace import check_adapter_trace
from .asset_reuse import check_automation_asset_reuse
from .automation_outcome import check_automation_outcome
from .data_factory import generate_fixtures
from .business_flows import check_business_flows, check_flow_case_coverage
from .case_quality import check_case_granularity
from .permission_quality import check_permission_coverage
from .discovery import plan_discovery
from .documentation import check_documentation_sync
from .evidence import check_evidence
from .execution_readiness import build_readiness_plan, evaluate_execution_readiness
from .environment_profile import resolve_environment
from .execution_contract import check_execution_probe, reserve_write_intent
from .playwright_receipts import collect_playwright_receipts
from .report_promotion import check_report_promotion
from .guarded_run import execute_guarded_playwright
from .synthetic_prepare import prepare_synthetic_guarded_run
from .evidence_privacy import check_evidence_privacy
from .knowledge_adapter import audit_local_baseline, audit_local_knowledge
from .one_pass import check_one_pass
from .execution_history import finish_execution, start_execution
from .exploration_handoff import check_exploration_handoff
from .private_repo import scaffold_private_repository
from .project import STAGES, initialize_project, scaffold_playwright
from .team_doctor import inspect_team_project
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
    return 0 if value.get("status") not in {"failed", "repair_required", "blocked", "inconsistent", "review_required"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-test", description="可移植的 AI 测试工程框架")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化共享测试项目")
    init.add_argument("path")
    init.add_argument("--name", required=True)
    init.add_argument("--system-id", required=True)
    init.add_argument("--environment", action="append", default=[])
    init.add_argument("--platform", action="append", choices=["web", "api", "app", "h5", "miniapp"], default=[])

    scaffold = commands.add_parser("playwright-scaffold", help="安装无业务连接的分层Web自动化样板（不覆盖）")
    scaffold.add_argument("--root", default=".")

    private_scaffold = commands.add_parser(
        "private-scaffold",
        help="安装受控私有资产仓库骨架（本地知识注册中心；不覆盖既有文件）")
    private_scaffold.add_argument("--root", default=".", help="私有仓库目录；不存在时创建")
    private_scaffold.add_argument("--name", help="项目显示名；仅当 ai-test.json 不存在时使用")
    private_scaffold.add_argument("--system-id", help="稳定系统标识；仅当 ai-test.json 不存在时使用")
    private_scaffold.add_argument("--environment", action="append", default=[])
    private_scaffold.add_argument("--platform", action="append",
                                  choices=["web", "api", "app", "h5", "miniapp"], default=[])
    private_scaffold.add_argument("--registry-id", help="知识注册中心稳定标识；默认由 system-id 派生")
    private_scaffold.add_argument("--title", help="知识注册中心标题")

    doctor = commands.add_parser("doctor", help="只读离线检查团队clone和项目安装；不授权业务执行")
    doctor.add_argument("--root", default=".", help="ai-test init生成的项目目录")
    doctor.add_argument("--framework-root", default=".", help="公开框架clone目录")
    doctor.add_argument("--private-root", help="可选：已有权限的本地知识仓库，只检查manifest哈希")
    doctor.add_argument("--require-business", action="store_true", help="要求业务执行准备度；M1阶段必然阻塞")

    env_resolve = commands.add_parser("env-resolve", help="比对已审环境画像、现场观测与请求；永不授予写入权限")
    env_resolve.add_argument("--profile", required=True)
    env_resolve.add_argument("--observation", required=True)
    env_resolve.add_argument("--request", required=True)

    probe_check = commands.add_parser("probe-check", help="冻结已有基线Case/临时探针和计划、Oracle、环境、运行ID")
    probe_check.add_argument("--input", required=True)
    probe_check.add_argument("--root", default=".")

    intent = commands.add_parser("write-intent-reserve", help="仅为已冻结目标创建一次本地写意图；不执行产品写入")
    intent.add_argument("--input", required=True)
    intent.add_argument("--observation", required=True)
    intent.add_argument("--approval", required=True)
    intent.add_argument("--root", default=".")

    adapter_trace = commands.add_parser("adapter-trace-check", help="通用只读适配器的逐阶段回执对账；不授予产品通过")
    adapter_trace.add_argument("--input", required=True)
    adapter_trace.add_argument("--root", default=".")

    synthetic_prepare = commands.add_parser("synthetic-run-prepare", help="仅本地虚构：基于已保存的run计划生成一次性charter/probe/bundle并启动日志")
    synthetic_prepare.add_argument("--root", default=".")
    synthetic_prepare.add_argument("--run-id", required=True)
    synthetic_prepare.add_argument("--browser-channel", choices=["msedge", "chromium"], default="msedge")

    guarded = commands.add_parser("guarded-web-run", help="仅本地虚构：冻结探针后单次运行Playwright并绑定当轮reporter；不产生产品通过")
    guarded.add_argument("--input", required=True)
    guarded.add_argument("--root", default=".")

    reporter_gate = commands.add_parser("playwright-receipts-check", help="从Playwright JSON附件自动对账逐断言回执（仍需语义复核）")
    reporter_gate.add_argument("--input", required=True)
    reporter_gate.add_argument("--root", default=".")

    promotion_gate = commands.add_parser("report-promotion-check", help="阻止直接Playwright结果晋升正式报告；仅支持合成运行材料只读核验")
    promotion_gate.add_argument("--input", required=True)
    promotion_gate.add_argument("--root", default=".")

    privacy_gate = commands.add_parser("privacy-check", help="离线证据脱敏风险扫描与逐文件人工复核声明校验")
    privacy_gate.add_argument("--input", required=True)
    privacy_gate.add_argument("--root", default=".")

    knowledge = commands.add_parser("knowledge-audit", help="只读调用私有本地注册器validate/load并逐文件校验必读哈希；非Current审核")
    knowledge.add_argument("--private-root", required=True)
    knowledge.add_argument("--feature", required=True)
    knowledge.add_argument("--stage", choices=["intake", "requirement", "assertion", "case_design", "readiness", "execution", "triage", "retrospective"], required=True)
    knowledge.add_argument("--platform", choices=["web", "app", "h5", "miniapp", "api", "device"])
    knowledge.add_argument("--role")
    knowledge.add_argument("--module-id", help="试点时必选：要求命中该模块的已登记必读条目")

    local_baseline = commands.add_parser("baseline-snapshot", help="只读核对私有工作项本地基线ID/哈希；不证明飞书Current")
    local_baseline.add_argument("--private-root", required=True)
    local_baseline.add_argument("--requirement-id", required=True)

    one_pass = commands.add_parser("one-pass-check", help="检查一站式临时用例计划/执行回执；不执行产品操作或批准业务结论")
    one_pass.add_argument("--input", required=True, help="已保存的一站式运行计划 JSON")
    one_pass.add_argument("--results", help="同run逐用例结果 JSON；省略时只作执行前检查")
    one_pass.add_argument("--root", default=".")
    one_pass.add_argument("--output", help="可选：保存结构化检查回执")

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
    work_create.add_argument("--test-mode", choices=["standard", "rapid", "one_pass"], default="standard")

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
    work_update.add_argument("--test-mode", choices=["standard", "rapid", "one_pass"])
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

    asset_reuse = commands.add_parser(
        "automation-asset-reuse-check",
        help="新增或改写自动化脚本前，校验既有资产检索和逐项复用决策",
    )
    asset_reuse.add_argument("--input", required=True)
    asset_reuse.add_argument("--root", default=".")
    asset_reuse.add_argument("--output", required=True)

    handoff_check = commands.add_parser(
        "exploration-handoff-check", help="重复执行前校验探索问题、可执行资产和逐断言证据计划/收口"
    )
    handoff_check.add_argument("--input", required=True)
    handoff_check.add_argument("--root", default=".")
    handoff_check.add_argument("--output", required=True)

    outcome = commands.add_parser(
        "automation-outcome-check", help="对账逐断言结果、独立Oracle与Playwright真实运行报告"
    )
    outcome.add_argument("--input", required=True)
    outcome.add_argument("--root", default=".")
    outcome.add_argument("--output", required=True)

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
    if args.command == "playwright-scaffold":
        return _emit(scaffold_playwright(Path(args.root)))
    if args.command == "private-scaffold":
        return _emit(scaffold_private_repository(
            Path(args.root), name=args.name, system_id=args.system_id,
            environments=args.environment, platforms=args.platform,
            registry_id=args.registry_id, title=args.title,
        ))
    if args.command == "doctor":
        return _emit(inspect_team_project(Path(args.root), Path(args.framework_root),
                                          private_root=Path(args.private_root) if args.private_root else None,
                                          require_business=args.require_business))
    if args.command == "env-resolve":
        return _emit(resolve_environment(_read(args.profile), _read(args.observation), _read(args.request)))
    if args.command == "probe-check":
        return _emit(check_execution_probe(_read(args.input), Path(args.root)))
    if args.command == "write-intent-reserve":
        return _emit(reserve_write_intent(_read(args.input), _read(args.observation),
                                          _read(args.approval), Path(args.root)))
    if args.command == "adapter-trace-check":
        return _emit(check_adapter_trace(_read(args.input), Path(args.root)))
    if args.command == "synthetic-run-prepare":
        return _emit(prepare_synthetic_guarded_run(Path(args.root), args.run_id, channel=args.browser_channel))
    if args.command == "guarded-web-run":
        return _emit(execute_guarded_playwright(_read(args.input), Path(args.root)))
    if args.command == "playwright-receipts-check":
        return _emit(collect_playwright_receipts(_read(args.input), Path(args.root)))
    if args.command == "report-promotion-check":
        return _emit(check_report_promotion(_read(args.input), Path(args.root)))
    if args.command == "privacy-check":
        return _emit(check_evidence_privacy(_read(args.input), Path(args.root)))
    if args.command == "knowledge-audit":
        return _emit(audit_local_knowledge(Path(args.private_root), feature=args.feature,
                                           stage=args.stage, platform=args.platform, role=args.role,
                                           module_id=args.module_id))
    if args.command == "baseline-snapshot":
        return _emit(audit_local_baseline(Path(args.private_root), args.requirement_id))
    if args.command == "one-pass-check":
        value = check_one_pass(_read(args.input), Path(args.root),
                               results=_read(args.results) if args.results else None,
                               plan_path=Path(args.input) if args.results else None)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "work-item-create":
        return _emit(create_work_item(
            Path(args.root), requirement_id=args.requirement_id, title=args.title,
            feature=args.feature, environments=args.environments, platforms=args.platforms,
            scope=args.scope, test_mode=args.test_mode,
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
            baseline_sha256=args.baseline_sha256, test_mode=args.test_mode,
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
    if args.command == "automation-asset-reuse-check":
        value = check_automation_asset_reuse(_read(args.input), Path(args.root))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "exploration-handoff-check":
        value = check_exploration_handoff(_read(args.input), Path(args.root))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return _emit(value)
    if args.command == "automation-outcome-check":
        value = check_automation_outcome(_read(args.input), Path(args.root))
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
