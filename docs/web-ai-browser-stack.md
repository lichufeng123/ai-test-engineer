# Web AI浏览器工具栈

## 1. 固定分工

Web正式回归只有一个执行器：Playwright Test。Playwright MCP、Chrome DevTools MCP、Ego Lite和Stagehand是探索、诊断与修复工具，不建立第二套正式用例，不改变已审核预期。

| 阶段 | 主工具 | 兜底 | 产物 |
|---|---|---|---|
| 新需求首次探索 | Ego Lite | 无 | 页面状态、登录态、稳定Test ID/Role/Label、DOM线索、等待条件与风险动作 |
| Playwright定位辅助 | Playwright MCP（可选） | Ego Lite、DOM/CDP、Inspector/Codegen、DevTools | Playwright定位器或复核结果；未安装也不阻塞脚本编写 |
| 失败诊断 | Chrome DevTools MCP | Ego Lite | 脱敏网络、Console、性能和页面现场 |
| 定位自愈 | Stagehand | Ego Lite、Playwright MCP | 最小修复候选，禁止改预期 |
| 正式回归 | Playwright Test | 无AI执行器回退 | 绑定Case ID和基线哈希的结果、Trace、截图、视频与报告 |

## 2. 新需求流程

```text
已审核需求/规则/用例
→ 自动化准备度与执行前确认
→ Ego Lite首轮语义/视觉探索并复用人工登录态
→ 按需使用Playwright MCP、DOM/CDP、Inspector/Codegen或DevTools生成/复核定位器
→ 生成并审查Playwright定位器与Page Object
→ Playwright Test单用例验证
→ Playwright Test正式回归
```

探索时允许读取页面、网络和状态；提交、收款、通知、删除、覆盖、批量写入等动作只有在用例已审核、fixture已确认且用户明确授权后才能执行。

## 3. 失败与自愈流程

```text
Playwright失败
→ 保存Trace、截图、视频、网络和当前状态
→ Chrome DevTools MCP判断网络/Console/性能/缓存因素
→ Ego Lite复核真实登录态与视觉现场（按需）
→ Stagehand只生成定位器、等待或已知弹窗修复候选
→ 代码审查
→ Playwright单用例验证与影响回归
```

Stagehand和其他AI工具不得修改预期结果、业务规则、权限边界、Case ID、基线哈希或删除断言。写操作默认不重试，必须先回读服务端状态再决定安全恢复。

## 4. 路由门禁

项目复制并修改 `templates/web-executor-routing.example.json`，然后执行：

```bash
ai-test web-executor-check \
  --input runs/latest/web-executor-routing.json \
  --output runs/latest/web-executor-routing-receipt.json
```

门禁检查：

- 正式执行器必须是 `playwright-test`。
- 正式回归不能回退到自由Agent执行器。
- Ego Lite负责首轮探索、认证复用和语义/视觉兜底。
- Playwright MCP只负责可选的Playwright定位器生成与复核，不得成为脚本编写前置条件。
- Chrome DevTools MCP负责诊断。
- Stagehand修复必须回到Playwright验证。
- 已可用工具必须锁定精确版本。
- 配置不得包含密码、Token、Cookie、密钥或认证载荷。

`passed_with_pending_tools` 表示路由契约有效，但仍有工具尚未安装或完成能力检查；它不等于执行门禁已经通过。

## 5. 安全配置

- 账号、密码、Cookie、Token、storage state和模型Key只通过本机安全配置或密钥系统提供。
- 内部页面默认本地执行；使用Stagehand或其他云浏览器前先完成数据与网络合规审批。
- Chrome DevTools MCP使用独立Profile、敏感请求头脱敏和内部域名allowlist；内部性能分析关闭CrUX。
- 浏览器认证文件必须被Git忽略并限制文件权限，不作为普通测试资产上传。
- 页面、网络和截图中的客户数据按证据最小化原则脱敏。

## 6. Playwright资产接收标准

探索或自愈只有同时满足以下条件才可进入稳定资产：

1. 引用稳定Case ID和已审核基线哈希。
2. 使用角色、Label、Test ID或稳定业务属性，不固化临时ref或坐标。
3. 明确账号角色、服务端数据、缓存、异步等待和清理策略。
4. 写操作具备幂等或状态回读，不盲目重试。
5. 失败证据、修复补丁、单用例验证和影响回归齐全。
6. 没有凭据、私有认证载荷或不必要的客户数据。
