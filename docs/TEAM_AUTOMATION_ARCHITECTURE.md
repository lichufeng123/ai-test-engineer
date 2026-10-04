# 团队自动化架构与结果对账（首轮可交付范围）

本指南连接现有的需求/业务断言/唯一用例基线、自动化准备度、执行计划、Playwright 结果与报告。它不把公开框架变成伊智业务知识库，也不以“脚本绿灯”代替业务正确性。

## 用例生成到执行的主链

1. 先按 `AGENTS.md` 与 `docs/TEST_CONTEXT_INDEX.md` 读取当前业务知识、审核需求、业务流程/原子断言、遗漏风险和正式用例基线；快速模式只用临时章程与探针，不创建第二套用例基线。`flow-check`、`case-granularity-check` 和适用的 `permission-check` 在用例审核前运行。
2. 需求审核后准备 `automation_readiness_plan`，用例审核后绑定稳定 Case ID、Fixture、环境、证据并冻结哈希；执行前运行 `readiness-check`。缺角色、数据或独立 Oracle 时只阻塞依赖用例，不为求绿跳过断言。
3. 自动化代码增量开发前运行 `automation-asset-reuse-check`；探索移交后通过 `exploration-handoff-check`，而不是复制临场脚本。
4. 正式运行前登记 `execution-log-start`。Playwright 的单条业务断言必须直接抛出失败，不允许记录失败后静默 `return false`。保存真实 JSON reporter、受控的 Oracle/写前 Fixture、逐断言原始证据；业务写入和隐私边界仍按项目计划执行。
5. 运行后用本页的 `automation-outcome-check` 对账，再完成媒体语义审核、缺陷分诊、结果/报告写回、遗漏风险与执行资产复盘及 `execution-log-finish`。对账通过不等于正式验收；其后还要审核产品预期、实际画面和运行身份。

## Web 分层边界

`ai-test playwright-scaffold --root <project>` 会在 `automation/web/` 安装一个虚构的本地计数器例子；如果任一目标文件已存在，整次安装阻塞，不覆盖团队代码。样板依赖首次 `npm install` 和本机 Chromium 下载，框架本身不负责安装依赖。纯示例不访问真实系统。真实项目至少维持以下边界：

| 层 | 负责 | 不负责 |
| --- | --- | --- |
| `pages/` | 稳定定位、用户动作、带类型的页面读取 | 权威预期、文件导出解析、报告通过结论 |
| `flows/` | 一个业务动作链的有序编排 | 选择任意目标或事后放宽预期 |
| `oracles/` | 从已审核规则、独立输入和固定 Fixture 纯计算预期 | 读取被测页面后反推正确值 |
| `fixtures/` | 唯一身份、来源、生命周期、状态与清理 | 共用“最新一条”、复用已消耗记录 |
| `tests/` | 一个稳定 Case ID 的前置、动作、直接断言、反例 | 串接多个历史运行补丁并吞掉断言失败 |
| 项目适配器 | 身份、环境、设备及下载等平台接入 | 在公开框架硬编码组织、私有地址或秘钥 |
| 取证与报告 | 记录阶段耗时、按断言绑定的脱敏原始证据 | 仅凭附件路径判产品通过 |

样板用 `page.setContent`，可用来检查分层与错误值会触发失败；不是任何真实 UI 功能的端到端验证。Playwright 中使用 `testInfo.attach` 保存最小、脱敏、可追溯附件；正式核心流程仍须按项目策略持续录屏并检查画面内容。不要将 Playwright trace、原始网络头或 storage state 自动上传；先经隐私审计。

## 结果对账门禁

输入参考 `templates/automation-outcome.example.json`，将所有零哈希替换为本轮实际文件 SHA-256，并在同一项目根目录放好文件；`standard` 引用唯一已审核的完整用例文件（至少含 `baseline_id`、`cases[].id` 和 `cases[].covered_rule_ids`），门禁核对每个 Case/Assertion ID 属于该基线，并要求本轮声称覆盖的用例列齐其 `covered_rule_ids`；不接受只含路径的基线指针；`rapid` 引用临时章程（在输入中标 `provisional`），不要求正式 Case ID。`test_title` 必须与本轮 Playwright JSON reporter 中唯一的测试标题一致，文件必须是同一源文件相对 reporter `config.rootDir` 的路径；当前门禁不处理跨机器的源码路径重映射。Playwright 报告和结果证据的相对路径必须包含本轮 `run_id` 目录，防止误拿旧运行文件；对每个原子断言登记 Oracle 文件、Fixture ID、声明结果及证据文件/内容复核状态。

```bash
ai-test automation-outcome-check \
  --input runs/RUN-001/automation-outcome.json \
  --root . \
  --output runs/RUN-001/automation-outcome-receipt.json
```

返回 `passed` 仅表示计划/结果/真实 JSON 报告与引用文件的局部一致性；`failed` 只表示有已记录的失败断言且 Playwright 也失败，不自动证明产品缺陷；`blocked` 包括缺文件、身份/哈希不符、断言缺回执、媒体未人工/受控语义复核、Playwright 失败或跳过却宣称通过，以及“断言失败却被脚本吞掉使 Playwright 仍绿”。非通过状态命令以非零退出，可用于 CI 阻止发布“全部通过”的报告。

这个门禁不能独立判断业务规则是否真经审核、Fixture 身份是否真实、视频是否真的拍到结论、证据是否伪造，也不能证明 Playwright 执行时源文件一定等于事后哈希；需要工作项的审核回执、运行前后代码/环境哈希和独立证据审计补足。不可将它的 `passed` 直接写成产品通过。

## 性能与团队推广后续工作

保留同一隔离 Fixture 内共享的认证准备，但每例复核角色/组织/版本；用条件等待替代固定 sleep；只对无共享写入且有独立夹具的场景并行。样板的 `evidence/phaseTiming.ts` 演示 `Fixture → 导航 → 动作 → 断言` 的耗时附件，但尚不覆盖登录、浏览器启动、媒体和报告处理；这些阶段须结合 Playwright reporter 总耗时另行测量。一次本地虚构样板运行的两项测试共约31秒、单例约0.4秒，不能据此推断真实业务耗时。优化不能以关闭独立 Oracle 或录屏为代价。跨平台密钥适配、自动从团队用例库导入逐条断言、真实 UI/设备完整回归仍是后续团队迭代。
