# Playwright MCP Adapter

Playwright MCP 是可选的Playwright定位器生成与复核工具，不是新需求首轮探索的强制入口，也不是第二套正式回归执行器。首轮探索默认使用Ego Lite；即使没有安装Playwright MCP，也可以根据Ego Lite语义快照、DOM/CDP、Playwright Inspector/Codegen、浏览器DevTools和现有Test ID编写Playwright脚本。正式结果仍由锁定版本的 `@playwright/test`、已审核Case ID和基线哈希产生。

## 职责

- 在需要二次语义复核时使用accessibility snapshot识别页面、表单、Tab、表格、弹窗与状态。
- 可选生成或验证 `getByRole`、`getByTestId`、`getByLabel` 等稳定Playwright定位器。
- 在探索后输出入口、前置、等待条件、瞬态UI、网络观察点和证据计划。
- 定位器修复后交给Playwright Test执行单用例验证和影响回归。

## 禁止边界

- 不修改正式预期、业务规则、Case ID或基线哈希。
- 不把snapshot ref直接固化为长期Playwright选择器。
- 不保存密码、Cookie、Token或含认证信息的storage state到仓库。
- 不在没有执行门禁与授权时执行提交、收款、通知、删除或批量写入。

## 接入

项目应固定精确版本，不在正式环境使用 `latest`：

```json
{
  "command": "npx",
  "args": ["@playwright/mcp@<exact-version>"]
}
```

需要复用已有Chrome登录态时优先使用官方扩展或受控CDP连接；使用独立测试Profile，并让浏览器明确提示与批准连接。探索结束后把稳定动作写回项目Page Object或fixture，不保留自由Agent作为CI断言来源。

## 输出资产

- 页面语义快照摘要和稳定定位器候选。
- 入口、角色、状态、fixture与等待条件。
- Playwright补丁候选及对应Case ID。
- 失败现场与修复后单用例/影响回归回执。
