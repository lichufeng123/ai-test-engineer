"""Command-line entry point for the AI test engineering framework."""

import argparse
import json
from pathlib import Path

from .data_factory import generate_fixtures
from .business_flows import check_business_flows, check_flow_case_coverage
from .case_quality import check_case_granularity
from .discovery import plan_discovery
from .documentation import check_documentation_sync
from .evidence import check_evidence
from .project import initialize_project
from .skills import build_portable_plugin, install_portable_skills, validate_portable_skills


def _read(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value.get("status") not in {"failed", "repair_required"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-test", description="可移植的 AI 测试工程框架")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化共享测试项目")
    init.add_argument("path")
    init.add_argument("--name", required=True)
    init.add_argument("--system-id", required=True)
    init.add_argument("--environment", action="append", default=[])
    init.add_argument("--platform", action="append", choices=["web", "app", "h5", "miniapp"], default=[])

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

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return _emit(initialize_project(Path(args.path), name=args.name, system_id=args.system_id,
                                        environments=args.environment, platforms=args.platform))
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
