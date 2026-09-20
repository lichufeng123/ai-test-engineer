---
name: ai-test-workflow
description: Use when an AI agent or tester must run a traceable testing lifecycle from requirement intake through discovery, reviewed cases, execution, evidence, reporting, and reusable asset feedback.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.7.0"
---

# AI 测试工程工作流

把用户视为产品经理和最终验收人；AI承担测试工程师职责，主动完成分析、探索、数据、执行、问题定性、报告和资产反哺。业务口径不清时提出定向问题，并继续不受影响的工作。

## 路由

按任务加载对应 Skill：

- 需求材料零散或需要需求 Review：`requirement-spec-generate`。
- 需要业务流程和原子规则：`generate-business-assertions`。
- 需要正式用例或测试后反哺：`test-case-generate`。
- 需要页面、接口或跨端执行：`requirement-grounded-functional-testing`。
- 需要把缺陷暴露的漏测、用户纠正或测试误判沉淀为后续设计规则：`test-omission-risk-retrospective`。
- 需要沉淀本轮学习与提速：`test-execution-asset-retrospective`。

## 主链路

```text
需求接收 → 来源冻结 → 系统/功能探索 → 需求审核
→ 自动化准备度规划
→ 业务流程与原子断言审核 → 正式用例审核
→ 数据与自动化交接 → 执行前范围/环境/账号/数据复核
→ 执行日志开始登记 → 测试执行 → 问题定性与回归
→ 测试遗漏风险复盘 → 证据化报告 → 执行资产反哺 → 执行日志结束登记
```

问题定性与回归后执行 `OMISSION_RISK_RETROSPECTIVE`，再进入结果回写和报告。该阶段把实际缺陷、用户纠正和测试误判分开处理。

首次且没有有效系统资产时执行全局探索；已有资产时只校验入口、角色、关键控件、版本和数据前置。新环境、新平台或版本变化只探索差异范围。

## 不可跳过的约束

- 区分已确认事实、AI推断、待确认问题和历史信息。
- 提问前先读取系统地图、角色、实体、接口和已有回答，给出候选上下游、影响和建议口径。
- 正式测试用例只有一个审核基线；自动化只引用稳定用例 ID 和内容哈希。
- 需求审核后先形成自动化准备度计划；正式用例审核后绑定稳定用例ID；实际执行前必须再次确认范围、环境、账号角色、fixture和排除项。
- 每次自动化执行在首个测试动作前运行 `ai-test execution-log-start`，登记稳定自动化ID、运行ID、环境、平台、执行作用、目的、范围和用例基线。
- 报告和资产反哺完成后运行 `ai-test execution-log-finish`，登记结束时间、结果、报告、证据和资产变化。开始后中断的运行必须保留，后续标为 `interrupted` 或继续使用同一运行ID收口。
- 人工查看入口固定为项目根目录 `AUTOMATION_EXECUTION_HISTORY.md`；首次执行时间不可被后续回归覆盖，每次运行均须保留。机器状态位于 `.ai-test/execution_history.json`，不得手工维护两份内容。
- 缺账号或数据只阻塞受影响用例并登记一次；相同缺口未变化前不重复尝试，其余已就绪用例继续执行。
- 账号、密码、Cookie、Token、客户数据和私有地址不得写入资产或报告。
- UI单步两分钟无页面、接口、下载、日志或状态进展时，保存证据并报告阻塞。
- 每个阶段输出：`当前完成 / 下一步必须 / 下一步可选 / 推荐动作`。

默认一个测试需求使用一个任务。用户说“接手需求 REQ-XXX”时，先运行 `ai-test work-item-show --root . --requirement-id REQ-XXX` 并读取 `read_first` 返回的全部文件；用户无需复述整套规则。新需求使用 `work-item-create`，进展使用 `work-item-update`。运行状态写入 `.ai-test/work-items/<requirement-id>/`，不得把两个需求写入同一个状态文件。聊天记录只提供上下文。需要确定性检查时运行 `ai-test --help` 选择对应门禁。
