---
name: test-execution-asset-retrospective
description: Use when a completed or interrupted test run contains reusable navigation, state, locator, fixture, environment, evidence, recovery, or efficiency learning that must be preserved for faster regression.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.4.0"
---

# 测试执行资产与复盘

首次测试同时学习系统和执行用例；结束时必须把可复用学习变成版本化执行资产。业务事实仍进入受控规则基线，不能混入执行经验。

## 资产范围

- 系统与导航地图、页面模型、角色权限模型、实体和状态模型。
- 稳定定位器、备用定位方式、登录分支、瞬态弹窗和恢复动作。
- 测试数据模板、生成方式、唯一命名、复用/清理策略和哈希。
- 缓存、刷新、重登、异步等待、下载、接口观察和环境差异。
- 证据计划、截图/录屏位置、报告发布和回读方法。
- 已确认产品行为、范围外项和禁止误报项。

每项记录 `last_verified_at`、环境、平台、产品版本、来源运行、适用范围和状态：`verified`、`stale`、`missing` 或 `local_unbacked`。账号、密码、Cookie、Token、客户数据、原始敏感载荷和一次性标识不得进入资产。

## 收尾流程

1. 对照本轮执行计划列出实际使用、新增、修正和失效的资产。
2. 将页面异常与业务缺陷分开；只有审核确认的产品事实才能更新业务规则。
3. 更新 `execution_asset_register`，记录来源证据、版本和哈希。
4. 写执行复盘：耗时点、根因、已经采取的修复、下轮直接复用方式和预期收益。
5. 报告中的每个结论与稳定用例ID、证据和资产变更互相校验。
6. 发布或备份后保存修订号与内容哈希；没有受控备份时保持 `local_unbacked`。

## 下轮使用

```text
加载资产 → 轻量有效性校验 → 识别变化范围
→ 只探索变化部分 → 执行回归 → 再次反哺
```

资产校验失败时只废弃对应范围，不默认否定全部系统认知。中断运行也要保存已验证资产、阻塞现场和下一步，避免下一会话从零探索。
