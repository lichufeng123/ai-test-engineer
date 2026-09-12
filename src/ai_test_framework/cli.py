"""Command-line entry point for the AI test engineering framework."""

import argparse
import json
from pathlib import Path

from .data_factory import generate_fixtures
from .discovery import plan_discovery
from .documentation import check_documentation_sync
from .evidence import check_evidence
from .project import initialize_project


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
