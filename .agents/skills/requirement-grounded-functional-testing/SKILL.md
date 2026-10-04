---
name: requirement-grounded-functional-testing
description: Use when reviewed requirements, rules, and approved cases must be executed across Web, API, App, H5, or mini-app environments with guarded UI actions, evidence, triage, regression, and reporting.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.8.0"
---

# 需求驱动的功能测试执行

页面现象不是业务预期。操作前先证明理解了需求、规则、状态和数据；执行后用截图、视频、接口、日志或数据回读支撑结论。

## 执行门禁

依次完成：

```text
ASSET_LOAD → ASSET_VALIDATION → SYSTEM_DISCOVERY（必要时）
→ PRE_EXECUTION_CONFIRMATION → EXECUTION_GATE → EXECUTION_LOG_START → TEST_EXECUTION → ISSUE_TRIAGE
→ OMISSION_RISK_RETROSPECTIVE → RESULT_WRITEBACK → REPORT_REPAIR → ASSET_FEEDBACK
→ EXECUTION_LOG_FINISH → COMPLETE
```

开始写操作前必须具备：已审核需求与规则、唯一正式用例基线及哈希、角色/权限、入口、状态机、缓存与持久化、异步窗口、数据方案、范围外事项、风险动作和证据计划。执行前必须对照需求阶段的 `automation_readiness_plan`，重新确认功能、目标环境、适用用例范围、账号角色、fixture和排除项，并生成引用计划哈希的 `pre_execution_confirmation` 与准备度回执。缺失项明确标为阻塞，不能边操作边把猜测当预期。

## 执行规则

权限类用例先读取 [权限测试设计规范](../test-case-generate/references/permission-testing.md)，核对矩阵、上级资格、角色和组织范围。执行确认的生效动作，分别留存页面、跳转、接口拒绝与拒绝后数据未变的证据；设计覆盖回执通过不能代替实际执行通过。

- 首次无系统资产时执行全局探索；稳定资产只做入口、关键控件、角色、数据和版本校验。
- 创建或大幅改写自动化脚本前，必须检索功能目录、Page Object、共享 helper、包命令、执行资产登记和历史运行脚本；对每个候选记录 `reuse`、`extend`、`reject` 或 `supersede` 及依据，并运行 `ai-test automation-asset-reuse-check`。门禁阻塞或缺少回执时不得建立竞争脚本，只能先补齐资产盘点或在既有正式资产上增量修改。
- Web正式回归由Playwright Test执行。新需求默认使用Ego Lite做首轮语义/视觉探索并发现稳定Test ID、Role、Label、DOM和等待条件；Playwright MCP只在需要时辅助生成或复核定位器，不是编写Playwright脚本的依赖；Chrome DevTools MCP负责网络、Console和性能诊断，Stagehand只生成定位器、等待条件和已知瞬态弹窗修复候选。所有候选必须回到Playwright单用例验证与影响回归。运行 `ai-test web-executor-check` 校验分工，禁止AI工具修改正式预期或成为正式回归的自由决策回退。
- 探索的任务是消除下一步脚本化所需的具体未知，并绑定经过校验的正式包代码，而不是连续几轮复用run-local脚本/聊天/方法JSON。首次探索结束或再次执行同功能前运行 `ai-test exploration-handoff-check`，区分 `first_exploration` 与 `repeat_execution`，缺正式包可执行runner、Oracle、测试收据、备份及连续录屏/错误截图计划时重复回归阻塞；应急恢复另行授权，不冒充回归。
- 核心流程在动作前启动连续录屏（正式Playwright用 `video: on` 而非 `retain-on-failure`）；短暂错误提示在可见时即时截图并回读。收口时视频经技术和内容双检查，逐断言人工/受控视觉复核截图是否真的包含目标提示和身份。只证明图片位于章节或DOM另有通知文字，不等于错误提示截图合格；证据缺口单独阻塞，不得事后拼接或盲目重传补拍。
- 正常窗口执行Web测试，建议宽度1920；低于1600的关键截图需补拍。移动端保留真实设备尺寸。
- 缓存相关场景分别验证保留缓存恢复、清缓存起点和服务端资源复用。
- UI单步两分钟无页面、网络、下载、日志或状态进展时停止等待，保留现场并汇报。
- 发生页面或接口错误时，保存脱敏请求、响应、时间、用例ID和可复现cURL到运行目录的 `errors/`；敏感请求头和凭据必须移除。
- 生产写入、删除、金额、库存、真实通知和批量数据按项目授权边界执行。
- 某条用例缺少账号角色、前置状态或测试数据时，只将该用例标为阻塞并登记一次 `missing_prerequisites.json`，随后继续执行其他已就绪用例。相同前置指纹未变化前不得反复登录、刷新、点击或重跑；收到补充数据或角色后只恢复受影响用例。
- 首个自动化动作前运行 `ai-test execution-log-start`，登记稳定自动化ID、唯一运行ID、环境、平台、执行作用、目的、范围和已审核用例基线。不得等测试结束后补猜开始时间。
- 报告、证据和资产反哺完成后运行 `ai-test execution-log-finish`；通过、部分通过、失败、阻塞和中断均须收口。项目根目录 `AUTOMATION_EXECUTION_HISTORY.md` 是固定人工查看入口，`.ai-test/execution_history.json` 为机器状态。

## 证据与结论

每条用例在执行前建立“操作前 → 关键操作 → 结果”的证据清单。保存、刷新、重登、异步完成和下游回读等独立主张需要独立证据。核心业务流程同时保留连续录屏和关键结果截图。

状态只使用：通过、失败、阻塞、未执行及项目审核的其他终态。全部断言验证完成才能标记通过；异常先作为候选问题，排除前置、缓存、旧数据、异步、权限、顺序、环境和脚本因素后再定性。

发布报告前后都运行证据检查并修复图片缺失、仅文件名、错误归位和尺寸问题。视频发布前还要运行第一阶段技术质量门禁；`trim_required` 或 `rerecord_required` 不得按合格视频交付，`blocked` 必须先恢复文件或分析工具。该门禁只检查时长、黑帧和静止区间，不代表页面和测试流程语义审核通过：

```bash
ai-test evidence-check --manifest <evidence.json> --root <run-dir> --report <report.md>
ai-test video-check --input <video-check.json> --root <run-dir> --output <video-receipt.json>
```

问题定性与缺陷回归后先调用 `test-omission-risk-retrospective`，区分实际缺陷、漏测、用户纠正、测试误判和待确认现象；再调用 `test-execution-asset-retrospective` 更新导航、定位、fixture、恢复方式等执行资产，最后更新报告和回执。
