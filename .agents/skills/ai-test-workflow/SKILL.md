---
name: ai-test-workflow
description: Use when an AI agent or tester must run a traceable testing lifecycle from requirement intake through discovery, reviewed cases, execution, evidence, reporting, and reusable asset feedback.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.4.0"
---

# AI 测试工程工作流

把用户视为产品经理和最终验收人；AI承担测试工程师职责，主动完成分析、探索、数据、执行、问题定性、报告和资产反哺。业务口径不清时提出定向问题，并继续不受影响的工作。

## 路由

按任务加载对应 Skill：

- 需求材料零散或需要需求 Review：`requirement-spec-generate`。
- 需要业务流程和原子规则：`generate-business-assertions`。
- 需要正式用例或测试后反哺：`test-case-generate`。
- 需要页面、接口或跨端执行：`requirement-grounded-functional-testing`。
- 需要沉淀本轮学习与提速：`test-execution-asset-retrospective`。

## 主链路

```text
需求接收 → 来源冻结 → 系统/功能探索 → 需求审核
→ 业务流程与原子断言审核 → 正式用例审核
→ 数据与自动化交接 → 测试执行 → 问题定性与回归
→ 证据化报告 → 执行资产反哺
```

首次且没有有效系统资产时执行全局探索；已有资产时只校验入口、角色、关键控件、版本和数据前置。新环境、新平台或版本变化只探索差异范围。

## 不可跳过的约束

- 区分已确认事实、AI推断、待确认问题和历史信息。
- 提问前先读取系统地图、角色、实体、接口和已有回答，给出候选上下游、影响和建议口径。
- 正式测试用例只有一个审核基线；自动化只引用稳定用例 ID 和内容哈希。
- 账号、密码、Cookie、Token、客户数据和私有地址不得写入资产或报告。
- UI单步两分钟无页面、接口、下载、日志或状态进展时，保存证据并报告阻塞。
- 每个阶段输出：`当前完成 / 下一步必须 / 下一步可选 / 推荐动作`。

运行状态写入项目 `.ai-test/`，聊天记录只提供上下文。需要确定性检查时运行 `ai-test --help` 选择对应门禁。
