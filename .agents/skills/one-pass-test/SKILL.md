---
name: one-pass-test
description: Use when the user requests one-stop testing that generates readable provisional cases, executes ready cases, and delivers a scenario-level report in one uninterrupted run without repeated formal reviews.
license: MIT
metadata:
  author: ai-test-engineer
  version: "1.0.0"
---

# 一站式测试模式（one_pass）

用户可以直接说“一站式测试 <功能>”。本模式在一个任务和一个运行内完成当前依据恢复 → 临时用例设计 → 向用户展示可读用例 → 数据准备 → 已就绪场景执行 → 独立回读 → 逐用例结果和报告。普通已授权 SIT 写入不需要按每步再次等用户批准；正式产品规则和用例的人审暂缓，结论永远标 `provisional`。它不创建或批准第二套正式用例基线，不做发布/验收放行。

## 进入条件与工作项

- 新需求用 `ai-test work-item-create --test-mode one_pass`；已有需求先 `work-item-show` 并读全 `read_first`，用户明确选择一站式时可 `work-item-update --test-mode one_pass`，保留之前快速/标准运行的真实历史身份。工作项仍按一个需求一个任务，SIT 每次运行独立记录。
- 先加载项目 `AGENTS.md`、`docs/TEST_CONTEXT_INDEX.md` 要求的系统地图、最新决策、当前基线（若有）、全部 `required_reads`（含适用的测试遗漏风险规则）、现有用例/缺陷/Fixture/执行资产。校验知识哈希并实际阅读；时间紧不跳过。产品决定优先于历史脚本或聊天。
- 首个页面/API/设备动作前保存本轮计划包。使用 [one-pass plan schema](../../schemas/one-pass-test-plan.schema.json) 和 [example](../../templates/one-pass-test-plan.example.json) 建临时 `OP-*` 用例；计划包含环境、角色、唯一Fixture、每步操作/原子预期/独立Oracle、证据、允许写入和停止/恢复条件。已批准基线可作来源，但本模式不把临时结果注册为正式Case。
- `ai-test one-pass-check --input <run-plan.json> --root <project> --output <preflight.json>` 检查计划；展示返回的 `case_preview` 和完整逐步用例给用户，然后直接执行已就绪项，无须等待例行审核答复。预期未知/来源未读/身份不唯一/缺独立Oracle的场景只标阻塞，独立可执行的场景继续；临场新发现只生成下一版计划和哈希，不倒改已执行预期。

## 一轮执行与结果

- 已就绪项按风险顺序测试正常、异常、边界、角色/组织、状态变化、重复/并发、写后搜索、导出范围及适用下游；不同机制分别列，不用一个大流程冒充覆盖。普通测试Fixture、UI导入、刷新回读和UI导出只在已指定的SIT范围内执行。真实结算、生产、真实通知、不可逆删除等保留单独授权界限。
- Consequential actions: each step reconfirms preconditions, unique target, expected values, independent Oracle, write budget, evidence, stop point. Unknown submission state: read back first; never blindly retry. Formal Web regression uses Playwright Test; one-pass first exploration may use Ego Lite, but cannot claim formal Playwright regression. New automation assets require复用门禁；自动化首个动作前 `execution-log-start`，报告和反馈后 `execution-log-finish`。
- 用 [results schema](../../schemas/one-pass-test-results.schema.json) 将每个 `OP-*` 及其每步回填 `passed/failed/blocked/not_executed`、实际值和当轮证据；失败按预期/实际/步骤/证据定性，受阻要写具体前置。运行 `ai-test one-pass-check --input <run-plan.json> --results <run-results.json> --root <project> --output <closure.json>`。`status=checked` 仅验证计划哈希、逐ID覆盖、证据文件存在和状态一致，仍须人工语义检查截图与业务Oracle。
- 最终报告与聊天直接列场景/输入/步骤/预期/实际/状态/证据、数据写入和清理、失败/阻塞/未测清单及风险；完整文件只是可追溯入口。逐项登记报告和资产回执，历史通过不得算本轮通过。结论注明“未经正式业务规则和用例审核，不作验收/发布门禁”。

## 转标准流程

发现正式缺陷、规则冲突、关键链路缺口，或需要验收、发布和重复正式回归时，把本轮证据作为审核输入，按原需求工作项完成需求/业务规则/Current/唯一正式用例基线审核、Fixture与自动化准备度，再由正式执行器运行；不得把 `OP-*` 改名为已审核 `TC-*` 或凭一站式脚本绿灯放行。没有上述目标时，本轮可以以有边界的 provisional 报告收口，未测项明确责任和续测前置。
