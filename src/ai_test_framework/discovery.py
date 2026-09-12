"""Decide whether a run needs system-wide, incremental, or feature discovery."""

from typing import Any, Dict, Iterable, List, Optional


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def plan_discovery(
    *,
    project: Dict[str, Any],
    asset_register: Optional[Dict[str, Any]],
    requested_environment: str,
    requested_platforms: Iterable[str],
    product_version: str,
    manual_global: bool = False,
) -> Dict[str, Any]:
    """Return an auditable discovery plan.

    Global discovery is exceptional: it is required for a first-time system or an
    explicit user request. Version, environment, and platform gaps are handled as
    scoped incremental discovery so a stable system is not relearned every run.
    """

    platforms = _unique(requested_platforms)
    reasons: List[str] = []
    uncovered_environments: List[str] = []
    uncovered_platforms: List[str] = []

    if manual_global:
        reasons.append("用户手动要求全局探索")
        decision = "system_global_required"
    elif not asset_register:
        reasons.append("首次没有系统探索资产")
        decision = "system_global_required"
    elif asset_register.get("status") not in {"verified", "valid"}:
        reasons.append("系统探索资产状态失效")
        decision = "system_global_required"
    else:
        known_environments = set(asset_register.get("environments", []))
        known_platforms = set(asset_register.get("platforms", []))
        if requested_environment and requested_environment not in known_environments:
            uncovered_environments.append(requested_environment)
            reasons.append("当前环境尚未探索")
        uncovered_platforms = [p for p in platforms if p not in known_platforms]
        if uncovered_platforms:
            reasons.append("当前平台尚未探索")
        if product_version and product_version != asset_register.get("product_version"):
            reasons.append("产品版本与已验证资产不一致")
        decision = "incremental_required" if reasons else "feature_only"
        if not reasons:
            reasons.append("系统资产有效，仅需目标功能探索或直接回归")

    return {
        "system_id": project.get("system_id"),
        "decision": decision,
        "global_exploration_required": decision == "system_global_required",
        "incremental_exploration_required": decision == "incremental_required",
        "feature_exploration_required": True,
        "requested_environment": requested_environment,
        "requested_platforms": platforms,
        "uncovered_environments": uncovered_environments,
        "uncovered_platforms": uncovered_platforms,
        "app_h5_pair_review_required": "app" in platforms and "h5" in platforms,
        "reasons": reasons,
        "next_actions": _next_actions(decision, platforms),
    }


def _next_actions(decision: str, platforms: List[str]) -> List[str]:
    actions: List[str] = []
    if decision == "system_global_required":
        actions.extend([
            "建立环境、登录分支、菜单、角色、实体和干扰弹窗地图",
            "系统探索达到 L2 后再进入目标功能探索",
        ])
    elif decision == "incremental_required":
        actions.append("只探索变化的环境、平台、版本和失效资产")
    else:
        actions.append("轻量校验入口、账号角色和关键控件")
    if "app" in platforms and "h5" in platforms:
        actions.append("分别验证 H5 业务流程与 App 容器、权限、返回和兼容差异")
    actions.append("目标功能达到 L3 后才生成自动化执行包")
    return actions
