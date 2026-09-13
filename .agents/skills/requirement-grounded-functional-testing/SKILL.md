---
name: requirement-grounded-functional-testing
description: Use when reviewed requirements, rules, and approved cases must be executed across Web, API, App, H5, or mini-app environments with guarded UI actions, evidence, triage, regression, and reporting.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.4.0"
---

# 需求驱动的功能测试执行

页面现象不是业务预期。操作前先证明理解了需求、规则、状态和数据；执行后用截图、视频、接口、日志或数据回读支撑结论。

## 执行门禁

依次完成：

```text
ASSET_LOAD → ASSET_VALIDATION → SYSTEM_DISCOVERY（必要时）
→ EXECUTION_GATE → TEST_EXECUTION → ISSUE_TRIAGE
→ RESULT_WRITEBACK → REPORT_REPAIR → ASSET_FEEDBACK → COMPLETE
```

开始写操作前必须具备：已审核需求与规则、唯一正式用例基线及哈希、角色/权限、入口、状态机、缓存与持久化、异步窗口、数据方案、范围外事项、风险动作和证据计划。缺失项明确标为阻塞，不能边操作边把猜测当预期。

## 执行规则

- 首次无系统资产时执行全局探索；稳定资产只做入口、关键控件、角色、数据和版本校验。
- Web稳定回归优先DOM/API自动化，Computer Use用于探索、原生弹窗和无法直接驱动的控件。小程序业务链路使用对应自动化框架，云真机和随机测试分别承担兼容/性能与稳定性冒烟。
- 正常窗口执行Web测试，建议宽度1920；低于1600的关键截图需补拍。移动端保留真实设备尺寸。
- 缓存相关场景分别验证保留缓存恢复、清缓存起点和服务端资源复用。
- UI单步两分钟无页面、网络、下载、日志或状态进展时停止等待，保留现场并汇报。
- 发生页面或接口错误时，保存脱敏请求、响应、时间、用例ID和可复现cURL到运行目录的 `errors/`；敏感请求头和凭据必须移除。
- 生产写入、删除、金额、库存、真实通知和批量数据按项目授权边界执行。

## 证据与结论

每条用例在执行前建立“操作前 → 关键操作 → 结果”的证据清单。保存、刷新、重登、异步完成和下游回读等独立主张需要独立证据。核心业务流程同时保留连续录屏和关键结果截图。

状态只使用：通过、失败、阻塞、未执行及项目审核的其他终态。全部断言验证完成才能标记通过；异常先作为候选问题，排除前置、缓存、旧数据、异步、权限、顺序、环境和脚本因素后再定性。

发布报告前后都运行证据检查并修复图片缺失、仅文件名、错误归位和尺寸问题：

```bash
ai-test evidence-check --manifest <evidence.json> --root <run-dir> --report <report.md>
```

结束时调用 `test-execution-asset-retrospective`，更新执行资产、报告和回执。
