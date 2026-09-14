---
name: requirement-spec-generate
description: Use when prototypes, HTML demos, screenshots, rough PRDs, review notes, defect evidence, or mixed materials must become a reviewable requirement specification before rule or test-case generation.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.5.0"
---

# 需求说明书生成

把零散材料整理为可审核、可追溯的需求说明。来源事实、当前基线、历史信息和AI推断必须分层；未经审核的推断不能作为正式预期。

## 执行方式

1. 冻结用户提供的全部来源，记录文件、版本、哈希和适用范围。缺失或损坏的材料明确列为阻塞或风险。
2. 静态盘点原型、表格、截图和HTML结构。存在可运行Demo时，在隔离环境遍历页面、状态、校验、分支和模拟数据；Demo只证明当前表现，不自动成为正确业务规则。
3. 加载已有系统地图、导航、角色权限、实体关系、平台关系、接口和当前业务基线。当前基线来源由项目适配器配置；检索命中只作为候选，必须回到权威来源校验。
4. 在提问前推导上游触发、下游消费、跨角色、Web/App/H5/小程序、统计和异步候选链路。问题包含当前理解、证据、具体疑点、影响、建议口径和需要确认内容。
5. 产出原子需求项，覆盖范围、角色、前置、主流程、异常、状态、字段、权限、幂等、并发、失败恢复、数据一致性和非目标范围。
6. 生成差距审计：来源冲突、缺失参数、未确认候选链路、无法观察的运行态和发布风险。P0未决不得进入正式下游。
7. 生成唯一审核入口，由产品经理最终审核。审核修改成为新冻结来源，不能直接改机器数据绕过复核。
8. 需求审核通过后立即梳理自动化准备度：可自动化与人工专属范围、目标环境/平台、账号角色、fixture与生成方式、证据计划、风险动作和待确认项。没有正式用例ID时先记录候选用例类别；用例审核后绑定稳定ID并重新冻结计划哈希。

## 产物契约

保存在 `.ai-test/requirements/<run-id>/`：

- `source_manifest.json`
- `prototype_inventory.json`，适用时增加 `demo_runtime_audit.json`
- `business_topology.json`
- `gap_audit.json`
- `requirement_items.json`
- `requirement_review.html` 或项目指定的审核载体
- 审核后的 `requirement_spec.md` 与 `review_receipt.json`
- `automation_readiness_source.json` 与 `automation_readiness_plan.json`

每条需求项包含稳定ID、陈述、来源定位、状态、优先级、适用角色/环境/平台和验收观察点。发布到外部文档系统属于独立写入动作，只有用户已授权且写后回读通过时才标记完成。

准备度计划只记录账号角色和用途，不得记录账号、密码、Cookie或Token。账号和数据缺口应在此阶段提前暴露，并在实际执行前再次确认。

审核通过后，把运行ID、需求哈希、审核摘要、稳定需求ID、业务拓扑和准备度计划交给 `generate-business-assertions`；需求审核不能替代规则审核或用例审核。
