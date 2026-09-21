"""Validate the guarded Web browser-tool routing contract."""

from typing import Any, Dict, Iterable, List, Mapping


REQUIRED_TOOL_ROLES = {
    "playwright-test": {"formal_regression"},
    "playwright-mcp": {"locator_generation", "locator_validation"},
    "chrome-devtools-mcp": {"diagnosis", "network", "console", "performance"},
    "ego-lite": {"discovery", "authenticated_exploration", "fallback"},
    "stagehand": {"controlled_self_heal"},
}

REQUIRED_ROUTES = {
    "new_feature_discovery": "ego-lite",
    "playwright_locator_assist": "playwright-mcp",
    "authenticated_or_visual_fallback": "ego-lite",
    "failure_diagnosis": "chrome-devtools-mcp",
    "locator_repair": "stagehand",
    "formal_regression": "playwright-test",
}

STAGEHAND_REQUIRED_FORBIDDEN_CHANGES = {
    "expected_result",
    "business_rule",
    "assertion_removal",
    "blind_write_retry",
}

SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "token",
    "cookie",
    "cookies",
    "authorization",
    "secret",
    "credentials",
    "api_key",
    "apikey",
}


class _Collector:
    def __init__(self) -> None:
        self.errors: List[Dict[str, str]] = []

    def add(self, code: str, path: str, message: str) -> None:
        self.errors.append({"code": code, "path": path, "message": message})


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _find_sensitive_fields(value: Any, path: str = "$") -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            child_path = f"{path}.{key}"
            if normalized in SENSITIVE_FIELD_NAMES:
                yield child_path
            yield from _find_sensitive_fields(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _find_sensitive_fields(child, f"{path}[{index}]")


def _is_exact_version(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().lower()
    return not any(marker in normalized for marker in ("latest", "*", "^", "~", "<", ">", "x"))


def check_web_execution_routing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Check that AI browser tools cannot replace the formal Playwright baseline."""

    collector = _Collector()
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "formal_executor": None,
            "pending_tools": [],
            "errors": [{
                "code": "INVALID_ROUTING_DOCUMENT",
                "path": "$",
                "message": "Web执行器路由必须是JSON对象",
            }],
            "error_codes": ["INVALID_ROUTING_DOCUMENT"],
        }

    if payload.get("schema_version") != 1:
        collector.add("UNSUPPORTED_SCHEMA_VERSION", "$.schema_version", "仅支持schema_version=1")

    if payload.get("formal_executor") != "playwright-test":
        collector.add(
            "FORMAL_EXECUTOR_MUST_BE_PLAYWRIGHT",
            "$.formal_executor",
            "正式Web回归执行器必须是playwright-test",
        )
    if payload.get("approved_baseline_required") is not True:
        collector.add(
            "APPROVED_BASELINE_REQUIRED",
            "$.approved_baseline_required",
            "正式回归必须引用已审核用例基线及内容哈希",
        )

    tools = _as_list(payload.get("tools"))
    tool_map: Dict[str, Mapping[str, Any]] = {}
    pending_tools: List[str] = []
    for index, item in enumerate(tools):
        tool = _as_mapping(item)
        tool_id = tool.get("id")
        if not isinstance(tool_id, str) or not tool_id:
            collector.add("TOOL_ID_REQUIRED", f"$.tools[{index}].id", "工具必须声明稳定ID")
            continue
        if tool_id in tool_map:
            collector.add("DUPLICATE_TOOL_ID", f"$.tools[{index}].id", f"工具ID重复: {tool_id}")
            continue
        tool_map[tool_id] = tool
        availability = tool.get("availability")
        if availability not in {"available", "planned", "blocked"}:
            collector.add(
                "INVALID_TOOL_AVAILABILITY",
                f"$.tools[{index}].availability",
                "availability必须是available、planned或blocked",
            )
        if availability != "available":
            pending_tools.append(tool_id)
        elif not _is_exact_version(tool.get("exact_version")):
            collector.add(
                "AVAILABLE_TOOL_VERSION_NOT_PINNED",
                f"$.tools[{index}].exact_version",
                f"已可用工具{tool_id}必须锁定精确版本，禁止latest或范围版本",
            )

    for tool_id, required_roles in REQUIRED_TOOL_ROLES.items():
        tool = tool_map.get(tool_id)
        if not tool:
            collector.add("REQUIRED_TOOL_MISSING", "$.tools", f"缺少工具: {tool_id}")
            continue
        roles = set(_as_list(tool.get("roles")))
        missing = sorted(required_roles - roles)
        if missing:
            collector.add(
                "TOOL_ROLE_INCOMPLETE",
                f"$.tools[{tool_id}].roles",
                f"{tool_id}缺少职责: {', '.join(missing)}",
            )

    routes = _as_mapping(payload.get("routes"))
    for route_id, expected_primary in REQUIRED_ROUTES.items():
        route = _as_mapping(routes.get(route_id))
        if not route:
            collector.add("REQUIRED_ROUTE_MISSING", f"$.routes.{route_id}", "缺少必需路由")
            continue
        if route.get("primary") != expected_primary:
            code = (
                "FORMAL_EXECUTOR_MUST_BE_PLAYWRIGHT"
                if route_id == "formal_regression"
                else "ROUTE_PRIMARY_MISMATCH"
            )
            collector.add(
                code,
                f"$.routes.{route_id}.primary",
                f"{route_id}的主工具必须是{expected_primary}",
            )
        references = [route.get("primary"), *_as_list(route.get("fallbacks"))]
        for reference in references:
            if isinstance(reference, str) and reference not in tool_map:
                collector.add(
                    "ROUTE_REFERENCES_UNKNOWN_TOOL",
                    f"$.routes.{route_id}",
                    f"路由引用未声明工具: {reference}",
                )

    formal_route = _as_mapping(routes.get("formal_regression"))
    if _as_list(formal_route.get("fallbacks")):
        collector.add(
            "FORMAL_REGRESSION_AGENTIC_FALLBACK_FORBIDDEN",
            "$.routes.formal_regression.fallbacks",
            "正式回归不得回退到AI自由决策执行器",
        )

    repair_route = _as_mapping(routes.get("locator_repair"))
    if repair_route.get("requires_validation_by") != "playwright-test":
        collector.add(
            "REPAIR_REQUIRES_PLAYWRIGHT_VALIDATION",
            "$.routes.locator_repair.requires_validation_by",
            "定位修复必须由playwright-test单用例验证并执行影响回归",
        )

    policies = _as_mapping(payload.get("policies"))
    if policies.get("playwright_mcp_required_for_script_generation") is not False:
        collector.add(
            "PLAYWRIGHT_MCP_MUST_BE_OPTIONAL",
            "$.policies.playwright_mcp_required_for_script_generation",
            "编写Playwright脚本不得强制依赖Playwright MCP；Ego Lite、DOM/CDP、Inspector或人工DevTools均可提供定位依据",
        )

    required_true = {
        "formal_expectations_immutable": (
            "FORMAL_EXPECTATIONS_MUST_BE_IMMUTABLE",
            "AI工具不得修改正式预期、业务规则或断言",
        ),
        "credentials_runtime_only": (
            "CREDENTIALS_MUST_BE_RUNTIME_ONLY",
            "凭据、Cookie和Token只能由运行时安全配置提供",
        ),
        "high_risk_write_requires_approval": (
            "HIGH_RISK_APPROVAL_REQUIRED",
            "提交、收款、通知、删除等高风险写操作必须获得明确授权",
        ),
        "agentic_output_requires_playwright_validation": (
            "AGENTIC_OUTPUT_REQUIRES_PLAYWRIGHT_VALIDATION",
            "AI探索或自愈结果必须回到Playwright验证",
        ),
    }
    for key, (code, message) in required_true.items():
        if policies.get(key) is not True:
            collector.add(code, f"$.policies.{key}", message)

    stagehand = _as_mapping(policies.get("stagehand"))
    forbidden = set(_as_list(stagehand.get("forbidden_changes")))
    if not STAGEHAND_REQUIRED_FORBIDDEN_CHANGES.issubset(forbidden):
        missing = sorted(STAGEHAND_REQUIRED_FORBIDDEN_CHANGES - forbidden)
        collector.add(
            "STAGEHAND_FORBIDDEN_CHANGES_INCOMPLETE",
            "$.policies.stagehand.forbidden_changes",
            f"Stagehand禁改项不完整: {', '.join(missing)}",
        )

    sensitive_paths = list(_find_sensitive_fields(payload))
    for sensitive_path in sensitive_paths:
        collector.add(
            "SENSITIVE_FIELD_FORBIDDEN",
            sensitive_path,
            "路由计划不得包含密码、Token、Cookie、密钥或认证载荷字段",
        )

    errors = collector.errors
    error_codes = sorted({item["code"] for item in errors})
    status = "failed" if errors else ("passed_with_pending_tools" if pending_tools else "passed")
    return {
        "status": status,
        "formal_executor": payload.get("formal_executor"),
        "pending_tools": pending_tools,
        "routes_checked": sorted(REQUIRED_ROUTES),
        "errors": errors,
        "error_codes": error_codes,
    }
