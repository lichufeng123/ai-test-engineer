# Ego Lite Adapter

Ego Lite 是新Web需求首轮探索的默认工具，并负责复用人工登录态、语义/视觉兜底和失败现场复核。基准测试显示它适合探索与自愈，但不替代Playwright Test的高频稳定回归。

## 职责

- 在隔离task space中复用用户登录态并避免干扰用户普通浏览器窗口。
- 优先使用 `snapshotText()` 和语义ref；复杂视觉页面使用截图与坐标；必要时使用CDP。
- 首轮直接发现页面流程、状态、稳定Test ID/Role/Label和等待条件；需要独立语义复核时再选择Playwright MCP。
- 提取入口、状态、控件和定位器候选，最终固化到Playwright资产。

## 会话规则

- 本轮 SIT 目标功能、账号候选、角色和组织范围在登录前一次性确定：先查经审核账号/Fixture 台账，再看现有浏览器会话是否仍匹配；没有唯一候选才问用户，不能临登录才拿历史显示名猜账号。聊天里不询问或回显密码。
- 一个用户目标复用同一个task space，并优先复用可核验的登录态；有登录态无需人工 handoff。
- 确需人工登录、验证码或人工确认时先调用 handoff，且只有返回 `done: true` 才请用户在该空间操作；交接后用户明确说“继续”时 `takeOverTaskSpace` 并核验账号/角色/组织。若空间原本为用户持有，须等用户明确说继续，再 `listTaskSpaces → claimTaskSpace(id) → listTabs/切回原 tab`，不能对用户持有空间重复 handoff 或再要求另一句“已登录”。`UI not available` 表示本次交接/接管未成功，不能要求用户在不可见空间登录或宣称恢复控制。
- 完成后关闭task space，除非用户明确要求保留现场。
- 单步120秒无页面、网络、日志或状态进展时停止并保留现场。

## 安全与执行边界

- 不在脚本、输出、报告中记录密码、Cookie、Token或私有地址；如需追溯账号，仅留非敏感别名、角色和组织范围。
- 写操作前必须通过执行门禁；收款、通知、删除和批量写入需要额外明确授权。
- snapshot ref只服务当前快照，不直接成为长期Playwright定位器。
- Ego Lite发现页面变化后只提出修复候选，正式通过状态由Playwright重跑确认。

## 已验证定位

适合顺序：`task space → open/reuse tab → snapshot → act → verify → handoff/complete`。正式回归中已有稳定定位器时继续优先Playwright。
