# 虚构 Playwright 团队样板

此例只用 `page.setContent`，不访问网站、不登录、不写业务。用它验证项目安装和 PO/Flow/Oracle/Test 分层，不得把样例 Case ID 当正式测试基线。

从已经初始化且安装本样板的项目出发，先审查随样板提供的 `package-lock.json`，再在项目内执行 `cd automation/web && npm ci --offline`（仅本机缓存可用时；无缓存要走团队批准的依赖供应链，不自动联网）。需有本机已安装 Edge 或 Chromium。回到项目根目录，先将框架仓库的 `templates/synthetic-run-test-plan.example.md` 复制到 `runs/<RUN-ID>/test-plan.v1.md`，核对范围后运行：

```bash
ai-test synthetic-run-prepare --root . --run-id <RUN-ID> --browser-channel msedge
ai-test guarded-web-run --root . --input runs/<RUN-ID>/guarded-bundle.json
```

第二条命令返回 `review_required` 且退出码 1，表示当轮 reporter 已对账但仍需媒体和隐私语义复核；绝不代表业务通过。缺依赖/浏览器只可做静态检查，不能称已运行 Playwright。直接执行 `npm test` 是开发调试，不产生本框架所需的受控运行回执。

- `pages/`：只封装页面动作、定位和结构化回读，不定义业务预期。
- `flows/`：编排跨页面动作，不选择业务对象或修改 Oracle。
- `oracles/`：从已审核规则和独立输入纯计算预期，错误值必须抛给 Playwright。
- `tests/`：绑定稳定 Case ID、唯一 Fixture、预期、动作与断言；负控确保错误值可令断言失败。
- `evidence/`：记录最小阶段耗时；`checkWithReceipt(testInfo, binding, () => assertResult())` 必须把断言失败重新抛给 Playwright，并附上 run/case/A/fixture/probe/Oracle 哈希，供 `ai-test playwright-receipts-check` 从真实 JSON reporter 自动对账。样板默认零哈希只是纯虚构演示，正式绑定须在运行前提供 `AI_TEST_PROBE_SHA256` 和 `AI_TEST_ORACLE_SHA256`；附件存在不能证明 DOM、业务结果或媒体语义真实。
- `runs/`：Playwright JSON/媒体输出，不入 Git，正式运行须一轮一个新目录。

真实项目必须另行提供：现行知识加载、已审核基线或临时章程、自动化准备度、受控身份/密钥适配器、唯一 Fixture、操作授权、执行日志、连续视频语义审核和逐断言证据。运行后使用 `ai-test automation-outcome-check` 对账真实 Playwright JSON 与逐断言结果；样板运行本身不能证明业务系统已通过。禁止将账号、Cookie、原始请求头或个人信息写入运行文件。
