# Web AI浏览器工具栈

## 1. 固定分工

Web正式回归只有一个执行器：Playwright Test。Playwright MCP、Chrome DevTools MCP、Ego Lite和Stagehand是探索、诊断与修复工具，不建立第二套正式用例，不改变已审核预期。

| 阶段 | 主工具 | 兜底 | 产物 |
|---|---|---|---|
| 新需求首轮探索 | Ego Lite执行；Jev配置时提供有限只读建议 | Jev不可用/低置信/无进展时停止建议循环，Ego Lite可继续；若实际浏览器执行器无法控制窗口，只阻塞需要 UI 的步骤并记录连接错误 | 页面状态、登录态、已配置时的建议收据、稳定Test ID/Role/Label、DOM线索、等待条件与风险动作 |
| Playwright定位辅助 | Playwright MCP（可选） | Ego Lite、DOM/CDP、Inspector/Codegen、DevTools | Playwright定位器或复核结果；未安装也不阻塞脚本编写 |
| 失败诊断 | Chrome DevTools MCP | Ego Lite | 脱敏网络、Console、性能和页面现场 |
| 定位自愈 | Stagehand | Ego Lite、Playwright MCP | 最小修复候选，禁止改预期 |
| 正式回归 | Playwright Test | 无AI执行器回退 | 绑定Case ID和基线哈希的结果、Trace、截图、视频与报告 |

## 2. 新需求流程

```text
已审核需求/规则/用例（快速测试按rapid-test临时章程）
→ 加载系统地图、已审核业务规则、遗漏风险及可复用资产
→ 从已审核账号/Fixture 索引选定唯一非敏感账号别名、角色和组织范围；检查可复用登录态
→ 自动化准备度与执行前确认（快速测试使用逐探针冻结）
→ 已认证则核验身份并继续；需人工登录则成功 handoff → 用户登录并明确交还 → take over 核验身份
→ Ego Lite观察页面 → Jev已配置时从有限只读候选动作中建议 → Ego Lite执行并回读
→ 按需使用Playwright MCP、DOM/CDP、Inspector/Codegen或DevTools生成/复核定位器
→ 生成并审查Playwright定位器与Page Object
→ Playwright Test单用例验证
→ Playwright Test正式回归
```

Jev不是浏览器执行器或Oracle：仅可从调用方提供的有限只读候选中选择，不能生成任意JavaScript、选择器、URL或业务目标；完整页面快照留在本地，仅传最小脱敏观察摘要。低置信、Provider错误、无进展或证据不足时停止，不自动重试。探索收据固定为 `advisory_only`，正式结论只能来自审核基线、独立Oracle和确定性执行器。

探索时允许读取页面、网络和状态；用户指定 SIT 功能测试时，隔离 Fixture 的常规 UI 提交、文件导入和导出属于任务范围，不必逐次再确认。生产、真实收款/结算、真实通知、超范围删除及不可逆写入单独判断；未知提交终态先回读，不自动重传。

### SIT 登录与控制权分流

SIT 功能测试授权覆盖本任务内的正常登录和隔离 Fixture 操作，登录前只需确认一次账号身份与凭据入口，不把“批准测试”“账号选定”“已有登录态”“浏览器交接完成”混为一件事。账号别名应来自受审台账，历史运行只能提供候选；若有多个或零个符合本轮角色/组织的账号，在登录前一次性确认。不得在聊天或报告中索要、回显密码或 Cookie。

| 实际状态 | 下一步 |
| --- | --- |
| 同一任务空间已认证，且角色和组织匹配 | 直接继续，复用登录态，不询问登录许可。 |
| 无会话，但批准的运行时凭据可用 | 走已有受控登录入口；登录后核验账号、角色和组织。 |
| 只能由用户输入验证码/密码 | 先调用 `handOffTaskSpace`；仅 `done: true` 时告知用户在该任务空间完成登录，用户明确说继续后 `takeOverTaskSpace` 并核验身份。 |
| 已 handoff 给用户，且用户明确表示继续 | 调用 `takeOverTaskSpace` 并核验实际账号、角色和组织；不再索取第二句“已登录”。 |
| 任务空间原本由用户持有 | 未收到明确继续时停止浏览器操作；收到明确继续后先查 `listTaskSpaces`，用 `claimTaskSpace(id)` 接管并选择原 tab，核验身份，不把 `handOffTaskSpace` 当成接管动作。 |
| handoff/接管返回 `UI not available` | 该动作未完成；不要让用户去不可用任务空间登录，也不要宣称已接管。记录工具错误并停止该空间的浏览器动作；若已经收到继续确认，可核实空间所有权并按上面对应方法恢复，仍不可用时只标记受影响的 UI 步骤阻塞。 |

若登录态过期，仅为实际新登录做一次交接，不重新询问是否允许执行原 SIT 测试。不得借其他任务空间/浏览器绕过用户当前持有的控制权。

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
- Ego Lite负责首轮观察、认证复用、候选动作实际执行和回读。
- 首轮发现路由的主工具是 `ego-lite`；可选的 `jev-advisor` 只提供受限只读候选动作建议，不替代Ego Lite执行或正式裁决。未配置 Jev 时不要求占位策略；配置但不可用时停止建议并标示其状态，实际执行器仍可继续。
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
