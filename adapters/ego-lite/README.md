# Ego Lite Adapter

Ego Lite 是新Web需求首轮探索的默认工具，并负责复用人工登录态、语义/视觉兜底和失败现场复核。基准测试显示它适合探索与自愈，但不替代Playwright Test的高频稳定回归。

## 职责

- 在隔离task space中复用用户登录态并避免干扰用户普通浏览器窗口。
- 优先使用 `snapshotText()` 和语义ref；复杂视觉页面使用截图与坐标；必要时使用CDP。
- 首轮直接发现页面流程、状态、稳定Test ID/Role/Label和等待条件；需要独立语义复核时再选择Playwright MCP。
- 提取入口、状态、控件和定位器候选，最终固化到Playwright资产。

## 会话规则

- 一个用户目标复用同一个task space。
- 登录、验证码或人工确认使用handoff；只有用户明确继续后才能take over。
- 完成后关闭task space，除非用户明确要求保留现场。
- 单步120秒无页面、网络、日志或状态进展时停止并保留现场。

## 安全与执行边界

- 不在脚本、输出、报告中记录账号、密码、Cookie、Token或私有地址。
- 写操作前必须通过执行门禁；收款、通知、删除和批量写入需要额外明确授权。
- snapshot ref只服务当前快照，不直接成为长期Playwright定位器。
- Ego Lite发现页面变化后只提出修复候选，正式通过状态由Playwright重跑确认。

## 已验证定位

适合顺序：`task space → open/reuse tab → snapshot → act → verify → handoff/complete`。正式回归中已有稳定定位器时继续优先Playwright。
