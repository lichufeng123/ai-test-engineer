# agent-device Adapter

agent-device 是默认的 AI-first 移动设备适配器候选。适配器只负责设备会话、可访问性快照、交互、证据和重放；正式预期仍来自已审核用例基线，业务动作保存在项目私有资产中。

## 运行模式

1. 探索：AI 通过 `agent-device mcp` 或 CLI 执行 `open → snapshot → act → verify`。
2. 固化：将审核后的稳定步骤保存为 `.ad` 或 TypeScript Node API 流程。
3. 回归：锁定版本执行 Replay；AI不临时改变业务预期或高风险写操作。
4. 恢复：失败后AI分析快照、截图、日志和Trace，修复候选必须完整重放后才能进入正式资产。

## 版本与能力

- 项目必须固定精确版本，禁止在正式执行中使用 `latest`。
- 先运行 `agent-device doctor` 和 `agent-device capabilities --platform <platform>`。
- 物理iOS、模拟器、Android真机和模拟器分别保存能力回执，不互相推定。
- 页面控件优先使用 accessibility ID、角色、文本和语义选择器。绝对坐标只允许探索或临时恢复。

## 设备与安全

- 真实设备标识、Bundle ID、私有地址和登录信息仅由运行时本机配置提供。
- 手机和外设必须通过框架执行目标及硬件fixture登记；同一资源一次只允许一个运行租用。
- 账号、密码、Cookie、Token、客户数据、设备序列号和UDID不得提交。
- 写操作默认不重试；只能先回读状态，再按 `verify_before_retry` 策略决定。
- 单步120秒没有页面、日志、接口或状态进展时停止并保存现场。

## AI集成

- 交互式探索优先由当前Codex/WorkTony Agent通过MCP或CLI调用，避免嵌套两个自主Agent。
- 独立QA Agent可使用 `agent-device/ai-sdk` 和外部配置的模型。
- 无人值守回归默认使用Replay或Node API，不在每次运行中让模型自由选择写操作。
- 需要用户审批的动作由框架风险目录和AI SDK工具审批共同约束。

## 项目接入

项目私有仓库至少包含：

```text
executors/agent-device/             通用私有执行封装
features/<feature>/mobile_automation/  页面与业务动作
features/<feature>/cross_platform_flows/ 跨App、API与Web计划
runs/<run-id>/                      忽略的证据和回执
```

准备度计划使用：

- `execution_target_requirements`
- `hardware_fixture_requirements`
- `required_execution_target_ids`
- `required_hardware_fixture_ids`

执行前只有通过 `readiness-check` 且完成 `execution-log-start` 后，才允许执行首个App或Web测试动作。
